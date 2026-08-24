from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator

from bridge.tool_packages._configurable_contracts import (
    CompositionView,
    OBJECT_ID_PATTERN,
    ProductCase,
    ProductDefinitionCard,
    RoleFraction,
    SHA256_PATTERN,
    VERSION_PATTERN,
    VersionedObjectRef,
)
from bridge.tool_packages._publication_safety import validate_publication_text
from bridge.tool_packages.p0_03_target_regional.models import LineageRole
from bridge.toolkit.contracts import FrozenModel, ScoreState


PublishedRef = Annotated[str, Field(pattern=OBJECT_ID_PATTERN)]
ReasonCode = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]


def _unique(values: list[object], field: str) -> list[object]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must contain unique values")
    return values


class DevelopmentRole(StrEnum):
    EARLIER = "earlier"
    WITHIN_WINDOW = "within_window"
    LATER = "later"
    BRANCH_SHIFT = "branch_shift"
    UNRESOLVED = "unresolved"


class DevelopmentStateAssignment(FrozenModel):
    state_id: str = Field(pattern=OBJECT_ID_PATTERN)
    label_level: Literal["L1", "L2", "L3"]
    development_role: DevelopmentRole
    target_related: StrictBool
    provenance_refs: list[VersionedObjectRef] = Field(default_factory=list)

    @field_validator("provenance_refs")
    @classmethod
    def provenance_is_unique(
        cls, value: list[VersionedObjectRef]
    ) -> list[VersionedObjectRef]:
        _unique([item.ref for item in value], "provenance_refs")
        return value


class DevelopmentWindowSpec(FrozenModel):
    object_version: Literal["0.1.0"]
    window_spec_id: str = Field(
        pattern=r"^development-window-spec:[A-Za-z0-9._:-]+$"
    )
    window_spec_version: str = Field(pattern=VERSION_PATTERN)
    product_definition_ref: VersionedObjectRef
    state_role_map_ref: VersionedObjectRef
    annotation_vocabulary_ref: str = Field(pattern=OBJECT_ID_PATTERN)
    review_state: Literal["draft", "reviewed", "frozen"]
    applicable_assays: list[Literal["scRNA-seq", "snRNA-seq"]] = Field(
        min_length=1,
        json_schema_extra={"uniqueItems": True},
    )
    composition_views: list[CompositionView] = Field(
        min_length=1,
        json_schema_extra={"uniqueItems": True},
    )
    included_label_levels: list[Literal["L1", "L2", "L3"]] = Field(
        min_length=1,
        json_schema_extra={"uniqueItems": True},
    )
    source_ids: list[PublishedRef] = Field(
        default_factory=list,
        json_schema_extra={"uniqueItems": True},
    )
    target_related_lineage_roles: list[LineageRole] = Field(
        min_length=1,
        json_schema_extra={"uniqueItems": True},
    )
    assignments: list[DevelopmentStateAssignment] = Field(min_length=1)
    unmapped_state_policy: Literal["report_unresolved"]
    timecourse_policy: Literal["static_without_timepoint_input"]

    @field_validator(
        "applicable_assays",
        "composition_views",
        "included_label_levels",
        "source_ids",
        "target_related_lineage_roles",
    )
    @classmethod
    def configured_lists_are_unique(cls, value: list[object]) -> list[object]:
        return _unique(value, "configured list")

    @field_validator("assignments")
    @classmethod
    def assignments_are_unique(
        cls, value: list[DevelopmentStateAssignment]
    ) -> list[DevelopmentStateAssignment]:
        _unique(
            [(item.label_level, item.state_id) for item in value],
            "assignments",
        )
        return value

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.window_spec_id,
            object_version=self.window_spec_version,
        )


class UnmappedDevelopmentState(FrozenModel):
    state_id: str = Field(pattern=OBJECT_ID_PATTERN)
    label_level: Literal["L1", "L2", "L3"]
    composition_view: CompositionView
    source_id: str | None = Field(default=None, pattern=OBJECT_ID_PATTERN)
    count: StrictInt = Field(ge=0)
    denominator: StrictInt = Field(gt=0)
    reason_code: Literal["development_role_not_configured"]


class StageCompositionChannel(FrozenModel):
    composition_view: CompositionView
    source_id: str | None = Field(default=None, pattern=OBJECT_ID_PATTERN)
    label_level: Literal["L1", "L2", "L3"]
    denominator_view: str = Field(min_length=1)
    whole_product_denominator: StrictInt = Field(gt=0)
    target_related_denominator: StrictInt = Field(ge=0)
    whole_product_stage_fractions: list[RoleFraction]
    target_related_stage_fractions: list[RoleFraction]

    _denominator_is_publication_safe = field_validator("denominator_view")(
        validate_publication_text
    )

    @model_validator(mode="after")
    def stage_roles_are_complete(self) -> Self:
        expected = {role.value for role in DevelopmentRole}
        for field in (
            self.whole_product_stage_fractions,
            self.target_related_stage_fractions,
        ):
            if {item.role for item in field} != expected or len(field) != len(expected):
                raise ValueError("stage fractions must contain each development role once")
        return self


class ReferenceStageSupportProfile(FrozenModel):
    assessment_state: Literal["not_assessed"]
    reason_code: Literal["reference_stage_support_not_supplied"]


class TimecourseProfile(FrozenModel):
    analysis_mode: Literal["static_profile"]
    evidence_state: Literal["unavailable"]
    reason_code: Literal["true_timepoint_input_not_supplied"]


class DevelopmentInputChecksums(FrozenModel):
    product_case: str = Field(pattern=SHA256_PATTERN)
    product_definition_card: str = Field(pattern=SHA256_PATTERN)
    state_role_map: str = Field(pattern=SHA256_PATTERN)
    development_window_spec: str = Field(pattern=SHA256_PATTERN)
    cell_state_evidence_profile: str = Field(pattern=SHA256_PATTERN)
    qc_readiness_profile: str = Field(pattern=SHA256_PATTERN)


class DevelopmentalCompatibilityResult(FrozenModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {"result_state": {"const": "not_assessed"}},
                        "required": ["result_state"],
                    },
                    "then": {
                        "properties": {
                            "stage_composition_channels": {"maxItems": 0},
                            "score_state": {"const": "unavailable"},
                        }
                    },
                },
                {
                    "if": {
                        "properties": {
                            "result_state": {"enum": ["complete", "partial"]}
                        },
                        "required": ["result_state"],
                    },
                    "then": {
                        "properties": {
                            "stage_composition_channels": {"minItems": 1},
                            "score_state": {"const": "shadow"},
                        }
                    },
                },
                {
                    "if": {
                        "properties": {"result_state": {"const": "complete"}},
                        "required": ["result_state"],
                    },
                    "then": {"properties": {"unmapped_states": {"maxItems": 0}}},
                },
            ]
        },
    )

    object_version: Literal["0.1.0"]
    result_id: str = Field(pattern=r"^developmental-result:[a-f0-9]{16}$")
    tool_id: Literal["P0-04"]
    tool_version: str = Field(pattern=VERSION_PATTERN)
    product_case_ref: VersionedObjectRef
    product_definition_ref: VersionedObjectRef
    state_role_map_ref: VersionedObjectRef
    development_window_ref: VersionedObjectRef
    cell_state_profile_ref: VersionedObjectRef
    qc_profile_ref: VersionedObjectRef
    input_sha256_by_role: DevelopmentInputChecksums
    result_state: Literal["complete", "partial", "not_assessed"]
    analysis_mode: Literal["static_profile"]
    stage_composition_channels: list[StageCompositionChannel]
    unmapped_states: list[UnmappedDevelopmentState]
    reference_stage_support: ReferenceStageSupportProfile
    timecourse_profile: TimecourseProfile
    evidence_refs: list[PublishedRef] = Field(
        json_schema_extra={"uniqueItems": True}
    )
    reason_codes: list[ReasonCode] = Field(
        json_schema_extra={"uniqueItems": True}
    )
    domain_score: None = None
    score_state: Literal[ScoreState.SHADOW, ScoreState.UNAVAILABLE]

    @field_validator("evidence_refs", "reason_codes")
    @classmethod
    def string_lists_are_unique_sorted(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("result string lists must be unique and sorted")
        return value

    @model_validator(mode="after")
    def result_state_is_coherent(self) -> Self:
        if self.result_state == "not_assessed" and self.stage_composition_channels:
            raise ValueError("not_assessed result cannot contain composition")
        if self.result_state == "complete" and (
            not self.stage_composition_channels or self.unmapped_states
        ):
            raise ValueError("complete result requires mapped composition")
        if self.result_state != "not_assessed" and self.score_state != ScoreState.SHADOW:
            raise ValueError("assessed developmental evidence remains shadow")
        if self.result_state == "not_assessed" and self.score_state != ScoreState.UNAVAILABLE:
            raise ValueError("not_assessed developmental evidence is unavailable")
        return self


PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/development-window-spec/v0.1": DevelopmentWindowSpec,
    "bridge://schemas/developmental-compatibility-result/v0.1": (
        DevelopmentalCompatibilityResult
    ),
}
