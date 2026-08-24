from __future__ import annotations

from enum import StrEnum
import math
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


class AnalysisScope(StrEnum):
    WHOLE_PRODUCT = "whole_product"
    STATE_SPECIFIC = "state_specific"


class ProgramEvidenceState(StrEnum):
    MEASURED = "measured"
    INFERRED = "inferred"
    PRIOR_ONLY = "prior_only"
    NEGATIVE = "negative"
    MISSING = "missing"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


class ReviewDirection(StrEnum):
    ABOVE_REFERENCE = "above_reference"
    BELOW_REFERENCE = "below_reference"
    OUTSIDE_REFERENCE = "outside_reference"


class ReferenceRelation(StrEnum):
    BELOW_REFERENCE = "below_reference"
    WITHIN_REFERENCE = "within_reference"
    ABOVE_REFERENCE = "above_reference"


class ReviewFlagState(StrEnum):
    TRANSCRIPTOMIC_REVIEW_FLAG = "transcriptomic_review_flag"
    CANNOT_RESOLVE = "cannot_resolve"
    NOT_ASSESSED = "not_assessed"


class ProgramReviewRule(FrozenModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {"analysis_scope": {"const": "state_specific"}},
                        "required": ["analysis_scope"],
                    },
                    "then": {"properties": {"state_ref": {"type": "object"}}},
                    "else": {"properties": {"state_ref": {"type": "null"}}},
                }
            ]
        },
    )

    rule_id: str = Field(pattern=r"^program-review-rule:[A-Za-z0-9._:-]+$")
    program_ref: VersionedObjectRef
    analysis_scope: AnalysisScope
    state_ref: VersionedObjectRef | None = None
    stage_context_ref: VersionedObjectRef
    applicable_assays: list[Literal["scRNA-seq", "snRNA-seq"]] = Field(
        min_length=1,
        json_schema_extra={"uniqueItems": True},
    )
    metric_name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9._:-]*$")
    unit: str = Field(min_length=1, max_length=120)
    reference_lower: FiniteNumber
    reference_upper: FiniteNumber
    minimum_gene_coverage: FiniteNumber = Field(ge=0, le=1)
    eligible_evidence_states: list[ProgramEvidenceState] = Field(
        min_length=1,
        json_schema_extra={"uniqueItems": True},
    )
    minimum_independence_groups: StrictInt = Field(gt=0)
    review_direction: ReviewDirection
    orthogonal_follow_up_refs: list[PublishedRef] = Field(
        default_factory=list,
        json_schema_extra={"uniqueItems": True},
    )

    _unit_is_publication_safe = field_validator("unit")(
        validate_publication_text
    )

    @field_validator(
        "reference_lower",
        "reference_upper",
        "minimum_gene_coverage",
    )
    @classmethod
    def numbers_are_finite(cls, value: FiniteNumber) -> FiniteNumber:
        checked = _finite(value)
        assert checked is not None
        return checked

    @field_validator(
        "applicable_assays",
        "eligible_evidence_states",
        "orthogonal_follow_up_refs",
    )
    @classmethod
    def lists_are_unique(cls, value: list[object]) -> list[object]:
        return _unique(value, "configured list")

    @model_validator(mode="after")
    def context_and_interval_are_coherent(self) -> Self:
        if float(self.reference_lower) > float(self.reference_upper):
            raise ValueError("reference interval lower bound exceeds upper bound")
        if self.analysis_scope is AnalysisScope.STATE_SPECIFIC and self.state_ref is None:
            raise ValueError("state_specific rule requires state_ref")
        if self.analysis_scope is AnalysisScope.WHOLE_PRODUCT and self.state_ref is not None:
            raise ValueError("whole_product rule cannot declare state_ref")
        return self


class ProgramAssessmentSpec(FrozenModel):
    object_version: Literal["0.1.0"]
    assessment_spec_id: str = Field(
        pattern=r"^program-assessment-spec:[A-Za-z0-9._:-]+$"
    )
    assessment_spec_version: str = Field(pattern=VERSION_PATTERN)
    product_definition_ref: VersionedObjectRef
    development_window_ref: VersionedObjectRef
    review_state: Literal["draft", "reviewed", "frozen"]
    rules: list[ProgramReviewRule] = Field(min_length=1)
    unmatched_observation_policy: Literal["report_unmatched"]
    no_flag_policy: Literal["cannot_resolve_without_validated_lod"]

    @field_validator("rules")
    @classmethod
    def rules_are_unique(cls, value: list[ProgramReviewRule]) -> list[ProgramReviewRule]:
        _unique([item.rule_id for item in value], "rules")
        return value

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.assessment_spec_id,
            object_version=self.assessment_spec_version,
        )


class ProgramObservation(FrozenModel):
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
                            "gene_coverage": {"type": "null"},
                        }
                    },
                    "else": {
                        "properties": {
                            "value": {"type": ["number", "integer"]},
                            "gene_coverage": {"type": ["number", "integer"]},
                        }
                    },
                }
            ]
        },
    )

    observation_id: str = Field(pattern=r"^program-observation:[A-Za-z0-9._:-]+$")
    rule_id: str = Field(pattern=r"^program-review-rule:[A-Za-z0-9._:-]+$")
    program_ref: VersionedObjectRef
    analysis_unit_ref: VersionedObjectRef
    evidence_family_id: PublishedRef
    independence_group: PublishedRef
    method_ref: VersionedObjectRef
    evidence_state: ProgramEvidenceState
    value: FiniteNumber | None
    gene_coverage: FiniteNumber | None = Field(default=None, ge=0, le=1)
    evidence_refs: list[PublishedRef] = Field(
        min_length=1,
        json_schema_extra={"uniqueItems": True},
    )

    @field_validator("value", "gene_coverage")
    @classmethod
    def numbers_are_finite(
        cls, value: FiniteNumber | None
    ) -> FiniteNumber | None:
        return _finite(value)

    @field_validator("evidence_refs")
    @classmethod
    def evidence_is_unique(cls, value: list[str]) -> list[str]:
        return _unique(value, "evidence_refs")

    @model_validator(mode="after")
    def numeric_state_is_coherent(self) -> Self:
        unavailable = {
            ProgramEvidenceState.MISSING,
            ProgramEvidenceState.UNKNOWN,
            ProgramEvidenceState.UNAVAILABLE,
        }
        if self.evidence_state in unavailable:
            if self.value is not None or self.gene_coverage is not None:
                raise ValueError("unavailable evidence cannot carry numeric values")
        elif self.value is None or self.gene_coverage is None:
            raise ValueError("numeric program evidence requires value and gene coverage")
        return self


class ProgramEvidenceBundle(FrozenModel):
    object_version: Literal["0.1.0"]
    evidence_bundle_id: str = Field(
        pattern=r"^program-evidence-bundle:[A-Za-z0-9._:-]+$"
    )
    evidence_bundle_version: str = Field(pattern=VERSION_PATTERN)
    product_case_ref: VersionedObjectRef
    product_definition_ref: VersionedObjectRef
    developmental_result_ref: VersionedObjectRef
    cell_state_profile_ref: VersionedObjectRef
    assay: Literal["scRNA-seq", "snRNA-seq"]
    observations: list[ProgramObservation] = Field(min_length=1)

    @field_validator("observations")
    @classmethod
    def observations_are_unique(
        cls, value: list[ProgramObservation]
    ) -> list[ProgramObservation]:
        _unique([item.observation_id for item in value], "observations")
        return value

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.evidence_bundle_id,
            object_version=self.evidence_bundle_version,
        )


class ProgramObservationAssessment(FrozenModel):
    observation_id: str = Field(pattern=r"^program-observation:[A-Za-z0-9._:-]+$")
    evidence_family_id: PublishedRef
    independence_group: PublishedRef
    method_ref: VersionedObjectRef
    evidence_state: ProgramEvidenceState
    value: FiniteNumber | None
    gene_coverage: FiniteNumber | None = Field(default=None, ge=0, le=1)
    reference_relation: ReferenceRelation | None
    included: StrictBool
    exclusion_reason: ReasonCode | None
    evidence_refs: list[PublishedRef] = Field(json_schema_extra={"uniqueItems": True})

    @field_validator("value", "gene_coverage")
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
    def inclusion_is_coherent(self) -> Self:
        if self.included and (
            self.exclusion_reason is not None or self.reference_relation is None
        ):
            raise ValueError("included observation must have a relation and no exclusion")
        if not self.included and self.exclusion_reason is None:
            raise ValueError("excluded observation requires a reason")
        return self


class TranscriptomicReviewFlag(FrozenModel):
    review_flag_state: ReviewFlagState
    flag_status: Literal["shadow"]
    rule_id: str = Field(pattern=r"^program-review-rule:[A-Za-z0-9._:-]+$")
    program_ref: VersionedObjectRef
    evidence_refs: list[PublishedRef] = Field(json_schema_extra={"uniqueItems": True})
    orthogonal_follow_up_refs: list[PublishedRef] = Field(
        json_schema_extra={"uniqueItems": True}
    )
    reason_codes: list[ReasonCode] = Field(json_schema_extra={"uniqueItems": True})

    @field_validator("evidence_refs", "orthogonal_follow_up_refs", "reason_codes")
    @classmethod
    def lists_are_unique_sorted(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("review flag lists must be unique and sorted")
        return value


class ProgramRuleResult(FrozenModel):
    rule_id: str = Field(pattern=r"^program-review-rule:[A-Za-z0-9._:-]+$")
    program_ref: VersionedObjectRef
    analysis_scope: AnalysisScope
    state_ref: VersionedObjectRef | None
    metric_name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9._:-]*$")
    unit: str = Field(min_length=1, max_length=120)
    reference_lower: FiniteNumber
    reference_upper: FiniteNumber
    observations: list[ProgramObservationAssessment]
    included_independence_group_count: StrictInt = Field(ge=0)
    triggering_independence_group_count: StrictInt = Field(ge=0)
    review_flag_state: ReviewFlagState
    evidence_refs: list[PublishedRef] = Field(json_schema_extra={"uniqueItems": True})
    reason_codes: list[ReasonCode] = Field(json_schema_extra={"uniqueItems": True})

    _unit_is_publication_safe = field_validator("unit")(
        validate_publication_text
    )

    @field_validator("reference_lower", "reference_upper")
    @classmethod
    def bounds_are_finite(cls, value: FiniteNumber) -> FiniteNumber:
        checked = _finite(value)
        assert checked is not None
        return checked

    @field_validator("evidence_refs", "reason_codes")
    @classmethod
    def lists_are_unique_sorted(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("program result lists must be unique and sorted")
        return value


class UnmatchedProgramObservation(FrozenModel):
    observation_id: str = Field(pattern=r"^program-observation:[A-Za-z0-9._:-]+$")
    rule_id: str = Field(pattern=r"^program-review-rule:[A-Za-z0-9._:-]+$")
    reason_code: Literal["program_rule_not_configured", "program_rule_binding_mismatch"]


class DeferredAssessmentProfile(FrozenModel):
    assessment_state: Literal["not_assessed"]
    reason_code: ReasonCode


class ProgramInputChecksums(FrozenModel):
    product_case: str = Field(pattern=SHA256_PATTERN)
    product_definition_card: str = Field(pattern=SHA256_PATTERN)
    program_assessment_spec: str = Field(pattern=SHA256_PATTERN)
    program_evidence_bundle: str = Field(pattern=SHA256_PATTERN)
    developmental_compatibility_result: str = Field(pattern=SHA256_PATTERN)
    qc_readiness_profile: str = Field(pattern=SHA256_PATTERN)


class ProliferationStressResponseProfile(FrozenModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {"result_state": {"const": "not_assessed"}},
                        "required": ["result_state"],
                    },
                    "then": {"properties": {"score_state": {"const": "unavailable"}}},
                    "else": {"properties": {"score_state": {"const": "shadow"}}},
                }
            ]
        },
    )

    object_version: Literal["0.1.0"]
    profile_id: str = Field(pattern=r"^proliferation-stress-profile:[a-f0-9]{16}$")
    tool_id: Literal["P0-06"]
    tool_version: str = Field(pattern=VERSION_PATTERN)
    product_case_ref: VersionedObjectRef
    product_definition_ref: VersionedObjectRef
    assessment_spec_ref: VersionedObjectRef
    evidence_bundle_ref: VersionedObjectRef
    developmental_result_ref: VersionedObjectRef
    qc_profile_ref: VersionedObjectRef
    input_sha256_by_role: ProgramInputChecksums
    result_state: Literal["complete", "partial", "not_assessed"]
    program_results: list[ProgramRuleResult]
    review_flags: list[TranscriptomicReviewFlag]
    unmatched_observations: list[UnmatchedProgramObservation]
    process_attribution: DeferredAssessmentProfile
    residual_pluripotency_lod: DeferredAssessmentProfile
    transcriptomic_cnv: DeferredAssessmentProfile
    evidence_refs: list[PublishedRef] = Field(json_schema_extra={"uniqueItems": True})
    reason_codes: list[ReasonCode] = Field(json_schema_extra={"uniqueItems": True})
    domain_score: None = None
    score_state: Literal[ScoreState.SHADOW, ScoreState.UNAVAILABLE]

    @field_validator("evidence_refs", "reason_codes")
    @classmethod
    def lists_are_unique_sorted(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("profile lists must be unique and sorted")
        return value

    @model_validator(mode="after")
    def result_is_coherent(self) -> Self:
        if len(self.program_results) != len(self.review_flags):
            raise ValueError("each configured rule requires one review flag")
        if [item.rule_id for item in self.program_results] != [
            item.rule_id for item in self.review_flags
        ]:
            raise ValueError("program results and review flags must align")
        assessed = any(
            item.review_flag_state is not ReviewFlagState.NOT_ASSESSED
            for item in self.program_results
        )
        if self.result_state == "not_assessed" and assessed:
            raise ValueError("not_assessed profile cannot contain assessed rules")
        if self.result_state != "not_assessed" and not assessed:
            raise ValueError("assessed profile requires at least one assessed rule")
        expected_score = (
            ScoreState.UNAVAILABLE
            if self.result_state == "not_assessed"
            else ScoreState.SHADOW
        )
        if self.score_state != expected_score:
            raise ValueError("score state does not match result state")
        return self


PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/program-assessment-spec/v0.1": ProgramAssessmentSpec,
    "bridge://schemas/program-evidence-bundle/v0.1": ProgramEvidenceBundle,
    "bridge://schemas/proliferation-stress-response-profile/v0.1": (
        ProliferationStressResponseProfile
    ),
}
