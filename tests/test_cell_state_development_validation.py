from __future__ import annotations

import importlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bridge.toolkit.contracts import BenchmarkSplitManifest, BenchmarkSplitRecord
from test_cell_state_method_adapters import _exchange_bundle, _split_manifest


def development():
    return importlib.import_module("bridge.tool_packages.p0_02_cell_state.development_validation")


def fixture_inputs(tmp_path: Path, *, role="development_ood"):
    root, asset = _exchange_bundle(tmp_path, raw_counts=True)
    split_path = _split_manifest(tmp_path, asset)
    _exchange_bundle(tmp_path, asset_id="OOD-fixture", data_role=role)
    manifest_path = root / "OOD-fixture" / "bundle.json"
    payload = json.loads(manifest_path.read_text())
    payload["source_family_id"] = "OOD-FAMILY"
    manifest_path.write_text(json.dumps(payload))
    split = BenchmarkSplitManifest.model_validate_json(split_path.read_text())
    records = [*split.records, *[
        BenchmarkSplitRecord(
            asset_id="OOD-fixture", source_family_id="OOD-FAMILY", sample_id=f"donor-{i}",
            partition=role, data_role=role, n_observations=4,
        ) for i in range(1, 4)
    ]]
    split_path.write_text(split.model_copy(update={"records": records}).model_dump_json())
    return root, asset, split_path


def test_design_binds_verified_inputs_and_prevents_behavior_data_feature_selection(tmp_path):
    dev = development()
    root, asset, split_path = fixture_inputs(tmp_path)
    _, folds, _, design = dev.prepare_development(root, asset, split_path, ["OOD-fixture"])
    assert len(folds) == 3
    assert design["features"] == ["TH", "FOXA2", "AQP4"]
    assert design["primary_fold"] == "fold-01"
    assert design["source_independence"] == "within_family_sample_rotation_not_external_validation"
    assert len(design["split_sha256"]) == 64
    other = tmp_path / "behavior"
    other.mkdir()
    b_root, b_asset, b_split = fixture_inputs(other, role="behavior_only")
    with pytest.raises(ValueError, match="development_ood_only"):
        dev.prepare_development(b_root, b_asset, b_split, ["OOD-fixture"])


def test_reference_source_mismatch_and_query_family_overlap_cannot_enter_design(tmp_path):
    dev = development()
    root, asset, split_path = fixture_inputs(tmp_path)
    manifest_path = root / asset / "bundle.json"
    payload = json.loads(manifest_path.read_text())
    payload["source_family_id"] = "WRONG"
    manifest_path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="reference_split_binding_mismatch"):
        dev.prepare_development(root, asset, split_path, ["OOD-fixture"])


def test_ood_continuous_metrics_use_ood_positive_and_never_calibration_rows():
    dev = development()
    result = dev.ood_metrics([-5.0, -4.0], [-2.0, -1.0])
    assert result["auroc_ood_positive"] == 1.0
    assert result["aupr_ood_positive"] == 1.0
    assert result["fpr_at_95pct_ood_recall"] == 0.0
    assert dev.ood_metrics([0., 0.], [0., 0.])["auroc_ood_positive"] == 0.5
    with pytest.raises(ValueError, match="ood_metrics_require_finite_nonempty_arrays"):
        dev.ood_metrics([], [1.])


def test_selective_metrics_keep_rejected_mass_and_state_denominators():
    dev = development()
    frame = pd.DataFrame({
        "true_label": ["L1:Neuron_DA", "L1:Neuron_DA", "L1:Astrocyte", "L1:Astrocyte"],
        "predicted_source_label": ["L1:Neuron_DA"] * 3 + ["L1:Astrocyte"],
        "assigned_state": ["L1:Neuron_DA", None, "L1:Neuron_DA", None],
        "assignment_state": ["candidate", "unknown", "candidate", "unavailable"],
        "sample_id": ["a", "a", "b", "b"],
    })
    result = dev.classification_metrics(frame)
    assert result["forced_accuracy"] == 0.75
    assert result["accepted_fraction"] == 0.5
    assert result["selective_precision"] == 0.5
    assert result["composition_l1_error_with_unknown_mass"] == 1.0
    da = next(row for row in result["per_state"] if row["state_id"] == "L1:Neuron_DA")
    assert da["n_true"] == 2
    assert da["n_assigned"] == 2
    assert da["recall_including_rejection"] == 0.5
    assert da["precision"] == 0.5


def test_parent_review_is_applied_before_training_fine_label_accuracy_not_invented():
    labels = development().training_labels(["L2:RG_mFP", "L2:Nb_mBIP", "L1:Neuron_DA"])
    assert labels.tolist() == ["L1:Radial_Glia", "L1:Neuroblast", "L1:Neuron_DA"]


def test_count_thinning_is_reproducible_preserves_input_and_normalized_only_is_unavailable(tmp_path):
    from bridge.tool_packages.p0_02_cell_state.method_adapter import load_adapter_context
    dev = development()
    root, asset = _exchange_bundle(tmp_path, raw_counts=True)
    bundle, _ = load_adapter_context(root, asset, _split_manifest(tmp_path, asset))
    before = bundle.raw_counts.copy()
    one = dev.perturbed_expression(bundle, "count_thinning_50pct", seed=11)
    two = dev.perturbed_expression(bundle, "count_thinning_50pct", seed=11)
    np.testing.assert_array_equal(one.toarray(), two.toarray())
    np.testing.assert_array_equal(bundle.raw_counts.toarray(), before.toarray())
    other = tmp_path / "normalized"
    other.mkdir()
    root2, asset2 = _exchange_bundle(other)
    bundle2, _ = load_adapter_context(root2, asset2, _split_manifest(other, asset2))
    assert dev.perturbed_expression(bundle2, "count_thinning_50pct", seed=11) is None


def test_real_development_run_is_append_only_hash_bound_and_not_qualified(tmp_path):
    pytest.importorskip("celltypist")
    dev = development()
    root, asset, split_path = fixture_inputs(tmp_path)
    out = tmp_path / "run"
    summary = dev.run_development(
        exchange_root=root, asset_id=asset, split_manifest_path=split_path,
        query_asset_ids=["OOD-fixture"], output_root=out, seed=11, max_iter=20, n_jobs=1,
    )
    assert summary["scientific_qualification"] == "not_established"
    assert summary["locked_assets_opened"] is False
    assert len(summary["folds"]) == 3
    assert (out / "development_design.json").is_file()
    assert (out / "fold-01" / "model" / "manifest.json").is_file()
    assert (out / "fold-01" / "test.parquet").is_file()
    assert summary["folds"][0]["ood"][0]["asset_id"] == "OOD-fixture"
    assert summary["folds"][0]["ood"][0]["count_thinning_50pct"]["state"] == "unavailable"
    frame = pd.read_parquet(out / "fold-01" / "test.parquet")
    assert len(frame) == 4
    assert set(frame["sample_id"]) == {"donor-1"}
    assert "raw_decision_L1:Neuron_DA" in frame
    with pytest.raises(FileExistsError):
        dev.run_development(
            exchange_root=root, asset_id=asset, split_manifest_path=split_path,
            query_asset_ids=["OOD-fixture"], output_root=out, seed=11, max_iter=20, n_jobs=1,
        )
