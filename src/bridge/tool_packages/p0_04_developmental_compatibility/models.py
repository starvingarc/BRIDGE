from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, StrictInt, field_validator, model_validator

from bridge.tool_packages._configurable_contracts import (
    OBJECT_ID_PATTERN,
    SHA256_PATTERN,
    VERSION_PATTERN,
    DevelopmentWindowSpec,
    ProductCase,
    ProductDefinitionCard,
    RoleFraction,
    VersionedObjectRef,
)
from bridge.tool_packages._publication_safety import validate_publication_text
from bridge.tool_packages.p0_04_developmental_compatibility.roles import (
    DevelopmentStageRole,
)
from bridge.toolkit.contracts import FrozenModel


ReasonCode = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]


def _unique(values: list[object], field: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must contain unique values")


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include a timezone")
    return value.astimezone(timezone.utc)


class DevelopmentStateAssignment(FrozenModel):
    state_id: str = Field(pattern=OBJECT_ID_PATTERN)
    label_level: Literal["L1", "L2", "L3"]
    stage_role: DevelopmentStageRole
    target_related: bool
    provenance_refs: list[VersionedObjectRef] = Field(default_factory=list)

    @field_validator("provenance_refs")
    @classmethod
    def provenance_is_unique(
        cls, value: list[VersionedObjectRef]
    ) -> list[VersionedObjectRef]:
        _unique([item.ref for item in value], "provenance_refs")
        return value


class DevelopmentStateMap(FrozenModel):
    object_version: Literal["0.1.0"]
    state_map_id: str = Field(pattern=r"^development-state-map:[A-Za-z0-9._:-]+$")
    state_map_version: str = Field(pattern=VERSION_PATTERN)
    product_definition_ref: VersionedObjectRef
    annotation_vocabulary_ref: str = Field(pattern=OBJECT_ID_PATTERN)
    review_state: Literal["draft", "reviewed", "frozen"]
    assignments: list[DevelopmentStateAssignment] = Field(min_length=1)

    @field_validator("assignments")
    @classmethod
    def assignments_are_unique(
        cls, value: list[DevelopmentStateAssignment]
    ) -> list[DevelopmentStateAssignment]:
        _unique([(item.label_level, item.state_id) for item in value], "assignments")
        return value

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.state_map_id,
            object_version=self.state_map_version,
        )


class DevelopmentTimepointStateCount(FrozenModel):
    state_id: str = Field(pattern=OBJECT_ID_PATTERN)
    label_level: Literal["L1", "L2", "L3"]
    count: StrictInt = Field(ge=0)


class DevelopmentTimepointRecord(FrozenModel):
    timepoint_id: str = Field(pattern=OBJECT_ID_PATTERN)
    timepoint_order: StrictInt = Field(ge=0)
    timepoint_label: str = Field(min_length=1)
    independence_group_refs: list[VersionedObjectRef] = Field(min_length=1)
    denominator: StrictInt = Field(gt=0)
    state_counts: list[DevelopmentTimepointStateCount]

    _label_is_safe = field_validator("timepoint_label")(validate_publication_text)

    @field_validator("independence_group_refs")
    @classmethod
    def groups_are_unique(
        cls, value: list[VersionedObjectRef]
    ) -> list[VersionedObjectRef]:
        _unique([item.ref for item in value], "independence_group_refs")
        return value

    @field_validator("state_counts")
    @classmethod
    def states_are_unique(
        cls, value: list[DevelopmentTimepointStateCount]
    ) -> list[DevelopmentTimepointStateCount]:
        _unique([(item.label_level, item.state_id) for item in value], "state_counts")
        return value

    @model_validator(mode="after")
    def counts_fit_denominator(self) -> Self:
        if sum(item.count for item in self.state_counts) > self.denominator:
            raise ValueError("timepoint state counts exceed denominator")
        return self


class DevelopmentTimepointSeries(FrozenModel):
    object_version: Literal["0.1.0"]
    series_id: str = Field(pattern=r"^development-timepoint-series:[A-Za-z0-9._:-]+$")
    series_version: str = Field(pattern=VERSION_PATTERN)
    product_case_ref: VersionedObjectRef
    state_map_ref: VersionedObjectRef
    time_basis: Literal["in_vitro_day", "declared_stage"]
    records: list[DevelopmentTimepointRecord] = Field(min_length=1)

    @field_validator("records")
    @classmethod
    def records_are_unique_and_ordered(
        cls, value: list[DevelopmentTimepointRecord]
    ) -> list[DevelopmentTimepointRecord]:
        _unique([item.timepoint_id for item in value], "timepoint IDs")
        _unique([item.timepoint_order for item in value], "timepoint orders")
        if [item.timepoint_order for item in value] != sorted(
            item.timepoint_order for item in value
        ):
            raise ValueError("timepoint records must follow timepoint_order")
        return value

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.series_id,
            object_version=self.series_version,
        )


class DevelopmentFractionProfile(FrozenModel):
    denominator_kind: Literal["whole_product", "target_related"]
    denominator_view: str = Field(min_length=1)
    denominator: StrictInt = Field(ge=0)
    role_fractions: list[RoleFraction] = Field(min_length=5, max_length=5)

    _denominator_view_is_safe = field_validator("denominator_view")(
        validate_publication_text
    )

    @model_validator(mode="after")
    def fractions_conserve_denominator(self) -> Self:
        roles = [item.role for item in self.role_fractions]
        if roles != [role.value for role in DevelopmentStageRole]:
            raise ValueError("stage fractions must contain every role in contract order")
        if any(item.denominator != self.denominator for item in self.role_fractions):
            raise ValueError("stage fraction denominators must match profile denominator")
        if sum(item.numerator for item in self.role_fractions) != self.denominator:
            raise ValueError("stage fractions must conserve their denominator")
        return self


class DevelopmentTimepointProfile(FrozenModel):
    timepoint_id: str = Field(pattern=OBJECT_ID_PATTERN)
    timepoint_order: StrictInt = Field(ge=0)
    timepoint_label: str = Field(min_length=1)
    independence_group_count: StrictInt = Field(ge=1)
    whole_product_profile: DevelopmentFractionProfile
    target_related_profile: DevelopmentFractionProfile

    _label_is_safe = field_validator("timepoint_label")(validate_publication_text)


class ReferenceStageSupport(FrozenModel):
    assessment_state: Literal["shadow", "unavailable"]
    method_bundle_ref: VersionedObjectRef | None = None
    method_bundle_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    selected_method_ids: list[str] = Field(default_factory=list)
    reason_code: str | None = None

    @model_validator(mode="after")
    def binding_matches_state(self) -> Self:
        available = self.assessment_state == "shadow"
        binding_present = (
            self.method_bundle_ref is not None
            and self.method_bundle_sha256 is not None
            and bool(self.selected_method_ids)
        )
        if available != binding_present:
            raise ValueError("reference-stage state and method binding disagree")
        if available and self.reason_code is not None:
            raise ValueError("available reference-stage support cannot retain a reason")
        if not available and not self.reason_code:
            raise ValueError("unavailable reference-stage support requires a reason")
        return self


class DevelopmentMeasurementMetricName(StrEnum):
    WHOLE_PRODUCT_ROLE_FRACTION = "whole_product_role_fraction"
    TARGET_RELATED_ROLE_FRACTION = "target_related_role_fraction"
    TIMEPOINT_WHOLE_PRODUCT_ROLE_FRACTION = (
        "timepoint_whole_product_role_fraction"
    )
    TIMEPOINT_TARGET_RELATED_ROLE_FRACTION = (
        "timepoint_target_related_role_fraction"
    )


class DevelopmentMeasurementArtifactBinding(FrozenModel):
    measurement_id: str = Field(min_length=1)
    metric_name: DevelopmentMeasurementMetricName
    denominator_kind: Literal["whole_product", "target_related"]
    stage_role: DevelopmentStageRole
    timepoint_id: str | None = Field(default=None, pattern=OBJECT_ID_PATTERN)
    timepoint_order: StrictInt | None = Field(default=None, ge=0)
    artifact_id: str = Field(min_length=1)
    file_name: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]*\.json$")
    sha256: str = Field(pattern=SHA256_PATTERN)
    reason_codes: list[ReasonCode] = Field(default_factory=list)

    @field_validator("reason_codes")
    @classmethod
    def reasons_are_sorted_unique(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("measurement reasons must be unique and sorted")
        return value

    @model_validator(mode="after")
    def metric_context_is_coherent(self) -> Self:
        is_timepoint = self.timepoint_id is not None
        if is_timepoint != (self.timepoint_order is not None):
            raise ValueError("timepoint ID and order must be supplied together")
        expected = {
            (False, "whole_product"): (
                DevelopmentMeasurementMetricName.WHOLE_PRODUCT_ROLE_FRACTION
            ),
            (False, "target_related"): (
                DevelopmentMeasurementMetricName.TARGET_RELATED_ROLE_FRACTION
            ),
            (True, "whole_product"): (
                DevelopmentMeasurementMetricName.TIMEPOINT_WHOLE_PRODUCT_ROLE_FRACTION
            ),
            (True, "target_related"): (
                DevelopmentMeasurementMetricName.TIMEPOINT_TARGET_RELATED_ROLE_FRACTION
            ),
        }[(is_timepoint, self.denominator_kind)]
        if self.metric_name is not expected:
            raise ValueError("measurement metric and projection context disagree")
        return self


class InputChecksumBindings(FrozenModel):
    product_case: str = Field(pattern=SHA256_PATTERN)
    product_definition_card: str = Field(pattern=SHA256_PATTERN)
    development_window_spec: str = Field(pattern=SHA256_PATTERN)
    development_state_map: str = Field(pattern=SHA256_PATTERN)
    measurement_spec: str = Field(pattern=SHA256_PATTERN)
    cell_state_evidence_profile: str = Field(pattern=SHA256_PATTERN)
    development_timepoint_series: str | None = Field(default=None, pattern=SHA256_PATTERN)
    qc_readiness_profile: str | None = Field(default=None, pattern=SHA256_PATTERN)
    biological_unit_manifest: str | None = Field(default=None, pattern=SHA256_PATTERN)
    biological_unit_assignment: str | None = Field(default=None, pattern=SHA256_PATTERN)
    annotation_vocabulary: str | None = Field(default=None, pattern=SHA256_PATTERN)
    reference_manifest: str | None = Field(default=None, pattern=SHA256_PATTERN)
    development_method_spec: str | None = Field(default=None, pattern=SHA256_PATTERN)


class DevelopmentalCompatibilityResult(FrozenModel):
    object_version: Literal["0.2.0"]
    result_id: str = Field(pattern=r"^developmental-compatibility-result:[A-Za-z0-9._:-]+$")
    tool_id: Literal["P0-04"]
    tool_version: str = Field(pattern=VERSION_PATTERN)
    product_case_ref: VersionedObjectRef
    product_definition_ref: VersionedObjectRef
    window_spec_ref: VersionedObjectRef
    state_map_ref: VersionedObjectRef
    measurement_spec_ref: VersionedObjectRef
    cell_state_profile_ref: VersionedObjectRef
    timepoint_series_ref: VersionedObjectRef | None = None
    input_sha256_by_role: InputChecksumBindings
    upstream_composition_state: Literal[
        "shadow", "not_assessed", "unavailable", "unknown", "missing"
    ]
    result_state: Literal["complete", "partial", "not_assessed"]
    window_compatibility_state: Literal["candidate", "not_assessed"]
    analysis_mode: Literal["static_profile", "descriptive_timecourse"]
    whole_product_profile: DevelopmentFractionProfile | None = None
    target_related_profile: DevelopmentFractionProfile | None = None
    timecourse_profiles: list[DevelopmentTimepointProfile] = Field(default_factory=list)
    reference_stage_support: ReferenceStageSupport
    evidence_state: Literal["shadow", "unavailable"]
    evidence_refs: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    domain_score: None = None
    score_state: Literal["unavailable"]

    @field_validator("evidence_refs", "reason_codes")
    @classmethod
    def set_like_values_are_unique(cls, value: list[str]) -> list[str]:
        _unique(value, "set-like list")
        return value

    @model_validator(mode="after")
    def result_is_coherent(self) -> Self:
        assessed = self.whole_product_profile is not None
        if assessed != (self.target_related_profile is not None):
            raise ValueError("both denominator profiles must be supplied together")
        if self.result_state == "not_assessed" and (assessed or self.timecourse_profiles):
            raise ValueError("not_assessed result cannot contain profiles")
        if self.result_state != "not_assessed" and not assessed:
            raise ValueError("assessed result requires both denominator profiles")
        if self.upstream_composition_state != "shadow" and self.result_state != "not_assessed":
            raise ValueError("non-shadow upstream composition cannot be assessed")
        if self.analysis_mode == "static_profile" and len(self.timecourse_profiles) > 1:
            raise ValueError("static profile cannot contain multiple timepoints")
        if self.analysis_mode == "descriptive_timecourse" and len(self.timecourse_profiles) < 2:
            raise ValueError("descriptive timecourse requires at least two timepoints")
        if self.evidence_state == "unavailable" and self.result_state != "not_assessed":
            raise ValueError("unavailable evidence requires not_assessed result")
        return self


class DevelopmentalCompatibilityResultV3(DevelopmentalCompatibilityResult):
    object_version: Literal["0.3.0"]
    measurement_artifacts: list[DevelopmentMeasurementArtifactBinding] = Field(
        min_length=10
    )

    @model_validator(mode="after")
    def measurement_projection_is_complete(self) -> Self:
        if self.measurement_artifacts != sorted(
            self.measurement_artifacts, key=lambda item: item.file_name
        ):
            raise ValueError("measurement artifacts must be sorted by file name")
        for field_name, values in (
            (
                "measurement IDs",
                [item.measurement_id for item in self.measurement_artifacts],
            ),
            (
                "measurement artifact IDs",
                [item.artifact_id for item in self.measurement_artifacts],
            ),
            (
                "measurement file names",
                [item.file_name for item in self.measurement_artifacts],
            ),
        ):
            _unique(values, field_name)

        expected = {
            (None, None, kind, role)
            for kind in ("whole_product", "target_related")
            for role in DevelopmentStageRole
        }
        expected.update(
            {
                (
                    profile.timepoint_id,
                    profile.timepoint_order,
                    kind,
                    role,
                )
                for profile in self.timecourse_profiles
                for kind in ("whole_product", "target_related")
                for role in DevelopmentStageRole
            }
        )
        observed = {
            (
                item.timepoint_id,
                item.timepoint_order,
                item.denominator_kind,
                item.stage_role,
            )
            for item in self.measurement_artifacts
        }
        if observed != expected or len(observed) != len(self.measurement_artifacts):
            raise ValueError(
                "measurement artifacts must bind every projected role fraction once"
            )
        return self


from bridge.tool_packages.p0_04_developmental_compatibility.method_models import (
    DevelopmentMethodBundle,
    DevelopmentMethodSpec,
)


PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/development-window-spec/v0.1": DevelopmentWindowSpec,
    "bridge://schemas/development-state-map/v0.1": DevelopmentStateMap,
    "bridge://schemas/development-timepoint-series/v0.1": DevelopmentTimepointSeries,
    "bridge://schemas/development-method-spec/v0.1": DevelopmentMethodSpec,
    "bridge://schemas/development-method-bundle/v0.1": DevelopmentMethodBundle,
    "bridge://schemas/developmental-compatibility-result/v0.2": (
        DevelopmentalCompatibilityResult
    ),
    "bridge://schemas/developmental-compatibility-result/v0.3": (
        DevelopmentalCompatibilityResultV3
    ),
}


__all__ = [
    "DevelopmentMeasurementArtifactBinding",
    "DevelopmentMeasurementMetricName",
    "DevelopmentStateMap",
    "DevelopmentTimepointSeries",
    "DevelopmentWindowSpec",
    "DevelopmentalCompatibilityResult",
    "DevelopmentalCompatibilityResultV3",
    "ProductCase",
    "ProductDefinitionCard",
    "PUBLIC_SCHEMA_MODELS",
]
