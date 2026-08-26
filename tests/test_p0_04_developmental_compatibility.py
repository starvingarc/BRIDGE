from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from bridge.tool_packages.p0_04_developmental_compatibility.adapter import (
    REQUIRED_ROLES,
    ROLE_MODELS,
    adapter,
)
from bridge.tool_packages.p0_04_developmental_compatibility.models import (
    PUBLIC_SCHEMA_MODELS,
)
from bridge.toolkit.contracts import (
    ExecutionState,
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
        tool_version="0.3.0",
        output_dir=output_dir or (tmp_path / "output"),
        object_inputs=refs,
    )


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
    assert spec.version == "0.3.0"
    assert spec.implementation_state.value == "implemented"
    assert spec.result_schema_ref.endswith("/v0.2")
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
    run = ToolRegistry.load_default().run(_request(tmp_path))
    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["object_version"] == "0.2.0"
    assert run.result["result_state"] == "complete"
    assert run.result["whole_product_profile"]["denominator"] == 12
    assert run.result["target_related_profile"]["denominator"] == 11
    assert run.result["reference_stage_support"]["assessment_state"] == "unavailable"
    assert run.result["domain_score"] is None
    assert run.result["score_state"] == "unavailable"
    assert len(run.artifacts) == 1


def test_same_inputs_reuse_deterministic_bundle(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)
    first = registry.run(request)
    second = registry.run(request)
    assert first.run_id == second.run_id
    assert first.result == second.result
    assert first.artifacts[0].sha256 == second.artifacts[0].sha256


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
    run = ToolRegistry.load_default().run(_request(tmp_path / "candidate", payloads))
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
    run = ToolRegistry.load_default().run(request)
    assert run.result["result_state"] == "not_assessed"
    assert run.result["whole_product_profile"] is None
    assert run.result["evidence_state"] == "unavailable"


def test_real_timepoints_remain_descriptive_without_method_spec(
    tmp_path: Path,
) -> None:
    run = ToolRegistry.load_default().run(
        _request(tmp_path, include_series=True)
    )
    assert run.result["analysis_mode"] == "descriptive_timecourse"
    assert len(run.result["timecourse_profiles"]) == 2
    assert "inferential_timecourse_not_supplied" in run.reason_codes


def test_v1_request_is_typed_refusal(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    spec = registry.describe("P0-04")
    request = ToolRequest(
        request_id="legacy-request",
        tool_id="P0-04",
        tool_version="0.3.0",
        output_dir=tmp_path.resolve(),
    )
    eligibility = adapter.check_eligibility(request, spec)
    assert not eligibility.eligible
    assert eligibility.reason_codes == ["tool_request_v2_required"]
