from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Literal

from bridge.tool_packages._configurable_contracts import (
    CompositionView,
    ProductCase,
    ProductDefinitionCard,
    RoleFraction,
    UpstreamCompositionRecord,
    VersionedObjectRef,
    parse_composition,
)
from bridge.tool_packages.p0_05_off_target.models import (
    OffTargetCompositionChannel,
    OffTargetControlResult,
    OffTargetRoleSpec,
    OODAssessmentProfile,
    ProductRole,
    RareStateDetectionProfile,
    StateCompositionRecord,
    UnmappedOffTargetState,
)
from bridge.tool_packages.p0_03_target_regional.models import StateRoleMap
from bridge.toolkit.contracts import CellStateEvidenceProfile, QCReadinessProfile, ScoreState


def evaluate_off_target_control(
    *,
    run_id: str,
    tool_version: str,
    product_case: ProductCase,
    product_definition: ProductDefinitionCard,
    state_role_map: StateRoleMap,
    role_spec: OffTargetRoleSpec,
    cell_state_profile: CellStateEvidenceProfile,
    cell_state_profile_version: str,
    qc_profile: QCReadinessProfile,
    qc_profile_version: str,
    input_sha256_by_role: dict[str, str],
) -> OffTargetControlResult:
    records = _selected_records(parse_composition(cell_state_profile), role_spec)
    grouped = _group_records(records)
    assignments = {
        (item.label_level, item.state_id): item for item in role_spec.assignments
    }
    channels: list[OffTargetCompositionChannel] = []
    unmapped: list[UnmappedOffTargetState] = []
    reasons: set[str] = {
        "ood_calibration_not_supplied",
        "rare_state_calibration_not_supplied",
    }

    if _requested_channels_missing(grouped, role_spec):
        reasons.add("requested_full_product_channel_unavailable")

    for (view, source_id, label_level), channel_records in sorted(
        grouped.items(), key=_channel_sort_key
    ):
        denominator, denominator_view = _channel_denominator(channel_records)
        role_counts = {role: 0 for role in ProductRole}
        state_breakdown: list[StateCompositionRecord] = []
        accounted = 0

        for record in sorted(channel_records, key=lambda item: item.label):
            accounted += record.count
            assignment = assignments.get((record.label_level, record.label))
            if assignment is None:
                role_counts[ProductRole.ROLE_UNRESOLVED] += record.count
                unmapped.append(
                    UnmappedOffTargetState(
                        state_id=record.label,
                        label_level=record.label_level,
                        composition_view=view,
                        source_id=record.source_id,
                        count=record.count,
                        denominator=record.denominator,
                        reason_code="product_role_not_configured",
                    )
                )
                state_breakdown.append(
                    StateCompositionRecord(
                        state_id=record.label,
                        product_role=ProductRole.ROLE_UNRESOLVED,
                        count=record.count,
                        denominator=record.denominator,
                    )
                )
                continue
            role_counts[assignment.product_role] += record.count
            state_breakdown.append(
                StateCompositionRecord(
                    state_id=record.label,
                    product_role=assignment.product_role,
                    role_evidence_class=assignment.role_evidence_class,
                    evidence_direction=assignment.evidence_direction,
                    unknown_reason=assignment.unknown_reason,
                    count=record.count,
                    denominator=record.denominator,
                )
            )

        if accounted > denominator:
            raise ValueError("cell_state_composition_channel_overfull")
        if residual := denominator - accounted:
            role_counts[ProductRole.ROLE_UNRESOLVED] += residual
            reasons.add("composition_residual_role_unresolved")

        channels.append(
            OffTargetCompositionChannel(
                composition_view=view,
                source_id=source_id,
                label_level=label_level,
                denominator_view=denominator_view,
                denominator=denominator,
                role_fractions=[
                    _fraction(role, role_counts[role], denominator)
                    for role in ProductRole
                ],
                state_breakdown=state_breakdown,
            )
        )

    if unmapped:
        reasons.add("product_role_mapping_incomplete")
    limiting = reasons - {
        "ood_calibration_not_supplied",
        "rare_state_calibration_not_supplied",
    }
    if not channels:
        reasons.add("off_target_composition_not_assessed")
        result_state = "not_assessed"
    elif limiting:
        result_state = "partial"
    else:
        result_state = "complete"

    return OffTargetControlResult(
        object_version="0.1.0",
        result_id=f"off-target-result:{run_id.removeprefix('run-')}",
        tool_id="P0-05",
        tool_version=tool_version,
        product_case_ref=product_case.ref,
        product_definition_ref=product_definition.ref,
        state_role_map_ref=state_role_map.ref,
        role_spec_ref=role_spec.ref,
        cell_state_profile_ref=VersionedObjectRef(
            object_id=cell_state_profile.profile_id,
            object_version=cell_state_profile_version,
        ),
        qc_profile_ref=VersionedObjectRef(
            object_id=qc_profile.profile_id,
            object_version=qc_profile_version,
        ),
        input_sha256_by_role=input_sha256_by_role,
        result_state=result_state,
        composition_channels=channels,
        unmapped_states=sorted(
            unmapped,
            key=lambda item: (
                item.composition_view,
                item.source_id or "",
                item.label_level,
                item.state_id,
            ),
        ),
        ood_assessment=OODAssessmentProfile(
            assessment_state="not_assessed",
            reason_code="ood_calibration_not_supplied",
        ),
        rare_state_detection=RareStateDetectionProfile(
            assessment_state="not_assessed",
            reason_code="rare_state_calibration_not_supplied",
        ),
        evidence_refs=sorted(
            set(cell_state_profile.evidence_ids) | set(qc_profile.evidence_ids)
        ),
        reason_codes=sorted(reasons),
        domain_score=None,
        score_state=(
            ScoreState.UNAVAILABLE
            if result_state == "not_assessed"
            else ScoreState.SHADOW
        ),
    )


def _selected_records(
    records: Iterable[UpstreamCompositionRecord],
    spec: OffTargetRoleSpec,
) -> list[UpstreamCompositionRecord]:
    views = {view.value for view in spec.composition_views}
    levels = set(spec.included_label_levels)
    sources = set(spec.source_ids)
    return [
        record
        for record in records
        if record.view.value in views
        and record.label_level in levels
        and record.denominator_view == spec.required_denominator_view
        and (
            record.view.value != CompositionView.SOURCE_SPECIFIC.value
            or not sources
            or record.source_id in sources
        )
    ]


def _group_records(
    records: Iterable[UpstreamCompositionRecord],
) -> dict[
    tuple[CompositionView, str | None, Literal["L1", "L2", "L3"]],
    list[UpstreamCompositionRecord],
]:
    grouped: dict[tuple, list[UpstreamCompositionRecord]] = defaultdict(list)
    for record in records:
        grouped[
            (CompositionView(record.view.value), record.source_id, record.label_level)
        ].append(record)
    return dict(grouped)


def _requested_channels_missing(
    grouped: dict[tuple, list[UpstreamCompositionRecord]],
    spec: OffTargetRoleSpec,
) -> bool:
    observed_kinds = {(key[0], key[2]) for key in grouped}
    requested_kinds = {
        (view, level)
        for view in spec.composition_views
        for level in spec.included_label_levels
    }
    if requested_kinds - observed_kinds:
        return True
    requested_sources = {
        (CompositionView.SOURCE_SPECIFIC, source_id, level)
        for source_id in spec.source_ids
        for level in spec.included_label_levels
        if CompositionView.SOURCE_SPECIFIC in spec.composition_views
    }
    return bool(requested_sources - set(grouped))


def _channel_denominator(
    records: list[UpstreamCompositionRecord],
) -> tuple[int, str]:
    denominators = {record.denominator for record in records}
    denominator_views = {record.denominator_view for record in records}
    if len(denominators) != 1 or len(denominator_views) != 1:
        raise ValueError("cell_state_composition_denominator_mismatch")
    return next(iter(denominators)), next(iter(denominator_views))


def _fraction(role: ProductRole, numerator: int, denominator: int) -> RoleFraction:
    return RoleFraction(
        role=role.value,
        numerator=numerator,
        denominator=denominator,
        fraction=numerator / denominator,
    )


def _channel_sort_key(item: tuple) -> tuple[str, str, str]:
    key, _ = item
    return key[0].value, key[1] or "", key[2]
