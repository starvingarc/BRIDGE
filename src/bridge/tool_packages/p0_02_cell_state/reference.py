from __future__ import annotations

import hashlib
import json
import os
from importlib.resources import files
from pathlib import Path
from typing import Any

import anndata as ad
import numpy as np
import yaml
from scipy import sparse

from bridge.tool_packages.p0_01_input_qc.io import sha256_path
from bridge.toolkit.contracts import (
    AnnotationVocabulary,
    MarkerProgramCard,
    ReferenceManifest,
    ReferenceProfile,
)


class ReferenceError(ValueError):
    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(detail)
        self.reason_code = reason_code


DENIED_SOURCE_FAMILIES = frozenset(
    {"STUDER", "CAPYBARABRAIN", "STUDER_CAPYBARABRAIN", "EMTAB14729", "E-MTAB-14729"}
)


def load_packaged_vocabulary() -> AnnotationVocabulary:
    payload = yaml.safe_load(
        files("bridge.tool_packages.p0_02_cell_state.resources")
        .joinpath("annotation_vocabulary.yaml")
        .read_text(encoding="utf-8")
    )
    return AnnotationVocabulary.model_validate(payload)


def load_packaged_marker_programs() -> tuple[dict[str, Any], list[MarkerProgramCard]]:
    payload = yaml.safe_load(
        files("bridge.tool_packages.p0_02_cell_state.resources")
        .joinpath("marker_programs.yaml")
        .read_text(encoding="utf-8")
    )
    cards = [MarkerProgramCard.model_validate(item) for item in payload.pop("cards")]
    return payload, cards


def build_reference_snapshot(catalog_path: Path, output_dir: Path) -> ReferenceManifest:
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    required = {"snapshot_id", "version", "status", "measurement_spec_ids", "sources"}
    missing = sorted(required - set(catalog))
    if missing:
        raise ReferenceError("reference_catalog_incomplete", ", ".join(missing))

    vocabulary = _load_vocabulary(catalog.get("vocabulary_path"))
    marker_header, marker_cards = _load_marker_programs(catalog.get("marker_program_path"))
    prohibited = sorted(set(catalog.get("prohibited_source_families", [])) | DENIED_SOURCE_FAMILIES)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ReferenceError("reference_snapshot_already_exists", catalog["snapshot_id"])
    output_dir.mkdir(parents=True, exist_ok=True)
    profile_dir = output_dir / "profiles"
    profile_dir.mkdir(exist_ok=True)

    vocabulary_path = output_dir / "annotation_vocabulary.json"
    marker_path = output_dir / "marker_programs.json"
    _write_json(vocabulary_path, vocabulary.model_dump(mode="json"))
    _write_json(
        marker_path,
        {**marker_header, "cards": [card.model_dump(mode="json") for card in marker_cards]},
    )

    profiles = [
        _build_source_profile(source, vocabulary, marker_cards, profile_dir, prohibited)
        for source in sorted(catalog["sources"], key=lambda item: item["source_id"])
    ]
    manifest = ReferenceManifest(
        snapshot_id=catalog["snapshot_id"],
        version=str(catalog["version"]),
        status=catalog["status"],
        vocabulary_file=vocabulary_path.name,
        vocabulary_sha256=sha256_path(vocabulary_path),
        marker_program_file=marker_path.name,
        marker_program_sha256=sha256_path(marker_path),
        measurement_spec_ids=sorted(catalog["measurement_spec_ids"]),
        profiles=profiles,
        prohibited_source_families=prohibited,
    )
    _write_json(output_dir / "reference_manifest.json", manifest.model_dump(mode="json"))
    return validate_reference_snapshot(output_dir)


def validate_reference_snapshot(root: Path) -> ReferenceManifest:
    manifest_path = root / "reference_manifest.json"
    if not manifest_path.is_file():
        raise ReferenceError("reference_manifest_not_found", root.name)
    manifest = ReferenceManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    _check_artifact(root, manifest.vocabulary_file, manifest.vocabulary_sha256)
    _check_artifact(root, manifest.marker_program_file, manifest.marker_program_sha256)
    source_ids: set[str] = set()
    profile_ids: set[str] = set()
    evidence_slots: set[tuple[str, str, str, str]] = set()
    for profile in manifest.profiles:
        if profile.source_id in source_ids:
            raise ReferenceError("duplicate_reference_source", profile.source_id)
        if profile.profile_id in profile_ids:
            raise ReferenceError("duplicate_reference_profile", profile.profile_id)
        source_ids.add(profile.source_id)
        profile_ids.add(profile.profile_id)
        slot = (profile.evidence_family_id, profile.assay, profile.label_level, profile.role)
        if profile.matrix_file and profile.role in {"primary", "refinement"}:
            if slot in evidence_slots:
                raise ReferenceError("duplicate_active_evidence_family", ":".join(slot))
            evidence_slots.add(slot)
        if profile.source_family_id in manifest.prohibited_source_families and profile.matrix_file:
            raise ReferenceError("prohibited_reference_source_family", profile.source_family_id)
        if bool(profile.matrix_file) != bool(profile.metadata_file):
            raise ReferenceError("incomplete_reference_profile_artifacts", profile.profile_id)
        if profile.matrix_file:
            _check_artifact(root, profile.matrix_file, profile.matrix_sha256)
            _check_artifact(root, profile.metadata_file or "", profile.metadata_sha256)
            matrix = np.load(root / profile.matrix_file, allow_pickle=False)
            metadata = json.loads((root / (profile.metadata_file or "")).read_text(encoding="utf-8"))
            if matrix.shape != (len(metadata["rows"]), len(metadata["genes"])):
                raise ReferenceError("reference_profile_shape_mismatch", profile.profile_id)
    return manifest


def validate_runtime_reference(manifest: ReferenceManifest) -> None:
    if not DENIED_SOURCE_FAMILIES.issubset(set(manifest.prohibited_source_families)):
        raise ReferenceError("reference_denylist_incomplete", manifest.snapshot_id)
    if manifest.status != "frozen" and os.environ.get("BRIDGE_ALLOW_CANDIDATE_REFERENCES") != "1":
        raise ReferenceError("reference_snapshot_not_frozen", manifest.snapshot_id)


def resolve_reference_snapshot(snapshot_id: str) -> Path:
    root_value = os.environ.get("BRIDGE_REFERENCE_ROOT")
    if not root_value:
        raise ReferenceError("reference_root_not_configured", "BRIDGE_REFERENCE_ROOT is not set")
    root = Path(root_value).expanduser().resolve() / snapshot_id
    if not root.is_dir():
        raise ReferenceError("reference_snapshot_not_found", snapshot_id)
    return root


def load_snapshot_resources(
    root: Path,
) -> tuple[ReferenceManifest, AnnotationVocabulary, list[MarkerProgramCard]]:
    manifest = validate_reference_snapshot(root)
    vocabulary = AnnotationVocabulary.model_validate_json(
        (root / manifest.vocabulary_file).read_text(encoding="utf-8")
    )
    marker_payload = json.loads((root / manifest.marker_program_file).read_text(encoding="utf-8"))
    cards = [MarkerProgramCard.model_validate(item) for item in marker_payload["cards"]]
    return manifest, vocabulary, cards


def load_reference_profile(root: Path, profile: ReferenceProfile) -> tuple[np.ndarray, dict[str, Any]]:
    if not profile.matrix_file or not profile.metadata_file:
        raise ReferenceError("reference_profile_unavailable", profile.profile_id)
    return (
        np.load(root / profile.matrix_file, allow_pickle=False),
        json.loads((root / profile.metadata_file).read_text(encoding="utf-8")),
    )


def _build_source_profile(
    source: dict[str, Any],
    vocabulary: AnnotationVocabulary,
    marker_cards: list[MarkerProgramCard],
    output_dir: Path,
    prohibited: list[str],
) -> ReferenceProfile:
    family = source["source_family_id"]
    if family in prohibited:
        raise ReferenceError("prohibited_reference_source_family", family)
    common = {
        "profile_id": source.get("profile_id", f"PROFILE-{source['source_id']}"),
        "source_id": source["source_id"],
        "source_family_id": family,
        "evidence_family_id": source["evidence_family_id"],
        "assay": source["assay"],
        "anatomy": source["anatomy"],
        "developmental_time": source["developmental_time"],
        "label_level": source["label_level"],
        "role": source["role"],
        "status": source.get("status", "candidate"),
    }
    asset_path = source.get("asset_path")
    if not asset_path:
        return ReferenceProfile(**common)
    path = Path(asset_path).expanduser().resolve()
    if not path.is_file() or path.suffix != ".h5ad":
        raise ReferenceError("reference_asset_not_found", source["source_id"])

    adata = ad.read_h5ad(path)
    mask = np.ones(adata.n_obs, dtype=bool)
    for column, expected in source.get("filters", {}).items():
        if column not in adata.obs:
            raise ReferenceError("reference_filter_column_not_found", f"{source['source_id']}:{column}")
        allowed = {str(item) for item in expected} if isinstance(expected, list) else {str(expected)}
        mask &= adata.obs[column].astype(str).isin(allowed).to_numpy()
    if not mask.any():
        raise ReferenceError("reference_filter_empty", source["source_id"])

    label_column = source["label_column"]
    sample_column = source["sample_column"]
    if label_column not in adata.obs or sample_column not in adata.obs:
        raise ReferenceError("reference_metadata_column_not_found", source["source_id"])
    matrix = _select_matrix(adata, source.get("matrix_location", "X"))[mask]
    genes = _gene_names(adata, source.get("gene_symbol_column"))
    labels, excluded = _map_labels(
        adata.obs.loc[mask, label_column].astype(str).to_numpy(),
        source.get("label_map", {}),
        vocabulary,
        source["label_level"],
    )
    samples = adata.obs.loc[mask, sample_column].astype(str).to_numpy()
    keep = np.array([label is not None for label in labels])
    if not keep.any():
        raise ReferenceError("reference_has_no_resolved_labels", source["source_id"])
    matrix = matrix[keep]
    samples = samples[keep]
    resolved_labels = np.asarray([label for label in labels if label is not None])
    profiles, rows = _pseudobulk(
        matrix,
        samples,
        resolved_labels,
        source.get("matrix_semantics", "normalized_expression"),
    )
    profiles, genes, feature_policy = _select_features(
        profiles,
        genes,
        rows,
        marker_cards,
        int(source.get("max_features", 2000)),
    )

    safe_id = _safe_id(common["profile_id"])
    matrix_path = output_dir / f"{safe_id}.npy"
    metadata_path = output_dir / f"{safe_id}.json"
    np.save(matrix_path, profiles.astype(np.float32), allow_pickle=False)
    _write_json(metadata_path, {"genes": genes.tolist(), "rows": rows})
    return ReferenceProfile(
        **common,
        n_samples=len(set(samples)),
        n_observations=int(keep.sum()),
        n_genes=len(genes),
        labels=sorted(set(resolved_labels)),
        matrix_file=matrix_path.relative_to(output_dir.parent).as_posix(),
        matrix_sha256=sha256_path(matrix_path),
        metadata_file=metadata_path.relative_to(output_dir.parent).as_posix(),
        metadata_sha256=sha256_path(metadata_path),
        source_sha256=sha256_path(path),
        feature_selection=feature_policy,
        exclusions=excluded,
    )


def _load_vocabulary(path: str | None) -> AnnotationVocabulary:
    if path is None:
        return load_packaged_vocabulary()
    return AnnotationVocabulary.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def _load_marker_programs(path: str | None) -> tuple[dict[str, Any], list[MarkerProgramCard]]:
    if path is None:
        return load_packaged_marker_programs()
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    cards = [MarkerProgramCard.model_validate(item) for item in payload.pop("cards")]
    return payload, cards


def _select_matrix(adata: ad.AnnData, location: str):
    if location == "X":
        return adata.X
    if location.startswith("layers/") and location[7:] in adata.layers:
        return adata.layers[location[7:]]
    raise ReferenceError("reference_matrix_location_not_found", location)


def _gene_names(adata: ad.AnnData, column: str | None) -> np.ndarray:
    values = adata.var_names if column is None else adata.var[column]
    genes = np.asarray([str(value).strip().upper() for value in values])
    if len(set(genes)) != len(genes):
        raise ReferenceError("reference_gene_ids_not_unique_after_normalization", column or "var_names")
    return genes


def _map_labels(
    raw_labels: np.ndarray,
    label_map: dict[str, str],
    vocabulary: AnnotationVocabulary,
    level: str,
) -> tuple[list[str | None], dict[str, int]]:
    by_name = {
        label.display_name: label
        for label in vocabulary.labels
        if label.level == level
    }
    by_id = {label.state_id: label for label in vocabulary.labels if label.level == level}
    excluded: dict[str, int] = {}
    mapped: list[str | None] = []
    for raw in raw_labels:
        target = label_map.get(raw, vocabulary.alias_map.get(raw, raw))
        label = by_id.get(target) or by_name.get(target)
        if label is None or label.status == "unresolved":
            reason = "unmapped" if label is None else "unresolved"
            excluded[reason] = excluded.get(reason, 0) + 1
            mapped.append(None)
        else:
            mapped.append(label.state_id)
    return mapped, excluded


def _pseudobulk(matrix, samples: np.ndarray, labels: np.ndarray, semantics: str):
    rows: list[dict[str, Any]] = []
    values: list[np.ndarray] = []
    for sample, label in sorted(set(zip(samples, labels, strict=True))):
        mask = (samples == sample) & (labels == label)
        selected = matrix[mask]
        summed = np.asarray(selected.sum(axis=0)).ravel().astype(float)
        if semantics == "raw_counts":
            total = summed.sum()
            vector = np.log1p(summed * (10000.0 / total)) if total > 0 else summed
        elif semantics == "normalized_expression":
            vector = summed / int(mask.sum())
        else:
            raise ReferenceError("reference_matrix_semantics_invalid", semantics)
        rows.append({"sample_id": str(sample), "label": str(label), "n_observations": int(mask.sum())})
        values.append(vector)
    return np.vstack(values), rows


def _select_features(
    profiles: np.ndarray,
    genes: np.ndarray,
    rows: list[dict[str, Any]],
    cards: list[MarkerProgramCard],
    max_features: int,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    labels = sorted({row["label"] for row in rows})
    centroids = np.vstack(
        [np.median(profiles[[row["label"] == label for row in rows]], axis=0) for label in labels]
    )
    variance = np.var(centroids, axis=0)
    top = np.argsort(variance, kind="stable")[-min(max_features, len(genes)) :]
    marker_genes = {
        gene.upper()
        for card in cards
        for gene in card.positive_markers + card.negative_markers
    }
    marker_indices = np.flatnonzero(np.isin(genes, sorted(marker_genes)))
    selected = np.unique(np.concatenate([top, marker_indices]))
    selected.sort()
    return (
        profiles[:, selected],
        genes[selected],
        {
            "method": "between_label_variance_plus_marker_union",
            "max_variance_features": max_features,
            "selected_gene_count": int(len(selected)),
            "query_independent": True,
        },
    )


def _check_artifact(root: Path, relative_path: str, expected_hash: str | None) -> None:
    resolved_root = root.resolve()
    path = (resolved_root / relative_path).resolve()
    if not path.is_relative_to(resolved_root):
        raise ReferenceError("reference_artifact_path_escape", relative_path)
    if not path.is_file():
        raise ReferenceError("reference_artifact_not_found", relative_path)
    if expected_hash is None or sha256_path(path) != expected_hash:
        raise ReferenceError("reference_artifact_checksum_mismatch", relative_path)


def _safe_id(value: str) -> str:
    return "".join(character if character.isalnum() or character in "-_" else "-" for character in value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def content_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
