from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

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
from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitAssignmentArtifact,
    BiologicalUnitManifest,
    parse_composition,
    profile_lineage_reasons,
)
from bridge.tool_packages.p0_03_target_regional.executor import evaluate_target_regional
from bridge.tool_packages.p0_03_target_regional.models import (
    ProductCase,
    ProductDefinitionCard,
    StateRoleMap,
    TargetRegionalAssessmentSpec,
)
from bridge.toolkit.contracts import (
    ArtifactManifest,
    CellStateEvidenceProfileV2,
    EligibilityResult,
    ExecutionState,
    FrozenModel,
    ImplementationState,
    MeasurementSpecV2,
    QCReadinessProfileV2,
    ReadinessState,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
    ToolRunV2,
)


RESULT_SCHEMA_REF = "bridge://schemas/target-regional-evidence-result/v0.1"
ROLE_MODELS: dict[str, tuple[str, type[FrozenModel]]] = {
    "product_case": ("bridge://schemas/product-case/v0.1", ProductCase),
    "product_definition_card": (
        "bridge://schemas/product-definition-card/v0.1",
        ProductDefinitionCard,
    ),
    "state_role_map": ("bridge://schemas/state-role-map/v0.1", StateRoleMap),
    "target_regional_assessment_spec": (
        "bridge://schemas/target-regional-assessment-spec/v0.1",
        TargetRegionalAssessmentSpec,
    ),
    "measurement_spec": (
        "bridge://schemas/measurement-spec/v0.2",
        MeasurementSpecV2,
    ),
    "cell_state_evidence_profile": (
        "bridge://schemas/cell-state-evidence-profile/v0.2",
        CellStateEvidenceProfileV2,
    ),
    "qc_readiness_profile": (
        "bridge://schemas/qc-readiness-profile/v0.2",
        QCReadinessProfileV2,
    ),
    "biological_unit_manifest": (
        "bridge://schemas/biological-unit-manifest/v0.1",
        BiologicalUnitManifest,
    ),
    "biological_unit_assignment": (
        "bridge://schemas/biological-unit-assignment/v0.1",
        BiologicalUnitAssignmentArtifact,
    ),
}
FIXED_OBJECT_VERSIONS = {
    "product_case": "0.1.0",
    "product_definition_card": "0.1.0",
    "state_role_map": "0.1.0",
    "target_regional_assessment_spec": "0.1.0",
    "cell_state_evidence_profile": "0.2.0",
    "qc_readiness_profile": "0.2.0",
    "biological_unit_manifest": "0.1.0",
    "biological_unit_assignment": "0.1.0",
}
COMPOSITION_STATES = {
    "shadow",
    "not_assessed",
    "unavailable",
    "unknown",
    "missing",
}
EVIDENCE_REF = re.compile(r"^evidence:[A-Za-z0-9._:-]+$")
CELL_STATE_PROFILE_REF = re.compile(r"^cell-state-profile:[A-Za-z0-9._:-]+$")
QC_PROFILE_REF = re.compile(r"^qc-profile:[A-Za-z0-9._:-]+$")


@dataclass(frozen=True)
class TargetRegionalAdapter:
    def check_eligibility(
        self, request: ToolRequestV2, spec: ToolPackageSpecV2
    ) -> EligibilityResult:
        if not isinstance(request, ToolRequestV2):
            tool_id = request.tool_id if isinstance(request, ToolRequest) else "P0-03"
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

        product_case = single_object(request, loaded, "product_case", ProductCase)
        product_definition = single_object(
            request, loaded, "product_definition_card", ProductDefinitionCard
        )
        state_role_map = single_object(
            request, loaded, "state_role_map", StateRoleMap
        )
        assessment_spec = single_object(
            request,
            loaded,
            "target_regional_assessment_spec",
            TargetRegionalAssessmentSpec,
        )
        measurement_spec = single_object(
            request, loaded, "measurement_spec", MeasurementSpecV2
        )
        cell_state_profile = single_object(
            request,
            loaded,
            "cell_state_evidence_profile",
            CellStateEvidenceProfileV2,
        )
        qc_profile = single_object(
            request, loaded, "qc_readiness_profile", QCReadinessProfileV2
        )
        biological_unit_manifest = single_object(
            request,
            loaded,
            "biological_unit_manifest",
            BiologicalUnitManifest,
        )
        input_hash = _input_hash(request, spec)
        run_id = f"run-{input_hash[:16]}"
        try:
            result = evaluate_target_regional(
                run_id=run_id,
                tool_version=spec.version,
                product_case=product_case,
                product_definition=product_definition,
                state_role_map=state_role_map,
                assessment_spec=assessment_spec,
                measurement_spec=measurement_spec,
                cell_state_profile=cell_state_profile,
                cell_state_profile_version=_input_version(
                    request, "cell_state_evidence_profile"
                ),
                qc_profile=qc_profile,
                qc_profile_version=_input_version(request, "qc_readiness_profile"),
                biological_unit_manifest=biological_unit_manifest,
                input_sha256_by_role={
                    ref.role: ref.sha256 for ref in request.object_inputs
                },
            )
        except ValueError as exc:
            reason = str(exc)
            if not reason.startswith("cell_state_composition_"):
                reason = "target_regional_evaluation_failed"
            return _failed_run(request, spec, [reason], input_hash=input_hash)

        payload = canonical_json_bytes(result.model_dump(mode="json"), indent=2)
        try:
            output_file = publish_single_json(
                request=request,
                run_id=run_id,
                filename="target_regional_evidence_result.json",
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
            artifact_id=f"artifact:{run_id}:target-regional-result",
            kind="target_regional_evidence_result",
            path=output_file,
            media_type="application/json",
            sha256=hashlib.sha256(payload).hexdigest(),
            evidence_ids=result.evidence_refs,
        )
        execution_state = (
            ExecutionState.PARTIAL
            if result.result_state == "partial"
            else ExecutionState.SUCCEEDED
        )
        return ToolRunV2(
            run_id=run_id,
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=execution_state,
            tool_version=spec.version,
            environment_spec_id=spec.environment_spec_id,
            input_hash=input_hash,
            created_at=product_case.created_at,
            measurements=[],
            artifacts=[artifact],
            visualizations=[],
            result_schema_ref=RESULT_SCHEMA_REF,
            result=result.model_dump(mode="json"),
            reason_codes=result.reason_codes,
            warnings=[],
        )


adapter = TargetRegionalAdapter()


def _envelope_reasons(
    request: ToolRequestV2, spec: ToolPackageSpecV2
) -> list[str]:
    reasons: list[str] = []
    if request.tool_version is not None and request.tool_version != spec.version:
        reasons.append("tool_version_mismatch")
    if request.assets:
        reasons.append("p0_03_expression_assets_forbidden")
    if request.measurement_spec_ref is not None:
        reasons.append("p0_03_measurement_spec_parameter_forbidden")
    if request.parameters:
        reasons.append("p0_03_parameters_forbidden")
    if request.random_seed != 0:
        reasons.append("p0_03_random_seed_forbidden")
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
        fixed_version = FIXED_OBJECT_VERSIONS.get(ref.role)
        if fixed_version is not None and ref.object_version != fixed_version:
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
    if isinstance(value, MeasurementSpecV2):
        version = value.version
    else:
        version = getattr(value, "object_version", None)
        if version is None:
            version = FIXED_OBJECT_VERSIONS.get(ref.role)
    if version != ref.object_version:
        raise StructuredInputError("object_input_version_mismatch")


def _binding_reasons(
    request: ToolRequestV2,
    loaded: LoadedInputs,
) -> list[str]:
    product_case = single_object(request, loaded, "product_case", ProductCase)
    product_definition = single_object(
        request, loaded, "product_definition_card", ProductDefinitionCard
    )
    state_role_map = single_object(request, loaded, "state_role_map", StateRoleMap)
    assessment_spec = single_object(
        request,
        loaded,
        "target_regional_assessment_spec",
        TargetRegionalAssessmentSpec,
    )
    measurement_spec = single_object(
        request, loaded, "measurement_spec", MeasurementSpecV2
    )
    cell_state_profile = single_object(
        request,
        loaded,
        "cell_state_evidence_profile",
        CellStateEvidenceProfileV2,
    )
    qc_profile = single_object(
        request, loaded, "qc_readiness_profile", QCReadinessProfileV2
    )
    biological_unit_manifest = single_object(
        request,
        loaded,
        "biological_unit_manifest",
        BiologicalUnitManifest,
    )
    biological_unit_assignment = single_object(
        request,
        loaded,
        "biological_unit_assignment",
        BiologicalUnitAssignmentArtifact,
    )
    input_sha256_by_role = {
        ref.role: ref.sha256 for ref in request.object_inputs
    }
    reasons = profile_lineage_reasons(
        product_case=product_case,
        cell_state_profile=cell_state_profile,
        measurement_spec=measurement_spec,
        qc_profile=qc_profile,
        biological_unit_manifest=biological_unit_manifest,
        biological_unit_assignment_artifact=biological_unit_assignment,
        input_sha256_by_role=input_sha256_by_role,
    )
    if product_case.product_definition_ref != product_definition.ref:
        reasons.append("product_definition_binding_mismatch")
    if product_definition.state_role_map_ref != state_role_map.ref:
        reasons.append("state_role_map_binding_mismatch")
    if state_role_map.product_definition_ref != product_definition.ref:
        reasons.append("state_role_map_product_definition_mismatch")
    if assessment_spec.product_definition_ref != product_definition.ref:
        reasons.append("assessment_spec_product_definition_mismatch")
    if (
        state_role_map.annotation_vocabulary_ref
        != cell_state_profile.annotation_vocabulary_ref
    ):
        reasons.append("annotation_vocabulary_binding_mismatch")
    if product_case.assay not in product_definition.supported_assays:
        reasons.append("product_case_assay_not_supported")
    if measurement_spec.assay != product_case.assay:
        reasons.append("measurement_spec_assay_mismatch")
    if (
        measurement_spec.applicable_product_cards
        and product_definition.product_definition_id
        not in measurement_spec.applicable_product_cards
        and product_definition.ref.ref
        not in measurement_spec.applicable_product_cards
    ):
        reasons.append("measurement_spec_product_definition_not_applicable")
    if cell_state_profile.assay != product_case.assay:
        reasons.append("cell_state_profile_assay_mismatch")
    if qc_profile.assay != product_case.assay:
        reasons.append("qc_profile_assay_mismatch")
    if qc_profile.readiness_state in {
        ReadinessState.BLOCKED,
        ReadinessState.NOT_ASSESSED,
        ReadinessState.NOT_APPLICABLE,
    }:
        reasons.append("qc_not_ready_for_target_regional_evidence")
    reasons.extend(_composition_reasons(cell_state_profile))
    if any(
        not EVIDENCE_REF.fullmatch(evidence_ref)
        for evidence_ref in [*cell_state_profile.evidence_ids, *qc_profile.evidence_ids]
    ):
        reasons.append("unsafe_evidence_reference")
    if (
        not CELL_STATE_PROFILE_REF.fullmatch(cell_state_profile.profile_id)
        or not QC_PROFILE_REF.fullmatch(qc_profile.profile_id)
    ):
        reasons.append("unsafe_profile_reference")
    return reasons


def _composition_reasons(
    cell_state_profile: CellStateEvidenceProfileV2,
) -> list[str]:
    state = cell_state_profile.composition.get("state")
    if state not in COMPOSITION_STATES:
        return ["cell_state_composition_state_invalid"]
    try:
        records = parse_composition(cell_state_profile)
    except ValueError as exc:
        return [str(exc)]
    if state != "shadow" and records:
        return ["cell_state_composition_state_conflict"]
    if (
        state == "shadow"
        and cell_state_profile.score_state.value != "shadow"
    ):
        return ["cell_state_composition_score_state_mismatch"]
    return []


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


def _input_version(request: ToolRequestV2, role: str) -> str:
    return next(ref.object_version for ref in request.object_inputs if ref.role == role)


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
