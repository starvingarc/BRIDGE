from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from bridge.tool_packages.p0_07_product_comparison_stability import (
    methods as comparison_methods,
)
from bridge.tool_packages.p0_07_product_comparison_stability.models import (
    ComparisonMethodBundle,
    ComparisonMethodExecutionState,
    ComparisonMethodId,
)
from bridge.toolkit.contracts import ExecutionState
from tests.test_p0_07_product_comparison_stability import (
    _bundle,
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
            "measurement_scale": "ratio",
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
            "measurement_scale": "ratio",
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


def _load_method_bundle(run: object) -> ComparisonMethodBundle:
    path = next(
        item.path
        for item in run.artifacts
        if item.kind == "comparison_method_bundle"
    )
    return ComparisonMethodBundle.model_validate_json(path.read_text())


def _refresh_manifest_checksum(payloads: dict[str, object]) -> None:
    payloads["comparison_method_input"]["comparison_manifest_sha256"] = (
        _payload_sha256(payloads["comparison_case_manifest"])
    )


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
    bundle = _load_method_bundle(first)
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


def test_robust_dispersion_accepts_ratio_scale_with_zero_observation(
    tmp_path: Path,
) -> None:
    payloads = _method_payloads()
    metric = payloads["bundle-baseline-1"]["metrics"][0]
    metric["raw_value"] = 0.0
    metric["interval"] = [0.0, 0.05]
    payloads["comparison_method_input"]["series"][0]["values"][0] = 0.0
    registry, request = _write_request(tmp_path, payloads)

    assert registry.check_eligibility(request).eligible
    bundle = _load_method_bundle(registry.run(request))
    record = next(
        item
        for item in bundle.records
        if item.method_id is ComparisonMethodId.ROBUST_DISPERSION
    )

    assert record.assessment_state == "available"
    assert set(record.estimates) == {
        "coefficient_of_variation",
        "median_absolute_deviation_ratio",
    }


def test_robust_dispersion_zero_mean_is_typed_not_assessed(
    tmp_path: Path,
) -> None:
    payloads = _method_payloads()
    for key in ("bundle-baseline-1", "bundle-baseline-2"):
        metric = payloads[key]["metrics"][0]
        metric["raw_value"] = 0.0
        metric["interval"] = [0.0, 0.0]
    payloads["comparison_method_input"]["series"][0]["values"] = [0.0, 0.0]
    registry, request = _write_request(tmp_path, payloads)

    assert registry.check_eligibility(request).eligible
    bundle = _load_method_bundle(registry.run(request))
    record = next(
        item
        for item in bundle.records
        if item.method_id is ComparisonMethodId.ROBUST_DISPERSION
    )

    assert record.assessment_state == "not_assessed"
    assert record.reason_codes == ["coefficient_of_variation_zero_mean"]


def test_methods_follow_reference_ood_gate_before_numeric_execution(
    tmp_path: Path,
) -> None:
    payloads = _method_payloads()
    payloads["comparison_case_manifest"]["groups"][1]["role"] = "reference_ood"
    _refresh_manifest_checksum(payloads)
    registry, request = _write_request(tmp_path, payloads)

    assert registry.check_eligibility(request).eligible
    run = registry.run(request)
    bundle = _load_method_bundle(run)

    assert run.result["comparison_eligibility"] == "reference_or_ood"
    assert all(item.assessment_state == "not_assessed" for item in bundle.records)
    assert {
        reason
        for item in bundle.records
        for reason in item.reason_codes
    } == {"comparison_method_reference_or_ood"}


def test_methods_propagate_alert_source_state(tmp_path: Path) -> None:
    payloads = _method_payloads()
    payloads["bundle-baseline-1"]["metrics"][0]["evidence_state"] = "alert"
    registry, request = _write_request(tmp_path, payloads)

    assert registry.check_eligibility(request).eligible
    bundle = _load_method_bundle(registry.run(request))

    assert all(item.assessment_state == "not_assessed" for item in bundle.records)
    assert {
        reason
        for item in bundle.records
        for reason in item.reason_codes
    } == {"comparison_method_source_alert"}


def test_methods_propagate_missing_source_state(tmp_path: Path) -> None:
    payloads = _method_payloads()
    metric = payloads["bundle-baseline-1"]["metrics"][0]
    metric.update(
        raw_value=None,
        interval=None,
        denominator_value=None,
        evidence_state="missing",
    )
    payloads["comparison_method_spec"]["tasks"] = [
        item
        for item in payloads["comparison_method_spec"]["tasks"]
        if item["method_id"] == "CMP-JS"
    ]
    payloads["comparison_method_input"]["series"] = [
        item
        for item in payloads["comparison_method_input"]["series"]
        if item["semantics"] == "probability_mass"
    ]
    registry, request = _write_request(tmp_path, payloads)

    assert registry.check_eligibility(request).eligible
    record = _load_method_bundle(registry.run(request)).records[0]

    assert record.assessment_state == "not_assessed"
    assert record.reason_codes == ["comparison_method_source_missing"]


def test_sample_series_must_cover_every_manifest_bundle(tmp_path: Path) -> None:
    payloads = _method_payloads()
    extra = _bundle("baseline-3", "group-baseline", 0.9)
    payloads["bundle-baseline-3"] = extra
    payloads["comparison_case_manifest"]["groups"][0]["bundle_refs"].append(
        _ref(extra["bundle_id"])
    )
    _refresh_manifest_checksum(payloads)
    registry, request = _write_request(tmp_path, payloads)

    eligibility = registry.check_eligibility(request)

    assert not eligibility.eligible
    assert (
        "comparison_series_source_bundle_set_mismatch"
        in eligibility.reason_codes
    )


def test_sample_series_rejects_duplicate_source_bundle(tmp_path: Path) -> None:
    payloads = _method_payloads()
    refs = payloads["comparison_method_input"]["series"][0][
        "source_bundle_refs"
    ]
    refs.append(refs[0])
    registry, request = _write_request(tmp_path, payloads)

    eligibility = registry.check_eligibility(request)

    assert not eligibility.eligible
    assert eligibility.reason_codes == ["structured_input_schema_invalid"]


@pytest.mark.parametrize("base", [0.5, 1.0])
def test_jensen_shannon_rejects_non_distance_log_base(
    tmp_path: Path,
    base: float,
) -> None:
    payloads = _method_payloads()
    payloads["comparison_method_spec"]["jensen_shannon_base"] = base
    registry, request = _write_request(tmp_path, payloads)

    eligibility = registry.check_eligibility(request)

    assert not eligibility.eligible
    assert eligibility.reason_codes == [
        "structured_input_schema_validation_failed"
    ]


def test_jensen_shannon_nonfinite_result_is_typed_not_assessed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads = _method_payloads()
    monkeypatch.setattr(
        comparison_methods.distance,
        "jensenshannon",
        lambda *args, **kwargs: float("nan"),
    )
    registry, request = _write_request(tmp_path, payloads)

    bundle = _load_method_bundle(registry.run(request))
    record = next(
        item
        for item in bundle.records
        if item.method_id is ComparisonMethodId.JENSEN_SHANNON
    )

    assert record.assessment_state == "not_assessed"
    assert record.reason_codes == ["jensen_shannon_nonfinite"]


def test_non_wasserstein_series_rejects_weights(tmp_path: Path) -> None:
    payloads = _method_payloads()
    payloads["comparison_method_input"]["series"][2]["weights"] = [
        1.0,
        1.0,
        1.0,
    ]
    registry, request = _write_request(tmp_path, payloads)

    eligibility = registry.check_eligibility(request)

    assert not eligibility.eligible
    assert eligibility.reason_codes == ["structured_input_schema_invalid"]


def test_robust_dispersion_requires_ratio_scale(tmp_path: Path) -> None:
    payloads = _method_payloads()
    payloads["comparison_method_input"]["series"][0][
        "measurement_scale"
    ] = "non_ratio"
    registry, request = _write_request(tmp_path, payloads)

    bundle = _load_method_bundle(registry.run(request))
    record = next(
        item
        for item in bundle.records
        if item.method_id is ComparisonMethodId.ROBUST_DISPERSION
    )

    assert record.assessment_state == "not_assessed"
    assert record.reason_codes == ["robust_dispersion_ratio_scale_required"]
