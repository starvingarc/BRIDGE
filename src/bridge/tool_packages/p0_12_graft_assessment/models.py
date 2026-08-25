from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, StrictFloat, StrictInt, field_validator, model_validator

from bridge.toolkit.contracts import FrozenModel


SafeId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")]
PublishedRef = Annotated[
    str,
    Field(pattern=r"^[A-Za-z][A-Za-z0-9+.-]*(?::[^\s]+)?$"),
]
NonNegativeInt = Annotated[StrictInt, Field(ge=0)]


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def _unique(values: list[object], field_name: str) -> list[object]:
    if len(values) != len({str(value) for value in values}):
        raise ValueError(f"{field_name} must not contain duplicates")
    return values


class GraftResultState(StrEnum):
    NOT_PROVIDED = "not_provided"
    CANDIDATE = "candidate"


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


class GraftEvidenceState(StrEnum):
    UNAVAILABLE = "unavailable"
    SHADOW = "shadow"


class EvidenceStateClass(StrEnum):
    USABLE = "usable"
    LIMITED = "limited"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    ALERT = "alert"


class GraftCase(FrozenModel):
    object_version: Literal["0.1.0"]
    graft_case_id: SafeId
    assay_id: SafeId
    specimen_id: SafeId
    animal_id: SafeId | None = None
    post_transplant_timepoint: SafeId | None = None
    biological_replicate_id: SafeId | None = None
    originating_preparation_id: SafeId | None = None
    linkage_evidence_refs: list[PublishedRef] = Field(default_factory=list)
    declared_confounder_refs: list[PublishedRef] = Field(default_factory=list)
    provenance_refs: list[PublishedRef] = Field(min_length=1)
    created_at: datetime

    @field_validator(
        "linkage_evidence_refs", "declared_confounder_refs", "provenance_refs"
    )
    @classmethod
    def refs_are_unique(cls, value: list[str], info: object) -> list[str]:
        return _unique(value, getattr(info, "field_name", "references"))

    @field_validator("created_at")
    @classmethod
    def created_at_is_aware(cls, value: datetime) -> datetime:
        return _aware_utc(value)


class GraftEvidenceRoleRule(FrozenModel):
    role_id: SafeId
    required: bool
    allowed_metric_ids: list[SafeId] = Field(min_length=1)
    allowed_states: list[SafeId] = Field(min_length=1)

    @field_validator("allowed_metric_ids", "allowed_states")
    @classmethod
    def values_are_unique(cls, value: list[str], info: object) -> list[str]:
        return _unique(value, getattr(info, "field_name", "values"))


class GraftAssessmentSpec(FrozenModel):
    object_version: Literal["0.1.0"]
    assessment_spec_id: SafeId
    role_rules: list[GraftEvidenceRoleRule] = Field(min_length=1)
    state_classes: dict[SafeId, EvidenceStateClass] = Field(min_length=1)
    method_ids: list[SafeId] = Field(min_length=1)
    provenance_refs: list[PublishedRef] = Field(min_length=1)

    @field_validator("method_ids", "provenance_refs")
    @classmethod
    def lists_are_unique(cls, value: list[str], info: object) -> list[str]:
        return _unique(value, getattr(info, "field_name", "values"))

    @model_validator(mode="after")
    def role_and_state_contract_is_complete(self) -> Self:
        role_ids = [rule.role_id for rule in self.role_rules]
        _unique(role_ids, "role_rules")
        declared_states = set(self.state_classes)
        used_states = {
            state for rule in self.role_rules for state in rule.allowed_states
        }
        if not used_states.issubset(declared_states):
            raise ValueError("every allowed state requires a state_classes entry")
        return self


class GraftEvidenceRecord(FrozenModel):
    evidence_id: SafeId
    role_id: SafeId
    metric_id: SafeId
    state: SafeId
    value: StrictInt | StrictFloat | None = None
    numerator: NonNegativeInt | None = None
    denominator: NonNegativeInt | None = None
    source_run_ref: PublishedRef
    provenance_refs: list[PublishedRef] = Field(min_length=1)

    @field_validator("provenance_refs")
    @classmethod
    def provenance_is_unique(cls, value: list[str]) -> list[str]:
        return _unique(value, "provenance_refs")

    @model_validator(mode="after")
    def numerator_and_denominator_are_paired(self) -> Self:
        if (self.numerator is None) != (self.denominator is None):
            raise ValueError("numerator and denominator must be paired")
        if self.denominator == 0:
            raise ValueError("denominator must be positive when provided")
        return self


class GraftEvidenceBundle(FrozenModel):
    object_version: Literal["0.1.0"]
    evidence_bundle_id: SafeId
    graft_case_ref: SafeId
    assessment_spec_ref: SafeId
    records: list[GraftEvidenceRecord] = Field(min_length=1)
    provenance_refs: list[PublishedRef] = Field(min_length=1)
    created_at: datetime

    @field_validator("records")
    @classmethod
    def records_are_unique(
        cls, value: list[GraftEvidenceRecord]
    ) -> list[GraftEvidenceRecord]:
        _unique([record.evidence_id for record in value], "records")
        return value

    @field_validator("provenance_refs")
    @classmethod
    def provenance_is_unique(cls, value: list[str]) -> list[str]:
        return _unique(value, "provenance_refs")

    @field_validator("created_at")
    @classmethod
    def created_at_is_aware(cls, value: datetime) -> datetime:
        return _aware_utc(value)


class GraftSourceBinding(FrozenModel):
    input_id: SafeId
    role: SafeId
    schema_ref: str = Field(min_length=1)
    object_version: Literal["0.1.0"]
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class GraftRoleSummary(FrozenModel):
    role_id: SafeId
    record_count: NonNegativeInt
    metric_ids: list[SafeId]
    evidence_states: list[SafeId]
    state_class_counts: dict[EvidenceStateClass, NonNegativeInt]
    evidence_ids: list[SafeId]


class PreparationGraftLinkage(FrozenModel):
    originating_preparation_id: SafeId
    linkage_evidence_refs: list[PublishedRef] = Field(min_length=1)
    descriptive_only: Literal[True] = True


class GraftAssessmentResult(FrozenModel):
    result_id: SafeId
    result_version: Literal["0.1.0"]
    state: GraftResultState
    graft_availability: GraftAvailability
    graft_case_ref: SafeId | None = None
    assessment_spec_ref: SafeId | None = None
    evidence_bundle_ref: SafeId | None = None
    linkage_state: GraftLinkageState
    analysis_mode: GraftAnalysisMode
    evidence_state: GraftEvidenceState
    source_bindings: list[GraftSourceBinding]
    role_summaries: list[GraftRoleSummary]
    missing_metadata: list[
        Literal[
            "animal_id",
            "post_transplant_timepoint",
            "biological_replicate_id",
        ]
    ]
    confounder_refs: list[PublishedRef]
    required_roles_missing: list[SafeId]
    preparation_linkage: PreparationGraftLinkage | None = None
    reason_codes: list[SafeId]
    pretransplant_evidence_effect: Literal["none"] = "none"
    domain_score: None = None
    score_state: Literal["unavailable"] = "unavailable"
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def created_at_is_aware(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def state_payload_is_coherent(self) -> Self:
        refs = (
            self.graft_case_ref,
            self.assessment_spec_ref,
            self.evidence_bundle_ref,
        )
        if self.state is GraftResultState.NOT_PROVIDED:
            if any(ref is not None for ref in refs) or any(
                (
                    self.source_bindings,
                    self.role_summaries,
                    self.missing_metadata,
                    self.confounder_refs,
                    self.required_roles_missing,
                )
            ):
                raise ValueError("not_provided result cannot carry graft evidence")
            if (
                self.graft_availability is not GraftAvailability.NOT_PROVIDED
                or self.linkage_state is not GraftLinkageState.NOT_APPLICABLE
                or self.analysis_mode is not GraftAnalysisMode.UNAVAILABLE
                or self.evidence_state is not GraftEvidenceState.UNAVAILABLE
                or self.preparation_linkage is not None
            ):
                raise ValueError("not_provided result states are inconsistent")
        else:
            if any(ref is None for ref in refs) or len(self.source_bindings) != 3:
                raise ValueError("candidate result requires three bound inputs")
            if (
                self.graft_availability is not GraftAvailability.PROVIDED
                or self.analysis_mode is not GraftAnalysisMode.DESCRIPTIVE_ONLY
                or self.evidence_state is not GraftEvidenceState.SHADOW
            ):
                raise ValueError("candidate result must remain descriptive shadow evidence")
            if (self.preparation_linkage is None) != (
                self.linkage_state is not GraftLinkageState.PROVIDED_LINKED
            ):
                raise ValueError("preparation linkage payload does not match linkage_state")
        return self


PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/graft-case/v0.1": GraftCase,
    "bridge://schemas/graft-assessment-spec/v0.1": GraftAssessmentSpec,
    "bridge://schemas/graft-evidence-bundle/v0.1": GraftEvidenceBundle,
    "bridge://schemas/graft-assessment-result/v0.1": GraftAssessmentResult,
}
