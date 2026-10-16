"""Raw-count, whole-view technical aggregate versus checked reference profiles."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from bridge.tool_packages._configurable_contracts import observation_ids_sha256
from bridge.tool_packages.p0_01_input_qc.io import sha256_path
from bridge.tool_packages.p0_02_cell_state.metrics import source_support
from bridge.tool_packages.p0_03_target_regional.exploratory_models import (
    ReferenceLabelSimilarity,
    ReferenceSimilarityExploratoryInput,
    ReferenceSimilarityExploratoryResult,
)
from bridge.tool_packages.p0_03_target_regional.method_runtime import (
    TargetRegionalMethodError,
    _QuerySummary,
    _load_checked_profile,
    _resolve_profiles,
)
from bridge.toolkit.contracts import InputAsset, ReferenceManifest


def _measurement_id(run_id: str, profile_id: str, label: str) -> str:
    suffix = hashlib.sha256((profile_id + "\0" + label).encode("utf-8")).hexdigest()[:24]
    return f"measurement:{run_id}:{suffix}"


def _reason_records(labels, *, run_id, profile_id, source_id, source_family_id,
                    label_level, shared, query_fraction, reference_fraction, reason):
    return [ReferenceLabelSimilarity(
        measurement_id=_measurement_id(run_id, profile_id, label),
        profile_id=profile_id, source_id=source_id,
        source_family_id=source_family_id, label_level=label_level,
        label=label, state="unavailable", shared_genes=shared,
        query_gene_fraction=query_fraction,
        reference_gene_fraction=reference_fraction, reason_codes=[reason],
    ) for label in labels]


def _scores_for_profile(*, query: np.ndarray, query_genes: np.ndarray,
                        reference: np.ndarray, metadata: dict,
                        profile_id: str, source_id: str,
                        source_family_id: str, label_level: str,
                        minimum_shared_genes: int,
                        run_id: str = "test") -> list[ReferenceLabelSimilarity]:
    genes = np.asarray(metadata["genes"])
    labels = np.asarray([str(row["label"]) for row in metadata["rows"]])
    unique_labels = sorted(set(labels.tolist()))
    shared = [gene for gene in genes if gene in set(query_genes)]
    coverage = (len(shared), len(shared) / len(query_genes), len(shared) / len(genes))
    common = dict(run_id=run_id, profile_id=profile_id, source_id=source_id,
                  source_family_id=source_family_id, label_level=label_level,
                  shared=coverage[0], query_fraction=coverage[1],
                  reference_fraction=coverage[2])
    if len(shared) < minimum_shared_genes:
        return _reason_records(unique_labels, **common, reason="insufficient_shared_genes")
    q_index = {gene: i for i, gene in enumerate(query_genes)}
    r_index = {gene: i for i, gene in enumerate(genes)}
    q_shared = query[[q_index[gene] for gene in shared]]
    if np.all(q_shared == 0):
        return _reason_records(unique_labels, **common, reason="zero_query_vector")
    if np.ptp(q_shared) == 0:
        return _reason_records(unique_labels, **common, reason="constant_query_vector")
    r_shared = reference[:, [r_index[gene] for gene in shared]]
    valid = {}
    for label in unique_labels:
        centroid = np.median(r_shared[labels == label], axis=0)
        valid[label] = np.any(centroid != 0) and np.ptp(centroid) > 0
    records = _reason_records(
        [label for label in unique_labels if not valid[label]],
        **common, reason="constant_reference_vector",
    )
    valid_labels = [label for label in unique_labels if valid[label]]
    if not valid_labels:
        return sorted(records, key=lambda item: item.label)
    mask = np.isin(labels, valid_labels)
    filtered_metadata = {**metadata, "rows": [row for row, keep in zip(metadata["rows"], mask, strict=True) if keep]}
    long, summary, _ = source_support(
        query.reshape(1, -1), query_genes, reference[mask],
        filtered_metadata, np.asarray(["whole-view"]),
        minimum_shared_genes=minimum_shared_genes, workers=1,
    )
    top = summary.iloc[0]
    for _, row in long.iterrows():
        label = str(row["label"])
        records.append(ReferenceLabelSimilarity(
            measurement_id=_measurement_id(run_id, profile_id, label),
            profile_id=profile_id, source_id=source_id,
            source_family_id=source_family_id, label_level=label_level,
            label=label, state="available", spearman=float(row["spearman_support"]),
            cosine=float(row["cosine_support"]),
            top_label=str(top["top_label"]),
            runner_up_label=str(top["runner_up_label"]) if len(valid_labels) > 1 else None,
            margin=float(top["margin"]) if len(valid_labels) > 1 and label == top["top_label"] else None,
            shared_genes=coverage[0], query_gene_fraction=coverage[1],
            reference_gene_fraction=coverage[2],
        ))
    return sorted(records, key=lambda item: item.label)


def _load_whole_view(asset: InputAsset, source: ReferenceSimilarityExploratoryInput):
    import anndata

    try:
        adata = anndata.read_h5ad(asset.path, backed="r")
    except (OSError, ValueError) as exc:
        raise TargetRegionalMethodError("expression_asset_unreadable") from exc
    try:
        view = source.data_view
        if adata.n_obs != view.n_observations:
            raise TargetRegionalMethodError("expression_view_observation_count_mismatch")
        identifiers = [str(value).strip() for value in adata.obs_names]
        if any(not value for value in identifiers) or len(set(identifiers)) != len(identifiers):
            raise TargetRegionalMethodError("observation_ids_invalid")
        if observation_ids_sha256(identifiers) != view.observation_ids_sha256:
            raise TargetRegionalMethodError("expression_view_observation_identity_mismatch")
        if source.gene_symbol_column is None:
            names = adata.var_names
        else:
            if source.gene_symbol_column not in adata.var:
                raise TargetRegionalMethodError("gene_symbol_column_missing")
            names = adata.var[source.gene_symbol_column]
            if pd.isna(names).any():
                raise TargetRegionalMethodError("gene_symbol_values_missing")
        genes = np.asarray([str(value).strip().upper() for value in names])
        if any(not gene for gene in genes) or len(set(genes)) != len(genes):
            raise TargetRegionalMethodError("gene_symbols_invalid")
        matrix = adata.X
        if view.matrix_location != "X":
            if not view.matrix_location.startswith("layers/"):
                raise TargetRegionalMethodError("unsupported_matrix_location")
            layer = view.matrix_location.removeprefix("layers/")
            if layer not in adata.layers:
                raise TargetRegionalMethodError("matrix_layer_not_found")
            matrix = adata.layers[layer]
        counts = np.zeros(adata.n_vars, dtype=np.float64)
        for start in range(0, adata.n_obs, 512):
            block = matrix[start:start + 512, :]
            values = block.toarray() if sparse.issparse(block) else np.asarray(block)
            if not np.isfinite(values).all() or np.any(values < 0) or np.any(values != np.floor(values)):
                raise TargetRegionalMethodError("raw_count_matrix_invalid")
            counts += values.sum(axis=0, dtype=np.float64)
        total = counts.sum()
        if total <= 0:
            raise TargetRegionalMethodError("zero_total_raw_counts")
        return np.log1p(counts * (10000.0 / total)), genes
    finally:
        if getattr(adata, "file", None) is not None:
            adata.file.close()


def run_exploratory_similarity(*, source: ReferenceSimilarityExploratoryInput,
                               asset: InputAsset, manifest: ReferenceManifest,
                               manifest_path: Path, manifest_sha256: str,
                               input_sha256: str, run_id: str,
                               tool_version: str) -> ReferenceSimilarityExploratoryResult:
    try:
        asset_sha = sha256_path(asset.path)
    except OSError as exc:
        raise TargetRegionalMethodError("expression_asset_unreadable") from exc
    if asset_sha != asset.checksum:
        raise TargetRegionalMethodError("expression_asset_checksum_mismatch")
    query, genes = _load_whole_view(asset, source)
    query_summary = _QuerySummary(
        matrix=query.reshape(1, -1), genes=genes,
        analysis_unit_refs=np.asarray([source.data_view.view_id]),
        independence_by_analysis_unit={},
        n_observations=source.data_view.n_observations,
        observation_ids_sha256=source.data_view.observation_ids_sha256,
    )
    profiles = _resolve_profiles(manifest, source.profile_ids)
    records = []
    for profile in profiles:
        if profile.assay != asset.assay:
            raise TargetRegionalMethodError("reference_assay_mismatch")
        checked = _load_checked_profile(manifest_path.parent, profile, query_summary)
        records.extend(_scores_for_profile(
            query=query, query_genes=genes, reference=checked.matrix,
            metadata=checked.metadata, profile_id=profile.profile_id,
            source_id=profile.source_id, source_family_id=profile.source_family_id,
            label_level=profile.label_level,
            minimum_shared_genes=source.minimum_shared_genes,
            run_id=run_id,
        ))
    available = sum(record.state == "available" for record in records)
    state = "available" if available == len(records) else "partial" if available else "unavailable"
    return ReferenceSimilarityExploratoryResult(
        result_id="reference-similarity:" + run_id.removeprefix("run-"),
        tool_version=tool_version, source_run_ref=f"tool-run:{run_id}@{tool_version}",
        source_asset_id=asset.asset_id, source_asset_sha256=asset_sha,
        input_sha256=input_sha256,
        reference_manifest_ref=f"{manifest.snapshot_id}@{manifest.version}",
        reference_manifest_sha256=manifest_sha256,
        data_view=source.data_view, n_observations=source.data_view.n_observations,
        n_query_genes=len(genes), result_state=state,
        measurements=records, created_at=datetime.now(timezone.utc),
    )
