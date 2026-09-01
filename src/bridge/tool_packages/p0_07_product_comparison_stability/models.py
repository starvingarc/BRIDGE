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


MetricStabilityV1 = MetricStability
GroupStabilityV1 = GroupStability
ProductComparisonStabilityProfileV1 = ProductComparisonStabilityProfile


class MetricStabilityV2(FrozenModel):
    metric_id: str = Field(pattern=OBJECT_ID_PATTERN)
    state: Literal[
        "multiple_analysis_units",
        "single_analysis_unit",
        "incomplete",
        "unavailable",
    ]
    assessed_analysis_unit_count: StrictInt = Field(ge=0)
    analysis_unit_count: StrictInt = Field(ge=1)
    observed_range: tuple[Numeric, Numeric] | None = None
    range_width: StrictFloat | None = Field(default=None, ge=0.0)
    range_semantics: Literal["observed_min_max"] = "observed_min_max"
    reason_codes: list[str]

    @model_validator(mode="after")
    def analysis_unit_range_is_coherent(self) -> Self:
        if self.assessed_analysis_unit_count > self.analysis_unit_count:
            raise ValueError("assessed analysis units exceed declared analysis units")
        present = self.observed_range is not None and self.range_width is not None
        if self.assessed_analysis_unit_count == 0:
            if present:
                raise ValueError("unavailable analysis units cannot carry a range")
            expected = "unavailable"
        else:
            if not present:
                raise ValueError("assessed analysis units require an observed range")
            lower, upper = self.observed_range
            if lower > upper:
                raise ValueError("observed range lower bound exceeds upper bound")
            if not math.isclose(
                self.range_width,
                float(upper) - float(lower),
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ValueError("range width does not match observed min-max")
            expected = (
                "incomplete"
                if self.assessed_analysis_unit_count < self.analysis_unit_count
                else (
                    "single_analysis_unit"
                    if self.analysis_unit_count == 1
                    else "multiple_analysis_units"
                )
            )
        if self.state != expected:
            raise ValueError("analysis-unit range state disagrees with counts")
        _unique(self.reason_codes, "metric stability reason codes")
        return self


class GroupStabilityV2(FrozenModel):
    group_id: str = Field(pattern=OBJECT_ID_PATTERN)
    analysis_unit_count: StrictInt = Field(ge=1)
    independence_state: Literal["declared", "not_recorded", "inconsistent"]
    independence_scope_ref: str | None = None
    independence_group_refs: list[str]
    declared_independence_group_count: StrictInt | None = Field(default=None, ge=1)
    batch_count: StrictInt = Field(ge=0)
    metric_stability: list[MetricStabilityV2] = Field(min_length=1)
    reason_codes: list[str]

    @model_validator(mode="after")
    def independence_and_counts_are_coherent(self) -> Self:
        _unique(self.independence_group_refs, "independence group references")
        _unique(self.reason_codes, "group stability reason codes")
        if any(
            item.analysis_unit_count != self.analysis_unit_count
            for item in self.metric_stability
        ):
            raise ValueError("metric analysis-unit counts disagree with group")
        if self.independence_state == "declared":
            if (
                self.independence_scope_ref is None
                or self.declared_independence_group_count
                != len(self.independence_group_refs)
                or self.declared_independence_group_count
                != self.analysis_unit_count
            ):
                raise ValueError(
                    "declared independence requires one group per analysis unit"
                )
        elif (
            self.independence_scope_ref is not None
            or self.declared_independence_group_count is not None
        ):
            raise ValueError(
                "unestablished independence cannot carry a scope or declared count"
            )
        return self


class ProductComparisonStabilityProfileV2(FrozenModel):
    object_version: Literal["0.2.0"]
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
    stability_results: list[GroupStabilityV2] = Field(min_length=2)
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


MetricStability = MetricStabilityV2
GroupStability = GroupStabilityV2
ProductComparisonStabilityProfile = ProductComparisonStabilityProfileV2


class ComparisonMethodId(StrEnum):
    SAMPLE_EFFECT = "CMP-EFFECT"
    JENSEN_SHANNON = "CMP-JS"
    PROFILE_CORRELATION = "CMP-CORR"
    WASSERSTEIN_1D = "CMP-WASS-1D"
    ROBUST_DISPERSION = "STAB-CV"


class ComparisonSeriesSemantics(StrEnum):
    PROBABILITY_MASS = "probability_mass"
    MATCHED_FEATURES = "matched_features"
    ORDERED_VALUES = "ordered_values"
    SAMPLE_VALUES = "sample_values"


class ComparisonMethodExecutionState(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    NOT_ASSESSED = "not_assessed"


class ComparisonMethodTask(FrozenModel):
    task_id: str = Field(
        pattern=r"^comparison-method-task:[A-Za-z0-9._:-]+$"
    )
    method_id: ComparisonMethodId
    series_ids: list[str] = Field(min_length=1, max_length=2)

    @field_validator("series_ids")
    @classmethod
    def series_ids_are_unique(cls, value: list[str]) -> list[str]:
        if any(
            not item.startswith("comparison-series:") or len(item) < 20
            for item in value
        ):
            raise ValueError("series IDs must use the comparison-series namespace")
        _unique(value, "task series IDs")
        return value

    @model_validator(mode="after")
    def arity_matches_method(self) -> Self:
        expected = (
            1
            if self.method_id is ComparisonMethodId.ROBUST_DISPERSION
            else 2
        )
        if len(self.series_ids) != expected:
            raise ValueError("comparison method task has the wrong series arity")
        return self


class ComparisonMethodSpec(FrozenModel):
    object_version: Literal["0.1.0"]
    method_spec_id: str = Field(
        pattern=r"^comparison-method-spec:[A-Za-z0-9._:-]+$"
    )
    method_spec_version: str = Field(pattern=VERSION_PATTERN)
    comparison_ref: VersionedObjectRef
    status: Literal["candidate"]
    tasks: list[ComparisonMethodTask] = Field(min_length=1)
    jensen_shannon_base: StrictFloat = Field(default=2.0, gt=1)
    active: bool

    @field_validator("tasks")
    @classmethod
    def tasks_are_unique(
        cls, value: list[ComparisonMethodTask]
    ) -> list[ComparisonMethodTask]:
        _unique([item.task_id for item in value], "comparison method task IDs")
        return value

class ComparisonMethodSeries(FrozenModel):
    series_id: str = Field(pattern=r"^comparison-series:[A-Za-z0-9._:-]+$")
    group_id: str = Field(pattern=OBJECT_ID_PATTERN)
    metric_id: str = Field(pattern=OBJECT_ID_PATTERN)
    semantics: ComparisonSeriesSemantics
    labels: list[str] = Field(min_length=2)
    values: list[Numeric] = Field(min_length=2)
    weights: list[StrictFloat] | None = None
    measurement_scale: Literal["ratio", "non_ratio", "unknown"] = "unknown"
    unit: str = Field(min_length=1)
    denominator_kind: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    source_bundle_refs: list[VersionedObjectRef] = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)

    _unit_is_safe = field_validator("unit")(validate_publication_text)

    @field_validator("labels", "evidence_refs")
    @classmethod
    def text_lists_are_unique(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("series labels and evidence refs must be non-empty")
        _unique(value, "series labels/evidence refs")
        return value

    @field_validator("source_bundle_refs")
    @classmethod
    def source_bundles_are_unique(
        cls, value: list[VersionedObjectRef]
    ) -> list[VersionedObjectRef]:
        _unique([item.ref for item in value], "series source bundles")
        return value

    @model_validator(mode="after")
    def series_values_are_coherent(self) -> Self:
        if len(self.labels) != len(self.values):
            raise ValueError("series labels and values must have equal length")
        for value in self.values:
            _finite(value, "series value")
        if self.weights is not None:
            if len(self.weights) != len(self.values):
                raise ValueError("series weights and values must have equal length")
            if any(
                value < 0 or not math.isfinite(value)
                for value in self.weights
            ):
                raise ValueError("series weights must be finite and non-negative")
            if sum(self.weights) <= 0:
                raise ValueError("series weights must contain positive mass")
            if self.semantics is not ComparisonSeriesSemantics.ORDERED_VALUES:
                raise ValueError(
                    "series weights are only supported for ordered_values"
                )
        if self.semantics is ComparisonSeriesSemantics.PROBABILITY_MASS:
            if any(value < 0 for value in self.values) or sum(self.values) <= 0:
                raise ValueError("probability-mass series require non-negative mass")
        return self


class ComparisonMethodInput(FrozenModel):
    object_version: Literal["0.1.0"]
    method_input_id: str = Field(
        pattern=r"^comparison-method-input:[A-Za-z0-9._:-]+$"
    )
    method_input_version: str = Field(pattern=VERSION_PATTERN)
    comparison_ref: VersionedObjectRef
    comparison_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    series: list[ComparisonMethodSeries] = Field(min_length=1)
    created_at: datetime

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @field_validator("series")
    @classmethod
    def series_are_unique(
        cls, value: list[ComparisonMethodSeries]
    ) -> list[ComparisonMethodSeries]:
        _unique([item.series_id for item in value], "comparison series IDs")
        return value


class ComparisonMethodRecord(FrozenModel):
    task_id: str = Field(
        pattern=r"^comparison-method-task:[A-Za-z0-9._:-]+$"
    )
    method_id: ComparisonMethodId
    series_ids: list[str] = Field(min_length=1, max_length=2)
    estimates: dict[str, StrictFloat]
    estimate_units: dict[str, str]
    raw_delta: StrictFloat | None = None
    raw_delta_unit: str | None = None
    n_values: list[StrictInt] = Field(min_length=1, max_length=2)
    assessment_state: Literal["available", "not_assessed"]
    reason_codes: list[str]

    @model_validator(mode="after")
    def result_state_is_coherent(self) -> Self:
        for name, value in self.estimates.items():
            if not name or not math.isfinite(value):
                raise ValueError("method estimates must be named and finite")
        if set(self.estimate_units) != set(self.estimates):
            raise ValueError("every method estimate requires one unit")
        for unit in self.estimate_units.values():
            validate_publication_text(unit)
        _finite(self.raw_delta, "method raw delta")
        if (self.raw_delta is None) != (self.raw_delta_unit is None):
            raise ValueError("method raw delta and unit must be paired")
        if self.raw_delta_unit is not None:
            validate_publication_text(self.raw_delta_unit)
        available = self.assessment_state == "available"
        if available != bool(self.estimates):
            raise ValueError("method estimates and assessment state disagree")
        if available == bool(self.reason_codes):
            raise ValueError("method reasons and assessment state disagree")
        return self


class ComparisonMethodExecution(FrozenModel):
    method_id: ComparisonMethodId
    method_ref: str = Field(pattern=r"^METHOD-[A-Z0-9-]+$")
    implementation: str = Field(min_length=1)
    execution_state: ComparisonMethodExecutionState
    package_versions: dict[str, str]
    reason_codes: list[str]


class ComparisonMethodBundle(FrozenModel):
    object_version: Literal["0.1.0"]
    bundle_id: str = Field(pattern=r"^comparison-method-bundle:[a-f0-9]{16}$")
    tool_id: Literal["P0-07"]
    tool_version: str = Field(pattern=VERSION_PATTERN)
    comparison_ref: VersionedObjectRef
    comparison_eligibility: Literal[
        "strictly_comparable",
        "contextual_comparator",
        "reference_or_ood",
        "not_comparable",
        "not_estimable",
    ]
    method_spec_sha256: str = Field(pattern=SHA256_PATTERN)
    method_input_sha256: str = Field(pattern=SHA256_PATTERN)
    selected_method_ids: list[ComparisonMethodId] = Field(min_length=1)
    executions: list[ComparisonMethodExecution] = Field(min_length=1)
    records: list[ComparisonMethodRecord] = Field(min_length=1)
    evidence_refs: list[str]
    evidence_state: Literal["shadow"] = "shadow"
    score_state: Literal["unavailable"] = "unavailable"
    domain_score: None = None
    created_at: datetime

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @model_validator(mode="after")
    def bundle_is_coherent(self) -> Self:
        _unique(self.selected_method_ids, "selected method IDs")
        _unique([item.task_id for item in self.records], "method record task IDs")
        executed = [item.method_id for item in self.executions]
        _unique(executed, "method execution IDs")
        if set(executed) != set(self.selected_method_ids):
            raise ValueError("executions must match selected methods")
        if {item.method_id for item in self.records} != set(
            self.selected_method_ids
        ):
            raise ValueError("records must cover selected methods")
        _unique(self.evidence_refs, "method evidence refs")
        return self


PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/comparison-stability-spec/v0.1": ComparisonStabilitySpec,
    "bridge://schemas/comparison-case-manifest/v0.1": ComparisonCaseManifest,
    "bridge://schemas/product-evidence-bundle/v0.1": ProductEvidenceBundle,
    "bridge://schemas/product-comparison-stability-profile/v0.1": ProductComparisonStabilityProfileV1,
    "bridge://schemas/product-comparison-stability-profile/v0.2": ProductComparisonStabilityProfile,
    "bridge://schemas/comparison-method-spec/v0.1": ComparisonMethodSpec,
    "bridge://schemas/comparison-method-input/v0.1": ComparisonMethodInput,
    "bridge://schemas/comparison-method-bundle/v0.1": ComparisonMethodBundle,
}
