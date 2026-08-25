from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import shutil
from typing import Any
from uuid import uuid4

from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    canonical_json_bytes,
    directory_state,
    failed_v2_run,
    inputs_unchanged,
    load_structured_inputs,
    read_regular_bytes,
    single_object,
)
from bridge.tool_packages.p0_10_claim_verifier.models import (
    ClaimVerificationResult,
    PublicExportEligibility,
    ReleaseState,
    ReportAudience,
    ReportDraft,
)
from bridge.tool_packages.p0_11_public_safe_export.models import (
    PublicClaimField,
    PublicExportManifest,
    PublicExportManifestEntry,
    PublicExportPolicySpec,
    PublicExportRequest,
    PublicExportResult,
    PublicExportState,
    PublicSafeClaim,
    PublicSafeReport,
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


RESULT_SCHEMA_REF = "bridge://schemas/public-export-result/v0.1"
ROLE_MODELS: dict[str, tuple[str, type[FrozenModel]]] = {
    "report_draft": ("bridge://schemas/report-draft/v0.1", ReportDraft),
    "claim_verification_result": (
        "bridge://schemas/claim-verification-result/v0.1",
        ClaimVerificationResult,
    ),
    "public_export_policy": (
        "bridge://schemas/public-export-policy-spec/v0.1",
        PublicExportPolicySpec,
    ),
    "public_export_request": (
        "bridge://schemas/public-export-request/v0.1",
        PublicExportRequest,
    ),
}
FILENAMES = (
    "public_safe_report.json",
    "public_export_manifest.json",
    "public_export_result.json",
)
LEAK_PATTERNS = (
    re.compile(
        r"(?:/data[12]/|/" r"Users/|/home/|[A-Za-z]:\\Users\\)",
        re.I,
    ),
    re.compile(r"\bbridge-amax\b", re.I),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    re.compile(
        r"\b(?:api[_-]?key|password|secret|access[_-]?token|"
        r"refresh[_-]?token|bearer)\b(?:\s*[:=]\s*|\s+)[^\s,;]+",
        re.I,
    ),
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{8,})\b"),
    re.compile(r"\b(?:evidence|product-case|sample|preparation):[A-Za-z0-9]", re.I),
)


class PublicationError(ValueError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True)
class ExportBundle:
    public_report: PublicSafeReport
    manifest: PublicExportManifest
    result: PublicExportResult
    payloads: dict[str, bytes]


@dataclass(frozen=True)
class PublicSafeExportAdapter:
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
            reasons.extend(_binding_reasons(request, loaded, spec))
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
        input_hash = _input_hash(request, spec)
        if not eligibility.eligible:
            return _failed_run(
                request, spec, eligibility.reason_codes, input_hash=input_hash
            )
        loaded, reasons = _load_inputs(request.object_inputs)
        if loaded is None or reasons:
            return _failed_run(request, spec, reasons, input_hash=input_hash)
        bundle = _build_bundle(request, loaded, spec)
        run_id = f"run-{input_hash[:16]}"
        try:
            output_dir = _publish_bundle(
                request=request,
                run_id=run_id,
                payloads=bundle.payloads,
            )
        except PublicationError as exc:
            return _failed_run(
                request, spec, [exc.reason_code], input_hash=input_hash
            )
        artifacts = [
            ArtifactManifest(
                artifact_id=f"artifact:{run_id}:{name.removesuffix('.json')}",
                kind=name.removesuffix(".json"),
                path=output_dir / name,
                media_type="application/json",
                sha256=hashlib.sha256(bundle.payloads[name]).hexdigest(),
                evidence_ids=[],
            )
            for name in FILENAMES
        ]
        export_request = single_object(
            request, loaded, "public_export_request", PublicExportRequest
        )
        return ToolRunV2(
            run_id=run_id,
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=ExecutionState.SUCCEEDED,
            tool_version=spec.version,
            environment_spec_id=spec.environment_spec_id,
            input_hash=input_hash,
            created_at=export_request.created_at,
            measurements=[],
            artifacts=artifacts,
            visualizations=[],
            result_schema_ref=RESULT_SCHEMA_REF,
            result=bundle.result.model_dump(mode="json"),
            reason_codes=[],
            warnings=[],
        )


adapter = PublicSafeExportAdapter()


def _envelope_reasons(
    request: ToolRequestV2, spec: ToolPackageSpecV2
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


def _validate_object_version(ref: StructuredInputRef, value: FrozenModel) -> None:
    if getattr(value, "object_version", None) != ref.object_version:
        from bridge.tool_packages._structured_runtime import StructuredInputError

        raise StructuredInputError("object_input_version_mismatch")


def _binding_reasons(
    request: ToolRequestV2,
    loaded: LoadedInputs,
    spec: ToolPackageSpecV2,
) -> list[str]:
    report = single_object(request, loaded, "report_draft", ReportDraft)
    receipt = single_object(
        request, loaded, "claim_verification_result", ClaimVerificationResult
    )
    policy = single_object(
        request, loaded, "public_export_policy", PublicExportPolicySpec
    )
    export_request = single_object(
        request, loaded, "public_export_request", PublicExportRequest
    )
    reasons: list[str] = []
    if not receipt.matches_report_draft(report):
        reasons.append("verification_receipt_report_binding_mismatch")
    if (
        receipt.public_export_eligibility is not PublicExportEligibility.ELIGIBLE
        or receipt.release_state
        not in {ReleaseState.VERIFIED, ReleaseState.VERIFIED_WITH_WARNINGS}
        or report.audience is not ReportAudience.PUBLIC_CANDIDATE
    ):
        reasons.append("claim_verification_result_not_export_eligible")
    if not policy.active:
        reasons.append("public_export_policy_inactive")
    if export_request.report_draft_ref != report.ref:
        reasons.append("export_request_report_binding_mismatch")
    if export_request.policy_ref != policy.ref:
        reasons.append("export_request_policy_binding_mismatch")
    if export_request.target_channel not in policy.target_channels:
        reasons.append("target_channel_not_allowed")
    missing_alias = any(
        claim.product_case_ref not in policy.public_case_aliases
        for claim in report.claim_blocks
    )
    if missing_alias:
        reasons.append("public_case_alias_missing")
    allowed_statements = set(policy.allowed_statement_refs)
    if any(
        not set(claim.statement_refs).issubset(allowed_statements)
        for claim in report.claim_blocks
    ):
        reasons.append("statement_not_allowlisted")
    if reasons:
        return reasons
    bundle = _build_bundle(request, loaded, spec)
    if any(_contains_leak(obj) for obj in (bundle.public_report, bundle.manifest, bundle.result)):
        reasons.append("public_payload_leak_detected")
    if (
        export_request.confirmation_hash is not None
        and export_request.confirmation_hash != bundle.result.candidate_hash
    ):
        reasons.append("confirmation_hash_mismatch")
    return reasons


def _project_report(
    request: ToolRequestV2,
    loaded: LoadedInputs,
) -> PublicSafeReport:
    report = single_object(request, loaded, "report_draft", ReportDraft)
    policy = single_object(
        request, loaded, "public_export_policy", PublicExportPolicySpec
    )
    export_request = single_object(
        request, loaded, "public_export_request", PublicExportRequest
    )
    report_ref = _ref_for_role(request, "report_draft")
    receipt_ref = _ref_for_role(request, "claim_verification_result")
    policy_ref = _ref_for_role(request, "public_export_policy")
    allowed = set(policy.allowlisted_claim_fields)
    claims: list[PublicSafeClaim] = []
    for position, claim in enumerate(report.claim_blocks):
        alias = policy.public_case_aliases[claim.product_case_ref]
        identity = hashlib.sha256(
            canonical_json_bytes(
                {
                    "position": position,
                    "public_case_alias": alias,
                    "claim_type": claim.claim_type,
                    "text": claim.text,
                    "language": claim.language,
                }
            )
        ).hexdigest()[:16]
        claims.append(
            PublicSafeClaim(
                public_claim_id=f"public-claim:{identity}",
                public_case_alias=alias,
                claim_type=claim.claim_type,
                text=claim.text,
                language=claim.language,
                statement_refs=(
                    sorted(claim.statement_refs)
                    if PublicClaimField.STATEMENT_REFS in allowed
                    else None
                ),
                reported_evidence_state=(
                    claim.reported_evidence_state
                    if PublicClaimField.REPORTED_EVIDENCE_STATE in allowed
                    else None
                ),
                comparison_mode=(
                    claim.comparison_mode
                    if PublicClaimField.COMPARISON_MODE in allowed
                    else None
                ),
            )
        )
    claims.sort(key=lambda item: item.public_claim_id)
    identity_payload = {
        "source_report_sha256": report_ref.sha256,
        "claim_verification_receipt_sha256": receipt_ref.sha256,
        "public_export_policy_sha256": policy_ref.sha256,
        "export_policy_ref": policy.ref,
        "target_channel": export_request.target_channel,
        "claims": [claim.model_dump(mode="json", exclude_none=True) for claim in claims],
        "created_at": export_request.created_at.isoformat(),
    }
    public_report_id = hashlib.sha256(
        canonical_json_bytes(identity_payload)
    ).hexdigest()[:16]
    return PublicSafeReport(
        object_version="0.1.0",
        public_report_id=f"public-report:{public_report_id}",
        public_report_version="0.1.0",
        source_report_sha256=report_ref.sha256,
        claim_verification_receipt_sha256=receipt_ref.sha256,
        export_policy_ref=policy.ref,
        target_channel=export_request.target_channel,
        claims=claims,
        created_at=export_request.created_at,
    )


def _build_bundle(
    request: ToolRequestV2,
    loaded: LoadedInputs,
    spec: ToolPackageSpecV2,
) -> ExportBundle:
    public_report = _project_report(request, loaded)
    report_bytes = canonical_json_bytes(
        public_report.model_dump(mode="json", exclude_none=True), indent=2
    )
    report_hash = hashlib.sha256(report_bytes).hexdigest()
    policy_ref = _ref_for_role(request, "public_export_policy")
    candidate_hash = hashlib.sha256(
        canonical_json_bytes(
            {
                "canonicalization_id": "bridge-canonical-json/v0.1",
                "public_safe_report_sha256": report_hash,
                "public_export_policy_sha256": policy_ref.sha256,
                "target_channel": public_report.target_channel,
            }
        )
    ).hexdigest()
    export_request = single_object(
        request, loaded, "public_export_request", PublicExportRequest
    )
    state = (
        PublicExportState.EXPORTED
        if export_request.confirmation_hash == candidate_hash
        else PublicExportState.READY_FOR_CONFIRMATION
    )
    confirmation_hash = (
        export_request.confirmation_hash
        if state is PublicExportState.EXPORTED
        else None
    )
    manifest = PublicExportManifest(
        object_version="0.1.0",
        manifest_id=f"public-export-manifest:{hashlib.sha256(canonical_json_bytes({'candidate_hash': candidate_hash, 'state': state})).hexdigest()[:16]}",
        tool_id="P0-11",
        tool_version=spec.version,
        canonicalization_id="bridge-canonical-json/v0.1",
        candidate_hash=candidate_hash,
        export_state=state,
        confirmation_hash=confirmation_hash,
        entries=[
            PublicExportManifestEntry(
                filename="public_safe_report.json",
                media_type="application/json",
                sha256=report_hash,
                byte_count=len(report_bytes),
            )
        ],
    )
    manifest_bytes = canonical_json_bytes(manifest.model_dump(mode="json"), indent=2)
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    result = PublicExportResult(
        object_version="0.1.0",
        export_id=f"public-export:{hashlib.sha256(canonical_json_bytes({'candidate_hash': candidate_hash, 'state': state})).hexdigest()[:16]}",
        tool_id="P0-11",
        tool_version=spec.version,
        export_state=state,
        candidate_hash=candidate_hash,
        confirmation_hash=confirmation_hash,
        public_report_sha256=report_hash,
        manifest_sha256=manifest_hash,
        leak_scan_state="passed",
        artifact_count=3,
        domain_score=None,
        score_state="unavailable",
    )
    result_bytes = canonical_json_bytes(result.model_dump(mode="json"), indent=2)
    return ExportBundle(
        public_report=public_report,
        manifest=manifest,
        result=result,
        payloads={
            "public_safe_report.json": report_bytes,
            "public_export_manifest.json": manifest_bytes,
            "public_export_result.json": result_bytes,
        },
    )


def _strings(value: Any):
    if isinstance(value, FrozenModel):
        value = value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, str):
        yield value


def _contains_leak(value: Any) -> bool:
    return any(pattern.search(text) for text in _strings(value) for pattern in LEAK_PATTERNS)


def _ref_for_role(request: ToolRequestV2, role: str) -> StructuredInputRef:
    return next(ref for ref in request.object_inputs if ref.role == role)


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


def _publish_bundle(
    *,
    request: ToolRequestV2,
    run_id: str,
    payloads: dict[str, bytes],
) -> Path:
    output_root = request.output_dir
    if directory_state(output_root) == "other":
        raise PublicationError("output_path_invalid")
    try:
        output_root.mkdir(parents=True, exist_ok=True)
    except (OSError, RuntimeError):
        raise PublicationError("output_path_invalid") from None
    if directory_state(output_root) != "directory":
        raise PublicationError("output_path_invalid")
    staging = output_root / f".{run_id}.staging-{uuid4().hex}"
    try:
        staging.mkdir(mode=0o700)
        for name in FILENAMES:
            (staging / name).write_bytes(payloads[name])
        if not inputs_unchanged(request.object_inputs):
            raise PublicationError("structured_input_modified_during_run")
        final = output_root / run_id
        final_state = directory_state(final)
        if final_state == "directory":
            try:
                matches = (
                    {path.name for path in final.iterdir()} == set(FILENAMES)
                    and all(
                        read_regular_bytes(final / name) == payloads[name]
                        for name in FILENAMES
                    )
                )
            except (OSError, RuntimeError):
                matches = False
            if not matches:
                raise PublicationError("existing_run_bundle_hash_mismatch")
            shutil.rmtree(staging)
        elif final_state == "missing":
            os.replace(staging, final)
        else:
            raise PublicationError("existing_run_bundle_hash_mismatch")
        if any(read_regular_bytes(final / name) != payloads[name] for name in FILENAMES):
            raise PublicationError("published_result_hash_mismatch")
        return final
    except PublicationError:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    except (OSError, RuntimeError):
        shutil.rmtree(staging, ignore_errors=True)
        raise PublicationError("output_path_invalid") from None


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
