from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Literal

from pydantic import ValidationError

from bridge.tool_packages.p0_03_target_regional.models import (
    CompositionView,
    LineageRole,
    ProductCase,
    ProductDefinitionCard,
    RegionalFidelityChannel,
    RegionalRole,
    RoleFraction,
    SpatialReferenceProjectionProfile,
    StateRoleMap,
    TargetIdentityChannel,
    TargetRegionalAssessmentSpec,
    TargetRegionalEvidenceResult,
    UnmappedStateRecord,
    UpstreamCompositionRecord,
    VersionedObjectRef,
)
from bridge.toolkit.contracts import (
    CellStateEvidenceProfile,
    QCReadinessProfile,
    ScoreState,
)


def parse_composition(
    profile: CellStateEvidenceProfile,
) -> list[UpstreamCompositionRecord]:
    raw_records = profile.composition.get("records")
    if raw_records is None:
        return []
    if not isinstance(raw_records, list):
        raise ValueError("cell_state_composition_invalid")
    records: list[UpstreamCompositionRecord] = []
    try:
        records = [UpstreamCompositionRecord.model_validate(item) for item in raw_records]
    except (ValidationError, TypeError, ValueError):
        raise ValueError("cell_state_composition_invalid") from None
    identities = [
        (item.view, item.source_id, item.label_level, item.label)
        for item in records
    ]
    if len(identities) != len(set(identities)):
        raise ValueError("cell_state_composition_duplicate_record")
    return records


def evaluate_target_regional(
    *,
    run_id: str,
    tool_version: str,
    product_case: ProductCase,
    product_definition: ProductDefinitionCard,
    state_role_map: StateRoleMap,
    assessment_spec: TargetRegionalAssessmentSpec,
    cell_state_profile: CellStateEvidenceProfile,
    cell_state_profile_version: str,
    qc_profile: QCReadinessProfile,
    qc_profile_version: str,
    input_sha256_by_role: dict[str, str],
) -> TargetRegionalEvidenceResult:
    records = parse_composition(cell_state_profile)
    selected = _selected_records(records, assessment_spec)
    assignments = {
        (item.label_level, item.state_id): item
        for item in state_role_map.assignments
    }
    grouped = _group_records(selected)
    target_channels: list[TargetIdentityChannel] = []
    regional_channels: list[RegionalFidelityChannel] = []
    unmapped: list[UnmappedStateRecord] = []
    reasons: set[str] = {"spatial_projection_not_supplied"}

    requested_channel_kinds = {
        (view, level)
        for view in assessment_spec.composition_views
        for level in assessment_spec.included_label_levels
    }
    observed_channel_kinds = {(key[0], key[2]) for key in grouped}
    if requested_channel_kinds - observed_channel_kinds:
        reasons.add("requested_composition_channel_unavailable")
    requested_source_channels = {
        (CompositionView.SOURCE_SPECIFIC, source_id, level)
        for source_id in assessment_spec.source_ids
        for level in assessment_spec.included_label_levels
        if CompositionView.SOURCE_SPECIFIC in assessment_spec.composition_views
    }
    if requested_source_channels - set(grouped):
        reasons.add("requested_composition_channel_unavailable")

    for (view, source_id, label_level), channel_records in sorted(
        grouped.items(), key=_channel_sort_key
    ):
        denominator, denominator_view = _channel_denominator(channel_records)
        lineage_counts = {role: 0 for role in LineageRole}
        regional_counts = {role: 0 for role in RegionalRole}
        target_related_denominator = 0
        whole_product_target_region_count = 0
        accounted = 0

        for record in sorted(channel_records, key=lambda item: item.label):
            accounted += record.count
            assignment = assignments.get((record.label_level, record.label))
            if assignment is None:
                lineage_counts[LineageRole.UNRESOLVED] += record.count
                unmapped.append(
                    UnmappedStateRecord(
                        state_id=record.label,
                        label_level=record.label_level,
                        composition_view=CompositionView(record.view.value),
                        source_id=record.source_id,
                        count=record.count,
                        denominator=record.denominator,
                        reason_code="state_role_not_configured",
                    )
                )
                continue
            lineage_counts[assignment.lineage_role] += record.count
            if assignment.regional_role in assessment_spec.whole_product_target_region_roles:
                whole_product_target_region_count += record.count
            if assignment.lineage_role in assessment_spec.regional_denominator_lineage_roles:
                target_related_denominator += record.count
                regional_counts[assignment.regional_role] += record.count

        if accounted > denominator:
            raise ValueError("cell_state_composition_channel_overfull")
        residual = denominator - accounted
        if residual:
            lineage_counts[LineageRole.UNRESOLVED] += residual
            reasons.add("composition_residual_unresolved")

        target_channels.append(
            TargetIdentityChannel(
                composition_view=view,
                source_id=source_id,
                label_level=label_level,
                denominator_view=denominator_view,
                denominator=denominator,
                role_fractions=[
                    _fraction(role.value, lineage_counts[role], denominator)
                    for role in LineageRole
                ],
            )
        )
        regional_channels.append(
            RegionalFidelityChannel(
                composition_view=view,
                source_id=source_id,
                label_level=label_level,
                denominator_view=denominator_view,
                whole_product_denominator=denominator,
                target_related_denominator=target_related_denominator,
                target_related_role_fractions=[
                    _fraction(
                        role.value,
                        regional_counts[role],
                        target_related_denominator,
                    )
                    for role in RegionalRole
                ],
                whole_product_target_region_fraction=_fraction(
                    "configured_target_region",
                    whole_product_target_region_count,
                    denominator,
                ),
            )
        )
        if target_related_denominator == 0:
            reasons.add("target_related_denominator_zero")

    if unmapped:
        reasons.add("state_role_mapping_incomplete")
    if not target_channels:
        reasons.add("cell_state_composition_not_assessed")
        result_state = "not_assessed"
    elif unmapped or len(reasons) > 1:
        result_state = "partial"
    else:
        result_state = "complete"

    evidence_refs = sorted(
        set(cell_state_profile.evidence_ids) | set(qc_profile.evidence_ids)
    )
    return TargetRegionalEvidenceResult(
        object_version="0.1.0",
        result_id=f"target-regional-result:{run_id.removeprefix('run-')}",
        tool_id="P0-03",
        tool_version=tool_version,
        product_case_ref=product_case.ref,
        product_definition_ref=product_definition.ref,
        state_role_map_ref=state_role_map.ref,
        assessment_spec_ref=assessment_spec.ref,
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
        target_identity_channels=target_channels,
        regional_fidelity_channels=regional_channels,
        unmapped_states=sorted(
            unmapped,
            key=lambda item: (
                item.composition_view,
                item.source_id or "",
                item.label_level,
                item.state_id,
            ),
        ),
        spatial_projection=SpatialReferenceProjectionProfile(
            assessment_state="not_assessed",
            reason_code="spatial_projection_not_supplied",
        ),
        evidence_refs=evidence_refs,
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
    spec: TargetRegionalAssessmentSpec,
) -> list[UpstreamCompositionRecord]:
    views = {view.value for view in spec.composition_views}
    levels = set(spec.included_label_levels)
    sources = set(spec.source_ids)
    return [
        record
        for record in records
        if record.view.value in views
        and record.label_level in levels
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


def _channel_denominator(
    records: list[UpstreamCompositionRecord],
) -> tuple[int, str]:
    denominators = {record.denominator for record in records}
    denominator_views = {record.denominator_view for record in records}
    if len(denominators) != 1 or len(denominator_views) != 1:
        raise ValueError("cell_state_composition_denominator_mismatch")
    return next(iter(denominators)), next(iter(denominator_views))


def _fraction(role: str, numerator: int, denominator: int) -> RoleFraction:
    return RoleFraction(
        role=role,
        numerator=numerator,
        denominator=denominator,
        fraction=(numerator / denominator if denominator else None),
    )


def _channel_sort_key(
    item: tuple[
        tuple[CompositionView, str | None, Literal["L1", "L2", "L3"]],
        list[UpstreamCompositionRecord],
    ]
) -> tuple[str, str, str]:
    key, _ = item
    return key[0].value, key[1] or "", key[2]
