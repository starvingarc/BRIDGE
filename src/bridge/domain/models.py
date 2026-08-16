from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from bridge.toolkit.contracts import FrozenModel, InputAsset


class CaseStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"


class PlanStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"


class StepDisposition(StrEnum):
    EXECUTE = "execute"
    SKIP = "skip"


class SampleRecord(FrozenModel):
    sample_id: str
    preparation_id: str
    asset_ids: list[str] = Field(min_length=1)
    data_role: str
    sampling_context: str
    donor_or_cell_line_id: str | None = None
    lot_id: str | None = None
    batch_id: str | None = None
    timepoint: str | None = None
    biological_replicate_id: str | None = None
    technical_replicate_id: str | None = None

    @model_validator(mode="after")
    def asset_ids_are_unique(self) -> "SampleRecord":
        if len(self.asset_ids) != len(set(self.asset_ids)):
            raise ValueError("sample asset ids must be unique")
        return self


class ProductCase(FrozenModel):
    case_id: str
    version: str
    status: CaseStatus
    product_type: str
    target_cell_type: str
    differentiation_stage: str
    intended_use: str
    assay: str
    product_definition_card_ref: str
    reference_policy_ref: str
    prior_snapshot_ref: str
    assets: list[InputAsset] = Field(min_length=1)
    samples: list[SampleRecord] = Field(min_length=1)

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
        return self


class PlanStep(FrozenModel):
    step_id: str
    tool_id: str = Field(pattern=r"^P0-(0[1-9]|1[0-2])$")
    tool_version: str
    disposition: StepDisposition
    depends_on: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def skipped_step_has_reason(self) -> "PlanStep":
        if self.disposition is StepDisposition.SKIP and not self.reason_codes:
            raise ValueError("skipped plan step requires a reason code")
        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValueError("plan step dependencies must be unique")
        if self.step_id in self.depends_on:
            raise ValueError("plan step cannot depend on itself")
        return self


class AnalysisPlan(FrozenModel):
    plan_id: str
    version: str
    case_ref: str
    status: PlanStatus
    knowledge_snapshot_ref: str
    steps: list[PlanStep] = Field(min_length=1)
    network_required: bool = False
    high_resource_required: bool = False

    @model_validator(mode="after")
    def validate_step_graph(self) -> "AnalysisPlan":
        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("analysis plan step ids must be unique")
        known: set[str] = set()
        for step in self.steps:
            missing = sorted(set(step.depends_on) - known)
            if missing:
                raise ValueError(
                    f"plan step dependencies must precede the step: {step.step_id}: {missing}"
                )
            known.add(step.step_id)
        return self
