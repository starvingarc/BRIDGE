from __future__ import annotations

from statistics import fmean

from bridge.tool_packages.p0_07_comparison.models import (
    CaseMetricSummary,
    CaseReadinessSummary,
    ComparabilityState,
    ComparisonCaseEvidence,
    ComparisonEvidenceBundle,
    ComparisonRecord,
    ComparisonRole,
    ComparisonSpec,
    ConfiguredInterpretation,
    ContractDimension,
    ContractDimensionCheck,
    DirectionRelation,
    MetricComparisonResult,
    MetricComparisonRule,
    MetricDirectionPolicy,
    ParetoAssessment,
)
from bridge.toolkit.contracts import ScoreState


def evaluate_comparison(
    *,
    run_id: str,
    tool_version: str,
    comparison_spec: ComparisonSpec,
    evidence_bundle: ComparisonEvidenceBundle,
    input_sha256_by_role: dict[str, str],
) -> ComparisonRecord:
    evidence_by_ref = {
        item.product_case_ref.ref: item for item in evidence_bundle.cases
    }
    cases = {
        item.role: evidence_by_ref[item.product_case_ref.ref]
        for item in comparison_spec.cases
    }
    baseline = cases[ComparisonRole.BASELINE]
    candidate = cases[ComparisonRole.CANDIDATE]
    checks = [
        _dimension_check(dimension, baseline, candidate)
        for dimension in sorted(
            comparison_spec.required_equal_dimensions,
            key=lambda item: item.value,
        )
    ]
    dimensions_match = all(item.matches for item in checks)
    if dimensions_match:
        comparability = ComparabilityState.STRICTLY_COMPARABLE
    else:
        comparability = ComparabilityState(
            comparison_spec.dimension_mismatch_policy
        )

    metric_results = [
        _compare_metric(rule, baseline, candidate, comparability)
        for rule in sorted(comparison_spec.metrics, key=lambda item: item.metric_id)
    ]
    readiness = [
        CaseReadinessSummary(
            role=role,
            product_case_ref=case.product_case_ref,
            sufficiency_profile_ref=case.sufficiency_profile_ref,
            sufficiency_state=case.sufficiency_state,
            independent_preparation_count=len(case.preparations),
        )
        for role, case in (
            (ComparisonRole.BASELINE, baseline),
            (ComparisonRole.CANDIDATE, candidate),
        )
    ]

    reasons = {
        "score_contract_not_supplied",
        *(reason for result in metric_results for reason in result.reason_codes),
    }
    if not dimensions_match:
        reasons.add("required_contract_dimension_mismatch")
    preparation_ready = all(
        len(case.preparations)
        >= comparison_spec.minimum_independent_preparations_per_case
        for case in cases.values()
    )
    if not preparation_ready:
        reasons.add("independent_preparations_below_configured_minimum")
    sufficiency_ready = all(
        case.sufficiency_state == "sufficient" for case in cases.values()
    )
    if not sufficiency_ready:
        reasons.add("case_evidence_sufficiency_not_sufficient")

    available = {
        item.metric_id
        for item in metric_results
        if item.result_state == "available"
    }
    required = {item.metric_id for item in comparison_spec.metrics if item.required}
    if not available:
        result_state = "not_assessed"
    elif (
        required <= available
        and comparability is ComparabilityState.STRICTLY_COMPARABLE
        and preparation_ready
        and sufficiency_ready
    ):
        result_state = "complete"
    else:
        result_state = "partial"

    evidence_refs = sorted(
        {evidence for result in metric_results for evidence in result.evidence_refs}
    )
    return ComparisonRecord(
        object_version="0.1.0",
        comparison_id=f"comparison-record:{run_id.removeprefix('run-')}",
        tool_id="P0-07",
        tool_version=tool_version,
        comparison_spec_ref=comparison_spec.ref,
        evidence_bundle_ref=evidence_bundle.ref,
        input_sha256_by_role=input_sha256_by_role,
        result_state=result_state,
        comparability_state=comparability,
        comparison_mode="descriptive_only",
        contract_checks=checks,
        case_readiness=readiness,
        metric_comparisons=metric_results,
        pareto_assessment=ParetoAssessment(
            assessment_state="not_assessed",
            reason_code="score_contract_not_supplied",
        ),
        evidence_refs=evidence_refs,
        reason_codes=sorted(reasons),
        overall_score=None,
        overall_rank=None,
        score_state=(
            ScoreState.UNAVAILABLE
            if result_state == "not_assessed"
            else ScoreState.SHADOW
        ),
    )


def _dimension_check(
    dimension: ContractDimension,
    baseline: ComparisonCaseEvidence,
    candidate: ComparisonCaseEvidence,
) -> ContractDimensionCheck:
    baseline_value = _dimension_value(baseline, dimension)
    candidate_value = _dimension_value(candidate, dimension)
    return ContractDimensionCheck(
        dimension=dimension,
        matches=baseline_value == candidate_value,
        baseline_value=baseline_value,
        candidate_value=candidate_value,
    )


def _dimension_value(
    case: ComparisonCaseEvidence, dimension: ContractDimension
) -> str:
    snapshot = case.contract_snapshot
    values = {
        ContractDimension.PRODUCT_DEFINITION: snapshot.product_definition_ref.ref,
        ContractDimension.TARGET_CONTEXT: snapshot.target_context_ref.ref,
        ContractDimension.ASSAY: snapshot.assay_ref.ref,
        ContractDimension.SAMPLING_CONTEXT: snapshot.sampling_context_ref.ref,
        ContractDimension.REFERENCE_SNAPSHOT: snapshot.reference_snapshot_ref.ref,
        ContractDimension.PRIOR_SNAPSHOT: snapshot.prior_snapshot_ref.ref,
        ContractDimension.MEASUREMENT_SPEC: snapshot.measurement_spec_ref.ref,
        ContractDimension.SCORE_CONTRACT: (
            snapshot.score_contract_ref.ref
            if snapshot.score_contract_ref is not None
            else "not_supplied"
        ),
        ContractDimension.ALGORITHM: snapshot.algorithm_ref.ref,
        ContractDimension.PREPROCESSING: snapshot.preprocessing_ref.ref,
    }
    return values[dimension]


def _compare_metric(
    rule: MetricComparisonRule,
    baseline_case: ComparisonCaseEvidence,
    candidate_case: ComparisonCaseEvidence,
    comparability: ComparabilityState,
) -> MetricComparisonResult:
    baseline, baseline_reasons = _summarize_metric(baseline_case, rule)
    candidate, candidate_reasons = _summarize_metric(candidate_case, rule)
    reasons = {*baseline_reasons, *candidate_reasons}
    if comparability is ComparabilityState.NOT_COMPARABLE:
        reasons.add("comparison_not_comparable")
    if (
        baseline.mean is None
        or candidate.mean is None
        or comparability is ComparabilityState.NOT_COMPARABLE
    ):
        delta = None
        relation = DirectionRelation.UNAVAILABLE
        interpretation = ConfiguredInterpretation.UNAVAILABLE
        result_state = "unavailable"
    else:
        delta = float(candidate.mean) - float(baseline.mean)
        relation = _direction_relation(delta)
        interpretation = _interpretation(rule.direction_policy, relation)
        result_state = "available"

    evidence_refs = sorted(
        {*baseline.evidence_refs, *candidate.evidence_refs}
    )
    return MetricComparisonResult(
        metric_id=rule.metric_id,
        unit=rule.unit,
        baseline=baseline,
        candidate=candidate,
        raw_delta_candidate_minus_baseline=delta,
        direction_relation=relation,
        configured_interpretation=interpretation,
        result_state=result_state,
        evidence_refs=evidence_refs,
        reason_codes=sorted(reasons),
    )


def _summarize_metric(
    case: ComparisonCaseEvidence,
    rule: MetricComparisonRule,
) -> tuple[CaseMetricSummary, set[str]]:
    values: list[float] = []
    evidence_refs: set[str] = set()
    reasons: set[str] = set()
    for preparation in case.preparations:
        metric = next(
            (item for item in preparation.metrics if item.metric_id == rule.metric_id),
            None,
        )
        if metric is None:
            reasons.add("metric_missing_for_preparation")
        elif metric.unit != rule.unit:
            reasons.add("metric_unit_mismatch")
        else:
            eligible = True
            if metric.evidence_state not in rule.eligible_evidence_states:
                reasons.add("metric_evidence_state_not_eligible")
                eligible = False
            if metric.value is None:
                reasons.add("metric_value_unavailable")
                eligible = False
            if eligible:
                values.append(float(metric.value))
                evidence_refs.update(metric.evidence_refs)
    return (
        CaseMetricSummary(
            product_case_ref=case.product_case_ref,
            eligible_preparation_count=len(values),
            mean=fmean(values) if values else None,
            minimum=min(values) if values else None,
            maximum=max(values) if values else None,
            evidence_refs=sorted(evidence_refs),
        ),
        reasons,
    )


def _direction_relation(delta: float) -> DirectionRelation:
    if delta > 0:
        return DirectionRelation.CANDIDATE_HIGHER
    if delta < 0:
        return DirectionRelation.CANDIDATE_LOWER
    return DirectionRelation.NO_OBSERVED_DIFFERENCE


def _interpretation(
    policy: MetricDirectionPolicy,
    relation: DirectionRelation,
) -> ConfiguredInterpretation:
    if relation is DirectionRelation.NO_OBSERVED_DIFFERENCE:
        return ConfiguredInterpretation.NO_OBSERVED_DIFFERENCE
    if policy is MetricDirectionPolicy.DESCRIPTIVE_ONLY:
        return ConfiguredInterpretation.NO_DIRECTIONAL_INTERPRETATION
    favorable = (
        policy is MetricDirectionPolicy.HIGHER_IS_FAVORABLE
        and relation is DirectionRelation.CANDIDATE_HIGHER
    ) or (
        policy is MetricDirectionPolicy.LOWER_IS_FAVORABLE
        and relation is DirectionRelation.CANDIDATE_LOWER
    )
    return (
        ConfiguredInterpretation.CONFIGURED_FAVORABLE_DIRECTION
        if favorable
        else ConfiguredInterpretation.CONFIGURED_UNFAVORABLE_DIRECTION
    )
