from __future__ import annotations

from pathlib import Path
from typing import Any

from bridge.identity.adapters import write_identity_outputs_to_obs
from bridge.identity.calibration import build_identity_probabilities
from bridge.identity.results import IdentityResult, IdentityThresholds, IdentityUncertainty
from bridge.identity.runtime import (
    load_scanvi_ref_model,
    predict_soft,
    prepare_and_load_scanvi_query_model,
    set_identity_seed,
    train_query_model,
)
from bridge.identity.selection import calibrate_threshold_from_ref, estimate_u_from_std, select_target_candidates
from bridge.identity.serialization import save_identity_results
from bridge.identity.uncertainty import ensemble_mean_std, predictive_entropy_norm, run_query_ensemble


def assess_identity_probabilities(
    probs_ref_cal,
    probs_query_cal,
    probs_query_ensemble,
    y_ref_series,
    target_class: str,
    entropy_source=None,
    target_precision: float = 0.8,
    std_quantile: float = 75.0,
    u_min: float = 0.005,
    entropy_threshold: float = 0.8,
    obs_index=None,
):
    mean_org, std_org = ensemble_mean_std(probs_query_ensemble)
    entropy_source = probs_query_cal if entropy_source is None else entropy_source
    entropy_norm = predictive_entropy_norm(entropy_source)
    threshold_t = calibrate_threshold_from_ref(
        probs_ref_cal[target_class],
        y_ref_series,
        target_class=target_class,
        target_precision=target_precision,
    )
    threshold_u, u_raw = estimate_u_from_std(std_org[target_class], q=std_quantile, u_min=u_min)
    thresholds = IdentityThresholds(
        threshold_t=threshold_t,
        threshold_u=threshold_u,
        threshold_v=entropy_threshold,
        u_raw=u_raw,
        target_precision=target_precision,
    )
    uncertainty = IdentityUncertainty(
        mean_prob=mean_org,
        std_prob=std_org,
        entropy_norm=entropy_norm,
        ensemble_size=len(probs_query_ensemble),
        seed_base=0,
    )
    selection = select_target_candidates(
        mean_org=mean_org,
        std_org=std_org,
        entropy_norm=entropy_norm,
        target_class=target_class,
        thresholds=thresholds,
        obs_index=mean_org.index if obs_index is None else obs_index,
    )
    return uncertainty, selection


def _identity_output_paths(output_dir: str | Path, prefix: str) -> dict[str, Path]:
    outdir = Path(output_dir)
    return {
        "thresholds_json": outdir / f"{prefix}.thresholds.json",
        "bdata_step2_h5ad": outdir / f"{prefix}.bdata_step2.h5ad",
        "adata_ref_step2_h5ad": outdir / f"{prefix}.adata_ref_step2.h5ad",
        "probs_ref_cal_csv": outdir / f"{prefix}.probs_ref_cal.csv",
        "probs_query_cal_csv": outdir / f"{prefix}.probs_query_cal.csv",
        "mean_org_csv": outdir / f"{prefix}.mean_org.csv",
        "std_org_csv": outdir / f"{prefix}.std_org.csv",
        "hnorm_csv": outdir / f"{prefix}.Hnorm.csv",
    }


def build_identity_summary(
    bdata,
    *,
    target_class: str,
    candidate_mask,
    thresholds: IdentityThresholds,
    max_epochs: int,
    ensemble_size: int,
    seed: int,
    output_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    query_count = int(getattr(bdata, "n_obs", len(bdata.obs)))
    mask = candidate_mask.reindex(bdata.obs_names).fillna(False).astype(bool)
    candidate_count = int(mask.sum())
    return {
        "query_count": query_count,
        "target_class": str(target_class),
        "candidate_count": candidate_count,
        "non_candidate_count": int(query_count - candidate_count),
        "candidate_fraction": float(candidate_count / query_count) if query_count else 0.0,
        "thresholds": {
            "t": float(thresholds.threshold_t),
            "u": float(thresholds.threshold_u),
            "u_raw": float(thresholds.u_raw),
            "v": float(thresholds.threshold_v),
            "target_precision": float(thresholds.target_precision),
        },
        "training": {
            "max_epochs": int(max_epochs),
            "ensemble_size": int(ensemble_size),
            "seed": int(seed),
        },
        "outputs": {str(k): str(v) for k, v in (output_paths or {}).items()},
    }


def identify(
    bdata,
    adata_ref,
    *,
    ref_model_dir: str | Path,
    target_class: str,
    ref_label_key: str = "cell_subtype",
    counts_layer: str = "counts",
    max_epochs: int = 100,
    ensemble_size: int = 5,
    target_precision: float = 0.8,
    std_quantile: float = 75.0,
    u_min: float = 0.005,
    entropy_threshold: float = 0.8,
    plan_kwargs: dict[str, Any] | None = None,
    early_stopping: bool = False,
    early_stopping_patience: int = 10,
    inplace_subset_query_vars: bool = True,
    set_X_to_counts: bool = True,
    seed: int = 0,
    output_dir: str | Path | None = None,
    prefix: str = "bridge",
) -> IdentityResult:
    """Run target identity assessment on AnnData objects.

    This notebook-first entrypoint preserves the Step2 artifact contract while avoiding
    YAML/workflow orchestration. It expects a Step1 RG candidate query object and a
    target-specific reference object that match the provided scANVI reference model.
    """
    if not str(target_class).strip():
        raise ValueError("target_class must be a non-empty string.")

    if plan_kwargs is None:
        plan_kwargs = {"weight_decay": 0.0}

    set_identity_seed(seed)
    scanvi_ref, adata_ref_runtime = load_scanvi_ref_model(
        ref_model_dir=str(ref_model_dir),
        adata=adata_ref,
        counts_layer=counts_layer,
        set_X_to_counts=set_X_to_counts,
    )
    probs_ref_raw = predict_soft(scanvi_ref, adata_ref_runtime)

    scanvi_query, bdata_q = prepare_and_load_scanvi_query_model(
        ref_model_dir=str(ref_model_dir),
        bdata=bdata,
        counts_layer=counts_layer,
        set_X_to_counts=set_X_to_counts,
        inplace_subset_query_vars=inplace_subset_query_vars,
    )
    train_query_model(
        scanvi_query,
        max_epochs=max_epochs,
        plan_kwargs=plan_kwargs,
        early_stopping=early_stopping,
        early_stopping_patience=early_stopping_patience,
    )
    probs_query_raw = predict_soft(scanvi_query, bdata_q)

    y_ref_series = adata_ref.obs[ref_label_key].astype(str)
    probabilities = build_identity_probabilities(
        probs_ref_raw=probs_ref_raw,
        probs_query_raw=probs_query_raw,
        y_ref_series=y_ref_series,
        target_class=target_class,
    )

    ensemble_prob_list = run_query_ensemble(
        ref_model_dir=str(ref_model_dir),
        bdata=bdata_q,
        calibrators=probabilities.calibrators,
        class_names=probabilities.class_names,
        M=ensemble_size,
        max_epochs=max_epochs,
        plan_kwargs=plan_kwargs,
        early_stopping=early_stopping,
        early_stopping_patience=early_stopping_patience,
        seed_base=seed,
    )
    if not ensemble_prob_list:
        raise RuntimeError("identity assessment failed because the query ensemble produced no successful runs.")

    uncertainty, selection = assess_identity_probabilities(
        probs_ref_cal=probabilities.probs_ref_cal,
        probs_query_cal=probabilities.probs_query_cal,
        probs_query_ensemble=ensemble_prob_list,
        y_ref_series=y_ref_series,
        target_class=target_class,
        target_precision=target_precision,
        std_quantile=std_quantile,
        u_min=u_min,
        entropy_threshold=entropy_threshold,
        obs_index=bdata_q.obs_names,
    )

    write_identity_outputs_to_obs(
        bdata_q,
        target_class,
        uncertainty.mean_prob,
        uncertainty.std_prob,
        uncertainty.entropy_norm,
        selection.candidate_mask,
        probs_query_cal=probabilities.probs_query_cal,
    )

    output_paths: dict[str, str] = {}
    if output_dir is not None:
        save_identity_results(
            outdir=str(output_dir),
            prefix=prefix,
            bdata=bdata_q,
            adata_ref=adata_ref,
            probs_ref_cal=probabilities.probs_ref_cal,
            probs_query_cal=probabilities.probs_query_cal,
            mean_org=uncertainty.mean_prob,
            std_org=uncertainty.std_prob,
            Hnorm=uncertainty.entropy_norm,
            t=selection.thresholds.threshold_t,
            u=selection.thresholds.threshold_u,
            u_raw=selection.thresholds.u_raw,
            v=selection.thresholds.threshold_v,
        )
        output_paths = {name: str(path) for name, path in _identity_output_paths(output_dir, prefix).items()}

    summary = build_identity_summary(
        bdata_q,
        target_class=target_class,
        candidate_mask=selection.candidate_mask,
        thresholds=selection.thresholds,
        max_epochs=max_epochs,
        ensemble_size=ensemble_size,
        seed=seed,
        output_paths=output_paths,
    )

    return IdentityResult(
        bdata=bdata_q,
        adata_ref=adata_ref,
        probabilities=probabilities,
        uncertainty=uncertainty,
        selection=selection,
        summary=summary,
        output_paths=output_paths,
    )
