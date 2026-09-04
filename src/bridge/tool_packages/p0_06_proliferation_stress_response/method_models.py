from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal, Self

from pydantic import (
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    field_validator,
    model_validator,
)

from bridge.tool_packages.p0_06_proliferation_stress_response.models import (
    AnalysisScope,
    SafeId,
    Sha256,
)
from bridge.toolkit.contracts import FrozenModel


def _unique(values: list[object], name: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must contain unique values")


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("created_at must include a timezone")
    return value.astimezone(timezone.utc)


class ProcessMethodId(StrEnum):
    SCANPY_SCORE_GENES = "PROC-SCORE-SCANPY"
    DECOUPLER_ULM = "PROC-SCORE-DECOUPLER"
    SCANPY_CELL_CYCLE = "PROC-CYCLE-SCANPY"
    CELL_CYCLE_AGGREGATION = "PROC-CYCLE-AGG"


class MethodExecutionState(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    NOT_ASSESSED = "not_assessed"


class ObservationState(StrEnum):
    CANDIDATE = "candidate"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


class ProcessProgramSelection(FrozenModel):
    program_id: SafeId


class ProcessMethodSpec(FrozenModel):
    object_version: Literal["0.1.0"]
    method_spec_id: str = Field(
        pattern=r"^process-method-spec:[A-Za-z0-9._:-]+$"
    )
    method_spec_version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    status: Literal["candidate"]
    expression_asset_id: str = Field(min_length=1)
    expression_layer: str | None = Field(
        default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_.-]*$"
    )
    gene_symbol_column: str | None = Field(
        default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_.-]*$"
    )
    selected_method_ids: list[ProcessMethodId] = Field(min_length=1)
    selected_analysis_scopes: list[AnalysisScope] = Field(min_length=1)
    programs: list[ProcessProgramSelection] = Field(default_factory=list)
    cell_cycle: ProcessProgramSelection | None = None
    scanpy_ctrl_size: StrictInt = Field(default=50, ge=1, le=500)
    scanpy_n_bins: StrictInt = Field(default=25, ge=2, le=100)
    scanpy_ctrl_as_ref: bool = True
    decoupler_tmin: StrictInt = Field(default=5, ge=2, le=100)
    minimum_cells_per_summary: StrictInt = Field(default=10, ge=1)
    lower_quantile: StrictFloat = Field(default=0.1, gt=0.0, lt=0.5)
    upper_quantile: StrictFloat = Field(default=0.9, gt=0.5, lt=1.0)
    active: bool

    @field_validator(
        "selected_method_ids",
        "selected_analysis_scopes",
        "programs",
    )
    @classmethod
    def configured_values_are_unique(cls, value: list[object]) -> list[object]:
        keys = [
            item.program_id if isinstance(item, ProcessProgramSelection) else item
            for item in value
        ]
        _unique(keys, "configured method values")
        return value

    @model_validator(mode="after")
    def method_inputs_are_complete(self) -> Self:
        selected = set(self.selected_method_ids)
        scoring = {
            ProcessMethodId.SCANPY_SCORE_GENES,
            ProcessMethodId.DECOUPLER_ULM,
        }
        if selected.intersection(scoring) and not self.programs:
            raise ValueError("selected program scorers require program selections")
        if ProcessMethodId.SCANPY_CELL_CYCLE in selected and self.cell_cycle is None:
            raise ValueError("cell-cycle scoring requires a cell-cycle selection")
        if (
            ProcessMethodId.CELL_CYCLE_AGGREGATION in selected
            and ProcessMethodId.SCANPY_CELL_CYCLE not in selected
        ):
            raise ValueError("cell-cycle aggregation requires Scanpy cell-cycle scoring")
        if self.lower_quantile >= self.upper_quantile:
            raise ValueError("summary quantiles must be ordered")
        return self


class ObservationStateAssignment(FrozenModel):
    observation_id: str = Field(min_length=1)
    state_id: SafeId | None = None
    state: ObservationState

    @model_validator(mode="after")
    def state_identity_is_coherent(self) -> Self:
        if (self.state is ObservationState.CANDIDATE) != (self.state_id is not None):
            raise ValueError("candidate state requires one state_id")
        return self


class ProcessMethodInput(FrozenModel):
    object_version: Literal["0.1.0"]
    method_input_id: str = Field(
        pattern=r"^process-method-input:[A-Za-z0-9._:-]+$"
    )
    method_input_version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    product_case_ref: str = Field(min_length=1)
    product_case_sha256: Sha256
    cell_state_profile_id: SafeId
    cell_state_profile_sha256: Sha256
    data_view_ref: str = Field(min_length=1)
    observation_ids_sha256: Sha256
    biological_unit_manifest_ref: str = Field(min_length=1)
    biological_unit_manifest_sha256: Sha256
    biological_unit_assignment_sha256: Sha256
    observation_states: list[ObservationStateAssignment] = Field(min_length=1)
    created_at: datetime

    @field_validator("observation_states")
    @classmethod
    def observations_are_unique(
        cls, value: list[ObservationStateAssignment]
    ) -> list[ObservationStateAssignment]:
        _unique([item.observation_id for item in value], "observation IDs")
        return value

    _created_at_utc = field_validator("created_at")(_aware_utc)


class MethodExecutionRecord(FrozenModel):
    method_id: ProcessMethodId
    method_ref: str = Field(pattern=r"^METHOD-[A-Z0-9-]+$")
    implementation: str = Field(min_length=1)
    execution_state: MethodExecutionState
    package_versions: dict[str, str]
    reason_codes: list[SafeId]


class ProgramScoreSummary(FrozenModel):
    method_id: ProcessMethodId
    program_id: SafeId
    analysis_scope: AnalysisScope
    analysis_unit_ref: str = Field(min_length=1)
    independence_group_ref: str = Field(min_length=1)
    cell_state_id: SafeId | None = None
    n_observations: StrictInt = Field(ge=0)
    observed_gene_count: StrictInt = Field(ge=0)
    declared_gene_count: StrictInt = Field(gt=0)
    gene_coverage: StrictFloat = Field(ge=0.0, le=1.0)
    score_unit: Literal[
        "scanpy_control_adjusted_expression",
        "decoupler_ulm_t_value",
    ]
    mean: StrictFloat | None = None
    median: StrictFloat | None = None
    lower_quantile: StrictFloat | None = None
    upper_quantile: StrictFloat | None = None
    assessment_state: Literal["available", "not_assessed"]
    reason_codes: list[SafeId]

    @model_validator(mode="after")
    def summary_state_is_coherent(self) -> Self:
        values = (self.mean, self.median, self.lower_quantile, self.upper_quantile)
        if self.assessment_state == "available":
            if any(value is None for value in values) or self.reason_codes:
                raise ValueError("available summary requires values and no reasons")
        elif any(value is not None for value in values) or not self.reason_codes:
            raise ValueError("not_assessed summary requires reasons and no values")
        if (self.analysis_scope is AnalysisScope.STATE_SPECIFIC) != (
            self.cell_state_id is not None
        ):
            raise ValueError("state-specific summary requires one state_id")
        return self


class CellCycleSummary(FrozenModel):
    analysis_scope: AnalysisScope
    analysis_unit_ref: str = Field(min_length=1)
    independence_group_ref: str = Field(min_length=1)
    cell_state_id: SafeId | None = None
    n_observations: StrictInt = Field(ge=0)
    s_gene_coverage: StrictFloat = Field(ge=0.0, le=1.0)
    g2m_gene_coverage: StrictFloat = Field(ge=0.0, le=1.0)
    mean_s_score: StrictFloat | None = None
    mean_g2m_score: StrictFloat | None = None
    phase_counts: dict[Literal["G1", "S", "G2M"], StrictInt]
    cycling_fraction: StrictFloat | None = Field(default=None, ge=0.0, le=1.0)
    assessment_state: Literal["available", "not_assessed"]
    reason_codes: list[SafeId]

    @model_validator(mode="after")
    def cycle_summary_is_coherent(self) -> Self:
        available = self.assessment_state == "available"
        values_present = (
            self.mean_s_score is not None
            and self.mean_g2m_score is not None
            and self.cycling_fraction is not None
        )
        if available != values_present:
            raise ValueError("cell-cycle values and assessment state disagree")
        if available and sum(self.phase_counts.values()) != self.n_observations:
            raise ValueError("phase counts must equal summary denominator")
        if available and self.reason_codes:
            raise ValueError("available cell-cycle summary cannot retain reasons")
        if not available and not self.reason_codes:
            raise ValueError("not_assessed cell-cycle summary requires reasons")
        if (self.analysis_scope is AnalysisScope.STATE_SPECIFIC) != (
            self.cell_state_id is not None
        ):
            raise ValueError("state-specific summary requires one state_id")
        return self


class MethodAgreementRecord(FrozenModel):
    program_id: SafeId
    analysis_scope: AnalysisScope
    cell_state_id: SafeId | None = None
    n_analysis_units: StrictInt = Field(ge=0)
    spearman_rho: StrictFloat | None = Field(default=None, ge=-1.0, le=1.0)
    assessment_state: Literal["available", "not_assessed"]
    reason_codes: list[SafeId]

    @model_validator(mode="after")
    def agreement_is_coherent(self) -> Self:
        available = self.assessment_state == "available"
        if available != (self.spearman_rho is not None):
            raise ValueError("agreement value and assessment state disagree")
        if available == bool(self.reason_codes):
            raise ValueError("agreement reasons and assessment state disagree")
        if (self.analysis_scope is AnalysisScope.STATE_SPECIFIC) != (
            self.cell_state_id is not None
        ):
            raise ValueError("state-specific agreement requires one state_id")
        return self


class ProcessMethodBundle(FrozenModel):
    object_version: Literal["0.1.0"]
    bundle_id: str = Field(pattern=r"^process-method-bundle:[a-f0-9]{16}$")
    tool_id: Literal["P0-06"]
    tool_version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    method_spec_sha256: Sha256
    program_spec_sha256: Sha256
    method_input_sha256: Sha256
    expression_asset_id: str = Field(min_length=1)
    expression_asset_sha256: Sha256
    biological_unit_manifest_sha256: Sha256
    biological_unit_assignment_sha256: Sha256
    analysis_unit_refs: list[str]
    independence_group_refs: list[str]
    selected_method_ids: list[ProcessMethodId]
    lower_quantile: StrictFloat
    upper_quantile: StrictFloat
    executions: list[MethodExecutionRecord]
    program_scores: list[ProgramScoreSummary]
    cell_cycle_summaries: list[CellCycleSummary]
    method_agreement: list[MethodAgreementRecord]
    evidence_state: Literal["shadow"]
    score_state: Literal["unavailable"]
    domain_score: None = None
    created_at: datetime
    @model_validator(mode="after")
    def execution_contract_is_coherent(self) -> Self:
        selected = list(self.selected_method_ids)
        executed = [item.method_id for item in self.executions]
        if len(selected) != len(set(selected)):
            raise ValueError("selected method IDs must be unique")
        if len(executed) != len(set(executed)) or set(executed) != set(selected):
            raise ValueError("executions must match selected method IDs")
        if len(self.analysis_unit_refs) != len(set(self.analysis_unit_refs)):
            raise ValueError("analysis unit refs must be unique")
        if len(self.independence_group_refs) != len(
            set(self.independence_group_refs)
        ):
            raise ValueError("independence group refs must be unique")
        if any(
            item.analysis_unit_ref not in self.analysis_unit_refs
            or item.independence_group_ref not in self.independence_group_refs
            for item in self.program_scores + self.cell_cycle_summaries
        ):
            raise ValueError("summaries must bind declared biological units")
        return self


    _created_at_utc = field_validator("created_at")(_aware_utc)


class ProcessMethodBundleV2(ProcessMethodBundle):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {
                            "input_matrix_semantics": {"const": "raw_counts"}
                        },
                        "required": ["input_matrix_semantics"],
                    },
                    "then": {
                        "required": [
                            "normalization_recipe_id",
                            "normalization_target_sum",
                        ],
                        "properties": {
                            "normalization_recipe_id": {
                                "const": "bridge_normalize_total_log1p_v0.1"
                            },
                            "normalization_target_sum": {"const": 10000.0},
                        },
                    },
                    "else": {
                        "properties": {
                            "normalization_recipe_id": {"type": "null"},
                            "normalization_target_sum": {"type": "null"},
                        }
                    },
                }
            ]
        }
    )

    object_version: Literal["0.2.0"]
    input_matrix_location: str = Field(min_length=1)
    input_matrix_semantics: Literal["raw_counts", "normalized_expression"]
    analysis_matrix_semantics: Literal["normalized_expression"] = (
        "normalized_expression"
    )
    normalization_recipe_id: Literal[
        "bridge_normalize_total_log1p_v0.1"
    ] | None = None
    normalization_target_sum: StrictFloat | None = Field(default=None, gt=0.0)

    @model_validator(mode="after")
    def normalization_lineage_is_coherent(self) -> Self:
        if self.input_matrix_semantics == "raw_counts":
            if (
                self.normalization_recipe_id
                != "bridge_normalize_total_log1p_v0.1"
                or self.normalization_target_sum != 10000.0
            ):
                raise ValueError(
                    "raw counts require package-owned 1e4 normalize_total and log1p"
                )
        elif (
            self.normalization_recipe_id is not None
            or self.normalization_target_sum is not None
        ):
            raise ValueError(
                "pre-normalized input cannot claim package-owned normalization"
            )
        return self


PUBLIC_METHOD_SCHEMA_MODELS = {
    "bridge://schemas/process-method-spec/v0.1": ProcessMethodSpec,
    "bridge://schemas/process-method-input/v0.1": ProcessMethodInput,
    "bridge://schemas/process-method-bundle/v0.1": ProcessMethodBundle,
    "bridge://schemas/process-method-bundle/v0.2": ProcessMethodBundleV2,
}
