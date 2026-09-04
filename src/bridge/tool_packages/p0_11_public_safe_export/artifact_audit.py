from __future__ import annotations

import csv
import hashlib
from html import unescape as html_unescape
import io
import ipaddress
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
from typing import Any
import unicodedata
from urllib.parse import unquote, urlsplit

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from markdown_it import MarkdownIt
import regex
from xml.etree.ElementTree import ParseError

from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    PublicationError,
    StructuredInputError,
    canonical_json_bytes,
    directory_state,
    failed_v2_run,
    inputs_unchanged,
    load_structured_inputs,
    publish_json_bundle,
    read_regular_bytes,
    request_v2_from_v1,
    single_object,
    strict_json_loads,
)
from bridge.tool_packages.p0_11_public_safe_export.artifact_models import (
    ArtifactAuditState,
    ArtifactCheckState,
    PUBLIC_REF_PATTERN,
    PublicArtifactAuditPolicy,
    PublicArtifactAuditRecord,
    PublicArtifactAuditResult,
    PublicArtifactCheck,
    PublicArtifactFileRef,
    PublicArtifactFormat,
    PublicArtifactManifest,
    is_public_dns_name,
)
from bridge.tool_packages.p0_11_public_safe_export.visualization import (
    prepare_public_safe_export_visualizations,
)
from bridge.tool_packages.p0_11_public_safe_export.visualization_data import (
    build_artifact_audit_visualization_data,
)
from bridge.toolkit.contracts import (
    ArtifactManifest,
    EligibilityResult,
    ExecutionState,
    FrozenModel,
    ImplementationState,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
    ToolRunV2,
)
from bridge.toolkit.schemas import load_schema


RESULT_SCHEMA_REF = "bridge://schemas/public-safe-export-run-result/v0.1"
ROLE_MODELS: dict[str, tuple[str, type[FrozenModel]]] = {
    "public_artifact_audit_policy": (
        "bridge://schemas/public-artifact-audit-policy/v0.1",
        PublicArtifactAuditPolicy,
    ),
    "public_artifact_manifest": (
        "bridge://schemas/public-artifact-manifest/v0.1",
        PublicArtifactManifest,
    ),
}
METHOD_IMPLEMENTATIONS = {
    "METHOD-CSV-DETERMINISTIC-RULE": "Python csv parser and formula guard",
    "METHOD-CUSTOM-DETERMINISTIC-RULES": (
        "BRIDGE manifest-ref syntax, leak and control-character rules"
    ),
    "METHOD-CUSTOM-SVG-INSPECTOR": "defusedxml plus BRIDGE SVG allowlist",
    "METHOD-FORMAT-GATE": "BRIDGE signature and MIME gate",
    "METHOD-JSONSCHEMA-HASHLIB": "jsonschema Draft 2020-12 and hashlib",
    "METHOD-MARKDOWN-PARSER-REGEX": "markdown-it-py and regex",
    "METHOD-OS-CLI": "file on a hash-bound read-only snapshot",
    "METHOD-URL-PARSER-ALLOWLIST": "urllib.parse URL allowlist",
}
EXPECTED_MEDIA_TYPES = {
    PublicArtifactFormat.JSON: {"application/json", "text/plain"},
    PublicArtifactFormat.MARKDOWN: {"text/markdown", "text/plain"},
    PublicArtifactFormat.CSV: {"text/csv", "text/plain"},
    PublicArtifactFormat.SVG: {"image/svg+xml", "text/xml", "application/xml"},
}
LEAK_PATTERNS = (
    regex.compile(
        r"(?<![A-Za-z0-9_+./:<-])/(?!/)(?:[A-Za-z0-9._-]+/)*"
        r"[A-Za-z0-9._-]+|[A-Za-z]:\\(?:[^\\\s]+\\)*[^\\\s]+",
        regex.I,
    ),
    regex.compile(r"\\\\[A-Za-z0-9._-]+\\(?:[^\\\s]+\\)*[^\\\s]+", regex.I),
    regex.compile(
        r"(?<![0-9.])(?:10(?:\.[0-9]{1,3}){3}|"
        r"127(?:\.[0-9]{1,3}){3}|"
        r"169\.254(?:\.[0-9]{1,3}){2}|"
        r"192\.168(?:\.[0-9]{1,3}){2}|"
        r"172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2})(?![0-9.])"
    ),
    regex.compile(
        r"\b(?:source|server|compute)\s+host(?:name)?\s*"
        r"(?:is|[:=])\s*[A-Za-z0-9._-]+\b",
        regex.I,
    ),
    regex.compile(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        regex.I,
    ),
    regex.compile(
        r"\b(?:api[_-]?key|password|secret|access[_-]?token|"
        r"refresh[_-]?token|bearer)\b(?:\s*[:=]\s*|\s+)[^\s,;]+",
        regex.I,
    ),
    regex.compile(r"\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{8,})\b"),
    regex.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----"),
    regex.compile(
        r"\b(?:internal|private|intranet|compute|server|cluster|worker|node|gpu)"
        r"[-_][A-Za-z0-9][A-Za-z0-9_-]*\b|"
        r"\b[A-Za-z0-9][A-Za-z0-9_-]*[-_]"
        r"(?:internal|private|intranet|compute|server|cluster|worker|node|gpu)\b",
        regex.I,
    ),
    regex.compile(
        r"\b(?:ssh|scp|rsync)\s+(?:[A-Za-z0-9._-]+@)?"
        r"[A-Za-z0-9][A-Za-z0-9_-]{1,62}\b",
        regex.I,
    ),
    regex.compile(
        r"\b(?:conda\s+activate|environment\s*(?:name|[:=])|"
        r"venv\s*(?:name|[:=]))\s*[A-Za-z0-9._-]+\b",
        regex.I,
    ),
    regex.compile(
        r"\b(?:evidence|product-case|sample|preparation):[A-Za-z0-9]",
        regex.I,
    ),
)
BARE_MARKDOWN_URL = regex.compile(
    r"(?<![A-Za-z0-9_])(?:https?://|www\.)[^\s<]+",
    regex.I,
)
FORMULA_PREFIX = regex.compile(r"^\s*[=+@-]")
NUMERIC_CELL = regex.compile(
    r"^\s*[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?\s*$"
)
SVG_URL_REFERENCE = regex.compile(
    r"url\(\s*(['\"]?)([^'\"\)\s]+)\1\s*\)", regex.I
)
ALLOWED_SVG_ELEMENTS = {
    "circle",
    "clipPath",
    "defs",
    "desc",
    "ellipse",
    "g",
    "line",
    "linearGradient",
    "path",
    "polygon",
    "polyline",
    "radialGradient",
    "rect",
    "stop",
    "svg",
    "text",
    "title",
    "tspan",
}
ALLOWED_SVG_ATTRIBUTES = {
    "class",
    "clip-path",
    "cx",
    "cy",
    "d",
    "dx",
    "dy",
    "fill",
    "fill-opacity",
    "font-family",
    "font-size",
    "font-weight",
    "height",
    "id",
    "offset",
    "opacity",
    "points",
    "preserveAspectRatio",
    "r",
    "rx",
    "ry",
    "stroke",
    "stroke-dasharray",
    "stroke-linecap",
    "stroke-linejoin",
    "stroke-opacity",
    "stroke-width",
    "text-anchor",
    "transform",
    "viewBox",
    "width",
    "x",
    "x1",
    "x2",
    "y",
    "y1",
    "y2",
}
HIDDEN_VALUES = {
    ("display", "none"),
    ("visibility", "hidden"),
    ("opacity", "0"),
}


def is_artifact_audit_request(request: ToolRequestV2) -> bool:
    return any(ref.role in ROLE_MODELS for ref in request.object_inputs)


def check_eligibility(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
) -> EligibilityResult:
    if not isinstance(request, ToolRequestV2):
        tool_id = request.tool_id if isinstance(request, ToolRequest) else "P0-11"
        return EligibilityResult(
            tool_id=tool_id,
            eligible=False,
            reason_codes=["tool_request_v2_required"],
        )
    reasons = _envelope_reasons(request, spec)
    loaded, loading_reasons = _load_inputs(request.object_inputs)
    reasons.extend(loading_reasons)
    if loaded is not None and not reasons:
        reasons.extend(_binding_reasons(request, loaded, spec))
    reason_codes = sorted(set(reasons))
    return EligibilityResult(
        tool_id=request.tool_id,
        eligible=not reason_codes,
        reason_codes=reason_codes,
    )


def run(request: ToolRequestV2, spec: ToolPackageSpecV2) -> ToolRunV2:
    if not isinstance(request, ToolRequestV2):
        return _failed_v1_request(request, spec)
    eligibility = check_eligibility(request, spec)
    input_hash = _input_hash(request, spec)
    if not eligibility.eligible:
        return _failed_run(
            request,
            spec,
            eligibility.reason_codes,
            input_hash=input_hash,
        )
    loaded, reasons = _load_inputs(request.object_inputs)
    if loaded is None or reasons:
        return _failed_run(request, spec, reasons, input_hash=input_hash)
    policy = single_object(
        request,
        loaded,
        "public_artifact_audit_policy",
        PublicArtifactAuditPolicy,
    )
    manifest = single_object(
        request,
        loaded,
        "public_artifact_manifest",
        PublicArtifactManifest,
    )
    policy_ref = _ref_for_role(request, "public_artifact_audit_policy")
    manifest_ref = _ref_for_role(request, "public_artifact_manifest")
    try:
        result = _audit_result(
            policy=policy,
            manifest=manifest,
            policy_sha256=policy_ref.sha256,
            manifest_sha256=manifest_ref.sha256,
            tool_version=spec.version,
            input_hash=input_hash,
        )
    except OSError:
        return _failed_run(
            request,
            spec,
            ["public_artifact_modified_during_run"],
            input_hash=input_hash,
        )
    run_id = f"run-{input_hash[:16]}"
    result_bytes = canonical_json_bytes(
        result.model_dump(mode="json"),
        indent=2,
    )
    try:
        profile = build_artifact_audit_visualization_data(
            run_id=run_id,
            tool_version=spec.version,
            result=result,
            source_result_sha256=hashlib.sha256(result_bytes).hexdigest(),
        )
    except (KeyError, TypeError, ValueError):
        return _failed_run(
            request,
            spec,
            ["visualization_data_invalid"],
            input_hash=input_hash,
        )
    try:
        prepared = prepare_public_safe_export_visualizations(
            profile=profile,
            output_dir=request.output_dir,
            run_id=run_id,
            tool_version=spec.version,
        )
    except (KeyError, OSError, RuntimeError, TypeError, ValueError):
        return _failed_run(
            request,
            spec,
            ["visualization_render_failed"],
            input_hash=input_hash,
        )
    result_spec = {
        "filename": "public_artifact_audit_result.json",
        "kind": "public_artifact_audit_result",
        "media_type": "application/json",
        "sha256": hashlib.sha256(result_bytes).hexdigest(),
        "evidence_ids": profile.evidence_ids,
    }
    payloads = {
        "public_artifact_audit_result.json": result_bytes,
        **prepared.payloads,
    }
    artifact_specs = [
        result_spec,
        *[
            {
                "filename": item.path.name,
                "kind": item.kind,
                "media_type": item.media_type,
                "sha256": item.sha256,
                "evidence_ids": item.evidence_ids,
            }
            for item in prepared.artifacts
        ],
    ]
    payloads["artifact_manifest.json"] = canonical_json_bytes(
        {
            "scope": "internal_run_provenance",
            "run_id": run_id,
            "tool_id": spec.tool_id,
            "tool_version": spec.version,
            "environment_spec_id": spec.environment_spec_id,
            "result_schema_ref": RESULT_SCHEMA_REF,
            "input_hash": input_hash,
            "structured_inputs": [
                {
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
            "artifacts": artifact_specs,
        },
        indent=2,
    )
    try:
        published = publish_json_bundle(
            request=request,
            run_id=run_id,
            payloads=payloads,
            inputs_are_unchanged=lambda refs: (
                inputs_unchanged(refs)
                and _artifact_files_unchanged(manifest)
            ),
        )
    except PublicationError as exc:
        return _failed_run(
            request,
            spec,
            [exc.reason_code],
            input_hash=input_hash,
        )
    artifacts = [
        ArtifactManifest(
            artifact_id=f"artifact:{run_id}:public-artifact-audit-result",
            kind="public_artifact_audit_result",
            path=published["public_artifact_audit_result.json"].resolve(),
            media_type="application/json",
            sha256=result_spec["sha256"],
            evidence_ids=profile.evidence_ids,
        ),
        *[
            item.model_copy(update={"path": published[item.path.name].resolve()})
            for item in prepared.artifacts
        ],
        ArtifactManifest(
            artifact_id=f"artifact:{run_id}:artifact-manifest",
            kind="artifact_manifest",
            path=published["artifact_manifest.json"].resolve(),
            media_type="application/json",
            sha256=hashlib.sha256(
                payloads["artifact_manifest.json"]
            ).hexdigest(),
            evidence_ids=profile.evidence_ids,
        ),
    ]
    return ToolRunV2(
        run_id=run_id,
        request=request,
        implementation_state=ImplementationState.IMPLEMENTED,
        execution_state=ExecutionState.SUCCEEDED,
        tool_version=spec.version,
        environment_spec_id=spec.environment_spec_id,
        input_hash=input_hash,
        created_at=manifest.created_at,
        measurements=[],
        artifacts=artifacts,
        visualizations=[],
        result_schema_ref=RESULT_SCHEMA_REF,
        result=result.model_dump(mode="json"),
        reason_codes=[],
        warnings=[],
    )


def _envelope_reasons(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
) -> list[str]:
    reasons: list[str] = []
    if request.tool_version is not None and request.tool_version != spec.version:
        reasons.append("tool_version_mismatch")
    if request.assets:
        reasons.append("p0_11_expression_assets_forbidden")
    if request.measurement_spec_ref is not None:
        reasons.append("p0_11_measurement_spec_forbidden")
    if request.parameters:
        reasons.append("p0_11_parameters_forbidden")
    roles = [ref.role for ref in request.object_inputs]
    for role in ROLE_MODELS:
        if roles.count(role) != 1:
            reasons.append(f"exactly_one_{role}_required")
    if any(role not in ROLE_MODELS for role in roles):
        reasons.append("unsupported_object_input_role")
    for ref in request.object_inputs:
        contract = ROLE_MODELS.get(ref.role)
        if contract is not None and ref.schema_ref != contract[0]:
            reasons.append("object_input_schema_mismatch")
        if ref.object_version != "0.1.0":
            reasons.append("object_input_version_mismatch")
    if directory_state(request.output_dir) == "other":
        reasons.append("output_dir_not_regular_directory")
    return reasons


def _load_inputs(
    refs: list[StructuredInputRef],
) -> tuple[LoadedInputs | None, list[str]]:
    return load_structured_inputs(
        refs,
        model_for=lambda ref: ROLE_MODELS.get(ref.role, ("", None))[1],
        validate_model=_validate_object_version,
    )


def _validate_object_version(
    ref: StructuredInputRef,
    value: FrozenModel,
) -> None:
    if getattr(value, "object_version", None) != ref.object_version:
        raise StructuredInputError("object_input_version_mismatch")


def _binding_reasons(
    request: ToolRequestV2,
    loaded: LoadedInputs,
    spec: ToolPackageSpecV2,
) -> list[str]:
    policy = single_object(
        request,
        loaded,
        "public_artifact_audit_policy",
        PublicArtifactAuditPolicy,
    )
    manifest = single_object(
        request,
        loaded,
        "public_artifact_manifest",
        PublicArtifactManifest,
    )
    reasons: set[str] = set()
    public_metadata = [
        policy.ref,
        manifest.ref,
        manifest.policy_ref,
        *[item.artifact_id for item in manifest.artifacts],
        *[item.source_artifact_ref for item in manifest.artifacts],
    ]
    if any(contains_registered_leak(value) for value in public_metadata):
        return ["public_artifact_metadata_leak_detected"]
    if not policy.active:
        reasons.add("public_artifact_policy_inactive")
    if manifest.policy_ref != policy.ref:
        reasons.add("public_artifact_policy_binding_mismatch")
    if any(item.format not in policy.allowed_formats for item in manifest.artifacts):
        reasons.add("public_artifact_format_not_allowed")
    json_ids = {
        item.artifact_id
        for item in manifest.artifacts
        if item.format is PublicArtifactFormat.JSON
    }
    csv_ids = {
        item.artifact_id
        for item in manifest.artifacts
        if item.format is PublicArtifactFormat.CSV
    }
    if set(policy.json_schema_refs) != json_ids:
        reasons.add("public_artifact_json_schema_binding_mismatch")
    if set(policy.csv_column_allowlists) != csv_ids:
        reasons.add("public_artifact_csv_allowlist_binding_mismatch")
    for schema_ref in policy.json_schema_refs.values():
        try:
            schema = load_schema(schema_ref)
            Draft202012Validator.check_schema(schema)
        except (KeyError, FileNotFoundError, SchemaError):
            reasons.add("public_artifact_json_schema_invalid")
    required_tools = {"file"}
    available_tools = {name for name in required_tools if shutil.which(name)}
    if not required_tools.issubset(available_tools):
        reasons.add("public_artifact_os_tool_unavailable")
    output_root = request.output_dir.resolve(strict=False)
    for item in manifest.artifacts:
        resolved = item.path.resolve(strict=False)
        if resolved == output_root or resolved.is_relative_to(output_root):
            reasons.add("public_artifact_output_overlap")
        try:
            metadata = item.path.lstat()
            if (
                not stat.S_ISREG(metadata.st_mode)
                or item.path.is_symlink()
            ):
                reasons.add("public_artifact_not_regular_file")
                continue
            if metadata.st_size == 0:
                reasons.add("public_artifact_empty")
            if metadata.st_size > policy.max_file_bytes:
                reasons.add("public_artifact_too_large")
                continue
            raw = read_regular_bytes(item.path)
        except FileNotFoundError:
            reasons.add("public_artifact_not_found")
            continue
        except OSError:
            reasons.add("public_artifact_not_regular_file")
            continue
        if hashlib.sha256(raw).hexdigest() != item.sha256:
            reasons.add("public_artifact_checksum_mismatch")
    if any(method not in spec.method_ids for method in METHOD_IMPLEMENTATIONS):
        reasons.add("public_artifact_method_not_registered")
    return sorted(reasons)


def _audit_result(
    *,
    policy: PublicArtifactAuditPolicy,
    manifest: PublicArtifactManifest,
    policy_sha256: str,
    manifest_sha256: str,
    tool_version: str,
    input_hash: str,
) -> PublicArtifactAuditResult:
    records = [
        _audit_artifact(item, policy)
        for item in manifest.artifacts
    ]
    records.sort(key=lambda item: item.artifact_id)
    selected_method_ids = sorted(
        {
            check.method_id
            for record in records
            for check in record.checks
        }
    )
    audit_state = (
        ArtifactAuditState.BLOCKED
        if any(
            record.audit_state is ArtifactAuditState.BLOCKED
            for record in records
        )
        else ArtifactAuditState.PASSED
    )
    return PublicArtifactAuditResult(
        object_version="0.1.0",
        audit_id=f"public-artifact-audit:{input_hash[:16]}",
        tool_id="P0-11",
        tool_version=tool_version,
        policy_ref=policy.ref,
        policy_sha256=policy_sha256,
        manifest_ref=manifest.ref,
        manifest_sha256=manifest_sha256,
        audit_state=audit_state,
        records=records,
        selected_method_ids=selected_method_ids,
        runtime_versions=_runtime_versions(),
        created_at=manifest.created_at,
        domain_score=None,
        score_state="unavailable",
    )


def _audit_artifact(
    item: PublicArtifactFileRef,
    policy: PublicArtifactAuditPolicy,
) -> PublicArtifactAuditRecord:
    raw = read_regular_bytes(item.path)
    if hashlib.sha256(raw).hexdigest() != item.sha256:
        raise OSError("public artifact changed before audit")
    checks: list[PublicArtifactCheck] = []
    detected_media, os_reasons = _os_checks(raw)
    checks.append(_check("METHOD-OS-CLI", os_reasons))
    format_reasons = []
    if detected_media not in EXPECTED_MEDIA_TYPES[item.format]:
        format_reasons.append("public_artifact_media_type_mismatch")
    if item.media_type not in EXPECTED_MEDIA_TYPES[item.format]:
        format_reasons.append("public_artifact_declared_media_type_mismatch")
    checks.append(_check("METHOD-FORMAT-GATE", format_reasons))
    common_reasons = [
        *_manifest_ref_syntax_reasons(item.source_artifact_ref),
        *_common_text_reasons(raw),
    ]
    if item.format is PublicArtifactFormat.JSON:
        common_reasons.extend(_decoded_json_leak_reasons(raw))
    checks.append(_check("METHOD-CUSTOM-DETERMINISTIC-RULES", common_reasons))

    if item.format is PublicArtifactFormat.JSON:
        checks.extend(_audit_json(item, raw, policy))
    elif item.format is PublicArtifactFormat.MARKDOWN:
        checks.extend(_audit_markdown(raw, policy))
    elif item.format is PublicArtifactFormat.CSV:
        checks.extend(_audit_csv(item, raw, policy))
    elif item.format is PublicArtifactFormat.SVG:
        checks.extend(_audit_svg(raw, policy))
    checks.sort(key=lambda value: value.method_id)
    blocked = any(
        value.state is ArtifactCheckState.BLOCKED
        for value in checks
    )
    return PublicArtifactAuditRecord(
        artifact_id=item.artifact_id,
        source_artifact_ref=item.source_artifact_ref,
        source_sha256=item.sha256,
        declared_format=item.format,
        declared_media_type=item.media_type,
        detected_media_type=detected_media,
        byte_count=len(raw),
        audit_state=(
            ArtifactAuditState.BLOCKED
            if blocked
            else ArtifactAuditState.PASSED
        ),
        checks=checks,
    )


def _check(
    method_id: str,
    reasons: list[str],
) -> PublicArtifactCheck:
    reason_codes = sorted(set(reasons))
    return PublicArtifactCheck(
        method_id=method_id,
        implementation=METHOD_IMPLEMENTATIONS[method_id],
        state=(
            ArtifactCheckState.BLOCKED
            if reason_codes
            else ArtifactCheckState.PASSED
        ),
        reason_codes=reason_codes,
    )


def _os_checks(raw: bytes) -> tuple[str, list[str]]:
    reasons: list[str] = []
    with tempfile.TemporaryDirectory(prefix="bridge-p0-11-audit-") as temp_dir:
        snapshot = Path(temp_dir) / "artifact"
        snapshot.write_bytes(raw)
        snapshot.chmod(0o400)
        try:
            detected = subprocess.run(
                ["file", "--brief", "--mime-type", "--", str(snapshot)],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            detected = "application/octet-stream"
            reasons.append("public_artifact_file_command_failed")
    return detected, reasons


def _manifest_ref_syntax_reasons(source_ref: str) -> list[str]:
    if not regex.fullmatch(PUBLIC_REF_PATTERN, source_ref):
        return ["public_artifact_source_ref_syntax_invalid"]
    source, version = source_ref.rsplit("@", 1)
    if source == "public-source:" or not version:
        return ["public_artifact_source_ref_syntax_invalid"]
    return []


def _common_text_reasons(raw: bytes) -> list[str]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ["public_artifact_utf8_invalid"]
    reasons = _semantic_leak_reasons(text)
    if any(
        ord(char) < 32 and char not in "\n\r\t"
        for char in text
    ):
        reasons.append("public_artifact_control_character")
    return sorted(set(reasons))


def _semantic_leak_reasons(text: str) -> list[str]:
    current = _canonical_semantic_text(text)
    values = {text, current}
    stabilized = False
    try:
        for _ in range(3):
            decoded = _canonical_semantic_text(
                unquote(html_unescape(current), errors="strict")
            )
            values.add(decoded)
            if decoded == current:
                stabilized = True
                break
            current = decoded
        if not stabilized:
            next_value = _canonical_semantic_text(
                unquote(html_unescape(current), errors="strict")
            )
            if next_value != current:
                return ["public_artifact_leak_pattern_detected"]
        semantic_values = set(values)
        for value in values:
            parsed = urlsplit(value)
            semantic_values.update(
                item
                for item in (
                    parsed.query,
                    parsed.fragment,
                    parsed.username,
                    parsed.password,
                )
                if item
            )
            if parsed.path:
                semantic_values.add(parsed.path.lstrip("/"))
                if parsed.path.startswith("//") or _local_url_path(
                    parsed.path
                ):
                    return ["public_artifact_leak_pattern_detected"]
    except (UnicodeDecodeError, ValueError):
        return ["public_artifact_leak_pattern_detected"]
    return (
        ["public_artifact_leak_pattern_detected"]
        if (
            any(_private_ip_present(value) for value in semantic_values)
            or any(
            pattern.search(value)
            for value in semantic_values
            for pattern in LEAK_PATTERNS
            )
        )
        else []
    )


def _local_url_path(path: str) -> bool:
    return bool(
        regex.match(
            r"^/+(?:Users|bin|data[0-9]*|dev|etc|gpfs|home|lib|lustre|mnt|opt|"
            r"proc|root|run|scratch|srv|sys|tmp|usr|var|Volumes|work)(?:/|$)",
            path,
            regex.I,
        )
    )


def _private_ip_present(text: str) -> bool:
    for candidate in regex.findall(
        r"(?<![A-Fa-f0-9:.])(?:[A-Fa-f0-9:.]{2,})(?![A-Fa-f0-9:.])",
        text,
    ):
        candidate = candidate.strip("[](),;.!?")
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if address.is_private or address.is_loopback or address.is_link_local:
            return True
    return False


def _canonical_semantic_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    return "".join(
        character for character in normalized if unicodedata.category(character) != "Cf"
    )


def contains_registered_leak(value: Any) -> bool:
    return any(
        _semantic_leak_reasons(text) for text in _semantic_strings(value)
    )


def _audit_json(
    item: PublicArtifactFileRef,
    raw: bytes,
    policy: PublicArtifactAuditPolicy,
) -> list[PublicArtifactCheck]:
    reasons: list[str] = []
    try:
        payload = strict_json_loads(raw)
        schema = load_schema(policy.json_schema_refs[item.artifact_id])
        Draft202012Validator(schema).validate(payload)
    except (
        KeyError,
        FileNotFoundError,
        UnicodeDecodeError,
        ValueError,
        SchemaError,
        ValidationError,
    ):
        reasons.append("public_artifact_json_schema_invalid")
    return [_check("METHOD-JSONSCHEMA-HASHLIB", reasons)]


def _semantic_strings(value: Any):
    if isinstance(value, FrozenModel):
        value = value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _semantic_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _semantic_strings(item)
    elif isinstance(value, str):
        yield value


def _decoded_json_leak_reasons(raw: bytes) -> list[str]:
    try:
        payload = strict_json_loads(raw)
    except (UnicodeDecodeError, ValueError):
        return []
    return sorted(
        {
            reason
            for text in _semantic_strings(payload)
            for reason in _semantic_leak_reasons(text)
        }
    )


def _audit_markdown(
    raw: bytes,
    policy: PublicArtifactAuditPolicy,
) -> list[PublicArtifactCheck]:
    parser_reasons: list[str] = []
    url_reasons: list[str] = []
    try:
        tokens = MarkdownIt("commonmark", {"html": True}).parse(
            raw.decode("utf-8")
        )
        for token in _markdown_tokens(tokens):
            parser_reasons.extend(_semantic_leak_reasons(token.content))
            for name, value in (token.attrs or {}).items():
                parser_reasons.extend(_semantic_leak_reasons(str(name)))
                parser_reasons.extend(_semantic_leak_reasons(str(value)))
            if token.type == "inline" and token.children:
                parser_reasons.extend(
                    _semantic_leak_reasons(_markdown_visible_text(token.children))
                )
            if token.type in {"html_block", "html_inline"}:
                parser_reasons.append("public_artifact_markdown_html_forbidden")
            if token.type == "link_open":
                target = token.attrGet("href")
                if target:
                    parser_reasons.extend(_semantic_leak_reasons(target))
                    if not _url_allowed(target, policy):
                        url_reasons.append("public_artifact_url_not_allowed")
            elif token.type == "image":
                target = token.attrGet("src")
                if target:
                    parser_reasons.extend(_semantic_leak_reasons(target))
                url_reasons.append("public_artifact_url_not_allowed")
            if token.type == "text":
                for match in BARE_MARKDOWN_URL.finditer(token.content):
                    target = match.group(0).rstrip(".,:;!?")
                    if target.lower().startswith("www.") or not _url_allowed(
                        target, policy
                    ):
                        url_reasons.append("public_artifact_url_not_allowed")
    except (UnicodeDecodeError, ValueError):
        parser_reasons.append("public_artifact_markdown_invalid")
    return [
        _check("METHOD-MARKDOWN-PARSER-REGEX", parser_reasons),
        _check("METHOD-URL-PARSER-ALLOWLIST", url_reasons),
    ]


def _markdown_tokens(tokens: list[Any]):
    for token in tokens:
        yield token
        if token.children:
            yield from _markdown_tokens(token.children)


def _markdown_visible_text(tokens: list[Any]) -> str:
    return "".join(
        (
            " "
            if token.type in {"softbreak", "hardbreak"}
            else token.content
            if token.type in {"text", "code_inline", "image"}
            else ""
        )
        for token in tokens
    )


def _url_allowed(
    target: str,
    policy: PublicArtifactAuditPolicy,
) -> bool:
    parsed = urlsplit(target)
    try:
        port = parsed.port
    except ValueError:
        return False
    return bool(
        parsed.scheme in policy.allowed_url_schemes
        and parsed.hostname in policy.allowed_url_hosts
        and parsed.hostname is not None
        and is_public_dns_name(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and port in (None, 443)
        and "?" not in target
        and "#" not in target
    )


def _audit_csv(
    item: PublicArtifactFileRef,
    raw: bytes,
    policy: PublicArtifactAuditPolicy,
) -> list[PublicArtifactCheck]:
    parser_reasons: list[str] = []
    rule_reasons: list[str] = []
    try:
        text = raw.decode("utf-8")
        rows = list(csv.reader(io.StringIO(text), strict=True))
        columns = rows[0] if rows else []
        parser_reasons.extend(
            reason for value in columns for reason in _semantic_leak_reasons(value)
        )
        expected = policy.csv_column_allowlists[item.artifact_id]
        if len(columns) != len(set(columns)) or sorted(columns) != expected:
            parser_reasons.append("public_artifact_csv_columns_not_allowed")
        if any(len(row) != len(columns) for row in rows[1:]):
            parser_reasons.append("public_artifact_csv_row_width_invalid")
        for row in rows[1:]:
            for value in row:
                parser_reasons.extend(_semantic_leak_reasons(value))
                if (
                    FORMULA_PREFIX.search(_canonical_semantic_text(value))
                    and not NUMERIC_CELL.fullmatch(_canonical_semantic_text(value))
                ):
                    rule_reasons.append("public_artifact_csv_formula_injection")
    except (UnicodeDecodeError, csv.Error, KeyError, ValueError):
        parser_reasons.append("public_artifact_csv_invalid")
    return [_check("METHOD-CSV-DETERMINISTIC-RULE", parser_reasons + rule_reasons)]


def _audit_svg(
    raw: bytes,
    policy: PublicArtifactAuditPolicy,
) -> list[PublicArtifactCheck]:
    del policy  # External URLs are never allowed in SVG.
    svg_reasons: list[str] = []
    try:
        text = raw.decode("utf-8")
        visible_xml = regex.sub(
            r"\A\s*<\?xml\s+[^?]*\?>",
            "",
            text,
            count=1,
            flags=regex.I,
        )
        if (
            "<?" in visible_xml
            or "<!--" in visible_xml
            or regex.search(r"<!DOCTYPE\b", visible_xml, flags=regex.I)
        ):
            svg_reasons.append("public_artifact_svg_hidden_content")
        root = ElementTree.fromstring(raw)
        elements = list(root.iter())
        element_ids = [
            element.attrib["id"]
            for element in elements
            if "id" in element.attrib
        ]
        known_ids = set(element_ids)
        if len(element_ids) != len(known_ids):
            svg_reasons.append("public_artifact_svg_duplicate_id")
        if _local_name(root.tag) != "svg":
            svg_reasons.append("public_artifact_svg_root_invalid")
        for element in elements:
            for text in (element.text, element.tail):
                if text:
                    svg_reasons.extend(_semantic_leak_reasons(text))
            tag = _local_name(element.tag)
            if tag in {"text", "title", "desc"}:
                svg_reasons.extend(_semantic_leak_reasons("".join(element.itertext())))
            if tag not in ALLOWED_SVG_ELEMENTS:
                svg_reasons.append("public_artifact_svg_element_forbidden")
            for raw_name, value in element.attrib.items():
                svg_reasons.extend(_semantic_leak_reasons(value))
                name = _local_name(raw_name)
                if "\\" in value or "/*" in value or "*/" in value:
                    svg_reasons.append("public_artifact_svg_url_invalid")
                if name.startswith("on") or name not in (
                    ALLOWED_SVG_ATTRIBUTES | {"href"}
                ):
                    svg_reasons.append(
                        "public_artifact_svg_attribute_forbidden"
                    )
                references = list(SVG_URL_REFERENCE.finditer(value))
                if "url(" in value.lower() and not references:
                    svg_reasons.append("public_artifact_svg_url_invalid")
                for match in references:
                    target = match.group(2)
                    if not target.startswith("#"):
                        svg_reasons.append(
                            "public_artifact_svg_external_resource_forbidden"
                        )
                    elif target[1:] not in known_ids:
                        svg_reasons.append(
                            "public_artifact_svg_local_reference_missing"
                        )
                if name == "href" and value:
                    if not value.startswith("#"):
                        svg_reasons.append(
                            "public_artifact_svg_external_resource_forbidden"
                        )
                    elif value[1:] not in known_ids:
                        svg_reasons.append(
                            "public_artifact_svg_local_reference_missing"
                        )
                if (name, value.strip().lower()) in HIDDEN_VALUES:
                    svg_reasons.append(
                        "public_artifact_svg_hidden_content"
                    )
    except (DefusedXmlException, ParseError, UnicodeDecodeError, ValueError):
        svg_reasons.append("public_artifact_svg_invalid")
    return [_check("METHOD-CUSTOM-SVG-INSPECTOR", svg_reasons)]


def _local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1]


def _runtime_versions() -> dict[str, str]:
    result: dict[str, str] = {}
    for package in (
        "defusedxml",
        "jsonschema",
        "markdown-it-py",
        "regex",
    ):
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "unavailable"
    for command in ("file",):
        path = shutil.which(command)
        result[command] = "available" if path else "unavailable"
    return dict(sorted(result.items()))


def _artifact_files_unchanged(
    manifest: PublicArtifactManifest,
) -> bool:
    for item in manifest.artifacts:
        try:
            raw = read_regular_bytes(item.path)
        except OSError:
            return False
        if hashlib.sha256(raw).hexdigest() != item.sha256:
            return False
    return True


def _ref_for_role(
    request: ToolRequestV2,
    role: str,
) -> StructuredInputRef:
    return next(ref for ref in request.object_inputs if ref.role == role)


def _input_hash(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
) -> str:
    payload = {
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "environment_spec_id": spec.environment_spec_id,
        "mode": "artifact_audit",
        "structured_inputs": [
            {
                "role": ref.role,
                "schema_ref": ref.schema_ref,
                "object_version": ref.object_version,
                "sha256": ref.sha256,
                "media_type": ref.media_type,
            }
            for ref in sorted(
                request.object_inputs,
                key=lambda item: item.role,
            )
        ],
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _failed_run(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    reasons: list[str],
    *,
    input_hash: str | None = None,
) -> ToolRunV2:
    return failed_v2_run(
        request,
        spec,
        reasons,
        result_schema_ref=RESULT_SCHEMA_REF,
        fingerprint_input_key="public_artifact_inputs",
        input_hash=input_hash,
    )


def _failed_v1_request(
    request: ToolRequest,
    spec: ToolPackageSpecV2,
) -> ToolRunV2:
    return _failed_run(
        request_v2_from_v1(request),
        spec,
        ["tool_request_v2_required"],
    )
