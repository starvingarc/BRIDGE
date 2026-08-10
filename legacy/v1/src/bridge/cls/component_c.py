from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from bridge.cls.base import build_component_result, save_component_result
from bridge.common.anndata import require_obs_column, require_obsm_key
from bridge.common.stats import normalize_weights, safe_auc


def compute_ref_cv_auc_logistic(
    adata_ref,
    target_class: str,
    label_key: str = "cell_subtype",
    embedding_key: str = "X_scVI",
    n_splits: int = 5,
    random_state: int = 0,
    solver: str = "liblinear",
    max_iter: int = 200,
):
    require_obsm_key(adata_ref, embedding_key, "C")
    if label_key not in adata_ref.obs:
        raise KeyError(f"[C] label_key '{label_key}' not found in adata_ref.obs.")
    X = np.asarray(adata_ref.obsm[embedding_key])
    y = (adata_ref.obs[label_key].astype(str).values == str(target_class)).astype(int)
    if np.unique(y).size < 2:
        raise ValueError(f"[C] Reference labels for '{target_class}' contain only one class; cannot compute AUC.")
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    aucs = []
    for tr, te in skf.split(X, y):
        clf = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                solver=solver,
                max_iter=max_iter,
                class_weight="balanced",
                random_state=random_state,
            ),
        )
        clf.fit(X[tr], y[tr])
        p = clf.predict_proba(X[te])[:, 1]
        aucs.append(safe_auc(y[te], p))
    return float(np.nanmean(aucs)), aucs


def compute_component_C(
    bdata,
    adata_ref,
    probs_ref_cal: pd.DataFrame | None,
    target_class: str,
    batch_key: str = "Sample",
    candidate_flag_prefix: str = "is_candidate_",
    score_prefix: str = "p_mean_",
    min_cells_per_batch: int = 20,
    auc_ref_method: str = "logistic_cv",
    ref_label_key: str = "cell_subtype",
    embedding_key: str = "X_scVI",
    cv_splits: int = 5,
    random_state: int = 0,
    solver: str = "liblinear",
    max_iter: int = 200,
):
    cand_col = f"{candidate_flag_prefix}{target_class}"
    score_col = f"{score_prefix}{target_class}"
    require_obs_column(bdata, batch_key, "C")
    require_obs_column(bdata, cand_col, "C")
    require_obs_column(bdata, score_col, "C")

    if auc_ref_method == "naive":
        if probs_ref_cal is None:
            raise ValueError("[C] auc_ref_method='naive' requires probs_ref_cal.")
        if ref_label_key not in adata_ref.obs:
            raise KeyError(f"[C] ref_label_key '{ref_label_key}' not found in adata_ref.obs")
        if target_class not in probs_ref_cal.columns:
            raise KeyError(f"[C] target_class '{target_class}' not in probs_ref_cal.columns")
        missing = adata_ref.obs_names.difference(probs_ref_cal.index)
        if len(missing) > 0:
            raise KeyError(f"[C] probs_ref_cal missing {len(missing)} ref cells (index mismatch).")
        y_ref = (adata_ref.obs[ref_label_key].astype(str).values == str(target_class)).astype(int)
        s_ref = probs_ref_cal.loc[adata_ref.obs_names, target_class].astype(float).values
        AUC_ref = safe_auc(y_ref, s_ref)
        auc_ref_details = {"method": "naive", "AUC_ref": AUC_ref}
    elif auc_ref_method == "logistic_cv":
        AUC_ref, per_fold = compute_ref_cv_auc_logistic(
            adata_ref=adata_ref,
            target_class=target_class,
            label_key=ref_label_key,
            embedding_key=embedding_key,
            n_splits=cv_splits,
            random_state=random_state,
            solver=solver,
            max_iter=max_iter,
        )
        auc_ref_details = {"method": "logistic_cv", "cv_aucs": per_fold, "AUC_ref": AUC_ref}
    else:
        raise ValueError(f"[C] Unknown auc_ref_method: {auc_ref_method}")

    cand_mask = bdata.obs[cand_col].astype(bool).values
    n_cand_total = int(cand_mask.sum())
    if n_cand_total == 0:
        raise ValueError(f"[C] No candidate cells found for '{target_class}' (flag {cand_col}).")
    grouped = bdata.obs.loc[bdata.obs_names[cand_mask], [batch_key]].groupby(batch_key, observed=False).groups
    score_series = bdata.obs[score_col].astype(float)
    rows = []
    for batch, pos_names in grouped.items():
        pos_names = list(pos_names)
        neg_names = bdata.obs_names[(bdata.obs[batch_key] == batch).values & (~cand_mask)]
        n_pos = len(pos_names)
        n_neg = int(len(neg_names))
        if (n_pos + n_neg) < int(min_cells_per_batch):
            continue
        if n_pos < 2 or n_neg < 2:
            continue
        idx = pd.Index(pos_names).append(pd.Index(neg_names))
        y_true = np.concatenate([np.ones(n_pos, dtype=int), np.zeros(n_neg, dtype=int)])
        y_score = score_series.loc[idx].to_numpy(dtype=float)
        auc_org = safe_auc(y_true, y_score)
        sC_b = np.nan if (np.isnan(AUC_ref) or np.isnan(auc_org)) else float(np.clip(1.0 - abs(float(AUC_ref) - float(auc_org)), 0.0, 1.0))
        rows.append({
            "batch": batch,
            "n_candidate": n_pos,
            "n_noncandidate_in_batch": n_neg,
            "AUC_org": auc_org,
            "AUC_ref": AUC_ref,
            "sC": sC_b,
        })
    score_df = pd.DataFrame(rows)
    if score_df.shape[0] == 0:
        raise ValueError("[C] No batches passed min_cells_per_batch / or no candidate batches found.")
    score_df = score_df.sort_values("sC", ascending=False).reset_index(drop=True)
    w = normalize_weights(score_df["n_candidate"].to_numpy(dtype=float))
    global_score = float(np.nansum(w * score_df["sC"].to_numpy(dtype=float)))
    meta = {
        "target_class": target_class,
        "batch_key": batch_key,
        "candidate_flag_col": cand_col,
        "score_col": score_col,
        "auc_ref_method": auc_ref_method,
        "auc_ref_details": auc_ref_details,
        "min_cells_per_batch": int(min_cells_per_batch),
        "n_candidate_total": n_cand_total,
        "n_batches_evaluated": int(score_df.shape[0]),
    }
    return score_df, global_score, meta


def compute_C_and_save(
    bdata,
    adata_ref,
    probs_ref_cal: pd.DataFrame | None,
    target_class: str,
    outdir: str,
    dataset_id: str,
    batch_key: str = "Sample",
    candidate_flag_prefix: str = "is_candidate_",
    score_prefix: str = "p_mean_",
    min_cells_per_batch: int = 20,
    auc_ref_method: str = "logistic_cv",
    ref_label_key: str = "cell_subtype",
    embedding_key: str = "X_scVI",
    cv_splits: int = 5,
    random_state: int = 0,
    solver: str = "liblinear",
    max_iter: int = 200,
    write_back_uns: bool = True,
):
    score_df, global_score, meta = compute_component_C(
        bdata=bdata,
        adata_ref=adata_ref,
        probs_ref_cal=probs_ref_cal,
        target_class=target_class,
        batch_key=batch_key,
        candidate_flag_prefix=candidate_flag_prefix,
        score_prefix=score_prefix,
        min_cells_per_batch=min_cells_per_batch,
        auc_ref_method=auc_ref_method,
        ref_label_key=ref_label_key,
        embedding_key=embedding_key,
        cv_splits=cv_splits,
        random_state=random_state,
        solver=solver,
        max_iter=max_iter,
    )
    result = build_component_result("C", score_df, global_score, meta)
    owner = bdata if write_back_uns else None
    return save_component_result(result, outdir=outdir, dataset_id=dataset_id, owner_adata=owner)
