from __future__ import annotations

from bridge.tool_packages.p0_10_claim_verifier.models import (
    ClaimVerificationResult,
    ReleaseState,
    ReportDraft,
)
from bridge.tool_packages.p0_11_public_export.models import (
    contains_machine_reference,
    ProjectionState,
    ReviewProjectionSpec,
    ReviewProjectedClaim,
    ContractValidatedReviewProjection,
    ReviewValueBinding,
    review_projection_hash,
)


def build_review_projection(
    *,
    run_id: str,
    tool_version: str,
    report: ReportDraft,
    verification: ClaimVerificationResult,
    projection_spec: ReviewProjectionSpec,
    claim_verification_sha256: str,
    input_sha256_by_role: dict[str, str],
) -> ContractValidatedReviewProjection:
    claims_by_id = {claim.claim_id: claim for claim in report.claim_blocks}
    review_claims: list[ReviewProjectedClaim] = []
    for selection in sorted(
        projection_spec.selections, key=lambda item: item.review_claim_id
    ):
        source = claims_by_id[selection.source_claim_id]
        text = source.text
        _require_review_text(
            [text, selection.review_case_label],
            projection_spec.prohibited_literals,
        )
        review_claims.append(
            ReviewProjectedClaim(
                review_claim_id=selection.review_claim_id,
                review_case_label=selection.review_case_label,
                claim_type=source.claim_type,
                text=text,
                language=source.language,
                evidence_state=source.reported_evidence_state,
                comparison_mode=source.comparison_mode,
                value_bindings=[
                    ReviewValueBinding(
                        binding_index=index,
                        source_field=binding.source_field,
                        canonical_numeric_string=binding.canonical_numeric_string,
                        raw_unit=binding.raw_unit,
                    )
                    for index, binding in enumerate(source.value_bindings)
                ],
            )
        )
    _require_review_text(
        projection_spec.source_accessions,
        projection_spec.prohibited_literals,
    )
    reason_codes = [
        "producer_provenance_unverified",
        "public_release_authority_not_configured",
    ]
    if verification.release_state is ReleaseState.VERIFIED_WITH_WARNINGS:
        reason_codes.append("p0_10_verified_with_warnings")
    payload = {
        "object_version": "0.1.0",
        "projection_id": f"review-projection:{run_id.removeprefix('run-')}",
        "projection_version": "0.1.0",
        "tool_id": "P0-11",
        "tool_version": tool_version,
        "source_report_hash": report.content_hash,
        "claim_verification_sha256": claim_verification_sha256,
        "projection_spec_ref": projection_spec.ref.model_dump(mode="json"),
        "input_sha256_by_role": input_sha256_by_role,
        "language": projection_spec.target_language,
        "source_accessions": sorted(projection_spec.source_accessions),
        "claims": [claim.model_dump(mode="json") for claim in review_claims],
        "producer_authentication_state": "not_available",
        "release_authority_state": "not_configured",
        "distribution_state": "internal_review_only",
        "projection_state": ProjectionState.REVIEW_REQUIRED,
        "checks": sorted(
            [
                "allowlist_projection_passed",
                "configured_literals_absent",
                "bounded_machine_reference_guard_passed",
            ]
        ),
        "reason_codes": sorted(reason_codes),
    }
    if contains_machine_reference(payload):
        raise ValueError("bounded machine reference remains")
    payload["projection_hash"] = review_projection_hash(payload)
    return ContractValidatedReviewProjection.model_validate(payload)


def _require_review_text(values: list[str], prohibited_literals: list[str]) -> None:
    prohibited = [item.casefold() for item in prohibited_literals]
    for value in values:
        folded = value.casefold()
        if any(item in folded for item in prohibited):
            raise ValueError("configured prohibited literal remains")
        if contains_machine_reference(value):
            raise ValueError("bounded machine reference remains")
