from __future__ import annotations

import hashlib
import json
from threading import RLock
from uuid import uuid4

from pydantic import Field

from bridge.domain.models import AnalysisPlan, PlanStatus, PlanStep
from bridge.runners.pipeline import ToolExecutionDenied, ToolExecutionPipeline
from bridge.toolkit.contracts import (
    ExecutionState,
    FrozenModel,
    ToolRun,
    ToolRunV2,
)
from bridge.workflow.event_store import InMemoryRunEventStore, RunEventStore
from bridge.workflow.events import (
    RunEventType,
    RunProjection,
    RunSnapshot,
    RunStatus,
    StepOutcomeReceipt,
    StepStatus,
    blocked_descendant_ids,
    project_run,
    recovery_blocked_step_payloads,
    recovery_step_payloads,
)


ToolRunModel = ToolRun | ToolRunV2


def _canonical_json(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class StepClaim(FrozenModel):
    workflow_run_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    attempt: int = Field(ge=1)
    approved_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    step: PlanStep


class LocalWorkflowExecutor:
    """Event-sourced coordinator for one local worker."""

    def __init__(
        self,
        event_store: RunEventStore | None = None,
        *,
        max_attempts: int = 2,
    ) -> None:
        if not 1 <= max_attempts <= 10:
            raise ValueError("max_attempts must be between one and ten")
        self._max_attempts = max_attempts
        self._event_store = event_store or InMemoryRunEventStore()
        self._operation_lock = RLock()

    def submit(self, plan: AnalysisPlan) -> str:
        if plan.status is not PlanStatus.APPROVED or plan.approval_receipt is None:
            raise ValueError("analysis_plan_not_approved")
        run_id = f"run-{uuid4().hex}"
        self._event_store.append(
            run_id,
            RunEventType.RUN_SUBMITTED,
            {
                "plan": plan.model_dump(mode="json"),
                "max_attempts": self._max_attempts,
            },
            expected_sequence=0,
        )
        return run_id

    def claim_step(self, run_id: str) -> StepClaim | None:
        with self._operation_lock:
            return self._claim_step(run_id)

    def _claim_step(self, run_id: str) -> StepClaim | None:
        run = self._projection(run_id)
        for plan_step in run.plan.steps:
            state = run.steps[plan_step.step_id]
            if state.status is not StepStatus.PENDING:
                continue
            if all(
                run.steps[dependency].status is StepStatus.SUCCEEDED
                for dependency in plan_step.depends_on
            ):
                if plan_step.approved_request_sha256 is None:
                    raise ValueError("workflow_step_missing_approved_request")
                claim_id = f"claim-{uuid4().hex}"
                attempt = state.attempts + 1
                self._event_store.append(
                    run_id,
                    RunEventType.STEP_CLAIMED,
                    {
                        "step_id": plan_step.step_id,
                        "claim_id": claim_id,
                        "attempt": attempt,
                    },
                    expected_sequence=run.last_sequence,
                )
                return StepClaim(
                    workflow_run_id=run_id,
                    step_id=plan_step.step_id,
                    claim_id=claim_id,
                    attempt=attempt,
                    approved_request_sha256=plan_step.approved_request_sha256,
                    step=plan_step,
                )
        return None

    def execute_claim(
        self,
        claim: StepClaim,
        pipeline: ToolExecutionPipeline,
    ) -> ToolRunModel:
        with self._operation_lock:
            return self._execute_claim(claim, pipeline)

    def _execute_claim(
        self,
        claim: StepClaim,
        pipeline: ToolExecutionPipeline,
    ) -> ToolRunModel:
        run = self._projection(claim.workflow_run_id)
        self._validate_claim(run, claim)
        try:
            outcome = pipeline.execute_step(claim.step)
        except ToolExecutionDenied as error:
            self.fail_step(claim, reason_codes=error.reason_codes)
            raise
        except Exception:
            self.fail_step(claim, reason_codes=["tool_execution_failed"])
            raise
        self._complete_outcome(claim, outcome)
        return outcome

    def _complete_outcome(self, claim: StepClaim, outcome: ToolRunModel) -> None:
        run = self._projection(claim.workflow_run_id)
        state = self._validate_claim(run, claim)
        plan_step = self._plan_step(run, claim.step_id)
        request_json = _canonical_json(outcome.request)
        request_sha256 = hashlib.sha256(request_json.encode()).hexdigest()
        if (
            request_sha256 != claim.approved_request_sha256
            or plan_step.approved_request_json != request_json
            or outcome.request.tool_id != plan_step.tool_id
            or outcome.tool_version != plan_step.tool_version
        ):
            raise ValueError("workflow_tool_run_not_bound_to_claim")

        outcome_sha256 = hashlib.sha256(
            _canonical_json(outcome).encode()
        ).hexdigest()
        receipt = StepOutcomeReceipt(
            workflow_run_id=claim.workflow_run_id,
            step_id=claim.step_id,
            claim_id=claim.claim_id,
            attempt=claim.attempt,
            approved_request_sha256=claim.approved_request_sha256,
            tool_run_id=outcome.run_id,
            tool_run_sha256=outcome_sha256,
            execution_state=outcome.execution_state.value,
            artifact_ids=tuple(item.artifact_id for item in outcome.artifacts),
        )
        event_type = (
            RunEventType.STEP_SUCCEEDED
            if outcome.execution_state is ExecutionState.SUCCEEDED
            else (
                RunEventType.STEP_PARTIAL
                if outcome.execution_state is ExecutionState.PARTIAL
                else RunEventType.STEP_FAILED
            )
        )
        # Tool reasons may describe scientific limits on successful execution.
        # Preserve them in the hashed ToolRun, not the workflow failure channel.
        reasons = () if event_type is RunEventType.STEP_SUCCEEDED else tuple(outcome.reason_codes)
        if event_type is RunEventType.STEP_FAILED and not reasons:
            reasons = ("tool_run_not_successful",)
        self._append_completion(
            run,
            state.attempts,
            claim,
            event_type=event_type,
            reason_codes=reasons,
            outcome_receipt=receipt,
        )

    def fail_step(self, claim: StepClaim, *, reason_codes: list[str]) -> None:
        with self._operation_lock:
            self._fail_step(claim, reason_codes=reason_codes)

    def _fail_step(self, claim: StepClaim, *, reason_codes: list[str]) -> None:
        if not reason_codes:
            raise ValueError("workflow_failure_requires_reason_codes")
        run = self._projection(claim.workflow_run_id)
        state = self._validate_claim(run, claim)
        self._append_completion(
            run,
            state.attempts,
            claim,
            event_type=RunEventType.STEP_FAILED,
            reason_codes=tuple(reason_codes),
            outcome_receipt=None,
        )

    def cancel(self, run_id: str) -> None:
        with self._operation_lock:
            self._cancel(run_id)

    def _cancel(self, run_id: str) -> None:
        run = self._projection(run_id)
        if not any(
            step.status in {StepStatus.PENDING, StepStatus.RUNNING}
            for step in run.steps.values()
        ):
            return
        self._event_store.append(
            run_id,
            RunEventType.RUN_CANCELLED,
            {},
            expected_sequence=run.last_sequence,
        )

    def resume(self, run_id: str) -> None:
        with self._operation_lock:
            self._resume(run_id)

    def _resume(self, run_id: str) -> None:
        run = self._projection(run_id)
        if run.status not in {RunStatus.RUNNING, RunStatus.FAILED, RunStatus.PARTIAL}:
            raise ValueError("workflow_run_not_resumable")
        recovered_steps = recovery_step_payloads(run)
        if not recovered_steps:
            raise ValueError("workflow_retry_limit_reached")
        exhausted = {
            item.step_id for item in recovered_steps if item.outcome == "failed"
        }
        blocked_steps = recovery_blocked_step_payloads(run, exhausted)
        self._event_store.append(
            run_id,
            RunEventType.RUN_RECOVERED,
            {
                "recovered_steps": [
                    item.model_dump(mode="json") for item in recovered_steps
                ],
                "blocked_steps": [
                    item.model_dump(mode="json") for item in blocked_steps
                ],
            },
            expected_sequence=run.last_sequence,
        )

    def get_status(self, run_id: str) -> RunSnapshot:
        return self._projection(run_id).snapshot()

    def _append_completion(
        self,
        run: RunProjection,
        attempt: int,
        claim: StepClaim,
        *,
        event_type: RunEventType,
        reason_codes: tuple[str, ...],
        outcome_receipt: StepOutcomeReceipt | None,
    ) -> None:
        retry_exhausted = (
            event_type is RunEventType.STEP_FAILED
            and attempt >= run.max_attempts
        )
        blocked_reason = (
            "upstream_step_partial"
            if event_type is RunEventType.STEP_PARTIAL
            else "upstream_step_retry_exhausted" if retry_exhausted else None
        )
        blocked_steps = (
            [
                {
                    "step_id": step_id,
                    "reason_codes": [blocked_reason],
                }
                for step_id in blocked_descendant_ids(run, claim.step_id)
            ]
            if blocked_reason is not None
            else []
        )
        self._event_store.append(
            claim.workflow_run_id,
            event_type,
            {
                "step_id": claim.step_id,
                "claim_id": claim.claim_id,
                "attempt": claim.attempt,
                "reason_codes": list(reason_codes),
                "outcome_receipt": (
                    outcome_receipt.model_dump(mode="json")
                    if outcome_receipt is not None
                    else None
                ),
                "retry_exhausted": retry_exhausted,
                "blocked_steps": blocked_steps,
            },
            expected_sequence=run.last_sequence,
        )

    @staticmethod
    def _validate_claim(run: RunProjection, claim: StepClaim):
        if claim.workflow_run_id != run.run_id:
            raise ValueError("workflow_claim_run_mismatch")
        try:
            state = run.steps[claim.step_id]
        except KeyError as exc:
            raise KeyError(f"unknown workflow step: {claim.step_id}") from exc
        if (
            state.status is not StepStatus.RUNNING
            or state.active_claim_id != claim.claim_id
            or state.attempts != claim.attempt
        ):
            raise ValueError("workflow_claim_fence_mismatch")
        plan_step = LocalWorkflowExecutor._plan_step(run, claim.step_id)
        if (
            claim.step_id != claim.step.step_id
            or claim.step != plan_step
            or claim.approved_request_sha256 != plan_step.approved_request_sha256
        ):
            raise ValueError("workflow_claim_contract_mismatch")
        return state

    @staticmethod
    def _plan_step(run: RunProjection, step_id: str) -> PlanStep:
        for step in run.plan.steps:
            if step.step_id == step_id:
                return step
        raise KeyError(f"unknown workflow step: {step_id}")

    def _projection(self, run_id: str) -> RunProjection:
        events = self._event_store.load(run_id)
        if not events:
            raise KeyError(f"unknown workflow run: {run_id}")
        return project_run(events)
