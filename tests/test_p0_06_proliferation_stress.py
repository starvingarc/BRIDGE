from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

import bridge.tool_packages.p0_06_proliferation_stress.adapter as adapter_module
from bridge.tool_packages.p0_06_proliferation_stress.adapter import adapter
from bridge.tool_packages.p0_06_proliferation_stress.models import (
    PUBLIC_SCHEMA_MODELS,
    ProliferationStressResponseProfile,
)
from bridge.toolkit.contracts import (
    ExecutionState,
    ImplementationState,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
)
from bridge.toolkit.registry import ToolRegistry


ROLE_SCHEMAS = {
    "product_case": "bridge://schemas/product-case/v0.1",
    "product_definition_card": "bridge://schemas/product-definition-card/v0.1",
    "program_assessment_spec": "bridge://schemas/program-assessment-spec/v0.1",
    "program_evidence_bundle": "bridge://schemas/program-evidence-bundle/v0.1",
    "developmental_compatibility_result": (
        "bridge://schemas/developmental-compatibility-result/v0.1"
    ),
    "qc_readiness_profile": "bridge://schemas/qc-readiness-profile/v0.1",
}
SHA = "a" * 64


def _role_fractions(active: str) -> list[dict]:
    return [
        {
            "role": role,
            "numerator": 100 if role == active else 0,
            "denominator": 100,
            "fraction": 1.0 if role == active else 0.0,
        }
        for role in ("earlier", "within_window", "later", "branch_shift", "unresolved")
    ]


def _payloads() -> dict[str, dict]:
    product_case_ref = {
        "object_id": "product-case:demo",
        "object_version": "1.0.0",
    }
    product_definition_ref = {
        "object_id": "product-definition:demo",
        "object_version": "1.0.0",
    }
    development_window_ref = {
        "object_id": "development-window-spec:demo",
        "object_version": "1.0.0",
    }
    developmental_result_ref = {
        "object_id": "developmental-result:0123456789abcdef",
        "object_version": "0.1.0",
    }
    cell_state_profile_ref = {
        "object_id": "cell-state-profile:demo",
        "object_version": "0.1.0",
    }
    rules = [
        {
            "rule_id": "program-review-rule:alpha",
            "program_ref": {
                "object_id": "program:alpha",
                "object_version": "1.0.0",
            },
            "analysis_scope": "whole_product",
            "state_ref": None,
            "stage_context_ref": development_window_ref,
            "applicable_assays": ["scRNA-seq"],
            "metric_name": "configured_metric",
            "unit": "arbitrary unit",
            "reference_lower": 0.2,
            "reference_upper": 0.8,
            "minimum_gene_coverage": 0.5,
            "eligible_evidence_states": ["measured", "inferred"],
            "minimum_independence_groups": 2,
            "review_direction": "above_reference",
            "orthogonal_follow_up_refs": ["assay:orthogonal-alpha"],
        },
        {
            "rule_id": "program-review-rule:beta",
            "program_ref": {
                "object_id": "program:beta",
                "object_version": "1.0.0",
            },
            "analysis_scope": "state_specific",
            "state_ref": {
                "object_id": "state:configured-beta",
                "object_version": "1.0.0",
            },
            "stage_context_ref": development_window_ref,
            "applicable_assays": ["scRNA-seq"],
            "metric_name": "configured_metric",
            "unit": "arbitrary unit",
            "reference_lower": -0.5,
            "reference_upper": 0.5,
            "minimum_gene_coverage": 0.4,
            "eligible_evidence_states": ["measured"],
            "minimum_independence_groups": 1,
            "review_direction": "outside_reference",
            "orthogonal_follow_up_refs": [],
        },
    ]
    observations = [
        {
            "observation_id": "program-observation:alpha-a",
            "rule_id": "program-review-rule:alpha",
            "program_ref": rules[0]["program_ref"],
            "analysis_unit_ref": {
                "object_id": "preparation:demo-a",
                "object_version": "1.0.0",
            },
            "evidence_family_id": "evidence-family:alpha-a",
            "independence_group": "independence-group:alpha-a",
            "method_ref": {
                "object_id": "method:configured-a",
                "object_version": "1.0.0",
            },
            "evidence_state": "measured",
            "value": 0.9,
            "gene_coverage": 0.9,
            "evidence_refs": ["evidence:program-alpha-a"],
        },
        {
            "observation_id": "program-observation:alpha-b",
            "rule_id": "program-review-rule:alpha",
            "program_ref": rules[0]["program_ref"],
            "analysis_unit_ref": {
                "object_id": "preparation:demo-b",
                "object_version": "1.0.0",
            },
            "evidence_family_id": "evidence-family:alpha-b",
            "independence_group": "independence-group:alpha-b",
            "method_ref": {
                "object_id": "method:configured-b",
                "object_version": "1.0.0",
            },
            "evidence_state": "inferred",
            "value": 1.0,
            "gene_coverage": 0.8,
            "evidence_refs": ["evidence:program-alpha-b"],
        },
        {
            "observation_id": "program-observation:beta-a",
            "rule_id": "program-review-rule:beta",
            "program_ref": rules[1]["program_ref"],
            "analysis_unit_ref": {
                "object_id": "preparation:demo-a",
                "object_version": "1.0.0",
            },
            "evidence_family_id": "evidence-family:beta-a",
            "independence_group": "independence-group:beta-a",
            "method_ref": {
                "object_id": "method:configured-a",
                "object_version": "1.0.0",
            },
            "evidence_state": "measured",
            "value": 0.1,
            "gene_coverage": 0.95,
            "evidence_refs": ["evidence:program-beta-a"],
        },
    ]
    return {
        "product_case": {
            "object_version": "0.1.0",
            "product_case_id": "product-case:demo",
            "case_version": "1.0.0",
            "product_definition_ref": product_definition_ref,
            "sample_or_preparation_ref": {
                "object_id": "preparation:demo",
                "object_version": "1.0.0",
            },
            "measurement_spec_ref": {
                "object_id": "measurement-spec:cell-state-demo",
                "object_version": "0.1.0",
            },
            "assay": "scRNA-seq",
            "provenance_refs": [
                {"object_id": "source:fully-synthetic", "object_version": "1"}
            ],
            "created_at": "2026-08-24T00:00:00Z",
        },
        "product_definition_card": {
            "object_version": "0.1.0",
            "product_definition_id": "product-definition:demo",
            "definition_version": "1.0.0",
            "state_role_map_ref": {
                "object_id": "state-role-map:demo",
                "object_version": "1.0.0",
            },
            "supported_assays": ["scRNA-seq"],
            "review_state": "draft",
            "provenance_refs": [
                {"object_id": "source:fully-synthetic", "object_version": "1"}
            ],
        },
        "program_assessment_spec": {
            "object_version": "0.1.0",
            "assessment_spec_id": "program-assessment-spec:demo",
            "assessment_spec_version": "1.0.0",
            "product_definition_ref": product_definition_ref,
            "development_window_ref": development_window_ref,
            "review_state": "draft",
            "rules": rules,
            "unmatched_observation_policy": "report_unmatched",
            "no_flag_policy": "cannot_resolve_without_validated_lod",
        },
        "program_evidence_bundle": {
            "object_version": "0.1.0",
            "evidence_bundle_id": "program-evidence-bundle:demo",
            "evidence_bundle_version": "1.0.0",
            "product_case_ref": product_case_ref,
            "product_definition_ref": product_definition_ref,
            "developmental_result_ref": developmental_result_ref,
            "cell_state_profile_ref": cell_state_profile_ref,
            "assay": "scRNA-seq",
            "observations": observations,
        },
        "developmental_compatibility_result": {
            "object_version": "0.1.0",
            "result_id": "developmental-result:0123456789abcdef",
            "tool_id": "P0-04",
            "tool_version": "0.2.0",
            "product_case_ref": product_case_ref,
            "product_definition_ref": product_definition_ref,
            "development_window_ref": development_window_ref,
            "cell_state_profile_ref": cell_state_profile_ref,
            "qc_profile_ref": {
                "object_id": "qc-profile:demo",
                "object_version": "0.1.0",
            },
            "input_sha256_by_role": {
                "product_case": SHA,
                "product_definition_card": SHA,
                "development_window_spec": SHA,
                "cell_state_evidence_profile": SHA,
                "qc_readiness_profile": SHA,
            },
            "result_state": "complete",
            "analysis_mode": "static_profile",
            "stage_composition_channels": [
                {
                    "composition_view": "consensus_supported_only",
                    "source_id": None,
                    "label_level": "L1",
                    "denominator_view": "all input observations",
                    "whole_product_denominator": 100,
                    "target_related_denominator": 100,
                    "whole_product_stage_fractions": _role_fractions("within_window"),
                    "target_related_stage_fractions": _role_fractions("within_window"),
                }
            ],
            "unmapped_states": [],
            "reference_stage_support": {
                "assessment_state": "not_assessed",
                "reason_code": "reference_stage_support_not_supplied",
            },
            "timecourse_profile": {
                "analysis_mode": "static_profile",
                "evidence_state": "unavailable",
                "reason_code": "true_timepoint_input_not_supplied",
            },
            "evidence_refs": ["evidence:developmental-demo"],
            "reason_codes": [
                "reference_stage_support_not_supplied",
                "true_timepoint_input_not_supplied",
            ],
            "domain_score": None,
            "score_state": "shadow",
        },
        "qc_readiness_profile": {
            "profile_id": "qc-profile:demo",
            "input_level": "analysis_ready",
            "assay": "scRNA-seq",
            "assay_spec_id": None,
            "measurement_spec_status": "candidate",
            "readiness_state": "ready",
            "schema_integrity": {},
            "metadata_completeness": {},
            "matrix_provenance": {},
            "upstream_library_qc": {},
            "cell_qc": {},
            "doublet_assessment": {},
            "cell_calling_assessment": {},
            "ambient_assessment": {},
            "data_views": {},
            "module_eligibility": {"P0-06": "eligible"},
            "missing_inputs": [],
            "blocking_issues": [],
            "warnings": [],
            "evidence_ids": ["evidence:qc-demo"],
            "score_state": "unavailable",
            "domain_score": None,
        },
    }


def _write_json(path: Path, payload: dict) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


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
    return ToolRequestV2(
        request_id=f"request-{input_id_prefix}",
        tool_id="P0-06",
        tool_version="0.2.0",
        output_dir=output_dir or (tmp_path / "output"),
        random_seed=random_seed,
        object_inputs=refs,
    )


def test_p0_06_is_an_implemented_v2_package() -> None:
    spec = ToolRegistry.load_default().describe("P0-06")

    assert isinstance(spec, ToolPackageSpecV2)
    assert spec.implementation_state is ImplementationState.IMPLEMENTED
    assert spec.result_schema_ref == (
        "bridge://schemas/proliferation-stress-response-profile/v0.1"
    )
    assert spec.adapter_ref == (
        "bridge.tool_packages.p0_06_proliferation_stress.adapter:adapter"
    )


@pytest.mark.parametrize("schema_ref,model", PUBLIC_SCHEMA_MODELS.items())
def test_public_models_emit_valid_draft_2020_12_schemas(
    schema_ref: str, model: type
) -> None:
    schema = model.model_json_schema()
    schema["$id"] = schema_ref
    Draft202012Validator.check_schema(schema)


def test_configured_program_evidence_runs(tmp_path: Path) -> None:
    run = ToolRegistry.load_default().run(_request(tmp_path))

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["result_state"] == "complete"
    assert run.result["domain_score"] is None
    assert run.result["score_state"] == "shadow"
    assert run.measurements == []
    assert run.visualizations == []
    assert len(run.artifacts) == 1
    results = {item["rule_id"]: item for item in run.result["program_results"]}
    assert results["program-review-rule:alpha"]["review_flag_state"] == (
        "transcriptomic_review_flag"
    )
    assert results["program-review-rule:alpha"][
        "triggering_independence_group_count"
    ] == 2
    assert results["program-review-rule:beta"]["review_flag_state"] == (
        "cannot_resolve"
    )
    assert "validated_lod_not_supplied" in results["program-review-rule:beta"][
        "reason_codes"
    ]
    assert run.result["process_attribution"]["assessment_state"] == "not_assessed"
    assert run.result["residual_pluripotency_lod"]["assessment_state"] == (
        "not_assessed"
    )
    assert run.result["transcriptomic_cnv"]["assessment_state"] == "not_assessed"
    assert not any(
        ref.input_id in json.dumps(run.result, sort_keys=True)
        for ref in run.request.object_inputs
    )


def test_result_schema_rejects_state_and_checksum_conflicts(tmp_path: Path) -> None:
    result = ToolRegistry.load_default().run(_request(tmp_path)).result
    validator = Draft202012Validator(
        ProliferationStressResponseProfile.model_json_schema()
    )

    inconsistent = deepcopy(result)
    inconsistent["result_state"] = "not_assessed"
    assert list(validator.iter_errors(inconsistent))

    incomplete = deepcopy(result)
    incomplete["input_sha256_by_role"].pop("program_assessment_spec")
    assert list(validator.iter_errors(incomplete))


def test_biological_rule_changes_only_through_spec(tmp_path: Path) -> None:
    baseline = ToolRegistry.load_default().run(
        _request(tmp_path / "baseline", output_dir=tmp_path / "output")
    )
    payloads = _payloads()
    payloads["program_assessment_spec"]["rules"][0]["reference_upper"] = 1.1
    changed = ToolRegistry.load_default().run(
        _request(
            tmp_path / "changed",
            payloads=payloads,
            output_dir=tmp_path / "output",
        )
    )

    before = baseline.result["program_results"][0]
    after = changed.result["program_results"][0]
    assert before["review_flag_state"] == "transcriptomic_review_flag"
    assert after["review_flag_state"] == "cannot_resolve"
    assert baseline.run_id != changed.run_id


def test_same_independence_group_does_not_count_twice(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["program_evidence_bundle"]["observations"][1][
        "independence_group"
    ] = "independence-group:alpha-a"
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    alpha = run.result["program_results"][0]
    assert alpha["included_independence_group_count"] == 1
    assert alpha["review_flag_state"] == "cannot_resolve"
    assert "independence_group_evidence_insufficient" in alpha["reason_codes"]


def test_low_coverage_is_excluded_not_zeroed(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["program_evidence_bundle"]["observations"][0]["gene_coverage"] = 0.1
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    alpha = run.result["program_results"][0]
    excluded = alpha["observations"][0]
    assert excluded["included"] is False
    assert excluded["value"] == 0.9
    assert excluded["exclusion_reason"] == "gene_coverage_below_configured_minimum"


def test_missing_evidence_remains_missing(tmp_path: Path) -> None:
    payloads = _payloads()
    observation = payloads["program_evidence_bundle"]["observations"][0]
    observation.update(
        {"evidence_state": "missing", "value": None, "gene_coverage": None}
    )
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assessed = run.result["program_results"][0]["observations"][0]
    assert assessed["evidence_state"] == "missing"
    assert assessed["value"] is None
    assert assessed["reference_relation"] is None
    assert assessed["exclusion_reason"] == "evidence_state_not_eligible"


def test_unavailable_development_context_returns_not_assessed(tmp_path: Path) -> None:
    payloads = _payloads()
    developmental = payloads["developmental_compatibility_result"]
    developmental.update(
        {
            "result_state": "not_assessed",
            "stage_composition_channels": [],
            "score_state": "unavailable",
        }
    )
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["result_state"] == "not_assessed"
    assert run.result["score_state"] == "unavailable"
    assert all(
        item["review_flag_state"] == "not_assessed"
        for item in run.result["program_results"]
    )


def test_unmatched_observation_is_reported_and_partial(tmp_path: Path) -> None:
    payloads = _payloads()
    observation = deepcopy(payloads["program_evidence_bundle"]["observations"][0])
    observation.update(
        {
            "observation_id": "program-observation:unmatched",
            "rule_id": "program-review-rule:unmatched",
        }
    )
    payloads["program_evidence_bundle"]["observations"].append(observation)
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.PARTIAL
    assert run.result["result_state"] == "partial"
    assert run.result["unmatched_observations"] == [
        {
            "observation_id": "program-observation:unmatched",
            "rule_id": "program-review-rule:unmatched",
            "reason_code": "program_rule_not_configured",
        }
    ]


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda p: p["program_assessment_spec"].update(
                {
                    "product_definition_ref": {
                        "object_id": "product-definition:other",
                        "object_version": "1.0.0",
                    }
                }
            ),
            "program_spec_product_definition_mismatch",
        ),
        (
            lambda p: p["program_evidence_bundle"].update(
                {
                    "product_case_ref": {
                        "object_id": "product-case:other",
                        "object_version": "1.0.0",
                    }
                }
            ),
            "program_evidence_product_case_mismatch",
        ),
        (
            lambda p: p["program_assessment_spec"]["rules"][0].update(
                {
                    "stage_context_ref": {
                        "object_id": "development-window-spec:other",
                        "object_version": "1.0.0",
                    }
                }
            ),
            "program_rule_stage_context_mismatch",
        ),
        (
            lambda p: p["program_evidence_bundle"].update(
                {
                    "cell_state_profile_ref": {
                        "object_id": "cell-state-profile:other",
                        "object_version": "0.1.0",
                    }
                }
            ),
            "program_evidence_cell_state_profile_mismatch",
        ),
        (
            lambda p: p["developmental_compatibility_result"].update(
                {
                    "qc_profile_ref": {
                        "object_id": "qc-profile:other",
                        "object_version": "0.1.0",
                    }
                }
            ),
            "developmental_result_qc_profile_mismatch",
        ),
        (
            lambda p: p["qc_readiness_profile"].update(
                {"readiness_state": "blocked"}
            ),
            "qc_not_ready_for_program_evidence",
        ),
    ],
)
def test_cross_binding_failures_are_typed(
    tmp_path: Path, mutate, reason: str
) -> None:
    payloads = _payloads()
    mutate(payloads)
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.FAILED
    assert reason in run.reason_codes
    assert run.result is None
    assert run.artifacts == []


@pytest.mark.parametrize(
    "unsafe_unit",
    ["/home/demo-user/private", "~/demo-private", "${HOME}/demo-private"],
)
def test_machine_local_unit_is_not_published(
    tmp_path: Path, unsafe_unit: str
) -> None:
    payloads = _payloads()
    payloads["program_assessment_spec"]["rules"][0]["unit"] = unsafe_unit

    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_schema_invalid"]
    assert run.result is None
    assert run.artifacts == []
    assert unsafe_unit not in json.dumps(run.model_dump(mode="json"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("value", "0.9"),
        ("value", True),
        ("gene_coverage", "0.9"),
        ("gene_coverage", True),
    ],
)
def test_scientific_numeric_coercion_is_rejected(
    tmp_path: Path, field: str, value: object
) -> None:
    payloads = _payloads()
    payloads["program_evidence_bundle"]["observations"][0][field] = value
    run = adapter.run(
        _request(tmp_path, payloads=payloads),
        ToolRegistry.load_default().describe("P0-06"),
    )

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_schema_invalid"]


def test_nonzero_random_seed_is_refused(tmp_path: Path) -> None:
    run = ToolRegistry.load_default().run(_request(tmp_path, random_seed=9))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["p0_06_random_seed_forbidden"]


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
    request = ToolRequest(request_id="v1", tool_id="P0-06", output_dir=tmp_path)
    spec = ToolRegistry.load_default().describe("P0-06")

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
    original = adapter_module.evaluate_proliferation_stress_response

    def mutate_input(**kwargs):
        result = original(**kwargs)
        target.write_text("{}", encoding="utf-8")
        return result

    monkeypatch.setattr(
        adapter_module,
        "evaluate_proliferation_stress_response",
        mutate_input,
    )
    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["input_asset_modified_during_run"]
    assert run.result is None
    assert run.artifacts == []


def test_implementation_contains_no_program_names_genes_or_limits() -> None:
    package = Path(adapter_module.__file__).parent
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(package.glob("*.py"))
    )

    for biological_term in (
        "PROC-",
        "MKI67",
        "TOP2A",
        "POU5F1",
        "NANOG",
        "HIF1A",
        "DDIT3",
        "TP53",
        "0.01%",
        "5%",
    ):
        assert biological_term not in source


def test_created_at_is_bound_to_product_case_not_wall_clock(tmp_path: Path) -> None:
    run = ToolRegistry.load_default().run(_request(tmp_path))

    assert run.created_at == datetime(2026, 8, 24, tzinfo=timezone.utc)
