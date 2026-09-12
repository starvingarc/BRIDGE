"""Evidence-bounded development entry gates, separate from scientific release.

Passing these criteria only permits consideration of a separately preregistered
locked evaluation. It is never an identity, product, clinical or release approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import logsumexp

from .celltypist_runtime import ModelPrediction, calibrate_rejection, load_model_bundle
from .development_validation import (
    _json_bytes, _sha, _write_json, classification_metrics, ood_metrics,
)
from .scientific_review import load_development_review

CRITERIA = {
    "policy_id": "CELLSTATE-DEVELOPMENT-ENTRY-v1",
    "purpose": "entry_to_locked_evaluation_not_scientific_or_clinical_acceptance",
    "energy_ood_auroc_mean_minimum": 0.80,
    "energy_ood_auroc_each_fold_minimum": 0.60,
    "energy_ood_fpr95_mean_maximum": 0.20,
    "ood_accepted_fraction_mean_maximum": 0.10,
    "reference_selective_precision_minimum": 0.90,
    "reference_accepted_fraction_minimum": 0.50,
    "count_thinning_assignment_agreement_mean_minimum": 0.85,
    "masked_feature_unavailable_fraction": 1.0,
    "state_selective_precision_minimum": 0.90,
    "state_true_observations_minimum": 100,
    "state_assigned_observations_minimum": 50,
    "state_source_samples_with_truth_minimum": 3,
    "fold_aggregation": "unweighted_mean_reused_ood_panels_not_independent_replicates",
    "ood_truth_scope": "declared_dataset_domain_shift_not_cellwise_outside_taxonomy_ground_truth",
}


def _finite(value):
    return value is not None and np.isfinite(float(value))


def assess_development_metrics(summary):
    folds = summary["folds"]
    if (
        len(folds) < 3 or len({r["fold_id"] for r in folds}) != len(folds)
        or summary["primary_fold"] != "fold-01"
        or summary["locked_assets_opened"] or summary["sealed_assets_opened"]
        or summary["scientific_qualification"] != "not_established"
        or summary["source_independence"] != "within_family_sample_rotation_not_external_validation"
    ):
        raise ValueError("development_scope_invalid")
    panels = {row["asset_id"] for row in folds[0]["ood"]}
    if not panels or any({r["asset_id"] for r in fold["ood"]} != panels
                         or len(fold["ood"]) != len(panels) for fold in folds):
        raise ValueError("development_ood_panels_incomplete")
    reasons, panel_results = [], []
    for panel in sorted(panels):
        records = [next(r for r in fold["ood"] if r["asset_id"] == panel) for fold in folds]
        auc = np.asarray([r["energy"]["auroc_ood_positive"] for r in records], dtype=float)
        fpr = np.asarray([r["energy"]["fpr_at_95pct_ood_recall"] for r in records], dtype=float)
        accepted = np.asarray([r["accepted_fraction"] for r in records], dtype=float)
        if not np.isfinite(np.r_[auc, fpr, accepted]).all() or np.any(np.r_[auc, fpr, accepted] < 0) or np.any(np.r_[auc, fpr, accepted] > 1):
            raise ValueError("development_ood_metrics_invalid")
        checks = {
            "energy_ood_auroc_mean_below_minimum": auc.mean() < CRITERIA["energy_ood_auroc_mean_minimum"],
            "energy_ood_auroc_fold_below_minimum": auc.min() < CRITERIA["energy_ood_auroc_each_fold_minimum"],
            "energy_ood_fpr95_above_maximum": fpr.mean() > CRITERIA["energy_ood_fpr95_mean_maximum"],
            "ood_accepted_fraction_above_maximum": accepted.mean() > CRITERIA["ood_accepted_fraction_mean_maximum"],
        }
        failures = sorted(code for code, failed in checks.items() if failed)
        reasons.extend(failures)
        panel_results.append({
            "asset_id": panel, "energy_auroc_mean": float(auc.mean()),
            "energy_auroc_min": float(auc.min()), "energy_fpr95_mean": float(fpr.mean()),
            "accepted_fraction_mean": float(accepted.mean()),
            "state": "failed" if failures else "passed", "reason_codes": failures,
        })
    overall = summary["overall"]
    if not _finite(overall["selective_precision"]) or overall["selective_precision"] < CRITERIA["reference_selective_precision_minimum"]:
        reasons.append("reference_selective_precision_below_minimum")
    if not _finite(overall["accepted_fraction"]) or overall["accepted_fraction"] < CRITERIA["reference_accepted_fraction_minimum"]:
        reasons.append("reference_accepted_fraction_below_minimum")
    thinning = [fold["sensitivities"].get("count_thinning_50pct", {}) for fold in folds]
    if any(r.get("state") != "measured_development_sensitivity" for r in thinning):
        reasons.append("reference_count_thinning_unavailable")
    elif np.mean([r["assignment_agreement"] for r in thinning]) < CRITERIA["count_thinning_assignment_agreement_mean_minimum"]:
        reasons.append("reference_count_thinning_unstable")
    masking = [fold["sensitivities"].get("gene_mask_25pct", {}) for fold in folds]
    if any(r.get("state") != "measured_development_sensitivity"
           or r.get("unavailable_fraction") != CRITERIA["masked_feature_unavailable_fraction"] for r in masking):
        reasons.append("missing_feature_gate_not_preserved")
    metrics = {r["state_id"]: r for r in overall["per_state"]}
    state_results = []
    for card in load_development_review().state_reviews:
        row = metrics.get(card.state_id)
        state_reasons = []
        if card.decision == "unavailable":
            state, state_reasons = "unavailable", ["source_identity_or_reference_unavailable"]
        elif card.decision == "parent_only":
            state, state_reasons = "parent_only", ["regional_source_label_not_validated"]
        elif row is None:
            state, state_reasons = "unavailable", ["state_development_evidence_missing"]
        else:
            for key, limit, reason in (
                ("n_true", "state_true_observations_minimum", "state_truth_support_insufficient"),
                ("n_assigned", "state_assigned_observations_minimum", "state_accepted_support_insufficient"),
                ("n_source_samples_with_truth", "state_source_samples_with_truth_minimum", "state_sample_support_insufficient"),
            ):
                if row[key] < CRITERIA[limit]:
                    state_reasons.append(reason)
            if not _finite(row["precision"]) or row["precision"] < CRITERIA["state_selective_precision_minimum"]:
                state_reasons.append("state_selective_precision_below_minimum")
            state = "unavailable" if state_reasons else "candidate_pending_independent_validation"
        state_results.append({
            "state_id": card.state_id, "state": state, "parent_state_id": card.parent_state_id,
            "scientific_release": "unavailable", "reason_codes": sorted(state_reasons),
            "metrics": row,
        })
    return {
        "criteria": dict(CRITERIA),
        "development_gate_state": "failed" if reasons else "passed",
        "reason_codes": sorted(set(reasons)), "ood_panels": panel_results,
        "per_state": state_results,
        "scientific_qualification": "not_established",
        "n_independent_source_families": 1,
        "qualified_state_ids": [],
        "locked_test_state": "not_run_development_failed" if reasons else "not_run",
        "interpretation": "source_label_recovery_and_domain_shift_diagnostics_not_validated_biological_identity",
    }


def _read_json(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("development_receipt_path_invalid")
    return json.loads(path.read_bytes(), parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite_json")))


def _equal(actual, expected):
    if _json_bytes(actual) != _json_bytes(expected):
        raise ValueError("development_metrics_do_not_match_predictions")


def verify_development_run(run_root: Path, *, expected_summary_sha256: str):
    root = Path(run_root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("development_receipt_path_invalid")
    if _sha(root / "summary.json") != expected_summary_sha256:
        raise ValueError("development_summary_checksum_mismatch")
    summary = _read_json(root / "summary.json")
    design = _read_json(root / "development_design.json")
    design_sha = _sha(root / "development_design.json")
    if (
        summary["development_design_sha256"] != design_sha
        or summary["locked_assets_opened"] or summary["sealed_assets_opened"]
        or design["locked_assets_opened"] or design["sealed_assets_opened"]
        or design["behavior_assets_used"]
    ):
        raise ValueError("development_design_binding_invalid")
    folds = summary["folds"]
    if {r["fold_id"] for r in folds} != set(design["folds"]) or len(folds) != len(design["folds"]):
        raise ValueError("development_fold_coverage_mismatch")
    all_tests, model_bindings = [], {}
    expected_panels = set(design["input_bundles"]) - {design["reference_asset"]}
    for record in folds:
        fold = record["fold_id"]
        if not fold.startswith("fold-") or not fold[5:].isdigit():
            raise ValueError("development_fold_path_invalid")
        folder = root / fold
        model, calibration = load_model_bundle(folder / "model", expected_sha256=record["model_manifest_sha256"])
        if model.fingerprint != record["model_sha256"] or model.training_provenance["development_design_sha256"] != design_sha:
            raise ValueError("development_model_binding_invalid")
        frames = {}
        for part in ("test", "calibration"):
            path = folder / f"{part}.parquet"
            if path.is_symlink() or _sha(path) != record[f"{part}_predictions_sha256"]:
                raise ValueError("development_predictions_checksum_mismatch")
            frame = pd.read_parquet(path)
            if (
                frame.observation_id.duplicated().any()
                or set(frame.sample_id) != set(design["folds"][fold][part])
                or set(frame.model_sha256) != {model.fingerprint}
                or set(frame.calibration_sha256) != {calibration.calibration_sha256}
            ):
                raise ValueError("development_prediction_scope_invalid")
            decisions = frame[[f"raw_decision_{label}" for label in model.classes]].to_numpy()
            if not np.isfinite(decisions).all() or not np.allclose(frame.energy, -logsumexp(decisions, axis=1), rtol=1e-12, atol=1e-12):
                raise ValueError("development_energy_not_raw_decision_bound")
            frames[part] = frame
        if set(frames["test"].observation_id) & set(frames["calibration"].observation_id):
            raise ValueError("development_calibration_test_overlap")
        for part in ("calibration", "test"):
            if set(design["folds"][fold][part]) & set(design["folds"][fold]["train"]):
                raise ValueError("development_training_query_overlap")
        cal = frames["calibration"]
        prediction = ModelPrediction(
            model.fingerprint, model.classes,
            cal[[f"raw_decision_{label}" for label in model.classes]].to_numpy(),
            cal.energy.to_numpy(), cal.knn_distance.to_numpy(), float(cal.feature_coverage.iloc[0]), (),
        )
        recreated = calibrate_rejection(
            prediction, cal.true_label, cal.observation_id,
            alpha=design["calibration"]["alpha"],
            min_class_support=design["calibration"]["min_correct_class_support"],
            minimum_feature_coverage=design["calibration"]["minimum_feature_coverage"],
        )
        if recreated != calibration:
            raise ValueError("development_calibration_does_not_match_predictions")
        _equal(classification_metrics(frames["test"]), record["test"])
        if {r["asset_id"] for r in record["ood"]} != expected_panels:
            raise ValueError("development_ood_panels_incomplete")
        for query in record["ood"]:
            identifier = query["asset_id"]
            if Path(identifier).name != identifier or identifier in {".", ".."}:
                raise ValueError("development_query_path_invalid")
            path = folder / f"{identifier}.parquet"
            if path.is_symlink() or _sha(path) != query["predictions_sha256"]:
                raise ValueError("development_predictions_checksum_mismatch")
            frame = pd.read_parquet(path)
            if set(frame.model_sha256) != {model.fingerprint} or set(frame.calibration_sha256) != {calibration.calibration_sha256}:
                raise ValueError("development_prediction_scope_invalid")
            _equal(ood_metrics(frames["test"].energy, frame.energy), query["energy"])
            _equal(ood_metrics(frames["test"].knn_distance, frame.knn_distance), query["knn_sensitivity"])
            _equal(float(frame.assignment_state.isin(["candidate", "parent_candidate"]).mean()), query["accepted_fraction"])
        all_tests.append(frames["test"])
        model_bindings[fold] = {"model_sha256": model.fingerprint, "model_manifest_sha256": record["model_manifest_sha256"]}
    combined = pd.concat(all_tests, ignore_index=True)
    if combined.observation_id.duplicated().any():
        raise ValueError("development_test_rotation_not_unique")
    _equal(classification_metrics(combined), summary["overall"])
    return {
        "object_version": "1.0.0",
        "summary_sha256": expected_summary_sha256, "development_design_sha256": design_sha,
        "training_review_sha256": design["development_review_sha256"],
        "metric_verification": "recomputed_from_checksums_bound_predictions",
        "verified_held_out_observations": len(combined), "models": model_bindings,
        "primary_fold": design["primary_fold"],
        "scientific_decision": assess_development_metrics(summary),
        "sensitivity_verification": "producer_recorded_not_recomputed_by_receipt_verifier",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--summary-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify_development_run(args.run_root, expected_summary_sha256=args.summary_sha256)
    _write_json(args.output, result)
    print(json.dumps({"verification_sha256": _sha(args.output),
                      "development_gate_state": result["scientific_decision"]["development_gate_state"],
                      "reason_codes": result["scientific_decision"]["reason_codes"]}))


if __name__ == "__main__":
    main()
