from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.stats import spearmanr

from bridge.cls.base import build_component_result, save_component_result
from bridge.common.anndata import align_by_common_varnames
from bridge.common.stats import normalize_weights


def _sc():
    import scanpy as sc
    return sc


def ensure_log1p_norm_layer(adata, counts_layer: str = "counts", out_layer: str = "log1p_norm", target_sum: float = 1e4):
    if out_layer in adata.layers:
        return
    if counts_layer not in adata.layers:
        raise KeyError(f"[E] counts layer '{counts_layer}' not found in adata.layers")
    sc = _sc()
    tmp = adata.copy()
    tmp.X = tmp.layers[counts_layer]
    sc.pp.normalize_total(tmp, target_sum=target_sum)
    sc.pp.log1p(tmp)
    adata.layers[out_layer] = tmp.X


def compute_dpt_pseudotime(adata, rep_key: str, neighbors_k: int = 30, pt_key: str = "pt", root_mode: str = "auto_min_pc1", random_state: int = 0):
    if pt_key in adata.obs:
        return
    if rep_key not in adata.obsm:
        raise KeyError(f"[E] rep_key '{rep_key}' not found in adata.obsm")
    sc = _sc()
    sc.pp.neighbors(adata, use_rep=rep_key, n_neighbors=neighbors_k, random_state=random_state)
    sc.tl.diffmap(adata)
    adata.uns["iroot"] = int(np.argmin(adata.obsm["X_diffmap"][:, 0])) if root_mode == "auto_min_pc1" else 0
    sc.tl.dpt(adata)
    x = adata.obs["dpt_pseudotime"].astype(float).to_numpy()
    x = (x - np.nanmin(x)) / (np.nanmax(x) - np.nanmin(x) + 1e-12)
    adata.obs[pt_key] = x


def spearman_gene_vs_vector(X, v, min_mean: float = 0.02):
    v = np.asarray(v).reshape(-1)
    n = v.shape[0]
    rv = v.argsort().argsort().astype(float)
    rv -= rv.mean()
    rv /= (rv.std(ddof=1) + 1e-12)
    means = np.asarray(X.mean(axis=0)).ravel()
    keep = means >= min_mean
    rho = np.zeros(X.shape[1], dtype=float)
    keep_idx = np.where(keep)[0]
    block = 512
    for start in range(0, len(keep_idx), block):
        idx = keep_idx[start:start + block]
        Xb = X[:, idx]
        if sp.issparse(Xb):
            Xb = Xb.toarray()
        ranks = np.argsort(np.argsort(Xb, axis=0), axis=0).astype(float)
        ranks -= ranks.mean(axis=0, keepdims=True)
        ranks /= (ranks.std(axis=0, ddof=1, keepdims=True) + 1e-12)
        rho_block = (rv.reshape(1, -1) @ ranks) / (n - 1)
        rho[idx] = np.asarray(rho_block).ravel()
    return rho, means


def select_gene_sets_for_E(adata_ref, pt_key: str = "pt", layer: str = "log1p_norm", n_genes: int = 800, min_mean: float = 0.02, cc_keys=("CC.Difference", "S.Score", "G2M.Score"), cc_abs_rho_thresh: float = 0.2):
    X = adata_ref.layers[layer]
    pt = adata_ref.obs[pt_key].to_numpy()
    rho_pt, means = spearman_gene_vs_vector(X, pt, min_mean=min_mean)
    cc_proxy = None
    used_cc_key = None
    for key in cc_keys:
        if key in adata_ref.obs.columns:
            cc_proxy = np.asarray(adata_ref.obs[key]).astype(float)
            used_cc_key = key
            break
    rho_cc = spearman_gene_vs_vector(X, cc_proxy, min_mean=min_mean)[0] if cc_proxy is not None else np.zeros_like(rho_pt)
    order = np.argsort(np.abs(rho_pt))[::-1]
    order = [i for i in order if means[i] >= min_mean][: max(n_genes, 3000)]
    cycle_order = sorted(order, key=lambda i: abs(rho_cc[i]), reverse=True)
    G_cycle_idx = cycle_order[: min(300, len(cycle_order))]
    dev_idx = [i for i in order if abs(rho_cc[i]) < cc_abs_rho_thresh][:n_genes]
    G_dev = adata_ref.var_names[dev_idx].to_list()
    G_cycle = adata_ref.var_names[G_cycle_idx].to_list()
    info = {
        "n_dev": int(len(G_dev)),
        "n_cycle": int(len(G_cycle)),
        "cc_proxy_used": used_cc_key,
        "rho_pt_range": (float(np.nanmin(rho_pt)), float(np.nanmax(rho_pt))),
        "rho_cc_range": (float(np.nanmin(rho_cc)), float(np.nanmax(rho_cc))),
        "min_mean": float(min_mean),
        "cc_abs_rho_thresh": float(cc_abs_rho_thresh),
    }
    return G_dev, G_cycle, info


def bin_smooth_trends_weighted(adata, genes, pt_key: str = "pt", layer: str = "log1p_norm", weights=None, n_bins: int = 80, min_eff_bin: int = 20, smooth_k: int = 5):
    X = adata.layers[layer]
    pt = adata.obs[pt_key].to_numpy().astype(float)
    w = np.ones_like(pt, dtype=float) if weights is None else np.clip(np.asarray(weights, dtype=float), 0, None)
    bins = np.linspace(0, 1, n_bins + 1)
    centers = (bins[:-1] + bins[1:]) / 2
    bidx = np.clip(np.digitize(pt, bins) - 1, 0, n_bins - 1)
    sumw = np.bincount(bidx, weights=w, minlength=n_bins)
    sumw2 = np.bincount(bidx, weights=w * w, minlength=n_bins)
    eff_n = (sumw**2) / (sumw2 + 1e-12)
    trends = {}
    for gene in genes:
        if gene not in adata.var_names:
            continue
        j = adata.var_names.get_loc(gene)
        col = X[:, j]
        col = np.asarray(col.toarray()).ravel() if sp.issparse(col) else np.asarray(col).ravel()
        y = np.full(n_bins, np.nan, float)
        for bi in range(n_bins):
            if eff_n[bi] >= min_eff_bin and sumw[bi] > 0:
                mask = bidx == bi
                y[bi] = float(np.sum(col[mask] * w[mask]) / sumw[bi])
        ok = ~np.isnan(y)
        if ok.sum() < max(8, n_bins // 5):
            continue
        y = np.interp(np.arange(n_bins), np.where(ok)[0], y[ok])
        if smooth_k and smooth_k > 1:
            kernel = np.ones(int(smooth_k), dtype=float) / float(smooth_k)
            y = np.convolve(y, kernel, mode="same")
        trends[gene] = (centers, y)
    return trends


def compute_gene_rhos_from_trend_dict(ref_trends, org_trends):
    common = sorted(set(ref_trends.keys()).intersection(org_trends.keys()))
    genes, rhos = [], []
    for gene in common:
        x_ref, y_ref = ref_trends[gene]
        x_org, y_org = org_trends[gene]
        if not np.allclose(x_ref, x_org):
            y_org = np.interp(x_ref, x_org, y_org)
        rho = spearmanr(y_ref, y_org).correlation
        if np.isfinite(rho):
            genes.append(str(gene))
            rhos.append(float(rho))
    return genes, rhos


def get_branch_weights_auto(adata_org, pt_key: str = "pt", cluster_key: str = "leiden_E", rep_key: str = "X_scanvi", max_branches: int = 3, random_state: int = 0):
    try:
        import cellrank as cr
        from cellrank.kernels import PseudotimeKernel

        pk = PseudotimeKernel(adata_org, time_key=pt_key)
        pk.compute_transition_matrix(threshold_scheme="hard", frac_to_keep=0.3, check_irreducibility=False)
        g = cr.estimators.GPCCA(pk)
        sc = _sc()
        if "leiden" not in adata_org.obs:
            sc.tl.leiden(adata_org, key_added="leiden", resolution=0.8, random_state=random_state)
        g.fit(cluster_key="leiden", n_states=8)
        try:
            g.predict_terminal_states(method="eigengap")
        except Exception:
            g.predict_terminal_states(method="top_n", n_states=2)
        g.compute_fate_probabilities(solver="direct", tol=1e-10, check_sum_tol=5e-3, use_petsc=False)
        fp = g.fate_probabilities
        fp = fp if isinstance(fp, pd.DataFrame) else pd.DataFrame(fp, index=adata_org.obs_names)
        cols = list(fp.columns)[:max_branches]
        weights_dict = {str(c): fp[c].to_numpy() for c in cols}
        meta = {"mode": "cellrank", "branches": cols, "mean_weights": {str(c): float(np.mean(weights_dict[str(c)])) for c in cols}}
        return weights_dict, meta
    except Exception:
        sc = _sc()
        sc.pp.neighbors(adata_org, use_rep=rep_key, n_neighbors=30, random_state=random_state)
        sc.tl.leiden(adata_org, key_added=cluster_key, resolution=0.6, random_state=random_state)
        counts = adata_org.obs[cluster_key].value_counts()
        top = list(counts.index[:max_branches])
        weights_dict = {str(c): (adata_org.obs[cluster_key].astype(str) == str(c)).astype(float).to_numpy() for c in top}
        meta = {"mode": "cluster", "branches": top, "cluster_key": cluster_key, "counts": counts.to_dict()}
        return weights_dict, meta


def compute_component_E(
    adata_ref,
    adata_org,
    rep_key_ref: str = "X_scanvi",
    rep_key_org: str = "X_scanvi",
    counts_layer: str = "counts",
    layer: str = "log1p_norm",
    pt_key: str = "pt",
    n_genes: int = 800,
    min_mean: float = 0.02,
    cc_keys=("CC.Difference", "S.Score", "G2M.Score"),
    cc_abs_rho_thresh: float = 0.2,
    n_bins: int = 80,
    min_eff_bin: int = 20,
    smooth_k: int = 5,
    max_branches: int = 3,
    random_state: int = 0,
    return_details: bool = False,
):
    ad_ref = adata_ref.copy()
    ad_org = adata_org.copy()
    ad_ref, ad_org, common = align_by_common_varnames(ad_ref, ad_org, "E")
    ensure_log1p_norm_layer(ad_ref, counts_layer=counts_layer, out_layer=layer)
    ensure_log1p_norm_layer(ad_org, counts_layer=counts_layer, out_layer=layer)
    compute_dpt_pseudotime(ad_ref, rep_key=rep_key_ref, pt_key=pt_key, random_state=random_state)
    compute_dpt_pseudotime(ad_org, rep_key=rep_key_org, pt_key=pt_key, random_state=random_state)
    G_dev, G_cycle, gs_info = select_gene_sets_for_E(ad_ref, pt_key=pt_key, layer=layer, n_genes=n_genes, min_mean=min_mean, cc_keys=cc_keys, cc_abs_rho_thresh=cc_abs_rho_thresh)
    ref_trends = bin_smooth_trends_weighted(ad_ref, G_dev, pt_key=pt_key, layer=layer, n_bins=n_bins, min_eff_bin=min_eff_bin, smooth_k=smooth_k)
    weights_dict, branch_meta = get_branch_weights_auto(ad_org, pt_key=pt_key, rep_key=rep_key_org, max_branches=max_branches, random_state=random_state)
    total_wsum = float(sum(np.sum(np.asarray(wi, float)) for wi in weights_dict.values()) + 1e-12)
    rows, branch_rho = [], {}
    pt_org = ad_org.obs[pt_key].to_numpy(dtype=float)
    for bname, w in weights_dict.items():
        w = np.asarray(w, float)
        wsum = float(np.sum(w) + 1e-12)
        w_norm = w / wsum
        org_trends = bin_smooth_trends_weighted(ad_org, G_dev, pt_key=pt_key, layer=layer, weights=w, n_bins=n_bins, min_eff_bin=min_eff_bin, smooth_k=smooth_k)
        genes_b, rhos_b = compute_gene_rhos_from_trend_dict(ref_trends, org_trends)
        branch_rho[str(bname)] = (genes_b, rhos_b)
        E_b = np.nan if len(rhos_b) == 0 else float((np.mean(rhos_b) + 1.0) / 2.0)
        rows.append({"branch": str(bname), "mode": branch_meta.get("mode", "auto"), "branch_weight": float(wsum / total_wsum), "mean_pt_weighted": float(np.sum(w_norm * pt_org)), "E_dev": float(E_b), "n_genes_used": int(len(rhos_b))})
    score_df = pd.DataFrame(rows)
    if score_df.shape[0] == 0:
        raise ValueError("[E] No branches produced.")
    score_df = score_df.sort_values("E_dev", ascending=False).reset_index(drop=True)
    w = normalize_weights(score_df["branch_weight"].to_numpy(dtype=float))
    E_weighted = float(np.nansum(w * score_df["E_dev"].to_numpy(dtype=float)))
    best_branch = str(score_df.loc[0, "branch"])
    best_genes, best_rhos = branch_rho.get(best_branch, ([], []))
    diagnostics = {
        "E_weighted": E_weighted,
        "E_best": float(np.nanmax(score_df["E_dev"].to_numpy(dtype=float))),
        "branch_meta": branch_meta,
        "gene_set_info": gs_info,
        "n_genes_requested": int(n_genes),
        "n_genes_ref_trends": int(len(ref_trends)),
        "n_branches": int(score_df.shape[0]),
        "pt_key": pt_key,
        "layer": layer,
        "rep_key_ref": rep_key_ref,
        "rep_key_org": rep_key_org,
        "n_common_genes": int(len(common)),
        "rho_branch": best_branch,
        "rho_genes": best_genes,
        "rho_values": best_rhos,
    }
    if return_details:
        return score_df, E_weighted, diagnostics, {"G_dev": G_dev, "G_cycle": G_cycle}
    return score_df, E_weighted, diagnostics


def compute_E_and_save(
    adata_ref,
    adata_org,
    outdir: str,
    dataset_id: str,
    rep_key_ref: str = "X_scanvi",
    rep_key_org: str = "X_scanvi",
    counts_layer: str = "counts",
    layer: str = "log1p_norm",
    pt_key: str = "pt",
    n_genes: int = 800,
    min_mean: float = 0.02,
    cc_keys=("CC.Difference", "S.Score", "G2M.Score"),
    cc_abs_rho_thresh: float = 0.2,
    n_bins: int = 80,
    min_eff_bin: int = 20,
    smooth_k: int = 5,
    max_branches: int = 3,
    random_state: int = 0,
    write_back_uns: bool = True,
):
    score_df, E_weighted, diag, extra = compute_component_E(
        adata_ref=adata_ref,
        adata_org=adata_org,
        rep_key_ref=rep_key_ref,
        rep_key_org=rep_key_org,
        counts_layer=counts_layer,
        layer=layer,
        pt_key=pt_key,
        n_genes=n_genes,
        min_mean=min_mean,
        cc_keys=cc_keys,
        cc_abs_rho_thresh=cc_abs_rho_thresh,
        n_bins=n_bins,
        min_eff_bin=min_eff_bin,
        smooth_k=smooth_k,
        max_branches=max_branches,
        random_state=random_state,
        return_details=True,
    )
    meta = dict(diag)
    meta["gene_sets"] = {"G_dev": extra["G_dev"], "G_cycle": extra["G_cycle"]}
    result = build_component_result("E", score_df, E_weighted, meta)
    owner = adata_org if write_back_uns else None
    return save_component_result(result, outdir=outdir, dataset_id=dataset_id, owner_adata=owner, table_key="branch_table")
