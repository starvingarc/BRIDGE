from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import hashlib
import importlib
import importlib.util
import json

import anndata as ad
import pandas as pd
import pytest

from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitAssignmentArtifact,
    observation_ids_sha256,
)
from bridge.tool_packages.p0_06_proliferation_stress_response import (
    method_models,
    method_runtime,
    observation_source,
)
from bridge.toolkit.contracts import (
    CellStateEvidenceProfileV3,
    ExecutionState,
    StructuredInputRef,
    ToolRequestV2,
)
from bridge.toolkit.registry import ToolRegistry
from tests.test_p0_06_real_methods import _canonical_bytes, _method_request


def test_process_method_input_v2_requires_one_source_descriptor(tmp_path: Path) -> None:
    source_model = getattr(method_models, "ProcessObservationSourceV1", None)
    input_model = getattr(method_models, "ProcessMethodInputV2", None)
    assert source_model is not None, "source-bound descriptor model is missing"
    assert input_model is not None, "source-bound method input model is missing"

    source = source_model(
        source_format="p0_02_cell_state_evidence_parquet_v0.1",
        producer_tool_id="P0-02",
        producer_run_ref="run-source-demo",
        producer_tool_version="0.5.0",
        artifact_manifest_path=(tmp_path / "artifact_manifest.json").resolve(),
        artifact_manifest_sha256="a" * 64,
        evidence_artifact_id="artifact:run-source-demo:evidence",
        evidence_path=(tmp_path / "cell_state_evidence.parquet").resolve(),
        evidence_sha256="b" * 64,
        label_level="L1",
    )
    payload = {
        "object_version": "0.2.0",
        "method_input_id": "process-method-input:source-demo",
        "method_input_version": "2.0.0",
        "product_case_ref": "product-case:demo@1.0.0",
        "product_case_sha256": "c" * 64,
        "cell_state_profile_id": "cell-state-profile:run-source-demo",
        "cell_state_profile_sha256": "d" * 64,
        "data_view_ref": "data-view:source-demo",
        "observation_ids_sha256": "e" * 64,
        "biological_unit_manifest_ref": "biological-unit-manifest:source-demo@1.0.0",
        "biological_unit_manifest_sha256": "f" * 64,
        "biological_unit_assignment_sha256": "1" * 64,
        "source_observations": source.model_dump(mode="python"),
        "created_at": datetime(2026, 9, 7, tzinfo=timezone.utc),
    }

    model = input_model.model_validate(payload)

    assert model.object_version == "0.2.0"
    assert model.source_observations.evidence_artifact_id == (
        "artifact:run-source-demo:evidence"
    )
    assert not hasattr(model, "observation_states")
    with pytest.raises(ValueError):
        input_model.model_validate(
            {
                **payload,
                "observation_states": [
                    {
                        "observation_id": "obs-1",
                        "state_id": "state:target",
                        "state": "candidate",
                    }
                ],
            }
        )


def _source_bound_fixture(
    tmp_path: Path,
) -> tuple[method_models.ProcessMethodInputV2, CellStateEvidenceProfileV3, Path]:
    request = _method_request(tmp_path)
    refs = {item.role: item for item in request.object_inputs}
    profile_path = refs["cell_state_evidence_profile"].path
    profile_payload = json.loads(profile_path.read_text(encoding="utf-8"))
    observation_ids = ["demo-cell-000", "demo-cell-001", "demo-cell-002", "demo-cell-003"]
    profile_payload["n_observations"] = len(observation_ids)
    profile_payload["input_data_view"]["n_observations"] = len(observation_ids)
    profile_payload["input_data_view"]["observation_ids_sha256"] = (
        observation_ids_sha256(observation_ids)
    )
    profile_payload["composition"] = {
        "state": "shadow",
        "records": [
            {
                "view": "reconciliation_state",
                "source_id": None,
                "label": support_state,
                "label_level": "L1",
                "state_evidence_state": state,
                "denominator_scope": "selected_data_view",
                "count": 1,
                "fraction": 0.25,
                "denominator": 4,
            }
            for support_state, state in (
                ("consensus_supported", "candidate"),
                ("single_source_supported", "candidate"),
                ("source_conflict", "unresolved"),
                ("unavailable", "unavailable"),
            )
        ]
        + [
            {
                "view": "consensus_supported_only",
                "source_id": None,
                "label": "state:target",
                "label_level": "L1",
                "state_evidence_state": "candidate",
                "denominator_scope": "selected_data_view",
                "count": 1,
                "fraction": 0.25,
                "denominator": 4,
            }
        ],
    }
    profile_raw = _canonical_bytes(profile_payload)
    profile_path.write_bytes(profile_raw)
    profile_sha = hashlib.sha256(profile_raw).hexdigest()
    profile = CellStateEvidenceProfileV3.model_validate(profile_payload)

    evidence_path = (tmp_path / "cell_state_evidence.parquet").resolve()
    pd.DataFrame(
        [
            {
                "observation_id": observation_ids[0],
                "prediction_set": '["state:target"]',
                "consensus_label": "state:target",
                "support_state": "consensus_supported",
                "assignment_state": "shadow_candidate",
                "open_set_state": "not_assessed",
            },
            {
                "observation_id": observation_ids[1],
                "prediction_set": '["state:outside"]',
                "consensus_label": None,
                "support_state": "single_source_supported",
                "assignment_state": "shadow_candidate",
                "open_set_state": "not_assessed",
            },
            {
                "observation_id": observation_ids[2],
                "prediction_set": '["state:outside","state:target"]',
                "consensus_label": None,
                "support_state": "source_conflict",
                "assignment_state": "shadow_candidate",
                "open_set_state": "not_assessed",
            },
            {
                "observation_id": observation_ids[3],
                "prediction_set": "[]",
                "consensus_label": None,
                "support_state": "unavailable",
                "assignment_state": "unavailable",
                "open_set_state": "not_assessed",
            },
        ]
    ).to_parquet(evidence_path, index=False)
    evidence_sha = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    producer_run = profile.producer_run_ref
    evidence_artifact_id = f"artifact:{producer_run}:evidence"
    manifest_path = (tmp_path / "artifact_manifest.json").resolve()
    manifest_payload = {
        "run_id": producer_run,
        "tool_id": "P0-02",
        "tool_version": profile.producer_tool_version,
        "environment_spec_id": profile.environment_spec_ref,
        "input_hash": "8" * 64,
        "reference_snapshot_id": profile.reference_snapshot_ref,
        "reference_manifest_hash": profile.reference_manifest_sha256,
        "measurement_spec_ref": profile.measurement_spec_id,
        "measurement_spec_sha256": profile.measurement_spec_sha256,
        "artifacts": [
            {
                "artifact_id": f"artifact:{producer_run}:profile-v3",
                "kind": "cell_state_profile_v3",
                "path": str(profile_path.resolve()),
                "media_type": "application/json",
                "sha256": profile_sha,
                "evidence_ids": [],
                "size_bytes": profile_path.stat().st_size,
            },
            {
                "artifact_id": evidence_artifact_id,
                "kind": "cell_state_evidence",
                "path": str(evidence_path),
                "media_type": "application/vnd.apache.parquet",
                "sha256": evidence_sha,
                "evidence_ids": [],
                "size_bytes": evidence_path.stat().st_size,
            },
        ],
        "visualizations": [],
    }
    manifest_raw = _canonical_bytes(manifest_payload)
    manifest_path.write_bytes(manifest_raw)
    manifest_sha = hashlib.sha256(manifest_raw).hexdigest()

    prior_input = json.loads(
        refs["process_method_input"].path.read_text(encoding="utf-8")
    )
    prior_input.pop("observation_states")
    prior_input.update(
        {
            "object_version": "0.2.0",
            "method_input_version": "2.0.0",
            "cell_state_profile_sha256": profile_sha,
            "observation_ids_sha256": observation_ids_sha256(observation_ids),
            "source_observations": {
                "source_format": "p0_02_cell_state_evidence_parquet_v0.1",
                "producer_tool_id": "P0-02",
                "producer_run_ref": producer_run,
                "producer_tool_version": profile.producer_tool_version,
                "artifact_manifest_path": str(manifest_path),
                "artifact_manifest_sha256": manifest_sha,
                "evidence_artifact_id": evidence_artifact_id,
                "evidence_path": str(evidence_path),
                "evidence_sha256": evidence_sha,
                "label_level": "L1",
            },
        }
    )
    return (
        method_models.ProcessMethodInputV2.model_validate(prior_input),
        profile,
        profile_path,
    )


def test_source_parser_preserves_all_four_producer_support_states(
    tmp_path: Path,
) -> None:
    module_name = (
        "bridge.tool_packages.p0_06_proliferation_stress_response."
        "observation_source"
    )
    assert importlib.util.find_spec(module_name) is not None, (
        "source observation parser is missing"
    )
    source_module = importlib.import_module(module_name)
    method_input, profile, profile_path = _source_bound_fixture(tmp_path)

    loaded = source_module.load_source_observations(
        method_input=method_input,
        cell_state=profile,
        cell_state_path=profile_path,
    )

    assert [row.state for row in loaded.rows] == [
        "candidate",
        "candidate",
        "unresolved",
        "unavailable",
    ]
    assert loaded.rows[0].state_id == "state:target"
    assert loaded.rows[0].support_state == "consensus_supported"
    assert loaded.rows[1].state_id == "state:outside"
    assert loaded.rows[1].support_state == "single_source_supported"
    resolved_conflict = loaded.rows[2]
    assert resolved_conflict.prediction_set == ["state:outside", "state:target"]
    assert resolved_conflict.state_id is None
    assert resolved_conflict.support_state == "source_conflict"
    assigned_to_state = {
        row.observation_id: row.state_id is not None for row in loaded.rows
    }
    conflict_observation_ids = [
        row.observation_id
        for row in loaded.rows
        if row.support_state == "source_conflict"
    ]
    assert all(
        not assigned_to_state[row_id] for row_id in conflict_observation_ids
    )
    assert loaded.rows[3].prediction_set == []
    assert loaded.rows[3].state_id is None
    assert all(row.state != "unknown" for row in loaded.rows)



def _source_bound_request(
    tmp_path: Path,
    *,
    all_conflict: bool = False,
) -> ToolRequestV2:
    request = _method_request(tmp_path)
    refs = {item.role: item for item in request.object_inputs}
    assignment_payload = json.loads(
        refs["biological_unit_assignment"].path.read_text(encoding="utf-8")
    )
    observation_ids = [
        item["observation_id"] for item in assignment_payload["assignments"]
    ]
    rows: list[dict[str, object]] = []
    if all_conflict:
        for observation_id in observation_ids:
            rows.append(
                {
                    "observation_id": observation_id,
                    "prediction_set": '["state:outside","state:target"]',
                    "consensus_label": None,
                    "support_state": "source_conflict",
                    "assignment_state": "shadow_candidate",
                    "open_set_state": "not_assessed",
                }
            )
        reconciliation = [("source_conflict", "unresolved", 96)]
        consensus: list[tuple[str, int]] = []
    else:
        for index, observation_id in enumerate(observation_ids):
            if index < 24:
                predictions = '["state:target"]'
                consensus_label = "state:target"
                support = "consensus_supported"
                assignment = "shadow_candidate"
            elif index < 48:
                predictions = '["state:outside"]'
                consensus_label = None
                support = "single_source_supported"
                assignment = "shadow_candidate"
            elif index < 72:
                predictions = '["state:outside","state:target"]'
                consensus_label = None
                support = "source_conflict"
                assignment = "shadow_candidate"
            else:
                predictions = "[]"
                consensus_label = None
                support = "unavailable"
                assignment = "unavailable"
            rows.append(
                {
                    "observation_id": observation_id,
                    "prediction_set": predictions,
                    "consensus_label": consensus_label,
                    "support_state": support,
                    "assignment_state": assignment,
                    "open_set_state": "not_assessed",
                }
            )
        reconciliation = [
            ("consensus_supported", "candidate", 24),
            ("single_source_supported", "candidate", 24),
            ("source_conflict", "unresolved", 24),
            ("unavailable", "unavailable", 24),
        ]
        consensus = [("state:target", 24)]

    profile_ref = refs["cell_state_evidence_profile"]
    profile_payload = json.loads(profile_ref.path.read_text(encoding="utf-8"))
    profile_payload["prediction_sets"]["state_counts"] = {
        label: count for label, _, count in reconciliation
    }
    profile_payload["composition"] = {
        "state": "shadow",
        "records": [
            {
                "view": "reconciliation_state",
                "source_id": None,
                "label": label,
                "label_level": "L1",
                "state_evidence_state": state,
                "denominator_scope": "selected_data_view",
                "count": count,
                "fraction": count / 96,
                "denominator": 96,
            }
            for label, state, count in reconciliation
        ]
        + [
            {
                "view": "consensus_supported_only",
                "source_id": None,
                "label": label,
                "label_level": "L1",
                "state_evidence_state": "candidate",
                "denominator_scope": "selected_data_view",
                "count": count,
                "fraction": count / 96,
                "denominator": 96,
            }
            for label, count in consensus
        ],
    }
    profile_raw = _canonical_bytes(profile_payload)
    profile_ref.path.write_bytes(profile_raw)
    profile_sha = hashlib.sha256(profile_raw).hexdigest()
    profile_ref = profile_ref.model_copy(update={"sha256": profile_sha})
    profile = CellStateEvidenceProfileV3.model_validate(profile_payload)

    source_root = tmp_path / "p0-02-source"
    source_root.mkdir()
    evidence_path = (source_root / "cell_state_evidence.parquet").resolve()
    pd.DataFrame(rows).to_parquet(evidence_path, index=False)
    evidence_sha = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    evidence_artifact_id = f"artifact:{profile.producer_run_ref}:evidence"
    manifest_path = (source_root / "artifact_manifest.json").resolve()
    manifest_payload = {
        "run_id": profile.producer_run_ref,
        "tool_id": profile.producer_tool_id,
        "tool_version": profile.producer_tool_version,
        "environment_spec_id": profile.environment_spec_ref,
        "input_hash": "8" * 64,
        "reference_snapshot_id": profile.reference_snapshot_ref,
        "reference_manifest_hash": profile.reference_manifest_sha256,
        "measurement_spec_ref": profile.measurement_spec_id,
        "measurement_spec_sha256": profile.measurement_spec_sha256,
        "artifacts": [
            {
                "artifact_id": (
                    f"artifact:{profile.producer_run_ref}:profile-v3"
                ),
                "kind": "cell_state_profile_v3",
                "path": str(profile_ref.path.resolve()),
                "media_type": "application/json",
                "sha256": profile_sha,
                "evidence_ids": [],
                "size_bytes": profile_ref.path.stat().st_size,
            },
            {
                "artifact_id": evidence_artifact_id,
                "kind": "cell_state_evidence",
                "path": str(evidence_path),
                "media_type": "application/vnd.apache.parquet",
                "sha256": evidence_sha,
                "evidence_ids": [],
                "size_bytes": evidence_path.stat().st_size,
            },
        ],
        "visualizations": [],
    }
    manifest_raw = _canonical_bytes(manifest_payload)
    manifest_path.write_bytes(manifest_raw)

    process_ref = refs["process_method_input"]
    process_payload = json.loads(process_ref.path.read_text(encoding="utf-8"))
    process_payload.pop("observation_states")
    process_payload.update(
        {
            "object_version": "0.2.0",
            "method_input_version": "2.0.0",
            "cell_state_profile_sha256": profile_sha,
            "source_observations": {
                "source_format": "p0_02_cell_state_evidence_parquet_v0.1",
                "producer_tool_id": "P0-02",
                "producer_run_ref": profile.producer_run_ref,
                "producer_tool_version": profile.producer_tool_version,
                "artifact_manifest_path": str(manifest_path),
                "artifact_manifest_sha256": hashlib.sha256(
                    manifest_raw
                ).hexdigest(),
                "evidence_artifact_id": evidence_artifact_id,
                "evidence_path": str(evidence_path),
                "evidence_sha256": evidence_sha,
                "label_level": "L1",
            },
        }
    )
    process_raw = _canonical_bytes(process_payload)
    process_ref.path.write_bytes(process_raw)
    process_ref = StructuredInputRef(
        input_id=process_ref.input_id,
        role=process_ref.role,
        schema_ref="bridge://schemas/process-method-input/v0.2",
        object_version="0.2.0",
        path=process_ref.path,
        sha256=hashlib.sha256(process_raw).hexdigest(),
        media_type=process_ref.media_type,
    )
    replacements = {
        "cell_state_evidence_profile": profile_ref,
        "process_method_input": process_ref,
    }
    return request.model_copy(
        update={
            "object_inputs": [
                replacements.get(item.role, item) for item in request.object_inputs
            ]
        }
    )


def test_source_bound_runtime_keeps_whole_product_denominator_and_filters_states(
    tmp_path: Path,
) -> None:
    request = _source_bound_request(tmp_path)
    registry = ToolRegistry.load_default()

    eligibility = registry.check_eligibility(request)
    assert eligibility.eligible, eligibility.reason_codes
    run = registry.run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    bundle_path = next(
        item.path for item in run.artifacts if item.kind == "process_method_bundle"
    )
    bundle = method_models.ProcessMethodBundleV2.model_validate_json(
        bundle_path.read_text(encoding="utf-8")
    )
    whole_product_counts = [
        item.n_observations
        for item in bundle.program_scores
        if item.method_id is method_models.ProcessMethodId.SCANPY_SCORE_GENES
        and item.program_id == "program:proliferation"
        and item.analysis_scope == "whole_product"
    ]
    state_specific = [
        item
        for item in bundle.program_scores
        if item.method_id is method_models.ProcessMethodId.SCANPY_SCORE_GENES
        and item.program_id == "program:proliferation"
        and item.analysis_scope == "state_specific"
    ]

    assert sum(whole_product_counts) == 96
    process_input_sha = next(
        item.sha256
        for item in request.object_inputs
        if item.role == "process_method_input"
    )
    assert bundle.method_input_sha256 == process_input_sha
    assert sum(item.n_observations for item in state_specific) == 24
    assert {item.cell_state_id for item in state_specific} == {"state:target"}
    assert all(item.cell_state_id != "state:outside" for item in state_specific)
    assert run.result["runtime_mode"] == "method_runtime"
    assert run.result["domain_score"] is None
    assert run.result["score_state"] == "unavailable"


def test_all_conflict_source_produces_no_fake_state_specific_result(
    tmp_path: Path,
) -> None:
    request = _source_bound_request(tmp_path, all_conflict=True)
    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    bundle_path = next(
        item.path for item in run.artifacts if item.kind == "process_method_bundle"
    )
    bundle = method_models.ProcessMethodBundleV2.model_validate_json(
        bundle_path.read_text(encoding="utf-8")
    )
    whole_product_counts = [
        item.n_observations
        for item in bundle.program_scores
        if item.method_id is method_models.ProcessMethodId.SCANPY_SCORE_GENES
        and item.program_id == "program:proliferation"
        and item.analysis_scope == "whole_product"
    ]

    assert sum(whole_product_counts) == 96
    assert not [
        item
        for item in bundle.program_scores
        if item.analysis_scope == "state_specific"
    ]
    assert not [
        item
        for item in bundle.cell_cycle_summaries
        if item.analysis_scope == "state_specific"
    ]



def _rewrite_evidence(
    method_input: method_models.ProcessMethodInputV2,
    frame: pd.DataFrame,
) -> method_models.ProcessMethodInputV2:
    source = method_input.source_observations
    frame.to_parquet(source.evidence_path, index=False)
    evidence_sha = hashlib.sha256(source.evidence_path.read_bytes()).hexdigest()
    manifest = json.loads(
        source.artifact_manifest_path.read_text(encoding="utf-8")
    )
    artifact = next(
        item
        for item in manifest["artifacts"]
        if item["artifact_id"] == source.evidence_artifact_id
    )
    artifact["sha256"] = evidence_sha
    artifact["size_bytes"] = source.evidence_path.stat().st_size
    manifest_raw = _canonical_bytes(manifest)
    source.artifact_manifest_path.write_bytes(manifest_raw)
    return method_input.model_copy(
        update={
            "source_observations": source.model_copy(
                update={
                    "evidence_sha256": evidence_sha,
                    "artifact_manifest_sha256": hashlib.sha256(
                        manifest_raw
                    ).hexdigest(),
                }
            )
        }
    )


def _malform_source_evidence(
    frame: pd.DataFrame,
    mutation: str,
) -> pd.DataFrame:
    frame = frame.copy()
    if mutation == "empty_consensus_prediction":
        index = frame.index[
            frame["support_state"] == "consensus_supported"
        ][0]
        frame.loc[index, "prediction_set"] = "[]"
    elif mutation == "empty_single_source_prediction":
        index = frame.index[
            frame["support_state"] == "single_source_supported"
        ][0]
        frame.loc[index, "prediction_set"] = "[]"
    elif mutation == "invalid_candidate_identifier":
        index = frame.index[
            frame["support_state"] == "consensus_supported"
        ][0]
        frame.loc[index, "prediction_set"] = '["state:invalid label"]'
        frame.loc[index, "consensus_label"] = "state:invalid label"
    elif mutation == "array_semantic_field":
        frame["support_state"] = [
            [value, "unexpected"] for value in frame["support_state"].tolist()
        ]
    else:
        raise AssertionError(f"unknown mutation: {mutation}")
    return frame


def _rewrite_request_evidence(
    request: ToolRequestV2,
    mutation: str,
) -> ToolRequestV2:
    process_ref = next(
        item for item in request.object_inputs if item.role == "process_method_input"
    )
    method_input = method_models.ProcessMethodInputV2.model_validate_json(
        process_ref.path.read_text(encoding="utf-8")
    )
    frame = pd.read_parquet(method_input.source_observations.evidence_path)
    malformed = _malform_source_evidence(frame, mutation)
    method_input = _rewrite_evidence(method_input, malformed)
    process_raw = _canonical_bytes(method_input.model_dump(mode="json"))
    process_ref.path.write_bytes(process_raw)
    updated_ref = process_ref.model_copy(
        update={"sha256": hashlib.sha256(process_raw).hexdigest()}
    )
    return request.model_copy(
        update={
            "object_inputs": [
                updated_ref if item.role == "process_method_input" else item
                for item in request.object_inputs
            ]
        }
    )


_MALFORMED_SEMANTIC_ROWS = [
    "empty_consensus_prediction",
    "empty_single_source_prediction",
    "invalid_candidate_identifier",
    "array_semantic_field",
]


@pytest.mark.parametrize("mutation", _MALFORMED_SEMANTIC_ROWS)
def test_source_parser_types_malformed_semantic_rows(
    tmp_path: Path,
    mutation: str,
) -> None:
    method_input, profile, profile_path = _source_bound_fixture(tmp_path)
    frame = pd.read_parquet(method_input.source_observations.evidence_path)
    method_input = _rewrite_evidence(
        method_input,
        _malform_source_evidence(frame, mutation),
    )

    with pytest.raises(
        observation_source.SourceObservationError,
        match="^source_observation_semantics_unsupported$",
    ):
        observation_source.load_source_observations(
            method_input=method_input,
            cell_state=profile,
            cell_state_path=profile_path,
        )


@pytest.mark.parametrize("mutation", _MALFORMED_SEMANTIC_ROWS)
def test_malformed_semantic_rows_fail_eligibility_and_run_with_typed_reason(
    tmp_path: Path,
    mutation: str,
) -> None:
    request = _rewrite_request_evidence(
        _source_bound_request(tmp_path),
        mutation,
    )
    registry = ToolRegistry.load_default()

    eligibility = registry.check_eligibility(request)
    run = registry.run(request)

    assert eligibility.eligible is False
    assert eligibility.reason_codes == [
        "source_observation_semantics_unsupported"
    ]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["source_observation_semantics_unsupported"]


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    [
        ("malformed_prediction", "source_prediction_set_invalid"),
        ("duplicate_prediction", "source_prediction_set_invalid"),
        ("duplicate_observation_id", "source_observation_ids_not_unique"),
        ("missing_observation_id", "source_observation_set_mismatch"),
        ("unsupported_semantics", "source_observation_semantics_unsupported"),
        (
            "swapped_consensus_label",
            "source_observation_profile_consensus_mismatch",
        ),
    ],
)
def test_source_parser_rejects_malformed_or_misbound_rows(
    tmp_path: Path,
    mutation: str,
    expected_reason: str,
) -> None:
    method_input, profile, profile_path = _source_bound_fixture(tmp_path)
    frame = pd.read_parquet(method_input.source_observations.evidence_path)
    if mutation == "malformed_prediction":
        frame.loc[0, "prediction_set"] = "[not-json"
    elif mutation == "duplicate_prediction":
        frame.loc[0, "prediction_set"] = '["state:target","state:target"]'
    elif mutation == "duplicate_observation_id":
        frame.loc[1, "observation_id"] = frame.loc[0, "observation_id"]
    elif mutation == "missing_observation_id":
        frame = frame.iloc[:-1].copy()
    elif mutation == "unsupported_semantics":
        frame.loc[0, "open_set_state"] = "candidate"
    elif mutation == "swapped_consensus_label":
        frame.loc[0, "prediction_set"] = '["state:outside"]'
        frame.loc[0, "consensus_label"] = "state:outside"
    method_input = _rewrite_evidence(method_input, frame)

    with pytest.raises(
        observation_source.SourceObservationError,
        match=f"^{expected_reason}",
    ):
        observation_source.load_source_observations(
            method_input=method_input,
            cell_state=profile,
            cell_state_path=profile_path,
        )


@pytest.mark.parametrize(
    ("field", "invalid_value", "expected_reason"),
    [
        ("run_id", "run-other", "source_manifest_producer_mismatch"),
        ("tool_version", "9.9.9", "source_manifest_producer_mismatch"),
        (
            "reference_manifest_hash",
            "7" * 64,
            "source_manifest_profile_lineage_mismatch",
        ),
    ],
)
def test_source_parser_rejects_manifest_lineage_drift(
    tmp_path: Path,
    field: str,
    invalid_value: str,
    expected_reason: str,
) -> None:
    method_input, profile, profile_path = _source_bound_fixture(tmp_path)
    source = method_input.source_observations
    manifest = json.loads(
        source.artifact_manifest_path.read_text(encoding="utf-8")
    )
    manifest[field] = invalid_value
    manifest_raw = _canonical_bytes(manifest)
    source.artifact_manifest_path.write_bytes(manifest_raw)
    method_input = method_input.model_copy(
        update={
            "source_observations": source.model_copy(
                update={
                    "artifact_manifest_sha256": hashlib.sha256(
                        manifest_raw
                    ).hexdigest()
                }
            )
        }
    )

    with pytest.raises(
        observation_source.SourceObservationError,
        match=f"^{expected_reason}",
    ):
        observation_source.load_source_observations(
            method_input=method_input,
            cell_state=profile,
            cell_state_path=profile_path,
        )


def test_source_parser_rejects_changed_or_symlinked_evidence(
    tmp_path: Path,
) -> None:
    method_input, profile, profile_path = _source_bound_fixture(tmp_path)
    source = method_input.source_observations
    source.evidence_path.write_bytes(source.evidence_path.read_bytes() + b"drift")
    with pytest.raises(
        observation_source.SourceObservationError,
        match="^source_evidence_checksum_mismatch",
    ):
        observation_source.load_source_observations(
            method_input=method_input,
            cell_state=profile,
            cell_state_path=profile_path,
        )

    symlink_root = tmp_path / "symlink-case"
    symlink_root.mkdir()
    method_input, profile, profile_path = _source_bound_fixture(symlink_root)
    source = method_input.source_observations
    original_path = source.evidence_path
    symlink_path = original_path.with_name("evidence-link.parquet")
    symlink_path.symlink_to(original_path)
    manifest = json.loads(
        source.artifact_manifest_path.read_text(encoding="utf-8")
    )
    evidence_artifact = next(
        item
        for item in manifest["artifacts"]
        if item["artifact_id"] == source.evidence_artifact_id
    )
    evidence_artifact["path"] = str(symlink_path)
    manifest_raw = _canonical_bytes(manifest)
    source.artifact_manifest_path.write_bytes(manifest_raw)
    method_input = method_input.model_copy(
        update={
            "source_observations": source.model_copy(
                update={
                    "evidence_path": symlink_path,
                    "artifact_manifest_sha256": hashlib.sha256(
                        manifest_raw
                    ).hexdigest(),
                }
            )
        }
    )
    with pytest.raises(
        observation_source.SourceObservationError,
        match="^source_evidence_not_regular_file",
    ):
        observation_source.load_source_observations(
            method_input=method_input,
            cell_state=profile,
            cell_state_path=profile_path,
        )


def test_expression_rows_join_source_states_by_observation_identity(
    tmp_path: Path,
) -> None:
    request = _source_bound_request(tmp_path)
    refs = {item.role: item for item in request.object_inputs}
    method_input = method_models.ProcessMethodInputV2.model_validate_json(
        refs["process_method_input"].path.read_text(encoding="utf-8")
    )
    profile = CellStateEvidenceProfileV3.model_validate_json(
        refs["cell_state_evidence_profile"].path.read_text(encoding="utf-8")
    )
    source_rows = observation_source.load_source_observations(
        method_input=method_input,
        cell_state=profile,
        cell_state_path=refs["cell_state_evidence_profile"].path,
    ).rows
    expression_path = request.assets[0].path
    expression = ad.read_h5ad(expression_path)
    reversed_ids = list(reversed(expression.obs_names.tolist()))
    expression = expression[reversed_ids].copy()
    expression.write_h5ad(expression_path)
    method_spec = method_models.ProcessMethodSpec.model_validate_json(
        refs["process_method_spec"].path.read_text(encoding="utf-8")
    )
    assignment = BiologicalUnitAssignmentArtifact.model_validate_json(
        refs["biological_unit_assignment"].path.read_text(encoding="utf-8")
    )

    loaded = method_runtime._load_expression(
        asset=request.assets[0],
        method_spec=method_spec,
        method_input=method_input,
        assignment=assignment,
        source_observation_states=source_rows,
    )

    state_by_id = {
        row.observation_id: row.state_id
        if row.state == "candidate"
        else None
        for row in source_rows
    }
    assert loaded.observation_ids.tolist() == reversed_ids
    assert loaded.state_ids.tolist() == [
        state_by_id[observation_id] for observation_id in reversed_ids
    ]



def test_missing_parquet_engine_is_typed_without_import_time_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    method_input, profile, profile_path = _source_bound_fixture(tmp_path)

    def unavailable_engine(*args: object, **kwargs: object) -> pd.DataFrame:
        raise ImportError("no parquet engine")

    monkeypatch.setattr(pd, "read_parquet", unavailable_engine)
    with pytest.raises(
        observation_source.SourceObservationError,
        match="^source_evidence_runtime_unavailable",
    ):
        observation_source.load_source_observations(
            method_input=method_input,
            cell_state=profile,
            cell_state_path=profile_path,
        )



def test_missing_parquet_engine_is_an_eligibility_reason(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _source_bound_request(tmp_path)

    def unavailable_engine(*args: object, **kwargs: object) -> pd.DataFrame:
        raise ImportError("no parquet engine")

    monkeypatch.setattr(pd, "read_parquet", unavailable_engine)
    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert eligibility.eligible is False
    assert eligibility.reason_codes == ["source_evidence_runtime_unavailable"]


def test_source_change_before_publication_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _source_bound_request(tmp_path)
    process_ref = next(
        item for item in request.object_inputs if item.role == "process_method_input"
    )
    process_input = method_models.ProcessMethodInputV2.model_validate_json(
        process_ref.path.read_text(encoding="utf-8")
    )
    evidence_path = process_input.source_observations.evidence_path
    adapter_module = importlib.import_module(
        "bridge.tool_packages.p0_06_proliferation_stress_response.adapter"
    )
    real_prepare = adapter_module.prepare_proliferation_stress_visualizations
    mutated = False

    def prepare_then_mutate(*args: object, **kwargs: object) -> object:
        nonlocal mutated
        prepared = real_prepare(*args, **kwargs)
        if not mutated:
            evidence_path.write_bytes(evidence_path.read_bytes() + b"changed")
            mutated = True
        return prepared

    monkeypatch.setattr(
        adapter_module,
        "prepare_proliferation_stress_visualizations",
        prepare_then_mutate,
    )
    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_modified_during_run"]
