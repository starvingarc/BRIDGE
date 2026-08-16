from __future__ import annotations

from pathlib import Path

import pytest

from bridge.workflow.event_store import (
    EventSequenceConflict,
    InMemoryRunEventStore,
    SQLiteRunEventStore,
)


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
        {"plan": {"plan_id": "plan-1"}},
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
