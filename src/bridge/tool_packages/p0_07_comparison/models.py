from __future__ import annotations

from enum import StrEnum
import math
import re
from typing import Annotated, Literal, Self

from pydantic import (
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    field_validator,
    model_validator,
)

from bridge.tool_packages._configurable_contracts import (
    OBJECT_ID_PATTERN,
    SHA256_PATTERN,
    VERSION_PATTERN,
    VersionedObjectRef,
)
from bridge.tool_packages._publication_safety import validate_publication_text
from bridge.toolkit.contracts import FrozenModel, ScoreState


PublishedRef = Annotated[str, Field(pattern=OBJECT_ID_PATTERN)]
ReasonCode = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
FiniteNumber = StrictFloat | StrictInt


def _unique(values: list[object], field: str) -> list[object]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must contain unique values")
    return values


def _finite(value: FiniteNumber | None) -> FiniteNumber | None:
    if value is not None and not math.isfinite(float(value)):
        raise ValueError("numeric values must be finite")
    return value


class ComparisonRole(StrEnum):
    BASELINE = "baseline"
    CANDIDATE = "candidate"


class ContractDimension(StrEnum):
    PRODUCT_DEFINITION = "product_definition"
    TARGET_CONTEXT = "target_context"
    ASSAY = "assay"
    SAMPLING_CONTEXT = "sampling_context"
    REFERENCE_SNAPSHOT = "reference_snapshot"
    PRIOR_SNAPSHOT = "prior_snapshot"
    MEASUREMENT_SPEC = "measurement_spec"
    SCORE_CONTRACT = "score_contract"
    ALGORITHM = "algorithm"
    PREPROCESSING = "preprocessing"


class ComparabilityState(StrEnum):
    STRICTLY_COMPARABLE = "strictly_comparable"
    CONTEXTUAL_COMPARATOR = "contextual_comparator"
    NOT_COMPARABLE = "not_comparable"


class MetricEvidenceState(StrEnum):
    MEASURED = "measured"
    INFERRED = "inferred"
    PRIOR_ONLY = "prior_only"
    NEGATIVE = "negative"
    MISSING = "missing"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


class MetricDirectionPolicy(StrEnum):
    HIGHER_IS_FAVORABLE = "higher_is_favorable"
    LOWER_IS_FAVORABLE = "lower_is_favorable"
    DESCRIPTIVE_ONLY = "descriptive_only"


class DirectionRelation(StrEnum):
    CANDIDATE_HIGHER = "candidate_higher"
    CANDIDATE_LOWER = "candidate_lower"
    NO_OBSERVED_DIFFERENCE = "no_observed_difference"
    UNAVAILABLE = "unavailable"


class ConfiguredInterpretation(StrEnum):
    CONFIGURED_FAVORABLE_DIRECTION = "configured_favorable_direction"
    CONFIGURED_UNFAVORABLE_DIRECTION = "configured_unfavorable_direction"
    NO_DIRECTIONAL_INTERPRETATION = "no_directional_interpretation"
    NO_OBSERVED_DIFFERENCE = "no_observed_difference"
    UNAVAILABLE = "unavailable"


class ComparisonCaseSpec(FrozenModel):
    role: ComparisonRole
    product_case_ref: VersionedObjectRef


class MetricComparisonRule(FrozenModel):
    metric_id: str = Field(pattern=r"^metric:[A-Za-z0-9._:-]+$")
    unit: str = Field(min_length=1, max_length=120)
    direction_policy: MetricDirectionPolicy
    required: StrictBool
    eligible_evidence_states: list[MetricEvidenceState] = Field(
        min_length=1,
        json_schema_extra={"uniqueItems": True},
    )

    _unit_is_publication_safe = field_validator("unit")(
        validate_publication_text
    )

    @field_validator("eligible_evidence_states")
    @classmethod
    def states_are_unique(
        cls, value: list[MetricEvidenceState]
    ) -> list[MetricEvidenceState]:
        return _unique(value, "eligible_evidence_states")


class ComparisonSpec(FrozenModel):
    object_version: Literal["0.1.0"]
    comparison_spec_id: str = Field(
        pattern=r"^comparison-spec:[A-Za-z0-9._:-]+$"
    )
    comparison_spec_version: str = Field(pattern=VERSION_PATTERN)
    cases: list[ComparisonCaseSpec] = Field(min_length=2, max_length=2)
    required_equal_dimensions: list[ContractDimension] = Field(
        min_length=1,
        json_schema_extra={"uniqueItems": True},
    )
    dimension_mismatch_policy: Literal["contextual_comparator", "not_comparable"]
    comparison_mode: Literal["descriptive_only"]
    minimum_biological_units_per_case: StrictInt = Field(gt=0)
    metrics: list[MetricComparisonRule] = Field(min_length=1)
    missing_metric_policy: Literal["report_unavailable"]
    pareto_policy: Literal["not_assessed_without_score_contract"]

    @field_validator("required_equal_dimensions")
    @classmethod
    def dimensions_are_unique(
        cls, value: list[ContractDimension]
    ) -> list[ContractDimension]:
        _unique(value, "required_equal_dimensions")
        required = set(ContractDimension) - {ContractDimension.SCORE_CONTRACT}
        if set(value) != required:
            raise ValueError(
                "required_equal_dimensions must contain every non-score contract dimension"
            )
        return value

    @field_validator("cases")
    @classmethod
    def cases_are_pairwise(
        cls, value: list[ComparisonCaseSpec]
    ) -> list[ComparisonCaseSpec]:
        if {item.role for item in value} != set(ComparisonRole):
            raise ValueError("cases require one baseline and one candidate")
        _unique([item.product_case_ref.ref for item in value], "case refs")
        return value

    @field_validator("metrics")
    @classmethod
    def metrics_are_unique(
        cls, value: list[MetricComparisonRule]
    ) -> list[MetricComparisonRule]:
        _unique([item.metric_id for item in value], "metrics")
        if not any(item.required for item in value):
            raise ValueError("at least one comparison metric must be required")
        return value

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.comparison_spec_id,
            object_version=self.comparison_spec_version,
        )


class ComparisonContractSnapshot(FrozenModel):
    product_definition_ref: VersionedObjectRef
    target_context_ref: VersionedObjectRef
    assay_ref: VersionedObjectRef
    sampling_context_ref: VersionedObjectRef
    reference_snapshot_ref: VersionedObjectRef
    prior_snapshot_ref: VersionedObjectRef
    measurement_spec_ref: VersionedObjectRef
    score_contract_ref: VersionedObjectRef | None
    algorithm_ref: VersionedObjectRef
    preprocessing_ref: VersionedObjectRef


class PreparationMetric(FrozenModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {
                            "evidence_state": {
                                "enum": ["missing", "unknown", "unavailable"]
                            }
                        },
                        "required": ["evidence_state"],
                    },
                    "then": {
                        "properties": {
                            "value": {"type": "null"},
                            "denominator": {"type": "null"},
                        }
                    },
                    "else": {"properties": {"value": {"type": ["number", "integer"]}}},
                }
            ]
        },
    )

    metric_id: str = Field(pattern=r"^metric:[A-Za-z0-9._:-]+$")
    unit: str = Field(min_length=1, max_length=120)
    value: FiniteNumber | None
    denominator: StrictInt | None = Field(default=None, gt=0)
    evidence_state: MetricEvidenceState
    evidence_refs: list[PublishedRef] = Field(
        min_length=1,
        json_schema_extra={"uniqueItems": True},
    )

    _unit_is_publication_safe = field_validator("unit")(
        validate_publication_text
    )

    @field_validator("value")
    @classmethod
    def value_is_finite(cls, value: FiniteNumber | None) -> FiniteNumber | None:
        return _finite(value)

    @field_validator("evidence_refs")
    @classmethod
    def evidence_is_unique(cls, value: list[str]) -> list[str]:
        return _unique(value, "evidence_refs")

    @model_validator(mode="after")
    def evidence_state_is_coherent(self) -> Self:
        unavailable = {
            MetricEvidenceState.MISSING,
            MetricEvidenceState.UNKNOWN,
            MetricEvidenceState.UNAVAILABLE,
        }
        if self.evidence_state in unavailable:
            if self.value is not None or self.denominator is not None:
                raise ValueError("unavailable metric cannot carry value or denominator")
        elif self.value is None:
            raise ValueError("available metric requires value")
        return self


class PreparationEvidence(FrozenModel):
    preparation_ref: VersionedObjectRef
    metrics: list[PreparationMetric] = Field(min_length=1)

    @field_validator("metrics")
    @classmethod
    def metrics_are_unique(
        cls, value: list[PreparationMetric]
    ) -> list[PreparationMetric]:
        _unique([item.metric_id for item in value], "preparation metrics")
        return value


class ComparisonCaseEvidence(FrozenModel):
    product_case_ref: VersionedObjectRef
    contract_snapshot: ComparisonContractSnapshot
    sufficiency_summary_ref: VersionedObjectRef
    preparations: list[PreparationEvidence] = Field(min_length=1)

    @field_validator("preparations")
    @classmethod
    def preparations_are_unique(
        cls, value: list[PreparationEvidence]
    ) -> list[PreparationEvidence]:
        _unique([item.preparation_ref.ref for item in value], "preparations")
        return value


class ComparisonEvidenceBundle(FrozenModel):
    object_version: Literal["0.1.0"]
    evidence_bundle_id: str = Field(
        pattern=r"^comparison-evidence-bundle:[A-Za-z0-9._:-]+$"
    )
    evidence_bundle_version: str = Field(pattern=VERSION_PATTERN)
    cases: list[ComparisonCaseEvidence] = Field(min_length=2, max_length=2)

    @field_validator("cases")
    @classmethod
    def case_refs_are_unique(
        cls, value: list[ComparisonCaseEvidence]
    ) -> list[ComparisonCaseEvidence]:
        _unique([item.product_case_ref.ref for item in value], "case evidence")
        return value

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.evidence_bundle_id,
            object_version=self.evidence_bundle_version,
        )


class ContractDimensionCheck(FrozenModel):
    dimension: ContractDimension
    matches: StrictBool
    baseline_value: str = Field(min_length=1)
    candidate_value: str = Field(min_length=1)


class CaseMetricSummary(FrozenModel):
    product_case_ref: VersionedObjectRef
    eligible_biological_unit_count: StrictInt = Field(ge=0)
    mean: FiniteNumber | None
    minimum: FiniteNumber | None
    maximum: FiniteNumber | None
    evidence_refs: list[PublishedRef] = Field(json_schema_extra={"uniqueItems": True})

    @field_validator("mean", "minimum", "maximum")
    @classmethod
    def numbers_are_finite(
        cls, value: FiniteNumber | None
    ) -> FiniteNumber | None:
        return _finite(value)

    @field_validator("evidence_refs")
    @classmethod
    def evidence_is_unique_sorted(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("evidence_refs must be unique and sorted")
        return value

    @model_validator(mode="after")
    def summary_is_coherent(self) -> Self:
        values = (self.mean, self.minimum, self.maximum)
        if self.eligible_biological_unit_count == 0 and any(
            value is not None for value in values
        ):
            raise ValueError("empty summary cannot contain numeric values")
        if self.eligible_biological_unit_count > 0 and any(
            value is None for value in values
        ):
            raise ValueError("nonempty summary requires mean and range")
        return self


class MetricComparisonResult(FrozenModel):
    metric_id: str = Field(pattern=r"^metric:[A-Za-z0-9._:-]+$")
    unit: str = Field(min_length=1, max_length=120)
    baseline: CaseMetricSummary
    candidate: CaseMetricSummary
    raw_delta_candidate_minus_baseline: FiniteNumber | None
    direction_relation: DirectionRelation
    configured_interpretation: ConfiguredInterpretation
    result_state: Literal["available", "unavailable"]
    evidence_refs: list[PublishedRef] = Field(json_schema_extra={"uniqueItems": True})
    reason_codes: list[ReasonCode] = Field(json_schema_extra={"uniqueItems": True})

    _unit_is_publication_safe = field_validator("unit")(
        validate_publication_text
    )

    @field_validator("raw_delta_candidate_minus_baseline")
    @classmethod
    def delta_is_finite(cls, value: FiniteNumber | None) -> FiniteNumber | None:
        return _finite(value)

    @field_validator("evidence_refs", "reason_codes")
    @classmethod
    def lists_are_unique_sorted(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("comparison result lists must be unique and sorted")
        return value

    @model_validator(mode="after")
    def result_is_coherent(self) -> Self:
        if self.result_state == "available" and (
            self.raw_delta_candidate_minus_baseline is None
            or self.direction_relation is DirectionRelation.UNAVAILABLE
            or self.configured_interpretation is ConfiguredInterpretation.UNAVAILABLE
        ):
            raise ValueError("available comparison requires delta and direction")
        if self.result_state == "unavailable" and (
            self.raw_delta_candidate_minus_baseline is not None
            or self.direction_relation is not DirectionRelation.UNAVAILABLE
            or self.configured_interpretation is not ConfiguredInterpretation.UNAVAILABLE
        ):
            raise ValueError("unavailable comparison cannot contain a delta")
        return self


class CaseReadinessSummary(FrozenModel):
    role: ComparisonRole
    product_case_ref: VersionedObjectRef
    sufficiency_summary_ref: VersionedObjectRef
    sufficiency_state: Literal["not_assessed", "insufficient", "limited", "sufficient"]
    declared_biological_unit_count: StrictInt = Field(gt=0)


class ParetoAssessment(FrozenModel):
    assessment_state: Literal["not_assessed"]
    reason_code: Literal["score_contract_not_supplied"]


class ComparisonInputChecksums(FrozenModel):
    comparison_spec: str = Field(pattern=SHA256_PATTERN)
    comparison_evidence_bundle: str = Field(pattern=SHA256_PATTERN)
    product_cases: list[str] = Field(
        min_length=2,
        max_length=2,
        json_schema_extra={"uniqueItems": True},
    )
    case_evidence_readiness_summaries: list[str] = Field(
        min_length=2,
        max_length=2,
        json_schema_extra={"uniqueItems": True},
    )

    @field_validator("product_cases", "case_evidence_readiness_summaries")
    @classmethod
    def summary_checksums_are_unique(cls, value: list[str]) -> list[str]:
        _unique(value, "multi-object checksums")
        if any(re.fullmatch(SHA256_PATTERN, item) is None for item in value):
            raise ValueError("invalid summary checksum")
        return value


class ComparisonRecord(FrozenModel):
    object_version: Literal["0.1.0"]
    comparison_id: str = Field(pattern=r"^comparison-record:[a-f0-9]{16}$")
    tool_id: Literal["P0-07"]
    tool_version: str = Field(pattern=VERSION_PATTERN)
    comparison_spec_ref: VersionedObjectRef
    evidence_bundle_ref: VersionedObjectRef
    input_sha256_by_role: ComparisonInputChecksums
    result_state: Literal["complete", "partial", "not_assessed"]
    comparability_state: ComparabilityState
    comparison_mode: Literal["descriptive_only"]
    contract_checks: list[ContractDimensionCheck]
    case_readiness: list[CaseReadinessSummary]
    metric_comparisons: list[MetricComparisonResult]
    pareto_assessment: ParetoAssessment
    evidence_refs: list[PublishedRef] = Field(json_schema_extra={"uniqueItems": True})
    reason_codes: list[ReasonCode] = Field(json_schema_extra={"uniqueItems": True})
    overall_score: None = None
    overall_rank: None = None
    score_state: Literal[ScoreState.SHADOW, ScoreState.UNAVAILABLE]

    @field_validator("evidence_refs", "reason_codes")
    @classmethod
    def lists_are_unique_sorted(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("comparison record lists must be unique and sorted")
        return value

    @model_validator(mode="after")
    def record_is_coherent(self) -> Self:
        available = any(
            item.result_state == "available" for item in self.metric_comparisons
        )
        if self.result_state == "not_assessed" and available:
            raise ValueError("not_assessed comparison cannot contain available deltas")
        if self.result_state != "not_assessed" and not available:
            raise ValueError("assessed comparison requires an available delta")
        expected_score = (
            ScoreState.UNAVAILABLE
            if self.result_state == "not_assessed"
            else ScoreState.SHADOW
        )
        if self.score_state != expected_score:
            raise ValueError("score state does not match result state")
        if {item.role for item in self.case_readiness} != set(ComparisonRole):
            raise ValueError("case readiness requires baseline and candidate")
        return self


PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/comparison-spec/v0.1": ComparisonSpec,
    "bridge://schemas/comparison-evidence-bundle/v0.1": ComparisonEvidenceBundle,
    "bridge://schemas/comparison-record/v0.1": ComparisonRecord,
}
