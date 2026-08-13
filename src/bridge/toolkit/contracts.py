from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

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
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {"implementation_state": {"const": "implemented"}},
                        "required": ["implementation_state"],
                    },
                    "then": {"properties": {"method_ids": {"minItems": 1}}},
                }
            ]
        }
    )

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
    method_ids: list[str]
    card_ref: str

    @model_validator(mode="after")
    def implemented_package_has_methods(self) -> "ToolPackageSpec":
        if self.implementation_state is ImplementationState.IMPLEMENTED and not self.method_ids:
            raise ValueError("implemented ToolPackageSpec requires at least one method")
        return self


class ToolPackageSpecV2(FrozenModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {"implementation_state": {"const": "implemented"}},
                        "required": ["implementation_state"],
                    },
                    "then": {
                        "properties": {
                            "method_ids": {"minItems": 1},
                            "adapter_ref": {"type": "string", "minLength": 1},
                            "result_schema_ref": {"type": "string", "minLength": 1},
                        },
                        "required": ["adapter_ref", "result_schema_ref"],
                    },
                },
                {
                    "if": {
                        "properties": {"implementation_state": {"const": "scaffold"}},
                        "required": ["implementation_state"],
                    },
                    "then": {
                        "properties": {
                            "method_ids": {"maxItems": 0},
                            "adapter_ref": {"type": "null"},
                            "result_schema_ref": {"type": "null"},
                        }
                    },
                },
            ]
        },
    )

    tool_id: str = Field(pattern=r"^P0-(0[1-9]|1[0-2])$")
    name: str
    version: str
    summary: str
    implementation_state: ImplementationState
    scientific_status: str
    optional: bool = False
    environment_spec_id: str
    input_schema_ref: Literal["bridge://schemas/tool-request/v0.2"]
    output_schema_ref: Literal["bridge://schemas/tool-run/v0.2"]
    method_ids: list[str]
    card_ref: str
    adapter_ref: str | None = Field(
        default=None,
        pattern=(
            r"^bridge\.tool_packages(?:\.[A-Za-z_][A-Za-z0-9_]*)+"
            r":[A-Za-z_][A-Za-z0-9_]*$"
        ),
    )
    result_schema_ref: str | None = None

    @model_validator(mode="after")
    def validate_implementation_bindings(self) -> "ToolPackageSpecV2":
        if self.implementation_state is ImplementationState.IMPLEMENTED:
            if not self.method_ids:
                raise ValueError("implemented ToolPackageSpecV2 requires at least one method")
            if not self.adapter_ref:
                raise ValueError("implemented ToolPackageSpecV2 requires adapter_ref")
            if not self.result_schema_ref:
                raise ValueError("implemented ToolPackageSpecV2 requires result_schema_ref")
        if self.implementation_state is ImplementationState.SCAFFOLD:
            if self.method_ids:
                raise ValueError("scaffold ToolPackageSpecV2 requires method_ids=[]")
            if self.adapter_ref is not None or self.result_schema_ref is not None:
                raise ValueError(
                    "scaffold ToolPackageSpecV2 cannot claim an adapter or result schema"
                )
        return self


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


class StructuredInputRef(FrozenModel):
    input_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    schema_ref: str = Field(min_length=1)
    object_version: str = Field(min_length=1)
    path: Path = Field(json_schema_extra={"pattern": r"^/"})
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: str = Field(
        default="application/json",
        pattern=r"^[A-Za-z0-9!#$&^_.+\-]+/[A-Za-z0-9!#$&^_.+\-]+$",
    )

    @field_validator("path")
    @classmethod
    def path_is_absolute(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("structured input path must be absolute")
        return value


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


class ToolRequestV2(FrozenModel):
    request_id: str
    tool_id: str = Field(pattern=r"^P0-(0[1-9]|1[0-2])$")
    output_dir: Path
    tool_version: str | None = None
    assets: list[InputAsset] = Field(default_factory=list)
    measurement_spec_ref: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    random_seed: int = 0
    object_inputs: list[StructuredInputRef] = Field(default_factory=list)

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
    release_manifest_ref: str | None = None


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
    status: Literal["candidate", "shadow", "unresolved", "provisional_frozen", "frozen"]


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


class ReviewerSignature(FrozenModel):
    reviewer_id: str
    reviewer_role: Literal["bridge_scientific_lead", "chen_team_reviewer"]
    key_id: str
    algorithm: Literal["ed25519"] = "ed25519"
    signed_at: datetime
    object_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    signature_base64: str = Field(min_length=80, max_length=96)


class StateReviewCard(FrozenModel):
    state_id: str
    display_name: str
    level: Literal["L1", "L2"]
    parent_state_ids: list[str] = Field(default_factory=list)
    definition: str
    positive_markers: list[str] = Field(default_factory=list)
    negative_markers: list[str] = Field(default_factory=list)
    anatomy_scope: str
    developmental_scope: str
    source_ids: list[str] = Field(min_length=1)
    count_source_id: str
    derivation_summary: str
    n_donors: int = Field(ge=0)
    n_observations: int = Field(ge=0)
    exploratory_markers: list[str] = Field(default_factory=list)
    confusion_states: list[str] = Field(default_factory=list)
    allowed_interpretations: list[str] = Field(min_length=1)
    forbidden_interpretations: list[str] = Field(min_length=1)
    review_blockers: list[str] = Field(default_factory=list)
    review_status: Literal["pending", "approved", "rejected"] = "pending"

    @model_validator(mode="after")
    def approved_card_requires_reviewed_markers(self) -> "StateReviewCard":
        if self.review_status == "approved":
            if not self.positive_markers or not self.negative_markers:
                raise ValueError("approved state review requires positive and negative markers")
            if self.review_blockers:
                raise ValueError("approved state review cannot retain review blockers")
        return self


class BiologicalReviewRecord(FrozenModel):
    review_record_id: str
    version: str
    vocabulary_ref: str
    status: Literal["pending", "partially_approved", "approved", "rejected"]
    product_definition_card_ref: str
    state_role_map_ref: str
    product_definition_review_status: Literal["pending", "approved", "rejected"] = "pending"
    state_role_map_review_status: Literal["pending", "approved", "rejected"] = "pending"
    state_reviews: list[StateReviewCard] = Field(min_length=1)
    alias_decisions: dict[str, str] = Field(default_factory=dict)
    conflict_exclusions: dict[str, int] = Field(default_factory=dict)
    signatures: list[ReviewerSignature] = Field(default_factory=list)

    @model_validator(mode="after")
    def reviewed_record_requires_both_roles(self) -> "BiologicalReviewRecord":
        state_ids = [card.state_id for card in self.state_reviews]
        if len(state_ids) != len(set(state_ids)):
            raise ValueError("biological review contains duplicate state ids")
        if self.status in {"partially_approved", "approved"}:
            if (
                self.product_definition_review_status != "approved"
                or self.state_role_map_review_status != "approved"
            ):
                raise ValueError("approved biological review requires product and role-map review")
            roles = {signature.reviewer_role for signature in self.signatures}
            required = {"bridge_scientific_lead", "chen_team_reviewer"}
            missing = sorted(required - roles)
            if missing:
                raise ValueError(f"reviewed biological record missing roles: {', '.join(missing)}")
            if len(self.signatures) != 2:
                raise ValueError("reviewed biological record requires exactly two signatures")
            if len({item.reviewer_id for item in self.signatures}) != 2:
                raise ValueError("reviewed biological record requires distinct reviewers")
            if len({item.key_id for item in self.signatures}) != 2:
                raise ValueError("reviewed biological record requires distinct signing keys")
        approved = [card for card in self.state_reviews if card.review_status == "approved"]
        if self.status == "approved" and len(approved) != len(self.state_reviews):
            raise ValueError("approved biological review contains an unapproved state card")
        if self.status == "partially_approved" and (
            not approved or len(approved) == len(self.state_reviews)
        ):
            raise ValueError("partially approved review requires mixed per-state decisions")
        return self


class CellStateBenchmarkSpec(FrozenModel):
    benchmark_spec_id: str
    version: str
    phase: Literal["pilot", "locked"]
    assay: Literal["scRNA-seq"]
    annotation_vocabulary_ref: str
    reference_snapshot_ref: str
    measurement_spec_ref: str
    environment_spec_refs: list[str] = Field(min_length=1)
    split_unit: Literal["source_family_and_sample"] = "source_family_and_sample"
    random_seed: int = 0
    methods: list[str] = Field(min_length=1)
    development_asset_ids: list[str] = Field(default_factory=list)
    development_ood_asset_ids: list[str] = Field(default_factory=list)
    behavior_only_asset_ids: list[str] = Field(default_factory=list)
    locked_asset_ids: list[str] = Field(default_factory=list)
    locked_method_exclusions: dict[str, list[str]] = Field(default_factory=dict)
    sealed_asset_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def benchmark_roles_are_disjoint(self) -> "CellStateBenchmarkSpec":
        if len(self.methods) != len(set(self.methods)):
            raise ValueError("benchmark methods must be unique")
        if len(self.environment_spec_refs) != len(set(self.environment_spec_refs)):
            raise ValueError("benchmark environment specs must be unique")
        groups = {
            "development": self.development_asset_ids,
            "development_ood": self.development_ood_asset_ids,
            "behavior_only": self.behavior_only_asset_ids,
            "locked": self.locked_asset_ids,
            "sealed": self.sealed_asset_ids,
        }
        owners: dict[str, str] = {}
        for role, asset_ids in groups.items():
            if len(asset_ids) != len(set(asset_ids)):
                raise ValueError(f"benchmark asset ids must be unique within {role}")
            for asset_id in asset_ids:
                if previous := owners.get(asset_id):
                    raise ValueError(
                        f"benchmark asset role overlap: {asset_id} ({previous}, {role})"
                    )
                owners[asset_id] = role
        if unknown := set(self.locked_method_exclusions) - set(self.locked_asset_ids):
            raise ValueError(
                f"locked method exclusions reference non-locked assets: {sorted(unknown)}"
            )
        for asset_id, methods in self.locked_method_exclusions.items():
            if (
                not methods
                or any(not method for method in methods)
                or len(methods) != len(set(methods))
            ):
                raise ValueError(
                    f"locked method exclusions must be non-empty and unique: {asset_id}"
                )
        return self


class BenchmarkSplitRecord(FrozenModel):
    asset_id: str
    source_family_id: str
    sample_id: str
    partition: Literal[
        "train",
        "calibration",
        "test",
        "development_ood",
        "behavior_only",
        "locked_test",
    ]
    data_role: str
    fold_id: str | None = None
    n_observations: int = Field(ge=0)


class BenchmarkSplitManifest(FrozenModel):
    split_manifest_id: str
    benchmark_spec_ref: str
    benchmark_spec_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase: Literal["pilot", "locked"]
    random_seed: int
    input_catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: list[BenchmarkSplitRecord]
    locked_assets_opened: bool = False
    sealed_assets_opened: bool = False

    @model_validator(mode="after")
    def validate_isolation(self) -> "BenchmarkSplitManifest":
        if self.phase == "pilot" and self.locked_assets_opened:
            raise ValueError("pilot split cannot open locked assets")
        if self.sealed_assets_opened:
            raise ValueError("sealed competitor assets cannot enter a benchmark split")
        by_fold: dict[tuple[str, str, str], set[str]] = {}
        for record in self.records:
            if record.fold_id and record.partition in {"train", "calibration", "test"}:
                key = (record.fold_id, record.source_family_id, record.sample_id)
                by_fold.setdefault(key, set()).add(record.partition)
        if any(len(partitions) > 1 for partitions in by_fold.values()):
            raise ValueError("source/sample group appears in multiple partitions within one fold")
        return self


class FreezeGateCriterion(FrozenModel):
    metric: str
    scope: str
    state_id: str | None = None
    method_id: str | None = None
    operator: Literal[">=", "<="]
    threshold: float | None = None
    pilot_observation: float | None = None
    rationale: str

    @model_validator(mode="after")
    def state_and_method_are_paired(self) -> "FreezeGateCriterion":
        if (self.state_id is None) != (self.method_id is None):
            raise ValueError("state-specific criteria require both state_id and method_id")
        return self


class FreezeGateSpec(FrozenModel):
    gate_spec_id: str
    version: str
    status: Literal["proposed", "approved", "rejected"]
    benchmark_spec_ref: str
    benchmark_spec_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    asset_catalog_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    reference_snapshot_ref: str | None = None
    reference_snapshot_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    environment_spec_refs: list[str] = Field(default_factory=list)
    environment_spec_sha256: dict[str, str] = Field(default_factory=dict)
    environment_health_record_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    adapter_contract_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    pilot_evidence_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    criteria: list[FreezeGateCriterion]
    signatures: list[ReviewerSignature] = Field(default_factory=list)

    @model_validator(mode="after")
    def approved_gate_requires_thresholds_and_signatures(self) -> "FreezeGateSpec":
        identities = [
            (item.metric, item.scope, item.state_id, item.method_id)
            for item in self.criteria
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("freeze gate criteria identities must be unique")
        if self.environment_spec_sha256:
            if set(self.environment_spec_sha256) != set(self.environment_spec_refs):
                raise ValueError("environment hashes must match environment references")
            if any(
                len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
                for value in self.environment_spec_sha256.values()
            ):
                raise ValueError("environment hashes must be sha256 values")
        if self.status == "approved":
            if not all(
                [
                    self.benchmark_spec_sha256,
                    self.asset_catalog_sha256,
                    self.reference_snapshot_ref,
                    self.reference_snapshot_sha256,
                    self.environment_spec_refs,
                    self.environment_spec_sha256,
                    self.environment_health_record_sha256,
                    self.adapter_contract_sha256,
                    self.pilot_evidence_sha256,
                ]
            ):
                raise ValueError("approved freeze gate requires benchmark bindings")
            if not self.criteria or any(item.threshold is None for item in self.criteria):
                raise ValueError("approved freeze gate requires numeric criteria")
            required_metrics = {
                "exact_accuracy",
                "macro_f1",
                "composition_mae",
                "prediction_set_coverage",
                "false_reassurance",
                "ood_assessment_coverage",
                "downsampling_drift",
                "preprocessing_sensitivity",
            }
            global_metrics = {
                item.metric for item in self.criteria if item.state_id is None
            }
            if not required_metrics.issubset(global_metrics):
                raise ValueError("approved freeze gate is missing mandatory metrics")
            state_groups: dict[tuple[str, str], list[FreezeGateCriterion]] = {}
            for criterion in self.criteria:
                if criterion.state_id is not None and criterion.method_id is not None:
                    state_groups.setdefault(
                        (criterion.state_id, criterion.method_id), []
                    ).append(criterion)
            for state_id, method_id in state_groups:
                support = [
                    item
                    for item in state_groups[(state_id, method_id)]
                    if item.metric == "n"
                ]
                if (
                    len(support) != 1
                    or support[0].operator != ">="
                    or support[0].threshold is None
                    or support[0].threshold < 1
                ):
                    raise ValueError(
                        "approved per-state gate requires a positive support threshold"
                    )
            roles = {signature.reviewer_role for signature in self.signatures}
            if len(self.signatures) != 2 or roles != {
                "bridge_scientific_lead",
                "chen_team_reviewer",
            }:
                raise ValueError("approved freeze gate requires both reviewer roles")
            if len({item.reviewer_id for item in self.signatures}) != 2:
                raise ValueError("approved freeze gate requires distinct reviewers")
            if len({item.key_id for item in self.signatures}) != 2:
                raise ValueError("approved freeze gate requires distinct signing keys")
        return self


class CellStateReleaseManifest(FrozenModel):
    release_manifest_id: str
    version: str
    status: Literal["draft", "frozen", "superseded"]
    assay: Literal["scRNA-seq", "snRNA-seq"]
    annotation_vocabulary_ref: str
    reference_snapshot_ref: str
    measurement_spec_ref: str
    benchmark_spec_ref: str
    biological_review_ref: str
    freeze_gate_ref: str
    locked_test_state: Literal["not_run", "passed", "failed"]
    per_state_release: dict[
        str, Literal["shadow", "provisional_frozen", "frozen", "unavailable"]
    ]
    selected_methods: dict[str, list[str]] = Field(default_factory=dict)
    biological_review_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    freeze_gate_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    locked_summary_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    locked_run_manifest_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    locked_split_manifest_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    reference_manifest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    runtime_tool_version: str | None = None
    environment_spec_ref: str | None = None
    method_implementation_versions: dict[str, str] = Field(default_factory=dict)
    signatures: list[ReviewerSignature] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_release_scope(self) -> "CellStateReleaseManifest":
        unknown_method_states = sorted(
            set(self.selected_methods) - set(self.per_state_release)
        )
        if unknown_method_states:
            raise ValueError("selected methods reference unknown release states")
        if any(
            not methods or len(methods) != len(set(methods))
            for methods in self.selected_methods.values()
        ):
            raise ValueError("selected method lists must be non-empty and unique")
        if any(
            state_id.startswith("L2:") and release_state == "frozen"
            for state_id, release_state in self.per_state_release.items()
        ):
            raise ValueError("L2 states cannot exceed provisional_frozen")
        if self.assay == "snRNA-seq" and any(
            state in {"provisional_frozen", "frozen"}
            for state in self.per_state_release.values()
        ):
            raise ValueError("snRNA states remain shadow in this release")
        if self.status == "frozen":
            released_states = {
                state_id
                for state_id, state in self.per_state_release.items()
                if state in {"provisional_frozen", "frozen"}
            }
            if set(self.selected_methods) != released_states:
                raise ValueError("every released state requires an explicit method combination")
            roles = {signature.reviewer_role for signature in self.signatures}
            if len(self.signatures) != 2 or roles != {
                "bridge_scientific_lead",
                "chen_team_reviewer",
            }:
                raise ValueError("frozen release requires both release signatures")
            if len({item.reviewer_id for item in self.signatures}) != 2:
                raise ValueError("frozen release requires distinct reviewers")
            if len({item.key_id for item in self.signatures}) != 2:
                raise ValueError("frozen release requires distinct signing keys")
            if self.locked_test_state != "passed":
                raise ValueError("frozen release requires a passed locked test")
            if not self.selected_methods:
                raise ValueError("frozen release requires selected methods")
            if not all(
                [
                    self.biological_review_sha256,
                    self.freeze_gate_sha256,
                    self.locked_summary_sha256,
                    self.locked_run_manifest_sha256,
                    self.locked_split_manifest_sha256,
                    self.reference_manifest_sha256,
                    self.runtime_tool_version,
                    self.environment_spec_ref,
                ]
            ):
                raise ValueError("frozen release requires bundle checksums")
            selected = {method for methods in self.selected_methods.values() for method in methods}
            if set(self.method_implementation_versions) != selected:
                raise ValueError("frozen release must version every selected method")
        return self


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
    method_outputs: dict[str, Any] = Field(default_factory=dict)
    assignment_state: dict[str, Any] = Field(default_factory=dict)
    unknown_reason: dict[str, Any] = Field(default_factory=dict)
    calibration: dict[str, Any] = Field(default_factory=dict)
    method_disagreement: dict[str, Any] = Field(default_factory=dict)
    per_state_release: dict[str, str] = Field(default_factory=dict)
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


class ToolRunV2(FrozenModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {
                            "implementation_state": {"const": "scaffold"}
                        },
                        "required": ["implementation_state"],
                    },
                    "then": {
                        "properties": {
                            "execution_state": {"enum": ["not_implemented", "failed"]},
                            "measurements": {"maxItems": 0},
                            "artifacts": {"maxItems": 0},
                            "visualizations": {"maxItems": 0},
                            "result_schema_ref": {"type": "null"},
                            "result": {"type": "null"},
                        }
                    },
                },
                {
                    "if": {
                        "properties": {
                            "execution_state": {"const": "not_implemented"}
                        },
                        "required": ["execution_state"],
                    },
                    "then": {
                        "properties": {
                            "measurements": {"maxItems": 0},
                            "artifacts": {"maxItems": 0},
                            "visualizations": {"maxItems": 0},
                            "result_schema_ref": {"type": "null"},
                            "result": {"type": "null"},
                        }
                    },
                },
                {
                    "if": {
                        "properties": {
                            "implementation_state": {"const": "implemented"},
                            "execution_state": {"enum": ["succeeded", "partial"]},
                        },
                        "required": ["implementation_state", "execution_state"],
                    },
                    "then": {
                        "properties": {
                            "result_schema_ref": {"type": "string", "minLength": 1},
                            "result": {"type": "object"},
                        },
                        "required": ["result_schema_ref", "result"],
                    },
                },
            ]
        },
    )

    run_id: str
    request: ToolRequestV2
    implementation_state: ImplementationState
    execution_state: ExecutionState
    tool_version: str
    environment_spec_id: str
    input_hash: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    measurements: list[MeasurementResult] = Field(default_factory=list)
    artifacts: list[ArtifactManifest] = Field(default_factory=list)
    visualizations: list[VisualizationArtifact] = Field(default_factory=list)
    result_schema_ref: str | None = None
    result: dict[str, Any] | None = None
    reason_codes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_execution_payload(self) -> "ToolRunV2":
        has_payload = bool(self.measurements or self.artifacts or self.visualizations)
        has_payload = has_payload or self.result is not None or self.result_schema_ref is not None
        if self.execution_state is ExecutionState.NOT_IMPLEMENTED and has_payload:
            raise ValueError(
                "not_implemented ToolRunV2 cannot contain scientific results, "
                "artifacts, or a result schema"
            )
        if self.implementation_state is ImplementationState.SCAFFOLD:
            if self.execution_state not in {
                ExecutionState.NOT_IMPLEMENTED,
                ExecutionState.FAILED,
            }:
                raise ValueError("scaffold ToolRunV2 cannot report successful or partial execution")
            if has_payload:
                raise ValueError(
                    "scaffold ToolRunV2 cannot contain scientific results, artifacts, "
                    "or a result schema"
                )
        if (
            self.implementation_state is ImplementationState.IMPLEMENTED
            and self.execution_state in {ExecutionState.SUCCEEDED, ExecutionState.PARTIAL}
        ):
            if not self.result_schema_ref or self.result is None:
                raise ValueError(
                    "successful or partial ToolRunV2 requires result_schema_ref and result"
                )
        return self


@runtime_checkable
class ToolPackageAdapter(Protocol):
    def check_eligibility(
        self, request: ToolRequestV2, spec: ToolPackageSpecV2
    ) -> EligibilityResult: ...

    def run(self, request: ToolRequestV2, spec: ToolPackageSpecV2) -> ToolRunV2: ...
