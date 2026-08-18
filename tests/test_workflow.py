from __future__ import annotations

from pathlib import Path

import pytest

from bridge.domain import AnalysisPlan, PlanStep
from bridge.workflow import LocalWorkflowExecutor, SQLiteRunEventStore


def _approved_plan() -> AnalysisPlan:
    return AnalysisPlan(
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
            ),
            PlanStep(
                step_id="step-p0-02",
                tool_id="P0-02",
                tool_version="0.1.0",
                disposition="execute",
                depends_on=["step-p0-01"],
            ),
            PlanStep(
                step_id="step-p0-03",
                tool_id="P0-03",
                tool_version="0.1.0",
                disposition="skip",
                depends_on=["step-p0-02"],
                reason_codes=["tool_package_not_implemented"],
            ),
        ],
    )


def test_executor_claims_dependencies_in_order() -> None:
    executor = LocalWorkflowExecutor()
    run_id = executor.submit(_approved_plan())

    first = executor.claim_step(run_id)
    assert first is not None and first.step_id == "step-p0-01"
    assert executor.claim_step(run_id) is None

    executor.complete_step(run_id, first.step_id, succeeded=True)
    second = executor.claim_step(run_id)
    assert second is not None and second.step_id == "step-p0-02"
    executor.complete_step(run_id, second.step_id, succeeded=True)

    snapshot = executor.get_status(run_id)
    assert snapshot.status == "succeeded"
    assert [step.status for step in snapshot.steps] == ["succeeded", "succeeded", "skipped"]


def test_executor_resumes_failed_step_without_rerunning_success() -> None:
    executor = LocalWorkflowExecutor(max_attempts=2)
    run_id = executor.submit(_approved_plan())
    first = executor.claim_step(run_id)
    assert first is not None
    executor.complete_step(run_id, first.step_id, succeeded=True)
    second = executor.claim_step(run_id)
    assert second is not None
    executor.complete_step(
        run_id,
        second.step_id,
        succeeded=False,
        reason_codes=["transient_subprocess_failure"],
    )

    executor.resume(run_id)
    retried = executor.claim_step(run_id)
    assert retried is not None and retried.step_id == second.step_id
    snapshot = executor.get_status(run_id)
    assert snapshot.steps[0].attempts == 1
    assert snapshot.steps[1].attempts == 2

    executor.complete_step(
        run_id,
        retried.step_id,
        succeeded=False,
        reason_codes=["transient_subprocess_failure"],
    )
    with pytest.raises(ValueError, match="retry_limit_reached"):
        executor.resume(run_id)


def test_retry_exhaustion_blocks_descendants_but_runs_independent_steps() -> None:
    plan = AnalysisPlan(
        plan_id="plan-branches",
        version="0.1",
        case_ref="case-1@0.1",
        status="approved",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
        steps=[
            PlanStep(
                step_id="failed-root",
                tool_id="P0-01",
                tool_version="0.1.0",
                disposition="execute",
            ),
            PlanStep(
                step_id="blocked-child",
                tool_id="P0-02",
                tool_version="0.1.0",
                disposition="execute",
                depends_on=["failed-root"],
            ),
            PlanStep(
                step_id="blocked-grandchild",
                tool_id="P0-03",
                tool_version="0.1.0",
                disposition="execute",
                depends_on=["blocked-child"],
            ),
            PlanStep(
                step_id="independent",
                tool_id="P0-04",
                tool_version="0.1.0",
                disposition="execute",
            ),
        ],
    )
    executor = LocalWorkflowExecutor(max_attempts=1)
    run_id = executor.submit(plan)
    failed = executor.claim_step(run_id)
    assert failed is not None and failed.step_id == "failed-root"
    executor.complete_step(
        run_id,
        failed.step_id,
        succeeded=False,
        reason_codes=["permanent_failure"],
    )

    partial = executor.get_status(run_id)
    assert partial.status == "partial"
    assert [step.status for step in partial.steps] == [
        "failed",
        "skipped",
        "skipped",
        "pending",
    ]
    assert partial.steps[1].reason_codes == ["upstream_step_retry_exhausted"]

    independent = executor.claim_step(run_id)
    assert independent is not None and independent.step_id == "independent"
    executor.complete_step(run_id, independent.step_id, succeeded=True)
    assert executor.get_status(run_id).status == "failed"


def test_failure_requires_reason_and_terminal_failure_cannot_be_cancelled() -> None:
    executor = LocalWorkflowExecutor(max_attempts=1)
    run_id = executor.submit(_approved_plan())
    claimed = executor.claim_step(run_id)
    assert claimed is not None
    with pytest.raises(ValueError, match="failure_requires_reason_codes"):
        executor.complete_step(run_id, claimed.step_id, succeeded=False)

    executor.complete_step(
        run_id,
        claimed.step_id,
        succeeded=False,
        reason_codes=["permanent_failure"],
    )
    executor.cancel(run_id)
    assert executor.get_status(run_id).status == "failed"


def test_executor_rejects_draft_plan() -> None:
    draft = _approved_plan().model_copy(update={"status": "draft"})
    with pytest.raises(ValueError, match="not_approved"):
        LocalWorkflowExecutor().submit(draft)


def test_sqlite_executor_recovers_an_interrupted_step(tmp_path: Path) -> None:
    database_path = tmp_path / "workflow.sqlite3"
    first_process = LocalWorkflowExecutor(SQLiteRunEventStore(database_path))
    run_id = first_process.submit(_approved_plan())
    claimed = first_process.claim_step(run_id)
    assert claimed is not None and claimed.step_id == "step-p0-01"

    restarted_process = LocalWorkflowExecutor(SQLiteRunEventStore(database_path))
    assert restarted_process.get_status(run_id).status == "running"
    restarted_process.resume(run_id)
    reclaimed = restarted_process.claim_step(run_id)

    assert reclaimed is not None and reclaimed.step_id == "step-p0-01"
    assert restarted_process.get_status(run_id).steps[0].attempts == 2


def test_sqlite_restart_preserves_retry_exhaustion_terminalization(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "workflow.sqlite3"
    first_process = LocalWorkflowExecutor(
        SQLiteRunEventStore(database_path), max_attempts=1
    )
    run_id = first_process.submit(_approved_plan())
    claimed = first_process.claim_step(run_id)
    assert claimed is not None
    first_process.complete_step(
        run_id,
        claimed.step_id,
        succeeded=False,
        reason_codes=["permanent_failure"],
    )

    restarted_process = LocalWorkflowExecutor(
        SQLiteRunEventStore(database_path), max_attempts=1
    )
    snapshot = restarted_process.get_status(run_id)
    assert snapshot.status == "failed"
    assert [step.status for step in snapshot.steps] == ["failed", "skipped", "skipped"]
    assert snapshot.steps[1].reason_codes == ["upstream_step_retry_exhausted"]
