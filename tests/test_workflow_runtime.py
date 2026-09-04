from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import sqlite3

import pytest

from bridge.domain import CaseInputBundle, approve_plan
from bridge.planner import PlanBuilder
from bridge.runners import ToolExecutionPipeline, ToolExecutionScope
from bridge.toolkit.contracts import (
    EligibilityResult,
    ExecutionState,
    ImplementationState,
    InputAsset,
    ToolPackageSpec,
    ToolRequest,
    ToolRun,
)
from bridge.workflow import (
    EventCompatibilityError,
    EventSequenceConflict,
    InMemoryRunEventStore,
    LocalWorkflowExecutor,
    SQLiteRunEventStore,
)


def _spec() -> ToolPackageSpec:
    return ToolPackageSpec(
        tool_id="P0-01",
        name="Input QC",
        version="0.1.3",
        summary="test",
        implementation_state=ImplementationState.IMPLEMENTED,
        scientific_status="candidate",
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
        execution_state: ExecutionState = ExecutionState.SUCCEEDED,
        reason_codes: list[str] | None = None,
    ) -> None:
        self.spec = _spec()
        self.execution_state = execution_state
        self.reason_codes = reason_codes or []
        self.run_calls = 0

    def describe(self, tool_id: str):
        return self.spec

    def check_eligibility(self, request):
        return EligibilityResult(tool_id=request.tool_id, eligible=True)

    def run(self, request):
        self.run_calls += 1
        return ToolRun(
            run_id=f"tool-{request.request_id}",
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=self.execution_state,
            tool_version=self.spec.version,
            environment_spec_id=self.spec.environment_spec_id,
            reason_codes=self.reason_codes,
        )

    def validate_result(self, result, request):
        assert result.request == request
        return result


def _asset(tmp_path: Path) -> InputAsset:
    path = tmp_path / "upload.h5ad"
    path.write_bytes(b"synthetic-upload")
    return InputAsset(
        asset_id="asset-1",
        path=path.resolve(),
        format="h5ad",
        input_level="analysis_ready",
        checksum=hashlib.sha256(path.read_bytes()).hexdigest(),
        matrix_semantics="normalized_expression",
        assay="scRNA-seq",
    )


def _plan(
    tmp_path: Path,
    *,
    two_steps: bool = False,
):
    registry = FakeRegistry()
    asset = _asset(tmp_path)
    bundle = CaseInputBundle(bundle_id="bundle-1", version="0.1", assets=[asset])
    requests = []
    dependencies = {}
    include_input_qc = True
    if two_steps:
        include_input_qc = False
        requests = [
            ToolRequest(
                request_id="first",
                tool_id="P0-01",
                output_dir=(tmp_path / "placeholder").resolve(),
                assets=[asset],
            ),
            ToolRequest(
                request_id="second",
                tool_id="P0-01",
                output_dir=(tmp_path / "placeholder").resolve(),
                assets=[asset],
            ),
        ]
        dependencies = {"second": ["first"]}
    draft = PlanBuilder(registry).build(
        bundle,
        output_root=tmp_path / "private-output",
        knowledge_snapshot_ref="knowledge:test",
        requests=requests,
        dependencies=dependencies,
        include_input_qc=include_input_qc,
    )
    approved = approve_plan(
        draft,
        approver_id="reviewer-1",
        authority_ref="local-review-record",
        approved_at=datetime(2026, 9, 4, tzinfo=timezone.utc),
    )
    return approved


def _pipeline(plan, registry: FakeRegistry | None = None):
    return ToolExecutionPipeline(
        ToolExecutionScope.from_plan(plan),
        registry or FakeRegistry(),
    )


def test_executor_rejects_unapproved_plan(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    payload = plan.model_dump(mode="json")
    payload["status"] = "draft"
    payload["approval_receipt"] = None
    from bridge.domain import AnalysisPlan

    with pytest.raises(ValueError, match="analysis_plan_not_approved"):
        LocalWorkflowExecutor().submit(AnalysisPlan.model_validate(payload))


def test_claim_execution_persists_tool_run_receipt(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    executor = LocalWorkflowExecutor()
    run_id = executor.submit(plan)
    claim = executor.claim_step(run_id)
    assert claim is not None

    result = executor.execute_claim(claim, _pipeline(plan))
    snapshot = executor.get_status(run_id)

    assert result.execution_state == "succeeded"
    assert snapshot.status == "succeeded"
    assert snapshot.status_scope == "execution_only"
    assert snapshot.scientific_readiness == "not_assessed"
    assert snapshot.domain_score is None
    receipt = snapshot.steps[0].outcome_receipt
    assert receipt is not None
    assert receipt.claim_id == claim.claim_id
    assert receipt.approved_request_sha256 == claim.approved_request_sha256


def test_recovery_invalidates_an_old_worker_claim(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    executor = LocalWorkflowExecutor(max_attempts=3)
    run_id = executor.submit(plan)
    old_claim = executor.claim_step(run_id)
    assert old_claim is not None

    executor.resume(run_id)
    new_claim = executor.claim_step(run_id)
    assert new_claim is not None
    assert new_claim.claim_id != old_claim.claim_id

    registry = FakeRegistry()
    with pytest.raises(ValueError, match="workflow_claim_fence_mismatch"):
        executor.execute_claim(old_claim, _pipeline(plan, registry))
    assert registry.run_calls == 0
    executor.execute_claim(new_claim, _pipeline(plan, registry))
    assert registry.run_calls == 1
    assert executor.get_status(run_id).status == "succeeded"


def test_forged_claim_contract_never_runs_tool(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    executor = LocalWorkflowExecutor()
    run_id = executor.submit(plan)
    claim = executor.claim_step(run_id)
    assert claim is not None

    forged = claim.model_copy(update={"approved_request_sha256": "0" * 64})
    registry = FakeRegistry()
    with pytest.raises(ValueError, match="workflow_claim_contract_mismatch"):
        executor.execute_claim(forged, _pipeline(plan, registry))
    assert registry.run_calls == 0


def test_failed_tool_run_is_not_recorded_as_success(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    executor = LocalWorkflowExecutor(max_attempts=2)
    run_id = executor.submit(plan)
    claim = executor.claim_step(run_id)
    assert claim is not None

    result = executor.execute_claim(
        claim,
        _pipeline(
            plan,
            FakeRegistry(
                execution_state=ExecutionState.FAILED,
                reason_codes=["deterministic_failure"],
            ),
        ),
    )

    assert result.execution_state == "failed"
    snapshot = executor.get_status(run_id)
    assert snapshot.status == "failed"
    assert snapshot.steps[0].reason_codes == ["deterministic_failure"]


def test_partial_tool_run_stays_partial_and_blocks_dependents(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path, two_steps=True)
    registry = FakeRegistry(
        execution_state=ExecutionState.PARTIAL,
        reason_codes=["individual_records_rejected"],
    )
    executor = LocalWorkflowExecutor()
    run_id = executor.submit(plan)
    claim = executor.claim_step(run_id)
    assert claim is not None

    result = executor.execute_claim(claim, _pipeline(plan, registry))

    snapshot = executor.get_status(run_id)
    assert result.execution_state == "partial"
    assert snapshot.status == "partial"
    assert [step.status for step in snapshot.steps] == ["partial", "skipped"]
    assert snapshot.steps[0].reason_codes == ["individual_records_rejected"]
    assert snapshot.steps[1].reason_codes == ["upstream_step_partial"]
    receipt = snapshot.steps[0].outcome_receipt
    assert receipt is not None
    assert receipt.execution_state == "partial"


def test_retry_exhaustion_skips_only_explicit_descendants(tmp_path: Path) -> None:
    plan = _plan(tmp_path, two_steps=True)
    executor = LocalWorkflowExecutor(max_attempts=1)
    run_id = executor.submit(plan)
    claim = executor.claim_step(run_id)
    assert claim is not None
    executor.fail_step(claim, reason_codes=["failed_once"])

    snapshot = executor.get_status(run_id)
    assert snapshot.status == "failed"
    assert [step.status for step in snapshot.steps] == ["failed", "skipped"]
    assert snapshot.steps[1].reason_codes == ["upstream_step_retry_exhausted"]


def test_success_with_a_preplanned_skip_is_operationally_partial(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    payload = plan.model_dump(mode="json")
    skipped = dict(payload["steps"][0])
    skipped.update(
        {
            "step_id": "step-skipped",
            "disposition": "skip",
            "reason_codes": ["not_selected"],
            "approved_request_json": None,
            "approved_request_sha256": None,
            "output_directory": None,
        }
    )
    payload["steps"].append(skipped)
    payload["status"] = "draft"
    payload["approval_receipt"] = None
    from bridge.domain import AnalysisPlan

    draft = AnalysisPlan.model_validate(payload)
    revised = approve_plan(
        draft,
        approver_id="reviewer-1",
        authority_ref="local-review-record",
        approved_at=datetime(2026, 9, 4, tzinfo=timezone.utc),
    )
    executor = LocalWorkflowExecutor()
    run_id = executor.submit(revised)
    claim = executor.claim_step(run_id)
    assert claim is not None
    executor.execute_claim(claim, _pipeline(revised))

    assert executor.get_status(run_id).status == "partial"


def test_sqlite_store_uses_private_directory_and_file_modes(tmp_path: Path) -> None:
    root = tmp_path / "events"
    root.mkdir(mode=0o700)
    database = root / "runs.sqlite"
    store = SQLiteRunEventStore(database)
    executor = LocalWorkflowExecutor(store)
    run_id = executor.submit(_plan(tmp_path))
    assert store.load(run_id)

    assert os.stat(root).st_mode & 0o077 == 0
    assert os.stat(database).st_mode & 0o077 == 0


def test_sqlite_store_rejects_nonprivate_parent(tmp_path: Path) -> None:
    root = tmp_path / "shared"
    root.mkdir(mode=0o755)
    root.chmod(0o755)
    with pytest.raises(ValueError, match="private_directory_permissions_invalid"):
        SQLiteRunEventStore(root / "runs.sqlite")


def test_sqlite_store_rejects_shared_writable_ancestor(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o777)
    shared.chmod(0o777)
    with pytest.raises(ValueError, match="private_path_ancestor_permissions_invalid"):
        SQLiteRunEventStore(shared / "events" / "runs.sqlite")


def test_sqlite_store_rejects_symlinked_parent(tmp_path: Path) -> None:
    target = tmp_path / "private"
    target.mkdir(mode=0o700)
    link = tmp_path / "events"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="private_path_not_directory"):
        SQLiteRunEventStore(link / "runs.sqlite")


def test_sqlite_store_rejects_unknown_event_schema(tmp_path: Path) -> None:
    root = tmp_path / "events"
    root.mkdir(mode=0o700)
    database = root / "runs.sqlite"
    store = SQLiteRunEventStore(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO run_events (
                run_id, sequence, event_id, event_type, recorded_at,
                payload_json, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run-bad",
                1,
                "event-bad",
                "run_submitted",
                "2026-09-04T00:00:00+00:00",
                "{}",
                "0",
            ),
        )
    with pytest.raises(
        EventCompatibilityError,
        match="workflow_event_schema_version_unsupported",
    ):
        store.load("run-bad")


def test_in_memory_store_rejects_stale_sequence() -> None:
    store = InMemoryRunEventStore()
    with pytest.raises(EventSequenceConflict):
        store.append(
            "run-1",
            "run_cancelled",
            {},
            expected_sequence=1,
        )


@pytest.mark.parametrize("max_attempts", [0, 11])
def test_executor_bounds_retry_budget(max_attempts: int) -> None:
    with pytest.raises(ValueError, match="between one and ten"):
        LocalWorkflowExecutor(max_attempts=max_attempts)
