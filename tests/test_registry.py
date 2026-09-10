from __future__ import annotations

import re
from importlib import import_module
from pathlib import Path

from bridge.toolkit.contracts import ImplementationState, ToolRequest
from bridge.toolkit.registry import ToolRegistry
from bridge.toolkit.schemas import SCHEMA_REFS, load_schema

EXPECTED_IDS = [f"P0-{index:02d}" for index in range(1, 13)]


def test_registry_discovers_exactly_twelve_tool_packages() -> None:
    registry = ToolRegistry.load_default()
    proliferation_stress_response = registry.describe("P0-06")
    product_comparison = registry.describe("P0-07")

    assert registry.ids() == EXPECTED_IDS
    assert registry.describe("P0-01").implementation_state is ImplementationState.IMPLEMENTED
    assert registry.describe("P0-02").implementation_state is ImplementationState.IMPLEMENTED
    assert registry.describe("P0-04").implementation_state is ImplementationState.IMPLEMENTED
    assert registry.describe("P0-03").implementation_state is ImplementationState.IMPLEMENTED
    assert registry.describe("P0-05").implementation_state is ImplementationState.IMPLEMENTED
    assert registry.describe("P0-06").implementation_state is ImplementationState.IMPLEMENTED
    assert registry.describe("P0-07").implementation_state is ImplementationState.IMPLEMENTED
    assert registry.describe("P0-08").implementation_state is ImplementationState.IMPLEMENTED
    assert registry.describe("P0-09").implementation_state is ImplementationState.IMPLEMENTED
    assert registry.describe("P0-10").implementation_state is ImplementationState.IMPLEMENTED
    assert registry.describe("P0-11").implementation_state is ImplementationState.IMPLEMENTED
    assert registry.describe("P0-12").implementation_state is ImplementationState.IMPLEMENTED
    assert proliferation_stress_response.name == "Proliferation & Stress Response"
    assert proliferation_stress_response.version == "0.8.1"
    assert product_comparison.version == "0.4.1"


def test_declared_tool_version_must_match_registry(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    request = ToolRequest(
        request_id="request-version-mismatch",
        tool_id="P0-01",
        tool_version="9.9.9",
        output_dir=tmp_path,
    )

    eligibility = registry.check_eligibility(request)

    assert eligibility.eligible is False
    assert eligibility.reason_codes == ["tool_version_mismatch"]



def test_every_tool_package_has_resolvable_contract_files() -> None:
    registry = ToolRegistry.load_default()

    for spec in registry.list():
        assert spec.card_ref.startswith("bridge://tool-cards/")
        assert registry.read_card(spec.tool_id).startswith(f"# {spec.tool_id}")
        assert spec.environment_spec_id
        assert registry.resolve_schema(spec.input_schema_ref)["title"]
        assert registry.resolve_schema(spec.output_schema_ref)["title"]
        if spec.implementation_state is ImplementationState.IMPLEMENTED:
            assert spec.method_ids
        else:
            assert spec.method_ids == []


def test_public_registry_payload_contains_no_absolute_paths() -> None:
    registry = ToolRegistry.load_default()

    payload = [spec.model_dump_json() for spec in registry.list()]

    serialized = "".join(payload)
    private_mount = re.compile(r"/(?:data[0-9]+|mnt|srv)/")
    assert private_mount.search(serialized) is None
    assert "/Users/" not in serialized


def test_every_tool_exposes_a_resolvable_input_contract() -> None:
    registry = ToolRegistry.load_default()

    for spec in registry.list():
        contract = registry.describe_input(spec.tool_id)
        assert contract.tool_id == spec.tool_id
        assert contract.request_schema_ref == spec.input_schema_ref
        for mode in contract.object_input_modes:
            for role in mode.roles:
                assert set(role.schema_refs).issubset(SCHEMA_REFS)

    assert registry.describe_input("P0-01").asset_input.max_count == 1
    assert len(registry.describe_input("P0-03").object_input_modes[0].roles) == 12
    p009_modes = registry.describe_input("P0-09").object_input_modes
    assert [mode.mode_id for mode in p009_modes] == [
        "case_initial",
        "case_append",
        "comparison_initial",
        "comparison_append",
        "case_initial_v2",
        "case_append_v2",
        "comparison_initial_v2",
        "comparison_append_v2",
        "case_query",
        "comparison_query",
    ]
    legacy_profile = next(
        role
        for role in p009_modes[0].roles
        if role.role == "evidence_sufficiency_profile"
    )
    assert legacy_profile.schema_refs == [
        "bridge://schemas/evidence-sufficiency-profile/v0.1",
        "bridge://schemas/evidence-sufficiency-profile/v0.2",
    ]
    assert legacy_profile.object_versions == ["0.1.0", "0.2.0"]
    canonical_run = next(
        role
        for role in p009_modes[4].roles
        if role.role == "evidence_sufficiency_run_result"
    )
    assert canonical_run.schema_refs == [
        "bridge://schemas/evidence-sufficiency-run-result/v0.2"
    ]
    assert (canonical_run.min_count, canonical_run.max_count) == (1, 1)
    for mode in (p009_modes[1], p009_modes[5]):
        base_manifest = next(
            role for role in mode.roles if role.role == "base_graph_manifest"
        )
        assert base_manifest.schema_refs == [
            "bridge://schemas/case-evidence-graph-manifest/v0.1"
        ]
    for mode in (p009_modes[3], p009_modes[7]):
        base_manifest = next(
            role for role in mode.roles if role.role == "base_graph_manifest"
        )
        assert base_manifest.schema_refs == [
            "bridge://schemas/comparison-evidence-graph-manifest/v0.1"
        ]
    assert [mode.mode_id for mode in registry.describe_input("P0-12").object_input_modes] == [
        "not_provided",
        "graft_assessment",
        "expression_analysis",
    ]


def test_p005_discovery_exposes_count_only_inputs_without_mass_bundle() -> None:
    registry = ToolRegistry.load_default()
    modes = {mode.mode_id: mode for mode in registry.describe_input("P0-05").object_input_modes}
    assert "hard_count_accounting" in modes
    roles = {role.role: role for role in modes["hard_count_accounting"].roles}
    assert set(roles) == {
        "product_case", "product_definition_card", "state_role_map",
        "off_target_assessment_spec", "cell_state_evidence_profile",
        "biological_unit_manifest", "biological_unit_attestation_receipt", "measurement_spec",
    }
    assert roles["cell_state_evidence_profile"].schema_refs == ["bridge://schemas/cell-state-evidence-profile/v0.3"]
    assert roles["cell_state_evidence_profile"].object_versions == ["0.3.0"]
    assert roles["measurement_spec"].min_count == 0
    assert all(role.max_count == 1 for role in roles.values())
    assert all(role.min_count == 1 for name, role in roles.items() if name != "measurement_spec")
    assert {"legacy_aggregation", "method_runtime"} <= set(modes)


def test_p006_discovery_selects_source_bound_input_without_changing_legacy_mode() -> None:
    registry = ToolRegistry.load_default()
    modes = {mode.mode_id: mode for mode in registry.describe_input("P0-06").object_input_modes}
    assert "method_runtime_source_bound" in modes
    source = modes["method_runtime_source_bound"]
    legacy = modes["method_runtime"]
    source_roles = {role.role: role for role in source.roles}
    legacy_roles = {role.role: role for role in legacy.roles}
    assert len(source_roles) == 12
    assert set(source_roles) == set(legacy_roles)
    assert source.asset_input == legacy.asset_input
    assert source_roles["process_method_input"].schema_refs == ["bridge://schemas/process-method-input/v0.2"]
    assert source_roles["process_method_input"].object_versions == ["0.2.0"]
    assert legacy_roles["process_method_input"].schema_refs == ["bridge://schemas/process-method-input/v0.1"]
    for role in source_roles.keys() - {"process_method_input"}:
        assert source_roles[role] == legacy_roles[role]


def test_input_contract_roles_match_runtime_adapters() -> None:
    modules = {
        "P0-03": "bridge.tool_packages.p0_03_target_regional.adapter",
        "P0-04": "bridge.tool_packages.p0_04_developmental_compatibility.adapter",
        "P0-05": "bridge.tool_packages.p0_05_off_target_control.adapter",
        "P0-06": "bridge.tool_packages.p0_06_proliferation_stress_response.adapter",
        "P0-07": "bridge.tool_packages.p0_07_product_comparison_stability.adapter",
        "P0-08": "bridge.tool_packages.p0_08_evidence_sufficiency.adapter",
        "P0-09": "bridge.tool_packages.p0_09_evidence_compiler.adapter",
        "P0-10": "bridge.tool_packages.p0_10_claim_verifier.adapter",
        "P0-11": "bridge.tool_packages.p0_11_public_safe_export.adapter",
        "P0-12": "bridge.tool_packages.p0_12_graft_assessment.adapter",
    }
    registry = ToolRegistry.load_default()

    for tool_id, module_name in modules.items():
        module = import_module(module_name)
        runtime_contract = getattr(module, "ROLE_SCHEMAS", None)
        if runtime_contract is None:
            runtime_contract = getattr(
                module, "ROLE_MODELS", getattr(module, "ROLE_CONTRACTS", {})
            )
        declared_roles = {
            role.role
            for mode in registry.describe_input(tool_id).object_input_modes
            for role in mode.roles
        }
        runtime_roles = set(runtime_contract)
        if tool_id == "P0-09":
            # Compilation and read-only query dispatch have separate loaders.
            query_runtime = import_module(
                "bridge.tool_packages.p0_09_evidence_compiler.query_runtime"
            )
            runtime_roles.update(query_runtime.QUERY_ROLES)
        assert declared_roles == runtime_roles


def test_shared_product_context_imports_remain_compatible() -> None:
    from bridge.tool_packages._configurable_contracts import (
        DevelopmentWindowSpec as SharedDevelopmentWindowSpec,
    )
    from bridge.tool_packages._configurable_contracts import (
        StateRoleMap as SharedStateRoleMap,
    )
    from bridge.tool_packages.p0_04_developmental_compatibility.models import (
        DevelopmentWindowSpec,
    )
    from bridge.tool_packages.p0_05_off_target_control.models import StateRoleMap

    assert DevelopmentWindowSpec is SharedDevelopmentWindowSpec
    assert StateRoleMap is SharedStateRoleMap



def test_all_public_contract_schemas_are_packaged_and_versioned() -> None:
    assert {
        "bridge://schemas/claim-verifier-run-result/v0.1",
        "bridge://schemas/verified-report/v0.1",
    }.isdisjoint(SCHEMA_REFS)
    for schema_ref in SCHEMA_REFS:
        schema = load_schema(schema_ref)
        assert schema["$id"] == schema_ref
        assert schema["title"]
