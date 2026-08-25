from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
from typing import Any, Callable, Literal
from uuid import uuid4

from pydantic import ValidationError

from bridge.toolkit.contracts import (
    ExecutionState,
    FrozenModel,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequestV2,
    ToolRunV2,
)


class StructuredInputError(ValueError):
    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(detail or reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True)
class LoadedInputs:
    objects_by_input_id: dict[str, FrozenModel]
    bytes_by_input_id: dict[str, bytes]


ModelResolver = Callable[[StructuredInputRef], type[FrozenModel] | None]
PayloadValidator = Callable[[StructuredInputRef, Any], None]
ModelValidator = Callable[[StructuredInputRef, FrozenModel], None]
VerifiedInputReader = Callable[[StructuredInputRef], bytes]


def canonical_json_bytes(payload: object, *, indent: int | None = None) -> bytes:
    text = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":") if indent is None else None,
        indent=indent,
    )
    if indent is not None:
        text += "\n"
    return text.encode("utf-8")


def strict_json_loads(raw: bytes) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant: {value}")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(
        raw.decode("utf-8"),
        parse_constant=reject_constant,
        object_pairs_hook=unique_object,
    )


def read_regular_bytes(path: Path) -> bytes:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or path.is_symlink():
        raise OSError("not a regular file")
    raw = path.read_bytes()
    after = path.lstat()
    if (
        not stat.S_ISREG(after.st_mode)
        or before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(raw) != after.st_size
    ):
        raise OSError("file changed while reading")
    return raw


def directory_state(path: Path) -> Literal["missing", "directory", "other"]:
    """Classify one path without following a final symlink."""

    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return "missing"
    except OSError:
        return "other"
    return "directory" if stat.S_ISDIR(mode) else "other"


def _read_verified_input(ref: StructuredInputRef) -> bytes:
    try:
        raw = read_regular_bytes(ref.path)
    except FileNotFoundError as exc:
        raise StructuredInputError("structured_input_not_found") from exc
    except OSError as exc:
        raise StructuredInputError("structured_input_not_regular_file") from exc
    if hashlib.sha256(raw).hexdigest() != ref.sha256:
        raise StructuredInputError("structured_input_checksum_mismatch")
    return raw


def load_structured_inputs(
    refs: list[StructuredInputRef],
    *,
    model_for: ModelResolver,
    validate_payload: PayloadValidator | None = None,
    validate_model: ModelValidator | None = None,
    read_verified: VerifiedInputReader = _read_verified_input,
) -> tuple[LoadedInputs | None, list[str]]:
    objects: dict[str, FrozenModel] = {}
    payload_bytes: dict[str, bytes] = {}
    reasons: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        if ref.input_id in seen:
            reasons.append("duplicate_object_input_id")
            continue
        seen.add(ref.input_id)
        model = model_for(ref)
        if model is None:
            continue
        if ref.media_type != "application/json":
            reasons.append("structured_input_media_type_unsupported")
        try:
            raw = read_verified(ref)
        except StructuredInputError as exc:
            reasons.append(exc.reason_code)
            continue
        payload_bytes[ref.input_id] = raw
        try:
            payload = strict_json_loads(raw)
        except (UnicodeDecodeError, ValueError):
            reasons.append("structured_input_json_invalid")
            continue
        try:
            if validate_payload is not None:
                validate_payload(ref, payload)
            value = model.model_validate(payload)
            if validate_model is not None:
                validate_model(ref, value)
        except StructuredInputError as exc:
            reasons.append(exc.reason_code)
            continue
        except (ValidationError, ValueError):
            reasons.append("structured_input_schema_invalid")
            continue
        objects[ref.input_id] = value
    if reasons:
        return None, sorted(set(reasons))
    return LoadedInputs(objects_by_input_id=objects, bytes_by_input_id=payload_bytes), []


def objects_for_role(
    request: ToolRequestV2,
    loaded: LoadedInputs,
    role: str,
    model: type[Any],
) -> list[Any]:
    values = [
        loaded.objects_by_input_id[ref.input_id]
        for ref in request.object_inputs
        if ref.role == role and ref.input_id in loaded.objects_by_input_id
    ]
    if not all(isinstance(item, model) for item in values):
        raise TypeError(f"loaded {role} object has wrong model")
    return values


def single_object(
    request: ToolRequestV2,
    loaded: LoadedInputs,
    role: str,
    model: type[Any],
) -> Any:
    values = objects_for_role(request, loaded, role, model)
    if len(values) != 1:
        raise ValueError(f"expected exactly one {role}")
    return values[0]


def inputs_unchanged(refs: list[StructuredInputRef]) -> bool:
    for ref in refs:
        try:
            if hashlib.sha256(read_regular_bytes(ref.path)).hexdigest() != ref.sha256:
                return False
        except OSError:
            return False
    return True


def write_json(path: Path, payload: object) -> None:
    path.write_bytes(canonical_json_bytes(payload, indent=2))


def publish_single_json(
    *,
    request: ToolRequestV2,
    run_id: str,
    filename: str,
    payload: bytes,
) -> Path:
    """Atomically publish one immutable JSON artifact for a deterministic run."""

    if Path(filename).name != filename or not filename.endswith(".json"):
        raise StructuredInputError("output_filename_invalid")
    if (
        not run_id
        or not run_id.isascii()
        or any(not (character.isalnum() or character in "._-") for character in run_id)
        or run_id in {".", ".."}
    ):
        raise StructuredInputError("output_run_id_invalid")
    output_root = request.output_dir
    if directory_state(output_root) == "other":
        raise StructuredInputError("output_path_invalid")
    try:
        output_root.mkdir(parents=True, exist_ok=True)
    except (OSError, RuntimeError):
        raise StructuredInputError("output_path_invalid") from None
    if directory_state(output_root) != "directory":
        raise StructuredInputError("output_path_invalid")

    staging = output_root / f".{run_id}.staging-{uuid4().hex}"
    try:
        staging.mkdir(mode=0o700)
        (staging / filename).write_bytes(payload)
        if not inputs_unchanged(request.object_inputs):
            raise StructuredInputError("structured_input_modified_during_run")

        final = output_root / run_id
        final_state = directory_state(final)
        if final_state == "directory":
            existing = final / filename
            try:
                matches = (
                    read_regular_bytes(existing) == payload
                    and {path.name for path in final.iterdir()} == {filename}
                )
            except (OSError, RuntimeError):
                matches = False
            if not matches:
                raise StructuredInputError("existing_run_bundle_hash_mismatch")
            shutil.rmtree(staging)
        elif final_state == "missing":
            os.replace(staging, final)
        else:
            raise StructuredInputError("existing_run_bundle_hash_mismatch")

        published = final / filename
        if read_regular_bytes(published) != payload:
            raise StructuredInputError("published_result_hash_mismatch")
        return published
    except StructuredInputError:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    except (OSError, RuntimeError):
        shutil.rmtree(staging, ignore_errors=True)
        raise StructuredInputError("output_path_invalid") from None


def failed_v2_run(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    reason_codes: list[str],
    *,
    result_schema_ref: str,
    fingerprint_input_key: str,
    input_hash: str | None = None,
) -> ToolRunV2:
    reasons = sorted(set(reason_codes))
    failure_hash = hashlib.sha256(
        canonical_json_bytes(
            {
                "tool_id": request.tool_id,
                "tool_version": spec.version,
                "reason_codes": reasons,
                fingerprint_input_key: [
                    {
                        "input_id": ref.input_id,
                        "role": ref.role,
                        "schema_ref": ref.schema_ref,
                        "object_version": ref.object_version,
                        "sha256": ref.sha256,
                        "media_type": ref.media_type,
                    }
                    for ref in sorted(
                        request.object_inputs,
                        key=lambda item: (item.role, item.input_id),
                    )
                ],
            }
        )
    ).hexdigest()
    return ToolRunV2(
        run_id=f"run-{failure_hash[:16]}",
        request=request,
        implementation_state=spec.implementation_state,
        execution_state=ExecutionState.FAILED,
        tool_version=spec.version,
        environment_spec_id=spec.environment_spec_id,
        input_hash=input_hash,
        created_at=datetime(1970, 1, 1, tzinfo=timezone.utc),
        measurements=[],
        artifacts=[],
        visualizations=[],
        result_schema_ref=result_schema_ref,
        result=None,
        reason_codes=reasons,
        warnings=[],
    )
