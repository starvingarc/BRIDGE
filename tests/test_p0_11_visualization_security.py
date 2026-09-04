from __future__ import annotations

import csv
import hashlib
import json
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from matplotlib.figure import Figure
from pydantic import ValidationError

from bridge.tool_packages.p0_11_public_safe_export import (
    visualization as p011_visualization,
)
from bridge.tool_packages.p0_11_public_safe_export.artifact_audit import (
    ALLOWED_SVG_ATTRIBUTES,
    _audit_artifact,
    _audit_markdown,
    _audit_svg,
    _semantic_leak_reasons,
)
from bridge.tool_packages.p0_11_public_safe_export.artifact_models import (
    ArtifactCheckState,
    PublicArtifactAuditPolicy,
    PublicArtifactAuditResult,
    PublicArtifactManifest,
)
from bridge.tool_packages.p0_11_public_safe_export.models import PublicClaimField
from bridge.tool_packages.p0_11_public_safe_export.visualization import (
    _SVG_STYLE_PROPERTIES,
    _accessibility_text,
)
from bridge.tool_packages.p0_11_public_safe_export.visualization_data import (
    PUBLIC_VISUALIZATION_SCHEMA_MODELS,
    REPORT_FIELD_PROJECTION_COMPONENT_REF,
    ArtifactAuditVisualizationDataV1,
    CandidateHashDisplayState,
    FieldProjectionState,
    P011VisualizationArtifactSet,
    PublicSafeExportVisualizationDataV1,
    RegisteredCheckDisplayState,
    ReportExportVisualizationDataV1,
)
from bridge.toolkit.contracts import ExecutionState
from bridge.toolkit.registry import ToolRegistry
from bridge.toolkit.schemas import load_schema
from tests.test_p0_11_artifact_audit import (
    _request as _audit_request,
    _sha256,
    _svg_policy,
)
from tests.test_p0_11_public_safe_export import _tool_request


def _artifact(run, *, kind: str):
    return next(item for item in run.artifacts if item.kind == kind)


def _profile(run):
    artifact = _artifact(run, kind="public_safe_export_visualization_data")
    return PublicSafeExportVisualizationDataV1.model_validate_json(
        artifact.path.read_bytes()
    ).root


def _artifact_set(run) -> P011VisualizationArtifactSet:
    artifact = _artifact(run, kind="visualization_artifact_set")
    return P011VisualizationArtifactSet.model_validate_json(artifact.path.read_bytes())


def _table_rows(run, table_artifact_id: str) -> list[dict[str, str]]:
    artifact = next(item for item in run.artifacts if item.artifact_id == table_artifact_id)
    return list(csv.DictReader(StringIO(artifact.path.read_text()), delimiter="\t"))


def _audit_direct(root: Path, artifact_format: str, raw: bytes):
    request = _audit_request(root)
    policy_ref = next(
        item
        for item in request.object_inputs
        if item.role == "public_artifact_audit_policy"
    )
    manifest_ref = next(
        item
        for item in request.object_inputs
        if item.role == "public_artifact_manifest"
    )
    policy = PublicArtifactAuditPolicy.model_validate_json(policy_ref.path.read_bytes())
    manifest = PublicArtifactManifest.model_validate_json(manifest_ref.path.read_bytes())
    source = next(item for item in manifest.artifacts if item.format == artifact_format)
    source.path.write_bytes(raw)
    source = source.model_copy(update={"sha256": hashlib.sha256(raw).hexdigest()})
    return _audit_artifact(source, policy)


def _all_reasons(record) -> set[str]:
    return {
        reason
        for check in record.checks
        for reason in check.reason_codes
    }


def test_report_visualization_bundle_is_complete_minimized_and_hash_bound(
    tmp_path: Path,
) -> None:
    run = ToolRegistry.load_default().run(
        _tool_request(
            tmp_path / "report-visualization",
            allowlisted_fields=sorted(item.value for item in PublicClaimField),
        )
    )

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert len(run.artifacts) == 14
    internal_manifest = json.loads(
        _artifact(run, kind="artifact_manifest").path.read_text()
    )
    assert internal_manifest["scope"] == "internal_run_provenance"
    assert len(internal_manifest["artifacts"]) == 13

    profile = _profile(run)
    assert isinstance(profile, ReportExportVisualizationDataV1)
    assert profile.candidate_hash == run.result["candidate_hash"]
    assert (
        profile.candidate_hash_state
        is CandidateHashDisplayState.AWAITING_MATCHING_CANDIDATE_HASH
    )
    by_field = {record.field: record for record in profile.field_records}
    assert (
        by_field[PublicClaimField.STATEMENT_REFS].projection_state
        is FieldProjectionState.INCLUDED
    )
    assert (
        by_field[PublicClaimField.REPORTED_EVIDENCE_STATE].projection_state
        is FieldProjectionState.NOT_APPLICABLE_IN_SOURCE
    )

    artifact_set = _artifact_set(run)
    assert len(artifact_set.visualizations) == 2
    assert all(len(item.renders) == 3 for item in artifact_set.visualizations)
    tables = [
        _table_rows(run, item.accessibility.table_artifact_id)
        for item in artifact_set.visualizations
    ]
    assert [len(rows) for rows in tables] == [6, 5]
    assert all(
        {
            "record_id",
            "evidence_ids",
            "evidence_state",
            "scientific_status",
            "missingness",
            "applicability",
            "display_state",
            "reason_codes",
        }
        <= set(rows[0])
        for rows in tables
    )
    assert all(row["candidate_hash"] == profile.candidate_hash for row in tables[1])

    excluded = (
        "The public demonstration result is available.",
        "claim-block:internal-demo",
        str(tmp_path),
    )
    for artifact in run.artifacts:
        if artifact.kind in {
            "public_safe_export_visualization_data",
            "visualization_table",
            "visualization_render",
            "visualization_artifact_set",
        }:
            payload = artifact.path.read_bytes()
            assert all(value.encode() not in payload for value in excluded)


def test_candidate_digest_state_changes_without_changing_candidate_hash(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    candidate = registry.run(_tool_request(tmp_path / "candidate"))
    supplied = registry.run(
        _tool_request(
            tmp_path / "supplied",
            confirmation_hash=candidate.result["candidate_hash"],
        )
    )

    first = _profile(candidate)
    second = _profile(supplied)
    assert first.candidate_hash == second.candidate_hash
    assert (
        first.candidate_hash_state
        is CandidateHashDisplayState.AWAITING_MATCHING_CANDIDATE_HASH
    )
    assert (
        second.candidate_hash_state
        is CandidateHashDisplayState.MATCHING_CANDIDATE_HASH_SUPPLIED
    )
    ledger = _artifact_set(supplied).visualizations[1]
    rows = _table_rows(supplied, ledger.accessibility.table_artifact_id)
    assert all(row["candidate_hash"] == first.candidate_hash for row in rows)
    assert "authenticate" in ledger.accessibility.alt_text


def test_report_static_capacity_uses_complete_table_fallback(tmp_path: Path) -> None:
    run = ToolRegistry.load_default().run(
        _tool_request(tmp_path / "capacity", claim_count=19)
    )

    profile = _profile(run)
    figure = _artifact_set(run).visualizations[0]
    rows = _table_rows(run, figure.accessibility.table_artifact_id)
    assert len(profile.field_records) == 19 * len(PublicClaimField)
    assert len(rows) == 19 * len(PublicClaimField)
    assert figure.applicability == "partially_applicable"
    assert figure.missing_reason_codes == [
        "static_render_requires_complete_table_fallback"
    ]
    large_profile = profile.model_copy(update={"claim_count": 10_000})
    alt_text, _ = _accessibility_text(
        large_profile,
        REPORT_FIELD_PROJECTION_COMPONENT_REF,
    )
    assert len(alt_text) <= 240


@pytest.mark.parametrize(
    "text",
    [
        "Contact alice&#64;example.org.",
        "Contact alice\u200b@example.org.",
        "Contact alice＠example.org.",
        "See %2Fopt%2Frestricted%2Frecord.",
        r"Open C:\restricted\record.txt.",
        r"Open \\private-host\restricted\record.txt.",
        "Private endpoint 10.23.45.67.",
    ],
)
def test_report_semantic_canaries_fail_without_output_or_echo(
    tmp_path: Path,
    text: str,
) -> None:
    run = ToolRegistry.load_default().run(
        _tool_request(
            tmp_path / hashlib.sha256(text.encode()).hexdigest()[:12],
            text=text,
        )
    )

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["public_payload_leak_detected"]
    assert run.artifacts == []
    assert text not in json.dumps(run.model_dump(mode="json"), ensure_ascii=False)


def test_report_metadata_canary_has_one_generic_reason_and_no_echo(
    tmp_path: Path,
) -> None:
    canary = "public-export-policy:private_internal"
    run = ToolRegistry.load_default().run(
        _tool_request(tmp_path / "metadata", policy_id=canary)
    )

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["public_artifact_metadata_leak_detected"]
    assert run.artifacts == []
    assert canary not in json.dumps(run.model_dump(mode="json"))


def test_artifact_metadata_canary_has_one_generic_reason_and_no_echo(
    tmp_path: Path,
) -> None:
    canary = "public-artifact-policy:private_internal"
    run = ToolRegistry.load_default().run(
        _audit_request(tmp_path / "artifact-metadata", policy_id=canary)
    )

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["public_artifact_metadata_leak_detected"]
    assert run.artifacts == []
    assert canary not in json.dumps(run.model_dump(mode="json"))


def test_artifact_visualization_grid_is_explicit_and_minimized(
    tmp_path: Path,
) -> None:
    request = _audit_request(tmp_path / "audit")
    source_manifest_ref = next(
        item
        for item in request.object_inputs
        if item.role == "public_artifact_manifest"
    )
    source_manifest = PublicArtifactManifest.model_validate_json(
        source_manifest_ref.path.read_bytes()
    )
    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert len(run.artifacts) == 12
    internal_manifest = json.loads(
        _artifact(run, kind="artifact_manifest").path.read_text()
    )
    assert internal_manifest["scope"] == "internal_run_provenance"
    assert len(internal_manifest["artifacts"]) == 11

    result = PublicArtifactAuditResult.model_validate(run.result)
    profile = _profile(run)
    assert isinstance(profile, ArtifactAuditVisualizationDataV1)
    assert profile.artifact_count == 4
    assert profile.registered_method_count == 8
    assert len(profile.check_records) == 32
    for display_id in {item.artifact_display_id for item in profile.artifact_records}:
        records = [
            item for item in profile.check_records
            if item.artifact_display_id == display_id
        ]
        assert len(records) == 8
        summary = next(
            item for item in profile.artifact_records
            if item.artifact_display_id == display_id
        )
        assert summary.check_count == sum(
            item.check_state is not RegisteredCheckDisplayState.NOT_APPLICABLE
            for item in records
        )

    excluded = {
        item.artifact_id for item in result.records
    } | {
        item.source_artifact_ref for item in result.records
    } | {
        str(item.path) for item in source_manifest.artifacts
    }
    for artifact in run.artifacts:
        if artifact.kind in {
            "public_safe_export_visualization_data",
            "visualization_table",
            "visualization_render",
            "visualization_artifact_set",
        }:
            payload = artifact.path.read_bytes()
            assert all(value.encode() not in payload for value in excluded)

def test_multiple_artifact_reasons_use_complete_table_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _unexpected_renderer(_profile):
        raise AssertionError("multi-reason status must not use the row renderer")

    monkeypatch.setattr(
        "bridge.tool_packages.p0_11_public_safe_export.visualization."
        "_render_artifact_status",
        _unexpected_renderer,
    )
    run = ToolRegistry.load_default().run(
        _audit_request(tmp_path / "multi-reason", bad_format="csv")
    )

    assert run.execution_state is ExecutionState.SUCCEEDED
    profile = _profile(run)
    summary = next(
        record for record in profile.artifact_records
        if len(record.reason_codes) > 1
    )
    status = _artifact_set(run).visualizations[0]
    assert status.component_id == "bridge.public-safe-export.artifact-status"
    assert status.applicability == "partially_applicable"
    assert status.missing_reason_codes == [
        "static_render_requires_complete_table_fallback"
    ]
    assert [render.media_type for render in status.renders] == [
        "image/svg+xml",
        "image/png",
        "application/pdf",
    ]

    rows = _table_rows(run, status.accessibility.table_artifact_id)
    row = next(
        item for item in rows
        if item["artifact_display_id"] == summary.artifact_display_id
    )
    assert json.loads(row["reason_codes"]) == summary.reason_codes
    assert len(json.loads(row["reason_labels"])) == len(summary.reason_codes)

@pytest.mark.parametrize(
    "value",
    [
        "alice&#64;example.org",
        "alice\u200b@example.org",
        "alice＠example.org",
        r"C:\restricted\record.txt",
        r"\\private-host\restricted\record.txt",
        "10.23.45.67",
        "／opt／restricted／record",
        "alice%25252540example.org",
    ],
)
def test_semantic_scanner_canonicalizes_registered_canaries(value: str) -> None:
    assert _semantic_leak_reasons(value) == [
        "public_artifact_leak_pattern_detected"
    ]


@pytest.mark.parametrize(
    "raw",
    [
        b"[ok](https://example.org/%2fetc%2fpasswd)",
        b"[visible]: https://example.org \"u%73er%40example.com\"\n\n[visible]",
        b"[u%73er%40example.com]: https://example.org",
        b"alice@**example**.org",
        b"api_**key**=secret",
    ],
)
def test_markdown_semantic_canaries_are_blocked(
    tmp_path: Path, raw: bytes
) -> None:
    record = _audit_direct(
        tmp_path / hashlib.sha256(raw).hexdigest()[:12], "markdown", raw
    )
    assert record.audit_state == "blocked"
    assert "public_artifact_leak_pattern_detected" in _all_reasons(record)


def test_normal_allowlisted_markdown_url_remains_unblocked() -> None:
    checks = _audit_markdown(b"[Methods](https://example.org/methods)", _svg_policy())
    assert all(check.state is ArtifactCheckState.PASSED for check in checks)

def test_remote_markdown_image_is_blocked_even_on_allowlisted_host() -> None:
    checks = _audit_markdown(
        b"![plot](https://example.org/image.png)",
        _svg_policy(),
    )
    assert checks[1].state is ArtifactCheckState.BLOCKED
    assert checks[1].reason_codes == ["public_artifact_url_not_allowed"]



@pytest.mark.parametrize(
    ("artifact_format", "raw"),
    [
        (
            "json",
            b'{"eligible":true,"reason_codes":["alice&#64;example.org"],"tool_id":"P0-11"}',
        ),
        ("csv", "name,value\nalpha,alice\u200b@example.org\n".encode()),
        (
            "svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><text>user@<tspan>example.com</tspan></text></svg>',
        ),
        (
            "svg",
            b'<?xml-stylesheet href="https://example.org/x.css"?><svg xmlns="http://www.w3.org/2000/svg"/>',
        ),
        (
            "svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><!-- hidden --></svg>',
        ),
        (
            "svg",
            b'<!DOCTYPE svg><svg xmlns="http://www.w3.org/2000/svg"/>',
        ),
        (
            "svg",
            b'<!DOCTYPE svg SYSTEM "https://example.org/test.dtd"><svg xmlns="http://www.w3.org/2000/svg"/>',
        ),
        (
            "svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><path fill="u\\72 l(https://example.org/x)"/></svg>',
        ),
        (
            "svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><path fill="\\75\\72\\6c(https://example.org/x)"/></svg>',
        ),
        (
            "svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><path fill="url\\28 https://example.org/x\\29"/></svg>',
        ),
    ],
)
def test_format_specific_semantic_and_hidden_content_is_blocked(
    tmp_path: Path,
    artifact_format: str,
    raw: bytes,
) -> None:
    record = _audit_direct(
        tmp_path / hashlib.sha256(raw).hexdigest()[:12],
        artifact_format,
        raw,
    )
    assert record.audit_state == "blocked"
    reasons = _all_reasons(record)
    assert reasons & {
        "public_artifact_leak_pattern_detected",
        "public_artifact_svg_hidden_content",
        "public_artifact_svg_url_invalid",
    }


def test_generated_visualization_media_are_deterministic_and_self_auditable(
    tmp_path: Path,
) -> None:
    first = ToolRegistry.load_default().run(
        _tool_request(tmp_path / "generated-a")
    )
    second = ToolRegistry.load_default().run(
        _tool_request(tmp_path / "generated-b")
    )
    first_renders = {
        item.path.name: item.path.read_bytes()
        for item in first.artifacts
        if item.kind == "visualization_render"
    }
    second_renders = {
        item.path.name: item.path.read_bytes()
        for item in second.artifacts
        if item.kind == "visualization_render"
    }
    assert first_renders == second_renders
    for artifact in first.artifacts:
        if artifact.kind != "visualization_render":
            continue
        payload = artifact.path.read_bytes()
        if artifact.media_type == "image/svg+xml":
            assert b"<!DOCTYPE" not in payload
            assert b"<metadata" not in payload
            assert b"Matplotlib" not in payload
            assert all(
                check.state is ArtifactCheckState.PASSED
                for check in _audit_svg(payload, _svg_policy())
            )
        elif artifact.media_type == "application/pdf":
            assert b"Matplotlib" not in payload
            assert b"/CreationDate" not in payload
            assert b"/ModDate" not in payload
            assert b"/Producer (BRIDGE)" in payload
        elif artifact.media_type == "image/png":
            assert b"Matplotlib" not in payload
            assert b"Creation Time" not in payload


def test_generated_svg_style_rules_are_no_broader_than_audit_rules() -> None:
    assert _SVG_STYLE_PROPERTIES <= ALLOWED_SVG_ATTRIBUTES


@pytest.mark.parametrize(
    "schema_ref,model",
    PUBLIC_VISUALIZATION_SCHEMA_MODELS.items(),
)
def test_p0_11_visualization_schema_files_are_exact_exports(
    schema_ref: str,
    model: type[Any],
) -> None:
    expected = model.model_json_schema()
    expected["$id"] = schema_ref
    actual = load_schema(schema_ref)

    Draft202012Validator.check_schema(actual)
    assert actual == expected


def test_existing_v0_1_result_schema_bytes_remain_unchanged() -> None:
    expected = {
        "public_export_result.schema.json":
            "8537b6dd43850e16ea5d8149e366b920bbd716ed06a11eb99d01881a19715c03",
        "public_artifact_audit_result.schema.json":
            "b0f7e0700e0d2c9911b8d3918463c3211768fa5ad5e5a10071f581f882e59795",
        "public_safe_export_run_result.schema.json":
            "23f4701b61f40429432489c6da72fbc385526912e81d8b0da3a42b1345901402",
    }
    root = Path("src/bridge/resources/schemas")
    assert {
        name: _sha256(root / name)
        for name in expected
    } == expected


def test_visualization_models_reject_uncontrolled_reasons_and_incomplete_sets(
    tmp_path: Path,
) -> None:
    run = ToolRegistry.load_default().run(_audit_request(tmp_path / "tamper"))
    profile = _profile(run)
    payload = profile.model_dump(mode="json")
    payload["check_records"][0]["reason_codes"] = ["patient_identifier"]
    with pytest.raises(ValidationError):
        ArtifactAuditVisualizationDataV1.model_validate(payload)

    artifact_set = _artifact_set(run)
    set_payload = artifact_set.model_dump(mode="json")
    set_payload["visualizations"][0]["renders"].pop()
    with pytest.raises(ValidationError):
        P011VisualizationArtifactSet.model_validate(set_payload)


@pytest.mark.parametrize(
    "target",
    [
        "bridge.tool_packages.p0_11_public_safe_export.adapter.prepare_public_safe_export_visualizations",
        "bridge.tool_packages.p0_11_public_safe_export.artifact_audit.prepare_public_safe_export_visualizations",
    ],
)
def test_render_failure_fails_before_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    canary = "synthetic@example.org /opt/restricted/render"

    def _fail(**_kwargs):
        raise ValueError(canary)

    monkeypatch.setattr(target, _fail)
    request = (
        _tool_request(tmp_path / "report-failure")
        if ".adapter." in target
        else _audit_request(tmp_path / "audit-failure")
    )
    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["visualization_render_failed"]
    assert run.artifacts == []
    final_dir = request.output_dir / run.run_id
    assert not final_dir.exists()
    assert canary not in json.dumps(run.model_dump(mode="json"))


@pytest.mark.parametrize("mode", ["report_export", "artifact_audit"])
def test_generated_svg_parse_failure_is_a_typed_run_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    def _invalid_svg(
        _figure,
        target,
        *,
        format: str,
        **_kwargs,
    ) -> None:
        assert format == "svg"
        target.write(b"<svg")

    monkeypatch.setattr(Figure, "savefig", _invalid_svg)
    request = (
        _tool_request(tmp_path / "report-svg-parse-failure")
        if mode == "report_export"
        else _audit_request(tmp_path / "audit-svg-parse-failure")
    )
    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["visualization_render_failed"]
    assert run.artifacts == []
    assert not (request.output_dir / run.run_id).exists()


@pytest.mark.parametrize(
    "drift",
    ["producer", "schema", "surface", "interaction"],
)
def test_figure_registry_contract_drift_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    original = p011_visualization._visualization_contract

    def _drifted_contract(**kwargs):
        artifact = original(**kwargs)
        if drift == "producer":
            return artifact.model_copy(update={"producer_tool_id": "P0-10"})
        if drift == "schema":
            binding = artifact.data_binding.model_copy(
                update={"schema_ref": "bridge://schemas/eligibility-result/v0.1"}
            )
            return artifact.model_copy(update={"data_binding": binding})
        if drift == "surface":
            png_only = [
                render
                for render in artifact.renders
                if render.media_type == "image/png"
            ]
            return artifact.model_copy(update={"renders": png_only})
        interactions = artifact.interactions.model_copy(
            update={"filter_ids": ["unexpected_filter"]}
        )
        return artifact.model_copy(update={"interactions": interactions})

    monkeypatch.setattr(
        p011_visualization,
        "_visualization_contract",
        _drifted_contract,
    )
    request = _tool_request(tmp_path / f"registry-{drift}")
    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["visualization_render_failed"]
    assert run.artifacts == []
    assert not (request.output_dir / run.run_id).exists()


def test_unknown_visualization_component_ref_is_rejected() -> None:
    with pytest.raises(KeyError):
        p011_visualization._records(
            object(),
            "bridge.public-safe-export.unknown@0.1.0",
        )
