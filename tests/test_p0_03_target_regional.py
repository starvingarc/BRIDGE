from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from bridge.tool_packages.p0_03_target_regional.adapter import ROLE_MODELS, adapter
from bridge.tool_packages.p0_03_target_regional.models import PUBLIC_SCHEMA_MODELS
from bridge.toolkit.contracts import (
    ExecutionState,
    ImplementationState,
    MeasurementResultV2,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
)
from bridge.toolkit.registry import ToolRegistry
from tests.p0_biological_units import bind_reviewed_biological_units


ROLE_SCHEMAS = {role: contract[0] for role, contract in ROLE_MODELS.items()}
ROLE_VERSIONS = {
    "product_case": "0.1.0",
    "product_definition_card": "0.1.0",
    "state_role_map": "0.1.0",
    "target_regional_assessment_spec": "0.1.0",
    "measurement_spec": "1.0.0",
    "cell_state_evidence_profile": "0.3.0",
    "qc_readiness_profile": "0.2.0",
    "biological_unit_manifest": "0.1.0",
    "biological_unit_assignment": "0.1.0",
    "annotation_vocabulary": "1.0.0",
    "reference_manifest": "1.0.0",
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


def _base_payloads() -> dict[str, dict]:
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
                "object_id": "measurement-spec:target-regional-demo",
                "object_version": "1.0.0",
            },
            "assay": "scRNA-seq",
            "provenance_refs": [
                {"object_id": "source:fully-synthetic", "object_version": "1"}
            ],
            "created_at": "2026-08-25T00:00:00Z",
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
        "target_regional_assessment_spec": {
            "object_version": "0.1.0",
            "assessment_spec_id": "target-regional-assessment-spec:demo",
            "assessment_spec_version": "1.0.0",
            "product_definition_ref": {
                "object_id": "product-definition:demo",
                "object_version": "1.0.0",
            },
            "status": "candidate",
            "composition_views": ["consensus_supported_only"],
            "included_label_levels": ["L1"],
            "source_ids": [],
            "target_identity_numerator_lineage_roles": ["target"],
            "regional_denominator_lineage_roles": [
                "target",
                "acceptable_adjacent",
            ],
            "regional_target_numerator_roles": ["target_region"],
            "whole_product_target_region_roles": ["target_region"],
            "unmapped_state_policy": "not_assessed",
            "ambiguous_state_policy": "not_assessed",
            "spatial_policy": "not_assessed_without_projection",
        },
        "measurement_spec": {
            "measurement_spec_id": "measurement-spec:target-regional-demo",
            "version": "1.0.0",
            "scientific_question": "Synthetic target and regional ratios",
            "assay": "scRNA-seq",
            "status": "candidate",
            "applicable_product_cards": ["product-definition:demo"],
            "input_contract": {"source": "checksummed structured objects"},
            "analysis_unit": "preparation",
            "analysis_unit_kind": "preparation",
            "independence_group_kind": "sample",
            "observation_unit_kind": "cell",
            "raw_metric_definition": {"metric_family": "three ratios"},
            "numerator": "externally configured role count",
            "denominator": "selected data view or configured target subset",
            "direction": None,
            "uncertainty_method": None,
            "minimum_data": {},
            "missing_behavior": "not_assessed",
            "tool_refs": ["P0-03"],
            "reference_refs": ["reference-snapshot:demo@1.0.0"],
            "prior_refs": ["prior:none"],
            "validation_ref": "validation:p0-03-synthetic",
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
            "module_eligibility": {"P0-03": "eligible"},
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
                    "level": "L1",
                    "parent_state_ids": [],
                    "aliases": [],
                    "status": "shadow",
                }
                for state in ("state:alpha", "state:beta", "state:gamma")
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
            "measurement_spec_ids": ["measurement-spec:target-regional-demo"],
            "profiles": [],
            "prohibited_source_families": [],
        },
    }


def _composition() -> dict:
    records = []
    for label, count in (("state:alpha", 60), ("state:beta", 20), ("state:gamma", 20)):
        records.append(
            {
                "view": "consensus_supported_only",
                "source_id": None,
                "label": label,
                "label_level": "L1",
                "state_evidence_state": "candidate",
                "denominator_scope": "selected_data_view",
                "count": count,
                "fraction": count / 100,
                "denominator": 100,
            }
        )
    records.append(
        {
            "view": "reconciliation_state",
            "source_id": None,
            "label": "consensus_supported",
            "label_level": "L1",
            "state_evidence_state": "candidate",
            "denominator_scope": "selected_data_view",
            "count": 100,
            "fraction": 1.0,
            "denominator": 100,
        }
    )
    return {"state": "shadow", "records": records}


def _prepare(payloads: dict[str, dict]) -> None:
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
    bind_reviewed_biological_units(payloads, view)
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
        "n_observations": 100,
        "n_genes": 1000,
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


def _request(
    tmp_path: Path,
    payloads: dict[str, dict] | None = None,
    *,
    output_dir: Path | None = None,
) -> ToolRequestV2:
    values = deepcopy(payloads or _base_payloads())
    _prepare(values)
    root = tmp_path / "objects"
    root.mkdir()
    refs = []
    for index, role in enumerate(ROLE_SCHEMAS, start=1):
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
        request_id="request-p0-03",
        tool_id="P0-03",
        tool_version="0.2.0",
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
        refs.append(ref.model_copy(update={"sha256": hashlib.sha256(raw).hexdigest()}))
    return request.model_copy(update={"object_inputs": refs})


def _metric(run, name: str) -> MeasurementResultV2:
    artifact = next(
        item
        for item in run.artifacts
        if item.kind == "measurement_result_v2"
        and name in item.path.name
    )
    return MeasurementResultV2.model_validate_json(
        artifact.path.read_text(encoding="utf-8")
    )


def test_p0_03_declares_the_eleven_object_v2_contract() -> None:
    spec = ToolRegistry.load_default().describe("P0-03")
    assert isinstance(spec, ToolPackageSpecV2)
    assert spec.implementation_state is ImplementationState.IMPLEMENTED
    assert len(ROLE_MODELS) == 11
    assert ROLE_SCHEMAS["cell_state_evidence_profile"].endswith("/v0.3")


@pytest.mark.parametrize("schema_ref,model", PUBLIC_SCHEMA_MODELS.items())
def test_public_models_emit_valid_draft_2020_12_schemas(
    schema_ref: str, model: type
) -> None:
    schema = model.model_json_schema()
    schema["$id"] = schema_ref
    Draft202012Validator.check_schema(schema)


def test_valid_run_publishes_only_three_normalized_ratio_types(
    tmp_path: Path,
) -> None:
    run = ToolRegistry.load_default().run(_request(tmp_path))
    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["result_state"] == "complete"
    assert run.result["domain_score"] is None
    assert run.result["score_state"] == "shadow"
    channel = run.result["channels"][0]
    assert channel["target_identity_fraction"]["fraction"] == 0.6
    assert channel["regional_fidelity_fraction"]["fraction"] == 0.75
    assert channel["whole_product_target_region_fraction"]["fraction"] == 0.6
    assert len(run.measurements) == 3
    assert len(run.artifacts) == 4
    assert {item.metric_name for item in run.measurements} == {
        "target_identity_fraction",
        "regional_fidelity_fraction",
        "whole_product_target_region_fraction",
    }
    assert set(run.result["input_sha256_by_role"]) == set(ROLE_SCHEMAS)
    for artifact in run.artifacts:
        assert hashlib.sha256(artifact.path.read_bytes()).hexdigest() == artifact.sha256


def test_identical_inputs_reuse_the_same_bundle(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)
    first = registry.run(request)
    second = registry.run(request)
    assert first.run_id == second.run_id
    assert first.result == second.result
    assert [item.sha256 for item in first.artifacts] == [
        item.sha256 for item in second.artifacts
    ]


@pytest.mark.parametrize(
    "role,expected",
    [
        ("measurement_spec", "measurement_spec_checksum_mismatch"),
        ("annotation_vocabulary", "annotation_vocabulary_checksum_mismatch"),
        ("reference_manifest", "reference_manifest_checksum_mismatch"),
        ("qc_readiness_profile", "cell_state_qc_profile_checksum_mismatch"),
    ],
)
def test_upstream_object_checksum_bindings_fail_closed(
    tmp_path: Path, role: str, expected: str
) -> None:
    request = _request(tmp_path)
    request = _mutate(
        request,
        role,
        lambda payload: payload.setdefault("warnings", []).append("changed")
        if role == "qc_readiness_profile"
        else payload.update(
            {"scientific_question": "changed"}
            if role == "measurement_spec"
            else {"product_scope": "changed"}
            if role == "annotation_vocabulary"
            else {"prohibited_source_families": ["source-family:changed"]}
        ),
    )
    result = ToolRegistry.load_default().check_eligibility(request)
    assert not result.eligible
    assert expected in result.reason_codes


@pytest.mark.parametrize(
    "case,expected",
    [
        ("product", "product_definition_binding_mismatch"),
        ("data_view", "cell_state_qc_data_view_mismatch"),
        ("assignment", "biological_unit_assignment_group_mismatch"),
    ],
)
def test_product_case_data_view_and_lineage_drift_fail_closed(
    tmp_path: Path, case: str, expected: str
) -> None:
    request = _request(tmp_path)
    if case == "product":
        request = _mutate(
            request,
            "product_case",
            lambda payload: payload["product_definition_ref"].update(
                {"object_version": "2.0.0"}
            ),
        )
    elif case == "data_view":
        request = _mutate(
            request,
            "cell_state_evidence_profile",
            lambda payload: payload["input_data_view"].update({"sha256": "f" * 64}),
        )
    else:
        request = _mutate(
            request,
            "biological_unit_assignment",
            lambda payload: payload["assignments"][0].update(
                {"independence_group_ref": "sample:other@1.0.0"}
            ),
        )
    result = ToolRegistry.load_default().check_eligibility(request)
    assert not result.eligible
    assert expected in result.reason_codes


@pytest.mark.parametrize("case", ["qc", "vocabulary", "reference"])
def test_qc_vocabulary_and_reference_applicability_are_enforced(
    tmp_path: Path, case: str
) -> None:
    request = _request(tmp_path)
    expected = {
        "qc": "qc_not_ready_for_target_regional_evidence",
        "vocabulary": "state_role_map_vocabulary_label_mismatch",
        "reference": "assessment_spec_reference_source_mismatch",
    }[case]
    if case == "qc":
        request = _mutate(
            request,
            "qc_readiness_profile",
            lambda payload: payload["module_eligibility"].update(
                {"P0-03": "not_eligible"}
            ),
        )
        request = _mutate(
            request,
            "cell_state_evidence_profile",
            lambda payload: payload.update(
                {
                    "upstream_qc_profile_sha256": next(
                        item.sha256
                        for item in request.object_inputs
                        if item.role == "qc_readiness_profile"
                    )
                }
            ),
        )
    elif case == "vocabulary":
        request = _mutate(
            request,
            "state_role_map",
            lambda payload: payload["assignments"][0].update(
                {"state_id": "state:not-in-vocabulary"}
            ),
        )
    else:
        request = _mutate(
            request,
            "target_regional_assessment_spec",
            lambda payload: payload.update(
                {"composition_views": ["source_specific"], "source_ids": ["source:missing"]}
            ),
        )
    result = ToolRegistry.load_default().check_eligibility(request)
    assert not result.eligible
    assert expected in result.reason_codes


@pytest.mark.parametrize("state", ["unknown", "ood"])
def test_unknown_and_ood_are_not_assessed_without_numbers(
    tmp_path: Path, state: str
) -> None:
    request = _request(tmp_path)

    def make_ambiguous(payload: dict) -> None:
        payload["composition"]["records"] = [
            {
                "view": "reconciliation_state",
                "source_id": None,
                "label": state,
                "label_level": "L1",
                "state_evidence_state": state,
                "denominator_scope": "selected_data_view",
                "count": 100,
                "fraction": 1.0,
                "denominator": 100,
            }
        ]

    run = ToolRegistry.load_default().run(
        _mutate(request, "cell_state_evidence_profile", make_ambiguous)
    )
    assert run.execution_state is ExecutionState.PARTIAL
    assert run.result["result_state"] == "not_assessed"
    channel = run.result["channels"][0]
    assert channel["assessment_state"] == "not_assessed"
    assert channel["target_identity_fraction"] is None
    assert channel["regional_fidelity_fraction"] is None
    assert channel["whole_product_target_region_fraction"] is None
    for artifact in [item for item in run.artifacts if item.kind == "measurement_result_v2"]:
        metric = MeasurementResultV2.model_validate_json(artifact.path.read_text())
        assert metric.evidence_state.value == "unknown"
        assert metric.raw_value is None
        assert metric.numerator is None
        assert metric.denominator is None


def test_zero_target_related_denominator_is_unavailable_not_zero(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)

    def remove_target_roles(payload: dict) -> None:
        for assignment in payload["assignments"]:
            assignment.update(
                {"lineage_role": "not_target", "regional_role": "regional_shift"}
            )

    run = ToolRegistry.load_default().run(
        _mutate(request, "state_role_map", remove_target_roles)
    )
    assert run.result["result_state"] == "partial"
    channel = run.result["channels"][0]
    assert channel["target_identity_fraction"]["fraction"] == 0.0
    assert channel["regional_fidelity_fraction"] is None
    metric = _metric(run, "regional_fidelity_fraction")
    assert metric.evidence_state.value == "unavailable"
    assert metric.raw_value is None
    assert metric.numerator is None
    assert metric.denominator is None


def test_external_spec_changes_all_three_ratio_definitions(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request = _mutate(
        request,
        "target_regional_assessment_spec",
        lambda payload: payload.update(
            {
                "target_identity_numerator_lineage_roles": ["acceptable_adjacent"],
                "regional_target_numerator_roles": ["acceptable_adjacent_region"],
                "whole_product_target_region_roles": [
                    "acceptable_adjacent_region"
                ],
            }
        ),
    )
    run = ToolRegistry.load_default().run(request)
    channel = run.result["channels"][0]
    assert channel["target_identity_fraction"]["fraction"] == 0.2
    assert channel["regional_fidelity_fraction"]["fraction"] == 0.25
    assert channel["whole_product_target_region_fraction"]["fraction"] == 0.2


def test_missing_requested_source_returns_not_assessed(tmp_path: Path) -> None:
    payloads = _base_payloads()
    payloads["target_regional_assessment_spec"].update(
        {"composition_views": ["source_specific"], "source_ids": ["source:demo"]}
    )
    payloads["reference_manifest"]["profiles"] = [
        {
            "profile_id": "reference-profile:demo",
            "source_id": "source:demo",
            "source_family_id": "source-family:demo",
            "evidence_family_id": "evidence-family:demo",
            "assay": "scRNA-seq",
            "anatomy": "synthetic",
            "developmental_time": "synthetic",
            "label_level": "L1",
            "role": "primary",
            "status": "candidate",
        }
    ]
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads))
    assert run.result["result_state"] == "not_assessed"
    assert run.result["channels"][0]["assessment_state"] == "not_assessed"
    assert all(item.raw_value is None for item in run.measurements)


def test_changed_existing_metric_bundle_is_refused(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)
    first = registry.run(request)
    metric_path = next(
        item.path for item in first.artifacts if item.kind == "measurement_result_v2"
    )
    metric_path.write_text("{}", encoding="utf-8")
    second = registry.run(request)
    assert second.execution_state is ExecutionState.FAILED
    assert second.reason_codes == ["existing_run_bundle_hash_mismatch"]


def test_v1_request_is_refused_with_a_typed_failure(tmp_path: Path) -> None:
    spec = ToolRegistry.load_default().describe("P0-03")
    request = ToolRequest(
        request_id="request-v1",
        tool_id="P0-03",
        tool_version="0.2.0",
        output_dir=tmp_path,
    )
    eligibility = adapter.check_eligibility(request, spec)
    run = adapter.run(request, spec)
    assert eligibility.reason_codes == ["tool_request_v2_required"]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["tool_request_v2_required"]


def test_implementation_contains_no_fixture_state_ids() -> None:
    root = Path(__file__).parents[1] / "src/bridge/tool_packages/p0_03_target_regional"
    source = "\n".join(path.read_text() for path in root.glob("*.py"))
    assert "state:alpha" not in source
    assert "state:beta" not in source
    assert "state:gamma" not in source
