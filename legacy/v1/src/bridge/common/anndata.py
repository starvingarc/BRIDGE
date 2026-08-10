from __future__ import annotations


def require_obs_column(adata, column: str, prefix: str):
    if column not in adata.obs:
        raise KeyError(f"[{prefix}] '{column}' not found in adata.obs")


def require_layer(adata, layer: str, prefix: str):
    if layer not in adata.layers:
        raise KeyError(f"[{prefix}] layer '{layer}' not found in adata.layers")


def require_obsm_key(adata, key: str, prefix: str):
    if key not in adata.obsm:
        raise KeyError(f"[{prefix}] '{key}' not found in adata.obsm")


def align_by_common_varnames(adata_left, adata_right, prefix: str):
    left = adata_left.var_names.astype(str)
    right = adata_right.var_names.astype(str)
    common = left.intersection(right)
    if len(common) == 0:
        raise ValueError(f"[{prefix}] No common genes between AnnData objects.")
    if not left.equals(common):
        adata_left = adata_left[:, common].copy()
    if not right.equals(common):
        adata_right = adata_right[:, common].copy()
    return adata_left, adata_right, common
