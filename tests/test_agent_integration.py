from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from jsonschema import Draft202012Validator
import pytest
from pydantic import ValidationError

from bridge.toolkit import (
    AgentIntegrationProfile,
    ToolRequest,
    ToolRequestV2,
    run_tool,
)
from bridge.toolkit.contracts import InputAsset
from bridge.toolkit.integration import (
    validate_agent_integration_profile,
    validate_profile_request,
)
from bridge.toolkit.schemas import load_schema


REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_ROOT = REPO_ROOT / "examples" / "agent-integration" / "profiles"
PROFILE_FILES = {
    "single-product": PROFILE_ROOT / "single-product.json",
    "comparison": PROFILE_ROOT / "comparison.json",
    "graft": PROFILE_ROOT / "graft.json",
}


def _load_profile(name: str) -> AgentIntegrationProfile:
    return AgentIntegrationProfile.model_validate_json(
        PROFILE_FILES[name].read_text(encoding="utf-8")
    )


def _no_graft_profile_payload() -> dict[str, Any]:
    return {
        "profile_id": "graft-control",
        "object_version": "0.1.0",
        "schema_ref": "bridge://schemas/agent-integration-profile/v0.1",
        "resource_slots": [],
        "request_bindings": [
            {
                "binding_id": "graft-not-provided",
                "tool_id": "P0-12",
                "tool_version": "0.4.0",
                "request_schema_ref": "bridge://schemas/tool-request/v0.2",
                "mode_id": "not_provided",
                "asset_slot_ids": [],
                "object_inputs": [],
                "measurement_spec_slot_id": None,
            }
        ],
    }


@pytest.mark.parametrize("name", sorted(PROFILE_FILES))
def test_published_profiles_validate_against_live_tool_contracts(name: str) -> None:
    profile = _load_profile(name)

    assert validate_agent_integration_profile(profile) is profile


def test_published_profiles_cover_the_three_declared_workflows() -> None:
    single = _load_profile("single-product")
    comparison = _load_profile("comparison")
    graft = _load_profile("graft")

    assert {binding.tool_id for binding in single.request_bindings} == {
        "P0-01",
        "P0-02",
        "P0-03",
        "P0-04",
        "P0-05",
        "P0-06",
        "P0-08",
        "P0-09",
        "P0-10",
        "P0-11",
    }
    assert [binding.tool_id for binding in comparison.request_bindings] == ["P0-07"]
    comparison_binding = comparison.request_bindings[0]
    assert comparison_binding.mode_id == "method_runtime"
    assert {item.role for item in comparison_binding.object_inputs} == {
        "comparison_stability_spec",
        "comparison_case_manifest",
        "product_evidence_bundle",
        "comparison_method_spec",
        "comparison_method_input",
    }
    comparison_slots = {slot.slot_id: slot for slot in comparison.resource_slots}
    assert comparison_slots["comparison-method-spec"].source == "system_resource"
    method_input = comparison_slots["comparison-method-input"]
    assert method_input.source == "agent_constructed"
    assert set(method_input.depends_on_slots) == {
        "comparison-case-manifest",
        "product-a-evidence",
        "product-b-evidence",
    }
    assert [binding.mode_id for binding in graft.request_bindings] == [
        "not_provided",
        "expression_analysis",
    ]


def test_single_product_profile_declares_top_level_measurement_specs() -> None:
    profile = _load_profile("single-product")
    bindings = {item.tool_id: item for item in profile.request_bindings}

    assert bindings["P0-01"].measurement_spec_slot_id == "qc-measurement-spec"
    assert bindings["P0-02"].measurement_spec_slot_id == "cell-state-measurement-spec"
    assert bindings["P0-03"].measurement_spec_slot_id is None


def test_expression_asset_bindings_include_method_specs() -> None:
    profile = _load_profile("single-product")
    slots = {item.slot_id: item for item in profile.resource_slots}
    bindings = {item.tool_id: item for item in profile.request_bindings}

    assert slots["target-regional-method-spec"].source == "system_resource"
    assert (
        slots["target-regional-method-spec"].schema_ref
        == "bridge://schemas/target-regional-method-spec/v0.1"
    )
    assert slots["target-regional-method-spec"].object_version == "0.1.0"
    assert {item.role: item.slot_id for item in bindings["P0-03"].object_inputs}[
        "target_regional_method_spec"
    ] == "target-regional-method-spec"

    assert slots["development-method-spec"].source == "system_resource"
    assert (
        slots["development-method-spec"].schema_ref
        == "bridge://schemas/development-method-spec/v0.1"
    )
    assert slots["development-method-spec"].object_version == "0.1.0"
    assert {item.role: item.slot_id for item in bindings["P0-04"].object_inputs}[
        "development_method_spec"
    ] == "development-method-spec"


def test_domain_gate_inputs_depend_on_case_and_product_definition() -> None:
    profile = _load_profile("single-product")
    gate_slots = [
        slot for slot in profile.resource_slots if slot.slot_id.endswith("-domain-gate")
    ]

    assert {slot.slot_id for slot in gate_slots} == {
        "target-domain-gate",
        "regional-domain-gate",
        "development-domain-gate",
        "off-target-domain-gate",
        "process-domain-gate",
    }
    for slot in gate_slots:
        assert {"product-case", "product-definition-card"}.issubset(
            slot.depends_on_slots
        )


def test_single_product_profile_routes_actual_upstream_artifacts() -> None:
    profile = _load_profile("single-product")
    slots = {slot.slot_id: slot for slot in profile.resource_slots}

    upload = slots["uploaded-expression"]
    assert set(upload.asset_contract.required_metadata_keys) == {
        "biological_unit_lineage",
        "source_family_id",
    }
    selected = slots["qc-selected-expression"]
    assert selected.source == "agent_constructed"
    assert set(selected.depends_on_slots) == {
        "qc-readiness-profile",
        "uploaded-expression",
    }
    assert selected.producer_binding_id is None
    assert selected.artifact_kind is None

    profile_v3 = slots["cell-state-profile"]
    assert profile_v3.producer_binding_id == "cell-state-evidence"
    assert profile_v3.artifact_kind == "cell_state_profile_v3"
    annotation = slots["annotation-vocabulary"]
    assert annotation.schema_ref == "bridge://schemas/annotation-vocabulary/v0.1"
    assert annotation.object_version == "0.1.0"
    reference = slots["reference-manifest"]
    assert reference.schema_ref == "bridge://schemas/reference-manifest/v0.1"
    assert reference.object_version == "0.2.0"

    observation_evidence = slots["cell-state-observation-evidence"]
    assert observation_evidence.source == "derived_output"
    assert observation_evidence.resource_type == "asset"
    assert observation_evidence.asset_contract.format == "parquet"
    assert observation_evidence.producer_binding_id == "cell-state-evidence"
    assert observation_evidence.artifact_kind == "cell_state_evidence"
    record_set = slots["evidence-record-set"]
    assert record_set.schema_ref == "bridge://schemas/evidence-record-set/v0.1"
    assert record_set.producer_binding_id == "evidence-compiler"
    assert record_set.artifact_kind == "evidence_records"

    sufficiency = slots["sufficiency-result"]
    assert sufficiency.producer_binding_id == "evidence-sufficiency"
    assert sufficiency.artifact_kind == "evidence_sufficiency_run_result"
    claim = slots["claim-verification-result"]
    assert claim.producer_binding_id == "claim-verifier"
    assert claim.artifact_kind == "claim_verification_result"


def test_single_product_agent_objects_declare_complete_direct_dependencies() -> None:
    profile = _load_profile("single-product")
    dependencies = {
        slot.slot_id: set(slot.depends_on_slots)
        for slot in profile.resource_slots
        if slot.source == "agent_constructed"
    }

    assert dependencies["product-case"] == {
        "biological-unit-manifest",
        "cell-state-measurement-spec",
        "product-definition-card",
        "qc-readiness-profile",
        "uploaded-expression",
    }
    assert dependencies["off-target-evidence"] == {
        "cell-state-profile",
        "product-case",
        "product-definition-card",
    }
    assert dependencies["off-target-method-input"] == {
        "biological-unit-assignment",
        "biological-unit-manifest",
        "cell-state-observation-evidence",
        "cell-state-profile",
        "off-target-assessment-spec",
        "off-target-evidence",
        "off-target-method-spec",
        "product-case",
        "state-role-map",
    }
    assert dependencies["protocol-ir"] == {
        "product-case",
        "uploaded-expression",
    }
    assert dependencies["process-method-input"] == {
        "biological-unit-assignment",
        "biological-unit-manifest",
        "cell-state-observation-evidence",
        "cell-state-profile",
        "process-program-spec",
        "product-case",
        "qc-selected-expression",
    }
    assert dependencies["compilation-bundle"] == {
        "claim-registry",
        "development-measurement-spec",
        "development-measurements",
        "evidence-family-registry",
        "off-target-measurement-spec",
        "off-target-measurements",
        "process-measurement-spec",
        "process-measurements",
        "product-case",
        "reconciliation-registry",
        "sufficiency-result",
        "target-measurement-spec",
        "target-measurements",
    }
    assert dependencies["report-draft"] == {
        "evidence-record-set",
        "case-graph-manifest",
        "claim-policy",
        "product-case",
        "statement-registry",
    }
    assert dependencies["public-export-request"] == {
        "claim-verification-result",
        "public-export-policy",
        "report-draft",
    }


def test_graft_case_is_user_supplied_and_expression_asset_binds_it() -> None:
    profile = _load_profile("graft")
    slots = {slot.slot_id: slot for slot in profile.resource_slots}

    graft_case = slots["graft-case"]
    assert graft_case.source == "user_upload"
    assert graft_case.depends_on_slots == []
    expression_asset = slots["graft-expression-asset"]
    assert expression_asset.source == "agent_constructed"
    assert set(expression_asset.depends_on_slots) == {
        "graft-case",
        "graft-expression-upload",
    }


def test_profile_rejects_duplicate_slot_ids() -> None:
    payload = _no_graft_profile_payload()
    slot = {
        "slot_id": "product-case",
        "source": "system_resource",
        "resource_type": "structured_object",
        "schema_ref": "bridge://schemas/product-case/v0.1",
        "object_version": "0.1.0",
        "min_count": 1,
        "max_count": 1,
    }
    payload["resource_slots"] = [slot, deepcopy(slot)]

    with pytest.raises(ValidationError, match="resource slot IDs must be unique"):
        AgentIntegrationProfile.model_validate(payload)


def test_profile_rejects_unknown_slot_references() -> None:
    payload = _no_graft_profile_payload()
    payload["request_bindings"][0]["asset_slot_ids"] = ["missing-upload"]

    with pytest.raises(ValidationError, match="unknown resource slot"):
        AgentIntegrationProfile.model_validate(payload)


def test_profile_rejects_dependency_cycles() -> None:
    payload = _no_graft_profile_payload()
    payload["resource_slots"] = [
        {
            "slot_id": slot_id,
            "source": "agent_constructed",
            "resource_type": "structured_object",
            "schema_ref": "bridge://schemas/product-case/v0.1",
            "object_version": "0.1.0",
            "min_count": 1,
            "max_count": 1,
            "depends_on_slots": [dependency],
        }
        for slot_id, dependency in (("object-a", "object-b"), ("object-b", "object-a"))
    ]

    with pytest.raises(ValidationError, match="dependency graph must be acyclic"):
        AgentIntegrationProfile.model_validate(payload)


def test_profile_shape_cannot_carry_runtime_locations_or_hashes() -> None:
    payload = _no_graft_profile_payload()
    payload["resource_slots"] = [
        {
            "slot_id": "uploaded-expression",
            "source": "user_upload",
            "resource_type": "asset",
            "min_count": 1,
            "max_count": 1,
            "asset_contract": {
                "format": "h5ad",
                "assay": "scRNA-seq",
                "input_level": "analysis_ready",
                "matrix_semantics": "normalized_expression",
            },
            "path": "/private/input.h5ad",
            "sha256": "a" * 64,
        }
    ]

    with pytest.raises(ValidationError, match="extra_forbidden"):
        AgentIntegrationProfile.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("tool_version", "9.9.9", "tool version"),
        ("request_schema_ref", "bridge://schemas/tool-request/v0.1", "request Schema"),
        ("mode_id", "unknown_mode", "input mode"),
    ],
)
def test_dynamic_validation_rejects_registry_contract_drift(
    field: str,
    value: str,
    message: str,
) -> None:
    payload = _no_graft_profile_payload()
    payload["request_bindings"][0][field] = value
    profile = AgentIntegrationProfile.model_validate(payload)

    with pytest.raises(ValueError, match=message):
        validate_agent_integration_profile(profile)


def test_dynamic_validation_requires_p0_02_top_level_measurement_spec() -> None:
    payload = _load_profile("single-product").model_dump(mode="json")
    p002 = next(
        item for item in payload["request_bindings"] if item["tool_id"] == "P0-02"
    )
    p002["measurement_spec_slot_id"] = None
    profile = AgentIntegrationProfile.model_validate(payload)

    with pytest.raises(ValueError, match="measurement_spec_ref is required"):
        validate_agent_integration_profile(profile)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_ref", "bridge://schemas/product-case/v0.1"),
        ("object_version", "1.0.0"),
    ],
)
def test_dynamic_validation_rejects_measurement_spec_contract_drift(
    field: str, value: str
) -> None:
    payload = _load_profile("single-product").model_dump(mode="json")
    slot = next(
        item for item in payload["resource_slots"]
        if item["slot_id"] == "qc-measurement-spec"
    )
    slot[field] = value
    profile = AgentIntegrationProfile.model_validate(payload)

    with pytest.raises(ValueError, match="unsupported measurement Spec Schema or version"):
        validate_agent_integration_profile(profile)


def test_materialized_measurement_ref_is_opaque_but_required(tmp_path: Path) -> None:
    profile = _load_profile("single-product")
    request = ToolRequest(
        request_id="request-qc-profile-binding",
        tool_id="P0-01",
        tool_version="0.1.4",
        output_dir=tmp_path,
        assets=[
            InputAsset(
                asset_id="uploaded-expression",
                path=tmp_path / "input.h5ad",
                format="h5ad",
                input_level="analysis_ready",
                matrix_semantics="normalized_expression",
                assay="scRNA-seq",
                metadata={
                    "source_family_id": "demo-source",
                    "biological_unit_lineage": "declared",
                },
            )
        ],
        measurement_spec_ref="deployment-owned-measurement-id",
    )

    assert validate_profile_request(profile, "input-audit-qc", request) is request


def test_no_graft_request_matches_binding_and_runs(tmp_path: Path) -> None:
    profile = AgentIntegrationProfile.model_validate(_no_graft_profile_payload())
    request = ToolRequestV2(
        request_id="request-no-graft",
        tool_id="P0-12",
        tool_version="0.4.0",
        output_dir=tmp_path,
    )

    assert validate_profile_request(profile, "graft-not-provided", request) is request
    run = run_tool(request)
    assert run.execution_state.value == "succeeded"


def test_materialized_request_fails_closed_when_slots_are_missing(
    tmp_path: Path,
) -> None:
    profile = _load_profile("single-product")
    request = ToolRequestV2(
        request_id="request-missing-slots",
        tool_id="P0-10",
        tool_version="0.4.0",
        output_dir=tmp_path,
    )

    with pytest.raises(ValueError, match="unresolved_input_slot"):
        validate_profile_request(profile, "claim-verifier", request)


def test_public_schema_matches_model_and_accepts_profiles() -> None:
    schema_ref = "bridge://schemas/agent-integration-profile/v0.1"
    schema = load_schema(schema_ref)
    expected = AgentIntegrationProfile.model_json_schema()
    expected["$id"] = schema_ref

    assert schema == expected
    validator = Draft202012Validator(schema)
    for path in PROFILE_FILES.values():
        assert not list(
            validator.iter_errors(json.loads(path.read_text(encoding="utf-8")))
        )


@pytest.mark.parametrize(
    "slot",
    [
        {
            "slot_id": "mixed-asset",
            "source": "user_upload",
            "resource_type": "asset",
            "schema_ref": "bridge://schemas/product-case/v0.1",
            "object_version": "0.1.0",
            "asset_contract": {
                "format": "h5ad",
                "assay": "scRNA-seq",
                "input_level": "analysis_ready",
                "matrix_semantics": "normalized_expression",
            },
        },
        {
            "slot_id": "mixed-object",
            "source": "system_resource",
            "resource_type": "structured_object",
            "schema_ref": "bridge://schemas/product-case/v0.1",
            "object_version": "0.1.0",
            "asset_contract": {
                "format": "h5ad",
                "assay": "scRNA-seq",
                "input_level": "analysis_ready",
                "matrix_semantics": "normalized_expression",
            },
        },
        {
            "slot_id": "incomplete-derived-output",
            "source": "derived_output",
            "resource_type": "structured_object",
            "schema_ref": "bridge://schemas/product-case/v0.1",
            "object_version": "0.1.0",
        },
        {
            "slot_id": "conflicting-agent-object",
            "source": "agent_constructed",
            "resource_type": "structured_object",
            "schema_ref": "bridge://schemas/product-case/v0.1",
            "object_version": "0.1.0",
            "producer_binding_id": "graft-not-provided",
            "artifact_kind": "result",
            "depends_on_slots": [],
        },
        {
            "slot_id": "conflicting-system-object",
            "source": "system_resource",
            "resource_type": "structured_object",
            "schema_ref": "bridge://schemas/product-case/v0.1",
            "object_version": "0.1.0",
            "producer_binding_id": "graft-not-provided",
            "artifact_kind": "result",
        },
    ],
)
def test_public_schema_rejects_resource_shape_conflicts(
    slot: dict[str, Any],
) -> None:
    payload = _no_graft_profile_payload()
    payload["resource_slots"] = [slot]
    validator = Draft202012Validator(
        load_schema("bridge://schemas/agent-integration-profile/v0.1")
    )

    assert not validator.is_valid(payload)


@pytest.mark.parametrize(
    ("slot_id", "field", "value"),
    [
        ("product-definition-card", "schema_ref", "https://example.invalid/schema"),
        ("product-definition-card", "object_version", "invalid version"),
        ("product-case", "depends_on_slots", ["Invalid Slot"]),
    ],
)
def test_public_schema_and_pydantic_reject_invalid_slot_scalars(
    slot_id: str, field: str, value: object
) -> None:
    payload = _load_profile("single-product").model_dump(mode="json")
    slot = next(
        item for item in payload["resource_slots"] if item["slot_id"] == slot_id
    )
    slot[field] = value
    schema = load_schema("bridge://schemas/agent-integration-profile/v0.1")

    assert not Draft202012Validator(schema).is_valid(payload)
    with pytest.raises(ValidationError):
        AgentIntegrationProfile.model_validate(payload)


def test_public_schema_declares_direct_list_uniqueness() -> None:
    schema = load_schema("bridge://schemas/agent-integration-profile/v0.1")
    definitions = schema["$defs"]

    assert (
        definitions["IntegrationAssetContract"]["properties"]["required_metadata_keys"][
            "uniqueItems"
        ]
        is True
    )
    assert (
        definitions["IntegrationResourceSlot"]["properties"]["depends_on_slots"][
            "uniqueItems"
        ]
        is True
    )
    assert (
        definitions["IntegrationRequestBinding"]["properties"]["asset_slot_ids"][
            "uniqueItems"
        ]
        is True
    )
    assert (
        definitions["IntegrationRequestBinding"]["properties"]["object_inputs"][
            "uniqueItems"
        ]
        is True
    )
    assert schema["properties"]["resource_slots"]["uniqueItems"] is True
    assert schema["properties"]["request_bindings"]["uniqueItems"] is True


def test_profile_helpers_are_not_exported_from_toolkit_root() -> None:
    import bridge.toolkit as toolkit

    assert "validate_agent_integration_profile" not in toolkit.__all__
    assert "validate_profile_request" not in toolkit.__all__


def test_reference_runner_validates_profile_and_runs_no_graft(tmp_path: Path) -> None:
    script = REPO_ROOT / "examples" / "agent-integration" / "reference_runner.py"
    profile_path = PROFILE_FILES["graft"]
    validate = subprocess.run(
        [
            sys.executable,
            str(script),
            "validate-profile",
            "--profile",
            str(profile_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert validate.returncode == 0, validate.stderr

    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "request_id": "reference-no-graft",
                "tool_id": "P0-12",
                "tool_version": "0.4.0",
                "output_dir": str(tmp_path / "output"),
            }
        ),
        encoding="utf-8",
    )
    run = subprocess.run(
        [
            sys.executable,
            str(script),
            "run-step",
            "--profile",
            str(profile_path),
            "--binding",
            "graft-not-provided",
            "--request",
            str(request_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    payload = json.loads(run.stdout)
    assert payload["execution_state"] == "succeeded"
    assert payload["request"]["tool_id"] == "P0-12"


def test_reference_runner_reports_an_unresolved_slot(tmp_path: Path) -> None:
    script = REPO_ROOT / "examples" / "agent-integration" / "reference_runner.py"
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "request_id": "reference-missing-inputs",
                "tool_id": "P0-10",
                "tool_version": "0.4.0",
                "output_dir": str(tmp_path / "output"),
            }
        ),
        encoding="utf-8",
    )

    run = subprocess.run(
        [
            sys.executable,
            str(script),
            "run-step",
            "--profile",
            str(PROFILE_FILES["single-product"]),
            "--binding",
            "claim-verifier",
            "--request",
            str(request_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert run.returncode == 3
    payload = json.loads(run.stdout)
    assert payload["error"] == "unresolved_input_slot"
