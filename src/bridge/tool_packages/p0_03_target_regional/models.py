from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from bridge.tool_packages._configurable_contracts import (
    CompositionView,
    OBJECT_ID_PATTERN,
    RoleFraction,
    SHA256_PATTERN,
    VERSION_PATTERN,
    VersionedObjectRef,
)
from bridge.tool_packages.p0_05_off_target_control.models import ProductRole
from bridge.toolkit.contracts import FrozenModel, ScoreState


PublishedRef = Annotated[str, Field(pattern=OBJECT_ID_PATTERN)]
ReasonCode = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]


def _unique(values: list[object], field: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must contain unique values")


class TargetRegionalAssessmentSpec(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    object_version: Literal["0.1.0"]
    assessment_spec_id: str = Field(
        pattern=r"^target-regional-assessment-spec:[A-Za-z0-9._:-]+$"
    )
    assessment_spec_version: str = Field(pattern=VERSION_PATTERN)
    product_definition_ref: VersionedObjectRef
    state_role_map_ref: VersionedObjectRef
    state_role_map_sha256: str = Field(pattern=SHA256_PATTERN)
    status: Literal["candidate", "frozen"]
    composition_views: list[CompositionView] = Field(min_length=1)
    included_label_levels: list[Literal["L1", "L2", "L3"]] = Field(
        min_length=1
    )
    source_ids: list[PublishedRef] = Field(default_factory=list)
    target_identity_numerator_product_roles: list[ProductRole] = Field(
        min_length=1
    )
    regional_denominator_state_ids: list[PublishedRef] = Field(min_length=1)
    regional_target_numerator_state_ids: list[PublishedRef] = Field(min_length=1)
    whole_product_target_region_state_ids: list[PublishedRef] = Field(min_length=1)
    unmapped_state_policy: Literal["not_assessed"]
    ambiguous_state_policy: Literal["not_assessed"]
    spatial_policy: Literal["not_assessed_without_projection"]

    @field_validator(
        "composition_views",
        "included_label_levels",
        "source_ids",
        "target_identity_numerator_product_roles",
        "regional_denominator_state_ids",
        "regional_target_numerator_state_ids",
        "whole_product_target_region_state_ids",
    )
    @classmethod
    def configured_values_are_unique(cls, value: list[object]) -> list[object]:
        _unique(value, "configured list")
        return value

    @model_validator(mode="after")
    def configuration_is_safe(self) -> Self:
        source_specific = CompositionView.SOURCE_SPECIFIC in self.composition_views
        if source_specific != bool(self.source_ids):
            raise ValueError(
                "source_specific view and non-empty source_ids are required together"
            )
        if ProductRole.ROLE_UNRESOLVED in (
            self.target_identity_numerator_product_roles
        ):
            raise ValueError(
                "unresolved product role cannot enter a configured ratio"
            )
        if not set(self.regional_target_numerator_state_ids).issubset(
            self.regional_denominator_state_ids
        ):
            raise ValueError("regional numerator states must be in its denominator")
        return self

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.assessment_spec_id,
            object_version=self.assessment_spec_version,
        )


class NormalizedMetricName(StrEnum):
    TARGET_IDENTITY_FRACTION = "target_identity_fraction"
    REGIONAL_FIDELITY_FRACTION = "regional_fidelity_fraction"
    WHOLE_PRODUCT_TARGET_REGION_FRACTION = (
        "whole_product_target_region_fraction"
    )


class ChannelAssessmentState(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    NOT_ASSESSED = "not_assessed"


class TargetRegionalChannelResult(FrozenModel):
    composition_view: CompositionView
    source_id: str | None = Field(default=None, pattern=OBJECT_ID_PATTERN)
    label_level: Literal["L1", "L2", "L3"]
    denominator_scope: Literal["selected_data_view"]
    assessment_state: ChannelAssessmentState
    target_identity_fraction: RoleFraction | None = None
    regional_fidelity_fraction: RoleFraction | None = None
    whole_product_target_region_fraction: RoleFraction | None = None
    measurement_ids: dict[NormalizedMetricName, str]
    reason_codes: list[ReasonCode] = Field(
        default_factory=list,
        json_schema_extra={"uniqueItems": True},
    )

    @field_validator("reason_codes")
    @classmethod
    def reasons_are_sorted_unique(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("channel reasons must be unique and sorted")
        return value

    @model_validator(mode="after")
    def channel_is_coherent(self) -> Self:
        source_specific = self.composition_view is CompositionView.SOURCE_SPECIFIC
        if source_specific != (self.source_id is not None):
            raise ValueError("source-specific channel requires one source ID")
        if set(self.measurement_ids) != set(NormalizedMetricName):
            raise ValueError("channel must bind exactly the three normalized metrics")
        values = (
            self.target_identity_fraction,
            self.regional_fidelity_fraction,
            self.whole_product_target_region_fraction,
        )
        if self.assessment_state is ChannelAssessmentState.COMPLETE and any(
            item is None for item in values
        ):
            raise ValueError("complete channel requires all three ratios")
        if self.assessment_state is ChannelAssessmentState.NOT_ASSESSED and any(
            item is not None for item in values
        ):
            raise ValueError("not_assessed channel cannot contain a numeric ratio")
        if self.assessment_state is ChannelAssessmentState.PARTIAL and (
            self.target_identity_fraction is None
            or self.whole_product_target_region_fraction is None
            or self.regional_fidelity_fraction is not None
        ):
            raise ValueError(
                "partial channel is reserved for a zero regional denominator"
            )
        return self


class MetricArtifactBinding(FrozenModel):
    measurement_id: str = Field(min_length=1)
    metric_name: NormalizedMetricName
    composition_view: CompositionView
    source_id: str | None = Field(default=None, pattern=OBJECT_ID_PATTERN)
    label_level: Literal["L1", "L2", "L3"]
    artifact_id: str = Field(min_length=1)
    file_name: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]*\.json$")
    sha256: str = Field(pattern=SHA256_PATTERN)


class InputChecksumBindings(FrozenModel):
    product_case: str = Field(pattern=SHA256_PATTERN)
    product_definition_card: str = Field(pattern=SHA256_PATTERN)
    state_role_map: str = Field(pattern=SHA256_PATTERN)
    target_regional_assessment_spec: str = Field(pattern=SHA256_PATTERN)
    measurement_spec: str = Field(pattern=SHA256_PATTERN)
    cell_state_evidence_profile: str = Field(pattern=SHA256_PATTERN)
    qc_readiness_profile: str = Field(pattern=SHA256_PATTERN)
    biological_unit_manifest: str = Field(pattern=SHA256_PATTERN)
    biological_unit_assignment: str = Field(pattern=SHA256_PATTERN)
    annotation_vocabulary: str = Field(pattern=SHA256_PATTERN)
    reference_manifest: str = Field(pattern=SHA256_PATTERN)


class TargetRegionalEvidenceResult(FrozenModel):
    object_version: Literal["0.1.0"]
    result_id: str = Field(pattern=r"^target-regional-result:[a-f0-9]{16}$")
    tool_id: Literal["P0-03"]
    tool_version: str = Field(pattern=VERSION_PATTERN)
    product_case_ref: VersionedObjectRef
    product_definition_ref: VersionedObjectRef
    state_role_map_ref: VersionedObjectRef
    assessment_spec_ref: VersionedObjectRef
    measurement_spec_ref: VersionedObjectRef
    cell_state_profile_ref: VersionedObjectRef
    qc_profile_ref: VersionedObjectRef
    biological_unit_manifest_ref: VersionedObjectRef
    annotation_vocabulary_ref: VersionedObjectRef
    reference_manifest_ref: VersionedObjectRef
    input_sha256_by_role: InputChecksumBindings
    upstream_composition_state: Literal[
        "shadow", "not_assessed", "unavailable", "unknown", "missing"
    ]
    result_state: Literal["complete", "partial", "not_assessed"]
    channels: list[TargetRegionalChannelResult] = Field(min_length=1)
    metric_artifacts: list[MetricArtifactBinding] = Field(min_length=3)
    spatial_projection_state: Literal["not_assessed"]
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
    def result_is_coherent(self) -> Self:
        channel_keys = [
            (item.composition_view, item.source_id, item.label_level)
            for item in self.channels
        ]
        if len(channel_keys) != len(set(channel_keys)):
            raise ValueError("channel identities must be unique")
        expected_ids = {
            measurement_id
            for channel in self.channels
            for measurement_id in channel.measurement_ids.values()
        }
        artifact_ids = [item.measurement_id for item in self.metric_artifacts]
        if set(artifact_ids) != expected_ids or len(artifact_ids) != len(expected_ids):
            raise ValueError("metric artifacts must bind every measurement exactly once")
        artifact_by_measurement = {
            item.measurement_id: item for item in self.metric_artifacts
        }
        for channel in self.channels:
            for metric_name, measurement_id in channel.measurement_ids.items():
                artifact = artifact_by_measurement[measurement_id]
                if (
                    artifact.metric_name != metric_name
                    or artifact.composition_view != channel.composition_view
                    or artifact.source_id != channel.source_id
                    or artifact.label_level != channel.label_level
                ):
                    raise ValueError("measurement artifact is bound to the wrong channel")
        states = [item.assessment_state for item in self.channels]
        expected_state = (
            "complete"
            if all(item is ChannelAssessmentState.COMPLETE for item in states)
            else "not_assessed"
            if all(item is ChannelAssessmentState.NOT_ASSESSED for item in states)
            else "partial"
        )
        if self.result_state != expected_state:
            raise ValueError("result state must summarize channel states")
        expected_score = (
            ScoreState.UNAVAILABLE
            if expected_state == "not_assessed"
            else ScoreState.SHADOW
        )
        if self.score_state != expected_score:
            raise ValueError("score state must match assessment availability")
        if self.upstream_composition_state != "shadow" and expected_state != "not_assessed":
            raise ValueError("non-shadow composition cannot produce numeric ratios")
        return self


PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/target-regional-assessment-spec/v0.1": (
        TargetRegionalAssessmentSpec
    ),
    "bridge://schemas/target-regional-evidence-result/v0.1": (
        TargetRegionalEvidenceResult
    ),
}
