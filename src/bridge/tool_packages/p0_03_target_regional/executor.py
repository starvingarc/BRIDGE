from __future__ import annotations

from typing import Literal

from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitManifest,
    CompositionView,
    composition_channel_denominator,
    group_composition_records,
    ProductCase,
    requested_composition_channels_missing,
    ProductDefinitionCard,
    RoleFraction,
    UpstreamCompositionRecord,
    VersionedObjectRef,
    parse_composition,
    select_composition_records,
)
from bridge.tool_packages.p0_03_target_regional.models import (
    LineageRole,
    RegionalFidelityChannel,
    RegionalRole,
    SpatialReferenceProjectionProfile,
    StateRoleMap,
    TargetIdentityChannel,
    TargetRegionalAssessmentSpec,
    TargetRegionalEvidenceResult,
    UnmappedStateRecord,
)
from bridge.toolkit.contracts import (
    CellStateEvidenceProfileV2,
    MeasurementSpecV2,
    QCReadinessProfileV2,
    ScoreState,
)

def evaluate_target_regional(
    *,
    run_id: str,
    tool_version: str,
    product_case: ProductCase,
    product_definition: ProductDefinitionCard,
    state_role_map: StateRoleMap,
    assessment_spec: TargetRegionalAssessmentSpec,
    measurement_spec: MeasurementSpecV2,
    cell_state_profile: CellStateEvidenceProfileV2,
    cell_state_profile_version: str,
    qc_profile: QCReadinessProfileV2,
    qc_profile_version: str,
    biological_unit_manifest: BiologicalUnitManifest,
    input_sha256_by_role: dict[str, str],
) -> TargetRegionalEvidenceResult:
    records = parse_composition(cell_state_profile)
    selected = select_composition_records(
        records,
        views=assessment_spec.composition_views,
        label_levels=assessment_spec.included_label_levels,
        source_ids=assessment_spec.source_ids,
    )
    assignments = {
        (item.label_level, item.state_id): item
        for item in state_role_map.assignments
    }
    grouped = group_composition_records(selected)
    target_channels: list[TargetIdentityChannel] = []
    regional_channels: list[RegionalFidelityChannel] = []
    unmapped: list[UnmappedStateRecord] = []
    composition_state = str(cell_state_profile.composition["state"])
    reasons: set[str] = {"spatial_projection_not_supplied"}
    if composition_state != "shadow":
        reasons.add(f"cell_state_composition_{composition_state}")

    if requested_composition_channels_missing(
        grouped,
        views=assessment_spec.composition_views,
        label_levels=assessment_spec.included_label_levels,
        source_ids=assessment_spec.source_ids,
    ):
        reasons.add("requested_composition_channel_unavailable")

    for (view, source_id, label_level), channel_records in sorted(
        grouped.items(), key=_channel_sort_key
    ):
        denominator, denominator_view = composition_channel_denominator(channel_records)
        lineage_counts = {role: 0 for role in LineageRole}
        regional_counts = {role: 0 for role in RegionalRole}
        target_related_denominator = 0
        whole_product_target_region_count = 0
        accounted = 0

        for record in sorted(channel_records, key=lambda item: item.label):
            accounted += record.count
            upstream_unresolved = (
                record.state_evidence_state != "assigned"
                or record.label in cell_state_profile.unresolved_labels
            )
            assignment = assignments.get((record.label_level, record.label))
            if upstream_unresolved or assignment is None:
                reason_code = (
                    "upstream_state_unresolved"
                    if upstream_unresolved
                    else "state_role_not_configured"
                )
                lineage_counts[LineageRole.UNRESOLVED] += record.count
                unmapped.append(
                    UnmappedStateRecord(
                        state_id=record.label,
                        label_level=record.label_level,
                        composition_view=CompositionView(record.view.value),
                        source_id=record.source_id,
                        count=record.count,
                        denominator=record.denominator,
                        reason_code=reason_code,
                    )
                )
                continue

            lineage_counts[assignment.lineage_role] += record.count
            if (
                assignment.lineage_role is LineageRole.UNRESOLVED
                or assignment.regional_role is RegionalRole.UNRESOLVED
            ):
                unmapped.append(
                    UnmappedStateRecord(
                        state_id=record.label,
                        label_level=record.label_level,
                        composition_view=CompositionView(record.view.value),
                        source_id=record.source_id,
                        count=record.count,
                        denominator=record.denominator,
                        reason_code="state_role_explicitly_unresolved",
                    )
                )
            if (
                assignment.lineage_role is not LineageRole.UNRESOLVED
                and assignment.regional_role is not RegionalRole.UNRESOLVED
                and assignment.regional_role
                in assessment_spec.whole_product_target_region_roles
            ):
                whole_product_target_region_count += record.count
            if (
                assignment.lineage_role
                in assessment_spec.regional_denominator_lineage_roles
            ):
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
        measurement_spec_ref=VersionedObjectRef(
            object_id=measurement_spec.measurement_spec_id,
            object_version=measurement_spec.version,
        ),
        cell_state_profile_ref=VersionedObjectRef(
            object_id=cell_state_profile.profile_id,
            object_version=cell_state_profile_version,
        ),
        qc_profile_ref=VersionedObjectRef(
            object_id=qc_profile.profile_id,
            object_version=qc_profile_version,
        ),
        biological_unit_manifest_ref=biological_unit_manifest.ref,
        input_sha256_by_role=input_sha256_by_role,
        upstream_composition_state=composition_state,
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
