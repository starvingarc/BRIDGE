from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)

from bridge.tool_packages._configurable_contracts import (
    CompositionView,
    OBJECT_ID_PATTERN,
    ProductCase,
    ProductDefinitionCard,
    RoleFraction,
    SHA256_PATTERN,
    UpstreamCompositionRecord,
    UpstreamCompositionView,
    VERSION_PATTERN,
    VersionedObjectRef,
)
from bridge.tool_packages._publication_safety import validate_publication_text
from bridge.toolkit.contracts import FrozenModel, ScoreState


PublishedRef = Annotated[str, Field(pattern=OBJECT_ID_PATTERN)]
ReasonCode = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]


def _unique(values: list[object], field: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must contain unique values")


class LineageRole(StrEnum):
    TARGET = "target"
    ACCEPTABLE_ADJACENT = "acceptable_adjacent"
    NOT_TARGET = "not_target"
    UNRESOLVED = "unresolved"


class RegionalRole(StrEnum):
    TARGET_REGION = "target_region"
    ACCEPTABLE_ADJACENT_REGION = "acceptable_adjacent_region"
    REGIONAL_SHIFT = "regional_shift"
    NOT_APPLICABLE = "not_applicable"
    UNRESOLVED = "unresolved"


class StateRoleAssignment(FrozenModel):
    state_id: str = Field(pattern=OBJECT_ID_PATTERN)
    label_level: Literal["L1", "L2", "L3"]
    lineage_role: LineageRole
    regional_role: RegionalRole
    provenance_refs: list[VersionedObjectRef] = Field(default_factory=list)

    @field_validator("provenance_refs")
    @classmethod
    def provenance_is_unique(
        cls, value: list[VersionedObjectRef]
    ) -> list[VersionedObjectRef]:
        _unique([item.ref for item in value], "provenance_refs")
        return value


class StateRoleMap(FrozenModel):
    object_version: Literal["0.1.0"]
    role_map_id: str = Field(pattern=r"^state-role-map:[A-Za-z0-9._:-]+$")
    role_map_version: str = Field(pattern=VERSION_PATTERN)
    product_definition_ref: VersionedObjectRef
    annotation_vocabulary_ref: str = Field(pattern=OBJECT_ID_PATTERN)
    review_state: Literal["draft", "reviewed", "frozen"]
    assignments: list[StateRoleAssignment] = Field(min_length=1)

    @field_validator("assignments")
    @classmethod
    def assignments_are_unique(
        cls, value: list[StateRoleAssignment]
    ) -> list[StateRoleAssignment]:
        _unique(
            [(item.label_level, item.state_id) for item in value],
            "assignments",
        )
        return value

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.role_map_id,
            object_version=self.role_map_version,
        )


class TargetRegionalAssessmentSpec(FrozenModel):
    object_version: Literal["0.1.0"]
    assessment_spec_id: str = Field(
        pattern=r"^target-regional-assessment-spec:[A-Za-z0-9._:-]+$"
    )
    assessment_spec_version: str = Field(pattern=VERSION_PATTERN)
    product_definition_ref: VersionedObjectRef
    status: Literal["candidate", "frozen"]
    composition_views: list[CompositionView] = Field(min_length=1)
    included_label_levels: list[Literal["L1", "L2", "L3"]] = Field(
        min_length=1
    )
    source_ids: list[str] = Field(default_factory=list)
    regional_denominator_lineage_roles: list[LineageRole] = Field(min_length=1)
    whole_product_target_region_roles: list[RegionalRole] = Field(min_length=1)
    unmapped_state_policy: Literal["report_unresolved"]
    spatial_policy: Literal["not_assessed_without_projection"]

    @field_validator(
        "composition_views",
        "included_label_levels",
        "source_ids",
        "regional_denominator_lineage_roles",
        "whole_product_target_region_roles",
    )
    @classmethod
    def configured_values_are_unique(cls, value: list[object]) -> list[object]:
        _unique(value, "configured list")
        return value

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.assessment_spec_id,
            object_version=self.assessment_spec_version,
        )


class UnmappedStateRecord(FrozenModel):
    state_id: str = Field(pattern=OBJECT_ID_PATTERN)
    label_level: Literal["L1", "L2", "L3"]
    composition_view: CompositionView
    source_id: str | None = Field(default=None, pattern=OBJECT_ID_PATTERN)
    count: StrictInt = Field(ge=0)
    denominator: StrictInt = Field(gt=0)
    reason_code: Literal["state_role_not_configured"]


class TargetIdentityChannel(FrozenModel):
    composition_view: CompositionView
    source_id: str | None = Field(default=None, pattern=OBJECT_ID_PATTERN)
    label_level: Literal["L1", "L2", "L3"]
    denominator_view: str = Field(min_length=1)
    denominator: StrictInt = Field(gt=0)
    role_fractions: list[RoleFraction] = Field(min_length=1)

    _denominator_is_publication_safe = field_validator("denominator_view")(
        validate_publication_text
    )


class RegionalFidelityChannel(FrozenModel):
    composition_view: CompositionView
    source_id: str | None = Field(default=None, pattern=OBJECT_ID_PATTERN)
    label_level: Literal["L1", "L2", "L3"]
    denominator_view: str = Field(min_length=1)
    whole_product_denominator: StrictInt = Field(gt=0)
    target_related_denominator: StrictInt = Field(ge=0)
    target_related_role_fractions: list[RoleFraction] = Field(min_length=1)
    whole_product_target_region_fraction: RoleFraction

    _denominator_is_publication_safe = field_validator("denominator_view")(
        validate_publication_text
    )


class SpatialReferenceProjectionProfile(FrozenModel):
    assessment_state: Literal["not_assessed"]
    reason_code: Literal["spatial_projection_not_supplied"]


class InputChecksumBindings(FrozenModel):
    product_case: str = Field(pattern=SHA256_PATTERN)
    product_definition_card: str = Field(pattern=SHA256_PATTERN)
    state_role_map: str = Field(pattern=SHA256_PATTERN)
    target_regional_assessment_spec: str = Field(pattern=SHA256_PATTERN)
    cell_state_evidence_profile: str = Field(pattern=SHA256_PATTERN)
    qc_readiness_profile: str = Field(pattern=SHA256_PATTERN)


class TargetRegionalEvidenceResult(FrozenModel):
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
                            "target_identity_channels": {"maxItems": 0},
                            "regional_fidelity_channels": {"maxItems": 0},
                            "score_state": {"const": "unavailable"},
                        }
                    },
                },
                {
                    "if": {
                        "properties": {"result_state": {"const": "complete"}},
                        "required": ["result_state"],
                    },
                    "then": {
                        "properties": {
                            "target_identity_channels": {"minItems": 1},
                            "regional_fidelity_channels": {"minItems": 1},
                            "unmapped_states": {"maxItems": 0},
                            "score_state": {"const": "shadow"},
                        }
                    },
                },
                {
                    "if": {
                        "properties": {"result_state": {"const": "partial"}},
                        "required": ["result_state"],
                    },
                    "then": {
                        "properties": {
                            "target_identity_channels": {"minItems": 1},
                            "regional_fidelity_channels": {"minItems": 1},
                            "score_state": {"const": "shadow"},
                        }
                    },
                },
            ]
        },
    )

    object_version: Literal["0.1.0"]
    result_id: str = Field(pattern=r"^target-regional-result:[a-f0-9]{16}$")
    tool_id: Literal["P0-03"]
    tool_version: str = Field(pattern=VERSION_PATTERN)
    product_case_ref: VersionedObjectRef
    product_definition_ref: VersionedObjectRef
    state_role_map_ref: VersionedObjectRef
    assessment_spec_ref: VersionedObjectRef
    cell_state_profile_ref: VersionedObjectRef
    qc_profile_ref: VersionedObjectRef
    input_sha256_by_role: InputChecksumBindings
    result_state: Literal["complete", "partial", "not_assessed"]
    target_identity_channels: list[TargetIdentityChannel]
    regional_fidelity_channels: list[RegionalFidelityChannel]
    unmapped_states: list[UnmappedStateRecord]
    spatial_projection: SpatialReferenceProjectionProfile
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
        has_channels = bool(
            self.target_identity_channels or self.regional_fidelity_channels
        )
        if self.result_state == "not_assessed" and has_channels:
            raise ValueError("not_assessed result cannot contain assessed channels")
        if self.result_state == "complete" and (
            not self.target_identity_channels
            or not self.regional_fidelity_channels
            or self.unmapped_states
        ):
            raise ValueError("complete result requires both profiles and no unmapped states")
        if self.score_state == ScoreState.UNAVAILABLE and self.result_state != "not_assessed":
            raise ValueError("assessed candidate result must remain shadow")
        return self


PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/product-case/v0.1": ProductCase,
    "bridge://schemas/product-definition-card/v0.1": ProductDefinitionCard,
    "bridge://schemas/state-role-map/v0.1": StateRoleMap,
    "bridge://schemas/target-regional-assessment-spec/v0.1": (
        TargetRegionalAssessmentSpec
    ),
    "bridge://schemas/target-regional-evidence-result/v0.1": (
        TargetRegionalEvidenceResult
    ),
}
