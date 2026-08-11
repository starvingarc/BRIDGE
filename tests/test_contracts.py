from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError
from pydantic import ValidationError

from bridge.toolkit.contracts import (
    ExecutionState,
    ImplementationState,
    MeasurementResult,
    InputAsset,
    ScoreState,
    ToolRequest,
    ToolRun,
)
from bridge.toolkit.schemas import load_schema


def test_measurement_result_requires_null_score_when_unavailable() -> None:
    with pytest.raises(ValidationError, match="domain_score"):
        MeasurementResult(
            measurement_id="m-1",
            measurement_spec_id="spec-1",
            metric_name="n_cells",
            raw_value=10,
            denominator=None,
            domain_score=70,
            score_state=ScoreState.UNAVAILABLE,
            evidence_state="measured",
        )


@pytest.mark.parametrize("score_state", [ScoreState.AVAILABLE, ScoreState.SHADOW])
def test_current_measurement_schema_rejects_all_non_null_domain_scores(score_state: ScoreState) -> None:
    with pytest.raises(ValidationError):
        MeasurementResult(
            measurement_id="m-1",
            measurement_spec_id="spec-1",
            metric_name="candidate_score",
            raw_value=0.7,
            domain_score=70,
            score_state=score_state,
            evidence_state="inferred",
        )


def test_current_measurement_schema_rejects_available_score_state_without_score() -> None:
    with pytest.raises(ValidationError, match="literal_error"):
        MeasurementResult(
            measurement_id="m-1",
            measurement_spec_id="spec-1",
            metric_name="candidate_score",
            raw_value=0.7,
            score_state=ScoreState.AVAILABLE,
            evidence_state="inferred",
        )


def test_scaffold_tool_run_cannot_contain_measurements(tmp_path: Path) -> None:
    request = ToolRequest(
        request_id="request-1",
        tool_id="P0-03",
        output_dir=tmp_path,
    )

    with pytest.raises(ValidationError, match="not_implemented"):
        ToolRun(
            run_id="run-1",
            request=request,
            implementation_state=ImplementationState.SCAFFOLD,
            execution_state=ExecutionState.NOT_IMPLEMENTED,
            tool_version="0.1.0",
            environment_spec_id="ENV-P0-CORE-v0.1",
            measurements=[
                MeasurementResult(
                    measurement_id="m-1",
                    measurement_spec_id="spec-1",
                    metric_name="placeholder",
                    raw_value=1,
                    domain_score=None,
                    score_state=ScoreState.UNAVAILABLE,
                    evidence_state="unavailable",
                )
            ],
        )


def test_scaffold_tool_run_cannot_claim_success_without_payload(tmp_path: Path) -> None:
    request = ToolRequest(
        request_id="request-1",
        tool_id="P0-03",
        output_dir=tmp_path,
    )

    with pytest.raises(ValidationError, match="scaffold ToolRun"):
        ToolRun(
            run_id="run-1",
            request=request,
            implementation_state=ImplementationState.SCAFFOLD,
            execution_state=ExecutionState.SUCCEEDED,
            tool_version="0.1.0",
            environment_spec_id="ENV-P0-CORE-v0.1",
        )


def test_exported_json_schemas_enforce_score_and_scaffold_guards(tmp_path: Path) -> None:
    measurement_schema = load_schema("bridge://schemas/measurement-result/v0.1")
    measurement_validator = Draft202012Validator(measurement_schema)
    invalid_measurement = {
        "measurement_id": "m-1",
        "measurement_spec_id": "spec-1",
        "metric_name": "candidate_score",
        "raw_value": 0.7,
        "domain_score": 70,
        "score_state": "available",
        "evidence_state": "inferred",
        "provenance_refs": [],
    }
    assert list(measurement_validator.iter_errors(invalid_measurement))

    profile_schema = load_schema("bridge://schemas/qc-readiness-profile/v0.1")
    serialized_profile_schema = json.dumps(profile_schema["properties"]["score_state"])
    assert '"available"' not in serialized_profile_schema
    assert profile_schema["properties"]["domain_score"]["type"] == "null"

    request = ToolRequest(
        request_id="request-1",
        tool_id="P0-03",
        output_dir=tmp_path,
    )
    tool_run_schema = load_schema("bridge://schemas/tool-run/v0.1")
    tool_run_validator = Draft202012Validator(tool_run_schema)
    invalid_run = {
        "run_id": "run-1",
        "request": request.model_dump(mode="json"),
        "implementation_state": "scaffold",
        "execution_state": "succeeded",
        "tool_version": "0.1.0",
        "environment_spec_id": "ENV-P0-CORE-v0.1",
        "measurements": [],
        "artifacts": [],
        "visualizations": [],
        "result": None,
        "reason_codes": [],
        "warnings": [],
    }
    assert list(tool_run_validator.iter_errors(invalid_run))


def test_tool_request_rejects_relative_output_directory() -> None:
    with pytest.raises(ValidationError, match="absolute"):
        ToolRequest(
            request_id="request-1",
            tool_id="P0-01",
            output_dir=Path("relative-output"),
        )


def test_input_level_and_matrix_semantics_must_agree(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="analysis_ready"):
        InputAsset(
            asset_id="asset-1",
            path=(tmp_path / "counts.h5ad").resolve(),
            format="h5ad",
            input_level="analysis_ready",
            matrix_semantics="raw_counts",
            assay="scRNA-seq",
        )

    with pytest.raises(ValidationError, match="droplet_ready"):
        InputAsset(
            asset_id="asset-2",
            path=(tmp_path / "droplets.h5ad").resolve(),
            format="h5ad",
            input_level="droplet_ready",
            matrix_semantics="raw_counts",
            assay="scRNA-seq",
        )


@pytest.mark.parametrize(
    "schema_ref",
    [
        "bridge://schemas/biological-review-record/v0.1",
        "bridge://schemas/cell-state-benchmark-spec/v0.1",
        "bridge://schemas/cell-state-benchmark-spec/v0.2",
        "bridge://schemas/benchmark-split-manifest/v0.1",
        "bridge://schemas/benchmark-split-manifest/v0.2",
        "bridge://schemas/freeze-gate-spec/v0.1",
        "bridge://schemas/freeze-gate-spec/v0.2",
        "bridge://schemas/cell-state-release-manifest/v0.1",
    ],
)
def test_cell_state_freeze_contracts_are_exported(schema_ref: str) -> None:
    schema = load_schema(schema_ref)

    assert schema["$id"] == schema_ref


def test_legacy_benchmark_schema_remains_loadable() -> None:
    payload = {
        "benchmark_spec_id": "CELLSTATE-BENCHMARK-scRNA-pilot-v0.1",
        "version": "0.1.0",
        "phase": "pilot",
        "assay": "scRNA-seq",
        "annotation_vocabulary_ref": "BRIDGE-PD-vMB-ANNOTATION-v0.1-draft",
        "reference_snapshot_ref": "REF-PD-vMB-CELLSTATE-v0.2",
        "methods": ["source_specific_correlation"],
    }
    Draft202012Validator(
        load_schema("bridge://schemas/cell-state-benchmark-spec/v0.1")
    ).validate(payload)
    with pytest.raises(JSONSchemaValidationError):
        Draft202012Validator(
            load_schema("bridge://schemas/cell-state-benchmark-spec/v0.2")
        ).validate(payload)


def test_legacy_split_and_gate_payloads_remain_loadable() -> None:
    split = {
        "split_manifest_id": "CELLSTATE-SPLIT-pilot-v0.1-fixture",
        "benchmark_spec_ref": "CELLSTATE-BENCHMARK-scRNA-pilot-v0.1",
        "phase": "pilot",
        "random_seed": 7,
        "input_catalog_sha256": "a" * 64,
        "records": [],
    }
    Draft202012Validator(
        load_schema("bridge://schemas/benchmark-split-manifest/v0.1")
    ).validate(split)
    with pytest.raises(JSONSchemaValidationError):
        Draft202012Validator(
            load_schema("bridge://schemas/benchmark-split-manifest/v0.2")
        ).validate(split)

    gate = {
        "gate_spec_id": "FREEZE-GATE-CELLSTATE-scRNA-v0.1-draft",
        "version": "0.1.0",
        "status": "proposed",
        "benchmark_spec_ref": "CELLSTATE-BENCHMARK-scRNA-pilot-v0.1",
        "criteria": [],
    }
    Draft202012Validator(
        load_schema("bridge://schemas/freeze-gate-spec/v0.1")
    ).validate(gate)
