from __future__ import annotations

import hashlib
import importlib
from importlib.machinery import ModuleSpec
from importlib.resources import files
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
from scripts import check_repository as repository_policy


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


def _v1_spec(
    *,
    state: ImplementationState = ImplementationState.IMPLEMENTED,
) -> ToolPackageSpec:
    return ToolPackageSpec(
        tool_id="P0-01",
        name="Synthetic legacy package",
        version="0.1.0",
        summary="Synthetic V1 contract fixture.",
        implementation_state=state,
        scientific_status="candidate",
        environment_spec_id="ENV-SYNTHETIC-v0.1",
        input_schema_ref="bridge://schemas/tool-request/v0.1",
        output_schema_ref="bridge://schemas/tool-run/v0.1",
        method_ids=(
            ["METHOD-SYNTHETIC"]
            if state is ImplementationState.IMPLEMENTED
            else []
        ),
        card_ref="bridge://tool-cards/P0-01",
    )


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
    package_payload = _v1_spec().model_dump(mode="json")
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
    package_payload = ToolRegistry.load_default().describe("P0-03").model_dump(
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
    deprecated = _v1_spec(state=ImplementationState.DEPRECATED)
    specs = [
        deprecated if spec.tool_id == deprecated.tool_id else spec
        for spec in ToolRegistry.load_default().list()
    ]
    registry = ToolRegistry(specs)
    request = ToolRequest(
        request_id="request-deprecated-v1",
        tool_id=deprecated.tool_id,
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


def test_repository_policy_rejects_root_contract_projections() -> None:
    problems: list[str] = []

    repository_policy._check_tracked_layout(
        [
            Path("schemas/example.schema.json"),
            Path("tool_packages/P0-01/README.md"),
            Path("catalog_seed/source_verification.json"),
            Path("tools/check_repository.py"),
            Path("PLANS.md"),
        ],
        problems,
    )

    assert problems == [
        "duplicate root projection: schemas/example.schema.json",
        "duplicate root projection: tool_packages/P0-01/README.md",
        "obsolete root directory: catalog_seed/source_verification.json",
        "obsolete root directory: tools/check_repository.py",
        "obsolete root plan index: PLANS.md",
    ]


def test_packaged_v1_contract_bytes_are_unchanged() -> None:
    repo = Path(__file__).resolve().parents[1]
    schema_dir = repo / "src/bridge/resources/schemas"
    for filename, expected_sha256 in V1_SCHEMA_SHA256.items():
        actual_sha256 = hashlib.sha256(
            (schema_dir / filename).read_bytes()
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



import hashlib
from io import BytesIO
from pathlib import Path

import pytest

from bridge.storage.artifacts import LocalArtifactStore


def test_artifact_store_addresses_and_verifies_content(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")
    artifact = store.put(BytesIO(b"measurement-result"), "application/json")

    assert artifact.artifact_id == f"sha256:{artifact.sha256}"
    assert not Path(artifact.relative_path).is_absolute()
    with store.open(artifact.artifact_id) as source:
        assert source.read() == b"measurement-result"
    assert store.verify(artifact.artifact_id).valid is True


def test_artifact_store_keeps_verified_snapshot_unlinked_inside_staging(
    tmp_path: Path,
) -> None:
    root = tmp_path / "artifacts"
    store = LocalArtifactStore(root)
    artifact = store.put(BytesIO(b"private-measurement"), "application/octet-stream")

    source = store.open(artifact.artifact_id)
    try:
        assert list((root / ".staging").iterdir()) == []
        assert source.read() == b"private-measurement"
    finally:
        source.close()


def test_artifact_store_deduplicates_equal_content(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")

    first = store.put(BytesIO(b"same"), "application/octet-stream")
    second = store.put(BytesIO(b"same"), "application/octet-stream")

    assert first.artifact_id == second.artifact_id
    assert list((tmp_path / "artifacts").glob("??/*")) == [
        tmp_path / "artifacts" / first.relative_path
    ]


def test_artifact_store_reports_tampering_without_rewriting(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")
    artifact = store.put(BytesIO(b"original"), "application/octet-stream")
    stored_path = tmp_path / "artifacts" / artifact.relative_path
    stored_path.write_bytes(b"tampered")

    verification = store.verify(artifact.artifact_id)

    assert verification.valid is False
    assert verification.reason_code == "artifact_checksum_mismatch"
    assert stored_path.read_bytes() == b"tampered"


def test_artifact_store_rejects_corrupt_deduplication_target(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    store = LocalArtifactStore(root)
    artifact = store.put(BytesIO(b"original"), "application/octet-stream")
    stored_path = root / artifact.relative_path
    stored_path.write_bytes(b"tampered")

    with pytest.raises(ValueError, match="artifact_checksum_mismatch"):
        store.put(BytesIO(b"original"), "application/octet-stream")

    assert stored_path.read_bytes() == b"tampered"
    assert list((root / ".staging").iterdir()) == []


def test_artifact_store_refuses_to_open_corrupt_content(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    store = LocalArtifactStore(root)
    artifact = store.put(BytesIO(b"original"), "application/octet-stream")
    (root / artifact.relative_path).write_bytes(b"tampered")

    with pytest.raises(ValueError, match="artifact_checksum_mismatch"):
        store.open(artifact.artifact_id)


def test_artifact_store_rejects_symlinked_shard_without_external_write(
    tmp_path: Path,
) -> None:
    content = b"outside-root"
    digest = hashlib.sha256(content).hexdigest()
    root = tmp_path / "artifacts"
    outside = tmp_path / "outside"
    outside.mkdir()
    store = LocalArtifactStore(root)
    (root / digest[:2]).symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="artifact_directory_not_regular"):
        store.put(BytesIO(content), "application/octet-stream")

    assert list(outside.iterdir()) == []
    assert list((root / ".staging").iterdir()) == []


def test_artifact_store_rejects_symlinked_object_without_external_read(
    tmp_path: Path,
) -> None:
    content = b"external-private-bytes"
    digest = hashlib.sha256(content).hexdigest()
    artifact_id = f"sha256:{digest}"
    root = tmp_path / "artifacts"
    outside = tmp_path / "private"
    outside.write_bytes(content)
    store = LocalArtifactStore(root)
    shard = root / digest[:2]
    shard.mkdir()
    (shard / digest).symlink_to(outside)

    with pytest.raises(ValueError, match="artifact_not_regular"):
        store.open(artifact_id)

    verification = store.verify(artifact_id)
    assert verification.valid is False
    assert verification.reason_code == "artifact_not_regular"


def test_artifact_store_rejects_symlinked_deduplication_target(
    tmp_path: Path,
) -> None:
    content = b"external-private-bytes"
    digest = hashlib.sha256(content).hexdigest()
    root = tmp_path / "artifacts"
    outside = tmp_path / "private"
    outside.write_bytes(content)
    store = LocalArtifactStore(root)
    shard = root / digest[:2]
    shard.mkdir()
    (shard / digest).symlink_to(outside)

    with pytest.raises(ValueError, match="artifact_not_regular"):
        store.put(BytesIO(content), "application/octet-stream")

    assert outside.read_bytes() == content
    assert list((root / ".staging").iterdir()) == []


def test_artifact_store_rejects_non_regular_digest_object(tmp_path: Path) -> None:
    content = b"expected"
    digest = hashlib.sha256(content).hexdigest()
    artifact_id = f"sha256:{digest}"
    root = tmp_path / "artifacts"
    store = LocalArtifactStore(root)
    (root / digest[:2] / digest).mkdir(parents=True)

    with pytest.raises(ValueError, match="artifact_not_regular"):
        store.open(artifact_id)

    assert store.verify(artifact_id).reason_code == "artifact_not_regular"


def test_artifact_store_rejects_symlinked_staging_directory(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / ".staging").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="artifact_directory_not_regular"):
        LocalArtifactStore(root)

    assert list(outside.iterdir()) == []


def test_artifact_store_rejects_symlinked_intermediate_root_component(
    tmp_path: Path,
) -> None:
    trusted = tmp_path / "trusted"
    outside = tmp_path / "outside"
    trusted.mkdir()
    outside.mkdir()
    (trusted / "redirect").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="artifact_root_not_directory"):
        LocalArtifactStore(trusted / "redirect" / "artifacts")

    assert list(outside.iterdir()) == []


def test_artifact_store_rejects_parent_traversal_in_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="artifact_root_invalid_component"):
        LocalArtifactStore(tmp_path / "trusted" / ".." / "artifacts")


def test_artifact_store_rejects_untrusted_ids(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")

    with pytest.raises(ValueError, match="invalid_artifact_id"):
        store.open("../../private-input")


def test_local_runtime_package_facades_preserve_public_exports() -> None:
    from bridge.domain import ProductCase
    from bridge.domain.models import ProductCase as ProductCaseModel
    from bridge.planner import PlanBuilder
    from bridge.planner.service import PlanBuilder as PlanBuilderService
    from bridge.runners import ToolExecutionPipeline
    from bridge.runners.pipeline import ToolExecutionPipeline as PipelineService
    from bridge.storage import LocalArtifactStore as ArtifactStoreFacade
    from bridge.workflow import LocalWorkflowExecutor, RunSnapshot
    from bridge.workflow.events import RunSnapshot as RunSnapshotModel
    from bridge.workflow.executor import LocalWorkflowExecutor as WorkflowExecutor

    assert ProductCase is ProductCaseModel
    assert PlanBuilder is PlanBuilderService
    assert ToolExecutionPipeline is PipelineService
    assert ArtifactStoreFacade is LocalArtifactStore
    assert LocalWorkflowExecutor is WorkflowExecutor
    assert RunSnapshot is RunSnapshotModel


def test_namespace_resource_packages_remain_importable() -> None:
    resources = {
        "bridge.resources.schemas": "tool_run.schema.json",
        "bridge.tool_packages.cards": "P0-01.md",
        "bridge.tool_packages.p0_02_cell_state.resources": "annotation_vocabulary.yaml",
        "bridge.tool_packages.p0_08_evidence_sufficiency.resources": (
            "gate_rule_spec_v0.1.json"
        ),
    }

    for package, filename in resources.items():
        assert files(package).joinpath(filename).is_file()
    assert len(ToolRegistry.load_default().list()) == 12


from pathlib import Path

import pytest
from pydantic import ValidationError

from bridge.domain.models import AnalysisPlan, PlanStep, ProductCase, SampleRecord
from bridge.toolkit.contracts import InputAsset


def _asset(tmp_path: Path) -> InputAsset:
    return InputAsset(
        asset_id="asset-1",
        path=(tmp_path / "product.h5ad").resolve(),
        format="h5ad",
        input_level="analysis_ready",
        matrix_semantics="normalized_expression",
        assay="scRNA-seq",
    )


def test_product_case_requires_declared_sample_assets(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="unknown assets"):
        ProductCase(
            case_id="case-1",
            version="0.1",
            status="confirmed",
            product_type="mDA progenitor preparation",
            target_cell_type="midbrain dopaminergic progenitor",
            differentiation_stage="D16",
            intended_use="research evaluation",
            assay="scRNA-seq",
            product_definition_card_ref="card://pd-mda/v0.1",
            reference_policy_ref="reference-policy://pd-mda/v0.1",
            prior_snapshot_ref="prior://pd-mda/v0.1",
            assets=[_asset(tmp_path)],
            samples=[
                SampleRecord(
                    sample_id="sample-1",
                    preparation_id="prep-1",
                    asset_ids=["undeclared-asset"],
                    data_role="evaluation",
                    sampling_context="pre-transplant",
                )
            ],
        )


def test_analysis_plan_requires_ordered_dependencies() -> None:
    with pytest.raises(ValidationError, match="must precede"):
        AnalysisPlan(
            plan_id="plan-1",
            version="0.1",
            case_ref="case-1@0.1",
            status="draft",
            knowledge_snapshot_ref="knowledge://p0/2026-08-12",
            steps=[
                PlanStep(
                    step_id="step-p0-02",
                    tool_id="P0-02",
                    tool_version="0.1.0",
                    disposition="execute",
                    depends_on=["step-p0-01"],
                ),
                PlanStep(
                    step_id="step-p0-01",
                    tool_id="P0-01",
                    tool_version="0.1.0",
                    disposition="execute",
                ),
            ],
        )


def test_skipped_plan_step_requires_reason_code() -> None:
    with pytest.raises(ValidationError, match="requires a reason code"):
        PlanStep(
            step_id="step-p0-03",
            tool_id="P0-03",
            tool_version="0.1.0",
            disposition="skip",
        )


def test_plan_rejects_execute_step_after_skipped_dependency() -> None:
    with pytest.raises(ValidationError, match="depends on skipped steps"):
        AnalysisPlan(
            plan_id="plan-1",
            version="0.1",
            case_ref="case-1@0.1",
            status="draft",
            knowledge_snapshot_ref="knowledge://p0/2026-08-12",
            steps=[
                PlanStep(
                    step_id="step-p0-01",
                    tool_id="P0-01",
                    tool_version="0.1.0",
                    disposition="skip",
                    reason_codes=["input_missing"],
                ),
                PlanStep(
                    step_id="step-p0-02",
                    tool_id="P0-02",
                    tool_version="0.1.0",
                    disposition="execute",
                    depends_on=["step-p0-01"],
                ),
            ],
        )


def test_domain_identifiers_and_references_cannot_be_empty() -> None:
    with pytest.raises(ValidationError, match="at least 1 character"):
        SampleRecord(
            sample_id="",
            preparation_id="prep-1",
            asset_ids=["asset-1"],
            data_role="evaluation",
            sampling_context="pre-transplant",
        )
    with pytest.raises(ValidationError, match="must be nonblank"):
        PlanStep(
            step_id="step-p0-01",
            tool_id="P0-01",
            tool_version="0.1.0",
            disposition="skip",
            reason_codes=[""],
        )
    with pytest.raises(ValidationError, match="must be nonblank"):
        PlanStep(
            step_id="step-p0-01",
            tool_id="P0-01",
            tool_version="0.1.0",
            disposition="skip",
            reference_refs=["   "],
            reason_codes=["input_missing"],
        )
    with pytest.raises(ValidationError, match="nonblank"):
        SampleRecord(
            sample_id="   ",
            preparation_id="prep-1",
            asset_ids=["asset-1"],
            data_role="evaluation",
            sampling_context="pre-transplant",
        )
    with pytest.raises(ValidationError, match="asset ids must be nonblank"):
        SampleRecord(
            sample_id="sample-1",
            preparation_id="prep-1",
            asset_ids=["   "],
            data_role="evaluation",
            sampling_context="pre-transplant",
        )


def test_plan_collections_are_immutable_snapshots() -> None:
    dependencies = ["step-p0-01"]
    step = PlanStep(
        step_id="step-p0-02",
        tool_id="P0-02",
        tool_version="0.1.0",
        disposition="skip",
        depends_on=dependencies,
        reference_refs=["reference://v1"],
        reason_codes=["measurement_spec_not_selected"],
    )
    dependencies.append("step-p0-99")

    assert step.depends_on == ("step-p0-01",)
    assert isinstance(step.reference_refs, tuple)


def test_product_case_defensively_freezes_nested_asset_metadata(tmp_path: Path) -> None:
    source_metadata = {"nested": {"labels": ["approved"]}}
    asset = _asset(tmp_path).model_copy(update={"metadata": source_metadata})
    case = ProductCase(
        case_id="case-1",
        version="0.1",
        status="confirmed",
        product_type="product",
        target_cell_type="target",
        differentiation_stage="D16",
        intended_use="research",
        assay="scRNA-seq",
        product_definition_card_ref="card://pd/v0.1",
        reference_policy_ref="reference://policy/v0.1",
        prior_snapshot_ref="prior://snapshot/v0.1",
        assets=[asset],
        samples=[
            SampleRecord(
                sample_id="sample-1",
                preparation_id="prep-1",
                asset_ids=["asset-1"],
                data_role="evaluation",
                sampling_context="pre-transplant",
            )
        ],
    )

    source_metadata["nested"]["labels"].append("mutated")
    assert case.model_dump(mode="json")["assets"][0]["metadata"] == {
        "nested": {"labels": ["approved"]}
    }
    with pytest.raises(TypeError):
        case.assets[0].metadata["nested"]["labels"] += ("mutated",)


from pathlib import Path
import hashlib
import json

from bridge.domain.models import ProductCase, SampleRecord
from bridge.planner.service import PlanBuilder
from bridge.toolkit.contracts import EligibilityResult, InputAsset, StructuredInputRef
from bridge.toolkit.registry import ToolRegistry


def _case(
    tmp_path: Path, *, status: str = "confirmed", asset_count: int = 1
) -> ProductCase:
    assets = []
    for index in range(asset_count):
        asset_path = tmp_path / f"product-{index + 1}.h5ad"
        asset_path.touch()
        assets.append(
            InputAsset(
                asset_id=f"asset-{index + 1}",
                path=asset_path.resolve(),
                format="h5ad",
                input_level="analysis_ready",
                matrix_semantics="normalized_expression",
                assay="scRNA-seq",
            )
        )
    return ProductCase(
        case_id="case-1",
        version="0.1",
        status=status,
        product_type="mDA progenitor preparation",
        target_cell_type="midbrain dopaminergic progenitor",
        differentiation_stage="D16",
        intended_use="research evaluation",
        assay="scRNA-seq",
        product_definition_card_ref="card://pd-mda/v0.1",
        reference_policy_ref="reference-policy://pd-mda/v0.1",
        prior_snapshot_ref="prior://pd-mda/v0.1",
        assets=assets,
        samples=[
            SampleRecord(
                sample_id="sample-1",
                preparation_id="prep-1",
                asset_ids=[asset.asset_id for asset in assets],
                data_role="evaluation",
                sampling_context="pre-transplant",
            )
        ],
    )


def test_plan_builder_is_deterministic_and_keeps_scaffolds_skipped(tmp_path: Path) -> None:
    builder = PlanBuilder()
    case = _case(tmp_path)

    first = builder.build(
        case,
        output_root=tmp_path / "runs",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
    )
    second = builder.build(
        case,
        output_root=tmp_path / "runs",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
    )

    assert first == second
    assert first.steps[0].tool_id == "P0-01"
    assert first.steps[0].disposition == "execute"
    assert first.steps[2].disposition == "skip"
    assert first.steps[2].reason_codes == ("upstream_step_not_executable",)
    assert first.steps[-1].tool_id == "P0-12"


def test_plan_builder_rejects_unconfirmed_case(tmp_path: Path) -> None:
    try:
        PlanBuilder().build(
            _case(tmp_path, status="draft"),
            output_root=tmp_path / "runs",
            knowledge_snapshot_ref="knowledge://p0/2026-08-12",
        )
    except ValueError as exc:
        assert str(exc) == "case_not_confirmed"
    else:
        raise AssertionError("draft case unexpectedly produced a plan")


def test_plan_builder_uses_safe_hashed_case_key_for_paths_and_request_ids(
    tmp_path: Path,
) -> None:
    payload = _case(tmp_path).model_dump(mode="python")
    payload["case_id"] = "../escaped/病例 🧬"
    case = ProductCase.model_validate(payload)
    output_root = (tmp_path / "runs").resolve()

    plan = PlanBuilder().build(
        case,
        output_root=output_root,
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
    )

    request_payloads = [
        json.loads(step.approved_request_json)
        for step in plan.steps
        if step.approved_request_json is not None
    ]
    assert request_payloads
    for request in request_payloads:
        assert Path(request["output_dir"]).resolve().is_relative_to(output_root)
        assert case.case_id not in request["request_id"]
    assert not (tmp_path / "escaped").exists()


def test_plan_builder_expands_input_qc_per_asset_without_collapsing_steps(
    tmp_path: Path,
) -> None:
    plan = PlanBuilder().build(
        _case(tmp_path, asset_count=2),
        output_root=tmp_path / "runs",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
    )

    qc_steps = [step for step in plan.steps if step.tool_id == "P0-01"]
    assert [step.step_id for step in qc_steps] == [
        "step-p0-01-asset-001",
        "step-p0-01-asset-002",
    ]
    requests = [json.loads(step.approved_request_json or "{}") for step in qc_steps]
    assert [[asset["asset_id"] for asset in item["assets"]] for item in requests] == [
        ["asset-1"],
        ["asset-2"],
    ]


class _StructuredPlanningRegistry:
    def __init__(self) -> None:
        self._delegate = ToolRegistry.load_default()

    def list(self):
        return self._delegate.list()

    def check_eligibility(self, request):
        if request.tool_id == "P0-08":
            return EligibilityResult(tool_id=request.tool_id, eligible=True)
        return self._delegate.check_eligibility(request)

    def check_case_eligibility(self, request, *, case_id, case_version):
        if request.tool_id == "P0-08":
            return EligibilityResult(tool_id=request.tool_id, eligible=True)
        return self._delegate.check_case_eligibility(
            request,
            case_id=case_id,
            case_version=case_version,
        )


def test_structured_tool_requires_explicit_inputs_and_is_not_blocked_by_scaffolds(
    tmp_path: Path,
) -> None:
    structured_path = (tmp_path / "gate.json").resolve()
    structured_path.write_text("{}", encoding="utf-8")
    structured = StructuredInputRef(
        input_id="gate-1",
        role="gate_rule_spec",
        schema_ref="bridge://schemas/evidence-gate-rule-spec/v0.1",
        object_version="0.1",
        path=structured_path,
        sha256=hashlib.sha256(b"{}").hexdigest(),
    )
    builder = PlanBuilder(_StructuredPlanningRegistry())

    missing = builder.build(
        _case(tmp_path),
        output_root=tmp_path / "runs-missing",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
    )
    supplied = builder.build(
        _case(tmp_path),
        output_root=tmp_path / "runs-supplied",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
        structured_input_bindings={"P0-08": [structured]},
    )

    missing_step = next(step for step in missing.steps if step.tool_id == "P0-08")
    supplied_step = next(step for step in supplied.steps if step.tool_id == "P0-08")
    assert missing_step.reason_codes == ("structured_inputs_not_selected",)
    assert supplied_step.disposition == "execute"
    assert supplied_step.depends_on == ()
    assert json.loads(supplied_step.approved_request_json or "{}")["object_inputs"][0][
        "input_id"
    ] == "gate-1"


def _p0_08_case_binding_refs(
    tmp_path: Path,
    *,
    product_case_id: str | None,
    product_case_version: str = "0.1",
) -> list[StructuredInputRef]:
    gate_bytes = (
        files("bridge.tool_packages.p0_08_evidence_sufficiency.resources")
        .joinpath("gate_rule_spec_v0.2.json")
        .read_bytes()
    )
    gate_path = (tmp_path / "gate-rules.json").resolve()
    gate_path.write_bytes(gate_bytes)
    domain_payload = {
        "domain_gate_input_id": "domain-gate-input:case-binding:target-identity",
        "object_version": "0.1.0",
        "created_at": "2026-08-13T00:00:00Z",
        "product_case": (
            {
                "object_id": product_case_id,
                "object_version": product_case_version,
                "provenance_refs": ["provenance:case-binding"],
            }
            if product_case_id is not None
            else None
        ),
        "product_definition": None,
        "domain_id": "target_identity",
        "method_requirement": "not_assessed",
        "prior_requirement": "not_assessed",
        "task_validation_state": "not_assessed",
        "provenance_refs": ["run:case-binding"],
    }
    domain_bytes = json.dumps(domain_payload, separators=(",", ":")).encode()
    domain_path = (tmp_path / "domain.json").resolve()
    domain_path.write_bytes(domain_bytes)
    return [
        StructuredInputRef(
            input_id="gate-rules",
            role="gate_rule_spec",
            schema_ref="bridge://schemas/evidence-sufficiency-gate-rule-spec/v0.2",
            object_version="0.2.0",
            path=gate_path,
            sha256=hashlib.sha256(gate_bytes).hexdigest(),
        ),
        StructuredInputRef(
            input_id="target-domain",
            role="domain_gate_input",
            schema_ref="bridge://schemas/domain-gate-input/v0.1",
            object_version="0.1.0",
            path=domain_path,
            sha256=hashlib.sha256(domain_bytes).hexdigest(),
        ),
    ]


@pytest.mark.parametrize(
    ("product_case_id", "product_case_version", "reason_code"),
    [
        ("foreign-case", "0.1", "approved_product_case_binding_mismatch"),
        ("case-1", "9.9", "approved_product_case_binding_mismatch"),
        (None, "0.1", "approved_product_case_binding_missing"),
    ],
)
def test_default_registry_rejects_foreign_or_unbound_p0_08_case_inputs(
    tmp_path: Path,
    product_case_id: str | None,
    product_case_version: str,
    reason_code: str,
) -> None:
    registry = ToolRegistry.load_default()
    request = ToolRequestV2(
        request_id="request-case-binding",
        tool_id="P0-08",
        tool_version=registry.describe("P0-08").version,
        output_dir=(tmp_path / "output").resolve(),
        object_inputs=_p0_08_case_binding_refs(
            tmp_path,
            product_case_id=product_case_id,
            product_case_version=product_case_version,
        ),
    )

    result = registry.check_case_eligibility(
        request,
        case_id="case-1",
        case_version="0.1",
    )

    assert result.eligible is False
    assert reason_code in result.reason_codes


def test_default_registry_uses_exact_canonical_p0_08_case_identity(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    request = ToolRequestV2(
        request_id="request-case-binding-match",
        tool_id="P0-08",
        tool_version=registry.describe("P0-08").version,
        output_dir=(tmp_path / "output").resolve(),
        object_inputs=_p0_08_case_binding_refs(
            tmp_path,
            product_case_id="case-1",
        ),
    )

    result = registry.check_case_eligibility(
        request,
        case_id="case-1",
        case_version="0.1",
    )

    assert "approved_product_case_binding_missing" not in result.reason_codes
    assert "approved_product_case_binding_mismatch" not in result.reason_codes


def test_default_registry_rejects_mixed_p0_08_case_bindings(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    refs = _p0_08_case_binding_refs(
        tmp_path,
        product_case_id="case-1",
    )
    second_payload = json.loads(refs[1].path.read_text(encoding="utf-8"))
    second_payload["domain_gate_input_id"] = (
        "domain-gate-input:case-binding:regional-fidelity"
    )
    second_payload["domain_id"] = "regional_fidelity"
    second_payload["product_case"]["object_id"] = "foreign-case"
    second_bytes = json.dumps(second_payload, separators=(",", ":")).encode()
    second_path = (tmp_path / "domain-2.json").resolve()
    second_path.write_bytes(second_bytes)
    refs.append(
        StructuredInputRef(
            input_id="regional-domain",
            role="domain_gate_input",
            schema_ref="bridge://schemas/domain-gate-input/v0.1",
            object_version="0.1.0",
            path=second_path,
            sha256=hashlib.sha256(second_bytes).hexdigest(),
        )
    )
    request = ToolRequestV2(
        request_id="request-case-binding-mixed",
        tool_id="P0-08",
        tool_version=registry.describe("P0-08").version,
        output_dir=(tmp_path / "output").resolve(),
        object_inputs=refs,
    )

    result = registry.check_case_eligibility(
        request,
        case_id="case-1",
        case_version="0.1",
    )

    assert "approved_product_case_binding_mismatch" in result.reason_codes


def test_p0_09_comparison_bundle_has_no_implicit_product_case_binding(
    tmp_path: Path,
) -> None:
    from bridge.tool_packages._structured_runtime import LoadedInputs
    from bridge.tool_packages.p0_09_evidence_compiler.adapter import (
        _approved_case_binding_reasons,
    )
    from bridge.tool_packages.p0_09_evidence_compiler.models import (
        EvidenceCompilationBundle,
        GraphKind,
    )

    bundle_ref = StructuredInputRef(
        input_id="bundle",
        role="compilation_bundle",
        schema_ref="bridge://schemas/evidence-compilation-bundle/v0.1",
        object_version="0.1.0",
        path=(tmp_path / "comparison.json").resolve(),
        sha256="a" * 64,
    )
    request = ToolRequestV2(
        request_id="comparison-request",
        tool_id="P0-09",
        tool_version="0.2.0",
        output_dir=(tmp_path / "output").resolve(),
        object_inputs=[bundle_ref],
    )
    comparison = EvidenceCompilationBundle.model_construct(
        graph_kind=GraphKind.COMPARISON,
        product_case_ref=None,
    )
    loaded = LoadedInputs(
        objects_by_input_id={"bundle": comparison},
        bytes_by_input_id={},
    )

    assert _approved_case_binding_reasons(
        request,
        loaded,
        ("case-1", "0.1"),
    ) == ["approved_product_case_binding_missing"]


from pathlib import Path
import hashlib
import json

import pytest

from bridge.domain.models import AnalysisPlan, PlanStep
from bridge.runners.pipeline import (
    ToolExecutionDenied,
    ToolExecutionPipeline,
    ToolExecutionScope,
)
from bridge.toolkit.contracts import (
    EligibilityResult,
    ExecutionState,
    ImplementationState,
    ToolPackageSpec,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
    ToolRun,
    ToolRunV2,
)


class FakeRegistry:
    def __init__(self, *, eligible: bool = True) -> None:
        self.eligible = eligible
        self.checked = 0
        self.ran = 0
        self.spec = ToolPackageSpec(
            tool_id="P0-01",
            name="Input Audit & QC",
            version="0.1.0",
            summary="Fake executable contract.",
            implementation_state="implemented",
            scientific_status="candidate",
            environment_spec_id="ENV-P0-CORE-v0.1",
            input_schema_ref="bridge://schemas/tool-request/v0.1",
            output_schema_ref="bridge://schemas/tool-run/v0.1",
            method_ids=["METHOD-FAKE"],
            card_ref="bridge://tool-cards/P0-01",
        )

    def describe(self, tool_id: str) -> ToolPackageSpec:
        assert tool_id == "P0-01"
        return self.spec

    def check_eligibility(self, request: ToolRequest) -> EligibilityResult:
        self.checked += 1
        return EligibilityResult(
            tool_id=request.tool_id,
            eligible=self.eligible,
            reason_codes=[] if self.eligible else ["synthetic_input_ineligible"],
        )

    def check_case_eligibility(
        self, request: ToolRequest, *, case_id: str, case_version: str
    ) -> EligibilityResult:
        return self.check_eligibility(request)

    def run(self, request: ToolRequest) -> ToolRun:
        self.ran += 1
        return ToolRun(
            run_id="tool-run-1",
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=ExecutionState.SUCCEEDED,
            tool_version="0.1.0",
            environment_spec_id="ENV-P0-CORE-v0.1",
        )

    def validate_result(self, result: object, request: ToolRequest) -> ToolRun:
        return ToolRegistry.validate_result(self, result, request)


def _request(tmp_path: Path, **updates) -> ToolRequest:
    payload = {
        "request_id": "request-1",
        "tool_id": "P0-01",
        "tool_version": "0.1.0",
        "output_dir": (tmp_path / "outputs").resolve(),
    }
    payload.update(updates)
    return ToolRequest(**payload)


def _canonical_request(request: ToolRequest) -> str:
    return json.dumps(
        request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )


def _scope(
    tmp_path: Path,
    *,
    network_required: bool = False,
    high_resource_required: bool = False,
) -> ToolExecutionScope:
    request = _request(tmp_path)
    plan = AnalysisPlan(
        plan_id="plan-1",
        version="0.1",
        case_ref="case-1@0.1",
        case_id="case-1",
        case_version="0.1",
        case_contract_sha256=hashlib.sha256(b"case-1@0.1").hexdigest(),
        status="approved",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
        network_required=network_required,
        high_resource_required=high_resource_required,
        steps=[
            PlanStep(
                step_id="step-p0-01",
                tool_id="P0-01",
                tool_version="0.1.0",
                disposition="execute",
                measurement_spec_ref=None,
                reference_refs=["reference-policy://pd-mda/v0.1"],
                prior_refs=["prior://pd-mda/v0.1"],
                approved_request_json=_canonical_request(request),
                environment_spec_id="ENV-P0-CORE-v0.1",
                input_schema_ref="bridge://schemas/tool-request/v0.1",
                output_schema_ref="bridge://schemas/tool-run/v0.1",
                implementation_state="implemented",
            ),
            PlanStep(
                step_id="step-p0-03",
                tool_id="P0-03",
                tool_version="0.1.0",
                disposition="skip",
                reason_codes=["tool_package_not_implemented"],
            ),
        ],
    )
    return ToolExecutionScope.from_plan(plan)


def test_pipeline_executes_only_after_all_gates(tmp_path: Path) -> None:
    registry = FakeRegistry()
    outcome = ToolExecutionPipeline(_scope(tmp_path), registry).execute(_request(tmp_path))

    assert outcome.execution_state == "succeeded"
    assert registry.checked == 1
    assert registry.ran == 1


def test_pipeline_rejects_tool_outside_approved_plan_before_registry(tmp_path: Path) -> None:
    registry = FakeRegistry()

    with pytest.raises(ToolExecutionDenied, match="tool_not_in_approved_plan"):
        ToolExecutionPipeline(_scope(tmp_path), registry).execute(
            _request(tmp_path, tool_id="P0-03")
        )

    assert registry.checked == 0
    assert registry.ran == 0


def test_pipeline_rejects_version_mismatch_before_registry(tmp_path: Path) -> None:
    registry = FakeRegistry()

    with pytest.raises(ToolExecutionDenied, match="approved_tool_version_mismatch"):
        ToolExecutionPipeline(_scope(tmp_path), registry).execute(
            _request(tmp_path, tool_version="9.9.9")
        )

    assert registry.checked == 0
    assert registry.ran == 0


def test_pipeline_does_not_run_ineligible_tool(tmp_path: Path) -> None:
    registry = FakeRegistry(eligible=False)

    with pytest.raises(ToolExecutionDenied, match="synthetic_input_ineligible"):
        ToolExecutionPipeline(_scope(tmp_path), registry).execute(_request(tmp_path))

    assert registry.checked == 1
    assert registry.ran == 0


@pytest.mark.parametrize(
    ("scope_updates", "reason_code"),
    [
        ({"network_required": True}, "network_capability_not_granted"),
        ({"high_resource_required": True}, "high_resource_capability_not_granted"),
    ],
)
def test_pipeline_requires_explicit_runtime_capability_grants(
    tmp_path: Path, scope_updates: dict, reason_code: str
) -> None:
    registry = FakeRegistry()

    with pytest.raises(ToolExecutionDenied, match=reason_code):
        ToolExecutionPipeline(_scope(tmp_path, **scope_updates), registry).execute(
            _request(tmp_path)
        )

    assert registry.checked == 0
    assert registry.ran == 0


@pytest.mark.parametrize(
    "updates",
    [
        {"request_id": "case-b-request"},
        {"output_dir": Path("/tmp/case-b-output")},
        {"parameters": {"case_id": "case-b"}},
    ],
)
def test_pipeline_rejects_any_unapproved_request_field(
    tmp_path: Path, updates: dict
) -> None:
    registry = FakeRegistry()

    with pytest.raises(ToolExecutionDenied, match="approved_request_mismatch"):
        ToolExecutionPipeline(_scope(tmp_path), registry).execute(
            _request(tmp_path, **updates)
        )

    assert registry.checked == 0
    assert registry.ran == 0


def test_scope_rejects_legacy_approved_plan_without_case_binding() -> None:
    plan = AnalysisPlan(
        plan_id="legacy-plan",
        version="0.1",
        case_ref="case-1@0.1",
        status="approved",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
        steps=[
            PlanStep(
                step_id="step-p0-01",
                tool_id="P0-01",
                tool_version="0.1.0",
                disposition="execute",
            )
        ],
    )

    with pytest.raises(ValueError, match="missing_case_contract"):
        ToolExecutionScope.from_plan(plan)


def test_externally_constructed_scope_cannot_approve_foreign_case_evidence(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    spec = registry.describe("P0-08")
    assert isinstance(spec, ToolPackageSpecV2)
    request = ToolRequestV2(
        request_id="foreign-case-request",
        tool_id="P0-08",
        tool_version=spec.version,
        output_dir=(tmp_path / "outputs").resolve(),
        object_inputs=_p0_08_case_binding_refs(
            tmp_path,
            product_case_id="foreign-case",
        ),
    )
    plan = AnalysisPlan(
        plan_id="external-plan",
        version="0.2",
        case_ref="case-1@0.1",
        case_id="case-1",
        case_version="0.1",
        case_contract_sha256=hashlib.sha256(b"case-1").hexdigest(),
        status="approved",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
        steps=[
            PlanStep(
                step_id="step-p0-08",
                tool_id="P0-08",
                tool_version=spec.version,
                disposition="execute",
                approved_request_json=json.dumps(
                    request.model_dump(mode="json"),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                reference_refs=["reference://policy/v0.1"],
                prior_refs=["prior://snapshot/v0.1"],
                environment_spec_id=spec.environment_spec_id,
                input_schema_ref=spec.input_schema_ref,
                output_schema_ref=spec.output_schema_ref,
                implementation_state=spec.implementation_state.value,
                result_schema_ref=spec.result_schema_ref,
            )
        ],
    )

    with pytest.raises(
        ToolExecutionDenied,
        match="approved_product_case_binding_mismatch",
    ):
        ToolExecutionPipeline(ToolExecutionScope.from_plan(plan), registry).execute(
            request
        )


class FakeV2Registry:
    def __init__(
        self,
        *,
        outcome_environment: str = "ENV-EVIDENCE-v0.1",
        result: dict | None = None,
    ) -> None:
        self.outcome_environment = outcome_environment
        self.result = result or {
            "tool_id": "P0-08",
            "eligible": True,
            "reason_codes": [],
            "warnings": [],
        }
        self.spec = ToolPackageSpecV2(
            tool_id="P0-08",
            name="Evidence Sufficiency",
            version="0.2.0",
            summary="Fake structured contract.",
            implementation_state="implemented",
            scientific_status="candidate",
            environment_spec_id="ENV-EVIDENCE-v0.1",
            input_schema_ref="bridge://schemas/tool-request/v0.2",
            output_schema_ref="bridge://schemas/tool-run/v0.2",
            result_schema_ref=RESULT_SCHEMA_REF,
            adapter_ref="bridge.tool_packages.p0_08_evidence_sufficiency.adapter:adapter",
            method_ids=["METHOD-FAKE"],
            card_ref="bridge://tool-cards/P0-08",
        )

    def describe(self, tool_id: str) -> ToolPackageSpecV2:
        assert tool_id == "P0-08"
        return self.spec

    def check_eligibility(self, request: ToolRequestV2) -> EligibilityResult:
        return EligibilityResult(tool_id=request.tool_id, eligible=True)

    def check_case_eligibility(
        self, request: ToolRequestV2, *, case_id: str, case_version: str
    ) -> EligibilityResult:
        return self.check_eligibility(request)

    def run(self, request: ToolRequestV2) -> ToolRunV2:
        return ToolRunV2(
            run_id="tool-run-v2",
            request=request,
            implementation_state="implemented",
            execution_state="succeeded",
            tool_version="0.2.0",
            environment_spec_id=self.outcome_environment,
            result_schema_ref=self.spec.result_schema_ref,
            result=self.result,
        )

    def validate_result(self, result: object, request: ToolRequestV2) -> ToolRunV2:
        return ToolRegistry.validate_result(self, result, request)


def _v2_request(tmp_path: Path) -> ToolRequestV2:
    return ToolRequestV2(
        request_id="request-v2",
        tool_id="P0-08",
        tool_version="0.2.0",
        output_dir=(tmp_path / "v2-outputs").resolve(),
    )


def _v2_scope(tmp_path: Path) -> ToolExecutionScope:
    request = _v2_request(tmp_path)
    plan = AnalysisPlan(
        plan_id="plan-v2",
        version="0.2",
        case_ref="case-1@0.1",
        case_id="case-1",
        case_version="0.1",
        case_contract_sha256=hashlib.sha256(b"case-1@0.1").hexdigest(),
        status="approved",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
        steps=[
            PlanStep(
                step_id="step-p0-08",
                tool_id="P0-08",
                tool_version="0.2.0",
                disposition="execute",
                approved_request_json=json.dumps(
                    request.model_dump(mode="json"),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                reference_refs=["reference-policy://pd-mda/v0.1"],
                prior_refs=["prior://pd-mda/v0.1"],
                environment_spec_id="ENV-EVIDENCE-v0.1",
                input_schema_ref="bridge://schemas/tool-request/v0.2",
                output_schema_ref="bridge://schemas/tool-run/v0.2",
                implementation_state="implemented",
                result_schema_ref=(
                    RESULT_SCHEMA_REF
                ),
            )
        ],
    )
    return ToolExecutionScope.from_plan(plan)


def test_pipeline_preserves_registry_selected_v2_contract(tmp_path: Path) -> None:
    outcome = ToolExecutionPipeline(
        _v2_scope(tmp_path), FakeV2Registry()
    ).execute(_v2_request(tmp_path))

    assert isinstance(outcome, ToolRunV2)
    assert isinstance(outcome.request, ToolRequestV2)


def test_pipeline_rejects_result_environment_drift(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="tool_outcome_contract_mismatch"):
        ToolExecutionPipeline(
            _v2_scope(tmp_path),
            FakeV2Registry(outcome_environment="ENV-UNAPPROVED"),
        ).execute(_v2_request(tmp_path))


def test_pipeline_rejects_v2_result_that_violates_registered_schema(
    tmp_path: Path,
) -> None:
    with pytest.raises(RuntimeError, match="tool_outcome_contract_mismatch"):
        ToolExecutionPipeline(
            _v2_scope(tmp_path),
            FakeV2Registry(result={"tool_id": "P0-08"}),
        ).execute(_v2_request(tmp_path))


from pathlib import Path

import pytest

from bridge.domain.models import AnalysisPlan, PlanStep
from bridge.workflow.event_store import SQLiteRunEventStore
from bridge.workflow.executor import LocalWorkflowExecutor


def _approved_plan() -> AnalysisPlan:
    return AnalysisPlan(
        plan_id="plan-1",
        version="0.1",
        case_ref="case-1@0.1",
        status="approved",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
        steps=[
            PlanStep(
                step_id="step-p0-01",
                tool_id="P0-01",
                tool_version="0.1.0",
                disposition="execute",
            ),
            PlanStep(
                step_id="step-p0-02",
                tool_id="P0-02",
                tool_version="0.1.0",
                disposition="execute",
                depends_on=["step-p0-01"],
            ),
            PlanStep(
                step_id="step-p0-03",
                tool_id="P0-03",
                tool_version="0.1.0",
                disposition="skip",
                depends_on=["step-p0-02"],
                reason_codes=["tool_package_not_implemented"],
            ),
        ],
    )


def test_executor_claims_dependencies_in_order() -> None:
    executor = LocalWorkflowExecutor()
    run_id = executor.submit(_approved_plan())

    first = executor.claim_step(run_id)
    assert first is not None and first.step_id == "step-p0-01"
    assert executor.claim_step(run_id) is None

    executor.complete_step(run_id, first.step_id, succeeded=True)
    second = executor.claim_step(run_id)
    assert second is not None and second.step_id == "step-p0-02"
    executor.complete_step(run_id, second.step_id, succeeded=True)

    snapshot = executor.get_status(run_id)
    assert snapshot.status == "succeeded"
    assert [step.status for step in snapshot.steps] == ["succeeded", "succeeded", "skipped"]


def test_executor_resumes_failed_step_without_rerunning_success() -> None:
    executor = LocalWorkflowExecutor(max_attempts=2)
    run_id = executor.submit(_approved_plan())
    first = executor.claim_step(run_id)
    assert first is not None
    executor.complete_step(run_id, first.step_id, succeeded=True)
    second = executor.claim_step(run_id)
    assert second is not None
    executor.complete_step(
        run_id,
        second.step_id,
        succeeded=False,
        reason_codes=["transient_subprocess_failure"],
    )

    executor.resume(run_id)
    retried = executor.claim_step(run_id)
    assert retried is not None and retried.step_id == second.step_id
    snapshot = executor.get_status(run_id)
    assert snapshot.steps[0].attempts == 1
    assert snapshot.steps[1].attempts == 2

    executor.complete_step(
        run_id,
        retried.step_id,
        succeeded=False,
        reason_codes=["transient_subprocess_failure"],
    )
    with pytest.raises(ValueError, match="retry_limit_reached"):
        executor.resume(run_id)


def test_retry_exhaustion_blocks_descendants_but_runs_independent_steps() -> None:
    plan = AnalysisPlan(
        plan_id="plan-branches",
        version="0.1",
        case_ref="case-1@0.1",
        status="approved",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
        steps=[
            PlanStep(
                step_id="failed-root",
                tool_id="P0-01",
                tool_version="0.1.0",
                disposition="execute",
            ),
            PlanStep(
                step_id="blocked-child",
                tool_id="P0-02",
                tool_version="0.1.0",
                disposition="execute",
                depends_on=["failed-root"],
            ),
            PlanStep(
                step_id="blocked-grandchild",
                tool_id="P0-03",
                tool_version="0.1.0",
                disposition="execute",
                depends_on=["blocked-child"],
            ),
            PlanStep(
                step_id="independent",
                tool_id="P0-04",
                tool_version="0.1.0",
                disposition="execute",
            ),
        ],
    )
    executor = LocalWorkflowExecutor(max_attempts=1)
    run_id = executor.submit(plan)
    failed = executor.claim_step(run_id)
    assert failed is not None and failed.step_id == "failed-root"
    executor.complete_step(
        run_id,
        failed.step_id,
        succeeded=False,
        reason_codes=["permanent_failure"],
    )

    partial = executor.get_status(run_id)
    assert partial.status == "partial"
    assert [step.status for step in partial.steps] == [
        "failed",
        "skipped",
        "skipped",
        "pending",
    ]
    assert partial.steps[1].reason_codes == ["upstream_step_retry_exhausted"]

    independent = executor.claim_step(run_id)
    assert independent is not None and independent.step_id == "independent"
    executor.complete_step(run_id, independent.step_id, succeeded=True)
    assert executor.get_status(run_id).status == "failed"


def test_failure_requires_reason_and_terminal_failure_cannot_be_cancelled() -> None:
    executor = LocalWorkflowExecutor(max_attempts=1)
    run_id = executor.submit(_approved_plan())
    claimed = executor.claim_step(run_id)
    assert claimed is not None
    with pytest.raises(ValueError, match="failure_requires_reason_codes"):
        executor.complete_step(run_id, claimed.step_id, succeeded=False)

    executor.complete_step(
        run_id,
        claimed.step_id,
        succeeded=False,
        reason_codes=["permanent_failure"],
    )
    executor.cancel(run_id)
    assert executor.get_status(run_id).status == "failed"


def test_executor_rejects_draft_plan() -> None:
    draft = _approved_plan().model_copy(update={"status": "draft"})
    with pytest.raises(ValueError, match="not_approved"):
        LocalWorkflowExecutor().submit(draft)


def test_sqlite_executor_recovers_an_interrupted_step(tmp_path: Path) -> None:
    database_path = tmp_path / "workflow.sqlite3"
    first_process = LocalWorkflowExecutor(SQLiteRunEventStore(database_path))
    run_id = first_process.submit(_approved_plan())
    claimed = first_process.claim_step(run_id)
    assert claimed is not None and claimed.step_id == "step-p0-01"

    restarted_process = LocalWorkflowExecutor(SQLiteRunEventStore(database_path))
    assert restarted_process.get_status(run_id).status == "running"
    restarted_process.resume(run_id)
    reclaimed = restarted_process.claim_step(run_id)

    assert reclaimed is not None and reclaimed.step_id == "step-p0-01"
    assert restarted_process.get_status(run_id).steps[0].attempts == 2


def test_sqlite_restart_preserves_retry_exhaustion_terminalization(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "workflow.sqlite3"
    first_process = LocalWorkflowExecutor(
        SQLiteRunEventStore(database_path), max_attempts=1
    )
    run_id = first_process.submit(_approved_plan())
    claimed = first_process.claim_step(run_id)
    assert claimed is not None
    first_process.complete_step(
        run_id,
        claimed.step_id,
        succeeded=False,
        reason_codes=["permanent_failure"],
    )

    restarted_process = LocalWorkflowExecutor(
        SQLiteRunEventStore(database_path), max_attempts=1
    )
    snapshot = restarted_process.get_status(run_id)
    assert snapshot.status == "failed"
    assert [step.status for step in snapshot.steps] == ["failed", "skipped", "skipped"]
    assert snapshot.steps[1].reason_codes == ["upstream_step_retry_exhausted"]


def test_sqlite_recovery_terminalizes_interrupted_final_attempt_atomically(
    tmp_path: Path,
) -> None:
    plan = AnalysisPlan(
        plan_id="plan-interrupted-branches",
        version="0.1",
        case_ref="case-1@0.1",
        status="approved",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
        steps=[
            PlanStep(
                step_id="interrupted-root",
                tool_id="P0-01",
                tool_version="0.1.0",
                disposition="execute",
            ),
            PlanStep(
                step_id="blocked-child",
                tool_id="P0-02",
                tool_version="0.1.0",
                disposition="execute",
                depends_on=["interrupted-root"],
            ),
            PlanStep(
                step_id="independent",
                tool_id="P0-04",
                tool_version="0.1.0",
                disposition="execute",
            ),
        ],
    )
    database_path = tmp_path / "workflow.sqlite3"
    first_process = LocalWorkflowExecutor(
        SQLiteRunEventStore(database_path), max_attempts=1
    )
    run_id = first_process.submit(plan)
    assert first_process.claim_step(run_id).step_id == "interrupted-root"  # type: ignore[union-attr]

    # Constructor drift cannot change the retry policy persisted by submit.
    restarted_process = LocalWorkflowExecutor(
        SQLiteRunEventStore(database_path), max_attempts=99
    )
    restarted_process.resume(run_id)

    snapshot = restarted_process.get_status(run_id)
    assert snapshot.status == "partial"
    assert [step.status for step in snapshot.steps] == [
        "failed",
        "skipped",
        "pending",
    ]
    assert snapshot.steps[0].reason_codes == [
        "worker_interrupted_retry_exhausted"
    ]
    assert snapshot.steps[1].reason_codes == ["upstream_step_retry_exhausted"]
    events = SQLiteRunEventStore(database_path).load(run_id)
    assert events[0].payload.max_attempts == 1  # type: ignore[union-attr]
    assert events[-1].event_type == "run_recovered"
    assert events[-1].sequence == 3

    independent = restarted_process.claim_step(run_id)
    assert independent is not None and independent.step_id == "independent"
    restarted_process.complete_step(run_id, independent.step_id, succeeded=True)
    assert restarted_process.get_status(run_id).status == "failed"


@pytest.mark.parametrize("store_kind", ["memory", "sqlite"])
def test_recovery_handles_every_interrupted_step_with_store_parity(
    tmp_path: Path, store_kind: str
) -> None:
    store = (
        InMemoryRunEventStore()
        if store_kind == "memory"
        else SQLiteRunEventStore(tmp_path / "workflow.sqlite3")
    )
    run_id = "run-two-interruptions"
    plan = AnalysisPlan(
        plan_id="plan-two-interruptions",
        version="0.1",
        case_ref="case-1@0.1",
        status="approved",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
        steps=[
            PlanStep(
                step_id="first",
                tool_id="P0-01",
                tool_version="0.1.0",
                disposition="execute",
            ),
            PlanStep(
                step_id="second",
                tool_id="P0-02",
                tool_version="0.1.0",
                disposition="execute",
            ),
        ],
    )
    store.append(
        run_id,
        "run_submitted",
        {"plan": plan.model_dump(mode="json"), "max_attempts": 2},
        expected_sequence=0,
    )
    store.append(
        run_id, "step_claimed", {"step_id": "first"}, expected_sequence=1
    )
    store.append(
        run_id, "step_claimed", {"step_id": "second"}, expected_sequence=2
    )

    executor = LocalWorkflowExecutor(store, max_attempts=7)
    executor.resume(run_id)

    snapshot = executor.get_status(run_id)
    assert [step.status for step in snapshot.steps] == ["pending", "pending"]
    assert [step.attempts for step in snapshot.steps] == [1, 1]
    recovered = store.load(run_id)[-1]
    assert recovered.event_type == "run_recovered"
    assert [
        step.step_id for step in recovered.payload.recovered_steps  # type: ignore[union-attr]
    ] == ["first", "second"]


def test_concurrent_sqlite_recovery_has_one_sequence_winner(tmp_path: Path) -> None:
    from threading import Barrier, Thread

    database_path = tmp_path / "workflow.sqlite3"
    base_store = SQLiteRunEventStore(database_path)
    first_process = LocalWorkflowExecutor(base_store, max_attempts=2)
    run_id = first_process.submit(_approved_plan())
    assert first_process.claim_step(run_id) is not None
    barrier = Barrier(2)

    class SynchronizedLoadStore:
        def append(self, *args, **kwargs):
            return base_store.append(*args, **kwargs)

        def load(self, loaded_run_id: str):
            events = base_store.load(loaded_run_id)
            barrier.wait(timeout=5)
            return events

    results: list[str] = []

    def recover() -> None:
        try:
            LocalWorkflowExecutor(SynchronizedLoadStore()).resume(run_id)
        except EventSequenceConflict:
            results.append("conflict")
        else:
            results.append("recovered")

    threads = [Thread(target=recover), Thread(target=recover)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not any(thread.is_alive() for thread in threads)
    assert sorted(results) == ["conflict", "recovered"]
    events = base_store.load(run_id)
    assert [event.event_type for event in events].count("run_recovered") == 1


from pathlib import Path

import pytest

from bridge.workflow.event_store import (
    EventCompatibilityError,
    EventSequenceConflict,
    InMemoryRunEventStore,
    SQLiteRunEventStore,
)


def _plan_payload() -> dict:
    return {
        "plan_id": "plan-1",
        "version": "0.1",
        "case_ref": "case-1@0.1",
        "status": "approved",
        "knowledge_snapshot_ref": "knowledge://p0/2026-08-12",
        "steps": [
            {
                "step_id": "step-p0-01",
                "tool_id": "P0-01",
                "tool_version": "0.1.0",
                "disposition": "execute",
            }
        ],
    }


@pytest.mark.parametrize("store_kind", ["memory", "sqlite"])
def test_event_store_appends_ordered_events(tmp_path: Path, store_kind: str) -> None:
    store = (
        InMemoryRunEventStore()
        if store_kind == "memory"
        else SQLiteRunEventStore(tmp_path / "workflow.sqlite3")
    )

    store.append(
        "run-1",
        "run_submitted",
        {"plan": _plan_payload()},
        expected_sequence=0,
    )
    store.append(
        "run-1",
        "run_cancelled",
        {},
        expected_sequence=1,
    )

    events = store.load("run-1")
    assert [event.sequence for event in events] == [1, 2]
    assert [event.event_type for event in events] == ["run_submitted", "run_cancelled"]
    assert [event.schema_version for event in events] == ["1", "1"]


@pytest.mark.parametrize("store_kind", ["memory", "sqlite"])
def test_event_store_rejects_stale_sequence(tmp_path: Path, store_kind: str) -> None:
    store = (
        InMemoryRunEventStore()
        if store_kind == "memory"
        else SQLiteRunEventStore(tmp_path / "workflow.sqlite3")
    )
    store.append("run-1", "run_cancelled", {}, expected_sequence=0)

    with pytest.raises(EventSequenceConflict, match="sequence_conflict"):
        store.append("run-1", "run_cancelled", {}, expected_sequence=0)


def test_sqlite_store_persists_across_instances(tmp_path: Path) -> None:
    database_path = tmp_path / "workflow.sqlite3"
    first = SQLiteRunEventStore(database_path)
    first.append("run-1", "run_cancelled", {}, expected_sequence=0)

    second = SQLiteRunEventStore(database_path)

    assert second.load("run-1") == first.load("run-1")


def test_memory_store_defensively_snapshots_nested_payloads() -> None:
    store = InMemoryRunEventStore()
    payload = {"plan": _plan_payload()}
    store.append("run-1", "run_submitted", payload, expected_sequence=0)
    payload["plan"]["plan_id"] = "mutated"

    loaded = store.load("run-1")
    assert loaded[0].payload.plan.plan_id == "plan-1"  # type: ignore[union-attr]
    loaded_again = store.load("run-1")
    assert loaded[0] is not loaded_again[0]
    assert loaded[0].payload is not loaded_again[0].payload


def test_sqlite_store_marks_pre_version_column_rows_as_legacy(tmp_path: Path) -> None:
    import json
    import sqlite3

    database_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE run_events (
                run_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                event_id TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (run_id, sequence)
            )
            """
        )
        connection.execute(
            "INSERT INTO run_events VALUES (?, ?, ?, ?, ?, ?)",
            (
                "run-1",
                1,
                "event-1",
                "run_cancelled",
                "2026-08-16T00:00:00+00:00",
                json.dumps({}),
            ),
        )

    events = SQLiteRunEventStore(database_path).load("run-1")
    assert events[0].schema_version == "0"


def test_sqlite_legacy_reasonless_failure_migrates_only_in_memory(
    tmp_path: Path,
) -> None:
    import json
    import sqlite3

    database_path = tmp_path / "legacy-history.sqlite3"
    store = SQLiteRunEventStore(database_path)
    rows = [
        ("event-1", "run_submitted", {"plan": _plan_payload()}),
        ("event-2", "step_claimed", {"step_id": "step-p0-01"}),
        ("event-3", "step_failed", {"step_id": "step-p0-01"}),
    ]
    with sqlite3.connect(database_path) as connection:
        for sequence, (event_id, event_type, payload) in enumerate(rows, start=1):
            connection.execute(
                """
                INSERT INTO run_events (
                    run_id, sequence, event_id, event_type, recorded_at,
                    payload_json, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, '0')
                """,
                (
                    "run-legacy",
                    sequence,
                    event_id,
                    event_type,
                    "2026-08-16T00:00:00+00:00",
                    json.dumps(payload, separators=(",", ":")),
                ),
            )

    events = store.load("run-legacy")
    projection = project_run(events)

    assert projection.max_attempts == 2
    assert projection.steps["step-p0-01"].reason_codes == (
        "legacy_failure_reason_unrecorded",
    )
    assert events[2].payload.retry_exhausted is False  # type: ignore[union-attr]
    with sqlite3.connect(database_path) as connection:
        raw_payload = connection.execute(
            "SELECT payload_json FROM run_events WHERE event_id = 'event-3'"
        ).fetchone()[0]
    assert json.loads(raw_payload) == {"step_id": "step-p0-01"}


@pytest.mark.parametrize(
    ("schema_version", "payload_json", "reason_code"),
    [
        ("99", "{}", "workflow_event_schema_version_unsupported"),
        ("0", "[]", "workflow_legacy_event_incompatible"),
        ("1", "[]", "workflow_event_schema_incompatible"),
    ],
)
def test_sqlite_event_decoder_reports_stable_compatibility_coordinates(
    tmp_path: Path,
    schema_version: str,
    payload_json: str,
    reason_code: str,
) -> None:
    import sqlite3

    database_path = tmp_path / f"incompatible-{schema_version}.sqlite3"
    store = SQLiteRunEventStore(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO run_events (
                run_id, sequence, event_id, event_type, recorded_at,
                payload_json, schema_version
            ) VALUES ('run-bad', 1, 'event-bad', 'run_submitted', ?, ?, ?)
            """,
            ("2026-08-16T00:00:00+00:00", payload_json, schema_version),
        )

    with pytest.raises(EventCompatibilityError, match=reason_code) as error:
        store.load("run-bad")

    assert error.value.reason_code == reason_code
    assert error.value.run_id == "run-bad"
    assert error.value.sequence == 1
    assert error.value.event_id == "event-bad"
    assert error.value.schema_version == schema_version


from datetime import datetime, timezone

import pytest

from bridge.domain.models import AnalysisPlan, PlanStep
from bridge.workflow.events import RunEvent, project_run


def _plan() -> AnalysisPlan:
    return AnalysisPlan(
        plan_id="plan-1",
        version="0.1",
        case_ref="case-1@0.1",
        status="approved",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
        steps=[
            PlanStep(
                step_id="step-p0-01",
                tool_id="P0-01",
                tool_version="0.1.0",
                disposition="execute",
            ),
            PlanStep(
                step_id="step-p0-02",
                tool_id="P0-02",
                tool_version="0.1.0",
                disposition="execute",
                depends_on=["step-p0-01"],
            ),
        ],
    )


def _event(sequence: int, event_type: str, payload: dict | None = None) -> RunEvent:
    return RunEvent(
        event_id=f"event-{sequence}",
        run_id="run-1",
        sequence=sequence,
        event_type=event_type,
        recorded_at=datetime(2026, 8, 16, tzinfo=timezone.utc),
        payload=payload or {},
    )


def test_projection_rebuilds_attempts_failure_and_resume() -> None:
    events = [
        _event(1, "run_submitted", {"plan": _plan().model_dump(mode="json")}),
        _event(2, "step_claimed", {"step_id": "step-p0-01"}),
        _event(3, "step_succeeded", {"step_id": "step-p0-01"}),
        _event(4, "step_claimed", {"step_id": "step-p0-02"}),
        _event(
            5,
            "step_failed",
            {"step_id": "step-p0-02", "reason_codes": ["transient_failure"]},
        ),
        _event(6, "run_resumed", {"step_ids": ["step-p0-02"]}),
        _event(7, "step_claimed", {"step_id": "step-p0-02"}),
        _event(8, "step_succeeded", {"step_id": "step-p0-02"}),
    ]

    projection = project_run(events)

    assert projection.status == "succeeded"
    assert projection.steps["step-p0-01"].attempts == 1
    assert projection.steps["step-p0-02"].attempts == 2
    assert projection.last_sequence == 8


def test_projection_rejects_a_sequence_gap() -> None:
    with pytest.raises(ValueError, match="sequence_invalid"):
        project_run(
            [
                _event(1, "run_submitted", {"plan": _plan().model_dump(mode="json")}),
                _event(3, "step_claimed", {"step_id": "step-p0-01"}),
            ]
        )


def test_projection_rejects_claim_before_dependencies() -> None:
    with pytest.raises(ValueError, match="dependencies_not_succeeded"):
        project_run(
            [
                _event(1, "run_submitted", {"plan": _plan().model_dump(mode="json")}),
                _event(2, "step_claimed", {"step_id": "step-p0-02"}),
            ]
        )


def test_event_contract_rejects_missing_and_duplicate_failure_reasons() -> None:
    with pytest.raises(ValueError, match="failure_requires_reason_codes"):
        _event(1, "step_failed", {"step_id": "step-p0-01"})
    with pytest.raises(ValueError, match="reason_codes_must_be_unique"):
        _event(
            1,
            "step_failed",
            {"step_id": "step-p0-01", "reason_codes": ["failure", "failure"]},
        )


def test_projection_rejects_cancellation_after_terminal_failure() -> None:
    events = [
        _event(1, "run_submitted", {"plan": _plan().model_dump(mode="json")}),
        _event(2, "step_claimed", {"step_id": "step-p0-01"}),
        _event(
            3,
            "step_failed",
            {
                "step_id": "step-p0-01",
                "reason_codes": ["permanent_failure"],
                "retry_exhausted": True,
                "blocked_steps": [
                    {
                        "step_id": "step-p0-02",
                        "reason_codes": ["upstream_step_retry_exhausted"],
                    }
                ],
            },
        ),
        _event(4, "run_cancelled"),
    ]
    with pytest.raises(ValueError, match="terminal_run_cannot_be_cancelled"):
        project_run(events)


def test_projection_rejects_recovery_that_disagrees_with_persisted_policy() -> None:
    events = [
        RunEvent(
            event_id="event-1",
            run_id="run-1",
            sequence=1,
            event_type="run_submitted",
            recorded_at=datetime(2026, 8, 16, tzinfo=timezone.utc),
            payload={
                "plan": _plan().model_dump(mode="json"),
                "max_attempts": 1,
            },
        ),
        _event(2, "step_claimed", {"step_id": "step-p0-01"}),
        _event(
            3,
            "run_recovered",
            {
                "recovered_steps": [
                    {"step_id": "step-p0-01", "outcome": "retry"}
                ]
            },
        ),
    ]

    with pytest.raises(ValueError, match="recovered_steps_invalid"):
        project_run(events)

    with pytest.raises(ValueError, match="resume_steps_invalid"):
        project_run(
            events[:2]
            + [_event(3, "run_resumed", {"step_ids": ["step-p0-01"]})]
        )


class _FakeHTTPResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, _limit: int) -> bytes:
        return self._payload


def _deepinfer_payload(content: str, *, model: str = "deepseek-v4-flash-0731") -> bytes:
    return json.dumps(
        {
            "id": "chatcmpl-test",
            "model": model,
            "choices": [
                {
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 7,
                "total_tokens": 18,
            },
        }
    ).encode()


def test_deepinfer_configuration_is_fixed_and_secret_free(monkeypatch: pytest.MonkeyPatch) -> None:
    from bridge.runners.llm import DEEPINFER_MODEL, DeepInferClient, DeepInferConfig

    config = DeepInferConfig(base_url="https://inference.example/v1/")
    assert config.base_url == "https://inference.example/v1"
    assert config.chat_completions_url == "https://inference.example/v1/chat/completions"
    assert config.model == DEEPINFER_MODEL == "deepseek-v4-flash-0731"
    assert config.timeout_seconds == 120

    monkeypatch.setenv("DEEPINFER_BASE_URL", "https://inference.example/v1")
    monkeypatch.setenv("DEEPINFER_API_KEY", "secret-canary")
    client = DeepInferClient.from_env(timeout_seconds=12)
    assert client.config.timeout_seconds == 12
    assert "secret-canary" not in repr(client)
    assert "secret-canary" not in client.config.model_dump_json()

    for invalid in (
        "",
        "file:///tmp/model",
        "https://user:password@example.test/v1",
        "https://example.test/v1?token=secret",
        "https://example.test/v1#fragment",
    ):
        with pytest.raises(ValidationError):
            DeepInferConfig(base_url=invalid)


def test_deepinfer_from_env_fails_before_network(monkeypatch: pytest.MonkeyPatch) -> None:
    from bridge.runners.llm import DeepInferClient, DeepInferError

    monkeypatch.delenv("DEEPINFER_BASE_URL", raising=False)
    with pytest.raises(DeepInferError) as missing:
        DeepInferClient.from_env()
    assert missing.value.reason_code == "deepinfer_base_url_missing"

    monkeypatch.setenv("DEEPINFER_BASE_URL", "not-a-url")
    with pytest.raises(DeepInferError) as invalid:
        DeepInferClient.from_env()
    assert invalid.value.reason_code == "deepinfer_base_url_invalid"


def test_deepinfer_client_sends_exact_model_and_returns_audit_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bridge.runners import DeepInferClient, DeepInferConfig
    from bridge.runners.llm import AgentMessage

    captured: dict[str, object] = {}
    response_bytes = _deepinfer_payload('{"assistant_message":"ok"}')

    def fake_urlopen(request: object, *, timeout: float) -> _FakeHTTPResponse:
        captured["request"] = request
        captured["timeout"] = timeout
        return _FakeHTTPResponse(response_bytes)

    monkeypatch.setattr("bridge.runners.llm.urlopen", fake_urlopen)
    client = DeepInferClient(
        DeepInferConfig(base_url="https://inference.example/v1", timeout_seconds=9),
        api_key="secret-canary",
    )
    result = client.complete((AgentMessage(role="user", content="hello"),))

    request = captured["request"]
    body = json.loads(request.data)
    assert request.full_url == "https://inference.example/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer secret-canary"
    assert captured["timeout"] == 9
    assert body == {
        "messages": [{"content": "hello", "role": "user"}],
        "model": "deepseek-v4-flash-0731",
        "response_format": {"type": "json_object"},
        "stream": False,
        "temperature": 0,
    }
    assert "tools" not in body and "tool_choice" not in body
    assert result.provider_request_id == "chatcmpl-test"
    assert result.model == "deepseek-v4-flash-0731"
    assert result.usage.total_tokens == 18
    assert result.request_sha256 == hashlib.sha256(request.data).hexdigest()
    expected_response_hash = hashlib.sha256(
        json.dumps(
            json.loads(response_bytes),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    assert result.response_sha256 == expected_response_hash
    assert "secret-canary" not in result.model_dump_json()


def test_local_agent_loop_accepts_only_explicit_public_safe_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bridge.runners import (
        AgentTurnRequest,
        AgentIntent,
        DeepInferClient,
        DeepInferConfig,
        LocalAgentLoop,
        PublicAgentContext,
    )

    captured: dict[str, object] = {}
    decision = {
        "assistant_message": "Please confirm the measurement specification.",
        "intent": "clarify",
        "proposed_actions": ["confirm MeasurementSpec"],
        "requires_user_confirmation": True,
    }

    def fake_urlopen(request: object, *, timeout: float) -> _FakeHTTPResponse:
        captured["body"] = json.loads(request.data)
        return _FakeHTTPResponse(_deepinfer_payload(json.dumps(decision)))

    monkeypatch.setattr("bridge.runners.llm.urlopen", fake_urlopen)
    loop = LocalAgentLoop(
        DeepInferClient(DeepInferConfig(base_url="https://inference.example/v1"))
    )
    turn = loop.respond(
        AgentTurnRequest(
            classification="public_safe",
            user_message="Can this case run?",
            public_safe_context=(
                PublicAgentContext(
                    context_id="status-summary",
                    content="P0-01 succeeded; score_state=unavailable",
                ),
            ),
        )
    )

    assert turn.decision.intent is AgentIntent.CLARIFY
    assert turn.decision.requires_user_confirmation is True
    assert turn.context_ids == ("status-summary",)
    body = captured["body"]
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "system"
    assert "cannot execute tools" in body["messages"][0]["content"]
    user_payload = json.loads(body["messages"][1]["content"])
    assert user_payload["public_safe_context"][0]["classification"] == "public_safe"
    assert "tools" not in body

    with pytest.raises(ValidationError):
        PublicAgentContext(
            context_id="private",
            classification="private",  # type: ignore[arg-type]
            content="must not leave the runtime",
        )
    with pytest.raises(ValueError, match="context_ids_duplicate"):
        loop.respond(
            AgentTurnRequest(
                classification="public_safe",
                user_message="explain",
                public_safe_context=(
                    PublicAgentContext(context_id="same", content="one"),
                    PublicAgentContext(context_id="same", content="two"),
                ),
            )
        )

    with pytest.raises(ValidationError):
        AgentTurnRequest(
            classification="private",  # type: ignore[arg-type]
            user_message="must not leave the runtime",
        )


@pytest.mark.parametrize(
    ("payload", "reason_code"),
    [
        (b"not-json", "deepinfer_response_invalid"),
        (_deepinfer_payload("{}", model="another-model"), "deepinfer_response_invalid"),
    ],
)
def test_deepinfer_rejects_invalid_provider_responses(
    monkeypatch: pytest.MonkeyPatch, payload: bytes, reason_code: str
) -> None:
    from bridge.runners.llm import AgentMessage, DeepInferClient, DeepInferConfig, DeepInferError

    monkeypatch.setattr(
        "bridge.runners.llm.urlopen",
        lambda *_args, **_kwargs: _FakeHTTPResponse(payload),
    )
    client = DeepInferClient(DeepInferConfig(base_url="https://inference.example/v1"))
    with pytest.raises(DeepInferError) as caught:
        client.complete((AgentMessage(role="user", content="hello"),))
    assert caught.value.reason_code == reason_code


def test_deepinfer_transport_errors_are_stable_and_secret_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from urllib.error import HTTPError, URLError

    from bridge.runners import AgentMessage, DeepInferClient, DeepInferConfig, DeepInferError

    client = DeepInferClient(
        DeepInferConfig(base_url="https://inference.example/v1"),
        api_key="secret-canary",
    )
    monkeypatch.setattr(
        "bridge.runners.llm.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            HTTPError("https://redacted.invalid", 503, "down", {}, None)
        ),
    )
    with pytest.raises(DeepInferError) as http_error:
        client.complete((AgentMessage(role="user", content="hello"),))
    assert http_error.value.reason_code == "deepinfer_http_error"
    assert http_error.value.status_code == 503
    assert "secret-canary" not in str(http_error.value)

    monkeypatch.setattr(
        "bridge.runners.llm.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("secret-canary")),
    )
    with pytest.raises(DeepInferError) as transport_error:
        client.complete((AgentMessage(role="user", content="hello"),))
    assert transport_error.value.reason_code == "deepinfer_transport_error"
    assert "secret-canary" not in str(transport_error.value)


def test_local_agent_loop_rejects_unstructured_model_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bridge.runners import (
        AgentTurnRequest,
        DeepInferClient,
        DeepInferConfig,
        DeepInferError,
        LocalAgentLoop,
    )

    monkeypatch.setattr(
        "bridge.runners.llm.urlopen",
        lambda *_args, **_kwargs: _FakeHTTPResponse(
            _deepinfer_payload("I executed P0-01")
        ),
    )
    loop = LocalAgentLoop(
        DeepInferClient(DeepInferConfig(base_url="https://inference.example/v1"))
    )
    with pytest.raises(DeepInferError) as caught:
        loop.respond(
            AgentTurnRequest(
                classification="public_safe",
                user_message="Run the tool",
            )
        )
    assert caught.value.reason_code == "agent_response_contract_invalid"


def test_bridge_agent_cli_runs_one_structured_turn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from bridge.runners.llm import main as agent_main

    request_path = tmp_path / "agent-request.json"
    request_path.write_text(
        json.dumps(
            {
                "classification": "public_safe",
                "user_message": "Explain this deterministic status.",
                "public_safe_context": [
                    {
                        "context_id": "status",
                        "classification": "public_safe",
                        "content": "score_state=unavailable",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    decision = {
        "assistant_message": "No score is available.",
        "intent": "explain",
        "proposed_actions": [],
        "requires_user_confirmation": False,
    }
    monkeypatch.setenv("DEEPINFER_BASE_URL", "https://inference.example/v1")
    monkeypatch.setenv("DEEPINFER_API_KEY", "secret-canary")
    monkeypatch.setattr(
        "bridge.runners.llm.urlopen",
        lambda *_args, **_kwargs: _FakeHTTPResponse(
            _deepinfer_payload(json.dumps(decision))
        ),
    )

    assert agent_main(["--request", str(request_path), "--timeout", "5"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["decision"] == decision
    assert output["context_ids"] == ["status"]
    assert output["model_call"]["model"] == "deepseek-v4-flash-0731"
    assert "secret-canary" not in json.dumps(output)


def test_bridge_agent_cli_rejects_private_or_invalid_input_without_echo(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from bridge.runners.llm import main as agent_main

    request_path = tmp_path / "agent-request.json"
    request_path.write_text(
        json.dumps(
            {
                "classification": "private",
                "user_message": "secret-canary",
                "public_safe_context": [
                    {
                        "context_id": "private",
                        "classification": "private",
                        "content": "secret-canary",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert agent_main(["--request", str(request_path)]) == 2
    output = capsys.readouterr().out
    assert json.loads(output) == {"ok": False, "reason_code": "agent_request_invalid"}
    assert "secret-canary" not in output
