from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from bridge.tool_packages.p0_07_product_comparison_stability.models import (
    ComparisonCaseManifest,
    ComparisonField,
    ComparisonGroup,
    ComparisonGroupRole,
    ComparisonStabilitySpec,
    ConfoundingFactor,
    GroupMetricSummary,
    GroupStability,
    InputChecksumBinding,
    MetricContrast,
    MetricContract,
    MetricEvidenceState,
    MetricStability,
    ProductComparisonStabilityProfile,
    ProductEvidenceBundle,
)


ABSENT_PRIORITY = (
    MetricEvidenceState.ALERT,
    MetricEvidenceState.UNAVAILABLE,
    MetricEvidenceState.UNKNOWN,
    MetricEvidenceState.MISSING,
)


def evaluate_product_comparison(
    *,
    run_id: str,
    tool_version: str,
    spec: ComparisonStabilitySpec,
    manifest: ComparisonCaseManifest,
    bundles: list[ProductEvidenceBundle],
    input_bindings: list[InputChecksumBinding],
) -> ProductComparisonStabilityProfile:
    bundles_by_ref = {bundle.ref.ref: bundle for bundle in bundles}
    grouped = {
        group.group_id: [bundles_by_ref[ref.ref] for ref in group.bundle_refs]
        for group in manifest.groups
    }
    field_mismatches = _field_mismatches(spec, grouped)
    missing_confounder_metadata, confounded = _confounding(spec, grouped)
    reasons: set[str] = {"descriptive_only_no_inferential_claim"}
    reasons.update(f"required_field_mismatch_{field.value}" for field in field_mismatches[0])
    reasons.update(f"contextual_field_mismatch_{field.value}" for field in field_mismatches[1])
    reasons.update(
        f"confounding_metadata_missing_{factor.value}"
        for factor in missing_confounder_metadata
    )
    reasons.update(f"complete_confounding_{factor.value}" for factor in confounded)

    if any(group.role is ComparisonGroupRole.REFERENCE_OOD for group in manifest.groups):
        eligibility = "reference_or_ood"
        reasons.add("reference_ood_group_not_rankable")
    elif field_mismatches[0] or missing_confounder_metadata:
        eligibility = "not_comparable"
    elif confounded:
        eligibility = "not_estimable"
    elif field_mismatches[1]:
        eligibility = spec.contextual_mismatch_policy
    else:
        eligibility = "strictly_comparable"

    summaries = [
        _group_metric_summary(group, metric, grouped[group.group_id])
        for group in manifest.groups
        for metric in spec.metric_contracts
    ]
    summary_lookup = {(item.group_id, item.metric_id): item for item in summaries}
    baseline = next(
        group for group in manifest.groups if group.role is ComparisonGroupRole.BASELINE
    )
    comparators = [
        group for group in manifest.groups if group.role is not ComparisonGroupRole.BASELINE
    ]
    contrasts = [
        _contrast(
            metric=metric,
            baseline=summary_lookup[(baseline.group_id, metric.metric_id)],
            comparator=summary_lookup[(group.group_id, metric.metric_id)],
            eligibility=eligibility,
            contextual=bool(field_mismatches[1]),
        )
        for group in comparators
        for metric in spec.metric_contracts
    ]
    stability = [
        _group_stability(group, spec.metric_contracts, grouped[group.group_id])
        for group in manifest.groups
    ]
    summary_reasons = {
        reason for summary in summaries for reason in summary.reason_codes
    }
    contrast_reasons = {
        reason for contrast in contrasts for reason in contrast.reason_codes
    }
    reasons.update(summary_reasons)
    reasons.update(contrast_reasons)

    estimable = eligibility in {"strictly_comparable", "contextual_comparator"}
    if not estimable:
        profile_state = "not_assessed"
    elif any(item.value_state != "shadow" for item in summaries):
        profile_state = "partial"
    elif eligibility == "contextual_comparator" or any(
        reason.startswith("evidence_sufficiency_") for reason in reasons
    ):
        profile_state = "partial"
    else:
        profile_state = "complete"
    evidence_refs = sorted(
        {
            ref
            for bundle in bundles
            for ref in [*bundle.evidence_refs, *(r for metric in bundle.metrics for r in metric.evidence_refs)]
        }
    )
    return ProductComparisonStabilityProfile(
        object_version="0.1.0",
        result_id=f"product-comparison-stability:{run_id.removeprefix('run-')}",
        tool_id="P0-07",
        tool_version=tool_version,
        comparison_ref=manifest.ref,
        spec_ref=spec.ref,
        input_bindings=input_bindings,
        comparison_eligibility=eligibility,
        comparison_mode="descriptive_only",
        profile_state=profile_state,
        group_summaries=summaries,
        metric_contrasts=contrasts,
        stability_results=stability,
        confounded_factors=sorted(confounded, key=lambda item: item.value),
        evidence_refs=evidence_refs,
        reason_codes=sorted(reasons),
        overall_score=None,
        overall_rank=None,
        domain_score=None,
        score_state="unavailable",
    )


def _field_mismatches(
    spec: ComparisonStabilitySpec,
    grouped: dict[str, list[ProductEvidenceBundle]],
) -> tuple[set[ComparisonField], set[ComparisonField]]:
    all_bundles = [bundle for values in grouped.values() for bundle in values]
    mismatches = {
        field
        for field in ComparisonField
        if len({_field_value(bundle, field) for bundle in all_bundles}) > 1
    }
    return mismatches.intersection(spec.required_equal_fields), mismatches.intersection(
        spec.contextual_fields
    )


def _field_value(bundle: ProductEvidenceBundle, field: ComparisonField) -> object:
    values = {
        ComparisonField.PRODUCT_DEFINITION: bundle.product_definition.ref.ref,
        ComparisonField.TARGET_STAGE: bundle.target_stage_ref.ref,
        ComparisonField.ASSAY: bundle.product_case.assay,
        ComparisonField.DATA_VIEW: bundle.data_view_ref.ref,
        ComparisonField.TIMEPOINT: (
            bundle.timepoint.basis,
            bundle.timepoint.label,
            bundle.timepoint.order,
        ),
        ComparisonField.REFERENCE: bundle.reference_snapshot_ref.ref,
        ComparisonField.PREPROCESSING: bundle.preprocessing_snapshot_ref.ref,
        ComparisonField.ALGORITHM: bundle.algorithm_ref.ref,
    }
    return values[field]


def _confounding(
    spec: ComparisonStabilitySpec,
    grouped: dict[str, list[ProductEvidenceBundle]],
) -> tuple[set[ConfoundingFactor], set[ConfoundingFactor]]:
    missing: set[ConfoundingFactor] = set()
    confounded: set[ConfoundingFactor] = set()
    for factor in spec.confounding_factors:
        levels = [
            {
                ref.ref
                for bundle in bundles
                for ref in getattr(bundle, f"{factor.value}_refs")
            }
            for bundles in grouped.values()
        ]
        if any(not group_levels for group_levels in levels):
            missing.add(factor)
        elif all(left.isdisjoint(right) for left, right in combinations(levels, 2)):
            confounded.add(factor)
    return missing, confounded


def _group_metric_summary(
    group: ComparisonGroup,
    contract: MetricContract,
    bundles: list[ProductEvidenceBundle],
) -> GroupMetricSummary:
    metrics = [
        next(metric for metric in bundle.metrics if metric.metric_id == contract.metric_id)
        for bundle in bundles
    ]
    reasons: set[str] = set()
    for state in ABSENT_PRIORITY:
        if any(metric.evidence_state is state for metric in metrics):
            reasons.add(f"metric_evidence_{state.value}")
            return GroupMetricSummary(
                group_id=group.group_id,
                metric_id=contract.metric_id,
                value_state=state.value,
                observed_count=0,
                expected_count=len(metrics),
                mean_value=None,
                observed_range=None,
                unit=contract.unit,
                denominator_kind=contract.denominator_kind,
                reason_codes=sorted(reasons),
            )
    values = [float(metric.raw_value) for metric in metrics if metric.raw_value is not None]
    for bundle in bundles:
        if bundle.sufficiency_state is None:
            reasons.add("evidence_sufficiency_not_supplied")
        elif bundle.sufficiency_state != "sufficient":
            reasons.add(f"evidence_sufficiency_{bundle.sufficiency_state}")
    return GroupMetricSummary(
        group_id=group.group_id,
        metric_id=contract.metric_id,
        value_state="shadow",
        observed_count=len(values),
        expected_count=len(metrics),
        mean_value=sum(values) / len(values),
        observed_range=(min(values), max(values)),
        unit=contract.unit,
        denominator_kind=contract.denominator_kind,
        reason_codes=sorted(reasons),
    )


def _contrast(
    *,
    metric: MetricContract,
    baseline: GroupMetricSummary,
    comparator: GroupMetricSummary,
    eligibility: str,
    contextual: bool,
) -> MetricContrast:
    reasons = set(baseline.reason_codes) | set(comparator.reason_codes)
    if eligibility not in {"strictly_comparable", "contextual_comparator"}:
        reasons.add(f"comparison_{eligibility}")
        return _empty_contrast(metric, baseline, comparator, "not_comparable", reasons)
    for state in ("alert", "unavailable", "unknown", "missing"):
        if state in {baseline.value_state, comparator.value_state}:
            reasons.add(f"contrast_{state}")
            return _empty_contrast(metric, baseline, comparator, state, reasons)
    if contextual:
        reasons.add("contextual_comparison_only")
    base = float(baseline.mean_value)
    comp = float(comparator.mean_value)
    delta = comp - base
    direction = "increase" if delta > 0 else "decrease" if delta < 0 else "no_change"
    return MetricContrast(
        metric_id=metric.metric_id,
        measurement_spec_ref=metric.measurement_spec_ref,
        baseline_group_id=baseline.group_id,
        comparator_group_id=comparator.group_id,
        contrast_state="shadow",
        baseline_value=base,
        comparator_value=comp,
        delta_comparator_minus_baseline=delta,
        direction=direction,
        interval_state="descriptive_only",
        unit=metric.unit,
        denominator_kind=metric.denominator_kind,
        reason_codes=sorted(reasons),
    )


def _empty_contrast(
    metric: MetricContract,
    baseline: GroupMetricSummary,
    comparator: GroupMetricSummary,
    state: str,
    reasons: set[str],
) -> MetricContrast:
    return MetricContrast(
        metric_id=metric.metric_id,
        measurement_spec_ref=metric.measurement_spec_ref,
        baseline_group_id=baseline.group_id,
        comparator_group_id=comparator.group_id,
        contrast_state=state,
        baseline_value=None,
        comparator_value=None,
        delta_comparator_minus_baseline=None,
        direction="not_assessed",
        interval_state="not_assessed",
        unit=metric.unit,
        denominator_kind=metric.denominator_kind,
        reason_codes=sorted(reasons),
    )


def _group_stability(
    group: ComparisonGroup,
    contracts: list[MetricContract],
    bundles: list[ProductEvidenceBundle],
) -> GroupStability:
    batch_count = len({ref.ref for bundle in bundles for ref in bundle.batch_refs})
    return GroupStability(
        group_id=group.group_id,
        independent_preparation_count=len(bundles),
        batch_count=batch_count,
        metric_stability=[
            _metric_stability(contract, bundles) for contract in contracts
        ],
    )


def _metric_stability(
    contract: MetricContract,
    bundles: list[ProductEvidenceBundle],
) -> MetricStability:
    metrics = [
        next(metric for metric in bundle.metrics if metric.metric_id == contract.metric_id)
        for bundle in bundles
    ]
    values = [
        float(metric.raw_value)
        for metric in metrics
        if metric.raw_value is not None
        and metric.evidence_state not in ABSENT_PRIORITY
    ]
    reasons: set[str] = set()
    if not values:
        state = "unavailable"
        observed_range = None
        width = None
        reasons.add("stability_metric_unavailable")
    elif len(values) < len(metrics):
        state = "incomplete"
        observed_range = (min(values), max(values))
        width = max(values) - min(values)
        reasons.add("stability_metric_incomplete")
    elif len(values) == 1:
        state = "single_preparation"
        observed_range = (values[0], values[0])
        width = 0.0
        reasons.add("single_preparation_descriptive_only")
    else:
        state = "replicated_descriptive"
        observed_range = (min(values), max(values))
        width = max(values) - min(values)
    return MetricStability(
        metric_id=contract.metric_id,
        state=state,
        observed_preparation_count=len(values),
        expected_preparation_count=len(metrics),
        observed_range=observed_range,
        range_width=width,
        reason_codes=sorted(reasons),
    )
