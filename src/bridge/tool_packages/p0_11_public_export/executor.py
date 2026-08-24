from __future__ import annotations

from bridge.tool_packages.p0_10_claim_verifier.models import (
    ClaimVerificationResult,
    ReleaseState,
    ReportDraft,
)
from bridge.tool_packages.p0_11_public_export.models import (
    contains_machine_reference,
    ExportState,
    PublicExportSpec,
    PublicSafeClaim,
    PublicSafeReport,
    PublicValueBinding,
    public_safe_report_hash,
)


def build_public_safe_report(
    *,
    run_id: str,
    tool_version: str,
    report: ReportDraft,
    verification: ClaimVerificationResult,
    export_spec: PublicExportSpec,
    claim_verification_sha256: str,
    input_sha256_by_role: dict[str, str],
) -> PublicSafeReport:
    claims_by_id = {claim.claim_id: claim for claim in report.claim_blocks}
    public_claims: list[PublicSafeClaim] = []
    for selection in sorted(
        export_spec.selections, key=lambda item: item.public_claim_id
    ):
        source = claims_by_id[selection.source_claim_id]
        text = source.text
        for replacement in sorted(
            selection.replacements,
            key=lambda item: (-len(item.source_literal), item.source_literal),
        ):
            text = text.replace(replacement.source_literal, replacement.public_literal)
        _require_public_text(
            [text, selection.public_case_label],
            export_spec.prohibited_literals,
        )
        public_claims.append(
            PublicSafeClaim(
                public_claim_id=selection.public_claim_id,
                public_case_label=selection.public_case_label,
                claim_type=source.claim_type,
                text=text,
                language=source.language,
                evidence_state=source.reported_evidence_state,
                comparison_mode=source.comparison_mode,
                value_bindings=[
                    PublicValueBinding(
                        binding_index=index,
                        source_field=binding.source_field,
                        canonical_numeric_string=binding.canonical_numeric_string,
                        raw_unit=binding.raw_unit,
                    )
                    for index, binding in enumerate(source.value_bindings)
                ],
            )
        )
    _require_public_text(
        export_spec.public_source_accessions,
        export_spec.prohibited_literals,
    )
    reason_codes = (
        ["p0_10_verified_with_warnings"]
        if verification.release_state is ReleaseState.VERIFIED_WITH_WARNINGS
        else []
    )
    payload = {
        "object_version": "0.1.0",
        "public_report_id": f"public-report:{run_id.removeprefix('run-')}",
        "public_report_version": "0.1.0",
        "tool_id": "P0-11",
        "tool_version": tool_version,
        "source_report_hash": report.content_hash,
        "claim_verification_sha256": claim_verification_sha256,
        "export_spec_ref": export_spec.ref.model_dump(mode="json"),
        "input_sha256_by_role": input_sha256_by_role,
        "language": export_spec.target_language,
        "public_source_accessions": sorted(export_spec.public_source_accessions),
        "claims": [claim.model_dump(mode="json") for claim in public_claims],
        "export_state": (
            ExportState.REVIEW_REQUIRED
            if reason_codes
            else ExportState.READY_FOR_CONFIRMATION
        ),
        "checks": sorted(
            [
                "allowlist_projection_passed",
                "configured_literals_absent",
                "bounded_machine_reference_guard_passed",
            ]
        ),
        "reason_codes": reason_codes,
    }
    if contains_machine_reference(payload):
        raise ValueError("bounded machine reference remains")
    payload["candidate_hash"] = public_safe_report_hash(payload)
    return PublicSafeReport.model_validate(payload)


def _require_public_text(values: list[str], prohibited_literals: list[str]) -> None:
    prohibited = [item.casefold() for item in prohibited_literals]
    for value in values:
        folded = value.casefold()
        if any(item in folded for item in prohibited):
            raise ValueError("configured prohibited literal remains")
        if contains_machine_reference(value):
            raise ValueError("bounded machine reference remains")
