from __future__ import annotations

import math
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from bridge.toolkit.contracts import EvidenceState, FrozenModel


CELL_STATE_EVIDENCE_MATRIX_SCHEMA_REF = (
    "bridge://schemas/cell-state-evidence-matrix-data/v0.1"
)
class MatrixAssessmentState(StrEnum):
    SOURCE_ANCHORED = "source_anchored"
    SUPPORT = "support"
    OPPOSITION = "opposition"
    CONFLICT = "conflict"
    NOT_ASSESSED = "not_assessed"


class EvidenceRole(StrEnum):
    PRIMARY_ANNOTATION = "primary_annotation"
    DERIVED_CONTEXT = "derived_context"
    DEPENDENT_SPATIAL_CONCORDANCE = "dependent_spatial_concordance"
    LITERATURE_PRIOR = "literature_prior"
    EXTERNAL_HOLDOUT = "external_holdout"


class SourceRelationship(StrEnum):
    PRIMARY = "primary"
    DERIVED_CONTAINS_PRIMARY = "derived_contains_primary"
    DEPENDENT_LABEL_TRANSFER = "dependent_label_transfer"
    INDEPENDENT_EXTERNAL = "independent_external"


class SourceAvailability(StrEnum):
    AVAILABLE = "available"
    REVIEW_PENDING = "review_pending"
    HOLDOUT_NOT_RUN = "holdout_not_run"


class EvidenceChannel(StrEnum):
    ANNOTATION_OBSERVATION = "annotation_observation"
    MARKER_PROGRAM = "marker_program"
    REFERENCE_PREDICTION = "reference_prediction"
    SPATIAL_MARKER = "spatial_marker"
    EXTERNAL_HOLDOUT = "external_holdout"
    OOD_ASSESSMENT = "ood_assessment"


_ASSESSMENT_EVIDENCE_STATES = {
    MatrixAssessmentState.SOURCE_ANCHORED: {EvidenceState.MEASURED},
    MatrixAssessmentState.SUPPORT: {
        EvidenceState.MEASURED,
        EvidenceState.INFERRED,
    },
    MatrixAssessmentState.OPPOSITION: {EvidenceState.NEGATIVE},
    MatrixAssessmentState.CONFLICT: {
        EvidenceState.UNKNOWN,
        EvidenceState.ALERT,
    },
    MatrixAssessmentState.NOT_ASSESSED: {
        EvidenceState.PRIOR_ONLY,
        EvidenceState.MISSING,
        EvidenceState.UNKNOWN,
        EvidenceState.UNAVAILABLE,
    },
}


class CellStateEvidenceSource(FrozenModel):
    source_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    source_family_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    display_name: str = Field(min_length=1)
    short_name: str = Field(min_length=1, max_length=24)
    assay: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    relationship: SourceRelationship
    availability: SourceAvailability
    observation_unit: str = Field(min_length=1)
    n_observations: int | None = Field(default=None, ge=0)
    dependency_source_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(min_length=1)
    limitation: str = Field(min_length=1)

    @field_validator("dependency_source_ids", "evidence_ids")
    @classmethod
    def lists_are_unique_and_nonblank(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("source references must be non-empty")
        if len(values) != len(set(values)):
            raise ValueError("source references must be unique")
        return values

    @model_validator(mode="after")
    def source_relationship_is_coherent(self) -> Self:
        if self.source_id in self.dependency_source_ids:
            raise ValueError("a source cannot depend on itself")
        if self.relationship in {
            SourceRelationship.PRIMARY,
            SourceRelationship.INDEPENDENT_EXTERNAL,
        } and self.dependency_source_ids:
            raise ValueError("primary and independent sources cannot declare dependencies")
        if self.relationship in {
            SourceRelationship.DERIVED_CONTAINS_PRIMARY,
            SourceRelationship.DEPENDENT_LABEL_TRANSFER,
        } and not self.dependency_source_ids:
            raise ValueError("derived and dependent sources require a dependency")
        return self


class CellStateEvidenceRow(FrozenModel):
    state_id: str = Field(pattern=r"^L[12]:[A-Za-z0-9_]+$")
    display_name: str = Field(min_length=1)
    level: Literal["L1", "L2"]
    row_group: str = Field(min_length=1)
    order: int = Field(ge=0)
    primary_n_observations: int = Field(ge=0)
    review_state: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    review_notes: list[str] = Field(default_factory=list)

    @field_validator("evidence_ids", "review_notes")
    @classmethod
    def row_lists_are_unique_and_nonblank(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("row evidence and review notes must be non-empty")
        if len(values) != len(set(values)):
            raise ValueError("row evidence and review notes must be unique")
        return values

    @model_validator(mode="after")
    def level_matches_state_id(self) -> Self:
        if not self.state_id.startswith(f"{self.level}:"):
            raise ValueError("state ID prefix must match its declared level")
        return self


class CellStateEvidenceStatistic(FrozenModel):
    metric_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")
    value: float
    unit: str = Field(min_length=1)
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def fraction_is_coherent(self) -> Self:
        if not math.isfinite(self.value):
            raise ValueError("statistic value must be finite")
        if (self.numerator is None) != (self.denominator is None):
            raise ValueError("statistic numerator and denominator must be paired")
        if self.numerator is not None and self.numerator > self.denominator:
            raise ValueError("statistic numerator cannot exceed denominator")
        return self


class CellStateEvidenceChannelRecord(FrozenModel):
    channel: EvidenceChannel
    assessment_state: MatrixAssessmentState
    evidence_state: EvidenceState
    summary: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    reason_codes: list[str] = Field(default_factory=list)
    statistics: list[CellStateEvidenceStatistic] = Field(default_factory=list)

    @field_validator("evidence_ids", "reason_codes")
    @classmethod
    def channel_lists_are_unique_and_nonblank(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("channel evidence and reasons must be non-empty")
        if len(values) != len(set(values)):
            raise ValueError("channel evidence and reasons must be unique")
        return values

    @model_validator(mode="after")
    def channel_state_is_coherent(self) -> Self:
        if self.evidence_state not in _ASSESSMENT_EVIDENCE_STATES[
            self.assessment_state
        ]:
            raise ValueError("assessment and evidence states are inconsistent")
        if self.assessment_state in {
            MatrixAssessmentState.OPPOSITION,
            MatrixAssessmentState.CONFLICT,
            MatrixAssessmentState.NOT_ASSESSED,
        } and not self.reason_codes:
            raise ValueError("opposition, conflict and not-assessed channels require reasons")
        return self


class CellStateEvidenceMatrixRecord(FrozenModel):
    state_id: str = Field(pattern=r"^L[12]:[A-Za-z0-9_]+$")
    source_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    assessment_state: MatrixAssessmentState
    evidence_role: EvidenceRole
    evidence_state: EvidenceState
    summary: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    reason_codes: list[str] = Field(default_factory=list)
    channels: list[CellStateEvidenceChannelRecord] = Field(min_length=1)

    @field_validator("evidence_ids", "reason_codes")
    @classmethod
    def record_lists_are_unique_and_nonblank(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("record evidence and reasons must be non-empty")
        if len(values) != len(set(values)):
            raise ValueError("record evidence and reasons must be unique")
        return values

    @model_validator(mode="after")
    def record_state_is_coherent(self) -> Self:
        if self.evidence_state not in _ASSESSMENT_EVIDENCE_STATES[
            self.assessment_state
        ]:
            raise ValueError("assessment and evidence states are inconsistent")
        if self.evidence_role is EvidenceRole.PRIMARY_ANNOTATION:
            if self.assessment_state not in {
                MatrixAssessmentState.SOURCE_ANCHORED,
                MatrixAssessmentState.NOT_ASSESSED,
            }:
                raise ValueError(
                    "primary annotation records must be anchored or not assessed"
                )
        if self.evidence_role is EvidenceRole.LITERATURE_PRIOR and (
            self.assessment_state is not MatrixAssessmentState.NOT_ASSESSED
            or self.evidence_state is not EvidenceState.PRIOR_ONLY
        ):
            raise ValueError("literature priors cannot be promoted to source support")
        if (
            self.evidence_state is EvidenceState.PRIOR_ONLY
            and self.evidence_role is not EvidenceRole.LITERATURE_PRIOR
        ):
            raise ValueError("prior-only evidence requires the literature-prior role")
        if self.assessment_state in {
            MatrixAssessmentState.OPPOSITION,
            MatrixAssessmentState.CONFLICT,
            MatrixAssessmentState.NOT_ASSESSED,
        } and not self.reason_codes:
            raise ValueError(
                "opposition, conflict and not-assessed records require reasons"
            )
        channel_ids = [channel.channel for channel in self.channels]
        if len(channel_ids) != len(set(channel_ids)):
            raise ValueError("record channels must be unique")
        channel_has_prior = any(
            channel.evidence_state is EvidenceState.PRIOR_ONLY
            for channel in self.channels
        )
        if channel_has_prior != (
            self.evidence_role is EvidenceRole.LITERATURE_PRIOR
        ):
            raise ValueError(
                "prior-only channels require the literature-prior role"
            )
        metric_ids = [
            statistic.metric_id
            for channel in self.channels
            for statistic in channel.statistics
        ]
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("record statistic metric IDs must be unique")
        channel_states = {channel.assessment_state for channel in self.channels}
        if (
            MatrixAssessmentState.CONFLICT in channel_states
            or {
                MatrixAssessmentState.SUPPORT,
                MatrixAssessmentState.OPPOSITION,
            } <= channel_states
        ):
            expected_assessment = MatrixAssessmentState.CONFLICT
        elif (
            self.evidence_role is EvidenceRole.PRIMARY_ANNOTATION
            and MatrixAssessmentState.SOURCE_ANCHORED in channel_states
        ):
            if MatrixAssessmentState.OPPOSITION in channel_states:
                expected_assessment = MatrixAssessmentState.CONFLICT
            else:
                expected_assessment = MatrixAssessmentState.SOURCE_ANCHORED
        else:
            assessed = channel_states - {MatrixAssessmentState.NOT_ASSESSED}
            if len(assessed) > 1:
                raise ValueError("channel roll-up is ambiguous")
            expected_assessment = (
                next(iter(assessed))
                if assessed
                else MatrixAssessmentState.NOT_ASSESSED
            )
        if self.assessment_state is not expected_assessment:
            raise ValueError("record assessment must equal the channel roll-up")
        matching = [
            channel
            for channel in self.channels
            if channel.assessment_state is self.assessment_state
        ]
        if self.assessment_state is MatrixAssessmentState.CONFLICT:
            if not matching and not {
                MatrixAssessmentState.SUPPORT,
                MatrixAssessmentState.OPPOSITION,
            } <= channel_states:
                raise ValueError(
                    "conflict requires a conflict channel or support and opposition channels"
                )
        elif not matching:
            raise ValueError("record assessment must be represented by a channel")
        if matching and self.evidence_state not in {
            channel.evidence_state for channel in matching
        }:
            raise ValueError("record evidence state must be represented by a channel")
        return self


class CellStateEvidenceMatrixData(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal["bridge://schemas/cell-state-evidence-matrix-data/v0.1"] = CELL_STATE_EVIDENCE_MATRIX_SCHEMA_REF
    profile_id: str = Field(pattern=r"^cell-state-evidence-matrix:[A-Za-z0-9._-]+$")
    producer_run_ref: str = Field(pattern=r"^run:[A-Za-z0-9._:-]+$")
    primary_source_id: str
    scientific_status: Literal["candidate"] = "candidate"
    review_state: str = Field(min_length=1)
    denominator: int = Field(gt=0)
    denominator_unit: Literal["state cards"] = "state cards"
    sources: list[CellStateEvidenceSource] = Field(min_length=2)
    states: list[CellStateEvidenceRow] = Field(min_length=1)
    records: list[CellStateEvidenceMatrixRecord] = Field(min_length=2)
    evidence_ids: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    alt_text: str = Field(min_length=40)
    long_description: str = Field(min_length=80)

    @model_validator(mode="after")
    def matrix_is_complete_and_source_aware(self) -> Self:
        source_ids = [source.source_id for source in self.sources]
        state_ids = [state.state_id for state in self.states]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("matrix source IDs must be unique")
        if len(state_ids) != len(set(state_ids)):
            raise ValueError("matrix state IDs must be unique")
        if len({state.order for state in self.states}) != len(self.states):
            raise ValueError("matrix state order must be unique")
        if [state.order for state in self.states] != sorted(
            state.order for state in self.states
        ):
            raise ValueError("matrix states must be listed in state order")

        source_by_id = {source.source_id: source for source in self.sources}
        state_by_id = {state.state_id: state for state in self.states}
        if self.primary_source_id not in source_by_id:
            raise ValueError("primary source must be present")
        primary_sources = [
            source.source_id
            for source in self.sources
            if source.relationship is SourceRelationship.PRIMARY
        ]
        if primary_sources != [self.primary_source_id]:
            raise ValueError("matrix must declare exactly one primary source")
        primary = source_by_id[self.primary_source_id]
        for source in self.sources:
            if not set(source.dependency_source_ids) <= set(source_ids):
                raise ValueError("source dependency must reference a declared source")
            if (
                source.relationship is SourceRelationship.INDEPENDENT_EXTERNAL
                and source.source_family_id == primary.source_family_id
            ):
                raise ValueError(
                    "independent sources cannot share the primary source family"
                )

        colors: dict[str, int] = {}

        def assert_acyclic(source_id: str) -> None:
            state = colors.get(source_id, 0)
            if state == 1:
                raise ValueError("source dependencies must be acyclic")
            if state == 2:
                return
            colors[source_id] = 1
            for dependency_id in source_by_id[source_id].dependency_source_ids:
                assert_acyclic(dependency_id)
            colors[source_id] = 2

        for source_id in source_ids:
            assert_acyclic(source_id)

        reachability: dict[str, bool] = {}

        def traces_to_primary(source_id: str) -> bool:
            if source_id == self.primary_source_id:
                return True
            if source_id in reachability:
                return reachability[source_id]
            source = source_by_id[source_id]
            reachable = (
                False
                if source.relationship is SourceRelationship.INDEPENDENT_EXTERNAL
                else any(
                    traces_to_primary(dependency_id)
                    for dependency_id in source.dependency_source_ids
                )
            )
            reachability[source_id] = reachable
            return reachable

        for source in self.sources:
            if source.relationship in {
                SourceRelationship.DERIVED_CONTAINS_PRIMARY,
                SourceRelationship.DEPENDENT_LABEL_TRANSFER,
            } and not traces_to_primary(source.source_id):
                raise ValueError(
                    "derived and dependent sources must trace to the primary source"
                )
        primary_dependent_families = {
            source.source_family_id
            for source in self.sources
            if traces_to_primary(source.source_id)
        }
        if any(
            source.relationship is SourceRelationship.INDEPENDENT_EXTERNAL
            and source.source_family_id in primary_dependent_families
            for source in self.sources
        ):
            raise ValueError(
                "independent sources cannot share a primary-dependent source family"
            )

        expected = {
            (state_id, source_id)
            for state_id in state_ids
            for source_id in source_ids
        }
        observed = {(record.state_id, record.source_id) for record in self.records}
        if len(observed) != len(self.records):
            raise ValueError("matrix state-source records must be unique")
        if observed != expected:
            raise ValueError("matrix must contain exactly one record per state and source")
        for record in self.records:
            source = source_by_id[record.source_id]
            state = state_by_id[record.state_id]
            if (
                state.primary_n_observations > 0
                and primary.n_observations is not None
                and state.primary_n_observations > primary.n_observations
            ):
                raise ValueError(
                    "state observation count cannot exceed the primary source count"
                )
            if record.source_id == self.primary_source_id:
                if record.evidence_role is not EvidenceRole.PRIMARY_ANNOTATION:
                    raise ValueError("primary-source records require the primary role")
                if (
                    state.primary_n_observations > 0
                    and record.assessment_state
                    is not MatrixAssessmentState.SOURCE_ANCHORED
                ) or (
                    state.primary_n_observations == 0
                    and record.assessment_state
                    is MatrixAssessmentState.SOURCE_ANCHORED
                ):
                    raise ValueError(
                        "primary observation counts and anchored states must agree"
                    )
            elif record.evidence_role is EvidenceRole.PRIMARY_ANNOTATION:
                raise ValueError("only the primary source can use the primary role")
            if (
                source.relationship is SourceRelationship.INDEPENDENT_EXTERNAL
                and record.evidence_role
                not in {
                    EvidenceRole.EXTERNAL_HOLDOUT,
                    EvidenceRole.LITERATURE_PRIOR,
                }
            ):
                raise ValueError(
                    "independent source records require external-holdout or prior roles"
                )
            if (
                record.evidence_role is EvidenceRole.DEPENDENT_SPATIAL_CONCORDANCE
                and source.relationship
                is not SourceRelationship.DEPENDENT_LABEL_TRANSFER
            ):
                raise ValueError(
                    "dependent spatial evidence requires a dependent source"
                )
            if (
                record.evidence_role is EvidenceRole.EXTERNAL_HOLDOUT
                and source.relationship
                is not SourceRelationship.INDEPENDENT_EXTERNAL
            ):
                raise ValueError(
                    "external holdout evidence requires an independent source"
                )
            if (
                source.availability is SourceAvailability.HOLDOUT_NOT_RUN
                and record.assessment_state
                is not MatrixAssessmentState.NOT_ASSESSED
            ):
                raise ValueError("unrun holdout sources cannot report an assessment")
            if (
                record.assessment_state is MatrixAssessmentState.SOURCE_ANCHORED
                and record.source_id != self.primary_source_id
            ):
                raise ValueError("only the primary source can be source anchored")

        if self.denominator != len(self.states):
            raise ValueError("matrix denominator must equal the number of state cards")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("profile evidence IDs must be unique")
        return self


PUBLIC_SCHEMA_MODELS = {
    CELL_STATE_EVIDENCE_MATRIX_SCHEMA_REF: CellStateEvidenceMatrixData,
}
