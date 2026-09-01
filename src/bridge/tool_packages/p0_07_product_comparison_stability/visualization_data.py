from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Literal, Self

from pydantic import Field, StrictFloat, field_validator, model_validator

from bridge.tool_packages.p0_07_product_comparison_stability.models import (
    ComparisonCaseManifest,
    ComparisonField,
    ComparisonGroupRole,
    ComparisonMethodBundle,
    ComparisonMethodId,
    ComparisonMethodInput,
    ComparisonMethodSpec,
    ComparisonSeriesSemantics,
    ComparisonStabilitySpec,
    MetricEvidenceState,
    ProductComparisonStabilityProfile,
    ProductEvidenceBundle,
)
from bridge.toolkit.contracts import EvidenceState, FrozenModel
from bridge.toolkit.visualization import VisualizationArtifactV2

PRODUCT_COMPARISON_VISUALIZATION_DATA_SCHEMA_REF = (
    "bridge://schemas/product-comparison-visualization-data/v0.1"
)
P007_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF = (
    "bridge://schemas/p0-07-visualization-artifact-set/v0.1"
)
COMPARABILITY_COMPONENT_REF = "bridge.product-comparison.comparability@0.1.0"
METRIC_DIFFERENCES_COMPONENT_REF = "bridge.product-comparison.metric-differences@0.1.0"
METHOD_EVIDENCE_COMPONENT_REF = "bridge.product-comparison.method-evidence@0.1.0"
P007_COMPONENT_REFS = (
    COMPARABILITY_COMPONENT_REF,
    METRIC_DIFFERENCES_COMPONENT_REF,
    METHOD_EVIDENCE_COMPONENT_REF,
)

_RECORD_ID = r"^[a-z][a-z0-9_.-]+$"
_SHA256 = r"^[0-9a-f]{64}$"
_ABSENT_STATES = {
    MetricEvidenceState.MISSING,
    MetricEvidenceState.UNKNOWN,
    MetricEvidenceState.UNAVAILABLE,
}
_METHOD_ROLES = {
    ComparisonMethodId.SAMPLE_EFFECT: "standardized_sample_effect",
    ComparisonMethodId.JENSEN_SHANNON: "probability_mass_distance",
    ComparisonMethodId.PROFILE_CORRELATION: "matched_feature_correlation",
    ComparisonMethodId.WASSERSTEIN_1D: "ordered_distribution_distance",
    ComparisonMethodId.ROBUST_DISPERSION: "within_group_dispersion",
}
_IndependenceSummary = tuple[
    Literal["declared", "not_recorded", "inconsistent"],
    int | None,
    str | None,
    list[str],
    list[str],
]


def _sorted_unique(values: list[str], field_name: str) -> list[str]:
    if values != sorted(set(values)):
        raise ValueError(f"{field_name} must be sorted and unique")
    return values


def _source_evidence_state(state: MetricEvidenceState) -> EvidenceState:
    if state is MetricEvidenceState.SHADOW:
        return EvidenceState.INFERRED
    return EvidenceState(state.value)


def _contrast_evidence_state(state: str) -> EvidenceState:
    if state == "shadow":
        return EvidenceState.INFERRED
    try:
        return EvidenceState(state)
    except ValueError:
        return EvidenceState.UNAVAILABLE


class _VisualizationRecord(FrozenModel):
    record_id: str = Field(pattern=_RECORD_ID)
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_state: EvidenceState
    scientific_status: Literal["candidate"] = "candidate"
    missingness: Literal["available", "unavailable"]
    applicability: Literal["applicable", "partially_applicable", "not_assessed"]
    assessment_state: Literal["available", "not_assessed"]
    reason_codes: list[str] = Field(default_factory=list)

    @field_validator("evidence_ids", "reason_codes")
    @classmethod
    def set_like_fields_are_sorted(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)


class GroupDesignValue(FrozenModel):
    group_id: str = Field(min_length=1)
    values: list[str] = Field(default_factory=list)

    @field_validator("values")
    @classmethod
    def values_are_sorted(cls, values: list[str]) -> list[str]:
        return _sorted_unique(values, "design values")


class ComparisonDesignRecord(_VisualizationRecord):
    component_ref: Literal[COMPARABILITY_COMPONENT_REF] = COMPARABILITY_COMPONENT_REF
    dimension_kind: Literal[
        "required_equal", "contextual", "confounder", "independence"
    ]
    dimension_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    values_by_group: list[GroupDesignValue] = Field(min_length=1)
    design_state: Literal[
        "matched",
        "required_mismatch",
        "contextual_mismatch",
        "metadata_missing",
        "completely_confounded",
        "overlap_present",
        "declared",
        "not_recorded",
        "inconsistent",
    ]
    blocks_numeric_difference: bool

    @field_validator("values_by_group")
    @classmethod
    def groups_are_unique(
        cls, values: list[GroupDesignValue]
    ) -> list[GroupDesignValue]:
        group_ids = [item.group_id for item in values]
        if group_ids != sorted(set(group_ids)):
            raise ValueError("design groups must be sorted and unique")
        return values

    @model_validator(mode="after")
    def design_semantics_are_coherent(self) -> Self:
        blocking_states = {
            "required_mismatch",
            "metadata_missing",
            "completely_confounded",
        }
        if self.blocks_numeric_difference != (self.design_state in blocking_states):
            raise ValueError("design blocker does not match design state")
        if self.assessment_state != "available":
            raise ValueError("design records are always explicit assessments")
        return self


class PreparationMetricRecord(_VisualizationRecord):
    component_ref: Literal[METRIC_DIFFERENCES_COMPONENT_REF] = (
        METRIC_DIFFERENCES_COMPONENT_REF
    )
    group_id: str = Field(min_length=1)
    group_role: ComparisonGroupRole
    bundle_ref: str = Field(min_length=1)
    product_case_ref: str = Field(min_length=1)
    analysis_unit_ref: str = Field(min_length=1)
    source_unit_kind: Literal["sample", "preparation"]
    independence_state: Literal["declared", "not_recorded", "inconsistent"]
    independence_scope_ref: str | None = None
    independence_group_refs: list[str] = Field(default_factory=list)
    declared_independence_group_count: int | None = Field(default=None, ge=1)
    timepoint_basis: Literal["in_vitro_day", "declared_stage", "not_applicable"]
    timepoint_label: str = Field(min_length=1)
    timepoint_order: int | None = Field(default=None, ge=0)
    metric_id: str = Field(min_length=1)
    measurement_spec_ref: str = Field(min_length=1)
    raw_value: StrictFloat | None = None
    value_state: MetricEvidenceState
    unit: str = Field(min_length=1)
    denominator_kind: str = Field(min_length=1)
    denominator_value: StrictFloat | None = Field(default=None, gt=0)
    source_interval: tuple[StrictFloat, StrictFloat] | None = None
    interval_semantics: Literal["not_declared"] = "not_declared"
    render_interval: Literal[False] = False
    sufficiency_state: (
        Literal["sufficient", "limited", "insufficient", "not_assessed"] | None
    ) = None

    @field_validator("independence_group_refs")
    @classmethod
    def independence_groups_are_sorted(cls, values: list[str]) -> list[str]:
        return _sorted_unique(values, "independence_group_refs")

    @model_validator(mode="after")
    def source_semantics_are_coherent(self) -> Self:
        numeric = self.raw_value is not None
        if numeric != (self.denominator_value is not None):
            raise ValueError("raw value and denominator must be paired")
        if self.value_state in _ABSENT_STATES and numeric:
            raise ValueError("absent metric evidence cannot carry a value")
        if self.value_state not in _ABSENT_STATES and not numeric:
            raise ValueError("assessed metric evidence requires a value")
        if self.source_interval is not None:
            lower, upper = self.source_interval
            if lower > upper:
                raise ValueError("source interval lower bound exceeds upper bound")
        expected_missingness = "available" if numeric else "unavailable"
        if self.missingness != expected_missingness:
            raise ValueError("metric missingness does not match raw value")
        expected_assessment = (
            "available"
            if numeric and self.value_state is not MetricEvidenceState.ALERT
            else "not_assessed"
        )
        if self.assessment_state != expected_assessment:
            raise ValueError("metric assessment state does not match source state")
        if self.independence_state == "declared":
            if (
                self.independence_scope_ref is None
                or not self.independence_group_refs
                or self.declared_independence_group_count
                != len(self.independence_group_refs)
            ):
                raise ValueError("declared independence requires complete bindings")
        elif self.declared_independence_group_count is not None:
            raise ValueError("undeclared independence cannot carry a count")
        return self


class MetricDifferenceRecord(_VisualizationRecord):
    component_ref: Literal[METRIC_DIFFERENCES_COMPONENT_REF] = (
        METRIC_DIFFERENCES_COMPONENT_REF
    )
    metric_id: str = Field(min_length=1)
    measurement_spec_ref: str = Field(min_length=1)
    baseline_group_id: str = Field(min_length=1)
    comparator_group_id: str = Field(min_length=1)
    comparison_state: Literal[
        "shadow", "missing", "unknown", "unavailable", "alert", "not_comparable"
    ]
    baseline_value: StrictFloat | None = None
    comparator_value: StrictFloat | None = None
    raw_delta: StrictFloat | None = None
    direction: Literal["increase", "decrease", "no_change", "not_assessed"]
    estimand: Literal["difference_in_group_means"] = "difference_in_group_means"
    uncertainty_state: Literal["not_available"] = "not_available"
    unit: str = Field(min_length=1)
    denominator_kind: str = Field(min_length=1)
    baseline_analysis_unit_count: int = Field(ge=1)
    comparator_analysis_unit_count: int = Field(ge=1)
    baseline_assessed_count: int = Field(ge=0)
    comparator_assessed_count: int = Field(ge=0)
    preparation_record_ids: list[str] = Field(min_length=2)
    stability_record_ids: list[str] = Field(min_length=2, max_length=2)

    @field_validator("preparation_record_ids", "stability_record_ids")
    @classmethod
    def linked_record_ids_are_sorted(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)

    @model_validator(mode="after")
    def difference_semantics_are_coherent(self) -> Self:
        assessed = self.comparison_state == "shadow"
        values = (self.baseline_value, self.comparator_value, self.raw_delta)
        if assessed != all(value is not None for value in values):
            raise ValueError("only assessed difference may carry numeric values")
        if assessed:
            expected = self.comparator_value - self.baseline_value
            if not math.isclose(self.raw_delta, expected, rel_tol=0.0, abs_tol=1e-12):
                raise ValueError("raw delta must equal comparator minus baseline")
            expected_direction = (
                "increase"
                if self.raw_delta > 0
                else "decrease"
                if self.raw_delta < 0
                else "no_change"
            )
            if self.direction != expected_direction:
                raise ValueError("difference direction disagrees with raw delta")
        elif self.direction != "not_assessed":
            raise ValueError("unavailable difference cannot carry a direction")
        if self.baseline_assessed_count > self.baseline_analysis_unit_count:
            raise ValueError("baseline assessed count exceeds analysis units")
        if self.comparator_assessed_count > self.comparator_analysis_unit_count:
            raise ValueError("comparator assessed count exceeds analysis units")
        return self


class MetricStabilityVisualizationRecord(_VisualizationRecord):
    component_ref: Literal[METRIC_DIFFERENCES_COMPONENT_REF] = (
        METRIC_DIFFERENCES_COMPONENT_REF
    )
    group_id: str = Field(min_length=1)
    metric_id: str = Field(min_length=1)
    analysis_unit_count: int = Field(ge=1)
    assessed_analysis_unit_count: int = Field(ge=0)
    independence_state: Literal["declared", "not_recorded", "inconsistent"]
    declared_independence_group_count: int | None = Field(default=None, ge=1)
    observed_min: StrictFloat | None = None
    observed_max: StrictFloat | None = None
    range_width: StrictFloat | None = Field(default=None, ge=0)
    range_semantics: Literal["observed_min_max"] = "observed_min_max"
    analysis_unit_coverage_state: Literal[
        "multiple_analysis_units",
        "single_analysis_unit",
        "incomplete",
        "unavailable",
    ]
    unit: str = Field(min_length=1)
    denominator_kind: str = Field(min_length=1)

    @model_validator(mode="after")
    def stability_semantics_are_coherent(self) -> Self:
        present = (
            self.observed_min is not None,
            self.observed_max is not None,
            self.range_width is not None,
        )
        if self.assessed_analysis_unit_count:
            if not all(present):
                raise ValueError("observed values require a complete descriptive range")
            if self.observed_min > self.observed_max:
                raise ValueError("observed range lower bound exceeds upper bound")
            if not math.isclose(
                self.range_width,
                self.observed_max - self.observed_min,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ValueError("range width does not match observed range")
        elif any(present):
            raise ValueError("unassessed stability cannot carry a range")
        if self.assessed_analysis_unit_count > self.analysis_unit_count:
            raise ValueError("assessed count exceeds analysis units")
        if self.independence_state == "declared":
            if self.declared_independence_group_count is None:
                raise ValueError("declared independence requires a count")
        elif self.declared_independence_group_count is not None:
            raise ValueError("undeclared independence cannot carry a count")
        expected_coverage = (
            "unavailable"
            if self.assessed_analysis_unit_count == 0
            else (
                "incomplete"
                if self.assessed_analysis_unit_count < self.analysis_unit_count
                else (
                    "single_analysis_unit"
                    if self.analysis_unit_count == 1
                    else "multiple_analysis_units"
                )
            )
        )
        if self.analysis_unit_coverage_state != expected_coverage:
            raise ValueError("analysis-unit coverage state disagrees with counts")
        return self


class MethodEvidenceRecord(_VisualizationRecord):
    component_ref: Literal[METHOD_EVIDENCE_COMPONENT_REF] = (
        METHOD_EVIDENCE_COMPONENT_REF
    )
    task_id: str = Field(min_length=1)
    method_id: ComparisonMethodId
    method_ref: str = Field(min_length=1)
    analytical_role: Literal[
        "standardized_sample_effect",
        "probability_mass_distance",
        "matched_feature_correlation",
        "ordered_distribution_distance",
        "within_group_dispersion",
    ]
    series_semantics: ComparisonSeriesSemantics
    metric_id: str = Field(min_length=1)
    group_ids: list[str] = Field(min_length=1, max_length=2)
    estimate_name: str | None = None
    estimate_value: StrictFloat | None = None
    estimate_unit: str | None = None
    raw_delta: StrictFloat | None = None
    raw_delta_unit: str | None = None
    n_values: list[int] = Field(min_length=1, max_length=2)
    method_assessment_state: Literal["available", "not_assessed"]
    display_axis_id: str = Field(min_length=1)

    @field_validator("group_ids")
    @classmethod
    def group_ids_are_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("method group IDs must be unique")
        return values

    @model_validator(mode="after")
    def method_semantics_are_coherent(self) -> Self:
        estimate_fields = (
            self.estimate_name,
            self.estimate_value,
            self.estimate_unit,
        )
        if self.method_assessment_state == "available":
            if not all(value is not None for value in estimate_fields):
                raise ValueError("available method estimate must be fully bound")
        elif any(value is not None for value in estimate_fields):
            raise ValueError("not-assessed method cannot carry an estimate")
        if (self.raw_delta is None) != (self.raw_delta_unit is None):
            raise ValueError("method raw delta and unit must be paired")
        if self.assessment_state != self.method_assessment_state:
            raise ValueError("method assessment aliases disagree")
        return self


class ProductComparisonVisualizationDataV1(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[PRODUCT_COMPARISON_VISUALIZATION_DATA_SCHEMA_REF] = (
        PRODUCT_COMPARISON_VISUALIZATION_DATA_SCHEMA_REF
    )
    profile_id: str = Field(pattern=r"^product-comparison-visualization:[a-f0-9]{16}$")
    producer_tool_id: Literal["P0-07"] = "P0-07"
    producer_tool_version: str = Field(min_length=1)
    producer_run_ref: str = Field(pattern=r"^run:run-[a-f0-9]{16}$")
    comparison_ref: str = Field(min_length=1)
    spec_ref: str = Field(min_length=1)
    comparison_eligibility: Literal[
        "strictly_comparable",
        "contextual_comparator",
        "reference_or_ood",
        "not_comparable",
        "not_estimable",
    ]
    comparison_mode: Literal["descriptive_only"]
    profile_state: Literal["complete", "partial", "not_assessed"]
    analysis_mode: Literal["legacy_comparison", "method_runtime"]
    input_sha256_by_role: dict[str, list[str]]
    method_spec_ref: str | None = None
    method_spec_sha256: str | None = Field(default=None, pattern=_SHA256)
    method_input_ref: str | None = None
    method_input_sha256: str | None = Field(default=None, pattern=_SHA256)
    method_bundle_ref: str | None = None
    method_bundle_sha256: str | None = Field(default=None, pattern=_SHA256)
    design_records: list[ComparisonDesignRecord] = Field(min_length=1)
    preparation_records: list[PreparationMetricRecord] = Field(min_length=2)
    difference_records: list[MetricDifferenceRecord] = Field(min_length=1)
    stability_records: list[MetricStabilityVisualizationRecord] = Field(min_length=2)
    method_records: list[MethodEvidenceRecord]
    evidence_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(min_length=1)
    overall_score: None = None
    overall_rank: None = None
    domain_score: None = None

    @field_validator("evidence_ids", "limitations")
    @classmethod
    def top_level_lists_are_sorted(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)

    @field_validator("input_sha256_by_role")
    @classmethod
    def input_hashes_are_valid(
        cls, values: dict[str, list[str]]
    ) -> dict[str, list[str]]:
        if not values:
            raise ValueError("input hash bindings cannot be empty")
        normalized: dict[str, list[str]] = {}
        for role, hashes in sorted(values.items()):
            if (
                not role
                or not hashes
                or any(re.fullmatch(_SHA256, value) is None for value in hashes)
            ):
                raise ValueError("input hash bindings must contain SHA-256 values")
            normalized[role] = _sorted_unique(
                sorted(hashes), f"input hashes for {role}"
            )
        return normalized

    @model_validator(mode="after")
    def records_and_provenance_are_coherent(self) -> Self:
        method_values = (
            self.method_spec_ref,
            self.method_spec_sha256,
            self.method_input_ref,
            self.method_input_sha256,
            self.method_bundle_ref,
            self.method_bundle_sha256,
        )
        if self.analysis_mode == "method_runtime":
            if not all(method_values) or not self.method_records:
                raise ValueError("method runtime requires complete method provenance")
        elif any(method_values) or self.method_records:
            raise ValueError("legacy comparison cannot carry method evidence")
        records = [
            *self.design_records,
            *self.preparation_records,
            *self.difference_records,
            *self.stability_records,
            *self.method_records,
        ]
        record_ids = [item.record_id for item in records]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("visualization record IDs must be unique")
        for difference in self.difference_records:
            groups = {
                difference.baseline_group_id,
                difference.comparator_group_id,
            }
            expected_preparations = sorted(
                item.record_id
                for item in self.preparation_records
                if item.group_id in groups
                and item.metric_id == difference.metric_id
                and item.unit == difference.unit
                and item.denominator_kind == difference.denominator_kind
            )
            expected_stability = sorted(
                item.record_id
                for item in self.stability_records
                if item.group_id in groups
                and item.metric_id == difference.metric_id
                and item.unit == difference.unit
                and item.denominator_kind == difference.denominator_kind
            )
            if difference.preparation_record_ids != expected_preparations:
                raise ValueError("metric difference preparation links are incomplete")
            if (
                difference.stability_record_ids != expected_stability
                or len(expected_stability) != 2
            ):
                raise ValueError("metric difference stability links are incomplete")
        return self


class P007VisualizationArtifactSet(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[P007_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF] = (
        P007_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF
    )
    artifact_set_id: str = Field(pattern=r"^p0-07-visualizations:[a-f0-9]{16}$")
    data_profile_artifact_id: str = Field(min_length=1)
    data_profile_sha256: str = Field(pattern=_SHA256)
    visualizations: list[VisualizationArtifactV2] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def artifact_set_is_exactly_bound(self) -> Self:
        refs = [item.component_ref for item in self.visualizations]
        if set(refs) != set(P007_COMPONENT_REFS) or len(refs) != len(set(refs)):
            raise ValueError("artifact set must contain each P0-07 component once")
        for item in self.visualizations:
            if (
                item.data_binding.artifact_id != self.data_profile_artifact_id
                or item.data_binding.sha256 != self.data_profile_sha256
            ):
                raise ValueError("visualization data binding does not match profile")
        return self


def build_product_comparison_visualization_data(
    *,
    run_id: str,
    tool_version: str,
    result: ProductComparisonStabilityProfile,
    spec: ComparisonStabilitySpec,
    manifest: ComparisonCaseManifest,
    bundles: list[ProductEvidenceBundle],
    method_spec: ComparisonMethodSpec | None = None,
    method_input: ComparisonMethodInput | None = None,
    method_bundle: ComparisonMethodBundle | None = None,
    method_bundle_sha256: str | None = None,
) -> ProductComparisonVisualizationDataV1:
    _validate_bindings(tool_version, result, spec, manifest, bundles)
    method_values = (method_spec, method_input, method_bundle, method_bundle_sha256)
    if any(value is not None for value in method_values) != all(
        value is not None for value in method_values
    ):
        raise ValueError("method visualization inputs must be supplied together")
    if method_bundle is not None:
        _validate_method_bindings(
            tool_version, manifest, method_spec, method_input, method_bundle
        )

    groups = sorted(
        manifest.groups,
        key=lambda item: (
            item.role is not ComparisonGroupRole.BASELINE,
            item.group_id,
        ),
    )
    bundle_by_ref = {item.ref.ref: item for item in bundles}
    grouped = {
        group.group_id: [
            bundle_by_ref[ref.ref]
            for ref in sorted(group.bundle_refs, key=lambda item: item.ref)
        ]
        for group in groups
    }
    evidence_ids = sorted(
        {
            *result.evidence_refs,
            *(
                ref
                for bundle in bundles
                for ref in [
                    *bundle.evidence_refs,
                    *(ref for metric in bundle.metrics for ref in metric.evidence_refs),
                ]
            ),
            *(method_bundle.evidence_refs if method_bundle is not None else []),
        }
    )
    independence = _independence_by_group(groups, grouped)
    design_records = _design_records(spec, groups, grouped, independence, evidence_ids)
    preparation_records = _preparation_records(groups, grouped, independence)
    stability_records = _stability_records(groups, preparation_records, independence)
    difference_records = _difference_records(
        result, groups, preparation_records, stability_records
    )
    method_records = _method_records(method_spec, method_input, method_bundle)
    input_hashes: dict[str, list[str]] = defaultdict(list)
    for binding in result.input_bindings:
        input_hashes[binding.role].append(binding.sha256)
    limitations = {
        "descriptive_only_no_inferential_interval",
        "different_metric_units_and_denominators_not_rankable",
        "overall_score_rank_and_domain_score_unavailable",
    }
    if any(item.source_interval is not None for item in preparation_records):
        limitations.add("source_interval_semantics_not_declared_not_rendered")
    states = {item[0] for item in independence.values()}
    if "not_recorded" in states:
        limitations.add("independence_not_recorded")
    if "inconsistent" in states:
        limitations.add("independence_binding_inconsistent")
    if "declared" in states:
        limitations.add("independence_declared_not_verified_by_visualization")
    if any(
        "declared_independence_group_shared_by_analysis_units" in item.reason_codes
        for item in preparation_records
    ):
        limitations.add("analysis_units_share_declared_independence_group")
    if method_records:
        limitations.add("method_estimands_are_task_specific_not_rankable")

    return ProductComparisonVisualizationDataV1(
        profile_id=(f"product-comparison-visualization:{run_id.removeprefix('run-')}"),
        producer_tool_version=tool_version,
        producer_run_ref=f"run:{run_id}",
        comparison_ref=result.comparison_ref.ref,
        spec_ref=result.spec_ref.ref,
        comparison_eligibility=result.comparison_eligibility,
        comparison_mode=result.comparison_mode,
        profile_state=result.profile_state,
        analysis_mode=(
            "method_runtime" if method_bundle is not None else "legacy_comparison"
        ),
        input_sha256_by_role={
            role: sorted(hashes) for role, hashes in sorted(input_hashes.items())
        },
        method_spec_ref=(
            f"{method_spec.method_spec_id}@{method_spec.method_spec_version}"
            if method_spec is not None
            else None
        ),
        method_spec_sha256=(
            method_bundle.method_spec_sha256 if method_bundle is not None else None
        ),
        method_input_ref=(
            f"{method_input.method_input_id}@{method_input.method_input_version}"
            if method_input is not None
            else None
        ),
        method_input_sha256=(
            method_bundle.method_input_sha256 if method_bundle is not None else None
        ),
        method_bundle_ref=(
            f"{method_bundle.bundle_id}@{method_bundle.object_version}"
            if method_bundle is not None
            else None
        ),
        method_bundle_sha256=method_bundle_sha256,
        design_records=design_records,
        preparation_records=preparation_records,
        difference_records=difference_records,
        stability_records=stability_records,
        method_records=method_records,
        evidence_ids=evidence_ids,
        limitations=sorted(limitations),
        overall_score=None,
        overall_rank=None,
        domain_score=None,
    )


def _validate_bindings(
    tool_version: str,
    result: ProductComparisonStabilityProfile,
    spec: ComparisonStabilitySpec,
    manifest: ComparisonCaseManifest,
    bundles: list[ProductEvidenceBundle],
) -> None:
    if result.tool_version != tool_version:
        raise ValueError("result tool version does not match producer")
    if result.comparison_ref != manifest.ref or result.spec_ref != spec.ref:
        raise ValueError("result comparison/spec bindings do not match inputs")
    if spec.comparison_ref != manifest.ref or manifest.spec_ref != spec.ref:
        raise ValueError("comparison spec and manifest are not mutually bound")
    expected = {ref.ref for group in manifest.groups for ref in group.bundle_refs}
    actual = {item.ref.ref for item in bundles}
    if len(actual) != len(bundles) or actual != expected:
        raise ValueError("visualization bundle set does not match manifest")


def _validate_method_bindings(
    tool_version: str,
    manifest: ComparisonCaseManifest,
    spec: ComparisonMethodSpec,
    method_input: ComparisonMethodInput,
    bundle: ComparisonMethodBundle,
) -> None:
    if (
        bundle.tool_version != tool_version
        or spec.comparison_ref != manifest.ref
        or method_input.comparison_ref != manifest.ref
        or bundle.comparison_ref != manifest.ref
    ):
        raise ValueError("method visualization bindings do not match comparison")


def _field_value(bundle: ProductEvidenceBundle, field: ComparisonField) -> str:
    values = {
        ComparisonField.PRODUCT_DEFINITION: bundle.product_definition.ref.ref,
        ComparisonField.TARGET_STAGE: bundle.target_stage_ref.ref,
        ComparisonField.ASSAY: bundle.product_case.assay,
        ComparisonField.DATA_VIEW: bundle.data_view_ref.ref,
        ComparisonField.TIMEPOINT: (
            f"{bundle.timepoint.basis}:{bundle.timepoint.label}:"
            f"{bundle.timepoint.order}"
        ),
        ComparisonField.REFERENCE: bundle.reference_snapshot_ref.ref,
        ComparisonField.PREPROCESSING: bundle.preprocessing_snapshot_ref.ref,
        ComparisonField.ALGORITHM: bundle.algorithm_ref.ref,
    }
    return values[field]


def _design_records(
    spec: ComparisonStabilitySpec,
    groups,
    grouped: dict[str, list[ProductEvidenceBundle]],
    independence: dict[str, _IndependenceSummary],
    evidence_ids: list[str],
) -> list[ComparisonDesignRecord]:
    records: list[ComparisonDesignRecord] = []
    index = 1
    for kind, fields in (
        ("required_equal", spec.required_equal_fields),
        ("contextual", spec.contextual_fields),
    ):
        for field in sorted(fields, key=lambda item: item.value):
            values_by_group = [
                GroupDesignValue(
                    group_id=group.group_id,
                    values=sorted(
                        {
                            _field_value(bundle, field)
                            for bundle in grouped[group.group_id]
                        }
                    ),
                )
                for group in groups
            ]
            matched = (
                len({value for item in values_by_group for value in item.values}) == 1
            )
            state = (
                "matched"
                if matched
                else (
                    "required_mismatch"
                    if kind == "required_equal"
                    else "contextual_mismatch"
                )
            )
            records.append(
                ComparisonDesignRecord(
                    record_id=f"design.{index:02d}",
                    evidence_ids=evidence_ids,
                    evidence_state=EvidenceState.INFERRED,
                    missingness="available",
                    applicability=(
                        "applicable" if state == "matched" else "partially_applicable"
                    ),
                    assessment_state="available",
                    reason_codes=(
                        [] if state == "matched" else [f"{kind}_{field.value}_mismatch"]
                    ),
                    dimension_kind=kind,
                    dimension_id=field.value,
                    values_by_group=values_by_group,
                    design_state=state,
                    blocks_numeric_difference=state == "required_mismatch",
                )
            )
            index += 1

    for factor in sorted(spec.confounding_factors, key=lambda item: item.value):
        values_by_group = [
            GroupDesignValue(
                group_id=group.group_id,
                values=sorted(
                    {
                        ref.ref
                        for bundle in grouped[group.group_id]
                        for ref in getattr(bundle, f"{factor.value}_refs")
                    }
                ),
            )
            for group in groups
        ]
        levels = {item.group_id: set(item.values) for item in values_by_group}
        baseline_id = next(
            group.group_id
            for group in groups
            if group.role is ComparisonGroupRole.BASELINE
        )
        comparator_ids = [
            group.group_id
            for group in groups
            if group.role is not ComparisonGroupRole.BASELINE
        ]
        if any(not values for values in levels.values()):
            state = "metadata_missing"
        elif any(
            levels[baseline_id].isdisjoint(levels[comparator_id])
            for comparator_id in comparator_ids
        ):
            state = "completely_confounded"
        else:
            state = "overlap_present"
        records.append(
            ComparisonDesignRecord(
                record_id=f"design.{index:02d}",
                evidence_ids=evidence_ids,
                evidence_state=EvidenceState.INFERRED,
                missingness=(
                    "unavailable" if state == "metadata_missing" else "available"
                ),
                applicability=(
                    "not_assessed"
                    if state in {"metadata_missing", "completely_confounded"}
                    else "applicable"
                ),
                assessment_state="available",
                reason_codes=(
                    []
                    if state == "overlap_present"
                    else [f"confounder_{factor.value}_{state}"]
                ),
                dimension_kind="confounder",
                dimension_id=factor.value,
                values_by_group=values_by_group,
                design_state=state,
                blocks_numeric_difference=state
                in {"metadata_missing", "completely_confounded"},
            )
        )
        index += 1

    independence_states = [independence[group.group_id][0] for group in groups]
    state = (
        independence_states[0] if len(set(independence_states)) == 1 else "inconsistent"
    )
    values_by_group = [
        GroupDesignValue(
            group_id=group.group_id,
            values=sorted(
                [
                    *(
                        [independence[group.group_id][2]]
                        if independence[group.group_id][2] is not None
                        else []
                    ),
                    *independence[group.group_id][3],
                ]
            ),
        )
        for group in groups
    ]
    records.append(
        ComparisonDesignRecord(
            record_id=f"design.{index:02d}",
            evidence_ids=evidence_ids,
            evidence_state=EvidenceState.INFERRED,
            missingness="available" if state == "declared" else "unavailable",
            applicability=(
                "applicable"
                if state == "declared"
                else (
                    "partially_applicable"
                    if state == "not_recorded"
                    else "not_assessed"
                )
            ),
            assessment_state="available",
            reason_codes=sorted(
                {
                    reason
                    for group in groups
                    for reason in independence[group.group_id][4]
                }
            ),
            dimension_kind="independence",
            dimension_id="independence",
            values_by_group=values_by_group,
            design_state=state,
            blocks_numeric_difference=False,
        )
    )
    return records


def _independence_by_group(
    groups,
    grouped: dict[str, list[ProductEvidenceBundle]],
) -> dict[str, _IndependenceSummary]:
    candidates: dict[str, tuple[str, str | None, list[str], list[str]]] = {}
    ref_owners: dict[str, set[str]] = defaultdict(set)
    for group in groups:
        scopes: set[str] = set()
        refs: list[str] = []
        any_binding = False
        complete = True
        for bundle in grouped[group.group_id]:
            case = bundle.product_case
            bound = (
                case.biological_unit_manifest_ref is not None
                or case.biological_unit_manifest_sha256 is not None
                or case.independence_scope_ref is not None
                or bool(case.independence_group_refs)
            )
            any_binding = any_binding or bound
            if not (
                case.biological_unit_manifest_ref is not None
                and case.biological_unit_manifest_sha256 is not None
                and case.independence_scope_ref is not None
                and case.independence_group_refs
            ):
                complete = False
                continue
            scopes.add(case.independence_scope_ref.ref)
            for ref in case.independence_group_refs:
                refs.append(ref.ref)
                ref_owners[ref.ref].add(group.group_id)

        unique_refs = sorted(set(refs))
        reasons: set[str] = set()
        if not any_binding:
            state = "not_recorded"
            reasons.add("independence_not_recorded")
        elif not complete or len(scopes) != 1:
            state = "inconsistent"
            reasons.add("independence_binding_inconsistent")
        else:
            state = "declared"
            if len(refs) != len(unique_refs):
                reasons.add("declared_independence_group_shared_by_analysis_units")
        candidates[group.group_id] = (
            state,
            next(iter(scopes), None),
            unique_refs,
            sorted(reasons),
        )

    cross_group_overlap = {
        group_id
        for owners in ref_owners.values()
        if len(owners) > 1
        for group_id in owners
    }
    result: dict[str, _IndependenceSummary] = {}
    for group in groups:
        state, scope, refs, reasons = candidates[group.group_id]
        if group.group_id in cross_group_overlap:
            state = "inconsistent"
            reasons = sorted(
                {*reasons, "independence_group_overlap_across_comparison_groups"}
            )
        result[group.group_id] = (
            state,
            len(refs) if state == "declared" else None,
            scope,
            refs,
            reasons,
        )
    return result


def _preparation_records(
    groups,
    grouped: dict[str, list[ProductEvidenceBundle]],
    independence: dict[str, _IndependenceSummary],
) -> list[PreparationMetricRecord]:
    records: list[PreparationMetricRecord] = []
    index = 1
    for group in groups:
        state, count, scope, refs, independence_reasons = independence[group.group_id]
        for bundle in grouped[group.group_id]:
            for metric in sorted(bundle.metrics, key=lambda item: item.metric_id):
                evidence_ids = sorted({*bundle.evidence_refs, *metric.evidence_refs})
                numeric = metric.raw_value is not None
                assessment = (
                    "available"
                    if numeric
                    and metric.evidence_state is not MetricEvidenceState.ALERT
                    else "not_assessed"
                )
                applicability = (
                    "applicable"
                    if assessment == "available"
                    else ("partially_applicable" if numeric else "not_assessed")
                )
                reasons = set(independence_reasons)
                if assessment != "available":
                    reasons.add(f"metric_evidence_{metric.evidence_state.value}")
                records.append(
                    PreparationMetricRecord(
                        record_id=f"preparation.{index:03d}",
                        evidence_ids=evidence_ids,
                        evidence_state=_source_evidence_state(metric.evidence_state),
                        missingness="available" if numeric else "unavailable",
                        applicability=applicability,
                        assessment_state=assessment,
                        reason_codes=sorted(reasons),
                        group_id=group.group_id,
                        group_role=group.role,
                        bundle_ref=bundle.ref.ref,
                        product_case_ref=bundle.product_case.ref.ref,
                        analysis_unit_ref=(
                            bundle.product_case.sample_or_preparation_ref.ref
                        ),
                        source_unit_kind=bundle.product_case.source_unit_kind,
                        independence_state=state,
                        independence_scope_ref=scope,
                        independence_group_refs=refs,
                        declared_independence_group_count=count,
                        timepoint_basis=bundle.timepoint.basis,
                        timepoint_label=bundle.timepoint.label,
                        timepoint_order=bundle.timepoint.order,
                        metric_id=metric.metric_id,
                        measurement_spec_ref=metric.measurement_spec_ref.ref,
                        raw_value=(
                            float(metric.raw_value)
                            if metric.raw_value is not None
                            else None
                        ),
                        value_state=metric.evidence_state,
                        unit=metric.unit,
                        denominator_kind=metric.denominator_kind,
                        denominator_value=(
                            float(metric.denominator_value)
                            if metric.denominator_value is not None
                            else None
                        ),
                        source_interval=(
                            tuple(float(value) for value in metric.interval)
                            if metric.interval is not None
                            else None
                        ),
                        interval_semantics="not_declared",
                        render_interval=False,
                        sufficiency_state=bundle.sufficiency_state,
                    )
                )
                index += 1
    return records


def _difference_records(
    result: ProductComparisonStabilityProfile,
    groups,
    preparations: list[PreparationMetricRecord],
    stability: list[MetricStabilityVisualizationRecord],
) -> list[MetricDifferenceRecord]:
    group_counts = {
        group.group_id: len(
            {
                item.analysis_unit_ref
                for item in preparations
                if item.group_id == group.group_id
            }
        )
        for group in groups
    }
    records: list[MetricDifferenceRecord] = []
    for index, contrast in enumerate(
        sorted(
            result.metric_contrasts,
            key=lambda item: (item.comparator_group_id, item.metric_id),
        ),
        start=1,
    ):
        group_ids = {contrast.baseline_group_id, contrast.comparator_group_id}
        relevant = [
            item
            for item in preparations
            if item.metric_id == contrast.metric_id
            and item.group_id in group_ids
            and item.unit == contrast.unit
            and item.denominator_kind == contrast.denominator_kind
        ]
        linked_stability = [
            item
            for item in stability
            if item.metric_id == contrast.metric_id
            and item.group_id in group_ids
            and item.unit == contrast.unit
            and item.denominator_kind == contrast.denominator_kind
        ]
        evidence_ids = sorted({ref for item in relevant for ref in item.evidence_ids})
        assessed = contrast.contrast_state == "shadow"
        applicability = (
            "applicable"
            if assessed and result.comparison_eligibility == "strictly_comparable"
            else ("partially_applicable" if assessed else "not_assessed")
        )
        records.append(
            MetricDifferenceRecord(
                record_id=f"difference.{index:03d}",
                evidence_ids=evidence_ids,
                evidence_state=_contrast_evidence_state(contrast.contrast_state),
                missingness="available" if assessed else "unavailable",
                applicability=applicability,
                assessment_state="available" if assessed else "not_assessed",
                reason_codes=sorted(set(contrast.reason_codes)),
                metric_id=contrast.metric_id,
                measurement_spec_ref=contrast.measurement_spec_ref.ref,
                baseline_group_id=contrast.baseline_group_id,
                comparator_group_id=contrast.comparator_group_id,
                comparison_state=contrast.contrast_state,
                baseline_value=contrast.baseline_value,
                comparator_value=contrast.comparator_value,
                raw_delta=contrast.delta_comparator_minus_baseline,
                direction=contrast.direction,
                unit=contrast.unit,
                denominator_kind=contrast.denominator_kind,
                baseline_analysis_unit_count=group_counts[contrast.baseline_group_id],
                comparator_analysis_unit_count=group_counts[
                    contrast.comparator_group_id
                ],
                baseline_assessed_count=sum(
                    item.assessment_state == "available"
                    for item in relevant
                    if item.group_id == contrast.baseline_group_id
                ),
                comparator_assessed_count=sum(
                    item.assessment_state == "available"
                    for item in relevant
                    if item.group_id == contrast.comparator_group_id
                ),
                preparation_record_ids=sorted(item.record_id for item in relevant),
                stability_record_ids=sorted(
                    item.record_id for item in linked_stability
                ),
            )
        )
    return records


def _stability_records(
    groups,
    preparations: list[PreparationMetricRecord],
    independence: dict[str, _IndependenceSummary],
) -> list[MetricStabilityVisualizationRecord]:
    records: list[MetricStabilityVisualizationRecord] = []
    index = 1
    for group in groups:
        group_preparations = [
            item for item in preparations if item.group_id == group.group_id
        ]
        analysis_count = len({item.analysis_unit_ref for item in group_preparations})
        independence_state, count, _, _, independence_reasons = independence[
            group.group_id
        ]
        metric_contracts = sorted(
            {
                (item.metric_id, item.unit, item.denominator_kind)
                for item in group_preparations
            }
        )
        for metric_id, unit, denominator_kind in metric_contracts:
            rows = [
                item
                for item in group_preparations
                if item.metric_id == metric_id
                and item.unit == unit
                and item.denominator_kind == denominator_kind
            ]
            values = [
                item.raw_value
                for item in rows
                if item.assessment_state == "available"
                and item.raw_value is not None
            ]
            if not values:
                coverage = "unavailable"
                coverage_reasons = {"analysis_unit_metric_unavailable"}
            elif len(values) < analysis_count:
                coverage = "incomplete"
                coverage_reasons = {"analysis_unit_metric_incomplete"}
            elif analysis_count == 1:
                coverage = "single_analysis_unit"
                coverage_reasons = {"single_analysis_unit_descriptive_only"}
            else:
                coverage = "multiple_analysis_units"
                coverage_reasons = set()
            shared = (
                "declared_independence_group_shared_by_analysis_units"
                in independence_reasons
            )
            independence_supports_units = (
                independence_state == "declared"
                and count == analysis_count
                and not shared
            )
            evidence_ids = sorted({ref for item in rows for ref in item.evidence_ids})
            records.append(
                MetricStabilityVisualizationRecord(
                    record_id=f"stability.{index:03d}",
                    evidence_ids=evidence_ids,
                    evidence_state=(
                        EvidenceState.INFERRED if values else EvidenceState.UNAVAILABLE
                    ),
                    missingness="available" if values else "unavailable",
                    applicability=(
                        "applicable"
                        if coverage == "multiple_analysis_units"
                        and independence_supports_units
                        else ("partially_applicable" if values else "not_assessed")
                    ),
                    assessment_state="available" if values else "not_assessed",
                    reason_codes=sorted(
                        {*coverage_reasons, *independence_reasons}
                    ),
                    group_id=group.group_id,
                    metric_id=metric_id,
                    analysis_unit_count=analysis_count,
                    assessed_analysis_unit_count=len(values),
                    independence_state=independence_state,
                    declared_independence_group_count=count,
                    observed_min=min(values) if values else None,
                    observed_max=max(values) if values else None,
                    range_width=(max(values) - min(values) if values else None),
                    analysis_unit_coverage_state=coverage,
                    unit=unit,
                    denominator_kind=denominator_kind,
                )
            )
            index += 1
    return records


def _method_records(
    spec: ComparisonMethodSpec | None,
    method_input: ComparisonMethodInput | None,
    bundle: ComparisonMethodBundle | None,
) -> list[MethodEvidenceRecord]:
    if spec is None or method_input is None or bundle is None:
        return []
    series_by_id = {item.series_id: item for item in method_input.series}
    execution_by_method = {item.method_id: item for item in bundle.executions}
    records: list[MethodEvidenceRecord] = []
    index = 1
    for result in sorted(bundle.records, key=lambda item: item.task_id):
        task = next(item for item in spec.tasks if item.task_id == result.task_id)
        series = [series_by_id[item] for item in task.series_ids]
        semantics = {item.semantics for item in series}
        metrics = {item.metric_id for item in series}
        if len(semantics) != 1 or len(metrics) != 1:
            raise ValueError("method task series do not share semantics and metric")
        execution = execution_by_method[result.method_id]
        evidence_ids = sorted({ref for item in series for ref in item.evidence_refs})
        estimates = (
            sorted(result.estimates.items()) if result.estimates else [(None, None)]
        )
        for estimate_name, estimate_value in estimates:
            estimate_unit = (
                result.estimate_units[estimate_name]
                if estimate_name is not None
                else None
            )
            state = result.assessment_state
            axis_name = estimate_name or "not_assessed"
            axis_unit = estimate_unit or "none"
            records.append(
                MethodEvidenceRecord(
                    record_id=f"method.{index:03d}",
                    evidence_ids=evidence_ids,
                    evidence_state=(
                        EvidenceState.INFERRED
                        if state == "available"
                        else EvidenceState.UNAVAILABLE
                    ),
                    missingness=(
                        "available" if state == "available" else "unavailable"
                    ),
                    applicability=(
                        "applicable" if state == "available" else "not_assessed"
                    ),
                    assessment_state=state,
                    reason_codes=sorted(set(result.reason_codes)),
                    task_id=result.task_id,
                    method_id=result.method_id,
                    method_ref=execution.method_ref,
                    analytical_role=_METHOD_ROLES[result.method_id],
                    series_semantics=next(iter(semantics)),
                    metric_id=next(iter(metrics)),
                    group_ids=[item.group_id for item in series],
                    estimate_name=estimate_name,
                    estimate_value=estimate_value,
                    estimate_unit=estimate_unit,
                    raw_delta=result.raw_delta,
                    raw_delta_unit=result.raw_delta_unit,
                    n_values=result.n_values,
                    method_assessment_state=state,
                    display_axis_id=_axis_id(
                        result.method_id.value, axis_name, axis_unit
                    ),
                )
            )
            index += 1
    return records


def _axis_id(method_id: str, estimate_name: str, unit: str) -> str:
    value = f"{method_id}.{estimate_name}.{unit}".lower()
    return re.sub(r"[^a-z0-9_.-]+", "-", value).strip("-")


PUBLIC_VISUALIZATION_SCHEMA_MODELS = {
    PRODUCT_COMPARISON_VISUALIZATION_DATA_SCHEMA_REF: ProductComparisonVisualizationDataV1,
    P007_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF: P007VisualizationArtifactSet,
}
