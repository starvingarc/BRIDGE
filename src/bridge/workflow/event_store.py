from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Protocol
from uuid import uuid4

from pydantic import ValidationError

from bridge.storage.private_paths import prepare_private_file, tighten_private_file
from bridge.workflow.events import RunEvent, RunEventType


class EventSequenceConflict(RuntimeError):
    pass


class EventCompatibilityError(RuntimeError):
    """A durable event cannot be interpreted by this runtime version."""

    def __init__(
        self,
        reason_code: str,
        *,
        run_id: str,
        sequence: int,
        event_id: str,
        schema_version: str,
    ) -> None:
        self.reason_code = reason_code
        self.run_id = run_id
        self.sequence = sequence
        self.event_id = event_id
        self.schema_version = schema_version
        super().__init__(
            f"{reason_code}: run_id={run_id} sequence={sequence} "
            f"event_id={event_id} schema_version={schema_version}"
        )


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
    _COLUMNS = {
        "run_id",
        "sequence",
        "event_id",
        "event_type",
        "recorded_at",
        "payload_json",
        "schema_version",
    }

    def __init__(self, database_path: Path) -> None:
        self.database_path = prepare_private_file(database_path)
        connection = self._connect()
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS run_events (
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    PRIMARY KEY (run_id, sequence)
                )
                """
            )
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(run_events)")
            }
            if columns != self._COLUMNS:
                raise ValueError("workflow_event_store_schema_incompatible")
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()
            self._tighten_files()

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
            self._tighten_files()

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
        self._tighten_files()
        events: list[RunEvent] = []
        for row in rows:
            coordinates = {
                "event_id": row[0],
                "run_id": row[1],
                "sequence": row[2],
                "event_type": row[3],
                "recorded_at": row[4],
                "schema_version": row[6],
            }
            if str(row[6]) != "1":
                raise _compatibility_error(
                    "workflow_event_schema_version_unsupported", coordinates
                )
            try:
                payload = json.loads(row[5])
                events.append(
                    RunEvent.model_validate(coordinates | {"payload": payload})
                )
            except (TypeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
                raise _compatibility_error(
                    "workflow_event_schema_incompatible", coordinates
                ) from exc
        return events

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _tighten_files(self) -> None:
        tighten_private_file(self.database_path)
        tighten_private_file(Path(f"{self.database_path}-wal"))
        tighten_private_file(Path(f"{self.database_path}-shm"))


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


def _compatibility_error(
    reason_code: str, coordinates: dict[str, Any]
) -> EventCompatibilityError:
    return EventCompatibilityError(
        reason_code,
        run_id=str(coordinates["run_id"]),
        sequence=int(coordinates["sequence"]),
        event_id=str(coordinates["event_id"]),
        schema_version=str(coordinates["schema_version"]),
    )
