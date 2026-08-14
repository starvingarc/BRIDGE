from __future__ import annotations

from pathlib import Path

from bridge.toolkit.contracts import ExecutionState, ImplementationState, ToolRequest
from bridge.toolkit.registry import ToolRegistry
from bridge.toolkit.schemas import SCHEMA_REFS, load_schema


EXPECTED_IDS = [f"P0-{index:02d}" for index in range(1, 13)]


def test_registry_discovers_exactly_twelve_tool_packages() -> None:
    registry = ToolRegistry.load_default()
    proliferation_stress_response = registry.describe("P0-06")

    assert registry.ids() == EXPECTED_IDS
    assert registry.describe("P0-01").implementation_state is ImplementationState.IMPLEMENTED
    assert registry.describe("P0-02").implementation_state is ImplementationState.IMPLEMENTED
    assert registry.describe("P0-08").implementation_state is ImplementationState.IMPLEMENTED
    assert registry.describe("P0-09").implementation_state is ImplementationState.IMPLEMENTED
    assert registry.describe("P0-10").implementation_state is ImplementationState.IMPLEMENTED
    assert all(
        registry.describe(tool_id).implementation_state is ImplementationState.SCAFFOLD
        for tool_id in EXPECTED_IDS[2:7] + EXPECTED_IDS[10:]
    )
    assert proliferation_stress_response.name == "Proliferation & Stress Response"
    assert proliferation_stress_response.version == "0.1.1"


def test_scaffold_run_returns_not_implemented_without_measurements(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    request = ToolRequest(
        request_id="request-scaffold",
        tool_id="P0-03",
        output_dir=tmp_path,
    )

    run = registry.run(request)

    assert run.execution_state is ExecutionState.NOT_IMPLEMENTED
    assert run.measurements == []
    assert run.artifacts == []
    assert run.reason_codes == ["tool_package_not_implemented"]


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


def test_scaffold_run_rejects_declared_version_mismatch(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    request = ToolRequest(
        request_id="request-scaffold-version-mismatch",
        tool_id="P0-03",
        tool_version="9.9.9",
        output_dir=tmp_path,
    )

    run = registry.run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.measurements == []
    assert run.reason_codes == ["tool_version_mismatch"]


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

    assert "/data1/" not in "".join(payload)
    assert "/data2/" not in "".join(payload)
    assert "/Users/" not in "".join(payload)


def test_all_public_contract_schemas_are_packaged_and_versioned() -> None:
    assert len(SCHEMA_REFS) == 56
    for schema_ref in SCHEMA_REFS:
        schema = load_schema(schema_ref)
        assert schema["$id"] == schema_ref
        assert schema["title"]
