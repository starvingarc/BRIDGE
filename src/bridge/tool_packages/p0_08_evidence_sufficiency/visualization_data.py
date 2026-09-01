from __future__ import annotations

import hashlib
from enum import StrEnum
from importlib.resources import files
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_08_evidence_sufficiency.models import (
    EvidenceSufficiencyRunResultV2,
    GateReasonSpec,
    P0DomainId,
    ReasonCodeCatalogV2,
)
from bridge.toolkit.contracts import EvidenceState, FrozenModel
from bridge.toolkit.visualization import VisualizationArtifactV2


EVIDENCE_SUFFICIENCY_VISUALIZATION_DATA_SCHEMA_REF = (
    "bridge://schemas/evidence-sufficiency-visualization-data/v0.1"
)
P008_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF = (
    "bridge://schemas/p0-08-visualization-artifact-set/v0.1"
)
DOMAIN_AXES_COMPONENT_REF = "bridge.evidence-sufficiency.domain-axes@0.1.0"
INTERPRETATION_REQUIREMENTS_COMPONENT_REF = (
    "bridge.evidence-sufficiency.interpretation-requirements@0.1.0"
)
MEASUREMENT_STATES_COMPONENT_REF = (
    "bridge.evidence-sufficiency.measurement-states@0.1.0"
)
P008_COMPONENT_REFS = (
    DOMAIN_AXES_COMPONENT_REF,
    INTERPRETATION_REQUIREMENTS_COMPONENT_REF,
    MEASUREMENT_STATES_COMPONENT_REF,
)

_SHA256 = r"^[0-9a-f]{64}$"
_RECORD_ID = r"^[a-z][a-z0-9_.-]+$"
_PROFILE_REF = r"^evidence-sufficiency-profile:[a-f0-9]{16}:[A-Za-z0-9._:-]+$"
_SUMMARY_REASON_CODES = {
    "raw_evidence_gate_sufficient",
    "raw_evidence_gate_limited",
    "raw_evidence_gate_insufficient",
    "raw_evidence_gate_not_assessed",
    "p0_score_contract_unavailable",
    "score_contract_ignored_current_release",
    "evidence_family_duplicate_collapsed",
}
_REVIEW_REQUIRED_CODES = {"evidence_family_conflict_requires_review"}


class EvidenceAxisId(StrEnum):
    INPUT_DATA = "input_data"
    METHOD_VALIDATION = "method_validation"
    REFERENCE_PRIOR = "reference_prior"
    INTERPRETATION = "interpretation"


class RequirementClass(StrEnum):
    MISSING = "missing"
    BLOCKING = "blocking"
    LIMITING = "limiting"
    REVIEW_REQUIRED = "review_required"


def _sorted_unique(values: list[str], field_name: str) -> list[str]:
    if values != sorted(set(values)):
        raise ValueError(f"{field_name} must be sorted and unique")
    return values


class _VisualizationRecord(FrozenModel):
    record_id: str = Field(pattern=_RECORD_ID)
    profile_ref: str = Field(pattern=_PROFILE_REF)
    evidence_ids: list[str] = Field(min_length=1)
    evidence_state: EvidenceState
    scientific_status: Literal["candidate"] = "candidate"
    missingness: Literal["available", "unavailable"]
    applicability: Literal["applicable", "partially_applicable", "not_assessed"]
    reason_codes: list[str] = Field(default_factory=list)

    @field_validator("evidence_ids", "reason_codes")
    @classmethod
    def set_like_fields_are_sorted(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)


class DomainVisualizationBinding(FrozenModel):
    profile_ref: str = Field(pattern=_PROFILE_REF)
    domain_id: P0DomainId | None = None
    domain_label: str = Field(min_length=1)
    measurement_spec_ref: str | None = None
    measurement_result_reference_count: int = Field(ge=0)
    source_evidence_refs: list[str]
    evidence_family_ids: list[str]

    @field_validator("source_evidence_refs", "evidence_family_ids")
    @classmethod
    def set_like_fields_are_sorted(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)


class DomainAxisRecord(_VisualizationRecord):
    component_ref: Literal[DOMAIN_AXES_COMPONENT_REF] = DOMAIN_AXES_COMPONENT_REF
    axis_id: EvidenceAxisId
    source_state: str = Field(min_length=1)
    scoped_state_label: str = Field(min_length=1)
    scope_basis: Literal[
        "bound_measurement_spec_input_requirements",
        "declared_method_context_and_validation_records",
        "declared_reference_and_prior_context",
        "current_candidate_interpretation_rules",
    ]


class InterpretationRequirementRecord(_VisualizationRecord):
    component_ref: Literal[INTERPRETATION_REQUIREMENTS_COMPONENT_REF] = (
        INTERPRETATION_REQUIREMENTS_COMPONENT_REF
    )
    reason_code: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    requirement_class: RequirementClass
    catalog_axis: Literal[
        "contract", "data", "model", "prior", "gate", "score", "provenance"
    ]
    catalog_severity: Literal["info", "warning", "limiting", "blocking", "missing"]


class MeasurementStateRecord(_VisualizationRecord):
    component_ref: Literal[MEASUREMENT_STATES_COMPONENT_REF] = (
        MEASUREMENT_STATES_COMPONENT_REF
    )
    measurement_evidence_state: EvidenceState
    reference_count: int = Field(ge=0)
    count_semantics: Literal[
        "domain_profile_measurement_result_references"
    ] = "domain_profile_measurement_result_references"
    independent_evidence_count: Literal[False] = False
    zero_semantics: Literal[
        "no_bound_measurement_result_reference_in_this_domain_profile"
    ] = "no_bound_measurement_result_reference_in_this_domain_profile"


class ReasonDisplayRecord(FrozenModel):
    reason_code: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    axis: Literal[
        "contract", "data", "model", "prior", "gate", "score", "provenance"
    ]
    severity: Literal["info", "warning", "limiting", "blocking", "missing"]
    description: str = Field(min_length=1)
    remediation: str = Field(min_length=1)


class EvidenceSufficiencyVisualizationDataV1(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[EVIDENCE_SUFFICIENCY_VISUALIZATION_DATA_SCHEMA_REF] = (
        EVIDENCE_SUFFICIENCY_VISUALIZATION_DATA_SCHEMA_REF
    )
    visualization_profile_id: str = Field(
        pattern=r"^evidence-sufficiency-visualization:[a-f0-9]{16}$"
    )
    producer_tool_id: Literal["P0-08"] = "P0-08"
    producer_tool_version: str = Field(min_length=1)
    producer_run_ref: str = Field(pattern=r"^run:run-[a-f0-9]{16}$")
    source_result_ref: str = Field(
        pattern=r"^evidence-sufficiency-result:[a-f0-9]{16}$"
    )
    source_result_version: Literal["0.2.0"] = "0.2.0"
    source_result_sha256: str = Field(pattern=_SHA256)
    gate_rule_spec_ref: Literal["GATE-EVIDENCE-SUFFICIENCY-v0.2"]
    reason_catalog_id: Literal["BRIDGE-REASON-CODE-CATALOG-v0.2"]
    reason_catalog_version: Literal["0.2.0"]
    reason_catalog_schema_ref: Literal[
        "bridge://schemas/evidence-sufficiency-reason-code-catalog/v0.2"
    ]
    reason_catalog_sha256: str = Field(pattern=_SHA256)
    domain_bindings: list[DomainVisualizationBinding] = Field(
        min_length=1, max_length=5
    )
    axis_records: list[DomainAxisRecord] = Field(min_length=4, max_length=20)
    requirement_records: list[InterpretationRequirementRecord]
    measurement_state_records: list[MeasurementStateRecord] = Field(
        min_length=8, max_length=40
    )
    reason_display_records: list[ReasonDisplayRecord]
    source_evidence_refs: list[str]
    evidence_ids: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    measurement_reference_counts_are_not_independent_evidence: Literal[True] = True
    evidence_family_ids_are_not_independent_evidence: Literal[True] = True
    domain_score: None = None

    @field_validator("reason_catalog_sha256")
    @classmethod
    def reason_catalog_hash_matches_packaged_bytes(cls, value: str) -> str:
        expected_hash, _ = _packaged_reason_catalog()
        if value != expected_hash:
            raise ValueError(
                "reason_catalog_sha256 must match the packaged v0.2 catalog"
            )
        return value

    @field_validator("source_evidence_refs", "evidence_ids", "limitations")
    @classmethod
    def set_like_fields_are_sorted(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)

    @model_validator(mode="after")
    def records_are_complete_and_do_not_invent_causality(self) -> Self:
        profile_refs = [item.profile_ref for item in self.domain_bindings]
        if len(profile_refs) != len(set(profile_refs)):
            raise ValueError("domain bindings must have unique profile refs")
        declared_domains = [
            binding.domain_id
            for binding in self.domain_bindings
            if binding.domain_id is not None
        ]
        if len(declared_domains) != len(set(declared_domains)):
            raise ValueError("declared domains must be unique")
        scope_by_axis = {
            EvidenceAxisId.INPUT_DATA: "bound_measurement_spec_input_requirements",
            EvidenceAxisId.METHOD_VALIDATION: "declared_method_context_and_validation_records",
            EvidenceAxisId.REFERENCE_PRIOR: "declared_reference_and_prior_context",
            EvidenceAxisId.INTERPRETATION: "current_candidate_interpretation_rules",
        }
        for position, profile_ref in enumerate(profile_refs, start=1):
            binding = self.domain_bindings[position - 1]
            if binding.domain_label != _domain_label(binding.domain_id, position):
                raise ValueError("domain label must match the declared domain")
            if binding.domain_id is not None and not profile_ref.endswith(
                f":{binding.domain_id.value}"
            ):
                raise ValueError("profile reference suffix must match the domain")
            axes = [
                item.axis_id
                for item in self.axis_records
                if item.profile_ref == profile_ref
            ]
            if axes != list(EvidenceAxisId):
                raise ValueError("each profile requires four fixed axes in order")
            for record in (
                item for item in self.axis_records if item.profile_ref == profile_ref
            ):
                try:
                    expected_label = _scoped_state_label(
                        record.axis_id, record.source_state
                    )
                except ValueError as exc:
                    raise ValueError("axis source state is not supported") from exc
                unavailable = record.source_state == "not_assessed"
                if (
                    record.scoped_state_label != expected_label
                    or record.scope_basis != scope_by_axis[record.axis_id]
                    or record.evidence_state
                    != (
                        EvidenceState.UNAVAILABLE
                        if unavailable
                        else EvidenceState.INFERRED
                    )
                    or record.missingness
                    != ("unavailable" if unavailable else "available")
                    or record.applicability
                    != ("not_assessed" if unavailable else "applicable")
                ):
                    raise ValueError("axis record fields are semantically inconsistent")
            states = [
                item.measurement_evidence_state
                for item in self.measurement_state_records
                if item.profile_ref == profile_ref
            ]
            if states != list(EvidenceState):
                raise ValueError("each profile requires all eight evidence states")
            binding = next(
                item for item in self.domain_bindings if item.profile_ref == profile_ref
            )
            total = sum(
                item.reference_count
                for item in self.measurement_state_records
                if item.profile_ref == profile_ref
            )
            if total != binding.measurement_result_reference_count:
                raise ValueError("measurement-state counts must match profile refs")
        records = [
            *self.axis_records,
            *self.requirement_records,
            *self.measurement_state_records,
        ]
        if not {item.profile_ref for item in records} <= set(profile_refs):
            raise ValueError("visualization records must bind declared profiles")
        requirements = [
            (item.profile_ref, item.reason_code) for item in self.requirement_records
        ]
        if len(requirements) != len(set(requirements)):
            raise ValueError("root requirements must be unique per profile")
        if any(code in _SUMMARY_REASON_CODES for _, code in requirements):
            raise ValueError("summary reasons cannot become root requirements")
        displays = {item.reason_code: item for item in self.reason_display_records}
        if len(displays) != len(self.reason_display_records):
            raise ValueError("reason displays must have unique codes")
        if set(displays) != {code for _, code in requirements}:
            raise ValueError("reason displays must cover root requirements exactly")
        expected_hash, catalog = _packaged_reason_catalog()
        if self.reason_catalog_sha256 != expected_hash:
            raise ValueError("reason catalog hash drifted during validation")
        catalog_by_code = {item.code: item for item in catalog.reasons}
        for code, display in displays.items():
            expected = catalog_by_code.get(code)
            if expected is None:
                raise ValueError(f"reason is absent from packaged catalog: {code}")
            if (
                display.axis != expected.axis
                or display.severity != expected.severity
                or display.description != expected.description
                or display.remediation != expected.remediation
            ):
                raise ValueError(f"reason display differs from catalog: {code}")
        for requirement in self.requirement_records:
            display = displays[requirement.reason_code]
            expected_class = (
                RequirementClass.REVIEW_REQUIRED
                if requirement.reason_code in _REVIEW_REQUIRED_CODES
                else RequirementClass(display.severity)
            )
            if (
                requirement.catalog_axis != display.axis
                or requirement.catalog_severity != display.severity
                or requirement.requirement_class != expected_class
                or requirement.reason_codes != [requirement.reason_code]
                or requirement.evidence_state
                != _requirement_evidence_state(expected_class)
                or requirement.missingness
                != (
                    "unavailable"
                    if expected_class
                    in {RequirementClass.MISSING, RequirementClass.REVIEW_REQUIRED}
                    else "available"
                )
                or requirement.applicability != "partially_applicable"
            ):
                raise ValueError(
                    f"requirement fields differ from catalog semantics: "
                    f"{requirement.reason_code}"
                )
        catalog_codes = set(catalog_by_code)
        if any(
            not set(record.reason_codes) <= catalog_codes for record in records
        ):
            raise ValueError("visualization records contain unknown reason codes")
        if any(record.evidence_ids != [record.profile_ref] for record in records):
            raise ValueError("record evidence IDs must equal its profile reference")
        expected_profile_refs = sorted(profile_refs)
        if self.evidence_ids != expected_profile_refs:
            raise ValueError("top-level evidence IDs must equal profile references")
        expected_source_refs = sorted(
            {ref for binding in self.domain_bindings for ref in binding.source_evidence_refs}
        )
        if self.source_evidence_refs != expected_source_refs:
            raise ValueError("source evidence refs must equal the domain-binding union")
        return self


class P008VisualizationArtifactSet(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[P008_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF] = (
        P008_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF
    )
    artifact_set_id: str = Field(
        pattern=r"^p0-08-visualizations:[a-f0-9]{16}$"
    )
    data_profile_artifact_id: str = Field(min_length=1)
    data_profile_sha256: str = Field(pattern=_SHA256)
    visualizations: list[VisualizationArtifactV2] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def artifact_set_is_exactly_bound(self) -> Self:
        refs = [item.component_ref for item in self.visualizations]
        if refs != list(P008_COMPONENT_REFS):
            raise ValueError("artifact set must contain the three P0-08 components")
        for item in self.visualizations:
            if (
                item.data_binding.artifact_id != self.data_profile_artifact_id
                or item.data_binding.sha256 != self.data_profile_sha256
            ):
                raise ValueError("visualization data binding does not match profile")
        return self


def build_evidence_sufficiency_visualization_data(
    *,
    run_id: str,
    tool_version: str,
    result: EvidenceSufficiencyRunResultV2,
    reason_catalog: ReasonCodeCatalogV2,
    reason_catalog_sha256: str,
) -> EvidenceSufficiencyVisualizationDataV1:
    digest = result.result_id.rsplit(":", 1)[1]
    if run_id != f"run-{digest}":
        raise ValueError("result and producer run digests must agree")
    if reason_catalog.catalog_id != "BRIDGE-REASON-CODE-CATALOG-v0.2":
        raise ValueError("P0-08 visualization requires reason catalog v0.2")
    reason_by_code = {item.code: item for item in reason_catalog.reasons}
    if len(reason_by_code) != len(reason_catalog.reasons):
        raise ValueError("reason catalog codes must be unique")

    domain_bindings: list[DomainVisualizationBinding] = []
    axis_records: list[DomainAxisRecord] = []
    requirement_records: list[InterpretationRequirementRecord] = []
    measurement_state_records: list[MeasurementStateRecord] = []
    root_codes: set[str] = set()
    axis_index = requirement_index = measurement_index = 0

    for profile_index, profile in enumerate(result.profiles, start=1):
        profile_ref = profile.profile_id
        evidence_ids = [profile_ref]
        domain_bindings.append(
            DomainVisualizationBinding(
                profile_ref=profile_ref,
                domain_id=profile.domain_id,
                domain_label=_domain_label(profile.domain_id, profile_index),
                measurement_spec_ref=(
                    None
                    if profile.measurement_spec_ref is None
                    else profile.measurement_spec_ref.ref
                ),
                measurement_result_reference_count=len(profile.measurement_result_refs),
                source_evidence_refs=sorted(profile.evidence_refs),
                evidence_family_ids=sorted(profile.deduplicated_evidence_family_ids),
            )
        )
        axis_inputs = (
            (
                EvidenceAxisId.INPUT_DATA,
                profile.data_readiness.value,
                "bound_measurement_spec_input_requirements",
                profile.data_reason_codes,
            ),
            (
                EvidenceAxisId.METHOD_VALIDATION,
                profile.model_robustness.value,
                "declared_method_context_and_validation_records",
                profile.robustness_reason_codes,
            ),
            (
                EvidenceAxisId.REFERENCE_PRIOR,
                profile.prior_applicability.value,
                "declared_reference_and_prior_context",
                profile.prior_reason_codes,
            ),
            (
                EvidenceAxisId.INTERPRETATION,
                profile.evidence_sufficiency_state.value,
                "current_candidate_interpretation_rules",
                [
                    *profile.missing_requirements,
                    *profile.blocking_reasons,
                    *profile.limiting_reasons,
                ],
            ),
        )
        for axis_id, state, scope_basis, reasons in axis_inputs:
            axis_index += 1
            cleaned_reasons = sorted(set(reasons).difference(_SUMMARY_REASON_CODES))
            unavailable = state == "not_assessed"
            axis_records.append(
                DomainAxisRecord(
                    record_id=f"axis.{axis_index:02d}",
                    profile_ref=profile_ref,
                    evidence_ids=evidence_ids,
                    evidence_state=(
                        EvidenceState.UNAVAILABLE
                        if unavailable
                        else EvidenceState.INFERRED
                    ),
                    missingness="unavailable" if unavailable else "available",
                    applicability="not_assessed" if unavailable else "applicable",
                    reason_codes=cleaned_reasons,
                    axis_id=axis_id,
                    source_state=state,
                    scoped_state_label=_scoped_state_label(axis_id, state),
                    scope_basis=scope_basis,
                )
            )

        buckets = (
            (RequirementClass.MISSING, profile.missing_requirements),
            (RequirementClass.BLOCKING, profile.blocking_reasons),
            (RequirementClass.LIMITING, profile.limiting_reasons),
        )
        seen: set[str] = set()
        for requirement_class, codes in buckets:
            for code in codes:
                if code in _SUMMARY_REASON_CODES or code in seen:
                    continue
                seen.add(code)
                reason = _catalog_reason(reason_by_code, code)
                root_codes.add(code)
                actual_class = (
                    RequirementClass.REVIEW_REQUIRED
                    if code in _REVIEW_REQUIRED_CODES
                    else requirement_class
                )
                requirement_index += 1
                requirement_records.append(
                    InterpretationRequirementRecord(
                        record_id=f"requirement.{requirement_index:02d}",
                        profile_ref=profile_ref,
                        evidence_ids=evidence_ids,
                        evidence_state=_requirement_evidence_state(actual_class),
                        missingness=(
                            "unavailable"
                            if actual_class
                            in {RequirementClass.MISSING, RequirementClass.REVIEW_REQUIRED}
                            else "available"
                        ),
                        applicability="partially_applicable",
                        reason_codes=[code],
                        reason_code=code,
                        requirement_class=actual_class,
                        catalog_axis=reason.axis,
                        catalog_severity=reason.severity,
                    )
                )

        counts = profile.measurement_evidence_state_counts.model_dump()
        for state in EvidenceState:
            measurement_index += 1
            measurement_state_records.append(
                MeasurementStateRecord(
                    record_id=f"measurement-state.{measurement_index:02d}",
                    profile_ref=profile_ref,
                    evidence_ids=evidence_ids,
                    evidence_state=EvidenceState.INFERRED,
                    missingness="available",
                    applicability="applicable",
                    reason_codes=[],
                    measurement_evidence_state=state,
                    reference_count=counts[state.value],
                )
            )

    reason_display_records = [
        ReasonDisplayRecord(
            reason_code=reason.code,
            axis=reason.axis,
            severity=reason.severity,
            description=reason.description,
            remediation=reason.remediation,
        )
        for reason in reason_catalog.reasons
        if reason.code in root_codes
    ]
    source_result_payload = canonical_json_bytes(
        result.model_dump(mode="json"), indent=2
    )
    return EvidenceSufficiencyVisualizationDataV1(
        visualization_profile_id=f"evidence-sufficiency-visualization:{digest}",
        producer_tool_version=tool_version,
        producer_run_ref=f"run:{run_id}",
        source_result_ref=result.result_id,
        source_result_sha256=hashlib.sha256(source_result_payload).hexdigest(),
        gate_rule_spec_ref=result.gate_rule_spec_ref,
        reason_catalog_id=reason_catalog.catalog_id,
        reason_catalog_version=reason_catalog.object_version,
        reason_catalog_schema_ref=(
            "bridge://schemas/evidence-sufficiency-reason-code-catalog/v0.2"
        ),
        reason_catalog_sha256=reason_catalog_sha256,
        domain_bindings=domain_bindings,
        axis_records=axis_records,
        requirement_records=requirement_records,
        measurement_state_records=measurement_state_records,
        reason_display_records=reason_display_records,
        source_evidence_refs=sorted(
            {ref for profile in result.profiles for ref in profile.evidence_refs}
        ),
        evidence_ids=sorted(profile.profile_id for profile in result.profiles),
        limitations=sorted(
            {
                "axis_states_are_scoped_to_bound_measurement_contracts",
                "evidence_family_ids_are_not_votes",
                "measurement_result_reference_counts_are_not_independent_evidence",
                "no_source_to_reason_causality_is_inferred",
                "score_and_domain_score_are_unavailable",
            }
        ),
        domain_score=None,
    )


def _catalog_reason(
    reason_by_code: dict[str, GateReasonSpec], code: str
) -> GateReasonSpec:
    try:
        return reason_by_code[code]
    except KeyError as exc:
        raise ValueError(f"root reason is absent from catalog: {code}") from exc


def _requirement_evidence_state(value: RequirementClass) -> EvidenceState:
    return {
        RequirementClass.MISSING: EvidenceState.MISSING,
        RequirementClass.BLOCKING: EvidenceState.ALERT,
        RequirementClass.LIMITING: EvidenceState.INFERRED,
        RequirementClass.REVIEW_REQUIRED: EvidenceState.UNKNOWN,
    }[value]


def _domain_label(domain: P0DomainId | None, position: int) -> str:
    if domain is None:
        return f"Unassigned domain {position}"
    return {
        P0DomainId.TARGET_IDENTITY: "Target cell identity",
        P0DomainId.REGIONAL_FIDELITY: "Midbrain regional support",
        P0DomainId.DEVELOPMENTAL_COMPATIBILITY: "Developmental compatibility",
        P0DomainId.OFF_TARGET_CONTROL: "Off-target and unresolved composition",
        P0DomainId.PROLIFERATION_STRESS_RESPONSE: (
            "Proliferation, cell-cycle and stress signals"
        ),
    }[domain]


def _scoped_state_label(axis: EvidenceAxisId, state: str) -> str:
    labels = {
        EvidenceAxisId.INPUT_DATA: {
            "adequate": "Adequate for the bound MeasurementSpec input requirements",
            "limited": "Limited for the bound MeasurementSpec input requirements",
            "insufficient": "Insufficient for the bound MeasurementSpec input requirements",
            "not_assessed": "Not assessed for the bound MeasurementSpec input requirements",
        },
        EvidenceAxisId.METHOD_VALIDATION: {
            "validated_applicable": "Validated within the declared method context of use",
            "candidate_applicable": "Candidate within the declared method context of use",
            "unstable": "Unstable within the declared method sensitivity scope",
            "not_applicable": "Not applicable to the declared method context",
            "not_required": "Not required by the declared MeasurementSpec",
            "not_assessed": "Not assessed for the declared method context",
        },
        EvidenceAxisId.REFERENCE_PRIOR: {
            "applicable": "Applicable to the declared reference and prior context",
            "partially_applicable": (
                "Partly applicable to the declared reference and prior context"
            ),
            "inapplicable": "Inapplicable to the declared reference and prior context",
            "not_required": "Not required by the declared MeasurementSpec",
            "not_assessed": "Not assessed for the declared reference and prior context",
        },
        EvidenceAxisId.INTERPRETATION: {
            "sufficient": "Sufficient under the current candidate interpretation rules",
            "limited": "Limited under the current candidate interpretation rules",
            "insufficient": "Insufficient under the current candidate interpretation rules",
            "not_assessed": "Not assessed under the current candidate interpretation rules",
        },
    }
    try:
        return labels[axis][state]
    except KeyError as exc:
        raise ValueError(
            f"unsupported P0-08 axis state: {axis.value}={state}"
        ) from exc


def _packaged_reason_catalog() -> tuple[str, ReasonCodeCatalogV2]:
    try:
        raw = (
            files("bridge.tool_packages.p0_08_evidence_sufficiency.resources")
            .joinpath("reason_code_catalog_v0.2.json")
            .read_bytes()
        )
        catalog = ReasonCodeCatalogV2.model_validate_json(raw)
    except (OSError, ValueError) as exc:
        raise ValueError("packaged reason catalog is unavailable or invalid") from exc
    return hashlib.sha256(raw).hexdigest(), catalog


PUBLIC_VISUALIZATION_SCHEMA_MODELS = {
    EVIDENCE_SUFFICIENCY_VISUALIZATION_DATA_SCHEMA_REF: (
        EvidenceSufficiencyVisualizationDataV1
    ),
    P008_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF: P008VisualizationArtifactSet,
}
