from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, StrictInt, field_validator, model_validator

from bridge.tool_packages._configurable_contracts import (
    CompositionView,
    OBJECT_ID_PATTERN,
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
ROLE_SCHEMA_CONDITIONALS = {
    "allOf": [
        {
            "if": {
                "properties": {"product_role": {"const": "unknown"}},
                "required": ["product_role"],
            },
            "then": {
                "required": ["unknown_reason"],
                "properties": {
                    "unknown_reason": {"type": "string"},
                    "role_evidence_class": {"type": "null"},
                    "evidence_direction": {"type": "null"},
                },
            },
            "else": {"properties": {"unknown_reason": {"type": "null"}}},
        },
        {
            "if": {
                "properties": {"product_role": {"const": "known_off_target"}},
                "required": ["product_role"],
            },
            "then": {
                "required": ["role_evidence_class", "evidence_direction"],
                "properties": {
                    "role_evidence_class": {"type": "string"},
                    "evidence_direction": {"type": "string"},
                },
            },
        },
    ]
}


def _unique(values: list[object], field: str) -> list[object]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must contain unique values")
    return values


class ProductRole(StrEnum):
    TARGET = "target"
    ACCEPTABLE_ADJACENT = "acceptable_adjacent"
    KNOWN_OFF_TARGET = "known_off_target"
    ROLE_UNRESOLVED = "role_unresolved"
    UNKNOWN = "unknown"


class ProductRoleLineageRule(FrozenModel):
    product_role: ProductRole
    allowed_lineage_roles: list[LineageRole] = Field(
        min_length=1,
        json_schema_extra={"uniqueItems": True},
    )

    @field_validator("allowed_lineage_roles")
    @classmethod
    def lineage_roles_are_unique(
        cls, value: list[LineageRole]
    ) -> list[LineageRole]:
        return _unique(value, "allowed_lineage_roles")


class RoleEvidenceClass(StrEnum):
    CLEAR_OFF_AXIS = "clear_off_axis"
    CONTEXT_DEPENDENT_NON_TARGET = "context_dependent_non_target"
    INTENDED_ACCESSORY = "intended_accessory"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class EvidenceDirection(StrEnum):
    ADVERSE_DIRECTION_SUPPORTED = "adverse_direction_supported"
    NON_TARGET_NO_OPTIMUM_KNOWN = "non_target_no_optimum_known"
    CONTEXT_DEPENDENT = "context_dependent"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class UnknownReason(StrEnum):
    REFERENCE_GAP = "reference_gap"
    METHOD_CONFLICT = "method_conflict"
    BIOLOGICAL_UNRESOLVED = "biological_unresolved"
    TECHNICAL_SHIFT = "technical_shift"
    TECHNICAL_UNAVAILABLE = "technical_unavailable"


def _check_role_evidence(
    product_role: ProductRole,
    role_evidence_class: RoleEvidenceClass | None,
    evidence_direction: EvidenceDirection | None,
    unknown_reason: UnknownReason | None,
) -> None:
    if product_role is ProductRole.UNKNOWN:
        if unknown_reason is None:
            raise ValueError("unknown role requires unknown_reason")
        if role_evidence_class is not None or evidence_direction is not None:
            raise ValueError("unknown role cannot claim product-role evidence")
    elif unknown_reason is not None:
        raise ValueError("known identity cannot declare unknown_reason")
    if product_role is ProductRole.KNOWN_OFF_TARGET and (
        role_evidence_class is None or evidence_direction is None
    ):
        raise ValueError("known_off_target requires evidence class and direction")


class OffTargetStateAssignment(FrozenModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra=ROLE_SCHEMA_CONDITIONALS,
    )

    state_id: str = Field(pattern=OBJECT_ID_PATTERN)
    label_level: Literal["L1", "L2", "L3"]
    product_role: ProductRole
    role_evidence_class: RoleEvidenceClass | None = None
    evidence_direction: EvidenceDirection | None = None
    unknown_reason: UnknownReason | None = None
    provenance_refs: list[VersionedObjectRef] = Field(default_factory=list)

    @field_validator("provenance_refs")
    @classmethod
    def provenance_is_unique(
        cls, value: list[VersionedObjectRef]
    ) -> list[VersionedObjectRef]:
        _unique([item.ref for item in value], "provenance_refs")
        return value

    @model_validator(mode="after")
    def role_evidence_is_coherent(self) -> Self:
        _check_role_evidence(
            self.product_role,
            self.role_evidence_class,
            self.evidence_direction,
            self.unknown_reason,
        )
        return self


class OffTargetRoleSpec(FrozenModel):
    object_version: Literal["0.1.0"]
    role_spec_id: str = Field(pattern=r"^off-target-role-spec:[A-Za-z0-9._:-]+$")
    role_spec_version: str = Field(pattern=VERSION_PATTERN)
    product_definition_ref: VersionedObjectRef
    state_role_map_ref: VersionedObjectRef
    annotation_vocabulary_ref: str = Field(pattern=OBJECT_ID_PATTERN)
    review_state: Literal["draft", "reviewed", "frozen"]
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
    required_denominator_view: str = Field(min_length=1)
    lineage_role_rules: list[ProductRoleLineageRule] = Field(min_length=1)
    assignments: list[OffTargetStateAssignment] = Field(min_length=1)
    unmapped_state_policy: Literal["report_role_unresolved"]
    ood_policy: Literal["not_assessed_without_calibration"]
    rare_state_policy: Literal["not_assessed_without_calibration"]

    _required_denominator_is_publication_safe = field_validator(
        "required_denominator_view"
    )(validate_publication_text)

    @field_validator(
        "composition_views",
        "included_label_levels",
        "source_ids",
    )
    @classmethod
    def configured_lists_are_unique(cls, value: list[object]) -> list[object]:
        return _unique(value, "configured list")

    @field_validator("assignments")
    @classmethod
    def assignments_are_unique(
        cls, value: list[OffTargetStateAssignment]
    ) -> list[OffTargetStateAssignment]:
        _unique(
            [(item.label_level, item.state_id) for item in value],
            "assignments",
        )
        return value

    @field_validator("lineage_role_rules")
    @classmethod
    def lineage_role_rules_are_complete(
        cls, value: list[ProductRoleLineageRule]
    ) -> list[ProductRoleLineageRule]:
        roles = [item.product_role for item in value]
        _unique(roles, "lineage_role_rules")
        if set(roles) != set(ProductRole):
            raise ValueError("lineage_role_rules must define every product role")
        return value

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.role_spec_id,
            object_version=self.role_spec_version,
        )


class StateCompositionRecord(FrozenModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra=ROLE_SCHEMA_CONDITIONALS,
    )

    state_id: str = Field(pattern=OBJECT_ID_PATTERN)
    product_role: ProductRole
    role_evidence_class: RoleEvidenceClass | None = None
    evidence_direction: EvidenceDirection | None = None
    unknown_reason: UnknownReason | None = None
    count: StrictInt = Field(ge=0)
    denominator: StrictInt = Field(gt=0)

    @model_validator(mode="after")
    def role_evidence_is_coherent(self) -> Self:
        _check_role_evidence(
            self.product_role,
            self.role_evidence_class,
            self.evidence_direction,
            self.unknown_reason,
        )
        return self


class UnmappedOffTargetState(FrozenModel):
    state_id: str = Field(pattern=OBJECT_ID_PATTERN)
    label_level: Literal["L1", "L2", "L3"]
    composition_view: CompositionView
    source_id: str | None = Field(default=None, pattern=OBJECT_ID_PATTERN)
    count: StrictInt = Field(ge=0)
    denominator: StrictInt = Field(gt=0)
    reason_code: Literal["product_role_not_configured"]


class OffTargetCompositionChannel(FrozenModel):
    composition_view: CompositionView
    source_id: str | None = Field(default=None, pattern=OBJECT_ID_PATTERN)
    label_level: Literal["L1", "L2", "L3"]
    denominator_view: str = Field(min_length=1)
    denominator: StrictInt = Field(gt=0)
    role_fractions: list[RoleFraction]
    state_breakdown: list[StateCompositionRecord]

    _denominator_is_publication_safe = field_validator("denominator_view")(
        validate_publication_text
    )

    @model_validator(mode="after")
    def roles_are_complete(self) -> Self:
        expected = {role.value for role in ProductRole}
        if (
            {item.role for item in self.role_fractions} != expected
            or len(self.role_fractions) != len(expected)
        ):
            raise ValueError("role fractions must contain each product role once")
        return self


class OODAssessmentProfile(FrozenModel):
    assessment_state: Literal["not_assessed"]
    reason_code: Literal["ood_calibration_not_supplied"]


class RareStateDetectionProfile(FrozenModel):
    assessment_state: Literal["not_assessed"]
    reason_code: Literal["rare_state_calibration_not_supplied"]


class OffTargetInputChecksums(FrozenModel):
    product_case: str = Field(pattern=SHA256_PATTERN)
    product_definition_card: str = Field(pattern=SHA256_PATTERN)
    state_role_map: str = Field(pattern=SHA256_PATTERN)
    off_target_role_spec: str = Field(pattern=SHA256_PATTERN)
    cell_state_evidence_profile: str = Field(pattern=SHA256_PATTERN)
    qc_readiness_profile: str = Field(pattern=SHA256_PATTERN)


class OffTargetControlResult(FrozenModel):
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
                            "composition_channels": {"maxItems": 0},
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
                            "composition_channels": {"minItems": 1},
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
    result_id: str = Field(pattern=r"^off-target-result:[a-f0-9]{16}$")
    tool_id: Literal["P0-05"]
    tool_version: str = Field(pattern=VERSION_PATTERN)
    product_case_ref: VersionedObjectRef
    product_definition_ref: VersionedObjectRef
    state_role_map_ref: VersionedObjectRef
    role_spec_ref: VersionedObjectRef
    cell_state_profile_ref: VersionedObjectRef
    qc_profile_ref: VersionedObjectRef
    input_sha256_by_role: OffTargetInputChecksums
    result_state: Literal["complete", "partial", "not_assessed"]
    composition_channels: list[OffTargetCompositionChannel]
    unmapped_states: list[UnmappedOffTargetState]
    ood_assessment: OODAssessmentProfile
    rare_state_detection: RareStateDetectionProfile
    evidence_refs: list[PublishedRef] = Field(json_schema_extra={"uniqueItems": True})
    reason_codes: list[ReasonCode] = Field(json_schema_extra={"uniqueItems": True})
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
        if self.result_state == "not_assessed" and self.composition_channels:
            raise ValueError("not_assessed result cannot contain composition")
        if self.result_state == "complete" and (
            not self.composition_channels or self.unmapped_states
        ):
            raise ValueError("complete result requires mapped composition")
        if self.result_state != "not_assessed" and self.score_state != ScoreState.SHADOW:
            raise ValueError("assessed off-target evidence remains shadow")
        if self.result_state == "not_assessed" and self.score_state != ScoreState.UNAVAILABLE:
            raise ValueError("not_assessed off-target evidence is unavailable")
        return self


PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/off-target-role-spec/v0.1": OffTargetRoleSpec,
    "bridge://schemas/off-target-control-result/v0.1": OffTargetControlResult,
}
