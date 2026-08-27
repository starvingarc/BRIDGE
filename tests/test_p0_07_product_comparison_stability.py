from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from bridge.tool_packages.p0_07_product_comparison_stability.adapter import adapter
from bridge.toolkit.contracts import ToolRequest
from bridge.toolkit.registry import ToolRegistry


SCHEMAS = {
    "comparison_stability_spec": "bridge://schemas/comparison-stability-spec/v0.1",
    "comparison_case_manifest": "bridge://schemas/comparison-case-manifest/v0.1",
    "product_evidence_bundle": "bridge://schemas/product-evidence-bundle/v0.1",
    "comparison_method_spec": "bridge://schemas/comparison-method-spec/v0.1",
    "comparison_method_input": "bridge://schemas/comparison-method-input/v0.1",
}


def _ref(object_id: str, version: str = "1.0.0") -> dict[str, str]:
    return {"object_id": object_id, "object_version": version}


def _bundle(slug: str, group: str, value: float) -> dict:
    product_ref = _ref("product-definition:demo")
    return {
        "object_version": "0.1.0",
        "bundle_id": f"product-evidence-bundle:{slug}",
        "bundle_version": "1.0.0",
        "comparison_ref": _ref("comparison:demo"),
        "group_id": group,
        "product_case": {
            "object_version": "0.1.0",
            "product_case_id": f"product-case:{slug}",
            "case_version": "1.0.0",
            "product_definition_ref": product_ref,
            "source_unit_kind": "preparation",
            "sample_or_preparation_ref": _ref(f"preparation:{slug}"),
            "measurement_spec_ref": _ref("measurement-spec:metric-a"),
            "assay": "scRNA-seq",
            "provenance_refs": [_ref(f"provenance:case-{slug}")],
            "created_at": "2026-08-25T00:00:00Z",
        },
        "product_definition": {
            "object_version": "0.1.0",
            "product_definition_id": product_ref["object_id"],
            "definition_version": product_ref["object_version"],
            "state_role_map_ref": _ref("state-role-map:demo"),
            "supported_assays": ["scRNA-seq", "snRNA-seq"],
            "review_state": "draft",
            "provenance_refs": [_ref("provenance:product")],
        },
        "target_stage_ref": _ref("target-stage:demo"),
        "data_view_ref": _ref("data-view-contract:qc-selected"),
        "timepoint": {"basis": "in_vitro_day", "label": "D25", "order": 25},
        "batch_refs": [_ref(f"batch:{slug}")],
        "protocol_refs": [_ref("protocol:shared")],
        "lab_refs": [_ref("lab:shared")],
        "cell_line_refs": [_ref(f"cell-line:{slug}")],
        "reference_snapshot_ref": _ref("reference-snapshot:demo"),
        "preprocessing_snapshot_ref": _ref("preprocessing:demo"),
        "algorithm_ref": _ref("algorithm:demo"),
        "metrics": [
            {
                "metric_id": "metric-a",
                "measurement_spec_ref": _ref("measurement-spec:metric-a"),
                "raw_value": value,
                "interval": [value - 0.05, value + 0.05],
                "unit": "fraction",
                "denominator_kind": "eligible_product_cells",
                "denominator_value": 100,
                "evidence_state": "shadow",
                "evidence_refs": [f"evidence:{slug}"],
                "provenance_refs": [_ref(f"provenance:metric-{slug}")],
                "domain_score": None,
                "score_state": "unavailable",
            }
        ],
        "sufficiency_summary_ref": f"case-evidence-readiness-summary:{slug}",
        "sufficiency_state": "sufficient",
        "evidence_refs": [f"evidence:{slug}"],
        "provenance_refs": [_ref(f"provenance:bundle-{slug}")],
        "created_at": "2026-08-25T00:00:00Z",
    }


def _payloads(*, replicated: bool = False) -> dict[str, object]:
    bundles = {
        "bundle-baseline-1": _bundle("baseline-1", "group-baseline", 0.4),
        "bundle-comparator-1": _bundle("comparator-1", "group-comparator", 0.6),
    }
    if replicated:
        bundles.update(
            {
                "bundle-baseline-2": _bundle("baseline-2", "group-baseline", 0.5),
                "bundle-comparator-2": _bundle(
                    "comparator-2", "group-comparator", 0.7
                ),
            }
        )
    baseline_refs = [
        _ref(bundle["bundle_id"])
        for bundle in bundles.values()
        if bundle["group_id"] == "group-baseline"
    ]
    comparator_refs = [
        _ref(bundle["bundle_id"])
        for bundle in bundles.values()
        if bundle["group_id"] == "group-comparator"
    ]
    return {
        "comparison_stability_spec": {
            "object_version": "0.1.0",
            "spec_id": "comparison-stability-spec:demo",
            "spec_version": "1.0.0",
            "comparison_ref": _ref("comparison:demo"),
            "status": "candidate",
            "analysis_mode": "descriptive_only",
            "required_equal_fields": [
                "product_definition",
                "target_stage",
                "assay",
                "data_view",
                "timepoint",
                "reference",
                "preprocessing",
                "algorithm",
            ],
            "contextual_fields": [],
            "contextual_mismatch_policy": "contextual_comparator",
            "confounding_factors": ["protocol"],
            "metric_contracts": [
                {
                    "metric_id": "metric-a",
                    "measurement_spec_ref": _ref("measurement-spec:metric-a"),
                    "unit": "fraction",
                    "denominator_kind": "eligible_product_cells",
                    "required": True,
                }
            ],
            "created_at": "2026-08-25T00:00:00Z",
        },
        "comparison_case_manifest": {
            "object_version": "0.1.0",
            "comparison_id": "comparison:demo",
            "comparison_version": "1.0.0",
            "spec_ref": _ref("comparison-stability-spec:demo"),
            "groups": [
                {
                    "group_id": "group-baseline",
                    "role": "baseline",
                    "product_definition_ref": _ref("product-definition:demo"),
                    "target_stage_ref": _ref("target-stage:demo"),
                    "bundle_refs": baseline_refs,
                },
                {
                    "group_id": "group-comparator",
                    "role": "comparator",
                    "product_definition_ref": _ref("product-definition:demo"),
                    "target_stage_ref": _ref("target-stage:demo"),
                    "bundle_refs": comparator_refs,
                },
            ],
            "provenance_refs": [_ref("provenance:comparison")],
            "created_at": "2026-08-25T00:00:00Z",
        },
        **bundles,
    }


def _role(key: str) -> str:
    return (
        key
        if key in {
            "comparison_stability_spec", "comparison_case_manifest",
            "comparison_method_spec", "comparison_method_input",
        }
        else "product_evidence_bundle"
    )


def _write_request(
    tmp_path: Path, payloads: dict[str, object], *, output_name: str = "output"
) -> tuple[ToolRegistry, object]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    refs = []
    for index, (key, payload) in enumerate(payloads.items()):
        role = _role(key)
        raw = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode()
        path = (tmp_path / f"{key}.json").resolve()
        path.write_bytes(raw)
        refs.append(
            {
                "input_id": f"input-{index:02d}-{key}",
                "role": role,
                "schema_ref": SCHEMAS[role],
                "object_version": "0.1.0",
                "path": str(path),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "media_type": "application/json",
            }
        )
    registry = ToolRegistry.load_default()
    request = registry.parse_request(
        {
            "request_id": f"request-{output_name}",
            "tool_id": "P0-07",
            "tool_version": "0.3.0",
            "output_dir": str((tmp_path / output_name).resolve()),
            "assets": [],
            "measurement_spec_ref": None,
            "parameters": {},
            "random_seed": 0,
            "object_inputs": refs,
        }
    )
    return registry, request


def test_registry_exposes_p0_07_v2_runtime() -> None:
    registry = ToolRegistry.load_default()
    spec = registry.describe("P0-07")
    assert spec.version == "0.3.0"
    assert spec.implementation_state.value == "implemented"
    assert registry.request_model("P0-07").__name__ == "ToolRequestV2"


def test_valid_run_is_descriptive_shadow_without_rank(tmp_path: Path) -> None:
    registry, request = _write_request(tmp_path, _payloads())
    assert registry.check_eligibility(request).eligible
    run = registry.run(request)
    assert run.execution_state.value == "succeeded"
    result = run.result
    assert result["comparison_eligibility"] == "strictly_comparable"
    assert result["comparison_mode"] == "descriptive_only"
    contrast = result["metric_contrasts"][0]
    assert contrast["delta_comparator_minus_baseline"] == pytest.approx(0.2)
    assert contrast["direction"] == "increase"
    assert result["overall_score"] is None and result["overall_rank"] is None
    assert result["domain_score"] is None and result["score_state"] == "unavailable"


def test_run_is_deterministic_across_order_and_paths(tmp_path: Path) -> None:
    payloads = _payloads()
    first_registry, first_request = _write_request(tmp_path / "first", payloads)
    first = first_registry.run(first_request)
    reversed_payloads = dict(reversed(list(payloads.items())))
    second_registry, second_request = _write_request(
        tmp_path / "second", reversed_payloads
    )
    second = second_registry.run(second_request)
    assert first.run_id == second.run_id
    assert first.result == second.result
    assert first.artifacts[0].sha256 == second.artifacts[0].sha256


def test_missing_metric_is_null_not_zero(tmp_path: Path) -> None:
    payloads = _payloads()
    metric = payloads["bundle-comparator-1"]["metrics"][0]
    metric.update(
        raw_value=None,
        interval=None,
        denominator_value=None,
        evidence_state="missing",
    )
    registry, request = _write_request(tmp_path, payloads)
    run = registry.run(request)
    assert run.execution_state.value == "partial"
    contrast = run.result["metric_contrasts"][0]
    assert contrast["contrast_state"] == "missing"
    assert contrast["comparator_value"] is None
    assert contrast["delta_comparator_minus_baseline"] is None


def test_checksum_mismatch_is_refused(tmp_path: Path) -> None:
    registry, request = _write_request(tmp_path, _payloads())
    payload = request.model_dump(mode="json")
    payload["object_inputs"][0]["sha256"] = "0" * 64
    invalid = registry.parse_request(payload)
    eligibility = registry.check_eligibility(invalid)
    assert not eligibility.eligible
    assert "structured_input_checksum_mismatch" in eligibility.reason_codes


def test_at_least_two_bundles_are_required(tmp_path: Path) -> None:
    payloads = _payloads()
    del payloads["bundle-comparator-1"]
    registry, request = _write_request(tmp_path, payloads)
    eligibility = registry.check_eligibility(request)
    assert not eligibility.eligible
    assert "two_to_twenty_product_evidence_bundles_required" in eligibility.reason_codes


def test_manifest_bundle_set_mismatch_is_refused(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["comparison_case_manifest"]["groups"][1]["bundle_refs"][0] = _ref(
        "product-evidence-bundle:other"
    )
    registry, request = _write_request(tmp_path, payloads)
    eligibility = registry.check_eligibility(request)
    assert not eligibility.eligible
    assert "comparison_manifest_bundle_set_mismatch" in eligibility.reason_codes


def test_metric_unit_contract_mismatch_is_refused(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["bundle-comparator-1"]["metrics"][0]["unit"] = "percent"
    registry, request = _write_request(tmp_path, payloads)
    eligibility = registry.check_eligibility(request)
    assert not eligibility.eligible
    assert "bundle_metric_contract_mismatch" in eligibility.reason_codes


def test_contextual_stage_mismatch_keeps_shadow_delta(tmp_path: Path) -> None:
    payloads = _payloads()
    spec = payloads["comparison_stability_spec"]
    spec["required_equal_fields"].remove("target_stage")
    spec["contextual_fields"] = ["target_stage"]
    other = _ref("target-stage:other")
    payloads["bundle-comparator-1"]["target_stage_ref"] = other
    payloads["comparison_case_manifest"]["groups"][1]["target_stage_ref"] = other
    registry, request = _write_request(tmp_path, payloads)
    run = registry.run(request)
    assert run.result["comparison_eligibility"] == "contextual_comparator"
    assert run.result["metric_contrasts"][0]["contrast_state"] == "shadow"
    assert "contextual_comparison_only" in run.result["metric_contrasts"][0]["reason_codes"]


def test_required_assay_mismatch_is_not_comparable(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["bundle-comparator-1"]["product_case"]["assay"] = "snRNA-seq"
    registry, request = _write_request(tmp_path, payloads)
    run = registry.run(request)
    assert run.result["comparison_eligibility"] == "not_comparable"
    assert run.result["profile_state"] == "not_assessed"
    assert run.result["metric_contrasts"][0]["delta_comparator_minus_baseline"] is None


def test_complete_protocol_confounding_is_not_estimable(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["bundle-comparator-1"]["protocol_refs"] = [_ref("protocol:other")]
    registry, request = _write_request(tmp_path, payloads)
    run = registry.run(request)
    assert run.result["comparison_eligibility"] == "not_estimable"
    assert run.result["confounded_factors"] == ["protocol"]
    assert run.result["metric_contrasts"][0]["contrast_state"] == "not_comparable"


def test_missing_confounder_metadata_is_not_comparable(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["bundle-comparator-1"]["protocol_refs"] = []
    registry, request = _write_request(tmp_path, payloads)
    run = registry.run(request)
    assert run.result["comparison_eligibility"] == "not_comparable"
    assert "confounding_metadata_missing_protocol" in run.reason_codes


def test_reference_ood_group_is_not_rankable(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["comparison_case_manifest"]["groups"][1]["role"] = "reference_ood"
    registry, request = _write_request(tmp_path, payloads)
    run = registry.run(request)
    assert run.result["comparison_eligibility"] == "reference_or_ood"
    assert run.result["metric_contrasts"][0]["delta_comparator_minus_baseline"] is None


def test_replicated_groups_report_descriptive_ranges(tmp_path: Path) -> None:
    registry, request = _write_request(tmp_path, _payloads(replicated=True))
    run = registry.run(request)
    assert run.execution_state.value == "succeeded"
    assert all(
        group["independent_preparation_count"] == 2
        for group in run.result["stability_results"]
    )
    assert all(
        group["metric_stability"][0]["state"] == "replicated_descriptive"
        for group in run.result["stability_results"]
    )


def test_direct_v1_request_is_typed_refusal(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    spec = registry.describe("P0-07")
    request = ToolRequest(
        request_id="legacy-request",
        tool_id="P0-07",
        tool_version="0.3.0",
        output_dir=tmp_path.resolve(),
    )
    eligibility = adapter.check_eligibility(request, spec)
    assert not eligibility.eligible
    assert eligibility.reason_codes == ["tool_request_v2_required"]
