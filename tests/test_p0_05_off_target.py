from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

import bridge.tool_packages.p0_05_off_target.adapter as adapter_module
from bridge.tool_packages.p0_05_off_target.adapter import adapter
from bridge.tool_packages.p0_05_off_target.models import (
    OffTargetControlResult,
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
    "product_definition_card": "bridge://schemas/product-definition-card/v0.1",
    "off_target_role_spec": "bridge://schemas/off-target-role-spec/v0.1",
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
        "off_target_role_spec": {
            "object_version": "0.1.0",
            "role_spec_id": "off-target-role-spec:demo",
            "role_spec_version": "1.0.0",
            "product_definition_ref": {
                "object_id": "product-definition:demo",
                "object_version": "1.0.0",
            },
            "annotation_vocabulary_ref": "annotation-vocabulary:demo",
            "review_state": "draft",
            "composition_views": ["consensus_supported_only"],
            "included_label_levels": ["L1"],
            "source_ids": [],
            "required_denominator_view": "all input observations",
            "assignments": [
                {
                    "state_id": "state:alpha",
                    "label_level": "L1",
                    "product_role": "target",
                    "role_evidence_class": None,
                    "evidence_direction": None,
                    "unknown_reason": None,
                    "provenance_refs": [],
                },
                {
                    "state_id": "state:beta",
                    "label_level": "L1",
                    "product_role": "acceptable_adjacent",
                    "role_evidence_class": None,
                    "evidence_direction": None,
                    "unknown_reason": None,
                    "provenance_refs": [],
                },
                {
                    "state_id": "state:gamma",
                    "label_level": "L1",
                    "product_role": "known_off_target",
                    "role_evidence_class": "clear_off_axis",
                    "evidence_direction": "adverse_direction_supported",
                    "unknown_reason": None,
                    "provenance_refs": [],
                },
                {
                    "state_id": "state:delta",
                    "label_level": "L1",
                    "product_role": "unknown",
                    "role_evidence_class": None,
                    "evidence_direction": None,
                    "unknown_reason": "reference_gap",
                    "provenance_refs": [],
                },
            ],
            "unmapped_state_policy": "report_role_unresolved",
            "ood_policy": "not_assessed_without_calibration",
            "rare_state_policy": "not_assessed_without_calibration",
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
                        "count": 50,
                        "fraction": 0.5,
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
                        "count": 20,
                        "fraction": 0.2,
                        "denominator": 100,
                        "label_level": "L1",
                        "denominator_view": "all input observations",
                    },
                    {
                        "view": "consensus_supported_only",
                        "source_id": None,
                        "label": "state:gamma",
                        "count": 20,
                        "fraction": 0.2,
                        "denominator": 100,
                        "label_level": "L1",
                        "denominator_view": "all input observations",
                    },
                    {
                        "view": "consensus_supported_only",
                        "source_id": None,
                        "label": "state:delta",
                        "count": 10,
                        "fraction": 0.1,
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
                "state:delta": "shadow",
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
            "module_eligibility": {"P0-05": "eligible"},
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
        tool_id="P0-05",
        tool_version="0.2.0",
        output_dir=output_dir or (tmp_path / "output"),
        random_seed=random_seed,
        object_inputs=refs,
    )


def _role_map(channel: dict) -> dict[str, dict]:
    return {item["role"]: item for item in channel["role_fractions"]}


def test_p0_05_is_an_implemented_v2_package() -> None:
    spec = ToolRegistry.load_default().describe("P0-05")

    assert isinstance(spec, ToolPackageSpecV2)
    assert spec.implementation_state is ImplementationState.IMPLEMENTED
    assert spec.result_schema_ref == "bridge://schemas/off-target-control-result/v0.1"
    assert spec.adapter_ref == "bridge.tool_packages.p0_05_off_target.adapter:adapter"


@pytest.mark.parametrize("schema_ref,model", PUBLIC_SCHEMA_MODELS.items())
def test_public_models_emit_valid_draft_2020_12_schemas(
    schema_ref: str, model: type
) -> None:
    schema = model.model_json_schema()
    schema["$id"] = schema_ref
    Draft202012Validator.check_schema(schema)


def test_configured_full_product_composition_runs(tmp_path: Path) -> None:
    run = ToolRegistry.load_default().run(_request(tmp_path))

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["result_state"] == "complete"
    assert run.result["domain_score"] is None
    assert run.result["score_state"] == "shadow"
    assert run.measurements == []
    assert run.visualizations == []
    assert len(run.artifacts) == 1
    channel = run.result["composition_channels"][0]
    roles = _role_map(channel)
    assert channel["denominator"] == 100
    assert channel["denominator_view"] == "all input observations"
    assert roles["target"]["numerator"] == 50
    assert roles["acceptable_adjacent"]["numerator"] == 20
    assert roles["known_off_target"]["numerator"] == 20
    assert roles["role_unresolved"]["numerator"] == 0
    assert roles["unknown"]["numerator"] == 10
    breakdown = {item["state_id"]: item for item in channel["state_breakdown"]}
    assert breakdown["state:gamma"]["role_evidence_class"] == "clear_off_axis"
    assert breakdown["state:delta"]["unknown_reason"] == "reference_gap"
    assert run.result["ood_assessment"]["assessment_state"] == "not_assessed"
    assert run.result["rare_state_detection"]["assessment_state"] == "not_assessed"
    assert not any(
        ref.input_id in json.dumps(run.result, sort_keys=True)
        for ref in run.request.object_inputs
    )


def test_result_schema_rejects_state_and_checksum_conflicts(tmp_path: Path) -> None:
    result = ToolRegistry.load_default().run(_request(tmp_path)).result
    validator = Draft202012Validator(OffTargetControlResult.model_json_schema())

    inconsistent = deepcopy(result)
    inconsistent["result_state"] = "not_assessed"
    assert list(validator.iter_errors(inconsistent))

    incomplete = deepcopy(result)
    incomplete["input_sha256_by_role"].pop("off_target_role_spec")
    assert list(validator.iter_errors(incomplete))

    unknown_without_reason = deepcopy(result)
    unknown = next(
        item
        for item in unknown_without_reason["composition_channels"][0][
            "state_breakdown"
        ]
        if item["product_role"] == "unknown"
    )
    unknown["unknown_reason"] = None
    assert list(validator.iter_errors(unknown_without_reason))


def test_biological_role_changes_only_through_role_spec(tmp_path: Path) -> None:
    baseline = ToolRegistry.load_default().run(
        _request(tmp_path / "baseline", output_dir=tmp_path / "output")
    )
    payloads = _payloads()
    payloads["off_target_role_spec"]["assignments"][2][
        "product_role"
    ] = "role_unresolved"
    changed = ToolRegistry.load_default().run(
        _request(
            tmp_path / "changed",
            payloads=payloads,
            output_dir=tmp_path / "output",
        )
    )

    before = _role_map(baseline.result["composition_channels"][0])
    after = _role_map(changed.result["composition_channels"][0])
    assert before["known_off_target"]["numerator"] == 20
    assert after["known_off_target"]["numerator"] == 0
    assert after["role_unresolved"]["numerator"] == 20
    assert baseline.run_id != changed.run_id


def test_unmapped_identity_is_role_unresolved_not_unknown(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["off_target_role_spec"]["assignments"] = payloads[
        "off_target_role_spec"
    ]["assignments"][:-2]
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.PARTIAL
    roles = _role_map(run.result["composition_channels"][0])
    assert roles["role_unresolved"]["numerator"] == 30
    assert roles["unknown"]["numerator"] == 0
    assert len(run.result["unmapped_states"]) == 2
    assert "product_role_mapping_incomplete" in run.reason_codes


def test_wrong_denominator_view_returns_not_assessed(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["off_target_role_spec"][
        "required_denominator_view"
    ] = "eligible product observations"
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["result_state"] == "not_assessed"
    assert run.result["composition_channels"] == []
    assert "requested_full_product_channel_unavailable" in run.reason_codes


def test_missing_explicit_source_is_partial(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["off_target_role_spec"].update(
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
    assert "requested_full_product_channel_unavailable" in run.reason_codes


def test_zero_observation_never_becomes_rare_state_absence(tmp_path: Path) -> None:
    payloads = _payloads()
    record = payloads["cell_state_evidence_profile"]["composition"]["records"][3]
    record.update({"count": 0, "fraction": 0.0})
    payloads["cell_state_evidence_profile"]["composition"]["records"][0][
        "count"
    ] = 70
    payloads["cell_state_evidence_profile"]["composition"]["records"][0][
        "fraction"
    ] = 0.7
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["rare_state_detection"] == {
        "assessment_state": "not_assessed",
        "reason_code": "rare_state_calibration_not_supplied",
    }


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda p: p["product_case"].update(
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
            lambda p: p["off_target_role_spec"].update(
                {
                    "product_definition_ref": {
                        "object_id": "product-definition:other",
                        "object_version": "1.0.0",
                    }
                }
            ),
            "off_target_role_spec_product_definition_mismatch",
        ),
        (
            lambda p: p["off_target_role_spec"].update(
                {"annotation_vocabulary_ref": "annotation-vocabulary:other"}
            ),
            "annotation_vocabulary_binding_mismatch",
        ),
        (
            lambda p: p["qc_readiness_profile"].update(
                {"readiness_state": "blocked"}
            ),
            "qc_not_ready_for_off_target_evidence",
        ),
        (
            lambda p: p["cell_state_evidence_profile"].update(
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


@pytest.mark.parametrize("field", ["count", "denominator", "fraction"])
def test_scientific_numeric_strings_are_rejected(tmp_path: Path, field: str) -> None:
    payloads = _payloads()
    payloads["cell_state_evidence_profile"]["composition"]["records"][0][
        field
    ] = "50"
    run = adapter.run(
        _request(tmp_path, payloads=payloads),
        ToolRegistry.load_default().describe("P0-05"),
    )

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["cell_state_composition_invalid"]


def test_unknown_role_requires_configured_reason(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["off_target_role_spec"]["assignments"][3]["unknown_reason"] = None
    run = adapter.run(
        _request(tmp_path, payloads=payloads),
        ToolRegistry.load_default().describe("P0-05"),
    )

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_schema_invalid"]


def test_nonzero_random_seed_is_refused(tmp_path: Path) -> None:
    run = ToolRegistry.load_default().run(_request(tmp_path, random_seed=9))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["p0_05_random_seed_forbidden"]


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
    request = ToolRequest(request_id="v1", tool_id="P0-05", output_dir=tmp_path)
    spec = ToolRegistry.load_default().describe("P0-05")

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
    original = adapter_module.evaluate_off_target_control

    def mutate_input(**kwargs):
        result = original(**kwargs)
        target.write_text("{}", encoding="utf-8")
        return result

    monkeypatch.setattr(adapter_module, "evaluate_off_target_control", mutate_input)
    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["input_asset_modified_during_run"]
    assert run.result is None
    assert run.artifacts == []


def test_implementation_contains_no_product_specific_roles_or_limits() -> None:
    package = Path(adapter_module.__file__).parent
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(package.glob("*.py"))
    )

    for biological_term in (
        "Astrocyte",
        "Pericyte",
        "Serotonergic",
        "Cortical",
        "Neural_Crest",
        "mFP",
        "Neuron_DA",
        "0.01%",
        "5%",
    ):
        assert biological_term not in source


def test_created_at_is_bound_to_product_case_not_wall_clock(tmp_path: Path) -> None:
    run = ToolRegistry.load_default().run(_request(tmp_path))

    assert run.created_at == datetime(2026, 8, 24, tzinfo=timezone.utc)
