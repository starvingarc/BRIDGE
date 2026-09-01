from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from bridge.tool_packages._configurable_contracts import ProductRole, StateRoleMap
from bridge.tool_packages.p0_05_off_target_control.method_models import (
    OODDisagreementRecord,
    OODEnsembleRecord,
    OffTargetMethodBundle,
    OffTargetMethodId,
    OffTargetMethodInput,
    OffTargetMethodSpec,
)
from bridge.tool_packages.p0_05_off_target_control.models import (
    AssessmentState,
    CoverageState,
    ExclusionState,
    OffTargetControlProfile,
    RareDetectionState,
)
from bridge.toolkit.contracts import (
    CellStateEvidenceProfileV2,
    EvidenceState,
    FrozenModel,
)
from bridge.toolkit.visualization import VisualizationArtifactV2


OFF_TARGET_VISUALIZATION_DATA_SCHEMA_REF = (
    "bridge://schemas/off-target-control-visualization-data/v0.1"
)
P005_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF = (
    "bridge://schemas/p0-05-visualization-artifact-set/v0.1"
)
PRODUCT_COMPONENT_REF = "bridge.off-target-control.product-accounting@0.1.0"
RARE_COMPONENT_REF = "bridge.off-target-control.rare-state-detectability@0.1.0"
OOD_COMPONENT_REF = "bridge.off-target-control.ood-source-agreement@0.1.0"
P005_COMPONENT_REFS = (
    PRODUCT_COMPONENT_REF,
    RARE_COMPONENT_REF,
    OOD_COMPONENT_REF,
)

_RECORD_ID = r"^[a-z][a-z0-9_.-]+$"
_SHA256 = r"^[0-9a-f]{64}$"
_ROLE_LABELS = {
    ProductRole.TARGET: "Declared target",
    ProductRole.ACCEPTABLE_ADJACENT: "Acceptable adjacent",
    ProductRole.KNOWN_OFF_TARGET: "Known non-target",
    ProductRole.ROLE_UNRESOLVED: "Role unresolved",
}


def _sorted_unique(values: list[str], field_name: str) -> list[str]:
    if values != sorted(set(values)):
        raise ValueError(f"{field_name} must be sorted and unique")
    return values


def _combined_coverage(*states: CoverageState) -> CoverageState:
    if all(state is CoverageState.COMPLETE for state in states):
        return CoverageState.COMPLETE
    if any(state is CoverageState.NOT_ASSESSED for state in states):
        return CoverageState.NOT_ASSESSED
    return CoverageState.PARTIAL


class ProductAccountingRecord(FrozenModel):
    record_id: str = Field(pattern=_RECORD_ID)
    component_ref: Literal[PRODUCT_COMPONENT_REF] = PRODUCT_COMPONENT_REF
    category: ProductRole | Literal["identity_unknown"]
    display_name: str = Field(min_length=1)
    soft_mass: float = Field(ge=0.0)
    observed_count: int = Field(ge=0)
    fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    denominator_soft_mass: float = Field(gt=0.0)
    denominator_count: int = Field(gt=0)
    denominator_scope: Literal["declared_primary_denominator"]
    unit: Literal["cells"]
    coverage_state: CoverageState
    assessment_state: AssessmentState
    exclusion_state: ExclusionState
    soft_interval_lower: float | None = Field(default=None, ge=0.0, le=1.0)
    soft_interval_upper: float | None = Field(default=None, ge=0.0, le=1.0)
    soft_interval_state: Literal["available", "not_assessed"]
    soft_interval_method_id: Literal["COMP-HBOOT"] | None = None
    soft_interval_semantics: Literal[
        "independence_group_bootstrap_of_soft_assignment_mass"
    ]
    count_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    count_interval_lower: float | None = Field(default=None, ge=0.0, le=1.0)
    count_interval_upper: float | None = Field(default=None, ge=0.0, le=1.0)
    count_interval_state: Literal["available", "not_assessed"]
    count_interval_method_id: Literal["COMP-EXACT"] | None = None
    count_interval_semantics: Literal[
        "selected_capture_cell_count_interval_excludes_annotation_uncertainty"
    ]
    confidence_level: float | None = Field(default=None, gt=0.5, lt=1.0)
    n_independence_groups: int | None = Field(default=None, ge=0)
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
    def quantitative_semantics_are_coherent(self) -> Self:
        expected_assessment = (
            AssessmentState.AVAILABLE
            if self.coverage_state is CoverageState.COMPLETE
            else AssessmentState.NOT_ASSESSED
        )
        if self.assessment_state is not expected_assessment:
            raise ValueError("product assessment state must match coverage state")
        if self.assessment_state is AssessmentState.AVAILABLE:
            expected = self.soft_mass / self.denominator_soft_mass
            if self.fraction is None or not math.isclose(
                self.fraction, expected, rel_tol=0.0, abs_tol=1e-9
            ):
                raise ValueError("available product fraction must match soft mass")
        elif self.fraction is not None:
            raise ValueError("not-assessed product fraction must be null")
        if self.count_fraction is not None:
            expected_count = self.observed_count / self.denominator_count
            if not math.isclose(
                self.count_fraction, expected_count, rel_tol=0.0, abs_tol=1e-9
            ):
                raise ValueError("product count fraction must match count")
        if self.coverage_state is not CoverageState.COMPLETE and any(
            value is not None
            for value in (
                self.fraction,
                self.count_fraction,
                self.soft_interval_lower,
                self.soft_interval_upper,
                self.count_interval_lower,
                self.count_interval_upper,
            )
        ):
            raise ValueError("incomplete coverage cannot expose fractions or intervals")
        self._validate_interval(
            self.soft_interval_state,
            self.soft_interval_lower,
            self.soft_interval_upper,
            self.soft_interval_method_id,
            "soft",
        )
        self._validate_interval(
            self.count_interval_state,
            self.count_interval_lower,
            self.count_interval_upper,
            self.count_interval_method_id,
            "count",
        )
        return self

    @staticmethod
    def _validate_interval(state, lower, upper, method, name) -> None:
        present = (lower is not None, upper is not None, method is not None)
        if state == "available" and not all(present):
            raise ValueError(f"available {name} interval must be fully bound")
        if state == "not_assessed" and any(present):
            raise ValueError(f"not-assessed {name} interval must be null")
        if lower is not None and upper is not None and lower > upper:
            raise ValueError(f"{name} interval lower bound exceeds upper bound")


class UnknownReasonVisualizationRecord(FrozenModel):
    record_id: str = Field(pattern=_RECORD_ID)
    component_ref: Literal[PRODUCT_COMPONENT_REF] = PRODUCT_COMPONENT_REF
    reason_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    parent_category: Literal["identity_unknown"] = "identity_unknown"
    soft_mass: float = Field(ge=0.0)
    observed_count: int = Field(ge=0)
    fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    denominator_soft_mass: float = Field(gt=0.0)
    denominator_count: int = Field(gt=0)
    denominator_scope: Literal["declared_primary_denominator"]
    unit: Literal["cells"]
    coverage_state: CoverageState
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
    def fraction_matches_coverage(self) -> Self:
        if self.coverage_state is CoverageState.COMPLETE:
            expected = self.soft_mass / self.denominator_soft_mass
            if self.fraction is None or not math.isclose(
                self.fraction, expected, rel_tol=0.0, abs_tol=1e-9
            ):
                raise ValueError("unknown-reason fraction must match soft mass")
        elif self.fraction is not None:
            raise ValueError("incomplete unknown coverage requires a null fraction")
        return self


class RareStateDetectabilityRecord(FrozenModel):
    record_id: str = Field(pattern=_RECORD_ID)
    component_ref: Literal[RARE_COMPONENT_REF] = RARE_COMPONENT_REF
    state_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    observed_count: int | None = Field(default=None, ge=0)
    count_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    soft_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    denominator_count: int = Field(gt=0)
    denominator_scope: Literal["declared_primary_denominator"]
    unit: Literal["cells"]
    count_interval_lower: float | None = Field(default=None, ge=0.0, le=1.0)
    count_interval_upper: float | None = Field(default=None, ge=0.0, le=1.0)
    count_interval_confidence_level: float | None = Field(
        default=None, gt=0.5, lt=1.0
    )
    count_interval_n_independence_groups: int | None = Field(default=None, ge=0)
    count_interval_state: Literal["available", "not_assessed"]
    count_interval_semantics: Literal[
        "selected_capture_cell_count_interval_excludes_annotation_uncertainty"
    ]
    detection_state: RareDetectionState
    calibration_ref: str | None = None
    calibration_sha256: str | None = Field(default=None, pattern=_SHA256)
    supplied_validated_detection_limit_fraction: float | None = Field(
        default=None, ge=0.0, le=1.0
    )
    supplied_false_positive_fraction: float | None = Field(
        default=None, ge=0.0, le=1.0
    )
    supplied_zero_observation_upper_bound_fraction: float | None = Field(
        default=None, ge=0.0, le=1.0
    )
    spike_in_candidate_detection_limit_fraction: float | None = Field(
        default=None, ge=0.0, le=1.0
    )
    spike_in_false_positive_fraction: float | None = Field(
        default=None, ge=0.0, le=1.0
    )
    spike_in_assessment_state: Literal["available", "not_assessed"]
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
    def detection_boundaries_are_distinct_and_coherent(self) -> Self:
        interval_values = (
            self.count_interval_lower,
            self.count_interval_upper,
            self.count_interval_confidence_level,
        )
        if self.count_interval_state == "available" and not all(
            value is not None for value in interval_values
        ):
            raise ValueError("available rare-state count interval is incomplete")
        if self.count_interval_state == "not_assessed" and any(
            value is not None for value in interval_values
        ):
            raise ValueError("not-assessed rare-state interval must be null")
        if self.observed_count is None and any(
            value is not None
            for value in (
                self.count_fraction,
                self.soft_fraction,
                self.supplied_zero_observation_upper_bound_fraction,
            )
        ):
            raise ValueError("missing rare-state observation cannot be rendered as zero")
        if self.count_fraction is not None and not math.isclose(
            self.count_fraction,
            self.observed_count / self.denominator_count,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError("rare-state count fraction must match observed count")
        if (
            self.supplied_zero_observation_upper_bound_fraction is not None
            and self.observed_count != 0
        ):
            raise ValueError("zero-observation upper bound requires an observed zero")
        if self.spike_in_assessment_state == "available":
            if self.spike_in_candidate_detection_limit_fraction is None:
                raise ValueError("available spike-in assessment requires a candidate limit")
        elif any(
            value is not None
            for value in (
                self.spike_in_candidate_detection_limit_fraction,
                self.spike_in_false_positive_fraction,
            )
        ):
            raise ValueError("not-assessed spike-in values must be null")
        return self


class SpikeInDetectionPointRecord(FrozenModel):
    record_id: str = Field(pattern=_RECORD_ID)
    component_ref: Literal[RARE_COMPONENT_REF] = RARE_COMPONENT_REF
    state_id: str = Field(min_length=1)
    spike_fraction: float = Field(ge=0.0, le=1.0)
    trial_count: int = Field(gt=0)
    detected_trial_count: int = Field(ge=0)
    independence_group_count: int = Field(gt=0)
    detection_hit_rate: float = Field(ge=0.0, le=1.0)
    detection_lower: float = Field(ge=0.0, le=1.0)
    detection_upper: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(min_length=1)
    evidence_state: Literal[EvidenceState.INFERRED] = EvidenceState.INFERRED
    scientific_status: Literal["candidate"]
    missingness: Literal["available"] = "available"
    applicability: Literal["partially_applicable"] = "partially_applicable"
    reason_codes: list[str] = Field(default_factory=list)

    @field_validator("evidence_ids", "reason_codes")
    @classmethod
    def lists_are_sorted_unique(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)

    @model_validator(mode="after")
    def hit_rate_is_coherent(self) -> Self:
        if self.detected_trial_count > self.trial_count:
            raise ValueError("detected trial count exceeds trial count")
        if not math.isclose(
            self.detection_hit_rate,
            self.detected_trial_count / self.trial_count,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError("detection hit rate does not match trial counts")
        if not self.detection_lower <= self.detection_hit_rate <= self.detection_upper:
            raise ValueError("detection interval must contain the hit rate")
        return self


class OODChannelVisualizationRecord(FrozenModel):
    record_id: str = Field(pattern=_RECORD_ID)
    component_ref: Literal[OOD_COMPONENT_REF] = OOD_COMPONENT_REF
    channel_id: str = Field(min_length=1)
    source_family_id: str = Field(min_length=1)
    channel_state: Literal["supported", "unknown", "ood", "unavailable"]
    reason_id: str | None = None
    method_ref: str = Field(min_length=1)
    reference_ref: str = Field(min_length=1)
    upstream_result_sha256: str = Field(pattern=_SHA256)
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


class OODFamilyVisualizationRecord(FrozenModel):
    record_id: str = Field(pattern=_RECORD_ID)
    component_ref: Literal[OOD_COMPONENT_REF] = OOD_COMPONENT_REF
    source_family_id: str = Field(min_length=1)
    family_state: Literal["supported", "unknown", "ood", "conflict", "unavailable"]
    channel_count: int = Field(gt=0)
    assessed_channel_count: int = Field(ge=0)
    channel_ids: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    evidence_state: EvidenceState
    scientific_status: Literal["candidate"]
    missingness: Literal["available", "unavailable"]
    applicability: Literal["applicable", "partially_applicable", "not_assessed"]
    reason_codes: list[str] = Field(default_factory=list)

    @field_validator("channel_ids", "evidence_ids", "reason_codes")
    @classmethod
    def lists_are_sorted_unique(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)

    @model_validator(mode="after")
    def family_counts_are_coherent(self) -> Self:
        if self.channel_count != len(self.channel_ids):
            raise ValueError("family channel count does not match channel IDs")
        if self.assessed_channel_count > self.channel_count:
            raise ValueError("assessed channel count exceeds channel count")
        if self.family_state == "unavailable" and self.assessed_channel_count:
            raise ValueError("unavailable family cannot contain assessed channels")
        return self


class OffTargetControlVisualizationDataV1(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[OFF_TARGET_VISUALIZATION_DATA_SCHEMA_REF] = (
        OFF_TARGET_VISUALIZATION_DATA_SCHEMA_REF
    )
    profile_id: str = Field(pattern=r"^off-target-visualization:[a-f0-9]{16}$")
    producer_tool_id: Literal["P0-05"] = "P0-05"
    producer_tool_version: str = Field(min_length=1)
    producer_run_ref: str = Field(min_length=1)
    product_case_ref: str = Field(min_length=1)
    product_definition_ref: str = Field(min_length=1)
    state_role_map_ref: str = Field(min_length=1)
    assessment_spec_ref: str = Field(min_length=1)
    cell_state_profile_ref: str = Field(min_length=1)
    evidence_bundle_ref: str = Field(min_length=1)
    input_sha256_by_role: dict[str, str]
    analysis_mode: Literal["legacy_aggregation", "method_runtime"]
    role_map_review_state: Literal["draft", "reviewed", "frozen"]
    denominator_id: str = Field(min_length=1)
    denominator_count: int = Field(gt=0)
    denominator_soft_mass: float = Field(gt=0.0)
    denominator_unit: Literal["cells"]
    composition_coverage_state: CoverageState
    unknown_coverage_state: CoverageState
    method_spec_ref: str | None = None
    method_spec_sha256: str | None = Field(default=None, pattern=_SHA256)
    method_input_ref: str | None = None
    method_input_sha256: str | None = Field(default=None, pattern=_SHA256)
    method_bundle_ref: str | None = None
    method_bundle_sha256: str | None = Field(default=None, pattern=_SHA256)
    product_records: list[ProductAccountingRecord]
    unknown_reason_records: list[UnknownReasonVisualizationRecord]
    rare_state_records: list[RareStateDetectabilityRecord]
    spike_in_detection_records: list[SpikeInDetectionPointRecord]
    ood_channel_records: list[OODChannelVisualizationRecord]
    ood_family_records: list[OODFamilyVisualizationRecord]
    ood_disagreement: OODDisagreementRecord | None = None
    ood_coordination: OODEnsembleRecord | None = None
    product_component_state: EvidenceState
    product_component_applicability: Literal[
        "applicable", "partially_applicable", "not_assessed"
    ]
    product_component_reason_codes: list[str]
    rare_component_state: EvidenceState
    rare_component_applicability: Literal[
        "applicable", "partially_applicable", "not_assessed"
    ]
    rare_component_reason_codes: list[str]
    ood_component_state: EvidenceState
    ood_component_applicability: Literal[
        "applicable", "partially_applicable", "not_assessed"
    ]
    ood_component_reason_codes: list[str]
    evidence_ids: list[str] = Field(min_length=1)

    @field_validator(
        "product_component_reason_codes",
        "rare_component_reason_codes",
        "ood_component_reason_codes",
        "evidence_ids",
    )
    @classmethod
    def lists_are_sorted_unique(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)

    @field_validator("input_sha256_by_role")
    @classmethod
    def input_hashes_are_valid(cls, values: dict[str, str]):
        if not values or any(
            not key or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value)
            for key, value in values.items()
        ):
            raise ValueError("input hashes must be non-empty SHA-256 bindings")
        return dict(sorted(values.items()))

    @model_validator(mode="after")
    def records_and_bindings_are_coherent(self) -> Self:
        method_values = (
            self.method_spec_ref,
            self.method_spec_sha256,
            self.method_input_ref,
            self.method_input_sha256,
            self.method_bundle_ref,
            self.method_bundle_sha256,
        )
        if self.analysis_mode == "method_runtime" and not all(method_values):
            raise ValueError("method runtime requires all method provenance bindings")
        if self.analysis_mode == "legacy_aggregation" and any(method_values):
            raise ValueError("legacy aggregation cannot carry method provenance")

        all_records = [
            *self.product_records,
            *self.unknown_reason_records,
            *self.rare_state_records,
            *self.spike_in_detection_records,
            *self.ood_channel_records,
            *self.ood_family_records,
        ]
        record_ids = [record.record_id for record in all_records]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("visualization record IDs must be unique")

        categories = {
            item.category.value if isinstance(item.category, ProductRole) else item.category
            for item in self.product_records
        }
        expected = {role.value for role in ProductRole} | {"identity_unknown"}
        if categories != expected or len(self.product_records) != len(expected):
            raise ValueError("product accounting must contain four roles and identity unknown")
        unknown = next(
            item for item in self.product_records if item.category == "identity_unknown"
        )
        identity_coverage = _combined_coverage(
            self.composition_coverage_state, self.unknown_coverage_state
        )
        for item in self.product_records:
            expected_coverage = (
                identity_coverage
                if item.category == "identity_unknown"
                else self.composition_coverage_state
            )
            if item.coverage_state is not expected_coverage:
                raise ValueError("product row coverage does not match top-level coverage")
            if item.denominator_count != self.denominator_count or not math.isclose(
                item.denominator_soft_mass,
                self.denominator_soft_mass,
                rel_tol=0.0,
                abs_tol=max(1e-9, self.denominator_soft_mass * 1e-9),
            ):
                raise ValueError("product row denominator does not match profile denominator")
        for item in self.unknown_reason_records:
            if item.coverage_state is not identity_coverage:
                raise ValueError("unknown-reason coverage does not match identity coverage")
            if item.denominator_count != self.denominator_count or not math.isclose(
                item.denominator_soft_mass,
                self.denominator_soft_mass,
                rel_tol=0.0,
                abs_tol=max(1e-9, self.denominator_soft_mass * 1e-9),
            ):
                raise ValueError("unknown-reason denominator does not match profile denominator")
        for item in self.rare_state_records:
            if item.denominator_count != self.denominator_count:
                raise ValueError("rare-state denominator does not match profile denominator")
            if self.composition_coverage_state is not CoverageState.COMPLETE and (
                item.count_fraction is not None
                or item.soft_fraction is not None
                or item.count_interval_state != "not_assessed"
                or any(
                    value is not None
                    for value in (
                        item.count_interval_lower,
                        item.count_interval_upper,
                        item.count_interval_confidence_level,
                    )
                )
            ):
                raise ValueError(
                    "incomplete composition coverage cannot expose rare-state fractions or intervals"
                )
        if not math.isclose(
            sum(item.soft_mass for item in self.unknown_reason_records),
            unknown.soft_mass,
            rel_tol=0.0,
            abs_tol=max(1e-9, self.denominator_soft_mass * 1e-9),
        ) or sum(item.observed_count for item in self.unknown_reason_records) != unknown.observed_count:
            raise ValueError("unknown reasons must close to the identity-unknown total")
        if self.composition_coverage_state is CoverageState.COMPLETE:
            if not math.isclose(
                sum(item.soft_mass for item in self.product_records),
                self.denominator_soft_mass,
                rel_tol=0.0,
                abs_tol=max(1e-9, self.denominator_soft_mass * 1e-9),
            ) or sum(item.observed_count for item in self.product_records) != self.denominator_count:
                raise ValueError("complete product records must close to the denominator")

        available_product_fractions = sum(
            item.fraction is not None for item in self.product_records
        )
        expected_product_applicability = (
            "applicable"
            if available_product_fractions == len(self.product_records)
            else "partially_applicable"
            if available_product_fractions
            else "not_assessed"
        )
        expected_product_state = (
            EvidenceState.INFERRED
            if expected_product_applicability == "applicable"
            else EvidenceState.UNKNOWN
            if expected_product_applicability == "partially_applicable"
            else EvidenceState.UNAVAILABLE
        )
        if self.product_component_applicability != expected_product_applicability:
            raise ValueError("product component applicability does not match fractions")
        if self.product_component_state is not expected_product_state:
            raise ValueError("product component evidence state does not match fractions")

        curve_keys = [
            (item.state_id, item.spike_fraction)
            for item in self.spike_in_detection_records
        ]
        if len(curve_keys) != len(set(curve_keys)):
            raise ValueError("spike-in state/fraction records must be unique")
        rare_state_ids = {item.state_id for item in self.rare_state_records}
        if any(
            item.state_id not in rare_state_ids
            for item in self.spike_in_detection_records
        ):
            raise ValueError("spike-in curve state must have a rare-state row")
        channel_ids = [item.channel_id for item in self.ood_channel_records]
        if len(channel_ids) != len(set(channel_ids)):
            raise ValueError("OOD channel IDs must be unique")
        family_ids = [item.source_family_id for item in self.ood_family_records]
        if len(family_ids) != len(set(family_ids)):
            raise ValueError("OOD source-family IDs must be unique")
        channels = {item.channel_id: item for item in self.ood_channel_records}
        family_channels = {
            channel_id
            for item in self.ood_family_records
            for channel_id in item.channel_ids
        }
        if family_channels != set(channels):
            raise ValueError("OOD family rows must partition the channel rows")
        for family in self.ood_family_records:
            members = sorted(
                (
                    item
                    for item in self.ood_channel_records
                    if item.source_family_id == family.source_family_id
                ),
                key=lambda item: item.channel_id,
            )
            expected_ids = [item.channel_id for item in members]
            if family.channel_ids != expected_ids:
                raise ValueError("OOD family membership does not match channel rows")
            assessed_states = [
                item.channel_state
                for item in members
                if item.channel_state != "unavailable"
            ]
            if family.assessed_channel_count != len(assessed_states):
                raise ValueError("OOD family assessed count does not match channel rows")
            distinct_states = set(assessed_states)
            expected_state = (
                "unavailable"
                if not assessed_states
                else next(iter(distinct_states))
                if len(distinct_states) == 1
                else "conflict"
            )
            if family.family_state != expected_state:
                raise ValueError("OOD family state does not match channel rows")
            expected_applicability = (
                "not_assessed"
                if not assessed_states
                else "partially_applicable"
                if expected_state == "conflict" or len(assessed_states) < len(members)
                else "applicable"
            )
            if family.applicability != expected_applicability:
                raise ValueError("OOD family applicability does not match channel rows")
        assessed_family_states = {
            item.source_family_id: item.family_state
            for item in self.ood_family_records
            if item.family_state != "unavailable"
        }
        assessed_channel_count = sum(
            item.channel_state != "unavailable" for item in self.ood_channel_records
        )
        if self.ood_disagreement is not None:
            disagreement = self.ood_disagreement
            if disagreement.assessed_channel_count != assessed_channel_count:
                raise ValueError("OOD disagreement channel count does not match rows")
            if disagreement.distinct_source_family_count != len(assessed_family_states):
                raise ValueError("OOD disagreement family count does not match rows")
            if disagreement.family_states != assessed_family_states:
                raise ValueError("OOD disagreement family states do not match rows")
            expected_disagreement = (
                None
                if len(assessed_family_states) < 2
                else "conflict" in assessed_family_states.values()
                or len(set(assessed_family_states.values())) > 1
            )
            expected_assessment = (
                "available" if expected_disagreement is not None else "not_assessed"
            )
            if (
                disagreement.disagreement is not expected_disagreement
                or disagreement.assessment_state != expected_assessment
            ):
                raise ValueError("OOD disagreement summary does not match family rows")
        if self.ood_coordination is not None:
            coordination = self.ood_coordination
            has_conflict = "conflict" in assessed_family_states.values()
            expected_votes = (
                Counter()
                if has_conflict
                else Counter(assessed_family_states.values())
            )
            expected_count = (
                len(assessed_family_states)
                if has_conflict
                else sum(expected_votes.values())
            )
            if (
                coordination.distinct_source_family_count
                not in {len(assessed_family_states), expected_count}
                or coordination.family_vote_counts != dict(sorted(expected_votes.items()))
            ):
                raise ValueError("OOD coordination summary does not match family rows")
            if has_conflict and (
                coordination.assessment_state != "not_assessed"
                or coordination.decision_state.value != "not_assessed"
            ):
                raise ValueError("OOD conflict cannot produce an assessed coordination")
        return self


class P005VisualizationArtifactSet(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[P005_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF] = (
        P005_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF
    )
    artifact_set_id: str = Field(pattern=r"^p0-05-visualizations:[a-f0-9]{16}$")
    data_profile_artifact_id: str = Field(min_length=1)
    data_profile_sha256: str = Field(pattern=_SHA256)
    visualizations: list[VisualizationArtifactV2] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def artifact_set_is_exactly_bound(self) -> Self:
        component_refs = [item.component_ref for item in self.visualizations]
        if set(component_refs) != set(P005_COMPONENT_REFS):
            raise ValueError("artifact set must contain all P0-05 components")
        if len(component_refs) != len(set(component_refs)):
            raise ValueError("visualization component references must be unique")
        for artifact in self.visualizations:
            if artifact.data_binding.artifact_id != self.data_profile_artifact_id:
                raise ValueError("visualization must bind the data-profile artifact")
            if artifact.data_binding.sha256 != self.data_profile_sha256:
                raise ValueError("visualization must bind the exact data-profile hash")
        return self


def build_off_target_control_visualization_data(
    *,
    run_id: str,
    tool_version: str,
    result: OffTargetControlProfile,
    composition_coverage_state: CoverageState,
    role_map: StateRoleMap,
    cell_state_profile: CellStateEvidenceProfileV2,
    input_sha256_by_role: dict[str, str],
    method_spec: OffTargetMethodSpec | None,
    method_input: OffTargetMethodInput | None,
    method_bundle: OffTargetMethodBundle | None,
    method_bundle_sha256: str | None,
) -> OffTargetControlVisualizationDataV1:
    evidence_ids = sorted(set(cell_state_profile.evidence_ids))
    composition_coverage = composition_coverage_state
    complete = composition_coverage is CoverageState.COMPLETE
    identity_coverage = _combined_coverage(
        composition_coverage, result.unknown_profile.coverage_state
    )
    intervals = {
        (item.method_id, item.scope_id): item
        for item in (method_bundle.composition_intervals if method_bundle else [])
    }
    product_records = []
    for index, item in enumerate(result.role_composition, start=1):
        soft_interval = intervals.get(
            (OffTargetMethodId.HIERARCHICAL_BOOTSTRAP, f"product-role:{item.product_role.value}")
        )
        count_interval = intervals.get(
            (OffTargetMethodId.COMPOSITION_EXACT, f"product-role:{item.product_role.value}")
        )
        product_records.append(
            _product_record(
                record_id=f"product.{index:02d}",
                category=item.product_role,
                display_name=_ROLE_LABELS[item.product_role],
                soft_mass=item.soft_mass,
                observed_count=item.observed_count,
                fraction=item.fraction,
                assessment_state=item.assessment_state,
                exclusion_state=item.exclusion_state,
                coverage_state=composition_coverage,
                denominator_count=result.primary_denominator.n_observations,
                denominator_soft_mass=result.primary_denominator.total_soft_mass,
                soft_interval=soft_interval,
                count_interval=count_interval,
                evidence_ids=evidence_ids,
            )
        )
    product_records.append(
        _product_record(
            record_id="product.05",
            category="identity_unknown",
            display_name="Identity unknown",
            soft_mass=result.unknown_profile.soft_mass,
            observed_count=result.unknown_profile.observed_count,
            fraction=result.unknown_profile.fraction,
            assessment_state=(
                AssessmentState.AVAILABLE
                if identity_coverage is CoverageState.COMPLETE
                else AssessmentState.NOT_ASSESSED
            ),
            exclusion_state=result.unknown_profile.exclusion_state,
            coverage_state=identity_coverage,
            denominator_count=result.primary_denominator.n_observations,
            denominator_soft_mass=result.primary_denominator.total_soft_mass,
            soft_interval=None,
            count_interval=None,
            evidence_ids=evidence_ids,
            extra_reasons=["unknown_interval_not_computed"],
        )
    )
    unknown_reason_records = [
        UnknownReasonVisualizationRecord(
            record_id=f"unknown.{index:02d}",
            reason_id=item.reason_id,
            display_name=item.reason_id.replace("_", " ").replace("-", " ").capitalize(),
            soft_mass=item.soft_mass,
            observed_count=item.observed_count,
            fraction=item.fraction,
            denominator_soft_mass=result.primary_denominator.total_soft_mass,
            denominator_count=result.primary_denominator.n_observations,
            denominator_scope="declared_primary_denominator",
            unit="cells",
            coverage_state=identity_coverage,
            evidence_ids=evidence_ids,
            evidence_state=(
                EvidenceState.INFERRED
                if item.fraction is not None
                else EvidenceState.UNAVAILABLE
            ),
            scientific_status="candidate",
            missingness="available" if item.fraction is not None else "unavailable",
            applicability="applicable" if item.fraction is not None else "not_assessed",
            reason_codes=(
                []
                if item.fraction is not None
                else ["identity_unknown_coverage_not_complete"]
            ),
        )
        for index, item in enumerate(result.unknown_profile.reasons, start=1)
    ]
    rare_intervals = {
        item.scope_id: item
        for item in (method_bundle.rare_intervals if method_bundle else [])
        if item.method_id is OffTargetMethodId.RARE_EXACT
    }
    spike_by_state = {
        item.state_id: item
        for item in (method_bundle.spike_in_calibrations if method_bundle else [])
    }
    rare_state_records = []
    spike_records = []
    for index, item in enumerate(result.rare_state_profile, start=1):
        interval = rare_intervals.get(item.state_id)
        spike = spike_by_state.get(item.state_id)
        interval_available = interval is not None and interval.assessment_state == "available"
        spike_available = spike is not None and spike.assessment_state == "available"
        reasons = set(item.reason_codes)
        if interval is not None:
            reasons.update(interval.reason_codes)
        if spike is not None:
            reasons.update(spike.reason_codes)
        if interval is None:
            reasons.add("rare_count_interval_not_assessed")
        if spike is None:
            reasons.add("spike_in_detection_not_assessed")
        rare_state_records.append(
            RareStateDetectabilityRecord(
                record_id=f"rare.{index:02d}",
                state_id=item.state_id,
                display_name=item.state_id,
                observed_count=item.observed_count,
                count_fraction=(
                    item.observed_count / result.primary_denominator.n_observations
                    if complete and item.observed_count is not None
                    else None
                ),
                soft_fraction=item.soft_fraction,
                denominator_count=result.primary_denominator.n_observations,
                denominator_scope="declared_primary_denominator",
                unit="cells",
                count_interval_lower=interval.lower if interval_available else None,
                count_interval_upper=interval.upper if interval_available else None,
                count_interval_confidence_level=(
                    interval.confidence_level if interval_available else None
                ),
                count_interval_n_independence_groups=(
                    interval.n_independence_groups if interval else None
                ),
                count_interval_state=(
                    "available" if interval_available else "not_assessed"
                ),
                count_interval_semantics=(
                    "selected_capture_cell_count_interval_excludes_annotation_uncertainty"
                ),
                detection_state=item.detection_state,
                calibration_ref=item.calibration_ref,
                calibration_sha256=item.calibration_sha256,
                supplied_validated_detection_limit_fraction=(
                    item.validated_detection_limit_fraction
                ),
                supplied_false_positive_fraction=item.false_positive_fraction,
                supplied_zero_observation_upper_bound_fraction=(
                    item.zero_observation_upper_bound_fraction
                    if item.detection_state
                    is RareDetectionState.NOT_DETECTED_ABOVE_LOD
                    else None
                ),
                spike_in_candidate_detection_limit_fraction=(
                    spike.candidate_detection_limit_fraction
                    if spike_available
                    else None
                ),
                spike_in_false_positive_fraction=(
                    spike.false_positive_fraction if spike_available else None
                ),
                spike_in_assessment_state=(
                    "available" if spike_available else "not_assessed"
                ),
                evidence_ids=evidence_ids,
                evidence_state=(
                    EvidenceState.INFERRED
                    if item.observed_count is not None
                    else EvidenceState.UNAVAILABLE
                ),
                scientific_status="candidate",
                missingness=(
                    "available" if item.observed_count is not None else "unavailable"
                ),
                applicability=(
                    "applicable"
                    if item.detection_state
                    in {
                        RareDetectionState.DETECTED,
                        RareDetectionState.NOT_DETECTED_ABOVE_LOD,
                    }
                    else (
                        "partially_applicable"
                        if item.observed_count is not None
                        else "not_assessed"
                    )
                ),
                reason_codes=sorted(reasons),
            )
        )
        if spike is not None:
            spike_records.extend(
                SpikeInDetectionPointRecord(
                    record_id=f"spike.{index:02d}.{point_index:02d}",
                    state_id=item.state_id,
                    spike_fraction=point.spike_fraction,
                    trial_count=point.trial_count,
                    detected_trial_count=point.detected_trial_count,
                    independence_group_count=point.independence_group_count,
                    detection_hit_rate=point.detection_rate,
                    detection_lower=point.detection_lower,
                    detection_upper=point.detection_upper,
                    evidence_ids=evidence_ids,
                    scientific_status="candidate",
                )
                for point_index, point in enumerate(
                    sorted(spike.curve, key=lambda value: value.spike_fraction),
                    start=1,
                )
            )

    ood_channels, ood_families = _ood_records(
        method_spec=method_spec,
        method_input=method_input,
        method_bundle=method_bundle,
        evidence_ids=evidence_ids,
    )
    product_reasons = {
        reason
        for item in [*product_records, *unknown_reason_records]
        for reason in item.reason_codes
    }
    product_fraction_count = sum(
        item.fraction is not None for item in product_records
    )
    product_complete = product_fraction_count == len(product_records)
    product_component_state = (
        EvidenceState.INFERRED
        if product_complete
        else EvidenceState.UNKNOWN
        if product_fraction_count
        else EvidenceState.UNAVAILABLE
    )
    product_applicability = (
        "applicable"
        if product_complete
        else "partially_applicable"
        if product_fraction_count
        else "not_assessed"
    )
    rare_reasons = {
        reason
        for item in rare_state_records
        for reason in item.reason_codes
    }
    if not rare_state_records:
        rare_reasons.add("rare_state_rules_not_supplied")
    ood_selected = bool(
        method_spec
        and set(method_spec.selected_method_ids).intersection(
            {OffTargetMethodId.OOD_DISAGREEMENT, OffTargetMethodId.OOD_ENSEMBLE}
        )
    )
    ood_reasons = set()
    if not ood_selected:
        ood_reasons.add("ood_methods_not_assessed")
    if method_bundle and method_bundle.ood_disagreement:
        ood_reasons.update(method_bundle.ood_disagreement.reason_codes)
    if method_bundle and method_bundle.ood_ensemble:
        ood_reasons.update(method_bundle.ood_ensemble.reason_codes)
    for family in ood_families:
        ood_reasons.update(family.reason_codes)
    rare_assessed = [
        item for item in rare_state_records if item.applicability != "not_assessed"
    ]
    ood_assessed = [
        item for item in ood_channels if item.channel_state != "unavailable"
    ]
    ood_conflict = any(item.family_state == "conflict" for item in ood_families)
    if ood_channels and not ood_assessed:
        ood_reasons.add("ood_channels_unavailable")
    elif len(ood_assessed) < len(ood_channels):
        ood_reasons.add("ood_channels_partially_available")
    if ood_conflict:
        ood_reasons.add("ood_source_family_conflict")

    return OffTargetControlVisualizationDataV1(
        profile_id=f"off-target-visualization:{run_id.removeprefix('run-')}",
        producer_tool_version=tool_version,
        producer_run_ref=f"run:{run_id}",
        product_case_ref=result.product_case_ref,
        product_definition_ref=result.product_definition_ref,
        state_role_map_ref=result.state_role_map_ref,
        assessment_spec_ref=result.assessment_spec_ref,
        cell_state_profile_ref=result.cell_state_profile_id,
        evidence_bundle_ref=result.evidence_bundle_ref,
        input_sha256_by_role=input_sha256_by_role,
        analysis_mode=(
            "method_runtime" if method_spec is not None else "legacy_aggregation"
        ),
        role_map_review_state=role_map.review_state,
        denominator_id=result.primary_denominator.denominator_id,
        denominator_count=result.primary_denominator.n_observations,
        denominator_soft_mass=result.primary_denominator.total_soft_mass,
        denominator_unit=result.primary_denominator.unit,
        composition_coverage_state=composition_coverage,
        unknown_coverage_state=result.unknown_profile.coverage_state,
        method_spec_ref=(
            f"{method_spec.method_spec_id}@{method_spec.method_spec_version}"
            if method_spec
            else None
        ),
        method_spec_sha256=(
            input_sha256_by_role.get("off_target_method_spec") if method_spec else None
        ),
        method_input_ref=(
            f"{method_input.method_input_id}@{method_input.method_input_version}"
            if method_input
            else None
        ),
        method_input_sha256=(
            input_sha256_by_role.get("off_target_method_input") if method_input else None
        ),
        method_bundle_ref=(method_bundle.bundle_id if method_bundle else None),
        method_bundle_sha256=method_bundle_sha256,
        product_records=product_records,
        unknown_reason_records=unknown_reason_records,
        rare_state_records=rare_state_records,
        spike_in_detection_records=spike_records,
        ood_channel_records=ood_channels,
        ood_family_records=ood_families,
        ood_disagreement=method_bundle.ood_disagreement if method_bundle else None,
        ood_coordination=method_bundle.ood_ensemble if method_bundle else None,
        product_component_state=product_component_state,
        product_component_applicability=product_applicability,
        product_component_reason_codes=sorted(product_reasons),
        rare_component_state=(
            EvidenceState.INFERRED if rare_assessed else EvidenceState.UNAVAILABLE
        ),
        rare_component_applicability=(
            "applicable"
            if rare_assessed
            and len(rare_assessed) == len(rare_state_records)
            and all(item.applicability == "applicable" for item in rare_state_records)
            else ("partially_applicable" if rare_assessed else "not_assessed")
        ),
        rare_component_reason_codes=sorted(rare_reasons),
        ood_component_state=(
            EvidenceState.UNKNOWN
            if ood_conflict
            else EvidenceState.INFERRED
            if ood_assessed
            else EvidenceState.UNAVAILABLE
        ),
        ood_component_applicability=(
            "applicable"
            if ood_assessed
            and len(ood_assessed) == len(ood_channels)
            and not ood_conflict
            else ("partially_applicable" if ood_assessed else "not_assessed")
        ),
        ood_component_reason_codes=sorted(ood_reasons),
        evidence_ids=evidence_ids,
    )


def _product_record(
    *,
    record_id,
    category,
    display_name,
    soft_mass,
    observed_count,
    fraction,
    assessment_state,
    exclusion_state,
    coverage_state,
    denominator_count,
    denominator_soft_mass,
    soft_interval,
    count_interval,
    evidence_ids,
    extra_reasons=(),
):
    soft_available = soft_interval is not None and soft_interval.assessment_state == "available"
    count_available = count_interval is not None and count_interval.assessment_state == "available"
    reasons = set(extra_reasons)
    if soft_interval is not None:
        reasons.update(soft_interval.reason_codes)
    else:
        reasons.add("soft_assignment_interval_not_assessed")
    if count_interval is not None:
        reasons.update(count_interval.reason_codes)
    else:
        reasons.add("cell_count_interval_not_assessed")
    if assessment_state is AssessmentState.NOT_ASSESSED:
        reasons.add(
            "identity_unknown_coverage_not_complete"
            if category == "identity_unknown"
            else "composition_coverage_not_complete"
        )
    return ProductAccountingRecord(
        record_id=record_id,
        category=category,
        display_name=display_name,
        soft_mass=soft_mass,
        observed_count=observed_count,
        fraction=fraction,
        denominator_soft_mass=denominator_soft_mass,
        denominator_count=denominator_count,
        denominator_scope="declared_primary_denominator",
        unit="cells",
        coverage_state=coverage_state,
        assessment_state=assessment_state,
        exclusion_state=exclusion_state,
        soft_interval_lower=soft_interval.lower if soft_available else None,
        soft_interval_upper=soft_interval.upper if soft_available else None,
        soft_interval_state="available" if soft_available else "not_assessed",
        soft_interval_method_id="COMP-HBOOT" if soft_available else None,
        soft_interval_semantics="independence_group_bootstrap_of_soft_assignment_mass",
        count_fraction=count_interval.estimate if count_available else None,
        count_interval_lower=count_interval.lower if count_available else None,
        count_interval_upper=count_interval.upper if count_available else None,
        count_interval_state="available" if count_available else "not_assessed",
        count_interval_method_id="COMP-EXACT" if count_available else None,
        count_interval_semantics=(
            "selected_capture_cell_count_interval_excludes_annotation_uncertainty"
        ),
        confidence_level=(
            soft_interval.confidence_level
            if soft_available
            else count_interval.confidence_level if count_available else None
        ),
        n_independence_groups=(
            soft_interval.n_independence_groups
            if soft_interval is not None
            else count_interval.n_independence_groups if count_interval is not None else None
        ),
        evidence_ids=evidence_ids,
        evidence_state=(
            EvidenceState.INFERRED
            if assessment_state is AssessmentState.AVAILABLE
            else EvidenceState.UNAVAILABLE
        ),
        scientific_status="candidate",
        missingness=(
            "available"
            if assessment_state is AssessmentState.AVAILABLE
            else "unavailable"
        ),
        applicability=(
            "applicable"
            if assessment_state is AssessmentState.AVAILABLE
            else "not_assessed"
        ),
        reason_codes=sorted(reasons),
    )


def _ood_records(*, method_spec, method_input, method_bundle, evidence_ids):
    selected = bool(
        method_spec
        and set(method_spec.selected_method_ids).intersection(
            {OffTargetMethodId.OOD_DISAGREEMENT, OffTargetMethodId.OOD_ENSEMBLE}
        )
    )
    if not selected or method_input is None or method_bundle is None:
        return [], []
    bindings = {item.channel_id: item for item in method_spec.ood_channel_bindings}
    states = {item.channel_id: item for item in method_input.ood_channels}
    if set(bindings) != set(states):
        raise ValueError("OOD visualization requires an exact channel-binding join")
    records = []
    for index, channel_id in enumerate(sorted(bindings), start=1):
        binding = bindings[channel_id]
        state = states[channel_id]
        unavailable = state.state.value == "unavailable"
        records.append(
            OODChannelVisualizationRecord(
                record_id=f"ood-channel.{index:02d}",
                channel_id=channel_id,
                source_family_id=binding.source_family_id,
                channel_state=state.state.value,
                reason_id=state.reason_id,
                method_ref=binding.method_ref,
                reference_ref=binding.reference_ref,
                upstream_result_sha256=binding.upstream_result_sha256,
                evidence_ids=evidence_ids,
                evidence_state=(
                    EvidenceState.UNAVAILABLE if unavailable else EvidenceState.INFERRED
                ),
                scientific_status="candidate",
                missingness="unavailable" if unavailable else "available",
                applicability="not_assessed" if unavailable else "applicable",
                reason_codes=(
                    [state.reason_id]
                    if state.reason_id is not None
                    else (["ood_channel_unavailable"] if unavailable else [])
                ),
            )
        )
    by_family = defaultdict(list)
    for record in records:
        by_family[record.source_family_id].append(record)
    families = []
    for index, family_id in enumerate(sorted(by_family), start=1):
        group = by_family[family_id]
        assessed = [item.channel_state for item in group if item.channel_state != "unavailable"]
        states_seen = set(assessed)
        if not assessed:
            family_state = "unavailable"
        elif len(states_seen) == 1:
            family_state = next(iter(states_seen))
        else:
            family_state = "conflict"
        conflict = family_state == "conflict"
        unavailable = family_state == "unavailable"
        partial = bool(assessed) and len(assessed) < len(group)
        families.append(
            OODFamilyVisualizationRecord(
                record_id=f"ood-family.{index:02d}",
                source_family_id=family_id,
                family_state=family_state,
                channel_count=len(group),
                assessed_channel_count=len(assessed),
                channel_ids=sorted(item.channel_id for item in group),
                evidence_ids=evidence_ids,
                evidence_state=(
                    EvidenceState.UNKNOWN
                    if conflict
                    else EvidenceState.UNAVAILABLE
                    if unavailable
                    else EvidenceState.INFERRED
                ),
                scientific_status="candidate",
                missingness="unavailable" if unavailable else "available",
                applicability=(
                    "not_assessed"
                    if unavailable
                    else "partially_applicable"
                    if conflict or partial
                    else "applicable"
                ),
                reason_codes=(
                    ["within_declared_source_family_state_conflict"]
                    if conflict
                    else ["ood_source_family_unavailable"]
                    if unavailable
                    else ["ood_source_family_partially_assessed"]
                    if partial
                    else []
                ),
            )
        )
    return records, families


PUBLIC_VISUALIZATION_SCHEMA_MODELS = {
    OFF_TARGET_VISUALIZATION_DATA_SCHEMA_REF: OffTargetControlVisualizationDataV1,
    P005_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF: P005VisualizationArtifactSet,
}
