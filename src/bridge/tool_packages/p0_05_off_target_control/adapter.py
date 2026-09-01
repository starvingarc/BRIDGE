from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass

from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitManifest,
    ProductCase,
    ProductDefinitionCard,
)
from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    PublicationError,
    StructuredInputError,
    canonical_json_bytes,
    directory_state,
    failed_v2_run,
    load_structured_inputs,
    publish_json_bundle,
    request_v2_from_v1,
    single_object,
)
from bridge.tool_packages.p0_05_off_target_control.method_binding import (
    method_binding_reasons,
)
from bridge.tool_packages.p0_05_off_target_control.method_models import (
    OffTargetMethodInput,
    OffTargetMethodSpec,
)
from bridge.tool_packages.p0_05_off_target_control.method_runtime import (
    execute_methods,
)
from bridge.tool_packages.p0_05_off_target_control.models import (
    AssessmentState,
    CoverageState,
    ExclusionState,
    OffTargetAssessmentSpec,
    OffTargetControlProfile,
    OffTargetEvidenceBundle,
    ProductRole,
    RareDetectionState,
    RareStateRecord,
    RoleCompositionRecord,
    StateRoleMap,
    UnknownProfile,
    UnknownReasonRecord,
)
from bridge.tool_packages.p0_05_off_target_control.visualization import (
    prepare_off_target_control_visualizations,
)
from bridge.tool_packages.p0_05_off_target_control.visualization_data import (
    build_off_target_control_visualization_data,
)
from bridge.toolkit.contracts import (
    ArtifactManifest,
    CellStateEvidenceProfileV2,
    CellStateEvidenceProfileV3,
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

RESULT_SCHEMA_REF = "bridge://schemas/off-target-control-profile/v0.1"
ROLE_CONTRACTS: dict[str, tuple[str, str, type[FrozenModel]]] = {
    "product_case": (
        "bridge://schemas/product-case/v0.1",
        "0.1.0",
        ProductCase,
    ),
    "product_definition_card": (
        "bridge://schemas/product-definition-card/v0.1",
        "0.1.0",
        ProductDefinitionCard,
    ),
    "state_role_map": (
        "bridge://schemas/state-role-map/v0.1",
        "0.1.0",
        StateRoleMap,
    ),
    "off_target_assessment_spec": (
        "bridge://schemas/off-target-assessment-spec/v0.1",
        "0.1.0",
        OffTargetAssessmentSpec,
    ),
    "cell_state_evidence_profile": (
        "bridge://schemas/cell-state-evidence-profile/v0.2",
        "0.2.0",
        CellStateEvidenceProfileV2,
    ),
    "off_target_evidence_bundle": (
        "bridge://schemas/off-target-evidence-bundle/v0.1",
        "0.1.0",
        OffTargetEvidenceBundle,
    ),
    "biological_unit_manifest": (
        "bridge://schemas/biological-unit-manifest/v0.1",
        "0.1.0",
        BiologicalUnitManifest,
    ),
    "off_target_method_spec": (
        "bridge://schemas/off-target-method-spec/v0.1",
        "0.1.0",
        OffTargetMethodSpec,
    ),
    "off_target_method_input": (
        "bridge://schemas/off-target-method-input/v0.1",
        "0.1.0",
        OffTargetMethodInput,
    ),
}
METHOD_ROLES = frozenset(
    {
        "biological_unit_manifest",
        "off_target_method_spec",
        "off_target_method_input",
    }
)
CELL_STATE_V3_CONTRACT = (
    "bridge://schemas/cell-state-evidence-profile/v0.3",
    "0.3.0",
    CellStateEvidenceProfileV3,
)
VISUAL_EVIDENCE_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*(?::[A-Za-z0-9][A-Za-z0-9_.-]*)*$"
)


@dataclass(frozen=True)
class OffTargetControlAdapter:
    def check_eligibility(
        self, request: ToolRequestV2, spec: ToolPackageSpecV2
    ) -> EligibilityResult:
        if not isinstance(request, ToolRequestV2):
            tool_id = request.tool_id if isinstance(request, ToolRequest) else "P0-05"
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

    def run(
        self, request: ToolRequestV2 | ToolRequest, spec: ToolPackageSpecV2
    ) -> ToolRunV2:
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
        role_map = single_object(request, loaded, "state_role_map", StateRoleMap)
        assessment_spec = single_object(
            request,
            loaded,
            "off_target_assessment_spec",
            OffTargetAssessmentSpec,
        )
        method_mode = _uses_method_runtime(request.object_inputs)
        cell_state_model = (
            CellStateEvidenceProfileV3 if method_mode else CellStateEvidenceProfileV2
        )
        cell_state_profile = single_object(
            request,
            loaded,
            "cell_state_evidence_profile",
            cell_state_model,
        )
        evidence_bundle = single_object(
            request,
            loaded,
            "off_target_evidence_bundle",
            OffTargetEvidenceBundle,
        )

        input_hash = _input_hash(request, spec)
        run_id = f"run-{input_hash[:16]}"
        result = _aggregate_profile(
            request=request,
            spec=spec,
            input_hash=input_hash,
            product_case=product_case,
            product_definition=product_definition,
            role_map=role_map,
            assessment_spec=assessment_spec,
            cell_state_profile=cell_state_profile,
            evidence_bundle=evidence_bundle,
        )
        result_bytes = canonical_json_bytes(result.model_dump(mode="json"), indent=2)
        payloads = {"off_target_control_profile.json": result_bytes}
        method_spec = None
        method_input = None
        method_bundle = None
        method_bytes: bytes | None = None
        method_bundle_sha256: str | None = None
        if method_mode:
            biological_units = single_object(
                request,
                loaded,
                "biological_unit_manifest",
                BiologicalUnitManifest,
            )
            method_spec = single_object(
                request, loaded, "off_target_method_spec", OffTargetMethodSpec
            )
            method_input = single_object(
                request,
                loaded,
                "off_target_method_input",
                OffTargetMethodInput,
            )
            input_refs = {ref.role: ref for ref in request.object_inputs}
            method_bundle = execute_methods(
                tool_version=spec.version,
                input_hash=input_hash,
                random_seed=request.random_seed,
                role_map=role_map,
                assessment_spec=assessment_spec,
                evidence=evidence_bundle,
                method_spec=method_spec,
                method_input=method_input,
                method_spec_sha256=input_refs["off_target_method_spec"].sha256,
                method_input_sha256=input_refs["off_target_method_input"].sha256,
                biological_unit_manifest_sha256=input_refs[
                    "biological_unit_manifest"
                ].sha256,
            )
            method_bytes = canonical_json_bytes(
                method_bundle.model_dump(mode="json"), indent=2
            )
            method_bundle_sha256 = hashlib.sha256(method_bytes).hexdigest()
            payloads["off_target_method_bundle.json"] = method_bytes
        try:
            visualization_profile = build_off_target_control_visualization_data(
                run_id=run_id,
                tool_version=spec.version,
                result=result,
                composition_coverage_state=evidence_bundle.composition_coverage_state,
                role_map=role_map,
                cell_state_profile=cell_state_profile,
                input_sha256_by_role={
                    ref.role: ref.sha256 for ref in request.object_inputs
                },
                method_spec=method_spec,
                method_input=method_input,
                method_bundle=method_bundle,
                method_bundle_sha256=method_bundle_sha256,
            )
        except (KeyError, ValueError):
            return _failed_run(
                request, spec, ["visualization_data_invalid"], input_hash=input_hash
            )
        try:
            prepared_visualizations = prepare_off_target_control_visualizations(
                profile=visualization_profile,
                output_dir=request.output_dir,
                run_id=run_id,
                tool_version=spec.version,
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return _failed_run(
                request, spec, ["visualization_render_failed"], input_hash=input_hash
            )
        payloads.update(prepared_visualizations.payloads)
        try:
            published = publish_json_bundle(
                request=request,
                run_id=run_id,
                payloads=payloads,
            )
        except PublicationError as exc:
            return _failed_run(
                request,
                spec,
                [exc.reason_code],
                input_hash=input_hash,
            )
        evidence_ids = sorted(set(cell_state_profile.evidence_ids))
        artifacts = [
            ArtifactManifest(
                artifact_id=f"artifact:{run_id}:off-target-control",
                kind="off_target_control_profile",
                path=published["off_target_control_profile.json"],
                media_type="application/json",
                sha256=hashlib.sha256(result_bytes).hexdigest(),
                evidence_ids=evidence_ids,
            )
        ]
        if method_bytes is not None:
            artifacts.append(
                ArtifactManifest(
                    artifact_id=f"artifact:{run_id}:off-target-methods",
                    kind="off_target_method_bundle",
                    path=published["off_target_method_bundle.json"],
                    media_type="application/json",
                    sha256=hashlib.sha256(method_bytes).hexdigest(),
                    evidence_ids=evidence_ids,
                )
            )
        artifacts.extend(prepared_visualizations.artifacts)
        return ToolRunV2(
            run_id=run_id,
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=ExecutionState.SUCCEEDED,
            tool_version=spec.version,
            environment_spec_id=spec.environment_spec_id,
            input_hash=input_hash,
            created_at=evidence_bundle.created_at,
            measurements=[],
            artifacts=artifacts,
            visualizations=[],
            result_schema_ref=RESULT_SCHEMA_REF,
            result=result.model_dump(mode="json"),
            reason_codes=[],
            warnings=[],
        )


adapter = OffTargetControlAdapter()


def _uses_method_runtime(refs: list[StructuredInputRef]) -> bool:
    return any(ref.role in METHOD_ROLES for ref in refs)


def _cell_state_contract(method_mode: bool):
    return (
        CELL_STATE_V3_CONTRACT
        if method_mode
        else ROLE_CONTRACTS["cell_state_evidence_profile"]
    )


def _envelope_reasons(request: ToolRequestV2, spec: ToolPackageSpecV2) -> list[str]:
    reasons: list[str] = []
    if request.tool_id != spec.tool_id:
        reasons.append("tool_id_mismatch")
    if request.tool_version is not None and request.tool_version != spec.version:
        reasons.append("tool_version_mismatch")
    if request.assets:
        reasons.append("p0_05_expression_assets_forbidden")
    if request.measurement_spec_ref is not None:
        reasons.append("p0_05_measurement_spec_forbidden")
    if request.parameters:
        reasons.append("p0_05_parameters_forbidden")
    roles = [ref.role for ref in request.object_inputs]
    base_roles = set(ROLE_CONTRACTS) - METHOD_ROLES
    for role in base_roles:
        if roles.count(role) != 1:
            reasons.append(f"exactly_one_{role}_required")
    method_mode = _uses_method_runtime(request.object_inputs)
    if method_mode:
        for role in METHOD_ROLES:
            if roles.count(role) != 1:
                reasons.append(f"exactly_one_{role}_required")
    if any(role not in ROLE_CONTRACTS for role in roles):
        reasons.append("unsupported_object_input_role")
    for ref in request.object_inputs:
        contract = ROLE_CONTRACTS.get(ref.role)
        if contract is None:
            continue
        if ref.role == "cell_state_evidence_profile":
            contract = _cell_state_contract(method_mode)
        schema_ref, object_version, _model = contract
        if ref.schema_ref != schema_ref:
            reasons.append("object_input_schema_mismatch")
        if ref.object_version != object_version:
            reasons.append("object_input_version_mismatch")
    if directory_state(request.output_dir) == "other":
        reasons.append("output_dir_not_regular_directory")
    return reasons


def _load_inputs(
    refs: list[StructuredInputRef],
) -> tuple[LoadedInputs | None, list[str]]:
    method_mode = _uses_method_runtime(refs)

    def model_for(ref: StructuredInputRef):
        if ref.role == "cell_state_evidence_profile":
            return _cell_state_contract(method_mode)[2]
        return ROLE_CONTRACTS.get(ref.role, ("", "", None))[2]

    return load_structured_inputs(
        refs,
        model_for=model_for,
        validate_model=_validate_object_version,
    )


def _validate_object_version(ref: StructuredInputRef, value: FrozenModel) -> None:
    if ref.role == "cell_state_evidence_profile":
        if isinstance(value, CellStateEvidenceProfileV3):
            expected = CELL_STATE_V3_CONTRACT[1]
        else:
            expected = ROLE_CONTRACTS[ref.role][1]
        actual = ref.object_version
    else:
        expected = ROLE_CONTRACTS[ref.role][1]
        actual = getattr(value, "object_version", None)
    if actual != expected:
        raise StructuredInputError("object_input_version_mismatch")


def _binding_reasons(request: ToolRequestV2, loaded: LoadedInputs) -> list[str]:
    product_case = single_object(request, loaded, "product_case", ProductCase)
    product_definition = single_object(
        request, loaded, "product_definition_card", ProductDefinitionCard
    )
    role_map = single_object(request, loaded, "state_role_map", StateRoleMap)
    assessment_spec = single_object(
        request,
        loaded,
        "off_target_assessment_spec",
        OffTargetAssessmentSpec,
    )
    method_mode = _uses_method_runtime(request.object_inputs)
    cell_state_model = (
        CellStateEvidenceProfileV3 if method_mode else CellStateEvidenceProfileV2
    )
    cell_state_profile = single_object(
        request,
        loaded,
        "cell_state_evidence_profile",
        cell_state_model,
    )
    evidence_bundle = single_object(
        request,
        loaded,
        "off_target_evidence_bundle",
        OffTargetEvidenceBundle,
    )
    input_refs = {ref.role: ref for ref in request.object_inputs}
    reasons: list[str] = []

    product_definition_ref = product_definition.ref.ref
    role_map_ref = role_map.ref.ref
    if product_case.product_definition_ref.ref != product_definition_ref:
        reasons.append("product_definition_binding_mismatch")
    if product_definition.state_role_map_ref.ref != role_map_ref:
        reasons.append("state_role_map_binding_mismatch")
    if role_map.product_definition_ref.ref != product_definition_ref:
        reasons.append("state_role_map_product_definition_mismatch")
    if product_case.assay not in product_definition.supported_assays:
        reasons.append("product_case_assay_not_supported")
    if cell_state_profile.assay != product_case.assay:
        reasons.append("cell_state_assay_binding_mismatch")
    if not cell_state_profile.evidence_ids:
        reasons.append("cell_state_evidence_ids_required_for_visualization")
    elif any(
        VISUAL_EVIDENCE_ID_PATTERN.fullmatch(evidence_id) is None
        for evidence_id in cell_state_profile.evidence_ids
    ):
        reasons.append("cell_state_evidence_ids_invalid_for_visualization")
    if (
        cell_state_profile.measurement_spec_id
        != product_case.measurement_spec_ref.object_id
        or cell_state_profile.measurement_spec_version
        != product_case.measurement_spec_ref.object_version
    ):
        reasons.append("cell_state_measurement_spec_binding_mismatch")

    if not assessment_spec.active:
        reasons.append("off_target_assessment_spec_inactive")
    if assessment_spec.product_definition_ref.ref != product_definition_ref:
        reasons.append("assessment_spec_product_definition_mismatch")
    if assessment_spec.state_role_map_ref.ref != role_map_ref:
        reasons.append("assessment_spec_state_role_map_mismatch")
    if assessment_spec.state_role_map_sha256 != input_refs["state_role_map"].sha256:
        reasons.append("assessment_spec_state_role_map_checksum_mismatch")

    if evidence_bundle.product_case_ref != product_case.ref.ref:
        reasons.append("evidence_bundle_product_case_ref_mismatch")
    if evidence_bundle.product_case_sha256 != input_refs["product_case"].sha256:
        reasons.append("evidence_bundle_product_case_checksum_mismatch")
    if evidence_bundle.product_definition_ref != product_definition_ref:
        reasons.append("evidence_bundle_product_definition_ref_mismatch")
    if (
        evidence_bundle.product_definition_sha256
        != input_refs["product_definition_card"].sha256
    ):
        reasons.append("evidence_bundle_product_definition_checksum_mismatch")
    if evidence_bundle.cell_state_profile_id != cell_state_profile.profile_id:
        reasons.append("evidence_bundle_cell_state_profile_ref_mismatch")
    if (
        evidence_bundle.cell_state_profile_sha256
        != input_refs["cell_state_evidence_profile"].sha256
    ):
        reasons.append("evidence_bundle_cell_state_profile_checksum_mismatch")
    if (
        evidence_bundle.denominator.denominator_id
        != assessment_spec.primary_denominator_id
    ):
        reasons.append("primary_denominator_binding_mismatch")
    if evidence_bundle.denominator.n_observations != cell_state_profile.n_observations:
        reasons.append("cell_state_denominator_observation_mismatch")

    assignment_ids = {item.state_id for item in role_map.assignments}
    observed_ids = {item.state_id for item in evidence_bundle.state_observations}
    if not observed_ids.issubset(assignment_ids):
        reasons.append("evidence_bundle_contains_unmapped_state")
    allowed_unknown = set(assessment_spec.allowed_unknown_reason_ids)
    observed_unknown = {item.reason_id for item in evidence_bundle.unknown_observations}
    if not observed_unknown.issubset(allowed_unknown):
        reasons.append("unknown_reason_not_allowed")
    rare_rule_ids = {item.state_id for item in assessment_spec.rare_state_rules}
    if not rare_rule_ids.issubset(assignment_ids):
        reasons.append("rare_state_rule_contains_unmapped_state")
    calibration_ids = {
        item.state_id for item in evidence_bundle.rare_state_calibrations
    }
    if not calibration_ids.issubset(rare_rule_ids):
        reasons.append("undeclared_rare_state_calibration")
    if method_mode:
        biological_units = single_object(
            request,
            loaded,
            "biological_unit_manifest",
            BiologicalUnitManifest,
        )
        method_spec = single_object(
            request, loaded, "off_target_method_spec", OffTargetMethodSpec
        )
        method_input = single_object(
            request,
            loaded,
            "off_target_method_input",
            OffTargetMethodInput,
        )
        if not isinstance(cell_state_profile, CellStateEvidenceProfileV3):
            reasons.append("cell_state_evidence_profile_v3_required")
        else:
            reasons.extend(
                method_binding_reasons(
                    input_refs=input_refs,
                    product_case=product_case,
                    cell_state_profile=cell_state_profile,
                    evidence_bundle=evidence_bundle,
                    biological_units=biological_units,
                    method_spec=method_spec,
                    method_input=method_input,
                    role_map=role_map,
                    assessment_spec=assessment_spec,
                )
            )
    return sorted(set(reasons))


def _aggregate_profile(
    *,
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    input_hash: str,
    product_case: ProductCase,
    product_definition: ProductDefinitionCard,
    role_map: StateRoleMap,
    assessment_spec: OffTargetAssessmentSpec,
    cell_state_profile: CellStateEvidenceProfileV2,
    evidence_bundle: OffTargetEvidenceBundle,
) -> OffTargetControlProfile:
    input_refs = {ref.role: ref for ref in request.object_inputs}
    assignments = {item.state_id: item for item in role_map.assignments}
    observations = {item.state_id: item for item in evidence_bundle.state_observations}
    complete = evidence_bundle.composition_coverage_state is CoverageState.COMPLETE
    role_records: list[RoleCompositionRecord] = []
    reason_codes: set[str] = set()
    for role in ProductRole:
        role_states = {
            state_id
            for state_id, assignment in assignments.items()
            if assignment.product_role is role
        }
        soft_mass = math.fsum(
            observation.soft_mass
            for state_id, observation in observations.items()
            if state_id in role_states
        )
        observed_count = sum(
            observation.observed_count
            for state_id, observation in observations.items()
            if state_id in role_states
        )
        if soft_mass == 0.0 and observed_count == 0:
            reason_codes.add("zero_observation_does_not_establish_absence")
        role_records.append(
            RoleCompositionRecord(
                product_role=role,
                soft_mass=float(soft_mass),
                observed_count=observed_count,
                fraction=(
                    float(soft_mass / evidence_bundle.denominator.total_soft_mass)
                    if complete
                    else None
                ),
                assessment_state=(
                    AssessmentState.AVAILABLE
                    if complete
                    else AssessmentState.NOT_ASSESSED
                ),
                exclusion_state=(
                    ExclusionState.OBSERVED
                    if soft_mass > 0.0 or observed_count > 0
                    else ExclusionState.CANNOT_EXCLUDE
                ),
            )
        )
    if not complete:
        reason_codes.add("composition_coverage_not_complete")

    unknown_complete = (
        complete and evidence_bundle.unknown_coverage_state is CoverageState.COMPLETE
    )
    unknown_mass = math.fsum(
        item.soft_mass for item in evidence_bundle.unknown_observations
    )
    unknown_count = sum(
        item.observed_count for item in evidence_bundle.unknown_observations
    )
    if unknown_mass == 0.0 and unknown_count == 0:
        reason_codes.add("zero_unknown_observation_does_not_exclude_unknowns")
    unknown_records = [
        UnknownReasonRecord(
            reason_id=item.reason_id,
            soft_mass=item.soft_mass,
            observed_count=item.observed_count,
            fraction=(
                float(item.soft_mass / evidence_bundle.denominator.total_soft_mass)
                if unknown_complete
                else None
            ),
        )
        for item in sorted(
            evidence_bundle.unknown_observations,
            key=lambda value: value.reason_id,
        )
    ]
    if not unknown_complete:
        reason_codes.add("unknown_coverage_not_complete")
    unknown_profile = UnknownProfile(
        coverage_state=evidence_bundle.unknown_coverage_state,
        soft_mass=float(unknown_mass),
        observed_count=unknown_count,
        fraction=(
            float(unknown_mass / evidence_bundle.denominator.total_soft_mass)
            if unknown_complete
            else None
        ),
        exclusion_state=(
            ExclusionState.OBSERVED
            if unknown_mass > 0.0 or unknown_count > 0
            else ExclusionState.CANNOT_EXCLUDE
        ),
        reasons=unknown_records,
    )

    calibrations = {
        item.state_id: item for item in evidence_bundle.rare_state_calibrations
    }
    rare_records: list[RareStateRecord] = []
    for rule in sorted(
        assessment_spec.rare_state_rules,
        key=lambda value: value.state_id,
    ):
        observation = observations.get(rule.state_id)
        calibration = calibrations.get(rule.state_id)
        if observation is None:
            rare_records.append(
                RareStateRecord(
                    state_id=rule.state_id,
                    observed_count=None,
                    soft_fraction=None,
                    detection_state=RareDetectionState.NOT_ASSESSED,
                    reason_codes=["rare_state_observation_missing"],
                )
            )
            reason_codes.add("rare_state_observation_missing")
            continue
        soft_fraction = (
            float(observation.soft_mass / evidence_bundle.denominator.total_soft_mass)
            if complete
            else None
        )
        if calibration is None:
            state = RareDetectionState(rule.missing_calibration_state)
            rare_records.append(
                RareStateRecord(
                    state_id=rule.state_id,
                    observed_count=observation.observed_count,
                    soft_fraction=soft_fraction,
                    detection_state=state,
                    reason_codes=["rare_state_calibration_missing"],
                )
            )
            reason_codes.add("rare_state_calibration_missing")
            continue
        calibrated = (
            calibration.validated_detection_limit_fraction
            <= rule.max_validated_detection_limit_fraction
            and calibration.false_positive_fraction <= rule.max_false_positive_fraction
        )
        if not calibrated:
            state = RareDetectionState.CANNOT_EXCLUDE
            record_reasons = ["rare_state_calibration_outside_spec"]
            reason_codes.add("rare_state_calibration_outside_spec")
        elif observation.observed_count > 0:
            state = RareDetectionState.DETECTED
            record_reasons = []
        elif not complete:
            state = RareDetectionState.CANNOT_EXCLUDE
            record_reasons = ["rare_state_coverage_not_complete"]
            reason_codes.add("rare_state_coverage_not_complete")
        else:
            state = RareDetectionState.NOT_DETECTED_ABOVE_LOD
            record_reasons = ["zero_observation_does_not_establish_absence"]
            reason_codes.add("zero_observation_does_not_establish_absence")
        rare_records.append(
            RareStateRecord(
                state_id=rule.state_id,
                observed_count=observation.observed_count,
                soft_fraction=soft_fraction,
                detection_state=state,
                calibration_ref=calibration.calibration_ref,
                calibration_sha256=calibration.calibration_sha256,
                validated_detection_limit_fraction=(
                    calibration.validated_detection_limit_fraction
                ),
                false_positive_fraction=calibration.false_positive_fraction,
                zero_observation_upper_bound_fraction=(
                    calibration.zero_observation_upper_bound_fraction
                ),
                reason_codes=record_reasons,
            )
        )

    return OffTargetControlProfile(
        object_version="0.1.0",
        profile_id=f"off-target-control:{input_hash[:24]}",
        profile_version="0.1.0",
        tool_id="P0-05",
        tool_version=spec.version,
        product_case_ref=product_case.ref.ref,
        product_case_sha256=input_refs["product_case"].sha256,
        product_definition_ref=product_definition.ref.ref,
        product_definition_sha256=input_refs["product_definition_card"].sha256,
        state_role_map_ref=role_map.ref.ref,
        state_role_map_sha256=input_refs["state_role_map"].sha256,
        assessment_spec_ref=assessment_spec.ref.ref,
        assessment_spec_sha256=input_refs["off_target_assessment_spec"].sha256,
        cell_state_profile_id=cell_state_profile.profile_id,
        cell_state_profile_sha256=input_refs["cell_state_evidence_profile"].sha256,
        evidence_bundle_ref=evidence_bundle.ref.ref,
        evidence_bundle_sha256=input_refs["off_target_evidence_bundle"].sha256,
        primary_denominator=evidence_bundle.denominator,
        role_composition=role_records,
        unknown_profile=unknown_profile,
        rare_state_profile=rare_records,
        evidence_state="shadow",
        score_state="unavailable",
        domain_score=None,
        reason_codes=sorted(reason_codes),
        created_at=evidence_bundle.created_at,
    )


def _input_hash(request: ToolRequestV2, spec: ToolPackageSpecV2) -> str:
    payload = {
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "environment_spec_id": spec.environment_spec_id,
        "random_seed": (
            request.random_seed if _uses_method_runtime(request.object_inputs) else None
        ),
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


def _failed_v1_request(request: ToolRequest, spec: ToolPackageSpecV2) -> ToolRunV2:
    return _failed_run(request_v2_from_v1(request), spec, ["tool_request_v2_required"])
