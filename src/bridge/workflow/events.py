from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Iterable

from pydantic import Field

from bridge.domain import AnalysisPlan, StepDisposition
from bridge.toolkit.contracts import FrozenModel
from bridge.workflow.models import RunSnapshot, RunStatus, StepSnapshot, StepStatus


class RunEventType(StrEnum):
    RUN_SUBMITTED = "run_submitted"
    STEP_CLAIMED = "step_claimed"
    STEP_SUCCEEDED = "step_succeeded"
    STEP_FAILED = "step_failed"
    RUN_RESUMED = "run_resumed"
    RUN_CANCELLED = "run_cancelled"


class RunEvent(FrozenModel):
    event_id: str
    run_id: str
    sequence: int = Field(ge=1)
    event_type: RunEventType
    recorded_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


@dataclass
class StepProjection:
    step_id: str
    tool_id: str
    depends_on: tuple[str, ...]
    status: StepStatus
    attempts: int = 0
    reason_codes: tuple[str, ...] = ()


@dataclass
class RunProjection:
    run_id: str
    plan: AnalysisPlan
    status: RunStatus
    steps: dict[str, StepProjection]
    last_sequence: int

    def snapshot(self) -> RunSnapshot:
        return RunSnapshot(
            run_id=self.run_id,
            plan_id=self.plan.plan_id,
            status=self.status,
            steps=[
                StepSnapshot(
                    step_id=step.step_id,
                    tool_id=step.tool_id,
                    status=step.status,
                    attempts=step.attempts,
                    reason_codes=list(step.reason_codes),
                )
                for step in self.steps.values()
            ],
        )


def project_run(events: Iterable[RunEvent]) -> RunProjection:
    ordered = list(events)
    if not ordered:
        raise ValueError("workflow_run_has_no_events")
    run_id = ordered[0].run_id
    for expected, event in enumerate(ordered, start=1):
        if event.run_id != run_id or event.sequence != expected:
            raise ValueError("workflow_event_sequence_invalid")
    first = ordered[0]
    if first.event_type is not RunEventType.RUN_SUBMITTED:
        raise ValueError("workflow_first_event_must_submit_run")
    plan = AnalysisPlan.model_validate(first.payload.get("plan"))
    steps = {
        step.step_id: StepProjection(
            step_id=step.step_id,
            tool_id=step.tool_id,
            depends_on=tuple(step.depends_on),
            status=(
                StepStatus.PENDING
                if step.disposition is StepDisposition.EXECUTE
                else StepStatus.SKIPPED
            ),
            reason_codes=tuple(step.reason_codes),
        )
        for step in plan.steps
    }
    projection = RunProjection(
        run_id=run_id,
        plan=plan,
        status=(
            RunStatus.PENDING
            if any(step.status is StepStatus.PENDING for step in steps.values())
            else RunStatus.SKIPPED
        ),
        steps=steps,
        last_sequence=first.sequence,
    )
    for event in ordered[1:]:
        _apply_event(projection, event)
        projection.last_sequence = event.sequence
    return projection


def _apply_event(projection: RunProjection, event: RunEvent) -> None:
    if event.event_type is RunEventType.RUN_SUBMITTED:
        raise ValueError("workflow_run_submitted_twice")
    if event.event_type is RunEventType.RUN_CANCELLED:
        for step in projection.steps.values():
            if step.status in {StepStatus.PENDING, StepStatus.RUNNING}:
                step.status = StepStatus.CANCELLED
        projection.status = RunStatus.CANCELLED
        return
    if event.event_type is RunEventType.RUN_RESUMED:
        step_ids = event.payload.get("step_ids")
        if not isinstance(step_ids, list) or not step_ids:
            raise ValueError("workflow_resume_requires_step_ids")
        for step_id in step_ids:
            step = _step(projection, step_id)
            if step.status not in {StepStatus.FAILED, StepStatus.RUNNING}:
                raise ValueError("workflow_resume_step_not_interrupted_or_failed")
            step.status = StepStatus.PENDING
            step.reason_codes = ()
        _refresh_status(projection)
        return

    step = _step(projection, event.payload.get("step_id"))
    if event.event_type is RunEventType.STEP_CLAIMED:
        if step.status is not StepStatus.PENDING:
            raise ValueError("workflow_step_not_pending")
        if not all(
            projection.steps[dependency].status is StepStatus.SUCCEEDED
            for dependency in step.depends_on
        ):
            raise ValueError("workflow_step_dependencies_not_succeeded")
        step.status = StepStatus.RUNNING
        step.attempts += 1
    elif event.event_type is RunEventType.STEP_SUCCEEDED:
        if step.status is not StepStatus.RUNNING:
            raise ValueError("workflow_step_not_running")
        step.status = StepStatus.SUCCEEDED
        step.reason_codes = tuple(event.payload.get("reason_codes", []))
    elif event.event_type is RunEventType.STEP_FAILED:
        if step.status is not StepStatus.RUNNING:
            raise ValueError("workflow_step_not_running")
        step.status = StepStatus.FAILED
        step.reason_codes = tuple(event.payload.get("reason_codes", []))
    _refresh_status(projection)


def _step(projection: RunProjection, step_id: Any) -> StepProjection:
    if not isinstance(step_id, str):
        raise ValueError("workflow_event_requires_step_id")
    try:
        return projection.steps[step_id]
    except KeyError as exc:
        raise ValueError("workflow_event_unknown_step") from exc


def _refresh_status(projection: RunProjection) -> None:
    states = {step.status for step in projection.steps.values()}
    if StepStatus.RUNNING in states:
        projection.status = RunStatus.RUNNING
    elif StepStatus.FAILED in states:
        projection.status = (
            RunStatus.PARTIAL if StepStatus.PENDING in states else RunStatus.FAILED
        )
    elif StepStatus.PENDING in states:
        projection.status = RunStatus.PENDING
    elif StepStatus.SUCCEEDED in states:
        projection.status = RunStatus.SUCCEEDED
    else:
        projection.status = RunStatus.SKIPPED
