from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from typing import Mapping, Sequence, TypeVar

from bridge.tool_packages.p0_08_evidence_sufficiency.models import (
    CaseEvidenceReadinessSummary,
    ContractValidationState,
    ContextMatchState,
    ContextOfUseState,
    CoverageState,
    DataReadinessState,
    DomainGateInput,
    EvidenceSensitivityRecord,
    EvidenceSufficiencyProfile,
    EvidenceSufficiencyRunResult,
    EvidenceSufficiencyState,
    EvidenceValidationRecord,
    GateRuleSpec,
    GateTraceEntry,
    MethodKind,
    ModelRobustnessState,
    P0DomainId,
    PriorApplicabilityRecord,
    PriorApplicabilityState,
    RequirementState,
    SCIENTIFIC_REASON_CODES,
    ScoreStateCount,
    SensitivityKind,
    SensitivityState,
    StateCount,
    ValidationCheckState,
)
from bridge.toolkit.contracts import (
    FrozenModel,
    MeasurementResult,
    MeasurementSpec,
    QCReadinessProfile,
    ReadinessState,
    ToolPackageSpecV2,
    ToolRequestV2,
)


REASON_CODES = SCIENTIFIC_REASON_CODES
REASON_ORDER = {code: position for position, code in enumerate(REASON_CODES)}
MISSING_REASONS = set(REASON_CODES[:17])
BLOCKING_REASONS = set(REASON_CODES[17:24]) | {"raw_evidence_gate_insufficient"}
LIMITING_REASONS = set(REASON_CODES[24:33]) | {
    "raw_evidence_gate_limited",
}

PRIOR_DIMENSIONS = (
    "species_match",
    "assay_match",
    "specimen_match",
    "anatomy_match",
    "developmental_stage_match",
    "product_definition_match",
    "gene_coverage_match",
    "version_match",
    "license_match",
)


RecordT = TypeVar(
    "RecordT", EvidenceValidationRecord, PriorApplicabilityRecord, EvidenceSensitivityRecord
)
ModelT = TypeVar("ModelT", bound=FrozenModel)


@dataclass(frozen=True)
class ReconciledRecords:
    records: tuple[tuple[str, FrozenModel], ...]
    ignored_input_ids: tuple[str, ...]
    has_required_conflict: bool
    family_ids: tuple[str, ...]


@dataclass(frozen=True)
class DomainEvaluation:
    profile: EvidenceSufficiencyProfile
    trace: GateTraceEntry


def canonical_json_bytes(payload: object, *, indent: int | None = None) -> bytes:
    separators = (",", ":") if indent is None else None
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=separators,
            indent=indent,
        )
        + ("\n" if indent is not None else "")
    ).encode("utf-8")


def canonical_input_hash(
    *,
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    objects_by_input_id: Mapping[str, FrozenModel],
) -> str:
    input_refs = []
    objects = []
    for ref in sorted(request.object_inputs, key=lambda item: (item.role, item.input_id)):
        input_refs.append(
            {
                "input_id": ref.input_id,
                "role": ref.role,
                "schema_ref": ref.schema_ref,
                "object_version": ref.object_version,
                "sha256": ref.sha256,
                "media_type": ref.media_type,
            }
        )
        objects.append(
            {
                "input_id": ref.input_id,
                "payload": objects_by_input_id[ref.input_id].model_dump(mode="json"),
            }
        )
    payload = {
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "environment_spec_id": spec.environment_spec_id,
        "result_schema_ref": spec.result_schema_ref,
        "object_inputs": input_refs,
        "validated_objects": objects,
        "random_seed": request.random_seed,
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def evaluate_evidence_sufficiency(
    *,
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    gate_rule: GateRuleSpec,
    domain_inputs: list[DomainGateInput],
    objects_by_input_id: Mapping[str, FrozenModel],
) -> EvidenceSufficiencyRunResult:
    input_hash = canonical_input_hash(
        request=request,
        spec=spec,
        objects_by_input_id=objects_by_input_id,
    )
    digest = input_hash[:16]
    run_id = f"run-{digest}"
    domain_order = {domain: position for position, domain in enumerate(P0DomainId)}
    ordered_domains = sorted(
        domain_inputs,
        key=lambda item: (
            domain_order[item.domain_id] if item.domain_id is not None else len(domain_order),
            item.domain_gate_input_id,
        ),
    )
    evaluations = [
        _evaluate_domain(
            domain_input=domain_input,
            digest=digest,
            run_id=run_id,
            gate_rule=gate_rule,
            objects_by_input_id=objects_by_input_id,
        )
        for domain_input in ordered_domains
    ]
    profiles = [evaluation.profile for evaluation in evaluations]
    traces = [evaluation.trace for evaluation in evaluations]
    state_counts = Counter(profile.evidence_sufficiency_state.value for profile in profiles)
    case_refs = {profile.product_case_ref for profile in profiles if profile.product_case_ref}
    case_ref = next(iter(case_refs), None)
    summary = CaseEvidenceReadinessSummary(
        summary_id=f"case-evidence-readiness-summary:{digest}",
        summary_version="0.1.0",
        product_case_ref=case_ref,
        profile_count=len(profiles),
        evidence_sufficiency_counts=StateCount(
            sufficient=state_counts[EvidenceSufficiencyState.SUFFICIENT.value],
            limited=state_counts[EvidenceSufficiencyState.LIMITED.value],
            insufficient=state_counts[EvidenceSufficiencyState.INSUFFICIENT.value],
            not_assessed=state_counts[EvidenceSufficiencyState.NOT_ASSESSED.value],
        ),
        score_state_counts=ScoreStateCount(unavailable=len(profiles)),
        blocking_reasons=_ordered_reasons(
            reason for profile in profiles for reason in profile.blocking_reasons
        ),
    )
    return EvidenceSufficiencyRunResult(
        result_id=f"evidence-sufficiency-result:{digest}",
        result_version="0.1.0",
        gate_rule_spec_ref=gate_rule.gate_rule_spec_id,
        profiles=profiles,
        case_summary=summary,
        gate_trace=traces,
    )


def _evaluate_domain(
    *,
    domain_input: DomainGateInput,
    digest: str,
    run_id: str,
    gate_rule: GateRuleSpec,
    objects_by_input_id: Mapping[str, FrozenModel],
) -> DomainEvaluation:
    measurement_spec = _typed_object(
        objects_by_input_id, domain_input.measurement_spec_input_id, MeasurementSpec
    )
    qc_profile = _typed_object(
        objects_by_input_id, domain_input.qc_profile_input_id, QCReadinessProfile
    )
    measurement_results = _typed_objects(
        objects_by_input_id, domain_input.measurement_result_input_ids, MeasurementResult
    )
    validation_pairs = _typed_object_pairs(
        objects_by_input_id,
        domain_input.validation_record_input_ids,
        EvidenceValidationRecord,
    )
    prior_pairs = _typed_object_pairs(
        objects_by_input_id,
        domain_input.prior_record_input_ids,
        PriorApplicabilityRecord,
    )
    sensitivity_pairs = _typed_object_pairs(
        objects_by_input_id,
        domain_input.sensitivity_record_input_ids,
        EvidenceSensitivityRecord,
    )
    reconciled_validation = _reconcile(validation_pairs)
    reconciled_prior = _reconcile(prior_pairs)
    reconciled_sensitivity = _reconcile(sensitivity_pairs)
    ignored_duplicates = sorted(
        {
            *reconciled_validation.ignored_input_ids,
            *reconciled_prior.ignored_input_ids,
            *reconciled_sensitivity.ignored_input_ids,
        }
    )
    validation_records = [
        record
        for _, record in reconciled_validation.records
        if isinstance(record, EvidenceValidationRecord)
    ]
    prior_records = [
        record
        for _, record in reconciled_prior.records
        if isinstance(record, PriorApplicabilityRecord)
    ]
    sensitivity_records = [
        record
        for _, record in reconciled_sensitivity.records
        if isinstance(record, EvidenceSensitivityRecord)
    ]

    data_state, data_reasons = _data_readiness(
        domain_input=domain_input,
        measurement_spec=measurement_spec,
        qc_profile=qc_profile,
        measurement_results=measurement_results,
    )
    model_state, model_reasons = _model_robustness(
        domain_input=domain_input,
        validation_records=validation_records,
        sensitivity_records=sensitivity_records,
        family_conflict=(
            reconciled_validation.has_required_conflict
            or reconciled_sensitivity.has_required_conflict
        ),
    )
    prior_state, prior_reasons = _prior_applicability(
        domain_input=domain_input,
        prior_records=prior_records,
        family_conflict=reconciled_prior.has_required_conflict,
    )
    if ignored_duplicates:
        affected_lists: list[list[str]] = []
        if reconciled_validation.ignored_input_ids or reconciled_sensitivity.ignored_input_ids:
            affected_lists.append(model_reasons)
        if reconciled_prior.ignored_input_ids:
            affected_lists.append(prior_reasons)
        for reasons in affected_lists:
            reasons.append("evidence_family_duplicate_collapsed")

    state, gate_reason = _final_gate(
        domain_input=domain_input,
        measurement_spec=measurement_spec,
        data_state=data_state,
        model_state=model_state,
        prior_state=prior_state,
        data_reasons=data_reasons,
        model_reasons=model_reasons,
        prior_reasons=prior_reasons,
    )
    data_reasons = _ordered_reasons(data_reasons)
    model_reasons = _ordered_reasons(model_reasons)
    prior_reasons = _ordered_reasons(prior_reasons)
    score_reasons = ["p0_score_contract_unavailable"]
    if domain_input.score_contract_ref is not None:
        score_reasons.append("score_contract_ignored_current_release")
    score_reasons = _ordered_reasons(score_reasons)
    selected_reasons = _ordered_reasons(
        [*data_reasons, *model_reasons, *prior_reasons, gate_reason, *score_reasons]
    )
    profile_suffix = (
        domain_input.domain_id.value
        if domain_input.domain_id is not None
        else domain_input.domain_gate_input_id
    )
    profile_id = f"evidence-sufficiency-profile:{digest}:{profile_suffix}"
    evidence_refs = _domain_evidence_refs(
        domain_input,
        measurement_results,
        validation_records,
        prior_records,
        sensitivity_records,
    )
    all_family_ids = sorted(
        {
            *reconciled_validation.family_ids,
            *reconciled_prior.family_ids,
            *reconciled_sensitivity.family_ids,
        }
    )
    profile = EvidenceSufficiencyProfile(
        profile_id=profile_id,
        profile_version="0.1.0",
        gate_rule_spec_ref=gate_rule.gate_rule_spec_id,
        gate_rule_version=gate_rule.object_version,
        product_case_ref=(
            domain_input.product_case.object_id if domain_input.product_case else None
        ),
        product_definition_ref=(
            domain_input.product_definition.object_id if domain_input.product_definition else None
        ),
        domain_id=domain_input.domain_id,
        measurement_spec_ref=(measurement_spec.measurement_spec_id if measurement_spec else None),
        score_contract_ref=domain_input.score_contract_ref,
        data_readiness=data_state,
        data_reason_codes=data_reasons,
        qc_profile_ref=qc_profile.profile_id if qc_profile else None,
        model_robustness=model_state,
        robustness_reason_codes=model_reasons,
        validation_refs=sorted(record.validation_record_id for record in validation_records),
        prior_applicability=prior_state,
        prior_reason_codes=prior_reasons,
        snapshot_refs=sorted({record.snapshot_ref for record in prior_records}),
        evidence_sufficiency_state=state,
        blocking_reasons=_ordered_reasons(
            code
            for code in selected_reasons
            if code in MISSING_REASONS or code in BLOCKING_REASONS
        ),
        limiting_reasons=_ordered_reasons(
            code for code in selected_reasons if code in LIMITING_REASONS
        ),
        missing_requirements=_ordered_reasons(
            code for code in selected_reasons if code in MISSING_REASONS
        ),
        domain_score=None,
        score_state="unavailable",
        score_reason_codes=score_reasons,
        measurement_result_refs=sorted(result.measurement_id for result in measurement_results),
        evidence_refs=evidence_refs,
        sensitivity_refs=sorted(
            record.sensitivity_record_id for record in sensitivity_records
        ),
        deduplicated_evidence_family_ids=all_family_ids,
        created_at=domain_input.created_at,
        deterministic_run_ref=run_id,
    )
    trace = GateTraceEntry(
        profile_ref=profile_id,
        domain_gate_input_ref=domain_input.domain_gate_input_id,
        evaluated_precedence=gate_rule.precedence,
        selected_state=state,
        selected_reason_codes=selected_reasons,
        ignored_duplicate_input_refs=ignored_duplicates,
    )
    return DomainEvaluation(profile=profile, trace=trace)


def _data_readiness(
    *,
    domain_input: DomainGateInput,
    measurement_spec: MeasurementSpec | None,
    qc_profile: QCReadinessProfile | None,
    measurement_results: Sequence[MeasurementResult],
) -> tuple[DataReadinessState, list[str]]:
    reasons: list[str] = []
    if domain_input.product_case is None:
        reasons.append("product_case_not_declared")
    if domain_input.product_definition is None:
        reasons.append("product_definition_not_declared")
    if domain_input.domain_id is None:
        reasons.append("domain_not_declared")
    if measurement_spec is None:
        reasons.append("measurement_spec_not_provided")
    if qc_profile is None:
        reasons.append("qc_profile_not_provided")
    if not measurement_results:
        reasons.append("measurement_result_not_provided")
    if domain_input.task_validation_state is ContractValidationState.NOT_ASSESSED:
        reasons.append("task_validation_not_assessed")
    if reasons:
        return DataReadinessState.NOT_ASSESSED, reasons
    assert measurement_spec is not None and qc_profile is not None
    state_by_qc = {
        ReadinessState.READY: (DataReadinessState.ADEQUATE, "data_readiness_adequate"),
        ReadinessState.LIMITED: (DataReadinessState.LIMITED, "data_readiness_limited"),
        ReadinessState.BLOCKED: (
            DataReadinessState.INSUFFICIENT,
            "data_readiness_insufficient",
        ),
        ReadinessState.NOT_APPLICABLE: (
            DataReadinessState.INSUFFICIENT,
            "data_readiness_not_applicable",
        ),
        ReadinessState.NOT_ASSESSED: (
            DataReadinessState.NOT_ASSESSED,
            "qc_readiness_not_assessed",
        ),
    }
    state, reason = state_by_qc[qc_profile.readiness_state]
    reasons.append(reason)
    if measurement_spec.status != "frozen":
        reasons.append("measurement_spec_not_frozen")
    if domain_input.task_validation_state is ContractValidationState.CANDIDATE:
        reasons.append("task_validation_candidate")
    return state, reasons


def _model_robustness(
    *,
    domain_input: DomainGateInput,
    validation_records: Sequence[EvidenceValidationRecord],
    sensitivity_records: Sequence[EvidenceSensitivityRecord],
    family_conflict: bool,
) -> tuple[ModelRobustnessState, list[str]]:
    reasons: list[str] = []
    required_validation = [
        record for record in validation_records if record.required_for_interpretation
    ]
    required_sensitivity = [
        record
        for record in sensitivity_records
        if record.required_for_interpretation
        and record.sensitivity_kind in domain_input.required_sensitivity_kinds
    ]
    if domain_input.method_requirement is RequirementState.NOT_ASSESSED:
        reasons.append("method_requirement_not_assessed")
    if not required_validation:
        reasons.append("validation_record_not_provided")
    if family_conflict:
        reasons.append("evidence_family_conflict_requires_review")
    required_kinds_present = {record.sensitivity_kind for record in required_sensitivity}
    if set(domain_input.required_sensitivity_kinds) - required_kinds_present:
        reasons.append("required_sensitivity_record_missing")
    if any(record.state is SensitivityState.NOT_ASSESSED for record in required_sensitivity):
        reasons.append("sensitivity_not_assessed")
    if any(_validation_has_not_assessed(record) for record in required_validation):
        reasons.append("validation_check_not_assessed")
    if reasons:
        return ModelRobustnessState.NOT_ASSESSED, reasons

    if any(record.state is SensitivityState.UNSTABLE for record in required_sensitivity):
        reasons.append("sensitivity_unstable")
        return ModelRobustnessState.UNSTABLE, reasons
    if any(
        record.context_of_use_state is ContextOfUseState.NOT_APPLICABLE
        for record in required_validation
    ):
        reasons.append("method_context_not_applicable")
    if any(
        record.calibration_state is ValidationCheckState.FAILED
        for record in required_validation
    ):
        reasons.append("calibration_validation_failed")
    if any(record.ood_state is ValidationCheckState.FAILED for record in required_validation):
        reasons.append("ood_validation_failed")
    if reasons:
        return ModelRobustnessState.NOT_APPLICABLE, reasons

    if domain_input.method_requirement is RequirementState.NOT_REQUIRED:
        deterministic_paths = [
            record
            for record in required_validation
            if record.method_kind is MethodKind.DETERMINISTIC
            and _validation_is_fully_covered(record)
        ]
        if deterministic_paths:
            reasons.append("deterministic_method_path_validated")
            return ModelRobustnessState.NOT_REQUIRED, reasons
        return ModelRobustnessState.NOT_ASSESSED, ["validation_check_not_assessed"]

    all_frozen_and_covered = all(
        _validation_is_fully_covered(record) for record in required_validation
    )
    sensitivities_stable = all(
        record.state is SensitivityState.STABLE for record in required_sensitivity
    )
    if all_frozen_and_covered and sensitivities_stable:
        reasons.append("method_validated_applicable")
        return ModelRobustnessState.VALIDATED_APPLICABLE, reasons

    if any(
        record.validation_state is ContractValidationState.CANDIDATE
        for record in required_validation
    ):
        reasons.append("method_validation_candidate")
    if any(
        record.environment_state is ContractValidationState.CANDIDATE
        for record in required_validation
    ):
        reasons.append("environment_validation_candidate")
    if any(
        record.source_holdout_state is CoverageState.NOT_COVERED
        for record in required_validation
    ):
        reasons.append("source_holdout_not_covered")
    if any(
        record.modality_holdout_state is CoverageState.NOT_COVERED
        for record in required_validation
    ):
        reasons.append("modality_holdout_not_covered")
    if any(record.state is SensitivityState.LIMITED for record in required_sensitivity):
        reasons.append("sensitivity_limited")
    if not reasons:
        reasons.append("method_validation_candidate")
    return ModelRobustnessState.CANDIDATE_APPLICABLE, reasons


def _prior_applicability(
    *,
    domain_input: DomainGateInput,
    prior_records: Sequence[PriorApplicabilityRecord],
    family_conflict: bool,
) -> tuple[PriorApplicabilityState, list[str]]:
    reasons: list[str] = []
    required = [record for record in prior_records if record.required_for_interpretation]
    if domain_input.prior_requirement is RequirementState.NOT_ASSESSED:
        reasons.append("prior_requirement_not_assessed")
        return PriorApplicabilityState.NOT_ASSESSED, reasons
    if domain_input.prior_requirement is RequirementState.NOT_REQUIRED:
        return PriorApplicabilityState.NOT_REQUIRED, ["prior_not_required"]
    if not required:
        reasons.append("required_prior_record_missing")
    if family_conflict:
        reasons.append("evidence_family_conflict_requires_review")
    values = [getattr(record, field) for record in required for field in PRIOR_DIMENSIONS]
    if any(value is ContextMatchState.NOT_ASSESSED for value in values):
        reasons.append("prior_match_not_assessed")
    if reasons:
        return PriorApplicabilityState.NOT_ASSESSED, reasons
    if any(value is ContextMatchState.MISMATCH for value in values):
        return PriorApplicabilityState.INAPPLICABLE, ["required_prior_inapplicable"]
    if any(value is ContextMatchState.PARTIAL_MATCH for value in values):
        return PriorApplicabilityState.PARTIALLY_APPLICABLE, ["prior_partially_applicable"]
    return PriorApplicabilityState.APPLICABLE, ["prior_applicable"]


def _final_gate(
    *,
    domain_input: DomainGateInput,
    measurement_spec: MeasurementSpec | None,
    data_state: DataReadinessState,
    model_state: ModelRobustnessState,
    prior_state: PriorApplicabilityState,
    data_reasons: Sequence[str],
    model_reasons: Sequence[str],
    prior_reasons: Sequence[str],
) -> tuple[EvidenceSufficiencyState, str]:
    all_reasons = {*data_reasons, *model_reasons, *prior_reasons}
    if (
        data_state is DataReadinessState.NOT_ASSESSED
        or model_state is ModelRobustnessState.NOT_ASSESSED
        or prior_state is PriorApplicabilityState.NOT_ASSESSED
        or "evidence_family_conflict_requires_review" in all_reasons
    ):
        return EvidenceSufficiencyState.NOT_ASSESSED, "raw_evidence_gate_not_assessed"
    if (
        data_state is DataReadinessState.INSUFFICIENT
        or model_state in {ModelRobustnessState.UNSTABLE, ModelRobustnessState.NOT_APPLICABLE}
        or prior_state is PriorApplicabilityState.INAPPLICABLE
    ):
        return EvidenceSufficiencyState.INSUFFICIENT, "raw_evidence_gate_insufficient"
    if (
        data_state is DataReadinessState.LIMITED
        or model_state is ModelRobustnessState.CANDIDATE_APPLICABLE
        or prior_state is PriorApplicabilityState.PARTIALLY_APPLICABLE
        or measurement_spec is None
        or measurement_spec.status != "frozen"
        or domain_input.task_validation_state is ContractValidationState.CANDIDATE
        or "sensitivity_limited" in all_reasons
    ):
        return EvidenceSufficiencyState.LIMITED, "raw_evidence_gate_limited"
    return EvidenceSufficiencyState.SUFFICIENT, "raw_evidence_gate_sufficient"


def _validation_has_not_assessed(record: EvidenceValidationRecord) -> bool:
    return (
        record.validation_state is ContractValidationState.NOT_ASSESSED
        or record.environment_state is ContractValidationState.NOT_ASSESSED
        or record.context_of_use_state is ContextOfUseState.NOT_ASSESSED
        or record.source_holdout_state is CoverageState.NOT_ASSESSED
        or record.modality_holdout_state is CoverageState.NOT_ASSESSED
        or record.calibration_state is ValidationCheckState.NOT_ASSESSED
        or record.ood_state is ValidationCheckState.NOT_ASSESSED
    )


def _validation_is_fully_covered(record: EvidenceValidationRecord) -> bool:
    return (
        record.validation_state is ContractValidationState.FROZEN
        and record.environment_state is ContractValidationState.FROZEN
        and record.context_of_use_state is ContextOfUseState.APPLICABLE
        and record.source_holdout_state in {CoverageState.COVERED, CoverageState.NOT_REQUIRED}
        and record.modality_holdout_state in {CoverageState.COVERED, CoverageState.NOT_REQUIRED}
        and record.calibration_state
        in {ValidationCheckState.PASSED, ValidationCheckState.NOT_REQUIRED}
        and record.ood_state in {ValidationCheckState.PASSED, ValidationCheckState.NOT_REQUIRED}
    )


def _reconcile(records: Sequence[tuple[str, RecordT]]) -> ReconciledRecords:
    grouped: dict[str, list[tuple[str, RecordT]]] = defaultdict(list)
    for input_id, record in records:
        grouped[record.evidence_family_id].append((input_id, record))
    selected: list[tuple[str, FrozenModel]] = []
    ignored: list[str] = []
    conflict = False
    family_ids: list[str] = []
    for family_id in sorted(grouped):
        family_ids.append(family_id)
        members = sorted(grouped[family_id], key=lambda item: item[0])
        canonical = [canonical_json_bytes(record.model_dump(mode="json")) for _, record in members]
        if len(set(canonical)) == 1:
            selected.append(members[0])
            ignored.extend(input_id for input_id, _ in members[1:])
            continue
        if any(record.required_for_interpretation for _, record in members):
            conflict = True
        else:
            selected.extend(members)
    return ReconciledRecords(
        records=tuple(selected),
        ignored_input_ids=tuple(sorted(ignored)),
        has_required_conflict=conflict,
        family_ids=tuple(family_ids),
    )


def _domain_evidence_refs(
    domain_input: DomainGateInput,
    measurement_results: Sequence[MeasurementResult],
    validation_records: Sequence[EvidenceValidationRecord],
    prior_records: Sequence[PriorApplicabilityRecord],
    sensitivity_records: Sequence[EvidenceSensitivityRecord],
) -> list[str]:
    evidence = set(domain_input.evidence_refs)
    for result in measurement_results:
        evidence.update(ref for ref in result.provenance_refs if ref.startswith("evidence:"))
    for record in [*validation_records, *prior_records, *sensitivity_records]:
        evidence.update(record.evidence_refs)
    return sorted(evidence)


def _ordered_reasons(reasons: Sequence[str] | object) -> list[str]:
    values = set(reasons)  # type: ignore[arg-type]
    unknown = values - set(REASON_ORDER)
    if unknown:
        raise ValueError(f"unknown P0-08 reason codes: {sorted(unknown)}")
    return sorted(values, key=REASON_ORDER.__getitem__)


def _typed_object(
    objects: Mapping[str, FrozenModel],
    input_id: str | None,
    model: type[ModelT],
) -> ModelT | None:
    if input_id is None:
        return None
    value = objects[input_id]
    if not isinstance(value, model):
        raise TypeError(f"{input_id} is not a {model.__name__}")
    return value


def _typed_objects(
    objects: Mapping[str, FrozenModel],
    input_ids: Sequence[str],
    model: type[ModelT],
) -> list[ModelT]:
    return [value for input_id in input_ids if (value := _typed_object(objects, input_id, model))]


def _typed_object_pairs(
    objects: Mapping[str, FrozenModel],
    input_ids: Sequence[str],
    model: type[ModelT],
) -> list[tuple[str, ModelT]]:
    return [
        (input_id, value)
        for input_id in input_ids
        if (value := _typed_object(objects, input_id, model)) is not None
    ]
