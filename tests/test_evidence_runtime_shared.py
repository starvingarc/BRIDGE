from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from bridge.tool_packages._structured_runtime import (
    StructuredInputError,
    canonical_json_bytes,
    inputs_unchanged,
    load_structured_inputs,
    strict_json_loads,
)
from bridge.toolkit.contracts import FrozenModel, StructuredInputRef


class ExampleInput(FrozenModel):
    object_version: str
    value: str


def _input_ref(path: Path, *, sha256: str | None = None) -> StructuredInputRef:
    return StructuredInputRef(
        input_id="example",
        role="example",
        schema_ref="bridge://schemas/example/v0.1",
        object_version="1.0.0",
        path=path.resolve(),
        sha256=sha256 or hashlib.sha256(path.read_bytes()).hexdigest(),
        media_type="application/json",
    )


@pytest.mark.parametrize(
    "raw",
    [b'{"value":1,"value":2}', b'{"value":NaN}', b'{"value":Infinity}'],
)
def test_strict_json_rejects_ambiguous_values(raw: bytes) -> None:
    with pytest.raises(ValueError):
        strict_json_loads(raw)


def test_shared_loader_preserves_module_validation_boundary(tmp_path: Path) -> None:
    path = tmp_path / "input.json"
    path.write_bytes(canonical_json_bytes({"object_version": "1.0.0", "value": "ok"}))
    ref = _input_ref(path)

    loaded, reasons = load_structured_inputs(
        [ref], model_for=lambda item: ExampleInput if item.role == "example" else None
    )

    assert reasons == []
    assert loaded is not None
    assert loaded.objects_by_input_id["example"] == ExampleInput(
        object_version="1.0.0", value="ok"
    )
    assert loaded.bytes_by_input_id["example"] == path.read_bytes()


def test_shared_loader_returns_module_reason_without_payload_echo(tmp_path: Path) -> None:
    path = tmp_path / "input.json"
    path.write_bytes(canonical_json_bytes({"object_version": "1.0.0", "value": "secret"}))
    ref = _input_ref(path)

    def reject(_ref: StructuredInputRef, _payload: object) -> None:
        raise StructuredInputError("module_policy_rejected")

    loaded, reasons = load_structured_inputs(
        [ref],
        model_for=lambda _item: ExampleInput,
        validate_payload=reject,
    )

    assert loaded is None
    assert reasons == ["module_policy_rejected"]
    assert "secret" not in str(reasons)


def test_input_snapshot_detects_checksum_drift(tmp_path: Path) -> None:
    path = tmp_path / "input.json"
    path.write_bytes(b"{}")
    ref = _input_ref(path)
    assert inputs_unchanged([ref])

    path.write_bytes(b'{"changed":true}')
    assert not inputs_unchanged([ref])


def test_canonical_json_encoding_remains_compact_or_newline_terminated() -> None:
    payload = {"z": 1, "a": "cell"}
    assert canonical_json_bytes(payload) == b'{"a":"cell","z":1}'
    assert canonical_json_bytes(payload, indent=2).endswith(b"\n")
