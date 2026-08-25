from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from bridge.tool_packages.p0_04_developmental_compatibility.adapter import adapter
from bridge.toolkit.contracts import ToolRequest
from bridge.toolkit.registry import ToolRegistry


SCHEMAS = {
    "product_case": "bridge://schemas/product-case/v0.1",
    "product_definition_card": "bridge://schemas/product-definition-card/v0.1",
    "development_window_spec": "bridge://schemas/development-window-spec/v0.1",
    "development_state_map": "bridge://schemas/development-state-map/v0.1",
    "measurement_spec": "bridge://schemas/measurement-spec/v0.2",
    "cell_state_evidence_profile": (
        "bridge://schemas/cell-state-evidence-profile/v0.2"
    ),
    "development_timepoint_series": (
        "bridge://schemas/development-timepoint-series/v0.1"
    ),
}


def _ref(object_id: str, version: str = "1.0.0") -> dict[str, str]:
    return {"object_id": object_id, "object_version": version}


def _payloads(*, include_series: bool = False) -> dict[str, dict]:
    product_ref = _ref("product-definition:demo")
    case_ref = _ref("product-case:demo")
    state_map_ref = _ref("development-state-map:demo")
    payloads: dict[str, dict] = {
        "product_case": {
            "object_version": "0.1.0",
            "product_case_id": case_ref["object_id"],
            "case_version": case_ref["object_version"],
            "product_definition_ref": product_ref,
            "source_unit_kind": "preparation",
            "sample_or_preparation_ref": _ref("preparation:demo"),
            "independence_group_refs": [],
            "biological_unit_manifest_ref": None,
            "biological_unit_manifest_sha256": None,
            "independence_scope_ref": None,
            "measurement_spec_ref": _ref("measurement-spec:development"),
            "assay": "scRNA-seq",
            "provenance_refs": [_ref("provenance:case")],
            "created_at": "2026-08-25T00:00:00Z",
        },
        "product_definition_card": {
            "object_version": "0.1.0",
            "product_definition_id": product_ref["object_id"],
            "definition_version": product_ref["object_version"],
            "state_role_map_ref": _ref("state-role-map:demo"),
            "supported_assays": ["scRNA-seq"],
            "review_state": "draft",
            "provenance_refs": [_ref("provenance:product")],
        },
        "development_window_spec": {
            "object_version": "0.1.0",
            "window_spec_id": "development-window-spec:demo",
            "window_spec_version": "1.0.0",
            "product_definition_ref": product_ref,
            "state_map_ref": state_map_ref,
            "review_state": "confirmed",
            "reviewer_ref": _ref("reviewer:development"),
            "confirmed_at": "2026-08-25T00:00:00Z",
            "applicable_assays": ["scRNA-seq"],
            "composition_view": "consensus_supported_only",
            "source_id": None,
            "label_level": "L2",
            "rationale_refs": [_ref("rationale:development")],
        },
        "development_state_map": {
            "object_version": "0.1.0",
            "state_map_id": state_map_ref["object_id"],
            "state_map_version": state_map_ref["object_version"],
            "product_definition_ref": product_ref,
            "annotation_vocabulary_ref": "annotation-vocabulary:demo",
            "review_state": "reviewed",
            "assignments": [
                {
                    "state_id": state,
                    "label_level": "L2",
                    "stage_role": role,
                    "target_related": target_related,
                    "provenance_refs": [_ref(f"provenance:{state}")],
                }
                for state, role, target_related in (
                    ("state-early", "earlier", True),
                    ("state-window", "within_window", True),
                    ("state-late", "later", True),
                    ("state-branch", "branch_shift", True),
                    ("state-unresolved", "unresolved", False),
                )
            ],
        },
        "measurement_spec": {
            "measurement_spec_id": "measurement-spec:development",
            "version": "1.0.0",
            "scientific_question": "Demo developmental composition question",
            "assay": "scRNA-seq",
            "status": "candidate",
            "applicable_product_cards": ["product-definition:demo@1.0.0"],
            "input_contract": {},
            "analysis_unit": "preparation",
            "analysis_unit_kind": "preparation",
            "independence_group_kind": "sample",
            "observation_unit_kind": "cell",
            "raw_metric_definition": {},
            "missing_behavior": "return typed unavailable evidence",
        },
        "cell_state_evidence_profile": {
            "profile_id": "cell-state-profile:demo",
            "assay": "scRNA-seq",
            "measurement_spec_id": "measurement-spec:development",
            "measurement_spec_version": "1.0.0",
            "measurement_spec_status": "candidate",
            "annotation_vocabulary_ref": "annotation-vocabulary:demo",
            "reference_snapshot_ref": "reference-manifest:demo@1.0.0",
            "n_observations": 10,
            "n_genes": 100,
            "denominator": "qc_selected_observations",
            "label_levels": {},
            "source_support": {},
            "marker_program_evidence": {},
            "prediction_sets": {},
            "composition": {
                "state": "shadow",
                "records": [
                    {
                        "view": "consensus_supported_only",
                        "source_id": None,
                        "label": state,
                        "label_level": "L2",
                        "denominator_view": "qc_selected_observations",
                        "count": count,
                        "fraction": count / 10,
                        "denominator": 10,
                    }
                    for state, count in (
                        ("state-early", 2),
                        ("state-window", 5),
                        ("state-late", 1),
                        ("state-branch", 1),
                        ("state-unresolved", 1),
                    )
                ],
            },
            "gene_coverage": {},
            "modality_sensitivity": {},
            "evidence_ids": ["evidence:cell-state-demo"],
            "score_state": "shadow",
            "domain_score": None,
        },
    }
    if include_series:
        payloads["development_timepoint_series"] = {
            "object_version": "0.1.0",
            "series_id": "development-timepoint-series:demo",
            "series_version": "1.0.0",
            "product_case_ref": case_ref,
            "state_map_ref": state_map_ref,
            "time_basis": "in_vitro_day",
            "records": [
                {
                    "timepoint_id": f"timepoint-{order}",
                    "timepoint_order": order,
                    "timepoint_label": f"D{day}",
                    "independence_group_refs": [_ref(f"sample:t{order}")],
                    "denominator": 10,
                    "state_counts": [
                        {"state_id": "state-early", "label_level": "L2", "count": early},
                        {"state_id": "state-window", "label_level": "L2", "count": 10 - early},
                    ],
                }
                for order, day, early in ((0, 16, 7), (1, 25, 3))
            ],
        }
    return payloads


def _write_request(
    tmp_path: Path,
    payloads: dict[str, dict],
    *,
    output_name: str = "output",
) -> tuple[ToolRegistry, object]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    refs = []
    for index, (role, payload) in enumerate(payloads.items()):
        raw = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode()
        path = (tmp_path / f"{role}.json").resolve()
        path.write_bytes(raw)
        if role == "measurement_spec":
            object_version = payload["version"]
        elif role == "cell_state_evidence_profile":
            object_version = "0.2.0"
        else:
            object_version = payload["object_version"]
        refs.append(
            {
                "input_id": f"input-{index:02d}-{role}",
                "role": role,
                "schema_ref": SCHEMAS[role],
                "object_version": object_version,
                "path": str(path),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "media_type": "application/json",
            }
        )
    registry = ToolRegistry.load_default()
    request = registry.parse_request(
        {
            "request_id": f"request-{output_name}",
            "tool_id": "P0-04",
            "tool_version": "0.2.0",
            "output_dir": str((tmp_path / output_name).resolve()),
            "assets": [],
            "measurement_spec_ref": None,
            "parameters": {},
            "random_seed": 0,
            "object_inputs": refs,
        }
    )
    return registry, request


def test_registry_exposes_p0_04_as_v2_implemented() -> None:
    registry = ToolRegistry.load_default()
    spec = registry.describe("P0-04")
    assert spec.version == "0.2.0"
    assert spec.implementation_state.value == "implemented"
    assert registry.request_model("P0-04").__name__ == "ToolRequestV2"
    assert spec.result_schema_ref == (
        "bridge://schemas/developmental-compatibility-result/v0.1"
    )


def test_valid_run_reports_two_denominators_and_no_score(tmp_path: Path) -> None:
    registry, request = _write_request(tmp_path, _payloads())
    assert registry.check_eligibility(request).eligible
    run = registry.run(request)
    assert run.execution_state.value == "succeeded"
    assert run.result["result_state"] == "complete"
    assert run.result["evidence_state"] == "shadow"
    assert run.result["domain_score"] is None
    assert run.result["score_state"] == "unavailable"
    assert run.result["whole_product_profile"]["denominator"] == 10
    assert run.result["target_related_profile"]["denominator"] == 9
    assert len(run.artifacts) == 1 and run.artifacts[0].path.is_file()


def test_run_identity_and_payload_ignore_request_and_output_paths(tmp_path: Path) -> None:
    payloads = _payloads()
    registry, first = _write_request(tmp_path / "first", payloads, output_name="out-a")
    first_run = registry.run(first)
    registry, second = _write_request(tmp_path / "second", payloads, output_name="out-b")
    second_run = registry.run(second)
    assert first_run.run_id == second_run.run_id
    assert first_run.result == second_run.result
    assert first_run.artifacts[0].sha256 == second_run.artifacts[0].sha256


def test_checksum_mismatch_is_refused(tmp_path: Path) -> None:
    registry, request = _write_request(tmp_path, _payloads())
    payload = request.model_dump(mode="json")
    payload["object_inputs"][0]["sha256"] = "0" * 64
    invalid = registry.parse_request(payload)
    eligibility = registry.check_eligibility(invalid)
    assert not eligibility.eligible
    assert "structured_input_checksum_mismatch" in eligibility.reason_codes


def test_missing_required_role_is_refused(tmp_path: Path) -> None:
    payloads = _payloads()
    del payloads["development_state_map"]
    registry, request = _write_request(tmp_path, payloads)
    eligibility = registry.check_eligibility(request)
    assert not eligibility.eligible
    assert "exactly_one_development_state_map_required" in eligibility.reason_codes


def test_wrong_schema_reference_is_refused(tmp_path: Path) -> None:
    registry, request = _write_request(tmp_path, _payloads())
    payload = request.model_dump(mode="json")
    window = next(
        item for item in payload["object_inputs"] if item["role"] == "development_window_spec"
    )
    window["schema_ref"] = "bridge://schemas/development-state-map/v0.1"
    invalid = registry.parse_request(payload)
    assert not registry.check_eligibility(invalid).eligible


def test_cross_object_binding_mismatch_is_refused(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["development_window_spec"]["product_definition_ref"] = _ref(
        "product-definition:other"
    )
    registry, request = _write_request(tmp_path, payloads)
    eligibility = registry.check_eligibility(request)
    assert not eligibility.eligible
    assert "window_product_definition_binding_mismatch" in eligibility.reason_codes


def test_unconfirmed_window_keeps_profile_but_no_compatibility_claim(tmp_path: Path) -> None:
    payloads = _payloads()
    window = payloads["development_window_spec"]
    window.update(review_state="candidate", reviewer_ref=None, confirmed_at=None)
    registry, request = _write_request(tmp_path, payloads)
    run = registry.run(request)
    assert run.execution_state.value == "partial"
    assert run.result["result_state"] == "partial"
    assert run.result["window_compatibility_state"] == "not_assessed"
    assert "development_window_not_confirmed" in run.reason_codes


def test_unavailable_upstream_is_not_zero(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["cell_state_evidence_profile"]["composition"] = {
        "state": "unavailable",
        "records": [],
    }
    registry, request = _write_request(tmp_path, payloads)
    run = registry.run(request)
    assert run.execution_state.value == "partial"
    assert run.result["result_state"] == "not_assessed"
    assert run.result["whole_product_profile"] is None
    assert run.result["target_related_profile"] is None
    assert run.result["evidence_state"] == "unavailable"


def test_unmapped_and_residual_counts_are_unresolved(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["development_state_map"]["assignments"].pop()
    payloads["cell_state_evidence_profile"]["composition"]["records"].pop()
    registry, request = _write_request(tmp_path, payloads)
    run = registry.run(request)
    assert run.result["result_state"] == "partial"
    unresolved = run.result["whole_product_profile"]["role_fractions"][-1]
    assert unresolved["role"] == "unresolved" and unresolved["numerator"] == 1
    assert "composition_residual_unresolved" in run.reason_codes


def test_zero_target_denominator_has_null_fractions(tmp_path: Path) -> None:
    payloads = _payloads()
    for assignment in payloads["development_state_map"]["assignments"]:
        assignment["target_related"] = False
    registry, request = _write_request(tmp_path, payloads)
    run = registry.run(request)
    target = run.result["target_related_profile"]
    assert target["denominator"] == 0
    assert all(item["fraction"] is None for item in target["role_fractions"])
    assert "target_related_denominator_zero" in run.reason_codes


def test_multiple_real_timepoints_are_descriptive_only(tmp_path: Path) -> None:
    registry, request = _write_request(tmp_path, _payloads(include_series=True))
    run = registry.run(request)
    assert run.result["analysis_mode"] == "descriptive_timecourse"
    assert len(run.result["timecourse_profiles"]) == 2
    assert "inferential_timecourse_not_implemented" in run.reason_codes
    assert "in_vitro_day" not in json.dumps(run.result)


def test_existing_output_drift_fails_without_overwrite(tmp_path: Path) -> None:
    registry, request = _write_request(tmp_path, _payloads())
    first = registry.run(request)
    output = first.artifacts[0].path
    output.write_text("{}\n", encoding="utf-8")
    second = registry.run(request)
    assert second.execution_state.value == "failed"
    assert second.reason_codes == ["existing_run_bundle_hash_mismatch"]
    assert output.read_text(encoding="utf-8") == "{}\n"


def test_direct_v1_request_is_typed_refusal(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    spec = registry.describe("P0-04")
    request = ToolRequest(
        request_id="legacy-request",
        tool_id="P0-04",
        tool_version="0.2.0",
        output_dir=tmp_path.resolve(),
    )
    eligibility = adapter.check_eligibility(request, spec)
    assert not eligibility.eligible
    assert eligibility.reason_codes == ["tool_request_v2_required"]
