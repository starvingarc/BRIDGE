from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bridge.tool_packages.p0_02_cell_state.celltypist_runtime import (
    FittedCellTypist, calibrate_rejection, predict_celltypist, save_model_bundle,
)
from bridge.tool_packages.p0_02_cell_state.metrics import normalize_query
from bridge.toolkit.contracts import ExecutionState
from bridge.toolkit.registry import ToolRegistry
from test_cell_state import _build_snapshot, _configure_qc_catalog, _request, _write_query


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path, value):
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _rig(tmp_path, monkeypatch):
    import anndata as ad
    _build_snapshot(tmp_path, monkeypatch)
    query = _write_query(tmp_path / "query.h5ad")
    _configure_qc_catalog(tmp_path, monkeypatch, query)
    trained = FittedCellTypist(
        features=("TH", "DDC"), classes=("L1:Neuron_DA", "L1:Neuron_GABA"),
        coefficients=np.array([[1., -1.]]), intercepts=np.array([1.]),
        means=np.zeros(2), scales=np.ones(2), with_mean=True,
        geometry_mean=np.zeros(2), geometry_components=np.eye(2),
        geometry_points=np.array([[1., 1.], [2., 2.]]),
        training_provenance={
            "source_family_ids": ["FIXTURE-TRAIN"], "development_design_sha256": "a" * 64,
            "fold_id": "fold-01", "training_observations_sha256": "b" * 64,
        },
    )
    data = ad.read_h5ad(query)
    prediction = predict_celltypist(trained, normalize_query(data.X, "raw_counts"), data.var_names)
    calibration = calibrate_rejection(
        prediction, prediction.predicted_labels, ["cal-1", "cal-2", "cal-3", "cal-4"],
        min_class_support=1,
    )
    bundle = tmp_path / "model"
    manifest_sha = save_model_bundle(bundle, trained, calibration)
    receipt = tmp_path / "verified-development.json"
    _json(receipt, {
        "object_version": "1.0.0", "summary_sha256": "c" * 64,
        "development_design_sha256": "a" * 64,
        "metric_verification": "recomputed_from_checksums_bound_predictions",
        "primary_fold": "fold-01",
        "models": {"fold-01": {
            "model_sha256": trained.fingerprint, "model_manifest_sha256": manifest_sha,
        }},
        "scientific_decision": {
            "development_gate_state": "failed", "reason_codes": ["fixture_ood_failed"],
            "scientific_qualification": "not_established", "qualified_state_ids": [],
            "locked_test_state": "not_run_development_failed",
        },
    })
    catalog = tmp_path / "candidate-catalog.json"
    binding = {
        "object_version": "1.0.0", "runtime_id": "fixture-celltypist-v1",
        "measurement_spec_ref": "CELLSTATE-scRNA-celltypist-candidate-v0.1",
        "model_bundle_path": str(bundle), "model_manifest_sha256": manifest_sha,
        "verification_path": str(receipt), "verification_sha256": _sha(receipt),
        "development_review_version": "1.1.0",
        "source_family_ids": ["FIXTURE-TRAIN"],
    }
    _json(catalog, {"fixture-celltypist-v1": binding})
    monkeypatch.setenv("BRIDGE_CELLSTATE_CANDIDATE_CATALOG", str(catalog))
    original = _request(tmp_path, query)
    request = original.model_copy(update={
        "measurement_spec_ref": binding["measurement_spec_ref"],
        "parameters": {**original.parameters, "candidate_runtime_ref": binding["runtime_id"]},
    })
    return request, catalog, receipt


def test_registered_candidate_runs_without_rewriting_auxiliary_reference_manifest(tmp_path, monkeypatch):
    request, _, _ = _rig(tmp_path, monkeypatch)
    registry = ToolRegistry.load_default()
    eligibility = registry.check_eligibility(request)
    assert eligibility.eligible, eligibility.reason_codes
    run = registry.run(request)
    assert run.execution_state is ExecutionState.SUCCEEDED, run.warnings
    result = run.result
    assert result["primary_method"] == "CellTypist"
    assert result["primary_ood"] == "energy"
    assert result["knn_role"] == "sensitivity_not_independent_vote"
    assert result["scientific_qualification"] == "not_established"
    assert result["development_gate_state"] == "failed"
    assert result["qualified_state_ids"] == []
    assert set(result["per_state_release"].values()) == {"unavailable"}
    assert result["target_fraction"] is None and result["domain_score"] is None
    assert result["n_observations"] == 4
    assert sum(row["count"] for row in result["candidate_composition"]) == 4
    assert result["biological_unit_state"] == "not_estimable"
    assert result["input_data_view"]["n_observations"] == 4
    assert result["auxiliary_run_ref"] != run.run_id
    assert "not_independent_of_primary_RNA" in result["limitations"]
    predictions = next(a for a in run.artifacts if a.kind == "celltypist_candidate_assignments")
    table = pd.read_parquet(predictions.path)
    assert len(table) == 4
    assert table["qualified_assignment"].eq(False).all()
    programs = next(a for a in run.artifacts if a.kind == "reviewed_marker_programs")
    cards = json.loads(programs.path.read_text())
    omtn = next(x for x in cards if x["state_id"] == "L1:Neuron_OMTN")
    assert "MNX1" not in omtn["positive_genes"]
    assert "MNX1" in omtn["counter_genes"]
    # Replaying an identical request must not rewrite or relabel history.
    before = {a.path: _sha(a.path) for a in run.artifacts}
    replay = registry.run(request)
    assert replay.run_id == run.run_id
    assert before == {a.path: _sha(a.path) for a in replay.artifacts}


def test_training_family_cannot_be_presented_as_independent_candidate_query(tmp_path, monkeypatch):
    request, _, _ = _rig(tmp_path, monkeypatch)
    asset = request.assets[0].model_copy(update={
        "metadata": {**request.assets[0].metadata, "source_family_id": "FIXTURE-TRAIN"},
    })
    request = request.model_copy(update={"assets": [asset]})
    check = ToolRegistry.load_default().check_eligibility(request)
    assert not check.eligible
    assert "candidate_query_source_overlap" in check.reason_codes


def test_candidate_requires_controlled_catalog_and_hash_bound_validation(tmp_path, monkeypatch):
    request, _, receipt = _rig(tmp_path, monkeypatch)
    receipt.write_text("{}", encoding="utf-8")
    check = ToolRegistry.load_default().check_eligibility(request)
    assert not check.eligible
    assert "candidate_verification_checksum_mismatch" in check.reason_codes
    monkeypatch.delenv("BRIDGE_CELLSTATE_CANDIDATE_CATALOG")
    check = ToolRegistry.load_default().check_eligibility(request)
    assert not check.eligible
    assert "candidate_runtime_catalog_required" in check.reason_codes


def test_candidate_cannot_select_best_fold_or_promote_failed_development(tmp_path, monkeypatch):
    request, catalog, receipt = _rig(tmp_path, monkeypatch)
    payload = json.loads(receipt.read_text())
    payload["primary_fold"] = "fold-02"
    _json(receipt, payload)
    bindings = json.loads(catalog.read_text())
    bindings["fixture-celltypist-v1"]["verification_sha256"] = _sha(receipt)
    _json(catalog, bindings)
    check = ToolRegistry.load_default().check_eligibility(request)
    assert not check.eligible
    assert "candidate_primary_model_binding_mismatch" in check.reason_codes


def test_reviewed_program_missing_gene_is_not_zero_and_never_becomes_identity():
    module = importlib.import_module("bridge.tool_packages.p0_02_cell_state.candidate_runtime")
    from scipy import sparse
    rows = module.reviewed_marker_evidence(sparse.csr_matrix([[1.], [0.]]), ["TH"])
    da = next(x for x in rows if x["state_id"] == "L1:Neuron_DA")
    assert da["gene_detection"]["TH"] == {"state": "measured", "count": 1, "denominator": 2}
    assert da["gene_detection"]["DDC"] == {"state": "missing", "count": None, "denominator": None}
    assert da["identity_state"] == "not_assessed"
    assert da["n_observations"] == 2
