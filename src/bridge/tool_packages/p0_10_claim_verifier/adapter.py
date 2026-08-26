from __future__ import annotations

import hashlib
from dataclasses import dataclass

from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    PublicationError,
    canonical_json_bytes,
    directory_state,
    failed_v2_run,
    load_structured_inputs,
    read_regular_bytes,
    request_v2_from_v1,
    single_object,
)
from bridge.tool_packages._structured_runtime import (
    publish_json_result as _publish_result,
)
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    CaseEvidenceGraphManifest,
    EvidenceRecordSet,
    contains_unsafe_reference,
)
from bridge.tool_packages.p0_09_evidence_compiler.queries import EvidenceGraphQueries
from bridge.tool_packages.p0_10_claim_verifier.benchmark import (
    benchmark_sha256,
    load_benchmark,
)
from bridge.tool_packages.p0_10_claim_verifier.models import (
    ClaimPolicySpec,
    ClaimVerifierReleaseContract,
    ReportDraft,
    StatementRegistry,
)
from bridge.tool_packages.p0_10_claim_verifier.verifier import (
    load_release_contract,
    release_contract_sha256,
    verify_report,
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

RESULT_SCHEMA_REF = "bridge://schemas/claim-verification-result/v0.1"
ROLE_MODELS: dict[str, tuple[str, type[FrozenModel]]] = {
    "report_draft": ("bridge://schemas/report-draft/v0.1", ReportDraft),
    "evidence_graph_manifest": (
        "bridge://schemas/case-evidence-graph-manifest/v0.1",
        CaseEvidenceGraphManifest,
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
class VerifiedEvidenceGraph:
    manifest: CaseEvidenceGraphManifest
    manifest_sha256: str
    evidence_set: EvidenceRecordSet


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
        release_contract, contract_reasons = _release_contract()
        reasons.extend(contract_reasons)
        try:
            load_benchmark()
        except (OSError, ValueError):
            reasons.append("benchmark_record_invalid")
        loaded, loading_reasons = _load_inputs(request.object_inputs)
        reasons.extend(loading_reasons)
        if loaded is not None and release_contract is not None and not reasons:
            reasons.extend(_binding_reasons(request, loaded, release_contract))
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
        release_contract, contract_reasons = _release_contract()
        if release_contract is None:
            return _failed_run(request, spec, contract_reasons)

        report = single_object(request, loaded, "report_draft", ReportDraft)
        try:
            evidence_graph = _verified_evidence_graph(request, loaded)
        except ValueError:
            return _failed_run(request, spec, ["evidence_graph_integrity_failed"])
        policy = single_object(
            request, loaded, "claim_policy_spec", ClaimPolicySpec
        )
        statements = single_object(
            request, loaded, "statement_registry", StatementRegistry
        )
        benchmark = load_benchmark()
        benchmark_hash = benchmark_sha256()
        contract_hash = release_contract_sha256()
        input_hash = _input_hash(request, spec, benchmark_hash, contract_hash)
        run_id = f"run-{input_hash[:16]}"
        result = verify_report(
            report=report,
            evidence_set=evidence_graph.evidence_set,
            policy=policy,
            statements=statements,
            release_contract=release_contract,
            release_contract_hash=contract_hash,
            benchmark_id=benchmark.benchmark_id,
            benchmark_sha256=benchmark_hash,
            run_id=run_id,
            evidence_graph_id=evidence_graph.manifest.graph_id,
            evidence_graph_version=evidence_graph.manifest.graph_version,
            evidence_graph_manifest_sha256=evidence_graph.manifest_sha256,
        )
        result_bytes = canonical_json_bytes(result.model_dump(mode="json"), indent=2)
        result_hash = hashlib.sha256(result_bytes).hexdigest()
        try:
            output_file = _publish_result(
                request=request,
                run_id=run_id,
                filename="claim_verification_result.json",
                payload=result_bytes,
            )
        except PublicationError as exc:
            return _failed_run(
                request,
                spec,
                [exc.reason_code],
                input_hash=input_hash,
            )
        try:
            published_matches = read_regular_bytes(output_file) == result_bytes
        except (OSError, RuntimeError):
            published_matches = False
        if not published_matches:
            return _failed_run(
                request,
                spec,
                ["published_result_hash_mismatch"],
                input_hash=input_hash,
            )
        artifact = ArtifactManifest(
            artifact_id=f"artifact:{run_id}:result",
            kind="claim_verification_result",
            path=output_file,
            media_type="application/json",
            sha256=result_hash,
            evidence_ids=sorted(
                {
                    ref.split("@", 1)[0]
                    for claim in report.claim_blocks
                    for ref in claim.evidence_refs
                }
            ),
        )
        return ToolRunV2(
            run_id=run_id,
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=ExecutionState.SUCCEEDED,
            tool_version=spec.version,
            environment_spec_id=spec.environment_spec_id,
            input_hash=input_hash,
            created_at=report.created_at,
            measurements=[],
            artifacts=[artifact],
            visualizations=[],
            result_schema_ref=RESULT_SCHEMA_REF,
            result=result.model_dump(mode="json"),
            reason_codes=[],
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
        if ref.role != "evidence_graph_manifest" and ref.object_version != "0.1.0":
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
    version = (
        str(value.graph_version)
        if isinstance(value, CaseEvidenceGraphManifest)
        else getattr(value, "object_version", None)
    )
    if version != ref.object_version:
        from bridge.tool_packages._structured_runtime import StructuredInputError

        raise StructuredInputError("object_input_version_mismatch")


def _release_contract() -> tuple[ClaimVerifierReleaseContract | None, list[str]]:
    try:
        return load_release_contract(), []
    except (OSError, ValueError):
        return None, ["release_contract_invalid"]


def _binding_reasons(
    request: ToolRequestV2,
    loaded: LoadedInputs,
    release_contract: ClaimVerifierReleaseContract,
) -> list[str]:
    report = single_object(request, loaded, "report_draft", ReportDraft)
    policy = single_object(request, loaded, "claim_policy_spec", ClaimPolicySpec)
    statements = single_object(
        request, loaded, "statement_registry", StatementRegistry
    )
    reasons: list[str] = []
    if contains_unsafe_reference(report.model_dump(mode="json")):
        reasons.append("unsafe_report_content")
    try:
        evidence_graph = _verified_evidence_graph(request, loaded)
    except ValueError:
        reasons.append("evidence_graph_integrity_failed")
        return reasons
    evidence_set = evidence_graph.evidence_set
    record_set_ref = f"{evidence_set.record_set_id}@{evidence_set.record_set_version}"
    if report.evidence_record_set_ref != record_set_ref:
        reasons.append("evidence_record_set_binding_mismatch")
    if report.claim_policy_ref != policy.ref:
        reasons.append("claim_policy_binding_mismatch")
    if report.statement_registry_ref != statements.ref:
        reasons.append("statement_registry_binding_mismatch")
    if canonical_json_bytes(policy.model_dump(mode="json")) != canonical_json_bytes(
        release_contract.claim_policy.model_dump(mode="json")
    ):
        reasons.append("claim_policy_not_approved")
    if canonical_json_bytes(statements.model_dump(mode="json")) != canonical_json_bytes(
        release_contract.statement_registry.model_dump(mode="json")
    ):
        reasons.append("statement_registry_not_approved")
    return reasons


def _verified_evidence_graph(
    request: ToolRequestV2, loaded: LoadedInputs
) -> VerifiedEvidenceGraph:
    manifest = single_object(
        request, loaded, "evidence_graph_manifest", CaseEvidenceGraphManifest
    )
    manifest_ref = next(
        ref for ref in request.object_inputs if ref.role == "evidence_graph_manifest"
    )
    graph = EvidenceGraphQueries.open(manifest_ref.path)
    evidence_set = graph.evidence_record_set
    if (
        evidence_set.graph_id != manifest.graph_id
        or evidence_set.graph_version != manifest.graph_version
    ):
        raise ValueError("manifest_integrity_failed")
    return VerifiedEvidenceGraph(
        manifest=manifest,
        manifest_sha256=manifest_ref.sha256,
        evidence_set=evidence_set,
    )


def _input_hash(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    benchmark_hash: str,
    release_contract_hash: str,
) -> str:
    payload = {
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "environment_spec_id": spec.environment_spec_id,
        "benchmark_sha256": benchmark_hash,
        "release_contract_sha256": release_contract_hash,
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


def _failed_v1_request(
    request: ToolRequest, spec: ToolPackageSpecV2
) -> ToolRunV2:
    return _failed_run(
        request_v2_from_v1(request), spec, ["tool_request_v2_required"]
    )
