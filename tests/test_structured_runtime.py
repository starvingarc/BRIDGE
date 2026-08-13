from __future__ import annotations

import hashlib
import importlib
from importlib.machinery import ModuleSpec
import json
from pathlib import Path
import sys
from types import ModuleType

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from bridge.toolkit import api
from bridge.toolkit.cli import main as cli_main
from bridge.toolkit.contracts import (
    EligibilityResult,
    ExecutionState,
    ImplementationState,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
    ToolRunV2,
)
from bridge.toolkit.registry import ToolRegistry
from bridge.toolkit.schemas import load_schema


RESULT_SCHEMA_REF = "bridge://schemas/eligibility-result/v0.1"
V1_SCHEMA_SHA256 = {
    "tool_package_spec.schema.json": (
        "5f65ecd5c26134c7425426bcfd57447a5199c4a9c9924aa1e2c6018e9f9deefd"
    ),
    "tool_request.schema.json": "83d8219f5fb489879c51d05b12cba8f3cefda5cb8d53e8f8e86e37cebdf52084",
    "tool_run.schema.json": "9a40726dd6c9ec5f2e0ddf6ad3024ca3264bb6f3a04940d34bed4477036dc338",
}


class SyntheticAdapter:
    def __init__(self) -> None:
        self.result_schema_ref = RESULT_SCHEMA_REF
        self.tool_version = "0.2.0"

    def check_eligibility(
        self, request: ToolRequestV2, spec: ToolPackageSpecV2
    ) -> EligibilityResult:
        return EligibilityResult(tool_id=request.tool_id, eligible=True)

    def run(self, request: ToolRequestV2, spec: ToolPackageSpecV2) -> ToolRunV2:
        return ToolRunV2(
            run_id="run-synthetic",
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=ExecutionState.SUCCEEDED,
            tool_version=self.tool_version,
            environment_spec_id=spec.environment_spec_id,
            result_schema_ref=self.result_schema_ref,
            result={"synthetic": True},
        )


def _structured_input(tmp_path: Path, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "input_id": "input-1",
        "role": "upstream_evidence",
        "schema_ref": "bridge://schemas/eligibility-result/v0.1",
        "object_version": "0.1.0",
        "path": (tmp_path / "input.json").resolve(),
        "sha256": "a" * 64,
    }
    payload.update(overrides)
    return payload


def _v2_spec(
    *,
    state: ImplementationState = ImplementationState.IMPLEMENTED,
    adapter_ref: str | None = "bridge.tool_packages.specs:SYNTHETIC_ADAPTER",
    result_schema_ref: str | None = RESULT_SCHEMA_REF,
) -> ToolPackageSpecV2:
    return ToolPackageSpecV2(
        tool_id="P0-03",
        name="Synthetic structured package",
        version="0.2.0",
        summary="Synthetic contract fixture.",
        implementation_state=state,
        scientific_status="candidate",
        environment_spec_id="ENV-SYNTHETIC-v0.1",
        input_schema_ref="bridge://schemas/tool-request/v0.2",
        output_schema_ref="bridge://schemas/tool-run/v0.2",
        method_ids=["METHOD-SYNTHETIC"] if state is ImplementationState.IMPLEMENTED else [],
        card_ref="bridge://tool-cards/P0-03",
        adapter_ref=adapter_ref,
        result_schema_ref=result_schema_ref,
    )


def _mixed_registry(spec: ToolPackageSpecV2) -> ToolRegistry:
    specs = ToolRegistry.load_default().list()
    specs[2] = spec
    return ToolRegistry(specs)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"path": Path("relative.json")}, "absolute"),
        ({"sha256": "A" * 64}, "sha256"),
        ({"sha256": "a" * 63}, "sha256"),
        ({"media_type": "json"}, "media_type"),
    ],
)
def test_structured_input_validates_path_hash_and_media_type(
    tmp_path: Path, overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        StructuredInputRef.model_validate(_structured_input(tmp_path, **overrides))


def test_structured_input_defaults_media_type_and_is_frozen(tmp_path: Path) -> None:
    structured_input = StructuredInputRef.model_validate(_structured_input(tmp_path))

    assert structured_input.media_type == "application/json"
    with pytest.raises(ValidationError, match="frozen"):
        structured_input.role = "changed"  # type: ignore[misc]


def test_structured_input_never_accepts_inline_payload(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="payload"):
        StructuredInputRef.model_validate(
            _structured_input(tmp_path, payload={"inline": "forbidden"})
        )

    with pytest.raises(ValidationError, match="payload"):
        ToolRequestV2(
            request_id="request-v2",
            tool_id="P0-03",
            output_dir=tmp_path,
            object_inputs=[_structured_input(tmp_path, payload={"inline": "forbidden"})],
        )


def test_v2_request_preserves_v1_asset_and_output_invariants(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="output_dir"):
        ToolRequestV2(
            request_id="request-v2",
            tool_id="P0-03",
            output_dir=Path("relative-output"),
        )

    with pytest.raises(ValidationError, match="analysis_ready"):
        ToolRequestV2(
            request_id="request-v2",
            tool_id="P0-03",
            output_dir=tmp_path,
            assets=[
                {
                    "asset_id": "asset-1",
                    "path": (tmp_path / "asset.h5ad").resolve(),
                    "format": "h5ad",
                    "input_level": "analysis_ready",
                    "matrix_semantics": "raw_counts",
                }
            ],
        )


def test_v2_package_state_bindings_are_enforced() -> None:
    with pytest.raises(ValidationError, match="at least one method"):
        ToolPackageSpecV2.model_validate(
            _v2_spec().model_dump() | {"method_ids": []}
        )
    with pytest.raises(ValidationError, match="requires adapter_ref"):
        _v2_spec(adapter_ref=None)
    with pytest.raises(ValidationError, match="requires result_schema_ref"):
        _v2_spec(result_schema_ref=None)
    with pytest.raises(ValidationError, match="cannot claim"):
        _v2_spec(state=ImplementationState.SCAFFOLD, adapter_ref="bridge.tool_packages.specs:X")

    scaffold = _v2_spec(
        state=ImplementationState.SCAFFOLD,
        adapter_ref=None,
        result_schema_ref=None,
    )
    assert scaffold.method_ids == []


@pytest.mark.parametrize("execution_state", [ExecutionState.SUCCEEDED, ExecutionState.PARTIAL])
def test_successful_or_partial_v2_run_requires_result_schema(
    tmp_path: Path, execution_state: ExecutionState
) -> None:
    request = ToolRequestV2(
        request_id="request-v2", tool_id="P0-03", output_dir=tmp_path
    )
    with pytest.raises(ValidationError, match="requires result_schema_ref"):
        ToolRunV2(
            run_id="run-v2",
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=execution_state,
            tool_version="0.2.0",
            environment_spec_id="ENV-SYNTHETIC-v0.1",
            result={"synthetic": True},
        )


@pytest.mark.parametrize(
    "implementation_state,execution_state",
    [
        (ImplementationState.SCAFFOLD, ExecutionState.FAILED),
        (ImplementationState.SCAFFOLD, ExecutionState.NOT_IMPLEMENTED),
        (ImplementationState.IMPLEMENTED, ExecutionState.NOT_IMPLEMENTED),
    ],
)
def test_scaffold_and_not_implemented_v2_runs_cannot_emit_payloads(
    tmp_path: Path,
    implementation_state: ImplementationState,
    execution_state: ExecutionState,
) -> None:
    request = ToolRequestV2(
        request_id="request-v2", tool_id="P0-03", output_dir=tmp_path
    )
    with pytest.raises(ValidationError, match="cannot contain"):
        ToolRunV2(
            run_id="run-v2",
            request=request,
            implementation_state=implementation_state,
            execution_state=execution_state,
            tool_version="0.2.0",
            environment_spec_id="ENV-SYNTHETIC-v0.1",
            result_schema_ref=RESULT_SCHEMA_REF,
            result={"synthetic": True},
        )


def test_registry_loads_mixed_contract_versions_and_selects_request_model(
    tmp_path: Path,
) -> None:
    registry = _mixed_registry(
        _v2_spec(
            state=ImplementationState.SCAFFOLD,
            adapter_ref=None,
            result_schema_ref=None,
        )
    )

    assert isinstance(
        registry.describe("P0-01"),
        type(ToolRegistry.load_default().describe("P0-01")),
    )
    assert isinstance(registry.describe("P0-03"), ToolPackageSpecV2)
    assert isinstance(
        registry.parse_request(
            {
                "request_id": "request-v2",
                "tool_id": "P0-03",
                "output_dir": str(tmp_path),
                "object_inputs": [_structured_input(tmp_path)],
            }
        ),
        ToolRequestV2,
    )
    assert isinstance(
        registry.parse_request(
            {
                "request_id": "request-v1",
                "tool_id": "P0-01",
                "output_dir": str(tmp_path),
            }
        ),
        ToolRequest,
    )

    assert isinstance(
        ToolRegistry._parse_spec(_v2_spec().model_dump(mode="json")),
        ToolPackageSpecV2,
    )
    assert not isinstance(
        ToolRegistry._parse_spec(
            ToolRegistry.load_default().describe("P0-01").model_dump(mode="json")
        ),
        ToolPackageSpecV2,
    )


def test_v2_adapter_resolution_and_sdk_result_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = SyntheticAdapter()
    specs_module = importlib.import_module("bridge.tool_packages.specs")
    monkeypatch.setattr(specs_module, "SYNTHETIC_ADAPTER", adapter, raising=False)
    registry = _mixed_registry(_v2_spec())
    monkeypatch.setattr(ToolRegistry, "load_default", classmethod(lambda cls: registry))
    request = ToolRequestV2(
        request_id="request-v2",
        tool_id="P0-03",
        output_dir=tmp_path,
        object_inputs=[StructuredInputRef.model_validate(_structured_input(tmp_path))],
    )

    eligibility = api.validate_request(request)
    result = api.run_tool(request)

    assert eligibility.eligible is True
    assert isinstance(result, ToolRunV2)
    assert result.result_schema_ref == RESULT_SCHEMA_REF
    assert result.result == {"synthetic": True}


@pytest.mark.parametrize(
    ("adapter_ref", "message"),
    [
        ("os:system", "adapter_ref"),
        ("bridge.tool_packages.specs:ADAPTER.__class__", "adapter_ref"),
        ("bridge.tool_packages..specs:ADAPTER", "adapter_ref"),
    ],
)
def test_v2_package_rejects_non_packaged_or_malicious_adapter_refs(
    adapter_ref: str, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _v2_spec(adapter_ref=adapter_ref)


def test_registry_rejects_packaged_attribute_that_is_not_an_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    specs_module = importlib.import_module("bridge.tool_packages.specs")
    monkeypatch.setattr(specs_module, "NOT_AN_ADAPTER", object(), raising=False)
    registry = _mixed_registry(
        _v2_spec(adapter_ref="bridge.tool_packages.specs:NOT_AN_ADAPTER")
    )
    request = ToolRequestV2(
        request_id="request-v2", tool_id="P0-03", output_dir=tmp_path
    )

    with pytest.raises(TypeError, match="does not satisfy"):
        registry.check_eligibility(request)


def test_registry_rejects_module_injected_outside_packaged_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_name = "bridge.tool_packages.injected"
    module = ModuleType(module_name)
    module.__spec__ = ModuleSpec(module_name, loader=None, origin=str(tmp_path / "outside.py"))
    module.SYNTHETIC_ADAPTER = SyntheticAdapter()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module_name, module)
    registry = _mixed_registry(
        _v2_spec(adapter_ref=f"{module_name}:SYNTHETIC_ADAPTER")
    )
    request = ToolRequestV2(
        request_id="request-v2", tool_id="P0-03", output_dir=tmp_path
    )

    with pytest.raises(ValueError, match="outside bridge.tool_packages"):
        registry.check_eligibility(request)


@pytest.mark.parametrize(
    ("attribute", "value", "message"),
    [
        ("tool_version", "9.9.9", "tool version"),
        ("result_schema_ref", "bridge://schemas/tool-run/v0.2", "result schema"),
    ],
)
def test_registry_rejects_adapter_result_binding_mismatches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    attribute: str,
    value: str,
    message: str,
) -> None:
    adapter = SyntheticAdapter()
    setattr(adapter, attribute, value)
    specs_module = importlib.import_module("bridge.tool_packages.specs")
    monkeypatch.setattr(specs_module, "SYNTHETIC_ADAPTER", adapter, raising=False)
    registry = _mixed_registry(_v2_spec())
    request = ToolRequestV2(
        request_id="request-v2", tool_id="P0-03", output_dir=tmp_path
    )

    with pytest.raises(ValueError, match=message):
        registry.run(request)


def test_cli_selects_v2_request_model_after_tool_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    adapter = SyntheticAdapter()
    specs_module = importlib.import_module("bridge.tool_packages.specs")
    monkeypatch.setattr(specs_module, "SYNTHETIC_ADAPTER", adapter, raising=False)
    registry = _mixed_registry(_v2_spec())
    monkeypatch.setattr(ToolRegistry, "load_default", classmethod(lambda cls: registry))
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "request_id": "request-v2",
                "tool_id": "P0-03",
                "output_dir": str(tmp_path / "output"),
                "object_inputs": [
                    _structured_input(tmp_path) | {"path": str(tmp_path / "input.json")}
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = cli_main(["run", "--request", str(request_path)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["request"]["object_inputs"][0]["input_id"] == "input-1"
    assert payload["result_schema_ref"] == RESULT_SCHEMA_REF


def test_v2_public_schemas_are_packaged_and_enforce_model_rules() -> None:
    refs = [
        "bridge://schemas/structured-input-ref/v0.1",
        "bridge://schemas/tool-request/v0.2",
        "bridge://schemas/tool-run/v0.2",
        "bridge://schemas/tool-package-spec/v0.2",
    ]
    for schema_ref in refs:
        schema = load_schema(schema_ref)
        assert schema["$id"] == schema_ref
        assert schema["additionalProperties"] is False

    request_schema = load_schema("bridge://schemas/tool-request/v0.2")
    assert "object_inputs" in request_schema["properties"]
    assert "payload" not in json.dumps(request_schema)

    package_validator = Draft202012Validator(
        load_schema("bridge://schemas/tool-package-spec/v0.2")
    )
    invalid_package = _v2_spec().model_dump(mode="json") | {"adapter_ref": None}
    assert list(package_validator.iter_errors(invalid_package))


def test_schema_projections_match_and_v1_contract_bytes_are_unchanged() -> None:
    repo = Path(__file__).resolve().parents[1]
    for filename in [
        "structured_input_ref.schema.json",
        "tool_request_v2.schema.json",
        "tool_run_v2.schema.json",
        "tool_package_spec_v2.schema.json",
    ]:
        assert (repo / "schemas" / filename).read_bytes() == (
            repo / "src/bridge/resources/schemas" / filename
        ).read_bytes()

    for filename, expected_sha256 in V1_SCHEMA_SHA256.items():
        actual_sha256 = hashlib.sha256(
            (repo / "schemas" / filename).read_bytes()
        ).hexdigest()
        assert actual_sha256 == expected_sha256
