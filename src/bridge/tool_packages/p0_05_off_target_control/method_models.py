from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, StrictFloat, StrictInt, field_validator, model_validator

from bridge.tool_packages._configurable_contracts import ProductRole
from bridge.toolkit.contracts import FrozenModel

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


class OffTargetMethodId(StrEnum):
    COMPOSITION_EXACT = "COMP-EXACT"
    HARD_LABEL_SENSITIVITY = "COMP-HARD-SENS"
    HIERARCHICAL_BOOTSTRAP = "COMP-HBOOT"
    RARE_EXACT = "RARE-EXACT"
    RARE_SPIKE_IN = "RARE-SPIKEIN"
    RARE_SCOPIT = "RARE-SCOPIT"
    OOD_DISAGREEMENT = "OOD-DISAGREE"
    OOD_ENSEMBLE = "OOD-ENSEMBLE"


class MethodExecutionState(StrEnum):
    SUCCEEDED = "succeeded"
    NOT_ASSESSED = "not_assessed"


class OODChannelState(StrEnum):
    SUPPORTED = "supported"
    UNKNOWN = "unknown"
    OOD = "ood"
    UNAVAILABLE = "unavailable"


class OODDecisionState(StrEnum):
    SUPPORTED = "supported"
    UNKNOWN = "unknown"
    OOD = "ood"
    NOT_ASSESSED = "not_assessed"


class UnitStateObservation(FrozenModel):
    state_id: str = Field(pattern=OBJECT_ID_PATTERN)
    soft_mass: StrictFloat = Field(ge=0.0)
    hard_count: StrictInt = Field(ge=0)


class UnitUnknownObservation(FrozenModel):
    reason_id: str = Field(pattern=REASON_ID_PATTERN)
    soft_mass: StrictFloat = Field(ge=0.0)
    hard_count: StrictInt = Field(ge=0)


class AnalysisUnitComposition(FrozenModel):
    analysis_unit_ref: str = Field(min_length=1)
    independence_group_ref: str = Field(min_length=1)
    denominator_count: StrictInt = Field(gt=0)
    state_observations: list[UnitStateObservation]
    unknown_observations: list[UnitUnknownObservation]

    @model_validator(mode="after")
    def observations_close_to_denominator(self) -> Self:
        _unique([item.state_id for item in self.state_observations], "unit state IDs")
        _unique(
            [item.reason_id for item in self.unknown_observations],
            "unit unknown reason IDs",
        )
        hard_count = sum(
            item.hard_count
            for item in [*self.state_observations, *self.unknown_observations]
        )
        if hard_count != self.denominator_count:
            raise ValueError("unit hard counts must equal denominator_count")
        soft_mass = math.fsum(
            item.soft_mass
            for item in [*self.state_observations, *self.unknown_observations]
        )
        if not math.isclose(
            soft_mass,
            float(self.denominator_count),
            rel_tol=0.0,
            abs_tol=max(1e-9, self.denominator_count * 1e-9),
        ):
            raise ValueError("unit soft mass must equal denominator_count")
        return self


class SpikeInTrial(FrozenModel):
    state_id: str = Field(pattern=OBJECT_ID_PATTERN)
    independence_group_ref: str = Field(min_length=1)
    spike_fraction: StrictFloat = Field(ge=0.0, le=1.0)
    n_observations: StrictInt = Field(gt=0)
    expected_spike_count: StrictInt = Field(ge=0)
    recovered_spike_count: StrictInt = Field(ge=0)
    false_positive_count: StrictInt = Field(ge=0)

    @model_validator(mode="after")
    def counts_are_coherent(self) -> Self:
        if self.expected_spike_count > self.n_observations:
            raise ValueError("expected spike count exceeds trial denominator")
        if self.recovered_spike_count > self.expected_spike_count:
            raise ValueError("recovered spike count exceeds expected spike count")
        if self.false_positive_count > self.n_observations - self.expected_spike_count:
            raise ValueError("false positives exceed background observations")
        expected_fraction = self.expected_spike_count / self.n_observations
        if not math.isclose(
            self.spike_fraction,
            expected_fraction,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError("spike fraction must equal expected count / denominator")
        return self


class OODChannelRecord(FrozenModel):
    channel_id: str = Field(pattern=OBJECT_ID_PATTERN)
    source_family_id: str = Field(pattern=OBJECT_ID_PATTERN)
    state: OODChannelState
    reason_id: str | None = Field(default=None, pattern=REASON_ID_PATTERN)


class OffTargetMethodInput(FrozenModel):
    object_version: Literal["0.1.0"]
    method_input_id: str = Field(pattern=r"^off-target-method-input:[A-Za-z0-9._:-]+$")
    method_input_version: str = Field(pattern=VERSION_PATTERN)
    product_case_ref: str = Field(min_length=1)
    product_case_sha256: str = Field(pattern=SHA256_PATTERN)
    cell_state_profile_id: str = Field(min_length=1)
    cell_state_profile_sha256: str = Field(pattern=SHA256_PATTERN)
    evidence_bundle_ref: str = Field(min_length=1)
    evidence_bundle_sha256: str = Field(pattern=SHA256_PATTERN)
    biological_unit_manifest_ref: str = Field(min_length=1)
    biological_unit_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    analysis_units: list[AnalysisUnitComposition]
    spike_in_trials: list[SpikeInTrial] = Field(default_factory=list)
    ood_channels: list[OODChannelRecord] = Field(default_factory=list)
    created_at: datetime

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @model_validator(mode="after")
    def identities_are_unique(self) -> Self:
        _unique(
            [item.analysis_unit_ref for item in self.analysis_units],
            "analysis unit refs",
        )
        _unique([item.channel_id for item in self.ood_channels], "OOD channel IDs")
        return self


class RarePlanningTarget(FrozenModel):
    state_id: str = Field(pattern=OBJECT_ID_PATTERN)
    expected_frequency_fraction: StrictFloat = Field(gt=0.0, le=1.0)
    desired_detection_probability: StrictFloat = Field(gt=0.0, lt=1.0)


class OODDecisionRule(FrozenModel):
    channel_state: Literal["supported", "unknown", "ood"]
    output_state: Literal["supported", "unknown", "ood"]
    minimum_distinct_source_families: StrictInt = Field(gt=0)
    reason_id: str = Field(pattern=REASON_ID_PATTERN)


class OffTargetMethodSpec(FrozenModel):
    object_version: Literal["0.1.0"]
    method_spec_id: str = Field(pattern=r"^off-target-method-spec:[A-Za-z0-9._:-]+$")
    method_spec_version: str = Field(pattern=VERSION_PATTERN)
    status: Literal["candidate"]
    selected_method_ids: list[OffTargetMethodId] = Field(min_length=1)
    confidence_level: StrictFloat = Field(gt=0.5, lt=1.0)
    bootstrap_replicates: StrictInt = Field(ge=100, le=100_000)
    minimum_spike_in_detection_probability: StrictFloat = Field(gt=0.0, lt=1.0)
    planning_targets: list[RarePlanningTarget] = Field(default_factory=list)
    ood_decision_rules: list[OODDecisionRule] = Field(default_factory=list)
    active: bool

    @model_validator(mode="after")
    def selections_are_coherent(self) -> Self:
        _unique(self.selected_method_ids, "selected method IDs")
        _unique([item.state_id for item in self.planning_targets], "planning state IDs")
        if (
            OffTargetMethodId.RARE_SCOPIT in self.selected_method_ids
            and not self.planning_targets
        ):
            raise ValueError("RARE-SCOPIT requires planning targets")
        if (
            OffTargetMethodId.OOD_ENSEMBLE in self.selected_method_ids
            and not self.ood_decision_rules
        ):
            raise ValueError("OOD-ENSEMBLE requires ordered decision rules")
        return self


class MethodExecutionRecord(FrozenModel):
    method_id: OffTargetMethodId
    method_ref: str = Field(pattern=r"^METHOD-[A-Z0-9-]+$")
    implementation: str = Field(min_length=1)
    execution_state: MethodExecutionState
    package_versions: dict[str, str]
    reason_codes: list[str]


class ProportionInterval(FrozenModel):
    scope_id: str = Field(min_length=1)
    method_id: OffTargetMethodId
    numerator_kind: Literal["hard_count", "soft_mass"]
    estimate: StrictFloat | None
    lower: StrictFloat | None
    upper: StrictFloat | None
    confidence_level: StrictFloat
    n_observations: StrictInt
    n_independence_groups: StrictInt
    assessment_state: Literal["available", "not_assessed"]
    reason_codes: list[str]


class HardSoftSensitivityRecord(FrozenModel):
    product_role: ProductRole
    soft_fraction: StrictFloat
    hard_fraction: StrictFloat
    hard_minus_soft: StrictFloat


class SpikeInCurvePoint(FrozenModel):
    spike_fraction: StrictFloat
    trial_count: StrictInt
    detected_trial_count: StrictInt
    detection_rate: StrictFloat
    detection_lower: StrictFloat
    detection_upper: StrictFloat


class SpikeInCalibrationRecord(FrozenModel):
    state_id: str = Field(pattern=OBJECT_ID_PATTERN)
    candidate_detection_limit_fraction: StrictFloat | None
    false_positive_fraction: StrictFloat | None
    assessment_state: Literal["available", "not_assessed"]
    curve: list[SpikeInCurvePoint]
    reason_codes: list[str]


class RarePlanningRecord(FrozenModel):
    state_id: str = Field(pattern=OBJECT_ID_PATTERN)
    expected_frequency_fraction: StrictFloat
    desired_detection_probability: StrictFloat
    required_observations: StrictInt

    assumption_codes: list[str]


class OODDisagreementRecord(FrozenModel):
    assessed_channel_count: StrictInt
    distinct_source_family_count: StrictInt
    family_states: dict[str, str]
    disagreement: bool | None
    assessment_state: Literal["available", "not_assessed"]
    reason_codes: list[str]


class OODEnsembleRecord(FrozenModel):
    decision_state: OODDecisionState
    distinct_source_family_count: StrictInt
    family_vote_counts: dict[str, StrictInt]
    matched_reason_id: str | None
    assessment_state: Literal["available", "not_assessed"]
    reason_codes: list[str]


class OffTargetMethodBundle(FrozenModel):
    object_version: Literal["0.1.0"]
    bundle_id: str = Field(pattern=r"^off-target-method-bundle:[A-Za-z0-9._:-]+$")
    bundle_version: Literal["0.1.0"]
    tool_id: Literal["P0-05"]
    tool_version: str
    method_spec_sha256: str = Field(pattern=SHA256_PATTERN)
    method_input_sha256: str = Field(pattern=SHA256_PATTERN)
    biological_unit_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    analysis_unit_refs: list[str]
    independence_group_refs: list[str]
    executions: list[MethodExecutionRecord]
    composition_intervals: list[ProportionInterval]
    hard_soft_sensitivity: list[HardSoftSensitivityRecord]
    rare_intervals: list[ProportionInterval]
    spike_in_calibrations: list[SpikeInCalibrationRecord]
    planning_records: list[RarePlanningRecord]
    ood_disagreement: OODDisagreementRecord | None
    ood_ensemble: OODEnsembleRecord | None
    evidence_state: Literal["shadow"]
    score_state: Literal["unavailable"]
    domain_score: None = None
    created_at: datetime

    _created_at_utc = field_validator("created_at")(_aware_utc)


PUBLIC_METHOD_SCHEMA_MODELS = {
    "bridge://schemas/off-target-method-spec/v0.1": OffTargetMethodSpec,
    "bridge://schemas/off-target-method-input/v0.1": OffTargetMethodInput,
    "bridge://schemas/off-target-method-bundle/v0.1": OffTargetMethodBundle,
}
