from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
import math
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, StrictInt, field_validator, model_validator

from bridge.tool_packages.p0_12_graft_assessment.models import (
    GraftSourceBinding,
    NonNegativeInt,
    PublishedRef,
    SafeId,
)
from bridge.toolkit.contracts import FrozenModel


FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
NonNegativeFloat = Annotated[
    float, Field(ge=0, allow_inf_nan=False)
]
UnitFloat = Annotated[
    float, Field(ge=0, le=1, allow_inf_nan=False)
]
SHA256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def _sorted_unique(values: list[object], name: str) -> list[object]:
    if values != sorted(set(values), key=str):
        raise ValueError(f"{name} must be unique and sorted")
    return values


class GraftAssay(StrEnum):
    SCRNA = "scRNA-seq"
    SNRNA = "snRNA-seq"


class GraftMatrixSemantics(StrEnum):
    RAW_COUNTS = "raw_counts"
    LOG_NORMALIZED = "log_normalized"


class AnalysisAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class GraftExpressionAsset(FrozenModel):
    object_version: Literal["0.1.0"]
    asset_id: SafeId
    graft_case_ref: SafeId
    assay_id: SafeId
    path: Path = Field(json_schema_extra={"pattern": r"^/"})
    sha256: SHA256
    format: Literal["h5ad"]
    assay: GraftAssay
    organism: SafeId
    gene_id_namespace: SafeId
    expression_layer: str = Field(
        min_length=1, pattern=r"^(?:X|[A-Za-z][A-Za-z0-9._-]*)$"
    )
    matrix_semantics: GraftMatrixSemantics
    analysis_value_semantics: Literal["log1p_cp10k"]
    gene_symbol_key: str | None = Field(
        default=None, pattern=r"^[A-Za-z][A-Za-z0-9._-]*$"
    )
    sample_id_key: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9._-]*$")
    graft_id_key: str | None = Field(
        default=None, pattern=r"^[A-Za-z][A-Za-z0-9._-]*$"
    )
    state_probability_columns: dict[SafeId, str] = Field(min_length=1)
    provenance_refs: list[PublishedRef] = Field(min_length=1)
    created_at: datetime

    @field_validator("path")
    @classmethod
    def path_is_absolute(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("graft expression path must be absolute")
        return value

    @field_validator("state_probability_columns")
    @classmethod
    def probability_columns_are_distinct(
        cls, value: dict[str, str]
    ) -> dict[str, str]:
        columns = list(value.values())
        if len(columns) != len(set(columns)) or any(not item for item in columns):
            raise ValueError("state probability columns must be distinct")
        return value

    @field_validator("provenance_refs")
    @classmethod
    def provenance_is_sorted(cls, value: list[str]) -> list[str]:
        return _sorted_unique(value, "provenance_refs")

    @field_validator("created_at")
    @classmethod
    def created_at_is_aware(cls, value: datetime) -> datetime:
        return _utc(value)


class GraftExpressionAnalysisSpec(FrozenModel):
    object_version: Literal["0.1.0"]
    analysis_spec_id: SafeId
    reference_panel_ref: SafeId
    marker_program_collection_ref: SafeId
    method_ids: list[SafeId] = Field(min_length=1)
    required_obs_fields: list[str]
    minimum_cells: StrictInt = Field(ge=1)
    minimum_genes: StrictInt = Field(ge=2)
    minimum_reference_genes: StrictInt = Field(ge=3)
    minimum_program_genes: StrictInt = Field(ge=1)
    probability_tolerance: UnitFloat
    max_file_bytes: StrictInt = Field(ge=1, le=2_000_000_000)
    provenance_refs: list[PublishedRef] = Field(min_length=1)

    @field_validator(
        "method_ids", "required_obs_fields", "provenance_refs"
    )
    @classmethod
    def lists_are_sorted(
        cls, value: list[object], info: object
    ) -> list[object]:
        return _sorted_unique(
            value, getattr(info, "field_name", "values")
        )


class GraftReferenceProfile(FrozenModel):
    profile_id: SafeId
    gene_values: dict[str, FiniteFloat] = Field(min_length=3)


class GraftReferencePanel(FrozenModel):
    object_version: Literal["0.1.0"]
    reference_panel_id: SafeId
    source_family_id: SafeId
    organism: SafeId
    gene_id_namespace: SafeId
    assay: GraftAssay
    value_semantics: Literal["log1p_cp10k"]
    profiles: list[GraftReferenceProfile] = Field(min_length=1)
    provenance_refs: list[PublishedRef] = Field(min_length=1)
    created_at: datetime

    @field_validator("profiles")
    @classmethod
    def profiles_are_sorted(
        cls, value: list[GraftReferenceProfile]
    ) -> list[GraftReferenceProfile]:
        ids = [item.profile_id for item in value]
        _sorted_unique(ids, "profiles")
        return value

    @field_validator("provenance_refs")
    @classmethod
    def provenance_is_sorted(cls, value: list[str]) -> list[str]:
        return _sorted_unique(value, "provenance_refs")

    @field_validator("created_at")
    @classmethod
    def created_at_is_aware(cls, value: datetime) -> datetime:
        return _utc(value)


class GraftMarkerProgram(FrozenModel):
    program_id: SafeId
    genes: list[str] = Field(min_length=1)

    @field_validator("genes")
    @classmethod
    def genes_are_sorted(cls, value: list[str]) -> list[str]:
        if any(not gene for gene in value):
            raise ValueError("marker genes cannot be empty")
        return _sorted_unique(value, "genes")


class GraftMarkerProgramCollection(FrozenModel):
    object_version: Literal["0.1.0"]
    collection_id: SafeId
    source_family_id: SafeId
    organism: SafeId
    gene_id_namespace: SafeId
    value_semantics: Literal["log1p_cp10k"]
    programs: list[GraftMarkerProgram] = Field(min_length=1)
    provenance_refs: list[PublishedRef] = Field(min_length=1)
    created_at: datetime

    @field_validator("programs")
    @classmethod
    def programs_are_sorted(
        cls, value: list[GraftMarkerProgram]
    ) -> list[GraftMarkerProgram]:
        ids = [item.program_id for item in value]
        _sorted_unique(ids, "programs")
        return value

    @field_validator("provenance_refs")
    @classmethod
    def provenance_is_sorted(cls, value: list[str]) -> list[str]:
        return _sorted_unique(value, "provenance_refs")

    @field_validator("created_at")
    @classmethod
    def created_at_is_aware(cls, value: datetime) -> datetime:
        return _utc(value)


class GraftCompositionEstimate(FrozenModel):
    state_id: SafeId
    mean_fraction: UnitFloat
    cell_equivalent: NonNegativeFloat
    denominator_cells: NonNegativeInt

    @model_validator(mode="after")
    def descriptive_fraction_is_coherent(self) -> Self:
        if self.denominator_cells < 1:
            raise ValueError("composition denominator must be positive")
        expected = self.cell_equivalent / self.denominator_cells
        if not math.isclose(
            self.mean_fraction,
            expected,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("composition fraction must use all uploaded rows")
        return self


class GraftReferenceSupport(FrozenModel):
    sample_id: SafeId
    profile_id: SafeId
    availability: AnalysisAvailability
    spearman_correlation: FiniteFloat | None = None
    shared_gene_count: NonNegativeInt
    reason_codes: list[SafeId]

    @model_validator(mode="after")
    def availability_is_coherent(self) -> Self:
        available = self.spearman_correlation is not None
        if available != (self.availability is AnalysisAvailability.AVAILABLE):
            raise ValueError("reference support must match availability")
        _sorted_unique(self.reason_codes, "reason_codes")
        return self


class GraftProgramEvidence(FrozenModel):
    sample_id: SafeId
    program_id: SafeId
    availability: AnalysisAvailability
    mean_expression: FiniteFloat | None = None
    gene_count: NonNegativeInt
    gene_coverage: UnitFloat
    reason_codes: list[SafeId]

    @model_validator(mode="after")
    def availability_is_coherent(self) -> Self:
        available = self.mean_expression is not None
        if available != (self.availability is AnalysisAvailability.AVAILABLE):
            raise ValueError("program evidence must match availability")
        _sorted_unique(self.reason_codes, "reason_codes")
        return self


class GraftExpressionAnalysisResult(FrozenModel):
    object_version: Literal["0.1.0"]
    result_id: SafeId
    tool_id: Literal["P0-12"]
    tool_version: str
    state: Literal["candidate"]
    evidence_state: Literal["shadow"]
    analysis_mode: Literal["expression_analysis"]
    graft_case_ref: SafeId
    asset_ref: SafeId
    analysis_spec_ref: SafeId
    reference_panel_ref: SafeId
    marker_program_collection_ref: SafeId
    reference_source_family_id: SafeId
    marker_source_family_id: SafeId
    assay: GraftAssay
    matrix_semantics: GraftMatrixSemantics
    analysis_value_semantics: Literal["log1p_cp10k"]
    qc_state: Literal["not_reassessed"]
    composition_denominator: Literal["all_uploaded_rows"]
    cell_count: NonNegativeInt
    gene_count: NonNegativeInt
    sample_count: NonNegativeInt
    graft_count: NonNegativeInt
    unassigned_fraction: UnitFloat
    composition_estimates: list[GraftCompositionEstimate]
    reference_support: list[GraftReferenceSupport]
    program_evidence: list[GraftProgramEvidence]
    source_bindings: list[GraftSourceBinding]
    selected_method_ids: list[SafeId] = Field(min_length=1)
    runtime_versions: dict[str, str]
    reason_codes: list[SafeId]
    pretransplant_evidence_effect: Literal["none"] = "none"
    domain_score: None = None
    score_state: Literal["unavailable"] = "unavailable"
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def created_at_is_aware(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def lists_are_coherent(self) -> Self:
        _sorted_unique(
            [item.state_id for item in self.composition_estimates],
            "composition_estimates",
        )
        reference_keys = [
            f"{item.sample_id}\0{item.profile_id}"
            for item in self.reference_support
        ]
        _sorted_unique(reference_keys, "reference_support")
        program_keys = [
            f"{item.sample_id}\0{item.program_id}"
            for item in self.program_evidence
        ]
        _sorted_unique(program_keys, "program_evidence")
        _sorted_unique(
            [item.role for item in self.source_bindings],
            "source_bindings",
        )
        _sorted_unique(self.selected_method_ids, "selected_method_ids")
        _sorted_unique(self.reason_codes, "reason_codes")
        if self.sample_count < 1 or self.cell_count < 1 or self.gene_count < 1:
            raise ValueError("expression analysis requires non-empty data")
        return self


PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/graft-expression-asset/v0.1": GraftExpressionAsset,
    (
        "bridge://schemas/graft-expression-analysis-spec/v0.1"
    ): GraftExpressionAnalysisSpec,
    "bridge://schemas/graft-reference-panel/v0.1": GraftReferencePanel,
    (
        "bridge://schemas/graft-marker-program-collection/v0.1"
    ): GraftMarkerProgramCollection,
    (
        "bridge://schemas/graft-expression-analysis-result/v0.1"
    ): GraftExpressionAnalysisResult,
}
