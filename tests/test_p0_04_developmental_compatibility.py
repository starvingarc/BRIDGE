from __future__ import annotations

import csv
import hashlib
import json
from copy import deepcopy
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

from bridge.tool_packages.p0_04_developmental_compatibility.adapter import (
    REQUIRED_ROLES,
    RESULT_SCHEMA_REF,
    ROLE_MODELS,
    adapter,
)
from bridge.tool_packages.p0_04_developmental_compatibility.visualization_data import (
    ReferenceStageSimilarityRecord,
    _reference_summary,
)
from bridge.tool_packages.p0_04_developmental_compatibility.models import (
    PUBLIC_SCHEMA_MODELS,
)
from bridge.toolkit.contracts import (
    ExecutionState,
    EvidenceState,
    MeasurementResultV2,
    ScoreState,
    StructuredInputRef,
    ToolRequest,
    ToolRequestV2,
)
from bridge.toolkit.registry import ToolRegistry

ROLE_SCHEMAS = {role: contract[0] for role, contract in ROLE_MODELS.items()}
ROLE_VERSIONS = {
    "product_case": "0.1.0",
    "product_definition_card": "0.1.0",
    "development_window_spec": "0.1.0",
    "development_state_map": "0.1.0",
    "measurement_spec": "1.0.0",
    "cell_state_evidence_profile": "0.3.0",
    "qc_readiness_profile": "0.2.0",
    "biological_unit_manifest": "0.1.0",
    "biological_unit_assignment": "0.1.0",
    "annotation_vocabulary": "1.0.0",
    "reference_manifest": "1.0.0",
    "development_timepoint_series": "0.1.0",
    "development_method_spec": "0.1.0",
}


def _canonical_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _sha(payload: dict) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _ref(object_id: str, version: str = "1.0.0") -> dict[str, str]:
    return {"object_id": object_id, "object_version": version}


def _base_payloads() -> dict[str, dict]:
    product_ref = _ref("product-definition:demo")
    return {
        "product_case": {
            "object_version": "0.1.0",
            "product_case_id": "product-case:demo",
            "case_version": "1.0.0",
            "product_definition_ref": product_ref,
            "source_unit_kind": "sample",
            "sample_or_preparation_ref": _ref("sample:demo"),
            "measurement_spec_ref": _ref("measurement-spec:development"),
            "assay": "scRNA-seq",
            "provenance_refs": [_ref("source:fully-synthetic")],
            "created_at": "2026-08-25T00:00:00Z",
        },
        "product_definition_card": {
            "object_version": "0.1.0",
            "product_definition_id": product_ref["object_id"],
            "definition_version": product_ref["object_version"],
            "state_role_map_ref": _ref("state-role-map:demo"),
            "supported_assays": ["scRNA-seq"],
            "review_state": "draft",
            "provenance_refs": [_ref("source:fully-synthetic")],
        },
        "development_window_spec": {
            "object_version": "0.1.0",
            "window_spec_id": "development-window-spec:demo",
            "window_spec_version": "1.0.0",
            "product_definition_ref": product_ref,
            "state_map_ref": _ref("development-state-map:demo"),
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
            "state_map_id": "development-state-map:demo",
            "state_map_version": "1.0.0",
            "product_definition_ref": product_ref,
            "annotation_vocabulary_ref": "annotation-vocabulary:demo",
            "review_state": "reviewed",
            "assignments": [
                {
                    "state_id": state,
                    "label_level": "L2",
                    "stage_role": role,
                    "target_related": target_related,
                    "provenance_refs": [_ref(f"source:{state}")],
                }
                for state, role, target_related in (
                    ("state:early", "earlier", True),
                    ("state:window", "within_window", True),
                    ("state:late", "later", True),
                    ("state:branch", "branch_shift", True),
                    ("state:unresolved", "unresolved", False),
                )
            ],
        },
        "measurement_spec": {
            "measurement_spec_id": "measurement-spec:development",
            "version": "1.0.0",
            "scientific_question": "Synthetic developmental compatibility",
            "assay": "scRNA-seq",
            "status": "candidate",
            "applicable_product_cards": ["product-definition:demo"],
            "input_contract": {"source": "checksummed structured objects"},
            "analysis_unit": "preparation",
            "analysis_unit_kind": "preparation",
            "independence_group_kind": "preparation",
            "observation_unit_kind": "cell",
            "raw_metric_definition": {"metric_family": "developmental evidence"},
            "numerator": "externally mapped stage-role count",
            "denominator": "selected data view",
            "direction": None,
            "uncertainty_method": "independence-group bootstrap when configured",
            "minimum_data": {},
            "missing_behavior": "not_assessed",
            "tool_refs": ["P0-04"],
            "reference_refs": ["reference-snapshot:demo@1.0.0"],
            "prior_refs": ["prior:none"],
            "validation_ref": "validation:p0-04-synthetic",
            "exclusion_rules": {},
            "release_manifest_ref": None,
            "applicable_contexts": ["candidate"],
        },
        "qc_readiness_profile": {
            "profile_id": "qc-profile:demo",
            "input_level": "analysis_ready",
            "assay": "scRNA-seq",
            "assay_spec_id": None,
            "measurement_spec_status": "candidate",
            "measurement_spec_version": "1.0.0",
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
        "annotation_vocabulary": {
            "vocabulary_id": "annotation-vocabulary:demo",
            "version": "1.0.0",
            "product_scope": "fully-synthetic",
            "status": "candidate",
            "labels": [
                {
                    "state_id": state,
                    "display_name": state,
                    "level": "L2",
                    "parent_state_ids": [],
                    "aliases": [],
                    "status": "shadow",
                }
                for state in (
                    "state:early",
                    "state:window",
                    "state:late",
                    "state:branch",
                    "state:unresolved",
                )
            ],
            "alias_map": {},
            "unresolved_conflicts": [],
        },
        "reference_manifest": {
            "snapshot_id": "reference-snapshot:demo",
            "version": "1.0.0",
            "status": "candidate",
            "vocabulary_file": "annotation_vocabulary.json",
            "vocabulary_sha256": "0" * 64,
            "marker_program_file": "marker_programs.json",
            "marker_program_sha256": "d" * 64,
            "measurement_spec_ids": ["measurement-spec:development"],
            "profiles": [],
            "prohibited_source_families": [],
        },
    }


def _composition(denominator: int) -> dict:
    counts = [
        ("state:early", 2),
        ("state:window", denominator - 6),
        ("state:late", 2),
        ("state:branch", 1),
        ("state:unresolved", 1),
    ]
    records = [
        {
            "view": "consensus_supported_only",
            "source_id": None,
            "label": label,
            "label_level": "L2",
            "state_evidence_state": "candidate",
            "denominator_scope": "selected_data_view",
            "count": count,
            "fraction": count / denominator,
            "denominator": denominator,
        }
        for label, count in counts
    ]
    records.append(
        {
            "view": "reconciliation_state",
            "source_id": None,
            "label": "consensus_supported",
            "label_level": "L2",
            "state_evidence_state": "candidate",
            "denominator_scope": "selected_data_view",
            "count": denominator,
            "fraction": 1.0,
            "denominator": denominator,
        }
    )
    return {"state": "shadow", "records": records}


def _prepare(
    payloads: dict[str, dict],
    *,
    n_observations: int = 12,
    units: list[tuple[str, str]] | None = None,
) -> None:
    resolved_units = units or [
        ("preparation:unit-demo@1.0.0", "preparation:unit-demo@1.0.0")
    ]
    observation_ids = [
        f"demo-observation-{index:04d}" for index in range(n_observations)
    ]
    observation_sha = hashlib.sha256(
        json.dumps(
            sorted(observation_ids),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    view = {
        "view_id": "data-view:demo:qc-selected",
        "view_kind": "qc_selected_observations",
        "artifact_id": "artifact:demo:selected-view",
        "sha256": "a" * 64,
        "parent_asset_id": "asset:demo-parent",
        "parent_asset_sha256": "b" * 64,
        "matrix_location": "X",
        "matrix_semantics": "normalized_expression",
        "n_observations": n_observations,
        "observation_ids_sha256": observation_sha,
        "sample_or_preparation_ref": "sample:demo@1.0.0",
        "selection_spec_ref": "QC-scRNA-candidate-v0.1@0.1.0",
    }
    assignments = [
        {
            "observation_id": observation_id,
            "capture_ref": None,
            "preparation_ref": capture_ref,
            "sample_ref": "sample:demo@1.0.0",
            "donor_ref": None,
            "animal_ref": None,
            "graft_unit_ref": None,
            "analysis_unit_ref": capture_ref,
            "independence_group_ref": group_ref,
        }
        for index, observation_id in enumerate(observation_ids)
        for capture_ref, group_ref in [resolved_units[index % len(resolved_units)]]
    ]
    assignment = {
        "object_version": "0.1.0",
        "schema_ref": "bridge://schemas/biological-unit-assignment/v0.1",
        "data_view_ref": view["view_id"],
        "observation_ids_sha256": observation_sha,
        "assignments": assignments,
    }
    manifest = {
        "object_version": "0.1.0",
        "manifest_id": "biological-unit-manifest:demo",
        "manifest_version": "1.0.0",
        "schema_ref": "bridge://schemas/biological-unit-manifest/v0.1",
        "generator_tool_id": "BRIDGE-BIOLOGICAL-UNIT-REVIEW",
        "generator_tool_version": "1.0.0",
        "data_view_ref": view["view_id"],
        "selected_artifact_sha256": view["sha256"],
        "observation_ids_sha256": observation_sha,
        "n_observations": n_observations,
        "assignment_schema_ref": (
            "bridge://schemas/biological-unit-assignment/v0.1"
        ),
        "assignment_artifact_sha256": _sha(assignment),
        "assignment_row_count": n_observations,
        "unit_identity_namespace_ref": _ref("biological-unit-namespace:demo"),
        "analysis_unit_kind": "preparation",
        "independence_group_kind": "preparation",
        "independence_scope_ref": _ref("independence-scope:demo"),
        "lineage_state": "reviewed",
        "review_gate_ref": _ref("biological-unit-review:demo"),
        "review_gate_sha256": "e" * 64,
        "unit_bindings": [
            {
                "analysis_unit_ref": _versioned_ref(capture_ref),
                "analysis_unit_kind": "preparation",
                "independence_group_ref": _versioned_ref(group_ref),
                "independence_group_kind": "preparation",
                "capture_ref": None,
                "preparation_ref": _versioned_ref(capture_ref),
                "sample_ref": _ref("sample:demo"),
            }
            for capture_ref, group_ref in resolved_units
        ],
    }
    manifest_sha = _sha(manifest)
    view.update(
        {
            "biological_unit_manifest_ref": (
                "biological-unit-manifest:demo@1.0.0"
            ),
            "biological_unit_manifest_sha256": manifest_sha,
        }
    )
    payloads["biological_unit_assignment"] = assignment
    payloads["biological_unit_manifest"] = manifest
    case = payloads["product_case"]
    case.update(
        {
            "independence_group_refs": [
                _versioned_ref(value)
                for value in sorted({item[1] for item in resolved_units})
            ],
            "biological_unit_manifest_ref": _ref(
                "biological-unit-manifest:demo"
            ),
            "biological_unit_manifest_sha256": manifest_sha,
            "independence_scope_ref": _ref("independence-scope:demo"),
        }
    )
    qc = payloads["qc_readiness_profile"]
    qc["selected_data_view"] = deepcopy(view)
    vocabulary = payloads["annotation_vocabulary"]
    reference = payloads["reference_manifest"]
    reference["vocabulary_sha256"] = _sha(vocabulary)
    measurement = payloads["measurement_spec"]
    payloads["cell_state_evidence_profile"] = {
        "profile_id": "cell-state-profile:run-demo",
        "assay": "scRNA-seq",
        "measurement_spec_id": measurement["measurement_spec_id"],
        "measurement_spec_status": measurement["status"],
        "annotation_vocabulary_ref": vocabulary["vocabulary_id"],
        "reference_snapshot_ref": reference["snapshot_id"],
        "n_observations": n_observations,
        "n_genes": 100,
        "denominator": "selected_data_view",
        "label_levels": {"L2": {"state": "shadow"}},
        "source_support": {"state": "shadow"},
        "marker_program_evidence": {"state": "shadow"},
        "prediction_sets": {"state": "shadow"},
        "composition": _composition(n_observations),
        "gene_coverage": {"state": "available"},
        "modality_sensitivity": {"state": "not_assessed"},
        "method_outputs": {},
        "assignment_state": {"state": "candidate_prediction_set"},
        "unknown_reason": {"state": "not_assessed"},
        "calibration": {"state": "not_assessed"},
        "method_disagreement": {},
        "per_state_release": {
            state: "shadow"
            for state in (
                "state:early",
                "state:window",
                "state:late",
                "state:branch",
                "state:unresolved",
            )
        },
        "unresolved_labels": [],
        "warnings": [],
        "evidence_ids": ["evidence:cell-state-demo"],
        "score_state": "shadow",
        "domain_score": None,
        "measurement_spec_version": measurement["version"],
        "measurement_spec_sha256": _sha(measurement),
        "annotation_vocabulary_version": vocabulary["version"],
        "annotation_vocabulary_sha256": _sha(vocabulary),
        "reference_manifest_version": reference["version"],
        "reference_manifest_sha256": _sha(reference),
        "upstream_qc_profile_ref": qc["profile_id"],
        "upstream_qc_profile_sha256": _sha(qc),
        "input_data_view": deepcopy(view),
        "open_set_state": "not_assessed",
        "calibration_state": "not_assessed",
        "producer_run_ref": "run-demo",
        "producer_tool_id": "P0-02",
        "producer_tool_version": "0.5.0",
        "environment_spec_ref": "ENV-CELLSTATE-PY-v0.1",
    }


def _versioned_ref(value: str) -> dict[str, str]:
    object_id, separator, object_version = value.rpartition("@")
    if not separator:
        raise ValueError("versioned reference required")
    return {"object_id": object_id, "object_version": object_version}


def _request(
    tmp_path: Path,
    payloads: dict[str, dict] | None = None,
    *,
    include_series: bool = False,
    units: list[tuple[str, str]] | None = None,
    n_observations: int = 12,
    output_dir: Path | None = None,
) -> ToolRequestV2:
    values = deepcopy(payloads or _base_payloads())
    _prepare(values, n_observations=n_observations, units=units)
    if include_series:
        values["development_timepoint_series"] = {
            "object_version": "0.1.0",
            "series_id": "development-timepoint-series:demo",
            "series_version": "1.0.0",
            "product_case_ref": _ref("product-case:demo"),
            "state_map_ref": _ref("development-state-map:demo"),
            "time_basis": "in_vitro_day",
            "records": [
                {
                    "timepoint_id": f"timepoint-{order}",
                    "timepoint_order": order,
                    "timepoint_label": f"D{day}",
                    "independence_group_refs": [_ref(f"sample:t{order}")],
                    "denominator": 10,
                    "state_counts": [
                        {
                            "state_id": "state:early",
                            "label_level": "L2",
                            "count": early,
                        },
                        {
                            "state_id": "state:window",
                            "label_level": "L2",
                            "count": 10 - early,
                        },
                    ],
                }
                for order, day, early in ((0, 16, 7), (1, 25, 3))
            ],
        }
    root = tmp_path / "objects"
    root.mkdir(parents=True)
    roles = sorted(REQUIRED_ROLES | ({"development_timepoint_series"} if include_series else set()))
    refs = []
    for index, role in enumerate(roles, start=1):
        path = root / f"{role}.json"
        raw = _canonical_bytes(values[role])
        path.write_bytes(raw)
        refs.append(
            StructuredInputRef(
                input_id=f"input-{index}",
                role=role,
                schema_ref=ROLE_SCHEMAS[role],
                object_version=ROLE_VERSIONS[role],
                path=path,
                sha256=hashlib.sha256(raw).hexdigest(),
                media_type="application/json",
            )
        )
    return ToolRequestV2(
        request_id="request-p0-04",
        tool_id="P0-04",
        tool_version="0.5.0",
        output_dir=output_dir or (tmp_path / "output"),
        object_inputs=refs,
    )


def _run(request: ToolRequestV2):
    return ToolRegistry.load_default().run(request)


def _mutate(request: ToolRequestV2, role: str, change) -> ToolRequestV2:
    refs = []
    for ref in request.object_inputs:
        if ref.role != role:
            refs.append(ref)
            continue
        payload = json.loads(ref.path.read_text(encoding="utf-8"))
        change(payload)
        raw = _canonical_bytes(payload)
        ref.path.write_bytes(raw)
        refs.append(
            ref.model_copy(update={"sha256": hashlib.sha256(raw).hexdigest()})
        )
    return request.model_copy(update={"object_inputs": refs})


def test_registry_exposes_current_traceable_contract() -> None:
    registry = ToolRegistry.load_default()
    spec = registry.describe("P0-04")
    assert spec.version == "0.5.0"
    assert spec.implementation_state.value == "implemented"
    assert RESULT_SCHEMA_REF.endswith("/v0.3")
    assert ROLE_SCHEMAS["cell_state_evidence_profile"].endswith("/v0.3")
    assert len(REQUIRED_ROLES) == 11


@pytest.mark.parametrize("schema_ref,model", PUBLIC_SCHEMA_MODELS.items())
def test_public_models_emit_draft_2020_12_schemas(schema_ref: str, model) -> None:
    schema = model.model_json_schema()
    Draft202012Validator.check_schema(schema)
    assert schema_ref.startswith("bridge://schemas/")


def test_valid_aggregation_reports_two_denominators_and_no_score(
    tmp_path: Path,
) -> None:
    run = _run(_request(tmp_path))
    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result_schema_ref.endswith("/v0.3")
    assert run.result["object_version"] == "0.3.0"
    assert run.result["result_state"] == "complete"
    assert run.result["whole_product_profile"]["denominator"] == 12
    assert run.result["target_related_profile"]["denominator"] == 11
    assert run.result["reference_stage_support"]["assessment_state"] == "unavailable"
    assert run.result["domain_score"] is None
    assert run.result["score_state"] == "unavailable"
    assert len(run.measurements) == 10
    assert len(run.result["measurement_artifacts"]) == 10
    assert len(run.artifacts) == 25
    assert {artifact.kind for artifact in run.artifacts} == {
        "developmental_compatibility_result",
        "developmental_compatibility_visualization_data",
        "measurement_result_v2",
        "visualization_table",
        "visualization_render",
        "visualization_artifact_set",
    }
    assert sum(item.kind == "visualization_table" for item in run.artifacts) == 3
    assert sum(item.kind == "visualization_render" for item in run.artifacts) == 9
    measurement_by_id = {
        measurement.measurement_id: measurement
        for measurement in run.measurements
    }
    for measurement in run.measurements:
        assert measurement.domain_score is None
        assert measurement.score_state is ScoreState.UNAVAILABLE
        assert measurement.raw_value == measurement.numerator / measurement.denominator
        assert measurement.interval is None
    for artifact in run.artifacts:
        assert hashlib.sha256(artifact.path.read_bytes()).hexdigest() == artifact.sha256
        if artifact.kind == "measurement_result_v2":
            projected = MeasurementResultV2.model_validate_json(
                artifact.path.read_text(encoding="utf-8")
            )
            assert projected == measurement_by_id[projected.measurement_id]
        if artifact.kind == "visualization_table":
            text = artifact.path.read_text(encoding="utf-8")
            assert list(csv.DictReader(StringIO(text), delimiter="\t"))
            assert "\\n" not in text
        if artifact.kind == "visualization_render" and artifact.media_type == "image/svg+xml":
            assert b"\\n" not in artifact.path.read_bytes()


def test_same_inputs_reuse_deterministic_bundle(tmp_path: Path) -> None:
    request = _request(tmp_path)
    first = _run(request)
    second = _run(request)
    assert first.run_id == second.run_id
    assert first.result == second.result
    assert [item.sha256 for item in first.artifacts] == [item.sha256 for item in second.artifacts]


def test_required_lineage_and_checksum_fail_closed(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)
    payload = request.model_dump(mode="json")
    payload["object_inputs"][0]["sha256"] = "0" * 64
    invalid = registry.parse_request(payload)
    eligibility = registry.check_eligibility(invalid)
    assert not eligibility.eligible
    assert "structured_input_checksum_mismatch" in eligibility.reason_codes


def test_unconfirmed_window_and_unavailable_upstream_are_typed(
    tmp_path: Path,
) -> None:
    payloads = _base_payloads()
    payloads["development_window_spec"].update(
        review_state="candidate", reviewer_ref=None, confirmed_at=None
    )
    run = _run(_request(tmp_path / "candidate", payloads))
    assert run.execution_state is ExecutionState.PARTIAL
    assert run.result["window_compatibility_state"] == "not_assessed"
    assert "development_window_not_confirmed" in run.reason_codes

    request = _request(tmp_path / "unavailable")
    request = _mutate(
        request,
        "cell_state_evidence_profile",
        lambda payload: payload.update(
            composition={"state": "unavailable", "records": []}
        ),
    )
    run = _run(request)
    assert run.result["result_state"] == "not_assessed"
    assert run.result["whole_product_profile"] is None
    assert run.result["evidence_state"] == "unavailable"
    assert len(run.measurements) == 10
    assert all(item.raw_value is None for item in run.measurements)
    assert all(item.numerator is None for item in run.measurements)
    assert all(item.denominator is None for item in run.measurements)
    assert all(
        item.evidence_state is EvidenceState.UNAVAILABLE
        for item in run.measurements
    )


@pytest.mark.parametrize(
    ("composition_state", "evidence_state", "unknown_scope"),
    [
        ("missing", EvidenceState.MISSING, None),
        ("unknown", EvidenceState.UNKNOWN, "measurement"),
        ("unavailable", EvidenceState.UNAVAILABLE, None),
    ],
)
def test_missing_unknown_and_unavailable_measurements_are_never_zero(
    tmp_path: Path,
    composition_state: str,
    evidence_state: EvidenceState,
    unknown_scope: str | None,
) -> None:
    request = _request(tmp_path)
    request = _mutate(
        request,
        "cell_state_evidence_profile",
        lambda payload: payload.update(
            composition={"state": composition_state, "records": []}
        ),
    )
    run = _run(request)
    assert len(run.measurements) == 10
    for measurement in run.measurements:
        assert measurement.evidence_state is evidence_state
        assert measurement.unknown_scope == unknown_scope
        assert measurement.raw_value is None
        assert measurement.numerator is None
        assert measurement.denominator is None
        assert measurement.interval is None
        assert measurement.score_state is ScoreState.UNAVAILABLE


def test_real_timepoints_remain_descriptive_without_method_spec(
    tmp_path: Path,
) -> None:
    run = _run(_request(tmp_path, include_series=True))
    assert run.result["analysis_mode"] == "descriptive_timecourse"
    assert len(run.result["timecourse_profiles"]) == 2
    assert len(run.measurements) == 30
    assert len(run.result["measurement_artifacts"]) == 30
    assert "inferential_timecourse_unavailable" in run.reason_codes


def test_changed_existing_measurement_bundle_is_refused(tmp_path: Path) -> None:
    request = _request(tmp_path)
    first = _run(request)
    metric_path = next(
        item.path
        for item in first.artifacts
        if item.kind == "measurement_result_v2"
    )
    metric_path.write_text("{}", encoding="utf-8")
    second = _run(request)
    assert second.execution_state is ExecutionState.FAILED
    assert second.reason_codes == ["existing_run_bundle_hash_mismatch"]


def test_v1_request_is_typed_refusal(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    spec = registry.describe("P0-04")
    request = ToolRequest(
        request_id="legacy-request",
        tool_id="P0-04",
        tool_version="0.5.0",
        output_dir=tmp_path.resolve(),
    )
    eligibility = adapter.check_eligibility(request, spec)
    assert not eligibility.eligible
    assert eligibility.reason_codes == ["tool_request_v2_required"]


def _artifact_json(run, kind: str) -> dict:
    artifact = next(item for item in run.artifacts if item.kind == kind)
    return json.loads(artifact.path.read_text(encoding="utf-8"))


def test_reference_similarity_keeps_partial_numeric_evidence() -> None:
    record = ReferenceStageSimilarityRecord(
        record_id="reference.partial",
        analysis_unit_ref="preparation:unit@1.0.0",
        profile_id="reference-profile:development",
        source_id="source:development",
        assay="scRNA-seq",
        anatomy="ventral midbrain",
        reference_scope="registered stages",
        top_label="reference:window",
        top_stage_role="within_window",
        top_ordinal_rank=1,
        top_spearman_support=None,
        top_cosine_support=None,
        margin=None,
        shared_genes=12,
        output_semantics="uncalibrated_similarity_not_age_or_probability",
        evidence_ids=["evidence:partial"],
        evidence_state=EvidenceState.INFERRED,
        scientific_status="candidate",
        missingness="available",
        applicability="partially_applicable",
        reason_codes=["similarity_metric_partially_unavailable"],
    )
    assert record.top_label == "reference:window"
    assert record.top_spearman_support is None
    assert record.margin is None

    result = SimpleNamespace(
        reference_stage_support=SimpleNamespace(reason_code=None)
    )
    available = record.model_copy(
        update={
            "top_spearman_support": 0.72,
            "top_cosine_support": 0.69,
            "applicability": "applicable",
            "reason_codes": [],
        }
    )
    assert _reference_summary(result=result, records=[available]) == (
        EvidenceState.INFERRED,
        "applicable",
        [],
    )
    assert _reference_summary(result=result, records=[record]) == (
        EvidenceState.INFERRED,
        "partially_applicable",
        ["similarity_metric_partially_unavailable"],
    )
    unavailable = record.model_copy(
        update={
            "evidence_state": EvidenceState.UNAVAILABLE,
            "reason_codes": ["reference_source_unavailable"],
        }
    )
    assert _reference_summary(result=result, records=[available, unavailable]) == (
        EvidenceState.UNAVAILABLE,
        "partially_applicable",

        ["reference_source_unavailable"],
    )

def test_visualization_preserves_cell_state_resolution_classes(tmp_path: Path) -> None:
    request = _request(tmp_path)

    def set_resolution_classes(payload: dict) -> None:
        records = [
            item
            for item in payload["composition"]["records"]
            if item["view"] != "reconciliation_state"
        ]
        consensus_counts = {
            "state:early": 2,
            "state:window": 2,
            "state:late": 1,
            "state:branch": 1,
            "state:unresolved": 1,
        }
        for item in records:
            item["count"] = consensus_counts[item["label"]]
            item["fraction"] = item["count"] / 12
        for state, count in (
            ("candidate", 7),
            ("unknown", 1),
            ("ood", 1),
            ("unresolved", 2),
            ("unavailable", 1),
        ):
            records.append(
                {
                    "view": "reconciliation_state",
                    "source_id": None,
                    "label": (
                        "consensus_supported"
                        if state == "candidate"
                        else f"resolution:{state}"
                    ),
                    "label_level": "L2",
                    "state_evidence_state": state,
                    "denominator_scope": "selected_data_view",
                    "count": count,
                    "fraction": count / 12,
                    "denominator": 12,
                }
            )
        payload["composition"]["records"] = records

    request = _mutate(
        request, "cell_state_evidence_profile", set_resolution_classes
    )
    run = _run(request)
    data = _artifact_json(
        run, "developmental_compatibility_visualization_data"
    )
    counts = {
        item["resolution_state"]: item["count"]
        for item in data["resolution_records"]
    }
    assert counts == {
        "supported": 7,
        "unknown": 1,
        "ood": 1,
        "unresolved": 2,
        "unavailable": 1,
    }
    assert sum(counts.values()) == 12


def test_zero_target_denominator_remains_missing_not_zero(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request = _mutate(
        request,
        "development_state_map",
        lambda payload: [
            item.update(target_related=False) for item in payload["assignments"]
        ],
    )
    run = _run(request)
    data = _artifact_json(
        run, "developmental_compatibility_visualization_data"
    )
    target_records = [
        item
        for item in data["stage_records"]
        if item["denominator_kind"] == "target_related"
    ]
    assert target_records
    assert {item["denominator"] for item in target_records} == {0}
    assert all(item["fraction"] is None for item in target_records)
    assert {item["missingness"] for item in target_records} == {"unavailable"}
    whole_records = [
        item for item in data["stage_records"]
        if item["denominator_kind"] == "whole_product"
    ]
    assert all(
        "target_related_denominator_zero" not in item["reason_codes"]
        for item in whole_records
    )
    assert all(
        "target_related_denominator_zero" in item["reason_codes"]
        for item in target_records
    )
    target_measurements = [
        item
        for item in run.result["measurement_artifacts"]
        if item["denominator_kind"] == "target_related"
        and item["timepoint_id"] is None
    ]
    assert len(target_measurements) == 5
    assert all(
        item["reason_codes"] == ["target_related_denominator_zero"]
        for item in target_measurements
    )
    projected = {
        item.measurement_id: item for item in run.measurements
    }
    for binding in target_measurements:
        measurement = projected[binding["measurement_id"]]
        assert measurement.evidence_state is EvidenceState.UNAVAILABLE
        assert measurement.raw_value is None
        assert measurement.numerator is None
        assert measurement.denominator is None
        assert measurement.score_state is ScoreState.UNAVAILABLE


def test_one_sampling_point_is_not_presented_as_dynamic_change(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, include_series=True)
    request = _mutate(
        request,
        "development_timepoint_series",
        lambda payload: payload.update(records=payload["records"][:1]),
    )
    run = _run(request)
    artifact_set = _artifact_json(run, "visualization_artifact_set")
    component = next(
        item
        for item in artifact_set["visualizations"]
        if item["component_id"]
        == "bridge.developmental-compatibility.observed-sampling-points"
    )
    assert component["applicability"] == "not_assessed"
    assert (
        "single_sampling_point_dynamic_change_unavailable"
        in component["missing_reason_codes"]
    )


def test_supplied_but_unusable_series_is_not_reported_as_absent(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, include_series=True)
    request = _mutate(
        request,
        "cell_state_evidence_profile",
        lambda payload: payload.update(
            composition={"state": "unavailable", "records": []}
        ),
    )
    run = _run(request)
    artifact_set = _artifact_json(run, "visualization_artifact_set")
    components = {
        item["component_id"]: item
        for item in artifact_set["visualizations"]
    }

    for component_id in (
        "bridge.developmental-compatibility.window-composition",
        "bridge.developmental-compatibility.observed-sampling-points",
    ):
        component = components[component_id]
        table_id = component["accessibility"]["table_artifact_id"]
        table_artifact = next(
            artifact
            for artifact in run.artifacts
            if artifact.artifact_id == table_id
        )
        rows = list(
            csv.DictReader(
                StringIO(table_artifact.path.read_text(encoding="utf-8")),
                delimiter="\t",
            )
        )
        assert rows
        assert rows[0]["assessment_applicability"] == component["applicability"]

    time_component = components[
        "bridge.developmental-compatibility.observed-sampling-points"
    ]
    assert (
        "timepoint_series_not_supplied"
        not in time_component["missing_reason_codes"]
    )
    assert "sampling_point_composition_unavailable" in (
        time_component["missing_reason_codes"]
    )
