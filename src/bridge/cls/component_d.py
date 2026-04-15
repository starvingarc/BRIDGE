from __future__ import annotations

import os
import warnings

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

from bridge.cls.base import build_component_result, save_component_result
from bridge.common.anndata import require_obs_column, require_obsm_key
from bridge.common.stats import normalize_weights

try:
    import scvi
    from scvi.model import SCANVI
except Exception:
    scvi = None
    SCANVI = None


def ensure_scanvi_embedding(
    adata_ref,
    bdata,
    ref_model_dir: str,
    emb_key: str = "X_scanvi",
    counts_layer: str = "counts",
    set_X_to_counts: bool = True,
    inplace_subset_query_vars: bool = True,
    train_query: bool = False,
    query_train_kwargs: dict | None = None,
):
    if emb_key in adata_ref.obsm and emb_key in bdata.obsm:
        return adata_ref, bdata
    if scvi is None or SCANVI is None:
        raise ImportError("[D] scvi-tools is required to compute embeddings when obsm is missing.")
    if ref_model_dir is None or (not os.path.exists(ref_model_dir)):
        raise ValueError(f"[D] ref_model_dir not found: {ref_model_dir}")

    ad_ref = adata_ref.copy()
    bd = bdata.copy()
    if set_X_to_counts:
        if counts_layer not in ad_ref.layers or counts_layer not in bd.layers:
            raise KeyError(f"[D] counts_layer '{counts_layer}' not found in AnnData layers")
        ad_ref.X = ad_ref.layers[counts_layer].copy()
        bd.X = bd.layers[counts_layer].copy()

    scanvi_ref = SCANVI.load(ref_model_dir, adata=ad_ref)
    SCANVI.prepare_query_anndata(bd, ref_model_dir)
    scanvi_q = SCANVI.load_query_data(
        adata=bd,
        reference_model=ref_model_dir,
        inplace_subset_query_vars=bool(inplace_subset_query_vars),
    )
    if train_query:
        kw = dict(query_train_kwargs or {})
        kw.setdefault("max_epochs", 100)
        kw.setdefault("plan_kwargs", {"weight_decay": 0.0})
        kw.setdefault("early_stopping", False)
        scanvi_q.train(**kw)

    ad_ref.obsm[emb_key] = scanvi_ref.get_latent_representation(ad_ref)
    bd.obsm[emb_key] = scanvi_q.get_latent_representation(bd)
    return ad_ref, bd


def compute_component_D(
    bdata,
    adata_ref,
    target_class: str,
    emb_key: str = "X_scanvi",
    batch_key: str = "Sample",
    candidate_flag_prefix: str = "is_candidate_",
    ref_label_key: str = "cell_subtype",
    pred_label_col: str | None = "pred_top1",
    k_query: int = 30,
    k_ref: int = 50,
    k_ref_for_dist: int = 20,
    min_cells_per_batch: int = 10,
    n_jobs: int = 4,
    write_to_obs: bool = True,
    return_details: bool = False,
):
    cand_col = f"{candidate_flag_prefix}{target_class}"
    require_obs_column(bdata, cand_col, "D")
    require_obs_column(bdata, batch_key, "D")
    if ref_label_key not in adata_ref.obs:
        raise KeyError(f"[D] ref_label_key '{ref_label_key}' not found in adata_ref.obs")
    require_obsm_key(bdata, emb_key, "D")
    require_obsm_key(adata_ref, emb_key, "D")

    emb_q = np.asarray(bdata.obsm[emb_key])
    emb_ref = np.asarray(adata_ref.obsm[emb_key])
    ref_target_mask = adata_ref.obs[ref_label_key].astype(str).values == str(target_class)
    n_ref_total = int(emb_ref.shape[0])
    n_ref_target = int(ref_target_mask.sum())
    if n_ref_target == 0:
        raise ValueError(f"[D] No reference target cells found for '{target_class}' in adata_ref.")
    prop_ref_target = n_ref_target / max(1, n_ref_total)

    cand_mask = bdata.obs[cand_col].astype(bool).values
    cand_local_idx = np.where(cand_mask)[0]
    n_cand = int(cand_local_idx.size)
    if n_cand == 0:
        raise ValueError(f"[D] No candidate cells found in bdata for '{target_class}'.")

    kq_use = min(int(k_query) + 1, emb_q.shape[0])
    nn_q = NearestNeighbors(n_neighbors=kq_use, n_jobs=n_jobs).fit(emb_q)
    neigh_q = nn_q.kneighbors(emb_q[cand_local_idx], return_distance=False)
    per_cand_frac = np.zeros(n_cand, dtype=float)
    per_label_agree = np.full(n_cand, np.nan, dtype=float)

    have_pred = (pred_label_col is not None) and (pred_label_col in bdata.obs.columns)
    if have_pred:
        pred_arr = bdata.obs[pred_label_col].astype(str).values

    for i_row, nbrs in enumerate(neigh_q):
        self_idx = int(cand_local_idx[i_row])
        nbrs_filtered = [int(x) for x in nbrs if int(x) != self_idx][: int(k_query)]
        denom = len(nbrs_filtered) if len(nbrs_filtered) > 0 else 1
        n_cand_neighbors = sum(1 for x in nbrs_filtered if cand_mask[int(x)])
        per_cand_frac[i_row] = n_cand_neighbors / denom
        if have_pred:
            my_label = pred_arr[self_idx]
            agree = sum(1 for x in nbrs_filtered if pred_arr[int(x)] == my_label)
            per_label_agree[i_row] = agree / denom

    perD_query = np.array(per_cand_frac, dtype=float)
    if have_pred:
        perD_query = np.where(np.isnan(per_label_agree), per_cand_frac, 0.5 * per_cand_frac + 0.5 * per_label_agree)

    kr_use = min(int(k_ref), emb_ref.shape[0])
    nn_ref = NearestNeighbors(n_neighbors=kr_use, n_jobs=n_jobs).fit(emb_ref)
    dists_ref, idxs_ref = nn_ref.kneighbors(emb_q[cand_local_idx], return_distance=True)
    ref_flags = ref_target_mask[idxs_ref]
    per_ref_frac = np.sum(ref_flags, axis=1) / max(1, idxs_ref.shape[1])
    per_mean_dist_to_kref = np.nanmean(dists_ref, axis=1)

    emb_ref_target = emb_ref[ref_target_mask]
    if emb_ref_target.shape[0] <= 1:
        mean_ref_internal = np.nan
        warnings.warn("[D] Too few reference target cells to compute internal distance baseline.")
    else:
        k_internal = min(int(k_ref_for_dist) + 1, emb_ref_target.shape[0])
        nn_rt = NearestNeighbors(n_neighbors=k_internal, n_jobs=n_jobs).fit(emb_ref_target)
        d_rt, _ = nn_rt.kneighbors(emb_ref_target, return_distance=True)
        if d_rt.shape[1] > 1:
            mean_ref_internal = float(np.nanmean(d_rt[:, 1:k_internal]))
        else:
            mean_ref_internal = float(np.nanmean(d_rt))

    per_dist_score = np.full(per_mean_dist_to_kref.shape, np.nan, dtype=float)
    if (not np.isnan(mean_ref_internal)) and (mean_ref_internal > 0):
        ratio = per_mean_dist_to_kref / float(mean_ref_internal)
        per_dist_score = 1.0 / (1.0 + ratio)
    perD_ref = np.where(np.isnan(per_dist_score), per_ref_frac, 0.5 * per_ref_frac + 0.5 * per_dist_score)
    perD = np.sqrt(np.nan_to_num(perD_query, nan=0.0) * np.nan_to_num(perD_ref, nan=0.0))

    per_cell_df = pd.DataFrame(
        {
            "obs_name": bdata.obs_names[cand_local_idx],
            "perD_cand_frac": per_cand_frac,
            "perD_label_agree": per_label_agree,
            "perD_query": perD_query,
            "perD_ref_frac": per_ref_frac,
            "perD_ref_mean_dist": per_mean_dist_to_kref,
            "perD_dist_score": per_dist_score,
            "perD_ref": perD_ref,
            "perD": perD,
        }
    ).set_index("obs_name")

    if write_to_obs:
        cols = list(per_cell_df.columns)
        for col in cols:
            bdata.obs[col] = np.nan
        bdata.obs.loc[per_cell_df.index, cols] = per_cell_df[cols]

    rows = []
    for batch, df_b in bdata.obs[cand_mask].groupby(batch_key, observed=False):
        obs_in_b = df_b.index.intersection(per_cell_df.index)
        n_in_b = int(len(obs_in_b))
        if n_in_b < int(min_cells_per_batch):
            continue
        rows.append(
            {
                "batch": batch,
                "n_candidate": n_in_b,
                "sD_query": float(per_cell_df.loc[obs_in_b, "perD_query"].mean()),
                "sD_ref": float(per_cell_df.loc[obs_in_b, "perD_ref"].mean()),
                "sD": float(per_cell_df.loc[obs_in_b, "perD"].mean()),
                "sD_frac_ref_gt_bg": float((per_cell_df.loc[obs_in_b, "perD_ref_frac"] > prop_ref_target).sum() / n_in_b),
            }
        )

    score_df = pd.DataFrame(rows)
    if score_df.shape[0] == 0:
        raise ValueError("[D] No batches passed min_cells_per_batch threshold.")
    score_df = score_df.sort_values("sD", ascending=False).reset_index(drop=True)
    w = normalize_weights(score_df["n_candidate"].to_numpy(dtype=float))
    global_score = float(np.nansum(w * score_df["sD"].to_numpy(dtype=float)))

    diagnostics = {
        "per_cell": per_cell_df,
        "n_ref_total": n_ref_total,
        "n_ref_target": n_ref_target,
        "prop_ref_target": prop_ref_target,
        "mean_ref_internal_dist": mean_ref_internal,
        "have_pred_label_agree": bool(have_pred),
    }
    if return_details:
        return score_df, global_score, diagnostics
    return score_df, global_score


def compute_D_and_save(
    bdata,
    adata_ref,
    target_class: str,
    outdir: str,
    dataset_id: str,
    emb_key: str = "X_scanvi",
    batch_key: str = "Sample",
    candidate_flag_prefix: str = "is_candidate_",
    ref_label_key: str = "cell_subtype",
    pred_label_col: str | None = "pred_top1",
    k_query: int = 30,
    k_ref: int = 50,
    k_ref_for_dist: int = 20,
    min_cells_per_batch: int = 10,
    n_jobs: int = 4,
    write_to_obs: bool = True,
    return_details: bool = False,
    ref_model_dir: str | None = None,
    counts_layer: str = "counts",
    train_query: bool = False,
    query_train_kwargs: dict | None = None,
    write_back_uns: bool = True,
):
    if emb_key not in bdata.obsm or emb_key not in adata_ref.obsm:
        if ref_model_dir is None:
            raise KeyError(f"[D] '{emb_key}' missing in .obsm and ref_model_dir not provided.")
        adata_ref, bdata = ensure_scanvi_embedding(
            adata_ref=adata_ref,
            bdata=bdata,
            ref_model_dir=ref_model_dir,
            emb_key=emb_key,
            counts_layer=counts_layer,
            train_query=train_query,
            query_train_kwargs=query_train_kwargs,
        )

    score_df, global_score, diag = compute_component_D(
        bdata=bdata,
        adata_ref=adata_ref,
        target_class=target_class,
        emb_key=emb_key,
        batch_key=batch_key,
        candidate_flag_prefix=candidate_flag_prefix,
        ref_label_key=ref_label_key,
        pred_label_col=pred_label_col,
        k_query=k_query,
        k_ref=k_ref,
        k_ref_for_dist=k_ref_for_dist,
        min_cells_per_batch=min_cells_per_batch,
        n_jobs=n_jobs,
        write_to_obs=write_to_obs,
        return_details=True,
    )

    meta = {
        "target_class": target_class,
        "emb_key": emb_key,
        "batch_key": batch_key,
        "candidate_flag_prefix": candidate_flag_prefix,
        "ref_label_key": ref_label_key,
        "pred_label_col": pred_label_col,
        "k_query": int(k_query),
        "k_ref": int(k_ref),
        "k_ref_for_dist": int(k_ref_for_dist),
        "min_cells_per_batch": int(min_cells_per_batch),
        "n_jobs": int(n_jobs),
        "prop_ref_target": float(diag["prop_ref_target"]),
        "mean_ref_internal_dist": None if np.isnan(diag["mean_ref_internal_dist"]) else float(diag["mean_ref_internal_dist"]),
        "have_pred_label_agree": bool(diag["have_pred_label_agree"]),
        "ref_model_dir_used": ref_model_dir,
        "train_query_used": bool(train_query),
    }
    result = build_component_result("D", score_df, global_score, meta)
    owner = bdata if write_back_uns else None
    saved = save_component_result(result, outdir=outdir, dataset_id=dataset_id, owner_adata=owner)
    if return_details:
        return (*saved, diag)
    return saved
