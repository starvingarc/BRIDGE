from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
from uuid import uuid4

from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    canonical_json_bytes,
    failed_v2_run,
    inputs_unchanged,
    load_structured_inputs,
    single_object,
    write_json,
)
from bridge.tool_packages.p0_09_evidence_compiler.models import EvidenceRecordSet
from bridge.tool_packages.p0_10_claim_verifier.benchmark import (
    benchmark_sha256,
    load_benchmark,
)
from bridge.tool_packages.p0_10_claim_verifier.models import (
    ClaimPolicySpec,
    ClaimVerifierRunResult,
    ReleaseState,
    ReportDraft,
    StatementRegistry,
)
from bridge.tool_packages.p0_10_claim_verifier.verifier import verify_report
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


RESULT_SCHEMA_REF = "bridge://schemas/claim-verifier-run-result/v0.1"
ROLE_MODELS: dict[str, tuple[str, type[FrozenModel]]] = {
    "report_draft": ("bridge://schemas/report-draft/v0.1", ReportDraft),
    "evidence_record_set": (
        "bridge://schemas/evidence-record-set/v0.1",
        EvidenceRecordSet,
    ),
    "claim_policy_spec": (
        "bridge://schemas/claim-policy-spec/v0.1",
        ClaimPolicySpec,
    ),
    "statement_registry": (
        "bridge://schemas/statement-registry/v0.1",
        StatementRegistry,
    ),
}


@dataclass(frozen=True)
class ClaimVerifierAdapter:
    def check_eligibility(
        self, request: ToolRequestV2, spec: ToolPackageSpecV2
    ) -> EligibilityResult:
        if not isinstance(request, ToolRequestV2):
            tool_id = request.tool_id if isinstance(request, ToolRequest) else "P0-10"
            return EligibilityResult(
                tool_id=tool_id,
                eligible=False,
                reason_codes=["tool_request_v2_required"],
            )
        reasons = _envelope_reasons(request, spec)
        loaded, loading_reasons = _load_inputs(request.object_inputs)
        reasons.extend(loading_reasons)
        if loaded is not None:
            reasons.extend(_binding_reasons(request, loaded))
        reason_codes = sorted(set(reasons))
        return EligibilityResult(
            tool_id=request.tool_id,
            eligible=not reason_codes,
            reason_codes=reason_codes,
        )

    def run(self, request: ToolRequestV2, spec: ToolPackageSpecV2) -> ToolRunV2:
        eligibility = self.check_eligibility(request, spec)
        if not eligibility.eligible:
            return _failed_run(request, spec, eligibility.reason_codes)
        loaded, reasons = _load_inputs(request.object_inputs)
        if loaded is None or reasons:
            return _failed_run(request, spec, reasons)

        report = single_object(request, loaded, "report_draft", ReportDraft)
        evidence_set = single_object(
            request, loaded, "evidence_record_set", EvidenceRecordSet
        )
        policy = single_object(
            request, loaded, "claim_policy_spec", ClaimPolicySpec
        )
        statements = single_object(
            request, loaded, "statement_registry", StatementRegistry
        )
        benchmark = load_benchmark()
        benchmark_hash = benchmark_sha256()
        input_hash = _input_hash(request, spec, benchmark_hash)
        run_id = f"run-{input_hash[:16]}"
        result = verify_report(
            report=report,
            evidence_set=evidence_set,
            policy=policy,
            statements=statements,
            benchmark_id=benchmark.benchmark_id,
            benchmark_sha256=benchmark_hash,
            run_id=run_id,
        )
        output_file = _publish_result(
            request=request,
            spec=spec,
            run_id=run_id,
            input_hash=input_hash,
            result=result,
        )
        if output_file is None:
            return _failed_run(
                request,
                spec,
                ["existing_run_bundle_hash_mismatch"],
                input_hash=input_hash,
            )
        artifact = ArtifactManifest(
            artifact_id=f"artifact:{run_id}:result",
            kind="claim_verifier_run_result",
            path=output_file,
            media_type="application/json",
            sha256=hashlib.sha256(output_file.read_bytes()).hexdigest(),
            evidence_ids=sorted(
                {
                    ref.split("@", 1)[0]
                    for refs in result.verification.claim_evidence_map.values()
                    for ref in refs
                }
            ),
        )
        not_assessed = result.verification.release_state is ReleaseState.NOT_ASSESSED
        return ToolRunV2(
            run_id=run_id,
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=(
                ExecutionState.PARTIAL if not_assessed else ExecutionState.SUCCEEDED
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
            reason_codes=["active_claim_policy_required"] if not_assessed else [],
            warnings=[],
        )


adapter = ClaimVerifierAdapter()


def _envelope_reasons(
    request: ToolRequestV2, spec: ToolPackageSpecV2
) -> list[str]:
    reasons: list[str] = []
    if request.tool_version is not None and request.tool_version != spec.version:
        reasons.append("tool_version_mismatch")
    if request.assets:
        reasons.append("p0_10_expression_assets_forbidden")
    if request.measurement_spec_ref is not None:
        reasons.append("p0_10_measurement_spec_forbidden")
    if request.parameters:
        reasons.append("p0_10_parameters_forbidden")
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
    if request.output_dir.exists() and (
        request.output_dir.is_symlink() or not request.output_dir.is_dir()
    ):
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
    version = getattr(
        value,
        {
            "evidence_record_set": "record_set_version",
        }.get(ref.role, "object_version"),
        None,
    )
    if version != ref.object_version:
        from bridge.tool_packages._structured_runtime import StructuredInputError

        raise StructuredInputError("object_input_version_mismatch")


def _binding_reasons(request: ToolRequestV2, loaded: LoadedInputs) -> list[str]:
    report = single_object(request, loaded, "report_draft", ReportDraft)
    evidence_set = single_object(
        request, loaded, "evidence_record_set", EvidenceRecordSet
    )
    policy = single_object(request, loaded, "claim_policy_spec", ClaimPolicySpec)
    statements = single_object(
        request, loaded, "statement_registry", StatementRegistry
    )
    reasons: list[str] = []
    record_set_ref = f"{evidence_set.record_set_id}@{evidence_set.record_set_version}"
    if report.evidence_record_set_ref != record_set_ref:
        reasons.append("evidence_record_set_binding_mismatch")
    if report.claim_policy_ref != policy.ref:
        reasons.append("claim_policy_binding_mismatch")
    if report.statement_registry_ref != statements.ref:
        reasons.append("statement_registry_binding_mismatch")
    claim_ids = {claim.claim_id for claim in report.claim_blocks}
    rule_ids = {rule.rule_id for rule in policy.text_rules}
    for decision in report.human_review_decisions:
        if decision.claim_id not in claim_ids:
            reasons.append("human_review_claim_not_found")
        if decision.rule_id not in rule_ids:
            reasons.append("human_review_rule_not_found")
    return reasons


def _input_hash(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    benchmark_hash: str,
) -> str:
    payload = {
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "environment_spec_id": spec.environment_spec_id,
        "benchmark_sha256": benchmark_hash,
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


def _publish_result(
    *,
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    run_id: str,
    input_hash: str,
    result: ClaimVerifierRunResult,
) -> Path | None:
    output_root = request.output_dir.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    staging = output_root / f".{run_id}.staging-{uuid4().hex}"
    staging.mkdir(mode=0o700)
    filename = "claim_verifier_run_result.json"
    try:
        write_json(staging / filename, result.model_dump(mode="json"))
        if not inputs_unchanged(request.object_inputs):
            shutil.rmtree(staging)
            return None
        final = output_root / run_id
        if final.exists():
            if final.is_symlink() or not final.is_dir():
                shutil.rmtree(staging)
                return None
            existing = final / filename
            if (
                not existing.is_file()
                or existing.is_symlink()
                or existing.read_bytes() != (staging / filename).read_bytes()
                or {path.name for path in final.iterdir()} != {filename}
            ):
                shutil.rmtree(staging)
                return None
            shutil.rmtree(staging)
        else:
            os.replace(staging, final)
        return (final / filename).resolve()
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


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
