from __future__ import annotations

from pathlib import Path
import hashlib
import json

import pytest

from bridge.domain import AnalysisPlan, PlanStep
from bridge.runners import ToolExecutionDenied, ToolExecutionPipeline, ToolExecutionScope
from bridge.toolkit.contracts import (
    EligibilityResult,
    ExecutionState,
    ImplementationState,
    ToolPackageSpec,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
    ToolRun,
    ToolRunV2,
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


def _request(tmp_path: Path, **updates) -> ToolRequest:
    payload = {
        "request_id": "request-1",
        "tool_id": "P0-01",
        "tool_version": "0.1.0",
        "output_dir": (tmp_path / "outputs").resolve(),
    }
    payload.update(updates)
    return ToolRequest(**payload)


def _canonical_request(request: ToolRequest) -> str:
    return json.dumps(
        request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )


def _scope(
    tmp_path: Path,
    *,
    network_required: bool = False,
    high_resource_required: bool = False,
) -> ToolExecutionScope:
    request = _request(tmp_path)
    plan = AnalysisPlan(
        plan_id="plan-1",
        version="0.1",
        case_ref="case-1@0.1",
        case_contract_sha256=hashlib.sha256(b"case-1@0.1").hexdigest(),
        status="approved",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
        network_required=network_required,
        high_resource_required=high_resource_required,
        steps=[
            PlanStep(
                step_id="step-p0-01",
                tool_id="P0-01",
                tool_version="0.1.0",
                disposition="execute",
                measurement_spec_ref=None,
                reference_refs=["reference-policy://pd-mda/v0.1"],
                prior_refs=["prior://pd-mda/v0.1"],
                approved_request_json=_canonical_request(request),
                environment_spec_id="ENV-P0-CORE-v0.1",
                input_schema_ref="bridge://schemas/tool-request/v0.1",
                output_schema_ref="bridge://schemas/tool-run/v0.1",
                implementation_state="implemented",
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


def test_pipeline_executes_only_after_all_gates(tmp_path: Path) -> None:
    registry = FakeRegistry()
    outcome = ToolExecutionPipeline(_scope(tmp_path), registry).execute(_request(tmp_path))

    assert outcome.execution_state == "succeeded"
    assert registry.checked == 1
    assert registry.ran == 1


def test_pipeline_rejects_tool_outside_approved_plan_before_registry(tmp_path: Path) -> None:
    registry = FakeRegistry()

    with pytest.raises(ToolExecutionDenied, match="tool_not_in_approved_plan"):
        ToolExecutionPipeline(_scope(tmp_path), registry).execute(
            _request(tmp_path, tool_id="P0-03")
        )

    assert registry.checked == 0
    assert registry.ran == 0


def test_pipeline_rejects_version_mismatch_before_registry(tmp_path: Path) -> None:
    registry = FakeRegistry()

    with pytest.raises(ToolExecutionDenied, match="approved_tool_version_mismatch"):
        ToolExecutionPipeline(_scope(tmp_path), registry).execute(
            _request(tmp_path, tool_version="9.9.9")
        )

    assert registry.checked == 0
    assert registry.ran == 0


def test_pipeline_does_not_run_ineligible_tool(tmp_path: Path) -> None:
    registry = FakeRegistry(eligible=False)

    with pytest.raises(ToolExecutionDenied, match="synthetic_input_ineligible"):
        ToolExecutionPipeline(_scope(tmp_path), registry).execute(_request(tmp_path))

    assert registry.checked == 1
    assert registry.ran == 0


@pytest.mark.parametrize(
    ("scope_updates", "reason_code"),
    [
        ({"network_required": True}, "network_capability_not_granted"),
        ({"high_resource_required": True}, "high_resource_capability_not_granted"),
    ],
)
def test_pipeline_requires_explicit_runtime_capability_grants(
    tmp_path: Path, scope_updates: dict, reason_code: str
) -> None:
    registry = FakeRegistry()

    with pytest.raises(ToolExecutionDenied, match=reason_code):
        ToolExecutionPipeline(_scope(tmp_path, **scope_updates), registry).execute(
            _request(tmp_path)
        )

    assert registry.checked == 0
    assert registry.ran == 0


@pytest.mark.parametrize(
    "updates",
    [
        {"request_id": "case-b-request"},
        {"output_dir": Path("/tmp/case-b-output")},
        {"parameters": {"case_id": "case-b"}},
    ],
)
def test_pipeline_rejects_any_unapproved_request_field(
    tmp_path: Path, updates: dict
) -> None:
    registry = FakeRegistry()

    with pytest.raises(ToolExecutionDenied, match="approved_request_mismatch"):
        ToolExecutionPipeline(_scope(tmp_path), registry).execute(
            _request(tmp_path, **updates)
        )

    assert registry.checked == 0
    assert registry.ran == 0


def test_scope_rejects_legacy_approved_plan_without_case_binding() -> None:
    plan = AnalysisPlan(
        plan_id="legacy-plan",
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
            )
        ],
    )

    with pytest.raises(ValueError, match="missing_case_contract"):
        ToolExecutionScope.from_plan(plan)


class FakeV2Registry:
    def __init__(self, *, outcome_environment: str = "ENV-EVIDENCE-v0.1") -> None:
        self.outcome_environment = outcome_environment
        self.spec = ToolPackageSpecV2(
            tool_id="P0-08",
            name="Evidence Sufficiency",
            version="0.2.0",
            summary="Fake structured contract.",
            implementation_state="implemented",
            scientific_status="candidate",
            environment_spec_id="ENV-EVIDENCE-v0.1",
            input_schema_ref="bridge://schemas/tool-request/v0.2",
            output_schema_ref="bridge://schemas/tool-run/v0.2",
            result_schema_ref="bridge://schemas/evidence-sufficiency-run-result/v0.1",
            adapter_ref="bridge.tool_packages.p0_08_evidence_sufficiency.adapter:adapter",
            method_ids=["METHOD-FAKE"],
            card_ref="bridge://tool-cards/P0-08",
        )

    def describe(self, tool_id: str) -> ToolPackageSpecV2:
        assert tool_id == "P0-08"
        return self.spec

    def check_eligibility(self, request: ToolRequestV2) -> EligibilityResult:
        return EligibilityResult(tool_id=request.tool_id, eligible=True)

    def run(self, request: ToolRequestV2) -> ToolRunV2:
        return ToolRunV2(
            run_id="tool-run-v2",
            request=request,
            implementation_state="implemented",
            execution_state="succeeded",
            tool_version="0.2.0",
            environment_spec_id=self.outcome_environment,
            result_schema_ref=self.spec.result_schema_ref,
            result={},
        )


def _v2_request(tmp_path: Path) -> ToolRequestV2:
    return ToolRequestV2(
        request_id="request-v2",
        tool_id="P0-08",
        tool_version="0.2.0",
        output_dir=(tmp_path / "v2-outputs").resolve(),
    )


def _v2_scope(tmp_path: Path) -> ToolExecutionScope:
    request = _v2_request(tmp_path)
    plan = AnalysisPlan(
        plan_id="plan-v2",
        version="0.2",
        case_ref="case-1@0.1",
        case_contract_sha256=hashlib.sha256(b"case-1@0.1").hexdigest(),
        status="approved",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
        steps=[
            PlanStep(
                step_id="step-p0-08",
                tool_id="P0-08",
                tool_version="0.2.0",
                disposition="execute",
                approved_request_json=json.dumps(
                    request.model_dump(mode="json"),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                reference_refs=["reference-policy://pd-mda/v0.1"],
                prior_refs=["prior://pd-mda/v0.1"],
                environment_spec_id="ENV-EVIDENCE-v0.1",
                input_schema_ref="bridge://schemas/tool-request/v0.2",
                output_schema_ref="bridge://schemas/tool-run/v0.2",
                implementation_state="implemented",
                result_schema_ref=(
                    "bridge://schemas/evidence-sufficiency-run-result/v0.1"
                ),
            )
        ],
    )
    return ToolExecutionScope.from_plan(plan)


def test_pipeline_preserves_registry_selected_v2_contract(tmp_path: Path) -> None:
    outcome = ToolExecutionPipeline(
        _v2_scope(tmp_path), FakeV2Registry()
    ).execute(_v2_request(tmp_path))

    assert isinstance(outcome, ToolRunV2)
    assert isinstance(outcome.request, ToolRequestV2)


def test_pipeline_rejects_result_environment_drift(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="outcome_environment_mismatch"):
        ToolExecutionPipeline(
            _v2_scope(tmp_path),
            FakeV2Registry(outcome_environment="ENV-UNAPPROVED"),
        ).execute(_v2_request(tmp_path))
