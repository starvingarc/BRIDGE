from __future__ import annotations

import hashlib
import importlib
from importlib.machinery import ModuleSpec
import json
from pathlib import Path
import sys
import tomllib
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
    ToolPackageSpec,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
    ToolRun,
    ToolRunV2,
)
from bridge.toolkit.registry import ToolRegistry
from bridge.toolkit.schemas import load_schema
from tools import check_repository as repository_policy


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
        self.environment_spec_id = "ENV-SYNTHETIC-v0.1"
        self.result_payload: dict[str, object] = {
            "tool_id": "P0-03",
            "eligible": True,
            "reason_codes": [],
            "warnings": [],
        }
        self.eligibility_calls = 0
        self.run_calls = 0
        self.mutate_path: Path | None = None
        self.mutate_during_eligibility: Path | None = None
        self.eligibility_error: Exception | None = None
        self.return_invalid_eligibility = False
        self.run_error: Exception | None = None
        self.return_invalid_result = False

    def check_eligibility(
        self, request: ToolRequestV2, spec: ToolPackageSpecV2
    ) -> EligibilityResult:
        self.eligibility_calls += 1
        if self.mutate_during_eligibility is not None:
            self.mutate_during_eligibility.write_text(
                '{"mutated":true}', encoding="utf-8"
            )
        if self.eligibility_error is not None:
            raise self.eligibility_error
        if self.return_invalid_eligibility:
            return object()  # type: ignore[return-value]
        return EligibilityResult(tool_id=request.tool_id, eligible=True)

    def run(self, request: ToolRequestV2, spec: ToolPackageSpecV2) -> ToolRunV2:
        self.run_calls += 1
        if self.mutate_path is not None:
            self.mutate_path.write_text('{"mutated":true}', encoding="utf-8")
        if self.run_error is not None:
            raise self.run_error
        if self.return_invalid_result:
            return object()  # type: ignore[return-value]
        return ToolRunV2(
            run_id="run-synthetic",
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=ExecutionState.SUCCEEDED,
            tool_version=self.tool_version,
            environment_spec_id=self.environment_spec_id,
            result_schema_ref=self.result_schema_ref,
            result=self.result_payload,
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


def _write_structured_input(
    tmp_path: Path,
    *,
    payload: object | None = None,
    schema_ref: str = RESULT_SCHEMA_REF,
    media_type: str = "application/json",
    filename: str = "input.json",
    input_id: str = "input-1",
    object_version: str = "0.1.0",
) -> StructuredInputRef:
    object_payload = payload
    if object_payload is None:
        object_payload = {
            "tool_id": "P0-01",
            "eligible": True,
            "reason_codes": [],
            "warnings": [],
        }
    encoded = json.dumps(object_payload, separators=(",", ":")).encode("utf-8")
    path = tmp_path / filename
    path.write_bytes(encoded)
    return StructuredInputRef.model_validate(
        _structured_input(
            tmp_path,
            path=path.resolve(),
            sha256=hashlib.sha256(encoded).hexdigest(),
            schema_ref=schema_ref,
            media_type=media_type,
            input_id=input_id,
            object_version=object_version,
        )
    )


def _write_raw_structured_input(
    tmp_path: Path,
    encoded: bytes,
    *,
    filename: str = "input.json",
    input_id: str = "input-1",
    schema_ref: str = RESULT_SCHEMA_REF,
    object_version: str = "0.1.0",
) -> StructuredInputRef:
    path = tmp_path / filename
    path.write_bytes(encoded)
    return StructuredInputRef.model_validate(
        _structured_input(
            tmp_path,
            path=path.resolve(),
            sha256=hashlib.sha256(encoded).hexdigest(),
            input_id=input_id,
            schema_ref=schema_ref,
            object_version=object_version,
        )
    )


def _registry_with_adapter(
    monkeypatch: pytest.MonkeyPatch,
    adapter: SyntheticAdapter,
    *,
    spec: ToolPackageSpecV2 | None = None,
) -> ToolRegistry:
    specs_module = importlib.import_module("bridge.tool_packages.specs")
    monkeypatch.setattr(specs_module, "SYNTHETIC_ADAPTER", adapter, raising=False)
    return _mixed_registry(spec or _v2_spec())


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


def test_v2_request_rejects_duplicate_structured_input_ids(tmp_path: Path) -> None:
    first = _write_structured_input(
        tmp_path, filename="first.json", input_id="duplicate-id"
    )
    second = _write_structured_input(
        tmp_path, filename="second.json", input_id="duplicate-id"
    )

    with pytest.raises(ValidationError, match="unique input_id"):
        ToolRequestV2(
            request_id="request-duplicate-id",
            tool_id="P0-03",
            output_dir=tmp_path / "output",
            object_inputs=[first, second],
        )


def test_v2_request_rejects_resolved_path_aliases(tmp_path: Path) -> None:
    first = _write_structured_input(
        tmp_path, filename="source.json", input_id="source"
    )
    alias_path = tmp_path / "alias.json"
    alias_path.symlink_to(first.path)
    alias = StructuredInputRef.model_validate(
        first.model_dump()
        | {
            "input_id": "alias",
            "role": "conflicting_role",
            "path": alias_path,
        }
    )

    with pytest.raises(ValidationError, match="resolved path"):
        ToolRequestV2(
            request_id="request-alias",
            tool_id="P0-03",
            output_dir=tmp_path / "output",
            object_inputs=[first, alias],
        )


@pytest.mark.parametrize(
    ("case", "reason_code"),
    [
        ("missing", "structured_input_not_found"),
        ("directory", "structured_input_not_regular_file"),
        ("checksum", "structured_input_checksum_mismatch"),
        ("media_type", "structured_input_media_type_unsupported"),
        ("json", "structured_input_invalid_json"),
        ("schema_ref", "structured_input_schema_not_registered"),
        ("schema_payload", "structured_input_schema_validation_failed"),
    ],
)
def test_v2_structured_input_failures_are_deterministic_and_block_adapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    reason_code: str,
) -> None:
    if case == "missing":
        input_ref = StructuredInputRef.model_validate(_structured_input(tmp_path))
    elif case == "directory":
        input_ref = StructuredInputRef.model_validate(
            _structured_input(tmp_path, path=tmp_path.resolve())
        )
    elif case == "checksum":
        valid = _write_structured_input(tmp_path)
        input_ref = StructuredInputRef.model_validate(
            valid.model_dump() | {"sha256": "0" * 64}
        )
    elif case == "media_type":
        input_ref = _write_structured_input(tmp_path, media_type="text/plain")
    elif case == "json":
        encoded = b"{not-json"
        path = tmp_path / "input.json"
        path.write_bytes(encoded)
        input_ref = StructuredInputRef.model_validate(
            _structured_input(
                tmp_path,
                sha256=hashlib.sha256(encoded).hexdigest(),
            )
        )
    elif case == "schema_ref":
        input_ref = _write_structured_input(
            tmp_path,
            schema_ref="bridge://schemas/not-registered/v0.1",
        )
    else:
        input_ref = _write_structured_input(tmp_path, payload={"eligible": True})

    adapter = SyntheticAdapter()
    registry = _registry_with_adapter(monkeypatch, adapter)
    request = ToolRequestV2(
        request_id=f"request-{case}",
        tool_id="P0-03",
        output_dir=tmp_path / "output",
        object_inputs=[input_ref],
    )

    eligibility = registry.check_eligibility(request)
    run = registry.run(request)

    assert eligibility.eligible is False
    assert eligibility.reason_codes == [reason_code]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == [reason_code]
    assert adapter.eligibility_calls == 0
    assert adapter.run_calls == 0


@pytest.mark.parametrize(
    "encoded",
    [
        b'{"eligible":NaN}',
        b'{"eligible":Infinity}',
        b'{"eligible":-Infinity}',
        b'{"tool_id":"P0-01","tool_id":"P0-02","eligible":true}',
    ],
    ids=["nan", "infinity", "negative-infinity", "duplicate-key"],
)
def test_v2_preflight_rejects_nonstandard_or_ambiguous_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    encoded: bytes,
) -> None:
    input_ref = _write_raw_structured_input(tmp_path, encoded)
    adapter = SyntheticAdapter()
    registry = _registry_with_adapter(monkeypatch, adapter)
    request = ToolRequestV2(
        request_id="request-strict-json",
        tool_id="P0-03",
        output_dir=tmp_path / "output",
        object_inputs=[input_ref],
    )

    eligibility = registry.check_eligibility(request)

    assert eligibility.eligible is False
    assert eligibility.reason_codes == ["structured_input_invalid_json"]
    assert adapter.eligibility_calls == 0


@pytest.mark.parametrize(
    "encoded",
    [
        b'{"eligible":NaN}',
        b'{"tool_id":"P0-01","tool_id":"P0-02","eligible":true}',
    ],
    ids=["nan", "duplicate-key"],
)
def test_cli_validate_reports_strict_json_failure_without_adapter_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    encoded: bytes,
) -> None:
    input_ref = _write_raw_structured_input(tmp_path, encoded)
    adapter = SyntheticAdapter()
    registry = _registry_with_adapter(monkeypatch, adapter)
    monkeypatch.setattr(ToolRegistry, "load_default", classmethod(lambda cls: registry))
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "request_id": "request-strict-json",
                "tool_id": "P0-03",
                "output_dir": str(tmp_path / "output"),
                "object_inputs": [input_ref.model_dump(mode="json")],
            }
        ),
        encoding="utf-8",
    )

    exit_code = cli_main(["validate", "--request", str(request_path)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 3
    assert payload["reason_codes"] == ["structured_input_invalid_json"]
    assert adapter.eligibility_calls == 0


def _versioned_structured_payload(tmp_path: Path, version: str) -> dict[str, object]:
    return {
        "input_id": "nested-input",
        "role": "synthetic_versioned_object",
        "schema_ref": RESULT_SCHEMA_REF,
        "object_version": version,
        "path": str((tmp_path / "nested.json").resolve()),
        "sha256": "b" * 64,
        "media_type": "application/json",
    }


@pytest.mark.parametrize(
    ("case", "reason_code"),
    [
        ("missing", "structured_input_object_version_missing"),
        ("mismatch", "structured_input_object_version_mismatch"),
    ],
)
def test_versioned_schema_requires_object_version_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    reason_code: str,
) -> None:
    payload = _versioned_structured_payload(tmp_path, "0.1.0")
    if case == "missing":
        payload.pop("object_version")
        ref_version = "0.1.0"
    else:
        ref_version = "9.9.9"
    input_ref = _write_structured_input(
        tmp_path,
        payload=payload,
        schema_ref="bridge://schemas/structured-input-ref/v0.1",
        object_version=ref_version,
    )
    adapter = SyntheticAdapter()
    registry = _registry_with_adapter(monkeypatch, adapter)
    request = ToolRequestV2(
        request_id=f"request-version-{case}",
        tool_id="P0-03",
        output_dir=tmp_path / "output",
        object_inputs=[input_ref],
    )

    eligibility = registry.check_eligibility(request)

    assert eligibility.eligible is False
    assert eligibility.reason_codes == [reason_code]
    assert adapter.eligibility_calls == 0


def test_established_top_level_version_binds_to_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_payload = ToolRegistry.load_default().describe("P0-01").model_dump(
        mode="json"
    )
    input_ref = _write_structured_input(
        tmp_path,
        payload=package_payload,
        schema_ref="bridge://schemas/tool-package-spec/v0.1",
        object_version=package_payload["version"],
    )
    adapter = SyntheticAdapter()
    registry = _registry_with_adapter(monkeypatch, adapter)
    request = ToolRequestV2(
        request_id="request-established-version",
        tool_id="P0-03",
        output_dir=tmp_path / "output",
        object_inputs=[input_ref],
    )

    eligibility = registry.check_eligibility(request)

    assert eligibility.eligible is True
    assert adapter.eligibility_calls == 1


@pytest.mark.parametrize(
    ("case", "reason_code"),
    [
        ("missing", "structured_input_object_version_missing"),
        ("mismatch", "structured_input_object_version_mismatch"),
    ],
)
def test_established_top_level_version_rejects_missing_or_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    reason_code: str,
) -> None:
    package_payload = ToolRegistry.load_default().describe("P0-01").model_dump(
        mode="json"
    )
    if case == "missing":
        package_payload.pop("version")
        ref_version = "0.1.0"
    else:
        ref_version = "9.9.9"
    input_ref = _write_structured_input(
        tmp_path,
        payload=package_payload,
        schema_ref="bridge://schemas/tool-package-spec/v0.1",
        object_version=ref_version,
    )
    adapter = SyntheticAdapter()
    registry = _registry_with_adapter(monkeypatch, adapter)
    request = ToolRequestV2(
        request_id=f"request-established-version-{case}",
        tool_id="P0-03",
        output_dir=tmp_path / "output",
        object_inputs=[input_ref],
    )

    eligibility = registry.check_eligibility(request)

    assert eligibility.eligible is False
    assert eligibility.reason_codes == [reason_code]
    assert adapter.eligibility_calls == 0


@pytest.mark.parametrize(
    ("schema_ref", "legacy_payload"),
    [
        (
            "bridge://schemas/measurement-result/v0.1",
            {
                "measurement_id": "measurement-1",
                "measurement_spec_id": "spec-1",
                "metric_name": "synthetic_metric",
                "raw_value": 1,
                "score_state": "unavailable",
                "evidence_state": "measured",
            },
        ),
        (
            "bridge://schemas/qc-readiness-profile/v0.1",
            {
                "profile_id": "profile-1",
                "input_level": "analysis_ready",
                "assay": "scRNA-seq",
                "readiness_state": "ready",
                "schema_integrity": {},
                "metadata_completeness": {},
                "matrix_provenance": {},
                "upstream_library_qc": {},
                "cell_qc": {},
                "doublet_assessment": {},
                "cell_calling_assessment": {},
                "ambient_assessment": {},
                "data_views": {},
                "module_eligibility": {},
            },
        ),
    ],
    ids=["measurement-result", "qc-readiness-profile"],
)
def test_legacy_schema_without_version_uses_external_object_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    schema_ref: str,
    legacy_payload: dict[str, object],
) -> None:
    input_ref = _write_structured_input(
        tmp_path,
        payload=legacy_payload,
        schema_ref=schema_ref,
        object_version="0.1",
    )
    adapter = SyntheticAdapter()
    registry = _registry_with_adapter(monkeypatch, adapter)
    request = ToolRequestV2(
        request_id="request-legacy-version",
        tool_id="P0-03",
        output_dir=tmp_path / "output",
        object_inputs=[input_ref],
    )

    eligibility = registry.check_eligibility(request)

    assert eligibility.eligible is True
    assert adapter.eligibility_calls == 1


def test_v2_run_rejects_structured_input_mutation_after_adapter_returns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _write_structured_input(
        tmp_path, filename="first.json", input_id="first"
    )
    second = _write_structured_input(
        tmp_path, filename="second.json", input_id="second"
    )
    adapter = SyntheticAdapter()
    adapter.mutate_path = second.path
    registry = _registry_with_adapter(monkeypatch, adapter)
    request = ToolRequestV2(
        request_id="request-mutation",
        tool_id="P0-03",
        output_dir=tmp_path / "output",
        object_inputs=[first, second],
    )

    run = registry.run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.result is None
    assert run.result_schema_ref is None
    assert run.reason_codes == ["input_asset_modified_during_run"]
    assert adapter.eligibility_calls == 1
    assert adapter.run_calls == 1


def test_v2_eligibility_rejects_structured_input_mutation_after_adapter_returns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_ref = _write_structured_input(tmp_path)
    adapter = SyntheticAdapter()
    adapter.mutate_during_eligibility = input_ref.path
    registry = _registry_with_adapter(monkeypatch, adapter)
    request = ToolRequestV2(
        request_id="request-eligibility-mutation",
        tool_id="P0-03",
        output_dir=tmp_path / "output",
        object_inputs=[input_ref],
    )

    eligibility = registry.check_eligibility(request)

    assert eligibility.eligible is False
    assert eligibility.reason_codes == ["input_asset_modified_during_run"]
    assert adapter.eligibility_calls == 1
    assert adapter.run_calls == 0


@pytest.mark.parametrize("invalid_result", [False, True], ids=["exception", "invalid-type"])
def test_eligibility_mutation_overrides_adapter_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid_result: bool,
) -> None:
    input_ref = _write_structured_input(tmp_path)
    adapter = SyntheticAdapter()
    adapter.mutate_during_eligibility = input_ref.path
    adapter.return_invalid_eligibility = invalid_result
    if not invalid_result:
        adapter.eligibility_error = RuntimeError("adapter eligibility failed")
    registry = _registry_with_adapter(monkeypatch, adapter)
    request = ToolRequestV2(
        request_id="request-eligibility-mutation-error",
        tool_id="P0-03",
        output_dir=tmp_path / "output",
        object_inputs=[input_ref],
    )

    eligibility = registry.check_eligibility(request)

    assert eligibility.eligible is False
    assert eligibility.reason_codes == ["input_asset_modified_during_run"]


@pytest.mark.parametrize("invalid_result", [False, True], ids=["exception", "invalid-type"])
def test_run_mutation_overrides_adapter_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid_result: bool,
) -> None:
    input_ref = _write_structured_input(tmp_path)
    adapter = SyntheticAdapter()
    adapter.mutate_path = input_ref.path
    adapter.return_invalid_result = invalid_result
    if not invalid_result:
        adapter.run_error = RuntimeError("adapter run failed")
    registry = _registry_with_adapter(monkeypatch, adapter)
    request = ToolRequestV2(
        request_id="request-run-mutation-failure",
        tool_id="P0-03",
        output_dir=tmp_path / "output",
        object_inputs=[input_ref],
    )

    run = registry.run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["input_asset_modified_during_run"]


@pytest.mark.parametrize("phase", ["eligibility", "run"])
def test_adapter_exception_is_preserved_when_inputs_are_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    input_ref = _write_structured_input(tmp_path)
    adapter = SyntheticAdapter()
    adapter.eligibility_error = (
        RuntimeError("unchanged adapter eligibility failure")
        if phase == "eligibility"
        else None
    )
    adapter.run_error = (
        RuntimeError("unchanged adapter run failure") if phase == "run" else None
    )
    registry = _registry_with_adapter(monkeypatch, adapter)
    request = ToolRequestV2(
        request_id=f"request-unchanged-{phase}-error",
        tool_id="P0-03",
        output_dir=tmp_path / "output",
        object_inputs=[input_ref],
    )

    with pytest.raises(RuntimeError, match=f"unchanged adapter {phase} failure"):
        if phase == "eligibility":
            registry.check_eligibility(request)
        else:
            registry.run(request)


@pytest.mark.parametrize("phase", ["eligibility", "run"])
def test_invalid_adapter_return_is_preserved_when_inputs_are_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    input_ref = _write_structured_input(tmp_path)
    adapter = SyntheticAdapter()
    adapter.return_invalid_eligibility = phase == "eligibility"
    adapter.return_invalid_result = phase == "run"
    registry = _registry_with_adapter(monkeypatch, adapter)
    request = ToolRequestV2(
        request_id=f"request-invalid-{phase}",
        tool_id="P0-03",
        output_dir=tmp_path / "output",
        object_inputs=[input_ref],
    )

    with pytest.raises(TypeError, match="invalid"):
        if phase == "eligibility":
            registry.check_eligibility(request)
        else:
            registry.run(request)


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
    with pytest.raises(ValidationError, match=r"method_ids=\[\]"):
        ToolPackageSpecV2.model_validate(
            _v2_spec(
                state=ImplementationState.SCAFFOLD,
                adapter_ref=None,
                result_schema_ref=None,
            ).model_dump()
            | {"method_ids": ["METHOD-SYNTHETIC"]}
        )

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

    with pytest.raises(ValidationError, match="requires result_schema_ref and result"):
        ToolRunV2(
            run_id="run-v2",
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=execution_state,
            tool_version="0.2.0",
            environment_spec_id="ENV-SYNTHETIC-v0.1",
            result_schema_ref=RESULT_SCHEMA_REF,
            result=None,
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


def test_deprecated_v1_package_is_ineligible_and_non_executable(tmp_path: Path) -> None:
    specs = ToolRegistry.load_default().list()
    deprecated = ToolPackageSpec.model_validate(
        ToolRegistry.load_default().describe("P0-01").model_dump(mode="json")
        | {"implementation_state": ImplementationState.DEPRECATED}
    )
    registry = ToolRegistry(
        [deprecated if spec.tool_id == "P0-01" else spec for spec in specs]
    )
    request = ToolRequest(
        request_id="request-deprecated-v1",
        tool_id="P0-01",
        output_dir=tmp_path,
    )

    eligibility = registry.check_eligibility(request)
    run = registry.run(request)

    assert eligibility.eligible is False
    assert eligibility.reason_codes == ["tool_package_deprecated"]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["tool_package_deprecated"]


def test_deprecated_v2_package_never_resolves_or_executes_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = SyntheticAdapter()
    registry = _registry_with_adapter(
        monkeypatch,
        adapter,
        spec=_v2_spec(state=ImplementationState.DEPRECATED),
    )
    request = ToolRequestV2(
        request_id="request-deprecated-v2",
        tool_id="P0-03",
        output_dir=tmp_path,
    )

    eligibility = registry.check_eligibility(request)
    run = registry.run(request)

    assert eligibility.eligible is False
    assert eligibility.reason_codes == ["tool_package_deprecated"]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["tool_package_deprecated"]
    assert adapter.eligibility_calls == 0
    assert adapter.run_calls == 0


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
        object_inputs=[_write_structured_input(tmp_path)],
    )

    eligibility = api.validate_request(request)
    result = api.run_tool(request)

    assert eligibility.eligible is True
    assert isinstance(result, ToolRunV2)
    assert result.result_schema_ref == RESULT_SCHEMA_REF
    assert result.result == {
        "tool_id": "P0-03",
        "eligible": True,
        "reason_codes": [],
        "warnings": [],
    }


def test_public_sdk_structures_v1_request_refusal_for_v2_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = SyntheticAdapter()
    registry = _registry_with_adapter(monkeypatch, adapter)
    monkeypatch.setattr(ToolRegistry, "load_default", classmethod(lambda cls: registry))
    request = ToolRequest(
        request_id="wrong-v1-envelope",
        tool_id="P0-03",
        output_dir=tmp_path,
    )

    eligibility = api.validate_request(request)
    run = api.run_tool(request)

    assert eligibility.eligible is False
    assert eligibility.reason_codes == ["tool_request_v2_required"]
    assert isinstance(run, ToolRun)
    assert run.request == request
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["tool_request_v2_required"]
    assert adapter.eligibility_calls == 0
    assert adapter.run_calls == 0


def test_public_sdk_structures_v2_request_refusal_for_v1_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = ToolRegistry.load_default()
    monkeypatch.setattr(ToolRegistry, "load_default", classmethod(lambda cls: registry))
    request = ToolRequestV2(
        request_id="wrong-v2-envelope",
        tool_id="P0-01",
        output_dir=tmp_path,
    )

    eligibility = api.validate_request(request)
    run = api.run_tool(request)

    assert eligibility.eligible is False
    assert eligibility.reason_codes == ["tool_request_v1_required"]
    assert isinstance(run, ToolRunV2)
    assert run.request == request
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["tool_request_v1_required"]


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
        ("environment_spec_id", "ENV-WRONG-v0.1", "environment spec"),
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


def test_registry_rejects_unknown_result_schema_before_adapter_executes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = SyntheticAdapter()
    registry = _registry_with_adapter(
        monkeypatch,
        adapter,
        spec=_v2_spec(result_schema_ref="bridge://schemas/not-registered/v0.1"),
    )
    request = ToolRequestV2(
        request_id="request-unknown-result-schema",
        tool_id="P0-03",
        output_dir=tmp_path,
    )

    with pytest.raises(ValueError, match="result schema is not registered"):
        registry.run(request)
    assert adapter.eligibility_calls == 0
    assert adapter.run_calls == 0


def test_registry_rejects_result_that_violates_registered_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = SyntheticAdapter()
    adapter.result_payload = {"eligible": True}
    registry = _registry_with_adapter(monkeypatch, adapter)
    request = ToolRequestV2(
        request_id="request-invalid-result",
        tool_id="P0-03",
        output_dir=tmp_path,
    )

    with pytest.raises(ValueError, match="violates its registered schema"):
        registry.run(request)


def test_registry_rejects_adapter_that_bypasses_model_and_omits_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class MissingResultAdapter(SyntheticAdapter):
        def run(
            self, request: ToolRequestV2, spec: ToolPackageSpecV2
        ) -> ToolRunV2:
            valid_result = super().run(request, spec)
            return valid_result.model_copy(update={"result": None})

    registry = _registry_with_adapter(monkeypatch, MissingResultAdapter())
    request = ToolRequestV2(
        request_id="request-missing-result",
        tool_id="P0-03",
        output_dir=tmp_path,
    )

    with pytest.raises(ValueError, match="without a bound result payload"):
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
    structured_input = _write_structured_input(tmp_path)
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "request_id": "request-v2",
                "tool_id": "P0-03",
                "output_dir": str(tmp_path / "output"),
                "object_inputs": [
                    structured_input.model_dump(mode="json")
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


def test_cli_validate_converts_adapter_exception_to_structured_exit_four(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    adapter = SyntheticAdapter()
    adapter.eligibility_error = RuntimeError("synthetic adapter failure")
    registry = _registry_with_adapter(monkeypatch, adapter)
    monkeypatch.setattr(ToolRegistry, "load_default", classmethod(lambda cls: registry))
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "request_id": "request-v2",
                "tool_id": "P0-03",
                "output_dir": str(tmp_path / "output"),
            }
        ),
        encoding="utf-8",
    )

    exit_code = cli_main(["validate", "--request", str(request_path)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 4
    assert payload == {
        "error": "tool_validation_error",
        "detail": "synthetic adapter failure",
        "tool_id": "P0-03",
    }


@pytest.mark.parametrize("invalid_result", [False, True], ids=["exception", "invalid-type"])
def test_cli_validate_prioritizes_input_mutation_over_adapter_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    invalid_result: bool,
) -> None:
    input_ref = _write_structured_input(tmp_path)
    adapter = SyntheticAdapter()
    adapter.mutate_during_eligibility = input_ref.path
    adapter.return_invalid_eligibility = invalid_result
    if not invalid_result:
        adapter.eligibility_error = RuntimeError("adapter eligibility failed")
    registry = _registry_with_adapter(monkeypatch, adapter)
    monkeypatch.setattr(ToolRegistry, "load_default", classmethod(lambda cls: registry))
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "request_id": "request-cli-eligibility-mutation",
                "tool_id": "P0-03",
                "output_dir": str(tmp_path / "output"),
                "object_inputs": [input_ref.model_dump(mode="json")],
            }
        ),
        encoding="utf-8",
    )

    exit_code = cli_main(["validate", "--request", str(request_path)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 3
    assert payload["reason_codes"] == ["input_asset_modified_during_run"]


@pytest.mark.parametrize("invalid_result", [False, True], ids=["exception", "invalid-type"])
def test_cli_run_prioritizes_input_mutation_over_adapter_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    invalid_result: bool,
) -> None:
    input_ref = _write_structured_input(tmp_path)
    adapter = SyntheticAdapter()
    adapter.mutate_path = input_ref.path
    adapter.return_invalid_result = invalid_result
    if not invalid_result:
        adapter.run_error = RuntimeError("adapter run failed")
    registry = _registry_with_adapter(monkeypatch, adapter)
    monkeypatch.setattr(ToolRegistry, "load_default", classmethod(lambda cls: registry))
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "request_id": "request-cli-run-mutation",
                "tool_id": "P0-03",
                "output_dir": str(tmp_path / "output"),
                "object_inputs": [input_ref.model_dump(mode="json")],
            }
        ),
        encoding="utf-8",
    )

    exit_code = cli_main(["run", "--request", str(request_path)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 3
    assert payload["execution_state"] == "failed"
    assert payload["reason_codes"] == ["input_asset_modified_during_run"]


def test_v2_public_schemas_are_packaged_and_enforce_model_rules(
    tmp_path: Path,
) -> None:
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
    assert request_schema["properties"]["object_inputs"]["uniqueItems"] is True
    assert "payload" not in json.dumps(request_schema)

    duplicate_ref = _structured_input(tmp_path)
    duplicate_request = {
        "request_id": "request-duplicate-ref",
        "tool_id": "P0-03",
        "output_dir": str(tmp_path),
        "object_inputs": [duplicate_ref, duplicate_ref],
    }
    assert list(Draft202012Validator(request_schema).iter_errors(duplicate_request))

    structured_input_validator = Draft202012Validator(
        load_schema("bridge://schemas/structured-input-ref/v0.1")
    )
    relative_input = _structured_input(tmp_path, path="relative/input.json")
    assert list(structured_input_validator.iter_errors(relative_input))

    package_validator = Draft202012Validator(
        load_schema("bridge://schemas/tool-package-spec/v0.2")
    )
    invalid_package = _v2_spec().model_dump(mode="json") | {"adapter_ref": None}
    assert list(package_validator.iter_errors(invalid_package))

    invalid_scaffold = _v2_spec(
        state=ImplementationState.SCAFFOLD,
        adapter_ref=None,
        result_schema_ref=None,
    ).model_dump(mode="json") | {"method_ids": ["METHOD-SYNTHETIC"]}
    assert list(package_validator.iter_errors(invalid_scaffold))

    request = ToolRequestV2(
        request_id="request-v2", tool_id="P0-03", output_dir=tmp_path
    )
    valid_run = ToolRunV2(
        run_id="run-v2",
        request=request,
        implementation_state=ImplementationState.IMPLEMENTED,
        execution_state=ExecutionState.SUCCEEDED,
        tool_version="0.2.0",
        environment_spec_id="ENV-SYNTHETIC-v0.1",
        result_schema_ref=RESULT_SCHEMA_REF,
        result={"tool_id": "P0-03", "eligible": True},
    ).model_dump(mode="json")
    valid_run.pop("result")
    run_validator = Draft202012Validator(load_schema("bridge://schemas/tool-run/v0.2"))
    assert list(run_validator.iter_errors(valid_run))


def test_repository_policy_rejects_unresolvable_v2_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _mixed_registry(
        _v2_spec(adapter_ref="bridge.tool_packages.missing:ADAPTER")
    )
    monkeypatch.setattr(
        repository_policy.ToolRegistry,
        "load_default",
        classmethod(lambda cls: registry),
    )
    problems: list[str] = []

    repository_policy._check_tool_package_specs(problems)

    assert any("adapter does not resolve: P0-03" in problem for problem in problems)


def test_repository_policy_rejects_unknown_v2_result_schema_without_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = SyntheticAdapter()
    registry = _registry_with_adapter(
        monkeypatch,
        adapter,
        spec=_v2_spec(result_schema_ref="bridge://schemas/not-registered/v0.1"),
    )
    monkeypatch.setattr(
        repository_policy.ToolRegistry,
        "load_default",
        classmethod(lambda cls: registry),
    )
    problems: list[str] = []

    repository_policy._check_tool_package_specs(problems)

    assert any("result schema does not resolve: P0-03" in problem for problem in problems)
    assert adapter.eligibility_calls == 0
    assert adapter.run_calls == 0


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


def test_jsonschema_is_declared_once_as_a_runtime_dependency() -> None:
    repo = Path(__file__).resolve().parents[1]
    project = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]

    runtime_dependencies = project["dependencies"]
    test_dependencies = project["optional-dependencies"]["test"]
    assert sum(item.startswith("jsonschema") for item in runtime_dependencies) == 1
    assert all(not item.startswith("jsonschema") for item in test_dependencies)
