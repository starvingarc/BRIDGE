from __future__ import annotations

from enum import StrEnum

from pydantic import Field

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
