from __future__ import annotations

import math
import re
from typing import Annotated, Literal, Self

from pydantic import Field, StrictFloat, StrictInt, field_validator, model_validator

from bridge.tool_packages._configurable_contracts import VersionedObjectRef
from bridge.tool_packages.p0_06_proliferation_stress_response.method_models import (
    CellCycleSummary,
    MethodAgreementRecord,
    ProcessMethodBundle,
    ProcessMethodId,
    ProcessMethodInput,
    ProcessMethodSpec,
    ProgramScoreSummary,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.models import (
    AnalysisScope,
    ProcessAttributionState,
    ProgramApplicabilityState,
    ProgramAvailabilityState,
    ProgramEvidenceSummary,
    ProgramSourceBinding,
    ProliferationStressResponseProfile,
    ReviewFlagState,
    TranscriptomicReviewFlag,
)
from bridge.toolkit.contracts import FrozenModel
from bridge.toolkit.visualization import VisualizationArtifactV2

PROLIFERATION_STRESS_VISUALIZATION_DATA_SCHEMA_REF = (
    "bridge://schemas/proliferation-stress-visualization-data/v0.1"
)
P006_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF = (
    "bridge://schemas/p0-06-visualization-artifact-set/v0.1"
)
PROGRAM_EVIDENCE_COMPONENT_REF = "bridge.proliferation-stress.program-evidence@0.1.0"
PROGRAM_SCORE_COMPONENT_REF = "bridge.proliferation-stress.program-score-summary@0.1.0"
CELL_CYCLE_COMPONENT_REF = "bridge.proliferation-stress.cell-cycle@0.1.0"
P006_COMPONENT_REFS = (
    PROGRAM_EVIDENCE_COMPONENT_REF,
    PROGRAM_SCORE_COMPONENT_REF,
    CELL_CYCLE_COMPONENT_REF,
)
_RECORD_ID = r"^[a-z][a-z0-9_.-]+$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
type Sha256 = Annotated[str, Field(pattern=_SHA256_PATTERN)]
type AssessmentState = Literal["available", "not_assessed"]
type ComponentState = Literal["available", "partial", "not_assessed"]
type ExpressionViewScope = Literal[
    "selected_expression_view",
    "candidate_state_subset_of_selected_expression_view",
]


def _sorted_unique(values: list[str], name: str) -> list[str]:
    if values != sorted(set(values)):
        raise ValueError(f"{name} must be sorted and unique")
    return values


def _expression_view_scope(scope: AnalysisScope) -> ExpressionViewScope:
    return (
        "selected_expression_view"
        if scope is AnalysisScope.WHOLE_PRODUCT
        else "candidate_state_subset_of_selected_expression_view"
    )


class _EvidenceRecord(FrozenModel):
    record_id: str = Field(pattern=_RECORD_ID)
    evidence_ids: list[str] = Field(min_length=1)
    evidence_state: Literal["shadow"] = "shadow"
    scientific_status: Literal["candidate"] = "candidate"
    assessment_state: AssessmentState
    reason_codes: list[str] = Field(default_factory=list)

    @field_validator("evidence_ids", "reason_codes")
    @classmethod
    def lists_are_sorted_unique(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)


class _SelectedCellRecord(_EvidenceRecord):
    analysis_scope: AnalysisScope
    expression_view_scope: ExpressionViewScope
    analysis_unit_ref: str = Field(min_length=1)
    independence_group_ref: str = Field(min_length=1)
    cell_state_id: str | None = None
    selected_expression_view_ref: str = Field(min_length=1)
    n_observations: StrictInt = Field(ge=0)
    observation_unit: Literal["cells"] = "cells"

    @model_validator(mode="after")
    def selected_view_scope_is_coherent(self) -> Self:
        if (self.analysis_scope is AnalysisScope.STATE_SPECIFIC) != (
            self.cell_state_id is not None
        ):
            raise ValueError("state-specific row requires one cell_state_id")
        if self.expression_view_scope != _expression_view_scope(self.analysis_scope):
            raise ValueError("expression-view scope does not match analysis scope")
        return self


class ProgramEvidenceVisualizationRecord(_EvidenceRecord):
    component_ref: Literal[PROGRAM_EVIDENCE_COMPONENT_REF] = (
        PROGRAM_EVIDENCE_COMPONENT_REF
    )
    evidence_id: str = Field(min_length=1)
    review_flag_id: str = Field(min_length=1)
    program_id: str = Field(min_length=1)
    analysis_scope: AnalysisScope
    cell_state_id: str | None = None
    stage_id: str = Field(min_length=1)
    metric_id: str = Field(min_length=1)
    value: StrictInt | StrictFloat | None = None
    unit: str | None = None
    numerator: StrictInt | None = Field(default=None, ge=0)
    denominator: StrictInt | None = Field(default=None, gt=0)
    denominator_scope: Literal["supplied_program_evidence_denominator"] | None = None
    gene_coverage: StrictFloat = Field(ge=0.0, le=1.0)
    minimum_gene_coverage: StrictFloat = Field(ge=0.0, le=1.0)
    gene_coverage_basis: Literal["supplied_program_evidence_gene_coverage"] = (
        "supplied_program_evidence_gene_coverage"
    )
    lod_state: str = Field(min_length=1)
    source_evidence_state: str = Field(min_length=1)
    applicability: ProgramApplicabilityState
    availability: ProgramAvailabilityState
    process_attribution: ProcessAttributionState
    process_step_ids: list[str] = Field(default_factory=list)
    review_flag_state: ReviewFlagState
    flag_status: Literal["shadow"]
    orthogonal_follow_up_refs: list[str] = Field(default_factory=list)

    @field_validator("process_step_ids", "orthogonal_follow_up_refs")
    @classmethod
    def provenance_lists_are_sorted_unique(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)

    @model_validator(mode="after")
    def evidence_and_flag_semantics_are_coherent(self) -> Self:
        if (self.analysis_scope is AnalysisScope.STATE_SPECIFIC) != (
            self.cell_state_id is not None
        ):
            raise ValueError("state-specific evidence requires one cell_state_id")
        if (self.numerator is None) != (self.denominator is None):
            raise ValueError("program-evidence counts must be paired")
        if (self.denominator is None) != (self.denominator_scope is None):
            raise ValueError("program-evidence denominator scope must be paired")
        if self.numerator is not None and self.numerator > self.denominator:
            raise ValueError("program-evidence numerator exceeds denominator")
        available = (
            self.applicability is ProgramApplicabilityState.APPLICABLE
            and self.availability is ProgramAvailabilityState.AVAILABLE
        )
        if self.assessment_state != ("available" if available else "not_assessed"):
            raise ValueError(
                "program assessment contradicts applicability/availability"
            )
        if not available and any(
            item is not None
            for item in (
                self.value,
                self.unit,
                self.numerator,
                self.denominator,
                self.denominator_scope,
            )
        ):
            raise ValueError(
                "not-assessed evidence cannot turn missing values into zeros"
            )
        if (
            self.process_attribution
            is not ProcessAttributionState.CONDITIONAL_ASSOCIATION
            and self.process_step_ids
        ):
            raise ValueError("unattributed evidence cannot expose process steps")
        if self.evidence_ids != [self.evidence_id]:
            raise ValueError("evidence row must bind its exact evidence_id")
        return self


class ProgramScoreVisualizationRecord(_SelectedCellRecord):
    component_ref: Literal[PROGRAM_SCORE_COMPONENT_REF] = PROGRAM_SCORE_COMPONENT_REF
    method_id: ProcessMethodId
    program_id: str = Field(min_length=1)
    observed_gene_count: StrictInt = Field(ge=0)
    declared_gene_count: StrictInt = Field(gt=0)
    gene_coverage: StrictFloat = Field(ge=0.0, le=1.0)
    gene_coverage_basis: Literal[
        "scanpy_positive_weight_targets_only",
        "decoupler_all_signed_weighted_targets",
    ]
    score_unit: Literal[
        "scanpy_control_adjusted_expression",
        "decoupler_ulm_t_value",
    ]
    mean: StrictFloat | None = None
    median: StrictFloat | None = None
    cell_distribution_lower_quantile: StrictFloat | None = None
    cell_distribution_upper_quantile: StrictFloat | None = None
    lower_quantile_probability: StrictFloat = Field(gt=0.0, lt=0.5)
    upper_quantile_probability: StrictFloat = Field(gt=0.5, lt=1.0)
    quantile_semantics: Literal[
        "selected_view_cell_distribution_not_confidence_interval"
    ] = "selected_view_cell_distribution_not_confidence_interval"

    @model_validator(mode="after")
    def score_summary_is_coherent(self) -> Self:
        if self.observed_gene_count > self.declared_gene_count:
            raise ValueError("observed gene count exceeds declared genes")
        if not math.isclose(
            self.gene_coverage,
            self.observed_gene_count / self.declared_gene_count,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError("score gene coverage does not match gene counts")
        expected = {
            ProcessMethodId.SCANPY_SCORE_GENES: (
                "scanpy_positive_weight_targets_only",
                "scanpy_control_adjusted_expression",
            ),
            ProcessMethodId.DECOUPLER_ULM: (
                "decoupler_all_signed_weighted_targets",
                "decoupler_ulm_t_value",
            ),
        }.get(self.method_id)
        if expected != (self.gene_coverage_basis, self.score_unit):
            raise ValueError("score unit/coverage basis does not match method")
        values = (
            self.mean,
            self.median,
            self.cell_distribution_lower_quantile,
            self.cell_distribution_upper_quantile,
        )
        if self.assessment_state == "available":
            if self.n_observations <= 0 or any(item is None for item in values):
                raise ValueError("available score requires cells and all summaries")
        elif any(item is not None for item in values):
            raise ValueError("not-assessed score cannot turn missing values into zeros")
        return self


class MethodAgreementVisualizationRecord(_EvidenceRecord):
    component_ref: Literal[PROGRAM_SCORE_COMPONENT_REF] = PROGRAM_SCORE_COMPONENT_REF
    display_scope: Literal["table_only"] = "table_only"
    program_id: str = Field(min_length=1)
    analysis_scope: AnalysisScope
    cell_state_id: str | None = None
    selected_expression_view_ref: str = Field(min_length=1)
    left_method_id: Literal[ProcessMethodId.SCANPY_SCORE_GENES] = (
        ProcessMethodId.SCANPY_SCORE_GENES
    )
    right_method_id: Literal[ProcessMethodId.DECOUPLER_ULM] = (
        ProcessMethodId.DECOUPLER_ULM
    )
    n_analysis_units: StrictInt = Field(ge=0)
    spearman_rho: StrictFloat | None = Field(default=None, ge=-1.0, le=1.0)
    agreement_semantics: Literal[
        "analysis_unit_rank_correlation_not_independent_replicate_validation"
    ] = "analysis_unit_rank_correlation_not_independent_replicate_validation"

    @model_validator(mode="after")
    def agreement_is_coherent(self) -> Self:
        if (self.analysis_scope is AnalysisScope.STATE_SPECIFIC) != (
            self.cell_state_id is not None
        ):
            raise ValueError("state-specific agreement requires one cell_state_id")
        available = self.assessment_state == "available"
        if available != (self.spearman_rho is not None):
            raise ValueError("method agreement contradicts assessment")
        if available and self.n_analysis_units < 2:
            raise ValueError("available agreement requires two analysis units")
        return self


class CellCycleVisualizationRecord(_SelectedCellRecord):
    component_ref: Literal[CELL_CYCLE_COMPONENT_REF] = CELL_CYCLE_COMPONENT_REF
    s_gene_coverage: StrictFloat = Field(ge=0.0, le=1.0)
    g2m_gene_coverage: StrictFloat = Field(ge=0.0, le=1.0)
    gene_coverage_basis: Literal[
        "scanpy_s_and_g2m_phase_gene_lists_assessed_separately"
    ] = "scanpy_s_and_g2m_phase_gene_lists_assessed_separately"
    mean_s_score: StrictFloat | None = None
    mean_g2m_score: StrictFloat | None = None
    score_unit: Literal["scanpy_relative_expression_score"] = (
        "scanpy_relative_expression_score"
    )
    g1_count: StrictInt | None = Field(default=None, ge=0)
    s_count: StrictInt | None = Field(default=None, ge=0)
    g2m_count: StrictInt | None = Field(default=None, ge=0)
    g1_fraction: StrictFloat | None = Field(default=None, ge=0.0, le=1.0)
    s_fraction: StrictFloat | None = Field(default=None, ge=0.0, le=1.0)
    g2m_fraction: StrictFloat | None = Field(default=None, ge=0.0, le=1.0)
    cycling_fraction: StrictFloat | None = Field(default=None, ge=0.0, le=1.0)
    phase_assignment_state: Literal["transcriptionally_assigned", "not_assessed"]

    @model_validator(mode="after")
    def phase_counts_and_fractions_are_coherent(self) -> Self:
        values = (
            self.mean_s_score,
            self.mean_g2m_score,
            self.g1_count,
            self.s_count,
            self.g2m_count,
            self.g1_fraction,
            self.s_fraction,
            self.g2m_fraction,
            self.cycling_fraction,
        )
        expected_phase_state = (
            "transcriptionally_assigned"
            if self.assessment_state == "available"
            else "not_assessed"
        )
        if self.phase_assignment_state != expected_phase_state:
            raise ValueError("phase-assignment state contradicts assessment")
        if self.assessment_state == "not_assessed":
            if any(item is not None for item in values):
                raise ValueError("not-assessed phase values must stay null, not zero")
            return self
        if self.n_observations <= 0 or any(item is None for item in values):
            raise ValueError("available cell-cycle row requires complete values")
        counts = (self.g1_count, self.s_count, self.g2m_count)
        fractions = (self.g1_fraction, self.s_fraction, self.g2m_fraction)
        if sum(counts) != self.n_observations:
            raise ValueError("phase counts must close to the cell denominator")
        expected = tuple(item / self.n_observations for item in counts)
        if any(
            not math.isclose(actual, wanted, rel_tol=0.0, abs_tol=1e-9)
            for actual, wanted in zip(fractions, expected, strict=True)
        ):
            raise ValueError("phase fractions must match phase counts")
        if not math.isclose(
            self.cycling_fraction,
            (self.s_count + self.g2m_count) / self.n_observations,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError("cycling fraction must equal S plus G2M fractions")
        return self


class ProliferationStressVisualizationDataV1(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[PROLIFERATION_STRESS_VISUALIZATION_DATA_SCHEMA_REF] = (
        PROLIFERATION_STRESS_VISUALIZATION_DATA_SCHEMA_REF
    )
    profile_id: str = Field(
        pattern=r"^proliferation-stress-visualization:[a-f0-9]{16}$"
    )
    producer_tool_id: Literal["P0-06"] = "P0-06"
    producer_tool_version: str = Field(min_length=1)
    producer_run_ref: str = Field(pattern=r"^run:run-[a-f0-9]{16}$")
    source_profile_id: str = Field(min_length=1)
    source_profile_version: Literal["0.1.0", "0.2.0"]
    product_case_ref: VersionedObjectRef
    product_definition_ref: VersionedObjectRef
    development_window_ref: VersionedObjectRef
    program_spec_ref: VersionedObjectRef
    cell_state_profile_ref: str = Field(min_length=1)
    protocol_context_ref: str = Field(min_length=1)
    input_sha256_by_role: dict[str, Sha256]
    analysis_mode: Literal["legacy_profile", "method_runtime"]
    analysis_interpretation: Literal["descriptive_only"] = "descriptive_only"
    evidence_state: Literal["shadow"] = "shadow"
    score_state: Literal["unavailable"] = "unavailable"
    domain_score: None = None
    method_spec_ref: str | None = None
    method_spec_sha256: Sha256 | None = None
    method_input_ref: str | None = None
    method_input_sha256: Sha256 | None = None
    method_bundle_ref: str | None = None
    method_bundle_sha256: Sha256 | None = None
    selected_expression_view_ref: str | None = None
    expression_asset_id: str | None = None
    expression_asset_sha256: Sha256 | None = None
    biological_unit_manifest_ref: str | None = None
    biological_unit_manifest_sha256: Sha256 | None = None
    biological_unit_assignment_sha256: Sha256 | None = None
    biological_unit_review_state: Literal["not_assessed"] = "not_assessed"
    biological_unit_review_reason_code: Literal[
        "biological_unit_review_state_not_carried"
    ] = "biological_unit_review_state_not_carried"
    lower_quantile_probability: StrictFloat | None = Field(default=None, gt=0.0, lt=0.5)
    upper_quantile_probability: StrictFloat | None = Field(default=None, gt=0.5, lt=1.0)
    reference_envelope_state: Literal["not_assessed"] = "not_assessed"
    reference_envelope_reason_code: Literal["typed_reference_envelope_not_supplied"] = (
        "typed_reference_envelope_not_supplied"
    )
    biological_unit_uncertainty_state: Literal["not_assessed"] = "not_assessed"
    biological_unit_uncertainty_reason_code: Literal[
        "biological_unit_uncertainty_not_estimated"
    ] = "biological_unit_uncertainty_not_estimated"
    program_evidence_records: list[ProgramEvidenceVisualizationRecord]
    program_score_records: list[ProgramScoreVisualizationRecord]
    method_agreement_records: list[MethodAgreementVisualizationRecord]
    cell_cycle_records: list[CellCycleVisualizationRecord]
    program_evidence_component_state: ComponentState
    program_evidence_component_reason_codes: list[str]
    program_score_component_state: ComponentState
    program_score_component_reason_codes: list[str]
    cell_cycle_component_state: ComponentState
    cell_cycle_component_reason_codes: list[str]
    evidence_ids: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)

    @field_validator(
        "program_evidence_component_reason_codes",
        "program_score_component_reason_codes",
        "cell_cycle_component_reason_codes",
        "evidence_ids",
        "limitations",
    )
    @classmethod
    def lists_are_sorted_unique(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)

    @field_validator("input_sha256_by_role")
    @classmethod
    def hashes_are_sorted(cls, values: dict[str, str]) -> dict[str, str]:
        if not values:
            raise ValueError("input SHA-256 bindings cannot be empty")
        return dict(sorted(values.items()))

    @model_validator(mode="after")
    def profile_bindings_and_states_are_coherent(self) -> Self:
        method_values = (
            self.method_spec_ref,
            self.method_spec_sha256,
            self.method_input_ref,
            self.method_input_sha256,
            self.method_bundle_ref,
            self.method_bundle_sha256,
            self.selected_expression_view_ref,
            self.expression_asset_id,
            self.expression_asset_sha256,
            self.biological_unit_manifest_ref,
            self.biological_unit_manifest_sha256,
            self.biological_unit_assignment_sha256,
            self.lower_quantile_probability,
            self.upper_quantile_probability,
        )
        if self.analysis_mode == "method_runtime" and not all(
            item is not None for item in method_values
        ):
            raise ValueError("method runtime requires complete method provenance")
        if self.analysis_mode == "legacy_profile" and any(
            item is not None for item in method_values
        ):
            raise ValueError("legacy profile cannot carry method provenance")
        method_records = (
            *self.program_score_records,
            *self.method_agreement_records,
            *self.cell_cycle_records,
        )
        if self.analysis_mode == "legacy_profile" and method_records:
            raise ValueError("legacy profile cannot expose method-derived records")
        if any(
            item.selected_expression_view_ref != self.selected_expression_view_ref
            for item in method_records
        ):
            raise ValueError("method rows must bind the selected expression view")
        all_records = (*self.program_evidence_records, *method_records)
        record_ids = [item.record_id for item in all_records]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("visualization record IDs must be unique")
        expected_states = (
            _component_state(self.program_evidence_records),
            _component_state(self.program_score_records),
            _component_state(self.cell_cycle_records),
        )
        if expected_states != (
            self.program_evidence_component_state,
            self.program_score_component_state,
            self.cell_cycle_component_state,
        ):
            raise ValueError("component states do not match row assessment states")
        row_evidence = {
            evidence_id for item in all_records for evidence_id in item.evidence_ids
        }
        if not row_evidence.issubset(self.evidence_ids):
            raise ValueError("row evidence IDs are not bound at profile level")
        return self


class P006VisualizationArtifactSet(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[P006_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF] = (
        P006_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF
    )
    artifact_set_id: str = Field(pattern=r"^p0-06-visualizations:[a-f0-9]{16}$")
    data_profile_artifact_id: str = Field(min_length=1)
    data_profile_sha256: Sha256
    visualizations: list[VisualizationArtifactV2] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def artifact_set_is_exactly_bound(self) -> Self:
        refs = [item.component_ref for item in self.visualizations]
        if set(refs) != set(P006_COMPONENT_REFS) or len(refs) != len(set(refs)):
            raise ValueError(
                "artifact set must contain each P0-06 component exactly once"
            )
        for artifact in self.visualizations:
            if artifact.data_binding.artifact_id != self.data_profile_artifact_id:
                raise ValueError("visualization must bind the data-profile artifact")
            if artifact.data_binding.sha256 != self.data_profile_sha256:
                raise ValueError("visualization must bind the exact data-profile hash")
        return self


def _source_binding_map(
    bindings: list[ProgramSourceBinding],
) -> dict[str, ProgramSourceBinding]:
    mapped: dict[str, ProgramSourceBinding] = {}
    for binding in bindings:
        if binding.role in mapped:
            raise ValueError(f"duplicate source binding role: {binding.role}")
        mapped[binding.role] = binding
    return mapped


def _strict_program_review_join(
    result: ProliferationStressResponseProfile,
) -> list[tuple[ProgramEvidenceSummary, TranscriptomicReviewFlag]]:
    flags = {item.evidence_id: item for item in result.review_flags}
    if len(flags) != len(result.review_flags):
        raise ValueError("review flag evidence IDs must be unique")
    seen: set[str] = set()
    joined: list[tuple[ProgramEvidenceSummary, TranscriptomicReviewFlag]] = []
    for summary in result.program_results:
        if summary.evidence_id in seen:
            raise ValueError("program result evidence IDs must be unique")
        seen.add(summary.evidence_id)
        flag = flags.get(summary.evidence_id)
        if flag is None:
            raise ValueError(f"missing review flag: {summary.evidence_id}")
        checks = (
            summary.program_id == flag.program_id,
            summary.analysis_scope is flag.analysis_scope,
            summary.cell_state_id == flag.cell_state_id,
            summary.stage_id == flag.stage_id,
            summary.applicability is flag.applicability,
            summary.availability is flag.availability,
            summary.process_attribution is flag.process_attribution,
            sorted(set(summary.reason_codes)) == sorted(set(flag.reason_codes)),
        )
        if not all(checks):
            raise ValueError(
                f"program result/review flag mismatch: {summary.evidence_id}"
            )
        joined.append((summary, flag))
    if seen != set(flags):
        raise ValueError("program result and review flag IDs must match exactly")
    return joined


def _program_evidence_row(
    index: int,
    summary: ProgramEvidenceSummary,
    flag: TranscriptomicReviewFlag,
) -> ProgramEvidenceVisualizationRecord:
    available = (
        summary.applicability is ProgramApplicabilityState.APPLICABLE
        and summary.availability is ProgramAvailabilityState.AVAILABLE
    )
    return ProgramEvidenceVisualizationRecord(
        record_id=f"program-evidence.{index:03d}",
        evidence_ids=[summary.evidence_id],
        assessment_state="available" if available else "not_assessed",
        reason_codes=sorted(set(summary.reason_codes) | set(flag.reason_codes)),
        evidence_id=summary.evidence_id,
        review_flag_id=flag.flag_id,
        program_id=summary.program_id,
        analysis_scope=summary.analysis_scope,
        cell_state_id=summary.cell_state_id,
        stage_id=summary.stage_id,
        metric_id=summary.metric_id,
        value=summary.value if available else None,
        unit=summary.unit if available else None,
        numerator=summary.numerator if available else None,
        denominator=summary.denominator if available else None,
        denominator_scope=(
            "supplied_program_evidence_denominator"
            if available and summary.denominator is not None
            else None
        ),
        gene_coverage=summary.gene_coverage,
        minimum_gene_coverage=summary.minimum_gene_coverage,
        lod_state=summary.lod_state,
        source_evidence_state=summary.evidence_state,
        applicability=summary.applicability,
        availability=summary.availability,
        process_attribution=summary.process_attribution,
        process_step_ids=sorted(set(summary.process_step_ids)),
        review_flag_state=flag.review_flag_state,
        flag_status=flag.flag_status,
        orthogonal_follow_up_refs=sorted(set(flag.orthogonal_follow_up_refs)),
    )


def _validate_method_bindings(
    *,
    tool_version: str,
    result: ProliferationStressResponseProfile,
    sources: dict[str, ProgramSourceBinding],
    spec: ProcessMethodSpec,
    method_input: ProcessMethodInput,
    bundle: ProcessMethodBundle,
    bundle_sha256: str,
) -> None:
    if re.fullmatch(_SHA256_PATTERN, bundle_sha256) is None:
        raise ValueError("method bundle hash must be lowercase SHA-256")
    if bundle.tool_version != tool_version or not spec.active:
        raise ValueError("method bundle tool version/spec activation mismatch")
    if list(spec.selected_method_ids) != list(bundle.selected_method_ids):
        raise ValueError("selected method IDs do not match method bundle")
    if spec.expression_asset_id != bundle.expression_asset_id:
        raise ValueError("expression asset ID does not match method bundle")
    if not (
        math.isclose(
            spec.lower_quantile,
            bundle.lower_quantile,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        and math.isclose(
            spec.upper_quantile,
            bundle.upper_quantile,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
    ):
        raise ValueError("method quantile levels do not match bundle")
    required = {"product_case", "cell_state_evidence_profile", "program_spec"}
    if not required.issubset(sources):
        raise ValueError("profile is missing method-lineage source bindings")
    if method_input.product_case_ref != result.product_case_ref.ref:
        raise ValueError("method input product case does not match profile")
    if method_input.cell_state_profile_id != result.cell_state_profile_ref:
        raise ValueError("method input cell-state profile does not match profile")
    if (
        method_input.product_case_sha256 != sources["product_case"].source_sha256
        or method_input.cell_state_profile_sha256
        != sources["cell_state_evidence_profile"].source_sha256
        or bundle.program_spec_sha256 != sources["program_spec"].source_sha256
    ):
        raise ValueError("method lineage hashes do not match profile inputs")
    if (
        method_input.biological_unit_manifest_sha256
        != bundle.biological_unit_manifest_sha256
        or method_input.biological_unit_assignment_sha256
        != bundle.biological_unit_assignment_sha256
    ):
        raise ValueError("biological-unit lineage does not match method bundle")
    methods = set(bundle.selected_method_ids)
    if any(item.method_id not in methods for item in bundle.program_scores):
        raise ValueError("program score uses an unselected method")
    if bundle.cell_cycle_summaries and ProcessMethodId.SCANPY_CELL_CYCLE not in methods:
        raise ValueError("cell-cycle summaries require selected cell-cycle scoring")
    scopes = set(spec.selected_analysis_scopes)
    outputs = (
        *bundle.program_scores,
        *bundle.cell_cycle_summaries,
        *bundle.method_agreement,
    )
    if any(item.analysis_scope not in scopes for item in outputs):
        raise ValueError("method output uses an unselected analysis scope")
    programs = {item.program_id for item in spec.programs}
    if any(
        item.program_id not in programs
        for item in (*bundle.program_scores, *bundle.method_agreement)
    ):
        raise ValueError("method output uses an unselected program")


def _program_score_row(
    index: int,
    summary: ProgramScoreSummary,
    method_input: ProcessMethodInput,
    bundle: ProcessMethodBundle,
) -> ProgramScoreVisualizationRecord:
    available = summary.assessment_state == "available"
    basis = (
        "scanpy_positive_weight_targets_only"
        if summary.method_id is ProcessMethodId.SCANPY_SCORE_GENES
        else "decoupler_all_signed_weighted_targets"
    )
    return ProgramScoreVisualizationRecord(
        record_id=f"program-score.{index:03d}",
        evidence_ids=[bundle.bundle_id],
        assessment_state=summary.assessment_state,
        reason_codes=sorted(set(summary.reason_codes)),
        method_id=summary.method_id,
        program_id=summary.program_id,
        analysis_scope=summary.analysis_scope,
        expression_view_scope=_expression_view_scope(summary.analysis_scope),
        analysis_unit_ref=summary.analysis_unit_ref,
        independence_group_ref=summary.independence_group_ref,
        cell_state_id=summary.cell_state_id,
        selected_expression_view_ref=method_input.data_view_ref,
        n_observations=summary.n_observations,
        observed_gene_count=summary.observed_gene_count,
        declared_gene_count=summary.declared_gene_count,
        gene_coverage=summary.gene_coverage,
        gene_coverage_basis=basis,
        score_unit=summary.score_unit,
        mean=summary.mean if available else None,
        median=summary.median if available else None,
        cell_distribution_lower_quantile=summary.lower_quantile if available else None,
        cell_distribution_upper_quantile=summary.upper_quantile if available else None,
        lower_quantile_probability=bundle.lower_quantile,
        upper_quantile_probability=bundle.upper_quantile,
    )


def _method_agreement_row(
    index: int,
    record: MethodAgreementRecord,
    method_input: ProcessMethodInput,
    bundle: ProcessMethodBundle,
) -> MethodAgreementVisualizationRecord:
    return MethodAgreementVisualizationRecord(
        record_id=f"agreement.{index:03d}",
        evidence_ids=[bundle.bundle_id],
        assessment_state=record.assessment_state,
        reason_codes=sorted(set(record.reason_codes)),
        program_id=record.program_id,
        analysis_scope=record.analysis_scope,
        cell_state_id=record.cell_state_id,
        selected_expression_view_ref=method_input.data_view_ref,
        n_analysis_units=record.n_analysis_units,
        spearman_rho=record.spearman_rho,
    )


def _cell_cycle_row(
    index: int,
    summary: CellCycleSummary,
    method_input: ProcessMethodInput,
    bundle: ProcessMethodBundle,
) -> CellCycleVisualizationRecord:
    available = summary.assessment_state == "available"
    if available and summary.n_observations <= 0:
        raise ValueError("available cell-cycle summary requires a positive denominator")
    counts = (
        (
            summary.phase_counts["G1"],
            summary.phase_counts["S"],
            summary.phase_counts["G2M"],
        )
        if available
        else (None, None, None)
    )
    fractions = (
        tuple(item / summary.n_observations for item in counts) if available else counts
    )
    return CellCycleVisualizationRecord(
        record_id=f"cell-cycle.{index:03d}",
        evidence_ids=[bundle.bundle_id],
        assessment_state=summary.assessment_state,
        reason_codes=sorted(set(summary.reason_codes)),
        analysis_scope=summary.analysis_scope,
        expression_view_scope=_expression_view_scope(summary.analysis_scope),
        analysis_unit_ref=summary.analysis_unit_ref,
        independence_group_ref=summary.independence_group_ref,
        cell_state_id=summary.cell_state_id,
        selected_expression_view_ref=method_input.data_view_ref,
        n_observations=summary.n_observations,
        s_gene_coverage=summary.s_gene_coverage,
        g2m_gene_coverage=summary.g2m_gene_coverage,
        mean_s_score=summary.mean_s_score if available else None,
        mean_g2m_score=summary.mean_g2m_score if available else None,
        g1_count=counts[0] if available else None,
        s_count=counts[1] if available else None,
        g2m_count=counts[2] if available else None,
        g1_fraction=fractions[0],
        s_fraction=fractions[1],
        g2m_fraction=fractions[2],
        cycling_fraction=summary.cycling_fraction if available else None,
        phase_assignment_state="transcriptionally_assigned"
        if available
        else "not_assessed",
    )


def _component_state(records: list[_EvidenceRecord]) -> ComponentState:
    available = sum(item.assessment_state == "available" for item in records)
    if records and available == len(records):
        return "available"
    return "partial" if available else "not_assessed"


def _component_reasons(records: list[_EvidenceRecord], absent: str) -> list[str]:
    if not records:
        return [absent]
    return sorted({reason for item in records for reason in item.reason_codes})


def build_proliferation_stress_visualization_data(
    *,
    run_id: str,
    tool_version: str,
    result: ProliferationStressResponseProfile,
    method_spec: ProcessMethodSpec | None = None,
    method_input: ProcessMethodInput | None = None,
    method_bundle: ProcessMethodBundle | None = None,
    method_bundle_sha256: str | None = None,
) -> ProliferationStressVisualizationDataV1:
    match = re.fullmatch(r"run-([a-f0-9]{16})", run_id)
    if match is None:
        raise ValueError("run_id must contain 16 lowercase hex characters")
    sources = _source_binding_map(result.source_bindings)
    if "program_evidence_bundle" not in sources:
        raise ValueError("program_evidence_bundle source binding is required")
    joined = _strict_program_review_join(result)
    evidence_rows = [
        _program_evidence_row(index, summary, flag)
        for index, (summary, flag) in enumerate(joined, start=1)
    ]
    supplied = (method_spec, method_input, method_bundle, method_bundle_sha256)
    if any(item is not None for item in supplied) and not all(
        item is not None for item in supplied
    ):
        raise ValueError("method spec, input, bundle and hash must be paired")
    score_rows: list[ProgramScoreVisualizationRecord] = []
    agreement_rows: list[MethodAgreementVisualizationRecord] = []
    cycle_rows: list[CellCycleVisualizationRecord] = []
    hashes = {role: item.source_sha256 for role, item in sources.items()}
    method_field_names = (
        "method_spec_ref",
        "method_spec_sha256",
        "method_input_ref",
        "method_input_sha256",
        "method_bundle_ref",
        "method_bundle_sha256",
        "selected_expression_view_ref",
        "expression_asset_id",
        "expression_asset_sha256",
        "biological_unit_manifest_ref",
        "biological_unit_manifest_sha256",
        "biological_unit_assignment_sha256",
        "lower_quantile_probability",
        "upper_quantile_probability",
    )
    method_fields = dict.fromkeys(method_field_names)
    if method_bundle is not None:
        assert method_spec is not None
        assert method_input is not None
        assert method_bundle_sha256 is not None
        _validate_method_bindings(
            tool_version=tool_version,
            result=result,
            sources=sources,
            spec=method_spec,
            method_input=method_input,
            bundle=method_bundle,
            bundle_sha256=method_bundle_sha256,
        )
        score_rows = [
            _program_score_row(index, item, method_input, method_bundle)
            for index, item in enumerate(method_bundle.program_scores, start=1)
        ]
        agreement_rows = [
            _method_agreement_row(index, item, method_input, method_bundle)
            for index, item in enumerate(method_bundle.method_agreement, start=1)
        ]
        cycle_rows = [
            _cell_cycle_row(index, item, method_input, method_bundle)
            for index, item in enumerate(method_bundle.cell_cycle_summaries, start=1)
        ]
        hashes.update(
            {
                "process_method_spec": method_bundle.method_spec_sha256,
                "process_method_input": method_bundle.method_input_sha256,
                "process_method_bundle": method_bundle_sha256,
                "expression_asset": method_bundle.expression_asset_sha256,
                "biological_unit_manifest": method_bundle.biological_unit_manifest_sha256,
                "biological_unit_assignment": method_bundle.biological_unit_assignment_sha256,
            }
        )
        method_fields = {
            "method_spec_ref": f"{method_spec.method_spec_id}@{method_spec.method_spec_version}",
            "method_spec_sha256": method_bundle.method_spec_sha256,
            "method_input_ref": f"{method_input.method_input_id}@{method_input.method_input_version}",
            "method_input_sha256": method_bundle.method_input_sha256,
            "method_bundle_ref": method_bundle.bundle_id,
            "method_bundle_sha256": method_bundle_sha256,
            "selected_expression_view_ref": method_input.data_view_ref,
            "expression_asset_id": method_bundle.expression_asset_id,
            "expression_asset_sha256": method_bundle.expression_asset_sha256,
            "biological_unit_manifest_ref": method_input.biological_unit_manifest_ref,
            "biological_unit_manifest_sha256": method_bundle.biological_unit_manifest_sha256,
            "biological_unit_assignment_sha256": method_bundle.biological_unit_assignment_sha256,
            "lower_quantile_probability": method_bundle.lower_quantile,
            "upper_quantile_probability": method_bundle.upper_quantile,
        }
    evidence_ids = {item.evidence_id for item in result.program_results}
    if method_bundle is not None:
        evidence_ids.add(method_bundle.bundle_id)
    return ProliferationStressVisualizationDataV1(
        profile_id=f"proliferation-stress-visualization:{match.group(1)}",
        producer_tool_version=tool_version,
        producer_run_ref=f"run:{run_id}",
        source_profile_id=result.profile_id,
        source_profile_version=result.profile_version,
        product_case_ref=result.product_case_ref,
        product_definition_ref=result.product_definition_ref,
        development_window_ref=result.development_window_ref,
        program_spec_ref=result.program_spec_ref,
        cell_state_profile_ref=result.cell_state_profile_ref,
        protocol_context_ref=result.protocol_context_ref,
        input_sha256_by_role=hashes,
        analysis_mode="method_runtime" if method_bundle else "legacy_profile",
        program_evidence_records=evidence_rows,
        program_score_records=score_rows,
        method_agreement_records=agreement_rows,
        cell_cycle_records=cycle_rows,
        program_evidence_component_state=_component_state(evidence_rows),
        program_evidence_component_reason_codes=_component_reasons(
            evidence_rows, "program_evidence_records_not_supplied"
        ),
        program_score_component_state=_component_state(score_rows),
        program_score_component_reason_codes=_component_reasons(
            score_rows,
            "method_bundle_not_supplied"
            if method_bundle is None
            else "program_score_summary_not_generated",
        ),
        cell_cycle_component_state=_component_state(cycle_rows),
        cell_cycle_component_reason_codes=_component_reasons(
            cycle_rows,
            "method_bundle_not_supplied"
            if method_bundle is None
            else "cell_cycle_summary_not_generated",
        ),
        evidence_ids=sorted(evidence_ids),
        limitations=sorted(
            {
                "biological_unit_uncertainty_not_estimated",
                "cell_cycle_is_transcriptional_assignment_not_proliferation_rate",
                "cells_are_not_independent_biological_replicates",
                "method_agreement_is_table_only_not_independent_replicate_validation",
                "method_score_scales_are_not_cross_method_comparable",
                "reference_envelope_not_assessed",
                "results_are_descriptive_not_safety_potency_or_release_evidence",
                "score_quantiles_are_selected_view_cell_distributions_not_confidence_intervals",
                "whole_product_method_results_describe_the_selected_expression_view",
            }
        ),
        **method_fields,
    )


PUBLIC_VISUALIZATION_SCHEMA_MODELS = {
    PROLIFERATION_STRESS_VISUALIZATION_DATA_SCHEMA_REF: ProliferationStressVisualizationDataV1,
    P006_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF: P006VisualizationArtifactSet,
}
__all__ = [
    "CELL_CYCLE_COMPONENT_REF",
    "P006_COMPONENT_REFS",
    "P006_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF",
    "PROGRAM_EVIDENCE_COMPONENT_REF",
    "PROGRAM_SCORE_COMPONENT_REF",
    "PROLIFERATION_STRESS_VISUALIZATION_DATA_SCHEMA_REF",
    "PUBLIC_VISUALIZATION_SCHEMA_MODELS",
    "CellCycleVisualizationRecord",
    "MethodAgreementVisualizationRecord",
    "P006VisualizationArtifactSet",
    "ProgramEvidenceVisualizationRecord",
    "ProgramScoreVisualizationRecord",
    "ProliferationStressVisualizationDataV1",
    "build_proliferation_stress_visualization_data",
]
