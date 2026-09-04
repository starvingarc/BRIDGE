from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    field_validator,
    model_validator,
)

from bridge.tool_packages._configurable_contracts import VersionedObjectRef
from bridge.toolkit.contracts import EvidenceState, FrozenModel


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


def projected_program_evidence_state(
    *,
    applicability: ProgramApplicabilityState,
    availability: ProgramAvailabilityState,
    review_flag_state: ReviewFlagState,
) -> EvidenceState:
    """Map one source program record to its gate-facing evidence state."""

    if (
        applicability is ProgramApplicabilityState.NOT_APPLICABLE
        or availability is ProgramAvailabilityState.UNAVAILABLE
        or review_flag_state is ReviewFlagState.NOT_ASSESSED
    ):
        return EvidenceState.UNAVAILABLE
    if (
        availability is ProgramAvailabilityState.CANNOT_RESOLVE
        or review_flag_state is ReviewFlagState.CANNOT_RESOLVE
    ):
        return EvidenceState.UNKNOWN
    if review_flag_state is ReviewFlagState.NOT_DETECTED_ABOVE_LOD:
        return EvidenceState.NEGATIVE
    if review_flag_state is ReviewFlagState.TRANSCRIPTOMIC_REVIEW_FLAG:
        return EvidenceState.ALERT
    raise ValueError("program evidence state cannot be projected")


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


class ProgramMeasurementArtifactBinding(FrozenModel):
    measurement_id: SafeId
    evidence_id: SafeId
    source_evidence_state: SafeId
    projected_evidence_state: EvidenceState
    artifact_id: SafeId
    file_name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*\.json$")
    sha256: Sha256


class MethodMeasurementArtifactBinding(FrozenModel):
    measurement_id: SafeId
    summary_kind: Literal["program_score", "cell_cycle"]
    source_method_id: SafeId
    source_summary_sha256: Sha256
    metric_name: Literal["program_score_mean", "cell_cycle_cycling_fraction"]
    program_id: SafeId
    analysis_scope: AnalysisScope
    analysis_unit_ref: str = Field(min_length=1)
    independence_group_ref: str = Field(min_length=1)
    cell_state_id: SafeId | None = None
    assessment_state: Literal["available", "not_assessed"]
    n_observations: NonNegativeInt
    artifact_id: SafeId
    file_name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*\.json$")
    sha256: Sha256

    @model_validator(mode="after")
    def scope_is_coherent(self) -> Self:
        if (self.analysis_scope is AnalysisScope.STATE_SPECIFIC) != (
            self.cell_state_id is not None
        ):
            raise ValueError("state-specific measurement requires one state_id")
        return self


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


class ProliferationStressResponseProfileV2(ProliferationStressResponseProfile):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {
                            "measurement_projection_state": {
                                "const": "not_requested"
                            }
                        },
                        "required": ["measurement_projection_state"],
                    },
                    "then": {
                        "required": ["measurement_artifacts"],
                        "properties": {
                            "measurement_spec_ref": {"type": "null"},
                            "measurement_artifacts": {"maxItems": 0},
                        },
                    },
                },
                {
                    "if": {
                        "properties": {
                            "measurement_projection_state": {"const": "available"}
                        },
                        "required": ["measurement_projection_state"],
                    },
                    "then": {
                        "required": [
                            "measurement_spec_ref",
                            "measurement_artifacts",
                        ],
                        "properties": {
                            "measurement_spec_ref": {"not": {"type": "null"}},
                            "measurement_artifacts": {"minItems": 1},
                        },
                    },
                },
            ]
        }
    )

    profile_version: Literal["0.2.0"]
    measurement_projection_state: Literal["not_requested", "available"]
    measurement_spec_ref: VersionedObjectRef | None = None
    measurement_artifacts: list[ProgramMeasurementArtifactBinding]

    @model_validator(mode="after")
    def measurement_projection_is_coherent(self) -> Self:
        measurement_ids = [item.measurement_id for item in self.measurement_artifacts]
        evidence_ids = [item.evidence_id for item in self.measurement_artifacts]
        artifact_ids = [item.artifact_id for item in self.measurement_artifacts]
        file_names = [item.file_name for item in self.measurement_artifacts]
        for values, name in (
            (measurement_ids, "measurement IDs"),
            (evidence_ids, "projected evidence IDs"),
            (artifact_ids, "measurement artifact IDs"),
            (file_names, "measurement artifact file names"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must be unique")
        program_evidence_ids = [item.evidence_id for item in self.program_results]
        if self.measurement_projection_state == "not_requested":
            if self.measurement_spec_ref is not None or self.measurement_artifacts:
                raise ValueError(
                    "not-requested projection cannot bind a spec or measurements"
                )
            return self
        if self.measurement_spec_ref is None:
            raise ValueError("available projection requires a measurement spec")
        if not self.measurement_artifacts:
            raise ValueError("available projection requires measurement artifacts")
        if evidence_ids != program_evidence_ids:
            raise ValueError(
                "measurement artifacts must bind every program result in order"
            )
        for summary, flag, binding in zip(
            self.program_results,
            self.review_flags,
            self.measurement_artifacts,
            strict=True,
        ):
            if (
                flag.applicability is not summary.applicability
                or flag.availability is not summary.availability
            ):
                raise ValueError("program result and review flag states must align")
            expected_state = projected_program_evidence_state(
                applicability=summary.applicability,
                availability=summary.availability,
                review_flag_state=flag.review_flag_state,
            )
            if binding.source_evidence_state != summary.evidence_state:
                raise ValueError("measurement binding source evidence state mismatch")
            if binding.projected_evidence_state is not expected_state:
                raise ValueError(
                    "measurement binding projected evidence state mismatch"
                )
        return self


class ProliferationStressResponseProfileV3(ProliferationStressResponseProfile):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {
                            "measurement_projection_state": {
                                "const": "not_requested"
                            }
                        },
                        "required": ["measurement_projection_state"],
                    },
                    "then": {
                        "properties": {
                            "measurement_spec_ref": {"type": "null"},
                            "measurement_spec_sha256": {"type": "null"},
                            "process_method_bundle_ref": {"type": "null"},
                            "process_method_bundle_sha256": {"type": "null"},
                            "measurement_artifacts": {"maxItems": 0},
                        }
                    },
                },
                {
                    "if": {
                        "properties": {
                            "measurement_projection_state": {
                                "const": "available"
                            }
                        },
                        "required": ["measurement_projection_state"],
                    },
                    "then": {
                        "required": [
                            "measurement_spec_ref",
                            "measurement_spec_sha256",
                        ],
                        "properties": {
                            "measurement_spec_ref": {"not": {"type": "null"}},
                            "measurement_spec_sha256": {
                                "not": {"type": "null"}
                            },
                            "measurement_artifacts": {"minItems": 1},
                        },
                    },
                },
                {
                    "if": {
                        "properties": {
                            "measurement_projection_state": {
                                "const": "not_assessed"
                            }
                        },
                        "required": ["measurement_projection_state"],
                    },
                    "then": {
                        "required": [
                            "measurement_spec_ref",
                            "measurement_spec_sha256",
                            "process_method_bundle_ref",
                            "process_method_bundle_sha256",
                        ],
                        "properties": {
                            "measurement_spec_ref": {"not": {"type": "null"}},
                            "measurement_spec_sha256": {
                                "not": {"type": "null"}
                            },
                            "process_method_bundle_ref": {
                                "not": {"type": "null"}
                            },
                            "process_method_bundle_sha256": {
                                "not": {"type": "null"}
                            },
                            "measurement_artifacts": {"maxItems": 0},
                        },
                    },
                },
                {
                    "if": {
                        "properties": {
                            "runtime_mode": {"const": "method_runtime"}
                        },
                        "required": ["runtime_mode"],
                    },
                    "then": {
                        "required": [
                            "measurement_spec_ref",
                            "measurement_spec_sha256",
                            "process_method_bundle_ref",
                            "process_method_bundle_sha256",
                        ],
                        "properties": {
                            "measurement_projection_state": {
                                "enum": ["available", "not_assessed"]
                            },
                            "measurement_spec_ref": {"not": {"type": "null"}},
                            "measurement_spec_sha256": {
                                "not": {"type": "null"}
                            },
                            "process_method_bundle_ref": {
                                "not": {"type": "null"}
                            },
                            "process_method_bundle_sha256": {
                                "not": {"type": "null"}
                            },
                            "program_results": {"maxItems": 0},
                            "review_flags": {"maxItems": 0},
                        },
                    },
                },
                {
                    "if": {
                        "properties": {
                            "runtime_mode": {"const": "legacy_aggregation"}
                        },
                        "required": ["runtime_mode"],
                    },
                    "then": {
                        "properties": {
                            "measurement_projection_state": {
                                "enum": ["not_requested", "available"]
                            },
                            "process_method_bundle_ref": {"type": "null"},
                            "process_method_bundle_sha256": {"type": "null"},
                        }
                    },
                },
            ]
        }
    )

    profile_version: Literal["0.3.0"]
    runtime_mode: Literal["legacy_aggregation", "method_runtime"]
    source_bindings: list[ProgramSourceBinding] = Field(min_length=7, max_length=10)
    measurement_projection_state: Literal[
        "not_requested", "available", "not_assessed"
    ]
    measurement_spec_ref: VersionedObjectRef | None = None
    measurement_spec_sha256: Sha256 | None = None
    process_method_bundle_ref: SafeId | None = None
    process_method_bundle_sha256: Sha256 | None = None
    measurement_artifacts: list[
        ProgramMeasurementArtifactBinding | MethodMeasurementArtifactBinding
    ]

    @model_validator(mode="after")
    def runtime_projection_is_coherent(self) -> Self:
        roles = [item.role for item in self.source_bindings]
        if len(roles) != len(set(roles)):
            raise ValueError("source binding roles must be unique")
        legacy_roles = {
            "product_case",
            "product_definition_card",
            "development_window_spec",
            "program_spec",
            "cell_state_evidence_profile",
            "protocol_ir",
            "program_evidence_bundle",
        }
        method_roles = legacy_roles.difference({"program_evidence_bundle"}) | {
            "biological_unit_manifest",
            "biological_unit_assignment",
            "process_method_spec",
            "process_method_input",
        }
        expected_roles = (
            legacy_roles if self.runtime_mode == "legacy_aggregation" else method_roles
        )
        if set(roles) != expected_roles:
            raise ValueError("source bindings do not match runtime mode")

        paired_spec = (
            self.measurement_spec_ref is not None
            and self.measurement_spec_sha256 is not None
        )
        if (self.measurement_spec_ref is None) != (
            self.measurement_spec_sha256 is None
        ):
            raise ValueError("measurement spec reference and checksum must be paired")
        paired_bundle = (
            self.process_method_bundle_ref is not None
            and self.process_method_bundle_sha256 is not None
        )
        if (self.process_method_bundle_ref is None) != (
            self.process_method_bundle_sha256 is None
        ):
            raise ValueError("method bundle reference and checksum must be paired")

        measurement_ids = [item.measurement_id for item in self.measurement_artifacts]
        evidence_ids = [
            item.evidence_id
            for item in self.measurement_artifacts
            if isinstance(item, ProgramMeasurementArtifactBinding)
        ]
        artifact_ids = [item.artifact_id for item in self.measurement_artifacts]
        file_names = [item.file_name for item in self.measurement_artifacts]
        for values, name in (
            (measurement_ids, "measurement IDs"),
            (evidence_ids, "projected evidence IDs"),
            (artifact_ids, "measurement artifact IDs"),
            (file_names, "measurement artifact file names"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must be unique")

        if self.runtime_mode == "legacy_aggregation":
            if paired_bundle:
                raise ValueError("legacy aggregation cannot bind a method bundle")
            if any(
                isinstance(item, MethodMeasurementArtifactBinding)
                for item in self.measurement_artifacts
            ):
                raise ValueError("legacy aggregation requires program measurements")
            if self.measurement_projection_state == "not_assessed":
                raise ValueError("legacy aggregation cannot use not_assessed projection")
            if self.measurement_projection_state == "not_requested":
                if paired_spec or self.measurement_artifacts:
                    raise ValueError(
                        "not-requested projection cannot bind a spec or measurements"
                    )
                return self
            if not paired_spec or not self.measurement_artifacts:
                raise ValueError("available projection requires spec and measurements")
            if evidence_ids != [item.evidence_id for item in self.program_results]:
                raise ValueError(
                    "program measurements must bind every program result in order"
                )
            for summary, flag, binding in zip(
                self.program_results,
                self.review_flags,
                self.measurement_artifacts,
                strict=True,
            ):
                if not isinstance(binding, ProgramMeasurementArtifactBinding):
                    raise ValueError(
                        "legacy aggregation requires program measurements"
                    )
                if (
                    flag.applicability is not summary.applicability
                    or flag.availability is not summary.availability
                ):
                    raise ValueError(
                        "program result and review flag states must align"
                    )
                expected_state = projected_program_evidence_state(
                    applicability=summary.applicability,
                    availability=summary.availability,
                    review_flag_state=flag.review_flag_state,
                )
                if binding.source_evidence_state != summary.evidence_state:
                    raise ValueError(
                        "measurement binding source evidence state mismatch"
                    )
                if binding.projected_evidence_state is not expected_state:
                    raise ValueError(
                        "measurement binding projected evidence state mismatch"
                    )
            return self

        if self.program_results or self.review_flags:
            raise ValueError("method runtime cannot carry caller-supplied program evidence")
        if not paired_bundle or not paired_spec:
            raise ValueError("method runtime requires method bundle and measurement spec")
        if any(
            isinstance(item, ProgramMeasurementArtifactBinding)
            for item in self.measurement_artifacts
        ):
            raise ValueError("method runtime requires method-derived measurements")
        expected_state = "available" if self.measurement_artifacts else "not_assessed"
        if self.measurement_projection_state != expected_state:
            raise ValueError("method projection state does not match measurements")
        return self


PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/program-spec/v0.1": ProgramSpec,
    "bridge://schemas/protocol-ir/v0.1": ProtocolIR,
    "bridge://schemas/program-evidence-bundle/v0.1": ProgramEvidenceBundle,
    "bridge://schemas/transcriptomic-review-flag/v0.1": TranscriptomicReviewFlag,
    "bridge://schemas/proliferation-stress-response-profile/v0.1": (
        ProliferationStressResponseProfile
    ),
    "bridge://schemas/proliferation-stress-response-profile/v0.2": (
        ProliferationStressResponseProfileV2
    ),
    "bridge://schemas/proliferation-stress-response-profile/v0.3": (
        ProliferationStressResponseProfileV3
    ),
}
