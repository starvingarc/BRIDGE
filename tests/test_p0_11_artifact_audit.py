from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from bridge.tool_packages.p0_11_public_safe_export.artifact_models import (
    PublicArtifactAuditPolicy,
    PublicArtifactAuditResult,
    PublicArtifactFileRef,
    PublicArtifactManifest,
)
from bridge.toolkit.contracts import (
    ExecutionState,
    StructuredInputRef,
    ToolRequestV2,
)
from bridge.toolkit.registry import ToolRegistry


CREATED_AT = "2026-08-27T00:00:00Z"
FORMATS = ("csv", "json", "markdown", "svg", "zip")
MEDIA_TYPES = {
    "csv": "text/csv",
    "json": "application/json",
    "markdown": "text/markdown",
    "svg": "image/svg+xml",
    "zip": "application/zip",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> str:
    payload = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    path.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return _sha256(path)


def _write_artifacts(root: Path, bad_format: str | None) -> list[PublicArtifactFileRef]:
    artifacts = root / "artifacts"
    artifacts.mkdir()
    paths = {
        "csv": artifacts / "table.csv",
        "json": artifacts / "result.json",
        "markdown": artifacts / "report.md",
        "svg": artifacts / "figure.svg",
        "zip": artifacts / "bundle.zip",
    }
    paths["json"].write_text(
        '{"eligible":true,"reason_codes":[],"tool_id":"P0-11"}\n',
        encoding="utf-8",
    )
    paths["markdown"].write_text(
        (
            "<div>unsafe</div>\n"
            if bad_format == "markdown"
            else "# Report\n\n[Methods](https://example.org/methods)\n"
        ),
        encoding="utf-8",
    )
    paths["csv"].write_text(
        (
            "name,value\nalpha,=SUM(1,2)\n"
            if bad_format == "csv"
            else "name,value\nalpha,1\n"
        ),
        encoding="utf-8",
    )
    paths["svg"].write_text(
        (
            '<svg xmlns="http://www.w3.org/2000/svg"><script>bad()</script></svg>\n'
            if bad_format == "svg"
            else (
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">'
                "<title>Demo</title><circle cx=\"10\" cy=\"10\" r=\"5\"/>"
                "</svg>\n"
            )
        ),
        encoding="utf-8",
    )
    with zipfile.ZipFile(paths["zip"], "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "../escape.txt" if bad_format == "zip" else "notes/readme.txt",
            "public demo\n",
        )
    return [
        PublicArtifactFileRef(
            artifact_id=f"public-artifact:{artifact_format}",
            source_artifact_ref=f"public-source:{artifact_format}@1.0.0",
            path=paths[artifact_format],
            format=artifact_format,
            media_type=MEDIA_TYPES[artifact_format],
            sha256=_sha256(paths[artifact_format]),
        )
        for artifact_format in FORMATS
    ]


def _request(root: Path, *, bad_format: str | None = None) -> ToolRequestV2:
    root.mkdir()
    inputs = root / "inputs"
    inputs.mkdir()
    policy = PublicArtifactAuditPolicy(
        object_version="0.1.0",
        policy_id="public-artifact-policy:demo",
        policy_version="1.0.0",
        active=True,
        allowed_formats=list(FORMATS),
        max_file_bytes=1_000_000,
        max_archive_entries=20,
        max_archive_uncompressed_bytes=1_000_000,
        allowed_url_schemes=["https"],
        allowed_url_hosts=["example.org"],
        json_schema_refs={
            "public-artifact:json": "bridge://schemas/eligibility-result/v0.1"
        },
        csv_column_allowlists={
            "public-artifact:csv": ["name", "value"]
        },
    )
    manifest = PublicArtifactManifest(
        object_version="0.1.0",
        manifest_id="public-artifact-manifest:demo",
        manifest_version="1.0.0",
        policy_ref=policy.ref,
        artifacts=_write_artifacts(root, bad_format),
        created_at=CREATED_AT,
    )
    objects = {
        "public_artifact_audit_policy": (
            policy,
            "bridge://schemas/public-artifact-audit-policy/v0.1",
            "policy.json",
        ),
        "public_artifact_manifest": (
            manifest,
            "bridge://schemas/public-artifact-manifest/v0.1",
            "manifest.json",
        ),
    }
    refs = []
    for role, (value, schema_ref, filename) in objects.items():
        path = inputs / filename
        checksum = _write_json(path, value)
        refs.append(
            StructuredInputRef(
                input_id=role,
                role=role,
                schema_ref=schema_ref,
                object_version="0.1.0",
                path=path,
                sha256=checksum,
                media_type="application/json",
            )
        )
    return ToolRequestV2(
        request_id=f"request-{root.name}",
        tool_id="P0-11",
        tool_version="0.3.0",
        output_dir=root / "output",
        object_inputs=refs,
    )


def test_artifact_audit_executes_all_registered_first_version_tools(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path / "safe")

    assert registry.check_eligibility(request).eligible is True
    first = registry.run(request)
    second = registry.run(request)

    assert first.execution_state is ExecutionState.SUCCEEDED
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    result = PublicArtifactAuditResult.model_validate(first.result)
    assert result.audit_state == "passed"
    assert [record.artifact_id for record in result.records] == [
        f"public-artifact:{artifact_format}" for artifact_format in FORMATS
    ]
    assert result.selected_method_ids == [
        "METHOD-ARTIFACT-PROVENANCE-CHECK",
        "METHOD-CSV-DETERMINISTIC-RULE",
        "METHOD-CUSTOM-DETERMINISTIC-RULES",
        "METHOD-CUSTOM-SVG-INSPECTOR",
        "METHOD-FORMAT-GATE",
        "METHOD-JSONSCHEMA-HASHLIB",
        "METHOD-MARKDOWN-PARSER-REGEX",
        "METHOD-OS-CLI",
        "METHOD-PANDAS-CSV-REGEX",
        "METHOD-STDLIB",
        "METHOD-URL-PARSER-ALLOWLIST",
        "METHOD-ZIPFILE-UNZIP",
    ]
    assert result.domain_score is None
    assert result.score_state == "unavailable"
    assert str(tmp_path) not in json.dumps(first.result, sort_keys=True)
    assert len(first.artifacts) == 1
    assert _sha256(first.artifacts[0].path) == first.artifacts[0].sha256


@pytest.mark.parametrize(
    ("bad_format", "reason_code"),
    [
        ("markdown", "public_artifact_markdown_html_forbidden"),
        ("csv", "public_artifact_csv_formula_injection"),
        ("svg", "public_artifact_svg_element_forbidden"),
        ("zip", "public_artifact_archive_path_unsafe"),
    ],
)
def test_unsafe_artifacts_are_successful_blocked_audits(
    tmp_path: Path,
    bad_format: str,
    reason_code: str,
) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path / bad_format, bad_format=bad_format)

    assert registry.check_eligibility(request).eligible is True
    run = registry.run(request)
    result = PublicArtifactAuditResult.model_validate(run.result)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert result.audit_state == "blocked"
    assert reason_code in {
        reason
        for record in result.records
        for check in record.checks
        for reason in check.reason_codes
    }


def test_artifact_replacement_fails_before_execution(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path / "replacement")
    manifest_ref = next(
        ref for ref in request.object_inputs if ref.role == "public_artifact_manifest"
    )
    manifest = PublicArtifactManifest.model_validate_json(
        manifest_ref.path.read_text(encoding="utf-8")
    )
    manifest.artifacts[0].path.write_text(
        "name,value\nchanged,2\n",
        encoding="utf-8",
    )

    eligibility = registry.check_eligibility(request)
    run = registry.run(request)

    assert eligibility.eligible is False
    assert eligibility.reason_codes == ["public_artifact_checksum_mismatch"]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["public_artifact_checksum_mismatch"]
    assert run.artifacts == []
