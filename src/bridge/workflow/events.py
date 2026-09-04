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
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class StepOutcomeReceipt(FrozenModel):
    workflow_run_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    attempt: int = Field(ge=1)
    approved_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool_run_id: str = Field(min_length=1)
    tool_run_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_state: str = Field(min_length=1)
    artifact_ids: tuple[str, ...] = ()


class StepSnapshot(FrozenModel):
    step_id: str
    tool_id: str
    scientific_status: str
    status: StepStatus
    attempts: int = Field(ge=0)
    reason_codes: list[str] = Field(default_factory=list)
    outcome_receipt: StepOutcomeReceipt | None = None


class RunSnapshot(FrozenModel):
    run_id: str
    plan_id: str
    status: RunStatus
    status_scope: Literal["execution_only"] = "execution_only"
    scientific_readiness: Literal["not_assessed"] = "not_assessed"
    domain_score: None = None
    steps: list[StepSnapshot]


class RunEventType(StrEnum):
    RUN_SUBMITTED = "run_submitted"
    STEP_CLAIMED = "step_claimed"
    STEP_SUCCEEDED = "step_succeeded"
    STEP_PARTIAL = "step_partial"
    STEP_FAILED = "step_failed"
    RUN_RECOVERED = "run_recovered"
    RUN_CANCELLED = "run_cancelled"


NonEmptyString = Annotated[str, Field(min_length=1)]


class RunSubmittedPayload(FrozenModel):
    plan: AnalysisPlan
    max_attempts: int = Field(default=2, ge=1, le=10)


class BlockedStepPayload(FrozenModel):
    step_id: NonEmptyString
    reason_codes: tuple[NonEmptyString, ...] = Field(min_length=1)


class StepEventPayload(FrozenModel):
    step_id: NonEmptyString
    claim_id: NonEmptyString
    attempt: int = Field(ge=1)
    reason_codes: tuple[NonEmptyString, ...] = ()
    outcome_receipt: StepOutcomeReceipt | None = None
    retry_exhausted: bool = False
    blocked_steps: tuple[BlockedStepPayload, ...] = ()


class RecoveredStepPayload(FrozenModel):
    step_id: NonEmptyString
    outcome: Literal["retry", "failed"]
    reason_codes: tuple[NonEmptyString, ...] = ()

    @model_validator(mode="after")
    def validate_outcome(self) -> "RecoveredStepPayload":
        if self.outcome == "failed" and not self.reason_codes:
            raise ValueError("workflow_recovery_failure_requires_reason_codes")
        if self.outcome == "retry" and self.reason_codes:
            raise ValueError("workflow_recovery_retry_cannot_have_reason_codes")
        return self


class RunRecoveredPayload(FrozenModel):
    recovered_steps: tuple[RecoveredStepPayload, ...] = Field(min_length=1)
    blocked_steps: tuple[BlockedStepPayload, ...] = ()


class EmptyPayload(FrozenModel):
    pass


RunEventPayload = (
    RunSubmittedPayload
    | StepEventPayload
    | RunRecoveredPayload
    | EmptyPayload
)


_PAYLOAD_MODELS = {
    RunEventType.RUN_SUBMITTED: RunSubmittedPayload,
    RunEventType.STEP_CLAIMED: StepEventPayload,
    RunEventType.STEP_SUCCEEDED: StepEventPayload,
    RunEventType.STEP_PARTIAL: StepEventPayload,
    RunEventType.STEP_FAILED: StepEventPayload,
    RunEventType.RUN_RECOVERED: RunRecoveredPayload,
    RunEventType.RUN_CANCELLED: EmptyPayload,
}


class RunEvent(FrozenModel):
    schema_version: Literal["1"] = "1"
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
        candidate["payload"] = _PAYLOAD_MODELS[event_type].model_validate(
            candidate.get("payload", {})
        )
        return candidate

    @model_validator(mode="after")
    def validate_step_event(self) -> "RunEvent":
        if not isinstance(self.payload, StepEventPayload):
            return self
        payload = self.payload
        receipt = payload.outcome_receipt
        if receipt is not None and (
            receipt.workflow_run_id != self.run_id
            or receipt.step_id != payload.step_id
            or receipt.claim_id != payload.claim_id
            or receipt.attempt != payload.attempt
        ):
            raise ValueError("workflow_outcome_receipt_binding_mismatch")
        if self.event_type is RunEventType.STEP_CLAIMED:
            if payload.reason_codes or receipt or payload.retry_exhausted or payload.blocked_steps:
                raise ValueError("workflow_claim_payload_invalid")
        elif self.event_type is RunEventType.STEP_SUCCEEDED:
            if receipt is None or payload.reason_codes:
                raise ValueError("workflow_success_requires_outcome_receipt")
            if payload.retry_exhausted or payload.blocked_steps:
                raise ValueError("workflow_success_payload_invalid")
        elif self.event_type is RunEventType.STEP_PARTIAL:
            if receipt is None or payload.retry_exhausted:
                raise ValueError("workflow_partial_requires_outcome_receipt")
        elif self.event_type is RunEventType.STEP_FAILED:
            if not payload.reason_codes:
                raise ValueError("workflow_failure_requires_reason_codes")
            if payload.blocked_steps and not payload.retry_exhausted:
                raise ValueError("workflow_retry_exhaustion_payload_invalid")
        return self


@dataclass
class StepProjection:
    step_id: str
    tool_id: str
    scientific_status: str
    depends_on: tuple[str, ...]
    status: StepStatus
    attempts: int = 0
    active_claim_id: str | None = None
    reason_codes: tuple[str, ...] = ()
    outcome_receipt: StepOutcomeReceipt | None = None


@dataclass
class RunProjection:
    run_id: str
    plan: AnalysisPlan
    status: RunStatus
    steps: dict[str, StepProjection]
    last_sequence: int
    max_attempts: int

    def snapshot(self) -> RunSnapshot:
        return RunSnapshot(
            run_id=self.run_id,
            plan_id=self.plan.plan_id,
            status=self.status,
            steps=[
                StepSnapshot(
                    step_id=step.step_id,
                    tool_id=step.tool_id,
                    scientific_status=step.scientific_status,
                    status=step.status,
                    attempts=step.attempts,
                    reason_codes=list(step.reason_codes),
                    outcome_receipt=step.outcome_receipt,
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
            scientific_status=step.scientific_status or "unknown",
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
        max_attempts=first.payload.max_attempts,
    )
    for event in ordered[1:]:
        _apply_event(projection, event)
        projection.last_sequence = event.sequence
    return projection


def _apply_event(projection: RunProjection, event: RunEvent) -> None:
    if event.event_type is RunEventType.RUN_SUBMITTED:
        raise ValueError("workflow_run_submitted_twice")
    if event.event_type is RunEventType.RUN_CANCELLED:
        if not any(
            step.status in {StepStatus.PENDING, StepStatus.RUNNING}
            for step in projection.steps.values()
        ):
            raise ValueError("workflow_terminal_run_cannot_be_cancelled")
        for step in projection.steps.values():
            if step.status in {StepStatus.PENDING, StepStatus.RUNNING}:
                step.status = StepStatus.CANCELLED
                step.active_claim_id = None
        projection.status = RunStatus.CANCELLED
        return
    if event.event_type is RunEventType.RUN_RECOVERED:
        if not isinstance(event.payload, RunRecoveredPayload):
            raise ValueError("workflow_recovery_payload_invalid")
        expected = recovery_step_payloads(projection)
        if event.payload.recovered_steps != expected:
            raise ValueError("workflow_recovered_steps_invalid")
        exhausted = {
            item.step_id for item in expected if item.outcome == "failed"
        }
        expected_blocked = recovery_blocked_step_payloads(projection, exhausted)
        if event.payload.blocked_steps != expected_blocked:
            raise ValueError("workflow_recovery_blocked_steps_invalid")
        for recovered in expected:
            step = _step(projection, recovered.step_id)
            step.status = (
                StepStatus.PENDING
                if recovered.outcome == "retry"
                else StepStatus.FAILED
            )
            step.active_claim_id = None
            step.reason_codes = recovered.reason_codes
        for blocked in expected_blocked:
            step = _step(projection, blocked.step_id)
            step.status = StepStatus.SKIPPED
            step.reason_codes = blocked.reason_codes
        _refresh_status(projection)
        return

    if not isinstance(event.payload, StepEventPayload):
        raise ValueError("workflow_step_payload_invalid")
    payload = event.payload
    step = _step(projection, payload.step_id)
    if event.event_type is RunEventType.STEP_CLAIMED:
        if step.status is not StepStatus.PENDING:
            raise ValueError("workflow_step_not_pending")
        if not all(
            projection.steps[dependency].status is StepStatus.SUCCEEDED
            for dependency in step.depends_on
        ):
            raise ValueError("workflow_step_dependencies_not_succeeded")
        if payload.attempt != step.attempts + 1:
            raise ValueError("workflow_claim_attempt_invalid")
        step.status = StepStatus.RUNNING
        step.attempts = payload.attempt
        step.active_claim_id = payload.claim_id
    else:
        if step.status is not StepStatus.RUNNING:
            raise ValueError("workflow_step_not_running")
        if (
            step.active_claim_id != payload.claim_id
            or step.attempts != payload.attempt
        ):
            raise ValueError("workflow_claim_fence_mismatch")
        step.active_claim_id = None
        if event.event_type is RunEventType.STEP_SUCCEEDED:
            step.status = StepStatus.SUCCEEDED
            step.outcome_receipt = payload.outcome_receipt
            step.reason_codes = ()
        elif event.event_type is RunEventType.STEP_PARTIAL:
            step.status = StepStatus.PARTIAL
            step.outcome_receipt = payload.outcome_receipt
            step.reason_codes = payload.reason_codes
            expected = blocked_descendant_ids(projection, step.step_id)
            actual = tuple(item.step_id for item in payload.blocked_steps)
            if actual != expected:
                raise ValueError("workflow_blocked_descendants_invalid")
            for blocked in payload.blocked_steps:
                child = _step(projection, blocked.step_id)
                child.status = StepStatus.SKIPPED
                child.reason_codes = blocked.reason_codes
        elif event.event_type is RunEventType.STEP_FAILED:
            step.status = StepStatus.FAILED
            step.outcome_receipt = payload.outcome_receipt
            step.reason_codes = payload.reason_codes
            if payload.retry_exhausted:
                expected = blocked_descendant_ids(projection, step.step_id)
                actual = tuple(item.step_id for item in payload.blocked_steps)
                if actual != expected:
                    raise ValueError("workflow_blocked_descendants_invalid")
                for blocked in payload.blocked_steps:
                    child = _step(projection, blocked.step_id)
                    child.status = StepStatus.SKIPPED
                    child.reason_codes = blocked.reason_codes
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


def recovery_step_payloads(
    projection: RunProjection,
) -> tuple[RecoveredStepPayload, ...]:
    recovered: list[RecoveredStepPayload] = []
    for step in projection.steps.values():
        if step.status is StepStatus.RUNNING:
            exhausted = step.attempts >= projection.max_attempts
            recovered.append(
                RecoveredStepPayload(
                    step_id=step.step_id,
                    outcome="failed" if exhausted else "retry",
                    reason_codes=("worker_interrupted_retry_exhausted",)
                    if exhausted
                    else (),
                )
            )
        elif step.status is StepStatus.FAILED and step.attempts < projection.max_attempts:
            recovered.append(
                RecoveredStepPayload(step_id=step.step_id, outcome="retry")
            )
    return tuple(recovered)


def recovery_blocked_step_payloads(
    projection: RunProjection, exhausted_step_ids: set[str]
) -> tuple[BlockedStepPayload, ...]:
    blocked = set(exhausted_step_ids)
    result: list[BlockedStepPayload] = []
    for plan_step in projection.plan.steps:
        state = projection.steps[plan_step.step_id]
        if state.status is StepStatus.PENDING and any(
            dependency in blocked for dependency in plan_step.depends_on
        ):
            result.append(
                BlockedStepPayload(
                    step_id=plan_step.step_id,
                    reason_codes=("upstream_step_retry_exhausted",),
                )
            )
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
    elif StepStatus.PARTIAL in states:
        projection.status = RunStatus.PARTIAL
    elif StepStatus.PENDING in states:
        projection.status = RunStatus.PENDING
    elif StepStatus.SUCCEEDED in states and StepStatus.SKIPPED in states:
        projection.status = RunStatus.PARTIAL
    elif StepStatus.SUCCEEDED in states:
        projection.status = RunStatus.SUCCEEDED
    else:
        projection.status = RunStatus.SKIPPED
