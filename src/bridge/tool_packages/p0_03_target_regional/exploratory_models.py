"""Source-bound descriptive reference similarity, without product qualification."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import Field, RootModel, field_validator, model_validator

from bridge.toolkit.contracts import DataViewBinding, FrozenModel, ScoreState
from bridge.tool_packages.p0_03_target_regional.models import TargetRegionalEvidenceResult


INPUT_SCHEMA_REF = "bridge://schemas/reference-similarity-exploratory-input/v0.1"
RESULT_SCHEMA_REF = "bridge://schemas/target-regional-result/v0.1"


class ReferenceSimilarityExploratoryInput(FrozenModel):
    object_version: Literal["0.1.0"]
    input_id: str = Field(min_length=1)
    data_view: DataViewBinding
    profile_ids: list[str] = Field(min_length=1)
    gene_symbol_column: str | None = Field(default=None, min_length=1)
    minimum_shared_genes: int = Field(default=100, ge=2)
    created_at: datetime

    @field_validator("profile_ids")
    @classmethod
    def unique_profiles(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("profile_ids must be unique")
        return value

    @model_validator(mode="after")
    def count_view_only(self) -> Self:
        if self.data_view.matrix_semantics != "raw_counts":
            raise ValueError("exploratory similarity requires raw counts")
        if self.data_view.view_kind != "all_observations":
            raise ValueError("this mode requires an exact all-observations view")
        return self


class ReferenceLabelSimilarity(FrozenModel):
    measurement_id: str
    profile_id: str
    source_id: str
    source_family_id: str
    label_level: Literal["L1", "L2", "L3"]
    label: str
    state: Literal["available", "unavailable"]
    spearman: float | None = None
    cosine: float | None = None
    top_label: str | None = None
    runner_up_label: str | None = None
    margin: float | None = None
    shared_genes: int = Field(ge=0)
    query_gene_fraction: float = Field(ge=0.0, le=1.0)
    reference_gene_fraction: float = Field(ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)
    unit: Literal["similarity_coefficient"] = "similarity_coefficient"
    method_id: Literal["METHOD-BRIDGE-PSEUDOBULK-CORRELATION"] = (
        "METHOD-BRIDGE-PSEUDOBULK-CORRELATION"
    )

    @model_validator(mode="after")
    def state_is_coherent(self) -> Self:
        if self.state == "available":
            if self.spearman is None or self.cosine is None or self.reason_codes:
                raise ValueError("available similarity needs both coefficients")
        elif any(v is not None for v in (self.spearman, self.cosine, self.margin)) or not self.reason_codes:
            raise ValueError("unavailable similarity must have null values and reasons")
        return self


class ReferenceSimilarityExploratoryResult(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    result_id: str
    tool_id: Literal["P0-03"] = "P0-03"
    tool_version: str
    source_run_ref: str
    source_asset_id: str
    source_asset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reference_manifest_ref: str
    reference_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_view: DataViewBinding
    n_observations: int = Field(gt=0)
    n_query_genes: int = Field(gt=0)
    analysis_scope: Literal["whole_view_technical_aggregate"] = "whole_view_technical_aggregate"
    biological_independence: Literal["unknown"] = "unknown"
    n_independent_biological_replicates: None = None
    normalization: Literal["log1p(sum_raw_counts*10000/total_counts)"] = (
        "log1p(sum_raw_counts*10000/total_counts)"
    )
    result_state: Literal["available", "partial", "unavailable"]
    measurements: list[ReferenceLabelSimilarity]
    domain_score: None = None
    score_state: Literal[ScoreState.UNAVAILABLE] = ScoreState.UNAVAILABLE
    created_at: datetime


class TargetRegionalResult(RootModel[TargetRegionalEvidenceResult | ReferenceSimilarityExploratoryResult]):
    pass


PUBLIC_EXPLORATORY_SCHEMA_MODELS = {
    INPUT_SCHEMA_REF: ReferenceSimilarityExploratoryInput,
    RESULT_SCHEMA_REF: TargetRegionalResult,
}
