from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, StrictFloat, StrictInt, field_validator, model_validator

from bridge.tool_packages._configurable_contracts import VersionedObjectRef
from bridge.toolkit.contracts import FrozenModel


SafeId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")]
PublishedRef = Annotated[
    str,
    Field(pattern=r"^[A-Za-z][A-Za-z0-9+.-]*(?::[^\s]+)?$"),
]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonNegativeInt = Annotated[StrictInt, Field(ge=0)]
GENE_PATTERN = r"^[^\s]+$"


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def _unique(values: list[object], field_name: str) -> list[object]:
    if len(values) != len({str(value) for value in values}):
        raise ValueError(f"{field_name} must not contain duplicates")
    return values


class AnalysisScope(StrEnum):
    WHOLE_PRODUCT = "whole_product"
    STATE_SPECIFIC = "state_specific"


class ProtocolMetadataState(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    NOT_PROVIDED = "not_provided"


class BatchConfoundingState(StrEnum):
    NOT_CONFOUNDED = "not_confounded"
    FULLY_CONFOUNDED = "fully_confounded"
    NOT_ASSESSED = "not_assessed"


class ReviewFlagState(StrEnum):
    TRANSCRIPTOMIC_REVIEW_FLAG = "transcriptomic_review_flag"
    NOT_DETECTED_ABOVE_LOD = "not_detected_above_lod"
    CANNOT_RESOLVE = "cannot_resolve"
    NOT_ASSESSED = "not_assessed"


class ProgramApplicabilityState(StrEnum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"


class ProgramAvailabilityState(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    CANNOT_RESOLVE = "cannot_resolve"


class ProcessAttributionState(StrEnum):
    CONDITIONAL_ASSOCIATION = "conditional_association"
    CANNOT_ATTRIBUTE = "cannot_attribute"
    NOT_REQUESTED = "not_requested"


class ProcessAttributionRule(FrozenModel):
    minimum_independent_replicates: StrictInt = Field(ge=1)
    minimum_comparable_groups: StrictInt = Field(ge=1)


class ProgramGeneTarget(FrozenModel):
    gene: str = Field(pattern=GENE_PATTERN)
    weight: StrictFloat

    @field_validator("weight")
    @classmethod
    def weight_is_nonzero(cls, value: float) -> float:
        if not math.isfinite(value) or value == 0.0:
            raise ValueError("program target weight must be finite and nonzero")
        return value


class ProgramRule(FrozenModel):
    program_id: SafeId
    gene_set_ref: PublishedRef
    gene_set_sha256: Sha256
    targets: list[ProgramGeneTarget] = Field(default_factory=list)
    s_genes: list[str] = Field(default_factory=list)
    g2m_genes: list[str] = Field(default_factory=list)
    allowed_analysis_scopes: list[AnalysisScope] = Field(min_length=1)
    allowed_state_ids: list[SafeId] = Field(default_factory=list)
    allowed_stage_ids: list[SafeId] = Field(min_length=1)
    allowed_metric_ids: list[SafeId] = Field(min_length=1)
    minimum_gene_coverage: StrictFloat = Field(ge=0.0, le=1.0)
    allowed_lod_states: list[SafeId] = Field(min_length=1)
    resolvable_lod_states: list[SafeId] = Field(min_length=1)
    review_outcomes: dict[SafeId, ReviewFlagState] = Field(min_length=1)
    orthogonal_follow_up_refs: list[PublishedRef] = Field(default_factory=list)
    provenance_refs: list[PublishedRef] = Field(min_length=1)

    @field_validator(
        "allowed_analysis_scopes",
        "allowed_state_ids",
        "allowed_stage_ids",
        "allowed_metric_ids",
        "allowed_lod_states",
        "resolvable_lod_states",
        "orthogonal_follow_up_refs",
        "provenance_refs",
    )
    @classmethod
    def lists_are_unique(cls, value: list[object], info: object) -> list[object]:
        return _unique(value, getattr(info, "field_name", "values"))

    @field_validator("targets")
    @classmethod
    def target_genes_are_unique(
        cls, value: list[ProgramGeneTarget]
    ) -> list[ProgramGeneTarget]:
        _unique([item.gene for item in value], "program target genes")
        return value

    @field_validator("s_genes", "g2m_genes")
    @classmethod
    def phase_genes_are_valid(cls, value: list[str]) -> list[str]:
        _unique(value, "cell-cycle genes")
        if any(not gene or any(char.isspace() for char in gene) for gene in value):
            raise ValueError("cell-cycle genes must be non-empty tokens")
        return value

    @model_validator(mode="after")
    def external_rule_is_complete(self) -> Self:
        if (
            AnalysisScope.STATE_SPECIFIC in self.allowed_analysis_scopes
            and not self.allowed_state_ids
        ):
            raise ValueError("state_specific programs require allowed_state_ids")
        if not set(self.resolvable_lod_states).issubset(self.allowed_lod_states):
            raise ValueError("resolvable_lod_states must be allowed")
        has_phase_content = bool(self.s_genes or self.g2m_genes)
        if self.targets and has_phase_content:
            raise ValueError("program rule cannot mix weighted and phase gene content")
        if bool(self.s_genes) != bool(self.g2m_genes):
            raise ValueError("cell-cycle rule requires both S and G2M gene sets")
        if set(self.s_genes).intersection(self.g2m_genes):
            raise ValueError("S and G2M gene sets must not overlap")
        return self


def program_rule_content_sha256(rule: ProgramRule) -> str | None:
    if rule.targets:
        payload = {
            "content_type": "weighted_program_targets",
            "targets": [
                {"gene": item.gene, "weight": item.weight}
                for item in sorted(rule.targets, key=lambda item: item.gene)
            ],
        }
    elif rule.s_genes and rule.g2m_genes:
        payload = {
            "content_type": "cell_cycle_phase_genes",
            "s_genes": sorted(rule.s_genes),
            "g2m_genes": sorted(rule.g2m_genes),
        }
    else:
        return None
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class ProgramSpec(FrozenModel):
    object_version: Literal["0.1.0"]
    program_spec_id: SafeId
    program_spec_version: SafeId
    product_definition_ref: VersionedObjectRef
    development_window_ref: VersionedObjectRef
    aggregation_method_ids: list[SafeId] = Field(min_length=1)
    attribution_rule: ProcessAttributionRule
    program_rules: list[ProgramRule] = Field(min_length=1)
    provenance_refs: list[PublishedRef] = Field(min_length=1)

    @field_validator("aggregation_method_ids", "provenance_refs")
    @classmethod
    def lists_are_unique(cls, value: list[str], info: object) -> list[str]:
        return _unique(value, getattr(info, "field_name", "values"))

    @field_validator("program_rules")
    @classmethod
    def programs_are_unique(cls, value: list[ProgramRule]) -> list[ProgramRule]:
        _unique([item.program_id for item in value], "program_rules")
        return value

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.program_spec_id,
            object_version=self.program_spec_version,
        )


class ProtocolIR(FrozenModel):
    object_version: Literal["0.1.0"]
    protocol_context_id: SafeId
    product_case_ref: VersionedObjectRef
    metadata_state: ProtocolMetadataState
    batch_confounding_state: BatchConfoundingState
    independent_replicate_count: NonNegativeInt
    comparable_group_count: NonNegativeInt
    declared_process_step_ids: list[SafeId] = Field(default_factory=list)
    provenance_refs: list[PublishedRef] = Field(min_length=1)
    created_at: datetime

    @field_validator("declared_process_step_ids", "provenance_refs")
    @classmethod
    def lists_are_unique(cls, value: list[str], info: object) -> list[str]:
        return _unique(value, getattr(info, "field_name", "values"))

    @field_validator("created_at")
    @classmethod
    def created_at_is_aware(cls, value: datetime) -> datetime:
        return _aware_utc(value)


class ProgramEvidenceRecord(FrozenModel):
    evidence_id: SafeId
    program_id: SafeId
    analysis_scope: AnalysisScope
    cell_state_id: SafeId | None = None
    stage_id: SafeId
    metric_id: SafeId
    value: StrictInt | StrictFloat | None = None
    unit: SafeId | None = None
    numerator: NonNegativeInt | None = None
    denominator: NonNegativeInt | None = None
    gene_coverage: StrictFloat = Field(ge=0.0, le=1.0)
    lod_state: SafeId
    evidence_state: SafeId
    process_step_ids: list[SafeId] = Field(default_factory=list)
    source_run_ref: PublishedRef
    provenance_refs: list[PublishedRef] = Field(min_length=1)

    @field_validator("process_step_ids", "provenance_refs")
    @classmethod
    def lists_are_unique(cls, value: list[str], info: object) -> list[str]:
        return _unique(value, getattr(info, "field_name", "values"))

    @model_validator(mode="after")
    def scope_and_counts_are_coherent(self) -> Self:
        if (self.analysis_scope is AnalysisScope.STATE_SPECIFIC) != (
            self.cell_state_id is not None
        ):
            raise ValueError("state_specific scope requires exactly one cell_state_id")
        if (self.numerator is None) != (self.denominator is None):
            raise ValueError("numerator and denominator must be paired")
        if self.denominator == 0:
            raise ValueError("denominator must be positive when provided")
        if (
            self.numerator is not None
            and self.denominator is not None
            and self.numerator > self.denominator
        ):
            raise ValueError("numerator cannot exceed denominator")
        return self


class ProgramEvidenceBundle(FrozenModel):
    object_version: Literal["0.1.0"]
    evidence_bundle_id: SafeId
    product_case_ref: VersionedObjectRef
    product_case_sha256: Sha256
    product_definition_ref: VersionedObjectRef
    product_definition_sha256: Sha256
    development_window_ref: VersionedObjectRef
    development_window_sha256: Sha256
    program_spec_ref: VersionedObjectRef
    program_spec_sha256: Sha256
    cell_state_profile_ref: SafeId
    cell_state_profile_sha256: Sha256
    protocol_context_ref: SafeId
    protocol_context_sha256: Sha256
    records: list[ProgramEvidenceRecord] = Field(min_length=1)
    provenance_refs: list[PublishedRef] = Field(min_length=1)
    created_at: datetime

    @field_validator("records")
    @classmethod
    def records_are_unique(
        cls, value: list[ProgramEvidenceRecord]
    ) -> list[ProgramEvidenceRecord]:
        _unique([item.evidence_id for item in value], "records")
        return value

    @field_validator("provenance_refs")
    @classmethod
    def provenance_is_unique(cls, value: list[str]) -> list[str]:
        return _unique(value, "provenance_refs")

    @field_validator("created_at")
    @classmethod
    def created_at_is_aware(cls, value: datetime) -> datetime:
        return _aware_utc(value)


class ProgramSourceBinding(FrozenModel):
    input_id: SafeId
    role: SafeId
    schema_ref: str = Field(min_length=1)
    object_version: SafeId
    source_sha256: Sha256


class ProgramEvidenceSummary(FrozenModel):
    evidence_id: SafeId
    program_id: SafeId
    analysis_scope: AnalysisScope
    cell_state_id: SafeId | None = None
    stage_id: SafeId
    metric_id: SafeId
    value: StrictInt | StrictFloat | None = None
    unit: SafeId | None = None
    numerator: NonNegativeInt | None = None
    denominator: NonNegativeInt | None = None
    gene_coverage: StrictFloat = Field(ge=0.0, le=1.0)
    minimum_gene_coverage: StrictFloat = Field(ge=0.0, le=1.0)
    lod_state: SafeId
    evidence_state: SafeId
    applicability: ProgramApplicabilityState
    availability: ProgramAvailabilityState
    process_attribution: ProcessAttributionState
    process_step_ids: list[SafeId]
    reason_codes: list[SafeId]


class TranscriptomicReviewFlag(FrozenModel):
    flag_id: SafeId
    evidence_id: SafeId
    program_id: SafeId
    analysis_scope: AnalysisScope
    cell_state_id: SafeId | None = None
    stage_id: SafeId
    review_flag_state: ReviewFlagState
    flag_status: Literal["shadow"] = "shadow"
    applicability: ProgramApplicabilityState
    availability: ProgramAvailabilityState
    process_attribution: ProcessAttributionState
    orthogonal_follow_up_refs: list[PublishedRef]
    reason_codes: list[SafeId]
    safety_interpretation: Literal["not_evidence_of_safety"] = (
        "not_evidence_of_safety"
    )


class ProliferationStressResponseProfile(FrozenModel):
    profile_id: SafeId
    profile_version: Literal["0.1.0"]
    product_case_ref: VersionedObjectRef
    product_definition_ref: VersionedObjectRef
    development_window_ref: VersionedObjectRef
    program_spec_ref: VersionedObjectRef
    cell_state_profile_ref: SafeId
    protocol_context_ref: SafeId
    source_bindings: list[ProgramSourceBinding] = Field(min_length=7, max_length=7)
    analysis_mode: Literal["descriptive_only"] = "descriptive_only"
    evidence_state: Literal["shadow"] = "shadow"
    process_attribution_state: ProcessAttributionState
    program_results: list[ProgramEvidenceSummary]
    review_flags: list[TranscriptomicReviewFlag]
    reason_codes: list[SafeId]
    untriggered_interpretation: Literal["not_evidence_of_safety"] = (
        "not_evidence_of_safety"
    )
    domain_score: None = None
    score_state: Literal["unavailable"] = "unavailable"
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def created_at_is_aware(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def outputs_align(self) -> Self:
        if len(self.program_results) != len(self.review_flags):
            raise ValueError("every program result requires one review flag")
        if [item.evidence_id for item in self.program_results] != [
            item.evidence_id for item in self.review_flags
        ]:
            raise ValueError("program results and review flags must align")
        return self


PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/program-spec/v0.1": ProgramSpec,
    "bridge://schemas/protocol-ir/v0.1": ProtocolIR,
    "bridge://schemas/program-evidence-bundle/v0.1": ProgramEvidenceBundle,
    "bridge://schemas/transcriptomic-review-flag/v0.1": TranscriptomicReviewFlag,
    "bridge://schemas/proliferation-stress-response-profile/v0.1": (
        ProliferationStressResponseProfile
    ),
}
