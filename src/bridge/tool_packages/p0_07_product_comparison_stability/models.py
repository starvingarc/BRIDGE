from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
import math
from typing import Literal, Self

from pydantic import Field, StrictFloat, StrictInt, field_validator, model_validator

from bridge.tool_packages._configurable_contracts import (
    OBJECT_ID_PATTERN,
    ProductCase,
    ProductDefinitionCard,
    SHA256_PATTERN,
    VERSION_PATTERN,
    VersionedObjectRef,
)
from bridge.tool_packages._publication_safety import validate_publication_text
from bridge.toolkit.contracts import FrozenModel


Numeric = StrictInt | StrictFloat


def _unique(values: list[object], field: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must contain unique values")


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include a timezone")
    return value.astimezone(timezone.utc)


def _finite(value: Numeric | None, field: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{field} must be finite")


class ComparisonField(StrEnum):
    PRODUCT_DEFINITION = "product_definition"
    TARGET_STAGE = "target_stage"
    ASSAY = "assay"
    DATA_VIEW = "data_view"
    TIMEPOINT = "timepoint"
    REFERENCE = "reference"
    PREPROCESSING = "preprocessing"
    ALGORITHM = "algorithm"


class ConfoundingFactor(StrEnum):
    PROTOCOL = "protocol"
    LAB = "lab"
    BATCH = "batch"
    CELL_LINE = "cell_line"


class ComparisonGroupRole(StrEnum):
    BASELINE = "baseline"
    COMPARATOR = "comparator"
    REFERENCE_OOD = "reference_ood"


class MetricEvidenceState(StrEnum):
    SHADOW = "shadow"
    MEASURED = "measured"
    INFERRED = "inferred"
    NEGATIVE = "negative"
    MISSING = "missing"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    ALERT = "alert"


class MetricContract(FrozenModel):
    metric_id: str = Field(pattern=OBJECT_ID_PATTERN)
    measurement_spec_ref: VersionedObjectRef
    unit: str = Field(min_length=1)
    denominator_kind: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    required: bool = True

    _unit_is_safe = field_validator("unit")(validate_publication_text)


class ComparisonStabilitySpec(FrozenModel):
    object_version: Literal["0.1.0"]
    spec_id: str = Field(pattern=r"^comparison-stability-spec:[A-Za-z0-9._:-]+$")
    spec_version: str = Field(pattern=VERSION_PATTERN)
    comparison_ref: VersionedObjectRef
    status: Literal["candidate", "frozen"]
    analysis_mode: Literal["descriptive_only"]
    required_equal_fields: list[ComparisonField]
    contextual_fields: list[ComparisonField]
    contextual_mismatch_policy: Literal["contextual_comparator", "not_comparable"]
    confounding_factors: list[ConfoundingFactor]
    metric_contracts: list[MetricContract] = Field(min_length=1)
    created_at: datetime

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @field_validator(
        "required_equal_fields", "contextual_fields", "confounding_factors"
    )
    @classmethod
    def configured_lists_are_unique(cls, value: list[object]) -> list[object]:
        _unique(value, "configured list")
        return value

    @field_validator("metric_contracts")
    @classmethod
    def metric_contracts_are_unique(
        cls, value: list[MetricContract]
    ) -> list[MetricContract]:
        _unique([item.metric_id for item in value], "metric IDs")
        return value

    @model_validator(mode="after")
    def field_policies_are_disjoint(self) -> Self:
        if set(self.required_equal_fields).intersection(self.contextual_fields):
            raise ValueError("required and contextual comparison fields must be disjoint")
        return self

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.spec_id,
            object_version=self.spec_version,
        )


class ComparisonGroup(FrozenModel):
    group_id: str = Field(pattern=OBJECT_ID_PATTERN)
    role: ComparisonGroupRole
    product_definition_ref: VersionedObjectRef
    target_stage_ref: VersionedObjectRef
    bundle_refs: list[VersionedObjectRef] = Field(min_length=1)

    @field_validator("bundle_refs")
    @classmethod
    def bundle_refs_are_unique(
        cls, value: list[VersionedObjectRef]
    ) -> list[VersionedObjectRef]:
        _unique([item.ref for item in value], "bundle_refs")
        return value


class ComparisonCaseManifest(FrozenModel):
    object_version: Literal["0.1.0"]
    comparison_id: str = Field(pattern=r"^comparison:[A-Za-z0-9._:-]+$")
    comparison_version: str = Field(pattern=VERSION_PATTERN)
    spec_ref: VersionedObjectRef
    groups: list[ComparisonGroup] = Field(min_length=2)
    provenance_refs: list[VersionedObjectRef] = Field(min_length=1)
    created_at: datetime

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @field_validator("groups")
    @classmethod
    def groups_are_unique(cls, value: list[ComparisonGroup]) -> list[ComparisonGroup]:
        _unique([item.group_id for item in value], "group IDs")
        bundle_refs = [ref.ref for group in value for ref in group.bundle_refs]
        _unique(bundle_refs, "bundle references")
        if sum(group.role is ComparisonGroupRole.BASELINE for group in value) != 1:
            raise ValueError("comparison requires exactly one baseline group")
        if not any(group.role is not ComparisonGroupRole.BASELINE for group in value):
            raise ValueError("comparison requires at least one non-baseline group")
        return value

    @field_validator("provenance_refs")
    @classmethod
    def provenance_is_unique(
        cls, value: list[VersionedObjectRef]
    ) -> list[VersionedObjectRef]:
        _unique([item.ref for item in value], "provenance_refs")
        return value

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.comparison_id,
            object_version=self.comparison_version,
        )


class TimepointBinding(FrozenModel):
    basis: Literal["in_vitro_day", "declared_stage", "not_applicable"]
    label: str = Field(min_length=1)
    order: StrictInt | None = Field(default=None, ge=0)

    _label_is_safe = field_validator("label")(validate_publication_text)

    @model_validator(mode="after")
    def order_is_explicit_for_real_time(self) -> Self:
        if self.basis == "not_applicable" and self.order is not None:
            raise ValueError("not_applicable timepoint cannot declare an order")
        if self.basis != "not_applicable" and self.order is None:
            raise ValueError("real timepoint requires an explicit order")
        return self


class ProductMetricEvidence(FrozenModel):
    metric_id: str = Field(pattern=OBJECT_ID_PATTERN)
    measurement_spec_ref: VersionedObjectRef
    raw_value: Numeric | None = None
    interval: tuple[Numeric, Numeric] | None = None
    unit: str = Field(min_length=1)
    denominator_kind: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    denominator_value: Numeric | None = Field(default=None, gt=0)
    evidence_state: MetricEvidenceState
    evidence_refs: list[str] = Field(default_factory=list)
    provenance_refs: list[VersionedObjectRef] = Field(min_length=1)
    domain_score: None = None
    score_state: Literal["unavailable"] = "unavailable"

    _unit_is_safe = field_validator("unit")(validate_publication_text)

    @field_validator("evidence_refs")
    @classmethod
    def evidence_is_unique(cls, value: list[str]) -> list[str]:
        _unique(value, "evidence_refs")
        return value

    @field_validator("provenance_refs")
    @classmethod
    def provenance_is_unique(
        cls, value: list[VersionedObjectRef]
    ) -> list[VersionedObjectRef]:
        _unique([item.ref for item in value], "provenance_refs")
        return value

    @model_validator(mode="after")
    def value_state_is_coherent(self) -> Self:
        _finite(self.raw_value, "raw_value")
        _finite(self.denominator_value, "denominator_value")
        if self.interval is not None:
            lower, upper = self.interval
            _finite(lower, "interval lower bound")
            _finite(upper, "interval upper bound")
            if lower > upper:
                raise ValueError("interval lower bound cannot exceed upper bound")
        absent = self.evidence_state in {
            MetricEvidenceState.MISSING,
            MetricEvidenceState.UNKNOWN,
            MetricEvidenceState.UNAVAILABLE,
        }
        if absent and any(
            value is not None
            for value in (self.raw_value, self.interval, self.denominator_value)
        ):
            raise ValueError("missing/unknown/unavailable evidence cannot carry values")
        if not absent and (
            self.raw_value is None or self.denominator_value is None
        ):
            raise ValueError("assessed evidence requires raw value and denominator")
        return self


class ProductEvidenceBundle(FrozenModel):
    object_version: Literal["0.1.0"]
    bundle_id: str = Field(pattern=r"^product-evidence-bundle:[A-Za-z0-9._:-]+$")
    bundle_version: str = Field(pattern=VERSION_PATTERN)
    comparison_ref: VersionedObjectRef
    group_id: str = Field(pattern=OBJECT_ID_PATTERN)
    product_case: ProductCase
    product_definition: ProductDefinitionCard
    target_stage_ref: VersionedObjectRef
    data_view_ref: VersionedObjectRef
    timepoint: TimepointBinding
    batch_refs: list[VersionedObjectRef]
    protocol_refs: list[VersionedObjectRef]
    lab_refs: list[VersionedObjectRef]
    cell_line_refs: list[VersionedObjectRef]
    reference_snapshot_ref: VersionedObjectRef
    preprocessing_snapshot_ref: VersionedObjectRef
    algorithm_ref: VersionedObjectRef
    metrics: list[ProductMetricEvidence] = Field(min_length=1)
    sufficiency_summary_ref: str | None = None
    sufficiency_state: Literal[
        "sufficient", "limited", "insufficient", "not_assessed"
    ] | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    provenance_refs: list[VersionedObjectRef] = Field(min_length=1)
    created_at: datetime

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @field_validator(
        "batch_refs", "protocol_refs", "lab_refs", "cell_line_refs", "provenance_refs"
    )
    @classmethod
    def ref_lists_are_unique(
        cls, value: list[VersionedObjectRef]
    ) -> list[VersionedObjectRef]:
        _unique([item.ref for item in value], "versioned reference list")
        return value

    @field_validator("metrics")
    @classmethod
    def metrics_are_unique(
        cls, value: list[ProductMetricEvidence]
    ) -> list[ProductMetricEvidence]:
        _unique([item.metric_id for item in value], "metric IDs")
        return value

    @field_validator("evidence_refs")
    @classmethod
    def evidence_is_unique(cls, value: list[str]) -> list[str]:
        _unique(value, "evidence_refs")
        return value

    @model_validator(mode="after")
    def bundle_bindings_are_coherent(self) -> Self:
        if self.product_case.product_definition_ref != self.product_definition.ref:
            raise ValueError("ProductCase and ProductDefinitionCard are not bound")
        if self.product_case.assay not in self.product_definition.supported_assays:
            raise ValueError("ProductCase assay is not supported by ProductDefinitionCard")
        if self.product_case.measurement_spec_ref.ref not in {
            item.measurement_spec_ref.ref for item in self.metrics
        }:
            raise ValueError("ProductCase MeasurementSpec is absent from bundle metrics")
        paired = self.sufficiency_summary_ref is not None and self.sufficiency_state is not None
        if paired != (
            self.sufficiency_summary_ref is not None
            or self.sufficiency_state is not None
        ):
            raise ValueError("sufficiency summary reference and state must be paired")
        return self

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.bundle_id,
            object_version=self.bundle_version,
        )


class InputChecksumBinding(FrozenModel):
    role: Literal[
        "comparison_stability_spec",
        "comparison_case_manifest",
        "product_evidence_bundle",
    ]
    sha256: str = Field(pattern=SHA256_PATTERN)


class GroupMetricSummary(FrozenModel):
    group_id: str = Field(pattern=OBJECT_ID_PATTERN)
    metric_id: str = Field(pattern=OBJECT_ID_PATTERN)
    value_state: Literal["shadow", "missing", "unknown", "unavailable", "alert"]
    observed_count: StrictInt = Field(ge=0)
    expected_count: StrictInt = Field(ge=1)
    mean_value: StrictFloat | None = None
    observed_range: tuple[Numeric, Numeric] | None = None
    unit: str = Field(min_length=1)
    denominator_kind: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    reason_codes: list[str]

    @model_validator(mode="after")
    def summary_is_coherent(self) -> Self:
        _finite(self.mean_value, "mean_value")
        if self.observed_count > self.expected_count:
            raise ValueError("observed metric count exceeds expected count")
        if self.value_state == "shadow":
            if self.mean_value is None or self.observed_range is None:
                raise ValueError("shadow group summary requires descriptive values")
        elif self.mean_value is not None or self.observed_range is not None:
            raise ValueError("non-shadow group summary cannot carry descriptive values")
        return self


class MetricContrast(FrozenModel):
    metric_id: str = Field(pattern=OBJECT_ID_PATTERN)
    measurement_spec_ref: VersionedObjectRef
    baseline_group_id: str = Field(pattern=OBJECT_ID_PATTERN)
    comparator_group_id: str = Field(pattern=OBJECT_ID_PATTERN)
    contrast_state: Literal[
        "shadow", "missing", "unknown", "unavailable", "alert", "not_comparable"
    ]
    baseline_value: StrictFloat | None = None
    comparator_value: StrictFloat | None = None
    delta_comparator_minus_baseline: StrictFloat | None = None
    direction: Literal["increase", "decrease", "no_change", "not_assessed"]
    interval_state: Literal["descriptive_only", "not_assessed"]
    unit: str = Field(min_length=1)
    denominator_kind: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    reason_codes: list[str]

    @model_validator(mode="after")
    def contrast_is_coherent(self) -> Self:
        for field, value in (
            ("baseline_value", self.baseline_value),
            ("comparator_value", self.comparator_value),
            ("delta", self.delta_comparator_minus_baseline),
        ):
            _finite(value, field)
        assessed = self.contrast_state == "shadow"
        values = (
            self.baseline_value,
            self.comparator_value,
            self.delta_comparator_minus_baseline,
        )
        if assessed != all(value is not None for value in values):
            raise ValueError("only shadow contrast may carry complete numeric values")
        if assessed != (self.direction != "not_assessed"):
            raise ValueError("numeric direction must match assessed contrast")
        if assessed != (self.interval_state == "descriptive_only"):
            raise ValueError("assessed contrast is descriptive only")
        return self


class MetricStability(FrozenModel):
    metric_id: str = Field(pattern=OBJECT_ID_PATTERN)
    state: Literal[
        "replicated_descriptive", "single_preparation", "incomplete", "unavailable"
    ]
    observed_preparation_count: StrictInt = Field(ge=0)
    expected_preparation_count: StrictInt = Field(ge=1)
    observed_range: tuple[Numeric, Numeric] | None = None
    range_width: StrictFloat | None = Field(default=None, ge=0.0)
    reason_codes: list[str]


class GroupStability(FrozenModel):
    group_id: str = Field(pattern=OBJECT_ID_PATTERN)
    independent_preparation_count: StrictInt = Field(ge=1)
    batch_count: StrictInt = Field(ge=0)
    metric_stability: list[MetricStability] = Field(min_length=1)


class ProductComparisonStabilityProfile(FrozenModel):
    object_version: Literal["0.1.0"]
    result_id: str = Field(pattern=r"^product-comparison-stability:[a-f0-9]{16}$")
    tool_id: Literal["P0-07"]
    tool_version: str = Field(pattern=VERSION_PATTERN)
    comparison_ref: VersionedObjectRef
    spec_ref: VersionedObjectRef
    input_bindings: list[InputChecksumBinding] = Field(min_length=4)
    comparison_eligibility: Literal[
        "strictly_comparable",
        "contextual_comparator",
        "reference_or_ood",
        "not_comparable",
        "not_estimable",
    ]
    comparison_mode: Literal["descriptive_only"]
    profile_state: Literal["complete", "partial", "not_assessed"]
    group_summaries: list[GroupMetricSummary] = Field(min_length=2)
    metric_contrasts: list[MetricContrast]
    stability_results: list[GroupStability] = Field(min_length=2)
    confounded_factors: list[ConfoundingFactor]
    evidence_refs: list[str]
    reason_codes: list[str]
    overall_score: None = None
    overall_rank: None = None
    domain_score: None = None
    score_state: Literal["unavailable"] = "unavailable"

    @field_validator("input_bindings")
    @classmethod
    def input_bindings_are_unique(
        cls, value: list[InputChecksumBinding]
    ) -> list[InputChecksumBinding]:
        _unique(
            [(item.role, item.sha256) for item in value],
            "input bindings",
        )
        return value

    @field_validator("confounded_factors", "evidence_refs", "reason_codes")
    @classmethod
    def set_like_outputs_are_unique(cls, value: list[object]) -> list[object]:
        _unique(value, "set-like output")
        return value

    @model_validator(mode="after")
    def assessment_state_is_coherent(self) -> Self:
        estimable = self.comparison_eligibility in {
            "strictly_comparable",
            "contextual_comparator",
        }
        if not estimable and any(
            item.contrast_state == "shadow" for item in self.metric_contrasts
        ):
            raise ValueError("non-estimable comparison cannot carry numeric deltas")
        if self.profile_state == "not_assessed" and estimable:
            raise ValueError("estimable comparison cannot be wholly not_assessed")
        return self


PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/comparison-stability-spec/v0.1": ComparisonStabilitySpec,
    "bridge://schemas/comparison-case-manifest/v0.1": ComparisonCaseManifest,
    "bridge://schemas/product-evidence-bundle/v0.1": ProductEvidenceBundle,
    "bridge://schemas/product-comparison-stability-profile/v0.1": ProductComparisonStabilityProfile,
}
