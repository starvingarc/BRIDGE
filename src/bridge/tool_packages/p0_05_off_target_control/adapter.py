from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
import shutil
from uuid import uuid4

from bridge.tool_packages._configurable_contracts import (
    ProductCase,
    ProductDefinitionCard,
)
from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    StructuredInputError,
    canonical_json_bytes,
    directory_state,
    failed_v2_run,
    inputs_unchanged,
    load_structured_inputs,
    read_regular_bytes,
    single_object,
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
from bridge.toolkit.contracts import (
    ArtifactManifest,
    CellStateEvidenceProfileV2,
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
}


class PublicationError(ValueError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


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
        if loaded is not None:
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
        cell_state_profile = single_object(
            request,
            loaded,
            "cell_state_evidence_profile",
            CellStateEvidenceProfileV2,
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
        result_sha256 = hashlib.sha256(result_bytes).hexdigest()
        try:
            output_file = _publish_result(
                request=request,
                run_id=run_id,
                payload=result_bytes,
            )
        except PublicationError as exc:
            return _failed_run(
                request,
                spec,
                [exc.reason_code],
                input_hash=input_hash,
            )
        artifact = ArtifactManifest(
            artifact_id=f"artifact:{run_id}:off-target-control",
            kind="off_target_control_profile",
            path=output_file,
            media_type="application/json",
            sha256=result_sha256,
            evidence_ids=sorted(set(cell_state_profile.evidence_ids)),
        )
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
            artifacts=[artifact],
            visualizations=[],
            result_schema_ref=RESULT_SCHEMA_REF,
            result=result.model_dump(mode="json"),
            reason_codes=[],
            warnings=[],
        )


adapter = OffTargetControlAdapter()


def _envelope_reasons(
    request: ToolRequestV2, spec: ToolPackageSpecV2
) -> list[str]:
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
    for role in ROLE_CONTRACTS:
        if roles.count(role) != 1:
            reasons.append(f"exactly_one_{role}_required")
    if any(role not in ROLE_CONTRACTS for role in roles):
        reasons.append("unsupported_object_input_role")
    for ref in request.object_inputs:
        contract = ROLE_CONTRACTS.get(ref.role)
        if contract is None:
            continue
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
    return load_structured_inputs(
        refs,
        model_for=lambda ref: (
            ROLE_CONTRACTS.get(ref.role, ("", "", None))[2]
        ),
        validate_model=_validate_object_version,
    )


def _validate_object_version(
    ref: StructuredInputRef, value: FrozenModel
) -> None:
    expected = ROLE_CONTRACTS[ref.role][1]
    if isinstance(value, CellStateEvidenceProfileV2):
        actual = ref.object_version
    else:
        actual = getattr(value, "object_version", None)
    if actual != expected:
        raise StructuredInputError("object_input_version_mismatch")


def _binding_reasons(
    request: ToolRequestV2, loaded: LoadedInputs
) -> list[str]:
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
    cell_state_profile = single_object(
        request,
        loaded,
        "cell_state_evidence_profile",
        CellStateEvidenceProfileV2,
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
    if (
        assessment_spec.state_role_map_sha256
        != input_refs["state_role_map"].sha256
    ):
        reasons.append("assessment_spec_state_role_map_checksum_mismatch")

    if evidence_bundle.product_case_ref != product_case.ref.ref:
        reasons.append("evidence_bundle_product_case_ref_mismatch")
    if (
        evidence_bundle.product_case_sha256
        != input_refs["product_case"].sha256
    ):
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
    if (
        evidence_bundle.denominator.n_observations
        != cell_state_profile.n_observations
    ):
        reasons.append("cell_state_denominator_observation_mismatch")

    assignment_ids = {item.state_id for item in role_map.assignments}
    observed_ids = {item.state_id for item in evidence_bundle.state_observations}
    if not observed_ids.issubset(assignment_ids):
        reasons.append("evidence_bundle_contains_unmapped_state")
    allowed_unknown = set(assessment_spec.allowed_unknown_reason_ids)
    observed_unknown = {
        item.reason_id for item in evidence_bundle.unknown_observations
    }
    if not observed_unknown.issubset(allowed_unknown):
        reasons.append("unknown_reason_not_allowed")
    rare_rule_ids = {
        item.state_id for item in assessment_spec.rare_state_rules
    }
    if not rare_rule_ids.issubset(assignment_ids):
        reasons.append("rare_state_rule_contains_unmapped_state")
    calibration_ids = {
        item.state_id for item in evidence_bundle.rare_state_calibrations
    }
    if not calibration_ids.issubset(rare_rule_ids):
        reasons.append("undeclared_rare_state_calibration")
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
    observations = {
        item.state_id: item for item in evidence_bundle.state_observations
    }
    complete = (
        evidence_bundle.composition_coverage_state is CoverageState.COMPLETE
    )
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
        complete
        and evidence_bundle.unknown_coverage_state is CoverageState.COMPLETE
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
                float(
                    item.soft_mass
                    / evidence_bundle.denominator.total_soft_mass
                )
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
        item.state_id: item
        for item in evidence_bundle.rare_state_calibrations
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
            float(
                observation.soft_mass
                / evidence_bundle.denominator.total_soft_mass
            )
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
            and calibration.false_positive_fraction
            <= rule.max_false_positive_fraction
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
        assessment_spec_sha256=input_refs[
            "off_target_assessment_spec"
        ].sha256,
        cell_state_profile_id=cell_state_profile.profile_id,
        cell_state_profile_sha256=input_refs[
            "cell_state_evidence_profile"
        ].sha256,
        evidence_bundle_ref=evidence_bundle.ref.ref,
        evidence_bundle_sha256=input_refs[
            "off_target_evidence_bundle"
        ].sha256,
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


def _input_hash(
    request: ToolRequestV2, spec: ToolPackageSpecV2
) -> str:
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
            for ref in sorted(
                request.object_inputs,
                key=lambda item: (item.role, item.input_id),
            )
        ],
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _publish_result(
    *,
    request: ToolRequestV2,
    run_id: str,
    payload: bytes,
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
    filename = "off_target_control_profile.json"
    try:
        staging.mkdir(mode=0o700)
        (staging / filename).write_bytes(payload)
        if not inputs_unchanged(request.object_inputs):
            raise PublicationError("structured_input_modified_during_run")
        final = output_root / run_id
        final_state = directory_state(final)
        if final_state == "directory":
            existing = final / filename
            try:
                matches = (
                    read_regular_bytes(existing) == payload
                    and {path.name for path in final.iterdir()} == {filename}
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
        published = final / filename
        if read_regular_bytes(published) != payload:
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
        fingerprint_input_key="structured_inputs",
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
