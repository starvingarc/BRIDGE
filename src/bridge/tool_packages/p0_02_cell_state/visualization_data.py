from __future__ import annotations

import math
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from bridge.tool_packages.p0_02_cell_state.hierarchical_composition import (
    ProductGroupingProvenance,
)
from bridge.toolkit.contracts import EvidenceState, FrozenModel
from bridge.toolkit.visualization import VisualizationArtifactV2


CELL_STATE_EVIDENCE_MATRIX_SCHEMA_REF = (
    "bridge://schemas/cell-state-evidence-matrix-data/v0.1"
)
CELL_STATE_EVIDENCE_MATRIX_V2_SCHEMA_REF = (
    "bridge://schemas/cell-state-evidence-matrix-data/v0.2"
)
HIERARCHICAL_CELL_STATE_VISUALIZATION_SCHEMA_REF = (
    "bridge://schemas/hierarchical-cell-state-visualization-data/v0.1"
)
P002_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF = (
    "bridge://schemas/p0-02-visualization-artifact-set/v0.1"
)
HIERARCHICAL_COMPOSITION_COMPONENT_REF = (
    "bridge.cell_state.hierarchical-composition@0.1.0"
)
SOURCE_STATE_EVIDENCE_COMPONENT_REF = "bridge.cell_state.source-state-evidence@0.1.0"
P002_COMPONENT_BINDINGS = (
    (
        HIERARCHICAL_COMPOSITION_COMPONENT_REF,
        "hierarchical-composition",
        HIERARCHICAL_CELL_STATE_VISUALIZATION_SCHEMA_REF,
        "records",
        "hierarchical-visualization",
    ),
    (
        SOURCE_STATE_EVIDENCE_COMPONENT_REF,
        "source-state-evidence",
        CELL_STATE_EVIDENCE_MATRIX_V2_SCHEMA_REF,
        "records",
        "source-state-evidence",
    ),
)
P002_COMPONENT_REFS = tuple(item[0] for item in P002_COMPONENT_BINDINGS)

_SHA256 = r"^[0-9a-f]{64}$"


def _artifact_id(digest: str, suffix: str) -> str:
    return f"artifact:run-{digest}:{suffix}"


def _visualization_id(digest: str, slug: str) -> str:
    return f"visualization:run-{digest}:{slug}"


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
        if (
            self.relationship
            in {
                SourceRelationship.PRIMARY,
                SourceRelationship.INDEPENDENT_EXTERNAL,
            }
            and self.dependency_source_ids
        ):
            raise ValueError(
                "primary and independent sources cannot declare dependencies"
            )
        if (
            self.relationship
            in {
                SourceRelationship.DERIVED_CONTAINS_PRIMARY,
                SourceRelationship.DEPENDENT_LABEL_TRANSFER,
            }
            and not self.dependency_source_ids
        ):
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
        if (
            self.evidence_state
            not in _ASSESSMENT_EVIDENCE_STATES[self.assessment_state]
        ):
            raise ValueError("assessment and evidence states are inconsistent")
        if (
            self.assessment_state
            in {
                MatrixAssessmentState.OPPOSITION,
                MatrixAssessmentState.CONFLICT,
                MatrixAssessmentState.NOT_ASSESSED,
            }
            and not self.reason_codes
        ):
            raise ValueError(
                "opposition, conflict and not-assessed channels require reasons"
            )
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
        if (
            self.evidence_state
            not in _ASSESSMENT_EVIDENCE_STATES[self.assessment_state]
        ):
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
        if (
            self.assessment_state
            in {
                MatrixAssessmentState.OPPOSITION,
                MatrixAssessmentState.CONFLICT,
                MatrixAssessmentState.NOT_ASSESSED,
            }
            and not self.reason_codes
        ):
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
        if channel_has_prior != (self.evidence_role is EvidenceRole.LITERATURE_PRIOR):
            raise ValueError("prior-only channels require the literature-prior role")
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
            }
            <= channel_states
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
                next(iter(assessed)) if assessed else MatrixAssessmentState.NOT_ASSESSED
            )
        if self.assessment_state is not expected_assessment:
            raise ValueError("record assessment must equal the channel roll-up")
        matching = [
            channel
            for channel in self.channels
            if channel.assessment_state is self.assessment_state
        ]
        if self.assessment_state is MatrixAssessmentState.CONFLICT:
            if (
                not matching
                and not {
                    MatrixAssessmentState.SUPPORT,
                    MatrixAssessmentState.OPPOSITION,
                }
                <= channel_states
            ):
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
    schema_ref: Literal["bridge://schemas/cell-state-evidence-matrix-data/v0.1"] = (
        CELL_STATE_EVIDENCE_MATRIX_SCHEMA_REF
    )
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
            (state_id, source_id) for state_id in state_ids for source_id in source_ids
        }
        observed = {(record.state_id, record.source_id) for record in self.records}
        if len(observed) != len(self.records):
            raise ValueError("matrix state-source records must be unique")
        if observed != expected:
            raise ValueError(
                "matrix must contain exactly one record per state and source"
            )
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
                    and record.assessment_state is MatrixAssessmentState.SOURCE_ANCHORED
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
                and source.relationship is not SourceRelationship.INDEPENDENT_EXTERNAL
            ):
                raise ValueError(
                    "external holdout evidence requires an independent source"
                )
            if (
                source.availability is SourceAvailability.HOLDOUT_NOT_RUN
                and record.assessment_state is not MatrixAssessmentState.NOT_ASSESSED
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


class CellStateEvidenceMatrixRecordV2(CellStateEvidenceMatrixRecord):
    record_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    scientific_status: Literal["candidate"] = "candidate"
    applicability: Literal["applicable", "not_assessed"]
    missingness: Literal["available", "missing", "unavailable"]

    @model_validator(mode="after")
    def presentation_axes_are_coherent(self) -> Self:
        assessed = self.assessment_state is not MatrixAssessmentState.NOT_ASSESSED
        if assessed != (self.applicability == "applicable"):
            raise ValueError("assessment and applicability must agree")
        expected_missingness = {
            EvidenceState.MISSING: "missing",
            EvidenceState.UNAVAILABLE: "unavailable",
        }.get(self.evidence_state, "available")
        if self.missingness != expected_missingness:
            raise ValueError("evidence state and missingness must agree")
        return self


class CellStateEvidenceMatrixDataV2(CellStateEvidenceMatrixData):
    object_version: Literal["0.2.0"] = "0.2.0"
    schema_ref: Literal["bridge://schemas/cell-state-evidence-matrix-data/v0.2"] = (
        CELL_STATE_EVIDENCE_MATRIX_V2_SCHEMA_REF
    )
    records: list[CellStateEvidenceMatrixRecordV2] = Field(min_length=2)
    matrix_scope: Literal["draft_state_definition_registry"] = (
        "draft_state_definition_registry"
    )
    query_dependent: Literal[False] = False
    runtime_reference_selection_represented: Literal[False] = False
    primary_source_semantics: Literal["current_state_label_count_source"] = (
        "current_state_label_count_source"
    )
    source_registry_ref: str = Field(min_length=1)
    source_registry_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def presentation_record_ids_are_unique(self) -> Self:
        record_ids = [record.record_id for record in self.records]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("matrix record IDs must be unique")
        digest = self.profile_id.rsplit(":", 1)[1]
        if self.producer_run_ref != f"run:run-{digest}":
            raise ValueError("matrix profile and producer run must share a digest")
        return self


class HierarchicalCellStateVisualizationRecord(FrozenModel):
    record_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    row_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    row_display_name: str = Field(min_length=1)
    row_order: int = Field(ge=0)
    row_count: int = Field(gt=0)
    row_whole_product_fraction: float = Field(gt=0, le=1)
    column_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    column_display_name: str = Field(min_length=1)
    column_order: int = Field(ge=0)
    column_kind: Literal[
        "group_share",
        "state",
        "subtype_unresolved",
        "subtype_unavailable",
        "source_conflict",
        "unavailable",
        "open_set_not_assessed",
    ]
    state_id: str | None = Field(default=None, pattern=r"^L[12]:[A-Za-z0-9_]+$")
    reference_level: Literal["L1", "L2", "status"]
    parent_state_id: str | None = Field(
        default=None,
        pattern=r"^L1:[A-Za-z0-9_]+$",
    )
    parent_denominator: int | None = Field(default=None, ge=0)
    parent_denominator_scope: str | None = None
    parent_fraction: float | None = Field(default=None, ge=0, le=1)
    count: int | None = Field(default=None, ge=0)
    denominator: int = Field(gt=0)
    denominator_scope: str = Field(min_length=1)
    fraction: float | None = Field(default=None, ge=0, le=1)
    evidence_state: EvidenceState
    scientific_status: Literal["candidate"] = "candidate"
    applicability: Literal["applicable", "not_assessed"]
    missingness: Literal["available", "unavailable"]
    evidence_ids: list[str] = Field(min_length=1)
    reason_codes: list[str] = Field(default_factory=list)

    @field_validator("evidence_ids", "reason_codes")
    @classmethod
    def presentation_lists_are_unique(cls, values: list[str]) -> list[str]:
        if values != sorted(set(values)):
            raise ValueError("presentation references must be sorted and unique")
        return values

    @model_validator(mode="after")
    def quantities_are_coherent(self) -> Self:
        if self.row_count > self.denominator:
            raise ValueError("presentation row count cannot exceed its denominator")
        if self.missingness == "unavailable":
            if self.count is not None or self.fraction is not None:
                raise ValueError("unavailable presentation records cannot encode zero")
            if self.applicability != "not_assessed" or not self.reason_codes:
                raise ValueError("unavailable presentation records require a reason")
        else:
            if self.count is None or self.fraction is None:
                raise ValueError("available presentation records require quantities")
            if not math.isclose(
                self.fraction,
                self.count / self.denominator,
                abs_tol=1e-12,
            ):
                raise ValueError("presentation fraction does not match its row")
            if self.applicability != "applicable":
                raise ValueError("available presentation records must be applicable")
        if (self.column_kind == "state") != (self.state_id is not None):
            raise ValueError("only state columns may declare a state ID")
        if self.column_kind in {"subtype_unresolved", "subtype_unavailable"} and (
            self.reference_level != "L2"
        ):
            raise ValueError("subtype status columns require refined-state semantics")
        parent_values = (
            self.parent_denominator,
            self.parent_denominator_scope,
            self.parent_fraction,
        )
        if self.reference_level == "L2":
            if self.parent_denominator is None or self.parent_denominator_scope is None:
                raise ValueError(
                    "refined records require their broad-state denominator"
                )
            if self.count is None:
                raise ValueError("refined records must retain quantitative mass")
            if self.parent_denominator == 0:
                if self.count != 0 or self.parent_fraction is not None:
                    raise ValueError(
                        "empty refined parents require zero count and no fraction"
                    )
            elif self.parent_fraction is None or not math.isclose(
                self.parent_fraction,
                self.count / self.parent_denominator,
                abs_tol=1e-12,
            ):
                raise ValueError("refined parent fraction does not match its count")
        elif any(value is not None for value in parent_values):
            raise ValueError("only refined records may carry parent denominators")
        if self.reference_level == "L2" and self.parent_state_id is None:
            raise ValueError("refined state columns require a parent state")
        if self.reference_level != "L2" and self.parent_state_id is not None:
            raise ValueError("only refined state columns may declare a parent")
        return self


class HierarchicalCellStateVisualizationDataV1(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[
        "bridge://schemas/hierarchical-cell-state-visualization-data/v0.1"
    ] = HIERARCHICAL_CELL_STATE_VISUALIZATION_SCHEMA_REF
    profile_id: str = Field(
        pattern=r"^hierarchical-cell-state-visualization:[A-Za-z0-9._-]+$"
    )
    producer_run_ref: str = Field(pattern=r"^run:[A-Za-z0-9._:-]+$")
    source_profile_ref: str = Field(
        pattern=r"^hierarchical-cell-state-composition:[A-Za-z0-9._-]+$"
    )
    source_profile_sha256: str = Field(pattern=_SHA256)
    scientific_status: Literal["candidate"] = "candidate"
    observation_unit: Literal["cells", "nuclei", "observations"]
    whole_product_denominator: int = Field(gt=0)
    denominator_scope: str = Field(min_length=1)
    grouping: ProductGroupingProvenance
    records: list[HierarchicalCellStateVisualizationRecord] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    alt_text: str = Field(min_length=40, max_length=240)
    long_description: str = Field(min_length=80)

    @model_validator(mode="after")
    def presentation_grid_is_complete(self) -> Self:
        digest = self.profile_id.rsplit(":", 1)[1]
        if self.producer_run_ref != f"run:run-{digest}":
            raise ValueError("hierarchy profile and producer run must share a digest")
        if self.source_profile_ref != (
            f"hierarchical-cell-state-composition:run-{digest}"
        ):
            raise ValueError("hierarchy source profile must share the producer digest")
        record_ids = [record.record_id for record in self.records]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("hierarchical presentation record IDs must be unique")
        rows = {}
        columns = {}
        for record in self.records:
            row_metadata = (
                record.row_order,
                record.row_display_name,
                record.row_count,
                record.row_whole_product_fraction,
            )
            column_metadata = (
                record.column_order,
                record.column_display_name,
                record.column_kind,
                record.state_id,
                record.reference_level,
                record.parent_state_id,
            )
            if record.row_id in rows and rows[record.row_id] != row_metadata:
                raise ValueError("presentation row metadata must be consistent")
            if (
                record.column_id in columns
                and columns[record.column_id] != column_metadata
            ):
                raise ValueError("presentation column metadata must be consistent")
            rows[record.row_id] = row_metadata
            columns[record.column_id] = column_metadata
        if len(rows) * len(columns) != len(self.records):
            raise ValueError("hierarchical presentation must be a complete grid")
        if {(record.row_id, record.column_id) for record in self.records} != {
            (row_id, column_id) for row_id in rows for column_id in columns
        }:
            raise ValueError("hierarchical presentation grid has missing cells")
        group_share_columns = [
            column_id
            for column_id, value in columns.items()
            if value[2] == "group_share"
        ]
        if len(group_share_columns) != 1:
            raise ValueError(
                "hierarchical presentation requires one product-share column"
            )
        open_set_columns = [
            column_id
            for column_id, value in columns.items()
            if value[2] == "open_set_not_assessed"
        ]
        if len(open_set_columns) != 1:
            raise ValueError("hierarchical presentation requires one open-set status")
        for row_id, (_, _, row_count, row_fraction) in rows.items():
            share = next(
                record
                for record in self.records
                if record.row_id == row_id
                and record.column_id == group_share_columns[0]
            )
            if (
                share.count != row_count
                or share.denominator != self.whole_product_denominator
                or share.denominator_scope != self.denominator_scope
                or share.fraction is None
                or not math.isclose(share.fraction, row_fraction, abs_tol=1e-12)
            ):
                raise ValueError(
                    "product-share record must bind the whole-product denominator"
                )
        row_orders = sorted(value[0] for value in rows.values())
        column_orders = sorted(value[0] for value in columns.values())
        for _, _, row_count, row_fraction in rows.values():
            if row_count > self.whole_product_denominator or not math.isclose(
                row_fraction,
                row_count / self.whole_product_denominator,
                abs_tol=1e-12,
            ):
                raise ValueError("presentation row share must use the whole product")
        if len(rows) == 1:
            only_row = next(iter(rows.values()))
            if only_row[2] != self.whole_product_denominator:
                raise ValueError("single-row presentation must cover the whole product")
        elif sum(value[2] for value in rows.values()) != self.whole_product_denominator:
            raise ValueError("product-group rows must conserve the whole product")
        if row_orders != list(range(len(rows))) or column_orders != list(
            range(len(columns))
        ):
            raise ValueError("presentation row and column order must be contiguous")
        l1_columns = {
            column_id for column_id, value in columns.items() if value[4] == "L1"
        }
        for row_id in rows:
            root = [
                record
                for record in self.records
                if record.row_id == row_id
                and (
                    record.column_id in l1_columns
                    or record.column_kind in {"source_conflict", "unavailable"}
                )
            ]
            available_total = sum(record.fraction or 0.0 for record in root)
            if not math.isclose(available_total, 1.0, abs_tol=1e-12):
                raise ValueError("broad-state presentation rows must be conserved")

        broad_column_by_state = {
            value[3]: column_id
            for column_id, value in columns.items()
            if value[4] == "L1" and value[3] is not None
        }
        refined_by_parent: dict[str, list[tuple[str, tuple]]] = {}
        for column_id, value in columns.items():
            if value[4] == "L2" and value[5] is not None:
                refined_by_parent.setdefault(value[5], []).append((column_id, value))
        for parent_state_id, refined_columns in refined_by_parent.items():
            parent_column_id = broad_column_by_state.get(parent_state_id)
            if parent_column_id is None:
                raise ValueError("refined presentation parent is missing")
            status_kinds = sorted(
                value[2] for _, value in refined_columns if value[2] != "state"
            )
            if status_kinds != ["subtype_unavailable", "subtype_unresolved"]:
                raise ValueError(
                    "each refined partition requires unresolved and unavailable rows"
                )
            for row_id in rows:
                parent = next(
                    record
                    for record in self.records
                    if record.row_id == row_id and record.column_id == parent_column_id
                )
                refined = [
                    next(
                        record
                        for record in self.records
                        if record.row_id == row_id and record.column_id == column_id
                    )
                    for column_id, _ in refined_columns
                ]
                parent_scopes = {item.parent_denominator_scope for item in refined}
                if any(item.parent_denominator != parent.count for item in refined):
                    raise ValueError(
                        "refined records must bind the displayed broad-parent count"
                    )
                if len(parent_scopes) != 1:
                    raise ValueError(
                        "refined records must share one broad-parent denominator scope"
                    )
                if parent.count is None or any(item.count is None for item in refined):
                    raise ValueError(
                        "refined presentation partitions must be quantitative"
                    )
                if sum(item.count or 0 for item in refined) != parent.count:
                    raise ValueError(
                        "refined presentation must conserve its broad parent"
                    )
        if self.evidence_ids != sorted(set(self.evidence_ids)):
            raise ValueError("profile evidence IDs must be sorted and unique")
        return self


class VisualizationArtifactHash(FrozenModel):
    artifact_id: str = Field(min_length=1)
    content_sha256: str = Field(pattern=_SHA256)


class P002VisualizationArtifactSet(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[P002_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF] = (
        P002_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF
    )
    artifact_set_id: str = Field(pattern=r"^p0-02-visualizations:[a-f0-9]{16}$")
    hierarchical_data_artifact_id: str = Field(min_length=1)
    hierarchical_data_sha256: str = Field(pattern=_SHA256)
    source_matrix_data_artifact_id: str = Field(min_length=1)
    source_matrix_data_sha256: str = Field(pattern=_SHA256)
    visualizations: list[VisualizationArtifactV2] = Field(min_length=2, max_length=2)
    artifact_hashes: list[VisualizationArtifactHash] = Field(
        min_length=10, max_length=10
    )

    @model_validator(mode="after")
    def component_set_is_complete(self) -> Self:
        if [item.component_ref for item in self.visualizations] != list(
            P002_COMPONENT_REFS
        ):
            raise ValueError("P0-02 artifact set requires the two fixed components")

        expected_data = (
            (self.hierarchical_data_artifact_id, self.hierarchical_data_sha256),
            (self.source_matrix_data_artifact_id, self.source_matrix_data_sha256),
        )
        if any(
            item.data_binding.artifact_id != artifact_id
            or item.data_binding.sha256 != sha256
            for item, (artifact_id, sha256) in zip(
                self.visualizations, expected_data, strict=True
            )
        ):
            raise ValueError("visualizations must bind their declared data artifacts")

        expected_media = ["image/svg+xml", "image/png", "application/pdf"]
        if any(
            [render.media_type for render in item.renders] != expected_media
            for item in self.visualizations
        ):
            raise ValueError("each visualization requires ordered SVG, PNG and PDF")

        digest = self.artifact_set_id.rsplit(":", 1)[1]
        if self.hierarchical_data_artifact_id != _artifact_id(
            digest, "hierarchical-visualization-data"
        ) or self.source_matrix_data_artifact_id != _artifact_id(
            digest, "source-state-evidence-data"
        ):
            raise ValueError("data artifact IDs must bind the artifact-set run")

        if len({item.visualization_id for item in self.visualizations}) != 2:
            raise ValueError("visualization IDs must be unique")
        table_ids = [
            item.accessibility.table_artifact_id for item in self.visualizations
        ]
        if len(set(table_ids)) != 2:
            raise ValueError("visualization table artifact IDs must be unique")

        for item, (
            component_ref,
            slug,
            schema_ref,
            records_path,
            artifact_slug,
        ) in zip(self.visualizations, P002_COMPONENT_BINDINGS, strict=True):
            if (
                item.component_ref != component_ref
                or item.visualization_id != _visualization_id(digest, slug)
                or item.data_binding.schema_ref != schema_ref
                or item.data_binding.records_path != records_path
                or item.accessibility.table_artifact_id
                != _artifact_id(digest, f"{artifact_slug}-table")
            ):
                raise ValueError("visualization identity does not match its component")
            expected_render_ids = [
                _artifact_id(digest, f"{artifact_slug}-{extension}")
                for extension in ("svg", "png", "pdf")
            ]
            if [render.artifact_id for render in item.renders] != expected_render_ids:
                raise ValueError("render artifact IDs must match format and component")

        producer_contracts = {
            (
                item.producer_tool_id,
                item.producer_tool_version,
                item.producer_run_ref,
            )
            for item in self.visualizations
        }
        if producer_contracts != {
            ("P0-02", self.visualizations[0].producer_tool_version, f"run:run-{digest}")
        }:
            raise ValueError("visualizations must share the artifact-set producer run")

        all_ids = {
            self.hierarchical_data_artifact_id,
            self.source_matrix_data_artifact_id,
            *table_ids,
            *(
                render.artifact_id
                for item in self.visualizations
                for render in item.renders
            ),
        }
        if len(all_ids) != 10:
            raise ValueError("data, table and render artifact IDs must be disjoint")
        artifact_hashes = {
            item.artifact_id: item.content_sha256 for item in self.artifact_hashes
        }
        if len(artifact_hashes) != len(self.artifact_hashes):
            raise ValueError("artifact content bindings must be unique")
        if set(artifact_hashes) != all_ids:
            raise ValueError("artifact content bindings must cover the exact bundle")
        if (
            artifact_hashes[self.hierarchical_data_artifact_id]
            != self.hierarchical_data_sha256
            or artifact_hashes[self.source_matrix_data_artifact_id]
            != self.source_matrix_data_sha256
        ):
            raise ValueError("data artifact content hashes must match their bindings")
        return self


PUBLIC_SCHEMA_MODELS = {
    CELL_STATE_EVIDENCE_MATRIX_SCHEMA_REF: CellStateEvidenceMatrixData,
    CELL_STATE_EVIDENCE_MATRIX_V2_SCHEMA_REF: CellStateEvidenceMatrixDataV2,
    HIERARCHICAL_CELL_STATE_VISUALIZATION_SCHEMA_REF: (
        HierarchicalCellStateVisualizationDataV1
    ),
    P002_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF: P002VisualizationArtifactSet,
}
