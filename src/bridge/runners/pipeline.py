from __future__ import annotations

from typing import Protocol

from bridge.domain import AnalysisPlan, PlanStatus, StepDisposition
from bridge.toolkit.contracts import (
    EligibilityResult,
    FrozenModel,
    ToolPackageSpec,
    ToolRequest,
    ToolRun,
)
from bridge.toolkit.registry import ToolRegistry


class ApprovedTool(FrozenModel):
    tool_id: str
    tool_version: str
    measurement_spec_ref: str | None = None
    reference_refs: list[str]
    prior_refs: list[str]


class ToolExecutionScope(FrozenModel):
    case_ref: str
    plan_id: str
    allowed_tools: dict[str, ApprovedTool]
    network_allowed: bool = False
    high_resource_allowed: bool = False

    @classmethod
    def from_plan(cls, plan: AnalysisPlan) -> "ToolExecutionScope":
        if plan.status is not PlanStatus.APPROVED:
            raise ValueError("analysis_plan_not_approved")
        return cls(
            case_ref=plan.case_ref,
            plan_id=plan.plan_id,
            allowed_tools={
                step.tool_id: ApprovedTool(
                    tool_id=step.tool_id,
                    tool_version=step.tool_version,
                    measurement_spec_ref=step.measurement_spec_ref,
                    reference_refs=step.reference_refs,
                    prior_refs=step.prior_refs,
                )
                for step in plan.steps
                if step.disposition is StepDisposition.EXECUTE
            },
            network_allowed=plan.network_required,
            high_resource_allowed=plan.high_resource_required,
        )


class ToolExecutionDenied(RuntimeError):
    def __init__(self, *reason_codes: str) -> None:
        if not reason_codes:
            raise ValueError("tool denial requires a reason code")
        self.reason_codes = list(reason_codes)
        super().__init__(",".join(reason_codes))


class ToolRegistryLike(Protocol):
    def describe(self, tool_id: str) -> ToolPackageSpec: ...

    def check_eligibility(self, request: ToolRequest) -> EligibilityResult: ...

    def run(self, request: ToolRequest) -> ToolRun: ...


class ToolExecutionPipeline:
    def __init__(
        self,
        scope: ToolExecutionScope,
        registry: ToolRegistryLike | None = None,
    ) -> None:
        self._scope = scope
        self._registry = registry or ToolRegistry.load_default()

    def execute(self, request: ToolRequest) -> ToolRun:
        approved = self._scope.allowed_tools.get(request.tool_id)
        if approved is None:
            raise ToolExecutionDenied("tool_not_in_approved_plan")
        if request.tool_version != approved.tool_version:
            raise ToolExecutionDenied("approved_tool_version_mismatch")
        if request.measurement_spec_ref != approved.measurement_spec_ref:
            raise ToolExecutionDenied("approved_measurement_spec_mismatch")

        spec = self._registry.describe(request.tool_id)
        if spec.version != approved.tool_version:
            raise ToolExecutionDenied("registry_tool_version_mismatch")
        eligibility = self._registry.check_eligibility(request)
        if not eligibility.eligible:
            raise ToolExecutionDenied(*eligibility.reason_codes)

        candidate = self._registry.run(request)
        outcome = ToolRun.model_validate(candidate.model_dump(mode="json"))
        if outcome.request != request or outcome.tool_version != approved.tool_version:
            raise RuntimeError("tool_outcome_contract_mismatch")
        return outcome
