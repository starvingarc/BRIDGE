from __future__ import annotations

from datetime import datetime
from enum import StrEnum
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from pydantic import Field, field_serializer, field_validator, model_validator

from bridge.toolkit.contracts import FrozenModel, InputAsset, InputLevel


class PlanStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"


class StepDisposition(StrEnum):
    EXECUTE = "execute"
    SKIP = "skip"


def _canonical_json(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


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
    """A content-bound local input asset."""

    asset_id: str = Field(min_length=1)
    path: Path
    format: str = Field(min_length=1)
    input_level: InputLevel
    checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    matrix_location: str | None = None
    matrix_semantics: str | None = None
    assay: str | None = None
    metadata: Mapping[str, Any] = Field(default_factory=dict)

    @field_validator(
        "asset_id",
        "format",
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


class CaseInputBundle(FrozenModel):
    """Local upload envelope; it is not the scientific ProductCase contract."""

    bundle_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    assets: tuple[CaseInputAsset, ...] = Field(min_length=1)

    @field_validator("bundle_id", "version")
    @classmethod
    def identifiers_are_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("input bundle identifiers must be nonblank")
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
    def asset_ids_are_unique(self) -> "CaseInputBundle":
        asset_ids = [asset.asset_id for asset in self.assets]
        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError("input bundle asset ids must be unique")
        return self


class OutputDirectoryBinding(FrozenModel):
    path: Path
    device: int = Field(ge=0)
    inode: int = Field(ge=0)

    @field_validator("path")
    @classmethod
    def path_is_absolute(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("output directory path must be absolute")
        return value


class PlanStep(FrozenModel):
    step_id: str = Field(min_length=1)
    tool_id: str = Field(pattern=r"^P0-(0[1-9]|1[0-2])$")
    tool_version: str = Field(min_length=1)
    disposition: StepDisposition
    depends_on: tuple[str, ...] = Field(default_factory=tuple)
    reason_codes: tuple[str, ...] = Field(default_factory=tuple)
    approved_request_json: str | None = None
    approved_request_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    output_directory: OutputDirectoryBinding | None = None
    environment_spec_id: str | None = None
    input_schema_ref: str | None = None
    output_schema_ref: str | None = None
    implementation_state: str | None = None
    scientific_status: str | None = None
    result_schema_ref: str | None = None

    @field_validator(
        "step_id",
        "tool_version",
        "approved_request_json",
        "environment_spec_id",
        "input_schema_ref",
        "output_schema_ref",
        "implementation_state",
        "scientific_status",
        "result_schema_ref",
    )
    @classmethod
    def optional_strings_are_nonempty(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("plan step identifiers and references cannot be blank")
        return value

    @model_validator(mode="after")
    def validate_execution_contract(self) -> "PlanStep":
        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValueError("plan step dependencies must be unique")
        if self.step_id in self.depends_on:
            raise ValueError("plan step cannot depend on itself")
        if any(not value.strip() for value in (*self.depends_on, *self.reason_codes)):
            raise ValueError("plan step references and reason codes must be nonblank")
        if self.disposition is StepDisposition.SKIP:
            if not self.reason_codes:
                raise ValueError("skipped plan step requires a reason code")
            if any(
                value is not None
                for value in (
                    self.approved_request_json,
                    self.approved_request_sha256,
                    self.output_directory,
                )
            ):
                raise ValueError("skipped plan step cannot carry an execution request")
            return self
        required = (
            self.approved_request_json,
            self.approved_request_sha256,
            self.output_directory,
            self.environment_spec_id,
            self.input_schema_ref,
            self.output_schema_ref,
            self.implementation_state,
            self.scientific_status,
        )
        if any(value is None for value in required):
            raise ValueError("executable plan step requires a complete execution contract")
        assert self.approved_request_json is not None
        expected = hashlib.sha256(self.approved_request_json.encode()).hexdigest()
        if self.approved_request_sha256 != expected:
            raise ValueError("approved request digest mismatch")
        return self


class PlanApprovalReceipt(FrozenModel):
    plan_id: str = Field(min_length=1)
    plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    approver_id: str = Field(min_length=1)
    authority_ref: str = Field(min_length=1)
    approved_at: datetime

    @field_validator("plan_id", "approver_id", "authority_ref")
    @classmethod
    def values_are_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("approval receipt values must be nonblank")
        return value

    @field_validator("approved_at")
    @classmethod
    def approved_at_is_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("approval timestamp must be timezone-aware")
        return value


class AnalysisPlan(FrozenModel):
    plan_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    input_bundle_ref: str = Field(min_length=1)
    input_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: PlanStatus
    knowledge_snapshot_ref: str = Field(min_length=1)
    steps: tuple[PlanStep, ...] = Field(min_length=1)
    approval_receipt: PlanApprovalReceipt | None = None

    @field_validator(
        "plan_id",
        "version",
        "input_bundle_ref",
        "knowledge_snapshot_ref",
    )
    @classmethod
    def required_strings_are_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("plan identifiers and provenance must be nonblank")
        return value

    def approval_sha256(self) -> str:
        payload = self.model_dump(
            mode="json",
            exclude={"status", "approval_receipt"},
        )
        return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()

    @model_validator(mode="after")
    def validate_plan(self) -> "AnalysisPlan":
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
        if self.status is PlanStatus.DRAFT:
            if self.approval_receipt is not None:
                raise ValueError("draft plan cannot carry an approval receipt")
        else:
            receipt = self.approval_receipt
            if receipt is None:
                raise ValueError("approved plan requires an approval receipt")
            if receipt.plan_id != self.plan_id:
                raise ValueError("approval receipt plan mismatch")
            if receipt.plan_sha256 != self.approval_sha256():
                raise ValueError("approval receipt digest mismatch")
        return self


def approve_plan(
    plan: AnalysisPlan,
    *,
    approver_id: str,
    authority_ref: str,
    approved_at: datetime,
) -> AnalysisPlan:
    if plan.status is not PlanStatus.DRAFT:
        raise ValueError("analysis_plan_not_draft")
    receipt = PlanApprovalReceipt(
        plan_id=plan.plan_id,
        plan_sha256=plan.approval_sha256(),
        approver_id=approver_id,
        authority_ref=authority_ref,
        approved_at=approved_at,
    )
    payload = plan.model_dump(mode="json")
    payload["status"] = PlanStatus.APPROVED
    payload["approval_receipt"] = receipt.model_dump(mode="json")
    return AnalysisPlan.model_validate(payload)
