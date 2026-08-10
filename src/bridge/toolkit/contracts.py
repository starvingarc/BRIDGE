from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ImplementationState(StrEnum):
    SCAFFOLD = "scaffold"
    IMPLEMENTED = "implemented"
    DEPRECATED = "deprecated"


class ExecutionState(StrEnum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_IMPLEMENTED = "not_implemented"


class ScoreState(StrEnum):
    AVAILABLE = "available"
    SHADOW = "shadow"
    UNAVAILABLE = "unavailable"


CurrentScoreState = Literal[ScoreState.SHADOW, ScoreState.UNAVAILABLE]


class EvidenceState(StrEnum):
    MEASURED = "measured"
    INFERRED = "inferred"
    PRIOR_ONLY = "prior_only"
    NEGATIVE = "negative"
    MISSING = "missing"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    ALERT = "alert"


class ReadinessState(StrEnum):
    READY = "ready"
    LIMITED = "limited"
    BLOCKED = "blocked"
    NOT_ASSESSED = "not_assessed"
    NOT_APPLICABLE = "not_applicable"


class InputLevel(StrEnum):
    ANALYSIS_READY = "analysis_ready"
    COUNT_READY = "count_ready"
    DROPLET_READY = "droplet_ready"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ToolPackageSpec(FrozenModel):
    tool_id: str = Field(pattern=r"^P0-(0[1-9]|1[0-2])$")
    name: str
    version: str
    summary: str
    implementation_state: ImplementationState
    scientific_status: str
    optional: bool = False
    environment_spec_id: str
    input_schema_ref: str
    output_schema_ref: str
    method_ids: list[str] = Field(min_length=1)
    card_ref: str


class InputAsset(FrozenModel):
    asset_id: str
    path: Path
    format: str
    input_level: InputLevel
    checksum: str | None = None
    matrix_location: str | None = None
    matrix_semantics: str | None = None
    assay: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("path")
    @classmethod
    def path_is_absolute(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("asset path must be absolute")
        return value

    @model_validator(mode="after")
    def validate_input_level_and_matrix_semantics(self) -> "InputAsset":
        if self.input_level is InputLevel.ANALYSIS_READY:
            if self.format != "h5ad" or self.matrix_semantics != "normalized_expression":
                raise ValueError("analysis_ready requires h5ad normalized_expression")
        elif self.matrix_semantics != "raw_counts":
            raise ValueError("count_ready and droplet_ready require raw_counts")
        if self.input_level is InputLevel.DROPLET_READY and self.format not in {"10x_h5", "10x_mtx"}:
            raise ValueError("droplet_ready requires a 10x_h5 or 10x_mtx asset")
        return self


class ToolRequest(FrozenModel):
    request_id: str
    tool_id: str = Field(pattern=r"^P0-(0[1-9]|1[0-2])$")
    output_dir: Path
    tool_version: str | None = None
    assets: list[InputAsset] = Field(default_factory=list)
    measurement_spec_ref: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    random_seed: int = 0

    @field_validator("output_dir")
    @classmethod
    def output_dir_is_absolute(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("output_dir must be absolute")
        return value


class MeasurementSpec(FrozenModel):
    measurement_spec_id: str
    version: str
    scientific_question: str
    assay: str
    status: str
    applicable_product_cards: list[str] = Field(default_factory=list)
    input_contract: dict[str, Any]
    analysis_unit: str
    raw_metric_definition: dict[str, Any]
    numerator: str | None = None
    denominator: str | None = None
    direction: str | None = None
    uncertainty_method: str | None = None
    minimum_data: dict[str, Any] = Field(default_factory=dict)
    missing_behavior: str
    tool_refs: list[str] = Field(default_factory=list)
    reference_refs: list[str] = Field(default_factory=list)
    prior_refs: list[str] = Field(default_factory=list)
    validation_ref: str | None = None
    exclusion_rules: dict[str, Any] = Field(default_factory=dict)


class MeasurementResult(FrozenModel):
    measurement_id: str
    measurement_spec_id: str
    metric_name: str
    raw_value: Any
    numerator: float | int | None = None
    denominator: float | int | None = None
    interval: tuple[float, float] | None = None
    domain_score: None = None
    score_state: CurrentScoreState
    evidence_state: EvidenceState
    provenance_refs: list[str] = Field(default_factory=list)

class ArtifactManifest(FrozenModel):
    artifact_id: str
    kind: str
    path: Path
    media_type: str
    sha256: str
    evidence_ids: list[str] = Field(default_factory=list)


class VisualizationArtifact(FrozenModel):
    visualization_id: str
    component_id: str
    data_artifact_id: str
    evidence_ids: list[str]
    denominator: str | None = None
    units: str | None = None
    status: str
    render_artifact_ids: list[str] = Field(default_factory=list)


class QCReadinessProfile(FrozenModel):
    profile_id: str
    input_level: str
    assay: str
    assay_spec_id: str | None = None
    measurement_spec_status: str = "not_selected"
    readiness_state: ReadinessState
    schema_integrity: dict[str, Any]
    metadata_completeness: dict[str, Any]
    matrix_provenance: dict[str, Any]
    upstream_library_qc: dict[str, Any]
    cell_qc: dict[str, Any]
    doublet_assessment: dict[str, Any]
    cell_calling_assessment: dict[str, Any]
    ambient_assessment: dict[str, Any]
    data_views: dict[str, Any]
    module_eligibility: dict[str, str]
    missing_inputs: list[str] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    score_state: CurrentScoreState = ScoreState.UNAVAILABLE
    domain_score: None = None


class AnnotationLabel(FrozenModel):
    state_id: str
    display_name: str
    level: Literal["L1", "L2", "L3"]
    parent_state_ids: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    status: Literal["candidate", "shadow", "unresolved"]


class AnnotationVocabulary(FrozenModel):
    vocabulary_id: str
    version: str
    product_scope: str
    status: str
    labels: list[AnnotationLabel]
    alias_map: dict[str, str] = Field(default_factory=dict)
    unresolved_conflicts: list[str] = Field(default_factory=list)


class ReferenceProfile(FrozenModel):
    profile_id: str
    source_id: str
    source_family_id: str
    evidence_family_id: str
    assay: str
    anatomy: str
    developmental_time: str
    label_level: Literal["L1", "L2", "L3"]
    role: Literal["primary", "refinement", "context", "sensitivity"]
    status: str
    n_samples: int = 0
    n_observations: int = 0
    n_genes: int = 0
    labels: list[str] = Field(default_factory=list)
    matrix_file: str | None = None
    matrix_sha256: str | None = None
    metadata_file: str | None = None
    metadata_sha256: str | None = None
    source_sha256: str | None = None
    feature_selection: dict[str, Any] = Field(default_factory=dict)
    exclusions: dict[str, int] = Field(default_factory=dict)

    @field_validator("matrix_file", "metadata_file")
    @classmethod
    def artifact_path_is_relative(cls, value: str | None) -> str | None:
        if value is not None and (Path(value).is_absolute() or ".." in Path(value).parts):
            raise ValueError("reference snapshot artifact paths must be relative")
        return value


class ReferenceManifest(FrozenModel):
    snapshot_id: str
    version: str
    status: Literal["candidate", "frozen"]
    vocabulary_file: str
    vocabulary_sha256: str
    marker_program_file: str
    marker_program_sha256: str
    measurement_spec_ids: list[str]
    profiles: list[ReferenceProfile]
    prohibited_source_families: list[str] = Field(default_factory=list)

    @field_validator("vocabulary_file", "marker_program_file")
    @classmethod
    def manifest_artifact_path_is_relative(cls, value: str) -> str:
        if Path(value).is_absolute() or ".." in Path(value).parts:
            raise ValueError("reference snapshot artifact paths must be relative")
        return value


class MarkerProgramCard(FrozenModel):
    card_id: str
    version: str
    state_id: str
    level: Literal["L1", "L2", "L3"]
    positive_markers: list[str] = Field(default_factory=list)
    negative_markers: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    review_status: str
    allowed_use: list[str] = Field(default_factory=list)


class CellStateEvidenceProfile(FrozenModel):
    profile_id: str
    assay: str
    measurement_spec_id: str
    measurement_spec_status: str
    annotation_vocabulary_ref: str
    reference_snapshot_ref: str
    n_observations: int
    n_genes: int
    denominator: str
    label_levels: dict[str, Any]
    source_support: dict[str, Any]
    marker_program_evidence: dict[str, Any]
    prediction_sets: dict[str, Any]
    composition: dict[str, Any]
    gene_coverage: dict[str, Any]
    modality_sensitivity: dict[str, Any]
    unresolved_labels: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    score_state: CurrentScoreState = ScoreState.SHADOW
    domain_score: None = None


class EligibilityResult(FrozenModel):
    tool_id: str
    eligible: bool
    reason_codes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class KnowledgeHit(FrozenModel):
    document_id: str
    document_type: str
    title: str
    snippet: str
    source_ids: list[str]
    tool_package_ids: list[str]
    method_ids: list[str]
    score: float
    snapshot_id: str


class ToolRun(FrozenModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {"implementation_state": {"const": "scaffold"}},
                        "required": ["implementation_state"],
                    },
                    "then": {
                        "properties": {
                            "execution_state": {"enum": ["not_implemented", "failed"]},
                            "measurements": {"maxItems": 0},
                            "artifacts": {"maxItems": 0},
                            "visualizations": {"maxItems": 0},
                            "result": {"type": "null"},
                        }
                    },
                }
            ]
        },
    )

    run_id: str
    request: ToolRequest
    implementation_state: ImplementationState
    execution_state: ExecutionState
    tool_version: str
    environment_spec_id: str
    input_hash: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    measurements: list[MeasurementResult] = Field(default_factory=list)
    artifacts: list[ArtifactManifest] = Field(default_factory=list)
    visualizations: list[VisualizationArtifact] = Field(default_factory=list)
    result: dict[str, Any] | None = None
    reason_codes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_not_implemented_payload(self) -> "ToolRun":
        if self.execution_state is ExecutionState.NOT_IMPLEMENTED:
            if self.measurements or self.artifacts or self.visualizations or self.result is not None:
                raise ValueError("not_implemented ToolRun cannot contain scientific results or artifacts")
        if self.implementation_state is ImplementationState.SCAFFOLD:
            if self.execution_state not in {ExecutionState.NOT_IMPLEMENTED, ExecutionState.FAILED}:
                raise ValueError("scaffold ToolRun cannot report successful or partial execution")
            if self.measurements or self.artifacts or self.visualizations or self.result is not None:
                raise ValueError("scaffold ToolRun cannot contain scientific results or artifacts")
        return self
