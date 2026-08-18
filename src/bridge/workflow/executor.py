from __future__ import annotations

from uuid import uuid4

from bridge.domain import AnalysisPlan, PlanStatus, PlanStep
from bridge.workflow.event_store import InMemoryRunEventStore, RunEventStore
from bridge.workflow.events import (
    RunEventType,
    RunProjection,
    blocked_descendant_ids,
    project_run,
)
from bridge.workflow.models import RunSnapshot, RunStatus, StepStatus


class LocalWorkflowExecutor:
    """Event-sourced state machine for one local worker.

    Persistence and tool invocation are deliberately outside this class. A caller
    claims a ready step, invokes the registered Tool Package, then reports the
    deterministic outcome with ``complete_step``.
    """

    def __init__(
        self,
        event_store: RunEventStore | None = None,
        *,
        max_attempts: int = 2,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        self._max_attempts = max_attempts
        self._event_store = event_store or InMemoryRunEventStore()

    def submit(self, plan: AnalysisPlan) -> str:
        if plan.status is not PlanStatus.APPROVED:
            raise ValueError("analysis_plan_not_approved")
        run_id = f"run-{uuid4().hex}"
        self._event_store.append(
            run_id,
            RunEventType.RUN_SUBMITTED,
            {"plan": plan.model_dump(mode="json")},
            expected_sequence=0,
        )
        return run_id

    def claim_step(self, run_id: str) -> PlanStep | None:
        run = self._projection(run_id)
        if run.status in {
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
            RunStatus.SKIPPED,
        }:
            return None
        for plan_step in run.plan.steps:
            state = run.steps[plan_step.step_id]
            if state.status is not StepStatus.PENDING:
                continue
            if all(
                run.steps[dependency].status is StepStatus.SUCCEEDED
                for dependency in plan_step.depends_on
            ):
                self._event_store.append(
                    run_id,
                    RunEventType.STEP_CLAIMED,
                    {"step_id": plan_step.step_id},
                    expected_sequence=run.last_sequence,
                )
                return plan_step
        return None

    def complete_step(
        self,
        run_id: str,
        step_id: str,
        *,
        succeeded: bool,
        reason_codes: list[str] | None = None,
    ) -> None:
        run = self._projection(run_id)
        state = self._step(run, step_id)
        if state.status is not StepStatus.RUNNING:
            raise ValueError("workflow_step_not_running")
        if not succeeded and not reason_codes:
            raise ValueError("workflow_failure_requires_reason_codes")
        retry_exhausted = not succeeded and state.attempts >= self._max_attempts
        blocked_steps = (
            [
                {
                    "step_id": blocked_step_id,
                    "reason_codes": ["upstream_step_retry_exhausted"],
                }
                for blocked_step_id in blocked_descendant_ids(run, step_id)
            ]
            if retry_exhausted
            else []
        )
        self._event_store.append(
            run_id,
            (
                RunEventType.STEP_SUCCEEDED
                if succeeded
                else RunEventType.STEP_FAILED
            ),
            {
                "step_id": step_id,
                "reason_codes": reason_codes or [],
                "retry_exhausted": retry_exhausted,
                "blocked_steps": blocked_steps,
            },
            expected_sequence=run.last_sequence,
        )

    def cancel(self, run_id: str) -> None:
        run = self._projection(run_id)
        if run.status in {
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
            RunStatus.SKIPPED,
        }:
            return
        self._event_store.append(
            run_id,
            RunEventType.RUN_CANCELLED,
            {},
            expected_sequence=run.last_sequence,
        )

    def resume(self, run_id: str) -> None:
        run = self._projection(run_id)
        if run.status not in {RunStatus.RUNNING, RunStatus.FAILED, RunStatus.PARTIAL}:
            raise ValueError("workflow_run_not_resumable")
        step_ids = [
            state.step_id
            for state in run.steps.values()
            if state.status in {StepStatus.RUNNING, StepStatus.FAILED}
            and state.attempts < self._max_attempts
        ]
        if not step_ids:
            raise ValueError("workflow_retry_limit_reached")
        self._event_store.append(
            run_id,
            RunEventType.RUN_RESUMED,
            {"step_ids": step_ids},
            expected_sequence=run.last_sequence,
        )

    def get_status(self, run_id: str) -> RunSnapshot:
        return self._projection(run_id).snapshot()

    @staticmethod
    def _step(run: RunProjection, step_id: str):
        try:
            return run.steps[step_id]
        except KeyError as exc:
            raise KeyError(f"unknown workflow step: {step_id}") from exc

    def _projection(self, run_id: str) -> RunProjection:
        events = self._event_store.load(run_id)
        if not events:
            raise KeyError(f"unknown workflow run: {run_id}")
        return project_run(events)
