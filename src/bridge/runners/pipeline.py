from __future__ import annotations

import hashlib
import json
from typing import Protocol

from bridge.domain.models import AnalysisPlan, PlanStatus, StepDisposition
from bridge.toolkit.contracts import (
    EligibilityResult,
    ExecutionState,
    FrozenModel,
    ToolPackageSpec,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
    ToolRun,
    ToolRunV2,
)
from bridge.toolkit.registry import ToolRegistry


ToolSpec = ToolPackageSpec | ToolPackageSpecV2
ToolRequestModel = ToolRequest | ToolRequestV2
ToolRunModel = ToolRun | ToolRunV2


def _canonical_json(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class ApprovedTool(FrozenModel):
    step_id: str
    tool_id: str
    tool_version: str
    approved_request_json: str
    approved_request_sha256: str
    measurement_spec_ref: str | None = None
    reference_refs: tuple[str, ...]
    prior_refs: tuple[str, ...]
    environment_spec_id: str
    input_schema_ref: str
    output_schema_ref: str
    implementation_state: str
    result_schema_ref: str | None = None


class ToolExecutionScope(FrozenModel):
    case_ref: str
    case_id: str
    case_version: str
    case_contract_sha256: str
    plan_id: str
    approved_steps: tuple[ApprovedTool, ...]
    network_allowed: bool = False
    high_resource_allowed: bool = False

    @classmethod
    def from_plan(cls, plan: AnalysisPlan) -> "ToolExecutionScope":
        if plan.status is not PlanStatus.APPROVED:
            raise ValueError("analysis_plan_not_approved")
        if plan.case_contract_sha256 is None:
            raise ValueError("approved_plan_missing_case_contract")
        if plan.case_id is None or plan.case_version is None:
            raise ValueError("approved_plan_missing_case_identity")
        approved_steps: list[ApprovedTool] = []
        for step in plan.steps:
            if step.disposition is not StepDisposition.EXECUTE:
                continue
            contract = (
                step.approved_request_json,
                step.environment_spec_id,
                step.input_schema_ref,
                step.output_schema_ref,
                step.implementation_state,
            )
            if any(value is None for value in contract):
                raise ValueError(
                    f"approved_step_missing_execution_contract:{step.step_id}"
                )
            request_json = step.approved_request_json
            assert request_json is not None
            approved_steps.append(
                ApprovedTool(
                    step_id=step.step_id,
                    tool_id=step.tool_id,
                    tool_version=step.tool_version,
                    approved_request_json=request_json,
                    approved_request_sha256=hashlib.sha256(
                        request_json.encode()
                    ).hexdigest(),
                    measurement_spec_ref=step.measurement_spec_ref,
                    reference_refs=step.reference_refs,
                    prior_refs=step.prior_refs,
                    environment_spec_id=step.environment_spec_id or "",
                    input_schema_ref=step.input_schema_ref or "",
                    output_schema_ref=step.output_schema_ref or "",
                    implementation_state=step.implementation_state or "",
                    result_schema_ref=step.result_schema_ref,
                )
            )
        return cls(
            case_ref=plan.case_ref,
            case_id=plan.case_id,
            case_version=plan.case_version,
            case_contract_sha256=plan.case_contract_sha256,
            plan_id=plan.plan_id,
            approved_steps=approved_steps,
            network_allowed=plan.network_required,
            high_resource_allowed=plan.high_resource_required,
        )

    @property
    def allowed_tools(self) -> tuple[ApprovedTool, ...]:
        """Compatibility view that cannot collapse duplicate tool IDs."""

        return self.approved_steps


class ToolExecutionDenied(RuntimeError):
    def __init__(self, *reason_codes: str) -> None:
        if not reason_codes:
            raise ValueError("tool denial requires a reason code")
        self.reason_codes = list(reason_codes)
        super().__init__(",".join(reason_codes))


class ToolRegistryLike(Protocol):
    def describe(self, tool_id: str) -> ToolSpec: ...

    def check_eligibility(self, request: ToolRequestModel) -> EligibilityResult: ...

    def check_case_eligibility(
        self,
        request: ToolRequestModel,
        *,
        case_id: str,
        case_version: str,
    ) -> EligibilityResult: ...

    def run(self, request: ToolRequestModel) -> ToolRunModel: ...

    def validate_result(
        self, result: object, request: ToolRequestModel
    ) -> ToolRunModel: ...


class ToolExecutionPipeline:
    def __init__(
        self,
        scope: ToolExecutionScope,
        registry: ToolRegistryLike | None = None,
        *,
        network_granted: bool = False,
        high_resource_granted: bool = False,
    ) -> None:
        self._scope = scope
        self._registry = registry or ToolRegistry.load_default()
        self._network_granted = network_granted
        self._high_resource_granted = high_resource_granted

    def execute(
        self, request: ToolRequestModel, *, step_id: str | None = None
    ) -> ToolRunModel:
        if self._scope.network_allowed and not self._network_granted:
            raise ToolExecutionDenied("network_capability_not_granted")
        if self._scope.high_resource_allowed and not self._high_resource_granted:
            raise ToolExecutionDenied("high_resource_capability_not_granted")
        candidates = [
            approved
            for approved in self._scope.approved_steps
            if approved.tool_id == request.tool_id
            and (step_id is None or approved.step_id == step_id)
        ]
        if not candidates:
            raise ToolExecutionDenied(
                "approved_step_not_found" if step_id is not None else "tool_not_in_approved_plan"
            )
        if len(candidates) == 1:
            candidate_approval = candidates[0]
            if request.tool_version != candidate_approval.tool_version:
                raise ToolExecutionDenied("approved_tool_version_mismatch")
            if request.measurement_spec_ref != candidate_approval.measurement_spec_ref:
                raise ToolExecutionDenied("approved_measurement_spec_mismatch")
        request_json = _canonical_json(request)
        exact = [
            approved
            for approved in candidates
            if approved.approved_request_json == request_json
        ]
        if len(exact) != 1:
            raise ToolExecutionDenied("approved_request_mismatch")
        approved = exact[0]

        spec = self._registry.describe(request.tool_id)
        if spec.version != approved.tool_version:
            raise ToolExecutionDenied("registry_tool_version_mismatch")
        if spec.environment_spec_id != approved.environment_spec_id:
            raise ToolExecutionDenied("registry_environment_mismatch")
        if spec.input_schema_ref != approved.input_schema_ref:
            raise ToolExecutionDenied("registry_input_schema_mismatch")
        if spec.output_schema_ref != approved.output_schema_ref:
            raise ToolExecutionDenied("registry_output_schema_mismatch")
        if spec.implementation_state.value != approved.implementation_state:
            raise ToolExecutionDenied("registry_implementation_state_mismatch")
        spec_result_schema = (
            spec.result_schema_ref if isinstance(spec, ToolPackageSpecV2) else None
        )
        if spec_result_schema != approved.result_schema_ref:
            raise ToolExecutionDenied("registry_result_schema_mismatch")
        if isinstance(spec, ToolPackageSpecV2) != isinstance(request, ToolRequestV2):
            raise ToolExecutionDenied("registry_request_generation_mismatch")

        eligibility = self._registry.check_case_eligibility(
            request,
            case_id=self._scope.case_id,
            case_version=self._scope.case_version,
        )
        if not eligibility.eligible:
            raise ToolExecutionDenied(*eligibility.reason_codes)

        candidate = self._registry.run(request)
        try:
            return self._registry.validate_result(candidate, request)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("tool_outcome_contract_mismatch") from exc
