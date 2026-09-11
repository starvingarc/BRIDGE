"""Development-only CellTypist validation, with pre-fit design and saved models.

This command is not a registered product measurement and cannot release a state.
It consumes the existing checksummed exchange and sample-level pilot splits.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.metrics import accuracy_score, average_precision_score, f1_score, roc_auc_score, roc_curve

from .celltypist_runtime import (
    calibrate_rejection, classify_with_rejection, fit_celltypist,
    predict_celltypist, save_model_bundle,
)
from .method_adapter import (
    AdapterBundle, _load_query_bundles, _load_split, _log1p_cp10k, load_adapter_context,
)
from .scientific_review import development_review_sha256, load_development_review

VERSION = "1.0.0"


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _write_json(path, value):
    with Path(path).open("xb") as handle:
        handle.write(_json_bytes(value))


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def training_labels(labels: Sequence[str]) -> np.ndarray:
    rows = {row.state_id: row for row in load_development_review().state_reviews}
    result = []
    for label in labels:
        row = rows.get(str(label))
        if row is None:
            raise ValueError("training_label_not_reviewed")
        result.append(row.parent_state_id if row.decision == "parent_only" else row.state_id)
    return np.asarray(result, dtype=str)


def prepare_development(exchange_root, asset_id, split_manifest_path, query_asset_ids):
    """Verify roles before loading queries; freeze gene IDs, not query expression."""
    root, split_path = Path(exchange_root), Path(split_manifest_path)
    split = _load_split(split_path, asset_id)
    if len(query_asset_ids) != len(set(query_asset_ids)):
        raise ValueError("duplicate_development_query")
    for query in query_asset_ids:
        records = [r for r in split.records if r.asset_id == query]
        if not records or any(r.partition != "development_ood" or r.data_role != "development_ood" for r in records):
            raise ValueError("development_ood_only")
    reference, folds = load_adapter_context(root, asset_id, split_path)
    ref_records = [r for r in split.records if r.asset_id == asset_id]
    if (
        reference.metadata["data_role"] != "labeled_reference"
        or any(r.source_family_id != reference.metadata["source_family_id"]
               or r.data_role != "labeled_reference" for r in ref_records)
        or any(r.n_observations != int(reference.observations.sample_id.eq(r.sample_id).sum())
               for r in ref_records)
    ):
        raise ValueError("reference_split_binding_mismatch")
    queries = _load_query_bundles(
        root, query_asset_ids, expected_level="L1", split=split,
    )
    if any(q.metadata["source_family_id"] == reference.metadata["source_family_id"] for q in queries):
        raise ValueError("development_ood_reference_family_overlap")
    common = set(reference.features)
    for query in queries:
        common.intersection_update(query.features)
    features = [gene for gene in reference.features if gene in common]
    if len(features) < 2:
        raise ValueError("development_common_panel_unavailable")
    labels = training_labels(reference.observations.true_label)
    reference = replace(
        reference, observations=reference.observations.assign(
            source_true_label=reference.observations.true_label, true_label=labels,
        ),
    )
    if "fold-01" not in folds:
        raise ValueError("fixed_primary_fold_missing")
    source_files = [Path(__file__), Path(__file__).with_name("celltypist_runtime.py"),
                    Path(__file__).with_name("scientific_review.py")]
    design = {
        "object_version": VERSION,
        "purpose": "development_not_scientific_release",
        "reference_asset": asset_id,
        "source_family_id": reference.metadata["source_family_id"],
        "source_independence": "within_family_sample_rotation_not_external_validation",
        "replication_limit": "sample_rotation_with_age_confounding_not_independent_source_or_effect_size",
        "split_sha256": _sha(split_path),
        "input_bundles": {b.asset_id: {
            "bundle_sha256": _sha(root / b.asset_id / "bundle.json"),
            "source_family_id": b.metadata["source_family_id"],
            "artifacts": b.metadata["artifacts"],
        } for b in [reference, *queries]},
        "implementation_sha256": {p.name: _sha(p) for p in source_files},
        "development_review_sha256": development_review_sha256(),
        "features": features,
        "feature_selection": "ordered_intersection_of_reference_and_development_ood_gene_ids_no_query_values",
        "features_sha256": hashlib.sha256("\n".join(features).encode()).hexdigest(),
        "normalization": "log1p_cp10k_on_full_original_gene_panel_before_common_panel_subset",
        "label_policy": "reviewed_parent_collapse_before_fitting_no_fine_label_accuracy_claim",
        "primary_fold": "fold-01",
        "folds": {fold: {part: sorted(set(reference.observations.loc[partitions.eq(part), "sample_id"]))
                          for part in ("train", "calibration", "test")}
                  for fold, partitions in folds.items()},
        "calibration": {"alpha": 0.05, "min_correct_class_support": 20, "minimum_feature_coverage": 0.9,
                        "energy": "negative_logsumexp_raw_ovr_decisions_temperature_1",
                        "energy_threshold": "represented_calibration_cells_empirical_95pct_higher_quantile",
                        "class_margin": "correct_calibration_cells_empirical_5pct_lower_quantile",
                        "knn": "training_only_pca32_mean10nn_sensitivity_not_independent_vote"},
        "sensitivities": ["count_thinning_50pct", "library_size_50pct", "gene_mask_25pct"],
        "ood_metrics": "ood_positive_auroc_aupr_fpr95_versus_held_out_reference_test_not_calibration",
        "qualification": "not_established_development_results_required_before_locked_contract",
        "locked_assets_opened": False, "sealed_assets_opened": False,
        "behavior_assets_used": False,
    }
    return reference, folds, queries, design


def ood_metrics(id_scores, ood_scores):
    known, unknown = np.asarray(id_scores, dtype=float), np.asarray(ood_scores, dtype=float)
    if (
        known.ndim != 1 or unknown.ndim != 1 or not len(known) or not len(unknown)
        or not np.isfinite(known).all() or not np.isfinite(unknown).all()
    ):
        raise ValueError("ood_metrics_require_finite_nonempty_arrays")
    labels = np.r_[np.zeros(len(known)), np.ones(len(unknown))]
    scores = np.r_[known, unknown]
    fpr, tpr, _ = roc_curve(labels, scores)
    return {
        "n_id": len(known), "n_ood": len(unknown),
        "auroc_ood_positive": float(roc_auc_score(labels, scores)),
        "aupr_ood_positive": float(average_precision_score(labels, scores)),
        "fpr_at_95pct_ood_recall": float(fpr[np.flatnonzero(tpr >= 0.95)[0]]),
        "ood_prevalence_for_aupr": float(len(unknown) / len(labels)),
    }


def classification_metrics(frame: pd.DataFrame):
    n = len(frame)
    if not n:
        raise ValueError("classification_metrics_require_observations")
    true = frame.true_label.astype(str)
    forced = frame.predicted_source_label.astype(str)
    accepted = frame.assignment_state.isin(["candidate", "parent_candidate"])
    assigned = frame.assigned_state.where(accepted, "__unknown__").fillna("__unknown__")
    correct = assigned.eq(true) & accepted
    states = sorted(set(true) | set(assigned) - {"__unknown__"})
    per_state = []
    for state in states:
        selected = assigned.eq(state)
        truth = true.eq(state)
        tp = int((selected & truth).sum())
        per_state.append({
            "state_id": state, "n_true": int(truth.sum()), "n_assigned": int(selected.sum()),
            "n_correct": tp, "n_source_samples_with_truth": int(frame.loc[truth, "sample_id"].nunique()),
            "precision": float(tp / selected.sum()) if selected.any() else None,
            "recall_including_rejection": float(tp / truth.sum()) if truth.any() else None,
        })
    comparison_states = sorted(set(true) | set(assigned))
    composition_error = sum(abs(float(true.eq(s).mean()) - float(assigned.eq(s).mean()))
                            for s in comparison_states)
    return {
        "n_observations": n, "n_source_samples": int(frame.sample_id.nunique()),
        "forced_accuracy": float(accuracy_score(true, forced)),
        "forced_macro_f1": float(f1_score(true, forced, average="macro", zero_division=0)),
        "accepted_fraction": float(accepted.mean()),
        "selective_precision": float(correct.sum() / accepted.sum()) if accepted.any() else None,
        "unknown_fraction": float(frame.assignment_state.eq("unknown").mean()),
        "unavailable_fraction": float(frame.assignment_state.eq("unavailable").mean()),
        "composition_l1_error_with_unknown_mass": composition_error,
        "per_state": per_state,
    }


def perturbed_expression(bundle: AdapterBundle, perturbation: str, *, seed: int):
    if perturbation == "count_thinning_50pct":
        if bundle.raw_counts is None:
            return None
        counts = bundle.raw_counts.copy()
        counts.data = np.random.default_rng(seed).binomial(np.rint(counts.data).astype(np.int64), 0.5)
        counts.eliminate_zeros()
        return _log1p_cp10k(counts)
    if perturbation == "library_size_50pct":
        values = bundle.matrix.copy()
        values.data = np.log1p(np.expm1(values.data) * 0.5)
        return values
    raise ValueError("unknown_expression_perturbation")


def _subset(bundle, selection):
    return replace(
        bundle, matrix=bundle.matrix[selection],
        observations=bundle.observations.loc[selection].reset_index(drop=True),
        raw_counts=bundle.raw_counts[selection] if bundle.raw_counts is not None else None,
    )


def _predict_frame(model, calibration, bundle):
    predictions = predict_celltypist(model, bundle.matrix, bundle.features)
    frame = classify_with_rejection(predictions, calibration, bundle.observations.observation_id)
    for column in bundle.observations.columns:
        if column not in frame:
            frame[column] = bundle.observations[column].to_numpy()
    for index, state in enumerate(predictions.classes):
        frame[f"raw_decision_{state}"] = predictions.decision_scores[:, index]
    frame["model_sha256"] = model.fingerprint
    frame["calibration_sha256"] = calibration.calibration_sha256
    return frame


def _sensitivity(model, calibration, bundle, baseline, *, seed):
    results = {}
    for name in ("count_thinning_50pct", "library_size_50pct", "gene_mask_25pct"):
        if name == "gene_mask_25pct":
            rng = np.random.default_rng(seed)
            removed = set(rng.choice(model.features, max(1, len(model.features) // 4), replace=False))
            indices = [i for i, gene in enumerate(bundle.features) if gene not in removed]
            changed = replace(bundle, matrix=bundle.matrix[:, indices],
                              features=[bundle.features[i] for i in indices], raw_counts=None)
        else:
            matrix = perturbed_expression(bundle, name, seed=seed)
            if matrix is None:
                results[name] = {"state": "unavailable", "reason": "raw_counts_not_available"}
                continue
            changed = replace(bundle, matrix=matrix)
        frame = _predict_frame(model, calibration, changed)
        same = frame.assigned_state.fillna("__unknown__").eq(baseline.assigned_state.fillna("__unknown__"))
        states = set(frame.assigned_state.dropna()) | set(baseline.assigned_state.dropna()) | {"__unknown__"}
        left = frame.assigned_state.fillna("__unknown__")
        right = baseline.assigned_state.fillna("__unknown__")
        results[name] = {
            "state": "measured_development_sensitivity",
            "n_observations": len(frame), "model_sha256": model.fingerprint,
            "assignment_agreement": float(same.mean()),
            "forced_label_agreement": float(frame.predicted_source_label.eq(baseline.predicted_source_label).mean()),
            "composition_l1_change_with_unknown_mass": sum(abs(float(left.eq(s).mean()) - float(right.eq(s).mean())) for s in states),
            "accepted_fraction": float(frame.assignment_state.isin(["candidate", "parent_candidate"]).mean()),
            "unavailable_fraction": float(frame.assignment_state.eq("unavailable").mean()),
            "feature_coverage": float(frame.feature_coverage.iloc[0]),
        }
    return results


def run_development(
    *, exchange_root: Path, asset_id: str, split_manifest_path: Path,
    query_asset_ids: Sequence[str], output_root: Path, seed: int = 20260911,
    max_iter: int = 200, n_jobs: int = 1,
):
    output_root = Path(output_root)
    # Fail before expensive loading; no resuming or overwriting a partial receipt.
    output_root.mkdir(parents=False, exist_ok=False)
    reference, folds, queries, design = prepare_development(
        exchange_root, asset_id, split_manifest_path, query_asset_ids,
    )
    design["training"] = {"seed": seed, "max_iter": max_iter, "n_jobs": n_jobs}
    _write_json(output_root / "development_design.json", design)
    design_sha = _sha(output_root / "development_design.json")
    print(json.dumps({"event": "design_frozen_before_fit", "sha256": design_sha,
                      "n_features": len(design["features"]), "n_reference": len(reference.observations)}), flush=True)
    features = design["features"]
    lookup = {gene: i for i, gene in enumerate(reference.features)}
    indices = [lookup[gene] for gene in features]
    results, frames = [], []
    for fold, partitions in folds.items():
        fold_root = output_root / fold
        fold_root.mkdir()
        train = partitions.eq("train").to_numpy()
        calibration_rows = partitions.eq("calibration").to_numpy()
        test = partitions.eq("test").to_numpy()
        print(json.dumps({"event": "fit_started", "fold": fold, "n_train": int(train.sum())}), flush=True)
        model = fit_celltypist(
            reference.matrix[train][:, indices], features,
            reference.observations.loc[train, "true_label"], seed=seed,
            max_iter=max_iter, n_jobs=n_jobs,
            training_provenance={
                "development_design_sha256": design_sha, "fold_id": fold,
                "asset_id": asset_id, "source_family_ids": [reference.metadata["source_family_id"]],
                "training_samples": design["folds"][fold]["train"],
                "training_observations_sha256": hashlib.sha256(
                    "\n".join(reference.observations.loc[train, "observation_id"]).encode()).hexdigest(),
                "feature_selection": design["feature_selection"],
            },
        )
        calibration_prediction = predict_celltypist(
            model, reference.matrix[calibration_rows], reference.features,
        )
        calibration = calibrate_rejection(
            calibration_prediction, reference.observations.loc[calibration_rows, "true_label"],
            reference.observations.loc[calibration_rows, "observation_id"],
        )
        model_manifest_sha = save_model_bundle(fold_root / "model", model, calibration)
        test_bundle = _subset(reference, test)
        test_frame = _predict_frame(model, calibration, test_bundle)
        test_frame["fold_id"] = fold
        test_frame.to_parquet(fold_root / "test.parquet", index=False)
        calibration_frame = _predict_frame(model, calibration, _subset(reference, calibration_rows))
        calibration_frame.to_parquet(fold_root / "calibration.parquet", index=False)
        sensitivity = _sensitivity(model, calibration, test_bundle, test_frame, seed=seed)
        result = {
            "fold_id": fold, "model_sha256": model.fingerprint,
            "model_manifest_sha256": model_manifest_sha,
            "test_predictions_sha256": _sha(fold_root / "test.parquet"),
            "calibration_predictions_sha256": _sha(fold_root / "calibration.parquet"),
            "test": classification_metrics(test_frame), "sensitivities": sensitivity, "ood": [],
        }
        for query in queries:
            query_frame = _predict_frame(model, calibration, query)
            query_frame.to_parquet(fold_root / f"{query.asset_id}.parquet", index=False)
            accepted = query_frame.assignment_state.isin(["candidate", "parent_candidate"])
            result["ood"].append({
                "asset_id": query.asset_id, "source_family_id": query.metadata["source_family_id"],
                "feature_coverage": float(query_frame.feature_coverage.iloc[0]),
                "predictions_sha256": _sha(fold_root / f"{query.asset_id}.parquet"),
                "energy": ood_metrics(test_frame.energy, query_frame.energy),
                "knn_sensitivity": ood_metrics(test_frame.knn_distance, query_frame.knn_distance),
                "accepted_fraction": float(accepted.mean()),
                "energy_rejected_fraction": float(query_frame.unknown_reason.eq("energy_ood_rejected").mean()),
                "unavailable_fraction": float(query_frame.assignment_state.eq("unavailable").mean()),
                "accepted_state_counts": {str(k): int(v) for k, v in query_frame.loc[accepted, "assigned_state"].value_counts().items()},
                **_sensitivity(model, calibration, query, query_frame, seed=seed),
            })
        _write_json(fold_root / "metrics.json", result)
        results.append(result)
        frames.append(test_frame)
        print(json.dumps({"event": "fold_complete", "fold": fold,
                          "accepted_fraction": result["test"]["accepted_fraction"],
                          "selective_precision": result["test"]["selective_precision"],
                          "ood_accepted": {r["asset_id"]: r["accepted_fraction"] for r in result["ood"]}}), flush=True)
    all_test = pd.concat(frames, ignore_index=True)
    if all_test.observation_id.duplicated().any():
        raise ValueError("test_rotation_observations_not_unique")
    summary = {
        "object_version": VERSION, "development_design_sha256": design_sha,
        "scientific_qualification": "not_established",
        "locked_assets_opened": False, "sealed_assets_opened": False,
        "source_independence": design["source_independence"],
        "primary_fold": design["primary_fold"], "overall": classification_metrics(all_test),
        "folds": results,
    }
    _write_json(output_root / "summary.json", summary)
    print(json.dumps({"event": "development_complete", "summary_sha256": _sha(output_root / "summary.json")}), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exchange-root", type=Path, required=True)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--split-manifest", type=Path, required=True)
    parser.add_argument("--query-asset", action="append", default=[])
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260911)
    parser.add_argument("--max-iter", type=int, default=200)
    parser.add_argument("--n-jobs", type=int, default=1)
    args = parser.parse_args()
    run_development(
        exchange_root=args.exchange_root, asset_id=args.asset_id,
        split_manifest_path=args.split_manifest, query_asset_ids=args.query_asset,
        output_root=args.output_root, seed=args.seed, max_iter=args.max_iter, n_jobs=args.n_jobs,
    )


if __name__ == "__main__":
    main()
