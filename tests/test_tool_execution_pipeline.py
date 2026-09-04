from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from bridge.domain import CaseInputBundle, approve_plan
from bridge.planner import PlanBuilder
from bridge.runners import (
    ToolExecutionDenied,
    ToolExecutionPipeline,
    ToolExecutionScope,
)
from bridge.toolkit.contracts import (
    EligibilityResult,
    ExecutionState,
    ImplementationState,
    InputAsset,
    ToolPackageSpec,
    ToolRequest,
    ToolRun,
)


def _spec(*, version: str = "0.1.3", scientific_status: str = "candidate"):
    return ToolPackageSpec(
        tool_id="P0-01",
        name="Input QC",
        version=version,
        summary="test",
        implementation_state=ImplementationState.IMPLEMENTED,
        scientific_status=scientific_status,
        environment_spec_id="env:test",
        input_schema_ref="bridge://schemas/tool-request/v0.1",
        output_schema_ref="bridge://schemas/tool-run/v0.1",
        method_ids=["method:test"],
        card_ref="card:test",
    )


class FakeRegistry:
    def __init__(
        self,
        *,
        spec=None,
        eligible: bool = True,
        run_error: Exception | None = None,
        validation_error: Exception | None = None,
    ) -> None:
        self.spec = spec or _spec()
        self.eligible = eligible
        self.run_error = run_error
        self.validation_error = validation_error
        self.run_calls = 0

    def describe(self, tool_id: str):
        assert tool_id == "P0-01"
        return self.spec

    def check_eligibility(self, request):
        return EligibilityResult(
            tool_id=request.tool_id,
            eligible=self.eligible,
            reason_codes=[] if self.eligible else ["test_ineligible"],
        )

    def run(self, request):
        self.run_calls += 1
        if self.run_error:
            raise self.run_error
        return ToolRun(
            run_id="tool-run-1",
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=ExecutionState.SUCCEEDED,
            tool_version=self.spec.version,
            environment_spec_id=self.spec.environment_spec_id,
        )

    def validate_result(self, result, request):
        if self.validation_error:
            raise self.validation_error
        assert result.request == request
        return result


def _approved_plan(tmp_path: Path, registry: FakeRegistry | None = None):
    registry = registry or FakeRegistry()
    asset_path = tmp_path / "upload.h5ad"
    asset_path.write_bytes(b"synthetic-upload")
    asset = InputAsset(
        asset_id="asset-1",
        path=asset_path.resolve(),
        format="h5ad",
        input_level="analysis_ready",
        checksum=hashlib.sha256(asset_path.read_bytes()).hexdigest(),
        matrix_semantics="normalized_expression",
        assay="scRNA-seq",
    )
    draft = PlanBuilder(registry).build(
        CaseInputBundle(bundle_id="bundle-1", version="0.1", assets=[asset]),
        output_root=tmp_path / "private-output",
        knowledge_snapshot_ref="knowledge:test",
    )
    approved = approve_plan(
        draft,
        approver_id="reviewer-1",
        authority_ref="local-review-record",
        approved_at=datetime(2026, 9, 4, tzinfo=timezone.utc),
    )
    request = ToolRequest.model_validate_json(
        approved.steps[0].approved_request_json
    )
    return approved, request


def test_scope_requires_typed_plan_approval(tmp_path: Path) -> None:
    registry = FakeRegistry()
    asset_path = tmp_path / "upload.h5ad"
    asset_path.write_bytes(b"synthetic-upload")
    asset = InputAsset(
        asset_id="asset-1",
        path=asset_path.resolve(),
        format="h5ad",
        input_level="analysis_ready",
        checksum=hashlib.sha256(asset_path.read_bytes()).hexdigest(),
        matrix_semantics="normalized_expression",
        assay="scRNA-seq",
    )
    draft = PlanBuilder(registry).build(
        CaseInputBundle(bundle_id="bundle-1", version="0.1", assets=[asset]),
        output_root=tmp_path / "private-output",
        knowledge_snapshot_ref="knowledge:test",
    )
    with pytest.raises(ValueError, match="analysis_plan_not_approved"):
        ToolExecutionScope.from_plan(draft)


def test_pipeline_executes_only_the_exact_approved_request(tmp_path: Path) -> None:
    registry = FakeRegistry()
    plan, request = _approved_plan(tmp_path, registry)
    result = ToolExecutionPipeline(
        ToolExecutionScope.from_plan(plan),
        registry,
    ).execute(request, step_id=plan.steps[0].step_id)

    assert result.execution_state == "succeeded"
    assert registry.run_calls == 1


def test_pipeline_rejects_changed_request_without_running(tmp_path: Path) -> None:
    registry = FakeRegistry()
    plan, request = _approved_plan(tmp_path, registry)
    changed = request.model_copy(update={"random_seed": 42})

    with pytest.raises(ToolExecutionDenied, match="approved_request_mismatch"):
        ToolExecutionPipeline(
            ToolExecutionScope.from_plan(plan),
            registry,
        ).execute(changed)
    assert registry.run_calls == 0


def test_pipeline_rechecks_registry_scientific_status(tmp_path: Path) -> None:
    plan_registry = FakeRegistry()
    plan, request = _approved_plan(tmp_path, plan_registry)
    runtime_registry = FakeRegistry(
        spec=_spec(scientific_status="formal")
    )

    with pytest.raises(ToolExecutionDenied, match="registry_scientific_status_mismatch"):
        ToolExecutionPipeline(
            ToolExecutionScope.from_plan(plan),
            runtime_registry,
        ).execute(request)


@pytest.mark.parametrize(
    "registry",
    [
        FakeRegistry(run_error=ValueError("adapter result invalid")),
        FakeRegistry(validation_error=TypeError("schema drift")),
    ],
)
def test_pipeline_normalizes_registry_outcome_contract_errors(
    tmp_path: Path,
    registry: FakeRegistry,
) -> None:
    plan, request = _approved_plan(tmp_path, FakeRegistry())
    with pytest.raises(RuntimeError, match="tool_outcome_contract_mismatch"):
        ToolExecutionPipeline(
            ToolExecutionScope.from_plan(plan),
            registry,
        ).execute(request)


def test_pipeline_rejects_replaced_output_directory(tmp_path: Path) -> None:
    registry = FakeRegistry()
    plan, request = _approved_plan(tmp_path, registry)
    output_dir = request.output_dir
    previous = output_dir.with_name(f"{output_dir.name}-previous")
    output_dir.rename(previous)
    output_dir.mkdir(mode=0o700)

    with pytest.raises(
        ToolExecutionDenied,
        match="approved_output_directory_invalid",
    ):
        ToolExecutionPipeline(
            ToolExecutionScope.from_plan(plan),
            registry,
        ).execute(request)
    assert registry.run_calls == 0


def test_pipeline_rejects_ineligible_request_without_running(tmp_path: Path) -> None:
    plan, request = _approved_plan(tmp_path, FakeRegistry())
    registry = FakeRegistry(eligible=False)
    with pytest.raises(ToolExecutionDenied, match="test_ineligible"):
        ToolExecutionPipeline(
            ToolExecutionScope.from_plan(plan),
            registry,
        ).execute(request)
    assert registry.run_calls == 0


def test_scope_preserves_approval_and_request_digests(tmp_path: Path) -> None:
    plan, request = _approved_plan(tmp_path)
    scope = ToolExecutionScope.from_plan(plan)

    assert scope.approval_sha256 == plan.approval_receipt.plan_sha256
    assert scope.approved_steps[0].approved_request_sha256 == hashlib.sha256(
        json.dumps(
            request.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
