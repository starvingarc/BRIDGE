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

    executor.complete_step(run_id, retried.step_id, succeeded=False)
    with pytest.raises(ValueError, match="retry_limit_reached"):
        executor.resume(run_id)


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
