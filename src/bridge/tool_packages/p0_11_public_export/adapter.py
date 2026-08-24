from __future__ import annotations

from dataclasses import dataclass
import hashlib

from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    StructuredInputError,
    canonical_json_bytes,
    directory_state,
    failed_v2_run,
    load_structured_inputs,
    publish_single_json,
    single_object,
)
from bridge.tool_packages.p0_10_claim_verifier.models import (
    ClaimVerificationResult,
    PublicExportEligibility,
    PublicReleaseAuthorityState,
    ReleaseState,
    ReportAudience,
    ReportDraft,
)
from bridge.tool_packages.p0_11_public_export.executor import (
    build_review_projection,
)
from bridge.tool_packages.p0_11_public_export.models import ReviewProjectionSpec
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


RESULT_SCHEMA_REF = "bridge://schemas/contract-validated-review-projection/v0.1"
ROLE_MODELS: dict[str, tuple[str, type[FrozenModel]]] = {
    "report_draft": ("bridge://schemas/report-draft/v0.1", ReportDraft),
    "claim_verification_result": (
        "bridge://schemas/claim-verification-result/v0.1",
        ClaimVerificationResult,
    ),
    "claim_verifier_run": (
        "bridge://schemas/tool-run/v0.2",
        ToolRunV2,
    ),
    "review_projection_spec": (
        "bridge://schemas/review-projection-spec/v0.1",
        ReviewProjectionSpec,
    ),
}


@dataclass(frozen=True)
class ReviewProjectionAdapter:
    def check_eligibility(
        self, request: ToolRequestV2, spec: ToolPackageSpecV2
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
            reasons.extend(_binding_reasons(request, loaded))
        reason_codes = sorted(set(reasons))
        return EligibilityResult(
            tool_id=request.tool_id,
            eligible=not reason_codes,
            reason_codes=reason_codes,
        )

    def run(self, request: ToolRequestV2, spec: ToolPackageSpecV2) -> ToolRunV2:
        if not isinstance(request, ToolRequestV2):
            return _failed_v1_request(request, spec)
        eligibility = self.check_eligibility(request, spec)
        if not eligibility.eligible:
            return _failed_run(request, spec, eligibility.reason_codes)
        loaded, reasons = _load_inputs(request.object_inputs)
        if loaded is None or reasons:
            return _failed_run(request, spec, reasons)
        report = single_object(request, loaded, "report_draft", ReportDraft)
        verification = single_object(
            request,
            loaded,
            "claim_verification_result",
            ClaimVerificationResult,
        )
        projection_spec = single_object(
            request, loaded, "review_projection_spec", ReviewProjectionSpec
        )
        input_hash = _input_hash(request, spec)
        run_id = f"run-{input_hash[:16]}"
        verification_sha256 = _role_ref(request, "claim_verification_result").sha256
        try:
            result = build_review_projection(
                run_id=run_id,
                tool_version=spec.version,
                report=report,
                verification=verification,
                projection_spec=projection_spec,
                claim_verification_sha256=verification_sha256,
                input_sha256_by_role={
                    ref.role: ref.sha256 for ref in request.object_inputs
                },
            )
        except ValueError:
            return _failed_run(
                request,
                spec,
                ["review_projection_failed"],
                input_hash=input_hash,
            )
        payload = canonical_json_bytes(result.model_dump(mode="json"), indent=2)
        try:
            output_file = publish_single_json(
                request=request,
                run_id=run_id,
                filename="contract_validated_review_projection.json",
                payload=payload,
            )
        except StructuredInputError as exc:
            return _failed_run(
                request,
                spec,
                [exc.reason_code],
                input_hash=input_hash,
            )
        artifact = ArtifactManifest(
            artifact_id=f"artifact:{run_id}:review-projection",
            kind="contract_validated_review_projection",
            path=output_file,
            media_type="application/json",
            sha256=hashlib.sha256(payload).hexdigest(),
            evidence_ids=[],
        )
        return ToolRunV2(
            run_id=run_id,
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=(
                ExecutionState.PARTIAL
                if result.projection_state == "review_required"
                else ExecutionState.SUCCEEDED
            ),
            tool_version=spec.version,
            environment_spec_id=spec.environment_spec_id,
            input_hash=input_hash,
            created_at=report.created_at,
            measurements=[],
            artifacts=[artifact],
            visualizations=[],
            result_schema_ref=RESULT_SCHEMA_REF,
            result=result.model_dump(mode="json"),
            reason_codes=result.reason_codes,
            warnings=[],
        )


adapter = ReviewProjectionAdapter()


def _envelope_reasons(
    request: ToolRequestV2, spec: ToolPackageSpecV2
) -> list[str]:
    reasons: list[str] = []
    if request.tool_version is not None and request.tool_version != spec.version:
        reasons.append("tool_version_mismatch")
    if request.assets:
        reasons.append("p0_11_file_assets_not_supported")
    if request.measurement_spec_ref is not None:
        reasons.append("p0_11_measurement_spec_forbidden")
    if request.parameters:
        reasons.append("p0_11_parameters_forbidden")
    if request.random_seed != 0:
        reasons.append("p0_11_random_seed_forbidden")
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
        if ref.role != "claim_verifier_run" and ref.object_version != "0.1.0":
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


def _validate_object_version(ref: StructuredInputRef, value: FrozenModel) -> None:
    if ref.role == "claim_verifier_run":
        return
    if getattr(value, "object_version", None) != ref.object_version:
        raise StructuredInputError("object_input_version_mismatch")


def _binding_reasons(
    request: ToolRequestV2,
    loaded: LoadedInputs,
) -> list[str]:
    report = single_object(request, loaded, "report_draft", ReportDraft)
    verification = single_object(
        request,
        loaded,
        "claim_verification_result",
        ClaimVerificationResult,
    )
    verifier_run = single_object(
        request, loaded, "claim_verifier_run", ToolRunV2
    )
    projection_spec = single_object(
        request, loaded, "review_projection_spec", ReviewProjectionSpec
    )
    reasons: list[str] = []
    if report.audience is not ReportAudience.PUBLIC_CANDIDATE:
        reasons.append("report_audience_not_public_candidate")
    if not verification.matches_report_draft(report):
        reasons.append("claim_verification_report_binding_mismatch")
    if verification.release_state not in {
        ReleaseState.VERIFIED,
        ReleaseState.VERIFIED_WITH_WARNINGS,
    }:
        reasons.append("claim_verification_not_verified_for_review_candidate")
    if (
        verification.public_release_authority_state
        is not PublicReleaseAuthorityState.NOT_CONFIGURED
        or verification.public_export_eligibility
        is not PublicExportEligibility.INELIGIBLE
    ):
        reasons.append("claim_verification_authority_state_inconsistent")
    if (
        projection_spec.source_report_ref != report.ref
        or projection_spec.source_report_hash != report.content_hash
    ):
        reasons.append("projection_spec_report_binding_mismatch")
    if projection_spec.claim_verification_id != verification.verification_id:
        reasons.append("projection_spec_verification_binding_mismatch")
    if projection_spec.target_language is not report.language:
        reasons.append("projection_language_mismatch")

    verification_ref = _role_ref(request, "claim_verification_result")
    matching_artifacts = [
        artifact
        for artifact in verifier_run.artifacts
        if artifact.kind == "claim_verification_result"
    ]
    if (
        verifier_run.request.tool_id != "P0-10"
        or verifier_run.implementation_state is not ImplementationState.IMPLEMENTED
        or verifier_run.execution_state is not ExecutionState.SUCCEEDED
        or verifier_run.result_schema_ref
        != "bridge://schemas/claim-verification-result/v0.1"
        or verifier_run.result != verification.model_dump(mode="json")
        or len(matching_artifacts) != 1
        or matching_artifacts[0].sha256 != verification_ref.sha256
    ):
        reasons.append("claim_verifier_run_binding_mismatch")

    claims = {claim.claim_id: claim for claim in report.claim_blocks}
    for selection in projection_spec.selections:
        claim = claims.get(selection.source_claim_id)
        if claim is None:
            reasons.append("projection_claim_not_found")
            continue
        if claim.claim_type not in projection_spec.allowed_claim_types:
            reasons.append("projection_claim_type_not_allowed")
        if claim.reported_evidence_state is None:
            if not projection_spec.allow_claims_without_evidence_state:
                reasons.append("projection_claim_requires_evidence_state")
        elif claim.reported_evidence_state not in projection_spec.allowed_evidence_states:
            reasons.append("projection_evidence_state_not_allowed")
    return reasons


def _input_hash(request: ToolRequestV2, spec: ToolPackageSpecV2) -> str:
    payload = {
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "environment_spec_id": spec.environment_spec_id,
        "structured_inputs": [
            {
                "role": ref.role,
                "schema_ref": ref.schema_ref,
                "object_version": ref.object_version,
                "sha256": ref.sha256,
                "media_type": ref.media_type,
            }
            for ref in sorted(request.object_inputs, key=lambda item: item.role)
        ],
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _role_ref(request: ToolRequestV2, role: str) -> StructuredInputRef:
    return next(ref for ref in request.object_inputs if ref.role == role)


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
        fingerprint_input_key="structured_inputs",
        input_hash=input_hash,
    )


def _failed_v1_request(request: ToolRequest, spec: ToolPackageSpecV2) -> ToolRunV2:
    request_v2 = ToolRequestV2(
        request_id=request.request_id,
        tool_id=request.tool_id,
        output_dir=request.output_dir,
        tool_version=request.tool_version,
        assets=request.assets,
        measurement_spec_ref=request.measurement_spec_ref,
        parameters=request.parameters,
        random_seed=request.random_seed,
        object_inputs=[],
    )
    return _failed_run(request_v2, spec, ["tool_request_v2_required"])
