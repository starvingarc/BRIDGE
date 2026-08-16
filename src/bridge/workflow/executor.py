from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from uuid import uuid4

from bridge.domain import AnalysisPlan, PlanStatus, PlanStep, StepDisposition
from bridge.workflow.models import RunSnapshot, RunStatus, StepSnapshot, StepStatus


@dataclass
class _StepState:
    plan_step: PlanStep
    status: StepStatus
    attempts: int = 0
    reason_codes: tuple[str, ...] = ()


@dataclass
class _RunState:
    plan: AnalysisPlan
    status: RunStatus
    steps: dict[str, _StepState]


class LocalWorkflowExecutor:
    """Thread-safe in-memory state machine for one local worker.

    Persistence and tool invocation are deliberately outside this class. A caller
    claims a ready step, invokes the registered Tool Package, then reports the
    deterministic outcome with ``complete_step``.
    """

    def __init__(self, *, max_attempts: int = 2) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        self._max_attempts = max_attempts
        self._runs: dict[str, _RunState] = {}
        self._lock = Lock()

    def submit(self, plan: AnalysisPlan) -> str:
        if plan.status is not PlanStatus.APPROVED:
            raise ValueError("analysis_plan_not_approved")
        with self._lock:
            run_id = f"run-{uuid4().hex}"
            steps = {
                step.step_id: _StepState(
                    plan_step=step,
                    status=(
                        StepStatus.PENDING
                        if step.disposition is StepDisposition.EXECUTE
                        else StepStatus.SKIPPED
                    ),
                    reason_codes=tuple(step.reason_codes),
                )
                for step in plan.steps
            }
            status = (
                RunStatus.PENDING
                if any(step.status is StepStatus.PENDING for step in steps.values())
                else RunStatus.SKIPPED
            )
            self._runs[run_id] = _RunState(plan=plan, status=status, steps=steps)
            return run_id

    def claim_step(self, run_id: str) -> PlanStep | None:
        with self._lock:
            run = self._get_run(run_id)
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
                    state.status = StepStatus.RUNNING
                    state.attempts += 1
                    run.status = RunStatus.RUNNING
                    return plan_step
            self._refresh_status(run)
            return None

    def complete_step(
        self,
        run_id: str,
        step_id: str,
        *,
        succeeded: bool,
        reason_codes: list[str] | None = None,
    ) -> None:
        with self._lock:
            run = self._get_run(run_id)
            state = self._get_step(run, step_id)
            if state.status is not StepStatus.RUNNING:
                raise ValueError("workflow_step_not_running")
            state.status = StepStatus.SUCCEEDED if succeeded else StepStatus.FAILED
            state.reason_codes = tuple(reason_codes or ())
            self._refresh_status(run)

    def cancel(self, run_id: str) -> None:
        with self._lock:
            run = self._get_run(run_id)
            if run.status in {RunStatus.SUCCEEDED, RunStatus.CANCELLED, RunStatus.SKIPPED}:
                return
            for state in run.steps.values():
                if state.status in {StepStatus.PENDING, StepStatus.RUNNING}:
                    state.status = StepStatus.CANCELLED
            run.status = RunStatus.CANCELLED

    def resume(self, run_id: str) -> None:
        with self._lock:
            run = self._get_run(run_id)
            if run.status not in {RunStatus.FAILED, RunStatus.PARTIAL}:
                raise ValueError("workflow_run_not_resumable")
            resumed = False
            for state in run.steps.values():
                if state.status is StepStatus.FAILED and state.attempts < self._max_attempts:
                    state.status = StepStatus.PENDING
                    state.reason_codes = ()
                    resumed = True
            if not resumed:
                raise ValueError("workflow_retry_limit_reached")
            run.status = RunStatus.PENDING

    def get_status(self, run_id: str) -> RunSnapshot:
        with self._lock:
            run = self._get_run(run_id)
            return RunSnapshot(
                run_id=run_id,
                plan_id=run.plan.plan_id,
                status=run.status,
                steps=[
                    StepSnapshot(
                        step_id=state.plan_step.step_id,
                        tool_id=state.plan_step.tool_id,
                        status=state.status,
                        attempts=state.attempts,
                        reason_codes=list(state.reason_codes),
                    )
                    for state in run.steps.values()
                ],
            )

    def _refresh_status(self, run: _RunState) -> None:
        states = {step.status for step in run.steps.values()}
        if StepStatus.RUNNING in states:
            run.status = RunStatus.RUNNING
        elif StepStatus.FAILED in states:
            run.status = (
                RunStatus.PARTIAL if StepStatus.PENDING in states else RunStatus.FAILED
            )
        elif StepStatus.PENDING in states:
            run.status = RunStatus.PENDING
        elif StepStatus.SUCCEEDED in states:
            run.status = RunStatus.SUCCEEDED
        else:
            run.status = RunStatus.SKIPPED

    def _get_run(self, run_id: str) -> _RunState:
        try:
            return self._runs[run_id]
        except KeyError as exc:
            raise KeyError(f"unknown workflow run: {run_id}") from exc

    @staticmethod
    def _get_step(run: _RunState, step_id: str) -> _StepState:
        try:
            return run.steps[step_id]
        except KeyError as exc:
            raise KeyError(f"unknown workflow step: {step_id}") from exc
