from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal, Self

from pydantic import (
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    field_validator,
    model_validator,
)

from bridge.tool_packages._configurable_contracts import (
    ProductRole,
    StateRoleMap,
    VersionedObjectRef,
)
from bridge.tool_packages.p0_05_off_target_control.method_models import (
    PUBLIC_METHOD_SCHEMA_MODELS,
)
from bridge.toolkit.contracts import EvidenceState, FrozenModel

OBJECT_ID_PATTERN = r"^[A-Za-z][A-Za-z0-9._:-]*$"
VERSION_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"
REASON_ID_PATTERN = r"^[a-z][a-z0-9_]*$"


def _unique(values: list[object], field: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must contain unique values")


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("created_at must include a timezone")
    return value.astimezone(timezone.utc)


class CoverageState(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    NOT_ASSESSED = "not_assessed"


class AssessmentState(StrEnum):
    AVAILABLE = "available"
    NOT_ASSESSED = "not_assessed"


class ExclusionState(StrEnum):
    OBSERVED = "observed"
    CANNOT_EXCLUDE = "cannot_exclude"


class RareDetectionState(StrEnum):
    DETECTED = "detected"
    NOT_DETECTED_ABOVE_LOD = "not_detected_above_lod"
    CANNOT_EXCLUDE = "cannot_exclude"
    NOT_ASSESSED = "not_assessed"


def role_projection_evidence_state(state: AssessmentState) -> EvidenceState:
    return {
        AssessmentState.AVAILABLE: EvidenceState.INFERRED,
        AssessmentState.NOT_ASSESSED: EvidenceState.UNAVAILABLE,
    }[state]


def unknown_projection_evidence_state(state: CoverageState) -> EvidenceState:
    return {
        CoverageState.COMPLETE: EvidenceState.UNKNOWN,
        CoverageState.PARTIAL: EvidenceState.UNKNOWN,
        CoverageState.NOT_ASSESSED: EvidenceState.UNAVAILABLE,
    }[state]


def rare_projection_evidence_state(state: RareDetectionState) -> EvidenceState:
    return {
        RareDetectionState.DETECTED: EvidenceState.INFERRED,
        RareDetectionState.NOT_DETECTED_ABOVE_LOD: EvidenceState.NEGATIVE,
        RareDetectionState.CANNOT_EXCLUDE: EvidenceState.UNKNOWN,
        RareDetectionState.NOT_ASSESSED: EvidenceState.UNAVAILABLE,
    }[state]


class RareStateRule(FrozenModel):
    state_id: str = Field(pattern=OBJECT_ID_PATTERN)
    max_validated_detection_limit_fraction: StrictFloat = Field(ge=0.0, le=1.0)
    max_false_positive_fraction: StrictFloat = Field(ge=0.0, le=1.0)
    missing_calibration_state: Literal["cannot_exclude", "not_assessed"]


class OffTargetAssessmentSpec(FrozenModel):
    object_version: Literal["0.1.0"]
    assessment_spec_id: str = Field(
        pattern=r"^off-target-assessment-spec:[A-Za-z0-9._:-]+$"
    )
    spec_version: str = Field(pattern=VERSION_PATTERN)
    product_definition_ref: VersionedObjectRef
    state_role_map_ref: VersionedObjectRef
    state_role_map_sha256: str = Field(pattern=SHA256_PATTERN)
    primary_denominator_id: str = Field(pattern=OBJECT_ID_PATTERN)
    allowed_unknown_reason_ids: list[str]
    rare_state_rules: list[RareStateRule]
    active: bool

    @field_validator("allowed_unknown_reason_ids")
    @classmethod
    def unknown_reasons_are_unique(cls, value: list[str]) -> list[str]:
        _unique(value, "allowed_unknown_reason_ids")
        if any(not reason or not reason.replace("_", "").isalnum() for reason in value):
            raise ValueError("unknown reason IDs must be stable snake-case identifiers")
        return value

    @field_validator("rare_state_rules")
    @classmethod
    def rare_rules_are_unique(
        cls, value: list[RareStateRule]
    ) -> list[RareStateRule]:
        _unique([item.state_id for item in value], "rare state rules")
        return value

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.assessment_spec_id,
            object_version=self.spec_version,
        )


class OffTargetDenominator(FrozenModel):
    denominator_id: str = Field(pattern=OBJECT_ID_PATTERN)
    n_observations: StrictInt = Field(gt=0)
    total_soft_mass: StrictFloat = Field(gt=0.0)
    unit: Literal["cells"]


class StateObservation(FrozenModel):
    state_id: str = Field(pattern=OBJECT_ID_PATTERN)
    soft_mass: StrictFloat = Field(ge=0.0)
    observed_count: StrictInt = Field(ge=0)


class UnknownObservation(FrozenModel):
    reason_id: str = Field(pattern=REASON_ID_PATTERN)
    soft_mass: StrictFloat = Field(ge=0.0)
    observed_count: StrictInt = Field(ge=0)


class RareStateCalibration(FrozenModel):
    state_id: str = Field(pattern=OBJECT_ID_PATTERN)
    calibration_ref: str = Field(pattern=OBJECT_ID_PATTERN)
    calibration_sha256: str = Field(pattern=SHA256_PATTERN)
    validated_detection_limit_fraction: StrictFloat = Field(ge=0.0, le=1.0)
    false_positive_fraction: StrictFloat = Field(ge=0.0, le=1.0)
    zero_observation_upper_bound_fraction: StrictFloat = Field(ge=0.0, le=1.0)


class OffTargetEvidenceBundle(FrozenModel):
    object_version: Literal["0.1.0"]
    bundle_id: str = Field(pattern=r"^off-target-evidence-bundle:[A-Za-z0-9._:-]+$")
    bundle_version: str = Field(pattern=VERSION_PATTERN)
    product_case_ref: str = Field(min_length=1)
    product_case_sha256: str = Field(pattern=SHA256_PATTERN)
    product_definition_ref: str = Field(min_length=1)
    product_definition_sha256: str = Field(pattern=SHA256_PATTERN)
    cell_state_profile_id: str = Field(min_length=1)
    cell_state_profile_sha256: str = Field(pattern=SHA256_PATTERN)
    denominator: OffTargetDenominator
    composition_coverage_state: CoverageState
    state_observations: list[StateObservation]
    unknown_coverage_state: CoverageState
    unknown_observations: list[UnknownObservation]
    rare_state_calibrations: list[RareStateCalibration]
    created_at: datetime

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @field_validator("state_observations")
    @classmethod
    def state_rows_are_unique(
        cls, value: list[StateObservation]
    ) -> list[StateObservation]:
        _unique([item.state_id for item in value], "state observations")
        return value

    @field_validator("unknown_observations")
    @classmethod
    def unknown_rows_are_unique(
        cls, value: list[UnknownObservation]
    ) -> list[UnknownObservation]:
        _unique([item.reason_id for item in value], "unknown observations")
        return value

    @field_validator("rare_state_calibrations")
    @classmethod
    def calibrations_are_unique(
        cls, value: list[RareStateCalibration]
    ) -> list[RareStateCalibration]:
        _unique([item.state_id for item in value], "rare state calibrations")
        return value

    @model_validator(mode="after")
    def complete_composition_matches_denominator(self) -> Self:
        if self.composition_coverage_state is CoverageState.COMPLETE:
            soft_mass = math.fsum(
                item.soft_mass
                for item in [*self.state_observations, *self.unknown_observations]
            )
            tolerance = max(1e-9, self.denominator.total_soft_mass * 1e-9)
            if not math.isclose(
                soft_mass,
                self.denominator.total_soft_mass,
                rel_tol=0.0,
                abs_tol=tolerance,
            ):
                raise ValueError(
                    "complete composition soft mass must equal the declared denominator"
                )
            hard_count = sum(
                item.observed_count
                for item in [*self.state_observations, *self.unknown_observations]
            )
            if hard_count != self.denominator.n_observations:
                raise ValueError(
                    "complete composition counts must equal the declared denominator"
                )
        return self

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.bundle_id,
            object_version=self.bundle_version,
        )


class RoleCompositionRecord(FrozenModel):
    product_role: ProductRole
    soft_mass: StrictFloat
    observed_count: StrictInt
    fraction: StrictFloat | None
    assessment_state: AssessmentState
    exclusion_state: ExclusionState


class UnknownReasonRecord(FrozenModel):
    reason_id: str = Field(pattern=REASON_ID_PATTERN)
    soft_mass: StrictFloat
    observed_count: StrictInt
    fraction: StrictFloat | None


class UnknownProfile(FrozenModel):
    coverage_state: CoverageState
    soft_mass: StrictFloat
    observed_count: StrictInt
    fraction: StrictFloat | None
    exclusion_state: ExclusionState
    reasons: list[UnknownReasonRecord]


class RareStateRecord(FrozenModel):
    state_id: str = Field(pattern=OBJECT_ID_PATTERN)
    observed_count: StrictInt | None
    soft_fraction: StrictFloat | None
    detection_state: RareDetectionState
    calibration_ref: str | None = Field(default=None, pattern=OBJECT_ID_PATTERN)
    calibration_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    validated_detection_limit_fraction: StrictFloat | None = None
    false_positive_fraction: StrictFloat | None = None
    zero_observation_upper_bound_fraction: StrictFloat | None = None
    reason_codes: list[str]


class OffTargetMeasurementArtifactBinding(FrozenModel):
    measurement_id: str = Field(min_length=1)
    metric_name: Literal[
        "off_target_role_composition",
        "off_target_identity_unknown",
        "off_target_rare_state_detection",
    ]
    record_scope: Literal["role", "identity_unknown", "rare_state"]
    record_id: str = Field(pattern=OBJECT_ID_PATTERN)
    evidence_state: EvidenceState
    artifact_id: str = Field(min_length=1)
    file_name: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]*\.json$")
    sha256: str = Field(pattern=SHA256_PATTERN)


class OffTargetControlProfile(FrozenModel):
    object_version: Literal["0.1.0"]
    profile_id: str = Field(pattern=r"^off-target-control:[A-Za-z0-9._:-]+$")
    profile_version: Literal["0.1.0"]
    tool_id: Literal["P0-05"]
    tool_version: str
    product_case_ref: str
    product_case_sha256: str = Field(pattern=SHA256_PATTERN)
    product_definition_ref: str
    product_definition_sha256: str = Field(pattern=SHA256_PATTERN)
    state_role_map_ref: str
    state_role_map_sha256: str = Field(pattern=SHA256_PATTERN)
    assessment_spec_ref: str
    assessment_spec_sha256: str = Field(pattern=SHA256_PATTERN)
    cell_state_profile_id: str
    cell_state_profile_sha256: str = Field(pattern=SHA256_PATTERN)
    evidence_bundle_ref: str
    evidence_bundle_sha256: str = Field(pattern=SHA256_PATTERN)
    primary_denominator: OffTargetDenominator
    role_composition: list[RoleCompositionRecord]
    unknown_profile: UnknownProfile
    rare_state_profile: list[RareStateRecord]
    evidence_state: Literal["shadow"]
    score_state: Literal["unavailable"]
    domain_score: None = None
    reason_codes: list[str]
    created_at: datetime

    _created_at_utc = field_validator("created_at")(_aware_utc)


class OffTargetControlProfileV2(OffTargetControlProfile):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {
                            "measurement_projection_state": {
                                "const": "not_requested"
                            }
                        },
                        "required": ["measurement_projection_state"],
                    },
                    "then": {
                        "required": [
                            "measurement_artifacts",
                        ],
                        "properties": {
                            "measurement_spec_ref": {"type": "null"},
                            "measurement_spec_sha256": {"type": "null"},
                            "measurement_artifacts": {"maxItems": 0},
                        },
                    },
                },
                {
                    "if": {
                        "properties": {
                            "measurement_projection_state": {"const": "available"}
                        },
                        "required": ["measurement_projection_state"],
                    },
                    "then": {
                        "required": [
                            "measurement_spec_ref",
                            "measurement_spec_sha256",
                            "measurement_artifacts",
                        ],
                        "properties": {
                            "measurement_spec_ref": {"not": {"type": "null"}},
                            "measurement_spec_sha256": {
                                "not": {"type": "null"}
                            },
                            "measurement_artifacts": {"minItems": 1},
                        },
                    },
                },
            ]
        }
    )

    object_version: Literal["0.2.0"]
    profile_version: Literal["0.2.0"]
    measurement_projection_state: Literal["not_requested", "available"]
    measurement_spec_ref: VersionedObjectRef | None = None
    measurement_spec_sha256: str | None = Field(
        default=None, pattern=SHA256_PATTERN
    )
    measurement_artifacts: list[OffTargetMeasurementArtifactBinding]

    @model_validator(mode="after")
    def measurement_projection_is_coherent(self) -> Self:
        measurement_ids = [item.measurement_id for item in self.measurement_artifacts]
        artifact_ids = [item.artifact_id for item in self.measurement_artifacts]
        file_names = [item.file_name for item in self.measurement_artifacts]
        binding_keys = [
            (item.record_scope, item.record_id)
            for item in self.measurement_artifacts
        ]
        for values, name in (
            (measurement_ids, "measurement IDs"),
            (artifact_ids, "measurement artifact IDs"),
            (file_names, "measurement artifact file names"),
            (binding_keys, "projected source records"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must be unique")
        if self.measurement_projection_state == "not_requested":
            if (
                self.measurement_spec_ref is not None
                or self.measurement_spec_sha256 is not None
                or self.measurement_artifacts
            ):
                raise ValueError(
                    "not-requested projection cannot bind a spec or measurements"
                )
            return self
        if (
            self.measurement_spec_ref is None
            or self.measurement_spec_sha256 is None
        ):
            raise ValueError("available projection requires a measurement spec")
        expected = {
            *(("role", item.product_role.value) for item in self.role_composition),
            ("identity_unknown", "identity-unknown"),
            *(("rare_state", item.state_id) for item in self.rare_state_profile),
        }
        if set(binding_keys) != expected:
            raise ValueError(
                "available projection must bind every role, unknown and rare record"
            )
        expected_metric_by_scope = {
            "role": "off_target_role_composition",
            "identity_unknown": "off_target_identity_unknown",
            "rare_state": "off_target_rare_state_detection",
        }
        if any(
            item.metric_name != expected_metric_by_scope[item.record_scope]
            for item in self.measurement_artifacts
        ):
            raise ValueError("measurement metric must match its source record scope")
        expected_evidence_by_record = {
            **{
                ("role", item.product_role.value): role_projection_evidence_state(
                    item.assessment_state
                )
                for item in self.role_composition
            },
            ("identity_unknown", "identity-unknown"): unknown_projection_evidence_state(
                self.unknown_profile.coverage_state
            ),
            **{
                ("rare_state", item.state_id): rare_projection_evidence_state(
                    item.detection_state
                )
                for item in self.rare_state_profile
            },
        }
        if any(
            item.evidence_state
            is not expected_evidence_by_record[
                (item.record_scope, item.record_id)
            ]
            for item in self.measurement_artifacts
        ):
            raise ValueError(
                "measurement evidence must match its source record state"
            )
        return self


PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/state-role-map/v0.1": StateRoleMap,
    "bridge://schemas/off-target-assessment-spec/v0.1": OffTargetAssessmentSpec,
    "bridge://schemas/off-target-evidence-bundle/v0.1": OffTargetEvidenceBundle,
    "bridge://schemas/off-target-control-profile/v0.1": OffTargetControlProfile,
    "bridge://schemas/off-target-control-profile/v0.2": OffTargetControlProfileV2,
    **PUBLIC_METHOD_SCHEMA_MODELS,
}
