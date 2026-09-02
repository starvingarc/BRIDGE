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
    ProliferationStressResponseProfileV2,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.visualization_data import (
    P006_COMPONENT_REFS,
    P006VisualizationArtifactSet,
    ProliferationStressVisualizationDataV1,
)
from bridge.toolkit.contracts import (
    ExecutionState,
    ImplementationState,
    MeasurementResultV2,
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
    "measurement_spec": ("bridge://schemas/measurement-spec/v0.2", "1.0.0"),
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
    measurement_spec = {
        "measurement_spec_id": "measurement-spec:p0-06-demo",
        "version": "1.0.0",
        "scientific_question": "Project configured program evidence for gate review.",
        "assay": "scRNA-seq",
        "status": "candidate",
        "applicable_product_cards": ["product-definition:demo@1.0.0"],
        "input_contract": {},
        "analysis_unit": "configured program evidence summary",
        "analysis_unit_kind": "preparation",
        "independence_group_kind": "preparation",
        "observation_unit_kind": "cell",
        "applicable_contexts": [],
        "raw_metric_definition": {
            "metric_ids": ["metric:program-score"],
            "analysis_scopes": ["state_specific", "whole_product"],
        },
        "numerator": "externally configured when applicable",
        "denominator": "externally configured when applicable",
        "direction": None,
        "uncertainty_method": None,
        "minimum_data": {},
        "missing_behavior": "Emit one state-preserving projection per program record.",
        "tool_refs": ["P0-06"],
        "reference_refs": [],
        "prior_refs": [],
        "validation_ref": None,
        "exclusion_rules": {},
        "release_manifest_ref": None,
    }
    return {
        "product_case": product_case,
        "product_definition_card": product_definition,
        "development_window_spec": window,
        "program_spec": program_spec,
        "cell_state_evidence_profile": cell_state,
        "protocol_ir": protocol,
        "program_evidence_bundle": bundle,
        "measurement_spec": measurement_spec,
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
    measurement_projection: bool = False,
) -> ToolRequestV2:
    payloads = deepcopy(payloads or _payloads())
    input_dir = tmp_path / "inputs"
    input_dir.mkdir(exist_ok=True)
    refs: dict[str, StructuredInputRef] = {}
    for role in ROLE_CONTRACTS:
        if role == "program_evidence_bundle" or (
            role == "measurement_spec" and not measurement_projection
        ):
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
        tool_version="0.5.0",
        output_dir=tmp_path / output_name,
        object_inputs=list(refs.values()),
    )


def _projection_spec() -> ToolPackageSpecV2:
    return (
        ToolRegistry.load_default()
        .describe("P0-06")
        .model_copy(
            update={
                "version": "0.5.0",
                "result_schema_ref": (
                    "bridge://schemas/proliferation-stress-response-profile/v0.2"
                ),
            }
        )
    )


def _projection_request(request: ToolRequestV2) -> ToolRequestV2:
    return request.model_copy(update={"tool_version": "0.5.0"})


def test_registry_declares_executable_v2_contract() -> None:
    spec = ToolRegistry.load_default().describe("P0-06")

    assert isinstance(spec, ToolPackageSpecV2)
    assert spec.implementation_state is ImplementationState.IMPLEMENTED
    assert spec.method_ids == METHOD_IDS
    assert spec.result_schema_ref == (
        "bridge://schemas/proliferation-stress-response-profile/v0.2"
    )


def test_valid_bundle_is_descriptive_shadow_and_deterministic(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)

    assert registry.check_eligibility(request).eligible
    first = registry.run(request)
    second = registry.run(request)
    result = ProliferationStressResponseProfileV2.model_validate(first.result)

    assert first.execution_state is ExecutionState.SUCCEEDED
    assert first.run_id == second.run_id
    assert first.result == second.result
    assert result.profile_version == "0.2.0"
    assert first.measurements == []
    assert not any(item.kind == "measurement_result_v2" for item in first.artifacts)
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


def test_v05_without_measurement_spec_uses_v2_not_requested_profile(
    tmp_path: Path,
) -> None:
    run = adapter.run(
        _projection_request(_request(tmp_path)),
        _projection_spec(),
    )
    profile = ProliferationStressResponseProfileV2.model_validate(run.result)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result_schema_ref == _projection_spec().result_schema_ref
    assert profile.profile_version == "0.2.0"
    assert profile.measurement_projection_state == "not_requested"
    assert profile.measurement_spec_ref is None
    assert profile.measurement_artifacts == []
    assert len(profile.program_results) == 2
    assert run.measurements == []
    assert not any(item.kind == "measurement_result_v2" for item in run.artifacts)


def test_v2_json_schema_encodes_projection_state_coherence(tmp_path: Path) -> None:
    spec = _projection_spec()
    not_requested = adapter.run(
        _projection_request(_request(tmp_path, output_name="not-requested")),
        spec,
    ).result
    available = adapter.run(
        _projection_request(
            _request(
                tmp_path,
                output_name="available",
                measurement_projection=True,
            )
        ),
        spec,
    ).result
    schema = ProliferationStressResponseProfileV2.model_json_schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    assert not list(validator.iter_errors(not_requested))
    assert not list(validator.iter_errors(available))

    omitted_default_ref = deepcopy(not_requested)
    omitted_default_ref.pop("measurement_spec_ref")
    parsed = ProliferationStressResponseProfileV2.model_validate(
        omitted_default_ref
    )

    assert parsed.measurement_spec_ref is None
    assert not list(validator.iter_errors(omitted_default_ref))

    invalid_not_requested = deepcopy(not_requested)
    invalid_not_requested.update(
        {
            "measurement_spec_ref": available["measurement_spec_ref"],
            "measurement_artifacts": available["measurement_artifacts"],
        }
    )
    with pytest.raises(ValueError):
        ProliferationStressResponseProfileV2.model_validate(invalid_not_requested)
    assert list(validator.iter_errors(invalid_not_requested))

    invalid_available = deepcopy(available)
    invalid_available.update(
        {
            "measurement_spec_ref": None,
            "measurement_artifacts": [],
        }
    )
    with pytest.raises(ValueError):
        ProliferationStressResponseProfileV2.model_validate(invalid_available)
    assert list(validator.iter_errors(invalid_available))


def test_default_contract_accepts_measurement_projection(tmp_path: Path) -> None:
    spec = ToolRegistry.load_default().describe("P0-06")
    request = _request(tmp_path, measurement_projection=True)

    eligibility = adapter.check_eligibility(request, spec)
    run = adapter.run(request, spec)

    assert eligibility.eligible
    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result_schema_ref == spec.result_schema_ref
    ProliferationStressResponseProfileV2.model_validate(run.result)


def test_measurement_projection_checksummed_artifact_per_program_record(
    tmp_path: Path,
) -> None:
    request = _projection_request(_request(tmp_path, measurement_projection=True))
    spec = _projection_spec()

    assert adapter.check_eligibility(request, spec).eligible
    run = adapter.run(request, spec)
    rerun = adapter.run(request, spec)
    profile = ProliferationStressResponseProfileV2.model_validate(run.result)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result_schema_ref == _projection_spec().result_schema_ref
    assert run.run_id == rerun.run_id
    assert run.result == rerun.result
    assert run.measurements == rerun.measurements
    assert profile.profile_version == "0.2.0"
    assert profile.measurement_projection_state == "available"
    assert profile.measurement_spec_ref.ref == "measurement-spec:p0-06-demo@1.0.0"
    assert len(profile.program_results) == 2
    assert len(run.measurements) == len(profile.program_results)
    assert len(profile.measurement_artifacts) == len(profile.program_results)
    assert [item.evidence_id for item in profile.measurement_artifacts] == [
        item.evidence_id for item in profile.program_results
    ]
    measurement_by_id = {item.measurement_id: item for item in run.measurements}
    summary_by_evidence = {item.evidence_id: item for item in profile.program_results}
    expected_states = {
        "program-evidence:proliferation": ("below-rule", "negative"),
        "program-evidence:stress": ("elevated", "alert"),
    }
    expected_provenance = {
        "program-evidence:proliferation": {
            "tool-run:upstream-proliferation",
            "provenance:evidence-proliferation",
        },
        "program-evidence:stress": {
            "tool-run:upstream-stress",
            "provenance:evidence-stress",
        },
    }
    for binding in profile.measurement_artifacts:
        measurement = measurement_by_id[binding.measurement_id]
        summary = summary_by_evidence[binding.evidence_id]
        artifact = next(
            item for item in run.artifacts if item.artifact_id == binding.artifact_id
        )
        persisted = MeasurementResultV2.model_validate_json(artifact.path.read_text())
        source_state, projected_state = expected_states[binding.evidence_id]
        assert persisted == measurement
        assert binding.source_evidence_state == source_state == summary.evidence_state
        assert binding.projected_evidence_state == projected_state
        assert measurement.metric_name == summary.metric_id
        assert measurement.raw_value == summary.value
        assert measurement.unit == summary.unit
        assert measurement.numerator == summary.numerator
        assert measurement.denominator == summary.denominator
        assert measurement.evidence_state == projected_state
        assert measurement.unknown_scope is None
        assert measurement.score_state == "unavailable"
        assert measurement.domain_score is None
        assert measurement.source_run_ref == f"tool-run:{run.run_id}@{run.tool_version}"
        assert measurement.source_execution_state == "succeeded"
        assert set(measurement.provenance_refs) == expected_provenance[
            binding.evidence_id
        ]
        assert hashlib.sha256(artifact.path.read_bytes()).hexdigest() == binding.sha256
        assert artifact.evidence_ids == [binding.evidence_id]


@pytest.mark.parametrize(
    ("record_index", "projected_state"),
    [
        (0, "negative"),
        (1, "alert"),
    ],
)
def test_numeric_projection_preserves_counts_and_unit_when_raw_value_is_null(
    tmp_path: Path,
    record_index: int,
    projected_state: str,
) -> None:
    payloads = _payloads()
    record = payloads["program_evidence_bundle"]["records"][record_index]
    record.update(
        {
            "value": None,
            "unit": "cell-count",
            "numerator": 0,
            "denominator": 10,
        }
    )
    run = adapter.run(
        _projection_request(
            _request(
                tmp_path,
                payloads=payloads,
                measurement_projection=True,
            )
        ),
        _projection_spec(),
    )
    profile = ProliferationStressResponseProfileV2.model_validate(run.result)
    summary = next(
        item
        for item in profile.program_results
        if item.evidence_id == record["evidence_id"]
    )
    binding = next(
        item
        for item in profile.measurement_artifacts
        if item.evidence_id == summary.evidence_id
    )
    measurement = next(
        item
        for item in run.measurements
        if item.measurement_id == binding.measurement_id
    )

    assert measurement.evidence_state == projected_state
    assert measurement.raw_value is summary.value is None
    assert measurement.unit == summary.unit == "cell-count"
    assert measurement.numerator == summary.numerator == 0
    assert measurement.denominator == summary.denominator == 10


@pytest.mark.parametrize(
    (
        "state",
        "availability",
        "applicability",
        "review_flag_state",
        "source_evidence_state",
        "projected_evidence_state",
    ),
    [
        (
            "unavailable",
            "unavailable",
            "applicable",
            "cannot_resolve",
            "below-rule",
            "unavailable",
        ),
        (
            "cannot_resolve_lod",
            "cannot_resolve",
            "applicable",
            "cannot_resolve",
            "below-rule",
            "unknown",
        ),
        (
            "cannot_resolve_review",
            "available",
            "applicable",
            "cannot_resolve",
            "uncertain",
            "unknown",
        ),
        (
            "not_assessed",
            "available",
            "applicable",
            "not_assessed",
            "below-rule",
            "unavailable",
        ),
        (
            "not_applicable",
            "unavailable",
            "not_applicable",
            "not_assessed",
            "below-rule",
            "unavailable",
        ),
    ],
)
def test_non_numeric_projection_preserves_source_record_without_fabricating_values(
    tmp_path: Path,
    state: str,
    availability: str,
    applicability: str,
    review_flag_state: str,
    source_evidence_state: str,
    projected_evidence_state: str,
) -> None:
    payloads = _payloads()
    if state == "unavailable":
        payloads["program_evidence_bundle"]["records"][0]["gene_coverage"] = 0.5
    elif state == "cannot_resolve_lod":
        payloads["program_evidence_bundle"]["records"][0]["lod_state"] = "unqualified"
    elif state == "cannot_resolve_review":
        payloads["program_evidence_bundle"]["records"][0]["evidence_state"] = (
            "uncertain"
        )
    elif state == "not_assessed":
        payloads["program_spec"]["program_rules"][0]["review_outcomes"][
            "below-rule"
        ] = "not_assessed"
    else:
        payloads["development_window_spec"].update(
            {"review_state": "candidate", "reviewer_ref": None, "confirmed_at": None}
        )
    run = adapter.run(
        _projection_request(
            _request(
                tmp_path,
                payloads=payloads,
                measurement_projection=True,
            )
        ),
        _projection_spec(),
    )
    profile = ProliferationStressResponseProfileV2.model_validate(run.result)
    summary = next(
        item
        for item in profile.program_results
        if item.evidence_id == "program-evidence:proliferation"
    )
    flag = next(
        item
        for item in profile.review_flags
        if item.evidence_id == summary.evidence_id
    )
    binding = next(
        item
        for item in profile.measurement_artifacts
        if item.evidence_id == summary.evidence_id
    )
    measurement = next(
        item
        for item in run.measurements
        if item.measurement_id == binding.measurement_id
    )

    assert len(profile.measurement_artifacts) == len(profile.program_results) == 2
    assert len(run.measurements) == 2
    assert summary.value == 0.2
    assert summary.unit == "relative-score"
    assert summary.availability == availability
    assert summary.applicability == applicability
    assert flag.review_flag_state == review_flag_state
    assert binding.source_evidence_state == source_evidence_state
    assert binding.projected_evidence_state == projected_evidence_state
    assert measurement.evidence_state == projected_evidence_state
    assert measurement.raw_value is None
    assert measurement.unit is None
    assert measurement.numerator is None
    assert measurement.denominator is None
    assert measurement.interval is None
    assert measurement.unknown_scope == (
        "measurement" if projected_evidence_state == "unknown" else None
    )
    assert measurement.score_state == "unavailable"
    assert measurement.domain_score is None
    assert set(measurement.provenance_refs) == {
        "tool-run:upstream-proliferation",
        "provenance:evidence-proliferation",
    }


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("duplicate", "projected evidence IDs must be unique"),
        ("source_state", "measurement binding source evidence state mismatch"),
        ("projected_state", "measurement binding projected evidence state mismatch"),
    ],
)
def test_v2_profile_rejects_duplicate_or_tampered_measurement_bindings(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    run = adapter.run(
        _projection_request(_request(tmp_path, measurement_projection=True)),
        _projection_spec(),
    )
    payload = deepcopy(run.result)
    bindings = payload["measurement_artifacts"]
    if mutation == "duplicate":
        bindings[1]["evidence_id"] = bindings[0]["evidence_id"]
    elif mutation == "source_state":
        bindings[0]["source_evidence_state"] = "tampered-state"
    else:
        bindings[0]["projected_evidence_state"] = "alert"

    with pytest.raises(ValueError, match=message):
        ProliferationStressResponseProfileV2.model_validate(payload)


def test_projection_rerun_rejects_tampered_measurement_artifact(
    tmp_path: Path,
) -> None:
    request = _projection_request(_request(tmp_path, measurement_projection=True))
    spec = _projection_spec()
    first = adapter.run(request, spec)
    measurement_artifact = next(
        item for item in first.artifacts if item.kind == "measurement_result_v2"
    )
    measurement_artifact.path.write_text("{}\n", encoding="utf-8")

    rerun = adapter.run(request, spec)

    assert rerun.execution_state is ExecutionState.FAILED
    assert rerun.reason_codes == ["existing_run_bundle_hash_mismatch"]


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("tool", "measurement_spec_tool_binding_mismatch"),
        ("metric", "measurement_spec_metric_ids_mismatch"),
        ("scope", "measurement_spec_analysis_scopes_mismatch"),
    ],
)
def test_measurement_spec_projection_scope_fails_closed(
    tmp_path: Path,
    mutation: str,
    reason: str,
) -> None:
    payloads = _payloads()
    measurement_spec = payloads["measurement_spec"]
    if mutation == "tool":
        measurement_spec["tool_refs"] = []
    elif mutation == "metric":
        measurement_spec["raw_metric_definition"]["metric_ids"] = ["metric:other"]
    else:
        measurement_spec["raw_metric_definition"]["analysis_scopes"] = ["whole_product"]

    eligibility = adapter.check_eligibility(
        _projection_request(
            _request(
                tmp_path,
                payloads=payloads,
                measurement_projection=True,
            )
        ),
        _projection_spec(),
    )

    assert not eligibility.eligible
    assert reason in eligibility.reason_codes


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
    result = ProliferationStressResponseProfileV2.model_validate(run.result)

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
    result = ProliferationStressResponseProfileV2.model_validate(run.result)
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
    result = ProliferationStressResponseProfileV2.model_validate(run.result)
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
    if schema_ref.endswith("proliferation-stress-response-profile/v0.2"):
        schema = PUBLIC_SCHEMA_MODELS[schema_ref].model_json_schema()
        schema["$id"] = schema_ref
    else:
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
        tool_version="0.5.0",
        output_dir=tmp_path / "output",
    )

    eligibility = adapter.check_eligibility(request, spec)
    run = adapter.run(request, spec)

    assert not eligibility.eligible
    assert eligibility.reason_codes == ["tool_request_v2_required"]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["tool_request_v2_required"]
