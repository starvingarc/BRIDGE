from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import pytest

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_12_graft_assessment.adapter import adapter
from bridge.tool_packages.p0_12_graft_assessment.run_models import (
    PUBLIC_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_12_graft_assessment.models import (
    GraftAssessmentResult,
)
from bridge.toolkit.contracts import (
    ExecutionState,
    ImplementationState,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
)
from bridge.toolkit.registry import ToolRegistry


adapter_module = importlib.import_module(
    "bridge.tool_packages.p0_12_graft_assessment.adapter"
)
CREATED_AT = "2026-08-25T00:00:00Z"
PACKAGE_METHOD_IDS = [
    "METHOD-ANNDATA",
    "METHOD-BRIDGE-GRAFTCASE-VALIDATOR",
    "METHOD-BRIDGE-PSEUDOBULK-REFERENCE-CORRELATION-2C3A8F",
    "METHOD-BRIDGE-SOFT-COMPOSITION-404672",
    "METHOD-SCANPY",
]
PRECOMPUTED_METHOD_IDS = [
    "METHOD-BRIDGE-GRAFTCASE-VALIDATOR",
    "METHOD-BRIDGE-SOFT-COMPOSITION-404672",
]


def _objects() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    case = {
        "object_version": "0.1.0",
        "graft_case_id": "graft-case:demo",
        "assay_id": "assay:demo",
        "specimen_id": "specimen:demo",
        "animal_id": "animal:demo-01",
        "post_transplant_timepoint": "day-42",
        "biological_replicate_id": "replicate:demo-01",
        "originating_preparation_id": "preparation:demo-01",
        "linkage_evidence_refs": ["provenance:explicit-linkage"],
        "declared_confounder_refs": [],
        "provenance_refs": ["provenance:graft-case"],
        "created_at": CREATED_AT,
    }
    assessment = {
        "object_version": "0.1.0",
        "assessment_spec_id": "graft-assessment-spec:demo",
        "role_rules": [
            {
                "role_id": "composition",
                "required": True,
                "allowed_metric_ids": ["soft-composition"],
                "allowed_states": ["observed"],
            },
            {
                "role_id": "reference-support",
                "required": True,
                "allowed_metric_ids": ["reference-support"],
                "allowed_states": ["supported"],
            },
            {
                "role_id": "maturation",
                "required": False,
                "allowed_metric_ids": ["maturation-signal"],
                "allowed_states": ["limited"],
            },
            {
                "role_id": "unknown",
                "required": False,
                "allowed_metric_ids": ["unknown-fraction"],
                "allowed_states": ["uncertain"],
            },
        ],
        "state_classes": {
            "observed": "usable",
            "supported": "usable",
            "limited": "limited",
            "uncertain": "unknown",
        },
        "method_ids": PRECOMPUTED_METHOD_IDS,
        "provenance_refs": ["provenance:assessment-spec"],
    }
    records = [
        {
            "evidence_id": "graft-evidence:composition",
            "role_id": "composition",
            "metric_id": "soft-composition",
            "state": "observed",
            "value": 0.8,
            "numerator": 80,
            "denominator": 100,
            "source_run_ref": "tool-run:composition",
            "provenance_refs": ["provenance:composition"],
        },
        {
            "evidence_id": "graft-evidence:reference",
            "role_id": "reference-support",
            "metric_id": "reference-support",
            "state": "supported",
            "value": 0.7,
            "source_run_ref": "tool-run:reference",
            "provenance_refs": ["provenance:reference"],
        },
        {
            "evidence_id": "graft-evidence:maturation",
            "role_id": "maturation",
            "metric_id": "maturation-signal",
            "state": "limited",
            "value": 0.4,
            "source_run_ref": "tool-run:maturation",
            "provenance_refs": ["provenance:maturation"],
        },
        {
            "evidence_id": "graft-evidence:unknown",
            "role_id": "unknown",
            "metric_id": "unknown-fraction",
            "state": "uncertain",
            "value": None,
            "source_run_ref": "tool-run:unknown",
            "provenance_refs": ["provenance:unknown"],
        },
    ]
    bundle = {
        "object_version": "0.1.0",
        "evidence_bundle_id": "graft-evidence-bundle:demo",
        "graft_case_ref": case["graft_case_id"],
        "assessment_spec_ref": assessment["assessment_spec_id"],
        "records": records,
        "provenance_refs": ["provenance:evidence-bundle"],
        "created_at": CREATED_AT,
    }
    return case, assessment, bundle


def _write_ref(
    root: Path,
    *,
    input_id: str,
    role: str,
    schema_ref: str,
    payload: object,
) -> StructuredInputRef:
    path = root / f"{input_id}.json"
    path.write_bytes(canonical_json_bytes(payload, indent=2))
    return StructuredInputRef(
        input_id=input_id,
        role=role,
        schema_ref=schema_ref,
        object_version="0.1.0",
        path=path,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        media_type="application/json",
    )


def _request(
    tmp_path: Path,
    *,
    case: dict[str, Any] | None = None,
    assessment: dict[str, Any] | None = None,
    bundle: dict[str, Any] | None = None,
    output_name: str = "output",
) -> ToolRequestV2:
    base_case, base_assessment, base_bundle = _objects()
    case = deepcopy(case or base_case)
    assessment = deepcopy(assessment or base_assessment)
    bundle = deepcopy(bundle or base_bundle)
    input_dir = tmp_path / "inputs"
    input_dir.mkdir(exist_ok=True)
    refs = [
        _write_ref(
            input_dir,
            input_id="case",
            role="graft_case",
            schema_ref="bridge://schemas/graft-case/v0.1",
            payload=case,
        ),
        _write_ref(
            input_dir,
            input_id="spec",
            role="assessment_spec",
            schema_ref="bridge://schemas/graft-assessment-spec/v0.1",
            payload=assessment,
        ),
        _write_ref(
            input_dir,
            input_id="bundle",
            role="evidence_bundle",
            schema_ref="bridge://schemas/graft-evidence-bundle/v0.1",
            payload=bundle,
        ),
    ]
    return ToolRequestV2(
        request_id="request-p0-12",
        tool_id="P0-12",
        tool_version="0.4.0",
        output_dir=tmp_path / output_name,
        object_inputs=refs,
    )


def test_registry_declares_executable_v2_contract() -> None:
    spec = ToolRegistry.load_default().describe("P0-12")

    assert isinstance(spec, ToolPackageSpecV2)
    assert spec.implementation_state is ImplementationState.IMPLEMENTED
    assert spec.method_ids == PACKAGE_METHOD_IDS
    assert spec.result_schema_ref == "bridge://schemas/graft-assessment-run-result/v0.1"
    assert spec.adapter_ref.endswith(":adapter")


def test_no_graft_is_successful_not_provided_and_deterministic(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    request = ToolRequestV2(
        request_id="request-no-graft",
        tool_id="P0-12",
        tool_version="0.4.0",
        output_dir=tmp_path / "output",
        object_inputs=[],
    )

    assert registry.check_eligibility(request).eligible
    first = registry.run(request)
    second = registry.run(request)

    assert first.execution_state is ExecutionState.SUCCEEDED
    assert first.run_id == second.run_id
    assert first.result == second.result
    assert [item.sha256 for item in first.artifacts] == [
        item.sha256 for item in second.artifacts
    ]
    result = GraftAssessmentResult.model_validate(first.result)
    assert result.state == "not_provided"
    assert result.reason_codes == ["graft_not_provided"]
    assert result.pretransplant_evidence_effect == "none"
    assert result.domain_score is None
    assert result.score_state == "unavailable"
    assert len(first.artifacts) == 16
    assert first.visualizations == []
    manifest = json.loads(
        next(
            item.path
            for item in first.artifacts
            if item.kind == "artifact_manifest"
        ).read_text()
    )
    assert len(manifest["artifacts"]) == 15


def test_three_objects_produce_bound_descriptive_shadow_candidate(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)

    assert registry.check_eligibility(request).eligible
    first = registry.run(request)
    second = registry.run(request)
    result = GraftAssessmentResult.model_validate(first.result)

    assert first.execution_state is ExecutionState.SUCCEEDED
    assert first.run_id == second.run_id
    assert result.state == "candidate"
    assert result.analysis_mode == "descriptive_only"
    assert result.evidence_state == "shadow"
    assert result.linkage_state == "provided_linked"
    assert len(result.source_bindings) == 3
    assert {item.role_id for item in result.role_summaries} == {
        "composition",
        "reference-support",
        "maturation",
        "unknown",
    }
    assert result.preparation_linkage is not None
    assert result.pretransplant_evidence_effect == "none"
    assert result.domain_score is None
    assert len(first.artifacts) == 16
    assert first.visualizations == []


def test_missing_metadata_confounding_linkage_and_role_remain_descriptive(
    tmp_path: Path,
) -> None:
    case, assessment, bundle = _objects()
    for field in (
        "animal_id",
        "post_transplant_timepoint",
        "biological_replicate_id",
        "originating_preparation_id",
    ):
        case[field] = None
    case["linkage_evidence_refs"] = []
    case["declared_confounder_refs"] = ["confounder:batch-with-timepoint"]
    bundle["records"] = [
        record
        for record in bundle["records"]
        if record["role_id"] != "reference-support"
    ]
    run = ToolRegistry.load_default().run(
        _request(tmp_path, case=case, assessment=assessment, bundle=bundle)
    )
    result = GraftAssessmentResult.model_validate(run.result)

    assert result.analysis_mode == "descriptive_only"
    assert result.linkage_state == "provided_unlinked"
    assert result.required_roles_missing == ["reference-support"]
    assert result.missing_metadata == [
        "animal_id",
        "post_transplant_timepoint",
        "biological_replicate_id",
    ]
    assert {
        "graft_metadata_incomplete",
        "graft_confounding_declared",
        "graft_required_role_missing",
        "graft_preparation_linkage_not_provided",
    }.issubset(result.reason_codes)


def test_roles_metrics_and_states_come_from_external_spec(tmp_path: Path) -> None:
    case, assessment, bundle = _objects()
    assessment["role_rules"] = [
        {
            "role_id": "future-role",
            "required": True,
            "allowed_metric_ids": ["future-metric"],
            "allowed_states": ["future-state"],
        }
    ]
    assessment["state_classes"] = {"future-state": "usable"}
    bundle["records"] = [
        {
            "evidence_id": "graft-evidence:future",
            "role_id": "future-role",
            "metric_id": "future-metric",
            "state": "future-state",
            "value": 1,
            "source_run_ref": "tool-run:future",
            "provenance_refs": ["provenance:future"],
        }
    ]
    run = ToolRegistry.load_default().run(
        _request(tmp_path, case=case, assessment=assessment, bundle=bundle)
    )

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["role_summaries"][0]["role_id"] == "future-role"


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"parameters": {"mode": "custom"}}, "p0_12_parameters_forbidden"),
        ({"object_inputs": []}, None),
    ],
)
def test_envelope_contract_is_narrow(
    tmp_path: Path, change: dict[str, Any], reason: str | None
) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path).model_copy(update=change)
    eligibility = registry.check_eligibility(request)

    if reason is None:
        assert eligibility.eligible
    else:
        assert not eligibility.eligible
        assert reason in eligibility.reason_codes


def test_partial_object_set_is_rejected(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)
    partial = request.model_copy(update={"object_inputs": request.object_inputs[:1]})

    eligibility = registry.check_eligibility(partial)

    assert not eligibility.eligible
    assert "exactly_one_assessment_spec_required" in eligibility.reason_codes
    assert "exactly_one_evidence_bundle_required" in eligibility.reason_codes


@pytest.mark.parametrize("binding", ["case", "spec", "methods"])
def test_cross_object_or_method_drift_fails_closed(
    tmp_path: Path, binding: str
) -> None:
    case, assessment, bundle = _objects()
    if binding == "case":
        bundle["graft_case_ref"] = "graft-case:other"
    elif binding == "spec":
        bundle["assessment_spec_ref"] = "graft-assessment-spec:other"
    else:
        assessment["method_ids"] = ["METHOD-BRIDGE-GRAFTCASE-VALIDATOR"]
    request = _request(
        tmp_path, case=case, assessment=assessment, bundle=bundle
    )

    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert not eligibility.eligible
    expected = (
        "graft_case_binding_mismatch"
        if binding == "case"
        else "assessment_spec_binding_mismatch"
    )
    assert expected in eligibility.reason_codes


@pytest.mark.parametrize("field", ["role_id", "metric_id", "state"])
def test_record_contract_drift_fails_closed(tmp_path: Path, field: str) -> None:
    case, assessment, bundle = _objects()
    bundle["records"][0][field] = "undeclared-value"
    request = _request(
        tmp_path, case=case, assessment=assessment, bundle=bundle
    )

    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert not eligibility.eligible
    assert "graft_evidence_contract_mismatch" in eligibility.reason_codes


def test_checksum_mismatch_is_rejected(tmp_path: Path) -> None:
    request = _request(tmp_path)
    bad_ref = request.object_inputs[0].model_copy(update={"sha256": "0" * 64})
    request = request.model_copy(
        update={"object_inputs": [bad_ref, *request.object_inputs[1:]]}
    )

    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert not eligibility.eligible
    assert "structured_input_checksum_mismatch" in eligibility.reason_codes


def test_input_change_during_run_fails_without_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path)
    spec = ToolRegistry.load_default().describe("P0-12")
    monkeypatch.setattr(adapter_module, "inputs_unchanged", lambda refs: False)

    run = adapter.run(request, spec)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_modified_during_run"]
    assert not (request.output_dir / run.run_id).exists()


@pytest.mark.parametrize(
    ("target", "reason_code"),
    [
        (
            "build_graft_assessment_visualization_data",
            "visualization_data_invalid",
        ),
        (
            "prepare_graft_assessment_visualizations",
            "visualization_render_failed",
        ),
    ],
)
def test_visualization_failures_are_typed_without_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
    reason_code: str,
) -> None:
    request = ToolRequestV2(
        request_id="request-no-graft-failure",
        tool_id="P0-12",
        tool_version="0.4.0",
        output_dir=tmp_path / target,
        object_inputs=[],
    )
    spec = ToolRegistry.load_default().describe("P0-12")

    def fail(*_args, **_kwargs):
        raise ValueError("controlled failure")

    monkeypatch.setattr(adapter_module, target, fail)
    run = adapter.run(request, spec)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == [reason_code]
    assert not request.output_dir.exists()


def test_published_bundle_mismatch_is_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = ToolRequestV2(
        request_id="request-no-graft-publish-mismatch",
        tool_id="P0-12",
        tool_version="0.4.0",
        output_dir=tmp_path / "publish-mismatch",
        object_inputs=[],
    )
    spec = ToolRegistry.load_default().describe("P0-12")
    monkeypatch.setattr(adapter_module, "_publish_bundle", lambda **_kwargs: {})

    run = adapter.run(request, spec)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["published_bundle_hash_mismatch"]


def test_existing_bundle_drift_fails_closed(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)
    first = registry.run(request)
    result_path = next(
        item.path
        for item in first.artifacts
        if item.kind == "graft_assessment_result"
    )
    result_path.write_text("{}\n", encoding="utf-8")

    second = registry.run(request)

    assert second.execution_state is ExecutionState.FAILED
    assert second.reason_codes == ["existing_run_bundle_hash_mismatch"]


@pytest.mark.parametrize(
    "schema_ref",
    sorted(PUBLIC_SCHEMA_MODELS),
)
def test_public_schemas_are_generated_and_valid(schema_ref: str) -> None:
    registry = ToolRegistry.load_default()
    schema = registry.resolve_schema(schema_ref)

    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == schema_ref
    if schema_ref == "bridge://schemas/graft-assessment-run-result/v0.1":
        assert len(schema["anyOf"]) == 2
    else:
        assert schema["additionalProperties"] is False


def test_v1_request_is_typed_refusal(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    spec = registry.describe("P0-12")
    request = ToolRequest(
        request_id="request-v1",
        tool_id="P0-12",
        tool_version="0.4.0",
        output_dir=tmp_path / "output",
    )

    eligibility = adapter.check_eligibility(request, spec)
    run = adapter.run(request, spec)

    assert not eligibility.eligible
    assert eligibility.reason_codes == ["tool_request_v2_required"]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["tool_request_v2_required"]
