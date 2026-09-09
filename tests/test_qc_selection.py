from __future__ import annotations

import json
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import pytest
from scipy import sparse

from bridge.tool_packages._configurable_contracts import observation_ids_sha256
from bridge.tool_packages.p0_01_input_qc import metrics as qc_metrics
from bridge.tool_packages.p0_01_input_qc.io import sha256_path
from bridge.toolkit.contracts import ExecutionState, InputAsset, ToolRequest
from bridge.toolkit.registry import ToolRegistry
from test_cell_state import GENES, _build_snapshot
from test_web_service import client


class _ControlledScrublet:
    """Replace only the external stochastic caller, not the QC/handoff code."""

    missing_calls = False

    def __init__(self, matrix, random_state):
        self.n = matrix.shape[0]
        self.threshold_ = 0.5
        self.doublet_scores_sim_ = np.array([0.1, 0.2, 0.8, 0.9])

    def scrub_doublets(self, **kwargs):
        scores = np.full(self.n, 0.1)
        scores[0] = 0.8
        calls = scores > 0.5
        return scores, None if self.missing_calls else calls


def _request(tmp_path: Path, monkeypatch, *, lineage: bool = False):
    import scrublet

    monkeypatch.setattr(scrublet, "Scrublet", _ControlledScrublet)
    genes = GENES + ["MT-ND1"] + [f"EXTRA-{i}" for i in range(119)]
    counts = np.ones((256, len(genes)), dtype=np.int64)
    counts[:, 0] = 2 + np.arange(256) % 3
    counts[[127, 255], :] = 0
    counts[[127, 255], 0] = 1
    captures = ["capture-a"] * 128 + ["capture-b"] * 128
    obs = pd.DataFrame(
        {
            "capture_id": captures,
            "sample_id": ["sample-a"] * 256,
            "capture_ref": [f"capture:{value}@1.0.0" for value in captures],
            "preparation_ref": ["preparation:product-a@1.0.0"] * 256,
            "donor_ref": ["donor:donor-a@1.0.0"] * 256,
        },
        index=[f"cell-{i:03d}" for i in range(256)],
    )
    path = tmp_path / "parent.h5ad"
    ad.AnnData(sparse.csr_matrix(counts), obs=obs, var=pd.DataFrame(index=genes)).write_h5ad(path)
    metadata = {"capture_id_column": "capture_id", "sample_id_column": "sample_id"}
    if lineage:
        metadata["biological_unit_lineage"] = {
            "source_unit_kind": "preparation",
            "source_unit_ref": {"object_id": "preparation:product-a", "object_version": "1.0.0"},
            "unit_identity_namespace_ref": {"object_id": "unit-namespace:test", "object_version": "1.0.0"},
            "analysis_unit_kind": "preparation",
            "independence_group_kind": "donor",
            "independence_scope_ref": {"object_id": "independence-scope:test", "object_version": "1.0.0"},
            "observation_ref_columns": {
                "capture": "capture_ref", "preparation": "preparation_ref", "donor": "donor_ref"
            },
        }
    return ToolRequest(
        request_id="selected-qc-test", tool_id="P0-01", output_dir=tmp_path / "qc-results",
        measurement_spec_ref="QC-scRNA-candidate-v0.1",
        parameters={"run_scrublet": True, "select_qc_eligible_cells": True},
        assets=[InputAsset(
            asset_id="parent", path=path, format="h5ad", input_level="count_ready",
            checksum=sha256_path(path), matrix_location="X", matrix_semantics="raw_counts",
            assay="scRNA-seq", metadata=metadata,
        )],
    )


def _artifact(run, kind):
    return next(item for item in run.artifacts if item.kind == kind)


@pytest.mark.parametrize("lineage", [False, True])
def test_registered_qc_selects_exact_cells_and_preserves_parent(tmp_path, monkeypatch, lineage):
    request = _request(tmp_path, monkeypatch, lineage=lineage)
    original = request.assets[0].path.read_bytes()
    run = ToolRegistry.load_default().run(request)
    assert run.execution_state is ExecutionState.SUCCEEDED, run.reason_codes
    selected = [item for item in run.artifacts if item.kind == "qc_selected_h5ad"]
    assert len(selected) == 1, "QC must materialize its selected raw-count input for downstream tools"
    selected = selected[0]
    expected_ids = [f"cell-{i:03d}" for i in range(256) if i not in (0, 127, 128, 255)]
    filtered = ad.read_h5ad(selected.path)
    assert filtered.obs_names.tolist() == expected_ids
    assert filtered.shape == (252, 240)
    annotated = ad.read_h5ad(_artifact(run, "derived_h5ad").path)
    assert annotated.shape == (256, 240)
    assert annotated.obs["passes_QC"].sum() == 252
    assert annotated.obs["bridge_qc_scrublet_class"].value_counts().to_dict() == {"singlet": 254, "doublet": 2}
    parent = ad.read_h5ad(request.assets[0].path)
    assert (annotated.X != parent.X).nnz == 0
    assert (filtered.X != parent[expected_ids].X).nnz == 0
    assert request.assets[0].path.read_bytes() == original
    assert sha256_path(selected.path) == selected.sha256
    profile = json.loads(_artifact(run, "qc_profile_v2").path.read_text())
    view = profile["selected_data_view"]
    assert view["view_kind"] == "qc_selected_observations"
    assert view["artifact_id"] == selected.artifact_id
    assert view["sha256"] == selected.sha256
    assert view["parent_asset_id"] == "parent"
    assert view["parent_asset_sha256"] == request.assets[0].checksum
    assert view["n_observations"] == 252
    assert view["observation_ids_sha256"] == observation_ids_sha256(expected_ids)
    assert view["selection_spec_ref"] == "QC-scRNA-candidate-v0.1"
    assert profile["schema_integrity"]["n_observations"] == 256
    assert profile["data_views"]["eligible_cells_view"]["n_observations"] == 252
    assert run.result["domain_score"] is None
    if lineage:
        assignment = json.loads(_artifact(run, "biological_unit_assignment").path.read_text())
        manifest = json.loads(_artifact(run, "biological_unit_manifest").path.read_text())
        assert [row["observation_id"] for row in assignment["assignments"]] == expected_ids
        assert manifest["n_observations"] == 252
        assert manifest["selected_artifact_sha256"] == selected.sha256


def test_missing_scrublet_class_cannot_publish_completed_qc_selection(tmp_path, monkeypatch):
    request = _request(tmp_path, monkeypatch)
    monkeypatch.setattr(_ControlledScrublet, "missing_calls", True)
    run = ToolRegistry.load_default().run(request)
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["qc_selection_doublets_unavailable"]
    assert not request.output_dir.exists()


def test_qc_selection_without_rules_cannot_silently_become_audit_only(tmp_path, monkeypatch):
    request = _request(tmp_path, monkeypatch).model_copy(update={"measurement_spec_ref": None})
    run = ToolRegistry.load_default().run(request)
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["qc_selection_requires_measurement_spec"]
    assert not request.output_dir.exists()


def test_web_selected_handoff_materializes_filtered_input_and_rejects_tampering(
        client, tmp_path, monkeypatch):
    from bridge.domain.models import CaseInputAsset, CaseInputBundle
    from test_web_service import new_session, confirm_change, declare_source
    from test_web_inputs import approve, choice

    request = _request(tmp_path, monkeypatch)
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    aid = client.post(url + "/uploads", files={"file": (
        "synthetic.h5ad", request.assets[0].path.read_bytes()
    )}).json()["uploads"][0]["id"]
    proposed = client.post(url + "/analysis-inputs/assets", json={
        "upload_id": aid, "assay": "scRNA-seq", "matrix_location": "X",
        "matrix_semantics": "raw_counts", "input_level": "count_ready",
        "metadata": request.assets[0].metadata,
    })
    assert proposed.status_code == 200, proposed.json()
    confirm_change(client, sid, proposed.json())
    declare_source(client, sid, aid, "source-family:selected-qc")
    service = client.app.state.service
    state = service.load(sid)
    original_declarations = json.loads(json.dumps(state["_asset_declarations"]))
    asset = CaseInputAsset.model_validate(state["_asset_declarations"][aid])
    bundle = CaseInputBundle(bundle_id="selected-qc-web", version="1", assets=[asset])
    request = request.model_copy(update={
        "assets": [asset.to_toolkit_asset()],
        "output_dir": service.directory(sid) / "runs",
    })
    service.propose_request(state, bundle, request, "Explicit candidate QC selection")
    assert approve(client, sid, state["plan"])["plan"]["status"] == "completed"
    state = service.load(sid)
    selected = service.effective_qc_asset(state, aid, register=False)
    assert selected.asset_id != aid, "Web handoff must replace the parent matrix, not just its metadata"
    assert selected.path.name == "qc_selected_view.h5ad"
    assert ad.read_h5ad(selected.path).n_obs == 252
    assert selected.checksum == sha256_path(selected.path)
    assert selected.metadata["parent_asset_sha256"] == asset.checksum
    assert state["_asset_declarations"] == original_declarations
    _build_snapshot(tmp_path, monkeypatch)
    from dataclasses import replace
    service.settings = replace(service.settings,
        cell_state_measurement_spec_ref="CELLSTATE-scRNA-shadow-v0.1")
    selection = {**choice("P0-02", None, assets=[aid]),
                 "measurement_spec_ref": "CELLSTATE-scRNA-shadow-v0.1"}
    assert client.post(url + "/analysis-inputs", json=selection).status_code == 200
    prepared = client.post(url + "/prepare-analysis", json={"tool_id": "P0-02"})
    assert prepared.json()["plan"]["status"] == "proposed"
    planned = json.loads(service.load(sid)["_plan"]["steps"][0]["approved_request_json"])
    assert planned["assets"][0]["path"] == str(selected.path)
    assert planned["assets"][0]["checksum"] == selected.checksum
    selected.path.write_bytes(selected.path.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="qc_artifact_integrity_mismatch"):
        service.effective_qc_asset(service.load(sid), aid, register=False)


def test_robust_rules_use_each_capture_and_keep_exact_boundary_cells():
    frame = pd.DataFrame({
        "total_counts": [1, 3, 7, 15, 31, 127, 255, 511, 1023, 2047],
        "detected_genes": [1, 3, 7, 15, 31, 127, 255, 511, 1023, 2047],
        "mitochondrial_fraction": [.01, .02, .03, .04, .09, .11, .12, .13, .14, .19],
    }, index=[f"row-{i}" for i in range(10)])
    captures = pd.Series(["a"] * 5 + ["b"] * 5, index=frame.index)
    rule = getattr(qc_metrics, "apply_robust_candidate_rules", None)
    assert callable(rule), "Versioned robust QC rules must execute in the existing deterministic package"
    flags, thresholds = rule(frame, captures, {"lower_log_mads": 1, "upper_mito_mads": 1})
    assert flags["bridge_qc_candidate_eligible"].tolist() == [False, True, True, True, False] * 2
    assert thresholds[0]["capture_id"] == "a"
    assert thresholds[0]["min_total_counts"] == 3
    assert thresholds[0]["min_detected_genes"] == 3
    assert thresholds[0]["max_mitochondrial_fraction"] == pytest.approx(.04)
    assert thresholds[1]["capture_id"] == "b"
    assert thresholds[1]["min_total_counts"] == 255
    assert thresholds[1]["max_mitochondrial_fraction"] == pytest.approx(.14)


@pytest.mark.parametrize("lineage", [False, True])
def test_cell_state_consumes_only_exact_qc_selected_view(tmp_path, monkeypatch, lineage):
    request = _request(tmp_path, monkeypatch, lineage=lineage)
    qc = ToolRegistry.load_default().run(request)
    selected = [item for item in qc.artifacts if item.kind == "qc_selected_h5ad"]
    assert len(selected) == 1, "The registered QC producer must supply the actual downstream view"
    selected = selected[0]
    profile = _artifact(qc, "qc_profile")
    index = _artifact(qc, "bridge://schemas/p0-01-structured-output-index/v0.1")
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"profiles": {qc.result["profile_id"]: {
        "path": str(profile.path), "sha256": profile.sha256,
        "structured_output_index_path": str(index.path),
        "structured_output_index_sha256": index.sha256,
    }}}))
    monkeypatch.setenv("BRIDGE_QC_PROFILE_CATALOG", str(catalog))
    _build_snapshot(tmp_path, monkeypatch)
    state_request = ToolRequest(
        request_id="selected-state-test", tool_id="P0-02", output_dir=tmp_path / "state-results",
        measurement_spec_ref="CELLSTATE-scRNA-shadow-v0.1",
        assets=[InputAsset(
            asset_id=selected.artifact_id, path=selected.path, checksum=selected.sha256,
            format="h5ad", input_level="count_ready", assay="scRNA-seq",
            matrix_location="X", matrix_semantics="raw_counts",
            metadata={"qc_profile_ref": qc.result["profile_id"], "source_family_id": "QUERY-INDEPENDENT"},
        )],
    )
    run = ToolRegistry.load_default().run(state_request)
    assert run.execution_state is ExecutionState.SUCCEEDED, run.reason_codes
    assert run.result["n_observations"] == 252
    evidence = pd.read_parquet(_artifact(run, "cell_state_evidence").path)
    expected = {f"cell-{i:03d}" for i in range(256) if i not in (0, 127, 128, 255)}
    assert set(evidence.observation_id) == expected
    assert run.result["domain_score"] is None
    wrong_asset = request.assets[0].model_copy(update={"metadata": state_request.assets[0].metadata})
    rejected = ToolRegistry.load_default().run(state_request.model_copy(
        update={"request_id": "reject-parent", "assets": [wrong_asset]}
    ))
    assert rejected.execution_state is ExecutionState.FAILED
    assert "qc_profile_binding_mismatch" in rejected.reason_codes

def test_robust_registered_selection_records_thresholds_and_review_plots(tmp_path, monkeypatch):
    request = _request(tmp_path, monkeypatch)
    matrix = ad.read_h5ad(request.assets[0].path)
    rng = np.random.default_rng(81)
    means = np.linspace(.1, 2.0, 256)
    counts = rng.poisson(means[:, None], (256, 240))
    counts[:, 120] = 2 + np.arange(256) % 9
    counts[[127, 255], :] = 0
    counts[[127, 255], 0] = 1
    matrix.X = sparse.csr_matrix(counts)
    matrix.write_h5ad(request.assets[0].path)
    request = request.model_copy(update={
        "measurement_spec_ref": "QC-scRNA-robust-candidate-v0.1",
        "assets": [request.assets[0].model_copy(update={"checksum": sha256_path(request.assets[0].path)})],
    })
    run = ToolRegistry.load_default().run(request)
    assert run.execution_state is ExecutionState.SUCCEEDED, run.reason_codes
    threshold_data = json.loads(_artifact(run, "qc_selection_thresholds").path.read_text())
    assert threshold_data["measurement_spec_ref"] == "QC-scRNA-robust-candidate-v0.1"
    assert [row["capture_id"] for row in threshold_data["thresholds_by_capture"]] == ["capture-a", "capture-b"]
    assert threshold_data["n_input"] == 256
    assert 0 < threshold_data["n_selected"] < 256
    plots = [item for item in run.artifacts if item.kind == "qc_selection_review_png"]
    assert len(plots) == 2
    for plot in plots:
        assert plot.path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        assert sha256_path(plot.path) == plot.sha256
    svgs = [item for item in run.artifacts if item.kind == "qc_selection_review_svg"]
    for svg, rule in zip(svgs, threshold_data["thresholds_by_capture"], strict=True):
        assert f"Applied: {rule['max_mitochondrial_fraction'] * 100:.4g}%" in svg.path.read_text()
    metrics = pd.read_parquet(_artifact(run, "qc_metrics").path)
    annotated = ad.read_h5ad(_artifact(run, "derived_h5ad").path)
    assert annotated.obs.loc[["cell-000", "cell-127", "cell-128", "cell-255"], "passes_QC"].tolist() == [False] * 4
    assert set(metrics.scrublet_class) == {"singlet", "doublet"}
    assert run.result["ambient_assessment"]["state"] == "not_assessed"

@pytest.mark.parametrize("parameter", ["select_qc_eligible_cells", "run_scrublet"])
def test_qc_action_parameters_reject_text_instead_of_coercing_it(tmp_path, monkeypatch, parameter):
    request = _request(tmp_path, monkeypatch)
    request = request.model_copy(update={"parameters": {**request.parameters, parameter: "false"}})
    result = ToolRegistry.load_default().check_eligibility(request)
    assert not result.eligible
    assert result.reason_codes == ["invalid_qc_boolean_parameter"]


def test_zero_count_barcode_is_excluded_without_a_fake_singlet_call(tmp_path, monkeypatch):
    request = _request(tmp_path, monkeypatch)
    matrix = ad.read_h5ad(request.assets[0].path)
    counts = matrix.X.toarray()
    counts[127] = 0
    matrix.X = sparse.csr_matrix(counts)
    matrix.write_h5ad(request.assets[0].path)
    request = request.model_copy(update={
        "assets": [request.assets[0].model_copy(update={"checksum": sha256_path(request.assets[0].path)})],
    })
    run = ToolRegistry.load_default().run(request)
    assert run.execution_state is ExecutionState.SUCCEEDED, run.reason_codes
    metrics = pd.read_parquet(_artifact(run, "qc_metrics").path)
    assert metrics.loc["cell-127", "scrublet_class"] == "not_assessed_empty_counts"
    assert pd.isna(metrics.loc["cell-127", "scrublet_score"])
    assert pd.isna(metrics.loc["cell-127", "mitochondrial_fraction"])
    assert run.result["doublet_assessment"]["n_assessed"] == 255
    selected = ad.read_h5ad(_artifact(run, "qc_selected_h5ad").path)
    assert "cell-127" not in selected.obs_names


def test_robust_rules_exclude_empty_counts_without_imputing_their_fraction():
    frame = pd.DataFrame({
        "total_counts": [0, 1, 3, 7, 15, 31],
        "detected_genes": [0, 1, 3, 7, 15, 31],
        "mitochondrial_fraction": [np.nan, .01, .02, .03, .04, .09],
    })
    groups = pd.Series(["a"] * 6)
    flags, thresholds = qc_metrics.apply_robust_candidate_rules(
        frame, groups, {"lower_log_mads": 1, "upper_mito_mads": 1}
    )
    assert flags["bridge_qc_candidate_eligible"].tolist() == [False, False, True, True, True, False]
    assert thresholds[0]["min_total_counts"] == 3
    assert thresholds[0]["max_mitochondrial_fraction"] == pytest.approx(.04)
    assert pd.isna(frame.loc[0, "mitochondrial_fraction"])
