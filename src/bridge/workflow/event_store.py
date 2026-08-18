from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Protocol
from uuid import uuid4

from bridge.workflow.events import RunEvent, RunEventType


class EventSequenceConflict(RuntimeError):
    pass


class RunEventStore(Protocol):
    def append(
        self,
        run_id: str,
        event_type: RunEventType,
        payload: dict[str, Any],
        *,
        expected_sequence: int,
    ) -> RunEvent: ...

    def load(self, run_id: str) -> list[RunEvent]: ...


class InMemoryRunEventStore:
    def __init__(self) -> None:
        self._events: dict[str, list[RunEvent]] = {}
        self._lock = Lock()

    def append(
        self,
        run_id: str,
        event_type: RunEventType,
        payload: dict[str, Any],
        *,
        expected_sequence: int,
    ) -> RunEvent:
        with self._lock:
            events = self._events.setdefault(run_id, [])
            if len(events) != expected_sequence:
                raise EventSequenceConflict("workflow_event_sequence_conflict")
            event = _new_event(run_id, len(events) + 1, event_type, payload)
            events.append(_clone_event(event))
            return _clone_event(event)

    def load(self, run_id: str) -> list[RunEvent]:
        with self._lock:
            return [_clone_event(event) for event in self._events.get(run_id, [])]


class SQLiteRunEventStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS run_events (
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    schema_version TEXT NOT NULL DEFAULT '0',
                    PRIMARY KEY (run_id, sequence)
                )
                """
            )
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(run_events)")
            }
            if "schema_version" not in columns:
                connection.execute(
                    "ALTER TABLE run_events "
                    "ADD COLUMN schema_version TEXT NOT NULL DEFAULT '0'"
                )

    def append(
        self,
        run_id: str,
        event_type: RunEventType,
        payload: dict[str, Any],
        *,
        expected_sequence: int,
    ) -> RunEvent:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) FROM run_events WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            current_sequence = int(row[0])
            if current_sequence != expected_sequence:
                connection.rollback()
                raise EventSequenceConflict("workflow_event_sequence_conflict")
            event = _new_event(run_id, current_sequence + 1, event_type, payload)
            connection.execute(
                """
                INSERT INTO run_events (
                    run_id, sequence, event_id, event_type, recorded_at, payload_json,
                    schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.run_id,
                    event.sequence,
                    event.event_id,
                    event.event_type.value,
                    event.recorded_at.isoformat(),
                    json.dumps(
                        event.payload.model_dump(mode="json"),
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    event.schema_version,
                ),
            )
            connection.commit()
            return event
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def load(self, run_id: str) -> list[RunEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT event_id, run_id, sequence, event_type, recorded_at, payload_json,
                       schema_version
                FROM run_events
                WHERE run_id = ?
                ORDER BY sequence
                """,
                (run_id,),
            ).fetchall()
        return [
            RunEvent(
                event_id=row[0],
                run_id=row[1],
                sequence=row[2],
                event_type=row[3],
                recorded_at=row[4],
                payload=json.loads(row[5]),
                schema_version=row[6],
            )
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection


def _new_event(
    run_id: str,
    sequence: int,
    event_type: RunEventType,
    payload: dict[str, Any],
) -> RunEvent:
    return RunEvent(
        event_id=f"event-{uuid4().hex}",
        run_id=run_id,
        sequence=sequence,
        event_type=event_type,
        recorded_at=datetime.now(timezone.utc),
        payload=payload,
    )


def _clone_event(event: RunEvent) -> RunEvent:
    return RunEvent.model_validate(event.model_dump(mode="json"))
