from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    PublicationError,
    StructuredInputError,
    canonical_json_bytes,
    directory_state,
    failed_v2_run,
    inputs_unchanged as _inputs_unchanged,
    load_structured_inputs,
    publish_json_bundle as _publish_bundle,
    read_regular_bytes as _read_regular_bytes,
    request_v2_from_v1,
    single_object,
)
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    CaseEvidenceGraphManifest,
    EvidenceRecordSet,
    contains_unsafe_reference,
)
from bridge.tool_packages.p0_09_evidence_compiler.queries import EvidenceGraphQueries
from bridge.tool_packages.p0_10_claim_verifier.models import (
    EXTERNAL_BENCHMARK_ID,
    EXTERNAL_BENCHMARK_SHA256,
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
from bridge.tool_packages.p0_10_claim_verifier.visualization import (
    PreparedClaimVerifierVisualizations,
    VisualizationFontUnavailable,
    prepare_claim_verifier_visualizations,
)
from bridge.tool_packages.p0_10_claim_verifier.visualization_data import (
    ClaimVerifierVisualizationDataV1,
    build_claim_verifier_visualization_data,
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
from bridge.toolkit.schemas import load_schema

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
    backing_artifacts: tuple[tuple[Path, str], ...]


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
        contract_hash = release_contract_sha256()
        input_hash = _input_hash(request, spec, contract_hash)
        run_id = f"run-{input_hash[:16]}"
        result = verify_report(
            report=report,
            evidence_set=evidence_graph.evidence_set,
            policy=policy,
            statements=statements,
            release_contract=release_contract,
            release_contract_hash=contract_hash,
            run_id=run_id,
            evidence_graph_id=evidence_graph.manifest.graph_id,
            evidence_graph_version=evidence_graph.manifest.graph_version,
            evidence_graph_manifest_sha256=evidence_graph.manifest_sha256,
        )
        result_bytes = canonical_json_bytes(result.model_dump(mode="json"), indent=2)
        try:
            visualization_profile = build_claim_verifier_visualization_data(
                run_id=run_id,
                tool_version=spec.version,
                report=report,
                evidence_set=evidence_graph.evidence_set,
                result=result,
            )
        except (KeyError, TypeError, ValueError):
            return _failed_run(
                request,
                spec,
                ["visualization_data_invalid"],
                input_hash=input_hash,
            )
        try:
            prepared_visualizations = prepare_claim_verifier_visualizations(
                profile=visualization_profile,
                output_dir=request.output_dir,
                run_id=run_id,
                tool_version=spec.version,
            )
        except VisualizationFontUnavailable:
            return _failed_run(
                request,
                spec,
                ["visualization_font_unavailable"],
                input_hash=input_hash,
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return _failed_run(
                request,
                spec,
                ["visualization_render_failed"],
                input_hash=input_hash,
            )

        result_spec = {
            "filename": "claim_verification_result.json",
            "kind": "claim_verification_result",
            "media_type": "application/json",
            "sha256": hashlib.sha256(result_bytes).hexdigest(),
            "evidence_ids": visualization_profile.evidence_ids,
        }
        payloads = {
            "claim_verification_result.json": result_bytes,
            **prepared_visualizations.payloads,
        }
        artifact_specs = [
            result_spec,
            *(
                _artifact_spec_from_manifest(artifact)
                for artifact in prepared_visualizations.artifacts
            ),
        ]
        payloads["artifact_manifest.json"] = canonical_json_bytes(
            _manifest_payload(
                request=request,
                spec=spec,
                run_id=run_id,
                input_hash=input_hash,
                artifact_specs=artifact_specs,
            ),
            indent=2,
        )
        try:
            published = _publish_bundle(
                request=request,
                run_id=run_id,
                payloads=payloads,
                inputs_are_unchanged=lambda refs: (
                    _inputs_unchanged(refs)
                    and _backing_artifacts_unchanged(evidence_graph.backing_artifacts)
                ),
            )
        except PublicationError as exc:
            return _failed_run(
                request,
                spec,
                [exc.reason_code],
                input_hash=input_hash,
            )
        try:
            published_matches = set(published) == set(payloads) and all(
                _read_regular_bytes(published[name]) == payload
                for name, payload in payloads.items()
            )
        except (OSError, RuntimeError):
            published_matches = False
        if not published_matches:
            return _failed_run(
                request,
                spec,
                ["published_bundle_hash_mismatch"],
                input_hash=input_hash,
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
            artifacts=_runtime_artifacts(
                published=published,
                payloads=payloads,
                run_id=run_id,
                profile=visualization_profile,
                result_spec=result_spec,
                prepared_visualizations=prepared_visualizations,
            ),
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
        validate_payload=_validate_json_schema,
        validate_model=_validate_object_version,
    )


def _validate_json_schema(ref: StructuredInputRef, payload: Any) -> None:
    try:
        schema = load_schema(ref.schema_ref)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(payload)
    except (KeyError, FileNotFoundError, SchemaError, ValidationError):
        raise StructuredInputError("structured_input_schema_invalid") from None


def _validate_object_version(ref: StructuredInputRef, value: FrozenModel) -> None:
    version = (
        str(value.graph_version)
        if isinstance(value, CaseEvidenceGraphManifest)
        else getattr(value, "object_version", None)
    )
    if version != ref.object_version:
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
    backing_artifacts = tuple(
        (manifest_ref.path.parent / artifact.filename, artifact.sha256)
        for artifact in (
            manifest.evidence_records,
            manifest.evidence_requirements,
            manifest.reconciliation_records,
            manifest.graph_nodes,
            manifest.graph_edges,
        )
    )
    if not _backing_artifacts_unchanged(backing_artifacts):
        raise ValueError("manifest_integrity_failed")
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
        backing_artifacts=backing_artifacts,
    )


def _backing_artifacts_unchanged(
    artifacts: tuple[tuple[Path, str], ...],
) -> bool:
    try:
        return all(
            hashlib.sha256(_read_regular_bytes(path)).hexdigest() == expected
            for path, expected in artifacts
        )
    except (OSError, RuntimeError):
        return False


def _input_hash(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    release_contract_hash: str,
) -> str:
    payload = {
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "environment_spec_id": spec.environment_spec_id,
        "external_benchmark_id": EXTERNAL_BENCHMARK_ID,
        "external_benchmark_sha256": EXTERNAL_BENCHMARK_SHA256,
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


def _artifact_spec_from_manifest(artifact: ArtifactManifest) -> dict[str, Any]:
    return {
        "filename": artifact.path.name,
        "kind": artifact.kind,
        "media_type": artifact.media_type,
        "sha256": artifact.sha256,
        "evidence_ids": artifact.evidence_ids,
    }


def _manifest_payload(
    *,
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    run_id: str,
    input_hash: str,
    artifact_specs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "environment_spec_id": spec.environment_spec_id,
        "result_schema_ref": RESULT_SCHEMA_REF,
        "input_hash": input_hash,
        "structured_inputs": [
            {
                "role": ref.role,
                "schema_ref": ref.schema_ref,
                "object_version": ref.object_version,
                "sha256": ref.sha256,
                "media_type": ref.media_type,
            }
            for ref in sorted(
                request.object_inputs,
                key=lambda item: (item.role, item.input_id),
            )
        ],
        "artifacts": artifact_specs,
    }


def _runtime_artifacts(
    *,
    published: dict[str, Any],
    payloads: dict[str, bytes],
    run_id: str,
    profile: ClaimVerifierVisualizationDataV1,
    result_spec: dict[str, Any],
    prepared_visualizations: PreparedClaimVerifierVisualizations,
) -> list[ArtifactManifest]:
    artifacts = [
        ArtifactManifest(
            artifact_id=f"artifact:{run_id}:result",
            kind=str(result_spec["kind"]),
            path=published[str(result_spec["filename"])].resolve(),
            media_type=str(result_spec["media_type"]),
            sha256=str(result_spec["sha256"]),
            evidence_ids=profile.evidence_ids,
        ),
        *(
            artifact.model_copy(
                update={"path": published[artifact.path.name].resolve()}
            )
            for artifact in prepared_visualizations.artifacts
        ),
    ]
    artifacts.append(
        ArtifactManifest(
            artifact_id=f"artifact:{run_id}:artifact-manifest",
            kind="artifact_manifest",
            path=published["artifact_manifest.json"].resolve(),
            media_type="application/json",
            sha256=hashlib.sha256(payloads["artifact_manifest.json"]).hexdigest(),
            evidence_ids=profile.evidence_ids,
        )
    )
    return artifacts


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
