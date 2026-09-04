from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from bridge.tool_packages.p0_11_public_safe_export.artifact_audit import (
    METHOD_IMPLEMENTATIONS,
    _audit_artifact,
    _audit_markdown,
    _audit_svg,
    _semantic_leak_reasons,
    _manifest_ref_syntax_reasons,
    _url_allowed,
)
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
FORMATS = ("csv", "json", "markdown", "svg")
MEDIA_TYPES = {
    "csv": "text/csv",
    "json": "application/json",
    "markdown": "text/markdown",
    "svg": "image/svg+xml",
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
                '<title>Demo</title><defs><clipPath id="clip">'
                '<rect x="0" y="0" width="20" height="20"/>'
                '</clipPath></defs><circle cx="10" cy="10" r="5" '
                'clip-path="url(#clip)"/>'
                "</svg>\n"
            )
        ),
        encoding="utf-8",
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


def _request(
    root: Path,
    *,
    bad_format: str | None = None,
    policy_id: str = "public-artifact-policy:demo",
) -> ToolRequestV2:
    root.mkdir()
    inputs = root / "inputs"
    inputs.mkdir()
    policy = PublicArtifactAuditPolicy(
        object_version="0.1.0",
        policy_id=policy_id,
        policy_version="1.0.0",
        active=True,
        allowed_formats=list(FORMATS),
        max_file_bytes=1_000_000,
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
        tool_version="0.4.0",
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
        "METHOD-CSV-DETERMINISTIC-RULE",
        "METHOD-CUSTOM-DETERMINISTIC-RULES",
        "METHOD-CUSTOM-SVG-INSPECTOR",
        "METHOD-FORMAT-GATE",
        "METHOD-JSONSCHEMA-HASHLIB",
        "METHOD-MARKDOWN-PARSER-REGEX",
        "METHOD-OS-CLI",
        "METHOD-URL-PARSER-ALLOWLIST",
    ]
    assert result.domain_score is None
    assert result.score_state == "unavailable"
    assert str(tmp_path) not in json.dumps(first.result, sort_keys=True)
    assert len(first.artifacts) == 12
    for artifact in first.artifacts:
        assert _sha256(artifact.path) == artifact.sha256


@pytest.mark.parametrize(
    ("bad_format", "reason_code"),
    [
        ("markdown", "public_artifact_markdown_html_forbidden"),
        ("csv", "public_artifact_csv_formula_injection"),
        ("svg", "public_artifact_svg_element_forbidden"),
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


def _svg_policy() -> PublicArtifactAuditPolicy:
    return PublicArtifactAuditPolicy(
        object_version="0.1.0",
        policy_id="public-artifact-policy:svg-test",
        policy_version="1.0.0",
        active=True,
        allowed_formats=["svg"],
        max_file_bytes=1_000_000,
        allowed_url_schemes=["https"],
        allowed_url_hosts=["example.org"],
        json_schema_refs={},
        csv_column_allowlists={},
    )


@pytest.mark.parametrize(
    "target",
    [
        "http://example.org/file",
        "https://user@example.org/file",
        "https://example.org:8443/file",
        "https://example.org/file?download=1",
        "https://example.org/file#section",
    ],
)
def test_external_urls_reject_ambiguous_or_stateful_targets(target: str) -> None:
    assert not _url_allowed(target, _svg_policy())


@pytest.mark.parametrize(
    "target",
    ["https://example.org/file", "https://example.org:443/file"],
)
def test_external_urls_accept_only_plain_https_allowlist_targets(
    target: str,
) -> None:
    assert _url_allowed(target, _svg_policy())


@pytest.mark.parametrize(
    ("target", "reason"),
    [
        ("#missing", "public_artifact_svg_local_reference_missing"),
        (
            "https://example.org/paint",
            "public_artifact_svg_external_resource_forbidden",
        ),
    ],
)
def test_svg_url_references_are_existing_local_fragments_only(
    target: str,
    reason: str,
) -> None:
    raw = (
        '<svg xmlns="http://www.w3.org/2000/svg"><defs>'
        '<linearGradient id="known"/></defs>'
        f'<circle fill="url({target})" cx="1" cy="1" r="1"/></svg>'
    ).encode()

    checks = _audit_svg(raw, _svg_policy())

    assert reason in {
        item
        for check in checks
        for item in check.reason_codes
    }


def test_manifest_ref_check_is_syntax_only_not_provenance_authority() -> None:
    assert _manifest_ref_syntax_reasons("public-source:demo@1.0.0") == []
    assert _manifest_ref_syntax_reasons("internal-source:demo@1.0.0") == [
        "public_artifact_source_ref_syntax_invalid"
    ]
    assert "METHOD-ARTIFACT-PROVENANCE-CHECK" not in METHOD_IMPLEMENTATIONS
    assert "manifest-ref syntax" in METHOD_IMPLEMENTATIONS[
        "METHOD-CUSTOM-DETERMINISTIC-RULES"
    ]


@pytest.mark.parametrize(
    "text",
    [
        "-----BEGIN PRIVATE KEY-----",
        "/opt/review-canary/project/config",
        "internal-host-canary",
        "conda activate private-env-canary",
    ],
)
def test_leak_scan_blocks_sensitive_canary_classes(text: str) -> None:
    assert _semantic_leak_reasons(text) == [
        "public_artifact_leak_pattern_detected"
    ]


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "127.0.0.01",
        "localhost",
        "compute-node",
        "service.internal",
        "service.localdomain",
        "service.example",
        "service.alt",
        "home.arpa",
        "router.home.arpa",
        "UPPER.example.org",
    ],
)
def test_url_policy_rejects_non_public_hosts(host: str) -> None:
    with pytest.raises(ValueError, match="static public-DNS policy"):
        PublicArtifactAuditPolicy(
            object_version="0.1.0",
            policy_id="public-artifact-policy:host-test",
            policy_version="1.0.0",
            active=True,
            allowed_formats=["markdown"],
            max_file_bytes=1_000_000,
            allowed_url_schemes=["https"],
            allowed_url_hosts=[host],
            json_schema_refs={},
            csv_column_allowlists={},
        )


@pytest.mark.parametrize(
    "target",
    [
        "https://not-allowlisted.example/path",
        "https://example.org@not-allowlisted.example/path",
        "http://example.org/path",
        "www.example.org/path",
    ],
)
def test_markdown_extended_autolinks_are_checked(target: str) -> None:
    checks = _audit_markdown(f"See {target}\n".encode(), _svg_policy())
    url_check = next(
        check
        for check in checks
        if check.method_id == "METHOD-URL-PARSER-ALLOWLIST"
    )
    assert url_check.state == "blocked"
    assert url_check.reason_codes == ["public_artifact_url_not_allowed"]


def test_markdown_allowed_bare_https_url_remains_valid() -> None:
    checks = _audit_markdown(
        b"See https://example.org/methods.\n",
        _svg_policy(),
    )
    url_check = next(
        check
        for check in checks
        if check.method_id == "METHOD-URL-PARSER-ALLOWLIST"
    )
    assert url_check.state == "passed"


def test_audit_binds_checks_to_the_hashed_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "report.md"
    original = b"# Public report\n"
    replacement = b"# Replaced report\n"
    path.write_bytes(original)
    item = PublicArtifactFileRef(
        artifact_id="public-artifact:markdown",
        source_artifact_ref="public-source:markdown@1.0.0",
        path=path,
        format="markdown",
        media_type="text/markdown",
        sha256=hashlib.sha256(original).hexdigest(),
    )
    monkeypatch.setattr(
        "bridge.tool_packages.p0_11_public_safe_export.artifact_audit.read_regular_bytes",
        lambda _: replacement,
    )

    with pytest.raises(OSError, match="changed before audit"):
        _audit_artifact(item, _svg_policy())
