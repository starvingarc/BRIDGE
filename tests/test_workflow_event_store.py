from __future__ import annotations

from pathlib import Path

import pytest

from bridge.workflow.event_store import (
    EventSequenceConflict,
    InMemoryRunEventStore,
    SQLiteRunEventStore,
)


def _plan_payload() -> dict:
    return {
        "plan_id": "plan-1",
        "version": "0.1",
        "case_ref": "case-1@0.1",
        "status": "approved",
        "knowledge_snapshot_ref": "knowledge://p0/2026-08-12",
        "steps": [
            {
                "step_id": "step-p0-01",
                "tool_id": "P0-01",
                "tool_version": "0.1.0",
                "disposition": "execute",
            }
        ],
    }


@pytest.mark.parametrize("store_kind", ["memory", "sqlite"])
def test_event_store_appends_ordered_events(tmp_path: Path, store_kind: str) -> None:
    store = (
        InMemoryRunEventStore()
        if store_kind == "memory"
        else SQLiteRunEventStore(tmp_path / "workflow.sqlite3")
    )

    store.append(
        "run-1",
        "run_submitted",
        {"plan": _plan_payload()},
        expected_sequence=0,
    )
    store.append(
        "run-1",
        "run_cancelled",
        {},
        expected_sequence=1,
    )

    events = store.load("run-1")
    assert [event.sequence for event in events] == [1, 2]
    assert [event.event_type for event in events] == ["run_submitted", "run_cancelled"]
    assert [event.schema_version for event in events] == ["1", "1"]


@pytest.mark.parametrize("store_kind", ["memory", "sqlite"])
def test_event_store_rejects_stale_sequence(tmp_path: Path, store_kind: str) -> None:
    store = (
        InMemoryRunEventStore()
        if store_kind == "memory"
        else SQLiteRunEventStore(tmp_path / "workflow.sqlite3")
    )
    store.append("run-1", "run_cancelled", {}, expected_sequence=0)

    with pytest.raises(EventSequenceConflict, match="sequence_conflict"):
        store.append("run-1", "run_cancelled", {}, expected_sequence=0)


def test_sqlite_store_persists_across_instances(tmp_path: Path) -> None:
    database_path = tmp_path / "workflow.sqlite3"
    first = SQLiteRunEventStore(database_path)
    first.append("run-1", "run_cancelled", {}, expected_sequence=0)

    second = SQLiteRunEventStore(database_path)

    assert second.load("run-1") == first.load("run-1")


def test_memory_store_defensively_snapshots_nested_payloads() -> None:
    store = InMemoryRunEventStore()
    payload = {"plan": _plan_payload()}
    store.append("run-1", "run_submitted", payload, expected_sequence=0)
    payload["plan"]["plan_id"] = "mutated"

    loaded = store.load("run-1")
    assert loaded[0].payload.plan.plan_id == "plan-1"  # type: ignore[union-attr]
    loaded_again = store.load("run-1")
    assert loaded[0] is not loaded_again[0]
    assert loaded[0].payload is not loaded_again[0].payload


def test_sqlite_store_marks_pre_version_column_rows_as_legacy(tmp_path: Path) -> None:
    import json
    import sqlite3

    database_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE run_events (
                run_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                event_id TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (run_id, sequence)
            )
            """
        )
        connection.execute(
            "INSERT INTO run_events VALUES (?, ?, ?, ?, ?, ?)",
            (
                "run-1",
                1,
                "event-1",
                "run_cancelled",
                "2026-08-16T00:00:00+00:00",
                json.dumps({}),
            ),
        )

    events = SQLiteRunEventStore(database_path).load("run-1")
    assert events[0].schema_version == "0"
