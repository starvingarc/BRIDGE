from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    PublicationError,
    StructuredInputError,
    canonical_json_bytes,
    directory_state,
    failed_v2_run,
    inputs_unchanged,
    load_structured_inputs,
    read_regular_bytes,
    request_v2_from_v1,
    single_object,
)
from bridge.tool_packages._structured_runtime import (
    publish_json_bundle as _publish_bundle,
)
from bridge.tool_packages.p0_12_graft_assessment.analysis import (
    ROLE_MODELS as ANALYSIS_ROLE_MODELS,
    GraftAnalysisError,
    build_expression_result,
    expression_asset,
    expression_asset_unchanged,
    expression_binding_reasons,
    is_expression_analysis_request,
)
from bridge.tool_packages.p0_12_graft_assessment.models import (
    GraftAnalysisMode,
    GraftAssessmentResult,
    GraftAssessmentSpec,
    GraftAvailability,
    GraftCase,
    GraftEvidenceBundle,
    GraftEvidenceState,
    GraftLinkageState,
    GraftResultState,
    GraftRoleSummary,
    GraftSourceBinding,
    PreparationGraftLinkage,
)
from bridge.tool_packages.p0_12_graft_assessment.visualization import (
    PreparedGraftAssessmentVisualizations,
    prepare_graft_assessment_visualizations,
)
from bridge.tool_packages.p0_12_graft_assessment.visualization_data import (
    GraftAssessmentVisualizationDataV1,
    build_graft_assessment_visualization_data,
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

RESULT_SCHEMA_REF = "bridge://schemas/graft-assessment-run-result/v0.1"
PRECOMPUTED_METHOD_IDS = [
    "METHOD-BRIDGE-GRAFTCASE-VALIDATOR",
    "METHOD-BRIDGE-SOFT-COMPOSITION-404672",
]
PRECOMPUTED_ROLE_MODELS: dict[str, tuple[str, type[FrozenModel]]] = {
    "graft_case": ("bridge://schemas/graft-case/v0.1", GraftCase),
    "assessment_spec": (
        "bridge://schemas/graft-assessment-spec/v0.1",
        GraftAssessmentSpec,
    ),
    "evidence_bundle": (
        "bridge://schemas/graft-evidence-bundle/v0.1",
        GraftEvidenceBundle,
    ),
}
ROLE_MODELS = {**PRECOMPUTED_ROLE_MODELS, **ANALYSIS_ROLE_MODELS}


@dataclass(frozen=True)
class _PreparedRequest:
    expression_mode: bool
    loaded: LoadedInputs | None
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class GraftAssessmentAdapter:
    def check_eligibility(
        self, request: ToolRequestV2, spec: ToolPackageSpecV2
    ) -> EligibilityResult:
        if not isinstance(request, ToolRequestV2):
            tool_id = request.tool_id if isinstance(request, ToolRequest) else "P0-12"
            return EligibilityResult(
                tool_id=tool_id,
                eligible=False,
                reason_codes=["tool_request_v2_required"],
            )
        prepared = _prepare(request, spec)
        return EligibilityResult(
            tool_id=request.tool_id,
            eligible=not prepared.reason_codes,
            reason_codes=list(prepared.reason_codes),
        )

    def run(self, request: ToolRequestV2, spec: ToolPackageSpecV2) -> ToolRunV2:
        if not isinstance(request, ToolRequestV2):
            return _failed_v1_request(request, spec)
        prepared = _prepare(request, spec)
        input_hash = _input_hash(request, spec, prepared.expression_mode)
        if prepared.reason_codes:
            return _failed_run(
                request,
                spec,
                list(prepared.reason_codes),
                input_hash=input_hash,
            )
        loaded = prepared.loaded
        if prepared.expression_mode:
            if loaded is None:
                return _failed_run(
                    request,
                    spec,
                    ["graft_expression_inputs_missing"],
                    input_hash=input_hash,
                )
            asset = expression_asset(request, loaded)
            try:
                result = build_expression_result(
                    request=request,
                    loaded=loaded,
                    tool_version=spec.version,
                    input_hash=input_hash,
                )
            except GraftAnalysisError as exc:
                return _failed_run(
                    request,
                    spec,
                    [exc.reason_code],
                    input_hash=input_hash,
                )
            result_filename = "graft_expression_analysis_result.json"
            evidence_ids: list[str] = []

            def inputs_are_unchanged(refs: list[StructuredInputRef]) -> bool:
                return inputs_unchanged(refs) and expression_asset_unchanged(
                    asset
                )
        else:
            result = _build_result(request, loaded, input_hash)
            result_filename = "graft_assessment_result.json"
            evidence_ids = (
                []
                if loaded is None
                else sorted(
                    record.evidence_id
                    for record in single_object(
                        request,
                        loaded,
                        "evidence_bundle",
                        GraftEvidenceBundle,
                    ).records
                )
            )
            inputs_are_unchanged = inputs_unchanged
        run_id = f"run-{input_hash[:16]}"
        result_bytes = canonical_json_bytes(
            result.model_dump(mode="json"), indent=2
        )
        result_sha = hashlib.sha256(result_bytes).hexdigest()
        try:
            profile = build_graft_assessment_visualization_data(
                result=result,
                result_sha=result_sha,
                run_id=run_id,
                tool_version=spec.version,
            )
        except (TypeError, ValueError):
            return _failed_run(
                request,
                spec,
                ["visualization_data_invalid"],
                input_hash=input_hash,
            )
        try:
            prepared = prepare_graft_assessment_visualizations(
                profile=profile,
                output_dir=request.output_dir,
                run_id=run_id,
                tool_version=spec.version,
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return _failed_run(
                request,
                spec,
                ["visualization_render_failed"],
                input_hash=input_hash,
            )

        core_spec = {
            "filename": result_filename,
            "kind": result_filename.removesuffix(".json"),
            "media_type": "application/json",
            "sha256": result_sha,
            "evidence_ids": evidence_ids,
        }
        artifact_specs = [
            core_spec,
            *(
                _artifact_spec_from_manifest(artifact)
                for artifact in prepared.artifacts
            ),
        ]
        payloads = {
            result_filename: result_bytes,
            **prepared.payloads,
        }
        payloads["artifact_manifest.json"] = canonical_json_bytes(
            _artifact_manifest_payload(
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
                inputs_are_unchanged=inputs_are_unchanged,
            )
        except PublicationError as exc:
            return _failed_run(
                request,
                spec,
                [exc.reason_code],
                input_hash=input_hash,
            )
        try:
            published_matches = (
                set(published) == set(payloads)
                and all(
                    read_regular_bytes(published[name]) == payload
                    for name, payload in payloads.items()
                )
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
        artifacts = _runtime_artifacts(
            published=published,
            payloads=payloads,
            run_id=run_id,
            profile=profile,
            core_spec=core_spec,
            prepared=prepared,
        )
        return ToolRunV2(
            run_id=run_id,
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=ExecutionState.SUCCEEDED,
            tool_version=spec.version,
            environment_spec_id=spec.environment_spec_id,
            input_hash=input_hash,
            created_at=result.created_at,
            measurements=[],
            artifacts=artifacts,
            visualizations=[],
            result_schema_ref=RESULT_SCHEMA_REF,
            result=result.model_dump(mode="json"),
            reason_codes=[],
            warnings=[],
        )


adapter = GraftAssessmentAdapter()


def _prepare(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
) -> _PreparedRequest:
    expression_mode = is_expression_analysis_request(request)
    role_models = (
        ANALYSIS_ROLE_MODELS if expression_mode else PRECOMPUTED_ROLE_MODELS
    )
    reasons = _envelope_reasons(request, spec, expression_mode, role_models)
    loaded: LoadedInputs | None = None
    if request.object_inputs and not reasons:
        loaded, loading_reasons = _load_inputs(request.object_inputs, role_models)
        reasons.extend(loading_reasons)
    if loaded is not None and not reasons:
        reasons.extend(
            expression_binding_reasons(request, loaded, spec)
            if expression_mode
            else _precomputed_binding_reasons(request, loaded, spec)
        )
    return _PreparedRequest(
        expression_mode=expression_mode,
        loaded=loaded,
        reason_codes=tuple(sorted(set(reasons))),
    )


def _envelope_reasons(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    expression_mode: bool,
    role_models: dict[str, tuple[str, type[FrozenModel]]],
) -> list[str]:
    reasons: list[str] = []
    if request.tool_version is not None and request.tool_version != spec.version:
        reasons.append("tool_version_mismatch")
    if request.assets:
        reasons.append(
            "p0_12_expression_assets_require_manifest"
            if expression_mode
            else "p0_12_expression_assets_forbidden"
        )
    if request.measurement_spec_ref is not None:
        reasons.append("p0_12_measurement_spec_forbidden")
    if request.parameters:
        reasons.append("p0_12_parameters_forbidden")
    if expression_mode or request.object_inputs:
        roles = [ref.role for ref in request.object_inputs]
        for role in role_models:
            if roles.count(role) != 1:
                reasons.append(f"exactly_one_{role}_required")
        if any(role not in role_models for role in roles):
            reasons.append("unsupported_object_input_role")
        for ref in request.object_inputs:
            contract = role_models.get(ref.role)
            if contract is not None and ref.schema_ref != contract[0]:
                reasons.append("object_input_schema_mismatch")
            if contract is not None and ref.object_version != "0.1.0":
                reasons.append("object_input_version_mismatch")
    if directory_state(request.output_dir) == "other":
        reasons.append("output_dir_not_regular_directory")
    return reasons


def _load_inputs(
    refs: list[StructuredInputRef],
    role_models: dict[str, tuple[str, type[FrozenModel]]],
) -> tuple[LoadedInputs | None, list[str]]:
    return load_structured_inputs(
        refs,
        model_for=lambda ref: role_models.get(ref.role, ("", None))[1],
        validate_model=_validate_object_version,
    )


def _validate_object_version(ref: StructuredInputRef, value: FrozenModel) -> None:
    if getattr(value, "object_version", None) != ref.object_version:
        raise StructuredInputError("object_input_version_mismatch")


def _precomputed_binding_reasons(
    request: ToolRequestV2,
    loaded: LoadedInputs,
    spec: ToolPackageSpecV2,
) -> list[str]:
    case = single_object(request, loaded, "graft_case", GraftCase)
    assessment = single_object(
        request, loaded, "assessment_spec", GraftAssessmentSpec
    )
    bundle = single_object(
        request, loaded, "evidence_bundle", GraftEvidenceBundle
    )
    reasons: list[str] = []
    if bundle.graft_case_ref != case.graft_case_id:
        reasons.append("graft_case_binding_mismatch")
    if bundle.assessment_spec_ref != assessment.assessment_spec_id:
        reasons.append("assessment_spec_binding_mismatch")
    if (
        assessment.method_ids != PRECOMPUTED_METHOD_IDS
        or not set(PRECOMPUTED_METHOD_IDS).issubset(spec.method_ids)
    ):
        reasons.append("assessment_spec_binding_mismatch")
    rules = {rule.role_id: rule for rule in assessment.role_rules}
    for record in bundle.records:
        rule = rules.get(record.role_id)
        if (
            rule is None
            or record.metric_id not in rule.allowed_metric_ids
            or record.state not in rule.allowed_states
            or record.state not in assessment.state_classes
        ):
            reasons.append("graft_evidence_contract_mismatch")
    return reasons


def _input_hash(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    expression_mode: bool,
) -> str:
    payload = {
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "environment_spec_id": spec.environment_spec_id,
        "mode": "expression_analysis" if expression_mode else "precomputed",
        "object_inputs": [
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


def _build_result(
    request: ToolRequestV2,
    loaded: LoadedInputs | None,
    input_hash: str,
) -> GraftAssessmentResult:
    result_id = f"graft-assessment:{input_hash[:24]}"
    if loaded is None:
        return GraftAssessmentResult(
            result_id=result_id,
            result_version="0.1.0",
            state=GraftResultState.NOT_PROVIDED,
            graft_availability=GraftAvailability.NOT_PROVIDED,
            linkage_state=GraftLinkageState.NOT_APPLICABLE,
            analysis_mode=GraftAnalysisMode.UNAVAILABLE,
            evidence_state=GraftEvidenceState.UNAVAILABLE,
            source_bindings=[],
            role_summaries=[],
            missing_metadata=[],
            confounder_refs=[],
            required_roles_missing=[],
            reason_codes=["graft_not_provided"],
            created_at=datetime(1970, 1, 1, tzinfo=timezone.utc),
        )

    case = single_object(request, loaded, "graft_case", GraftCase)
    assessment = single_object(
        request, loaded, "assessment_spec", GraftAssessmentSpec
    )
    bundle = single_object(
        request, loaded, "evidence_bundle", GraftEvidenceBundle
    )
    records_by_role = defaultdict(list)
    for record in bundle.records:
        records_by_role[record.role_id].append(record)
    summaries: list[GraftRoleSummary] = []
    for role_id in sorted(records_by_role):
        records = records_by_role[role_id]
        class_counts = Counter(
            assessment.state_classes[record.state] for record in records
        )
        summaries.append(
            GraftRoleSummary(
                role_id=role_id,
                record_count=len(records),
                metric_ids=sorted({record.metric_id for record in records}),
                evidence_states=sorted({record.state for record in records}),
                state_class_counts=dict(sorted(class_counts.items())),
                evidence_ids=sorted(record.evidence_id for record in records),
            )
        )
    missing_metadata = [
        field_name
        for field_name in (
            "animal_id",
            "post_transplant_timepoint",
            "biological_replicate_id",
        )
        if getattr(case, field_name) is None
    ]
    required_roles_missing = sorted(
        rule.role_id
        for rule in assessment.role_rules
        if rule.required and rule.role_id not in records_by_role
    )
    linked = bool(
        case.originating_preparation_id and case.linkage_evidence_refs
    )
    linkage = (
        PreparationGraftLinkage(
            originating_preparation_id=case.originating_preparation_id,
            linkage_evidence_refs=case.linkage_evidence_refs,
        )
        if linked and case.originating_preparation_id is not None
        else None
    )
    reason_codes = ["graft_evidence_descriptive_candidate"]
    if missing_metadata:
        reason_codes.append("graft_metadata_incomplete")
    if case.declared_confounder_refs:
        reason_codes.append("graft_confounding_declared")
    if required_roles_missing:
        reason_codes.append("graft_required_role_missing")
    if not linked:
        reason_codes.append("graft_preparation_linkage_not_provided")
    ref_by_role = {ref.role: ref for ref in request.object_inputs}
    bindings = [
        GraftSourceBinding(
            input_id=ref.input_id,
            role=role,
            schema_ref=ref.schema_ref,
            object_version="0.1.0",
            source_sha256=ref.sha256,
        )
        for role, ref in sorted(ref_by_role.items())
    ]
    return GraftAssessmentResult(
        result_id=result_id,
        result_version="0.1.0",
        state=GraftResultState.CANDIDATE,
        graft_availability=GraftAvailability.PROVIDED,
        graft_case_ref=case.graft_case_id,
        assessment_spec_ref=assessment.assessment_spec_id,
        evidence_bundle_ref=bundle.evidence_bundle_id,
        linkage_state=(
            GraftLinkageState.PROVIDED_LINKED
            if linked
            else GraftLinkageState.PROVIDED_UNLINKED
        ),
        analysis_mode=GraftAnalysisMode.DESCRIPTIVE_ONLY,
        evidence_state=GraftEvidenceState.SHADOW,
        source_bindings=bindings,
        role_summaries=summaries,
        missing_metadata=missing_metadata,
        confounder_refs=sorted(case.declared_confounder_refs),
        required_roles_missing=required_roles_missing,
        preparation_linkage=linkage,
        reason_codes=sorted(reason_codes),
        created_at=bundle.created_at,
    )


def _artifact_spec_from_manifest(
    artifact: ArtifactManifest,
) -> dict[str, Any]:
    return {
        "filename": artifact.path.name,
        "kind": artifact.kind,
        "media_type": artifact.media_type,
        "sha256": artifact.sha256,
        "evidence_ids": artifact.evidence_ids,
    }


def _artifact_manifest_payload(
    *,
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    run_id: str,
    input_hash: str,
    artifact_specs: list[dict[str, Any]],
) -> dict[str, object]:
    return {
        "manifest_version": "0.1.0",
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "run_id": run_id,
        "input_hash": input_hash,
        "inputs": [
            {
                "input_id": ref.input_id,
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
    profile: GraftAssessmentVisualizationDataV1,
    core_spec: dict[str, Any],
    prepared: PreparedGraftAssessmentVisualizations,
) -> list[ArtifactManifest]:
    result_artifact = ArtifactManifest(
        artifact_id=(
            f"artifact:{run_id}:"
            f"{str(core_spec['filename']).removesuffix('.json')}"
        ),
        kind=str(core_spec["kind"]),
        path=published[str(core_spec["filename"])].resolve(),
        media_type=str(core_spec["media_type"]),
        sha256=str(core_spec["sha256"]),
        evidence_ids=list(core_spec["evidence_ids"]),
    )
    artifacts = [
        result_artifact,
        *(
            artifact.model_copy(
                update={
                    "path": published[artifact.path.name].resolve()
                }
            )
            for artifact in prepared.artifacts
        ),
        ArtifactManifest(
            artifact_id=f"artifact:{run_id}:artifact-manifest",
            kind="artifact_manifest",
            path=published["artifact_manifest.json"].resolve(),
            media_type="application/json",
            sha256=hashlib.sha256(
                payloads["artifact_manifest.json"]
            ).hexdigest(),
            evidence_ids=profile.evidence_ids,
        ),
    ]
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
        fingerprint_input_key="object_inputs",
        input_hash=input_hash,
    )


def _failed_v1_request(
    request: ToolRequest, spec: ToolPackageSpecV2
) -> ToolRunV2:
    return _failed_run(
        request_v2_from_v1(request), spec, ["tool_request_v2_required"]
    )
