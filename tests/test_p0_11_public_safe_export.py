from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from bridge.tool_packages.p0_10_claim_verifier.models import (
    ClaimVerificationResult,
    ReportDraft,
    report_content_hash,
)
from bridge.tool_packages.p0_11_public_safe_export.models import (
    PublicExportManifest,
    PublicExportPolicySpec,
    PublicExportRequest,
    PublicExportResult,
    PublicSafeReport,
)
from bridge.toolkit.contracts import (
    ExecutionState,
    ImplementationState,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
)
from bridge.toolkit.registry import ToolRegistry


CREATED_AT = "2026-08-25T00:00:00Z"
PRODUCT_CASE_REF = "product-case:internal-demo@1.0.0"
STATEMENT_REF = "statement:approved-public-note@1.0.0"


def _write(path: Path, value: object) -> str:
    payload = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    path.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _report(
    *,
    text: str = "The public demonstration result is available.",
    statement_refs: list[str] | None = None,
) -> ReportDraft:
    payload: dict[str, Any] = {
        "object_version": "0.1.0",
        "report_id": "report:internal-demo",
        "report_version": "1.0.0",
        "content_hash": "0" * 64,
        "audience": "public_candidate",
        "language": "en",
        "evidence_record_set_ref": "evidence-record-set:internal-demo@1.0.0",
        "claim_policy_ref": "claim-policy:p0-10-public@0.1.0",
        "statement_registry_ref": "BRIDGE-STATEMENT-REGISTRY-v0.1@0.1.0",
        "claim_blocks": [
            {
                "claim_id": "claim-block:internal-demo",
                "claim_version": "1.0.0",
                "claim_ref": "claim:internal-demo@1.0.0",
                "product_case_ref": PRODUCT_CASE_REF,
                "claim_type": "policy_or_boundary_statement",
                "text": text,
                "language": "en",
                "evidence_refs": [],
                "statement_refs": statement_refs or [],
                "value_bindings": [],
                "reported_evidence_state": None,
                "comparison_mode": "not_applicable",
                "authoring_channel": "deterministic_renderer",
            }
        ],
        "renderer_id": "BRIDGE-REPORT-DRAFT-RENDERER-v0.1",
        "renderer_version": "0.1.0",
        "authoring_channel": "deterministic_renderer",
        "created_at": CREATED_AT,
    }
    payload["content_hash"] = report_content_hash(payload)
    return ReportDraft.model_validate(payload)


def _receipt(report: ReportDraft, *, report_hash: str | None = None) -> ClaimVerificationResult:
    return ClaimVerificationResult.model_validate(
        {
            "object_version": "0.1.0",
            "verification_id": "claim-verification:" + "a" * 16,
            "verifier_version": "0.1.0",
            "benchmark_id": "P0-10-BENCHMARK-v0.1",
            "benchmark_sha256": "908da7e8c8141e5f44e230315134d53fb63dbc6856b37e06a3b227fe2af51baa",
            "release_contract_id": "P0-10-RELEASE-CONTRACT-v0.1",
            "release_contract_sha256": "c8a9237652cba4e6b3eb1c4f4215437980f0f480a0944d232abddeef5c4236c8",
            "report_draft_ref": report.ref,
            "report_content_hash": report_hash or report.content_hash,
            "report_audience": "public_candidate",
            "evidence_graph_id": "case-evidence-graph:internal-demo",
            "evidence_graph_version": 1,
            "evidence_graph_manifest_sha256": "b" * 64,
            "claim_policy_ref": "claim-policy:p0-10-public@0.1.0",
            "statement_registry_ref": "BRIDGE-STATEMENT-REGISTRY-v0.1@0.1.0",
            "release_state": "verified",
            "check_records": [],
            "public_export_eligibility": "eligible",
        }
    )


def _policy(
    *,
    active: bool = True,
    aliases: dict[str, str] | None = None,
    allowed_statements: list[str] | None = None,
) -> PublicExportPolicySpec:
    return PublicExportPolicySpec(
        object_version="0.1.0",
        policy_id="public-export-policy:json-demo",
        policy_version="1.0.0",
        active=active,
        report_audience="public_candidate",
        target_channels=["public_json"],
        allowlisted_claim_fields=[
            "claim_type",
            "language",
            "statement_refs",
            "text",
        ],
        public_case_aliases=aliases or {PRODUCT_CASE_REF: "Demo case"},
        allowed_statement_refs=allowed_statements or [],
    )


def _tool_request(
    root: Path,
    *,
    text: str = "The public demonstration result is available.",
    statement_refs: list[str] | None = None,
    allowed_statements: list[str] | None = None,
    aliases: dict[str, str] | None = None,
    active: bool = True,
    confirmation_hash: str | None = None,
    receipt_report_hash: str | None = None,
    request_policy_ref: str | None = None,
) -> ToolRequestV2:
    root.mkdir()
    inputs = root / "inputs"
    inputs.mkdir()
    report = _report(text=text, statement_refs=statement_refs)
    receipt = _receipt(report, report_hash=receipt_report_hash)
    policy = _policy(
        active=active,
        aliases=aliases,
        allowed_statements=allowed_statements,
    )
    export_request = PublicExportRequest(
        object_version="0.1.0",
        export_request_id="public-export-request:demo",
        report_draft_ref=report.ref,
        policy_ref=request_policy_ref or policy.ref,
        target_channel="public_json",
        confirmation_hash=confirmation_hash,
        created_at=CREATED_AT,
    )
    objects = {
        "report_draft": (
            report,
            "bridge://schemas/report-draft/v0.1",
            "report.json",
        ),
        "claim_verification_result": (
            receipt,
            "bridge://schemas/claim-verification-result/v0.1",
            "receipt.json",
        ),
        "public_export_policy": (
            policy,
            "bridge://schemas/public-export-policy-spec/v0.1",
            "policy.json",
        ),
        "public_export_request": (
            export_request,
            "bridge://schemas/public-export-request/v0.1",
            "request.json",
        ),
    }
    refs = []
    for role, (value, schema_ref, filename) in objects.items():
        path = inputs / filename
        checksum = _write(path, value)
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


def test_registry_declares_executable_v2_contract() -> None:
    spec = ToolRegistry.load_default().describe("P0-11")

    assert isinstance(spec, ToolPackageSpecV2)
    assert spec.implementation_state is ImplementationState.IMPLEMENTED
    assert spec.method_ids == [
        "METHOD-BRIDGE-ALGORITHM-2AFBC8",
        "METHOD-BRIDGE-RULE-ENGINE",
        "METHOD-CSV-DETERMINISTIC-RULE",
        "METHOD-CUSTOM-DETERMINISTIC-RULES",
        "METHOD-CUSTOM-SVG-INSPECTOR",
        "METHOD-FORMAT-GATE",
        "METHOD-JSONSCHEMA-HASHLIB",
        "METHOD-MARKDOWN-PARSER-REGEX",
        "METHOD-OS-CLI",
        "METHOD-URL-PARSER-ALLOWLIST",
    ]
    assert spec.result_schema_ref == "bridge://schemas/public-safe-export-run-result/v0.1"


def test_candidate_run_rebuilds_three_checksummed_public_json_artifacts(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    request = _tool_request(tmp_path / "candidate")

    assert registry.check_eligibility(request).eligible is True
    run = registry.run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.measurements == []
    assert run.visualizations == []
    assert len(run.artifacts) == 3
    result = PublicExportResult.model_validate(run.result)
    assert result.export_state == "ready_for_confirmation"
    assert result.domain_score is None
    assert result.score_state == "unavailable"
    for artifact in run.artifacts:
        assert hashlib.sha256(artifact.path.read_bytes()).hexdigest() == artifact.sha256

    report_artifact = next(item for item in run.artifacts if item.kind == "public_safe_report")
    public_report = PublicSafeReport.model_validate_json(report_artifact.path.read_text())
    assert public_report.claims[0].public_case_alias == "Demo case"
    serialized = report_artifact.path.read_text()
    for restricted in (
        "claim_ref",
        "product_case_ref",
        "evidence_refs",
        "value_bindings",
        "renderer_id",
        "sample:",
        "preparation:",
    ):
        assert restricted not in serialized


def test_matching_confirmation_exports_same_candidate_without_upload(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    candidate = registry.run(_tool_request(tmp_path / "candidate"))
    candidate_hash = candidate.result["candidate_hash"]

    confirmed = registry.run(
        _tool_request(tmp_path / "confirmed", confirmation_hash=candidate_hash)
    )

    result = PublicExportResult.model_validate(confirmed.result)
    assert confirmed.execution_state is ExecutionState.SUCCEEDED
    assert result.export_state == "exported"
    assert result.confirmation_hash == candidate_hash
    assert result.candidate_hash == candidate_hash


def test_confirmation_mismatch_fails_without_artifacts(tmp_path: Path) -> None:
    run = ToolRegistry.load_default().run(
        _tool_request(tmp_path / "mismatch", confirmation_hash="f" * 64)
    )

    assert run.execution_state is ExecutionState.FAILED
    assert run.artifacts == []
    assert run.reason_codes == ["confirmation_hash_mismatch"]


@pytest.mark.parametrize(
    "text",
    [
        "Private path /" + "mnt/internal-team/run must not be public.",
        "Contact alice@example.org for details.",
        "Credential api_key=super-secret-value is private.",
        "Internal evidence:abcdef must not appear.",
        "Internal sample:private-1 must not appear.",
        "The source hostname is compute-node-17.",
    ],
)
def test_leak_canaries_fail_closed(tmp_path: Path, text: str) -> None:
    run = ToolRegistry.load_default().run(
        _tool_request(tmp_path / hashlib.sha256(text.encode()).hexdigest()[:8], text=text)
    )

    assert run.execution_state is ExecutionState.FAILED
    assert run.artifacts == []
    assert run.reason_codes == ["public_payload_leak_detected"]


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        (
            {"receipt_report_hash": "f" * 64},
            "verification_receipt_report_binding_mismatch",
        ),
        (
            {"active": False},
            "public_export_policy_inactive",
        ),
        (
            {
                "request_policy_ref":
                    "public-export-policy:different@1.0.0"
            },
            "export_request_policy_binding_mismatch",
        ),
        (
            {
                "aliases": {
                    "product-case:other@1.0.0": "Other public case"
                }
            },
            "public_case_alias_missing",
        ),
        (
            {"statement_refs": [STATEMENT_REF]},
            "statement_not_allowlisted",
        ),
    ],
)
def test_binding_and_policy_refusals(
    tmp_path: Path, changes: dict[str, Any], reason: str
) -> None:
    run = ToolRegistry.load_default().run(
        _tool_request(tmp_path / reason, **changes)
    )

    assert run.execution_state is ExecutionState.FAILED
    assert reason in run.reason_codes
    assert run.artifacts == []


def test_checksum_mismatch_and_v1_request_are_typed_refusals(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    request = _tool_request(tmp_path / "checksum")
    refs = list(request.object_inputs)
    refs[0] = refs[0].model_copy(update={"sha256": "0" * 64})
    bad = request.model_copy(update={"object_inputs": refs})

    checksum_run = registry.run(bad)
    v1_run = registry.run(
        ToolRequest(
            request_id="request-v1",
            tool_id="P0-11",
            tool_version="0.3.0",
            output_dir=tmp_path / "v1-output",
        )
    )

    assert checksum_run.execution_state is ExecutionState.FAILED
    assert checksum_run.reason_codes == ["structured_input_checksum_mismatch"]
    assert v1_run.execution_state is ExecutionState.FAILED
    assert v1_run.reason_codes == ["tool_request_v2_required"]


def test_existing_bundle_is_reused_or_fails_closed_on_tamper(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    request = _tool_request(tmp_path / "reuse")
    first = registry.run(request)
    second = registry.run(request)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")

    result_path = next(
        item.path for item in first.artifacts if item.kind == "public_export_result"
    )
    result_path.write_text("{}\n", encoding="utf-8")
    third = registry.run(request)

    assert third.execution_state is ExecutionState.FAILED
    assert third.reason_codes == ["existing_run_bundle_hash_mismatch"]


def test_output_models_bind_manifest_and_result_hashes(tmp_path: Path) -> None:
    run = ToolRegistry.load_default().run(
        _tool_request(
            tmp_path / "statements",
            statement_refs=[STATEMENT_REF],
            allowed_statements=[STATEMENT_REF],
        )
    )
    by_kind = {artifact.kind: artifact for artifact in run.artifacts}
    manifest = PublicExportManifest.model_validate_json(
        by_kind["public_export_manifest"].path.read_text()
    )
    result = PublicExportResult.model_validate_json(
        by_kind["public_export_result"].path.read_text()
    )

    assert manifest.entries[0].sha256 == by_kind["public_safe_report"].sha256
    assert result.public_report_sha256 == by_kind["public_safe_report"].sha256
    assert result.manifest_sha256 == by_kind["public_export_manifest"].sha256
