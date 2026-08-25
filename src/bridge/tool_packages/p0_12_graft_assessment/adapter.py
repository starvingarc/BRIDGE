from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import shutil
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


RESULT_SCHEMA_REF = "bridge://schemas/graft-assessment-result/v0.1"
ROLE_MODELS: dict[str, tuple[str, type[FrozenModel]]] = {
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


class PublicationError(ValueError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


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
        reasons = _envelope_reasons(request, spec)
        if request.object_inputs:
            loaded, loading_reasons = _load_inputs(request.object_inputs)
            reasons.extend(loading_reasons)
            if loaded is not None and not loading_reasons and not reasons:
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
        if not eligibility.eligible:
            return _failed_run(request, spec, eligibility.reason_codes)

        loaded: LoadedInputs | None = None
        if request.object_inputs:
            loaded, reasons = _load_inputs(request.object_inputs)
            if loaded is None or reasons:
                return _failed_run(request, spec, reasons)
        input_hash = _input_hash(request, spec)
        run_id = f"run-{input_hash[:16]}"
        result = _build_result(request, loaded, input_hash)
        result_bytes = canonical_json_bytes(result.model_dump(mode="json"), indent=2)
        result_sha = hashlib.sha256(result_bytes).hexdigest()
        manifest = _artifact_manifest_payload(
            request=request,
            spec=spec,
            run_id=run_id,
            input_hash=input_hash,
            result_sha=result_sha,
        )
        manifest_bytes = canonical_json_bytes(manifest, indent=2)
        try:
            published = _publish_bundle(
                request=request,
                run_id=run_id,
                payloads={
                    "graft_assessment_result.json": result_bytes,
                    "artifact_manifest.json": manifest_bytes,
                },
            )
        except PublicationError as exc:
            return _failed_run(
                request,
                spec,
                [exc.reason_code],
                input_hash=input_hash,
            )
        evidence_ids = (
            []
            if loaded is None
            else sorted(
                record.evidence_id
                for record in single_object(
                    request, loaded, "evidence_bundle", GraftEvidenceBundle
                ).records
            )
        )
        artifacts = [
            ArtifactManifest(
                artifact_id=f"artifact:{run_id}:{path.stem}",
                kind=path.stem,
                path=path,
                media_type="application/json",
                sha256=hashlib.sha256(read_regular_bytes(path)).hexdigest(),
                evidence_ids=evidence_ids,
            )
            for path in sorted(published.values(), key=lambda item: item.name)
        ]
        created_at = (
            datetime(1970, 1, 1, tzinfo=timezone.utc)
            if loaded is None
            else single_object(
                request, loaded, "evidence_bundle", GraftEvidenceBundle
            ).created_at
        )
        return ToolRunV2(
            run_id=run_id,
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=ExecutionState.SUCCEEDED,
            tool_version=spec.version,
            environment_spec_id=spec.environment_spec_id,
            input_hash=input_hash,
            created_at=created_at,
            measurements=[],
            artifacts=artifacts,
            visualizations=[],
            result_schema_ref=RESULT_SCHEMA_REF,
            result=result.model_dump(mode="json"),
            reason_codes=[],
            warnings=[],
        )


adapter = GraftAssessmentAdapter()


def _envelope_reasons(
    request: ToolRequestV2, spec: ToolPackageSpecV2
) -> list[str]:
    reasons: list[str] = []
    if request.tool_version is not None and request.tool_version != spec.version:
        reasons.append("tool_version_mismatch")
    if request.assets:
        reasons.append("p0_12_expression_assets_forbidden")
    if request.measurement_spec_ref is not None:
        reasons.append("p0_12_measurement_spec_forbidden")
    if request.parameters:
        reasons.append("p0_12_parameters_forbidden")
    if request.object_inputs:
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
            if contract is not None and ref.object_version != "0.1.0":
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
    if sorted(assessment.method_ids) != sorted(spec.method_ids):
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


def _input_hash(request: ToolRequestV2, spec: ToolPackageSpecV2) -> str:
    payload = {
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "environment_spec_id": spec.environment_spec_id,
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


def _artifact_manifest_payload(
    *,
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    run_id: str,
    input_hash: str,
    result_sha: str,
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
            for ref in sorted(request.object_inputs, key=lambda item: item.role)
        ],
        "artifacts": [
            {
                "filename": "graft_assessment_result.json",
                "media_type": "application/json",
                "sha256": result_sha,
            }
        ],
    }


def _publish_bundle(
    *,
    request: ToolRequestV2,
    run_id: str,
    payloads: dict[str, bytes],
) -> dict[str, Path]:
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
        for filename, payload in payloads.items():
            (staging / filename).write_bytes(payload)
        if not inputs_unchanged(request.object_inputs):
            raise PublicationError("structured_input_modified_during_run")
        final = output_root / run_id
        state = directory_state(final)
        if state == "directory":
            try:
                matches = {path.name for path in final.iterdir()} == set(payloads)
                matches = matches and all(
                    read_regular_bytes(final / filename) == payload
                    for filename, payload in payloads.items()
                )
            except (OSError, RuntimeError):
                matches = False
            if not matches:
                raise PublicationError("existing_run_bundle_hash_mismatch")
            shutil.rmtree(staging)
        elif state == "missing":
            os.replace(staging, final)
        else:
            raise PublicationError("existing_run_bundle_hash_mismatch")
        published = {name: final / name for name in payloads}
        if any(
            read_regular_bytes(path) != payloads[name]
            for name, path in published.items()
        ):
            raise PublicationError("published_result_hash_mismatch")
        return published
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
        fingerprint_input_key="object_inputs",
        input_hash=input_hash,
    )


def _failed_v1_request(
    request: ToolRequest, spec: ToolPackageSpecV2
) -> ToolRunV2:
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
