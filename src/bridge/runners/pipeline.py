from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from bridge.domain.models import AnalysisPlan, PlanStatus, PlanStep, StepDisposition
from bridge.storage.private_paths import (
    PrivatePathError,
    verify_private_directory,
)
from bridge.toolkit.contracts import (
    EligibilityResult,
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
    output_dir: str
    output_dir_device: int
    output_dir_inode: int
    environment_spec_id: str
    input_schema_ref: str
    output_schema_ref: str
    implementation_state: str
    scientific_status: str
    result_schema_ref: str | None = None


class ToolExecutionScope(FrozenModel):
    input_bundle_ref: str
    input_bundle_sha256: str
    plan_id: str
    approval_sha256: str
    approved_steps: tuple[ApprovedTool, ...]

    @classmethod
    def from_plan(cls, plan: AnalysisPlan) -> "ToolExecutionScope":
        if plan.status is not PlanStatus.APPROVED or plan.approval_receipt is None:
            raise ValueError("analysis_plan_not_approved")
        approved_steps: list[ApprovedTool] = []
        for step in plan.steps:
            if step.disposition is not StepDisposition.EXECUTE:
                continue
            required = (
                step.approved_request_json,
                step.approved_request_sha256,
                step.output_directory,
                step.environment_spec_id,
                step.input_schema_ref,
                step.output_schema_ref,
                step.implementation_state,
                step.scientific_status,
            )
            if any(value is None for value in required):
                raise ValueError(
                    f"approved_step_missing_execution_contract:{step.step_id}"
                )
            assert step.approved_request_json is not None
            assert step.approved_request_sha256 is not None
            assert step.output_directory is not None
            approved_steps.append(
                ApprovedTool(
                    step_id=step.step_id,
                    tool_id=step.tool_id,
                    tool_version=step.tool_version,
                    approved_request_json=step.approved_request_json,
                    approved_request_sha256=step.approved_request_sha256,
                    output_dir=str(step.output_directory.path),
                    output_dir_device=step.output_directory.device,
                    output_dir_inode=step.output_directory.inode,
                    environment_spec_id=step.environment_spec_id or "",
                    input_schema_ref=step.input_schema_ref or "",
                    output_schema_ref=step.output_schema_ref or "",
                    implementation_state=step.implementation_state or "",
                    scientific_status=step.scientific_status or "",
                    result_schema_ref=step.result_schema_ref,
                )
            )
        return cls(
            input_bundle_ref=plan.input_bundle_ref,
            input_bundle_sha256=plan.input_bundle_sha256,
            plan_id=plan.plan_id,
            approval_sha256=plan.approval_receipt.plan_sha256,
            approved_steps=approved_steps,
        )


class ToolExecutionDenied(RuntimeError):
    def __init__(self, *reason_codes: str) -> None:
        if not reason_codes:
            raise ValueError("tool denial requires a reason code")
        self.reason_codes = list(reason_codes)
        super().__init__(",".join(reason_codes))


class ToolRegistryLike(Protocol):
    def describe(self, tool_id: str) -> ToolSpec: ...

    def check_eligibility(self, request: ToolRequestModel) -> EligibilityResult: ...

    def run(self, request: ToolRequestModel) -> ToolRunModel: ...

    def validate_result(
        self, result: object, request: ToolRequestModel
    ) -> ToolRunModel: ...


class ToolExecutionPipeline:
    def __init__(
        self,
        scope: ToolExecutionScope,
        registry: ToolRegistryLike | None = None,
    ) -> None:
        self._scope = scope
        self._registry = registry or ToolRegistry.load_default()

    def execute_step(self, step: PlanStep) -> ToolRunModel:
        if (
            step.disposition is not StepDisposition.EXECUTE
            or step.approved_request_json is None
        ):
            raise ToolExecutionDenied("approved_step_not_executable")
        spec = self._registry.describe(step.tool_id)
        request_model = (
            ToolRequestV2 if isinstance(spec, ToolPackageSpecV2) else ToolRequest
        )
        try:
            request = request_model.model_validate_json(step.approved_request_json)
        except ValueError as exc:
            raise ToolExecutionDenied("approved_request_invalid") from exc
        return self.execute(request, step_id=step.step_id)

    def execute(
        self, request: ToolRequestModel, *, step_id: str | None = None
    ) -> ToolRunModel:
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
        if spec.scientific_status != approved.scientific_status:
            raise ToolExecutionDenied("registry_scientific_status_mismatch")
        spec_result_schema = (
            spec.result_schema_ref if isinstance(spec, ToolPackageSpecV2) else None
        )
        if spec_result_schema != approved.result_schema_ref:
            raise ToolExecutionDenied("registry_result_schema_mismatch")
        if isinstance(spec, ToolPackageSpecV2) != isinstance(request, ToolRequestV2):
            raise ToolExecutionDenied("registry_request_generation_mismatch")

        self._verify_output_directory(approved, "approved_output_directory_invalid")
        eligibility = self._registry.check_eligibility(request)
        if not eligibility.eligible:
            raise ToolExecutionDenied(*eligibility.reason_codes)

        try:
            candidate = self._registry.run(request)
            result = self._registry.validate_result(candidate, request)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("tool_outcome_contract_mismatch") from exc
        self._verify_output_directory(approved, "approved_output_directory_changed")
        return result

    @staticmethod
    def _verify_output_directory(approved: ApprovedTool, reason_code: str) -> None:
        try:
            verify_private_directory(
                Path(approved.output_dir),
                device=approved.output_dir_device,
                inode=approved.output_dir_inode,
            )
        except (OSError, PrivatePathError) as exc:
            raise ToolExecutionDenied(reason_code) from exc
