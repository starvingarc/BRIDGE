from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bridge.tool_packages.p0_07_product_comparison_stability.models import (
    ComparisonMethodBundle,
    ComparisonMethodExecutionState,
    ComparisonMethodId,
)
from bridge.toolkit.contracts import ExecutionState
from tests.test_p0_07_product_comparison_stability import (
    _payloads,
    _ref,
    _write_request,
)


def _payload_sha256(payload: object) -> str:
    raw = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode()
    return hashlib.sha256(raw).hexdigest()


def _bundle_refs(payloads: dict[str, object], group_id: str) -> list[dict[str, str]]:
    return [
        _ref(payload["bundle_id"])
        for key, payload in payloads.items()
        if key.startswith("bundle-") and payload["group_id"] == group_id
    ]


def _method_payloads() -> dict[str, object]:
    payloads = _payloads(replicated=True)
    baseline_refs = _bundle_refs(payloads, "group-baseline")
    comparator_refs = _bundle_refs(payloads, "group-comparator")
    baseline_labels = [
        "preparation:baseline-1@1.0.0",
        "preparation:baseline-2@1.0.0",
    ]
    comparator_labels = [
        "preparation:comparator-1@1.0.0",
        "preparation:comparator-2@1.0.0",
    ]
    method_spec = {
        "object_version": "0.1.0",
        "method_spec_id": "comparison-method-spec:demo",
        "method_spec_version": "1.0.0",
        "comparison_ref": _ref("comparison:demo"),
        "status": "candidate",
        "tasks": [
            {
                "task_id": "comparison-method-task:effect",
                "method_id": "CMP-EFFECT",
                "series_ids": [
                    "comparison-series:baseline-samples",
                    "comparison-series:comparator-samples",
                ],
            },
            {
                "task_id": "comparison-method-task:js",
                "method_id": "CMP-JS",
                "series_ids": [
                    "comparison-series:baseline-mass",
                    "comparison-series:comparator-mass",
                ],
            },
            {
                "task_id": "comparison-method-task:corr",
                "method_id": "CMP-CORR",
                "series_ids": [
                    "comparison-series:baseline-features",
                    "comparison-series:comparator-features",
                ],
            },
            {
                "task_id": "comparison-method-task:wasserstein",
                "method_id": "CMP-WASS-1D",
                "series_ids": [
                    "comparison-series:baseline-ordered",
                    "comparison-series:comparator-ordered",
                ],
            },
            {
                "task_id": "comparison-method-task:dispersion",
                "method_id": "STAB-CV",
                "series_ids": ["comparison-series:baseline-samples"],
            },
        ],
        "jensen_shannon_base": 2.0,
        "active": True,
    }
    series = [
        {
            "series_id": "comparison-series:baseline-samples",
            "group_id": "group-baseline",
            "metric_id": "metric-a",
            "semantics": "sample_values",
            "labels": baseline_labels,
            "values": [0.4, 0.5],
            "weights": None,
            "unit": "fraction",
            "denominator_kind": "eligible_product_cells",
            "source_bundle_refs": baseline_refs,
            "evidence_refs": ["evidence:baseline-sample-series"],
        },
        {
            "series_id": "comparison-series:comparator-samples",
            "group_id": "group-comparator",
            "metric_id": "metric-a",
            "semantics": "sample_values",
            "labels": comparator_labels,
            "values": [0.6, 0.7],
            "weights": None,
            "unit": "fraction",
            "denominator_kind": "eligible_product_cells",
            "source_bundle_refs": comparator_refs,
            "evidence_refs": ["evidence:comparator-sample-series"],
        },
        {
            "series_id": "comparison-series:baseline-mass",
            "group_id": "group-baseline",
            "metric_id": "metric-a",
            "semantics": "probability_mass",
            "labels": ["state:a", "state:b", "state:c"],
            "values": [0.6, 0.3, 0.1],
            "weights": None,
            "unit": "fraction",
            "denominator_kind": "eligible_product_cells",
            "source_bundle_refs": baseline_refs,
            "evidence_refs": ["evidence:baseline-mass"],
        },
        {
            "series_id": "comparison-series:comparator-mass",
            "group_id": "group-comparator",
            "metric_id": "metric-a",
            "semantics": "probability_mass",
            "labels": ["state:a", "state:b", "state:c"],
            "values": [0.4, 0.4, 0.2],
            "weights": None,
            "unit": "fraction",
            "denominator_kind": "eligible_product_cells",
            "source_bundle_refs": comparator_refs,
            "evidence_refs": ["evidence:comparator-mass"],
        },
        {
            "series_id": "comparison-series:baseline-features",
            "group_id": "group-baseline",
            "metric_id": "metric-a",
            "semantics": "matched_features",
            "labels": ["feature:a", "feature:b", "feature:c", "feature:d"],
            "values": [1.0, 2.0, 3.0, 4.0],
            "weights": None,
            "unit": "fraction",
            "denominator_kind": "eligible_product_cells",
            "source_bundle_refs": baseline_refs,
            "evidence_refs": ["evidence:baseline-features"],
        },
        {
            "series_id": "comparison-series:comparator-features",
            "group_id": "group-comparator",
            "metric_id": "metric-a",
            "semantics": "matched_features",
            "labels": ["feature:a", "feature:b", "feature:c", "feature:d"],
            "values": [1.1, 2.2, 2.9, 4.2],
            "weights": None,
            "unit": "fraction",
            "denominator_kind": "eligible_product_cells",
            "source_bundle_refs": comparator_refs,
            "evidence_refs": ["evidence:comparator-features"],
        },
        {
            "series_id": "comparison-series:baseline-ordered",
            "group_id": "group-baseline",
            "metric_id": "metric-a",
            "semantics": "ordered_values",
            "labels": ["value:1", "value:2", "value:3"],
            "values": [0.2, 0.5, 0.8],
            "weights": [0.2, 0.5, 0.3],
            "unit": "fraction",
            "denominator_kind": "eligible_product_cells",
            "source_bundle_refs": baseline_refs,
            "evidence_refs": ["evidence:baseline-ordered"],
        },
        {
            "series_id": "comparison-series:comparator-ordered",
            "group_id": "group-comparator",
            "metric_id": "metric-a",
            "semantics": "ordered_values",
            "labels": ["value:1", "value:2", "value:3"],
            "values": [0.3, 0.6, 0.9],
            "weights": [0.3, 0.4, 0.3],
            "unit": "fraction",
            "denominator_kind": "eligible_product_cells",
            "source_bundle_refs": comparator_refs,
            "evidence_refs": ["evidence:comparator-ordered"],
        },
    ]
    payloads["comparison_method_spec"] = method_spec
    payloads["comparison_method_input"] = {
        "object_version": "0.1.0",
        "method_input_id": "comparison-method-input:demo",
        "method_input_version": "1.0.0",
        "comparison_ref": _ref("comparison:demo"),
        "comparison_manifest_sha256": _payload_sha256(
            payloads["comparison_case_manifest"]
        ),
        "series": series,
        "created_at": "2026-08-27T00:00:00Z",
    }
    return payloads


def test_real_comparison_methods_execute_and_are_deterministic(
    tmp_path: Path,
) -> None:
    registry, request = _write_request(tmp_path, _method_payloads())

    eligibility = registry.check_eligibility(request)
    assert eligibility.eligible, eligibility.reason_codes
    first = registry.run(request)
    second = registry.run(request)

    assert first.execution_state is ExecutionState.SUCCEEDED
    assert first.run_id == second.run_id
    assert len(first.artifacts) == 2
    bundle_path = next(
        item.path for item in first.artifacts
        if item.kind == "comparison_method_bundle"
    )
    bundle = ComparisonMethodBundle.model_validate_json(bundle_path.read_text())
    assert set(bundle.selected_method_ids) == set(ComparisonMethodId)
    assert all(
        item.execution_state is ComparisonMethodExecutionState.SUCCEEDED
        for item in bundle.executions
    )
    estimate_names = {
        name for record in bundle.records for name in record.estimates
    }
    assert {
        "hedges_g",
        "jensen_shannon_distance",
        "spearman_rho",
        "wasserstein_distance",
        "coefficient_of_variation",
        "median_absolute_deviation_ratio",
    }.issubset(estimate_names)
    effect = next(
        item for item in bundle.records
        if item.method_id is ComparisonMethodId.SAMPLE_EFFECT
    )
    assert effect.estimate_units == {"hedges_g": "dimensionless"}
    assert effect.raw_delta_unit == "fraction"
    assert bundle.evidence_state == "shadow"
    assert bundle.score_state == "unavailable"
    assert bundle.domain_score is None


def test_method_runtime_rejects_sample_series_without_bound_units(
    tmp_path: Path,
) -> None:
    payloads = _method_payloads()
    payloads["comparison_method_input"]["series"][0]["labels"][0] = (
        "preparation:not-declared@1.0.0"
    )
    registry, request = _write_request(tmp_path, payloads)

    eligibility = registry.check_eligibility(request)

    assert not eligibility.eligible
    assert "comparison_series_analysis_unit_mismatch" in eligibility.reason_codes


def test_method_runtime_rejects_sample_value_not_in_source_bundle(
    tmp_path: Path,
) -> None:
    payloads = _method_payloads()
    payloads["comparison_method_input"]["series"][0]["values"][0] = 0.41
    registry, request = _write_request(tmp_path, payloads)

    eligibility = registry.check_eligibility(request)

    assert not eligibility.eligible
    assert (
        "comparison_series_source_value_mismatch"
        in eligibility.reason_codes
    )


def test_method_runtime_rejects_nonpositive_dispersion_series(
    tmp_path: Path,
) -> None:
    payloads = _method_payloads()
    payloads["comparison_method_input"]["series"][0]["values"][0] = 0.0
    registry, request = _write_request(tmp_path, payloads)

    eligibility = registry.check_eligibility(request)

    assert not eligibility.eligible
    assert (
        "robust_dispersion_positive_values_required"
        in eligibility.reason_codes
    )
