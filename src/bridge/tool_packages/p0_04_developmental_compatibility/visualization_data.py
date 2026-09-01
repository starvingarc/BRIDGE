from __future__ import annotations

from collections import defaultdict
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from bridge.tool_packages._configurable_contracts import (
    DevelopmentWindowSpec,
    VersionedObjectRef,
)
from bridge.tool_packages.p0_04_developmental_compatibility.method_models import (
    DevelopmentMethodBundle,
    DevelopmentMethodSpec,
)
from bridge.tool_packages.p0_04_developmental_compatibility.models import (
    DevelopmentFractionProfile,
    DevelopmentalCompatibilityResult,
    InputChecksumBindings,
)
from bridge.tool_packages.p0_04_developmental_compatibility.roles import (
    DevelopmentStageRole,
)
from bridge.toolkit.contracts import (
    CellStateCompositionRecordState,
    CellStateCompositionView,
    CellStateEvidenceProfileV3,
    EvidenceState,
    FrozenModel,
    ReferenceManifest,
)
from bridge.toolkit.visualization import VisualizationArtifactV2


DEVELOPMENTAL_VISUALIZATION_DATA_SCHEMA_REF = (
    "bridge://schemas/developmental-compatibility-visualization-data/v0.1"
)
P004_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF = (
    "bridge://schemas/p0-04-visualization-artifact-set/v0.1"
)
STAGE_COMPONENT_REF = (
    "bridge.developmental-compatibility.window-composition@0.1.0"
)
REFERENCE_COMPONENT_REF = (
    "bridge.developmental-compatibility.reference-stage-summary@0.1.0"
)
TIMEPOINT_COMPONENT_REF = (
    "bridge.developmental-compatibility.observed-sampling-points@0.1.0"
)
DEVELOPMENTAL_COMPONENT_REFS = (
    STAGE_COMPONENT_REF,
    REFERENCE_COMPONENT_REF,
    TIMEPOINT_COMPONENT_REF,
)

_STAGE_LABELS = {
    DevelopmentStageRole.EARLIER: "Earlier than the declared window",
    DevelopmentStageRole.WITHIN_WINDOW: "Within the declared window",
    DevelopmentStageRole.LATER: "Later than the declared window",
    DevelopmentStageRole.BRANCH_SHIFT: "Different developmental branch",
    DevelopmentStageRole.UNRESOLVED: "Not resolved",
}
_ORDERED_ROLES = {
    DevelopmentStageRole.EARLIER,
    DevelopmentStageRole.WITHIN_WINDOW,
    DevelopmentStageRole.LATER,
}


def _sorted_unique(values: list[str], field: str) -> list[str]:
    if values != sorted(set(values)):
        raise ValueError(f"{field} must be sorted and unique")
    return values


class DevelopmentStageCompositionRecord(FrozenModel):
    record_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]+$")
    component_ref: Literal[STAGE_COMPONENT_REF] = STAGE_COMPONENT_REF
    denominator_kind: Literal["whole_product", "target_related"]
    denominator_label: str = Field(min_length=1)
    stage_role: DevelopmentStageRole
    axis_group: Literal["ordered_window_axis", "off_axis"]
    display_name: str = Field(min_length=1)
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    denominator_scope: Literal["evaluated_product", "target_related_subset"]
    unit: Literal["observations"]
    interval_lower: None = None
    interval_upper: None = None
    interval_state: Literal["not_estimable"]
    evidence_ids: list[str] = Field(min_length=1)
    evidence_state: EvidenceState
    scientific_status: Literal["candidate"]
    missingness: Literal["available", "unavailable"]
    applicability: Literal["applicable", "partially_applicable", "not_assessed"]
    reason_codes: list[str] = Field(default_factory=list)

    @field_validator("evidence_ids", "reason_codes")
    @classmethod
    def lists_are_sorted_unique(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)

    @model_validator(mode="after")
    def values_are_coherent(self) -> Self:
        if self.axis_group == "ordered_window_axis" and self.stage_role not in _ORDERED_ROLES:
            raise ValueError("only earlier, within-window and later belong on the ordered axis")
        if self.axis_group == "off_axis" and self.stage_role in _ORDERED_ROLES:
            raise ValueError("ordered stage roles cannot be marked off-axis")
        if self.denominator == 0:
            if self.numerator != 0 or self.fraction is not None:
                raise ValueError("zero denominator requires zero numerator and null fraction")
            if (
                self.evidence_state is not EvidenceState.UNAVAILABLE
                or self.missingness != "unavailable"
                or self.applicability != "not_assessed"
                or not self.reason_codes
            ):
                raise ValueError("zero denominator requires an explicit unavailable state")
        else:
            if self.numerator > self.denominator:
                raise ValueError("stage numerator exceeds denominator")
            if (
                self.fraction is None
                or abs(self.fraction - self.numerator / self.denominator) > 1e-9
            ):
                raise ValueError("stage fraction does not match numerator and denominator")
            if (
                self.evidence_state is not EvidenceState.INFERRED
                or self.missingness != "available"
                or self.applicability not in {"applicable", "partially_applicable"}
            ):
                raise ValueError("available composition must remain inferred and assessable")
        return self


class ReferenceStageSimilarityRecord(FrozenModel):
    record_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]+$")
    component_ref: Literal[REFERENCE_COMPONENT_REF] = REFERENCE_COMPONENT_REF
    analysis_unit_ref: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    assay: str = Field(min_length=1)
    anatomy: str = Field(min_length=1)
    reference_scope: str = Field(min_length=1)
    top_label: str | None = None
    top_stage_role: DevelopmentStageRole | None = None
    top_ordinal_rank: int | None = Field(default=None, ge=0)
    top_spearman_support: float | None = Field(default=None, ge=-1.0, le=1.0)
    top_cosine_support: float | None = Field(default=None, ge=-1.0, le=1.0)
    runner_up_label: str | None = None
    runner_up_stage_role: DevelopmentStageRole | None = None
    runner_up_ordinal_rank: int | None = Field(default=None, ge=0)
    margin: float | None = Field(default=None, ge=0.0, le=2.0)
    shared_genes: int = Field(ge=0)
    output_semantics: Literal["uncalibrated_similarity_not_age_or_probability"]
    evidence_ids: list[str] = Field(min_length=1)
    evidence_state: EvidenceState
    scientific_status: Literal["candidate"]
    missingness: Literal["available", "unavailable"]
    applicability: Literal["applicable", "partially_applicable", "not_assessed"]
    reason_codes: list[str] = Field(default_factory=list)

    @field_validator("evidence_ids", "reason_codes")
    @classmethod
    def lists_are_sorted_unique(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)

    @model_validator(mode="after")
    def support_is_coherent(self) -> Self:
        top_identity = (
            self.top_label,
            self.top_stage_role,
            self.top_ordinal_rank,
        )
        if any(value is None for value in top_identity):
            if any(value is not None for value in top_identity):
                raise ValueError("top-stage identity fields must be supplied together")
            if self.missingness != "unavailable" or self.applicability != "not_assessed":
                raise ValueError("missing top-stage identity must be unavailable")
        elif self.missingness != "available":
            raise ValueError("available top-stage identity must remain visible")
        runner_fields = (
            self.runner_up_label,
            self.runner_up_stage_role,
            self.runner_up_ordinal_rank,
        )
        if any(value is None for value in runner_fields) and any(
            value is not None for value in runner_fields
        ):
            raise ValueError("runner-up stage fields must be supplied together")
        if self.evidence_state is EvidenceState.UNAVAILABLE and not self.reason_codes:
            raise ValueError("unavailable reference evidence requires a reason")
        return self


class RegisteredReferenceStageRecord(FrozenModel):
    record_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]+$")
    profile_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    stage_role: DevelopmentStageRole
    ordinal_rank: int = Field(ge=0)
    evidence_ids: list[str] = Field(min_length=1)

    @field_validator("evidence_ids")
    @classmethod
    def evidence_is_sorted_unique(cls, values: list[str]):
        return _sorted_unique(values, "evidence_ids")


class CellStateResolutionRecord(FrozenModel):
    record_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]+$")
    resolution_state: Literal[
        "supported", "unknown", "ood", "unresolved", "unavailable"
    ]
    display_name: str = Field(min_length=1)
    count: int = Field(ge=0)
    denominator: int = Field(gt=0)
    fraction: float = Field(ge=0.0, le=1.0)
    unit: Literal["observations"]
    evidence_ids: list[str] = Field(min_length=1)

    @field_validator("evidence_ids")
    @classmethod
    def evidence_is_sorted_unique(cls, values: list[str]):
        return _sorted_unique(values, "evidence_ids")

    @model_validator(mode="after")
    def fraction_matches_counts(self) -> Self:
        if self.count > self.denominator:
            raise ValueError("resolution count exceeds denominator")
        if abs(self.fraction - self.count / self.denominator) > 1e-9:
            raise ValueError("resolution fraction does not match counts")
        return self


class ObservedSamplingPointRecord(FrozenModel):
    record_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]+$")
    component_ref: Literal[TIMEPOINT_COMPONENT_REF] = TIMEPOINT_COMPONENT_REF
    timepoint_id: str = Field(min_length=1)
    timepoint_order: int = Field(ge=0)
    timepoint_label: str = Field(min_length=1)
    time_basis: Literal["in_vitro_day", "declared_stage"]
    independence_group_count: int = Field(ge=1)
    denominator_kind: Literal["whole_product", "target_related"]
    denominator_label: str = Field(min_length=1)
    stage_role: DevelopmentStageRole
    axis_group: Literal["ordered_window_axis", "off_axis"]
    display_name: str = Field(min_length=1)
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    denominator_scope: Literal[
        "declared_timepoint_all_observations",
        "declared_timepoint_target_related_subset",
    ]
    unit: Literal["observations"]
    interval_lower: None = None
    interval_upper: None = None
    interval_state: Literal["not_estimable"]
    evidence_ids: list[str] = Field(min_length=1)
    evidence_state: EvidenceState
    scientific_status: Literal["candidate"]
    missingness: Literal["available", "unavailable"]
    applicability: Literal["applicable", "not_assessed"]
    reason_codes: list[str] = Field(default_factory=list)

    @field_validator("evidence_ids", "reason_codes")
    @classmethod
    def lists_are_sorted_unique(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)

    @model_validator(mode="after")
    def values_are_coherent(self) -> Self:
        if self.axis_group == "ordered_window_axis" and self.stage_role not in _ORDERED_ROLES:
            raise ValueError("only ordered stage roles belong on the window axis")
        if self.axis_group == "off_axis" and self.stage_role in _ORDERED_ROLES:
            raise ValueError("off-axis sampling records cannot contain ordered roles")
        if self.denominator == 0:
            if self.numerator != 0 or self.fraction is not None:
                raise ValueError("zero sampling denominator requires a null fraction")
            if self.evidence_state is not EvidenceState.UNAVAILABLE or not self.reason_codes:
                raise ValueError("zero sampling denominator requires unavailable evidence")
        else:
            if self.numerator > self.denominator:
                raise ValueError("sampling numerator exceeds denominator")
            if (
                self.fraction is None
                or abs(self.fraction - self.numerator / self.denominator) > 1e-9
            ):
                raise ValueError("sampling fraction does not match counts")
        return self


class DevelopmentalCompatibilityVisualizationDataV1(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[DEVELOPMENTAL_VISUALIZATION_DATA_SCHEMA_REF] = (
        DEVELOPMENTAL_VISUALIZATION_DATA_SCHEMA_REF
    )
    profile_id: str = Field(
        pattern=r"^developmental-compatibility-visualization-data:[a-f0-9]{16}$"
    )
    producer_run_ref: str = Field(pattern=r"^run:run-[a-f0-9]{16}$")
    producer_tool_version: str = Field(min_length=1)
    product_case_ref: VersionedObjectRef
    product_definition_ref: VersionedObjectRef
    window_spec_ref: VersionedObjectRef
    state_map_ref: VersionedObjectRef
    measurement_spec_ref: VersionedObjectRef
    cell_state_profile_ref: VersionedObjectRef
    timepoint_series_ref: VersionedObjectRef | None = None
    method_spec_ref: VersionedObjectRef | None = None
    method_bundle_ref: VersionedObjectRef | None = None
    method_bundle_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    reference_manifest_ref: VersionedObjectRef | None = None
    input_sha256_by_role: InputChecksumBindings
    window_review_state: Literal["candidate", "confirmed"]
    analysis_mode: Literal["static_profile", "descriptive_timecourse"]
    continuous_time_state: Literal["not_assessed"]
    continuous_time_reason_code: Literal["numeric_time_axis_not_bound"]
    stage_records: list[DevelopmentStageCompositionRecord] = Field(default_factory=list)
    resolution_records: list[CellStateResolutionRecord] = Field(default_factory=list)
    reference_support_state: EvidenceState
    reference_support_applicability: Literal[
        "applicable", "partially_applicable", "not_assessed"
    ]
    reference_support_reason_codes: list[str] = Field(default_factory=list)
    stage_composition_state: EvidenceState
    stage_composition_reason_codes: list[str] = Field(default_factory=list)
    reference_records: list[ReferenceStageSimilarityRecord] = Field(default_factory=list)
    registered_reference_stages: list[RegisteredReferenceStageRecord] = Field(
        default_factory=list
    )
    sampling_point_state: EvidenceState
    sampling_point_reason_codes: list[str] = Field(default_factory=list)
    sampling_point_records: list[ObservedSamplingPointRecord] = Field(default_factory=list)
    evidence_ids: list[str] = Field(min_length=1)

    @field_validator(
        "reference_support_reason_codes",
        "stage_composition_reason_codes",
        "sampling_point_reason_codes",
        "evidence_ids",
    )
    @classmethod
    def lists_are_sorted_unique(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)

    @model_validator(mode="after")
    def records_are_unique_and_conserve_counts(self) -> Self:
        if (self.method_bundle_ref is None) != (self.method_bundle_sha256 is None):
            raise ValueError("method bundle reference and hash must be paired")
        if self.reference_records and self.method_bundle_ref is None:
            raise ValueError("reference records require a method-bundle binding")
        if self.sampling_point_records and self.timepoint_series_ref is None:
            raise ValueError("sampling records require a timepoint-series binding")

        records = [
            *self.stage_records,
            *self.resolution_records,
            *self.reference_records,
            *self.registered_reference_stages,
            *self.sampling_point_records,
        ]
        record_ids = [record.record_id for record in records]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("visualization record IDs must be unique")

        by_denominator: dict[str, list[DevelopmentStageCompositionRecord]] = defaultdict(list)
        for record in self.stage_records:
            by_denominator[record.denominator_kind].append(record)
        for denominator_kind, group in by_denominator.items():
            if {record.stage_role for record in group} != set(DevelopmentStageRole):
                raise ValueError(f"{denominator_kind} must contain every stage role")
            denominators = {record.denominator for record in group}
            if len(denominators) != 1:
                raise ValueError("stage records must share one denominator per view")
            if sum(record.numerator for record in group) != next(iter(denominators)):
                raise ValueError("stage records must conserve the denominator")

        if self.resolution_records:
            states = {record.resolution_state for record in self.resolution_records}
            if states != {"supported", "unknown", "ood", "unresolved", "unavailable"}:
                raise ValueError("resolution records must contain every resolution state")
            denominators = {record.denominator for record in self.resolution_records}
            if len(denominators) != 1:
                raise ValueError("resolution records must share one denominator")
            if sum(record.count for record in self.resolution_records) != next(iter(denominators)):
                raise ValueError("resolution records must conserve the whole-product denominator")

        by_timepoint: dict[tuple[str, str], list[ObservedSamplingPointRecord]] = defaultdict(list)
        for record in self.sampling_point_records:
            by_timepoint[(record.timepoint_id, record.denominator_kind)].append(record)
        for group in by_timepoint.values():
            if {record.stage_role for record in group} != set(DevelopmentStageRole):
                raise ValueError("each sampling-point view must contain every stage role")
            denominators = {record.denominator for record in group}
            if len(denominators) != 1:
                raise ValueError("sampling-point records must share one denominator")
            if sum(record.numerator for record in group) != next(iter(denominators)):
                raise ValueError("sampling-point records must conserve the denominator")
        return self


class P004VisualizationArtifactSet(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[P004_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF] = (
        P004_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF
    )
    artifact_set_id: str = Field(pattern=r"^p0-04-visualizations:[a-f0-9]{16}$")
    data_profile_artifact_id: str = Field(min_length=1)
    data_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    visualizations: list[VisualizationArtifactV2] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def artifact_set_is_exactly_bound(self) -> Self:
        refs = [artifact.component_ref for artifact in self.visualizations]
        if set(refs) != set(DEVELOPMENTAL_COMPONENT_REFS) or len(refs) != len(set(refs)):
            raise ValueError("artifact set must contain each P0-04 component exactly once")
        for artifact in self.visualizations:
            if artifact.data_binding.artifact_id != self.data_profile_artifact_id:
                raise ValueError("visualization must bind the data-profile artifact")
            if artifact.data_binding.sha256 != self.data_profile_sha256:
                raise ValueError("visualization must bind the exact data-profile hash")
        return self


def build_developmental_compatibility_visualization_data(
    *,
    run_id: str,
    tool_version: str,
    result: DevelopmentalCompatibilityResult,
    window_spec: DevelopmentWindowSpec,
    timepoint_series,
    method_spec: DevelopmentMethodSpec | None,
    method_bundle: DevelopmentMethodBundle | None,
    method_bundle_sha256: str | None,
    reference_manifest: ReferenceManifest,
    cell_state_profile: CellStateEvidenceProfileV3,
) -> DevelopmentalCompatibilityVisualizationDataV1:
    evidence_ids = sorted(result.evidence_refs)
    stage_records: list[DevelopmentStageCompositionRecord] = []
    stage_reasons = sorted(
        reason
        for reason in result.reason_codes
        if reason
        in {
            "development_window_not_confirmed",
            "state_mapping_incomplete",
            "composition_residual_unresolved",
            "target_related_denominator_zero",
            "requested_composition_channel_unavailable",
        }
    )
    if result.whole_product_profile is not None:
        stage_records.extend(
            _composition_records(
                result.whole_product_profile,
                evidence_ids,
                window_confirmed=window_spec.review_state == "confirmed",
                stage_reasons=stage_reasons,
            )
        )
        stage_records.extend(
            _composition_records(
                result.target_related_profile,
                evidence_ids,
                window_confirmed=window_spec.review_state == "confirmed",
                stage_reasons=stage_reasons,
            )
        )
    if stage_records:
        stage_state = EvidenceState.INFERRED
    else:
        stage_state = EvidenceState.UNAVAILABLE
        stage_reasons = (
            stage_reasons or ["developmental_stage_composition_unavailable"]
        )

    resolution_records = _resolution_records(
        cell_state_profile=cell_state_profile,
        evidence_ids=evidence_ids,
    )
    registered_reference_stages = _registered_reference_stages(
        method_spec=method_spec,
        evidence_ids=evidence_ids,
    )
    reference_records = _reference_records(
        method_spec=method_spec,
        method_bundle=method_bundle,
        reference_manifest=reference_manifest,
        evidence_ids=evidence_ids,
    )
    reference_state, reference_applicability, reference_reasons = _reference_summary(
        result=result,
        records=reference_records,
    )

    sampling_records = _sampling_records(
        result=result,
        timepoint_series=timepoint_series,
        evidence_ids=evidence_ids,
    )
    if sampling_records:
        sampling_state = EvidenceState.INFERRED
        sampling_reasons = sorted(
            reason
            for reason in result.reason_codes
            if reason.startswith("timepoint_") or reason.startswith("single_timepoint_")
        )
    else:
        sampling_state = EvidenceState.UNAVAILABLE
        sampling_reasons = (
            ["timepoint_series_not_supplied"]
            if timepoint_series is None
            else sorted(
                {
                    reason
                    for reason in result.reason_codes
                    if reason.startswith("timepoint_")
                    or reason.startswith("cell_state_composition_")
                    or reason == "requested_composition_channel_unavailable"
                }
                or {"sampling_point_composition_unavailable"}
            )
        )

    return DevelopmentalCompatibilityVisualizationDataV1(
        profile_id=(
            "developmental-compatibility-visualization-data:"
            f"{run_id.removeprefix('run-')}"
        ),
        producer_run_ref=f"run:{run_id}",
        producer_tool_version=tool_version,
        product_case_ref=result.product_case_ref,
        product_definition_ref=result.product_definition_ref,
        window_spec_ref=result.window_spec_ref,
        state_map_ref=result.state_map_ref,
        measurement_spec_ref=result.measurement_spec_ref,
        cell_state_profile_ref=result.cell_state_profile_ref,
        timepoint_series_ref=result.timepoint_series_ref,
        method_spec_ref=None if method_spec is None else method_spec.ref,
        method_bundle_ref=(
            None
            if method_bundle is None
            else VersionedObjectRef(
                object_id=method_bundle.bundle_id,
                object_version=method_bundle.object_version,
            )
        ),
        method_bundle_sha256=method_bundle_sha256,
        reference_manifest_ref=(
            None
            if method_bundle is None
            else VersionedObjectRef(
                object_id=reference_manifest.snapshot_id,
                object_version=reference_manifest.version,
            )
        ),
        input_sha256_by_role=result.input_sha256_by_role,
        window_review_state=window_spec.review_state,
        analysis_mode=result.analysis_mode,
        continuous_time_state="not_assessed",
        continuous_time_reason_code="numeric_time_axis_not_bound",
        stage_composition_state=stage_state,
        stage_composition_reason_codes=stage_reasons,
        stage_records=stage_records,
        resolution_records=resolution_records,
        reference_support_state=reference_state,
        reference_support_applicability=reference_applicability,
        reference_support_reason_codes=reference_reasons,
        reference_records=reference_records,
        registered_reference_stages=registered_reference_stages,
        sampling_point_state=sampling_state,
        sampling_point_reason_codes=sampling_reasons,
        sampling_point_records=sampling_records,
        evidence_ids=evidence_ids,
    )


def _composition_records(
    profile: DevelopmentFractionProfile,
    evidence_ids: list[str],
    *,
    window_confirmed: bool,
    stage_reasons: list[str],
) -> list[DevelopmentStageCompositionRecord]:
    target_related = profile.denominator_kind == "target_related"
    denominator_label = (
        "Target-related subset" if target_related else "All evaluated observations"
    )
    denominator_scope = (
        "target_related_subset" if target_related else "evaluated_product"
    )
    reason_codes = {
        reason
        for reason in stage_reasons
        if target_related or reason != "target_related_denominator_zero"
    }
    if target_related and profile.denominator == 0:
        reason_codes.add("target_related_denominator_zero")
    reason_codes = sorted(reason_codes)
    records = []
    for item in profile.role_fractions:
        role = DevelopmentStageRole(item.role)
        records.append(
            DevelopmentStageCompositionRecord(
                record_id=f"stage.{profile.denominator_kind}.{role.value}",
                denominator_kind=profile.denominator_kind,
                denominator_label=denominator_label,
                stage_role=role,
                axis_group=(
                    "ordered_window_axis" if role in _ORDERED_ROLES else "off_axis"
                ),
                display_name=_STAGE_LABELS[role],
                numerator=item.numerator,
                denominator=item.denominator,
                fraction=item.fraction,
                denominator_scope=denominator_scope,
                unit="observations",
                interval_state="not_estimable",
                evidence_ids=evidence_ids,
                evidence_state=(
                    EvidenceState.INFERRED
                    if profile.denominator
                    else EvidenceState.UNAVAILABLE
                ),
                scientific_status="candidate",
                missingness="available" if profile.denominator else "unavailable",
                applicability=(
                    ("applicable" if window_confirmed else "partially_applicable")
                    if profile.denominator
                    else "not_assessed"
                ),
                reason_codes=reason_codes,
            )
        )
    return records


def _resolution_records(
    *,
    cell_state_profile: CellStateEvidenceProfileV3,
    evidence_ids: list[str],
) -> list[CellStateResolutionRecord]:
    if cell_state_profile.composition.state != "shadow":
        return []
    records = [
        item
        for item in cell_state_profile.composition.records
        if item.view is CellStateCompositionView.RECONCILIATION_STATE
    ]
    if not records:
        return []
    state_map = {
        CellStateCompositionRecordState.CANDIDATE: "supported",
        CellStateCompositionRecordState.UNKNOWN: "unknown",
        CellStateCompositionRecordState.OOD: "ood",
        CellStateCompositionRecordState.UNRESOLVED: "unresolved",
        CellStateCompositionRecordState.UNAVAILABLE: "unavailable",
    }
    labels = {
        "supported": "Reference-supported",
        "unknown": "Unknown",
        "ood": "Outside reference support",
        "unresolved": "Unresolved",
        "unavailable": "Not assessable",
    }
    denominator = records[0].denominator
    counts = {state: 0 for state in labels}
    for record in records:
        counts[state_map[record.state_evidence_state]] += record.count
    return [
        CellStateResolutionRecord(
            record_id=f"resolution.{state}",
            resolution_state=state,
            display_name=labels[state],
            count=counts[state],
            denominator=denominator,
            fraction=counts[state] / denominator,
            unit="observations",
            evidence_ids=evidence_ids,
        )
        for state in labels
    ]


def _registered_reference_stages(
    *,
    method_spec: DevelopmentMethodSpec | None,
    evidence_ids: list[str],
) -> list[RegisteredReferenceStageRecord]:
    if method_spec is None:
        return []
    return [
        RegisteredReferenceStageRecord(
            record_id=f"registered-stage.{index:04d}",
            profile_id=item.profile_id,
            label=item.label,
            stage_role=item.stage_role,
            ordinal_rank=item.ordinal_rank,
            evidence_ids=evidence_ids,
        )
        for index, item in enumerate(
            sorted(
                method_spec.reference_stages,
                key=lambda row: (row.profile_id, row.ordinal_rank, row.label),
            ),
            start=1,
        )
    ]


def _reference_records(
    *,
    method_spec: DevelopmentMethodSpec | None,
    method_bundle: DevelopmentMethodBundle | None,
    reference_manifest: ReferenceManifest,
    evidence_ids: list[str],
) -> list[ReferenceStageSimilarityRecord]:
    if method_spec is None or method_bundle is None:
        return []
    definitions = {
        (item.profile_id, item.label): item for item in method_spec.reference_stages
    }
    profiles = {item.profile_id: item for item in reference_manifest.profiles}
    records = []
    for index, item in enumerate(
        sorted(
            method_bundle.reference_stage_support,
            key=lambda row: (
                row.profile_source_id, row.profile_assay,
                row.profile_id, row.analysis_unit_ref,
            ),
        ),
        start=1,
    ):
        profile = profiles[item.profile_id]
        runner = (
            None
            if item.runner_up_label is None
            else definitions.get((item.profile_id, item.runner_up_label))
        )
        identity_available = item.top_label is not None
        spearman_available = item.top_spearman_support is not None
        similarity_available = (
            item.top_spearman_support is not None
            or item.top_cosine_support is not None
        )
        reason_codes = set(item.reason_codes)
        if identity_available and not similarity_available:
            reason_codes.add(
                "reference_similarity_metric_unavailable"
            )
        if identity_available and not spearman_available:
            reason_codes.add("reference_spearman_similarity_unavailable")
        evidence_state = (
            EvidenceState.INFERRED
            if item.evidence_state == "shadow"
            else EvidenceState.UNAVAILABLE
        )
        if not identity_available:
            applicability = "not_assessed"
        elif item.evidence_state == "shadow" and spearman_available:
            applicability = "applicable"
        else:
            applicability = "partially_applicable"
        records.append(
            ReferenceStageSimilarityRecord(
                record_id=f"reference.{index:04d}",
                analysis_unit_ref=item.analysis_unit_ref,
                profile_id=item.profile_id,
                source_id=item.profile_source_id,
                assay=item.profile_assay,
                anatomy=profile.anatomy,
                reference_scope=profile.developmental_time,
                top_label=item.top_label,
                top_stage_role=item.top_stage_role,
                top_ordinal_rank=item.top_ordinal_rank,
                top_spearman_support=item.top_spearman_support,
                top_cosine_support=item.top_cosine_support,
                runner_up_label=item.runner_up_label,
                runner_up_stage_role=None if runner is None else runner.stage_role,
                runner_up_ordinal_rank=None if runner is None else runner.ordinal_rank,
                margin=item.margin,
                shared_genes=item.shared_genes,
                output_semantics="uncalibrated_similarity_not_age_or_probability",
                evidence_ids=evidence_ids,
                evidence_state=evidence_state,
                scientific_status="candidate",
                missingness="available" if identity_available else "unavailable",
                applicability=applicability,
                reason_codes=sorted(reason_codes),
            )
        )
    return records


def _reference_summary(
    *,
    result: DevelopmentalCompatibilityResult,
    records: list[ReferenceStageSimilarityRecord],
):
    reasons = {
        *(
            [result.reference_stage_support.reason_code]
            if result.reference_stage_support.reason_code
            else []
        ),
        *(reason for record in records for reason in record.reason_codes),
    }
    if not records or not any(record.missingness == "available" for record in records):
        return EvidenceState.UNAVAILABLE, "not_assessed", sorted(
            reasons or {"reference_stage_support_not_supplied"}
        )
    if all(record.evidence_state is EvidenceState.INFERRED for record in records):
        applicability = (
            "applicable"
            if all(record.applicability == "applicable" for record in records)
            else "partially_applicable"
        )
        return EvidenceState.INFERRED, applicability, sorted(reasons)
    return EvidenceState.UNAVAILABLE, "partially_applicable", sorted(reasons)


def _sampling_records(
    *,
    result: DevelopmentalCompatibilityResult,
    timepoint_series,
    evidence_ids: list[str],
) -> list[ObservedSamplingPointRecord]:
    if timepoint_series is None:
        return []
    records = []
    for timepoint in result.timecourse_profiles:
        for profile in (timepoint.whole_product_profile, timepoint.target_related_profile):
            target_related = profile.denominator_kind == "target_related"
            reason_codes = (
                ["timepoint_target_related_denominator_zero"]
                if target_related and profile.denominator == 0
                else []
            )
            for item in profile.role_fractions:
                role = DevelopmentStageRole(item.role)
                records.append(
                    ObservedSamplingPointRecord(
                        record_id=(
                            f"timepoint.{timepoint.timepoint_order:03d}."
                            f"{profile.denominator_kind}.{role.value}"
                        ),
                        timepoint_id=timepoint.timepoint_id,
                        timepoint_order=timepoint.timepoint_order,
                        timepoint_label=timepoint.timepoint_label,
                        time_basis=timepoint_series.time_basis,
                        independence_group_count=timepoint.independence_group_count,
                        denominator_kind=profile.denominator_kind,
                        denominator_label=(
                            "Target-related subset"
                            if target_related
                            else "All evaluated observations"
                        ),
                        stage_role=role,
                        axis_group=(
                            "ordered_window_axis"
                            if role in _ORDERED_ROLES
                            else "off_axis"
                        ),
                        display_name=_STAGE_LABELS[role],
                        numerator=item.numerator,
                        denominator=item.denominator,
                        fraction=item.fraction,
                        denominator_scope=(
                            "declared_timepoint_target_related_subset"
                            if target_related
                            else "declared_timepoint_all_observations"
                        ),
                        unit="observations",
                        interval_state="not_estimable",
                        evidence_ids=evidence_ids,
                        evidence_state=(
                            EvidenceState.INFERRED
                            if profile.denominator
                            else EvidenceState.UNAVAILABLE
                        ),
                        scientific_status="candidate",
                        missingness=(
                            "available" if profile.denominator else "unavailable"
                        ),
                        applicability=(
                            "applicable" if profile.denominator else "not_assessed"
                        ),
                        reason_codes=reason_codes,
                    )
                )
    return records


PUBLIC_VISUALIZATION_SCHEMA_MODELS = {
    DEVELOPMENTAL_VISUALIZATION_DATA_SCHEMA_REF: DevelopmentalCompatibilityVisualizationDataV1,
    P004_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF: P004VisualizationArtifactSet,
}


__all__ = [
    "DEVELOPMENTAL_COMPONENT_REFS",
    "DEVELOPMENTAL_VISUALIZATION_DATA_SCHEMA_REF",
    "P004_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF",
    "P004VisualizationArtifactSet",
    "REFERENCE_COMPONENT_REF",
    "ReferenceStageSimilarityRecord",
    "RegisteredReferenceStageRecord",
    "STAGE_COMPONENT_REF",
    "TIMEPOINT_COMPONENT_REF",
    "CellStateResolutionRecord",
    "DevelopmentalCompatibilityVisualizationDataV1",
    "build_developmental_compatibility_visualization_data",
]
