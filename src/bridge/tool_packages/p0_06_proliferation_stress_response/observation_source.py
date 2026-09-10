from __future__ import annotations

import hashlib
import io
import json
import stat
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from bridge.tool_packages._configurable_contracts import observation_ids_sha256
from bridge.tool_packages.p0_06_proliferation_stress_response.method_models import (
    ProcessMethodInputV2,
    ProcessObservationStateV2,
)
from bridge.toolkit.contracts import CellStateEvidenceProfileV3


_REQUIRED_COLUMNS = {
    "observation_id",
    "prediction_set",
    "consensus_label",
    "support_state",
    "assignment_state",
    "open_set_state",
}


class SourceObservationError(RuntimeError):
    def __init__(self, reason_code: str, detail: str | None = None) -> None:
        self.reason_code = reason_code
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)


@dataclass(frozen=True)
class LoadedSourceObservations:
    rows: tuple[ProcessObservationStateV2, ...]
    artifact_manifest_sha256: str
    evidence_sha256: str


def _hash_regular_file(path: Path, *, kind: str) -> str:
    try:
        before = path.lstat()
        if path.is_symlink() or not stat.S_ISREG(before.st_mode):
            raise SourceObservationError(f"source_{kind}_not_regular_file")
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        after = path.lstat()
    except FileNotFoundError as exc:
        raise SourceObservationError(f"source_{kind}_not_found") from exc
    except SourceObservationError:
        raise
    except OSError as exc:
        raise SourceObservationError(f"source_{kind}_unreadable") from exc
    if (
        path.is_symlink()
        or not stat.S_ISREG(after.st_mode)
        or before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
    ):
        raise SourceObservationError(f"source_{kind}_modified_during_read")
    return digest.hexdigest()


def _read_bound_bytes(path: Path, expected_sha256: str, *, kind: str) -> bytes:
    if _hash_regular_file(path, kind=kind) != expected_sha256:
        raise SourceObservationError(f"source_{kind}_checksum_mismatch")
    try:
        before = path.lstat()
        payload = path.read_bytes()
        after = path.lstat()
    except FileNotFoundError as exc:
        raise SourceObservationError(f"source_{kind}_not_found") from exc
    except OSError as exc:
        raise SourceObservationError(f"source_{kind}_unreadable") from exc
    if (
        path.is_symlink()
        or not stat.S_ISREG(after.st_mode)
        or before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
    ):
        raise SourceObservationError(f"source_{kind}_modified_during_read")
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise SourceObservationError(f"source_{kind}_checksum_mismatch")
    if _hash_regular_file(path, kind=kind) != expected_sha256:
        raise SourceObservationError(f"source_{kind}_checksum_mismatch")
    return payload


def _canonical_path(value: object, *, reason_code: str) -> Path:
    if not isinstance(value, str) or not value:
        raise SourceObservationError(reason_code)
    path = Path(value)
    if not path.is_absolute():
        raise SourceObservationError(reason_code)
    return path.resolve()


def _manifest_artifact(
    manifest: dict[str, Any],
    *,
    artifact_id: str,
    kind: str,
    reason_code: str,
) -> dict[str, Any]:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise SourceObservationError("source_artifact_manifest_invalid")
    matches = [
        item
        for item in artifacts
        if isinstance(item, dict)
        and item.get("artifact_id") == artifact_id
        and item.get("kind") == kind
    ]
    if len(matches) != 1:
        raise SourceObservationError(reason_code)
    return matches[0]


def _validate_manifest(
    *,
    manifest: dict[str, Any],
    method_input: ProcessMethodInputV2,
    cell_state: CellStateEvidenceProfileV3,
    cell_state_path: Path,
) -> None:
    source = method_input.source_observations
    if (
        source.producer_run_ref != cell_state.producer_run_ref
        or source.producer_tool_id != cell_state.producer_tool_id
        or source.producer_tool_version != cell_state.producer_tool_version
    ):
        raise SourceObservationError("source_descriptor_producer_mismatch")
    if (
        manifest.get("run_id") != source.producer_run_ref
        or manifest.get("tool_id") != source.producer_tool_id
        or manifest.get("tool_version") != source.producer_tool_version
    ):
        raise SourceObservationError("source_manifest_producer_mismatch")
    if (
        manifest.get("reference_manifest_hash")
        != cell_state.reference_manifest_sha256
        or manifest.get("measurement_spec_sha256")
        != cell_state.measurement_spec_sha256
    ):
        raise SourceObservationError("source_manifest_profile_lineage_mismatch")

    profile_artifact = _manifest_artifact(
        manifest,
        artifact_id=f"artifact:{source.producer_run_ref}:profile-v3",
        kind="cell_state_profile_v3",
        reason_code="source_manifest_profile_binding_mismatch",
    )
    if (
        profile_artifact.get("media_type") != "application/json"
        or profile_artifact.get("sha256") != method_input.cell_state_profile_sha256
        or _canonical_path(
            profile_artifact.get("path"),
            reason_code="source_manifest_profile_binding_mismatch",
        )
        != cell_state_path.resolve()
    ):
        raise SourceObservationError("source_manifest_profile_binding_mismatch")

    if source.evidence_artifact_id != f"artifact:{source.producer_run_ref}:evidence":
        raise SourceObservationError("source_manifest_evidence_binding_mismatch")
    evidence_artifact = _manifest_artifact(
        manifest,
        artifact_id=source.evidence_artifact_id,
        kind="cell_state_evidence",
        reason_code="source_manifest_evidence_binding_mismatch",
    )
    if (
        evidence_artifact.get("media_type") != "application/vnd.apache.parquet"
        or evidence_artifact.get("sha256") != source.evidence_sha256
        or _canonical_path(
            evidence_artifact.get("path"),
            reason_code="source_manifest_evidence_binding_mismatch",
        )
        != source.evidence_path.resolve()
    ):
        raise SourceObservationError("source_manifest_evidence_binding_mismatch")


def _nullable_string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        if value:
            return value
        raise SourceObservationError("source_observation_semantics_unsupported")
    if pd.api.types.is_scalar(value) and bool(pd.isna(value)):
        return None
    raise SourceObservationError("source_observation_semantics_unsupported")


def _parse_prediction_set(value: object) -> list[str]:
    if not isinstance(value, str):
        raise SourceObservationError("source_prediction_set_invalid")
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError) as exc:
        raise SourceObservationError("source_prediction_set_invalid") from exc
    if (
        not isinstance(parsed, list)
        or any(not isinstance(item, str) or not item for item in parsed)
        or len(parsed) != len(set(parsed))
    ):
        raise SourceObservationError("source_prediction_set_invalid")
    return parsed


def _parse_row(row: Any) -> ProcessObservationStateV2:
    observation_id = row.observation_id
    if not isinstance(observation_id, str) or not observation_id:
        raise SourceObservationError("source_observation_id_invalid")
    predictions = _parse_prediction_set(row.prediction_set)
    consensus = _nullable_string(row.consensus_label)
    support = _nullable_string(row.support_state)
    assignment = _nullable_string(row.assignment_state)
    open_set = _nullable_string(row.open_set_state)
    if support == "consensus_supported":
        if not (
            len(predictions) == 1
            and consensus == predictions[0]
            and assignment == "shadow_candidate"
            and open_set == "not_assessed"
        ):
            raise SourceObservationError(
                "source_observation_semantics_unsupported"
            )
        state, state_id = "candidate", predictions[0]
    elif support == "single_source_supported":
        if not (
            len(predictions) == 1
            and consensus is None
            and assignment == "shadow_candidate"
            and open_set == "not_assessed"
        ):
            raise SourceObservationError(
                "source_observation_semantics_unsupported"
            )
        state, state_id = "candidate", predictions[0]
    elif support == "source_conflict":
        if not (
            len(predictions) >= 2
            and consensus is None
            and assignment == "shadow_candidate"
            and open_set == "not_assessed"
        ):
            raise SourceObservationError(
                "source_observation_semantics_unsupported"
            )
        state, state_id = "unresolved", None
    elif support == "unavailable":
        if not (
            not predictions
            and consensus is None
            and assignment == "unavailable"
            and open_set == "not_assessed"
        ):
            raise SourceObservationError(
                "source_observation_semantics_unsupported"
            )
        state, state_id = "unavailable", None
    else:
        raise SourceObservationError("source_observation_semantics_unsupported")
    try:
        return ProcessObservationStateV2(
            observation_id=observation_id,
            state=state,
            state_id=state_id,
            prediction_set=predictions,
            support_state=support,
            assignment_state=assignment,
            open_set_state=open_set,
        )
    except ValueError:
        raise SourceObservationError(
            "source_observation_semantics_unsupported"
        ) from None


def _profile_counts(
    cell_state: CellStateEvidenceProfileV3,
    view: str,
) -> dict[str, int]:
    return {
        item.label: item.count
        for item in cell_state.composition.records
        if item.label_level == "L1" and item.view.value == view
    }


def load_source_observations(
    *,
    method_input: ProcessMethodInputV2,
    cell_state: CellStateEvidenceProfileV3,
    cell_state_path: Path,
) -> LoadedSourceObservations:
    source = method_input.source_observations
    profile_bytes = _read_bound_bytes(
        cell_state_path,
        method_input.cell_state_profile_sha256,
        kind="profile",
    )
    try:
        persisted_profile = CellStateEvidenceProfileV3.model_validate_json(
            profile_bytes
        )
    except ValueError as exc:
        raise SourceObservationError("source_profile_invalid") from exc
    if persisted_profile != cell_state:
        raise SourceObservationError("source_profile_binding_mismatch")

    manifest_bytes = _read_bound_bytes(
        source.artifact_manifest_path,
        source.artifact_manifest_sha256,
        kind="artifact_manifest",
    )
    try:
        manifest = json.loads(manifest_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SourceObservationError("source_artifact_manifest_invalid") from exc
    if not isinstance(manifest, dict):
        raise SourceObservationError("source_artifact_manifest_invalid")
    _validate_manifest(
        manifest=manifest,
        method_input=method_input,
        cell_state=cell_state,
        cell_state_path=cell_state_path,
    )

    evidence_bytes = _read_bound_bytes(
        source.evidence_path,
        source.evidence_sha256,
        kind="evidence",
    )
    try:
        evidence = pd.read_parquet(io.BytesIO(evidence_bytes))
    except ImportError as exc:
        raise SourceObservationError(
            "source_evidence_runtime_unavailable"
        ) from exc
    except Exception as exc:
        raise SourceObservationError("source_evidence_invalid") from exc
    if not _REQUIRED_COLUMNS.issubset(evidence.columns):
        raise SourceObservationError("source_evidence_columns_unsupported")
    try:
        rows = tuple(_parse_row(row) for row in evidence.itertuples(index=False))
    except AttributeError as exc:
        raise SourceObservationError("source_evidence_columns_unsupported") from exc
    observation_ids = [row.observation_id for row in rows]
    if len(observation_ids) != len(set(observation_ids)):
        raise SourceObservationError("source_observation_ids_not_unique")
    if len(rows) != cell_state.input_data_view.n_observations:
        raise SourceObservationError("source_observation_set_mismatch")
    calculated_digest = observation_ids_sha256(observation_ids)
    if (
        calculated_digest != method_input.observation_ids_sha256
        or calculated_digest != cell_state.input_data_view.observation_ids_sha256
    ):
        raise SourceObservationError("source_observation_digest_mismatch")

    reconciliation_counts = dict(Counter(row.support_state for row in rows))
    if reconciliation_counts != _profile_counts(
        cell_state, "reconciliation_state"
    ):
        raise SourceObservationError(
            "source_observation_profile_reconciliation_mismatch"
        )
    consensus_counts = dict(
        Counter(
            row.state_id
            for row in rows
            if row.support_state == "consensus_supported"
            and row.state_id is not None
        )
    )
    if consensus_counts != _profile_counts(
        cell_state, "consensus_supported_only"
    ):
        raise SourceObservationError("source_observation_profile_consensus_mismatch")

    return LoadedSourceObservations(
        rows=rows,
        artifact_manifest_sha256=source.artifact_manifest_sha256,
        evidence_sha256=source.evidence_sha256,
    )


def source_observations_unchanged(method_input: ProcessMethodInputV2) -> bool:
    source = method_input.source_observations
    try:
        return (
            _hash_regular_file(
                source.artifact_manifest_path,
                kind="artifact_manifest",
            )
            == source.artifact_manifest_sha256
            and _hash_regular_file(source.evidence_path, kind="evidence")
            == source.evidence_sha256
        )
    except SourceObservationError:
        return False
