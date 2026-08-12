from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from bridge.toolkit.contracts import (
    ExecutionState,
    ImplementationState,
    MeasurementResult,
    InputAsset,
    ScoreState,
    ToolRequest,
    ToolRun,
    ToolPackageSpec,
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


def test_scaffold_spec_allows_no_selected_methods() -> None:
    spec = ToolPackageSpec(
        tool_id="P0-03",
        name="Target Identity & Regional Fidelity",
        version="0.1.0",
        summary="Scaffold contract.",
        implementation_state=ImplementationState.SCAFFOLD,
        scientific_status="candidate",
        environment_spec_id="ENV-P0-CORE-v0.1",
        input_schema_ref="bridge://schemas/tool-request/v0.1",
        output_schema_ref="bridge://schemas/tool-run/v0.1",
        method_ids=[],
        card_ref="bridge://tool-cards/P0-03",
    )

    assert spec.method_ids == []


def test_implemented_spec_requires_a_selected_method() -> None:
    with pytest.raises(ValidationError, match="requires at least one method"):
        ToolPackageSpec(
            tool_id="P0-01",
            name="Input Audit & QC",
            version="0.1.0",
            summary="Executable contract.",
            implementation_state=ImplementationState.IMPLEMENTED,
            scientific_status="candidate",
            environment_spec_id="ENV-P0-CORE-v0.1",
            input_schema_ref="bridge://schemas/tool-request/v0.1",
            output_schema_ref="bridge://schemas/tool-run/v0.1",
            method_ids=[],
            card_ref="bridge://tool-cards/P0-01",
        )


def test_tool_package_schema_allows_empty_scaffolds_but_not_empty_implementations() -> None:
    validator = Draft202012Validator(load_schema("bridge://schemas/tool-package-spec/v0.1"))
    payload = {
        "tool_id": "P0-03",
        "name": "Target Identity & Regional Fidelity",
        "version": "0.1.0",
        "summary": "Scaffold contract.",
        "implementation_state": "scaffold",
        "scientific_status": "candidate",
        "optional": False,
        "environment_spec_id": "ENV-P0-CORE-v0.1",
        "input_schema_ref": "bridge://schemas/tool-request/v0.1",
        "output_schema_ref": "bridge://schemas/tool-run/v0.1",
        "method_ids": [],
        "card_ref": "bridge://tool-cards/P0-03",
    }

    assert list(validator.iter_errors(payload)) == []
    payload["implementation_state"] = "implemented"
    assert list(validator.iter_errors(payload))


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
        "bridge://schemas/cell-state-benchmark-spec/v0.2",
        "bridge://schemas/benchmark-split-manifest/v0.2",
        "bridge://schemas/freeze-gate-spec/v0.2",
        "bridge://schemas/cell-state-release-manifest/v0.1",
    ],
)
def test_cell_state_freeze_contracts_are_exported(schema_ref: str) -> None:
    schema = load_schema(schema_ref)

    assert schema["$id"] == schema_ref
