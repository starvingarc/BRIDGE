from __future__ import annotations

from collections import defaultdict
from enum import StrEnum
from statistics import median
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from bridge.tool_packages._configurable_contracts import (
    CompositionView,
    ProductRole,
    StateRoleMap,
    VersionedObjectRef,
)
from bridge.tool_packages.p0_03_target_regional.method_models import (
    TargetRegionalMethodBundle,
    TargetRegionalMethodId,
)
from bridge.tool_packages.p0_03_target_regional.method_runtime import (
    ReferenceStateSupportValue,
)
from bridge.tool_packages.p0_03_target_regional.models import (
    InputChecksumBindings,
    TargetRegionalAssessmentSpec,
    TargetRegionalEvidenceResult,
)
from bridge.toolkit.contracts import (
    AnnotationVocabulary,
    CellStateCompositionRecordState,
    CellStateCompositionView,
    CellStateEvidenceProfileV3,
    EvidenceState,
    FrozenModel,
    ReferenceManifest,
)
from bridge.toolkit.visualization import VisualizationArtifactV2


TARGET_REGIONAL_VISUALIZATION_DATA_SCHEMA_REF = (
    "bridge://schemas/target-regional-visualization-data/v0.1"
)
P003_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF = (
    "bridge://schemas/p0-03-visualization-artifact-set/v0.1"
)
ROLE_COMPONENT_REF = "bridge.target-regional.product-roles@0.1.0"
REFERENCE_COMPONENT_REF = "bridge.target-regional.reference-fingerprint@0.1.0"
TARGET_REGIONAL_COMPONENT_REFS = (ROLE_COMPONENT_REF, REFERENCE_COMPONENT_REF)


class CompositionCategory(StrEnum):
    TARGET = "target"
    ACCEPTABLE_ADJACENT = "acceptable_adjacent"
    KNOWN_OFF_TARGET = "known_off_target"
    ROLE_UNRESOLVED = "role_unresolved"
    UNKNOWN = "unknown"
    OOD = "ood"
    UNAVAILABLE = "unavailable"


class ProductRoleCompositionRecord(FrozenModel):
    record_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]+$")
    component_ref: Literal[ROLE_COMPONENT_REF] = ROLE_COMPONENT_REF
    channel_id: str = Field(pattern=r"^channel\.[0-9]{2}$")
    composition_view: CompositionView
    source_id: str | None = None
    label_level: Literal["L1", "L2", "L3"]
    category: CompositionCategory
    display_name: str = Field(min_length=1)
    channel_assessment_state: Literal["complete", "partial", "not_assessed"]
    channel_reason_codes: list[str] = Field(default_factory=list)
    count: int | None = Field(default=None, ge=0)
    product_denominator: int = Field(gt=0)
    fraction_of_product: float | None = Field(default=None, ge=0.0, le=1.0)
    denominator_scope: Literal["selected_product_view"]
    unit: Literal["observations"]
    interval_lower: None = None
    interval_upper: None = None
    interval_state: Literal["not_estimable"]
    contributing_state_ids: list[str] = Field(default_factory=list)
    source_labels: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(min_length=1)
    evidence_state: EvidenceState
    scientific_status: Literal["candidate"]
    missingness: Literal["available", "unknown", "unavailable"]
    applicability: Literal["applicable", "partially_applicable", "not_assessed"]
    reason_codes: list[str] = Field(default_factory=list)

    @field_validator(
        "channel_reason_codes",
        "contributing_state_ids",
        "source_labels",
        "evidence_ids",
        "reason_codes",
    )
    @classmethod
    def lists_are_sorted_unique(cls, values: list[str]) -> list[str]:
        if values != sorted(set(values)):
            raise ValueError("visualization record lists must be sorted and unique")
        return values

    @model_validator(mode="after")
    def count_and_fraction_are_coherent(self) -> Self:
        if (self.count is None) != (self.fraction_of_product is None):
            raise ValueError("composition count and fraction must be paired")
        if self.count is not None:
            if self.count > self.product_denominator:
                raise ValueError("composition count exceeds denominator")
            if (
                abs(self.fraction_of_product - self.count / self.product_denominator)
                > 1e-9
            ):
                raise ValueError("composition fraction does not match count")
        elif self.missingness != "unavailable":
            raise ValueError("missing composition values must be unavailable")
        return self


class RegionalStateCompositionRecord(FrozenModel):
    record_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]+$")
    component_ref: Literal[ROLE_COMPONENT_REF] = ROLE_COMPONENT_REF
    channel_id: str = Field(pattern=r"^channel\.[0-9]{2}$")
    composition_view: CompositionView
    source_id: str | None = None
    label_level: Literal["L1", "L2", "L3"]
    state_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    product_role: ProductRole
    is_target_related: bool
    is_target_region: bool
    channel_assessment_state: Literal["complete", "partial", "not_assessed"]
    channel_reason_codes: list[str] = Field(default_factory=list)
    count: int = Field(ge=0)
    product_denominator: int = Field(gt=0)
    fraction_of_product: float = Field(ge=0.0, le=1.0)
    denominator_scope: Literal["selected_product_view"]
    unit: Literal["observations"]
    interval_lower: None = None
    interval_upper: None = None
    interval_state: Literal["not_estimable"]
    target_related_denominator: int | None = Field(default=None, ge=0)
    fraction_of_target_related: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(min_length=1)
    evidence_state: Literal[EvidenceState.INFERRED]
    scientific_status: Literal["candidate"]
    missingness: Literal["available"]
    applicability: Literal["applicable", "partially_applicable"]
    reason_codes: list[str] = Field(default_factory=list)

    @field_validator("channel_reason_codes", "evidence_ids", "reason_codes")
    @classmethod
    def lists_are_sorted_unique(cls, values: list[str]) -> list[str]:
        if values != sorted(set(values)):
            raise ValueError("visualization record lists must be sorted and unique")
        return values

    @model_validator(mode="after")
    def denominators_are_coherent(self) -> Self:
        if abs(self.fraction_of_product - self.count / self.product_denominator) > 1e-9:
            raise ValueError("whole-product state fraction is incoherent")
        if self.fraction_of_target_related is not None:
            if not self.target_related_denominator:
                raise ValueError(
                    "target-related fraction requires a positive denominator"
                )
            if (
                abs(
                    self.fraction_of_target_related
                    - self.count / self.target_related_denominator
                )
                > 1e-9
            ):
                raise ValueError("target-related state fraction is incoherent")
        return self


class ReferenceStateSupportRecord(FrozenModel):
    record_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]+$")
    component_ref: Literal[REFERENCE_COMPONENT_REF] = REFERENCE_COMPONENT_REF
    evidence_scope: Literal["target_identity", "regional_fidelity"]
    profile_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    profile_assay: str = Field(min_length=1)
    anatomy: str = Field(min_length=1)
    developmental_time: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    n_analysis_units: int = Field(ge=0)
    n_available_analysis_units: int = Field(ge=0)
    median_spearman_support: float | None = Field(default=None, ge=-1.0, le=1.0)
    minimum_spearman_support: float | None = Field(default=None, ge=-1.0, le=1.0)
    maximum_spearman_support: float | None = Field(default=None, ge=-1.0, le=1.0)
    shared_genes: int = Field(ge=0)
    range_semantics: Literal["analysis_unit_range_not_confidence_interval"]
    evidence_ids: list[str] = Field(min_length=1)
    evidence_state: EvidenceState
    scientific_status: Literal["candidate"]
    missingness: Literal["available", "unavailable"]
    applicability: Literal["applicable", "partially_applicable", "not_assessed"]
    reason_codes: list[str] = Field(default_factory=list)

    @field_validator("evidence_ids", "reason_codes")
    @classmethod
    def lists_are_sorted_unique(cls, values: list[str]) -> list[str]:
        if values != sorted(set(values)):
            raise ValueError("visualization record lists must be sorted and unique")
        return values

    @model_validator(mode="after")
    def support_summary_is_coherent(self) -> Self:
        values = (
            self.median_spearman_support,
            self.minimum_spearman_support,
            self.maximum_spearman_support,
        )
        available = self.missingness == "available"
        if self.n_available_analysis_units > self.n_analysis_units:
            raise ValueError("available analysis units exceed total analysis units")
        if available != (self.n_available_analysis_units > 0):
            raise ValueError("analysis-unit availability and missingness disagree")
        if available != all(value is not None for value in values):
            raise ValueError("reference support values and availability disagree")
        if available and not (
            self.minimum_spearman_support
            <= self.median_spearman_support
            <= self.maximum_spearman_support
        ):
            raise ValueError("reference support range is incoherent")
        return self


class TargetRegionalVisualizationDataV1(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[TARGET_REGIONAL_VISUALIZATION_DATA_SCHEMA_REF] = (
        TARGET_REGIONAL_VISUALIZATION_DATA_SCHEMA_REF
    )
    profile_id: str = Field(
        pattern=r"^target-regional-visualization-data:[a-f0-9]{16}$"
    )
    producer_run_ref: str = Field(pattern=r"^run:[A-Za-z0-9._:-]+$")
    producer_tool_version: str = Field(min_length=1)
    product_case_ref: VersionedObjectRef
    product_definition_ref: VersionedObjectRef
    state_role_map_ref: VersionedObjectRef
    assessment_spec_ref: VersionedObjectRef
    data_view_id: str = Field(min_length=1)
    assay: Literal["scRNA-seq", "snRNA-seq"]
    n_observations: int = Field(gt=0)
    role_map_review_state: Literal["draft", "reviewed", "frozen"]
    input_sha256_by_role: InputChecksumBindings
    spatial_projection_state: Literal["not_assessed"]
    product_records: list[
        ProductRoleCompositionRecord | RegionalStateCompositionRecord
    ] = Field(min_length=1)
    reference_support_state: EvidenceState
    reference_support_applicability: Literal[
        "applicable", "partially_applicable", "not_assessed"
    ]
    reference_support_reason_codes: list[str] = Field(default_factory=list)
    reference_records: list[ReferenceStateSupportRecord] = Field(default_factory=list)
    evidence_ids: list[str] = Field(min_length=1)

    @field_validator("reference_support_reason_codes", "evidence_ids")
    @classmethod
    def evidence_is_sorted_unique(cls, values: list[str]) -> list[str]:
        if values != sorted(set(values)):
            raise ValueError("evidence IDs must be sorted and unique")
        return values

    @model_validator(mode="after")
    def records_are_unique_and_conservative(self) -> Self:
        records = [
            *self.product_records,
            *self.reference_records,
        ]
        record_ids = [record.record_id for record in records]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("visualization record IDs must be unique")
        by_channel: dict[str, list[ProductRoleCompositionRecord]] = defaultdict(list)
        for record in self.product_records:
            if isinstance(record, ProductRoleCompositionRecord):
                by_channel[record.channel_id].append(record)
        for channel_records in by_channel.values():
            available = [
                record for record in channel_records if record.count is not None
            ]
            unavailable = [record for record in channel_records if record.count is None]
            if unavailable:
                if available:
                    raise ValueError(
                        "unavailable composition channel cannot contain counts"
                    )
                continue
            denominator = {record.product_denominator for record in available}
            if len(denominator) != 1:
                raise ValueError("composition channel must use one denominator")
            if sum(record.count for record in available) != next(iter(denominator)):
                raise ValueError("composition channel must conserve its denominator")
        return self


class P003VisualizationArtifactSet(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[P003_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF] = (
        P003_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF
    )
    artifact_set_id: str = Field(pattern=r"^p0-03-visualizations:[a-f0-9]{16}$")
    data_profile_artifact_id: str = Field(min_length=1)
    data_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    visualizations: list[VisualizationArtifactV2] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def artifact_set_is_exactly_bound(self) -> Self:
        component_refs = [item.component_ref for item in self.visualizations]
        if set(component_refs) != set(TARGET_REGIONAL_COMPONENT_REFS):
            raise ValueError(
                "artifact set must contain both target-regional components"
            )
        if len(component_refs) != len(set(component_refs)):
            raise ValueError("visualization component references must be unique")
        for artifact in self.visualizations:
            if artifact.data_binding.artifact_id != self.data_profile_artifact_id:
                raise ValueError("visualization must bind the data-profile artifact")
            if artifact.data_binding.sha256 != self.data_profile_sha256:
                raise ValueError("visualization must bind the exact data-profile hash")
        return self


_CATEGORY_LABELS = {
    CompositionCategory.TARGET: "Declared target states",
    CompositionCategory.ACCEPTABLE_ADJACENT: "Acceptable adjacent states",
    CompositionCategory.KNOWN_OFF_TARGET: "Known non-target states",
    CompositionCategory.ROLE_UNRESOLVED: "Role or identity unresolved",
    CompositionCategory.UNKNOWN: "Unknown reference correspondence",
    CompositionCategory.OOD: "Outside assessed references",
    CompositionCategory.UNAVAILABLE: "Not assessable",
}
_CATEGORY_ORDER = tuple(CompositionCategory)
_STATE_TO_CATEGORY = {
    CellStateCompositionRecordState.UNKNOWN: CompositionCategory.UNKNOWN,
    CellStateCompositionRecordState.OOD: CompositionCategory.OOD,
    CellStateCompositionRecordState.UNRESOLVED: CompositionCategory.ROLE_UNRESOLVED,
    CellStateCompositionRecordState.UNAVAILABLE: CompositionCategory.UNAVAILABLE,
}


def build_target_regional_visualization_data(
    *,
    run_id: str,
    tool_version: str,
    result: TargetRegionalEvidenceResult,
    cell_state_profile: CellStateEvidenceProfileV3,
    state_role_map: StateRoleMap,
    assessment_spec: TargetRegionalAssessmentSpec,
    annotation_vocabulary: AnnotationVocabulary,
    reference_manifest: ReferenceManifest,
    method_bundle: TargetRegionalMethodBundle | None,
    reference_state_support: tuple[ReferenceStateSupportValue, ...],
) -> TargetRegionalVisualizationDataV1:
    evidence_ids = sorted(result.evidence_refs)
    display_by_state = {
        label.state_id: label.display_name for label in annotation_vocabulary.labels
    }
    role_by_state = {
        assignment.state_id: assignment.product_role
        for assignment in state_role_map.assignments
    }
    composition_records: list[ProductRoleCompositionRecord] = []
    state_records: list[RegionalStateCompositionRecord] = []
    for channel_index, channel in enumerate(result.channels, start=1):
        channel_id = f"channel.{channel_index:02d}"
        selected = _selected_composition_records(cell_state_profile, channel)
        role_rows, states = _channel_records(
            channel_id=channel_id,
            channel=channel,
            selected=selected,
            cell_state_profile=cell_state_profile,
            role_by_state=role_by_state,
            display_by_state=display_by_state,
            assessment_spec=assessment_spec,
            evidence_ids=evidence_ids,
        )
        composition_records.extend(role_rows)
        state_records.extend(states)

    reference_records = _reference_records(
        values=reference_state_support,
        reference_manifest=reference_manifest,
        display_by_state=display_by_state,
        evidence_ids=evidence_ids,
    )
    reference_state, reference_applicability, reference_reasons = _reference_assessment(
        method_bundle=method_bundle,
        records=reference_records,
    )
    return TargetRegionalVisualizationDataV1(
        profile_id=(
            "target-regional-visualization-data:" f"{run_id.removeprefix('run-')}"
        ),
        producer_run_ref=f"run:{run_id}",
        producer_tool_version=tool_version,
        product_case_ref=result.product_case_ref,
        product_definition_ref=result.product_definition_ref,
        state_role_map_ref=result.state_role_map_ref,
        assessment_spec_ref=result.assessment_spec_ref,
        data_view_id=cell_state_profile.input_data_view.view_id,
        assay=cell_state_profile.assay,
        n_observations=cell_state_profile.n_observations,
        role_map_review_state=state_role_map.review_state,
        input_sha256_by_role=result.input_sha256_by_role,
        spatial_projection_state=result.spatial_projection_state,
        product_records=[*composition_records, *state_records],
        reference_support_state=reference_state,
        reference_support_applicability=reference_applicability,
        reference_support_reason_codes=reference_reasons,
        reference_records=reference_records,
        evidence_ids=evidence_ids,
    )


def _selected_composition_records(cell_state_profile, channel):
    return sorted(
        [
            record
            for record in cell_state_profile.composition.records
            if record.view.value == channel.composition_view.value
            and record.source_id == channel.source_id
            and record.label_level == channel.label_level
        ],
        key=lambda record: record.label,
    )


def _channel_records(
    *,
    channel_id,
    channel,
    selected,
    cell_state_profile,
    role_by_state,
    display_by_state,
    assessment_spec,
    evidence_ids,
):
    denominator = cell_state_profile.n_observations
    if cell_state_profile.composition.state != "shadow" or not selected:
        record = ProductRoleCompositionRecord(
            record_id=f"role.{channel_id}.unavailable",
            channel_id=channel_id,
            composition_view=channel.composition_view,
            source_id=channel.source_id,
            label_level=channel.label_level,
            category=CompositionCategory.UNAVAILABLE,
            display_name=_CATEGORY_LABELS[CompositionCategory.UNAVAILABLE],
            channel_assessment_state=channel.assessment_state,
            channel_reason_codes=channel.reason_codes,
            product_denominator=denominator,
            denominator_scope="selected_product_view",
            unit="observations",
            interval_state="not_estimable",
            evidence_ids=evidence_ids,
            evidence_state=EvidenceState.UNAVAILABLE,
            scientific_status="candidate",
            missingness="unavailable",
            applicability="not_assessed",
            reason_codes=["composition_channel_not_available"],
        )
        return [record], []

    counts = {category: 0 for category in _CATEGORY_ORDER}
    states_by_category: dict[CompositionCategory, set[str]] = defaultdict(set)
    labels_by_category: dict[CompositionCategory, set[str]] = defaultdict(set)
    for record in selected:
        role = role_by_state.get(record.label, ProductRole.ROLE_UNRESOLVED)
        category = CompositionCategory(role.value)
        counts[category] += record.count
        states_by_category[category].add(record.label)

    covered = sum(record.count for record in selected)
    if channel.composition_view is CompositionView.CONSENSUS_SUPPORTED_ONLY:
        reconciliation = [
            record
            for record in cell_state_profile.composition.records
            if record.view is CellStateCompositionView.RECONCILIATION_STATE
            and record.label != "consensus_supported"
        ]
        for record in reconciliation:
            category = _STATE_TO_CATEGORY.get(
                record.state_evidence_state, CompositionCategory.ROLE_UNRESOLVED
            )
            counts[category] += record.count
            labels_by_category[category].add(record.label)
    elif covered < denominator:
        counts[CompositionCategory.UNAVAILABLE] += denominator - covered
        labels_by_category[CompositionCategory.UNAVAILABLE].add(
            "source_specific_unresolved_remainder"
        )

    role_records = []
    for category in _CATEGORY_ORDER:
        state = _category_evidence_state(category, counts[category])
        reason_codes = ["independent_unit_composition_not_supplied"]
        if (
            category
            in {
                CompositionCategory.ROLE_UNRESOLVED,
                CompositionCategory.UNKNOWN,
                CompositionCategory.OOD,
                CompositionCategory.UNAVAILABLE,
            }
            and counts[category]
        ):
            reason_codes.append(f"{category.value}_observed")
        role_records.append(
            ProductRoleCompositionRecord(
                record_id=f"role.{channel_id}.{category.value}",
                channel_id=channel_id,
                composition_view=channel.composition_view,
                source_id=channel.source_id,
                label_level=channel.label_level,
                category=category,
                display_name=_CATEGORY_LABELS[category],
                channel_assessment_state=channel.assessment_state,
                channel_reason_codes=channel.reason_codes,
                count=counts[category],
                product_denominator=denominator,
                fraction_of_product=counts[category] / denominator,
                denominator_scope="selected_product_view",
                unit="observations",
                interval_state="not_estimable",
                contributing_state_ids=sorted(states_by_category[category]),
                source_labels=sorted(labels_by_category[category]),
                evidence_ids=evidence_ids,
                evidence_state=state,
                scientific_status="candidate",
                missingness=(
                    "available"
                    if state is EvidenceState.INFERRED
                    else (
                        "unavailable"
                        if state is EvidenceState.UNAVAILABLE
                        else "unknown"
                    )
                ),
                applicability=(
                    "applicable"
                    if state is EvidenceState.INFERRED
                    and channel.assessment_state == "complete"
                    else (
                        "not_assessed"
                        if state is EvidenceState.UNAVAILABLE
                        else "partially_applicable"
                    )
                ),
                reason_codes=sorted(set(reason_codes)),
            )
        )

    target_related_ids = set(assessment_spec.regional_denominator_state_ids)
    target_region_ids = set(assessment_spec.regional_target_numerator_state_ids)
    target_related_denominator = sum(
        record.count for record in selected if record.label in target_related_ids
    )
    formal_regional_available = channel.regional_fidelity_fraction is not None
    state_rows = []
    for index, record in enumerate(selected, start=1):
        role = role_by_state.get(record.label, ProductRole.ROLE_UNRESOLVED)
        target_related = record.label in target_related_ids
        relative = (
            record.count / target_related_denominator
            if target_related
            and target_related_denominator > 0
            and formal_regional_available
            else None
        )
        reasons = []
        if target_related and relative is None:
            reasons.append("formal_regional_channel_not_assessed")
        state_rows.append(
            RegionalStateCompositionRecord(
                record_id=f"state.{channel_id}.{index:03d}",
                channel_id=channel_id,
                composition_view=channel.composition_view,
                source_id=channel.source_id,
                label_level=channel.label_level,
                state_id=record.label,
                display_name=display_by_state.get(record.label, record.label),
                channel_assessment_state=channel.assessment_state,
                channel_reason_codes=channel.reason_codes,
                product_role=role,
                is_target_related=target_related,
                is_target_region=record.label in target_region_ids,
                count=record.count,
                product_denominator=denominator,
                fraction_of_product=record.count / denominator,
                denominator_scope="selected_product_view",
                unit="observations",
                interval_state="not_estimable",
                target_related_denominator=(
                    target_related_denominator if target_related else None
                ),
                fraction_of_target_related=relative,
                evidence_ids=evidence_ids,
                evidence_state=EvidenceState.INFERRED,
                scientific_status="candidate",
                missingness="available",
                applicability=(
                    "applicable"
                    if role is not ProductRole.ROLE_UNRESOLVED
                    and channel.assessment_state == "complete"
                    else "partially_applicable"
                ),
                reason_codes=reasons,
            )
        )
    return role_records, state_rows


def _category_evidence_state(category, count):
    if count == 0:
        return EvidenceState.INFERRED
    if category is CompositionCategory.UNAVAILABLE:
        return EvidenceState.UNAVAILABLE
    if category in {
        CompositionCategory.ROLE_UNRESOLVED,
        CompositionCategory.UNKNOWN,
        CompositionCategory.OOD,
    }:
        return EvidenceState.UNKNOWN
    return EvidenceState.INFERRED


def _reference_records(*, values, reference_manifest, display_by_state, evidence_ids):
    profile_by_id = {
        profile.profile_id: profile for profile in reference_manifest.profiles
    }
    grouped = defaultdict(list)
    for value in values:
        grouped[
            (
                value.evidence_scope,
                value.profile_id,
                value.profile_assay,
                value.state_id,
            )
        ].append(value)
    records = []
    for index, (key, group) in enumerate(sorted(grouped.items()), start=1):
        scope, profile_id, assay, state_id = key
        profile = profile_by_id.get(profile_id)
        available = [
            item
            for item in group
            if item.spearman_support is not None and item.cosine_support is not None
        ]
        spearman = [item.spearman_support for item in available]
        reasons = sorted({reason for item in group for reason in item.reason_codes})
        n_units = len({item.analysis_unit_ref for item in group})
        n_available_units = len({item.analysis_unit_ref for item in available})
        if available and n_available_units < n_units:
            reasons = sorted({*reasons, "reference_support_missing_for_some_units"})
        records.append(
            ReferenceStateSupportRecord(
                record_id=f"reference.{index:04d}",
                evidence_scope=scope,
                profile_id=profile_id,
                source_id=profile.source_id if profile else "not_recorded",
                profile_assay=assay,
                anatomy=profile.anatomy if profile else "not recorded",
                developmental_time=(
                    profile.developmental_time if profile else "not recorded"
                ),
                state_id=state_id,
                display_name=display_by_state.get(state_id, state_id),
                n_analysis_units=n_units,
                n_available_analysis_units=n_available_units,
                median_spearman_support=median(spearman) if spearman else None,
                minimum_spearman_support=min(spearman) if spearman else None,
                maximum_spearman_support=max(spearman) if spearman else None,
                shared_genes=min(item.shared_genes for item in group),
                range_semantics="analysis_unit_range_not_confidence_interval",
                evidence_ids=evidence_ids,
                evidence_state=(
                    EvidenceState.INFERRED if available else EvidenceState.UNAVAILABLE
                ),
                scientific_status="candidate",
                missingness="available" if available else "unavailable",
                applicability=(
                    "applicable"
                    if n_available_units == n_units
                    else "partially_applicable" if available else "not_assessed"
                ),
                reason_codes=reasons
                or ([] if available else ["reference_support_not_available"]),
            )
        )
    return records


def _reference_assessment(
    *,
    method_bundle: TargetRegionalMethodBundle | None,
    records: list[ReferenceStateSupportRecord],
) -> tuple[
    EvidenceState,
    Literal["applicable", "partially_applicable", "not_assessed"],
    list[str],
]:
    if records:
        available = [record for record in records if record.n_available_analysis_units]
        reasons = sorted(
            {reason for record in records for reason in record.reason_codes}
        )
        if available:
            partial = len(available) != len(records) or any(
                record.applicability == "partially_applicable" for record in available
            )
            if partial:
                reasons = sorted({*reasons, "reference_support_missing_for_some_units"})
            return (
                EvidenceState.INFERRED,
                "partially_applicable" if partial else "applicable",
                reasons,
            )
        return (
            EvidenceState.UNAVAILABLE,
            "not_assessed",
            reasons or ["reference_support_not_available"],
        )
    if method_bundle is None:
        return (
            EvidenceState.UNAVAILABLE,
            "not_assessed",
            ["expression_method_bundle_not_supplied"],
        )
    support_method_ids = {
        TargetRegionalMethodId.TARGET_PSEUDOBULK_CORRELATION,
        TargetRegionalMethodId.REGIONAL_PSEUDOBULK_CORRELATION,
        TargetRegionalMethodId.REGIONAL_CROSS_REFERENCE,
        TargetRegionalMethodId.REGIONAL_MODALITY_SENSITIVITY,
    }
    evidence = [
        item
        for item in method_bundle.method_evidence
        if item.method_id in support_method_ids
    ]
    if not evidence:
        reasons = ["reference_support_method_not_selected"]
    else:
        reasons = sorted({reason for item in evidence for reason in item.reason_codes})
        if not reasons:
            reasons = ["reference_state_support_not_available"]
    return EvidenceState.UNAVAILABLE, "not_assessed", reasons


PUBLIC_VISUALIZATION_SCHEMA_MODELS = {
    TARGET_REGIONAL_VISUALIZATION_DATA_SCHEMA_REF: TargetRegionalVisualizationDataV1,
    P003_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF: P003VisualizationArtifactSet,
}
