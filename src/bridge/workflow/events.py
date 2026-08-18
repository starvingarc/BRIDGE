from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Iterable, Literal

from pydantic import Field, model_validator

from bridge.domain.models import AnalysisPlan, StepDisposition
from bridge.toolkit.contracts import FrozenModel


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PARTIAL = "partial"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class StepSnapshot(FrozenModel):
    step_id: str
    tool_id: str
    status: StepStatus
    attempts: int = Field(ge=0)
    reason_codes: list[str] = Field(default_factory=list)


class RunSnapshot(FrozenModel):
    run_id: str
    plan_id: str
    status: RunStatus
    steps: list[StepSnapshot]


class RunEventType(StrEnum):
    RUN_SUBMITTED = "run_submitted"
    STEP_CLAIMED = "step_claimed"
    STEP_SUCCEEDED = "step_succeeded"
    STEP_FAILED = "step_failed"
    RUN_RESUMED = "run_resumed"
    RUN_CANCELLED = "run_cancelled"


NonEmptyString = Annotated[str, Field(min_length=1)]


class RunSubmittedPayload(FrozenModel):
    plan: AnalysisPlan


class BlockedStepPayload(FrozenModel):
    step_id: NonEmptyString
    reason_codes: tuple[NonEmptyString, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def reason_codes_are_unique(self) -> "BlockedStepPayload":
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("workflow_reason_codes_must_be_unique")
        return self


class StepEventPayload(FrozenModel):
    step_id: NonEmptyString
    reason_codes: tuple[NonEmptyString, ...] = ()
    retry_exhausted: bool = False
    blocked_steps: tuple[BlockedStepPayload, ...] = ()

    @model_validator(mode="after")
    def reason_codes_are_unique(self) -> "StepEventPayload":
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("workflow_reason_codes_must_be_unique")
        blocked_ids = [blocked.step_id for blocked in self.blocked_steps]
        if len(set(blocked_ids)) != len(blocked_ids):
            raise ValueError("workflow_blocked_step_ids_must_be_unique")
        return self


class RunResumedPayload(FrozenModel):
    step_ids: tuple[NonEmptyString, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def step_ids_are_unique(self) -> "RunResumedPayload":
        if len(set(self.step_ids)) != len(self.step_ids):
            raise ValueError("workflow_resume_step_ids_must_be_unique")
        return self


class EmptyPayload(FrozenModel):
    pass


RunEventPayload = RunSubmittedPayload | StepEventPayload | RunResumedPayload | EmptyPayload


_PAYLOAD_MODELS = {
    RunEventType.RUN_SUBMITTED: RunSubmittedPayload,
    RunEventType.STEP_CLAIMED: StepEventPayload,
    RunEventType.STEP_SUCCEEDED: StepEventPayload,
    RunEventType.STEP_FAILED: StepEventPayload,
    RunEventType.RUN_RESUMED: RunResumedPayload,
    RunEventType.RUN_CANCELLED: EmptyPayload,
}


class RunEvent(FrozenModel):
    schema_version: Literal["0", "1"] = "1"
    event_id: str
    run_id: str
    sequence: int = Field(ge=1)
    event_type: RunEventType
    recorded_at: datetime
    payload: RunEventPayload

    @model_validator(mode="before")
    @classmethod
    def validate_payload_contract(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        candidate = dict(value)
        event_type = RunEventType(candidate.get("event_type"))
        payload_model = _PAYLOAD_MODELS[event_type]
        candidate["payload"] = payload_model.model_validate(candidate.get("payload", {}))
        return candidate

    @model_validator(mode="after")
    def validate_event_specific_reasons(self) -> "RunEvent":
        if not isinstance(self.payload, StepEventPayload):
            return self
        if self.event_type is RunEventType.STEP_FAILED:
            if not self.payload.reason_codes:
                raise ValueError("workflow_failure_requires_reason_codes")
            if self.payload.blocked_steps and not self.payload.retry_exhausted:
                raise ValueError("workflow_retry_exhaustion_payload_invalid")
        elif self.event_type is RunEventType.STEP_CLAIMED and self.payload.reason_codes:
            raise ValueError("workflow_claim_cannot_have_reason_codes")
        elif self.payload.retry_exhausted or self.payload.blocked_steps:
            raise ValueError("workflow_non_failure_cannot_block_steps")
        return self


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
    if not isinstance(first.payload, RunSubmittedPayload):
        raise ValueError("workflow_submit_payload_invalid")
    plan = first.payload.plan
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
        if projection.status in {
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
            RunStatus.SKIPPED,
        }:
            raise ValueError("workflow_terminal_run_cannot_be_cancelled")
        for step in projection.steps.values():
            if step.status in {StepStatus.PENDING, StepStatus.RUNNING}:
                step.status = StepStatus.CANCELLED
        projection.status = RunStatus.CANCELLED
        return
    if event.event_type is RunEventType.RUN_RESUMED:
        if not isinstance(event.payload, RunResumedPayload):
            raise ValueError("workflow_resume_payload_invalid")
        for step_id in event.payload.step_ids:
            step = _step(projection, step_id)
            if step.status not in {StepStatus.FAILED, StepStatus.RUNNING}:
                raise ValueError("workflow_resume_step_not_interrupted_or_failed")
            step.status = StepStatus.PENDING
            step.reason_codes = ()
        _refresh_status(projection)
        return

    if not isinstance(event.payload, StepEventPayload):
        raise ValueError("workflow_step_payload_invalid")
    step = _step(projection, event.payload.step_id)
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
        step.reason_codes = event.payload.reason_codes
    elif event.event_type is RunEventType.STEP_FAILED:
        if step.status is not StepStatus.RUNNING:
            raise ValueError("workflow_step_not_running")
        step.status = StepStatus.FAILED
        step.reason_codes = event.payload.reason_codes
        if event.payload.retry_exhausted:
            expected = blocked_descendant_ids(projection, step.step_id)
            actual = tuple(blocked.step_id for blocked in event.payload.blocked_steps)
            if actual != expected:
                raise ValueError("workflow_blocked_descendants_invalid")
            for blocked_payload in event.payload.blocked_steps:
                blocked = projection.steps[blocked_payload.step_id]
                blocked.status = StepStatus.SKIPPED
                blocked.reason_codes = blocked_payload.reason_codes
    _refresh_status(projection)


def _step(projection: RunProjection, step_id: Any) -> StepProjection:
    if not isinstance(step_id, str):
        raise ValueError("workflow_event_requires_step_id")
    try:
        return projection.steps[step_id]
    except KeyError as exc:
        raise ValueError("workflow_event_unknown_step") from exc


def blocked_descendant_ids(
    projection: RunProjection, failed_step_id: str
) -> tuple[str, ...]:
    blocked = {failed_step_id}
    result: list[str] = []
    for plan_step in projection.plan.steps:
        state = projection.steps[plan_step.step_id]
        if state.status is StepStatus.PENDING and any(
            dependency in blocked for dependency in plan_step.depends_on
        ):
            result.append(plan_step.step_id)
            blocked.add(plan_step.step_id)
    return tuple(result)


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
