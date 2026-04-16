from __future__ import annotations

from pathlib import Path

from bridge.identity.adapters import write_identity_outputs_to_obs
from bridge.identity.api import run_identity_assessment
from bridge.identity.calibration import build_identity_probabilities
from bridge.identity.runtime import (
    load_scanvi_ref_model,
    predict_soft,
    prepare_and_load_scanvi_query_model,
    set_identity_seed,
    train_query_model,
)
from bridge.identity.serialization import save_identity_results
from bridge.identity.uncertainty import run_query_ensemble
from bridge.workflows.config import BridgeRunConfig, WorkflowValidationError


def _identity_output_paths(config: BridgeRunConfig) -> dict[str, Path]:
    outdir = config.paths.identity_output_dir
    prefix = config.dataset.prefix
    return {
        "outdir": outdir,
        "thresholds_json": outdir / f"{prefix}.thresholds.json",
        "bdata_step2_h5ad": outdir / f"{prefix}.bdata_step2.h5ad",
        "adata_ref_step2_h5ad": outdir / f"{prefix}.adata_ref_step2.h5ad",
        "probs_ref_cal_csv": outdir / f"{prefix}.probs_ref_cal.csv",
        "probs_query_cal_csv": outdir / f"{prefix}.probs_query_cal.csv",
        "mean_org_csv": outdir / f"{prefix}.mean_org.csv",
        "std_org_csv": outdir / f"{prefix}.std_org.csv",
        "hnorm_csv": outdir / f"{prefix}.Hnorm.csv",
    }


def _validate_identity_inputs(config: BridgeRunConfig) -> None:
    required = {
        "paths.reference_h5ad": config.paths.reference_h5ad,
        "paths.query_h5ad": config.paths.query_h5ad,
        "paths.ref_model_dir": config.paths.ref_model_dir,
    }
    missing = [name for name, path in required.items() if path is None]
    if missing:
        raise WorkflowValidationError(f"Missing required identity paths: {', '.join(missing)}")
    not_found = [name for name, path in required.items() if not path.exists()]
    if not_found:
        raise WorkflowValidationError(f"Identity workflow inputs not found: {', '.join(not_found)}")


def build_identity_run_plan(config: BridgeRunConfig) -> dict:
    _validate_identity_inputs(config)
    outputs = {name: str(path) for name, path in _identity_output_paths(config).items() if name != "outdir"}
    return {
        "workflow": "identity",
        "dataset_id": config.dataset.id,
        "dataset_prefix": config.dataset.prefix,
        "target_class": config.identity.target_class,
        "inputs": {
            "reference_h5ad": str(config.paths.reference_h5ad),
            "query_h5ad": str(config.paths.query_h5ad),
            "ref_model_dir": str(config.paths.ref_model_dir),
        },
        "outputs": outputs,
        "checks": [
            "reference/query/model paths resolved",
            "identity configuration validated",
            "step2 output paths determined",
        ],
    }


def run_identity_workflow(config: BridgeRunConfig, dry_run: bool = False) -> dict:
    plan = build_identity_run_plan(config)
    if dry_run:
        return plan

    import scanpy as sc

    set_identity_seed(config.runtime.seed)
    adata_ref = sc.read_h5ad(config.paths.reference_h5ad)
    bdata = sc.read_h5ad(config.paths.query_h5ad)

    scanvi_ref, adata_ref_runtime = load_scanvi_ref_model(
        ref_model_dir=str(config.paths.ref_model_dir),
        adata=adata_ref,
        counts_layer=config.identity.counts_layer,
        set_X_to_counts=config.identity.set_X_to_counts,
    )
    probs_ref_raw = predict_soft(scanvi_ref, adata_ref_runtime)

    scanvi_query, bdata_q = prepare_and_load_scanvi_query_model(
        ref_model_dir=str(config.paths.ref_model_dir),
        bdata=bdata,
        counts_layer=config.identity.counts_layer,
        set_X_to_counts=config.identity.set_X_to_counts,
        inplace_subset_query_vars=config.identity.inplace_subset_query_vars,
    )
    train_query_model(
        scanvi_query,
        max_epochs=config.identity.max_epochs,
        plan_kwargs=config.identity.plan_kwargs,
        early_stopping=config.identity.early_stopping,
        early_stopping_patience=config.identity.early_stopping_patience,
    )
    probs_query_raw = predict_soft(scanvi_query, bdata_q)

    probabilities = build_identity_probabilities(
        probs_ref_raw=probs_ref_raw,
        probs_query_raw=probs_query_raw,
        y_ref_series=adata_ref.obs[config.identity.ref_label_key].astype(str),
        target_class=config.identity.target_class,
    )

    ensemble_prob_list = run_query_ensemble(
        ref_model_dir=str(config.paths.ref_model_dir),
        bdata=bdata_q,
        calibrators=probabilities.calibrators,
        class_names=probabilities.class_names,
        M=config.identity.ensemble_size,
        max_epochs=config.identity.max_epochs,
        plan_kwargs=config.identity.plan_kwargs,
        early_stopping=config.identity.early_stopping,
        early_stopping_patience=config.identity.early_stopping_patience,
        seed_base=config.runtime.seed,
    )
    if not ensemble_prob_list:
        raise WorkflowValidationError("Identity workflow failed because the query ensemble produced no successful runs.")

    uncertainty, selection = run_identity_assessment(
        probs_ref_cal=probabilities.probs_ref_cal,
        probs_query_cal=probabilities.probs_query_cal,
        probs_query_ensemble=ensemble_prob_list,
        y_ref_series=adata_ref.obs[config.identity.ref_label_key].astype(str),
        target_class=config.identity.target_class,
        target_precision=config.identity.target_precision,
        std_quantile=config.identity.std_quantile,
        u_min=config.identity.u_min,
        entropy_threshold=config.identity.entropy_threshold,
        obs_index=bdata_q.obs_names,
    )

    write_identity_outputs_to_obs(
        bdata_q,
        config.identity.target_class,
        uncertainty.mean_prob,
        uncertainty.std_prob,
        uncertainty.entropy_norm,
        selection.candidate_mask,
        probs_query_cal=probabilities.probs_query_cal,
    )
    save_identity_results(
        outdir=str(config.paths.identity_output_dir),
        prefix=config.dataset.prefix,
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

    return {
        "workflow": "identity",
        "status": "completed",
        "dataset_id": config.dataset.id,
        "dataset_prefix": config.dataset.prefix,
        "output_dir": str(config.paths.identity_output_dir),
        "target_class": config.identity.target_class,
        "candidate_count": int(selection.candidate_mask.sum()),
        "outputs": {name: str(path) for name, path in _identity_output_paths(config).items() if name != "outdir"},
    }
