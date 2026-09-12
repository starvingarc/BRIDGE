from __future__ import annotations

import importlib
import json

import pytest


def module():
    return importlib.import_module("bridge.tool_packages.p0_02_cell_state.development_qualification")


def sample_summary():
    return {
        "primary_fold": "fold-01",
        "source_independence": "within_family_sample_rotation_not_external_validation",
        "scientific_qualification": "not_established",
        "locked_assets_opened": False, "sealed_assets_opened": False,
        "overall": {"accepted_fraction": 0.8, "selective_precision": 0.95,
                    "per_state": [{"state_id": "L1:Neuron_DA", "n_true": 100,
                                   "n_assigned": 80, "n_source_samples_with_truth": 3,
                                   "precision": 0.95, "recall_including_rejection": 0.76}]},
        "folds": [{
            "fold_id": f"fold-{i:02d}",
            "sensitivities": {
                "count_thinning_50pct": {"state": "measured_development_sensitivity", "assignment_agreement": 0.9},
                "gene_mask_25pct": {"state": "measured_development_sensitivity", "unavailable_fraction": 1.0},
            },
            "ood": [{"asset_id": "OOD-example", "energy": {
                "auroc_ood_positive": 0.92, "fpr_at_95pct_ood_recall": 0.15,
            }, "accepted_fraction": 0.04}],
        } for i in range(1, 4)],
    }


def test_passing_development_never_confers_independent_scientific_qualification():
    outcome = module().assess_development_metrics(sample_summary())
    assert outcome["development_gate_state"] == "passed"
    assert outcome["scientific_qualification"] == "not_established"
    assert outcome["locked_test_state"] == "not_run"
    assert outcome["n_independent_source_families"] == 1
    assert outcome["qualified_state_ids"] == []


def test_failed_energy_cannot_be_rescued_by_knn_or_a_passing_average():
    data = sample_summary()
    data["folds"][0]["ood"][0]["energy"]["auroc_ood_positive"] = 0.3
    data["folds"][0]["ood"][0]["knn_sensitivity"] = {"auroc_ood_positive": 0.999}
    outcome = module().assess_development_metrics(data)
    assert outcome["development_gate_state"] == "failed"
    assert outcome["locked_test_state"] == "not_run_development_failed"
    assert "energy_ood_auroc_fold_below_minimum" in outcome["reason_codes"]
    assert outcome["qualified_state_ids"] == []


def test_parent_only_and_zero_observation_states_cannot_be_promoted_by_aggregate_accuracy():
    data = sample_summary()
    data["overall"]["per_state"] += [
        {"state_id": "L2:RG_mFP", "n_true": 200, "n_assigned": 200,
         "n_source_samples_with_truth": 4, "precision": 1., "recall_including_rejection": 1.},
        {"state_id": "L1:Neuron_ChAT", "n_true": 200, "n_assigned": 200,
         "n_source_samples_with_truth": 4, "precision": 1., "recall_including_rejection": 1.},
    ]
    result = module().assess_development_metrics(data)
    states = {row["state_id"]: row for row in result["per_state"]}
    assert states["L2:RG_mFP"]["state"] == "parent_only"
    assert states["L1:Neuron_ChAT"]["state"] == "unavailable"
    assert states["L1:Neuron_DA"]["state"] == "candidate_pending_independent_validation"


def test_qualification_rejects_missing_fold_or_ood_evidence_not_zero_fills():
    data = sample_summary()
    data["folds"][0]["ood"] = []
    with pytest.raises(ValueError, match="development_ood_panels_incomplete"):
        module().assess_development_metrics(data)
    data = sample_summary()
    data["folds"][0]["sensitivities"]["count_thinning_50pct"] = {"state": "unavailable"}
    result = module().assess_development_metrics(data)
    assert "reference_count_thinning_unavailable" in result["reason_codes"]


def test_actual_receipt_verification_recomputes_values_and_checks_expected_hashes(tmp_path):
    from test_cell_state_development_validation import fixture_inputs, development
    from bridge.tool_packages.p0_02_cell_state.development_validation import _sha
    pytest.importorskip("celltypist")
    root, asset, split = fixture_inputs(tmp_path)
    run = tmp_path / "run"
    development().run_development(
        exchange_root=root, asset_id=asset, split_manifest_path=split,
        query_asset_ids=["OOD-fixture"], output_root=run, seed=11, max_iter=20, n_jobs=1,
    )
    expected = _sha(run / "summary.json")
    verified = module().verify_development_run(run, expected_summary_sha256=expected)
    assert verified["summary_sha256"] == expected
    assert verified["verified_held_out_observations"] == 12
    assert verified["metric_verification"] == "recomputed_from_checksums_bound_predictions"
    summary_path = run / "summary.json"
    payload = json.loads(summary_path.read_text())
    payload["overall"]["forced_accuracy"] = 1.0 - payload["overall"]["forced_accuracy"]
    summary_path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="development_summary_checksum_mismatch"):
        module().verify_development_run(run, expected_summary_sha256=expected)
    with pytest.raises(ValueError, match="development_metrics_do_not_match_predictions"):
        module().verify_development_run(run, expected_summary_sha256=_sha(summary_path))
