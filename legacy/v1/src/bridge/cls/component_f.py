from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
from scipy import sparse

from bridge.cls.base import build_component_result, save_component_result
from bridge.common.stats import normalize_weights

try:
    import decoupler as dc
except Exception:
    dc = None


def run_aucell_decoupler2(adata, net: pd.DataFrame, layer: str | None = None, raw: bool = False, tmin: int = 5, n_up: int | None = 2000, verbose: bool = True) -> pd.DataFrame:
    if dc is None:
        raise ImportError("[F] decoupler is required. Please install decoupler>=2.x.")
    obsm_before = set(adata.obsm.keys())
    res = dc.mt.aucell(adata, net=net, tmin=tmin, layer=layer, raw=raw, verbose=verbose, n_up=n_up)
    if isinstance(res, pd.DataFrame):
        return res
    if isinstance(res, np.ndarray):
        sources = sorted(net["source"].unique().tolist())
        return pd.DataFrame(res, index=adata.obs_names, columns=sources)
    if isinstance(res, dict):
        for key in ["acts", "estimate", "scores", "es"]:
            if key in res:
                val = res[key]
                if isinstance(val, pd.DataFrame):
                    return val
                if isinstance(val, np.ndarray):
                    sources = sorted(net["source"].unique().tolist())
                    return pd.DataFrame(val, index=adata.obs_names, columns=sources)
    obsm_after = set(adata.obsm.keys())
    new_keys = sorted(list(obsm_after - obsm_before), key=lambda x: ("aucell" not in x.lower(), x))
    for key in new_keys:
        val = adata.obsm[key]
        if isinstance(val, pd.DataFrame):
            return val
        if isinstance(val, np.ndarray) and val.shape[0] == adata.n_obs:
            sources = sorted(net["source"].unique().tolist())
            if val.shape[1] == len(sources):
                return pd.DataFrame(val, index=adata.obs_names, columns=sources)
            return pd.DataFrame(val, index=adata.obs_names)
    raise RuntimeError(f"[F] dc.mt.aucell produced no retrievable result. Return type={type(res)}, new obsm keys={new_keys}.")


def _det_rate(X):
    if sparse.issparse(X):
        return np.asarray((X > 0).mean(axis=0)).ravel()
    return (np.asarray(X) > 0).mean(axis=0)


def _build_net_from_regulons(regulons: dict[str, list[str]]) -> pd.DataFrame:
    rows = [(tf, gene, 1.0) for tf, tgts in regulons.items() for gene in tgts]
    return pd.DataFrame(rows, columns=["source", "target", "weight"])


def _get_X(adata, layer: str | None):
    if layer and (layer in adata.layers):
        return adata.layers[layer]
    return adata.X


def _compile_regulon_indices(regulons: dict[str, list[str]], var_names) -> dict[str, np.ndarray]:
    gene_to_idx = {str(gene): idx for idx, gene in enumerate(map(str, var_names))}
    compiled: dict[str, np.ndarray] = {}
    for tf, genes in regulons.items():
        idx = [gene_to_idx[g] for g in genes if g in gene_to_idx]
        if idx:
            compiled[str(tf)] = np.asarray(idx, dtype=np.int64)
    return compiled


def _active_regulon_mask(det_rate: np.ndarray, regulon_idx: np.ndarray, threshold: float) -> np.ndarray:
    return det_rate[regulon_idx] >= float(threshold)


def _mean_auc_vector(auc_df: pd.DataFrame, cells) -> np.ndarray:
    return auc_df.loc[cells].mean(axis=0).to_numpy(dtype=float)


def _safe_corrcoef(x: np.ndarray, y: np.ndarray) -> float:
    if np.std(x) <= 0 or np.std(y) <= 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def compute_component_F(
    adata_ref_sceniclike,
    regulons_json_path: str,
    adata_query,
    batch_key: str = "Sample",
    expr_layer: str = "logcounts",
    det_rate_threshold: float = 0.05,
    min_targets: int = 10,
    aucell_n_up: int = 2000,
    eta1: float = 0.4,
    eta2: float = 0.6,
    verbose_aucell: bool = True,
    precomputed_query_auc: pd.DataFrame | None = None,
    return_qry_auc: bool = False,
):
    if not os.path.exists(regulons_json_path):
        raise FileNotFoundError(f"[F] regulons_json_path not found: {regulons_json_path}")
    if batch_key not in adata_query.obs:
        raise KeyError(f"[F] batch_key '{batch_key}' not in adata_query.obs")
    with open(regulons_json_path, "r", encoding="utf-8") as fh:
        regulons = json.load(fh)
    if not isinstance(regulons, dict) or len(regulons) == 0:
        raise ValueError("[F] regulons.json is empty or invalid dict.")
    common_genes = adata_ref_sceniclike.var_names.intersection(adata_query.var_names)
    if len(common_genes) == 0:
        raise ValueError("[F] No common genes between ref_sceniclike and query.")
    ref = adata_ref_sceniclike[:, common_genes].copy()
    qry = adata_query[:, common_genes].copy()
    if "X_regulon_auc" not in ref.obsm:
        raise KeyError("[F] ref_sceniclike.obsm['X_regulon_auc'] not found.")
    if "regulon_names" not in ref.uns:
        raise KeyError("[F] ref_sceniclike.uns['regulon_names'] not found.")
    ref_reg_names = list(ref.uns["regulon_names"])
    ref_auc = pd.DataFrame(ref.obsm["X_regulon_auc"], index=ref.obs_names, columns=ref_reg_names)
    layer_for_aucell = expr_layer if (expr_layer in qry.layers) else None
    if precomputed_query_auc is not None:
        qry_auc = precomputed_query_auc.copy()
    else:
        net = _build_net_from_regulons(regulons)
        qry_auc = run_aucell_decoupler2(
            qry,
            net=net,
            layer=layer_for_aucell,
            raw=False,
            tmin=min_targets,
            n_up=aucell_n_up,
            verbose=verbose_aucell,
        )
    common_regs = ref_auc.columns.intersection(qry_auc.columns)
    if len(common_regs) == 0:
        raise ValueError("[F] No common regulons between ref_auc and qry_auc (column mismatch).")
    ref_auc = ref_auc[common_regs]
    qry_auc = qry_auc[common_regs]
    regulon_idx_map = _compile_regulon_indices(regulons, qry.var_names)
    regulon_idx_map = {tf: regulon_idx_map[tf] for tf in common_regs if tf in regulon_idx_map}
    dr_ref = _det_rate(_get_X(ref, expr_layer))
    ref_active_masks: dict[str, np.ndarray] = {}
    for tf in common_regs:
        if tf not in regulon_idx_map:
            continue
        active_mask = _active_regulon_mask(dr_ref, regulon_idx_map[tf], det_rate_threshold)
        if int(active_mask.sum()) >= int(min_targets):
            ref_active_masks[str(tf)] = active_mask
    if len(ref_active_masks) == 0:
        raise ValueError("[F] No regulons passed ref_active filter.")
    v_r = ref_auc.mean(axis=0).to_numpy(dtype=float)
    rows = []
    for batch, idx in qry.obs.groupby(batch_key).indices.items():
        idx = np.asarray(idx, dtype=int)
        n_cells = int(len(idx))
        if n_cells == 0:
            continue
        cells = qry.obs_names[idx]
        v_q = _mean_auc_vector(qry_auc[common_regs], cells)
        ra = _safe_corrcoef(v_q, v_r)
        Xb = _get_X(qry, expr_layer)[idx, :]
        dr_b = _det_rate(Xb)
        j_list = []
        for tf, ref_mask in ref_active_masks.items():
            idx_tf = regulon_idx_map[tf]
            batch_mask = _active_regulon_mask(dr_b, idx_tf, det_rate_threshold)
            if int(batch_mask.sum()) < int(min_targets):
                continue
            inter = int(np.count_nonzero(ref_mask & batch_mask))
            union = int(np.count_nonzero(ref_mask | batch_mask))
            if union:
                j_list.append(inter / union)
        J = float(np.mean(j_list)) if len(j_list) > 0 else np.nan
        sF = np.nan
        if np.isfinite(J) and np.isfinite(ra):
            sF = float(float(eta1) * J + float(eta2) * ((ra + 1.0) / 2.0))
        rows.append({"batch": batch, "n_cells": n_cells, "J": J, "ra": ra, "sF": sF, "n_reg_used": int(len(j_list))})
    score_df = pd.DataFrame(rows)
    if score_df.shape[0] == 0:
        raise ValueError("[F] No batches produced. Check batch_key and query data.")
    score_df = score_df.sort_values("batch").reset_index(drop=True)
    w = normalize_weights(score_df["n_cells"].to_numpy(dtype=float))
    global_score = float(np.nansum(w * score_df["sF"].to_numpy(dtype=float)))
    meta = {
        "batch_key": batch_key,
        "expr_layer": expr_layer,
        "det_rate_threshold": float(det_rate_threshold),
        "min_targets": int(min_targets),
        "aucell_n_up": int(aucell_n_up),
        "eta1": float(eta1),
        "eta2": float(eta2),
        "n_common_genes": int(len(common_genes)),
        "n_common_regulons": int(len(common_regs)),
        "n_ref_active_regulons": int(len(ref_active_masks)),
        "regulons_json_path": regulons_json_path,
        "used_precomputed_query_auc": bool(precomputed_query_auc is not None),
    }
    if return_qry_auc:
        return score_df, global_score, meta, qry_auc
    return score_df, global_score, meta


def compute_F_and_save(
    adata_ref_sceniclike,
    regulons_json_path: str,
    adata_query,
    outdir: str,
    dataset_id: str,
    batch_key: str = "Sample",
    expr_layer: str = "logcounts",
    det_rate_threshold: float = 0.05,
    min_targets: int = 10,
    aucell_n_up: int = 2000,
    eta1: float = 0.4,
    eta2: float = 0.6,
    verbose_aucell: bool = True,
    query_aucell_path: str | None = None,
    save_qry_auc: bool = False,
    write_back_uns: bool = True,
):
    precomputed_query_auc = None
    if query_aucell_path is not None:
        if not os.path.exists(query_aucell_path):
            raise FileNotFoundError(f"[F] query_aucell_path not found: {query_aucell_path}")
        precomputed_query_auc = pd.read_csv(query_aucell_path, index_col=0)
    if save_qry_auc:
        score_df, global_score, meta, qry_auc = compute_component_F(
            adata_ref_sceniclike=adata_ref_sceniclike,
            regulons_json_path=regulons_json_path,
            adata_query=adata_query,
            batch_key=batch_key,
            expr_layer=expr_layer,
            det_rate_threshold=det_rate_threshold,
            min_targets=min_targets,
            aucell_n_up=aucell_n_up,
            eta1=eta1,
            eta2=eta2,
            verbose_aucell=verbose_aucell,
            precomputed_query_auc=precomputed_query_auc,
            return_qry_auc=True,
        )
        save_dir = os.path.join(outdir, dataset_id, "F")
        os.makedirs(save_dir, exist_ok=True)
        qry_auc_path = os.path.join(save_dir, "query_aucell.csv")
        qry_auc.to_csv(qry_auc_path)
        meta["query_aucell_csv"] = qry_auc_path
    else:
        score_df, global_score, meta = compute_component_F(
            adata_ref_sceniclike=adata_ref_sceniclike,
            regulons_json_path=regulons_json_path,
            adata_query=adata_query,
            batch_key=batch_key,
            expr_layer=expr_layer,
            det_rate_threshold=det_rate_threshold,
            min_targets=min_targets,
            aucell_n_up=aucell_n_up,
            eta1=eta1,
            eta2=eta2,
            verbose_aucell=verbose_aucell,
            precomputed_query_auc=precomputed_query_auc,
            return_qry_auc=False,
        )
    result = build_component_result("F", score_df, global_score, meta)
    owner = adata_query if write_back_uns else None
    return save_component_result(result, outdir=outdir, dataset_id=dataset_id, owner_adata=owner)
