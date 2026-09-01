from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path

import pytest

from bridge.tool_packages.p0_07_product_comparison_stability.adapter import adapter
from bridge.tool_packages.p0_07_product_comparison_stability.models import (
    ComparisonCaseManifest,
    ComparisonMethodBundle,
    ComparisonMethodInput,
    ComparisonMethodSpec,
    ComparisonStabilitySpec,
    ProductComparisonStabilityProfile,
    ProductEvidenceBundle,
)
from bridge.tool_packages.p0_07_product_comparison_stability.visualization_data import (
    MetricDifferenceRecord,
    MetricStabilityVisualizationRecord,
    P007VisualizationArtifactSet,
    ProductComparisonVisualizationDataV1,
    build_product_comparison_visualization_data,
)
from bridge.toolkit.contracts import ToolRequest
from bridge.toolkit.registry import ToolRegistry

adapter_module = importlib.import_module(
    "bridge.tool_packages.p0_07_product_comparison_stability.adapter"
)

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
                "bundle-comparator-2": _bundle("comparator-2", "group-comparator", 0.7),
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


def _add_comparator_group(
    payloads: dict[str, object],
    *,
    slug: str,
    value: float,
    protocol_ref: str = "protocol:shared",
) -> None:
    group_id = f"group-{slug}"
    bundle = _bundle(slug, group_id, value)
    bundle["protocol_refs"] = [_ref(protocol_ref)]
    payloads[f"bundle-{slug}"] = bundle
    payloads["comparison_case_manifest"]["groups"].append(
        {
            "group_id": group_id,
            "role": "comparator",
            "product_definition_ref": _ref("product-definition:demo"),
            "target_stage_ref": _ref("target-stage:demo"),
            "bundle_refs": [_ref(bundle["bundle_id"])],
        }
    )


def _role(key: str) -> str:
    return (
        key
        if key
        in {
            "comparison_stability_spec",
            "comparison_case_manifest",
            "comparison_method_spec",
            "comparison_method_input",
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
            "tool_version": "0.4.0",
            "output_dir": str((tmp_path / output_name).resolve()),
            "assets": [],
            "measurement_spec_ref": None,
            "parameters": {},
            "random_seed": 0,
            "object_inputs": refs,
        }
    )
    return registry, request


def _build_visualization(
    tmp_path: Path, payloads: dict[str, object]
) -> tuple[object, object]:
    registry, request = _write_request(tmp_path, payloads)
    run = registry.run(request)
    method_spec = (
        ComparisonMethodSpec.model_validate(payloads["comparison_method_spec"])
        if "comparison_method_spec" in payloads
        else None
    )
    method_input = (
        ComparisonMethodInput.model_validate(payloads["comparison_method_input"])
        if "comparison_method_input" in payloads
        else None
    )
    method_artifact = next(
        (item for item in run.artifacts if item.kind == "comparison_method_bundle"),
        None,
    )
    method_bundle = (
        ComparisonMethodBundle.model_validate_json(method_artifact.path.read_text())
        if method_artifact is not None
        else None
    )
    profile = build_product_comparison_visualization_data(
        run_id=run.run_id,
        tool_version=run.tool_version,
        result=ProductComparisonStabilityProfile.model_validate(run.result),
        spec=ComparisonStabilitySpec.model_validate(
            payloads["comparison_stability_spec"]
        ),
        manifest=ComparisonCaseManifest.model_validate(
            payloads["comparison_case_manifest"]
        ),
        bundles=[
            ProductEvidenceBundle.model_validate(value)
            for key, value in payloads.items()
            if key.startswith("bundle-")
        ],
        method_spec=method_spec,
        method_input=method_input,
        method_bundle=method_bundle,
        method_bundle_sha256=(
            method_artifact.sha256 if method_artifact is not None else None
        ),
    )
    return run, profile


def _load_visualization_data(run: object) -> ProductComparisonVisualizationDataV1:
    artifact = next(
        item
        for item in run.artifacts
        if item.kind == "product_comparison_visualization_data"
    )
    return ProductComparisonVisualizationDataV1.model_validate_json(
        artifact.path.read_text()
    )


def _load_visualization_artifact_set(run: object) -> P007VisualizationArtifactSet:
    artifact = next(
        item for item in run.artifacts if item.kind == "visualization_artifact_set"
    )
    return P007VisualizationArtifactSet.model_validate_json(artifact.path.read_text())


def test_registry_exposes_p0_07_v2_runtime() -> None:
    registry = ToolRegistry.load_default()
    spec = registry.describe("P0-07")
    assert spec.version == "0.4.0"
    assert spec.implementation_state.value == "implemented"
    assert registry.request_model("P0-07").__name__ == "ToolRequestV2"


def test_valid_run_is_descriptive_shadow_without_rank(tmp_path: Path) -> None:
    registry, request = _write_request(tmp_path, _payloads())
    assert registry.check_eligibility(request).eligible
    run = registry.run(request)
    assert run.execution_state.value == "succeeded"
    assert len(run.artifacts) == 16
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
    assert len(first.artifacts) == len(second.artifacts) == 16
    assert [item.sha256 for item in first.artifacts] == [
        item.sha256 for item in second.artifacts
    ]


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
    assert (
        "contextual_comparison_only"
        in run.result["metric_contrasts"][0]["reason_codes"]
    )


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


def test_visualization_preserves_preparation_values_and_descriptive_semantics(
    tmp_path: Path,
) -> None:
    _, profile = _build_visualization(tmp_path, _payloads(replicated=True))

    assert len(profile.preparation_records) == 4
    assert sorted(item.raw_value for item in profile.preparation_records) == [
        0.4,
        0.5,
        0.6,
        0.7,
    ]
    assert all(
        item.interval_semantics == "not_declared" and not item.render_interval
        for item in profile.preparation_records
    )
    assert {item.independence_state for item in profile.preparation_records} == {
        "not_recorded"
    }
    assert all(
        item.declared_independence_group_count is None
        for item in profile.preparation_records
    )
    difference = profile.difference_records[0]
    assert difference.raw_delta == pytest.approx(0.2)
    assert difference.uncertainty_state == "not_available"
    assert difference.preparation_record_ids == [
        item.record_id
        for item in profile.preparation_records
    ]
    assert difference.stability_record_ids == [
        item.record_id for item in profile.stability_records
    ]
    assert profile.producer_run_ref.startswith("run:run-")
    ranges = {item.group_id: item for item in profile.stability_records}
    assert ranges["group-baseline"].observed_min == pytest.approx(0.4)
    assert ranges["group-baseline"].observed_max == pytest.approx(0.5)
    assert ranges["group-baseline"].range_width == pytest.approx(0.1)
    assert ranges["group-comparator"].observed_min == pytest.approx(0.6)
    assert ranges["group-comparator"].observed_max == pytest.approx(0.7)
    assert ranges["group-comparator"].range_width == pytest.approx(0.1)
    assert {item.analysis_unit_coverage_state for item in ranges.values()} == {
        "multiple_analysis_units"
    }
    assert profile.overall_score is None
    assert profile.overall_rank is None
    assert profile.domain_score is None


@pytest.mark.parametrize("state", ["missing", "alert"])
def test_visualization_keeps_partial_preparation_evidence_without_zero_fill(
    tmp_path: Path,
    state: str,
) -> None:
    payloads = _payloads(replicated=True)
    metric = payloads["bundle-comparator-1"]["metrics"][0]
    if state == "missing":
        metric.update(
            raw_value=None,
            interval=None,
            denominator_value=None,
            evidence_state="missing",
        )
    else:
        metric["evidence_state"] = "alert"

    _, profile = _build_visualization(tmp_path, payloads)

    row = next(
        item
        for item in profile.preparation_records
        if item.analysis_unit_ref == "preparation:comparator-1@1.0.0"
    )
    if state == "missing":
        assert row.raw_value is None
        assert row.missingness == "unavailable"
    else:
        assert row.raw_value == pytest.approx(0.6)
        assert row.evidence_state.value == "alert"
    assert row.assessment_state == "not_assessed"
    assert profile.difference_records[0].raw_delta is None
    comparator = next(
        item
        for item in profile.stability_records
        if item.group_id == "group-comparator"
    )
    assert comparator.assessed_analysis_unit_count == 1
    assert comparator.analysis_unit_coverage_state == "incomplete"
    assert comparator.observed_min == pytest.approx(0.7)
    assert comparator.observed_max == pytest.approx(0.7)


def test_visualization_marks_contextual_and_blocked_comparisons(
    tmp_path: Path,
) -> None:
    contextual = _payloads()
    spec = contextual["comparison_stability_spec"]
    spec["required_equal_fields"].remove("target_stage")
    spec["contextual_fields"] = ["target_stage"]
    other = _ref("target-stage:other")
    contextual["bundle-comparator-1"]["target_stage_ref"] = other
    contextual["comparison_case_manifest"]["groups"][1]["target_stage_ref"] = other
    _, contextual_profile = _build_visualization(tmp_path / "contextual", contextual)
    target_stage = next(
        item
        for item in contextual_profile.design_records
        if item.dimension_id == "target_stage"
    )
    assert target_stage.design_state == "contextual_mismatch"
    assert contextual_profile.difference_records[0].raw_delta == pytest.approx(0.2)
    assert (
        contextual_profile.difference_records[0].applicability == "partially_applicable"
    )

    blocked = _payloads()
    blocked["bundle-comparator-1"]["product_case"]["assay"] = "snRNA-seq"
    _, blocked_profile = _build_visualization(tmp_path / "blocked", blocked)
    assay = next(
        item for item in blocked_profile.design_records if item.dimension_id == "assay"
    )
    assert assay.design_state == "required_mismatch"
    assert assay.blocks_numeric_difference
    assert blocked_profile.difference_records[0].raw_delta is None
    assert len(blocked_profile.preparation_records) == 2


def test_visualization_only_counts_complete_nonoverlapping_independence(
    tmp_path: Path,
) -> None:
    payloads = _payloads(replicated=True)
    for key, bundle in payloads.items():
        if not key.startswith("bundle-"):
            continue
        slug = bundle["bundle_id"].split(":")[-1]
        case = bundle["product_case"]
        case.update(
            biological_unit_manifest_ref=_ref(f"biological-unit-manifest:{slug}"),
            biological_unit_manifest_sha256=(slug[0] * 64),
            independence_scope_ref=_ref("independence-scope:demo"),
            independence_group_refs=[_ref(f"independence-group:{slug}")],
        )
    _, declared = _build_visualization(tmp_path / "declared", payloads)
    assert {item.independence_state for item in declared.preparation_records} == {
        "declared"
    }
    assert {
        item.declared_independence_group_count for item in declared.preparation_records
    } == {2}

    shared_payloads = _payloads(replicated=True)
    for key, bundle in shared_payloads.items():
        if not key.startswith("bundle-"):
            continue
        slug = bundle["bundle_id"].split(":")[-1]
        group_id = bundle["group_id"]
        bundle["product_case"].update(
            biological_unit_manifest_ref=_ref(
                f"biological-unit-manifest:{slug}"
            ),
            biological_unit_manifest_sha256=(slug[0] * 64),
            independence_scope_ref=_ref("independence-scope:demo"),
            independence_group_refs=[_ref(f"independence-group:{group_id}")],
        )
    _, shared = _build_visualization(tmp_path / "shared", shared_payloads)
    assert {item.independence_state for item in shared.preparation_records} == {
        "declared"
    }
    assert {
        item.declared_independence_group_count for item in shared.preparation_records
    } == {1}
    assert all(
        "declared_independence_group_shared_by_analysis_units"
        in item.reason_codes
        for item in shared.preparation_records
    )
    assert all(
        item.analysis_unit_coverage_state == "multiple_analysis_units"
        and item.applicability == "partially_applicable"
        for item in shared.stability_records
    )

    for key in ("bundle-baseline-1", "bundle-comparator-1"):
        payloads[key]["product_case"]["independence_group_refs"] = [
            _ref("independence-group:overlap")
        ]
    _, inconsistent = _build_visualization(tmp_path / "inconsistent", payloads)
    assert {item.independence_state for item in inconsistent.preparation_records} == {
        "inconsistent"
    }
    assert all(
        item.declared_independence_group_count is None
        for item in inconsistent.preparation_records
    )


def test_any_baseline_comparator_confounding_blocks_all_numeric_deltas(
    tmp_path: Path,
) -> None:
    payloads = _payloads()
    _add_comparator_group(
        payloads,
        slug="comparator-b",
        value=0.9,
        protocol_ref="protocol:exclusive",
    )
    registry, request = _write_request(tmp_path, payloads)

    run = registry.run(request)
    profile = _load_visualization_data(run)

    assert run.result["comparison_eligibility"] == "not_estimable"
    assert all(
        item["delta_comparator_minus_baseline"] is None
        for item in run.result["metric_contrasts"]
    )
    protocol = next(
        item for item in profile.design_records if item.dimension_id == "protocol"
    )
    assert protocol.design_state == "completely_confounded"
    assert protocol.blocks_numeric_difference
    assert all(item.raw_delta is None for item in profile.difference_records)


def test_visualization_artifact_links_and_capacity_fallback_are_explicit(
    tmp_path: Path,
) -> None:
    payloads = _payloads()
    for index in range(2, 5):
        _add_comparator_group(
            payloads,
            slug=f"comparator-{index}",
            value=0.6 + 0.1 * index,
        )
    registry, request = _write_request(tmp_path, payloads)

    run = registry.run(request)
    profile = _load_visualization_data(run)
    artifact_set = _load_visualization_artifact_set(run)
    data_artifact = next(
        item
        for item in run.artifacts
        if item.kind == "product_comparison_visualization_data"
    )

    assert artifact_set.data_profile_artifact_id == data_artifact.artifact_id
    assert artifact_set.data_profile_sha256 == data_artifact.sha256
    assert all(
        item.data_binding.artifact_id == data_artifact.artifact_id
        and item.data_binding.sha256 == data_artifact.sha256
        for item in artifact_set.visualizations
    )
    metric = next(
        item
        for item in artifact_set.visualizations
        if item.component_ref
        == "bridge.product-comparison.metric-differences@0.1.0"
    )
    comparability = next(
        item
        for item in artifact_set.visualizations
        if item.component_ref
        == "bridge.product-comparison.comparability@0.1.0"
    )
    assert metric.data_binding.records_path == "difference_records"
    assert "static_render_requires_table_fallback" in metric.missing_reason_codes
    assert (
        "static_render_requires_table_fallback"
        in comparability.missing_reason_codes
    )
    linked_preparations = {
        record_id
        for difference in profile.difference_records
        for record_id in difference.preparation_record_ids
    }
    assert linked_preparations == {
        item.record_id for item in profile.preparation_records
    }
    table_artifact = next(
        item
        for item in run.artifacts
        if item.artifact_id == metric.accessibility.table_artifact_id
    )
    table = table_artifact.path.read_text()
    assert all(
        record_type in table
        for record_type in (
            "preparation_metric",
            "metric_difference",
            "metric_stability",
        )
    )


@pytest.mark.parametrize(
    ("attribute", "reason_code"),
    [
        ("build_product_comparison_visualization_data", "visualization_data_invalid"),
        ("prepare_product_comparison_visualizations", "visualization_render_failed"),
    ],
)
def test_visualization_failure_leaves_no_partial_run_bundle(
    tmp_path: Path,
    monkeypatch,
    attribute: str,
    reason_code: str,
) -> None:
    registry, request = _write_request(tmp_path, _payloads())

    def fail(**_kwargs):
        raise ValueError("forced visualization failure")

    monkeypatch.setattr(adapter_module, attribute, fail)
    run = registry.run(request)

    assert run.execution_state.value == "failed"
    assert reason_code in run.reason_codes
    assert not request.output_dir.exists()


def test_visualization_models_reject_false_delta_and_range(
    tmp_path: Path,
) -> None:
    _, profile = _build_visualization(tmp_path, _payloads(replicated=True))
    difference = profile.difference_records[0].model_dump(mode="json")
    difference["raw_delta"] = 0.9
    with pytest.raises(ValueError, match="raw delta"):
        MetricDifferenceRecord.model_validate(difference)

    stability = profile.stability_records[0].model_dump(mode="json")
    stability["range_width"] = 9.0
    with pytest.raises(ValueError, match="range width"):
        MetricStabilityVisualizationRecord.model_validate(stability)

    payload = profile.model_dump(mode="json")
    payload["difference_records"][0]["preparation_record_ids"][-1] = (
        "preparation.999"
    )
    with pytest.raises(ValueError, match="preparation links"):
        ProductComparisonVisualizationDataV1.model_validate(payload)


def test_direct_v1_request_is_typed_refusal(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    spec = registry.describe("P0-07")
    request = ToolRequest(
        request_id="legacy-request",
        tool_id="P0-07",
        tool_version="0.4.0",
        output_dir=tmp_path.resolve(),
    )
    eligibility = adapter.check_eligibility(request, spec)
    assert not eligibility.eligible
    assert eligibility.reason_codes == ["tool_request_v2_required"]
