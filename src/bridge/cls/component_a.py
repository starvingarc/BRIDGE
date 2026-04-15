from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

from bridge.cls.base import build_component_result, save_component_result
from bridge.common.anndata import require_obs_column
from bridge.common.stats import normalize_weights


def _as_1d_float(x) -> np.ndarray:
    x = np.asarray(x).astype(float).ravel()
    return x[np.isfinite(x)]


def compute_component_A(
    bdata,
    adata_ref,
    probs_ref_cal: pd.DataFrame,
    target_class: str,
    batch_key: str = "Sample",
    candidate_flag_prefix: str = "is_candidate_",
    p_mean_prefix: str = "p_mean_",
    ref_label_key: str = "cell_subtype",
    org_mode: str = "candidate",
    alphaA1: float = 0.5,
    alphaA2: float = 0.5,
    ks_method: str = "auto",
    min_cells_per_batch: int = 20,
):
    flag_col = f"{candidate_flag_prefix}{target_class}"
    p_col_org = f"{p_mean_prefix}{target_class}"
    if ref_label_key not in adata_ref.obs:
        raise KeyError(f"[A] ref_label_key '{ref_label_key}' not in adata_ref.obs")
    if target_class not in probs_ref_cal.columns:
        raise KeyError(f"[A] target_class '{target_class}' not in probs_ref_cal.columns")
    require_obs_column(bdata, p_col_org, "A")
    require_obs_column(bdata, batch_key, "A")
    if org_mode not in ("candidate", "all"):
        raise ValueError(f"[A] org_mode must be 'candidate' or 'all', got '{org_mode}'")

    alpha_sum = float(alphaA1 + alphaA2)
    if alpha_sum <= 0:
        raise ValueError("[A] alphaA1+alphaA2 must be > 0")
    alphaA1 = float(alphaA1 / alpha_sum)
    alphaA2 = float(alphaA2 / alpha_sum)

    ref_mask = adata_ref.obs[ref_label_key].astype(str).values == str(target_class)
    n_ref_target = int(ref_mask.sum())
    if n_ref_target == 0:
        raise ValueError(f"[A] No reference target cells found for '{target_class}'")
    ref_ids = adata_ref.obs_names[ref_mask]
    missing_ref = ref_ids.difference(probs_ref_cal.index)
    if len(missing_ref) > 0:
        raise KeyError(f"[A] probs_ref_cal missing {len(missing_ref)} ref cells (index mismatch).")
    p_ref = _as_1d_float(probs_ref_cal.loc[ref_ids, target_class].values)
    pE_bar = float(np.mean(p_ref))

    if org_mode == "candidate":
        require_obs_column(bdata, flag_col, "A")
        org_mask_global = bdata.obs[flag_col].astype(bool).values
        n_used_total = int(org_mask_global.sum())
        if n_used_total == 0:
            raise ValueError(f"[A] No candidate cells found for '{target_class}' (flag {flag_col}).")
    else:
        org_mask_global = np.ones(bdata.n_obs, dtype=bool)
        n_used_total = int(bdata.n_obs)

    rows = []
    obs_use = bdata.obs.loc[bdata.obs_names[org_mask_global], [batch_key, p_col_org]].copy()
    for batch, df_b in obs_use.groupby(batch_key, observed=False):
        n = int(df_b.shape[0])
        if n < int(min_cells_per_batch):
            continue
        p_org = _as_1d_float(df_b[p_col_org].values)
        if p_org.size < 2:
            continue
        pOb_bar = float(np.mean(p_org))
        sA1_b = float(np.clip(1.0 - abs(pOb_bar - pE_bar), 0.0, 1.0))
        try:
            ks = float(ks_2samp(p_org, p_ref, method=ks_method).statistic)
        except TypeError:
            ks = float(ks_2samp(p_org, p_ref).statistic)
        sA2_b = float(np.clip(1.0 - ks, 0.0, 1.0))
        sA_b = float(alphaA1 * sA1_b + alphaA2 * sA2_b)
        rows.append({
            "batch": batch,
            "n_cells": n,
            "p_bar_organoid": pOb_bar,
            "p_bar_reference": pE_bar,
            "KS": ks,
            "sA1_mean": sA1_b,
            "sA2_ks": sA2_b,
            "sA": sA_b,
        })

    score_df = pd.DataFrame(rows).sort_values("sA", ascending=False).reset_index(drop=True)
    if score_df.shape[0] == 0:
        raise ValueError("[A] No batches passed min_cells_per_batch / insufficient cells after filtering.")
    w = normalize_weights(score_df["n_cells"].to_numpy(dtype=float))
    global_score = float(np.nansum(w * score_df["sA"].to_numpy(dtype=float)))
    meta = {
        "target_class": target_class,
        "batch_key": batch_key,
        "org_mode": org_mode,
        "candidate_flag_col": flag_col if org_mode == "candidate" else None,
        "org_prob_col": p_col_org,
        "ref_label_key": ref_label_key,
        "n_ref_target": n_ref_target,
        "n_org_used_total": n_used_total,
        "pE_bar": pE_bar,
        "alphaA1": alphaA1,
        "alphaA2": alphaA2,
        "ks_method": ks_method,
        "min_cells_per_batch": int(min_cells_per_batch),
    }
    return score_df, global_score, meta


def compute_A_and_save(
    bdata,
    adata_ref,
    probs_ref_cal: pd.DataFrame,
    target_class: str,
    outdir: str,
    dataset_id: str,
    batch_key: str = "Sample",
    candidate_flag_prefix: str = "is_candidate_",
    p_mean_prefix: str = "p_mean_",
    ref_label_key: str = "cell_subtype",
    org_mode: str = "candidate",
    alphaA1: float = 0.5,
    alphaA2: float = 0.5,
    ks_method: str = "auto",
    min_cells_per_batch: int = 20,
    write_back_uns: bool = True,
):
    score_df, global_score, meta = compute_component_A(
        bdata=bdata,
        adata_ref=adata_ref,
        probs_ref_cal=probs_ref_cal,
        target_class=target_class,
        batch_key=batch_key,
        candidate_flag_prefix=candidate_flag_prefix,
        p_mean_prefix=p_mean_prefix,
        ref_label_key=ref_label_key,
        org_mode=org_mode,
        alphaA1=alphaA1,
        alphaA2=alphaA2,
        ks_method=ks_method,
        min_cells_per_batch=min_cells_per_batch,
    )
    result = build_component_result("A", score_df, global_score, meta)
    owner = bdata if write_back_uns else None
    return save_component_result(result, outdir=outdir, dataset_id=dataset_id, owner_adata=owner)
