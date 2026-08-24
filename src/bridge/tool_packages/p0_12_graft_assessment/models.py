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
from bridge.toolkit.contracts import EvidenceState, FrozenModel, ScoreState


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


class GraftAvailability(StrEnum):
    NOT_PROVIDED = "not_provided"
    PROVIDED = "provided"


class GraftLinkageState(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    PROVIDED_UNLINKED = "provided_unlinked"
    PROVIDED_LINKED = "provided_linked"


class GraftAnalysisMode(StrEnum):
    UNAVAILABLE = "unavailable"
    DESCRIPTIVE_ONLY = "descriptive_only"


class ConfiguredIntervalRelation(StrEnum):
    BELOW_CONFIGURED_INTERVAL = "below_configured_interval"
    WITHIN_CONFIGURED_INTERVAL = "within_configured_interval"
    ABOVE_CONFIGURED_INTERVAL = "above_configured_interval"
    NO_INTERVAL_CONFIGURED = "no_interval_configured"
    UNAVAILABLE = "unavailable"


class GraftChannelRule(FrozenModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {
                            "interpretation_policy": {"const": "descriptive_only"}
                        },
                        "required": ["interpretation_policy"],
                    },
                    "then": {
                        "properties": {
                            "configured_lower_bound": {"type": "null"},
                            "configured_upper_bound": {"type": "null"},
                        }
                    },
                    "else": {
                        "properties": {
                            "configured_lower_bound": {
                                "type": ["number", "integer"]
                            },
                            "configured_upper_bound": {
                                "type": ["number", "integer"]
                            },
                        }
                    },
                }
            ]
        },
    )

    channel_id: str = Field(pattern=r"^graft-channel:[A-Za-z0-9._:-]+$")
    unit: str = Field(min_length=1, max_length=120)
    required: StrictBool
    eligible_evidence_states: list[EvidenceState] = Field(
        min_length=1,
        json_schema_extra={"uniqueItems": True},
    )
    minimum_independent_units: StrictInt = Field(gt=0)
    interpretation_policy: Literal["descriptive_only", "configured_interval"]
    configured_lower_bound: FiniteNumber | None = None
    configured_upper_bound: FiniteNumber | None = None

    _unit_is_publication_safe = field_validator("unit")(
        validate_publication_text
    )

    @field_validator("eligible_evidence_states")
    @classmethod
    def evidence_states_are_unique(
        cls, value: list[EvidenceState]
    ) -> list[EvidenceState]:
        return _unique(value, "eligible_evidence_states")

    @field_validator("configured_lower_bound", "configured_upper_bound")
    @classmethod
    def bounds_are_finite(
        cls, value: FiniteNumber | None
    ) -> FiniteNumber | None:
        return _finite(value)

    @model_validator(mode="after")
    def interpretation_is_coherent(self) -> Self:
        bounds = (self.configured_lower_bound, self.configured_upper_bound)
        if self.interpretation_policy == "descriptive_only":
            if any(value is not None for value in bounds):
                raise ValueError("descriptive_only rule cannot declare bounds")
        elif any(value is None for value in bounds):
            raise ValueError("configured_interval rule requires both bounds")
        elif float(self.configured_lower_bound) > float(
            self.configured_upper_bound
        ):
            raise ValueError("configured interval lower bound exceeds upper bound")
        return self


class GraftAssessmentSpec(FrozenModel):
    object_version: Literal["0.1.0"]
    assessment_spec_id: str = Field(
        pattern=r"^graft-assessment-spec:[A-Za-z0-9._:-]+$"
    )
    assessment_spec_version: str = Field(pattern=VERSION_PATTERN)
    product_case_ref: VersionedObjectRef
    measurement_spec_ref: VersionedObjectRef
    assay_ref: VersionedObjectRef
    sampling_context_ref: VersionedObjectRef
    reference_snapshot_ref: VersionedObjectRef
    algorithm_ref: VersionedObjectRef
    rules: list[GraftChannelRule] = Field(min_length=1)
    missing_observation_policy: Literal["report_unavailable"]
    confounded_design_policy: Literal["descriptive_only"]
    preparation_linkage_policy: Literal["explicit_evidence_only"]
    score_policy: Literal["unavailable"]

    @field_validator("rules")
    @classmethod
    def rules_are_unique(
        cls, value: list[GraftChannelRule]
    ) -> list[GraftChannelRule]:
        _unique([item.channel_id for item in value], "graft channel rules")
        return value

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.assessment_spec_id,
            object_version=self.assessment_spec_version,
        )


class GraftObservation(FrozenModel):
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
                    "else": {
                        "properties": {
                            "value": {"type": ["number", "integer"]}
                        }
                    },
                }
            ]
        },
    )

    observation_id: str = Field(pattern=r"^graft-observation:[A-Za-z0-9._:-]+$")
    channel_id: str = Field(pattern=r"^graft-channel:[A-Za-z0-9._:-]+$")
    unit: str = Field(min_length=1, max_length=120)
    value: FiniteNumber | None
    denominator: StrictInt | None = Field(default=None, gt=0)
    evidence_state: EvidenceState
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
    def state_and_value_are_coherent(self) -> Self:
        unavailable = {
            EvidenceState.MISSING,
            EvidenceState.UNKNOWN,
            EvidenceState.UNAVAILABLE,
        }
        if self.evidence_state in unavailable:
            if self.value is not None or self.denominator is not None:
                raise ValueError("unavailable observation cannot carry a value")
        elif self.value is None:
            raise ValueError("available observation requires a value")
        return self


class GraftUnitEvidence(FrozenModel):
    unit_ref: VersionedObjectRef
    animal_ref: VersionedObjectRef
    graft_ref: VersionedObjectRef
    timepoint_ref: VersionedObjectRef
    originating_preparation_ref: VersionedObjectRef | None = None
    linkage_evidence_refs: list[PublishedRef] = Field(
        default_factory=list,
        json_schema_extra={"uniqueItems": True},
    )
    observations: list[GraftObservation] = Field(min_length=1)

    @field_validator("linkage_evidence_refs")
    @classmethod
    def linkage_evidence_is_unique(cls, value: list[str]) -> list[str]:
        return _unique(value, "linkage_evidence_refs")

    @field_validator("observations")
    @classmethod
    def observations_are_unique(
        cls, value: list[GraftObservation]
    ) -> list[GraftObservation]:
        _unique([item.observation_id for item in value], "graft observations")
        _unique([item.channel_id for item in value], "unit channels")
        return value

    @model_validator(mode="after")
    def linkage_is_explicit(self) -> Self:
        has_preparation = self.originating_preparation_ref is not None
        has_evidence = bool(self.linkage_evidence_refs)
        if has_preparation != has_evidence:
            raise ValueError(
                "preparation linkage requires both reference and evidence"
            )
        return self


class GraftEvidenceBundle(FrozenModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {
                            "graft_availability": {"const": "not_provided"}
                        },
                        "required": ["graft_availability"],
                    },
                    "then": {
                        "properties": {
                            "graft_case_ref": {"type": "null"},
                            "measurement_spec_ref": {"type": "null"},
                            "assay_ref": {"type": "null"},
                            "sampling_context_ref": {"type": "null"},
                            "reference_snapshot_ref": {"type": "null"},
                            "algorithm_ref": {"type": "null"},
                            "design_constraint_refs": {"maxItems": 0},
                            "units": {"maxItems": 0},
                        }
                    },
                    "else": {
                        "properties": {
                            "graft_case_ref": {"type": "object"},
                            "measurement_spec_ref": {"type": "object"},
                            "assay_ref": {"type": "object"},
                            "sampling_context_ref": {"type": "object"},
                            "reference_snapshot_ref": {"type": "object"},
                            "algorithm_ref": {"type": "object"},
                        }
                    },
                }
            ]
        },
    )

    object_version: Literal["0.1.0"]
    evidence_bundle_id: str = Field(
        pattern=r"^graft-evidence-bundle:[A-Za-z0-9._:-]+$"
    )
    evidence_bundle_version: str = Field(pattern=VERSION_PATTERN)
    graft_availability: GraftAvailability
    product_case_ref: VersionedObjectRef
    graft_case_ref: VersionedObjectRef | None = None
    measurement_spec_ref: VersionedObjectRef | None = None
    assay_ref: VersionedObjectRef | None = None
    sampling_context_ref: VersionedObjectRef | None = None
    reference_snapshot_ref: VersionedObjectRef | None = None
    algorithm_ref: VersionedObjectRef | None = None
    design_constraint_refs: list[VersionedObjectRef] = Field(default_factory=list)
    units: list[GraftUnitEvidence] = Field(default_factory=list)

    @field_validator("design_constraint_refs")
    @classmethod
    def design_constraints_are_unique(
        cls, value: list[VersionedObjectRef]
    ) -> list[VersionedObjectRef]:
        _unique([item.ref for item in value], "design_constraint_refs")
        return value

    @field_validator("units")
    @classmethod
    def units_are_independent(
        cls, value: list[GraftUnitEvidence]
    ) -> list[GraftUnitEvidence]:
        _unique([item.unit_ref.ref for item in value], "graft units")
        _unique(
            [
                (item.animal_ref.ref, item.graft_ref.ref, item.timepoint_ref.ref)
                for item in value
            ],
            "animal/graft/timepoint units",
        )
        return value

    @model_validator(mode="after")
    def availability_is_coherent(self) -> Self:
        context = (
            self.graft_case_ref,
            self.measurement_spec_ref,
            self.assay_ref,
            self.sampling_context_ref,
            self.reference_snapshot_ref,
            self.algorithm_ref,
        )
        if self.graft_availability is GraftAvailability.NOT_PROVIDED:
            if any(value is not None for value in context):
                raise ValueError("not_provided bundle cannot declare graft context")
            if self.design_constraint_refs or self.units:
                raise ValueError("not_provided bundle cannot carry graft evidence")
        elif any(value is None for value in context):
            raise ValueError("provided bundle requires complete graft context")
        return self

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.evidence_bundle_id,
            object_version=self.evidence_bundle_version,
        )


class GraftChannelSummary(FrozenModel):
    channel_id: str = Field(pattern=r"^graft-channel:[A-Za-z0-9._:-]+$")
    unit: str = Field(min_length=1, max_length=120)
    required: StrictBool
    minimum_independent_units: StrictInt = Field(gt=0)
    eligible_unit_count: StrictInt = Field(ge=0)
    mean: FiniteNumber | None
    minimum: FiniteNumber | None
    maximum: FiniteNumber | None
    configured_lower_bound: FiniteNumber | None
    configured_upper_bound: FiniteNumber | None
    configured_interval_relation: ConfiguredIntervalRelation
    result_state: Literal["available", "unavailable"]
    evidence_refs: list[PublishedRef] = Field(json_schema_extra={"uniqueItems": True})
    reason_codes: list[ReasonCode] = Field(json_schema_extra={"uniqueItems": True})

    _unit_is_publication_safe = field_validator("unit")(
        validate_publication_text
    )

    @field_validator(
        "mean",
        "minimum",
        "maximum",
        "configured_lower_bound",
        "configured_upper_bound",
    )
    @classmethod
    def numbers_are_finite(
        cls, value: FiniteNumber | None
    ) -> FiniteNumber | None:
        return _finite(value)

    @field_validator("evidence_refs", "reason_codes")
    @classmethod
    def strings_are_unique_sorted(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("summary lists must be unique and sorted")
        return value

    @model_validator(mode="after")
    def summary_is_coherent(self) -> Self:
        values = (self.mean, self.minimum, self.maximum)
        if self.result_state == "unavailable":
            if self.eligible_unit_count != 0 or any(
                value is not None for value in values
            ):
                raise ValueError("unavailable summary cannot contain values")
            if self.configured_interval_relation is not ConfiguredIntervalRelation.UNAVAILABLE:
                raise ValueError("unavailable summary requires unavailable relation")
        else:
            if self.eligible_unit_count == 0 or any(
                value is None for value in values
            ):
                raise ValueError("available summary requires values")
            if (
                self.configured_lower_bound is None
                and self.configured_upper_bound is None
            ):
                if (
                    self.configured_interval_relation
                    is not ConfiguredIntervalRelation.NO_INTERVAL_CONFIGURED
                ):
                    raise ValueError("unbounded summary requires no-interval relation")
            elif (
                self.configured_lower_bound is None
                or self.configured_upper_bound is None
            ):
                raise ValueError("configured output interval requires both bounds")
            else:
                assert self.mean is not None
                expected = _configured_relation(
                    float(self.mean),
                    float(self.configured_lower_bound),
                    float(self.configured_upper_bound),
                )
                if self.configured_interval_relation is not expected:
                    raise ValueError("configured interval relation does not match mean")
        return self


class PreparationGraftLinkage(FrozenModel):
    unit_ref: VersionedObjectRef
    originating_preparation_ref: VersionedObjectRef
    evidence_refs: list[PublishedRef] = Field(
        min_length=1,
        json_schema_extra={"uniqueItems": True},
    )

    @field_validator("evidence_refs")
    @classmethod
    def evidence_is_unique_sorted(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("linkage evidence must be unique and sorted")
        return value


class UnmatchedGraftObservation(FrozenModel):
    unit_ref: VersionedObjectRef
    observation_id: str = Field(pattern=r"^graft-observation:[A-Za-z0-9._:-]+$")
    channel_id: str = Field(pattern=r"^graft-channel:[A-Za-z0-9._:-]+$")
    reason_code: Literal["graft_channel_not_configured"]


class GraftInputChecksums(FrozenModel):
    graft_assessment_spec: str = Field(pattern=SHA256_PATTERN)
    graft_evidence_bundle: str = Field(pattern=SHA256_PATTERN)


class GraftAssessment(FrozenModel):
    object_version: Literal["0.1.0"]
    assessment_id: str = Field(pattern=r"^graft-assessment:[a-f0-9]{16}$")
    tool_id: Literal["P0-12"]
    tool_version: str = Field(pattern=VERSION_PATTERN)
    assessment_spec_ref: VersionedObjectRef
    evidence_bundle_ref: VersionedObjectRef
    product_case_ref: VersionedObjectRef
    graft_case_ref: VersionedObjectRef | None
    measurement_spec_ref: VersionedObjectRef | None
    input_sha256_by_role: GraftInputChecksums
    result_state: Literal["complete", "partial", "not_assessed", "not_provided"]
    graft_availability: GraftAvailability
    linkage_state: GraftLinkageState
    analysis_mode: GraftAnalysisMode
    independent_unit_count: StrictInt = Field(ge=0)
    design_constraint_refs: list[VersionedObjectRef]
    channel_summaries: list[GraftChannelSummary]
    preparation_linkages: list[PreparationGraftLinkage]
    unmatched_observations: list[UnmatchedGraftObservation]
    evidence_refs: list[PublishedRef] = Field(json_schema_extra={"uniqueItems": True})
    reason_codes: list[ReasonCode] = Field(json_schema_extra={"uniqueItems": True})
    product_backfill: Literal["not_performed"]
    graft_score: None = None
    domain_score: None = None
    score_state: Literal[ScoreState.SHADOW, ScoreState.UNAVAILABLE]

    @field_validator("design_constraint_refs")
    @classmethod
    def design_constraints_are_sorted(
        cls, value: list[VersionedObjectRef]
    ) -> list[VersionedObjectRef]:
        refs = [item.ref for item in value]
        if refs != sorted(set(refs)):
            raise ValueError("design constraints must be unique and sorted")
        return value

    @field_validator("channel_summaries")
    @classmethod
    def channel_summaries_are_sorted(
        cls, value: list[GraftChannelSummary]
    ) -> list[GraftChannelSummary]:
        ids = [item.channel_id for item in value]
        if ids != sorted(set(ids)):
            raise ValueError("channel summaries must be unique and sorted")
        return value

    @field_validator("evidence_refs", "reason_codes")
    @classmethod
    def strings_are_unique_sorted(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("assessment lists must be unique and sorted")
        return value

    @model_validator(mode="after")
    def assessment_is_coherent(self) -> Self:
        available = [
            item for item in self.channel_summaries if item.result_state == "available"
        ]
        if self.graft_availability is GraftAvailability.NOT_PROVIDED:
            if self.result_state != "not_provided":
                raise ValueError("absent graft requires not_provided result")
            if any(
                (
                    self.graft_case_ref is not None,
                    self.measurement_spec_ref is not None,
                    self.independent_unit_count != 0,
                    bool(self.channel_summaries),
                    bool(self.preparation_linkages),
                    bool(self.unmatched_observations),
                )
            ):
                raise ValueError("not_provided result cannot contain graft evidence")
            if self.linkage_state is not GraftLinkageState.NOT_APPLICABLE:
                raise ValueError("not_provided result has no linkage")
            if self.analysis_mode is not GraftAnalysisMode.UNAVAILABLE:
                raise ValueError("not_provided result has unavailable analysis")
        else:
            if self.graft_case_ref is None or self.measurement_spec_ref is None:
                raise ValueError("provided result requires graft context")
            if self.result_state == "not_provided":
                raise ValueError("provided graft cannot return not_provided")
            if self.analysis_mode is not GraftAnalysisMode.DESCRIPTIVE_ONLY:
                raise ValueError("callable graft slice is descriptive only")
            if self.result_state == "not_assessed" and available:
                raise ValueError("not_assessed result cannot contain available channels")
            if self.result_state != "not_assessed" and not available:
                raise ValueError("assessed result requires an available channel")
            if self.result_state == "complete" and (
                self.unmatched_observations
                or any(
                    item.required
                    and (
                        item.result_state != "available"
                        or item.eligible_unit_count
                        < item.minimum_independent_units
                    )
                    for item in self.channel_summaries
                )
            ):
                raise ValueError("complete result requires all configured evidence")
            fully_linked = self.independent_unit_count > 0 and len(
                self.preparation_linkages
            ) == self.independent_unit_count
            if (
                self.linkage_state is GraftLinkageState.PROVIDED_LINKED
            ) != fully_linked:
                raise ValueError("linkage state does not match explicit records")
        expected_score_state = (
            ScoreState.SHADOW if available else ScoreState.UNAVAILABLE
        )
        if self.score_state != expected_score_state:
            raise ValueError("score state does not match available evidence")
        return self


def _configured_relation(
    mean: float, lower: float, upper: float
) -> ConfiguredIntervalRelation:
    if mean < lower:
        return ConfiguredIntervalRelation.BELOW_CONFIGURED_INTERVAL
    if mean > upper:
        return ConfiguredIntervalRelation.ABOVE_CONFIGURED_INTERVAL
    return ConfiguredIntervalRelation.WITHIN_CONFIGURED_INTERVAL


PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/graft-assessment-spec/v0.1": GraftAssessmentSpec,
    "bridge://schemas/graft-evidence-bundle/v0.1": GraftEvidenceBundle,
    "bridge://schemas/graft-assessment/v0.1": GraftAssessment,
}
