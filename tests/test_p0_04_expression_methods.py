from __future__ import annotations

import hashlib
import json
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import pytest

from bridge.tool_packages.p0_01_input_qc.io import sha256_path
from bridge.tool_packages.p0_04_developmental_compatibility.adapter import ROLE_MODELS
from bridge.tool_packages.p0_04_developmental_compatibility.method_models import (
    DevelopmentMethodBundle,
)
from bridge.toolkit.contracts import ExecutionState, InputAsset, StructuredInputRef
from bridge.toolkit.registry import ToolRegistry
from tests.test_p0_04_developmental_compatibility import (
    _canonical_bytes,
    _mutate,
    _request,
)


def _write_reference_profile(
    root: Path,
    *,
    profile_key: str,
    source_id: str,
    assay: str,
    role: str,
    matrix: np.ndarray,
    genes: list[str],
) -> dict:
    matrix_path = root / f"development_reference_{profile_key}.npy"
    metadata_path = root / f"development_reference_{profile_key}.metadata.json"
    np.save(matrix_path, matrix, allow_pickle=False)
    labels = [
        "reference:early",
        "reference:early",
        "reference:window",
        "reference:window",
        "reference:late",
        "reference:late",
    ]
    metadata = {
        "genes": genes,
        "rows": [
            {
                "label": label,
                "n_observations": 10,
                "sample_id": f"reference-{index}",
            }
            for index, label in enumerate(labels)
        ],
    }
    metadata_path.write_bytes(_canonical_bytes(metadata))
    return {
        "profile_id": f"reference-profile:development-synthetic-{profile_key}",
        "source_id": source_id,
        "source_family_id": f"source-family:development-synthetic-{profile_key}",
        "evidence_family_id": f"evidence-family:development-synthetic-{profile_key}",
        "assay": assay,
        "anatomy": "fully-synthetic",
        "developmental_time": "externally-declared-synthetic-order",
        "label_level": "L2",
        "role": role,
        "status": "candidate",
        "n_samples": 6,
        "n_observations": 60,
        "n_genes": len(genes),
        "labels": sorted(set(labels)),
        "matrix_file": matrix_path.name,
        "matrix_sha256": sha256_path(matrix_path),
        "metadata_file": metadata_path.name,
        "metadata_sha256": sha256_path(metadata_path),
        "source_sha256": hashlib.sha256(source_id.encode()).hexdigest(),
        "feature_selection": {
            "method": "fully_synthetic_fixture",
            "query_independent": True,
            "selected_gene_count": len(genes),
        },
        "exclusions": {},
    }


def _expression_request(
    tmp_path: Path, *, second_profile_gene_count: int = 8
):
    units = [
        (
            f"preparation:unit-{index}@1.0.0",
            f"preparation:unit-{index}@1.0.0",
        )
        for index in range(8)
    ]
    request = _request(
        tmp_path,
        units=units,
        n_observations=40,
    )
    objects = request.object_inputs[0].path.parent
    assignment_ref = next(
        item
        for item in request.object_inputs
        if item.role == "biological_unit_assignment"
    )
    assignments = json.loads(
        assignment_ref.path.read_text(encoding="utf-8")
    )["assignments"]
    observation_ids = [item["observation_id"] for item in assignments]
    analysis_units = np.asarray(
        [item["analysis_unit_ref"] for item in assignments]
    )

    genes = [f"G{index}" for index in range(8)]
    early = np.asarray([8.0, 7.0, 6.0, 1.0, 0.5, 0.3, 0.2, 0.1])
    within = np.asarray([1.0, 6.0, 8.0, 7.0, 5.0, 1.0, 0.3, 0.2])
    late = np.asarray([0.2, 0.4, 1.0, 4.0, 7.0, 8.0, 6.0, 5.0])
    reference_matrix = np.vstack(
        [early, early * 0.95, within, within * 0.95, late, late * 0.95]
    )
    primary_profile = _write_reference_profile(
        objects,
        profile_key="primary",
        source_id="source:development-synthetic-primary",
        assay="scRNA-seq",
        role="primary",
        matrix=reference_matrix,
        genes=genes,
    )
    sensitivity_genes = genes[:second_profile_gene_count]
    sensitivity_profile = _write_reference_profile(
        objects,
        profile_key="sensitivity",
        source_id="source:development-synthetic-sensitivity",
        assay="snRNA-seq",
        role="sensitivity",
        matrix=reference_matrix[:, :second_profile_gene_count],
        genes=sensitivity_genes,
    )
    profiles = [primary_profile, sensitivity_profile]
    marker_payload = {
        "object_version": "0.1.0",
        "cards": [
            {
                "card_id": "program-card:development-window",
                "version": "1.0.0",
                "state_id": "state:window",
                "level": "L2",
                "positive_markers": ["G1", "G2", "G3", "G4"],
                "negative_markers": ["G6", "G7"],
                "source_ids": ["source:fully-synthetic"],
                "review_status": "candidate",
                "allowed_use": ["shadow_evidence"],
            }
        ],
    }
    marker_path = objects / "marker_programs.json"
    marker_path.write_bytes(_canonical_bytes(marker_payload))
    request = _mutate(
        request,
        "reference_manifest",
        lambda payload: payload.update(
            {
                "marker_program_file": marker_path.name,
                "marker_program_sha256": sha256_path(marker_path),
                "profiles": profiles,
            }
        ),
    )
    manifest_sha = next(
        item.sha256
        for item in request.object_inputs
        if item.role == "reference_manifest"
    )
    request = _mutate(
        request,
        "cell_state_evidence_profile",
        lambda payload: payload.update(
            {"reference_manifest_sha256": manifest_sha}
        ),
    )

    base_by_unit = {}
    for index, (unit_ref, _) in enumerate(units):
        timepoint = index // 2
        base_by_unit[unit_ref] = [
            early,
            0.55 * early + 0.45 * within,
            within,
            0.35 * within + 0.65 * late,
        ][timepoint]
    expression = np.vstack(
        [
            base_by_unit[analysis_unit] + (index % 5) * 0.005
            for index, analysis_unit in enumerate(analysis_units)
        ]
    )
    asset_path = tmp_path / "expression_view.h5ad"
    ad.AnnData(
        X=expression,
        obs=pd.DataFrame(
            {"analysis_unit_ref": analysis_units},
            index=pd.Index(observation_ids, name="observation_id"),
        ),
        var=pd.DataFrame(
            {"gene_symbol": genes},
            index=pd.Index(genes, name="feature_id"),
        ),
    ).write_h5ad(asset_path)
    profile_ref = next(
        item
        for item in request.object_inputs
        if item.role == "cell_state_evidence_profile"
    )
    cell_state_profile = json.loads(
        profile_ref.path.read_text(encoding="utf-8")
    )
    view = cell_state_profile["input_data_view"]
    asset = InputAsset(
        asset_id="asset:development-expression-view",
        path=asset_path,
        format="h5ad",
        input_level="analysis_ready",
        checksum=sha256_path(asset_path),
        matrix_location="X",
        matrix_semantics="normalized_expression",
        assay="scRNA-seq",
        metadata={
            "data_view_id": view["view_id"],
            "parent_asset_sha256": view["parent_asset_sha256"],
        },
    )
    method_spec = {
        "object_version": "0.1.0",
        "method_spec_id": "development-method-spec:fully-synthetic",
        "method_spec_version": "1.0.0",
        "status": "candidate",
        "expression_asset_id": asset.asset_id,
        "observation_id_column": None,
        "gene_symbol_column": "gene_symbol",
        "reference_profile_ids": [
            profile["profile_id"] for profile in profiles
        ],
        "reference_stages": [
            {
                "profile_id": profile["profile_id"],
                "label": label,
                "ordinal_rank": rank,
                "stage_role": role,
            }
            for profile in profiles
            for label, rank, role in (
                ("reference:early", 0, "earlier"),
                ("reference:window", 1, "within_window"),
                ("reference:late", 2, "later"),
            )
        ],
        "program_card_ids": ["program-card:development-window"],
        "analysis_unit_timepoints": [
            {
                "analysis_unit_ref": unit_ref,
                "timepoint_id": f"timepoint-{index // 2}",
                "timepoint_order": index // 2,
                "timepoint_label": f"D{10 + 10 * (index // 2)}",
            }
            for index, (unit_ref, _) in enumerate(units)
        ],
        "selected_method_ids": [
            "DEV-PSEUDOBULK-CORR",
            "DEV-ORDINAL",
            "DEV-PROGRAM",
            "DEV-BOOTSTRAP",
            "TIME-PROGRAM",
            "TIME-GAM-PY",
        ],
        "minimum_shared_genes": 4,
        "minimum_program_genes": 2,
        "bootstrap_replicates": 100,
        "bootstrap_confidence_level": 0.9,
        "spline_degrees_of_freedom": 3,
        "ordinal_group_heldout_evidence": {
            "object_version": "0.1.0",
            "evidence_id": "ordinal-group-heldout-evidence:fully-synthetic",
            "evidence_version": "1.0.0",
            "review_state": "reviewed",
            "validation_state": "passed",
            "grouping_unit": "source_id",
            "reference_profile_ids": [
                profile["profile_id"] for profile in profiles
            ],
            "held_out_source_ids": [
                profile["source_id"] for profile in profiles
            ],
        },
    }
    method_path = objects / "development_method_spec.json"
    raw = _canonical_bytes(method_spec)
    method_path.write_bytes(raw)
    method_ref = StructuredInputRef(
        input_id="input-development-methods",
        role="development_method_spec",
        schema_ref=ROLE_MODELS["development_method_spec"][0],
        object_version="0.1.0",
        path=method_path,
        sha256=hashlib.sha256(raw).hexdigest(),
        media_type="application/json",
    )
    return request.model_copy(
        update={
            "assets": [asset],
            "object_inputs": [*request.object_inputs, method_ref],
            "random_seed": 17,
        }
    )


def test_expression_mode_executes_methods_and_refuses_false_time_axis(tmp_path: Path) -> None:
    run = ToolRegistry.load_default().run(_expression_request(tmp_path))
    assert run.execution_state is ExecutionState.PARTIAL
    assert run.result["reference_stage_support"]["assessment_state"] == "shadow"
    artifact = next(
        item for item in run.artifacts if item.kind == "development_method_bundle"
    )
    bundle = DevelopmentMethodBundle.model_validate_json(
        artifact.path.read_text(encoding="utf-8")
    )
    assert {item.method_id.value for item in bundle.method_evidence} == {
        "DEV-PSEUDOBULK-CORR",
        "DEV-ORDINAL",
        "DEV-PROGRAM",
        "DEV-BOOTSTRAP",
        "TIME-PROGRAM",
        "TIME-GAM-PY",
    }
    states = {item.method_id.value: item for item in bundle.method_evidence}
    assert {states[method_id].execution_state.value for method_id in {
        "DEV-PSEUDOBULK-CORR", "DEV-ORDINAL", "DEV-PROGRAM", "DEV-BOOTSTRAP"
    }} == {"succeeded"}
    for method_id in {"TIME-PROGRAM", "TIME-GAM-PY"}:
        assert states[method_id].execution_state.value == "not_assessed"
        assert states[method_id].reason_codes == [
            "numeric_experimental_time_contract_unavailable"
        ]
    assert len(bundle.analysis_unit_refs) == 8
    assert len(bundle.independence_group_refs) == 8
    assert bundle.reference_stage_support
    assert bundle.ordinal_stage_predictions
    assert {
        item.calibration_state for item in bundle.ordinal_stage_predictions
    } == {"uncalibrated_baseline"}
    assert {
        item.group_heldout_evidence_ref.object_id
        for item in bundle.ordinal_stage_predictions
    } == {"ordinal-group-heldout-evidence:fully-synthetic"}
    assert bundle.program_activity
    assert bundle.bootstrap_intervals[0].interval_state == "available"
    assert bundle.time_trends == []
    assert "inferential_timecourse_unavailable" in run.reason_codes
    assert "numeric_experimental_time_contract_unavailable" in run.reason_codes
    assert bundle.domain_score is None
    assert bundle.score_state.value == "shadow"


@pytest.mark.parametrize("remove_asset", [True, False])
def test_expression_mode_requires_method_spec_and_asset(
    tmp_path: Path, remove_asset: bool
) -> None:
    request = _expression_request(tmp_path)
    if remove_asset:
        request = request.model_copy(update={"assets": []})
    else:
        request = request.model_copy(
            update={
                "object_inputs": [
                    item
                    for item in request.object_inputs
                    if item.role != "development_method_spec"
                ]
            }
        )
    eligibility = ToolRegistry.load_default().check_eligibility(request)
    assert not eligibility.eligible
    assert "expression_method_inputs_incomplete" in eligibility.reason_codes


def test_expression_asset_replacement_fails_closed(tmp_path: Path) -> None:
    request = _expression_request(tmp_path)
    with request.assets[0].path.open("ab") as handle:
        handle.write(b"changed")
    run = ToolRegistry.load_default().run(request)
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["expression_asset_checksum_mismatch"]


def test_reference_stage_roles_are_external_configuration(
    tmp_path: Path,
) -> None:
    request = _expression_request(tmp_path)
    first = ToolRegistry.load_default().run(request)
    first_bundle = DevelopmentMethodBundle.model_validate_json(
        next(
            item.path
            for item in first.artifacts
            if item.kind == "development_method_bundle"
        ).read_text(encoding="utf-8")
    )
    changed_root = tmp_path / "changed"
    changed_request = _expression_request(changed_root)
    changed_request = _mutate(
        changed_request,
        "development_method_spec",
        lambda payload: [
            item.update(stage_role="branch_shift")
            for item in payload["reference_stages"]
            if item["label"] == "reference:window"
        ],
    )
    second = ToolRegistry.load_default().run(changed_request)
    second_bundle = DevelopmentMethodBundle.model_validate_json(
        next(
            item.path
            for item in second.artifacts
            if item.kind == "development_method_bundle"
        ).read_text(encoding="utf-8")
    )
    first_roles = {
        item.top_stage_role for item in first_bundle.reference_stage_support
    }
    second_roles = {
        item.top_stage_role for item in second_bundle.reference_stage_support
    }
    assert first_roles != second_roles


def test_ordinal_requires_external_group_heldout_evidence(
    tmp_path: Path,
) -> None:
    request = _expression_request(tmp_path)
    request = _mutate(
        request,
        "development_method_spec",
        lambda payload: payload.pop("ordinal_group_heldout_evidence"),
    )
    run = ToolRegistry.load_default().run(request)
    bundle = DevelopmentMethodBundle.model_validate_json(
        next(
            item.path
            for item in run.artifacts
            if item.kind == "development_method_bundle"
        ).read_text(encoding="utf-8")
    )
    ordinal = next(
        item
        for item in bundle.method_evidence
        if item.method_id.value == "DEV-ORDINAL"
    )
    assert ordinal.execution_state.value == "not_assessed"
    assert ordinal.reason_codes == [
        "ordinal_group_heldout_evidence_not_supplied"
    ]
    assert bundle.ordinal_stage_predictions == []


def test_low_reference_profile_coverage_makes_support_unavailable(
    tmp_path: Path,
) -> None:
    run = ToolRegistry.load_default().run(
        _expression_request(tmp_path, second_profile_gene_count=3)
    )
    assert (
        run.result["reference_stage_support"]["assessment_state"]
        == "unavailable"
    )
    bundle_artifact = next(
        item for item in run.artifacts if item.kind == "development_method_bundle"
    )
    bundle = DevelopmentMethodBundle.model_validate_json(
        bundle_artifact.path.read_text(encoding="utf-8")
    )
    assert bundle.reference_stage_support
    assert {
        item.evidence_state for item in bundle.reference_stage_support
    } == {"unavailable"}
    assert all(
        "reference_stage_profile_coverage_incomplete" in item.reason_codes
        for item in bundle.reference_stage_support
    )
    visualization_artifact = next(
        item
        for item in run.artifacts
        if item.kind == "developmental_compatibility_visualization_data"
    )
    visualization = json.loads(
        visualization_artifact.path.read_text(encoding="utf-8")
    )
    assert visualization["method_bundle_ref"]["object_id"] == bundle.bundle_id
    assert visualization["method_bundle_sha256"] == bundle_artifact.sha256
    assert visualization["reference_records"]


def test_cross_source_assay_stage_disagreement_makes_support_unavailable(
    tmp_path: Path,
) -> None:
    request = _expression_request(tmp_path)

    def configure_disagreement(payload: dict) -> None:
        payload["selected_method_ids"] = ["DEV-PSEUDOBULK-CORR"]
        replacement = {
            "earlier": "later",
            "within_window": "branch_shift",
            "later": "earlier",
        }
        for item in payload["reference_stages"]:
            if item["profile_id"].endswith("-sensitivity"):
                item["stage_role"] = replacement[item["stage_role"]]

    request = _mutate(
        request,
        "development_method_spec",
        configure_disagreement,
    )
    run = ToolRegistry.load_default().run(request)
    assert (
        run.result["reference_stage_support"]["assessment_state"]
        == "unavailable"
    )
    bundle = DevelopmentMethodBundle.model_validate_json(
        next(
            item.path
            for item in run.artifacts
            if item.kind == "development_method_bundle"
        ).read_text(encoding="utf-8")
    )
    assert {
        item.evidence_state for item in bundle.reference_stage_support
    } == {"unavailable"}
    assert all(
        item.reason_codes
        == ["reference_stage_source_assay_disagreement"]
        for item in bundle.reference_stage_support
    )
