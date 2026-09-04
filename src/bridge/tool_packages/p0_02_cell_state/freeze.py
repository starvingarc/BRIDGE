from __future__ import annotations

import hashlib
import base64
import json
import math
import os
import platform
from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
import yaml
import h5py
from scipy import sparse
from scipy.stats import rankdata
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support

from bridge.tool_packages.p0_02_cell_state.reference import (
    DENIED_SOURCE_FAMILIES,
    load_packaged_marker_programs,
)
from bridge.toolkit.contracts import (
    BenchmarkSplitManifest,
    BenchmarkSplitRecord,
    BiologicalReviewRecord,
    CellStateBenchmarkSpec,
    CellStateReleaseManifest,
    FreezeGateSpec,
    FrozenModel,
)


class BenchmarkError(ValueError):
    def __init__(self, reason_code: str, detail: str | None = None) -> None:
        super().__init__(detail or reason_code)
        self.reason_code = reason_code


RUNTIME_EXECUTABLE_METHODS = frozenset(
    {"source_specific_correlation", "marker_program_evidence"}
)
RUNTIME_METHOD_VERSIONS = {method: "0.4.8" for method in RUNTIME_EXECUTABLE_METHODS}
RUNTIME_TOOL_VERSION = "0.5.2"
RUNTIME_ENVIRONMENT_SPEC = "ENV-P0-CORE-v0.2"
BENCHMARK_IMPLEMENTATION_VERSION = "0.4.8"
LOCKED_RUNNER_IMPLEMENTATION_VERSION: str | None = None
SIGNATURE_DOMAIN = b"BRIDGE-CELLSTATE-ED25519-v1\n"
_DENIED_IDENTIFIERS = {
    "".join(character for character in value.upper() if character.isalnum())
    for value in DENIED_SOURCE_FAMILIES
}
METHOD_ADAPTER_CONTRACTS: dict[str, dict[str, Any]] = {
    "source_specific_correlation": {
        "adapter_implementation_version": "0.4.8",
        "evidence_family": "reference_similarity",
        "independent_evidence_vote": True,
        "probability_semantics": "uncalibrated_score",
        "query_expression_used_as_unlabeled_during_training": False,
        "label_levels": {"L1", "L2"},
        "include_auxiliary": True,
    },
    "marker_program_evidence": {
        "adapter_implementation_version": "0.4.8",
        "evidence_family": "marker_program",
        "independent_evidence_vote": True,
        "probability_semantics": "uncalibrated_score",
        "query_expression_used_as_unlabeled_during_training": False,
        "label_levels": {"L1"},
        "include_auxiliary": True,
    },
    "celltypist_custom": {
        "adapter_implementation_version": "0.2.3",
        "package_version": "1.7.1",
        "evidence_family": "supervised_classifier",
        "independent_evidence_vote": True,
        "probability_semantics": "one_vs_rest_sigmoid",
        "query_expression_used_as_unlabeled_during_training": False,
        "max_iter": 100,
        "label_levels": {"L1", "L2"},
        "include_auxiliary": True,
    },
    "singler": {
        "adapter_implementation_version": "0.1.2",
        "package_version": "2.14.1",
        "evidence_family": "reference_similarity",
        "independent_evidence_vote": True,
        "probability_semantics": "spearman_reference_score",
        "query_expression_used_as_unlabeled_during_training": False,
        "label_levels": {"L1", "L2"},
        "include_auxiliary": False,
    },
    "scmap": {
        "adapter_implementation_version": "0.1.2",
        "package_version": "1.34.0",
        "evidence_family": "reference_similarity",
        "independent_evidence_vote": True,
        "probability_semantics": "multi_similarity_consensus",
        "query_expression_used_as_unlabeled_during_training": False,
        "label_levels": {"L1", "L2"},
        "include_auxiliary": False,
    },
    "scanvi": {
        "adapter_implementation_version": "0.2.3",
        "package_version": "1.4.0.post1",
        "evidence_family": "latent_reference_mapping",
        "independent_evidence_vote": True,
        "probability_semantics": "categorical_simplex",
        "query_expression_used_as_unlabeled_during_training": True,
        "preset": "small",
        "scvi_epochs": 20,
        "scanvi_epochs": 10,
        "label_levels": {"L1", "L2"},
        "include_auxiliary": False,
    },
    "symphony": {
        "adapter_implementation_version": "0.1.2",
        "package_version": "0.1.3",
        "evidence_family": "latent_reference_mapping",
        "independent_evidence_vote": True,
        "probability_semantics": "knn_vote_fraction",
        "query_expression_used_as_unlabeled_during_training": False,
        "label_levels": {"L1", "L2"},
        "include_auxiliary": False,
    },
    "scconform_calibration": {
        "adapter_implementation_version": "0.1.2",
        "package_version": "1.0.0",
        "evidence_family": "latent_reference_mapping",
        "independent_evidence_vote": False,
        "probability_semantics": "prediction_set",
        "query_expression_used_as_unlabeled_during_training": True,
        "base_adapter": "scanvi",
        "alpha": 0.1,
        "label_levels": {"L1", "L2"},
        "include_auxiliary": False,
    },
}


def load_biological_review_draft() -> BiologicalReviewRecord:
    payload = _load_resource("biological_review_draft.yaml")
    defaults = payload.pop("card_defaults")
    _, marker_cards = load_packaged_marker_programs()
    markers = {card.state_id: card for card in marker_cards}
    cards = []
    for item in payload["state_reviews"]:
        marker = markers.get(item["state_id"])
        cards.append(
            {
                **defaults,
                **item,
                "positive_markers": item.get(
                    "positive_markers", marker.positive_markers if marker else []
                ),
                "negative_markers": item.get(
                    "negative_markers", marker.negative_markers if marker else []
                ),
                "source_ids": item.get(
                    "source_ids", marker.source_ids if marker else defaults["source_ids"]
                ),
            }
        )
    payload["state_reviews"] = cards
    return BiologicalReviewRecord.model_validate(payload)


def load_pilot_benchmark_spec() -> CellStateBenchmarkSpec:
    return CellStateBenchmarkSpec.model_validate(_load_resource("benchmark_spec_pilot_v0.2.yaml"))


def load_release_manifest_draft() -> CellStateReleaseManifest:
    payload = _load_resource("release_manifest_v1.0_draft.yaml")
    if payload.get("per_state_release") == "from_review_draft":
        review = load_biological_review_draft()
        payload["per_state_release"] = {
            card.state_id: "unavailable" if card.n_observations == 0 else "shadow"
            for card in review.state_reviews
        }
    return CellStateReleaseManifest.model_validate(payload)


def prepare_benchmark_split(
    spec: CellStateBenchmarkSpec,
    asset_catalog_path: Path,
    *,
    freeze_gate: FreezeGateSpec | None = None,
    reviewer_registry_path: Path | None = None,
) -> BenchmarkSplitManifest:
    if spec.phase == "locked":
        if LOCKED_RUNNER_IMPLEMENTATION_VERSION is None:
            raise BenchmarkError("locked_runner_not_implemented")
        if freeze_gate is None or freeze_gate.status != "approved":
            raise BenchmarkError("locked_test_not_authorized")
        if freeze_gate.benchmark_spec_ref != spec.benchmark_spec_id:
            raise BenchmarkError("freeze_gate_benchmark_mismatch")
        if (
            freeze_gate.benchmark_spec_sha256 != _model_sha256(spec)
            or freeze_gate.asset_catalog_sha256 != _sha256(asset_catalog_path)
            or freeze_gate.reference_snapshot_ref != spec.reference_snapshot_ref
            or freeze_gate.environment_spec_refs != spec.environment_spec_refs
            or freeze_gate.adapter_contract_sha256 != _adapter_contract_sha256(spec)
        ):
            raise BenchmarkError("freeze_gate_binding_mismatch")
        verify_reviewer_signatures(freeze_gate, reviewer_registry_path)
    assets = _load_asset_catalog(asset_catalog_path)
    _validate_catalog_role_isolation(assets, spec)

    allowed = set(spec.development_asset_ids)
    allowed.update(spec.development_ood_asset_ids)
    allowed.update(spec.behavior_only_asset_ids)
    if spec.phase == "locked":
        allowed = set(spec.locked_asset_ids)
    selected_ids = {str(asset.get("asset_id", "")) for asset in assets} & allowed
    missing_assets = sorted(allowed - selected_ids)
    if missing_assets:
        raise BenchmarkError("benchmark_assets_missing_from_catalog", ",".join(missing_assets))
    records: list[BenchmarkSplitRecord] = []
    locked_opened = False
    expected_roles = {
        **{asset_id: "labeled_reference" for asset_id in spec.development_asset_ids},
        **{asset_id: "development_ood" for asset_id in spec.development_ood_asset_ids},
        **{asset_id: "behavior_only" for asset_id in spec.behavior_only_asset_ids},
    }
    for asset in assets:
        asset_id = str(asset.get("asset_id", ""))
        if asset_id in spec.sealed_asset_ids:
            continue
        if asset_id not in allowed:
            continue
        _validate_selected_asset(asset, spec, expected_roles.get(asset_id))
        if spec.phase == "pilot" and asset_id in spec.locked_asset_ids:
            raise BenchmarkError("pilot_attempted_locked_asset", asset_id)
        if spec.phase == "locked":
            locked_opened = True
        role = str(asset.get("data_role", ""))
        if role == "labeled_reference":
            records.extend(_donor_rotation_records(asset))
        elif role == "development_ood":
            records.extend(_single_partition_records(asset, "development_ood"))
        elif role == "behavior_only":
            records.extend(_single_partition_records(asset, "behavior_only"))
        elif role in {"locked_source_holdout", "locked_ood"} and spec.phase == "locked":
            records.extend(_single_partition_records(asset, "locked_test"))
        else:
            raise BenchmarkError("asset_role_not_supported", f"{asset_id}:{role}")
    if not records:
        raise BenchmarkError("benchmark_split_empty")
    return BenchmarkSplitManifest(
        split_manifest_id=_split_manifest_id(spec, asset_catalog_path),
        benchmark_spec_ref=spec.benchmark_spec_id,
        benchmark_spec_sha256=_model_sha256(spec),
        phase=spec.phase,
        random_seed=spec.random_seed,
        input_catalog_sha256=_sha256(asset_catalog_path),
        records=records,
        locked_assets_opened=locked_opened,
        sealed_assets_opened=False,
    )


def validate_probability_output(path: Path) -> set[str]:
    frame = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path, sep="\t")
    return _validate_probability_frame(frame)


def _validate_probability_frame(
    frame: pd.DataFrame, *, require_predicted_label: bool = False
) -> set[str]:
    required = {"observation_id", "partition", "true_label"}
    if not required.issubset(frame.columns):
        raise BenchmarkError("prediction_contract_incomplete")
    probability_columns = [column for column in frame.columns if column.startswith("prob__")]
    if not probability_columns:
        raise BenchmarkError("probability_columns_required")
    partitions = set(frame["partition"].astype(str))
    if not {"calibration", "test"}.issubset(partitions):
        raise BenchmarkError("independent_calibration_and_test_required")
    identity_columns = ["observation_id"]
    if "fold_id" in frame:
        identity_columns.insert(0, "fold_id")
    if frame[identity_columns].astype(str).duplicated().any():
        raise BenchmarkError("prediction_observation_ids_not_unique")
    probabilities = frame[probability_columns].apply(pd.to_numeric, errors="coerce")
    values = probabilities.to_numpy(dtype=float)
    if (
        not np.isfinite(values).all()
        or ((probabilities < 0) | (probabilities > 1)).any().any()
    ):
        raise BenchmarkError("probability_values_invalid")
    if not probabilities.sum(axis=1).between(0.999, 1.001).all():
        raise BenchmarkError("probability_rows_must_sum_to_one")
    labels = [column.removeprefix("prob__") for column in probability_columns]
    if require_predicted_label and "predicted_label" not in frame:
        raise BenchmarkError("prediction_contract_incomplete")
    if "predicted_label" in frame:
        label_index = {label: index for index, label in enumerate(labels)}
        predicted = frame["predicted_label"].astype(str)
        if not predicted.isin(label_index).all():
            raise BenchmarkError("predicted_label_probability_mismatch")
        chosen = np.asarray(
            [values[index, label_index[label]] for index, label in enumerate(predicted)]
        )
        if not np.isclose(chosen, values.max(axis=1), rtol=1e-9, atol=1e-12).all():
            raise BenchmarkError("predicted_label_probability_mismatch")
    return set(labels)


def object_signing_hash(value: FrozenModel | dict[str, Any]) -> str:
    payload = value.model_dump(mode="json") if isinstance(value, FrozenModel) else dict(value)
    payload["signatures"] = []
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _model_sha256(value: FrozenModel) -> str:
    return _json_sha256(value.model_dump(mode="json"))


def _json_sha256(value: Any) -> str:
    def normalize(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: normalize(current) for key, current in sorted(item.items())}
        if isinstance(item, set):
            return sorted(normalize(current) for current in item)
        if isinstance(item, (list, tuple)):
            return [normalize(current) for current in item]
        return item

    encoded = json.dumps(
        normalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def _adapter_contract_sha256(spec: CellStateBenchmarkSpec) -> str:
    try:
        contracts = {method: METHOD_ADAPTER_CONTRACTS[method] for method in spec.methods}
    except KeyError as exc:
        raise BenchmarkError("benchmark_method_contract_missing", str(exc.args[0])) from exc
    return _json_sha256(
        {
            "contracts": contracts,
            "implementation_artifact_sha256": _adapter_implementation_hashes(),
        }
    )


def _adapter_implementation_hashes() -> dict[str, str]:
    root = Path(__file__).resolve().parent
    paths = sorted((*root.glob("*.py"), *root.glob("*.R")))
    hashes = {path.name: _sha256(path) for path in paths}
    contracts_path = root.parents[1] / "toolkit" / "contracts.py"
    hashes["bridge/toolkit/contracts.py"] = _sha256(contracts_path)
    return hashes


def verify_reviewer_signatures(
    value: FrozenModel, registry_path: Path | None = None
) -> None:
    path = registry_path or _reviewer_registry_path()
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
        reviewers = registry["reviewers"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise BenchmarkError("trusted_reviewer_registry_invalid") from exc
    trusted = {}
    public_keys: set[bytes] = set()
    for item in reviewers:
        identity = (item.get("reviewer_id"), item.get("reviewer_role"), item.get("key_id"))
        if None in identity or identity in trusted:
            raise BenchmarkError("trusted_reviewer_registry_invalid")
        try:
            public_key = base64.b64decode(item.get("public_key_base64", ""), validate=True)
        except (TypeError, ValueError) as exc:
            raise BenchmarkError("trusted_reviewer_registry_invalid") from exc
        if len(public_key) != 32 or public_key in public_keys:
            raise BenchmarkError("trusted_reviewer_registry_invalid")
        public_keys.add(public_key)
        trusted[identity] = public_key
    expected_hash = object_signing_hash(value)
    signatures = getattr(value, "signatures", [])
    if len(signatures) != 2:
        raise BenchmarkError("reviewer_signatures_incomplete")
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise BenchmarkError("signature_verifier_unavailable") from exc
    for signature in signatures:
        identity = (signature.reviewer_id, signature.reviewer_role, signature.key_id)
        public_key = trusted.get(identity)
        if signature.object_sha256 != expected_hash or public_key is None:
            raise BenchmarkError("reviewer_signature_identity_mismatch")
        try:
            key = Ed25519PublicKey.from_public_bytes(public_key)
            key.verify(
                base64.b64decode(signature.signature_base64, validate=True),
                SIGNATURE_DOMAIN + expected_hash.encode(),
            )
        except (ValueError, InvalidSignature) as exc:
            raise BenchmarkError("reviewer_signature_invalid", signature.reviewer_id) from exc


def _reviewer_registry_path() -> Path:
    value = os.environ.get("BRIDGE_CELLSTATE_REVIEWER_REGISTRY")
    if not value:
        raise BenchmarkError("trusted_reviewer_registry_not_configured")
    return Path(value).expanduser().resolve()


def validate_release_bundle(
    root: Path, *, reviewer_registry_path: Path | None = None
) -> CellStateReleaseManifest:
    if LOCKED_RUNNER_IMPLEMENTATION_VERSION is None:
        raise BenchmarkError("locked_runner_not_implemented")
    return _validate_release_bundle_structure(
        root, reviewer_registry_path=reviewer_registry_path
    )


def _validate_release_bundle_structure(
    root: Path, *, reviewer_registry_path: Path | None = None
) -> CellStateReleaseManifest:
    paths = {
        "release": root / "release_manifest.json",
        "review": root / "biological_review.json",
        "gate": root / "freeze_gate.json",
        "summary": root / "locked_benchmark_summary.json",
        "run": root / "locked_run_manifest.json",
        "split": root / "locked_split_manifest.json",
    }
    if missing := [name for name, path in paths.items() if not path.is_file()]:
        raise BenchmarkError("release_bundle_incomplete", ",".join(missing))
    release = CellStateReleaseManifest.model_validate_json(
        paths["release"].read_text(encoding="utf-8")
    )
    if release.status != "frozen":
        raise BenchmarkError("cell_state_release_not_frozen")
    review = BiologicalReviewRecord.model_validate_json(paths["review"].read_text(encoding="utf-8"))
    gate = FreezeGateSpec.model_validate_json(paths["gate"].read_text(encoding="utf-8"))
    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    run = json.loads(paths["run"].read_text(encoding="utf-8"))
    split = BenchmarkSplitManifest.model_validate_json(paths["split"].read_text(encoding="utf-8"))
    checksum_pairs = [
        (release.biological_review_sha256, paths["review"]),
        (release.freeze_gate_sha256, paths["gate"]),
        (release.locked_summary_sha256, paths["summary"]),
        (release.locked_run_manifest_sha256, paths["run"]),
        (release.locked_split_manifest_sha256, paths["split"]),
    ]
    if any(expected != _sha256(path) for expected, path in checksum_pairs):
        raise BenchmarkError("release_bundle_checksum_mismatch")
    for signed in (review, gate, release):
        verify_reviewer_signatures(signed, reviewer_registry_path)
    if (
        review.review_record_id != release.biological_review_ref
        or review.status not in {"partially_approved", "approved"}
    ):
        raise BenchmarkError("biological_review_not_approved")
    if review.vocabulary_ref != release.annotation_vocabulary_ref:
        raise BenchmarkError("release_annotation_review_mismatch")
    approved_states = {
        card.state_id for card in review.state_reviews if card.review_status == "approved"
    }
    released_states = {
        state_id
        for state_id, state in release.per_state_release.items()
        if state in {"provisional_frozen", "frozen"}
    }
    if not released_states.issubset(approved_states):
        raise BenchmarkError("release_contains_unapproved_state")
    selected_methods = {
        method for methods in release.selected_methods.values() for method in methods
    }
    unsupported_methods = sorted(selected_methods - RUNTIME_EXECUTABLE_METHODS)
    if unsupported_methods:
        raise BenchmarkError(
            "released_method_not_available_in_runtime", ",".join(unsupported_methods)
        )
    if any(
        "source_specific_correlation" not in methods
        for methods in release.selected_methods.values()
    ):
        raise BenchmarkError("released_state_missing_assignment_method")
    if (
        release.runtime_tool_version != RUNTIME_TOOL_VERSION
        or release.environment_spec_ref != RUNTIME_ENVIRONMENT_SPEC
        or release.method_implementation_versions
        != {method: RUNTIME_METHOD_VERSIONS[method] for method in selected_methods}
    ):
        raise BenchmarkError("release_runtime_version_mismatch")
    if gate.gate_spec_id != release.freeze_gate_ref or gate.status != "approved":
        raise BenchmarkError("freeze_gate_not_approved")
    if gate.benchmark_spec_ref != release.benchmark_spec_ref:
        raise BenchmarkError("release_benchmark_spec_mismatch")
    locked_spec = _validate_locked_run_bundle(run, split, summary, release, gate, root)
    raw_gate_results = summary.get("gate_results", [])
    gate_results = {
        (
            str(item.get("metric")),
            str(item.get("scope")),
            item.get("state_id"),
            item.get("method_id"),
        ): item
        for item in raw_gate_results
    }
    global_criteria = [criterion for criterion in gate.criteria if criterion.state_id is None]
    expected_gate_results = {
        (criterion.metric, criterion.scope, None, None) for criterion in global_criteria
    }
    gate_passed = all(
        _gate_result_passes(
            criterion,
            gate_results.get((criterion.metric, criterion.scope, None, None)),
        )
        for criterion in global_criteria
    )
    if (
        summary.get("locked_test_state") != "passed"
        or summary.get("benchmark_spec_ref") != release.benchmark_spec_ref
        or summary.get("gate_spec_ref") != release.freeze_gate_ref
        or summary.get("tuning_after_lock") is not False
        or len(gate_results) != len(raw_gate_results)
        or set(gate_results) != expected_gate_results
        or not gate_passed
    ):
        raise BenchmarkError("locked_benchmark_not_releasable")
    for criterion in global_criteria:
        _validate_global_gate_provenance(
            gate_results[(criterion.metric, criterion.scope, None, None)],
            locked_spec,
            split,
        )
    _validate_state_method_results(summary, release, gate, locked_spec, split)
    return release


def _validate_locked_run_bundle(
    run: dict[str, Any],
    split: BenchmarkSplitManifest,
    summary: dict[str, Any],
    release: CellStateReleaseManifest,
    gate: FreezeGateSpec,
    root: Path,
) -> CellStateBenchmarkSpec:
    if (
        split.phase != "locked"
        or split.benchmark_spec_ref != gate.benchmark_spec_ref
        or split.benchmark_spec_sha256 != gate.benchmark_spec_sha256
        or split.input_catalog_sha256 != gate.asset_catalog_sha256
        or not split.locked_assets_opened
        or split.sealed_assets_opened
        or not split.records
        or any(record.partition != "locked_test" for record in split.records)
    ):
        raise BenchmarkError("locked_split_manifest_invalid")
    required = {
        "run_id",
        "phase",
        "implementation_version",
        "benchmark_spec",
        "benchmark_spec_ref",
        "benchmark_spec_sha256",
        "gate_spec_ref",
        "freeze_gate_sha256",
        "asset_catalog_sha256",
        "split_manifest_sha256",
        "reference_snapshot_ref",
        "reference_manifest_sha256",
        "environment_spec_refs",
        "environment_spec_sha256",
        "environment_health_record_sha256",
        "adapter_contract_sha256",
        "pilot_evidence_sha256",
        "locked_assets_opened",
        "sealed_assets_opened",
        "tuning_after_lock",
        "artifact_hashes",
        "method_implementation_versions",
    }
    if not required.issubset(run):
        raise BenchmarkError("locked_run_manifest_incomplete")
    locked_spec = CellStateBenchmarkSpec.model_validate(run["benchmark_spec"])
    if (
        release.assay != locked_spec.assay
        or release.annotation_vocabulary_ref
        != locked_spec.annotation_vocabulary_ref
        or release.reference_snapshot_ref != locked_spec.reference_snapshot_ref
        or release.measurement_spec_ref != locked_spec.measurement_spec_ref
    ):
        raise BenchmarkError("release_scientific_contract_mismatch")
    if (
        gate.reference_snapshot_ref != locked_spec.reference_snapshot_ref
        or gate.environment_spec_refs != locked_spec.environment_spec_refs
        or gate.adapter_contract_sha256 != _adapter_contract_sha256(locked_spec)
    ):
        raise BenchmarkError("freeze_gate_binding_mismatch")
    if (
        run["phase"] != "locked"
        or locked_spec.phase != "locked"
        or run["implementation_version"] != BENCHMARK_IMPLEMENTATION_VERSION
        or run["benchmark_spec_ref"] != release.benchmark_spec_ref
        or locked_spec.benchmark_spec_id != release.benchmark_spec_ref
        or _model_sha256(locked_spec) != gate.benchmark_spec_sha256
        or run["benchmark_spec_sha256"] != gate.benchmark_spec_sha256
        or run["gate_spec_ref"] != release.freeze_gate_ref
        or run["freeze_gate_sha256"] != release.freeze_gate_sha256
        or run["asset_catalog_sha256"] != gate.asset_catalog_sha256
        or run["split_manifest_sha256"] != release.locked_split_manifest_sha256
        or run["reference_manifest_sha256"] != release.reference_manifest_sha256
        or run["reference_snapshot_ref"] != gate.reference_snapshot_ref
        or run["reference_manifest_sha256"] != gate.reference_snapshot_sha256
        or run["environment_spec_refs"] != gate.environment_spec_refs
        or run["environment_spec_sha256"] != gate.environment_spec_sha256
        or run["environment_health_record_sha256"]
        != gate.environment_health_record_sha256
        or run["adapter_contract_sha256"] != gate.adapter_contract_sha256
        or run["pilot_evidence_sha256"] != gate.pilot_evidence_sha256
        or run["locked_assets_opened"] is not True
        or run["sealed_assets_opened"] is not False
        or run["tuning_after_lock"] is not False
        or run["method_implementation_versions"] != release.method_implementation_versions
    ):
        raise BenchmarkError("locked_run_manifest_mismatch")
    hashes = run["artifact_hashes"]
    if not isinstance(hashes, dict) or not hashes:
        raise BenchmarkError("locked_run_artifacts_missing")
    for relative, expected in hashes.items():
        path = _resolve_relative_artifact(root, str(relative))
        if not path.is_file() or _sha256(path) != expected:
            raise BenchmarkError("locked_run_artifact_checksum_mismatch", str(relative))
    if (
        summary.get("run_id") != run["run_id"]
        or summary.get("run_manifest_sha256") != release.locked_run_manifest_sha256
        or summary.get("split_manifest_sha256") != release.locked_split_manifest_sha256
        or summary.get("reference_manifest_sha256") != release.reference_manifest_sha256
    ):
        raise BenchmarkError("locked_summary_run_mismatch")
    return locked_spec


def _validate_state_method_results(
    summary: dict[str, Any],
    release: CellStateReleaseManifest,
    gate: FreezeGateSpec,
    spec: CellStateBenchmarkSpec,
    split: BenchmarkSplitManifest,
) -> None:
    results_by_state = summary.get("state_method_results", {})
    source_holdouts = {
        record.asset_id
        for record in split.records
        if record.data_role == "locked_source_holdout"
    }
    for state_id, methods in release.selected_methods.items():
        for method_id in methods:
            result = results_by_state.get(state_id, {}).get(method_id, {})
            if result.get("implementation_version") != release.method_implementation_versions[
                method_id
            ]:
                raise BenchmarkError("released_state_method_not_passed", state_id)
            criteria = [
                criterion
                for criterion in gate.criteria
                if criterion.state_id == state_id and criterion.method_id == method_id
            ]
            metrics = result.get("metrics")
            tested_assets = result.get("tested_asset_ids")
            if (
                not criteria
                or not isinstance(metrics, dict)
                or not isinstance(tested_assets, list)
                or not tested_assets
                or not set(tested_assets).issubset(source_holdouts)
                or any(
                    method_id in spec.locked_method_exclusions.get(asset_id, [])
                    for asset_id in tested_assets
                )
            ):
                raise BenchmarkError("released_state_gate_missing", f"{state_id}:{method_id}")
            support_criteria = [item for item in criteria if item.metric == "n"]
            try:
                support_value = float(metrics["n"])
            except (KeyError, TypeError, ValueError) as exc:
                raise BenchmarkError(
                    "released_state_support_insufficient", f"{state_id}:{method_id}"
                ) from exc
            if (
                len(support_criteria) != 1
                or not math.isfinite(support_value)
                or support_value <= 0
                or not support_value.is_integer()
                or not _criterion_value_passes(support_criteria[0], support_value)
            ):
                raise BenchmarkError(
                    "released_state_support_insufficient", f"{state_id}:{method_id}"
                )
            for criterion in criteria:
                try:
                    value = float(metrics[criterion.metric])
                except (KeyError, TypeError, ValueError) as exc:
                    raise BenchmarkError(
                        "released_state_metric_missing",
                        f"{state_id}:{method_id}:{criterion.metric}",
                    ) from exc
                if not math.isfinite(value) or not _criterion_value_passes(criterion, value):
                    raise BenchmarkError("released_state_method_not_passed", state_id)


def _validate_global_gate_provenance(
    result: dict[str, Any],
    spec: CellStateBenchmarkSpec,
    split: BenchmarkSplitManifest,
) -> None:
    raw_pairs = result.get("method_asset_pairs")
    if not isinstance(raw_pairs, list) or not raw_pairs:
        raise BenchmarkError("locked_gate_provenance_missing")
    locked_assets = {record.asset_id for record in split.records}
    pairs: list[tuple[str, str]] = []
    for raw in raw_pairs:
        if not isinstance(raw, dict) or set(raw) != {"method_id", "asset_id"}:
            raise BenchmarkError("locked_gate_provenance_missing")
        method_id = str(raw["method_id"])
        asset_id = str(raw["asset_id"])
        if method_id not in spec.methods or asset_id not in locked_assets:
            raise BenchmarkError("locked_gate_provenance_missing")
        pairs.append((method_id, asset_id))
    if len(pairs) != len(set(pairs)):
        raise BenchmarkError("locked_gate_provenance_missing")
    if any(
        method_id in spec.locked_method_exclusions.get(asset_id, [])
        for method_id, asset_id in pairs
    ):
        raise BenchmarkError("locked_gate_uses_excluded_method")


def _criterion_value_passes(criterion: Any, value: float) -> bool:
    if criterion.threshold is None:
        return False
    if criterion.operator == ">=":
        return value >= criterion.threshold
    return value <= criterion.threshold


def _gate_result_passes(
    criterion: Any, result: dict[str, Any] | None
) -> bool:
    if result is None or result.get("state") != "passed" or criterion.threshold is None:
        return False
    try:
        value = float(result["value"])
    except (KeyError, TypeError, ValueError):
        return False
    if not math.isfinite(value):
        return False
    return _criterion_value_passes(criterion, value)


def resolve_release_bundle(release_manifest_id: str) -> CellStateReleaseManifest:
    root_value = os.environ.get("BRIDGE_CELLSTATE_RELEASE_ROOT")
    if not root_value:
        raise BenchmarkError("cell_state_release_root_not_configured")
    identity = Path(release_manifest_id)
    if identity.is_absolute() or identity.name != release_manifest_id or release_manifest_id in {".", ".."}:
        raise BenchmarkError("cell_state_release_id_invalid")
    base = Path(root_value).expanduser().resolve()
    root = (base / identity).resolve()
    if root.parent != base:
        raise BenchmarkError("cell_state_release_id_invalid")
    if not root.is_dir():
        raise BenchmarkError("cell_state_release_not_found", release_manifest_id)
    release = validate_release_bundle(root)
    if release.release_manifest_id != release_manifest_id:
        raise BenchmarkError("cell_state_release_id_mismatch")
    return release


def run_pilot_benchmark(
    spec: CellStateBenchmarkSpec,
    asset_catalog_path: Path,
    split: BenchmarkSplitManifest,
    output_dir: Path,
) -> dict[str, Any]:
    if spec.phase != "pilot" or split.phase != "pilot":
        raise BenchmarkError("pilot_runner_requires_pilot_spec")
    if split.benchmark_spec_ref != spec.benchmark_spec_id:
        raise BenchmarkError("benchmark_split_spec_mismatch")
    canonical_split = prepare_benchmark_split(spec, asset_catalog_path)
    if split != canonical_split:
        raise BenchmarkError("benchmark_split_not_canonical")
    if split.input_catalog_sha256 != _sha256(asset_catalog_path):
        raise BenchmarkError("benchmark_asset_catalog_checksum_mismatch")
    assets = {item["asset_id"]: item for item in _load_asset_catalog(asset_catalog_path)}
    opened_ids = {record.asset_id for record in split.records}
    if opened_ids & set(spec.locked_asset_ids):
        raise BenchmarkError("pilot_attempted_locked_asset")
    if opened_ids & set(spec.sealed_asset_ids):
        raise BenchmarkError("sealed_asset_entered_benchmark")

    run_id = _benchmark_run_id(spec, split)
    run_dir = output_dir / run_id
    exchange_dir = run_dir / "exchange"
    predictions_dir = run_dir / "predictions"
    exchange_dir.mkdir(parents=True, exist_ok=True)
    predictions_dir.mkdir(exist_ok=True)
    split_path = run_dir / "split_manifest.json"
    _write_json_file(split_path, split.model_dump(mode="json"))

    loaded: dict[str, dict[str, Any]] = {}
    for asset_id in sorted(opened_ids):
        asset = assets.get(asset_id)
        if asset is None:
            raise BenchmarkError("benchmark_asset_not_in_catalog", asset_id)
        loaded[asset_id] = _load_expression_asset(asset)
        _write_exchange_bundle(exchange_dir / asset_id, asset, loaded[asset_id])
        loaded[asset_id]["raw_counts"] = None

    method_status: dict[str, str] = {}
    for method in spec.methods:
        if method not in {"source_specific_correlation", "marker_program_evidence"}:
            method_status[method] = "not_run_adapter_required"
            continue
        frames = []
        auxiliary = [
            (assets[asset_id], loaded[asset_id])
            for asset_id in sorted(opened_ids)
            if assets[asset_id].get("data_role") in {"development_ood", "behavior_only"}
        ]
        for asset_id in sorted(opened_ids):
            asset = assets[asset_id]
            if asset.get("data_role") != "labeled_reference":
                continue
            records = [record for record in split.records if record.asset_id == asset_id]
            frame = _run_native_method(
                method,
                asset,
                loaded[asset_id],
                records,
                auxiliary=auxiliary,
            )
            if not frame.empty:
                frames.append(frame)
        if not frames:
            method_status[method] = "not_assessed"
            continue
        predictions = pd.concat(frames, ignore_index=True)
        predictions = predictions.sort_values(
            ["label_level", "fold_id", "partition", "observation_id"]
        ).reset_index(drop=True)
        predictions.to_parquet(predictions_dir / f"{method}.parquet", index=False)
        method_status[method] = "completed"

    _write_json_file(
        run_dir / "run_manifest.json",
        {
            "run_id": run_id,
            "implementation_version": BENCHMARK_IMPLEMENTATION_VERSION,
            "environment": _environment_snapshot(),
            "benchmark_spec": spec.model_dump(mode="json"),
            "benchmark_spec_sha256": _model_sha256(spec),
            "adapter_contract_sha256": _adapter_contract_sha256(spec),
            "adapter_implementation_sha256": _adapter_implementation_hashes(),
            "split_manifest": split.model_dump(mode="json"),
            "split_manifest_sha256": _sha256(split_path),
            "asset_catalog_sha256": _sha256(asset_catalog_path),
            "asset_sha256": {
                asset_id: data["source_sha256"] for asset_id, data in sorted(loaded.items())
            },
            "native_artifact_hashes": _native_artifact_hashes(run_dir),
            "method_status": method_status,
            "locked_assets_opened": False,
            "sealed_assets_opened": False,
        },
    )
    summarize_benchmark(run_dir, include_external=False)
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "locked_assets_opened": False,
        "sealed_assets_opened": False,
        "method_status": method_status,
        "artifact_hashes": _core_artifact_hashes(run_dir),
    }


def summarize_benchmark(run_dir: Path, *, include_external: bool = True) -> dict[str, Any]:
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.is_file():
        raise BenchmarkError("benchmark_run_manifest_not_found")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    split = _validate_benchmark_run(run_dir, manifest)
    metrics: dict[str, dict[str, Any]] = {}
    behavior_only: dict[str, dict[str, Any]] = {}
    method_status = dict(manifest["method_status"])
    registered_methods = set(manifest["benchmark_spec"]["methods"])
    method_frames: dict[str, list[pd.DataFrame]] = {}
    method_metadata: dict[str, dict[str, Any]] = {}
    accepted_prediction_paths: list[Path] = []
    missing_labels_by_level: dict[str, dict[str, Any]] = {}
    prediction_paths = sorted((run_dir / "predictions").glob("*.parquet"))
    parquet_stems = {path.stem for path in prediction_paths}
    prediction_paths.extend(
        path
        for path in sorted((run_dir / "predictions").glob("*.tsv"))
        if path.stem not in parquet_stems
    )
    for path in prediction_paths:
        if not include_external and path.stem not in {
            "source_specific_correlation",
            "marker_program_evidence",
        }:
            continue
        frame = _read_table(path)
        metadata = _prediction_metadata(path)
        _validate_prediction_frame(frame)
        _validate_prediction_provenance(run_dir, path, frame, metadata, manifest, split)
        accepted_prediction_paths.append(path)
        method = path.stem if metadata["adapter"] == "native" else str(metadata["adapter"])
        if method not in registered_methods:
            raise BenchmarkError("benchmark_output_method_not_registered", method)
        previous = method_metadata.get(method)
        if previous and any(
            previous.get(key) != metadata.get(key)
            for key in (
                "adapter",
                "adapter_implementation_version",
                "package_version",
                "evidence_family",
                "probability_semantics",
                "query_expression_used_as_unlabeled_during_training",
            )
        ):
            raise BenchmarkError("adapter_metadata_conflict", method)
        method_metadata[method] = metadata
        method_frames.setdefault(method, []).append(frame)
        for level in sorted(frame["label_level"].astype(str).unique()):
            missing_labels_by_level.setdefault(method, {})[level] = metadata.get(
                "fold_missing_training_labels", {}
            )
        method_status[method] = (
            "completed_external_adapter" if metadata["adapter"] != "native" else "completed"
        )

    for method, frames in sorted(method_frames.items()):
        frame = pd.concat(frames, ignore_index=True)
        _validate_prediction_frame(frame)
        _validate_method_asset_coverage(run_dir, method, frame, split)
        metadata = method_metadata[method]
        test = frame.loc[frame["partition"].eq("test") & frame["true_label"].notna()].copy()
        if test.empty:
            continue
        ood = frame.loc[frame["partition"].eq("development_ood")]
        by_label_level = {
            level: _benchmark_metric_block(
                test.loc[test["label_level"].eq(level)],
                ood.loc[ood["label_level"].eq(level)],
                metadata,
            )
            for level in sorted(test["label_level"].astype(str).unique())
        }
        metrics[method] = {
            "evidence_family": metadata["evidence_family"],
            "independent_evidence_vote": bool(metadata["independent_evidence_vote"]),
            "adapter": metadata["adapter"],
            "adapter_implementation_version": metadata.get("adapter_implementation_version"),
            "package_version": metadata.get("package_version"),
            "probability_semantics": metadata.get("probability_semantics"),
            "fold_missing_training_labels_by_label_level": missing_labels_by_level.get(
                method, {}
            ),
            "evaluation_protocol": _evaluation_protocol(metadata),
            "label_levels": sorted(test["label_level"].astype(str).unique()),
            "metric_scope": (
                "pooled_diagnostic" if len(by_label_level) > 1 else next(iter(by_label_level))
            ),
            **_benchmark_metric_block(test, ood, metadata),
            "by_label_level": by_label_level,
        }
        behavior = frame.loc[frame["partition"].eq("behavior_only")]
        if not behavior.empty:
            standard = {
                "observation_id",
                "sample_id",
                "true_label",
                "asset_id",
                "source_family_id",
                "fold_id",
                "partition",
                "label_level",
                "predicted_label",
                "score",
                "margin",
                "assignment_state",
                "prediction_set",
                "unavailable_reason",
            }
            behavior_only[method] = {
                "n_observations": _unique_observation_count(behavior),
                "n_evaluations": int(len(behavior)),
                "context_columns": sorted(
                    column
                    for column in set(behavior.columns) - standard
                    if not column.startswith("prob__")
                ),
            }
    l1_metrics = [
        result["by_label_level"]["L1"]
        for result in metrics.values()
        if "L1" in result["by_label_level"]
    ]
    pilot_accuracy = max((result["exact_accuracy"] for result in l1_metrics), default=None)
    pilot_composition = min((result["composition_mae"] for result in l1_metrics), default=None)
    pilot_false_reassurance = min(
        (
            result["false_reassurance"]
            for result in l1_metrics
            if result["false_reassurance"] is not None
        ),
        default=None,
    )
    pilot_ood_coverage = max(
        (
            result["ood_assessment_coverage"]
            for result in l1_metrics
            if result["ood_assessment_coverage"] is not None
        ),
        default=None,
    )
    evidence_artifact_sha256 = _json_sha256(
        _evidence_artifact_hashes(run_dir, accepted_prediction_paths)
    )
    evidence_run_id = (
        "CELLSTATE-EVIDENCE-"
        f"{_json_sha256([manifest['run_id'], evidence_artifact_sha256])[:12]}"
    )
    proposal = FreezeGateSpec(
        gate_spec_id="FREEZE-GATE-CELLSTATE-scRNA-v1.0-draft",
        version="0.1.0",
        status="proposed",
        benchmark_spec_ref=manifest["benchmark_spec"]["benchmark_spec_id"],
        benchmark_spec_sha256=manifest["benchmark_spec_sha256"],
        asset_catalog_sha256=manifest["asset_catalog_sha256"],
        reference_snapshot_ref=manifest["benchmark_spec"]["reference_snapshot_ref"],
        reference_snapshot_sha256=_reference_snapshot_sha256(manifest),
        environment_spec_refs=manifest["benchmark_spec"]["environment_spec_refs"],
        adapter_contract_sha256=manifest["adapter_contract_sha256"],
        pilot_evidence_sha256=evidence_artifact_sha256,
        criteria=[
            {
                "metric": "exact_accuracy",
                "scope": "per-state and overall L1 source/donor holdout",
                "operator": ">=",
                "threshold": None,
                "pilot_observation": pilot_accuracy,
                "rationale": "Human review must set the floor before locked data are opened.",
            },
            {
                "metric": "macro_f1",
                "scope": "per-state and overall L1 source/donor holdout",
                "operator": ">=",
                "threshold": None,
                "pilot_observation": max(
                    (result["macro_f1"] for result in l1_metrics), default=None
                ),
                "rationale": "Protects rare states from being hidden by overall accuracy.",
            },
            {
                "metric": "composition_mae",
                "scope": "sample-level L1 composition",
                "operator": "<=",
                "threshold": None,
                "pilot_observation": pilot_composition,
                "rationale": "Human review must set the tolerance before locked data are opened.",
            },
            {
                "metric": "prediction_set_coverage",
                "scope": "independent calibration and donor/source holdout",
                "operator": ">=",
                "threshold": None,
                "pilot_observation": None,
                "rationale": "Requires a conformal-ready categorical probability output.",
            },
            {
                "metric": "false_reassurance",
                "scope": "development OOD",
                "operator": "<=",
                "threshold": None,
                "pilot_observation": pilot_false_reassurance,
                "rationale": "Requires calibrated open-set method outputs.",
            },
            {
                "metric": "ood_assessment_coverage",
                "scope": "development OOD",
                "operator": ">=",
                "threshold": None,
                "pilot_observation": pilot_ood_coverage,
                "rationale": "Prevents unavailable OOD results from appearing reassuring.",
            },
            {
                "metric": "downsampling_drift",
                "scope": "sample-preserving cell and library downsampling",
                "operator": "<=",
                "threshold": None,
                "pilot_observation": None,
                "rationale": "Must be measured under a signed sensitivity specification.",
            },
            {
                "metric": "preprocessing_sensitivity",
                "scope": "registered preprocessing swap",
                "operator": "<=",
                "threshold": None,
                "pilot_observation": None,
                "rationale": "Must be measured under a signed sensitivity specification.",
            },
        ],
    )
    summary = {
        "run_id": manifest["run_id"],
        "evidence_run_id": evidence_run_id,
        "adapter_contract_sha256": manifest["adapter_contract_sha256"],
        "evidence_artifact_sha256": evidence_artifact_sha256,
        "phase": manifest["split_manifest"]["phase"],
        "method_status": method_status,
        "method_metrics": metrics,
        "behavior_only": behavior_only,
        "preliminary_pareto_candidates": _pareto_candidates(metrics),
        "transductive_diagnostics": sorted(
            method
            for method, result in metrics.items()
            if "transductive" in result["evaluation_protocol"]
        ),
        "preliminary_pareto_candidates_by_label_level": {
            level: _pareto_candidates(
                {
                    method: {**result, **result["by_label_level"][level]}
                    for method, result in metrics.items()
                    if level in result["by_label_level"]
                }
            )
            for level in sorted(
                {level for result in metrics.values() for level in result["by_label_level"]}
            )
        },
        "pareto_candidates": [],
        "selection_state": "blocked_until_gate_and_locked_test",
        "freeze_gate_proposal": proposal.model_dump(mode="json"),
        "locked_test_state": "not_authorized",
    }
    _write_json_file(run_dir / "freeze_gate_proposal.json", proposal.model_dump(mode="json"))
    _write_json_file(run_dir / "benchmark_summary.json", summary)
    _write_versioned_json_file(
        run_dir / f"freeze_gate_proposal--{evidence_run_id}.json",
        proposal.model_dump(mode="json"),
    )
    _write_versioned_json_file(
        run_dir / f"benchmark_summary--{evidence_run_id}.json", summary
    )
    return summary


def _benchmark_metric_block(
    test: pd.DataFrame, ood: pd.DataFrame, metadata: dict[str, Any]
) -> dict[str, Any]:
    coverage, set_size = (
        _prediction_set_metrics(test)
        if metadata.get("probability_semantics") == "prediction_set"
        else (None, None)
    )
    ood_assessable = ~ood["assignment_state"].isin(["unavailable", "not_assessed"])
    ood_assessed = ood.loc[ood_assessable]
    return {
        "n_test_observations": int(len(test)),
        "exact_accuracy": float(accuracy_score(test["true_label"], test["predicted_label"])),
        "macro_f1": float(f1_score(test["true_label"], test["predicted_label"], average="macro")),
        "hierarchical_error": _hierarchical_error(test),
        "calibration": _calibration_metrics(test, metadata),
        "composition_mae": _composition_mae(test),
        "prediction_set_coverage": coverage,
        "mean_prediction_set_size": set_size,
        "n_development_ood_observations": _unique_observation_count(ood),
        "n_development_ood_evaluations": int(len(ood)),
        "n_development_ood_assessed_evaluations": int(len(ood_assessed)),
        "ood_assessment_coverage": float(ood_assessable.mean()) if len(ood) else None,
        "false_reassurance": (
            float(
                (~ood_assessed["assignment_state"].isin(
                    ["unknown", "unknown_uncalibrated", "conformal_empty"]
                )).mean()
            )
            if len(ood_assessed)
            else None
        ),
        "per_state": _per_state_metrics(test),
        "sensitivity": {
            "gene_masking": {"state": "not_assessed"},
            "sample_preserving_downsampling": {"state": "not_assessed"},
            "preprocessing_swap": {"state": "not_assessed"},
        },
    }


def _unique_observation_count(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    columns = [column for column in ("asset_id", "observation_id") if column in frame]
    return int(frame[columns].astype(str).drop_duplicates().shape[0])


def _load_resource(name: str) -> dict[str, Any]:
    return yaml.safe_load(
        files("bridge.tool_packages.p0_02_cell_state.resources")
        .joinpath(name)
        .read_text(encoding="utf-8")
    )


def _donor_rotation_records(asset: dict[str, Any]) -> list[BenchmarkSplitRecord]:
    frame = _read_metadata(asset)
    sample_ids = _sample_ids(frame, asset)
    samples = sorted(sample_ids.unique())
    if len(samples) < 3:
        raise BenchmarkError("at_least_three_independent_samples_required", asset["asset_id"])
    records = []
    for index, test_sample in enumerate(samples):
        calibration_sample = samples[(index + 1) % len(samples)]
        fold_id = f"fold-{index + 1:02d}"
        for sample in samples:
            partition = (
                "test"
                if sample == test_sample
                else "calibration"
                if sample == calibration_sample
                else "train"
            )
            records.append(_record(asset, sample_ids, sample, partition, fold_id))
    return records


def _single_partition_records(
    asset: dict[str, Any], partition: str
) -> list[BenchmarkSplitRecord]:
    frame = _read_metadata(asset)
    sample_ids = _sample_ids(frame, asset)
    return [
        _record(asset, sample_ids, sample, partition, None)
        for sample in sorted(sample_ids.unique())
    ]


def _record(
    asset: dict[str, Any],
    sample_ids: pd.Series,
    sample: str,
    partition: str,
    fold_id: str | None,
) -> BenchmarkSplitRecord:
    return BenchmarkSplitRecord(
        asset_id=asset["asset_id"],
        source_family_id=asset["source_family_id"],
        sample_id=sample,
        partition=partition,
        data_role=asset["data_role"],
        fold_id=fold_id,
        n_observations=int(sample_ids.eq(sample).sum()),
    )


def _sample_ids(frame: pd.DataFrame, asset: dict[str, Any]) -> pd.Series:
    sample_column = asset.get("sample_column")
    if sample_column:
        if sample_column not in frame:
            raise BenchmarkError("benchmark_sample_column_not_found", str(sample_column))
        values = frame[sample_column]
    elif asset.get("sample_id_value"):
        values = pd.Series(str(asset["sample_id_value"]), index=frame.index)
    else:
        raise BenchmarkError("asset_catalog_incomplete", "sample_column_or_sample_id_value")
    if values.isna().any() or values.astype(str).str.strip().eq("").any():
        raise BenchmarkError("benchmark_sample_id_missing", str(asset.get("asset_id", "")))
    return values.astype(str)


def _read_metadata(asset: dict[str, Any]) -> pd.DataFrame:
    path = Path(_required(asset, "path"))
    if path.suffix == ".tsv":
        frame = pd.read_csv(path, sep="\t")
        return _filter_metadata(frame, asset)[0]
    if path.suffix == ".h5ad":
        import anndata as ad

        adata = ad.read_h5ad(path, backed="r")
        try:
            return _filter_metadata(adata.obs.copy(), asset)[0]
        finally:
            adata.file.close()
    raise BenchmarkError("benchmark_asset_format_not_supported", path.suffix)


def _load_expression_asset(asset: dict[str, Any]) -> dict[str, Any]:
    path = Path(_required(asset, "path"))
    if path.suffix != ".h5ad":
        raise BenchmarkError("benchmark_expression_requires_h5ad", asset["asset_id"])
    source_sha256 = _sha256(path)
    if asset.get("checksum") and asset["checksum"] != source_sha256:
        raise BenchmarkError("benchmark_asset_checksum_mismatch", asset["asset_id"])
    import anndata as ad

    adata = ad.read_h5ad(path)
    location = asset.get("matrix_location", "X")
    if location == "X":
        matrix = adata.X
    elif location.startswith("layers/") and location[7:] in adata.layers:
        matrix = adata.layers[location[7:]]
    else:
        raise BenchmarkError("benchmark_matrix_location_not_found", location)
    matrix = sparse.csr_matrix(matrix, dtype=np.float32)
    obs, mask = _filter_metadata(adata.obs.copy(), asset)
    matrix = matrix[mask]
    obs.insert(0, "observation_id", obs.index.astype(str))
    obs["sample_id"] = _sample_ids(obs, asset)
    level = str(asset.get("label_level", "L1"))
    if "__bridge_true_label" in obs:
        obs["true_label"] = obs.pop("__bridge_true_label")
    else:
        obs["true_label"] = None
    genes = np.asarray([str(value).strip().upper() for value in adata.var_names])
    if len(set(genes)) != len(genes):
        raise BenchmarkError("benchmark_gene_ids_not_unique")
    semantics = str(asset.get("matrix_semantics", ""))
    raw_counts = None
    if semantics == "raw_counts":
        if np.any(matrix.data < 0) or not np.allclose(matrix.data, np.rint(matrix.data)):
            raise BenchmarkError("raw_counts_must_be_nonnegative_integers", asset["asset_id"])
        raw_counts = matrix.copy()
    normalized = _normalize_matrix(matrix, semantics)
    context_columns = [
        column for column in asset.get("metadata_columns", []) if column in obs.columns
    ]
    return {
        "matrix": normalized,
        "raw_counts": raw_counts,
        "genes": genes,
        "obs": obs[["observation_id", "sample_id", "true_label", *context_columns]],
        "label_level": level,
        "context_columns": context_columns,
        "source_sha256": source_sha256,
    }


def _filter_metadata(
    frame: pd.DataFrame, asset: dict[str, Any]
) -> tuple[pd.DataFrame, np.ndarray]:
    mask = np.ones(len(frame), dtype=bool)
    for column, expected in asset.get("filters", {}).items():
        if column not in frame:
            raise BenchmarkError("benchmark_filter_column_not_found", str(column))
        allowed = {str(item) for item in expected} if isinstance(expected, list) else {str(expected)}
        mask &= frame[column].astype(str).isin(allowed).to_numpy()

    label_column = asset.get("label_column")
    mapped = pd.Series(None, index=frame.index, dtype=object)
    if label_column:
        if label_column not in frame:
            raise BenchmarkError("benchmark_label_column_not_found", str(label_column))
        level = str(asset.get("label_level", "L1"))
        review = load_biological_review_draft()
        allowed_states = {
            card.state_id: card for card in review.state_reviews if card.level == level
        }
        aliases = review.alias_decisions
        mapped = frame[label_column].astype(str).map(
            lambda raw: aliases.get(raw, raw)
        ).map(lambda value: value if value.startswith(f"{level}:") else f"{level}:{value}")
        mapped = mapped.where(mapped.isin(allowed_states))
        mask &= mapped.notna().to_numpy()
        parent_column = asset.get("parent_label_column")
        if level == "L2" and parent_column:
            if parent_column not in frame:
                raise BenchmarkError("benchmark_parent_label_column_not_found", str(parent_column))
            expected_parent = mapped.map(
                {
                    state_id: card.parent_state_ids[0]
                    for state_id, card in allowed_states.items()
                    if card.parent_state_ids
                }
            )
            observed_parent = frame[parent_column].astype(str).map(
                lambda value: value if value.startswith("L1:") else f"L1:{value}"
            )
            mask &= expected_parent.eq(observed_parent).to_numpy()

    filtered = frame.loc[mask].copy()
    if label_column:
        filtered["__bridge_true_label"] = mapped.loc[mask].astype(str)
    return filtered, mask


def _normalize_matrix(matrix: sparse.csr_matrix, semantics: str) -> sparse.csr_matrix:
    matrix = matrix.astype(np.float32, copy=True)
    if semantics == "raw_counts":
        totals = np.asarray(matrix.sum(axis=1)).ravel()
        scale = np.divide(10_000.0, totals, out=np.zeros_like(totals), where=totals > 0)
        matrix = sparse.diags(scale) @ matrix
        matrix.data = np.log1p(matrix.data)
    elif semantics != "normalized_expression":
        raise BenchmarkError("benchmark_matrix_semantics_unsupported", semantics)
    return matrix.tocsr()


def _write_exchange_bundle(root: Path, asset: dict[str, Any], data: dict[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    matrix = data["raw_counts"] if data["raw_counts"] is not None else data["matrix"]
    semantics = "raw_counts" if data["raw_counts"] is not None else "normalized_expression"
    if _exchange_bundle_matches(root, asset, data, matrix.shape, semantics):
        manifest_path = root / "bundle.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if payload.get("data_role") != asset["data_role"]:
            payload["data_role"] = asset["data_role"]
            _write_json_file(manifest_path, payload)
        return
    matrix_path = root / "matrix.h5"
    _write_sparse_h5(matrix_path, matrix)
    genes_path = root / "features.tsv"
    pd.Series(data["genes"]).to_csv(genes_path, index=False, header=False)
    observations_path = root / "observations.parquet"
    data["obs"].to_parquet(observations_path, index=False)
    observations_tsv = root / "observations.tsv"
    data["obs"].to_csv(observations_tsv, sep="\t", index=False)
    payload = {
        "bundle_version": "0.2.0",
        "asset_id": asset["asset_id"],
        "source_family_id": asset["source_family_id"],
        "source_sha256": data["source_sha256"],
        "assay": asset["assay"],
        "data_role": asset["data_role"],
        "label_level": data["label_level"],
        "label_universe": _label_universe_for_level(data["label_level"]),
        "matrix_shape": list(matrix.shape),
        "matrix_semantics": semantics,
        "artifacts": {
            "matrix.h5": _sha256(matrix_path),
            "features.tsv": _sha256(genes_path),
            "observations.parquet": _sha256(observations_path),
            "observations.tsv": _sha256(observations_tsv),
        },
    }
    _write_json_file(root / "bundle.json", payload)


def _exchange_bundle_matches(
    root: Path,
    asset: dict[str, Any],
    data: dict[str, Any],
    shape: tuple[int, int],
    semantics: str,
) -> bool:
    try:
        payload = json.loads((root / "bundle.json").read_text(encoding="utf-8"))
        expected = {
            "bundle_version": "0.2.0",
            "asset_id": asset["asset_id"],
            "source_sha256": data["source_sha256"],
            "matrix_shape": list(shape),
            "matrix_semantics": semantics,
            "label_universe": _label_universe_for_level(data["label_level"]),
        }
        if any(payload.get(key) != value for key, value in expected.items()):
            return False
        artifacts = payload.get("artifacts", {})
        return bool(artifacts) and all(
            (root / name).is_file() and _sha256(root / name) == checksum
            for name, checksum in artifacts.items()
        )
    except (OSError, ValueError, TypeError):
        return False


def _label_universe_for_level(level: str) -> list[str]:
    return sorted(
        card.state_id
        for card in load_biological_review_draft().state_reviews
        if card.level == level
    )


def _write_sparse_h5(path: Path, matrix: sparse.csr_matrix) -> None:
    matrix = sparse.csr_matrix(matrix)
    with h5py.File(path, "w", track_order=False) as handle:
        group = handle.create_group("matrix", track_order=False)
        group.attrs["format"] = "csr"
        group.create_dataset(
            "shape", data=np.asarray(matrix.shape, dtype=np.int64), track_times=False
        )
        group.create_dataset(
            "data", data=matrix.data, compression="lzf", shuffle=True, track_times=False
        )
        group.create_dataset(
            "indices",
            data=matrix.indices,
            compression="lzf",
            shuffle=True,
            track_times=False,
        )
        group.create_dataset(
            "indptr",
            data=matrix.indptr,
            compression="lzf",
            shuffle=True,
            track_times=False,
        )


def _run_native_method(
    method: str,
    asset: dict[str, Any],
    data: dict[str, Any],
    records: list[BenchmarkSplitRecord],
    *,
    auxiliary: list[tuple[dict[str, Any], dict[str, Any]]],
) -> pd.DataFrame:
    frames = []
    obs = data["obs"].reset_index(drop=True)
    for fold_id in sorted({record.fold_id for record in records if record.fold_id}):
        partition_by_sample = {
            record.sample_id: record.partition
            for record in records
            if record.fold_id == fold_id
        }
        partitions = obs["sample_id"].map(partition_by_sample)
        train_mask = partitions.eq("train").to_numpy()
        predict_mask = partitions.isin(["calibration", "test"]).to_numpy()
        if not train_mask.any() or not predict_mask.any():
            continue
        correlation_model = None
        if method == "source_specific_correlation":
            correlation_model = _fit_correlation(
                data["matrix"], data["genes"], obs, train_mask
            )
            labels, scores, margins = _apply_correlation(
                correlation_model,
                data["matrix"][predict_mask],
                data["genes"],
            )
        else:
            try:
                labels, scores, margins = _marker_predict(
                    data["matrix"], data["genes"], data["label_level"], predict_mask
                )
            except BenchmarkError as exc:
                if exc.reason_code == "marker_program_gene_coverage_insufficient":
                    return pd.DataFrame()
                raise
        frames.append(
            _prediction_frame(
                obs.loc[predict_mask].copy(),
                asset,
                fold_id,
                partitions.loc[predict_mask].to_numpy(),
                data["label_level"],
                labels,
                scores,
                margins,
                "assigned_uncalibrated",
            )
        )
        for auxiliary_asset, auxiliary_data in auxiliary:
            if auxiliary_data["label_level"] != data["label_level"]:
                continue
            auxiliary_mask = np.ones(len(auxiliary_data["obs"]), dtype=bool)
            partition = (
                "development_ood"
                if auxiliary_asset["data_role"] == "development_ood"
                else "behavior_only"
            )
            try:
                if method == "source_specific_correlation":
                    labels, scores, margins = _apply_correlation(
                        correlation_model,
                        auxiliary_data["matrix"],
                        auxiliary_data["genes"],
                    )
                else:
                    labels, scores, margins = _marker_predict(
                        auxiliary_data["matrix"],
                        auxiliary_data["genes"],
                        auxiliary_data["label_level"],
                        auxiliary_mask,
                    )
                assignment_state = "forced_mapping_uncalibrated"
                unavailable_reason = None
            except BenchmarkError as exc:
                if exc.reason_code not in {
                    "benchmark_gene_overlap_insufficient",
                    "marker_program_gene_coverage_insufficient",
                }:
                    raise
                labels = ["__unavailable__"] * len(auxiliary_data["obs"])
                scores = margins = np.full(len(labels), np.nan)
                assignment_state = "not_assessed"
                unavailable_reason = exc.reason_code
            auxiliary_frame = _prediction_frame(
                auxiliary_data["obs"].copy(),
                auxiliary_asset,
                fold_id,
                np.repeat(partition, len(labels)),
                auxiliary_data["label_level"],
                labels,
                scores,
                margins,
                assignment_state,
            )
            if unavailable_reason:
                auxiliary_frame["unavailable_reason"] = unavailable_reason
            frames.append(auxiliary_frame)
    frames = [frame.dropna(axis=1, how="all") for frame in frames]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _fit_correlation(
    matrix: sparse.csr_matrix,
    genes: np.ndarray,
    obs: pd.DataFrame,
    train_mask: np.ndarray,
) -> dict[str, Any]:
    selected_features = _variable_features(matrix[train_mask], genes, max_features=2000)
    train = matrix[train_mask][:, selected_features]
    train_obs = obs.loc[train_mask].reset_index(drop=True)
    profiles = []
    profile_labels = []
    for label in sorted(train_obs["true_label"].dropna().unique()):
        sample_profiles = []
        for sample in sorted(train_obs.loc[train_obs["true_label"].eq(label), "sample_id"].unique()):
            mask = train_obs["true_label"].eq(label) & train_obs["sample_id"].eq(sample)
            sample_profiles.append(np.asarray(train[mask.to_numpy()].mean(axis=0)).ravel())
        profiles.append(np.median(np.vstack(sample_profiles), axis=0))
        profile_labels.append(label)
    return {
        "genes": genes[selected_features],
        "profiles": np.vstack(profiles),
        "labels": profile_labels,
    }


def _apply_correlation(
    model: dict[str, Any] | None,
    matrix: sparse.csr_matrix,
    genes: np.ndarray,
) -> tuple[list[str], np.ndarray, np.ndarray]:
    if model is None:
        raise BenchmarkError("correlation_model_not_fitted")
    query_index = {gene: index for index, gene in enumerate(genes)}
    model_indices = []
    query_indices = []
    for index, gene in enumerate(model["genes"]):
        if gene in query_index:
            model_indices.append(index)
            query_indices.append(query_index[gene])
    if len(query_indices) < 2:
        raise BenchmarkError("benchmark_gene_overlap_insufficient")
    profiles = model["profiles"][:, model_indices]
    profile_rank = _rank_normalize_rows(profiles)
    labels: list[str] = []
    scores: list[np.ndarray] = []
    margins: list[np.ndarray] = []
    for start in range(0, matrix.shape[0], 2048):
        query = matrix[start : start + 2048, query_indices].toarray()
        correlations = _rank_normalize_rows(query) @ profile_rank.T
        order = np.argsort(correlations, axis=1)
        top = order[:, -1]
        second = order[:, -2] if correlations.shape[1] > 1 else top
        labels.extend(model["labels"][index] for index in top)
        scores.append(correlations[np.arange(len(top)), top])
        margins.append(
            correlations[np.arange(len(top)), top]
            - correlations[np.arange(len(top)), second]
        )
    return (
        labels,
        np.concatenate(scores),
        np.concatenate(margins),
    )


def _prediction_frame(
    observations: pd.DataFrame,
    asset: dict[str, Any],
    fold_id: str,
    partitions: np.ndarray,
    label_level: str,
    labels: list[str],
    scores: np.ndarray,
    margins: np.ndarray,
    assignment_state: str,
) -> pd.DataFrame:
    observations["asset_id"] = asset["asset_id"]
    observations["source_family_id"] = asset["source_family_id"]
    observations["fold_id"] = fold_id
    observations["partition"] = partitions
    observations["label_level"] = label_level
    observations["predicted_label"] = labels
    observations["score"] = scores
    observations["margin"] = margins
    observations["assignment_state"] = assignment_state
    observations["prediction_set"] = [json.dumps([label]) for label in labels]
    observations["unavailable_reason"] = ""
    return observations


def _marker_predict(
    matrix: sparse.csr_matrix,
    genes: np.ndarray,
    level: str,
    predict_mask: np.ndarray,
) -> tuple[list[str], np.ndarray, np.ndarray]:
    _, cards = load_packaged_marker_programs()
    observed_states = {
        card.state_id
        for card in load_biological_review_draft().state_reviews
        if card.level == level and card.n_observations > 0
    }
    gene_index = {gene: index for index, gene in enumerate(genes)}
    labels = []
    columns = []
    query = matrix[predict_mask]
    for card in cards:
        if card.level != level or card.state_id not in observed_states:
            continue
        positive = [gene_index[gene] for gene in card.positive_markers if gene in gene_index]
        if not positive:
            continue
        negative = [gene_index[gene] for gene in card.negative_markers if gene in gene_index]
        score = np.asarray(query[:, positive].mean(axis=1)).ravel()
        if negative:
            score -= np.asarray(query[:, negative].mean(axis=1)).ravel()
        labels.append(card.state_id)
        columns.append(score)
    if not columns:
        raise BenchmarkError("marker_program_gene_coverage_insufficient")
    score_matrix = np.column_stack(columns)
    order = np.argsort(score_matrix, axis=1)
    top = order[:, -1]
    second = order[:, -2] if score_matrix.shape[1] > 1 else top
    return (
        [labels[index] for index in top],
        score_matrix[np.arange(len(top)), top],
        score_matrix[np.arange(len(top)), top] - score_matrix[np.arange(len(top)), second],
    )


def _variable_features(matrix: sparse.csr_matrix, genes: np.ndarray, max_features: int) -> np.ndarray:
    if matrix.shape[1] <= max_features:
        return np.arange(matrix.shape[1])
    mean = np.asarray(matrix.mean(axis=0)).ravel()
    squared = np.asarray(matrix.power(2).mean(axis=0)).ravel()
    variance = np.maximum(squared - mean**2, 0)
    marker_genes = {
        gene
        for card in load_packaged_marker_programs()[1]
        for gene in card.positive_markers + card.negative_markers
    }
    marker_indices = {index for index, gene in enumerate(genes) if gene in marker_genes}
    variable = list(np.argsort(variance)[::-1])
    selected = list(sorted(marker_indices))
    selected.extend(index for index in variable if index not in marker_indices)
    return np.asarray(selected[:max_features])


def _rank_normalize_rows(values: np.ndarray) -> np.ndarray:
    ranked = rankdata(values, axis=1)
    ranked -= ranked.mean(axis=1, keepdims=True)
    scale = np.linalg.norm(ranked, axis=1, keepdims=True)
    return ranked / np.maximum(scale, 1e-12)


def _composition_mae(frame: pd.DataFrame) -> float:
    errors = []
    for _, group in frame.groupby(["asset_id", "sample_id"], sort=True):
        labels = sorted(set(group["true_label"]) | set(group["predicted_label"]))
        truth = group["true_label"].value_counts(normalize=True).reindex(labels, fill_value=0)
        prediction = (
            group["predicted_label"].value_counts(normalize=True).reindex(labels, fill_value=0)
        )
        errors.append(float(np.abs(truth - prediction).mean()))
    return float(np.mean(errors))


def _hierarchical_error(frame: pd.DataFrame) -> dict[str, float]:
    review = load_biological_review_draft()
    parents = {
        card.state_id: card.parent_state_ids[0]
        for card in review.state_reviews
        if card.parent_state_ids
    }
    wrong = frame["true_label"].astype(str).ne(frame["predicted_label"].astype(str))
    if not wrong.any():
        return {"within_parent_error_rate": 0.0, "cross_parent_error_rate": 0.0}
    true_parent = frame["true_label"].map(parents)
    predicted_parent = frame["predicted_label"].map(parents)
    within = wrong & true_parent.notna() & true_parent.eq(predicted_parent)
    cross = wrong & ~within
    return {
        "within_parent_error_rate": float(within.mean()),
        "cross_parent_error_rate": float(cross.mean()),
    }


def _calibration_metrics(frame: pd.DataFrame, metadata: dict[str, Any]) -> dict[str, Any]:
    if "label_level" in frame and frame["label_level"].astype(str).nunique() > 1:
        return {"state": "not_assessed", "reason": "mixed_label_levels"}
    probability_columns = [
        column
        for column in frame
        if column.startswith("prob__") and frame[column].notna().any()
    ]
    if metadata.get("probability_semantics") != "categorical_simplex":
        return {"state": "not_assessed", "reason": "categorical_simplex_required"}
    if len(probability_columns) < 2:
        return {"state": "not_assessed", "reason": "probability_columns_missing"}
    probabilities = frame[probability_columns].to_numpy(dtype=float)
    if np.isnan(probabilities).any():
        raise BenchmarkError("probability_values_invalid")
    labels = np.asarray([column.removeprefix("prob__") for column in probability_columns])
    if not np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-5):
        raise BenchmarkError("probability_rows_must_sum_to_one")
    true = frame["true_label"].astype(str).to_numpy()
    if not set(true).issubset(set(labels)):
        return {"state": "not_assessed", "reason": "true_label_outside_probability_columns"}
    top = probabilities.argmax(axis=1)
    confidence = probabilities[np.arange(len(probabilities)), top]
    correct = labels[top] == true
    bins = np.minimum((confidence * 10).astype(int), 9)
    ece = 0.0
    for index in range(10):
        selected = bins == index
        if selected.any():
            ece += selected.mean() * abs(correct[selected].mean() - confidence[selected].mean())
    true_index = {label: index for index, label in enumerate(labels)}
    target = np.zeros_like(probabilities)
    target[np.arange(len(true)), [true_index[label] for label in true]] = 1.0
    return {
        "state": "measured",
        "top_label_ece_10bin": float(ece),
        "multiclass_brier": float(np.mean(np.sum((probabilities - target) ** 2, axis=1))),
    }


def _prediction_metadata(path: Path) -> dict[str, Any]:
    metadata_path = Path(f"{path}.metadata.json")
    if not metadata_path.is_file():
        contract = METHOD_ADAPTER_CONTRACTS.get(path.stem)
        if contract is None or path.stem not in {
            "source_specific_correlation",
            "marker_program_evidence",
        }:
            raise BenchmarkError("adapter_metadata_not_found", path.stem)
        return {
            "adapter": "native",
            **{key: value for key, value in contract.items() if key not in {"label_levels", "include_auxiliary"}},
        }
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkError("adapter_metadata_invalid", path.stem) from exc
    required = {"adapter", "evidence_family", "output_sha256"}
    if not required.issubset(metadata):
        raise BenchmarkError("adapter_metadata_incomplete", path.stem)
    provenance = {
        "split_manifest_sha256",
        "split_manifest_id",
        "benchmark_spec_ref",
        "input_bundle_sha256",
    }
    if metadata.get("adapter") != "native" and not provenance.issubset(metadata):
        raise BenchmarkError("adapter_input_provenance_missing", path.stem)
    if metadata["output_sha256"] != _sha256(path):
        raise BenchmarkError("adapter_output_checksum_mismatch", path.stem)
    contract = METHOD_ADAPTER_CONTRACTS.get(str(metadata["adapter"]))
    if contract is None:
        raise BenchmarkError("adapter_contract_not_registered", str(metadata["adapter"]))
    defaults = {
        "independent_evidence_vote": True,
        "query_expression_used_as_unlabeled_during_training": False,
    }
    for key, expected in contract.items():
        if key in {"label_levels", "include_auxiliary"}:
            continue
        actual = metadata.get(key, defaults.get(key))
        if actual != expected:
            raise BenchmarkError("adapter_contract_mismatch", f"{metadata['adapter']}:{key}")
        metadata[key] = expected
    return metadata


def _validate_benchmark_run(
    run_dir: Path, manifest: dict[str, Any]
) -> BenchmarkSplitManifest:
    split_path = run_dir / "split_manifest.json"
    if not split_path.is_file() or manifest.get("split_manifest_sha256") != _sha256(split_path):
        raise BenchmarkError("benchmark_split_artifact_mismatch")
    split = BenchmarkSplitManifest.model_validate_json(split_path.read_text(encoding="utf-8"))
    if split.model_dump(mode="json") != manifest.get("split_manifest"):
        raise BenchmarkError("benchmark_split_manifest_mismatch")
    spec = CellStateBenchmarkSpec.model_validate(manifest.get("benchmark_spec"))
    if (
        split.benchmark_spec_sha256 != _model_sha256(spec)
        or manifest.get("benchmark_spec_sha256") != split.benchmark_spec_sha256
    ):
        raise BenchmarkError("benchmark_spec_artifact_mismatch")
    if manifest.get("adapter_contract_sha256") != _adapter_contract_sha256(spec):
        raise BenchmarkError("adapter_contract_artifact_mismatch")
    if manifest.get("adapter_implementation_sha256") != _adapter_implementation_hashes():
        raise BenchmarkError("adapter_implementation_artifact_mismatch")
    hashes = manifest.get("native_artifact_hashes")
    if not isinstance(hashes, dict) or not hashes:
        raise BenchmarkError("native_artifact_manifest_missing")
    for relative, expected in hashes.items():
        path = _resolve_relative_artifact(run_dir, str(relative))
        if not path.is_file() or _sha256(path) != expected:
            raise BenchmarkError("native_artifact_checksum_mismatch", str(relative))
    return split


def _validate_prediction_provenance(
    run_dir: Path,
    path: Path,
    frame: pd.DataFrame,
    metadata: dict[str, Any],
    manifest: dict[str, Any],
    split: BenchmarkSplitManifest,
) -> None:
    _validate_frame_against_split(frame, split)
    _validate_prediction_coverage(run_dir, frame, split)
    if metadata["adapter"] == "native":
        relative = path.relative_to(run_dir).as_posix()
        if manifest["native_artifact_hashes"].get(relative) != _sha256(path):
            raise BenchmarkError("native_prediction_not_bound_to_run", relative)
        return
    if (
        metadata.get("split_manifest_sha256") != manifest.get("split_manifest_sha256")
        or metadata.get("split_manifest_id") != split.split_manifest_id
        or metadata.get("benchmark_spec_ref") != split.benchmark_spec_ref
    ):
        raise BenchmarkError("adapter_split_provenance_mismatch", path.stem)
    if (
        metadata["adapter"] != "scconform_calibration"
        and metadata.get("seed") != manifest["benchmark_spec"]["random_seed"]
    ):
        raise BenchmarkError("adapter_seed_mismatch", path.stem)
    bundle_hashes = metadata.get("input_bundle_sha256")
    if not isinstance(bundle_hashes, dict):
        raise BenchmarkError("adapter_input_provenance_missing", path.stem)
    asset_ids = set(frame["asset_id"].astype(str))
    if set(bundle_hashes) != asset_ids:
        raise BenchmarkError("adapter_input_asset_set_mismatch", path.stem)
    for asset_id in sorted(asset_ids):
        relative = f"exchange/{asset_id}/bundle.json"
        expected = manifest["native_artifact_hashes"].get(relative)
        if expected is None or bundle_hashes.get(asset_id) != expected:
            raise BenchmarkError("adapter_input_bundle_mismatch", asset_id)
    if metadata["adapter"] == "scconform_calibration":
        _validate_scconform_lineage(run_dir, path, frame, metadata)


def _validate_scconform_lineage(
    run_dir: Path, path: Path, frame: pd.DataFrame, metadata: dict[str, Any]
) -> None:
    asset_ids = sorted(set(frame["asset_id"].astype(str)))
    if len(asset_ids) != 1:
        raise BenchmarkError("scconform_base_asset_ambiguous", path.stem)
    stem = f"scanvi--{asset_ids[0]}"
    base_path = next(
        (
            candidate
            for candidate in (
                run_dir / "predictions" / f"{stem}.parquet",
                run_dir / "predictions" / f"{stem}.tsv",
            )
            if candidate.is_file()
        ),
        None,
    )
    if base_path is None:
        raise BenchmarkError("scconform_base_prediction_missing", stem)
    base_metadata_path = Path(f"{base_path}.metadata.json")
    base_metadata = _prediction_metadata(base_path)
    if (
        base_metadata.get("adapter") != "scanvi"
        or base_metadata.get("probability_semantics") != "categorical_simplex"
        or base_metadata.get("conformal_eligible") is not True
        or metadata.get("base_adapter") != "scanvi"
        or metadata.get("probability_metadata_sha256") != _sha256(base_metadata_path)
    ):
        raise BenchmarkError("scconform_base_contract_mismatch", stem)

    input_path = base_path
    if metadata.get("base_prediction_sha256") != _sha256(base_path):
        manifest_path = run_dir / "exchange" / "scconform_input" / f"{stem}.tsv.manifest.json"
        try:
            conversion = json.loads(manifest_path.read_text(encoding="utf-8"))
            input_path = manifest_path.with_name(str(conversion["output"]))
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise BenchmarkError("scconform_conversion_manifest_invalid", stem) from exc
        if (
            conversion.get("source_sha256") != _sha256(base_path)
            or conversion.get("output_sha256") != metadata.get("base_prediction_sha256")
            or not input_path.is_file()
            or _sha256(input_path) != conversion.get("output_sha256")
        ):
            raise BenchmarkError("scconform_conversion_lineage_mismatch", stem)
        _assert_prediction_content_equal(_read_table(base_path), _read_table(input_path), stem)

    source = _read_table(input_path)
    _validate_probability_frame(source, require_predicted_label=True)
    expected = source.loc[source["partition"].eq("test")].copy()
    if not frame["partition"].eq("test").all():
        raise BenchmarkError("scconform_test_partition_only", stem)
    shared = [
        "fold_id",
        "observation_id",
        "partition",
        "true_label",
        "predicted_label",
        *sorted(column for column in source if column.startswith("prob__")),
    ]
    _assert_prediction_content_equal(expected[shared], frame[shared], stem)
    _validate_scconform_prediction_sets(
        source, frame, alpha=float(metadata["alpha"]), detail=stem
    )


def _validate_scconform_prediction_sets(
    source: pd.DataFrame, observed: pd.DataFrame, *, alpha: float, detail: str
) -> None:
    probability_columns = sorted(column for column in source if column.startswith("prob__"))
    labels = [column.removeprefix("prob__") for column in probability_columns]
    expected: dict[tuple[str, str], list[str]] = {}
    for fold_id in sorted(source["fold_id"].astype(str).unique()):
        current = source["fold_id"].astype(str).eq(fold_id)
        calibration = source.loc[current & source["partition"].eq("calibration")]
        test = source.loc[current & source["partition"].eq("test")]
        if calibration.empty or test.empty:
            raise BenchmarkError("scconform_calibration_partition_invalid", detail)
        label_index = {label: index for index, label in enumerate(labels)}
        try:
            columns = [label_index[str(label)] for label in calibration["true_label"]]
        except KeyError as exc:
            raise BenchmarkError("scconform_calibration_label_invalid", detail) from exc
        probabilities = calibration[probability_columns].to_numpy(dtype=float)
        conformity = 1.0 - probabilities[np.arange(len(calibration)), columns]
        quantile = math.ceil((len(calibration) + 1) * (1.0 - alpha)) / len(calibration)
        if quantile > 1.0:
            raise BenchmarkError("scconform_calibration_too_small", detail)
        threshold = 1.0 - float(np.quantile(conformity, quantile, method="linear"))
        test_probabilities = test[probability_columns].to_numpy(dtype=float)
        test_ids = test[["fold_id", "observation_id"]].itertuples(index=False, name=None)
        for (row_fold, observation_id), row_probabilities in zip(
            test_ids, test_probabilities, strict=True
        ):
            selected = [
                label
                for label, probability in zip(labels, row_probabilities, strict=True)
                if float(probability) >= threshold
            ]
            expected[(str(row_fold), str(observation_id))] = selected

    for row in observed.itertuples(index=False):
        key = (str(row.fold_id), str(row.observation_id))
        try:
            actual = json.loads(str(row.prediction_set))
        except (TypeError, json.JSONDecodeError) as exc:
            raise BenchmarkError("scconform_prediction_set_invalid", detail) from exc
        if (
            not isinstance(actual, list)
            or any(not isinstance(label, str) for label in actual)
            or len(actual) != len(set(actual))
            or sorted(actual) != sorted(expected.get(key, []))
        ):
            raise BenchmarkError("scconform_prediction_set_mismatch", detail)
        state = (
            "conformal_empty"
            if not actual
            else "conformal_singleton"
            if len(actual) == 1
            else "conformal_set"
        )
        if str(row.assignment_state) != state:
            raise BenchmarkError("scconform_assignment_state_mismatch", detail)


def _assert_prediction_content_equal(
    expected: pd.DataFrame, observed: pd.DataFrame, detail: str
) -> None:
    order = ["fold_id", "observation_id"]
    expected = expected.sort_values(order).reset_index(drop=True)
    observed = observed.sort_values(order).reset_index(drop=True)
    if list(expected.columns) != list(observed.columns) or len(expected) != len(observed):
        raise BenchmarkError("prediction_content_mismatch", detail)
    for column in expected:
        left, right = expected[column], observed[column]
        if pd.api.types.is_numeric_dtype(left) and pd.api.types.is_numeric_dtype(right):
            if pd.api.types.is_integer_dtype(left) and pd.api.types.is_integer_dtype(right):
                matches = np.array_equal(left.to_numpy(), right.to_numpy())
            else:
                matches = np.allclose(
                    pd.to_numeric(left),
                    pd.to_numeric(right),
                    rtol=1e-12,
                    atol=1e-12,
                    equal_nan=True,
                )
            if not matches:
                raise BenchmarkError("prediction_content_mismatch", detail)
        elif not left.astype(str).equals(right.astype(str)):
            raise BenchmarkError("prediction_content_mismatch", detail)
def _validate_frame_against_split(
    frame: pd.DataFrame, split: BenchmarkSplitManifest
) -> None:
    folded = {
        (record.asset_id, str(record.fold_id), record.sample_id): (
            record.partition,
            record.source_family_id,
        )
        for record in split.records
        if record.fold_id is not None
    }
    ungrouped = {
        record.asset_id: (record.partition, record.source_family_id)
        for record in split.records
        if record.fold_id is None
    }
    for row in frame[
        ["asset_id", "fold_id", "sample_id", "partition", "source_family_id"]
    ].astype(str).drop_duplicates().itertuples(index=False):
        expected = folded.get((row.asset_id, row.fold_id, row.sample_id))
        if expected is None:
            expected = ungrouped.get(row.asset_id)
        if expected != (row.partition, row.source_family_id):
            raise BenchmarkError("prediction_split_membership_mismatch", row.asset_id)


def _validate_prediction_coverage(
    run_dir: Path, frame: pd.DataFrame, split: BenchmarkSplitManifest
) -> None:
    for asset_id in sorted(frame["asset_id"].astype(str).unique()):
        observations_path = run_dir / "exchange" / asset_id / "observations.parquet"
        if not observations_path.is_file():
            raise BenchmarkError("prediction_observation_manifest_missing", asset_id)
        observations = pd.read_parquet(
            observations_path, columns=["observation_id", "sample_id", "true_label"]
        ).astype({"observation_id": str, "sample_id": str})
        if observations["observation_id"].duplicated().any():
            raise BenchmarkError("benchmark_observation_ids_not_unique", asset_id)
        expected_by_sample = observations.groupby("sample_id")["observation_id"].agg(set)
        records = [record for record in split.records if record.asset_id == asset_id]
        if not records:
            raise BenchmarkError("prediction_asset_not_in_split", asset_id)
        current = frame.loc[frame["asset_id"].astype(str).eq(asset_id)].copy()
        actual_ids = set(current["observation_id"].astype(str))
        if not actual_ids.issubset(set(observations["observation_id"])):
            raise BenchmarkError("prediction_observation_not_in_input", asset_id)
        expected_context = observations.set_index("observation_id")[["sample_id", "true_label"]]
        actual_context = current[["observation_id", "sample_id", "true_label"]].copy()
        actual_context["observation_id"] = actual_context["observation_id"].astype(str)
        actual_context["sample_id"] = actual_context["sample_id"].astype(str)
        if actual_context.drop_duplicates().groupby("observation_id").size().gt(1).any():
            raise BenchmarkError("prediction_observation_context_conflict", asset_id)
        actual_context = actual_context.drop_duplicates().set_index("observation_id")
        expected = expected_context.loc[actual_context.index]
        if (
            actual_context["sample_id"].ne(expected["sample_id"]).any()
            or actual_context["true_label"].fillna("").astype(str).ne(
                expected["true_label"].fillna("").astype(str)
            ).any()
        ):
            raise BenchmarkError("prediction_observation_context_mismatch", asset_id)

        folded = [record for record in records if record.fold_id is not None]
        if folded:
            required_partitions = {"test"}
            required_partitions.update(
                partition
                for partition in ("calibration", "train")
                if current["partition"].astype(str).eq(partition).any()
            )
            for fold_id in sorted({str(record.fold_id) for record in folded}):
                for partition in sorted(required_partitions):
                    sample_ids = {
                        record.sample_id
                        for record in folded
                        if str(record.fold_id) == fold_id and record.partition == partition
                    }
                    expected = set().union(
                        *(expected_by_sample.get(sample_id, set()) for sample_id in sample_ids)
                    )
                    actual = set(
                        current.loc[
                            current["fold_id"].astype(str).eq(fold_id)
                            & current["partition"].astype(str).eq(partition),
                            "observation_id",
                        ].astype(str)
                    )
                    if actual != expected:
                        raise BenchmarkError(
                            "prediction_observation_coverage_mismatch",
                            f"{asset_id}:{fold_id}:{partition}",
                        )
        else:
            expected = set(observations["observation_id"])
            for fold_id in sorted(current["fold_id"].astype(str).unique()):
                actual = set(
                    current.loc[
                        current["fold_id"].astype(str).eq(fold_id), "observation_id"
                    ].astype(str)
                )
                if actual != expected:
                    raise BenchmarkError(
                        "prediction_observation_coverage_mismatch", f"{asset_id}:{fold_id}"
                    )


def _validate_method_asset_coverage(
    run_dir: Path,
    method: str,
    frame: pd.DataFrame,
    split: BenchmarkSplitManifest,
) -> None:
    contract = METHOD_ADAPTER_CONTRACTS.get(method)
    if contract is None:
        raise BenchmarkError("adapter_contract_not_registered", method)
    expected: set[str] = set()
    for asset_id in sorted({record.asset_id for record in split.records}):
        bundle_path = run_dir / "exchange" / asset_id / "bundle.json"
        try:
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BenchmarkError("adapter_input_provenance_missing", asset_id) from exc
        if bundle.get("label_level") not in contract["label_levels"]:
            continue
        role = bundle.get("data_role")
        if role == "labeled_reference" or (
            contract["include_auxiliary"] and role in {"development_ood", "behavior_only"}
        ):
            expected.add(asset_id)
    actual = set(frame["asset_id"].astype(str))
    if actual != expected:
        detail = f"{method}:missing={sorted(expected - actual)}:extra={sorted(actual - expected)}"
        raise BenchmarkError("adapter_asset_coverage_mismatch", detail)


def _resolve_relative_artifact(root: Path, relative: str) -> Path:
    value = Path(relative)
    if value.is_absolute() or not value.parts or ".." in value.parts:
        raise BenchmarkError("artifact_path_invalid", relative)
    path = (root / value).resolve()
    if path != root.resolve() and root.resolve() not in path.parents:
        raise BenchmarkError("artifact_path_invalid", relative)
    return path


def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".tsv":
        return pd.read_csv(path, sep="\t")
    raise BenchmarkError("prediction_format_not_supported", path.suffix)


def _validate_prediction_frame(frame: pd.DataFrame) -> None:
    required = {
        "fold_id",
        "observation_id",
        "sample_id",
        "asset_id",
        "source_family_id",
        "partition",
        "label_level",
        "true_label",
        "predicted_label",
        "assignment_state",
        "prediction_set",
    }
    if not required.issubset(frame.columns):
        raise BenchmarkError(
            "prediction_contract_incomplete", ",".join(sorted(required - set(frame.columns)))
        )
    identity = ["asset_id", "label_level", "fold_id", "observation_id"]
    if frame[identity].astype(str).duplicated().any():
        raise BenchmarkError("prediction_observation_ids_not_unique")


def _prediction_set_metrics(frame: pd.DataFrame) -> tuple[float | None, float | None]:
    if "prediction_set" not in frame:
        return None, None
    sets: list[list[str]] = []
    for raw in frame["prediction_set"]:
        try:
            value = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError as exc:
            raise BenchmarkError("prediction_set_invalid") from exc
        if not isinstance(value, list):
            raise BenchmarkError("prediction_set_invalid")
        sets.append([str(item) for item in value])
    if not sets:
        return None, None
    coverage = np.mean(
        [str(label) in prediction_set for label, prediction_set in zip(frame["true_label"], sets)]
    )
    return float(coverage), float(np.mean([len(value) for value in sets]))


def _per_state_metrics(frame: pd.DataFrame) -> dict[str, dict[str, float | int]]:
    labels = sorted(set(frame["true_label"]) | set(frame["predicted_label"]))
    precision, recall, f1, support = precision_recall_fscore_support(
        frame["true_label"],
        frame["predicted_label"],
        labels=labels,
        zero_division=0,
    )
    return {
        label: {
            "n": int(support[index]),
            "precision": float(precision[index]),
            "recall": float(recall[index]),
            "f1": float(f1[index]),
        }
        for index, label in enumerate(labels)
    }


def _pareto_candidates(metrics: dict[str, dict[str, Any]]) -> list[str]:
    eligible = {
        method: result
        for method, result in metrics.items()
        if result.get("independent_evidence_vote", True)
        and result.get("evaluation_protocol", "inductive") == "inductive"
    }
    by_family: dict[str, list[str]] = {}
    for method, result in eligible.items():
        by_family.setdefault(str(result["evidence_family"]), []).append(method)
    representatives = {
        min(
            methods,
            key=lambda method: (
                -eligible[method]["exact_accuracy"],
                eligible[method]["composition_mae"],
                method,
            ),
        )
        for methods in by_family.values()
    }
    candidates = []
    for method in sorted(representatives):
        result = eligible[method]
        dominated = any(
            other != method
            and other in representatives
            and other_result["exact_accuracy"] >= result["exact_accuracy"]
            and other_result["composition_mae"] <= result["composition_mae"]
            and (
                other_result["exact_accuracy"] > result["exact_accuracy"]
                or other_result["composition_mae"] < result["composition_mae"]
            )
            for other, other_result in eligible.items()
        )
        if not dominated:
            candidates.append(method)
    return sorted(candidates)


def _evaluation_protocol(metadata: dict[str, Any]) -> str:
    if metadata.get("adapter") == "scconform_calibration":
        return (
            "calibration_layer_on_transductive_base"
            if metadata.get("query_expression_used_as_unlabeled_during_training") is True
            else "calibration_layer"
        )
    if metadata.get("query_expression_used_as_unlabeled_during_training") is True:
        return "transductive_unlabeled_query"
    return "inductive"


def _benchmark_run_id(spec: CellStateBenchmarkSpec, split: BenchmarkSplitManifest) -> str:
    payload = json.dumps(
        {
            "implementation_version": BENCHMARK_IMPLEMENTATION_VERSION,
            "environment": _environment_snapshot(),
            "adapter_contract_sha256": _adapter_contract_sha256(spec),
            "spec": spec.model_dump(mode="json"),
            "split": split.model_dump(mode="json"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"CELLSTATE-PILOT-{hashlib.sha256(payload.encode()).hexdigest()[:12]}"


def _environment_snapshot() -> dict[str, str]:
    packages = ["anndata", "h5py", "numpy", "pandas", "pyarrow", "scipy", "scikit-learn"]
    snapshot = {"python": platform.python_version()}
    for package in packages:
        try:
            snapshot[package] = version(package)
        except PackageNotFoundError:
            snapshot[package] = "not_installed"
    return snapshot


def _reference_snapshot_sha256(manifest: dict[str, Any]) -> str:
    spec = manifest["benchmark_spec"]
    resources = Path(__file__).resolve().parent / "resources"
    return _json_sha256(
        {
            "annotation_vocabulary_ref": spec["annotation_vocabulary_ref"],
            "reference_snapshot_ref": spec["reference_snapshot_ref"],
            "resource_sha256": {
                name: _sha256(resources / name)
                for name in ("annotation_vocabulary.yaml", "marker_programs.yaml")
            },
            "asset_sha256": {
                asset_id: manifest["asset_sha256"][asset_id]
                for asset_id in sorted(spec["development_asset_ids"])
            },
        }
    )


def _evidence_artifact_hashes(
    run_dir: Path, prediction_paths: Sequence[Path]
) -> dict[str, str]:
    paths = list(prediction_paths)
    paths.extend(
        metadata
        for path in prediction_paths
        if (metadata := Path(f"{path}.metadata.json")).is_file()
    )
    if any(path.stem.startswith("scconform_calibration") for path in prediction_paths):
        conversion_root = run_dir / "exchange" / "scconform_input"
        if conversion_root.is_dir():
            paths.extend(path for path in conversion_root.rglob("*") if path.is_file())
    return {
        path.relative_to(run_dir).as_posix(): _sha256(path) for path in sorted(set(paths))
    }


def _artifact_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _core_artifact_hashes(root: Path) -> dict[str, str]:
    native_predictions = {
        "predictions/source_specific_correlation.parquet",
        "predictions/marker_program_evidence.parquet",
    }
    return {
        relative: checksum
        for relative, checksum in _artifact_hashes(root).items()
        if not relative.startswith("predictions/") or relative in native_predictions
    }


def _native_artifact_hashes(root: Path) -> dict[str, str]:
    native_predictions = {
        "predictions/source_specific_correlation.parquet",
        "predictions/marker_program_evidence.parquet",
    }
    return {
        relative: checksum
        for relative, checksum in _artifact_hashes(root).items()
        if relative.startswith("exchange/") or relative in native_predictions
    }


def _write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_versioned_json_file(path: Path, payload: dict[str, Any]) -> None:
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
    except FileExistsError as exc:
        if path.read_text(encoding="utf-8") != content:
            raise BenchmarkError("versioned_evidence_collision", path.name) from exc


def _load_asset_catalog(path: Path) -> list[dict[str, Any]]:
    try:
        catalog = yaml.safe_load(path.read_text(encoding="utf-8"))
        assets = catalog["assets"]
    except (OSError, KeyError, TypeError, yaml.YAMLError) as exc:
        raise BenchmarkError("asset_catalog_invalid") from exc
    if not isinstance(assets, list) or not all(isinstance(asset, dict) for asset in assets):
        raise BenchmarkError("asset_catalog_invalid")
    asset_ids = [str(asset.get("asset_id", "")) for asset in assets]
    if any(not asset_id for asset_id in asset_ids) or len(asset_ids) != len(set(asset_ids)):
        raise BenchmarkError("asset_catalog_asset_ids_invalid")
    return assets


def _validate_selected_asset(
    asset: dict[str, Any], spec: CellStateBenchmarkSpec, expected_role: str | None
) -> None:
    asset_id = str(asset.get("asset_id", ""))
    source_family = str(_required(asset, "source_family_id"))
    source_accession = str(_required(asset, "source_accession"))
    root_source_family = str(_required(asset, "root_source_family_id"))
    leakage_group = str(_required(asset, "leakage_group"))
    derived_from = asset.get("derived_from")
    if not isinstance(derived_from, list) or any(
        not isinstance(value, str) or not value for value in derived_from
    ):
        raise BenchmarkError("asset_catalog_incomplete", "derived_from")
    role = str(asset.get("data_role", ""))
    assay = str(asset.get("assay", ""))
    access_policy = str(_required(asset, "access_policy")).lower()
    path = Path(_required(asset, "path"))
    checksum = str(_required(asset, "checksum"))
    normalized = {
        "".join(character for character in value.upper() if character.isalnum())
        for value in (
            asset_id,
            source_family,
            source_accession,
            root_source_family,
            leakage_group,
            *derived_from,
        )
    }
    denied_name = any(
        denied in identifier
        for identifier in normalized
        for denied in _DENIED_IDENTIFIERS
    )
    denied_policy = "sealed" in access_policy or "competitor" in access_policy
    if denied_name or denied_policy:
        raise BenchmarkError("sealed_or_denied_asset_selected", asset_id)
    if (
        len(checksum) != 64
        or any(character not in "0123456789abcdef" for character in checksum)
        or not path.is_file()
    ):
        raise BenchmarkError("benchmark_asset_checksum_invalid", asset_id)
    if _sha256(path) != checksum:
        raise BenchmarkError("benchmark_asset_checksum_mismatch", asset_id)
    if assay != spec.assay:
        raise BenchmarkError("benchmark_asset_assay_mismatch", asset_id)
    if expected_role is not None and role != expected_role:
        raise BenchmarkError("benchmark_asset_role_mismatch", f"{asset_id}:{role}")
    if spec.phase == "locked" and role not in {"locked_source_holdout", "locked_ood"}:
        raise BenchmarkError("benchmark_asset_role_mismatch", f"{asset_id}:{role}")


def _validate_catalog_role_isolation(
    assets: list[dict[str, Any]], spec: CellStateBenchmarkSpec
) -> None:
    role_assets = {
        "development": set(spec.development_asset_ids),
        "development_ood": set(spec.development_ood_asset_ids),
        "behavior_only": set(spec.behavior_only_asset_ids),
        "locked": set(spec.locked_asset_ids),
        "sealed": set(spec.sealed_asset_ids),
    }
    roles = {
        asset_id: role for role, asset_ids in role_assets.items() for asset_id in asset_ids
    }
    assets_by_id = {str(asset.get("asset_id", "")): asset for asset in assets}
    lineage: dict[str, set[str]] = {}

    def resolve(asset_id: str, visiting: set[str]) -> set[str]:
        if asset_id in lineage:
            return lineage[asset_id]
        if asset_id in visiting:
            raise BenchmarkError("asset_catalog_lineage_cycle", asset_id)
        asset = assets_by_id.get(asset_id)
        if asset is None:
            lineage[asset_id] = {_normalize_lineage_token(asset_id)}
            return lineage[asset_id]
        derived_from = asset.get("derived_from")
        if not isinstance(derived_from, list) or any(
            not isinstance(value, str) or not value for value in derived_from
        ):
            raise BenchmarkError("asset_catalog_incomplete", "derived_from")
        values = [
            asset_id,
            str(_required(asset, "source_family_id")),
            str(_required(asset, "source_accession")),
            str(_required(asset, "root_source_family_id")),
            str(_required(asset, "leakage_group")),
            *derived_from,
        ]
        tokens = {_normalize_lineage_token(value) for value in values}
        tokens.discard("")
        next_visiting = {*visiting, asset_id}
        for parent_id in derived_from:
            if parent_id in assets_by_id:
                tokens.update(resolve(parent_id, next_visiting))
        lineage[asset_id] = tokens
        return tokens

    for asset_id in roles:
        resolve(asset_id, set())
    asset_ids = sorted(roles)
    for index, left in enumerate(asset_ids):
        for right in asset_ids[index + 1 :]:
            if roles[left] == roles[right]:
                continue
            if lineage[left] & lineage[right]:
                if "sealed" in {roles[left], roles[right]}:
                    selected = right if roles[left] == "sealed" else left
                    raise BenchmarkError("sealed_or_denied_asset_selected", selected)
                raise BenchmarkError(
                    "benchmark_role_lineage_overlap",
                    f"{left}:{roles[left]}|{right}:{roles[right]}",
                )


def _normalize_lineage_token(value: str) -> str:
    return "".join(character for character in value.upper() if character.isalnum())


def _required(payload: dict[str, Any], key: str) -> Any:
    value = payload.get(key)
    if value in {None, ""}:
        raise BenchmarkError("asset_catalog_incomplete", key)
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _split_manifest_id(spec: CellStateBenchmarkSpec, catalog_path: Path) -> str:
    token = hashlib.sha256(
        f"{spec.benchmark_spec_id}:{spec.phase}:{spec.random_seed}:{_sha256(catalog_path)}".encode()
    ).hexdigest()[:12]
    return f"CELLSTATE-SPLIT-{spec.phase}-{token}"
