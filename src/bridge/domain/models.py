from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from pydantic import Field, field_serializer, field_validator, model_validator

from bridge.toolkit.contracts import FrozenModel, InputAsset, InputLevel


class CaseStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"


class PlanStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"


class StepDisposition(StrEnum):
    EXECUTE = "execute"
    SKIP = "skip"


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError("asset metadata must contain JSON-compatible immutable values")


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


class CaseInputAsset(FrozenModel):
    """Defensive, deeply immutable snapshot of an input asset in a confirmed case."""

    asset_id: str = Field(min_length=1)
    path: Path
    format: str = Field(min_length=1)
    input_level: InputLevel
    checksum: str | None = None
    matrix_location: str | None = None
    matrix_semantics: str | None = None
    assay: str | None = None
    metadata: Mapping[str, Any] = Field(default_factory=dict)

    @field_validator(
        "asset_id",
        "format",
        "checksum",
        "matrix_location",
        "matrix_semantics",
        "assay",
    )
    @classmethod
    def strings_are_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("asset identity and provenance must be nonblank")
        return value

    @field_validator("path")
    @classmethod
    def path_is_absolute(cls, value: Path) -> Path:
        path = Path(value)
        if not path.is_absolute():
            raise ValueError("asset path must be absolute")
        return path

    @field_validator("metadata", mode="before")
    @classmethod
    def metadata_is_deeply_frozen(cls, value: Any) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise ValueError("asset metadata must be an object")
        return _freeze_json(value)

    @field_serializer("metadata")
    def serialize_metadata(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return _thaw_json(value)

    @model_validator(mode="after")
    def validate_input_level_and_matrix_semantics(self) -> "CaseInputAsset":
        if self.input_level is InputLevel.ANALYSIS_READY:
            if self.format != "h5ad" or self.matrix_semantics != "normalized_expression":
                raise ValueError("analysis_ready requires h5ad normalized_expression")
        elif self.matrix_semantics != "raw_counts":
            raise ValueError("count_ready and droplet_ready require raw_counts")
        if self.input_level is InputLevel.DROPLET_READY and self.format not in {
            "10x_h5",
            "10x_mtx",
        }:
            raise ValueError("droplet_ready requires a 10x_h5 or 10x_mtx asset")
        return self

    def to_toolkit_asset(self) -> InputAsset:
        return InputAsset.model_validate(self.model_dump(mode="python"))


class SampleRecord(FrozenModel):
    sample_id: str = Field(min_length=1)
    preparation_id: str = Field(min_length=1)
    asset_ids: tuple[str, ...] = Field(min_length=1)
    data_role: str = Field(min_length=1)
    sampling_context: str = Field(min_length=1)
    donor_or_cell_line_id: str | None = None
    lot_id: str | None = None
    batch_id: str | None = None
    timepoint: str | None = None
    biological_replicate_id: str | None = None
    technical_replicate_id: str | None = None

    @field_validator(
        "sample_id",
        "preparation_id",
        "data_role",
        "sampling_context",
        "donor_or_cell_line_id",
        "lot_id",
        "batch_id",
        "timepoint",
        "biological_replicate_id",
        "technical_replicate_id",
    )
    @classmethod
    def strings_are_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("sample identifiers and provenance must be nonblank")
        return value

    @model_validator(mode="after")
    def asset_ids_are_unique(self) -> "SampleRecord":
        if any(not asset_id.strip() for asset_id in self.asset_ids):
            raise ValueError("sample asset ids must be nonblank")
        if len(self.asset_ids) != len(set(self.asset_ids)):
            raise ValueError("sample asset ids must be unique")
        return self


class ProductCase(FrozenModel):
    case_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    status: CaseStatus
    product_type: str = Field(min_length=1)
    target_cell_type: str = Field(min_length=1)
    differentiation_stage: str = Field(min_length=1)
    intended_use: str = Field(min_length=1)
    assay: str = Field(min_length=1)
    product_definition_card_ref: str = Field(min_length=1)
    reference_policy_ref: str = Field(min_length=1)
    prior_snapshot_ref: str = Field(min_length=1)
    assets: tuple[CaseInputAsset, ...] = Field(min_length=1)
    samples: tuple[SampleRecord, ...] = Field(min_length=1)

    @field_validator(
        "case_id",
        "version",
        "product_type",
        "target_cell_type",
        "differentiation_stage",
        "intended_use",
        "assay",
        "product_definition_card_ref",
        "reference_policy_ref",
        "prior_snapshot_ref",
    )
    @classmethod
    def required_strings_are_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("case identifiers and provenance must be nonblank")
        return value

    @field_validator("assets", mode="before")
    @classmethod
    def snapshot_assets(cls, value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            return [
                item.model_dump(mode="python") if isinstance(item, InputAsset) else item
                for item in value
            ]
        return value

    @model_validator(mode="after")
    def validate_case_graph(self) -> "ProductCase":
        asset_ids = [asset.asset_id for asset in self.assets]
        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError("case asset ids must be unique")
        sample_ids = [sample.sample_id for sample in self.samples]
        if len(sample_ids) != len(set(sample_ids)):
            raise ValueError("case sample ids must be unique")
        unknown_assets = sorted(
            {
                asset_id
                for sample in self.samples
                for asset_id in sample.asset_ids
                if asset_id not in set(asset_ids)
            }
        )
        if unknown_assets:
            raise ValueError(f"samples reference unknown assets: {unknown_assets}")
        if any(not asset_id.strip() for asset_id in asset_ids):
            raise ValueError("case asset ids must be nonblank")
        return self


class PlanStep(FrozenModel):
    step_id: str = Field(min_length=1)
    tool_id: str = Field(pattern=r"^P0-(0[1-9]|1[0-2])$")
    tool_version: str = Field(min_length=1)
    disposition: StepDisposition
    depends_on: tuple[str, ...] = Field(default_factory=tuple)
    measurement_spec_ref: str | None = None
    reference_refs: tuple[str, ...] = Field(default_factory=tuple)
    prior_refs: tuple[str, ...] = Field(default_factory=tuple)
    reason_codes: tuple[str, ...] = Field(default_factory=tuple)
    approved_request_json: str | None = None
    environment_spec_id: str | None = None
    input_schema_ref: str | None = None
    output_schema_ref: str | None = None
    implementation_state: str | None = None
    result_schema_ref: str | None = None

    @field_validator(
        "step_id",
        "tool_version",
        "measurement_spec_ref",
        "approved_request_json",
        "environment_spec_id",
        "input_schema_ref",
        "output_schema_ref",
        "implementation_state",
        "result_schema_ref",
    )
    @classmethod
    def optional_strings_are_nonempty(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("plan step identifiers and references cannot be blank")
        return value

    @model_validator(mode="after")
    def skipped_step_has_reason(self) -> "PlanStep":
        if self.disposition is StepDisposition.SKIP and not self.reason_codes:
            raise ValueError("skipped plan step requires a reason code")
        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValueError("plan step dependencies must be unique")
        if self.step_id in self.depends_on:
            raise ValueError("plan step cannot depend on itself")
        for label, values in (
            ("dependency", self.depends_on),
            ("reference", self.reference_refs),
            ("prior", self.prior_refs),
            ("reason code", self.reason_codes),
        ):
            if any(not value.strip() for value in values):
                raise ValueError(f"plan step {label} values must be nonblank")
        if self.disposition is StepDisposition.SKIP and self.approved_request_json is not None:
            raise ValueError("skipped plan step cannot carry an approved request")
        return self


class AnalysisPlan(FrozenModel):
    plan_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    case_ref: str = Field(min_length=1)
    case_id: str | None = None
    case_version: str | None = None
    case_contract_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    status: PlanStatus
    knowledge_snapshot_ref: str = Field(min_length=1)
    steps: tuple[PlanStep, ...] = Field(min_length=1)
    network_required: bool = False
    high_resource_required: bool = False

    @field_validator(
        "plan_id",
        "version",
        "case_ref",
        "case_id",
        "case_version",
        "knowledge_snapshot_ref",
    )
    @classmethod
    def required_strings_are_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("plan identifiers and provenance must be nonblank")
        return value

    @model_validator(mode="after")
    def validate_step_graph(self) -> "AnalysisPlan":
        if (self.case_id is None) != (self.case_version is None):
            raise ValueError("analysis plan case identity must include ID and version")
        if (
            self.case_id is not None
            and self.case_ref != f"{self.case_id}@{self.case_version}"
        ):
            raise ValueError("analysis plan case reference does not match case identity")
        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("analysis plan step ids must be unique")
        known: set[str] = set()
        dispositions: dict[str, StepDisposition] = {}
        for step in self.steps:
            missing = sorted(set(step.depends_on) - known)
            if missing:
                raise ValueError(
                    f"plan step dependencies must precede the step: {step.step_id}: {missing}"
                )
            blocked = [
                dependency
                for dependency in step.depends_on
                if dispositions[dependency] is StepDisposition.SKIP
            ]
            if step.disposition is StepDisposition.EXECUTE and blocked:
                raise ValueError(
                    f"executable plan step depends on skipped steps: {step.step_id}: {blocked}"
                )
            known.add(step.step_id)
            dispositions[step.step_id] = step.disposition
        return self
