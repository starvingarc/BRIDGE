from __future__ import annotations

from pathlib import Path

import pytest

from bridge.domain import AnalysisPlan, PlanStep
from bridge.runners import ToolExecutionDenied, ToolExecutionPipeline, ToolExecutionScope
from bridge.toolkit.contracts import (
    EligibilityResult,
    ExecutionState,
    ImplementationState,
    ToolPackageSpec,
    ToolRequest,
    ToolRun,
)


class FakeRegistry:
    def __init__(self, *, eligible: bool = True) -> None:
        self.eligible = eligible
        self.checked = 0
        self.ran = 0
        self.spec = ToolPackageSpec(
            tool_id="P0-01",
            name="Input Audit & QC",
            version="0.1.0",
            summary="Fake executable contract.",
            implementation_state="implemented",
            scientific_status="candidate",
            environment_spec_id="ENV-P0-CORE-v0.1",
            input_schema_ref="bridge://schemas/tool-request/v0.1",
            output_schema_ref="bridge://schemas/tool-run/v0.1",
            method_ids=["METHOD-FAKE"],
            card_ref="bridge://tool-cards/P0-01",
        )

    def describe(self, tool_id: str) -> ToolPackageSpec:
        assert tool_id == "P0-01"
        return self.spec

    def check_eligibility(self, request: ToolRequest) -> EligibilityResult:
        self.checked += 1
        return EligibilityResult(
            tool_id=request.tool_id,
            eligible=self.eligible,
            reason_codes=[] if self.eligible else ["synthetic_input_ineligible"],
        )

    def run(self, request: ToolRequest) -> ToolRun:
        self.ran += 1
        return ToolRun(
            run_id="tool-run-1",
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=ExecutionState.SUCCEEDED,
            tool_version="0.1.0",
            environment_spec_id="ENV-P0-CORE-v0.1",
        )


def _scope() -> ToolExecutionScope:
    plan = AnalysisPlan(
        plan_id="plan-1",
        version="0.1",
        case_ref="case-1@0.1",
        status="approved",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
        steps=[
            PlanStep(
                step_id="step-p0-01",
                tool_id="P0-01",
                tool_version="0.1.0",
                disposition="execute",
                measurement_spec_ref=None,
                reference_refs=["reference-policy://pd-mda/v0.1"],
                prior_refs=["prior://pd-mda/v0.1"],
            ),
            PlanStep(
                step_id="step-p0-03",
                tool_id="P0-03",
                tool_version="0.1.0",
                disposition="skip",
                reason_codes=["tool_package_not_implemented"],
            ),
        ],
    )
    return ToolExecutionScope.from_plan(plan)


def _request(tmp_path: Path, **updates) -> ToolRequest:
    payload = {
        "request_id": "request-1",
        "tool_id": "P0-01",
        "tool_version": "0.1.0",
        "output_dir": (tmp_path / "outputs").resolve(),
    }
    payload.update(updates)
    return ToolRequest(**payload)


def test_pipeline_executes_only_after_all_gates(tmp_path: Path) -> None:
    registry = FakeRegistry()
    outcome = ToolExecutionPipeline(_scope(), registry).execute(_request(tmp_path))

    assert outcome.execution_state == "succeeded"
    assert registry.checked == 1
    assert registry.ran == 1


def test_pipeline_rejects_tool_outside_approved_plan_before_registry(tmp_path: Path) -> None:
    registry = FakeRegistry()

    with pytest.raises(ToolExecutionDenied, match="tool_not_in_approved_plan"):
        ToolExecutionPipeline(_scope(), registry).execute(
            _request(tmp_path, tool_id="P0-03")
        )

    assert registry.checked == 0
    assert registry.ran == 0


def test_pipeline_rejects_version_mismatch_before_registry(tmp_path: Path) -> None:
    registry = FakeRegistry()

    with pytest.raises(ToolExecutionDenied, match="approved_tool_version_mismatch"):
        ToolExecutionPipeline(_scope(), registry).execute(
            _request(tmp_path, tool_version="9.9.9")
        )

    assert registry.checked == 0
    assert registry.ran == 0


def test_pipeline_does_not_run_ineligible_tool(tmp_path: Path) -> None:
    registry = FakeRegistry(eligible=False)

    with pytest.raises(ToolExecutionDenied, match="synthetic_input_ineligible"):
        ToolExecutionPipeline(_scope(), registry).execute(_request(tmp_path))

    assert registry.checked == 1
    assert registry.ran == 0
