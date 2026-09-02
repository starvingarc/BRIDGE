from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from bridge.tool_packages.p0_05_off_target_control.adapter import adapter
from bridge.tool_packages.p0_05_off_target_control.visualization import (
    prepare_off_target_control_visualizations,
)
from bridge.tool_packages.p0_05_off_target_control.visualization_data import (
    OffTargetControlVisualizationDataV1,
    PRODUCT_COMPONENT_REF,
    RARE_COMPONENT_REF,
    P005VisualizationArtifactSet,
)
from bridge.toolkit.contracts import ExecutionState, StructuredInputRef, ToolRequestV2
from bridge.toolkit.registry import ToolRegistry
from p0_biological_units import bind_reviewed_biological_units
from test_p0_05_off_target_control import (
    _encoded,
    _projection_request,
    _projection_spec,
    _request,
    _with_measurement_spec,
    _write,
)


METHOD_ROLE_SCHEMAS = {
    "biological_unit_manifest": (
        "bridge://schemas/biological-unit-manifest/v0.1",
        "0.1.0",
    ),
    "off_target_method_spec": (
        "bridge://schemas/off-target-method-spec/v0.1",
        "0.1.0",
    ),
    "off_target_method_input": (
        "bridge://schemas/off-target-method-input/v0.1",
        "0.1.0",
    ),
}


def _sha(payload: dict) -> str:
    return hashlib.sha256(_encoded(payload)).hexdigest()


def _composition() -> dict:
    return {
        "state": "shadow",
        "records": [
            {
                "view": "consensus_supported_only",
                "source_id": None,
                "label": "state:a",
                "label_level": "L1",
                "state_evidence_state": "candidate",
                "denominator_scope": "selected_data_view",
                "count": 7,
                "fraction": 0.7,
                "denominator": 10,
            },
            {
                "view": "consensus_supported_only",
                "source_id": None,
                "label": "state:b",
                "label_level": "L1",
                "state_evidence_state": "candidate",
                "denominator_scope": "selected_data_view",
                "count": 2,
                "fraction": 0.2,
                "denominator": 10,
            },
            {
                "view": "reconciliation_state",
                "source_id": None,
                "label": "consensus_supported",
                "label_level": "L1",
                "state_evidence_state": "candidate",
                "denominator_scope": "selected_data_view",
                "count": 9,
                "fraction": 0.9,
                "denominator": 10,
            },
            {
                "view": "reconciliation_state",
                "source_id": None,
                "label": "reference_gap",
                "label_level": "L1",
                "state_evidence_state": "unknown",
                "denominator_scope": "selected_data_view",
                "count": 1,
                "fraction": 0.1,
                "denominator": 10,
            },
        ],
    }


def _analysis_units() -> list[dict]:
    rows = [
        ("u1", "g1", 3, 2.0, 2, 0.5, 0, 0.5, 1),
        ("u2", "g2", 3, 2.0, 2, 1.0, 1, 0.0, 0),
        ("u3", "g3", 2, 1.5, 2, 0.5, 0, 0.0, 0),
        ("u4", "g4", 2, 1.5, 1, 0.0, 1, 0.5, 0),
    ]
    return [
        {
            "analysis_unit_ref": f"preparation:{unit}@1.0.0",
            "independence_group_ref": f"sample:{group}@1.0.0",
            "denominator_count": denominator,
            "state_observations": [
                {
                    "state_id": "state:a",
                    "soft_mass": a_soft,
                    "hard_count": a_hard,
                },
                {
                    "state_id": "state:b",
                    "soft_mass": b_soft,
                    "hard_count": b_hard,
                },
            ],
            "unknown_observations": [
                {
                    "reason_id": "reference_gap",
                    "soft_mass": unknown_soft,
                    "hard_count": unknown_hard,
                }
            ],
        }
        for (
            unit,
            group,
            denominator,
            a_soft,
            a_hard,
            b_soft,
            b_hard,
            unknown_soft,
            unknown_hard,
        ) in rows
    ]


def _method_request(tmp_path: Path) -> ToolRequestV2:
    legacy = _request(tmp_path)
    payloads = {
        ref.role: json.loads(ref.path.read_text(encoding="utf-8"))
        for ref in legacy.object_inputs
    }
    units = [
        (f"preparation:u{index}@1.0.0", f"sample:g{index}@1.0.0")
        for index in range(1, 5)
    ]
    view = {
        "view_id": "data-view:p0-05:qc-selected",
        "view_kind": "qc_selected_observations",
        "artifact_id": "artifact:p0-05:candidate-view",
        "sha256": "a" * 64,
        "parent_asset_id": "asset:p0-05-demo",
        "parent_asset_sha256": "b" * 64,
        "matrix_location": "X",
        "matrix_semantics": "raw_counts",
        "n_observations": 10,
        "observation_ids_sha256": "c" * 64,
        "sample_or_preparation_ref": "preparation:demo@1",
        "selection_spec_ref": "QC-scRNA-candidate-v0.1@0.1.0",
    }
    bind_reviewed_biological_units(
        payloads,
        view,
        slug="p0-05-demo",
        units=units,
        observation_ids=[f"demo-cell-{index:02d}" for index in range(10)],
    )
    manifest = payloads["biological_unit_manifest"]
    manifest_sha = _sha(manifest)
    view["biological_unit_manifest_sha256"] = manifest_sha
    payloads["product_case"]["biological_unit_manifest_sha256"] = manifest_sha

    payloads["cell_state_evidence_profile"] = {
        "profile_id": "cell-state-profile:run-p0-05-demo",
        "assay": "scRNA-seq",
        "measurement_spec_id": "measurement-spec:cell-state",
        "measurement_spec_status": "candidate",
        "annotation_vocabulary_ref": "annotation-vocabulary:demo",
        "reference_snapshot_ref": "reference-snapshot:demo",
        "n_observations": 10,
        "n_genes": 100,
        "denominator": "selected_data_view",
        "label_levels": {"L1": {"state": "shadow"}},
        "source_support": {"state": "shadow"},
        "marker_program_evidence": {"state": "shadow"},
        "prediction_sets": {"state": "shadow"},
        "composition": _composition(),
        "gene_coverage": {"state": "available"},
        "modality_sensitivity": {"state": "not_assessed"},
        "method_outputs": {},
        "assignment_state": {"state": "candidate_prediction_set"},
        "unknown_reason": {"state": "unknown"},
        "calibration": {"state": "not_assessed"},
        "method_disagreement": {},
        "per_state_release": {"state:a": "shadow", "state:b": "shadow"},
        "unresolved_labels": ["reference_gap"],
        "warnings": [],
        "evidence_ids": ["evidence:p0-05-demo"],
        "score_state": "shadow",
        "domain_score": None,
        "measurement_spec_version": "1",
        "measurement_spec_sha256": "d" * 64,
        "annotation_vocabulary_version": "1",
        "annotation_vocabulary_sha256": "e" * 64,
        "reference_manifest_version": "1",
        "reference_manifest_sha256": "f" * 64,
        "upstream_qc_profile_ref": "qc-profile:p0-05-demo",
        "upstream_qc_profile_sha256": "1" * 64,
        "input_data_view": deepcopy(view),
        "open_set_state": "candidate",
        "calibration_state": "not_assessed",
        "producer_run_ref": "run-p0-05-demo",
        "producer_tool_id": "P0-02",
        "producer_tool_version": "0.5.0",
        "environment_spec_ref": "ENV-CELLSTATE-PY-v0.1",
    }

    root = legacy.object_inputs[0].path.parent
    product_case_sha = _write(root / "product_case.json", payloads["product_case"])
    profile_sha = _write(
        root / "cell_state_evidence_profile.json",
        payloads["cell_state_evidence_profile"],
    )
    evidence = payloads["off_target_evidence_bundle"]
    evidence.update(
        {
            "product_case_sha256": product_case_sha,
            "cell_state_profile_id": "cell-state-profile:run-p0-05-demo",
            "cell_state_profile_sha256": profile_sha,
        }
    )
    evidence_sha = _write(root / "off_target_evidence_bundle.json", evidence)
    _write(root / "biological_unit_manifest.json", manifest)

    method_spec = {
        "object_version": "0.1.0",
        "method_spec_id": "off-target-method-spec:demo",
        "method_spec_version": "1.0.0",
        "status": "candidate",
        "selected_method_ids": [
            "COMP-EXACT",
            "COMP-HARD-SENS",
            "COMP-HBOOT",
            "RARE-EXACT",
            "RARE-SPIKEIN",
            "RARE-BINOMIAL-AT-LEAST-ONE",
            "OOD-DISAGREE",
            "OOD-ENSEMBLE",
        ],
        "confidence_level": 0.9,
        "bootstrap_replicates": 200,
        "minimum_spike_in_detection_probability": 0.2,
        "planning_targets": [
            {
                "state_id": "state:b",
                "expected_frequency_fraction": 0.01,
                "desired_detection_probability": 0.95,
            }
        ],
        "ood_channel_bindings": [
            {
                "channel_id": "ood-channel:reference",
                "source_family_id": "ood-family:reference",
                "upstream_result_sha256": "5" * 64,
                "method_ref": "METHOD-REFERENCE-DISTANCE",
                "reference_ref": "reference:demo",
            },
            {
                "channel_id": "ood-channel:model",
                "source_family_id": "ood-family:model",
                "upstream_result_sha256": "6" * 64,
                "method_ref": "METHOD-OOD-MODEL",
                "reference_ref": "reference:demo",
            },
        ],
        "ood_decision_rules": [
            {
                "channel_state": "ood",
                "output_state": "ood",
                "minimum_distinct_source_families": 2,
                "reason_id": "reference_gap",
            }
        ],
        "active": True,
    }
    _write(root / "off_target_method_spec.json", method_spec)
    method_input = {
        "object_version": "0.1.0",
        "method_input_id": "off-target-method-input:demo",
        "method_input_version": "1.0.0",
        "product_case_ref": "product-case:demo@1",
        "product_case_sha256": product_case_sha,
        "cell_state_profile_id": "cell-state-profile:run-p0-05-demo",
        "cell_state_profile_sha256": profile_sha,
        "evidence_bundle_ref": "off-target-evidence-bundle:demo@1",
        "evidence_bundle_sha256": evidence_sha,
        "biological_unit_manifest_ref": ("biological-unit-manifest:p0-05-demo@1.0.0"),
        "biological_unit_manifest_sha256": manifest_sha,
        "analysis_units": _analysis_units(),
        "spike_in_trials": [
            {
                "state_id": "state:b",
                "independence_group_ref": f"sample:g{index}@1.0.0",
                "spike_fraction": 0.02,
                "n_observations": 100,
                "expected_spike_count": 2,
                "recovered_spike_count": 2,
                "false_positive_count": 0,
            }
            for index in range(1, 5)
        ],
        "ood_channels": [
            {
                "channel_id": "ood-channel:reference",
                "state": "ood",
                "reason_id": "reference_gap",
            },
            {
                "channel_id": "ood-channel:model",
                "state": "ood",
                "reason_id": "reference_gap",
            },
        ],
        "created_at": "2026-08-25T00:00:00Z",
    }
    _write(root / "off_target_method_input.json", method_input)

    schema_by_role = {
        ref.role: (ref.schema_ref, ref.object_version) for ref in legacy.object_inputs
    }
    schema_by_role["cell_state_evidence_profile"] = (
        "bridge://schemas/cell-state-evidence-profile/v0.3",
        "0.3.0",
    )
    schema_by_role.update(METHOD_ROLE_SCHEMAS)
    refs = []
    for index, (role, (schema_ref, object_version)) in enumerate(
        schema_by_role.items(), start=1
    ):
        path = root / f"{role}.json"
        raw = path.read_bytes()
        refs.append(
            StructuredInputRef(
                input_id=f"input-{index}",
                role=role,
                schema_ref=schema_ref,
                object_version=object_version,
                path=path,
                sha256=hashlib.sha256(raw).hexdigest(),
            )
        )
    return legacy.model_copy(
        update={
            "request_id": "request-p0-05-methods",
            "object_inputs": refs,
        }
    )


def _rewrite_method(request: ToolRequestV2, role: str, change) -> ToolRequestV2:
    refs = list(request.object_inputs)
    index = next(index for index, ref in enumerate(refs) if ref.role == role)
    ref = refs[index]
    payload = json.loads(ref.path.read_text(encoding="utf-8"))
    change(payload)
    digest = _write(ref.path, payload)
    refs[index] = ref.model_copy(update={"sha256": digest})
    return request.model_copy(update={"object_inputs": refs})


def _method_request_with_measurement_spec(tmp_path: Path) -> ToolRequestV2:
    request = _projection_request(
        _with_measurement_spec(_method_request(tmp_path))
    )
    measurement_sha = next(
        item.sha256 for item in request.object_inputs if item.role == "measurement_spec"
    )
    request = _rewrite_method(
        request,
        "cell_state_evidence_profile",
        lambda payload: payload.update(
            {"measurement_spec_sha256": measurement_sha}
        ),
    )
    profile_sha = next(
        item.sha256
        for item in request.object_inputs
        if item.role == "cell_state_evidence_profile"
    )
    request = _rewrite_method(
        request,
        "off_target_evidence_bundle",
        lambda payload: payload.update(
            {"cell_state_profile_sha256": profile_sha}
        ),
    )
    evidence_sha = next(
        item.sha256
        for item in request.object_inputs
        if item.role == "off_target_evidence_bundle"
    )
    return _rewrite_method(
        request,
        "off_target_method_input",
        lambda payload: payload.update(
            {
                "cell_state_profile_sha256": profile_sha,
                "evidence_bundle_sha256": evidence_sha,
            }
        ),
    )


def test_method_mode_executes_eight_transparent_methods(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    request = _method_request(tmp_path)

    assert registry.check_eligibility(request).eligible
    first = registry.run(request)
    second = registry.run(request)
    different_seed = registry.run(
        request.model_copy(update={"random_seed": request.random_seed + 1})
    )

    assert first.execution_state is ExecutionState.SUCCEEDED
    assert len(first.artifacts) == 16
    method_artifact = next(
        item for item in first.artifacts if item.kind == "off_target_method_bundle"
    )
    bundle = json.loads(method_artifact.path.read_text(encoding="utf-8"))
    assert [item["method_id"] for item in bundle["executions"]] == [
        "COMP-EXACT",
        "COMP-HARD-SENS",
        "COMP-HBOOT",
        "RARE-EXACT",
        "RARE-SPIKEIN",
        "RARE-BINOMIAL-AT-LEAST-ONE",
        "OOD-DISAGREE",
        "OOD-ENSEMBLE",
    ]
    assert {item["execution_state"] for item in bundle["executions"]} == {"succeeded"}
    assert len(bundle["composition_intervals"]) == 8
    assert len(bundle["hard_soft_sensitivity"]) == 4
    calibration = bundle["spike_in_calibrations"][0]
    assert calibration["assessment_state"] == "available"
    assert calibration["curve"][0]["trial_count"] == 4
    assert calibration["curve"][0]["independence_group_count"] == 4
    assert bundle["planning_records"][0]["required_observations"] == 299
    assert bundle["ood_disagreement"]["disagreement"] is False
    assert bundle["ood_ensemble"]["decision_state"] == "ood"
    assert bundle["evidence_state"] == "shadow"
    assert bundle["score_state"] == "unavailable"
    assert bundle["domain_score"] is None
    assert {
        item.path.name: item.sha256 for item in first.artifacts
    } == {
        item.path.name: item.sha256 for item in second.artifacts
    }
    visualization = next(
        item
        for item in first.artifacts
        if item.kind == "off_target_control_visualization_data"
    )
    figure_data = json.loads(visualization.path.read_text(encoding="utf-8"))
    rare = figure_data["rare_state_records"][0]
    assert "supplied_validated_detection_limit_fraction" in rare
    assert "supplied_zero_observation_upper_bound_fraction" in rare
    assert "spike_in_candidate_detection_limit_fraction" in rare
    assert "detection_hit_rate" in figure_data["spike_in_detection_records"][0]
    assert {
        item["upstream_result_sha256"]
        for item in figure_data["ood_channel_records"]
    } == {"5" * 64, "6" * 64}
    artifact_set = next(
        item
        for item in first.artifacts
        if item.kind == "visualization_artifact_set"
    )
    typed_set = P005VisualizationArtifactSet.model_validate_json(
        artifact_set.path.read_text(encoding="utf-8")
    )
    product_figure = next(
        item
        for item in typed_set.visualizations
        if item.component_ref == PRODUCT_COMPONENT_REF
    )
    rare_figure = next(
        item
        for item in typed_set.visualizations
        if item.component_ref == RARE_COMPONENT_REF
    )
    assert rare_figure.data_binding.unit_field == "unit"
    assert {item["unit"] for item in figure_data["rare_state_records"]} == {"cells"}
    assert product_figure.data_binding.numerator_field == "soft_mass"
    assert product_figure.data_binding.denominator_field == "denominator_soft_mass"
    assert product_figure.data_binding.interval_lower_field == "soft_interval_lower"
    assert product_figure.data_binding.interval_upper_field == "soft_interval_upper"
    assert first.run_id != different_seed.run_id


def test_method_mode_can_opt_into_measurement_projection(tmp_path: Path) -> None:
    request = _method_request_with_measurement_spec(tmp_path)

    registry = ToolRegistry.load_default()
    assert registry.check_eligibility(request).eligible
    run = registry.run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["object_version"] == "0.2.0"
    assert run.result_schema_ref == _projection_spec().result_schema_ref
    assert run.result["measurement_projection_state"] == "available"
    assert len(run.measurements) == 6
    assert len(
        [item for item in run.artifacts if item.kind == "measurement_result_v2"]
    ) == 6
    assert any(item.kind == "off_target_method_bundle" for item in run.artifacts)
    assert len(run.artifacts) == 22


def test_method_mode_rejects_measurement_spec_checksum_drift(
    tmp_path: Path,
) -> None:
    request = _rewrite_method(
        _method_request_with_measurement_spec(tmp_path),
        "measurement_spec",
        lambda payload: payload.update(
            {"scientific_question": "A changed projection contract"}
        ),
    )

    eligibility = adapter.check_eligibility(request, _projection_spec())

    assert not eligibility.eligible
    assert "measurement_spec_checksum_mismatch" in eligibility.reason_codes


def test_method_mode_partial_coverage_withholds_intervals(tmp_path: Path) -> None:
    request = _rewrite_method(
        _method_request(tmp_path),
        "off_target_evidence_bundle",
        lambda payload: payload.update(
            {
                "composition_coverage_state": "partial",
                "unknown_coverage_state": "partial",
            }
        ),
    )
    evidence_sha = next(
        item.sha256
        for item in request.object_inputs
        if item.role == "off_target_evidence_bundle"
    )
    request = _rewrite_method(
        request,
        "off_target_method_input",
        lambda payload: payload.update({"evidence_bundle_sha256": evidence_sha}),
    )

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    method_artifact = next(
        item for item in run.artifacts if item.kind == "off_target_method_bundle"
    )
    bundle = json.loads(method_artifact.path.read_text(encoding="utf-8"))
    execution = {
        item["method_id"]: item for item in bundle["executions"]
    }
    for method_id in ("COMP-EXACT", "COMP-HARD-SENS", "COMP-HBOOT", "RARE-EXACT"):
        assert execution[method_id]["execution_state"] == "not_assessed"
        assert execution[method_id]["reason_codes"] == [
            "composition_coverage_not_complete"
        ]
    assert bundle["hard_soft_sensitivity"] == []
    assert all(
        item["assessment_state"] == "not_assessed"
        and item["estimate"] is None
        and item["lower"] is None
        and item["upper"] is None
        for item in [
            *bundle["composition_intervals"],
            *bundle["rare_intervals"],
        ]
    )
    visualization = next(
        item
        for item in run.artifacts
        if item.kind == "off_target_control_visualization_data"
    )
    figure_data = json.loads(visualization.path.read_text(encoding="utf-8"))
    assert all(item["fraction"] is None for item in figure_data["product_records"])
    assert all(
        item["count_interval_state"] == "not_assessed"
        for item in figure_data["rare_state_records"]
    )



def test_method_mode_requires_all_three_additional_objects(tmp_path: Path) -> None:
    request = _method_request(tmp_path)
    request = request.model_copy(
        update={
            "object_inputs": [
                ref
                for ref in request.object_inputs
                if ref.role != "off_target_method_input"
            ]
        }
    )

    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert not eligibility.eligible
    assert "exactly_one_off_target_method_input_required" in eligibility.reason_codes


def test_method_mode_rejects_independence_group_drift(tmp_path: Path) -> None:
    request = _rewrite_method(
        _method_request(tmp_path),
        "off_target_method_input",
        lambda payload: payload["analysis_units"][0].update(
            {"independence_group_ref": "sample:other@1.0.0"}
        ),
    )

    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert not eligibility.eligible
    assert "method_input_independence_group_mismatch" in eligibility.reason_codes


def test_method_mode_rejects_file_replacement(tmp_path: Path) -> None:
    request = _method_request(tmp_path)
    ref = next(
        item for item in request.object_inputs if item.role == "off_target_method_spec"
    )
    ref.path.write_text(ref.path.read_text(encoding="utf-8") + " ")

    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert not eligibility.eligible
    assert eligibility.reason_codes == ["structured_input_checksum_mismatch"]


def test_method_mode_rejects_reused_spike_in_independence_group(
    tmp_path: Path,
) -> None:
    def reuse_group(payload: dict) -> None:
        payload["spike_in_trials"][1]["independence_group_ref"] = (
            payload["spike_in_trials"][0]["independence_group_ref"]
        )

    request = _rewrite_method(
        _method_request(tmp_path),
        "off_target_method_input",
        reuse_group,
    )

    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert not eligibility.eligible
    assert (
        "spike_in_independence_group_reused_within_fraction"
        in eligibility.reason_codes
    )


def test_method_mode_rejects_one_upstream_result_as_two_ood_families(
    tmp_path: Path,
) -> None:
    def duplicate_upstream(payload: dict) -> None:
        payload["ood_channel_bindings"][1]["upstream_result_sha256"] = (
            payload["ood_channel_bindings"][0]["upstream_result_sha256"]
        )

    request = _rewrite_method(
        _method_request(tmp_path),
        "off_target_method_spec",
        duplicate_upstream,
    )

    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert not eligibility.eligible
    assert (
        "ood_upstream_result_reused_across_source_families"
        in eligibility.reason_codes
    )


def test_method_mode_requires_reviewed_biological_unit_lineage(
    tmp_path: Path,
) -> None:
    request = _method_request(tmp_path)
    request = _rewrite_method(
        request,
        "biological_unit_manifest",
        lambda payload: payload.update(
            {
                "generator_tool_id": "P0-01",
                "lineage_state": "declared",
                "review_gate_ref": None,
                "review_gate_sha256": None,
            }
        ),
    )
    manifest_sha = next(
        item.sha256
        for item in request.object_inputs
        if item.role == "biological_unit_manifest"
    )
    request = _rewrite_method(
        request,
        "product_case",
        lambda payload: payload.update(
            {"biological_unit_manifest_sha256": manifest_sha}
        ),
    )
    product_case_sha = next(
        item.sha256 for item in request.object_inputs if item.role == "product_case"
    )
    request = _rewrite_method(
        request,
        "cell_state_evidence_profile",
        lambda payload: payload["input_data_view"].update(
            {"biological_unit_manifest_sha256": manifest_sha}
        ),
    )
    profile_sha = next(
        item.sha256
        for item in request.object_inputs
        if item.role == "cell_state_evidence_profile"
    )
    request = _rewrite_method(
        request,
        "off_target_evidence_bundle",
        lambda payload: payload.update(
            {
                "product_case_sha256": product_case_sha,
                "cell_state_profile_sha256": profile_sha,
            }
        ),
    )
    evidence_sha = next(
        item.sha256
        for item in request.object_inputs
        if item.role == "off_target_evidence_bundle"
    )
    request = _rewrite_method(
        request,
        "off_target_method_input",
        lambda payload: payload.update(
            {
                "product_case_sha256": product_case_sha,
                "cell_state_profile_sha256": profile_sha,
                "evidence_bundle_sha256": evidence_sha,
                "biological_unit_manifest_sha256": manifest_sha,
            }
        ),
    )

    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert not eligibility.eligible
    assert "biological_unit_lineage_not_reviewed" in eligibility.reason_codes


def test_mixed_channel_availability_marks_family_partially_applicable(
    tmp_path: Path,
) -> None:
    request = _rewrite_method(
        _method_request(tmp_path),
        "off_target_method_spec",
        lambda payload: payload["ood_channel_bindings"][1].update(
            {"source_family_id": "ood-family:reference"}
        ),
    )
    request = _rewrite_method(
        request,
        "off_target_method_input",
        lambda payload: payload["ood_channels"][1].update(
            {"state": "unavailable", "reason_id": None}
        ),
    )

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    visual = next(
        item
        for item in run.artifacts
        if item.kind == "off_target_control_visualization_data"
    )
    payload = json.loads(visual.path.read_text(encoding="utf-8"))
    assert len(payload["ood_family_records"]) == 1
    family = payload["ood_family_records"][0]
    assert family["channel_count"] == 2
    assert family["assessed_channel_count"] == 1
    assert family["family_state"] == "ood"
    assert family["applicability"] == "partially_applicable"
    assert family["reason_codes"] == ["ood_source_family_partially_assessed"]


def test_renderer_retains_more_than_five_spike_in_states(
    tmp_path: Path,
) -> None:
    run = ToolRegistry.load_default().run(_method_request(tmp_path))
    visual = next(
        item
        for item in run.artifacts
        if item.kind == "off_target_control_visualization_data"
    )
    payload = json.loads(visual.path.read_text(encoding="utf-8"))
    base = payload["spike_in_detection_records"][0]
    base_rare = payload["rare_state_records"][0]
    payload["rare_state_records"] = [
        {
            **base_rare,
            "record_id": f"rare.extra-{index:02d}",
            "state_id": f"state:curve-{index:02d}",
            "display_name": f"Curve state {index:02d}",
        }
        for index in range(1, 7)
    ]
    payload["spike_in_detection_records"] = [
        {
            **base,
            "record_id": f"spike.extra-{index:02d}",
            "state_id": f"state:curve-{index:02d}",
        }
        for index in range(1, 7)
    ]
    profile = OffTargetControlVisualizationDataV1.model_validate(payload)

    rendered = prepare_off_target_control_visualizations(
        profile=profile,
        output_dir=tmp_path / "rerender",
        run_id=run.run_id,
        tool_version="0.5.0",
    )
    svg = rendered.payloads[
        "off_target_control_rare-state-detectability.svg"
    ].decode()

    for index in range(1, 7):
        assert f"state:curve-{index:02d}" in svg


def test_visualization_schema_rejects_partial_rare_fraction(
    tmp_path: Path,
) -> None:
    request = _rewrite_method(
        _method_request(tmp_path),
        "off_target_evidence_bundle",
        lambda payload: payload.update(
            {
                "composition_coverage_state": "partial",
                "unknown_coverage_state": "partial",
            }
        ),
    )
    evidence_sha = next(
        item.sha256
        for item in request.object_inputs
        if item.role == "off_target_evidence_bundle"
    )
    request = _rewrite_method(
        request,
        "off_target_method_input",
        lambda payload: payload.update({"evidence_bundle_sha256": evidence_sha}),
    )
    run = ToolRegistry.load_default().run(request)
    visual = next(
        item
        for item in run.artifacts
        if item.kind == "off_target_control_visualization_data"
    )
    payload = json.loads(visual.path.read_text(encoding="utf-8"))
    rare = payload["rare_state_records"][0]
    rare["count_fraction"] = rare["observed_count"] / rare["denominator_count"]

    with pytest.raises(
        ValueError,
        match="incomplete composition coverage cannot expose rare-state fractions",
    ):
        OffTargetControlVisualizationDataV1.model_validate(payload)


def test_visualization_schema_rejects_ood_summary_drift(
    tmp_path: Path,
) -> None:
    run = ToolRegistry.load_default().run(_method_request(tmp_path))
    visual = next(
        item
        for item in run.artifacts
        if item.kind == "off_target_control_visualization_data"
    )
    payload = json.loads(visual.path.read_text(encoding="utf-8"))
    payload["ood_disagreement"]["family_states"] = {
        family_id: "supported"
        for family_id in payload["ood_disagreement"]["family_states"]
    }

    with pytest.raises(
        ValueError,
        match="OOD disagreement family states do not match rows",
    ):
        OffTargetControlVisualizationDataV1.model_validate(payload)
