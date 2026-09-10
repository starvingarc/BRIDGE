"""Typed, non-gate-facing descriptive P0-06 measurement contracts."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Literal, Self

from pydantic import (
    Field,
    RootModel,
    StrictFloat,
    StrictInt,
    field_validator,
    model_validator,
)

from bridge.tool_packages.p0_06_proliferation_stress_response.method_models import (
    MethodExecutionRecord,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.models import (
    PublishedRef,
    SafeId,
    Sha256,
    _aware_utc,
    ProliferationStressResponseProfileV3,
)
from bridge.toolkit.contracts import DataViewBinding, FrozenModel

EXPLORATORY_INPUT_SCHEMA = "bridge://schemas/exploratory-process-input/v0.1"
P006_RESULT_SCHEMA = "bridge://schemas/proliferation-stress-response-result/v0.1"


class ExploratoryProcessInput(FrozenModel):
    object_version: Literal["0.1.0"]
    input_id: SafeId
    source_family_id: SafeId
    data_view: DataViewBinding
    gene_symbol_column: str | None = Field(default=None, min_length=1)
    resource_ref: PublishedRef
    resource_version: str = Field(min_length=1)
    resource_sha256: Sha256
    s_genes: list[str] = Field(min_length=5)
    s_genes_sha256: Sha256
    g2m_genes: list[str] = Field(min_length=5)
    g2m_genes_sha256: Sha256
    created_at: datetime

    @model_validator(mode="after")
    def gene_resource_is_coherent(self) -> Self:
        for genes, expected in (
            (self.s_genes, self.s_genes_sha256),
            (self.g2m_genes, self.g2m_genes_sha256),
        ):
            if len(set(genes)) != len(genes):
                raise ValueError("gene lists must be unique")
            if any(not gene or any(c.isspace() for c in gene) for gene in genes):
                raise ValueError(
                    "gene symbols must be nonempty and contain no whitespace"
                )
            digest = hashlib.sha256(
                ("\n".join(genes) + "\n").encode("utf-8")
            ).hexdigest()
            if digest != expected:
                raise ValueError("gene list content checksum mismatch")
        if set(self.s_genes).intersection(self.g2m_genes):
            raise ValueError("S and G2M gene programs must be disjoint")
        return self

    _created_at_utc = field_validator("created_at")(_aware_utc)


class ExploratoryMethodParameters(FrozenModel):
    """Versioned first-mode parameters, not a product-specific decision rule."""

    minimum_gene_coverage: Literal[1.0] = 1.0
    scanpy_ctrl_size: Literal[50] = 50
    cell_cycle_ctrl_size: StrictInt = Field(ge=5)
    scanpy_n_bins: Literal[25] = 25
    scanpy_ctrl_as_ref: Literal[True] = True
    decoupler_tmin: Literal[5] = 5
    decoupler_empty: Literal[False] = False
    use_raw: Literal[False] = False
    layer: None = None
    lower_quantile: Literal[0.1] = 0.1
    upper_quantile: Literal[0.9] = 0.9
    random_seed: StrictInt


class ExploratoryProgramSummary(FrozenModel):
    program_id: Literal["S", "G2M"]
    method_id: Literal["PROC-SCORE-SCANPY", "PROC-SCORE-DECOUPLER"]
    score_unit: Literal["scanpy_control_adjusted_expression", "decoupler_ulm_t_value"]
    n_observations: StrictInt = Field(gt=0)
    observed_gene_count: StrictInt = Field(ge=0)
    declared_gene_count: StrictInt = Field(gt=0)
    missing_genes: list[str]
    ambiguous_genes: list[str] = Field(default_factory=list)
    mean: StrictFloat | None = None
    median: StrictFloat | None = None
    lower_quantile: StrictFloat | None = None
    upper_quantile: StrictFloat | None = None
    assessment_state: Literal["available", "not_assessed"]
    reason_codes: list[SafeId]

    @model_validator(mode="after")
    def measurement_state_is_coherent(self) -> Self:
        values = [self.mean, self.median, self.lower_quantile, self.upper_quantile]
        if self.assessment_state == "available":
            if (
                any(v is None for v in values)
                or self.reason_codes
                or self.missing_genes
                or self.ambiguous_genes
            ):
                raise ValueError(
                    "available program requires complete genes and finite values"
                )
        elif any(v is not None for v in values) or not self.reason_codes:
            raise ValueError("unassessed program requires reasons and null values")
        if (
            self.observed_gene_count
            + len(self.missing_genes)
            + len(self.ambiguous_genes)
            != self.declared_gene_count
        ):
            raise ValueError("gene coverage denominator mismatch")
        return self


class ExploratoryCellCycleSummary(FrozenModel):
    n_observations: StrictInt = Field(gt=0)
    s_missing_genes: list[str]
    g2m_missing_genes: list[str]
    s_ambiguous_genes: list[str] = Field(default_factory=list)
    g2m_ambiguous_genes: list[str] = Field(default_factory=list)
    phase_counts: dict[Literal["G1", "S", "G2M"], StrictInt] | None = None
    s_g2m_fraction: StrictFloat | None = Field(default=None, ge=0.0, le=1.0)
    mean_s_score: StrictFloat | None = None
    mean_g2m_score: StrictFloat | None = None
    assessment_state: Literal["available", "not_assessed"]
    reason_codes: list[SafeId]

    @model_validator(mode="after")
    def cycle_state_is_coherent(self) -> Self:
        values = [
            self.phase_counts,
            self.s_g2m_fraction,
            self.mean_s_score,
            self.mean_g2m_score,
        ]
        if self.assessment_state == "available":
            if any(v is None for v in values) or self.reason_codes:
                raise ValueError("available phase summary requires counts and scores")
            if set(self.phase_counts) != {"S", "G2M", "G1"}:
                raise ValueError("phase counts require all three labels")
            if (
                any(v < 0 for v in self.phase_counts.values())
                or sum(self.phase_counts.values()) != self.n_observations
            ):
                raise ValueError("phase denominator mismatch")
            expected = (
                self.phase_counts["S"] + self.phase_counts["G2M"]
            ) / self.n_observations
            if abs(self.s_g2m_fraction - expected) > 1e-12:
                raise ValueError("phase fraction must use all observations")
        elif any(v is not None for v in values) or not self.reason_codes:
            raise ValueError("unassessed phases require reasons and null values")
        return self


class ExploratoryProcessProfile(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    runtime_mode: Literal["exploratory_process"] = "exploratory_process"
    profile_id: SafeId
    tool_id: Literal["P0-06"] = "P0-06"
    tool_version: str
    input_sha256: Sha256
    expression_asset_sha256: Sha256
    input_contract: ExploratoryProcessInput
    method_parameters: ExploratoryMethodParameters
    normalization_recipe: Literal[
        "normalize_total_10000_log1p", "declared_normalized_expression"
    ]
    evidence_family_id: SafeId
    n_observations: StrictInt = Field(gt=0)
    n_features: StrictInt = Field(gt=0)
    feature_resolution_policy: Literal["exact_symbols_to_unique_input_feature_ids"] = (
        "exact_symbols_to_unique_input_feature_ids"
    )
    target_feature_ids: dict[str, str]
    duplicated_background_symbol_count: StrictInt = Field(ge=0)
    data_view_provenance_state: Literal["caller_declared_content_verified"] = (
        "caller_declared_content_verified"
    )
    state_review_status: Literal["pending"] = "pending"
    independence_state: Literal["unknown"] = "unknown"
    n_independent_replicates: None = None
    interpretation_scope: Literal["descriptive_only"] = "descriptive_only"
    score_state: Literal["unavailable"] = "unavailable"
    domain_score: None = None
    executions: list[MethodExecutionRecord]
    program_summaries: list[ExploratoryProgramSummary]
    cell_cycle: ExploratoryCellCycleSummary
    limitations: list[SafeId]
    created_at: datetime


class ProliferationStressResponseResult(
    RootModel[ProliferationStressResponseProfileV3 | ExploratoryProcessProfile]
):
    """Additive result envelope: no reinterpretation of old profile payloads."""


PUBLIC_EXPLORATORY_SCHEMA_MODELS = {
    EXPLORATORY_INPUT_SCHEMA: ExploratoryProcessInput,
    "bridge://schemas/exploratory-process-profile/v0.1": ExploratoryProcessProfile,
    P006_RESULT_SCHEMA: ProliferationStressResponseResult,
}
