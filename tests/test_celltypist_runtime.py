from __future__ import annotations

import importlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import sparse
from scipy.special import expit


def runtime():
    return importlib.import_module("bridge.tool_packages.p0_02_cell_state.celltypist_runtime")


def model():
    return runtime().FittedCellTypist(
        features=("A", "B"),
        classes=("L1:Neuron_DA", "L1:Neuron_GABA"),
        coefficients=np.array([[2.0, -1.0]]),
        intercepts=np.array([0.25]),
        means=np.array([1.0, 2.0]),
        scales=np.array([2.0, 1.0]),
        with_mean=True,
        geometry_mean=np.array([0.0, 0.0]),
        geometry_components=np.eye(2),
        geometry_points=np.array([[0.0, 0.0], [1.0, -1.0]]),
        training_provenance={"source_family_ids": ["fixture-train"], "seed": 11},
    )


def test_raw_decisions_binary_expansion_and_energy_match_hand_calculation():
    prediction = runtime().predict_celltypist(
        model(), sparse.csr_matrix([[3.0, 1.0], [1.0, 2.0]]), ["A", "B"],
    )
    np.testing.assert_allclose(prediction.decision_scores, [[-3.25, 3.25], [-0.25, 0.25]])
    np.testing.assert_allclose(prediction.probabilities, expit([[-3.25, 3.25], [-0.25, 0.25]]))
    np.testing.assert_allclose(prediction.energy, [-3.25150231016, -0.72407698418], rtol=1e-9)
    assert prediction.predicted_labels.tolist() == ["L1:Neuron_GABA", "L1:Neuron_GABA"]


def test_feature_order_does_not_change_prediction_and_missing_is_not_measured_zero():
    full = runtime().predict_celltypist(model(), sparse.csr_matrix([[3.0, 0.0]]), ["A", "B"])
    reordered = runtime().predict_celltypist(model(), sparse.csr_matrix([[0.0, 3.0]]), ["B", "A"])
    missing = runtime().predict_celltypist(model(), sparse.csr_matrix([[3.0]]), ["A"])
    np.testing.assert_allclose(full.decision_scores, reordered.decision_scores)
    np.testing.assert_allclose(full.decision_scores, [[-4.25, 4.25]])
    np.testing.assert_allclose(missing.decision_scores, [[-2.25, 2.25]])
    assert missing.feature_coverage == 0.5
    assert missing.missing_features == ("B",)
    assert full.missing_features == ()


def test_large_logits_are_finite_and_zero_feature_overlap_is_unavailable():
    prediction = runtime().predict_celltypist(model(), sparse.csr_matrix([[1e6, 0.0]]), ["A", "B"])
    assert np.isfinite(prediction.energy).all()
    np.testing.assert_allclose(prediction.decision_scores, [[-22.25, 22.25]])
    with pytest.raises(ValueError, match="model_gene_overlap_unavailable"):
        runtime().predict_celltypist(model(), sparse.csr_matrix([[1.0]]), ["C"])


def test_rejection_uses_calibration_model_binding_and_records_knn_as_sensitivity():
    rt = runtime()
    trained = model()
    known = rt.predict_celltypist(trained, sparse.csr_matrix([[3., 1.], [5., 1.], [1., 6.], [1., 5.]]), ["A", "B"])
    calibration = rt.calibrate_rejection(
        known, known.predicted_labels, ["c1", "c2", "c3", "c4"],
        alpha=0.25, min_class_support=1,
    )
    assert calibration.model_sha256 == trained.fingerprint
    query = rt.predict_celltypist(trained, sparse.csr_matrix([[1., 2.], [3., 1.]]), ["A", "B"])
    decisions = rt.classify_with_rejection(query, calibration, ["q1", "q2"])
    assert decisions.loc[0, "assignment_state"] == "unknown"
    assert decisions.loc[0, "unknown_reason"] == "energy_ood_rejected"
    assert decisions.loc[1, "assignment_state"] == "candidate"
    assert decisions.loc[1, "assigned_state"] == "L1:Neuron_GABA"
    assert "knn_sensitivity_rejected" in decisions
    corrupted = calibration.model_copy(update={"model_sha256": "f" * 64})
    with pytest.raises(ValueError, match="calibration_model_mismatch"):
        rt.classify_with_rejection(query, corrupted, ["q1", "q2"])


def test_unresolved_source_identity_and_missing_feature_coverage_are_not_known_labels():
    rt = runtime()
    trained = model()
    known = rt.predict_celltypist(trained, sparse.csr_matrix([[3., 1.], [5., 1.], [1., 6.], [1., 5.]]), ["A", "B"])
    calibration = rt.calibrate_rejection(known, known.predicted_labels, ["c1", "c2", "c3", "c4"], min_class_support=1)
    missing = rt.predict_celltypist(trained, sparse.csr_matrix([[100.]]), ["A"])
    decisions = rt.classify_with_rejection(missing, calibration, ["q"])
    assert decisions.loc[0, "assignment_state"] == "unavailable"
    assert decisions.loc[0, "unknown_reason"] == "calibration_feature_coverage_mismatch"


def test_calibration_rejects_empty_duplicate_and_unlabeled_inputs():
    rt = runtime()
    known = rt.predict_celltypist(model(), sparse.csr_matrix([[3., 1.], [5., 1.]]), ["A", "B"])
    with pytest.raises(ValueError, match="calibration_observation_identity_invalid"):
        rt.calibrate_rejection(known, known.predicted_labels, ["same", "same"])
    with pytest.raises(ValueError, match="calibration_labels_invalid"):
        rt.calibrate_rejection(known, ["", ""], ["a", "b"])


def test_bundle_roundtrip_is_hash_bound_non_pickle_and_append_only(tmp_path: Path):
    rt = runtime()
    trained = model()
    known = rt.predict_celltypist(trained, sparse.csr_matrix([[3., 1.], [5., 1.], [1., 6.], [1., 5.]]), ["A", "B"])
    calibration = rt.calibrate_rejection(known, known.predicted_labels, ["c1", "c2", "c3", "c4"], min_class_support=1)
    bundle_path = tmp_path / "model"
    digest = rt.save_model_bundle(bundle_path, trained, calibration)
    restored, checked = rt.load_model_bundle(bundle_path, expected_sha256=digest)
    assert restored.fingerprint == trained.fingerprint
    assert checked == calibration
    np.testing.assert_allclose(
        rt.predict_celltypist(restored, sparse.csr_matrix([[3., 1.]]), ["A", "B"]).decision_scores,
        [[-3.25, 3.25]],
    )
    assert sorted(p.suffix for p in bundle_path.iterdir()) == [".json", ".npz"]
    with pytest.raises(FileExistsError):
        rt.save_model_bundle(bundle_path, trained, calibration)
    manifest = bundle_path / "manifest.json"
    payload = json.loads(manifest.read_text())
    payload["model_sha256"] = "e" * 64
    manifest.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="model_bundle_checksum_mismatch"):
        rt.load_model_bundle(bundle_path, expected_sha256=digest)


def test_fitted_inference_matches_real_celltypist_and_does_not_refit_query():
    celltypist = pytest.importorskip("celltypist")
    anndata = pytest.importorskip("anndata")
    rt = runtime()
    rng = np.random.default_rng(7)
    counts = rng.poisson(2, (40, 12)).astype(float)
    counts[:20, :4] += 20
    counts[20:, 8:] += 20
    normalized = np.log1p(counts / counts.sum(axis=1, keepdims=True) * 10000)
    genes = [f"G{i}" for i in range(12)]
    labels = np.array(["L1:Neuron_DA"] * 20 + ["L1:Neuron_GABA"] * 20)
    native = celltypist.train(
        X=sparse.csr_matrix(normalized), labels=labels, genes=genes,
        check_expression=False, max_iter=200, n_jobs=1, random_state=11,
    )
    trained = rt.fit_celltypist(
        sparse.csr_matrix(normalized), genes, labels, seed=11,
        max_iter=200, n_jobs=1,
        training_provenance={"source_family_ids": ["fixture-train"], "training_units": ["u1"]},
    )
    expected = celltypist.annotate(
        anndata.AnnData(X=sparse.csr_matrix(normalized[:5]), var=pd.DataFrame(index=genes)),
        model=native, majority_voting=False,
    )
    before = trained.fingerprint
    actual = rt.predict_celltypist(trained, sparse.csr_matrix(normalized[:5]), genes)
    np.testing.assert_allclose(actual.decision_scores, expected.decision_matrix.to_numpy(), rtol=1e-6, atol=1e-6)
    np.testing.assert_allclose(actual.probabilities, expected.probability_matrix.to_numpy(), rtol=1e-6, atol=1e-6)
    assert trained.fingerprint == before
