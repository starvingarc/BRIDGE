from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from bridge.tool_packages._configurable_contracts import (
    ProductCase,
    ProductDefinitionCard,
    RoleFraction,
    UpstreamCompositionRecord,
    VersionedObjectRef,
    parse_composition,
)
from bridge.tool_packages.p0_04_developmental_compatibility.models import (
    DevelopmentalCompatibilityResult,
    DevelopmentFractionProfile,
    DevelopmentStageRole,
    DevelopmentStateMap,
    DevelopmentTimepointProfile,
    DevelopmentTimepointRecord,
    DevelopmentTimepointSeries,
    DevelopmentWindowSpec,
    InputChecksumBindings,
    ReferenceStageSupport,
)
from bridge.toolkit.contracts import CellStateEvidenceProfileV3, MeasurementSpecV2


ROLE_ORDER = tuple(DevelopmentStageRole)


def evaluate_developmental_compatibility(
    *,
    run_id: str,
    tool_version: str,
    product_case: ProductCase,
    product_definition: ProductDefinitionCard,
    window_spec: DevelopmentWindowSpec,
    state_map: DevelopmentStateMap,
    measurement_spec: MeasurementSpecV2,
    cell_state_profile: CellStateEvidenceProfileV3,
    cell_state_profile_version: str,
    timepoint_series: DevelopmentTimepointSeries | None,
    input_sha256_by_role: dict[str, str],
    method_bundle_ref: VersionedObjectRef | None = None,
    method_bundle_sha256: str | None = None,
    selected_method_ids: list[str] | None = None,
    method_reason_codes: list[str] | None = None,
    reference_stage_support_available: bool = False,
) -> DevelopmentalCompatibilityResult:
    composition_state = cell_state_profile.composition.state
    selected_method_ids = sorted(set(selected_method_ids or []))
    reasons: set[str] = set(method_reason_codes or [])
    if method_bundle_ref is None:
        reasons.add("reference_stage_support_not_supplied")
    whole_profile: DevelopmentFractionProfile | None = None
    target_profile: DevelopmentFractionProfile | None = None

    if composition_state == "shadow":
        selected = _selected_records(parse_composition(cell_state_profile), window_spec)
        if selected:
            whole_profile, target_profile, profile_reasons = _profiles_from_records(
                selected, state_map
            )
            reasons.update(profile_reasons)
        else:
            reasons.add("requested_composition_channel_unavailable")
    else:
        reasons.add(f"cell_state_composition_{composition_state}")

    timecourse_profiles: list[DevelopmentTimepointProfile] = []
    if timepoint_series is not None:
        timecourse_profiles = [
            _timepoint_profile(record, state_map) for record in timepoint_series.records
        ]
        if len(timecourse_profiles) == 1:
            reasons.add("single_timepoint_dynamic_evidence_unavailable")
        if any(item.target_related_profile.denominator == 0 for item in timecourse_profiles):
            reasons.add("timepoint_target_related_denominator_zero")

    analysis_mode = (
        "descriptive_timecourse" if len(timecourse_profiles) >= 2 else "static_profile"
    )
    if timepoint_series is None:
        reasons.add("timepoint_series_not_supplied")
    reasons.add("inferential_timecourse_unavailable")

    if whole_profile is None:
        result_state = "not_assessed"
        compatibility_state = "not_assessed"
        evidence_state = "unavailable"
        timecourse_profiles = []
        analysis_mode = "static_profile"
    else:
        evidence_state = "shadow"
        compatibility_state = (
            "candidate" if window_spec.review_state == "confirmed" else "not_assessed"
        )
        if window_spec.review_state != "confirmed":
            reasons.add("development_window_not_confirmed")
        result_state = (
            "complete"
            if window_spec.review_state == "confirmed"
            and not {
                "state_mapping_incomplete",
                "composition_residual_unresolved",
                "target_related_denominator_zero",
            }.intersection(reasons)
            else "partial"
        )

    return DevelopmentalCompatibilityResult(
        object_version="0.2.0",
        result_id=(
            "developmental-compatibility-result:"
            f"{run_id.removeprefix('run-')}"
        ),
        tool_id="P0-04",
        tool_version=tool_version,
        product_case_ref=product_case.ref,
        product_definition_ref=product_definition.ref,
        window_spec_ref=window_spec.ref,
        state_map_ref=state_map.ref,
        measurement_spec_ref=VersionedObjectRef(
            object_id=measurement_spec.measurement_spec_id,
            object_version=measurement_spec.version,
        ),
        cell_state_profile_ref=VersionedObjectRef(
            object_id=cell_state_profile.profile_id,
            object_version=cell_state_profile_version,
        ),
        timepoint_series_ref=(None if timepoint_series is None else timepoint_series.ref),
        input_sha256_by_role=InputChecksumBindings(
            product_case=input_sha256_by_role["product_case"],
            product_definition_card=input_sha256_by_role["product_definition_card"],
            development_window_spec=input_sha256_by_role["development_window_spec"],
            development_state_map=input_sha256_by_role["development_state_map"],
            measurement_spec=input_sha256_by_role["measurement_spec"],
            cell_state_evidence_profile=input_sha256_by_role[
                "cell_state_evidence_profile"
            ],
            development_timepoint_series=input_sha256_by_role.get(
                "development_timepoint_series"
            ),
            qc_readiness_profile=input_sha256_by_role.get("qc_readiness_profile"),
            biological_unit_manifest=input_sha256_by_role.get(
                "biological_unit_manifest"
            ),
            biological_unit_assignment=input_sha256_by_role.get(
                "biological_unit_assignment"
            ),
            annotation_vocabulary=input_sha256_by_role.get("annotation_vocabulary"),
            reference_manifest=input_sha256_by_role.get("reference_manifest"),
            development_method_spec=input_sha256_by_role.get(
                "development_method_spec"
            ),
        ),
        upstream_composition_state=composition_state,
        result_state=result_state,
        window_compatibility_state=compatibility_state,
        analysis_mode=analysis_mode,
        whole_product_profile=whole_profile,
        target_related_profile=target_profile,
        timecourse_profiles=timecourse_profiles,
        reference_stage_support=(
            ReferenceStageSupport(
                assessment_state="shadow",
                method_bundle_ref=method_bundle_ref,
                method_bundle_sha256=method_bundle_sha256,
                selected_method_ids=selected_method_ids,
            )
            if method_bundle_ref is not None and reference_stage_support_available
            else ReferenceStageSupport(
                assessment_state="unavailable",
                reason_code=(
                    "reference_stage_support_not_supplied"
                    if method_bundle_ref is None
                    else "reference_stage_support_unavailable"
                ),
            )
        ),
        evidence_state=evidence_state,
        evidence_refs=sorted(set(cell_state_profile.evidence_ids)),
        reason_codes=sorted(reasons),
        domain_score=None,
        score_state="unavailable",
    )


def _selected_records(
    records: list[UpstreamCompositionRecord],
    window_spec: DevelopmentWindowSpec,
) -> list[UpstreamCompositionRecord]:
    return [
        record
        for record in records
        if record.view.value == window_spec.composition_view
        and record.source_id == window_spec.source_id
        and record.label_level == window_spec.label_level
    ]


def _profiles_from_records(
    records: list[UpstreamCompositionRecord],
    state_map: DevelopmentStateMap,
) -> tuple[DevelopmentFractionProfile, DevelopmentFractionProfile, set[str]]:
    denominators = {(item.denominator, item.denominator_view) for item in records}
    if len(denominators) != 1:
        raise ValueError("cell_state_composition_channel_denominator_mismatch")
    denominator, denominator_view = next(iter(denominators))
    assignments = {
        (item.label_level, item.state_id): item for item in state_map.assignments
    }
    whole_counts = defaultdict(int)
    target_counts = defaultdict(int)
    accounted = 0
    reasons: set[str] = set()
    for record in records:
        accounted += record.count
        assignment = assignments.get((record.label_level, record.label))
        if assignment is None:
            whole_counts[DevelopmentStageRole.UNRESOLVED] += record.count
            reasons.add("state_mapping_incomplete")
            continue
        whole_counts[assignment.stage_role] += record.count
        if assignment.target_related:
            target_counts[assignment.stage_role] += record.count
    if accounted > denominator:
        raise ValueError("cell_state_composition_channel_overfull")
    if accounted < denominator:
        whole_counts[DevelopmentStageRole.UNRESOLVED] += denominator - accounted
        reasons.add("composition_residual_unresolved")
    target_denominator = sum(target_counts.values())
    if target_denominator == 0:
        reasons.add("target_related_denominator_zero")
    return (
        _fraction_profile("whole_product", denominator_view, denominator, whole_counts),
        _fraction_profile(
            "target_related", denominator_view, target_denominator, target_counts
        ),
        reasons,
    )


def _timepoint_profile(
    record: DevelopmentTimepointRecord,
    state_map: DevelopmentStateMap,
) -> DevelopmentTimepointProfile:
    assignments = {
        (item.label_level, item.state_id): item for item in state_map.assignments
    }
    whole_counts = defaultdict(int)
    target_counts = defaultdict(int)
    accounted = 0
    for item in record.state_counts:
        accounted += item.count
        assignment = assignments.get((item.label_level, item.state_id))
        if assignment is None:
            whole_counts[DevelopmentStageRole.UNRESOLVED] += item.count
            continue
        whole_counts[assignment.stage_role] += item.count
        if assignment.target_related:
            target_counts[assignment.stage_role] += item.count
    whole_counts[DevelopmentStageRole.UNRESOLVED] += record.denominator - accounted
    target_denominator = sum(target_counts.values())
    return DevelopmentTimepointProfile(
        timepoint_id=record.timepoint_id,
        timepoint_order=record.timepoint_order,
        timepoint_label=record.timepoint_label,
        independence_group_count=len(record.independence_group_refs),
        whole_product_profile=_fraction_profile(
            "whole_product", "declared_timepoint_all_cells", record.denominator, whole_counts
        ),
        target_related_profile=_fraction_profile(
            "target_related",
            "declared_timepoint_target_related",
            target_denominator,
            target_counts,
        ),
    )


def _fraction_profile(
    kind: str,
    denominator_view: str,
    denominator: int,
    counts: dict[DevelopmentStageRole, int],
) -> DevelopmentFractionProfile:
    return DevelopmentFractionProfile(
        denominator_kind=kind,
        denominator_view=denominator_view,
        denominator=denominator,
        role_fractions=[
            RoleFraction(
                role=role.value,
                numerator=counts[role],
                denominator=denominator,
                fraction=(counts[role] / denominator if denominator else None),
            )
            for role in ROLE_ORDER
        ],
    )
