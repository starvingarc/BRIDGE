from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

import bridge.tool_packages.p0_07_comparison.adapter as adapter_module
from bridge.tool_packages.p0_07_comparison.adapter import adapter
from bridge.tool_packages.p0_07_comparison.models import PUBLIC_SCHEMA_MODELS
from bridge.toolkit.contracts import (
    ExecutionState,
    ImplementationState,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
)
from bridge.toolkit.registry import ToolRegistry
from tests.p0_biological_units import (
    bind_reviewed_biological_units,
    canonical_sha256,
)


ROLE_SCHEMAS = {
    "comparison_spec": "bridge://schemas/comparison-spec/v0.1",
    "comparison_evidence_bundle": (
        "bridge://schemas/comparison-evidence-bundle/v0.1"
    ),
}


def _ref(object_id: str, version: str = "1.0.0") -> dict[str, str]:
    return {"object_id": object_id, "object_version": version}


def _snapshot() -> dict:
    return {
        "product_definition_ref": _ref("product-definition:configured"),
        "target_context_ref": _ref("target-context:configured"),
        "assay_ref": _ref("assay:configured"),
        "sampling_context_ref": _ref("sampling-context:configured"),
        "reference_snapshot_ref": _ref("reference-snapshot:configured"),
        "prior_snapshot_ref": _ref("prior-snapshot:configured"),
        "measurement_spec_ref": _ref("measurement-spec:configured"),
        "score_contract_ref": None,
        "algorithm_ref": _ref("algorithm:configured"),
        "preprocessing_ref": _ref("preprocessing:configured"),
    }


def _preparation(case_slug: str, index: int, value: float) -> dict:
    return {
        "preparation_ref": _ref(f"preparation:{case_slug}-{index}"),
        "metrics": [
            {
                "metric_id": "metric:configured-primary",
                "unit": "configured-unit",
                "value": value,
                "denominator": 100,
                "evidence_state": "measured",
                "evidence_refs": [f"evidence:{case_slug}-{index}"],
            }
        ],
    }


def _sufficiency_result(case_slug: str, digest: str) -> dict:
    case_ref = _ref(f"product-case:{case_slug}")
    profile_id = f"evidence-sufficiency-profile:{digest}:target_identity"
    profile = {
        "profile_id": profile_id,
        "profile_version": "0.1.0",
        "gate_rule_spec_ref": "GATE-EVIDENCE-SUFFICIENCY-v0.1",
        "gate_rule_version": "0.1.0",
        "product_case_ref": case_ref,
        "product_definition_ref": _ref("product-definition:configured"),
        "domain_id": "target_identity",
        "measurement_spec_ref": _ref("measurement-spec:configured"),
        "score_contract_ref": None,
        "data_readiness": "adequate",
        "data_reason_codes": [],
        "qc_profile_ref": _ref(f"qc-profile:{case_slug}", "0.1.0"),
        "model_robustness": "validated_applicable",
        "robustness_reason_codes": [],
        "validation_refs": [],
        "prior_applicability": "not_required",
        "prior_reason_codes": [],
        "snapshot_refs": [],
        "evidence_sufficiency_state": "sufficient",
        "blocking_reasons": [],
        "limiting_reasons": [],
        "missing_requirements": [],
        "domain_score": None,
        "score_state": "unavailable",
        "score_reason_codes": ["p0_score_contract_unavailable"],
        "measurement_result_refs": [],
        "measurement_result_bindings": [],
        "measurement_evidence_state_counts": _empty_measurement_counts(),
        "evidence_refs": [f"evidence:sufficiency-{case_slug}"],
        "sensitivity_refs": [],
        "deduplicated_evidence_family_ids": [],
        "created_at": "2026-08-24T00:00:00Z",
        "deterministic_run_ref": f"run-{digest}",
    }
    return {
        "result_id": f"evidence-sufficiency-result:{digest}",
        "result_version": "0.1.0",
        "gate_rule_spec_ref": "GATE-EVIDENCE-SUFFICIENCY-v0.1",
        "profiles": [profile],
        "case_summary": {
            "summary_id": f"case-evidence-readiness-summary:{digest}",
            "summary_version": "0.1.0",
            "product_case_ref": case_ref,
            "profile_count": 1,
            "evidence_sufficiency_counts": {
                "sufficient": 1,
                "limited": 0,
                "insufficient": 0,
                "not_assessed": 0,
            },
            "measurement_evidence_state_counts": _empty_measurement_counts(),
            "score_state_counts": {"unavailable": 1},
            "blocking_reasons": [],
        },
        "gate_trace": [
            {
                "profile_ref": profile_id,
                "domain_gate_input_ref": f"domain-gate-input:{case_slug}",
                "evaluated_precedence": [
                    "not_assessed",
                    "insufficient",
                    "limited",
                    "sufficient",
                ],
                "selected_state": "sufficient",
                "selected_reason_codes": [],
                "ignored_duplicate_input_refs": [],
            }
        ],
    }


def _empty_measurement_counts() -> dict[str, int]:
    return {
        "measured": 0,
        "inferred": 0,
        "prior_only": 0,
        "negative": 0,
        "missing": 0,
        "unknown": 0,
        "unavailable": 0,
        "alert": 0,
    }


def _payloads() -> dict[str, dict]:
    baseline_ref = _ref("product-case:baseline")
    candidate_ref = _ref("product-case:candidate")
    payloads = {
        "product_cases": [
            {
                "object_version": "0.1.0",
                "product_case_id": f"product-case:{case_slug}",
                "case_version": "1.0.0",
                "product_definition_ref": _ref("product-definition:configured"),
                "sample_or_preparation_ref": _ref(
                    f"preparation:{case_slug}-parent"
                ),
                "biological_unit_refs": [
                    _ref(f"preparation:{case_slug}-1"),
                    _ref(f"preparation:{case_slug}-2"),
                ],
                "measurement_spec_ref": _ref("measurement-spec:configured"),
                "assay": "scRNA-seq",
                "provenance_refs": [_ref("source:fully-synthetic", "1")],
                "created_at": "2026-08-24T00:00:00Z",
            }
            for case_slug in ("baseline", "candidate")
        ],
        "comparison_spec": {
            "object_version": "0.1.0",
            "comparison_spec_id": "comparison-spec:configured",
            "comparison_spec_version": "1.0.0",
            "cases": [
                {"role": "baseline", "product_case_ref": baseline_ref},
                {"role": "candidate", "product_case_ref": candidate_ref},
            ],
            "required_equal_dimensions": [
                "product_definition",
                "target_context",
                "assay",
                "sampling_context",
                "reference_snapshot",
                "prior_snapshot",
                "measurement_spec",
                "algorithm",
                "preprocessing",
            ],
            "dimension_mismatch_policy": "contextual_comparator",
            "comparison_mode": "descriptive_only",
            "minimum_biological_units_per_case": 2,
            "metrics": [
                {
                    "metric_id": "metric:configured-primary",
                    "unit": "configured-unit",
                    "direction_policy": "higher_is_favorable",
                    "required": True,
                    "eligible_evidence_states": ["measured", "inferred"],
                }
            ],
            "missing_metric_policy": "report_unavailable",
            "pareto_policy": "not_assessed_without_score_contract",
        },
        "comparison_evidence_bundle": {
            "object_version": "0.1.0",
            "evidence_bundle_id": "comparison-evidence-bundle:configured",
            "evidence_bundle_version": "1.0.0",
            "cases": [
                {
                    "product_case_ref": baseline_ref,
                    "contract_snapshot": _snapshot(),
                    "sufficiency_summary_ref": _ref(
                        "case-evidence-readiness-summary:1111111111111111", "0.1.0"
                    ),
                    "preparations": [
                        _preparation("baseline", 1, 1.0),
                        _preparation("baseline", 2, 3.0),
                    ],
                },
                {
                    "product_case_ref": candidate_ref,
                    "contract_snapshot": _snapshot(),
                    "sufficiency_summary_ref": _ref(
                        "case-evidence-readiness-summary:2222222222222222", "0.1.0"
                    ),
                    "preparations": [
                        _preparation("candidate", 1, 2.0),
                        _preparation("candidate", 2, 4.0),
                    ],
                },
            ],
        },
        "evidence_sufficiency_run_results": [
            _sufficiency_result("baseline", "1111111111111111"),
            _sufficiency_result("candidate", "2222222222222222"),
        ],
    }
    payloads["biological_unit_manifests"] = []
    for case_slug, product_case in zip(
        ("baseline", "candidate"), payloads["product_cases"], strict=True
    ):
        holder = {"product_case": product_case}
        bind_reviewed_biological_units(
            holder,
            {
                "view_id": f"data-view:{case_slug}:qc-selected",
                "sha256": ("b" if case_slug == "baseline" else "c") * 64,
                "observation_ids_sha256": (
                    "d" if case_slug == "baseline" else "e"
                ) * 64,
                "n_observations": 2,
            },
            slug=case_slug,
            units=[
                (
                    f"preparation:{case_slug}-1@1.0.0",
                    f"sample:{case_slug}-1@1.0.0",
                ),
                (
                    f"preparation:{case_slug}-2@1.0.0",
                    f"sample:{case_slug}-2@1.0.0",
                ),
            ],
        )
        payloads["biological_unit_manifests"].append(
            holder["biological_unit_manifest"]
        )
    return payloads


def _write_json(path: Path, payload: dict) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    path.write_bytes(encoded)
    return hashlib.sha256(encoded).hexdigest()


def _request(
    tmp_path: Path,
    *,
    payloads: dict[str, dict] | None = None,
    output_dir: Path | None = None,
    input_id_prefix: str = "input",
    random_seed: int = 0,
) -> ToolRequestV2:
    values = deepcopy(payloads or _payloads())
    input_root = tmp_path / f"objects-{input_id_prefix}"
    input_root.mkdir(parents=True)
    refs: list[StructuredInputRef] = []
    for index, role in enumerate(ROLE_SCHEMAS, start=1):
        path = input_root / f"{role}.json"
        digest = _write_json(path, values[role])
        refs.append(
            StructuredInputRef(
                input_id=f"{input_id_prefix}-{index}",
                role=role,
                schema_ref=ROLE_SCHEMAS[role],
                object_version="0.1.0",
                path=path,
                sha256=digest,
                media_type="application/json",
            )
        )
    for product_case in values["product_cases"]:
        offset = len(refs) + 1
        path = input_root / f"product_case_{offset}.json"
        digest = _write_json(path, product_case)
        refs.append(
            StructuredInputRef(
                input_id=f"{input_id_prefix}-{offset}",
                role="product_case",
                schema_ref="bridge://schemas/product-case/v0.1",
                object_version="0.1.0",
                path=path,
                sha256=digest,
                media_type="application/json",
            )
        )
    for offset, result in enumerate(
        values["evidence_sufficiency_run_results"],
        start=len(refs) + 1,
    ):
        path = input_root / f"evidence_sufficiency_run_result_{offset}.json"
        digest = _write_json(path, result)
        refs.append(
            StructuredInputRef(
                input_id=f"{input_id_prefix}-{offset}",
                role="evidence_sufficiency_run_result",
                schema_ref="bridge://schemas/evidence-sufficiency-run-result/v0.1",
                object_version="0.1.0",
                path=path,
                sha256=digest,
                media_type="application/json",
            )
        )
    for manifest in values["biological_unit_manifests"]:
        offset = len(refs) + 1
        path = input_root / f"biological_unit_manifest_{offset}.json"
        digest = _write_json(path, manifest)
        refs.append(
            StructuredInputRef(
                input_id=f"{input_id_prefix}-{offset}",
                role="biological_unit_manifest",
                schema_ref="bridge://schemas/biological-unit-manifest/v0.1",
                object_version="0.1.0",
                path=path,
                sha256=digest,
                media_type="application/json",
            )
        )
    return ToolRequestV2(
        request_id=f"request-{input_id_prefix}",
        tool_id="P0-07",
        tool_version="0.2.0",
        output_dir=output_dir or (tmp_path / "output"),
        random_seed=random_seed,
        object_inputs=refs,
    )


def test_p0_07_is_an_implemented_v2_package() -> None:
    spec = ToolRegistry.load_default().describe("P0-07")

    assert isinstance(spec, ToolPackageSpecV2)
    assert spec.implementation_state is ImplementationState.IMPLEMENTED
    assert spec.result_schema_ref == "bridge://schemas/comparison-record/v0.1"
    assert spec.adapter_ref == (
        "bridge.tool_packages.p0_07_comparison.adapter:adapter"
    )


@pytest.mark.parametrize("schema_ref,model", PUBLIC_SCHEMA_MODELS.items())
def test_public_models_emit_valid_draft_2020_12_schemas(
    schema_ref: str, model: type
) -> None:
    schema = model.model_json_schema()
    schema["$id"] = schema_ref
    Draft202012Validator.check_schema(schema)


def test_configured_pairwise_comparison_runs(tmp_path: Path) -> None:
    run = ToolRegistry.load_default().run(_request(tmp_path))

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["result_state"] == "complete"
    assert run.result["comparability_state"] == "strictly_comparable"
    metric = run.result["metric_comparisons"][0]
    assert metric["baseline"]["mean"] == 2.0
    assert metric["candidate"]["mean"] == 3.0
    assert metric["raw_delta_candidate_minus_baseline"] == 1.0
    assert metric["direction_relation"] == "candidate_higher"
    assert metric["configured_interpretation"] == (
        "configured_favorable_direction"
    )
    assert run.result["pareto_assessment"]["assessment_state"] == "not_assessed"
    assert run.result["overall_score"] is None
    assert run.result["overall_rank"] is None
    assert run.result["score_state"] == "shadow"
    assert run.measurements == []
    assert len(run.artifacts) == 1
    assert not any(
        ref.input_id in json.dumps(run.result, sort_keys=True)
        for ref in run.request.object_inputs
    )


def test_direction_is_controlled_only_by_comparison_spec(tmp_path: Path) -> None:
    baseline = ToolRegistry.load_default().run(_request(tmp_path / "baseline"))
    payloads = _payloads()
    payloads["comparison_spec"]["metrics"][0]["direction_policy"] = (
        "lower_is_favorable"
    )
    changed = ToolRegistry.load_default().run(
        _request(tmp_path / "changed", payloads=payloads)
    )

    assert baseline.result["metric_comparisons"][0][
        "configured_interpretation"
    ] == "configured_favorable_direction"
    assert changed.result["metric_comparisons"][0][
        "configured_interpretation"
    ] == "configured_unfavorable_direction"
    assert baseline.run_id != changed.run_id


def test_missing_metric_remains_unavailable_not_zero(tmp_path: Path) -> None:
    payloads = _payloads()
    metric = payloads["comparison_evidence_bundle"]["cases"][1]["preparations"][0][
        "metrics"
    ][0]
    metric.update({"evidence_state": "missing", "value": None, "denominator": None})
    payloads["comparison_evidence_bundle"]["cases"][1]["preparations"][1][
        "metrics"
    ] = [
        {
            "metric_id": "metric:configured-other",
            "unit": "configured-unit",
            "value": 4.0,
            "denominator": 100,
            "evidence_state": "measured",
            "evidence_refs": ["evidence:candidate-other"],
        }
    ]
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    result = run.result["metric_comparisons"][0]
    assert run.result["result_state"] == "not_assessed"
    assert result["candidate"]["mean"] is None
    assert result["raw_delta_candidate_minus_baseline"] is None
    assert result["result_state"] == "unavailable"
    assert "metric_value_unavailable" in result["reason_codes"]
    assert "metric_missing_for_preparation" in result["reason_codes"]


def test_contract_mismatch_can_be_contextual_without_hiding_raw_delta(
    tmp_path: Path,
) -> None:
    payloads = _payloads()
    payloads["comparison_evidence_bundle"]["cases"][1]["contract_snapshot"][
        "assay_ref"
    ] = _ref("assay:different")
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.PARTIAL
    assert run.result["comparability_state"] == "contextual_comparator"
    assert run.result["metric_comparisons"][0][
        "raw_delta_candidate_minus_baseline"
    ] == 1.0
    assert run.result["metric_comparisons"][0][
        "configured_interpretation"
    ] == "no_directional_interpretation"
    assert "required_contract_dimension_mismatch" in run.reason_codes


def test_not_comparable_blocks_delta_instead_of_ranking(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["comparison_spec"]["dimension_mismatch_policy"] = "not_comparable"
    payloads["comparison_evidence_bundle"]["cases"][1]["contract_snapshot"][
        "assay_ref"
    ] = _ref("assay:different")
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.result["result_state"] == "not_assessed"
    assert run.result["comparability_state"] == "not_comparable"
    assert run.result["metric_comparisons"][0][
        "raw_delta_candidate_minus_baseline"
    ] is None
    assert run.result["score_state"] == "unavailable"


def test_unit_mismatch_is_unavailable(tmp_path: Path) -> None:
    payloads = _payloads()
    for preparation in payloads["comparison_evidence_bundle"]["cases"][1][
        "preparations"
    ]:
        preparation["metrics"][0]["unit"] = "different-unit"
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    metric = run.result["metric_comparisons"][0]
    assert metric["candidate"]["mean"] is None
    assert "metric_unit_mismatch" in metric["reason_codes"]


def test_preparation_and_sufficiency_gates_are_descriptive(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["comparison_spec"]["minimum_biological_units_per_case"] = 3
    candidate_summary = payloads["evidence_sufficiency_run_results"][1][
        "case_summary"
    ]
    candidate_summary["evidence_sufficiency_counts"].update(
        {"sufficient": 0, "limited": 1}
    )
    candidate_result = payloads["evidence_sufficiency_run_results"][1]
    candidate_result["profiles"][0].update(
        {
            "evidence_sufficiency_state": "limited",
            "limiting_reasons": ["data_readiness_limited"],
        }
    )
    candidate_result["gate_trace"][0].update(
        {
            "selected_state": "limited",
            "selected_reason_codes": ["data_readiness_limited"],
        }
    )
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.PARTIAL
    assert run.result["result_state"] == "partial"
    assert "biological_units_below_configured_minimum" in run.reason_codes
    assert "case_evidence_sufficiency_not_sufficient" in run.reason_codes
    assert run.result["metric_comparisons"][0][
        "raw_delta_candidate_minus_baseline"
    ] == 1.0
    assert run.result["metric_comparisons"][0][
        "configured_interpretation"
    ] == "no_directional_interpretation"


def test_case_binding_mismatch_is_typed(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["comparison_spec"]["cases"][1]["product_case_ref"] = _ref(
        "product-case:other"
    )
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["comparison_case_binding_mismatch"]
    assert run.result is None
    assert run.artifacts == []


def test_all_non_score_comparability_dimensions_are_required(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["comparison_spec"]["required_equal_dimensions"].remove("algorithm")

    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_schema_invalid"]


def test_biological_units_must_match_product_case_declaration(
    tmp_path: Path,
) -> None:
    payloads = _payloads()
    payloads["product_cases"][1]["biological_unit_refs"][1] = _ref(
        "preparation:candidate-other"
    )

    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == [
        "comparison_biological_unit_manifest_binding_mismatch"
    ]


def test_preparation_must_be_declared_by_manifest(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["comparison_evidence_bundle"]["cases"][1]["preparations"][1][
        "preparation_ref"
    ] = _ref("preparation:candidate-other")

    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["comparison_biological_unit_binding_mismatch"]


def test_cross_arm_biological_unit_overlap_is_rejected(tmp_path: Path) -> None:
    payloads = _payloads()
    shared = _ref("sample:baseline-1")
    candidate_manifest = payloads["biological_unit_manifests"][1]
    candidate_manifest["unit_bindings"][0]["independence_group_ref"] = shared
    candidate_manifest["unit_bindings"][0]["sample_ref"] = shared
    candidate_case = payloads["product_cases"][1]
    candidate_case["biological_unit_refs"] = [
        shared,
        _ref("sample:candidate-2"),
    ]
    candidate_case["biological_unit_manifest_sha256"] = canonical_sha256(
        candidate_manifest
    )

    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["comparison_biological_unit_overlap"]


def test_score_contract_is_refused_until_a_contract_exists(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["comparison_evidence_bundle"]["cases"][0]["contract_snapshot"][
        "score_contract_ref"
    ] = _ref("score-contract:not-frozen")
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["score_contract_not_supported"]


@pytest.mark.parametrize(
    ("surface", "unsafe_unit"),
    [
        ("comparison_spec", "/home/demo-user/private"),
        ("comparison_evidence_bundle", "~/demo-private"),
        ("comparison_evidence_bundle", "${HOME}/demo-private"),
    ],
)
def test_machine_local_unit_is_not_published(
    tmp_path: Path, surface: str, unsafe_unit: str
) -> None:
    payloads = _payloads()
    if surface == "comparison_spec":
        payloads[surface]["metrics"][0]["unit"] = unsafe_unit
    else:
        payloads[surface]["cases"][0]["preparations"][0]["metrics"][0][
            "unit"
        ] = unsafe_unit

    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_schema_invalid"]
    assert run.result is None
    assert run.artifacts == []
    assert unsafe_unit not in json.dumps(run.model_dump(mode="json"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("value", "1.0"),
        ("value", True),
        ("denominator", "100"),
        ("denominator", True),
    ],
)
def test_scientific_numeric_coercion_is_rejected(
    tmp_path: Path, field: str, value: object
) -> None:
    payloads = _payloads()
    payloads["comparison_evidence_bundle"]["cases"][0]["preparations"][0][
        "metrics"
    ][0][field] = value
    run = adapter.run(
        _request(tmp_path, payloads=payloads),
        ToolRegistry.load_default().describe("P0-07"),
    )

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_schema_invalid"]


def test_nonzero_random_seed_is_refused(tmp_path: Path) -> None:
    run = ToolRegistry.load_default().run(_request(tmp_path, random_seed=7))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["p0_07_random_seed_forbidden"]


def test_input_id_renaming_reuses_same_scientific_bundle(tmp_path: Path) -> None:
    first = ToolRegistry.load_default().run(
        _request(
            tmp_path / "first",
            output_dir=tmp_path / "output",
            input_id_prefix="alpha",
        )
    )
    second = ToolRegistry.load_default().run(
        _request(
            tmp_path / "second",
            output_dir=tmp_path / "output",
            input_id_prefix="beta",
        )
    )

    assert first.run_id == second.run_id
    assert first.input_hash == second.input_hash
    assert first.result == second.result
    assert first.artifacts[0].sha256 == second.artifacts[0].sha256


def test_existing_output_file_returns_typed_failure(tmp_path: Path) -> None:
    output = tmp_path / "occupied"
    output.write_text("keep", encoding="utf-8")
    run = ToolRegistry.load_default().run(
        _request(tmp_path / "request", output_dir=output)
    )

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["output_dir_not_regular_directory"]
    assert output.read_text(encoding="utf-8") == "keep"


def test_v1_request_is_refused_without_bare_exception(tmp_path: Path) -> None:
    request = ToolRequest(request_id="v1", tool_id="P0-07", output_dir=tmp_path)
    spec = ToolRegistry.load_default().describe("P0-07")

    eligibility = adapter.check_eligibility(request, spec)
    run = adapter.run(request, spec)

    assert eligibility.reason_codes == ["tool_request_v2_required"]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["tool_request_v2_required"]


def test_registry_detects_input_mutation_during_adapter_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path)
    target = request.object_inputs[0].path
    original = adapter_module.evaluate_comparison

    def mutate_input(**kwargs):
        result = original(**kwargs)
        target.write_text("{}", encoding="utf-8")
        return result

    monkeypatch.setattr(adapter_module, "evaluate_comparison", mutate_input)
    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["input_asset_modified_during_run"]
    assert run.result is None
    assert run.artifacts == []


def test_implementation_contains_no_biological_program_or_threshold() -> None:
    package = Path(adapter_module.__file__).parent
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(package.glob("*.py"))
    )

    for biological_term in (
        "MKI67",
        "FOXA2",
        "LMX1A",
        "ventral midbrain",
        "fetal",
        "scRNA-seq",
        "snRNA-seq",
        "0.05",
    ):
        assert biological_term not in source


def test_tool_run_timestamp_is_deterministic(tmp_path: Path) -> None:
    run = ToolRegistry.load_default().run(_request(tmp_path))

    assert run.created_at == datetime(1970, 1, 1, tzinfo=timezone.utc)
