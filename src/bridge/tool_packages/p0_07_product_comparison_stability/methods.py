from __future__ import annotations

import math
from importlib.metadata import PackageNotFoundError, version

import numpy as np
from scipy import stats
from scipy.spatial import distance

from bridge.tool_packages.p0_07_product_comparison_stability.models import (
    ComparisonMethodBundle,
    ComparisonMethodExecution,
    ComparisonMethodExecutionState,
    ComparisonMethodId,
    ComparisonMethodInput,
    ComparisonMethodRecord,
    ComparisonMethodSpec,
    ComparisonMethodTask,
    ComparisonMethodSeries,
)


METHOD_REFS = {
    ComparisonMethodId.SAMPLE_EFFECT: (
        "METHOD-BRIDGE-SAMPLE-LEVEL-EFFECT-SIZE-ENGINE",
        "BRIDGE Hedges-g sample-level effect-size engine",
    ),
    ComparisonMethodId.JENSEN_SHANNON: (
        "METHOD-JENSEN-SHANNON-DISTANCE",
        "scipy.spatial.distance.jensenshannon",
    ),
    ComparisonMethodId.PROFILE_CORRELATION: (
        "METHOD-PSEUDOBULK-CORRELATION-DISTANCE",
        "scipy.stats.spearmanr",
    ),
    ComparisonMethodId.WASSERSTEIN_1D: (
        "METHOD-WASSERSTEIN-DISTANCE",
        "scipy.stats.wasserstein_distance",
    ),
    ComparisonMethodId.ROBUST_DISPERSION: (
        "METHOD-COEFFICIENT-OF-VARIATION-ROBUST-DISPERSION",
        "NumPy coefficient of variation and median absolute deviation",
    ),
}


def _package_versions() -> dict[str, str]:
    result: dict[str, str] = {}
    for package in ("numpy", "scipy"):
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "unavailable"
    return result


def _values(series: ComparisonMethodSeries) -> np.ndarray:
    return np.asarray(series.values, dtype=float)


def _not_assessed(
    task: ComparisonMethodTask,
    series: list[ComparisonMethodSeries],
    reasons: str | list[str],
) -> ComparisonMethodRecord:
    reason_codes = [reasons] if isinstance(reasons, str) else sorted(set(reasons))
    return ComparisonMethodRecord(
        task_id=task.task_id,
        method_id=task.method_id,
        series_ids=task.series_ids,
        estimates={},
        estimate_units={},
        raw_delta=None,
        raw_delta_unit=None,
        n_values=[len(item.values) for item in series],
        assessment_state="not_assessed",
        reason_codes=reason_codes,
    )


def _available(
    task: ComparisonMethodTask,
    series: list[ComparisonMethodSeries],
    *,
    estimates: dict[str, float],
    estimate_units: dict[str, str],
    raw_delta: float | None = None,
    raw_delta_unit: str | None = None,
) -> ComparisonMethodRecord:
    return ComparisonMethodRecord(
        task_id=task.task_id,
        method_id=task.method_id,
        series_ids=task.series_ids,
        estimates=estimates,
        estimate_units=estimate_units,
        raw_delta=raw_delta,
        raw_delta_unit=raw_delta_unit,
        n_values=[len(item.values) for item in series],
        assessment_state="available",
        reason_codes=[],
    )


def _jensen_shannon(
    task: ComparisonMethodTask,
    series: list[ComparisonMethodSeries],
    spec: ComparisonMethodSpec,
) -> ComparisonMethodRecord:
    estimate = float(
        distance.jensenshannon(
            _values(series[0]),
            _values(series[1]),
            base=spec.jensen_shannon_base,
        )
    )
    if not math.isfinite(estimate):
        return _not_assessed(task, series, "jensen_shannon_nonfinite")
    return _available(
        task,
        series,
        estimates={"jensen_shannon_distance": estimate},
        estimate_units={"jensen_shannon_distance": "dimensionless"},
    )


def _wasserstein(
    task: ComparisonMethodTask,
    series: list[ComparisonMethodSeries],
) -> ComparisonMethodRecord:
    left, right = series
    estimate = float(
        stats.wasserstein_distance(
            _values(left),
            _values(right),
            u_weights=left.weights,
            v_weights=right.weights,
        )
    )
    return _available(
        task,
        series,
        estimates={"wasserstein_distance": estimate},
        estimate_units={"wasserstein_distance": left.unit},
    )


def _profile_correlation(
    task: ComparisonMethodTask,
    series: list[ComparisonMethodSeries],
) -> ComparisonMethodRecord:
    left = _values(series[0])
    right = _values(series[1])
    if np.ptp(left) == 0.0 or np.ptp(right) == 0.0:
        return _not_assessed(task, series, "profile_correlation_constant_input")
    estimate = float(stats.spearmanr(left, right).statistic)
    if not math.isfinite(estimate):
        return _not_assessed(task, series, "profile_correlation_nonfinite")
    return _available(
        task,
        series,
        estimates={"spearman_rho": estimate},
        estimate_units={"spearman_rho": "dimensionless"},
    )


def _sample_effect(
    task: ComparisonMethodTask,
    series: list[ComparisonMethodSeries],
) -> ComparisonMethodRecord:
    baseline = _values(series[0])
    comparator = _values(series[1])
    baseline_mean = float(baseline.mean())
    comparator_mean = float(comparator.mean())
    raw_delta = comparator_mean - baseline_mean
    degrees = len(baseline) + len(comparator) - 2
    pooled_variance = (
        (len(baseline) - 1) * float(baseline.var(ddof=1))
        + (len(comparator) - 1) * float(comparator.var(ddof=1))
    ) / degrees
    if pooled_variance <= 0:
        return _not_assessed(task, series, "effect_size_zero_pooled_variance")
    cohen_d = raw_delta / math.sqrt(pooled_variance)
    correction = 1.0 - 3.0 / (4.0 * (len(baseline) + len(comparator)) - 9.0)
    return _available(
        task,
        series,
        estimates={"hedges_g": float(cohen_d * correction)},
        estimate_units={"hedges_g": "dimensionless"},
        raw_delta=float(raw_delta),
        raw_delta_unit=series[0].unit,
    )


def _robust_dispersion(
    task: ComparisonMethodTask,
    series: list[ComparisonMethodSeries],
) -> ComparisonMethodRecord:
    if series[0].measurement_scale != "ratio":
        return _not_assessed(task, series, "robust_dispersion_ratio_scale_required")
    values = _values(series[0])
    if np.any(values < 0):
        return _not_assessed(task, series, "robust_dispersion_negative_value")
    mean = float(values.mean())
    median = float(np.median(values))
    if mean == 0.0:
        return _not_assessed(task, series, "coefficient_of_variation_zero_mean")
    if median == 0.0:
        return _not_assessed(
            task, series, "median_absolute_deviation_ratio_zero_median"
        )
    mad = float(np.median(np.abs(values - median)))
    estimates = {
        "coefficient_of_variation": float(values.std(ddof=1) / mean),
        "median_absolute_deviation_ratio": mad / median,
    }
    return _available(
        task,
        series,
        estimates=estimates,
        estimate_units={name: "dimensionless" for name in estimates},
    )


def _execute_task(
    task: ComparisonMethodTask,
    series_by_id: dict[str, ComparisonMethodSeries],
    spec: ComparisonMethodSpec,
    comparison_eligibility: str,
    series_gate_reasons: dict[str, str],
) -> ComparisonMethodRecord:
    series = [series_by_id[item] for item in task.series_ids]
    if comparison_eligibility not in {
        "strictly_comparable",
        "contextual_comparator",
    }:
        return _not_assessed(
            task,
            series,
            f"comparison_method_{comparison_eligibility}",
        )
    source_reasons = [
        series_gate_reasons[item]
        for item in task.series_ids
        if item in series_gate_reasons
    ]
    if source_reasons:
        return _not_assessed(task, series, source_reasons)
    if task.method_id is ComparisonMethodId.JENSEN_SHANNON:
        return _jensen_shannon(task, series, spec)
    if task.method_id is ComparisonMethodId.WASSERSTEIN_1D:
        return _wasserstein(task, series)
    if task.method_id is ComparisonMethodId.PROFILE_CORRELATION:
        return _profile_correlation(task, series)
    if task.method_id is ComparisonMethodId.SAMPLE_EFFECT:
        return _sample_effect(task, series)
    return _robust_dispersion(task, series)


def run_comparison_methods(
    *,
    run_id: str,
    tool_version: str,
    comparison_eligibility: str,
    method_spec: ComparisonMethodSpec,
    method_spec_sha256: str,
    method_input: ComparisonMethodInput,
    method_input_sha256: str,
    series_gate_reasons: dict[str, str],
) -> ComparisonMethodBundle:
    series_by_id = {item.series_id: item for item in method_input.series}
    records = [
        _execute_task(
            task,
            series_by_id,
            method_spec,
            comparison_eligibility,
            series_gate_reasons,
        )
        for task in method_spec.tasks
    ]
    records.sort(key=lambda item: item.task_id)
    selected = sorted(
        {task.method_id for task in method_spec.tasks},
        key=lambda item: item.value,
    )
    packages = _package_versions()
    executions: list[ComparisonMethodExecution] = []
    for method_id in selected:
        method_records = [item for item in records if item.method_id is method_id]
        reasons = sorted(
            {
                reason
                for item in method_records
                for reason in item.reason_codes
            }
        )
        available = sum(
            item.assessment_state == "available" for item in method_records
        )
        if available == 0:
            state = ComparisonMethodExecutionState.NOT_ASSESSED
        elif reasons:
            state = ComparisonMethodExecutionState.PARTIAL
        else:
            state = ComparisonMethodExecutionState.SUCCEEDED
        method_ref, implementation = METHOD_REFS[method_id]
        executions.append(
            ComparisonMethodExecution(
                method_id=method_id,
                method_ref=method_ref,
                implementation=implementation,
                execution_state=state,
                package_versions=packages,
                reason_codes=reasons,
            )
        )
    return ComparisonMethodBundle(
        object_version="0.1.0",
        bundle_id=f"comparison-method-bundle:{run_id.removeprefix('run-')}",
        tool_id="P0-07",
        tool_version=tool_version,
        comparison_ref=method_input.comparison_ref,
        comparison_eligibility=comparison_eligibility,
        method_spec_sha256=method_spec_sha256,
        method_input_sha256=method_input_sha256,
        selected_method_ids=selected,
        executions=executions,
        records=records,
        evidence_refs=sorted(
            {
                evidence_ref
                for series in method_input.series
                for evidence_ref in series.evidence_refs
            }
        ),
        evidence_state="shadow",
        score_state="unavailable",
        domain_score=None,
        created_at=method_input.created_at,
    )
