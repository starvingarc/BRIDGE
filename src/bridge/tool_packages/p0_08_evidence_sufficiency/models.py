from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
import re
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from bridge.tool_packages._configurable_contracts import VersionedObjectRef
from bridge.toolkit.contracts import FrozenModel, ScoreState


class P0DomainId(StrEnum):
    TARGET_IDENTITY = "target_identity"
    REGIONAL_FIDELITY = "regional_fidelity"
    DEVELOPMENTAL_COMPATIBILITY = "developmental_compatibility"
    OFF_TARGET_CONTROL = "off_target_control"
    PROLIFERATION_STRESS_RESPONSE = "proliferation_stress_response"


class DataReadinessState(StrEnum):
    ADEQUATE = "adequate"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"
    NOT_ASSESSED = "not_assessed"


class ModelRobustnessState(StrEnum):
    VALIDATED_APPLICABLE = "validated_applicable"
    CANDIDATE_APPLICABLE = "candidate_applicable"
    UNSTABLE = "unstable"
    NOT_APPLICABLE = "not_applicable"
    NOT_REQUIRED = "not_required"
    NOT_ASSESSED = "not_assessed"


class PriorApplicabilityState(StrEnum):
    APPLICABLE = "applicable"
    PARTIALLY_APPLICABLE = "partially_applicable"
    INAPPLICABLE = "inapplicable"
    NOT_REQUIRED = "not_required"
    NOT_ASSESSED = "not_assessed"


class EvidenceSufficiencyState(StrEnum):
    SUFFICIENT = "sufficient"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"
    NOT_ASSESSED = "not_assessed"


class RequirementState(StrEnum):
    REQUIRED = "required"
    NOT_REQUIRED = "not_required"
    NOT_ASSESSED = "not_assessed"


class ContractValidationState(StrEnum):
    FROZEN = "frozen"
    CANDIDATE = "candidate"
    NOT_ASSESSED = "not_assessed"


class MethodKind(StrEnum):
    LEARNED = "learned"
    DETERMINISTIC = "deterministic"


class ContextOfUseState(StrEnum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    NOT_ASSESSED = "not_assessed"


class CoverageState(StrEnum):
    COVERED = "covered"
    NOT_COVERED = "not_covered"
    NOT_REQUIRED = "not_required"
    NOT_ASSESSED = "not_assessed"


class ValidationCheckState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_REQUIRED = "not_required"
    NOT_ASSESSED = "not_assessed"


class SensitivityKind(StrEnum):
    REFERENCE = "reference"
    PREPROCESSING = "preprocessing"
    ANNOTATION = "annotation"
    ASSAY = "assay"
    METHOD = "method"
    DOWNSAMPLING = "downsampling"


class SensitivityState(StrEnum):
    STABLE = "stable"
    LIMITED = "limited"
    UNSTABLE = "unstable"
    NOT_ASSESSED = "not_assessed"


class PriorKind(StrEnum):
    REFERENCE = "reference"
    PRIOR = "prior"
    ONTOLOGY = "ontology"
    KNOWLEDGE_SNAPSHOT = "knowledge_snapshot"


class ContextMatchState(StrEnum):
    MATCH = "match"
    PARTIAL_MATCH = "partial_match"
    MISMATCH = "mismatch"
    NOT_REQUIRED = "not_required"
    NOT_ASSESSED = "not_assessed"


class GateRuleStatus(StrEnum):
    CANDIDATE = "candidate"
    FROZEN = "frozen"


class ReasonSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    LIMITING = "limiting"
    BLOCKING = "blocking"
    MISSING = "missing"


SCIENTIFIC_REASON_CODES = (
    "product_case_not_declared",
    "product_definition_not_declared",
    "domain_not_declared",
    "measurement_spec_not_provided",
    "qc_profile_not_provided",
    "measurement_result_not_provided",
    "measurement_state_missing",
    "measurement_state_unknown",
    "measurement_state_unavailable",
    "measurement_source_run_not_provided",
    "task_validation_not_assessed",
    "method_requirement_not_assessed",
    "validation_record_not_provided",
    "validation_check_not_assessed",
    "required_sensitivity_record_missing",
    "sensitivity_not_assessed",
    "prior_requirement_not_assessed",
    "required_prior_record_missing",
    "prior_match_not_assessed",
    "evidence_family_conflict_requires_review",
    "qc_readiness_not_assessed",
    "data_readiness_insufficient",
    "data_readiness_not_applicable",
    "sensitivity_unstable",
    "method_context_not_applicable",
    "calibration_validation_failed",
    "ood_validation_failed",
    "required_prior_inapplicable",
    "data_readiness_limited",
    "measurement_spec_not_frozen",
    "task_validation_candidate",
    "method_validation_candidate",
    "environment_validation_candidate",
    "source_holdout_not_covered",
    "modality_holdout_not_covered",
    "sensitivity_limited",
    "prior_partially_applicable",
    "data_readiness_adequate",
    "method_validated_applicable",
    "deterministic_method_path_validated",
    "prior_applicable",
    "prior_not_required",
    "raw_evidence_gate_sufficient",
    "raw_evidence_gate_limited",
    "raw_evidence_gate_insufficient",
    "raw_evidence_gate_not_assessed",
    "p0_score_contract_unavailable",
    "score_contract_ignored_current_release",
    "evidence_family_duplicate_collapsed",
)
SCIENTIFIC_REASON_ORDER = {
    code: position for position, code in enumerate(SCIENTIFIC_REASON_CODES)
}
MISSING_REASON_CODES = frozenset(SCIENTIFIC_REASON_CODES[:21]) | {
    "raw_evidence_gate_not_assessed"
}
BLOCKING_REASON_CODES = frozenset(SCIENTIFIC_REASON_CODES[21:28]) | {
    "raw_evidence_gate_insufficient"
}
LIMITING_REASON_CODES = frozenset(SCIENTIFIC_REASON_CODES[28:37]) | {
    "raw_evidence_gate_limited"
}
PUBLISHED_REF = re.compile(
    r"^(?:[A-Za-z][A-Za-z0-9+.-]*://[^\s]+|"
    r"[A-Za-z][A-Za-z0-9._-]*(?::[A-Za-z0-9._:/-]+)?)$"
)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def _unique(values: list[object], field_name: str) -> list[object]:
    keys = [str(value) for value in values]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{field_name} must not contain duplicates")
    return values


def _strip(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("reference strings must not be blank")
    return stripped


def published_ref(value: str) -> str:
    stripped = _strip(value)
    if not PUBLISHED_REF.fullmatch(stripped):
        raise ValueError("published references must be scheme- or identifier-shaped")
    return stripped


def _reason_codes_in_catalog_order(values: list[str]) -> list[str]:
    cleaned = [_strip(value) for value in values]
    _unique(cleaned, "reason-code list")
    try:
        positions = [SCIENTIFIC_REASON_ORDER[value] for value in cleaned]
    except KeyError as exc:
        raise ValueError(f"unknown P0-08 reason code: {exc.args[0]}") from exc
    if positions != sorted(positions):
        raise ValueError("P0-08 reason codes must follow catalog order")
    return cleaned


class GateReasonSpec(FrozenModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    axis: Literal["contract", "data", "model", "prior", "gate", "score", "provenance"]
    severity: ReasonSeverity
    description: str = Field(min_length=1)
    remediation: str = Field(min_length=1)

    @field_validator("code", "description", "remediation")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return _strip(value)


class ReasonCodeCatalog(FrozenModel):
    catalog_id: Literal["BRIDGE-REASON-CODE-CATALOG-v0.1"]
    object_version: Literal["0.1.0"]
    status: GateRuleStatus
    created_at: datetime
    reasons: list[GateReasonSpec] = Field(min_length=1)

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @field_validator("reasons")
    @classmethod
    def reason_codes_are_unique(cls, value: list[GateReasonSpec]) -> list[GateReasonSpec]:
        _unique([reason.code for reason in value], "reasons")
        return value


class GateRuleSpec(FrozenModel):
    gate_rule_spec_id: Literal["GATE-EVIDENCE-SUFFICIENCY-v0.1"]
    object_version: Literal["0.1.0"]
    status: GateRuleStatus
    created_at: datetime
    engine_method_id: Literal["METHOD-BRIDGE-ALGORITHM-A0908D"]
    prior_matcher_method_id: Literal["METHOD-BRIDGE-ALGORITHM-A0908D"]
    reason_catalog_method_id: Literal["METHOD-BRIDGE-REGISTRY"]
    legacy_checker_method_id: Literal["METHOD-BRIDGE-VALIDATOR"]
    reason_code_catalog_ref: Literal[
        "bridge://schemas/evidence-sufficiency-reason-code-catalog/v0.1"
    ]
    applicable_domains: list[P0DomainId] = Field(min_length=5, max_length=5)
    precedence: tuple[
        Literal["not_assessed"],
        Literal["insufficient"],
        Literal["limited"],
        Literal["sufficient"],
    ]
    score_policy: Literal["domain_score_null_score_state_unavailable"]

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @model_validator(mode="after")
    def fixed_rule_contract(self) -> Self:
        if self.applicable_domains != list(P0DomainId):
            raise ValueError("applicable_domains must equal the five P0 domain IDs in order")
        if self.precedence != ("not_assessed", "insufficient", "limited", "sufficient"):
            raise ValueError("unsupported evidence-sufficiency precedence")
        return self


class VersionedObjectPointer(FrozenModel):
    object_id: str = Field(min_length=1)
    object_version: str = Field(min_length=1)
    provenance_refs: list[str] = Field(min_length=1)

    @field_validator("object_id")
    @classmethod
    def object_id_is_publishable(cls, value: str) -> str:
        return published_ref(value)

    @field_validator("object_version")
    @classmethod
    def strip_version(cls, value: str) -> str:
        return _strip(value)

    @field_validator("provenance_refs")
    @classmethod
    def unique_provenance(cls, value: list[str]) -> list[str]:
        cleaned = [published_ref(item) for item in value]
        return list(_unique(cleaned, "provenance_refs"))


class DomainGateInput(FrozenModel):
    domain_gate_input_id: str = Field(pattern=r"^domain-gate-input:[A-Za-z0-9._:-]+$")
    object_version: Literal["0.1.0"]
    created_at: datetime
    product_case: VersionedObjectPointer | None = None
    product_definition: VersionedObjectPointer | None = None
    domain_id: P0DomainId | None = None
    measurement_spec_input_id: str | None = None
    qc_profile_input_id: str | None = None
    measurement_result_input_ids: list[str] = Field(default_factory=list)
    validation_record_input_ids: list[str] = Field(default_factory=list)
    prior_record_input_ids: list[str] = Field(default_factory=list)
    sensitivity_record_input_ids: list[str] = Field(default_factory=list)
    method_requirement: RequirementState = RequirementState.NOT_ASSESSED
    prior_requirement: RequirementState = RequirementState.NOT_ASSESSED
    required_sensitivity_kinds: list[SensitivityKind] = Field(default_factory=list)
    task_validation_state: ContractValidationState = ContractValidationState.NOT_ASSESSED
    score_contract_ref: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    provenance_refs: list[str] = Field(min_length=1)

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @field_validator(
        "domain_gate_input_id",
        "measurement_spec_input_id",
        "qc_profile_input_id",
    )
    @classmethod
    def strip_optional_refs(cls, value: str | None) -> str | None:
        return None if value is None else _strip(value)

    @field_validator("score_contract_ref")
    @classmethod
    def score_ref_is_publishable(cls, value: str | None) -> str | None:
        return None if value is None else published_ref(value)

    @field_validator(
        "measurement_result_input_ids",
        "validation_record_input_ids",
        "prior_record_input_ids",
        "sensitivity_record_input_ids",
    )
    @classmethod
    def unique_input_id_lists(cls, value: list[str]) -> list[str]:
        cleaned = [_strip(item) for item in value]
        return list(_unique(cleaned, "input ID list"))

    @field_validator(
        "evidence_refs",
        "provenance_refs",
    )
    @classmethod
    def unique_ref_lists(cls, value: list[str]) -> list[str]:
        cleaned = [published_ref(item) for item in value]
        return list(_unique(cleaned, "input/reference list"))

    @field_validator("required_sensitivity_kinds")
    @classmethod
    def unique_sensitivity_kinds(
        cls, value: list[SensitivityKind]
    ) -> list[SensitivityKind]:
        return list(_unique(value, "required_sensitivity_kinds"))


class EvidenceValidationRecord(FrozenModel):
    validation_record_id: str = Field(pattern=r"^validation-record:[A-Za-z0-9._:-]+$")
    object_version: str = Field(min_length=1)
    created_at: datetime
    measurement_spec_ref: str = Field(min_length=1)
    method_id: str = Field(pattern=r"^METHOD-[A-Z0-9-]+$")
    method_version: str = Field(min_length=1)
    tool_ref: str = Field(min_length=1)
    environment_spec_ref: str = Field(min_length=1)
    evidence_family_id: str = Field(min_length=1)
    required_for_interpretation: bool = True
    method_kind: MethodKind
    validation_state: ContractValidationState
    environment_state: ContractValidationState
    context_of_use_ref: str = Field(min_length=1)
    context_of_use_state: ContextOfUseState
    source_family_ref: str = Field(min_length=1)
    source_holdout_state: CoverageState
    modality: str = Field(min_length=1)
    modality_holdout_state: CoverageState
    calibration_state: ValidationCheckState
    ood_state: ValidationCheckState
    validation_refs: list[str] = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    provenance_refs: list[str] = Field(min_length=1)

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @field_validator(
        "validation_record_id",
        "object_version",
        "measurement_spec_ref",
        "method_id",
        "method_version",
        "tool_ref",
        "environment_spec_ref",
        "evidence_family_id",
        "context_of_use_ref",
        "source_family_ref",
        "modality",
    )
    @classmethod
    def strip_string_fields(cls, value: str) -> str:
        return _strip(value)

    @field_validator("validation_refs", "evidence_refs", "provenance_refs")
    @classmethod
    def unique_ref_lists(cls, value: list[str]) -> list[str]:
        cleaned = [_strip(item) for item in value]
        return list(_unique(cleaned, "reference list"))


class PriorApplicabilityRecord(FrozenModel):
    prior_record_id: str = Field(pattern=r"^prior-record:[A-Za-z0-9._:-]+$")
    object_version: str = Field(min_length=1)
    created_at: datetime
    measurement_spec_ref: str = Field(min_length=1)
    product_definition_ref: str = Field(min_length=1)
    prior_ref: str = Field(min_length=1)
    snapshot_ref: str = Field(min_length=1)
    prior_kind: PriorKind
    evidence_family_id: str = Field(min_length=1)
    required_for_interpretation: bool = True
    species_match: ContextMatchState
    assay_match: ContextMatchState
    specimen_match: ContextMatchState
    anatomy_match: ContextMatchState
    developmental_stage_match: ContextMatchState
    product_definition_match: ContextMatchState
    gene_coverage_match: ContextMatchState
    version_match: ContextMatchState
    license_match: ContextMatchState
    crosswalk_ref: str | None = None
    evidence_refs: list[str] = Field(min_length=1)
    provenance_refs: list[str] = Field(min_length=1)

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @field_validator(
        "prior_record_id",
        "object_version",
        "measurement_spec_ref",
        "product_definition_ref",
        "prior_ref",
        "snapshot_ref",
        "evidence_family_id",
        "crosswalk_ref",
    )
    @classmethod
    def strip_string_fields(cls, value: str | None) -> str | None:
        return None if value is None else _strip(value)

    @field_validator("evidence_refs", "provenance_refs")
    @classmethod
    def unique_ref_lists(cls, value: list[str]) -> list[str]:
        cleaned = [_strip(item) for item in value]
        return list(_unique(cleaned, "reference list"))


class EvidenceSensitivityRecord(FrozenModel):
    sensitivity_record_id: str = Field(pattern=r"^sensitivity-record:[A-Za-z0-9._:-]+$")
    object_version: str = Field(min_length=1)
    created_at: datetime
    measurement_spec_ref: str = Field(min_length=1)
    sensitivity_kind: SensitivityKind
    evidence_family_id: str = Field(min_length=1)
    required_for_interpretation: bool = True
    state: SensitivityState
    baseline_ref: str = Field(min_length=1)
    perturbation_ref: str = Field(min_length=1)
    conclusion_ref: str = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    provenance_refs: list[str] = Field(min_length=1)

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @field_validator(
        "sensitivity_record_id",
        "object_version",
        "measurement_spec_ref",
        "evidence_family_id",
        "baseline_ref",
        "perturbation_ref",
        "conclusion_ref",
    )
    @classmethod
    def strip_string_fields(cls, value: str) -> str:
        return _strip(value)

    @field_validator("evidence_refs", "provenance_refs")
    @classmethod
    def unique_ref_lists(cls, value: list[str]) -> list[str]:
        cleaned = [_strip(item) for item in value]
        return list(_unique(cleaned, "reference list"))


class EvidenceSufficiencyProfile(FrozenModel):
    profile_id: str = Field(
        pattern=r"^evidence-sufficiency-profile:[a-f0-9]{16}:[A-Za-z0-9._:-]+$"
    )
    profile_version: Literal["0.1.0"]
    gate_rule_spec_ref: Literal["GATE-EVIDENCE-SUFFICIENCY-v0.1"]
    gate_rule_version: Literal["0.1.0"]
    product_case_ref: str | None = None
    product_definition_ref: str | None = None
    domain_id: P0DomainId | None = None
    measurement_spec_ref: str | None = None
    score_contract_ref: str | None = None
    data_readiness: DataReadinessState
    data_reason_codes: list[str]
    qc_profile_ref: str | None = None
    model_robustness: ModelRobustnessState
    robustness_reason_codes: list[str]
    validation_refs: list[str]
    prior_applicability: PriorApplicabilityState
    prior_reason_codes: list[str]
    snapshot_refs: list[str]
    evidence_sufficiency_state: EvidenceSufficiencyState
    blocking_reasons: list[str]
    limiting_reasons: list[str]
    missing_requirements: list[str]
    domain_score: None = None
    score_state: Literal[ScoreState.UNAVAILABLE] = ScoreState.UNAVAILABLE
    score_reason_codes: list[str]
    measurement_result_refs: list[str]
    evidence_refs: list[str]
    sensitivity_refs: list[str]
    deduplicated_evidence_family_ids: list[str]
    created_at: datetime
    deterministic_run_ref: str = Field(pattern=r"^run-[a-f0-9]{16}$")

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @field_validator(
        "product_case_ref",
        "product_definition_ref",
        "measurement_spec_ref",
        "score_contract_ref",
        "qc_profile_ref",
    )
    @classmethod
    def scalar_output_refs_are_publishable(
        cls, value: str | None
    ) -> str | None:
        return None if value is None else published_ref(value)

    @field_validator(
        "data_reason_codes",
        "robustness_reason_codes",
        "prior_reason_codes",
        "blocking_reasons",
        "limiting_reasons",
        "missing_requirements",
        "score_reason_codes",
    )
    @classmethod
    def reason_lists_follow_catalog_order(cls, value: list[str]) -> list[str]:
        return _reason_codes_in_catalog_order(value)

    @field_validator(
        "validation_refs",
        "snapshot_refs",
        "measurement_result_refs",
        "evidence_refs",
        "sensitivity_refs",
        "deduplicated_evidence_family_ids",
    )
    @classmethod
    def output_lists_are_unique(cls, value: list[str]) -> list[str]:
        cleaned = [published_ref(item) for item in value]
        return list(_unique(cleaned, "output list"))

    @model_validator(mode="after")
    def score_is_always_unavailable(self) -> Self:
        if not set(self.blocking_reasons) <= BLOCKING_REASON_CODES:
            raise ValueError("blocking_reasons may contain only blocking catalog codes")
        if not set(self.limiting_reasons) <= LIMITING_REASON_CODES:
            raise ValueError("limiting_reasons may contain only limiting catalog codes")
        if not set(self.missing_requirements) <= MISSING_REASON_CODES:
            raise ValueError("missing_requirements may contain only missing catalog codes")
        if self.domain_score is not None or self.score_state is not ScoreState.UNAVAILABLE:
            raise ValueError("P0-08 cannot emit a domain score in the current release")
        expected_score_reasons = ["p0_score_contract_unavailable"]
        if self.score_contract_ref is not None:
            expected_score_reasons.append("score_contract_ignored_current_release")
        if self.score_reason_codes != expected_score_reasons:
            raise ValueError("P0-08 score reason codes must follow the current no-score policy")
        digest = self.profile_id.split(":", 2)[1]
        if self.deterministic_run_ref != f"run-{digest}":
            raise ValueError("profile and deterministic run digests must agree")
        if self.domain_id is not None and not self.profile_id.endswith(
            f":{self.domain_id.value}"
        ):
            raise ValueError("profile ID suffix must match the declared domain")
        return self


class StateCount(FrozenModel):
    sufficient: int = Field(ge=0)
    limited: int = Field(ge=0)
    insufficient: int = Field(ge=0)
    not_assessed: int = Field(ge=0)


class ScoreStateCount(FrozenModel):
    unavailable: int = Field(ge=0)


class CaseEvidenceReadinessSummary(FrozenModel):
    summary_id: str = Field(pattern=r"^case-evidence-readiness-summary:[a-f0-9]{16}$")
    summary_version: Literal["0.1.0"]
    product_case_ref: str | None = None
    profile_count: int = Field(ge=1, le=5)
    evidence_sufficiency_counts: StateCount
    score_state_counts: ScoreStateCount
    blocking_reasons: list[str]

    @field_validator("blocking_reasons")
    @classmethod
    def unique_reasons(cls, value: list[str]) -> list[str]:
        return _reason_codes_in_catalog_order(value)

    @field_validator("product_case_ref")
    @classmethod
    def product_case_is_publishable(cls, value: str | None) -> str | None:
        return None if value is None else published_ref(value)

    @model_validator(mode="after")
    def count_totals_match(self) -> Self:
        if not set(self.blocking_reasons) <= BLOCKING_REASON_CODES:
            raise ValueError("case blocking_reasons may contain only blocking catalog codes")
        counts = self.evidence_sufficiency_counts
        total = counts.sufficient + counts.limited + counts.insufficient + counts.not_assessed
        if total != self.profile_count:
            raise ValueError("evidence sufficiency counts must equal profile_count")
        if self.score_state_counts.unavailable != self.profile_count:
            raise ValueError("every P0-08 profile must have unavailable score state")
        return self


class GateTraceEntry(FrozenModel):
    profile_ref: str
    domain_gate_input_ref: str
    evaluated_precedence: tuple[
        Literal["not_assessed"],
        Literal["insufficient"],
        Literal["limited"],
        Literal["sufficient"],
    ]
    selected_state: EvidenceSufficiencyState
    selected_reason_codes: list[str]
    ignored_duplicate_input_refs: list[str]

    @field_validator("profile_ref", "domain_gate_input_ref")
    @classmethod
    def strip_refs(cls, value: str) -> str:
        return _strip(value)

    @field_validator("selected_reason_codes", "ignored_duplicate_input_refs")
    @classmethod
    def unique_lists(cls, value: list[str]) -> list[str]:
        return list(_unique(value, "trace list"))

    @field_validator("selected_reason_codes")
    @classmethod
    def reasons_follow_catalog_order(cls, value: list[str]) -> list[str]:
        return _reason_codes_in_catalog_order(value)


class EvidenceSufficiencyRunResult(FrozenModel):
    result_id: str = Field(pattern=r"^evidence-sufficiency-result:[a-f0-9]{16}$")
    result_version: Literal["0.1.0"]
    gate_rule_spec_ref: Literal["GATE-EVIDENCE-SUFFICIENCY-v0.1"]
    profiles: list[EvidenceSufficiencyProfile] = Field(min_length=1, max_length=5)
    case_summary: CaseEvidenceReadinessSummary
    gate_trace: list[GateTraceEntry] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def validate_aggregate_bindings(self) -> Self:
        digest = self.result_id.rsplit(":", 1)[1]
        if self.case_summary.summary_id != f"case-evidence-readiness-summary:{digest}":
            raise ValueError("result and summary digests must agree")
        if self.case_summary.profile_count != len(self.profiles):
            raise ValueError("summary profile_count must equal profiles length")
        if len(self.gate_trace) != len(self.profiles):
            raise ValueError("one gate-trace entry is required per profile")
        for profile, trace in zip(self.profiles, self.gate_trace, strict=True):
            if f":{digest}:" not in profile.profile_id:
                raise ValueError("profile digest must agree with result digest")
            if trace.profile_ref != profile.profile_id:
                raise ValueError("gate trace must bind the corresponding profile")
            if trace.selected_state is not profile.evidence_sufficiency_state:
                raise ValueError("gate trace selected state must match the profile")
        case_refs = {
            profile.product_case_ref
            for profile in self.profiles
            if profile.product_case_ref
        }
        if len(case_refs) > 1:
            raise ValueError("profiles in one result must belong to one product case")
        expected_case = next(iter(case_refs), None)
        if self.case_summary.product_case_ref != expected_case:
            raise ValueError("case summary product case must match profiles")
        actual_counts = {
            state: sum(
                profile.evidence_sufficiency_state.value == state
                for profile in self.profiles
            )
            for state in ("sufficient", "limited", "insufficient", "not_assessed")
        }
        if self.case_summary.evidence_sufficiency_counts.model_dump() != actual_counts:
            raise ValueError("case summary state counts must match profiles")
        expected_blocking = sorted(
            {
                reason
                for profile in self.profiles
                for reason in profile.blocking_reasons
            },
            key=SCIENTIFIC_REASON_ORDER.__getitem__,
        )
        if self.case_summary.blocking_reasons != expected_blocking:
            raise ValueError("case summary blocking reasons must match profiles")
        domain_order = {domain: position for position, domain in enumerate(P0DomainId)}
        actual_order = [
            (
                domain_order[profile.domain_id]
                if profile.domain_id is not None
                else len(domain_order),
                trace.domain_gate_input_ref if profile.domain_id is None else "",
            )
            for profile, trace in zip(self.profiles, self.gate_trace, strict=True)
        ]
        if actual_order != sorted(actual_order):
            raise ValueError("profiles and gate traces must follow P0 domain order")
        return self


SOURCE_OBJECT_SCHEMA_BY_ROLE = {
    "gate_rule_spec": "bridge://schemas/evidence-sufficiency-gate-rule-spec/v0.1",
    "domain_gate_input": "bridge://schemas/domain-gate-input/v0.1",
    "measurement_spec": "bridge://schemas/measurement-spec/v0.2",
    "qc_readiness_profile": "bridge://schemas/qc-readiness-profile/v0.2",
    "measurement_result": "bridge://schemas/measurement-result/v0.2",
    "validation_record": "bridge://schemas/evidence-validation-record/v0.1",
    "prior_applicability_record": (
        "bridge://schemas/prior-applicability-record/v0.1"
    ),
    "sensitivity_record": "bridge://schemas/evidence-sensitivity-record/v0.1",
}


class SourceObjectBinding(FrozenModel):
    """Path-free binding to one exact accepted structured-input object."""

    input_id: str = Field(min_length=1)
    role: Literal[
        "gate_rule_spec",
        "domain_gate_input",
        "measurement_spec",
        "qc_readiness_profile",
        "measurement_result",
        "validation_record",
        "prior_applicability_record",
        "sensitivity_record",
    ]
    logical_object_id: str = Field(min_length=1)
    object_version: str = Field(min_length=1)
    schema_ref: Literal[
        "bridge://schemas/evidence-sufficiency-gate-rule-spec/v0.1",
        "bridge://schemas/domain-gate-input/v0.1",
        "bridge://schemas/measurement-spec/v0.2",
        "bridge://schemas/qc-readiness-profile/v0.2",
        "bridge://schemas/measurement-result/v0.2",
        "bridge://schemas/evidence-validation-record/v0.1",
        "bridge://schemas/prior-applicability-record/v0.1",
        "bridge://schemas/evidence-sensitivity-record/v0.1",
    ]
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("input_id", "object_version")
    @classmethod
    def local_binding_fields_are_not_blank(cls, value: str) -> str:
        return _strip(value)

    @field_validator("logical_object_id")
    @classmethod
    def logical_object_id_is_publishable(cls, value: str) -> str:
        return published_ref(value)

    @property
    def ref(self) -> str:
        return f"{self.logical_object_id}@{self.object_version}"

    @model_validator(mode="after")
    def role_and_schema_agree(self) -> Self:
        if self.schema_ref != SOURCE_OBJECT_SCHEMA_BY_ROLE[self.role]:
            raise ValueError("source-object role and schema_ref must agree")
        return self


class MeasurementEvidenceStateCount(FrozenModel):
    measured: int = Field(ge=0)
    inferred: int = Field(ge=0)
    prior_only: int = Field(ge=0)
    negative: int = Field(ge=0)
    missing: int = Field(ge=0)
    unknown: int = Field(ge=0)
    unavailable: int = Field(ge=0)
    alert: int = Field(ge=0)

    @property
    def total(self) -> int:
        return sum(self.model_dump().values())


class EvidenceSufficiencyProfileV2(EvidenceSufficiencyProfile):
    profile_version: Literal["0.2.0"]
    product_case_ref: VersionedObjectRef | None = Field(
        default=None,
        description=(
            "Versioned pointer declared inside DomainGateInput; P0-08 does not "
            "consume or validate ProductCase object content."
        ),
    )
    product_definition_ref: VersionedObjectRef | None = Field(
        default=None,
        description=(
            "Versioned pointer declared inside DomainGateInput; P0-08 does not "
            "consume or validate ProductDefinition object content."
        ),
    )
    measurement_spec_ref: VersionedObjectRef | None = None
    qc_profile_ref: VersionedObjectRef | None = None
    measurement_result_refs: list[VersionedObjectRef]
    measurement_evidence_state_counts: MeasurementEvidenceStateCount = Field(
        description="Counts MeasurementResult references bound to this domain profile."
    )

    @field_validator("score_contract_ref")
    @classmethod
    def scalar_output_refs_are_publishable(
        cls, value: str | None
    ) -> str | None:
        return None if value is None else published_ref(value)

    @field_validator(
        "validation_refs",
        "snapshot_refs",
        "evidence_refs",
        "sensitivity_refs",
        "deduplicated_evidence_family_ids",
    )
    @classmethod
    def output_lists_are_unique(cls, value: list[str]) -> list[str]:
        cleaned = [published_ref(item) for item in value]
        return list(_unique(cleaned, "output list"))

    @field_validator("measurement_result_refs")
    @classmethod
    def measurement_results_are_unique(
        cls, value: list[VersionedObjectRef]
    ) -> list[VersionedObjectRef]:
        if len({item.ref for item in value}) != len(value):
            raise ValueError("measurement_result_refs must be unique")
        return value

    @model_validator(mode="after")
    def v2_handoff_is_coherent(self) -> Self:
        if self.measurement_evidence_state_counts.total != len(
            self.measurement_result_refs
        ):
            raise ValueError(
                "measurement evidence-state counts must match result refs"
            )
        if (
            self.evidence_sufficiency_state
            is not EvidenceSufficiencyState.NOT_ASSESSED
        ):
            required = (
                self.product_case_ref,
                self.product_definition_ref,
                self.domain_id,
                self.measurement_spec_ref,
                self.qc_profile_ref,
            )
            if any(item is None for item in required):
                raise ValueError(
                    "assessed profile requires complete versioned context"
                )
        return self


class CaseEvidenceReadinessSummaryV2(CaseEvidenceReadinessSummary):
    summary_version: Literal["0.2.0"]
    product_case_ref: VersionedObjectRef | None = None
    measurement_evidence_state_counts: MeasurementEvidenceStateCount = Field(
        description=(
            "Sum of domain-profile MeasurementResult references; one source object "
            "shared across domains is counted once per domain profile."
        )
    )

    @field_validator("product_case_ref")
    @classmethod
    def product_case_is_publishable(
        cls, value: VersionedObjectRef | None
    ) -> VersionedObjectRef | None:
        return value


class EvidenceSufficiencyRunResultV2(EvidenceSufficiencyRunResult):
    result_version: Literal["0.2.0"]
    source_object_bindings: list[SourceObjectBinding] = Field(
        min_length=2,
        description=(
            "One path-free exact-source binding for every accepted StructuredInputRef."
        ),
    )
    profiles: list[EvidenceSufficiencyProfileV2] = Field(
        min_length=1, max_length=5
    )
    case_summary: CaseEvidenceReadinessSummaryV2

    @model_validator(mode="after")
    def validate_v2_source_bindings(self) -> Self:
        source_input_ids = [item.input_id for item in self.source_object_bindings]
        if len(source_input_ids) != len(set(source_input_ids)):
            raise ValueError("source-object input IDs must be unique")
        expected_order = sorted(
            self.source_object_bindings,
            key=lambda item: (item.role, item.input_id),
        )
        if self.source_object_bindings != expected_order:
            raise ValueError("source-object bindings must follow role/input order")
        source_by_role: dict[str, list[SourceObjectBinding]] = {}
        for binding in self.source_object_bindings:
            source_by_role.setdefault(binding.role, []).append(binding)
        gate_bindings = source_by_role.get("gate_rule_spec", [])
        domain_bindings = source_by_role.get("domain_gate_input", [])
        if (
            len(gate_bindings) != 1
            or gate_bindings[0].logical_object_id != self.gate_rule_spec_ref
        ):
            raise ValueError("result must bind its one gate-rule source object")
        if not 1 <= len(domain_bindings) <= 5:
            raise ValueError("result must bind one to five domain input objects")
        expected_domain_refs = {
            item.logical_object_id for item in domain_bindings
        }
        actual_domain_refs = {
            trace.domain_gate_input_ref for trace in self.gate_trace
        }
        if actual_domain_refs != expected_domain_refs:
            raise ValueError("gate trace must cover every domain input source")
        expected_measurement_refs = {
            item.ref for item in source_by_role.get("measurement_result", [])
        }
        actual_measurement_refs = {
            item.ref
            for profile in self.profiles
            for item in profile.measurement_result_refs
        }
        if actual_measurement_refs != expected_measurement_refs:
            raise ValueError(
                "profile measurement refs must cover measurement source objects"
            )
        for role, field in (
            ("measurement_spec", "measurement_spec_ref"),
            ("qc_readiness_profile", "qc_profile_ref"),
        ):
            expected_refs = {
                item.ref for item in source_by_role.get(role, [])
            }
            actual_refs = {
                ref.ref
                for profile in self.profiles
                if (ref := getattr(profile, field)) is not None
            }
            if actual_refs != expected_refs:
                raise ValueError(
                    f"profile {field} values must cover {role} source objects"
                )
        expected_measurement_counts = {
            state: sum(
                profile.measurement_evidence_state_counts.model_dump()[state]
                for profile in self.profiles
            )
            for state in (
                self.case_summary.measurement_evidence_state_counts.model_dump()
            )
        }
        if (
            self.case_summary.measurement_evidence_state_counts.model_dump()
            != expected_measurement_counts
        ):
            raise ValueError(
                "case summary measurement-state counts must match profiles"
            )
        return self


PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/evidence-sufficiency-reason-code-catalog/v0.1": ReasonCodeCatalog,
    "bridge://schemas/evidence-sufficiency-gate-rule-spec/v0.1": GateRuleSpec,
    "bridge://schemas/domain-gate-input/v0.1": DomainGateInput,
    "bridge://schemas/evidence-validation-record/v0.1": EvidenceValidationRecord,
    "bridge://schemas/prior-applicability-record/v0.1": PriorApplicabilityRecord,
    "bridge://schemas/evidence-sensitivity-record/v0.1": EvidenceSensitivityRecord,
    "bridge://schemas/evidence-sufficiency-profile/v0.1": EvidenceSufficiencyProfile,
    "bridge://schemas/case-evidence-readiness-summary/v0.1": CaseEvidenceReadinessSummary,
    "bridge://schemas/evidence-sufficiency-run-result/v0.1": EvidenceSufficiencyRunResult,
    "bridge://schemas/evidence-sufficiency-run-result/v0.2": (
        EvidenceSufficiencyRunResultV2
    ),
}
