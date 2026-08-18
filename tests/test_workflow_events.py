from __future__ import annotations

from datetime import datetime, timezone

import pytest

from bridge.domain import AnalysisPlan, PlanStep
from bridge.workflow.events import RunEvent, project_run


def _plan() -> AnalysisPlan:
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
        ],
    )


def _event(sequence: int, event_type: str, payload: dict | None = None) -> RunEvent:
    return RunEvent(
        event_id=f"event-{sequence}",
        run_id="run-1",
        sequence=sequence,
        event_type=event_type,
        recorded_at=datetime(2026, 8, 16, tzinfo=timezone.utc),
        payload=payload or {},
    )


def test_projection_rebuilds_attempts_failure_and_resume() -> None:
    events = [
        _event(1, "run_submitted", {"plan": _plan().model_dump(mode="json")}),
        _event(2, "step_claimed", {"step_id": "step-p0-01"}),
        _event(3, "step_succeeded", {"step_id": "step-p0-01"}),
        _event(4, "step_claimed", {"step_id": "step-p0-02"}),
        _event(
            5,
            "step_failed",
            {"step_id": "step-p0-02", "reason_codes": ["transient_failure"]},
        ),
        _event(6, "run_resumed", {"step_ids": ["step-p0-02"]}),
        _event(7, "step_claimed", {"step_id": "step-p0-02"}),
        _event(8, "step_succeeded", {"step_id": "step-p0-02"}),
    ]

    projection = project_run(events)

    assert projection.status == "succeeded"
    assert projection.steps["step-p0-01"].attempts == 1
    assert projection.steps["step-p0-02"].attempts == 2
    assert projection.last_sequence == 8


def test_projection_rejects_a_sequence_gap() -> None:
    with pytest.raises(ValueError, match="sequence_invalid"):
        project_run(
            [
                _event(1, "run_submitted", {"plan": _plan().model_dump(mode="json")}),
                _event(3, "step_claimed", {"step_id": "step-p0-01"}),
            ]
        )


def test_projection_rejects_claim_before_dependencies() -> None:
    with pytest.raises(ValueError, match="dependencies_not_succeeded"):
        project_run(
            [
                _event(1, "run_submitted", {"plan": _plan().model_dump(mode="json")}),
                _event(2, "step_claimed", {"step_id": "step-p0-02"}),
            ]
        )


def test_event_contract_rejects_missing_and_duplicate_failure_reasons() -> None:
    with pytest.raises(ValueError, match="failure_requires_reason_codes"):
        _event(1, "step_failed", {"step_id": "step-p0-01"})
    with pytest.raises(ValueError, match="reason_codes_must_be_unique"):
        _event(
            1,
            "step_failed",
            {"step_id": "step-p0-01", "reason_codes": ["failure", "failure"]},
        )


def test_projection_rejects_cancellation_after_terminal_failure() -> None:
    events = [
        _event(1, "run_submitted", {"plan": _plan().model_dump(mode="json")}),
        _event(2, "step_claimed", {"step_id": "step-p0-01"}),
        _event(
            3,
            "step_failed",
            {
                "step_id": "step-p0-01",
                "reason_codes": ["permanent_failure"],
                "retry_exhausted": True,
                "blocked_steps": [
                    {
                        "step_id": "step-p0-02",
                        "reason_codes": ["upstream_step_retry_exhausted"],
                    }
                ],
            },
        ),
        _event(4, "run_cancelled"),
    ]
    with pytest.raises(ValueError, match="terminal_run_cannot_be_cancelled"):
        project_run(events)
