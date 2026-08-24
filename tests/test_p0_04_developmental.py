from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

import bridge.tool_packages.p0_04_developmental.adapter as adapter_module
from bridge.tool_packages.p0_04_developmental.adapter import adapter
from bridge.tool_packages.p0_04_developmental.models import (
    DevelopmentalCompatibilityResult,
    PUBLIC_SCHEMA_MODELS,
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
    "product_definition_card": (
        "bridge://schemas/product-definition-card/v0.1"
    ),
    "state_role_map": "bridge://schemas/state-role-map/v0.1",
    "development_window_spec": (
        "bridge://schemas/development-window-spec/v0.1"
    ),
    "cell_state_evidence_profile": (
        "bridge://schemas/cell-state-evidence-profile/v0.1"
    ),
    "qc_readiness_profile": "bridge://schemas/qc-readiness-profile/v0.1",
}


def _payloads() -> dict[str, dict]:
    return {
        "product_case": {
            "object_version": "0.1.0",
            "product_case_id": "product-case:demo",
            "case_version": "1.0.0",
            "product_definition_ref": {
                "object_id": "product-definition:demo",
                "object_version": "1.0.0",
            },
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
        "state_role_map": {
            "object_version": "0.1.0",
            "role_map_id": "state-role-map:demo",
            "role_map_version": "1.0.0",
            "product_definition_ref": {
                "object_id": "product-definition:demo",
                "object_version": "1.0.0",
            },
            "annotation_vocabulary_ref": "annotation-vocabulary:demo",
            "review_state": "draft",
            "assignments": [
                {
                    "state_id": "state:alpha",
                    "label_level": "L1",
                    "lineage_role": "target",
                    "regional_role": "target_region",
                    "provenance_refs": [],
                },
                {
                    "state_id": "state:beta",
                    "label_level": "L1",
                    "lineage_role": "acceptable_adjacent",
                    "regional_role": "acceptable_adjacent_region",
                    "provenance_refs": [],
                },
                {
                    "state_id": "state:gamma",
                    "label_level": "L1",
                    "lineage_role": "not_target",
                    "regional_role": "regional_shift",
                    "provenance_refs": [],
                },
            ],
        },
        "development_window_spec": {
            "object_version": "0.1.0",
            "window_spec_id": "development-window-spec:demo",
            "window_spec_version": "1.0.0",
            "product_definition_ref": {
                "object_id": "product-definition:demo",
                "object_version": "1.0.0",
            },
            "state_role_map_ref": {
                "object_id": "state-role-map:demo",
                "object_version": "1.0.0",
            },
            "annotation_vocabulary_ref": "annotation-vocabulary:demo",
            "review_state": "draft",
            "applicable_assays": ["scRNA-seq"],
            "composition_views": ["consensus_supported_only"],
            "included_label_levels": ["L1"],
            "source_ids": [],
            "target_related_lineage_roles": [
                "target",
                "acceptable_adjacent",
            ],
            "assignments": [
                {
                    "state_id": "state:alpha",
                    "label_level": "L1",
                    "development_role": "earlier",
                    "target_related": True,
                    "provenance_refs": [],
                },
                {
                    "state_id": "state:beta",
                    "label_level": "L1",
                    "development_role": "within_window",
                    "target_related": True,
                    "provenance_refs": [],
                },
                {
                    "state_id": "state:gamma",
                    "label_level": "L1",
                    "development_role": "later",
                    "target_related": False,
                    "provenance_refs": [],
                },
            ],
            "unmapped_state_policy": "report_unresolved",
            "timecourse_policy": "static_without_timepoint_input",
        },
        "cell_state_evidence_profile": {
            "profile_id": "cell-state-profile:demo",
            "assay": "scRNA-seq",
            "measurement_spec_id": "measurement-spec:cell-state-demo",
            "measurement_spec_status": "candidate",
            "annotation_vocabulary_ref": "annotation-vocabulary:demo",
            "reference_snapshot_ref": "reference-snapshot:demo",
            "n_observations": 100,
            "n_genes": 1000,
            "denominator": "all observations in the declared post-QC input view",
            "label_levels": {"L1": {"state": "shadow"}},
            "source_support": {"state": "shadow"},
            "marker_program_evidence": {"state": "shadow"},
            "prediction_sets": {"state": "shadow"},
            "composition": {
                "state": "shadow",
                "records": [
                    {
                        "view": "consensus_supported_only",
                        "source_id": None,
                        "label": "state:alpha",
                        "count": 20,
                        "fraction": 0.2,
                        "denominator": 100,
                        "label_level": "L1",
                        "denominator_view": "all input observations",
                    },
                    {
                        "view": "reconciliation_state",
                        "source_id": None,
                        "label": "supported",
                        "count": 80,
                        "fraction": 0.8,
                        "denominator": 100,
                        "label_level": "L1",
                        "denominator_view": "all input observations",
                    },
                    {
                        "view": "consensus_supported_only",
                        "source_id": None,
                        "label": "state:beta",
                        "count": 50,
                        "fraction": 0.5,
                        "denominator": 100,
                        "label_level": "L1",
                        "denominator_view": "all input observations",
                    },
                    {
                        "view": "consensus_supported_only",
                        "source_id": None,
                        "label": "state:gamma",
                        "count": 30,
                        "fraction": 0.3,
                        "denominator": 100,
                        "label_level": "L1",
                        "denominator_view": "all input observations",
                    },
                ],
            },
            "gene_coverage": {"state": "available"},
            "modality_sensitivity": {"state": "not_assessed"},
            "method_outputs": {},
            "assignment_state": {"state": "candidate_prediction_set"},
            "unknown_reason": {"state": "not_assessed"},
            "calibration": {"state": "not_assessed"},
            "method_disagreement": {},
            "per_state_release": {
                "state:alpha": "shadow",
                "state:beta": "shadow",
                "state:gamma": "shadow",
            },
            "unresolved_labels": [],
            "warnings": [],
            "evidence_ids": ["evidence:cell-state-demo"],
            "score_state": "shadow",
            "domain_score": None,
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
            "module_eligibility": {"P0-04": "eligible"},
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


def _bind_upstream_profiles(payloads: dict[str, dict]) -> None:
    view = {
        "view_id": "data-view:demo:qc-selected",
        "view_kind": "qc_selected_observations",
        "artifact_id": "artifact:demo:candidate-view",
        "sha256": "a" * 64,
        "parent_asset_id": "asset:demo",
        "parent_asset_sha256": "b" * 64,
        "matrix_location": "X",
        "matrix_semantics": "raw_counts",
        "n_observations": 100,
        "observation_ids_sha256": "c" * 64,
        "sample_or_preparation_ref": "preparation:demo@1.0.0",
        "selection_spec_ref": "QC-scRNA-candidate-v0.1@0.1.0",
    }
    qc = payloads["qc_readiness_profile"]
    qc["selected_data_view"] = view
    qc_raw = json.dumps(
        qc,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    cell_state = payloads["cell_state_evidence_profile"]
    cell_state.update(
        {
            "measurement_spec_version": "0.1.0",
            "upstream_qc_profile_ref": qc["profile_id"],
            "upstream_qc_profile_sha256": hashlib.sha256(qc_raw).hexdigest(),
            "input_data_view": view,
        }
    )


def _request(
    tmp_path: Path,
    *,
    payloads: dict[str, dict] | None = None,
    output_dir: Path | None = None,
    input_id_prefix: str = "input",
    random_seed: int = 0,
) -> ToolRequestV2:
    values = deepcopy(payloads or _payloads())
    _bind_upstream_profiles(values)
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
        tool_id="P0-04",
        tool_version="0.2.0",
        output_dir=output_dir or (tmp_path / "output"),
        random_seed=random_seed,
        object_inputs=refs,
    )


def _role_map(items: list[dict]) -> dict[str, dict]:
    return {item["role"]: item for item in items}


def test_p0_04_is_an_implemented_v2_package() -> None:
    spec = ToolRegistry.load_default().describe("P0-04")

    assert isinstance(spec, ToolPackageSpecV2)
    assert spec.implementation_state is ImplementationState.IMPLEMENTED
    assert spec.result_schema_ref == (
        "bridge://schemas/developmental-compatibility-result/v0.1"
    )
    assert spec.adapter_ref == (
        "bridge.tool_packages.p0_04_developmental.adapter:adapter"
    )


@pytest.mark.parametrize("schema_ref,model", PUBLIC_SCHEMA_MODELS.items())
def test_public_models_emit_valid_draft_2020_12_schemas(
    schema_ref: str, model: type
) -> None:
    schema = model.model_json_schema()
    schema["$id"] = schema_ref
    Draft202012Validator.check_schema(schema)


def test_static_configuration_runs_and_preserves_both_denominators(
    tmp_path: Path,
) -> None:
    run = ToolRegistry.load_default().run(_request(tmp_path))

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result_schema_ref == (
        "bridge://schemas/developmental-compatibility-result/v0.1"
    )
    assert run.result["result_state"] == "complete"
    assert run.result["analysis_mode"] == "static_profile"
    assert run.result["domain_score"] is None
    assert run.result["score_state"] == "shadow"
    assert run.measurements == []
    assert run.visualizations == []
    assert len(run.artifacts) == 1
    channel = run.result["stage_composition_channels"][0]
    whole = _role_map(channel["whole_product_stage_fractions"])
    target = _role_map(channel["target_related_stage_fractions"])
    assert channel["denominator_view"] == "all input observations"
    assert channel["whole_product_denominator"] == 100
    assert channel["target_related_denominator"] == 70
    assert whole["earlier"]["numerator"] == 20
    assert whole["within_window"]["numerator"] == 50
    assert whole["later"]["numerator"] == 30
    assert target["earlier"]["fraction"] == pytest.approx(20 / 70)
    assert target["within_window"]["fraction"] == pytest.approx(50 / 70)
    assert target["later"]["numerator"] == 0
    assert run.result["reference_stage_support"] == {
        "assessment_state": "not_assessed",
        "reason_code": "reference_stage_support_not_supplied",
    }
    assert run.result["timecourse_profile"] == {
        "analysis_mode": "static_profile",
        "evidence_state": "unavailable",
        "reason_code": "true_timepoint_input_not_supplied",
    }
    assert set(run.result["input_sha256_by_role"]) == set(ROLE_SCHEMAS)
    assert not any(
        ref.input_id in json.dumps(run.result, sort_keys=True)
        for ref in run.request.object_inputs
    )


def test_result_schema_rejects_state_and_checksum_binding_conflicts(
    tmp_path: Path,
) -> None:
    result = ToolRegistry.load_default().run(_request(tmp_path)).result
    validator = Draft202012Validator(
        DevelopmentalCompatibilityResult.model_json_schema()
    )

    inconsistent_state = deepcopy(result)
    inconsistent_state["result_state"] = "not_assessed"
    assert list(validator.iter_errors(inconsistent_state))

    incomplete_binding = deepcopy(result)
    incomplete_binding["input_sha256_by_role"].pop("development_window_spec")
    assert list(validator.iter_errors(incomplete_binding))


def test_biological_assignment_changes_only_through_window_spec(
    tmp_path: Path,
) -> None:
    baseline = ToolRegistry.load_default().run(
        _request(tmp_path / "baseline", output_dir=tmp_path / "output")
    )
    payloads = _payloads()
    payloads["development_window_spec"]["assignments"][0][
        "development_role"
    ] = "branch_shift"
    changed = ToolRegistry.load_default().run(
        _request(
            tmp_path / "changed",
            payloads=payloads,
            output_dir=tmp_path / "output",
        )
    )

    baseline_roles = _role_map(
        baseline.result["stage_composition_channels"][0][
            "whole_product_stage_fractions"
        ]
    )
    changed_roles = _role_map(
        changed.result["stage_composition_channels"][0][
            "whole_product_stage_fractions"
        ]
    )
    assert baseline_roles["earlier"]["numerator"] == 20
    assert changed_roles["earlier"]["numerator"] == 0
    assert changed_roles["branch_shift"]["numerator"] == 20
    assert baseline.run_id != changed.run_id


def test_unmapped_state_is_partial_and_not_guessed(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["development_window_spec"]["assignments"] = payloads[
        "development_window_spec"
    ]["assignments"][:-1]
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.PARTIAL
    assert run.result["result_state"] == "partial"
    assert run.result["unmapped_states"] == [
        {
            "state_id": "state:gamma",
            "label_level": "L1",
            "composition_view": "consensus_supported_only",
            "source_id": None,
            "count": 30,
            "denominator": 100,
            "reason_code": "development_role_not_configured",
        }
    ]
    assert "development_role_mapping_incomplete" in run.result["reason_codes"]
    whole = _role_map(
        run.result["stage_composition_channels"][0][
            "whole_product_stage_fractions"
        ]
    )
    assert whole["unresolved"]["numerator"] == 30


def test_complete_contract_without_selected_composition_is_not_assessed(
    tmp_path: Path,
) -> None:
    payloads = _payloads()
    payloads["cell_state_evidence_profile"]["composition"]["records"] = []
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["result_state"] == "not_assessed"
    assert run.result["score_state"] == "unavailable"
    assert run.result["stage_composition_channels"] == []
    assert "developmental_composition_not_assessed" in run.result["reason_codes"]


def test_missing_explicit_source_is_partial(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["development_window_spec"].update(
        {
            "composition_views": ["source_specific"],
            "source_ids": ["REF-PRESENT", "REF-MISSING"],
        }
    )
    payloads["cell_state_evidence_profile"]["composition"]["records"].append(
        {
            "view": "source_specific",
            "source_id": "REF-PRESENT",
            "label": "state:alpha",
            "count": 100,
            "fraction": 1.0,
            "denominator": 100,
            "label_level": "L1",
            "denominator_view": "all input observations",
        }
    )

    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.PARTIAL
    assert run.result["result_state"] == "partial"
    assert "requested_composition_channel_unavailable" in run.reason_codes


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda payloads: payloads["product_case"].update(
                {
                    "product_definition_ref": {
                        "object_id": "product-definition:other",
                        "object_version": "1.0.0",
                    }
                }
            ),
            "product_definition_binding_mismatch",
        ),
        (
            lambda payloads: payloads["development_window_spec"].update(
                {
                    "product_definition_ref": {
                        "object_id": "product-definition:other",
                        "object_version": "1.0.0",
                    }
                }
            ),
            "development_window_product_definition_mismatch",
        ),
        (
            lambda payloads: payloads["development_window_spec"].update(
                {"annotation_vocabulary_ref": "annotation-vocabulary:other"}
            ),
            "annotation_vocabulary_binding_mismatch",
        ),
        (
            lambda payloads: payloads["development_window_spec"].update(
                {"applicable_assays": ["snRNA-seq"]}
            ),
            "development_window_assay_not_supported",
        ),
        (
            lambda payloads: payloads["qc_readiness_profile"].update(
                {"readiness_state": "blocked"}
            ),
            "qc_not_ready_for_developmental_evidence",
        ),
        (
            lambda payloads: payloads["cell_state_evidence_profile"].update(
                {"evidence_ids": ["/private/path/evidence"]}
            ),
            "unsafe_evidence_reference",
        ),
    ],
)
def test_cross_binding_and_publication_failures_are_typed(
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
    "unsafe_denominator",
    ["/home/demo-user/private", "~/demo-private", "${HOME}/demo-private"],
)
def test_machine_local_denominator_is_not_published(
    tmp_path: Path, unsafe_denominator: str
) -> None:
    payloads = _payloads()
    payloads["cell_state_evidence_profile"]["composition"]["records"][0][
        "denominator_view"
    ] = unsafe_denominator

    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["cell_state_composition_invalid"]
    assert run.result is None
    assert run.artifacts == []
    assert unsafe_denominator not in json.dumps(run.model_dump(mode="json"))


@pytest.mark.parametrize("field", ["count", "denominator", "fraction"])
def test_scientific_numeric_strings_are_rejected(tmp_path: Path, field: str) -> None:
    payloads = _payloads()
    payloads["cell_state_evidence_profile"]["composition"]["records"][0][
        field
    ] = "20"
    run = adapter.run(
        _request(tmp_path, payloads=payloads),
        ToolRegistry.load_default().describe("P0-04"),
    )

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["cell_state_composition_invalid"]
    assert run.result is None


def test_window_boolean_string_is_rejected(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["development_window_spec"]["assignments"][0][
        "target_related"
    ] = "true"
    run = adapter.run(
        _request(tmp_path, payloads=payloads),
        ToolRegistry.load_default().describe("P0-04"),
    )

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_schema_invalid"]
    assert run.result is None


def test_nonzero_random_seed_is_refused_for_deterministic_engine(
    tmp_path: Path,
) -> None:
    run = ToolRegistry.load_default().run(_request(tmp_path, random_seed=7))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["p0_04_random_seed_forbidden"]
    assert run.result is None


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
    request = ToolRequest(
        request_id="v1",
        tool_id="P0-04",
        output_dir=tmp_path,
    )
    spec = ToolRegistry.load_default().describe("P0-04")

    eligibility = adapter.check_eligibility(request, spec)
    run = adapter.run(request, spec)

    assert eligibility.eligible is False
    assert eligibility.reason_codes == ["tool_request_v2_required"]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["tool_request_v2_required"]
    assert run.result is None


def test_registry_detects_input_mutation_during_adapter_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path)
    target = request.object_inputs[0].path
    original = adapter_module.evaluate_developmental_compatibility

    def mutate_input(**kwargs):
        result = original(**kwargs)
        target.write_text("{}", encoding="utf-8")
        return result

    monkeypatch.setattr(
        adapter_module,
        "evaluate_developmental_compatibility",
        mutate_input,
    )
    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["input_asset_modified_during_run"]
    assert run.result is None
    assert run.artifacts == []


def test_implementation_contains_no_product_specific_state_or_window_names() -> None:
    package = Path(adapter_module.__file__).parent
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(package.glob("*.py"))
    )

    for biological_term in (
        "Radial_Glia",
        "Neuroblast",
        "Neuron_DA",
        "Pericyte",
        "Astrocyte",
        "mFP",
        "mBMP",
        "mBIP",
        "GW7",
        "PCW6",
        "D16",
    ):
        assert biological_term not in source


def test_created_at_is_bound_to_product_case_not_wall_clock(tmp_path: Path) -> None:
    run = ToolRegistry.load_default().run(_request(tmp_path))

    assert run.created_at == datetime(2026, 8, 24, tzinfo=timezone.utc)
