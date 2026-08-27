from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from bridge.tool_packages._configurable_contracts import (
    OBJECT_ID_PATTERN,
    SHA256_PATTERN,
    VERSION_PATTERN,
    VersionedObjectRef,
)
from bridge.toolkit.contracts import FrozenModel, ScoreState


ReasonCode = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]


class TargetRegionalMethodId(StrEnum):
    TARGET_PSEUDOBULK_CORRELATION = "TRG-PBCORR"
    REGIONAL_PSEUDOBULK_CORRELATION = "REG-PBCORR"
    TARGET_NNLS = "TRG-NNLS"
    TARGET_DECOUPLER = "TRG-DECOUPLER"
    REGIONAL_DECOUPLER = "REG-DECOUPLER"
    TARGET_BOOTSTRAP = "TRG-BOOTSTRAP"
    REGIONAL_CROSS_REFERENCE = "REG-CROSSREF"
    REGIONAL_MODALITY_SENSITIVITY = "REG-MODALITY"


class ExpressionSemanticsContract(FrozenModel):
    """Caller-reviewed assertion that query and reference values are comparable."""

    object_version: Literal["0.1.0"]
    contract_id: str = Field(
        pattern=r"^expression-semantics-contract:[A-Za-z0-9._:-]+$"
    )
    contract_version: str = Field(pattern=VERSION_PATTERN)
    status: Literal["candidate", "frozen"]
    expression_asset_id: str = Field(min_length=1)
    reference_profile_ids: list[str] = Field(min_length=1)
    matrix_semantics: Literal["normalized_expression"]
    normalization_method: str = Field(min_length=1)
    transformation: str = Field(min_length=1)
    gene_identifier_namespace: str = Field(min_length=1)

    @field_validator("reference_profile_ids")
    @classmethod
    def profiles_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("expression-semantics profiles must be unique")
        return value


class MatchedModalityComparisonGroup(FrozenModel):
    """Externally declared feature- and context-matched modality comparison."""

    object_version: Literal["0.1.0"]
    group_id: str = Field(pattern=r"^modality-comparison-group:[A-Za-z0-9._:-]+$")
    group_version: str = Field(pattern=VERSION_PATTERN)
    status: Literal["candidate", "frozen"]
    reference_profile_ids: list[str] = Field(min_length=2)
    matched_feature_view_id: str = Field(min_length=1)
    matched_context_id: str = Field(min_length=1)

    @field_validator("reference_profile_ids")
    @classmethod
    def profiles_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("modality-comparison profiles must be unique")
        return value


class NnlsResidualApplicabilityContract(FrozenModel):
    """Externally reviewed applicability limit for the normalized NNLS residual."""

    object_version: Literal["0.1.0"]
    contract_id: str = Field(
        pattern=r"^nnls-residual-applicability-contract:[A-Za-z0-9._:-]+$"
    )
    contract_version: str = Field(pattern=VERSION_PATTERN)
    status: Literal["candidate", "frozen"]
    residual_metric: Literal["relative_l2_norm"]
    maximum_residual: float = Field(gt=0.0)


class TargetRegionalMethodSpec(FrozenModel):
    """External, versioned choices for optional expression-level evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    object_version: Literal["0.1.0"]
    method_spec_id: str = Field(
        pattern=r"^target-regional-method-spec:[A-Za-z0-9._:-]+$"
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
    target_reference_profile_ids: list[str] = Field(default_factory=list)
    regional_reference_profile_ids: list[str] = Field(default_factory=list)
    selected_method_ids: list[TargetRegionalMethodId] = Field(min_length=1)
    target_program_card_ids: list[str] = Field(default_factory=list)
    regional_program_card_ids: list[str] = Field(default_factory=list)
    minimum_shared_genes: int = Field(ge=2)
    minimum_program_genes: int = Field(ge=2)
    bootstrap_replicates: int = Field(default=1000, ge=10, le=10000)
    bootstrap_confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    expression_semantics_contract: ExpressionSemanticsContract | None = None
    modality_comparison_group: MatchedModalityComparisonGroup | None = None
    nnls_residual_applicability: NnlsResidualApplicabilityContract | None = None

    @field_validator(
        "target_reference_profile_ids",
        "regional_reference_profile_ids",
        "selected_method_ids",
        "target_program_card_ids",
        "regional_program_card_ids",
    )
    @classmethod
    def configured_values_are_unique(cls, value: list[object]) -> list[object]:
        if len(value) != len(set(value)):
            raise ValueError("configured method values must be unique")
        return value

    @model_validator(mode="after")
    def program_choices_are_explicit(self) -> Self:
        selected = set(self.selected_method_ids)
        target_reference_methods = {
            TargetRegionalMethodId.TARGET_PSEUDOBULK_CORRELATION,
            TargetRegionalMethodId.TARGET_NNLS,
            TargetRegionalMethodId.TARGET_BOOTSTRAP,
        }
        regional_reference_methods = {
            TargetRegionalMethodId.REGIONAL_PSEUDOBULK_CORRELATION,
            TargetRegionalMethodId.REGIONAL_CROSS_REFERENCE,
            TargetRegionalMethodId.REGIONAL_MODALITY_SENSITIVITY,
        }
        if (
            selected & target_reference_methods
            and not self.target_reference_profile_ids
        ):
            raise ValueError(
                "selected target reference methods require target profiles"
            )
        if (
            selected & regional_reference_methods
            and not self.regional_reference_profile_ids
        ):
            raise ValueError(
                "selected regional reference methods require regional profiles"
            )
        if (
            TargetRegionalMethodId.TARGET_DECOUPLER in selected
            and not self.target_program_card_ids
        ):
            raise ValueError("target decoupler requires target program cards")
        if (
            TargetRegionalMethodId.REGIONAL_DECOUPLER in selected
            and not self.regional_program_card_ids
        ):
            raise ValueError("regional decoupler requires regional program cards")
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


class TargetRegionalMethodEvidence(FrozenModel):
    method_id: TargetRegionalMethodId
    execution_state: MethodExecutionState
    evidence_family: Literal[
        "reference_similarity",
        "regional_similarity",
        "continuous_identity",
        "marker_program",
        "regional_program",
        "uncertainty",
        "robustness",
    ]
    implementation: str = Field(min_length=1)
    package_versions: dict[str, str] = Field(default_factory=dict)
    reference_profile_ids: list[str] = Field(default_factory=list)
    n_analysis_units: int = Field(ge=0)
    n_shared_genes: int | None = Field(default=None, ge=0)
    reason_codes: list[ReasonCode] = Field(default_factory=list)

    @field_validator("reference_profile_ids", "reason_codes")
    @classmethod
    def lists_are_sorted_unique(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("method evidence lists must be sorted and unique")
        return value

    @model_validator(mode="after")
    def execution_is_coherent(self) -> Self:
        if self.execution_state is MethodExecutionState.SUCCEEDED and self.reason_codes:
            raise ValueError("successful method evidence cannot retain reason codes")
        if (
            self.execution_state is MethodExecutionState.NOT_ASSESSED
            and not self.reason_codes
        ):
            raise ValueError("not_assessed method evidence requires a reason code")
        return self


class ReferenceSupportRecord(FrozenModel):
    analysis_unit_ref: str = Field(min_length=1)
    evidence_scope: Literal["target_identity", "regional_fidelity"]
    profile_id: str = Field(min_length=1)
    profile_assay: str = Field(min_length=1)
    top_label: str | None = None
    top_spearman_support: float | None = Field(default=None, ge=-1.0, le=1.0)
    runner_up_label: str | None = None
    margin: float | None = Field(default=None, ge=0.0, le=2.0)
    top_cosine_support: float | None = Field(default=None, ge=-1.0, le=1.0)
    shared_genes: int = Field(ge=0)
    evidence_state: Literal["shadow", "unavailable"]


class ContinuousIdentityWeight(FrozenModel):
    analysis_unit_ref: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    state_id: str = Field(pattern=OBJECT_ID_PATTERN)
    weight: float = Field(ge=0.0, le=1.0)
    residual_norm: float = Field(ge=0.0)
    residual_metric: Literal["relative_l2_norm"]
    applicability_state: Literal["shadow", "unknown"]
    reason_codes: list[ReasonCode] = Field(default_factory=list)

    @model_validator(mode="after")
    def applicability_is_coherent(self) -> Self:
        if (self.applicability_state == "unknown") != bool(self.reason_codes):
            raise ValueError("NNLS applicability state and reasons disagree")
        return self


class ProgramActivityRecord(FrozenModel):
    analysis_unit_ref: str = Field(min_length=1)
    card_id: str = Field(min_length=1)
    state_id: str = Field(pattern=OBJECT_ID_PATTERN)
    evidence_scope: Literal["target_identity", "regional_fidelity"]
    activity: float
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    observed_positive_markers: int = Field(ge=0)
    observed_negative_markers: int = Field(ge=0)


class SampleBootstrapInterval(FrozenModel):
    metric_name: Literal["target_identity_nnls_weight"]
    estimate: float = Field(ge=0.0, le=1.0)
    lower: float | None = Field(default=None, ge=0.0, le=1.0)
    upper: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_level: float | None = Field(default=None, gt=0.0, lt=1.0)
    n_independent_units: int = Field(ge=1)
    replicates: int = Field(ge=0)
    interval_state: Literal["available", "descriptive_only"]

    @model_validator(mode="after")
    def interval_is_coherent(self) -> Self:
        available = self.interval_state == "available"
        values_present = self.lower is not None and self.upper is not None
        if available != values_present:
            raise ValueError("bootstrap interval state and bounds disagree")
        if available and self.lower > self.upper:
            raise ValueError("bootstrap lower bound exceeds upper bound")
        if available != (self.confidence_level is not None and self.replicates > 0):
            raise ValueError("bootstrap metadata and interval state disagree")
        return self


class RobustnessRecord(FrozenModel):
    robustness_kind: Literal["cross_reference", "modality"]
    analysis_unit_ref: str = Field(min_length=1)
    compared_profile_ids: list[str] = Field(default_factory=list)
    top_labels: list[str] = Field(default_factory=list)
    label_agreement: Literal["agree", "disagree", "not_assessed"]
    support_range: float | None = Field(default=None, ge=0.0, le=2.0)
    reason_codes: list[ReasonCode] = Field(default_factory=list)

    @field_validator("compared_profile_ids", "top_labels", "reason_codes")
    @classmethod
    def lists_are_sorted_unique(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("robustness lists must be sorted and unique")
        return value

    @model_validator(mode="after")
    def assessment_is_coherent(self) -> Self:
        assessed = self.label_agreement != "not_assessed"
        if assessed and len(self.compared_profile_ids) < 2:
            raise ValueError("assessed robustness requires two reference profiles")
        if assessed and not self.top_labels:
            raise ValueError("assessed robustness requires a supported label")
        if assessed and self.reason_codes:
            raise ValueError("assessed robustness cannot retain reason codes")
        if not assessed and not self.reason_codes:
            raise ValueError("unassessed robustness requires a reason code")
        if not assessed and self.support_range is not None:
            raise ValueError("unassessed robustness cannot retain a support range")
        return self


class TargetRegionalMethodBundle(FrozenModel):
    object_version: Literal["0.1.0"]
    bundle_id: str = Field(pattern=r"^target-regional-method-bundle:[a-f0-9]{16}$")
    tool_id: Literal["P0-03"]
    tool_version: str = Field(pattern=VERSION_PATTERN)
    method_spec_ref: VersionedObjectRef
    expression_asset_id: str = Field(min_length=1)
    expression_asset_sha256: str = Field(pattern=SHA256_PATTERN)
    reference_manifest_ref: VersionedObjectRef
    analysis_unit_refs: list[str] = Field(min_length=1)
    independence_group_refs: list[str] = Field(min_length=1)
    n_observations: int = Field(ge=1)
    n_genes: int = Field(ge=1)
    method_evidence: list[TargetRegionalMethodEvidence] = Field(min_length=1)
    reference_support: list[ReferenceSupportRecord] = Field(default_factory=list)
    continuous_identity_weights: list[ContinuousIdentityWeight] = Field(
        default_factory=list
    )
    program_activity: list[ProgramActivityRecord] = Field(default_factory=list)
    bootstrap_intervals: list[SampleBootstrapInterval] = Field(default_factory=list)
    robustness: list[RobustnessRecord] = Field(default_factory=list)
    domain_score: None = None
    score_state: Literal[ScoreState.SHADOW, ScoreState.UNAVAILABLE]

    @field_validator("analysis_unit_refs", "independence_group_refs")
    @classmethod
    def units_are_sorted_unique(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("biological-unit references must be sorted and unique")
        return value

    @model_validator(mode="after")
    def score_state_matches_evidence(self) -> Self:
        has_evidence = any(
            item.execution_state
            in {MethodExecutionState.SUCCEEDED, MethodExecutionState.PARTIAL}
            for item in self.method_evidence
        )
        expected = ScoreState.SHADOW if has_evidence else ScoreState.UNAVAILABLE
        if self.score_state != expected:
            raise ValueError(
                "method bundle score state must match evidence availability"
            )
        return self


class TargetRegionalMethodArtifactBinding(FrozenModel):
    bundle_ref: VersionedObjectRef
    file_name: Literal["target_regional_method_bundle.json"]
    sha256: str = Field(pattern=SHA256_PATTERN)
    selected_method_ids: list[TargetRegionalMethodId] = Field(min_length=1)

    @field_validator("selected_method_ids")
    @classmethod
    def methods_are_sorted_unique(
        cls, value: list[TargetRegionalMethodId]
    ) -> list[TargetRegionalMethodId]:
        if value != sorted(set(value), key=str):
            raise ValueError("selected methods must be sorted and unique")
        return value
