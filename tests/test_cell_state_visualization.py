from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from bridge.tool_packages.p0_02_cell_state.visualization import (
    render_source_state_evidence_matrix,
    write_source_state_evidence_table,
)
from bridge.tool_packages.p0_02_cell_state.visualization_data import (
    CELL_STATE_EVIDENCE_MATRIX_SCHEMA_REF,
    CellStateEvidenceChannelRecord,
    CellStateEvidenceMatrixData,
    CellStateEvidenceMatrixRecord,
    CellStateEvidenceRow,
    CellStateEvidenceSource,
    EvidenceChannel,
    EvidenceRole,
    MatrixAssessmentState,
    SourceAvailability,
    SourceRelationship,
)
from bridge.toolkit.contracts import EvidenceState
from bridge.toolkit.schemas import load_schema

def _channel(
    channel: EvidenceChannel,
    assessment: MatrixAssessmentState,
    evidence: EvidenceState,
    *,
    reasons: list[str] | None = None,
) -> CellStateEvidenceChannelRecord:
    return CellStateEvidenceChannelRecord(
        channel=channel,
        assessment_state=assessment,
        evidence_state=evidence,
        summary=f"Synthetic {channel.value} record.",
        evidence_ids=[f"EVIDENCE-{channel.value.upper()}"],
        reason_codes=reasons or [],
    )


def _record(
    state_id: str,
    source_id: str,
    assessment: MatrixAssessmentState,
    role: EvidenceRole,
    evidence: EvidenceState,
    channel: EvidenceChannel,
    *,
    reasons: list[str] | None = None,
) -> CellStateEvidenceMatrixRecord:
    return CellStateEvidenceMatrixRecord(
        state_id=state_id,
        source_id=source_id,
        assessment_state=assessment,
        evidence_role=role,
        evidence_state=evidence,
        summary="Synthetic matrix evidence for contract validation.",
        evidence_ids=[f"EVIDENCE-{state_id.split(':')[-1]}-{source_id}"],
        reason_codes=reasons or [],
        channels=[
            _channel(
                channel,
                assessment,
                evidence,
                reasons=reasons,
            )
        ],
    )


def _profile() -> CellStateEvidenceMatrixData:
    primary = "REF-PRIMARY"
    external = "REF-EXTERNAL"
    sources = [
        CellStateEvidenceSource(
            source_id=primary,
            source_family_id="FAMILY-PRIMARY",
            display_name="Primary scRNA reference",
            short_name="Primary scRNA",
            assay="scRNA-seq",
            scope="Current primary annotation",
            relationship=SourceRelationship.PRIMARY,
            availability=SourceAvailability.AVAILABLE,
            observation_unit="cells",
            n_observations=100,
            evidence_ids=["EVIDENCE-SOURCE-PRIMARY"],
            limitation="The source defines the current labels and is not independent validation.",
        ),
        CellStateEvidenceSource(
            source_id=external,
            source_family_id="FAMILY-EXTERNAL",
            display_name="Independent external source",
            short_name="External",
            assay="scRNA-seq",
            scope="Held-out source",
            relationship=SourceRelationship.INDEPENDENT_EXTERNAL,
            availability=SourceAvailability.HOLDOUT_NOT_RUN,
            observation_unit="cells",
            n_observations=50,
            evidence_ids=["EVIDENCE-SOURCE-EXTERNAL"],
            limitation="The registered held-out analysis has not been run.",
        ),
    ]
    states = [
        CellStateEvidenceRow(
            state_id="L1:State_A",
            display_name="State A",
            level="L1",
            row_group="L1 neural",
            order=0,
            primary_n_observations=60,
            review_state="pending",
            evidence_ids=["EVIDENCE-STATE-A"],
        ),
        CellStateEvidenceRow(
            state_id="L1:State_B",
            display_name="State B",
            level="L1",
            row_group="L1 neural",
            order=1,
            primary_n_observations=0,
            review_state="pending",
            evidence_ids=["EVIDENCE-STATE-B"],
        ),
    ]
    records = [
        _record(
            "L1:State_A",
            primary,
            MatrixAssessmentState.SOURCE_ANCHORED,
            EvidenceRole.PRIMARY_ANNOTATION,
            EvidenceState.MEASURED,
            EvidenceChannel.ANNOTATION_OBSERVATION,
        ),
        _record(
            "L1:State_B",
            primary,
            MatrixAssessmentState.NOT_ASSESSED,
            EvidenceRole.PRIMARY_ANNOTATION,
            EvidenceState.UNAVAILABLE,
            EvidenceChannel.ANNOTATION_OBSERVATION,
            reasons=["no_primary_observations"],
        ),
        _record(
            "L1:State_A",
            external,
            MatrixAssessmentState.NOT_ASSESSED,
            EvidenceRole.LITERATURE_PRIOR,
            EvidenceState.PRIOR_ONLY,
            EvidenceChannel.MARKER_PROGRAM,
            reasons=["literature_prior_only"],
        ),
        _record(
            "L1:State_B",
            external,
            MatrixAssessmentState.NOT_ASSESSED,
            EvidenceRole.EXTERNAL_HOLDOUT,
            EvidenceState.UNAVAILABLE,
            EvidenceChannel.EXTERNAL_HOLDOUT,
            reasons=["heldout_runner_not_executed"],
        ),
    ]
    return CellStateEvidenceMatrixData(
        profile_id="cell-state-evidence-matrix:synthetic",
        producer_run_ref="run:synthetic",
        primary_source_id=primary,
        review_state="candidate_review",
        denominator=2,
        sources=sources,
        states=states,
        records=records,
        evidence_ids=["EVIDENCE-MATRIX-SYNTHETIC"],
        limitations=["Synthetic contract fixture; no biological interpretation is permitted."],
        alt_text=(
            "A two-state by two-source matrix distinguishes a primary annotation "
            "from an unrun independent external source."
        ),
        long_description=(
            "State A is present in the synthetic primary annotation and carries "
            "literature prior only in the external source. State B has no primary "
            "observations, and the external held-out analysis is not assessed."
        ),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _single(frame: pd.DataFrame, column: str):
    values = frame[column].drop_duplicates()
    assert len(values) == 1
    return values.iloc[0]


def _profile_from_table(frame: pd.DataFrame) -> CellStateEvidenceMatrixData:
    first = frame.iloc[0]
    sources = []
    for source_order in sorted(frame["source_order"].unique()):
        row = frame.loc[frame["source_order"] == source_order].iloc[0]
        n_observations = row["source_n_observations"]
        sources.append(
            {
                "source_id": row["source_id"],
                "source_family_id": row["source_family_id"],
                "display_name": row["source_display_name"],
                "short_name": row["source_short_name"],
                "assay": row["source_assay"],
                "scope": row["source_scope"],
                "relationship": row["source_relationship"],
                "availability": row["source_availability"],
                "observation_unit": row["source_observation_unit"],
                "n_observations": (
                    None if pd.isna(n_observations) else int(n_observations)
                ),
                "dependency_source_ids": json.loads(
                    row["source_dependency_ids_json"]
                ),
                "evidence_ids": json.loads(row["source_evidence_ids_json"]),
                "limitation": row["source_limitation"],
            }
        )
    states = []
    for state_order in sorted(frame["state_order"].unique()):
        row = frame.loc[frame["state_order"] == state_order].iloc[0]
        states.append(
            {
                "state_id": row["state_id"],
                "display_name": row["state_display_name"],
                "level": row["state_level"],
                "row_group": row["state_row_group"],
                "order": int(row["state_order"]),
                "primary_n_observations": int(
                    row["state_primary_n_observations"]
                ),
                "review_state": row["state_review_state"],
                "evidence_ids": json.loads(row["state_evidence_ids_json"]),
                "review_notes": json.loads(row["state_review_notes_json"]),
            }
        )
    records = []
    for _, row in frame.sort_values("record_order").iterrows():
        records.append(
            {
                "state_id": row["state_id"],
                "source_id": row["source_id"],
                "assessment_state": row["assessment_state"],
                "evidence_role": row["evidence_role"],
                "evidence_state": row["evidence_state"],
                "summary": row["summary"],
                "evidence_ids": json.loads(row["record_evidence_ids_json"]),
                "reason_codes": json.loads(row["reason_codes_json"]),
                "channels": json.loads(row["channels_json"]),
            }
        )
    payload = {
        "object_version": _single(frame, "object_version"),
        "schema_ref": _single(frame, "schema_ref"),
        "profile_id": _single(frame, "profile_id"),
        "producer_run_ref": _single(frame, "producer_run_ref"),
        "primary_source_id": _single(frame, "primary_source_id"),
        "scientific_status": _single(frame, "profile_scientific_status"),
        "review_state": _single(frame, "profile_review_state"),
        "denominator": int(_single(frame, "profile_denominator")),
        "denominator_unit": _single(frame, "profile_denominator_unit"),
        "sources": sources,
        "states": states,
        "records": records,
        "evidence_ids": json.loads(_single(frame, "profile_evidence_ids_json")),
        "limitations": json.loads(_single(frame, "profile_limitations_json")),
        "alt_text": _single(frame, "profile_alt_text"),
        "long_description": _single(frame, "profile_long_description"),
    }
    return CellStateEvidenceMatrixData.model_validate(payload)


def test_cell_state_evidence_matrix_schema_matches_model() -> None:
    profile = _profile()
    schema = CellStateEvidenceMatrixData.model_json_schema()
    schema["$id"] = CELL_STATE_EVIDENCE_MATRIX_SCHEMA_REF
    assert load_schema(CELL_STATE_EVIDENCE_MATRIX_SCHEMA_REF) == schema
    assert not list(
        Draft202012Validator(schema).iter_errors(
            profile.model_dump(mode="json")
        )
    )


def test_matrix_requires_exactly_one_record_per_state_and_source() -> None:
    payload = _profile().model_dump(mode="json")
    payload["records"].pop()
    with pytest.raises(ValidationError, match="exactly one record"):
        CellStateEvidenceMatrixData.model_validate(payload)


def test_matrix_states_must_follow_declared_order() -> None:
    payload = _profile().model_dump(mode="json")
    payload["states"].reverse()
    with pytest.raises(ValidationError, match="listed in state order"):
        CellStateEvidenceMatrixData.model_validate(payload)


def test_literature_prior_cannot_be_promoted_to_support() -> None:
    payload = _profile().model_dump(mode="json")
    record = payload["records"][2]
    record["assessment_state"] = "support"
    record["evidence_state"] = "inferred"
    with pytest.raises(ValidationError, match="literature priors"):
        CellStateEvidenceMatrixData.model_validate(payload)


def test_prior_only_requires_literature_prior_role() -> None:
    payload = _profile().model_dump(mode="json")
    payload["records"][2]["evidence_role"] = "external_holdout"
    with pytest.raises(ValidationError, match="prior-only evidence"):
        CellStateEvidenceMatrixData.model_validate(payload)


def test_prior_only_channel_requires_literature_prior_role() -> None:
    payload = _profile().model_dump(mode="json")
    record = payload["records"][3]
    record["channels"].append(payload["records"][2]["channels"][0])
    with pytest.raises(ValidationError, match="prior-only channels"):
        CellStateEvidenceMatrixData.model_validate(payload)


def test_independent_source_cannot_share_primary_family() -> None:
    payload = _profile().model_dump(mode="json")
    payload["sources"][1]["source_family_id"] = "FAMILY-PRIMARY"
    with pytest.raises(ValidationError, match="share the primary source family"):
        CellStateEvidenceMatrixData.model_validate(payload)


def test_independent_source_cannot_share_a_primary_derived_family() -> None:
    payload = _profile().model_dump(mode="json")
    payload["sources"][1]["source_family_id"] = "FAMILY-DERIVED"
    payload["sources"].append(
        {
            "source_id": "REF-DERIVED",
            "source_family_id": "FAMILY-DERIVED",
            "display_name": "Primary-derived context",
            "short_name": "Derived",
            "assay": "scRNA-seq",
            "scope": "Derived source",
            "relationship": "derived_contains_primary",
            "availability": "review_pending",
            "observation_unit": "cells",
            "n_observations": 20,
            "dependency_source_ids": ["REF-PRIMARY"],
            "evidence_ids": ["EVIDENCE-SOURCE-DERIVED"],
            "limitation": "This source contains primary evidence.",
        }
    )
    for state in payload["states"]:
        payload["records"].append(
            _record(
                state["state_id"],
                "REF-DERIVED",
                MatrixAssessmentState.NOT_ASSESSED,
                EvidenceRole.DERIVED_CONTEXT,
                EvidenceState.UNAVAILABLE,
                EvidenceChannel.MARKER_PROGRAM,
                reasons=["derived_context_not_assessed"],
            ).model_dump(mode="json")
        )
    with pytest.raises(ValidationError, match="primary-dependent source family"):
        CellStateEvidenceMatrixData.model_validate(payload)


def test_source_dependency_cycles_are_rejected_independent_of_order() -> None:
    payload = _profile().model_dump(mode="json")
    for source_id, family_id, dependencies in (
        ("REF-DERIVED-A", "FAMILY-A", ["REF-PRIMARY", "REF-DERIVED-B"]),
        ("REF-DERIVED-B", "FAMILY-B", ["REF-DERIVED-A"]),
    ):
        payload["sources"].append(
            {
                "source_id": source_id,
                "source_family_id": family_id,
                "display_name": source_id,
                "short_name": source_id,
                "assay": "scRNA-seq",
                "scope": "Cycle test",
                "relationship": "derived_contains_primary",
                "availability": "review_pending",
                "observation_unit": "cells",
                "n_observations": 10,
                "dependency_source_ids": dependencies,
                "evidence_ids": [f"EVIDENCE-{source_id}"],
                "limitation": "Synthetic cycle test source.",
            }
        )
        for state in payload["states"]:
            payload["records"].append(
                _record(
                    state["state_id"],
                    source_id,
                    MatrixAssessmentState.NOT_ASSESSED,
                    EvidenceRole.DERIVED_CONTEXT,
                    EvidenceState.UNAVAILABLE,
                    EvidenceChannel.MARKER_PROGRAM,
                    reasons=["cycle_test_not_assessed"],
                ).model_dump(mode="json")
            )
    with pytest.raises(ValidationError, match="acyclic"):
        CellStateEvidenceMatrixData.model_validate(payload)


def test_channel_rollup_cannot_hide_opposition_as_primary_support() -> None:
    payload = _profile().model_dump(mode="json")
    payload["records"][0]["channels"].append(
        _channel(
            EvidenceChannel.MARKER_PROGRAM,
            MatrixAssessmentState.OPPOSITION,
            EvidenceState.NEGATIVE,
            reasons=["synthetic_opposition"],
        ).model_dump(mode="json")
    )
    with pytest.raises(ValidationError, match="channel roll-up"):
        CellStateEvidenceMatrixData.model_validate(payload)


def test_unrun_holdout_cannot_report_support() -> None:
    payload = _profile().model_dump(mode="json")
    record = payload["records"][2]
    record.update(
        assessment_state="support",
        evidence_role="external_holdout",
        evidence_state="inferred",
        reason_codes=[],
    )
    record["channels"][0].update(
        assessment_state="support",
        evidence_state="inferred",
        reason_codes=[],
    )
    with pytest.raises(ValidationError, match="unrun holdout"):
        CellStateEvidenceMatrixData.model_validate(payload)


def test_primary_counts_must_match_anchored_state() -> None:
    payload = _profile().model_dump(mode="json")
    payload["states"][0]["primary_n_observations"] = 0
    with pytest.raises(ValidationError, match="counts and anchored states"):
        CellStateEvidenceMatrixData.model_validate(payload)


def test_available_external_assessment_controls_figure_text(
    tmp_path: Path,
) -> None:
    payload = _profile().model_dump(mode="json")
    payload["sources"][1]["availability"] = "available"
    record = payload["records"][2]
    record.update(
        assessment_state="conflict",
        evidence_role="external_holdout",
        evidence_state="alert",
        reason_codes=["support_opposition_conflict"],
        channels=[
            _channel(
                EvidenceChannel.MARKER_PROGRAM,
                MatrixAssessmentState.SUPPORT,
                EvidenceState.INFERRED,
            ).model_dump(mode="json"),
            _channel(
                EvidenceChannel.EXTERNAL_HOLDOUT,
                MatrixAssessmentState.OPPOSITION,
                EvidenceState.NEGATIVE,
                reasons=["synthetic_opposition"],
            ).model_dump(mode="json"),
        ],
    )
    profile = CellStateEvidenceMatrixData.model_validate(payload)
    svg, _, _ = render_source_state_evidence_matrix(profile, tmp_path / "matrix")
    text = svg.read_text()
    assert "Independent assessment is recorded for 1/2 states" in text
    assert "No independent held-out state assessment" not in text
    assert "absence of conflict cannot be inferred" not in text


def test_matrix_render_and_table_are_deterministic(tmp_path: Path) -> None:
    profile = _profile()
    hashes = []
    for name in ("first", "second"):
        root = tmp_path / name
        root.mkdir()
        outputs = render_source_state_evidence_matrix(profile, root / "matrix")
        table = write_source_state_evidence_table(profile, root / "matrix.tsv")
        hashes.append([_sha256(path) for path in (*outputs, table)])
    assert hashes[0] == hashes[1]
    table = pd.read_csv(tmp_path / "first" / "matrix.tsv", sep="\t")
    assert len(table) == 4
    assert set(table["assessment_state"]) == {"source_anchored", "not_assessed"}
    assert {
        "object_version",
        "schema_ref",
        "profile_id",
        "producer_run_ref",
        "primary_source_id",
        "profile_denominator",
        "profile_denominator_unit",
        "profile_alt_text",
        "profile_long_description",
        "source_order",
        "source_short_name",
        "source_n_observations",
        "source_observation_unit",
        "source_dependency_ids_json",
        "state_order",
        "state_review_state",
        "state_evidence_ids_json",
        "reason_codes_json",
        "channels_json",
        "profile_scientific_status",
        "profile_limitations_json",
    } <= set(table)
    channels = json.loads(table.loc[0, "channels_json"])
    assert channels[0]["evidence_state"] == "measured"
    assert channels[0]["evidence_ids"]
    assert "statistics" in channels[0]
    assert _profile_from_table(table) == profile


def test_matrix_legend_covers_every_visual_state(tmp_path: Path) -> None:
    svg, _, _ = render_source_state_evidence_matrix(
        _profile(), tmp_path / "matrix"
    )
    text = svg.read_text()
    for label in (
        "Support · measured",
        "Support · inferred",
        "Conflict · alert",
        "Conflict · unknown",
        "Not assessed · missing",
        "Not assessed · unknown",
        "Not assessed · unavailable",
    ):
        assert label in text
