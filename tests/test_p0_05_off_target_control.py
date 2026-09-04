from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Callable

from jsonschema import Draft202012Validator
import pytest

from bridge.tool_packages.p0_05_off_target_control.adapter import adapter
from bridge.tool_packages.p0_05_off_target_control.models import (
    OffTargetControlProfileV2,
)
from bridge.tool_packages.p0_05_off_target_control.visualization_data import (
    OffTargetControlVisualizationDataV1,
    P005VisualizationArtifactSet,
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
from bridge.toolkit.schemas import load_schema
from bridge.toolkit.visualization import FigureRegistry


ROLE_SCHEMAS = {
    "product_case": ("bridge://schemas/product-case/v0.1", "0.1.0"),
    "product_definition_card": (
        "bridge://schemas/product-definition-card/v0.1",
        "0.1.0",
    ),
    "state_role_map": ("bridge://schemas/state-role-map/v0.1", "0.1.0"),
    "off_target_assessment_spec": (
        "bridge://schemas/off-target-assessment-spec/v0.1",
        "0.1.0",
    ),
    "cell_state_evidence_profile": (
        "bridge://schemas/cell-state-evidence-profile/v0.2",
        "0.2.0",
    ),
    "off_target_evidence_bundle": (
        "bridge://schemas/off-target-evidence-bundle/v0.1",
        "0.1.0",
    ),
    "biological_unit_manifest": (
        "bridge://schemas/biological-unit-manifest/v0.1",
        "0.1.0",
    ),
}


def _encoded(payload: dict) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()


def _write(path: Path, payload: dict) -> str:
    raw = _encoded(payload)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def _request(tmp_path: Path) -> ToolRequestV2:
    root = tmp_path / "objects"
    root.mkdir()
    timestamp = datetime(2026, 8, 25, tzinfo=timezone.utc).isoformat()
    role_map = {
        "object_version": "0.1.0",
        "state_role_map_id": "state-role-map:demo",
        "map_version": "1",
        "product_definition_ref": {
            "object_id": "product-definition:demo",
            "object_version": "1",
        },
        "review_state": "draft",
        "assignments": [
            {
                "state_id": "state:a",
                "product_role": "target",
                "role_evidence_class": "externally_defined_target",
                "evidence_direction": "externally_defined",
                "source_refs": ["source:role-map"],
            },
            {
                "state_id": "state:b",
                "product_role": "known_off_target",
                "role_evidence_class": "externally_defined_non_target",
                "evidence_direction": "externally_defined",
                "source_refs": ["source:role-map"],
            },
        ],
        "provenance_refs": [
            {"object_id": "source:role-map", "object_version": "1"}
        ],
    }
    product_definition = {
        "object_version": "0.1.0",
        "product_definition_id": "product-definition:demo",
        "definition_version": "1",
        "state_role_map_ref": {
            "object_id": "state-role-map:demo",
            "object_version": "1",
        },
        "supported_assays": ["scRNA-seq"],
        "review_state": "draft",
        "provenance_refs": [
            {"object_id": "source:definition", "object_version": "1"}
        ],
    }
    product_case = {
        "object_version": "0.1.0",
        "product_case_id": "product-case:demo",
        "case_version": "1",
        "product_definition_ref": {
            "object_id": "product-definition:demo",
            "object_version": "1",
        },
        "source_unit_kind": "preparation",
        "sample_or_preparation_ref": {
            "object_id": "preparation:demo",
            "object_version": "1",
        },
        "measurement_spec_ref": {
            "object_id": "measurement-spec:cell-state",
            "object_version": "1",
        },
        "assay": "scRNA-seq",
        "provenance_refs": [
            {"object_id": "source:case", "object_version": "1"}
        ],
        "created_at": timestamp,
    }
    cell_state_profile = {
        "profile_id": "cell-state-profile:demo",
        "assay": "scRNA-seq",
        "measurement_spec_id": "measurement-spec:cell-state",
        "measurement_spec_version": "1",
        "measurement_spec_status": "candidate",
        "annotation_vocabulary_ref": "annotation-vocabulary:demo@1",
        "reference_snapshot_ref": "reference-snapshot:demo@1",
        "n_observations": 10,
        "n_genes": 100,
        "denominator": "eligible cells",
        "label_levels": {},
        "source_support": {},
        "marker_program_evidence": {},
        "prediction_sets": {},
        "composition": {},
        "gene_coverage": {},
        "modality_sensitivity": {},
        "score_state": "shadow",
        "domain_score": None,
        "evidence_ids": ["evidence:demo"],
    }

    manifest = {
        "object_version": "0.1.0",
        "manifest_id": "biological-unit-manifest:demo",
        "manifest_version": "1",
        "schema_ref": "bridge://schemas/biological-unit-manifest/v0.1",
        "generator_tool_id": "BRIDGE-BIOLOGICAL-UNIT-REVIEW",
        "generator_tool_version": "1",
        "data_view_ref": "data-view:demo",
        "selected_artifact_sha256": "a" * 64,
        "observation_ids_sha256": "b" * 64,
        "n_observations": 10,
        "assignment_schema_ref": "bridge://schemas/biological-unit-assignment/v0.1",
        "assignment_artifact_sha256": "c" * 64,
        "assignment_row_count": 10,
        "unit_identity_namespace_ref": {
            "object_id": "biological-unit-namespace:demo",
            "object_version": "1",
        },
        "analysis_unit_kind": "preparation",
        "independence_group_kind": "sample",
        "independence_scope_ref": {
            "object_id": "independence-scope:demo",
            "object_version": "1",
        },
        "lineage_state": "reviewed",
        "review_gate_ref": {
            "object_id": "biological-unit-review:demo",
            "object_version": "1",
        },
        "review_gate_sha256": "d" * 64,
        "unit_bindings": [
            {
                "analysis_unit_ref": {
                    "object_id": "preparation:demo",
                    "object_version": "1",
                },
                "analysis_unit_kind": "preparation",
                "independence_group_ref": {
                    "object_id": "sample:demo",
                    "object_version": "1",
                },
                "independence_group_kind": "sample",
                "capture_ref": None,
                "preparation_ref": {
                    "object_id": "preparation:demo",
                    "object_version": "1",
                },
                "sample_ref": {
                    "object_id": "sample:demo",
                    "object_version": "1",
                },
            }
        ],
    }
    paths = {
        role: root / f"{role}.json"
        for role in ROLE_SCHEMAS
    }
    role_map_sha = _write(paths["state_role_map"], role_map)
    definition_sha = _write(
        paths["product_definition_card"], product_definition
    )
    manifest_sha = _write(paths["biological_unit_manifest"], manifest)
    product_case.update(
        {
            "biological_unit_manifest_ref": {
                "object_id": manifest["manifest_id"],
                "object_version": manifest["manifest_version"],
            },
            "biological_unit_manifest_sha256": manifest_sha,
            "independence_scope_ref": manifest["independence_scope_ref"],
            "independence_group_refs": [
                manifest["unit_bindings"][0]["independence_group_ref"]
            ],
        }
    )
    case_sha = _write(paths["product_case"], product_case)
    profile_sha = _write(
        paths["cell_state_evidence_profile"], cell_state_profile
    )
    assessment_spec = {
        "object_version": "0.1.0",
        "assessment_spec_id": "off-target-assessment-spec:demo",
        "spec_version": "1",
        "product_definition_ref": {
            "object_id": "product-definition:demo",
            "object_version": "1",
        },
        "state_role_map_ref": {
            "object_id": "state-role-map:demo",
            "object_version": "1",
        },
        "state_role_map_sha256": role_map_sha,
        "primary_denominator_id": "eligible-cells",
        "allowed_unknown_reason_ids": ["reference_gap"],
        "rare_state_rules": [
            {
                "state_id": "state:b",
                "max_validated_detection_limit_fraction": 0.05,
                "max_false_positive_fraction": 0.01,
                "missing_calibration_state": "cannot_exclude",
            }
        ],
        "active": True,
    }
    _write(paths["off_target_assessment_spec"], assessment_spec)
    evidence_bundle = {
        "object_version": "0.1.0",
        "bundle_id": "off-target-evidence-bundle:demo",
        "bundle_version": "1",
        "product_case_ref": "product-case:demo@1",
        "product_case_sha256": case_sha,
        "product_definition_ref": "product-definition:demo@1",
        "product_definition_sha256": definition_sha,
        "cell_state_profile_id": "cell-state-profile:demo",
        "cell_state_profile_sha256": profile_sha,
        "denominator": {
            "denominator_id": "eligible-cells",
            "n_observations": 10,
            "total_soft_mass": 10.0,
            "unit": "cells",
        },
        "composition_coverage_state": "complete",
        "state_observations": [
            {"state_id": "state:a", "soft_mass": 7.0, "observed_count": 7},
            {"state_id": "state:b", "soft_mass": 2.0, "observed_count": 2},
        ],
        "unknown_coverage_state": "complete",
        "unknown_observations": [
            {
                "reason_id": "reference_gap",
                "soft_mass": 1.0,
                "observed_count": 1,
            }
        ],
        "rare_state_calibrations": [
            {
                "state_id": "state:b",
                "calibration_ref": "calibration:demo",
                "calibration_sha256": "a" * 64,
                "validated_detection_limit_fraction": 0.02,
                "false_positive_fraction": 0.005,
                "zero_observation_upper_bound_fraction": 0.03,
            }
        ],
        "created_at": timestamp,
    }
    _write(paths["off_target_evidence_bundle"], evidence_bundle)

    refs = []
    for role, (schema_ref, object_version) in ROLE_SCHEMAS.items():
        raw = paths[role].read_bytes()
        refs.append(
            StructuredInputRef(
                input_id=f"input-{role}",
                role=role,
                schema_ref=schema_ref,
                object_version=object_version,
                path=paths[role],
                sha256=hashlib.sha256(raw).hexdigest(),
            )
        )
    return ToolRequestV2(
        request_id="request-p0-05",
        tool_id="P0-05",
        tool_version="0.5.1",
        output_dir=tmp_path / "output",
        object_inputs=refs,
    )


def _projection_spec() -> ToolPackageSpecV2:
    return ToolRegistry.load_default().describe("P0-05")


def _projection_request(request: ToolRequestV2) -> ToolRequestV2:
    return request


def _with_measurement_spec(request: ToolRequestV2) -> ToolRequestV2:
    root = request.object_inputs[0].path.parent
    payload = {
        "measurement_spec_id": "measurement-spec:cell-state",
        "version": "1",
        "scientific_question": (
            "How should declared off-target accounting records be projected?"
        ),
        "assay": "scRNA-seq",
        "status": "candidate",
        "applicable_product_cards": ["product-definition:demo@1"],
        "input_contract": {
            "source_result": "off-target-control-profile",
            "projection": "record_preserving",
        },
        "analysis_unit": "preparation",
        "analysis_unit_kind": "preparation",
        "independence_group_kind": "sample",
        "observation_unit_kind": "cell",
        "applicable_contexts": ["in_vitro_product_assessment"],
        "raw_metric_definition": {
            "metric_names": [
                "off_target_identity_unknown",
                "off_target_rare_state_detection",
                "off_target_role_composition",
            ]
        },
        "numerator": None,
        "denominator": None,
        "direction": None,
        "uncertainty_method": None,
        "minimum_data": {},
        "missing_behavior": "preserve_missing_unknown_and_unavailable_states",
        "tool_refs": ["P0-05"],
        "reference_refs": [],
        "prior_refs": [],
        "validation_ref": None,
        "exclusion_rules": {},
        "release_manifest_ref": None,
    }
    path = root / "measurement_spec.json"
    digest = _write(path, payload)
    ref = StructuredInputRef(
        input_id="input-measurement-spec",
        role="measurement_spec",
        schema_ref="bridge://schemas/measurement-spec/v0.2",
        object_version=payload["version"],
        path=path,
        sha256=digest,
    )
    return request.model_copy(
        update={"object_inputs": [*request.object_inputs, ref]}
    )


def _projected_measurement(
    run, record_scope: str, record_id: str
) -> MeasurementResultV2:
    binding = next(
        item
        for item in run.result["measurement_artifacts"]
        if item["record_scope"] == record_scope and item["record_id"] == record_id
    )
    artifact = next(
        item for item in run.artifacts if item.artifact_id == binding["artifact_id"]
    )
    return MeasurementResultV2.model_validate_json(
        artifact.path.read_text(encoding="utf-8")
    )


def _rewrite(
    request: ToolRequestV2,
    role: str,
    mutate: Callable[[dict], None],
) -> ToolRequestV2:
    refs = list(request.object_inputs)
    index = next(index for index, ref in enumerate(refs) if ref.role == role)
    ref = refs[index]
    payload = json.loads(ref.path.read_text())
    mutate(payload)
    digest = _write(ref.path, payload)
    refs[index] = ref.model_copy(update={"sha256": digest})
    return request.model_copy(update={"object_inputs": refs})


def _role(result: dict, role: str) -> dict:
    return next(
        item for item in result["role_composition"]
        if item["product_role"] == role
    )


def test_registry_exposes_executable_p0_05() -> None:
    spec = ToolRegistry.load_default().describe("P0-05")

    assert spec.implementation_state is ImplementationState.IMPLEMENTED
    assert spec.version == "0.5.1"
    assert spec.result_schema_ref == (
        "bridge://schemas/off-target-control-profile/v0.2"
    )
    assert spec.method_ids == [
        "METHOD-BRIDGE-ROLE-AWARE-SOFT-COMPOSITION",
        "METHOD-EXACT-BINOMIAL-CLOPPER-PEARSON",
        "METHOD-HARD-LABEL-COMPOSITION",
        "METHOD-SAMPLE-PRESERVING-HIERARCHICAL-BOOTSTRAP-9669E1",
        "METHOD-BRIDGE-SAMPLE-PRESERVING-SPIKE-IN",
        "METHOD-SINGLE-STATE-AT-LEAST-ONE-BINOMIAL-PLANNER",
        "METHOD-BRIDGE-MODEL-AND-REFERENCE-DISAGREEMENT",
        "METHOD-BRIDGE-OOD-ENSEMBLE",
    ]
    contract = ToolRegistry.load_default().describe_input("P0-05")
    for mode in contract.object_input_modes:
        role = next(item for item in mode.roles if item.role == "measurement_spec")
        assert role.schema_refs == ["bridge://schemas/measurement-spec/v0.2"]
        assert role.object_version_policy == "payload"
        assert role.min_count == 0
        assert role.max_count == 1




def test_happy_run_aggregates_external_roles_and_publishes_checksum(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)

    assert registry.check_eligibility(request).eligible
    run = registry.run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.measurements == []
    assert run.result_schema_ref.endswith("off-target-control-profile/v0.2")
    assert run.result["object_version"] == "0.2.0"
    assert run.result["profile_version"] == "0.2.0"
    assert run.result["measurement_projection_state"] == "not_requested"
    assert len(run.artifacts) == 15
    assert _role(run.result, "target")["fraction"] == pytest.approx(0.7)
    assert _role(run.result, "known_off_target")["fraction"] == pytest.approx(0.2)
    assert run.result["unknown_profile"]["fraction"] == pytest.approx(0.1)
    assert run.result["rare_state_profile"][0]["detection_state"] == "detected"
    assert run.result["evidence_state"] == "shadow"
    assert run.result["score_state"] == "unavailable"
    assert run.result["domain_score"] is None
    assert hashlib.sha256(run.artifacts[0].path.read_bytes()).hexdigest() == (
        run.artifacts[0].sha256
    )
    visualization_data = next(
        item
        for item in run.artifacts
        if item.kind == "off_target_control_visualization_data"
    )
    payload = json.loads(visualization_data.path.read_text(encoding="utf-8"))
    assert {
        item["category"] for item in payload["product_records"]
    } == {
        "target",
        "acceptable_adjacent",
        "known_off_target",
        "role_unresolved",
        "identity_unknown",
    }
    assert sum(
        item["observed_count"] for item in payload["product_records"]
    ) == payload["denominator_count"]
    assert payload["ood_component_applicability"] == "not_assessed"
    assert payload["ood_channel_records"] == []
    artifact_set = next(
        item
        for item in run.artifacts
        if item.kind == "visualization_artifact_set"
    )
    typed_set = P005VisualizationArtifactSet.model_validate_json(
        artifact_set.path.read_text(encoding="utf-8")
    )
    figure_registry = FigureRegistry.load_default()
    for artifact in typed_set.visualizations:
        figure_registry.validate_artifact(artifact)
    assert load_schema(
        "bridge://schemas/off-target-control-visualization-data/v0.1"
    )
    assert load_schema(
        "bridge://schemas/p0-05-visualization-artifact-set/v0.1"
    )


def test_v05_without_measurement_spec_uses_v2_not_requested_profile(
    tmp_path: Path,
) -> None:
    request = _projection_request(_request(tmp_path))
    run = adapter.run(request, _projection_spec())

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result_schema_ref == _projection_spec().result_schema_ref
    assert run.result["object_version"] == "0.2.0"
    assert run.result["profile_version"] == "0.2.0"
    assert run.result["measurement_projection_state"] == "not_requested"
    assert run.result["measurement_spec_ref"] is None
    assert run.result["measurement_spec_sha256"] is None
    assert run.result["measurement_artifacts"] == []
    assert run.measurements == []
    assert not any(
        item.kind == "measurement_result_v2" for item in run.artifacts
    )
    assert _role(run.result, "target")["fraction"] == pytest.approx(0.7)
    assert run.result["unknown_profile"]["fraction"] == pytest.approx(0.1)
    assert run.result["rare_state_profile"][0]["detection_state"] == "detected"


def test_v2_json_schema_encodes_projection_state_coherence(tmp_path: Path) -> None:
    base_request = _request(tmp_path)
    not_requested = adapter.run(
        _projection_request(base_request),
        _projection_spec(),
    ).result
    available = adapter.run(
        _projection_request(_with_measurement_spec(base_request)),
        _projection_spec(),
    ).result
    schema = OffTargetControlProfileV2.model_json_schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    assert not list(validator.iter_errors(not_requested))
    assert not list(validator.iter_errors(available))

    omitted_default_fields = json.loads(json.dumps(not_requested))
    omitted_default_fields.pop("measurement_spec_ref")
    omitted_default_fields.pop("measurement_spec_sha256")
    parsed = OffTargetControlProfileV2.model_validate(omitted_default_fields)

    assert parsed.measurement_spec_ref is None
    assert parsed.measurement_spec_sha256 is None
    assert not list(validator.iter_errors(omitted_default_fields))

    invalid_not_requested = json.loads(json.dumps(not_requested))
    invalid_not_requested.update(
        {
            "measurement_spec_ref": available["measurement_spec_ref"],
            "measurement_spec_sha256": available["measurement_spec_sha256"],
            "measurement_artifacts": available["measurement_artifacts"],
        }
    )
    assert list(validator.iter_errors(invalid_not_requested))

    invalid_available = json.loads(json.dumps(available))
    invalid_available.update(
        {
            "measurement_spec_ref": None,
            "measurement_spec_sha256": None,
            "measurement_artifacts": [],
        }
    )
    assert list(validator.iter_errors(invalid_available))


def test_measurement_spec_opts_into_v02_checksummed_record_projection(
    tmp_path: Path,
) -> None:
    request = _projection_request(_with_measurement_spec(_request(tmp_path)))

    registry = ToolRegistry.load_default()
    assert registry.check_eligibility(request).eligible
    run = registry.run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result_schema_ref == _projection_spec().result_schema_ref
    assert run.result["measurement_projection_state"] == "available"
    assert run.result["object_version"] == "0.2.0"
    assert run.result["profile_version"] == "0.2.0"
    assert run.result["measurement_spec_ref"] == {
        "object_id": "measurement-spec:cell-state",
        "object_version": "1",
    }
    assert len(run.measurements) == 6
    assert len(run.result["measurement_artifacts"]) == 6
    assert len(run.artifacts) == 21
    measurement_artifacts = [
        item for item in run.artifacts if item.kind == "measurement_result_v2"
    ]
    assert len(measurement_artifacts) == 6
    for artifact in measurement_artifacts:
        assert hashlib.sha256(artifact.path.read_bytes()).hexdigest() == artifact.sha256
        measurement = MeasurementResultV2.model_validate_json(
            artifact.path.read_text(encoding="utf-8")
        )
        assert measurement.domain_score is None
        assert measurement.measurement_spec_id == "measurement-spec:cell-state"
        assert measurement.measurement_spec_version == "1"
        assert measurement.source_execution_state == "succeeded"

    target = _projected_measurement(run, "role", "target")
    assert target.evidence_state.value == "inferred"
    assert target.raw_value == _role(run.result, "target")
    assert target.score_state.value == "unavailable"
    unresolved = _projected_measurement(run, "role", "role_unresolved")
    assert unresolved.evidence_state.value == "inferred"
    assert unresolved.raw_value["observed_count"] == 0
    assert unresolved.raw_value["exclusion_state"] == "cannot_exclude"
    unknown = _projected_measurement(run, "identity_unknown", "identity-unknown")
    assert unknown.evidence_state.value == "unknown"
    assert unknown.unknown_scope == "identity"
    assert unknown.raw_value == run.result["unknown_profile"]
    assert unknown.score_state.value == "unavailable"
    rare = _projected_measurement(run, "rare_state", "state:b")
    assert rare.evidence_state.value == "inferred"
    assert rare.raw_value == run.result["rare_state_profile"][0]
    assert rare.score_state.value == "unavailable"


def test_v2_profile_rejects_scope_metric_binding_tamper(tmp_path: Path) -> None:
    run = adapter.run(
        _projection_request(_with_measurement_spec(_request(tmp_path))),
        _projection_spec(),
    )
    payload = run.result
    target = next(
        item
        for item in payload["measurement_artifacts"]
        if item["record_scope"] == "role" and item["record_id"] == "target"
    )
    target["metric_name"] = "off_target_rare_state_detection"

    with pytest.raises(
        ValueError,
        match="measurement metric must match its source record scope",
    ):
        OffTargetControlProfileV2.model_validate(payload)


def test_v2_profile_rejects_source_evidence_state_binding_tamper(
    tmp_path: Path,
) -> None:
    run = adapter.run(
        _projection_request(_with_measurement_spec(_request(tmp_path))),
        _projection_spec(),
    )
    payload = run.result
    target = next(
        item
        for item in payload["measurement_artifacts"]
        if item["record_scope"] == "role" and item["record_id"] == "target"
    )
    target["evidence_state"] = "negative"

    with pytest.raises(
        ValueError,
        match="measurement evidence must match its source record state",
    ):
        OffTargetControlProfileV2.model_validate(payload)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (
            lambda payload: payload.update({"tool_refs": []}),
            "measurement_spec_tool_not_authorized",
        ),
        (
            lambda payload: payload["raw_metric_definition"].update(
                {"metric_names": ["off_target_role_composition"]}
            ),
            "measurement_spec_metric_names_mismatch",
        ),
    ],
)
def test_measurement_spec_authorization_fails_closed(
    tmp_path: Path,
    change: Callable[[dict], None],
    reason: str,
) -> None:
    request = _projection_request(_with_measurement_spec(_request(tmp_path)))
    request = _rewrite(request, "measurement_spec", change)

    eligibility = adapter.check_eligibility(request, _projection_spec())

    assert not eligibility.eligible
    assert reason in eligibility.reason_codes


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("analysis_unit_kind", "capture"),
        ("independence_group_kind", "donor"),
        ("observation_unit_kind", "nucleus"),
    ],
)
def test_aggregation_projection_rejects_biological_unit_mismatch(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    request = _rewrite(
        _with_measurement_spec(_request(tmp_path)),
        "measurement_spec",
        lambda payload: payload.update({field: value}),
    )

    eligibility = adapter.check_eligibility(request, _projection_spec())

    assert not eligibility.eligible
    assert "measurement_spec_biological_unit_mismatch" in eligibility.reason_codes


def test_aggregation_projection_requires_reviewed_biological_units(
    tmp_path: Path,
) -> None:
    request = _with_measurement_spec(_request(tmp_path))
    request = request.model_copy(
        update={
            "object_inputs": [
                item
                for item in request.object_inputs
                if item.role != "biological_unit_manifest"
            ]
        }
    )

    eligibility = adapter.check_eligibility(request, _projection_spec())

    assert not eligibility.eligible
    assert (
        "measurement_projection_requires_biological_unit_manifest"
        in eligibility.reason_codes
    )


def test_projection_preserves_partial_unknown_and_withholds_unavailable_values(
    tmp_path: Path,
) -> None:
    request = _rewrite(
        _with_measurement_spec(_request(tmp_path)),
        "off_target_evidence_bundle",
        lambda payload: payload.update(
            {
                "composition_coverage_state": "partial",
                "unknown_coverage_state": "partial",
                "state_observations": [
                    {"state_id": "state:a", "soft_mass": 7.0, "observed_count": 7},
                    {"state_id": "state:b", "soft_mass": 0.0, "observed_count": 0},
                ],
            }
        ),
    )
    request = _projection_request(request)

    run = adapter.run(request, _projection_spec())

    target = _projected_measurement(run, "role", "target")
    assert target.evidence_state.value == "unavailable"
    assert target.raw_value is None
    assert target.score_state.value == "unavailable"
    assert target.numerator is None
    assert target.denominator is None
    unknown = _projected_measurement(run, "identity_unknown", "identity-unknown")
    assert unknown.evidence_state.value == "unknown"
    assert unknown.unknown_scope == "identity"
    assert unknown.raw_value == run.result["unknown_profile"]
    rare = _projected_measurement(run, "rare_state", "state:b")
    assert rare.evidence_state.value == "unknown"
    assert rare.unknown_scope == "measurement"
    assert rare.raw_value is None
    assert rare.score_state.value == "unavailable"
    assert run.result["rare_state_profile"][0]["observed_count"] == 0
    assert run.result["rare_state_profile"][0]["detection_state"] == "cannot_exclude"


def test_projection_maps_calibrated_zero_to_negative_without_absence_claim(
    tmp_path: Path,
) -> None:
    def zero_rare_state(payload: dict) -> None:
        payload["state_observations"] = [
            {"state_id": "state:a", "soft_mass": 9.0, "observed_count": 9},
            {"state_id": "state:b", "soft_mass": 0.0, "observed_count": 0},
        ]

    request = _rewrite(
        _with_measurement_spec(_request(tmp_path)),
        "off_target_evidence_bundle",
        zero_rare_state,
    )
    request = _projection_request(request)

    run = adapter.run(request, _projection_spec())
    rare = _projected_measurement(run, "rare_state", "state:b")

    assert rare.evidence_state.value == "negative"
    assert rare.raw_value["detection_state"] == "not_detected_above_lod"
    assert rare.raw_value["observed_count"] == 0
    assert "zero_observation_does_not_establish_absence" in rare.raw_value[
        "reason_codes"
    ]


def test_projection_maps_missing_rare_observation_to_unavailable(
    tmp_path: Path,
) -> None:
    def remove_rare_row(payload: dict) -> None:
        payload["composition_coverage_state"] = "partial"
        payload["unknown_coverage_state"] = "not_assessed"
        payload["state_observations"] = payload["state_observations"][:1]

    request = _rewrite(
        _with_measurement_spec(_request(tmp_path)),
        "off_target_evidence_bundle",
        remove_rare_row,
    )
    request = _projection_request(request)
    run = adapter.run(request, _projection_spec())
    rare = _projected_measurement(run, "rare_state", "state:b")

    assert rare.evidence_state.value == "unavailable"
    assert rare.raw_value is None
    assert rare.numerator is None
    assert rare.denominator is None
    unknown = _projected_measurement(run, "identity_unknown", "identity-unknown")
    assert unknown.evidence_state.value == "unavailable"
    assert unknown.raw_value is None
    assert run.result["rare_state_profile"][0]["observed_count"] is None
    assert run.result["rare_state_profile"][0]["reason_codes"] == [
        "rare_state_observation_missing"
    ]


def test_product_figure_discloses_soft_mass_denominator(
    tmp_path: Path,
) -> None:
    def unequal_soft_mass(payload: dict) -> None:
        payload["denominator"]["total_soft_mass"] = 8.0
        payload["state_observations"][0]["soft_mass"] = 5.0

    request = _rewrite(
        _request(tmp_path), "off_target_evidence_bundle", unequal_soft_mass
    )
    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    visual = next(
        item
        for item in run.artifacts
        if item.kind == "off_target_control_visualization_data"
    )
    payload = json.loads(visual.path.read_text(encoding="utf-8"))
    target = next(
        item for item in payload["product_records"] if item["category"] == "target"
    )
    assert target["fraction"] == pytest.approx(5.0 / 8.0)
    svg = next(
        item
        for item in run.artifacts
        if item.path.name == "off_target_control_product-accounting.svg"
    ).path.read_text(encoding="utf-8")
    assert "Cell count n=10" in svg
    assert "total soft-assignment mass=8.00 (percentage denominator)" in svg
    artifact_set = next(
        item
        for item in run.artifacts
        if item.kind == "visualization_artifact_set"
    )
    typed_set = P005VisualizationArtifactSet.model_validate_json(
        artifact_set.path.read_text(encoding="utf-8")
    )
    product_figure = next(
        item
        for item in typed_set.visualizations
        if item.component_id == "bridge.off-target-control.product-accounting"
    )
    assert "total soft-assignment mass=8" in product_figure.denominator_label


def test_role_mapping_is_external_not_inferred_from_state_name(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)

    def move_role(payload: dict) -> None:
        payload["assignments"][1]["product_role"] = "acceptable_adjacent"

    request = _rewrite(request, "state_role_map", move_role)
    map_sha = next(
        ref.sha256 for ref in request.object_inputs
        if ref.role == "state_role_map"
    )
    request = _rewrite(
        request,
        "off_target_assessment_spec",
        lambda payload: payload.update({"state_role_map_sha256": map_sha}),
    )
    run = registry.run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert _role(run.result, "acceptable_adjacent")["fraction"] == pytest.approx(
        0.2
    )
    assert _role(run.result, "known_off_target")["fraction"] == 0.0


def test_partial_coverage_withholds_fractions(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)
    request = _rewrite(
        request,
        "off_target_evidence_bundle",
        lambda payload: payload.update(
            {
                "composition_coverage_state": "partial",
                "unknown_coverage_state": "partial",
                "state_observations": [
                    {"state_id": "state:a", "soft_mass": 7.0, "observed_count": 7},
                    {"state_id": "state:b", "soft_mass": 0.0, "observed_count": 0},
                ],
            }
        ),
    )

    run = registry.run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert all(
        item["fraction"] is None
        and item["assessment_state"] == "not_assessed"
        for item in run.result["role_composition"]
    )
    assert run.result["unknown_profile"]["fraction"] is None
    assert "composition_coverage_not_complete" in run.result["reason_codes"]
    assert run.result["rare_state_profile"][0]["detection_state"] == (
        "cannot_exclude"
    )
    visual = next(
        item
        for item in run.artifacts
        if item.kind == "off_target_control_visualization_data"
    )
    payload = json.loads(visual.path.read_text(encoding="utf-8"))
    assert {
        reason
        for item in payload["unknown_reason_records"]
        for reason in item["reason_codes"]
    } == {"identity_unknown_coverage_not_complete"}


def test_not_assessed_coverage_is_preserved_in_visualization(
    tmp_path: Path,
) -> None:
    request = _rewrite(
        _request(tmp_path),
        "off_target_evidence_bundle",
        lambda payload: payload.update(
            {
                "composition_coverage_state": "not_assessed",
                "unknown_coverage_state": "not_assessed",
            }
        ),
    )

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    visual = next(
        item
        for item in run.artifacts
        if item.kind == "off_target_control_visualization_data"
    )
    payload = json.loads(visual.path.read_text(encoding="utf-8"))
    assert payload["composition_coverage_state"] == "not_assessed"
    assert payload["unknown_coverage_state"] == "not_assessed"
    assert payload["product_component_applicability"] == "not_assessed"
    assert payload["product_component_state"] == "unavailable"
    assert all(item["fraction"] is None for item in payload["product_records"])


def test_empty_upstream_evidence_ids_fail_before_visualization(
    tmp_path: Path,
) -> None:
    request = _rewrite(
        _request(tmp_path),
        "cell_state_evidence_profile",
        lambda payload: payload.update({"evidence_ids": []}),
    )
    profile_sha = next(
        item.sha256
        for item in request.object_inputs
        if item.role == "cell_state_evidence_profile"
    )
    request = _rewrite(
        request,
        "off_target_evidence_bundle",
        lambda payload: payload.update({"cell_state_profile_sha256": profile_sha}),
    )

    registry = ToolRegistry.load_default()
    eligibility = registry.check_eligibility(request)
    run = registry.run(request)

    assert not eligibility.eligible
    assert eligibility.reason_codes == [
        "cell_state_evidence_ids_required_for_visualization"
    ]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == eligibility.reason_codes


def test_invalid_upstream_evidence_id_fails_before_visualization(
    tmp_path: Path,
) -> None:
    request = _rewrite(
        _request(tmp_path),
        "cell_state_evidence_profile",
        lambda payload: payload.update({"evidence_ids": ["evidence/one"]}),
    )
    profile_sha = next(
        item.sha256
        for item in request.object_inputs
        if item.role == "cell_state_evidence_profile"
    )
    request = _rewrite(
        request,
        "off_target_evidence_bundle",
        lambda payload: payload.update({"cell_state_profile_sha256": profile_sha}),
    )

    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert not eligibility.eligible
    assert eligibility.reason_codes == [
        "cell_state_evidence_ids_invalid_for_visualization"
    ]


def test_rare_state_reason_does_not_pollute_product_component(
    tmp_path: Path,
) -> None:
    request = _rewrite(
        _request(tmp_path),
        "off_target_evidence_bundle",
        lambda payload: payload.update({"rare_state_calibrations": []}),
    )
    run = ToolRegistry.load_default().run(request)
    visual = next(
        item
        for item in run.artifacts
        if item.kind == "off_target_control_visualization_data"
    )
    payload = json.loads(visual.path.read_text(encoding="utf-8"))

    assert "rare_state_calibration_missing" in payload["rare_component_reason_codes"]
    assert "rare_state_calibration_missing" not in payload["product_component_reason_codes"]


def test_complete_product_coverage_cannot_hide_fraction(
    tmp_path: Path,
) -> None:
    run = ToolRegistry.load_default().run(_request(tmp_path))
    visual = next(
        item
        for item in run.artifacts
        if item.kind == "off_target_control_visualization_data"
    )
    payload = json.loads(visual.path.read_text(encoding="utf-8"))
    payload["product_records"][0].update(
        {"assessment_state": "not_assessed", "fraction": None}
    )

    with pytest.raises(
        ValueError,
        match="product assessment state must match coverage state",
    ):
        OffTargetControlVisualizationDataV1.model_validate(payload)


def test_zero_observation_is_cannot_exclude_not_absent(
    tmp_path: Path,
) -> None:
    run = ToolRegistry.load_default().run(_request(tmp_path))

    unresolved = _role(run.result, "role_unresolved")
    assert unresolved["observed_count"] == 0
    assert unresolved["exclusion_state"] == "cannot_exclude"
    assert "zero_observation_does_not_establish_absence" in (
        run.result["reason_codes"]
    )


def test_unknown_reason_must_be_declared_by_external_spec(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)
    request = _rewrite(
        request,
        "off_target_evidence_bundle",
        lambda payload: payload["unknown_observations"][0].update(
            {"reason_id": "caller_specific_reason"}
        ),
    )

    eligibility = registry.check_eligibility(request)

    assert not eligibility.eligible
    assert "unknown_reason_not_allowed" in eligibility.reason_codes


@pytest.mark.parametrize(
    ("bundle_mutation", "expected_state", "expected_reason"),
    [
        (
            lambda payload: payload.update({"rare_state_calibrations": []}),
            "cannot_exclude",
            "rare_state_calibration_missing",
        ),
        (
            lambda payload: payload["rare_state_calibrations"][0].update(
                {"validated_detection_limit_fraction": 0.2}
            ),
            "cannot_exclude",
            "rare_state_calibration_outside_spec",
        ),
    ],
)
def test_rare_state_calibration_fails_closed(
    tmp_path: Path,
    bundle_mutation: Callable[[dict], None],
    expected_state: str,
    expected_reason: str,
) -> None:
    request = _rewrite(
        _request(tmp_path),
        "off_target_evidence_bundle",
        bundle_mutation,
    )

    run = ToolRegistry.load_default().run(request)
    record = run.result["rare_state_profile"][0]

    assert record["detection_state"] == expected_state
    assert expected_reason in record["reason_codes"]


def test_calibrated_zero_is_not_detected_above_lod_with_upper_bound(
    tmp_path: Path,
) -> None:
    def zero_rare_state(payload: dict) -> None:
        payload["state_observations"] = [
            {"state_id": "state:a", "soft_mass": 9.0, "observed_count": 9},
            {"state_id": "state:b", "soft_mass": 0.0, "observed_count": 0},
        ]

    request = _rewrite(
        _request(tmp_path), "off_target_evidence_bundle", zero_rare_state
    )
    run = ToolRegistry.load_default().run(request)
    record = run.result["rare_state_profile"][0]

    assert record["detection_state"] == "not_detected_above_lod"
    assert record["zero_observation_upper_bound_fraction"] == pytest.approx(0.03)
    assert "zero_observation_does_not_establish_absence" in (
        record["reason_codes"]
    )


def test_missing_rare_observation_is_not_assessed(tmp_path: Path) -> None:
    def remove_rare_row(payload: dict) -> None:
        payload["composition_coverage_state"] = "partial"
        payload["state_observations"] = payload["state_observations"][:1]

    request = _rewrite(
        _request(tmp_path), "off_target_evidence_bundle", remove_rare_row
    )
    run = ToolRegistry.load_default().run(request)
    record = run.result["rare_state_profile"][0]

    assert record["detection_state"] == "not_assessed"
    assert record["observed_count"] is None
    assert record["reason_codes"] == ["rare_state_observation_missing"]
    visual = next(
        item
        for item in run.artifacts
        if item.kind == "off_target_control_visualization_data"
    )
    payload = json.loads(visual.path.read_text(encoding="utf-8"))
    visual_record = payload["rare_state_records"][0]
    assert visual_record["observed_count"] is None
    assert visual_record["count_fraction"] is None
    svg = next(
        item
        for item in run.artifacts
        if item.path.name == "off_target_control_rare-state-detectability.svg"
    )
    svg_text = svg.path.read_text(encoding="utf-8")
    assert "not assessed" in svg_text
    assert "0/10" not in svg_text


@pytest.mark.parametrize(
    ("role", "mutate", "reason"),
    [
        (
            "product_case",
            lambda payload: payload["product_definition_ref"].update(
                {"object_id": "product-definition:other"}
            ),
            "product_definition_binding_mismatch",
        ),
        (
            "cell_state_evidence_profile",
            lambda payload: payload.update({"assay": "snRNA-seq"}),
            "cell_state_assay_binding_mismatch",
        ),
        (
            "off_target_assessment_spec",
            lambda payload: payload.update({"active": False}),
            "off_target_assessment_spec_inactive",
        ),
        (
            "off_target_evidence_bundle",
            lambda payload: payload["denominator"].update(
                {"denominator_id": "other-denominator"}
            ),
            "primary_denominator_binding_mismatch",
        ),
    ],
)
def test_cross_object_binding_failures_are_typed(
    tmp_path: Path,
    role: str,
    mutate: Callable[[dict], None],
    reason: str,
) -> None:
    request = _rewrite(_request(tmp_path), role, mutate)

    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert not eligibility.eligible
    assert reason in eligibility.reason_codes


def test_unmapped_state_fails_closed(tmp_path: Path) -> None:
    def add_unmapped(payload: dict) -> None:
        payload["state_observations"].append(
            {"state_id": "state:unmapped", "soft_mass": 0.0, "observed_count": 0}
        )

    request = _rewrite(
        _request(tmp_path), "off_target_evidence_bundle", add_unmapped
    )
    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert not eligibility.eligible
    assert "evidence_bundle_contains_unmapped_state" in eligibility.reason_codes


def test_checksum_mismatch_fails_before_execution(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)
    ref = next(
        item for item in request.object_inputs if item.role == "state_role_map"
    )
    ref.path.write_text(ref.path.read_text() + " ")

    eligibility = registry.check_eligibility(request)

    assert not eligibility.eligible
    assert eligibility.reason_codes == ["structured_input_checksum_mismatch"]


def test_v1_request_receives_typed_refusal(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    spec = registry.describe("P0-05")
    request = ToolRequest(
        request_id="legacy-request",
        tool_id="P0-05",
        output_dir=tmp_path / "output",
    )

    run = adapter.run(request, spec)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["tool_request_v2_required"]
    assert run.result is None


def test_identical_input_reuses_output_and_tamper_fails_closed(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)

    first = registry.run(request)
    second = registry.run(request)
    assert first.run_id == second.run_id
    assert first.artifacts[0].sha256 == second.artifacts[0].sha256

    first.artifacts[0].path.write_text("{}\n")
    third = registry.run(request)

    assert third.execution_state is ExecutionState.FAILED
    assert third.reason_codes == ["existing_run_bundle_hash_mismatch"]
