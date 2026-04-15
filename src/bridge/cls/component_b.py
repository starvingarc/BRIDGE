from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse

from bridge.cls.base import build_component_result, save_component_result
from bridge.common.anndata import align_by_common_varnames, require_obs_column
from bridge.common.stats import normalize_weights, safe_pearson


def _mean_vector(X) -> np.ndarray:
    if sparse.issparse(X):
        return np.asarray(X.mean(axis=0)).ravel()
    return np.asarray(X).mean(axis=0).ravel()


def compute_component_B(
    bdata,
    adata_ref,
    target_class: str,
    batch_key: str = "Sample",
    candidate_flag_prefix: str = "is_candidate_",
    ref_label_key: str = "cell_subtype",
    layer: str | None = None,
    min_cells_per_batch: int = 20,
    standardize_to_unit: bool = True,
):
    flag_col = f"{candidate_flag_prefix}{target_class}"
    if ref_label_key not in adata_ref.obs:
        raise KeyError(f"[B] ref_label_key '{ref_label_key}' not in adata_ref.obs")
    require_obs_column(bdata, flag_col, "B")
    require_obs_column(bdata, batch_key, "B")
    if layer is not None:
        if layer not in adata_ref.layers:
            raise KeyError(f"[B] layer '{layer}' not in adata_ref.layers")
        if layer not in bdata.layers:
            raise KeyError(f"[B] layer '{layer}' not in bdata.layers")

    adata_ref_al, bdata_al, common_genes = align_by_common_varnames(adata_ref, bdata, "B")
    ref_mask = adata_ref_al.obs[ref_label_key].astype(str).values == str(target_class)
    n_ref_target = int(ref_mask.sum())
    if n_ref_target == 0:
        raise ValueError(f"[B] No reference cells for target_class '{target_class}'")

    X_ref = adata_ref_al[ref_mask].layers[layer] if layer else adata_ref_al[ref_mask].X
    ref_bulk = _mean_vector(X_ref)
    cand_mask = bdata_al.obs[flag_col].astype(bool).values
    n_cand_total = int(cand_mask.sum())
    if n_cand_total == 0:
        raise ValueError(f"[B] No candidate cells found in organoid for '{target_class}' (flag {flag_col}).")

    bdata_cand = bdata_al[bdata_al.obs_names[cand_mask]].copy()
    rows = []
    for batch, idx in bdata_cand.obs.groupby(batch_key, observed=False).groups.items():
        n = len(idx)
        if n < min_cells_per_batch:
            continue
        X_b = bdata_cand[idx].layers[layer] if layer else bdata_cand[idx].X
        bulk_b = _mean_vector(X_b)
        r = safe_pearson(bulk_b, ref_bulk)
        sB = (r + 1.0) / 2.0 if (standardize_to_unit and np.isfinite(r)) else r
        if standardize_to_unit and np.isfinite(sB):
            sB = float(np.clip(sB, 0.0, 1.0))
        rows.append({"batch": batch, "n_cells": n, "r": r, "sB": sB})

    score_df = pd.DataFrame(rows)
    if score_df.shape[0] == 0:
        raise ValueError(f"[B] No batches passed min_cells_per_batch={min_cells_per_batch} among candidate cells.")
    score_df = score_df.sort_values("sB", ascending=False).reset_index(drop=True)
    w = normalize_weights(score_df["n_cells"].to_numpy(dtype=float))
    global_score = float(np.nansum(w * score_df["sB"].to_numpy(dtype=float)))
    meta = {
        "target_class": target_class,
        "batch_key": batch_key,
        "candidate_flag_col": flag_col,
        "ref_label_key": ref_label_key,
        "layer": layer,
        "min_cells_per_batch": int(min_cells_per_batch),
        "standardize_to_unit": bool(standardize_to_unit),
        "n_ref_target": n_ref_target,
        "n_cand_total": n_cand_total,
        "n_genes_used": int(len(common_genes)),
    }
    return score_df, global_score, meta


def compute_B_and_save(
    bdata,
    adata_ref,
    target_class: str,
    outdir: str,
    dataset_id: str,
    batch_key: str = "Sample",
    candidate_flag_prefix: str = "is_candidate_",
    ref_label_key: str = "cell_subtype",
    layer: str | None = None,
    min_cells_per_batch: int = 20,
    standardize_to_unit: bool = True,
    write_back_uns: bool = True,
):
    score_df, global_score, meta = compute_component_B(
        bdata=bdata,
        adata_ref=adata_ref,
        target_class=target_class,
        batch_key=batch_key,
        candidate_flag_prefix=candidate_flag_prefix,
        ref_label_key=ref_label_key,
        layer=layer,
        min_cells_per_batch=min_cells_per_batch,
        standardize_to_unit=standardize_to_unit,
    )
    result = build_component_result("B", score_df, global_score, meta)
    owner = bdata if write_back_uns else None
    return save_component_result(result, outdir=outdir, dataset_id=dataset_id, owner_adata=owner)
