from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from bridge.prescreen.runtime import (
    predict_soft,
    prepare_and_load_scanvi_query_model,
    set_prescreen_seed,
    train_query_model,
)


PRESCREEN_COLUMN = "step1_prescreen"
RG_CANDIDATE = "RG_candidate"
NON_RG = "non_RG"


@dataclass(frozen=True)
class PrescreenResult:
    adata: Any
    probabilities: pd.DataFrame
    annotations: pd.DataFrame
    summary: dict[str, Any]
    output_paths: dict[str, str]


def _obs_index(adata) -> pd.Index:
    return pd.Index(adata.obs_names)


def _probability_frame(pred_prob, obs_index: pd.Index) -> pd.DataFrame:
    if isinstance(pred_prob, pd.DataFrame):
        probs = pred_prob.copy()
    else:
        probs = pd.DataFrame(pred_prob, index=obs_index)
    if probs.shape[1] == 0:
        raise ValueError("Step1 probability table must contain at least one predicted class column.")
    return probs.reindex(index=obs_index).fillna(0.0)


def build_prescreen_annotations(adata, pred_prob, rg_label: str = "Radial Glia") -> pd.DataFrame:
    obs_index = _obs_index(adata)
    probs = _probability_frame(pred_prob, obs_index)
    pred_cell_type = probs.idxmax(axis=1).astype(str)
    pred_maxp = probs.max(axis=1).astype(float)
    if rg_label in probs.columns:
        rg_prob = probs[rg_label].astype(float)
    else:
        rg_prob = pd.Series(0.0, index=obs_index, dtype=float)
    is_rg = pred_cell_type.eq(rg_label)
    return pd.DataFrame(
        {
            "step1_pred_cell_type": pred_cell_type.astype(str),
            "step1_pred_maxp": pred_maxp,
            "step1_rg_prob": rg_prob,
            "step1_is_rg": is_rg.astype(bool),
            PRESCREEN_COLUMN: np.where(is_rg, RG_CANDIDATE, NON_RG),
        },
        index=obs_index,
    )


def write_prescreen_outputs_to_obs(adata, pred_prob, rg_label: str = "Radial Glia") -> pd.DataFrame:
    annotations = build_prescreen_annotations(adata, pred_prob, rg_label=rg_label)
    for column in annotations.columns:
        adata.obs[column] = annotations[column].loc[adata.obs_names].values
    return annotations


def build_prescreen_summary(
    adata,
    *,
    rg_label: str = "Radial Glia",
    train_query: bool = False,
    max_epochs: int = 0,
    output_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    if PRESCREEN_COLUMN not in adata.obs:
        raise KeyError(f"Step1 summary requires '{PRESCREEN_COLUMN}' in adata.obs.")
    query_count = int(getattr(adata, "n_obs", len(adata.obs)))
    prescreen_counts = adata.obs[PRESCREEN_COLUMN].astype(str).value_counts().to_dict()
    predicted_label_counts = adata.obs["step1_pred_cell_type"].astype(str).value_counts().to_dict()
    rg_count = int(prescreen_counts.get(RG_CANDIDATE, 0))
    non_rg_count = int(prescreen_counts.get(NON_RG, 0))
    return {
        "query_count": query_count,
        "rg_label": rg_label,
        "rg_candidate_count": rg_count,
        "non_rg_count": non_rg_count,
        "rg_candidate_fraction": float(rg_count / query_count) if query_count else 0.0,
        "prescreen_counts": {str(k): int(v) for k, v in prescreen_counts.items()},
        "predicted_label_counts": {str(k): int(v) for k, v in predicted_label_counts.items()},
        "training": {
            "train_query": bool(train_query),
            "max_epochs": int(max_epochs),
        },
        "outputs": {str(k): str(v) for k, v in (output_paths or {}).items()},
    }


def _default_output_paths(output_dir: str | Path, prefix: str) -> dict[str, Path]:
    outdir = Path(output_dir)
    return {
        "prescreened_h5ad": outdir / f"{prefix}.step1_prescreened.h5ad",
        "rg_candidates_h5ad": outdir / f"{prefix}.step1_rg_candidates.h5ad",
        "probs_csv": outdir / f"{prefix}.step1_scanvi_probs.csv",
        "summary_json": outdir / f"{prefix}.step1_summary.json",
    }


def save_prescreen_outputs(
    adata,
    probabilities: pd.DataFrame,
    summary: dict[str, Any],
    *,
    output_dir: str | Path,
    prefix: str,
) -> dict[str, str]:
    output_paths = _default_output_paths(output_dir, prefix)
    output_paths["prescreened_h5ad"].parent.mkdir(parents=True, exist_ok=True)
    probabilities.to_csv(output_paths["probs_csv"])
    adata.write_h5ad(output_paths["prescreened_h5ad"])
    rg_mask = adata.obs[PRESCREEN_COLUMN].astype(str).eq(RG_CANDIDATE).values
    adata[rg_mask].copy().write_h5ad(output_paths["rg_candidates_h5ad"])

    import json

    payload_paths = {name: str(path) for name, path in output_paths.items()}
    summary = dict(summary)
    summary["outputs"] = payload_paths
    output_paths["summary_json"].write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return payload_paths


def prescreen(
    adata,
    ref_model_dir: str | Path,
    *,
    rg_label: str = "Radial Glia",
    counts_layer: str = "counts",
    train_query: bool = False,
    max_epochs: int = 0,
    plan_kwargs: dict[str, Any] | None = None,
    early_stopping: bool = False,
    early_stopping_patience: int = 10,
    inplace_subset_query_vars: bool = True,
    set_X_to_counts: bool = True,
    prediction_batch_size: int = 1024,
    seed: int = 0,
    output_dir: str | Path | None = None,
    prefix: str = "bridge",
) -> PrescreenResult:
    """Run Step1 whole-brain prescreening on an AnnData object.

    This function is designed for notebooks. It mirrors the validated Step1 notebook strategy:
    prepare scANVI query data, optionally train query adaptation, predict soft labels, and
    annotate RG candidates.
    """
    if train_query and max_epochs <= 0:
        raise ValueError("max_epochs must be greater than 0 when train_query=True.")

    set_prescreen_seed(seed)
    scanvi_query, query_adata = prepare_and_load_scanvi_query_model(
        ref_model_dir=str(ref_model_dir),
        bdata=adata,
        counts_layer=counts_layer,
        set_X_to_counts=set_X_to_counts,
        inplace_subset_query_vars=inplace_subset_query_vars,
    )
    if train_query:
        train_query_model(
            scanvi_query,
            max_epochs=max_epochs,
            plan_kwargs=plan_kwargs,
            early_stopping=early_stopping,
            early_stopping_patience=early_stopping_patience,
        )

    probabilities = predict_soft(scanvi_query, query_adata, batch_size=prediction_batch_size)
    annotations = write_prescreen_outputs_to_obs(query_adata, probabilities, rg_label=rg_label)
    summary = build_prescreen_summary(
        query_adata,
        rg_label=rg_label,
        train_query=train_query,
        max_epochs=max_epochs,
    )
    output_paths: dict[str, str] = {}
    if output_dir is not None:
        output_paths = save_prescreen_outputs(
            query_adata,
            probabilities,
            summary,
            output_dir=output_dir,
            prefix=prefix,
        )
        summary = dict(summary)
        summary["outputs"] = output_paths

    return PrescreenResult(
        adata=query_adata,
        probabilities=probabilities,
        annotations=annotations,
        summary=summary,
        output_paths=output_paths,
    )
