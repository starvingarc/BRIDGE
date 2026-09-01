from __future__ import annotations

import hashlib
import importlib
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_06_proliferation_stress_response.adapter import adapter
from bridge.tool_packages.p0_06_proliferation_stress_response.method_models import (
    PUBLIC_METHOD_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.models import (
    PUBLIC_SCHEMA_MODELS,
    ProliferationStressResponseProfile,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.visualization_data import (
    P006_COMPONENT_REFS,
    P006VisualizationArtifactSet,
    ProliferationStressVisualizationDataV1,
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
    "bridge.tool_packages.p0_06_proliferation_stress_response.adapter"
)
CREATED_AT = "2026-08-25T00:00:00Z"
CORE_METHOD_IDS = [
    "METHOD-BRIDGE-SAMPLE-STATE-AGGREGATION",
    "METHOD-DESIGN-AUDIT-AND-SENSITIVITY-STRATIFICATION",
]
METHOD_IDS = [
    *CORE_METHOD_IDS,
    "METHOD-SCANPY-SCORE-GENES",
    "METHOD-DECOUPLER",
    "METHOD-SCANPY-SCORE-GENES-CELL-CYCLE",
]
ROLE_CONTRACTS = {
    "product_case": ("bridge://schemas/product-case/v0.1", "0.1.0"),
    "product_definition_card": (
        "bridge://schemas/product-definition-card/v0.1",
        "0.1.0",
    ),
    "development_window_spec": (
        "bridge://schemas/development-window-spec/v0.1",
        "0.1.0",
    ),
    "program_spec": ("bridge://schemas/program-spec/v0.1", "0.1.0"),
    "cell_state_evidence_profile": (
        "bridge://schemas/cell-state-evidence-profile/v0.2",
        "0.2.0",
    ),
    "protocol_ir": ("bridge://schemas/protocol-ir/v0.1", "0.1.0"),
    "program_evidence_bundle": (
        "bridge://schemas/program-evidence-bundle/v0.1",
        "0.1.0",
    ),
}


def _payloads() -> dict[str, dict[str, Any]]:
    product_definition_ref = {
        "object_id": "product-definition:demo",
        "object_version": "1.0.0",
    }
    product_case_ref = {
        "object_id": "product-case:demo",
        "object_version": "1.0.0",
    }
    window_ref = {
        "object_id": "development-window-spec:demo",
        "object_version": "1.0.0",
    }
    program_spec_ref = {
        "object_id": "program-spec:demo",
        "object_version": "1.0.0",
    }
    product_case = {
        "object_version": "0.1.0",
        "product_case_id": product_case_ref["object_id"],
        "case_version": product_case_ref["object_version"],
        "product_definition_ref": product_definition_ref,
        "source_unit_kind": "preparation",
        "sample_or_preparation_ref": {
            "object_id": "preparation:demo",
            "object_version": "1.0.0",
        },
        "independence_group_refs": [],
        "biological_unit_manifest_ref": None,
        "biological_unit_manifest_sha256": None,
        "independence_scope_ref": None,
        "measurement_spec_ref": {
            "object_id": "measurement-spec:cell-state-demo",
            "object_version": "1.0.0",
        },
        "assay": "scRNA-seq",
        "provenance_refs": [
            {
                "object_id": "provenance:product-case",
                "object_version": "1.0.0",
            }
        ],
        "created_at": CREATED_AT,
    }
    product_definition = {
        "object_version": "0.1.0",
        "product_definition_id": product_definition_ref["object_id"],
        "definition_version": product_definition_ref["object_version"],
        "state_role_map_ref": {
            "object_id": "state-role-map:demo",
            "object_version": "1.0.0",
        },
        "supported_assays": ["scRNA-seq"],
        "review_state": "draft",
        "provenance_refs": [
            {
                "object_id": "provenance:product-definition",
                "object_version": "1.0.0",
            }
        ],
    }
    window = {
        "object_version": "0.1.0",
        "window_spec_id": window_ref["object_id"],
        "window_spec_version": window_ref["object_version"],
        "product_definition_ref": product_definition_ref,
        "state_map_ref": product_definition["state_role_map_ref"],
        "review_state": "confirmed",
        "reviewer_ref": {
            "object_id": "reviewer:demo",
            "object_version": "1.0.0",
        },
        "confirmed_at": CREATED_AT,
        "applicable_assays": ["scRNA-seq"],
        "composition_view": "consensus_supported_only",
        "label_level": "L2",
        "rationale_refs": [
            {
                "object_id": "provenance:development-window",
                "object_version": "1.0.0",
            }
        ],
    }
    program_spec = {
        "object_version": "0.1.0",
        "program_spec_id": program_spec_ref["object_id"],
        "program_spec_version": program_spec_ref["object_version"],
        "product_definition_ref": product_definition_ref,
        "development_window_ref": window_ref,
        "aggregation_method_ids": CORE_METHOD_IDS,
        "attribution_rule": {
            "minimum_independent_replicates": 2,
            "minimum_comparable_groups": 2,
        },
        "program_rules": [
            {
                "program_id": "program:proliferation",
                "gene_set_ref": "gene-set:proliferation-demo",
                "gene_set_sha256": "a" * 64,
                "allowed_analysis_scopes": ["whole_product"],
                "allowed_state_ids": [],
                "allowed_stage_ids": ["stage:target"],
                "allowed_metric_ids": ["metric:program-score"],
                "minimum_gene_coverage": 0.8,
                "allowed_lod_states": ["qualified", "unqualified"],
                "resolvable_lod_states": ["qualified"],
                "review_outcomes": {
                    "elevated": "transcriptomic_review_flag",
                    "below-rule": "not_detected_above_lod",
                    "uncertain": "cannot_resolve",
                },
                "orthogonal_follow_up_refs": ["assay:orthogonal-review"],
                "provenance_refs": ["provenance:program-rule-proliferation"],
            },
            {
                "program_id": "program:stress",
                "gene_set_ref": "gene-set:stress-demo",
                "gene_set_sha256": "b" * 64,
                "allowed_analysis_scopes": ["state_specific"],
                "allowed_state_ids": ["state:target"],
                "allowed_stage_ids": ["stage:target"],
                "allowed_metric_ids": ["metric:program-score"],
                "minimum_gene_coverage": 0.8,
                "allowed_lod_states": ["qualified", "unqualified"],
                "resolvable_lod_states": ["qualified"],
                "review_outcomes": {
                    "elevated": "transcriptomic_review_flag",
                    "below-rule": "not_detected_above_lod",
                    "uncertain": "cannot_resolve",
                },
                "orthogonal_follow_up_refs": ["assay:orthogonal-review"],
                "provenance_refs": ["provenance:program-rule-stress"],
            },
        ],
        "provenance_refs": ["provenance:program-spec"],
    }
    cell_state = {
        "profile_id": "cell-state-profile:demo",
        "assay": "scRNA-seq",
        "measurement_spec_id": "measurement-spec:cell-state-demo",
        "measurement_spec_status": "candidate",
        "annotation_vocabulary_ref": "annotation-vocabulary:demo",
        "reference_snapshot_ref": "reference-snapshot:demo",
        "n_observations": 100,
        "n_genes": 1000,
        "denominator": "eligible-cells",
        "label_levels": {},
        "source_support": {},
        "marker_program_evidence": {},
        "prediction_sets": {},
        "composition": {},
        "gene_coverage": {},
        "modality_sensitivity": {},
        "method_outputs": {},
        "assignment_state": {},
        "unknown_reason": {},
        "calibration": {},
        "method_disagreement": {},
        "per_state_release": {},
        "unresolved_labels": [],
        "warnings": [],
        "evidence_ids": ["cell-state-evidence:demo"],
        "score_state": "shadow",
        "domain_score": None,
        "measurement_spec_version": "1.0.0",
        "upstream_qc_profile_ref": None,
        "upstream_qc_profile_sha256": None,
        "input_data_view": None,
    }
    protocol = {
        "object_version": "0.1.0",
        "protocol_context_id": "protocol-ir:demo",
        "product_case_ref": product_case_ref,
        "metadata_state": "complete",
        "batch_confounding_state": "not_confounded",
        "independent_replicate_count": 2,
        "comparable_group_count": 2,
        "declared_process_step_ids": ["process:dissociation"],
        "provenance_refs": ["provenance:protocol-ir"],
        "created_at": CREATED_AT,
    }
    bundle = {
        "object_version": "0.1.0",
        "evidence_bundle_id": "program-evidence-bundle:demo",
        "records": [
            {
                "evidence_id": "program-evidence:proliferation",
                "program_id": "program:proliferation",
                "analysis_scope": "whole_product",
                "cell_state_id": None,
                "stage_id": "stage:target",
                "metric_id": "metric:program-score",
                "value": 0.2,
                "unit": "relative-score",
                "numerator": None,
                "denominator": None,
                "gene_coverage": 0.95,
                "lod_state": "qualified",
                "evidence_state": "below-rule",
                "process_step_ids": ["process:dissociation"],
                "source_run_ref": "tool-run:upstream-proliferation",
                "provenance_refs": ["provenance:evidence-proliferation"],
            },
            {
                "evidence_id": "program-evidence:stress",
                "program_id": "program:stress",
                "analysis_scope": "state_specific",
                "cell_state_id": "state:target",
                "stage_id": "stage:target",
                "metric_id": "metric:program-score",
                "value": 0.9,
                "unit": "relative-score",
                "numerator": 9,
                "denominator": 10,
                "gene_coverage": 0.9,
                "lod_state": "qualified",
                "evidence_state": "elevated",
                "process_step_ids": [],
                "source_run_ref": "tool-run:upstream-stress",
                "provenance_refs": ["provenance:evidence-stress"],
            },
        ],
        "provenance_refs": ["provenance:program-evidence-bundle"],
        "created_at": CREATED_AT,
    }
    return {
        "product_case": product_case,
        "product_definition_card": product_definition,
        "development_window_spec": window,
        "program_spec": program_spec,
        "cell_state_evidence_profile": cell_state,
        "protocol_ir": protocol,
        "program_evidence_bundle": bundle,
    }


def _write_ref(
    root: Path,
    role: str,
    payload: object,
) -> StructuredInputRef:
    schema_ref, object_version = ROLE_CONTRACTS[role]
    path = root / f"{role}.json"
    path.write_bytes(canonical_json_bytes(payload, indent=2))
    return StructuredInputRef(
        input_id=role,
        role=role,
        schema_ref=schema_ref,
        object_version=object_version,
        path=path,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        media_type="application/json",
    )


def _request(
    tmp_path: Path,
    *,
    payloads: dict[str, dict[str, Any]] | None = None,
    bundle_updates: dict[str, Any] | None = None,
    output_name: str = "output",
) -> ToolRequestV2:
    payloads = deepcopy(payloads or _payloads())
    input_dir = tmp_path / "inputs"
    input_dir.mkdir(exist_ok=True)
    refs: dict[str, StructuredInputRef] = {}
    for role in ROLE_CONTRACTS:
        if role == "program_evidence_bundle":
            continue
        refs[role] = _write_ref(input_dir, role, payloads[role])

    case = payloads["product_case"]
    definition = payloads["product_definition_card"]
    window = payloads["development_window_spec"]
    program_spec = payloads["program_spec"]
    cell_state = payloads["cell_state_evidence_profile"]
    protocol = payloads["protocol_ir"]
    bundle = payloads["program_evidence_bundle"]
    bundle.update(
        {
            "product_case_ref": {
                "object_id": case["product_case_id"],
                "object_version": case["case_version"],
            },
            "product_case_sha256": refs["product_case"].sha256,
            "product_definition_ref": {
                "object_id": definition["product_definition_id"],
                "object_version": definition["definition_version"],
            },
            "product_definition_sha256": refs["product_definition_card"].sha256,
            "development_window_ref": {
                "object_id": window["window_spec_id"],
                "object_version": window["window_spec_version"],
            },
            "development_window_sha256": refs["development_window_spec"].sha256,
            "program_spec_ref": {
                "object_id": program_spec["program_spec_id"],
                "object_version": program_spec["program_spec_version"],
            },
            "program_spec_sha256": refs["program_spec"].sha256,
            "cell_state_profile_ref": cell_state["profile_id"],
            "cell_state_profile_sha256": refs["cell_state_evidence_profile"].sha256,
            "protocol_context_ref": protocol["protocol_context_id"],
            "protocol_context_sha256": refs["protocol_ir"].sha256,
        }
    )
    bundle.update(bundle_updates or {})
    refs["program_evidence_bundle"] = _write_ref(
        input_dir,
        "program_evidence_bundle",
        bundle,
    )
    return ToolRequestV2(
        request_id="request-p0-06",
        tool_id="P0-06",
        tool_version="0.4.0",
        output_dir=tmp_path / output_name,
        object_inputs=list(refs.values()),
    )


def test_registry_declares_executable_v2_contract() -> None:
    spec = ToolRegistry.load_default().describe("P0-06")

    assert isinstance(spec, ToolPackageSpecV2)
    assert spec.implementation_state is ImplementationState.IMPLEMENTED
    assert spec.method_ids == METHOD_IDS
    assert spec.result_schema_ref == (
        "bridge://schemas/proliferation-stress-response-profile/v0.1"
    )


def test_valid_bundle_is_descriptive_shadow_and_deterministic(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)

    assert registry.check_eligibility(request).eligible
    first = registry.run(request)
    second = registry.run(request)
    result = ProliferationStressResponseProfile.model_validate(first.result)

    assert first.execution_state is ExecutionState.SUCCEEDED
    assert first.run_id == second.run_id
    assert first.result == second.result
    assert result.analysis_mode == "descriptive_only"
    assert result.evidence_state == "shadow"
    assert result.process_attribution_state == "conditional_association"
    assert result.domain_score is None
    assert result.score_state == "unavailable"
    assert len(result.source_bindings) == 7
    assert len(first.artifacts) == 16
    by_program = {item.program_id: item for item in result.review_flags}
    assert by_program["program:proliferation"].review_flag_state == (
        "not_detected_above_lod"
    )
    assert by_program["program:stress"].review_flag_state == (
        "transcriptomic_review_flag"
    )
    assert all(
        item.safety_interpretation == "not_evidence_of_safety"
        for item in result.review_flags
    )
    data_artifact = next(
        item
        for item in first.artifacts
        if item.kind == "proliferation_stress_visualization_data"
    )
    visual_data = ProliferationStressVisualizationDataV1.model_validate_json(
        data_artifact.path.read_text()
    )
    set_path = next(
        item.path
        for item in first.artifacts
        if item.kind == "visualization_artifact_set"
    )
    artifact_set = P006VisualizationArtifactSet.model_validate_json(
        set_path.read_text()
    )
    states = (
        visual_data.program_evidence_component_state,
        visual_data.program_score_component_state,
        visual_data.cell_cycle_component_state,
    )
    assert states == ("available", "not_assessed", "not_assessed")
    assert {item.component_ref for item in artifact_set.visualizations} == set(
        P006_COMPONENT_REFS
    )
    assert all(
        item.data_binding.sha256 == data_artifact.sha256
        for item in artifact_set.visualizations
    )


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("metadata_state", "incomplete", "process_metadata_incomplete"),
        (
            "batch_confounding_state",
            "fully_confounded",
            "process_batch_confounding_unresolved",
        ),
        (
            "independent_replicate_count",
            1,
            "process_replication_insufficient",
        ),
    ],
)
def test_process_limits_force_cannot_attribute(
    tmp_path: Path, field: str, value: object, reason: str
) -> None:
    payloads = _payloads()
    payloads["protocol_ir"][field] = value
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))
    result = ProliferationStressResponseProfile.model_validate(run.result)

    assert result.process_attribution_state == "cannot_attribute"
    first = next(
        item
        for item in result.program_results
        if item.program_id == "program:proliferation"
    )
    assert first.process_attribution == "cannot_attribute"
    assert first.process_step_ids == []
    assert reason in first.reason_codes


@pytest.mark.parametrize(
    ("field", "value", "availability", "reason"),
    [
        (
            "gene_coverage",
            0.5,
            "unavailable",
            "program_gene_coverage_insufficient",
        ),
        (
            "lod_state",
            "unqualified",
            "cannot_resolve",
            "program_lod_cannot_resolve",
        ),
    ],
)
def test_coverage_and_lod_limit_resolution(
    tmp_path: Path,
    field: str,
    value: object,
    availability: str,
    reason: str,
) -> None:
    payloads = _payloads()
    payloads["program_evidence_bundle"]["records"][0][field] = value
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))
    result = ProliferationStressResponseProfile.model_validate(run.result)
    first = next(
        item
        for item in result.program_results
        if item.program_id == "program:proliferation"
    )
    flag = next(
        item
        for item in result.review_flags
        if item.program_id == "program:proliferation"
    )

    assert first.availability == availability
    assert flag.review_flag_state == "cannot_resolve"
    assert reason in first.reason_codes


@pytest.mark.parametrize("change", ["window", "stage"])
def test_stage_not_applicable_is_unavailable(tmp_path: Path, change: str) -> None:
    payloads = _payloads()
    if change == "window":
        payloads["development_window_spec"]["review_state"] = "candidate"
        payloads["development_window_spec"]["reviewer_ref"] = None
        payloads["development_window_spec"]["confirmed_at"] = None
    else:
        payloads["program_evidence_bundle"]["records"][0]["stage_id"] = "stage:other"
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))
    result = ProliferationStressResponseProfile.model_validate(run.result)
    first = next(
        item
        for item in result.program_results
        if item.program_id == "program:proliferation"
    )

    assert first.applicability == "not_applicable"
    assert first.availability == "unavailable"
    assert (
        next(
            item
            for item in result.review_flags
            if item.evidence_id == first.evidence_id
        ).review_flag_state
        == "not_assessed"
    )


def test_program_stage_metric_and_review_vocabulary_is_external(
    tmp_path: Path,
) -> None:
    payloads = _payloads()
    spec = payloads["program_spec"]
    spec["program_rules"] = [
        {
            "program_id": "future-program",
            "gene_set_ref": "gene-set:future",
            "gene_set_sha256": "c" * 64,
            "allowed_analysis_scopes": ["whole_product"],
            "allowed_state_ids": [],
            "allowed_stage_ids": ["future-stage"],
            "allowed_metric_ids": ["future-metric"],
            "minimum_gene_coverage": 0.1,
            "allowed_lod_states": ["future-lod"],
            "resolvable_lod_states": ["future-lod"],
            "review_outcomes": {"future-state": "transcriptomic_review_flag"},
            "orthogonal_follow_up_refs": [],
            "provenance_refs": ["provenance:future-rule"],
        }
    ]
    payloads["program_evidence_bundle"]["records"] = [
        {
            "evidence_id": "future-evidence",
            "program_id": "future-program",
            "analysis_scope": "whole_product",
            "cell_state_id": None,
            "stage_id": "future-stage",
            "metric_id": "future-metric",
            "value": 1,
            "unit": None,
            "numerator": None,
            "denominator": None,
            "gene_coverage": 1.0,
            "lod_state": "future-lod",
            "evidence_state": "future-state",
            "process_step_ids": [],
            "source_run_ref": "tool-run:future",
            "provenance_refs": ["provenance:future"],
        }
    ]

    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["program_results"][0]["program_id"] == "future-program"
    assert (
        run.result["review_flags"][0]["review_flag_state"]
        == "transcriptomic_review_flag"
    )


def test_partial_envelope_and_parameters_are_rejected(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)
    partial = request.model_copy(update={"object_inputs": request.object_inputs[:1]})
    parameterized = request.model_copy(update={"parameters": {"threshold": 0.1}})

    partial_result = registry.check_eligibility(partial)
    parameter_result = registry.check_eligibility(parameterized)

    assert not partial_result.eligible
    assert "exactly_one_program_spec_required" in partial_result.reason_codes
    assert not parameter_result.eligible
    assert "p0_06_parameters_forbidden" in parameter_result.reason_codes


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        (
            {"product_case_sha256": "0" * 64},
            "program_evidence_lineage_checksum_mismatch",
        ),
        (
            {
                "program_spec_ref": {
                    "object_id": "program-spec:other",
                    "object_version": "1.0.0",
                }
            },
            "program_evidence_bundle_binding_mismatch",
        ),
    ],
)
def test_bundle_lineage_drift_fails_closed(
    tmp_path: Path, updates: dict[str, Any], reason: str
) -> None:
    request = _request(tmp_path, bundle_updates=updates)

    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert not eligibility.eligible
    assert reason in eligibility.reason_codes


def test_cell_state_measurement_binding_drift_fails_closed(
    tmp_path: Path,
) -> None:
    payloads = _payloads()
    payloads["cell_state_evidence_profile"]["measurement_spec_version"] = "2.0.0"
    request = _request(tmp_path, payloads=payloads)

    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert not eligibility.eligible
    assert "cell_state_profile_binding_mismatch" in eligibility.reason_codes


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("program_id", "program:undeclared"),
        ("metric_id", "metric:undeclared"),
        ("lod_state", "undeclared-lod"),
        ("evidence_state", "undeclared-state"),
        ("process_step_ids", ["process:undeclared"]),
    ],
)
def test_evidence_outside_external_spec_fails_closed(
    tmp_path: Path, field: str, value: object
) -> None:
    payloads = _payloads()
    payloads["program_evidence_bundle"]["records"][0][field] = value
    request = _request(tmp_path, payloads=payloads)

    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert not eligibility.eligible
    assert "program_evidence_contract_mismatch" in eligibility.reason_codes


def test_input_change_during_run_fails_without_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path)
    spec = ToolRegistry.load_default().describe("P0-06")
    monkeypatch.setattr(adapter_module, "inputs_unchanged", lambda refs: False)

    run = adapter.run(request, spec)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_modified_during_run"]
    assert not (request.output_dir / run.run_id).exists()


def test_visualization_data_failure_is_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path)
    spec = ToolRegistry.load_default().describe("P0-06")

    def fail(**_: object) -> None:
        raise ValueError("invalid visualization data")

    monkeypatch.setattr(
        adapter_module, "build_proliferation_stress_visualization_data", fail
    )
    run = adapter.run(request, spec)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["visualization_data_invalid"]


def test_visualization_render_failure_is_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path)
    spec = ToolRegistry.load_default().describe("P0-06")

    def fail(**_: object) -> None:
        raise RuntimeError("render failed")

    monkeypatch.setattr(
        adapter_module, "prepare_proliferation_stress_visualizations", fail
    )
    run = adapter.run(request, spec)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["visualization_render_failed"]


def test_existing_output_drift_fails_closed(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)
    first = registry.run(request)
    result_path = next(
        item.path
        for item in first.artifacts
        if item.kind == "proliferation_stress_response_profile"
    )
    result_path.write_text("{}\n", encoding="utf-8")

    second = registry.run(request)

    assert second.execution_state is ExecutionState.FAILED
    assert second.reason_codes == ["existing_run_bundle_hash_mismatch"]


@pytest.mark.parametrize(
    "schema_ref", sorted(PUBLIC_SCHEMA_MODELS | PUBLIC_METHOD_SCHEMA_MODELS)
)
def test_public_schemas_are_generated_and_valid(schema_ref: str) -> None:
    schema = ToolRegistry.load_default().resolve_schema(schema_ref)

    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == schema_ref
    assert schema["additionalProperties"] is False


def test_v1_request_is_typed_refusal(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    spec = registry.describe("P0-06")
    request = ToolRequest(
        request_id="request-v1",
        tool_id="P0-06",
        tool_version="0.4.0",
        output_dir=tmp_path / "output",
    )

    eligibility = adapter.check_eligibility(request, spec)
    run = adapter.run(request, spec)

    assert not eligibility.eligible
    assert eligibility.reason_codes == ["tool_request_v2_required"]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["tool_request_v2_required"]
