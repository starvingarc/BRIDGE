from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, StrictInt, field_validator, model_validator

from bridge.tool_packages._configurable_contracts import (
    SHA256_PATTERN,
    VERSION_PATTERN,
    VersionedObjectRef,
)
from bridge.tool_packages.p0_04_developmental_compatibility.roles import (
    DevelopmentStageRole,
)
from bridge.toolkit.contracts import FrozenModel, ScoreState


ReasonCode = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]


class DevelopmentMethodId(StrEnum):
    PSEUDOBULK_CORRELATION = "DEV-PSEUDOBULK-CORR"
    ORDINAL_CLASSIFIER = "DEV-ORDINAL"
    PROGRAM_ACTIVITY = "DEV-PROGRAM"
    SAMPLE_BOOTSTRAP = "DEV-BOOTSTRAP"
    TIME_PROGRAM = "TIME-PROGRAM"
    TIME_GAM_PY = "TIME-GAM-PY"


class ReferenceStageDefinition(FrozenModel):
    profile_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    ordinal_rank: StrictInt = Field(ge=0)
    stage_role: DevelopmentStageRole


class AnalysisUnitTimepoint(FrozenModel):
    analysis_unit_ref: str = Field(min_length=1)
    timepoint_id: str = Field(min_length=1)
    timepoint_order: StrictInt = Field(
        ge=0,
        description="Categorical display order; not a numeric time value.",
    )
    timepoint_label: str = Field(min_length=1)


class OrdinalGroupHeldoutEvidence(FrozenModel):
    """External receipt for source-group-held-out ordinal validation."""

    object_version: Literal["0.1.0"]
    evidence_id: str = Field(
        pattern=r"^ordinal-group-heldout-evidence:[A-Za-z0-9._:-]+$"
    )
    evidence_version: str = Field(pattern=VERSION_PATTERN)
    review_state: Literal["candidate", "reviewed"]
    validation_state: Literal["passed", "not_passed"]
    grouping_unit: Literal["source_id"]
    reference_profile_ids: list[str] = Field(min_length=2)
    held_out_source_ids: list[str] = Field(min_length=2)

    @field_validator("reference_profile_ids", "held_out_source_ids")
    @classmethod
    def identifiers_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("group-held-out identifiers must be unique")
        return value

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.evidence_id,
            object_version=self.evidence_version,
        )


class DevelopmentMethodSpec(FrozenModel):
    """External, versioned choices for optional expression-level evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    object_version: Literal["0.1.0"]
    method_spec_id: str = Field(
        pattern=r"^development-method-spec:[A-Za-z0-9._:-]+$"
    )
    method_spec_version: str = Field(pattern=VERSION_PATTERN)
    status: Literal["candidate", "frozen"]
    expression_asset_id: str = Field(min_length=1)
    observation_id_column: str | None = Field(
        default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_.-]*$"
    )
    gene_symbol_column: str | None = Field(
        default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_.-]*$"
    )
    reference_profile_ids: list[str] = Field(default_factory=list)
    reference_stages: list[ReferenceStageDefinition] = Field(default_factory=list)
    program_card_ids: list[str] = Field(default_factory=list)
    analysis_unit_timepoints: list[AnalysisUnitTimepoint] = Field(default_factory=list)
    selected_method_ids: list[DevelopmentMethodId] = Field(min_length=1)
    minimum_shared_genes: StrictInt = Field(default=50, ge=2)
    minimum_program_genes: StrictInt = Field(default=3, ge=2)
    bootstrap_replicates: StrictInt = Field(default=1000, ge=10, le=10000)
    bootstrap_confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    spline_degrees_of_freedom: StrictInt = Field(default=3, ge=3, le=8)
    ordinal_group_heldout_evidence: OrdinalGroupHeldoutEvidence | None = None

    @field_validator(
        "reference_profile_ids",
        "program_card_ids",
        "selected_method_ids",
    )
    @classmethod
    def configured_values_are_unique(cls, value: list[object]) -> list[object]:
        if len(value) != len(set(value)):
            raise ValueError("configured method values must be unique")
        return value

    @field_validator("reference_stages")
    @classmethod
    def reference_stages_are_unique(
        cls, value: list[ReferenceStageDefinition]
    ) -> list[ReferenceStageDefinition]:
        keys = [(item.profile_id, item.label) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("reference stage definitions must be unique")
        return value

    @field_validator("analysis_unit_timepoints")
    @classmethod
    def timepoint_units_are_unique(
        cls, value: list[AnalysisUnitTimepoint]
    ) -> list[AnalysisUnitTimepoint]:
        unit_keys = [item.analysis_unit_ref for item in value]
        if len(unit_keys) != len(set(unit_keys)):
            raise ValueError("analysis units may have only one timepoint")
        labels_by_order: dict[int, tuple[str, str]] = {}
        for item in value:
            identity = (item.timepoint_id, item.timepoint_label)
            previous = labels_by_order.setdefault(item.timepoint_order, identity)
            if previous != identity:
                raise ValueError("one timepoint order must have one identity and label")
        return value

    @model_validator(mode="after")
    def method_prerequisites_are_explicit(self) -> Self:
        selected = set(self.selected_method_ids)
        reference_methods = {
            DevelopmentMethodId.PSEUDOBULK_CORRELATION,
            DevelopmentMethodId.ORDINAL_CLASSIFIER,
            DevelopmentMethodId.SAMPLE_BOOTSTRAP,
        }
        if selected & reference_methods:
            if not self.reference_profile_ids or not self.reference_stages:
                raise ValueError(
                    "reference methods require profiles and stage definitions"
                )
            defined_profiles = {item.profile_id for item in self.reference_stages}
            if set(self.reference_profile_ids) - defined_profiles:
                raise ValueError(
                    "every selected reference profile requires stage definitions"
                )
        program_methods = {
            DevelopmentMethodId.PROGRAM_ACTIVITY,
        }
        if selected & program_methods and not self.program_card_ids:
            raise ValueError("program methods require program cards")
        return self

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.method_spec_id,
            object_version=self.method_spec_version,
        )


class MethodExecutionState(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    NOT_ASSESSED = "not_assessed"


class DevelopmentMethodEvidence(FrozenModel):
    method_id: DevelopmentMethodId
    execution_state: MethodExecutionState
    evidence_family: Literal[
        "reference_stage_support",
        "ordinal_stage_support",
        "stage_program",
        "uncertainty",
        "time_trend",
    ]
    implementation: str = Field(min_length=1)
    package_versions: dict[str, str] = Field(default_factory=dict)
    n_analysis_units: StrictInt = Field(ge=0)
    n_independence_groups: StrictInt = Field(ge=0)
    reason_codes: list[ReasonCode] = Field(default_factory=list)

    @field_validator("reason_codes")
    @classmethod
    def reasons_are_sorted_unique(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("reason codes must be sorted and unique")
        return value

    @model_validator(mode="after")
    def execution_is_coherent(self) -> Self:
        if self.execution_state is MethodExecutionState.SUCCEEDED and self.reason_codes:
            raise ValueError("successful method evidence cannot retain reason codes")
        if self.execution_state is MethodExecutionState.NOT_ASSESSED and not self.reason_codes:
            raise ValueError("not_assessed method evidence requires a reason code")
        return self


class ReferenceStageSupportRecord(FrozenModel):
    analysis_unit_ref: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    profile_source_id: str = Field(min_length=1)
    profile_assay: str = Field(min_length=1)
    top_label: str | None = None
    top_stage_role: DevelopmentStageRole | None = None
    top_ordinal_rank: StrictInt | None = Field(default=None, ge=0)
    top_spearman_support: float | None = Field(default=None, ge=-1.0, le=1.0)
    runner_up_label: str | None = None
    margin: float | None = Field(default=None, ge=0.0, le=2.0)
    top_cosine_support: float | None = Field(default=None, ge=-1.0, le=1.0)
    shared_genes: StrictInt = Field(ge=0)
    evidence_state: Literal["shadow", "unavailable"]
    reason_codes: list[ReasonCode] = Field(default_factory=list)

    @field_validator("reason_codes")
    @classmethod
    def reasons_are_sorted_unique(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("reference support reasons must be sorted and unique")
        return value

    @model_validator(mode="after")
    def evidence_state_is_coherent(self) -> Self:
        if (self.evidence_state == "unavailable") != bool(self.reason_codes):
            raise ValueError("reference support state and reasons disagree")
        return self


class OrdinalStagePrediction(FrozenModel):
    analysis_unit_ref: str = Field(min_length=1)
    expected_ordinal_rank: float
    nearest_label: str = Field(min_length=1)
    nearest_stage_role: DevelopmentStageRole
    rank_probabilities: dict[str, float]
    calibration_state: Literal["uncalibrated_baseline"]
    group_heldout_evidence_ref: VersionedObjectRef
    n_reference_rows: StrictInt = Field(ge=1)
    n_reference_sources: StrictInt = Field(ge=1)

    @field_validator("rank_probabilities")
    @classmethod
    def probabilities_are_coherent(cls, value: dict[str, float]) -> dict[str, float]:
        if not value or any(item < 0.0 or item > 1.0 for item in value.values()):
            raise ValueError("ordinal probabilities must be within [0, 1]")
        if abs(sum(value.values()) - 1.0) > 1e-6:
            raise ValueError("ordinal probabilities must sum to one")
        return value


class DevelopmentProgramActivity(FrozenModel):
    analysis_unit_ref: str = Field(min_length=1)
    card_id: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    activity: float
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    observed_positive_markers: StrictInt = Field(ge=0)
    observed_negative_markers: StrictInt = Field(ge=0)


class DevelopmentBootstrapInterval(FrozenModel):
    metric_name: Literal["within_window_reference_support"]
    estimate: float = Field(ge=-1.0, le=1.0)
    lower: float | None = Field(default=None, ge=-1.0, le=1.0)
    upper: float | None = Field(default=None, ge=-1.0, le=1.0)
    confidence_level: float | None = Field(default=None, gt=0.0, lt=1.0)
    n_independence_groups: StrictInt = Field(ge=1)
    replicates: StrictInt = Field(ge=0)
    interval_state: Literal["available", "descriptive_only"]

    @model_validator(mode="after")
    def interval_is_coherent(self) -> Self:
        available = self.interval_state == "available"
        bounds = self.lower is not None and self.upper is not None
        if available != bounds:
            raise ValueError("bootstrap interval state and bounds disagree")
        if available and self.lower > self.upper:
            raise ValueError("bootstrap lower bound exceeds upper bound")
        if available != (self.confidence_level is not None and self.replicates > 0):
            raise ValueError("bootstrap metadata and interval state disagree")
        return self


class TimeTrendPoint(FrozenModel):
    timepoint_id: str = Field(min_length=1)
    timepoint_order: StrictInt = Field(ge=0)
    timepoint_label: str = Field(min_length=1)
    fitted_value: float


class DevelopmentTimeTrend(FrozenModel):
    metric_name: Literal[
        "within_window_reference_support",
        "stage_program_activity",
    ]
    card_id: str | None = None
    n_analysis_units: StrictInt = Field(ge=1)
    n_independence_groups: StrictInt = Field(ge=1)
    n_timepoints: StrictInt = Field(ge=2)
    spline_degrees_of_freedom: StrictInt = Field(ge=3)
    analysis_state: Literal["unadjusted_descriptive"]
    fitted_points: list[TimeTrendPoint] = Field(min_length=2)


class DevelopmentMethodBundle(FrozenModel):
    object_version: Literal["0.1.0"]
    bundle_id: str = Field(pattern=r"^development-method-bundle:[a-f0-9]{16}$")
    tool_id: Literal["P0-04"]
    tool_version: str = Field(pattern=VERSION_PATTERN)
    method_spec_ref: VersionedObjectRef
    expression_asset_id: str = Field(min_length=1)
    expression_asset_sha256: str = Field(pattern=SHA256_PATTERN)
    reference_manifest_ref: VersionedObjectRef
    analysis_unit_refs: list[str] = Field(min_length=1)
    independence_group_refs: list[str] = Field(min_length=1)
    n_observations: StrictInt = Field(ge=1)
    n_genes: StrictInt = Field(ge=1)
    method_evidence: list[DevelopmentMethodEvidence] = Field(min_length=1)
    reference_stage_support: list[ReferenceStageSupportRecord] = Field(
        default_factory=list
    )
    ordinal_stage_predictions: list[OrdinalStagePrediction] = Field(
        default_factory=list
    )
    program_activity: list[DevelopmentProgramActivity] = Field(default_factory=list)
    bootstrap_intervals: list[DevelopmentBootstrapInterval] = Field(
        default_factory=list
    )
    time_trends: list[DevelopmentTimeTrend] = Field(default_factory=list)
    domain_score: None = None
    score_state: Literal[ScoreState.SHADOW, ScoreState.UNAVAILABLE]

    @field_validator("analysis_unit_refs", "independence_group_refs")
    @classmethod
    def units_are_sorted_unique(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("biological-unit references must be sorted and unique")
        return value


class DevelopmentMethodArtifactBinding(FrozenModel):
    bundle_ref: VersionedObjectRef
    file_name: Literal["development_method_bundle.json"]
    sha256: str = Field(pattern=SHA256_PATTERN)
    selected_method_ids: list[DevelopmentMethodId]
