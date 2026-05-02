from __future__ import annotations

import numpy as np
import pandas as pd


def _import_scvi_stack():
    import torch
    import scvi
    from scvi.model import SCANVI

    return torch, scvi, SCANVI


def set_prescreen_seed(seed: int = 0):
    torch, scvi, _ = _import_scvi_stack()
    np.random.seed(seed)
    torch.manual_seed(seed)
    scvi.settings.seed = seed
    print(f"[prescreen] Seed set to {seed}")


def prepare_and_load_scanvi_query_model(
    ref_model_dir: str,
    bdata,
    counts_layer: str = "counts",
    set_X_to_counts: bool = True,
    inplace_subset_query_vars: bool = True,
):
    _, _, SCANVI = _import_scvi_stack()
    print(f"[prescreen] Preparing query AnnData against whole-brain ref model: {ref_model_dir}")
    bd = bdata.copy()
    if set_X_to_counts:
        if counts_layer not in bd.layers:
            raise KeyError(f"[prescreen] layer '{counts_layer}' not found in query AnnData layers.")
        bd.X = bd.layers[counts_layer].copy()
        print(f"[prescreen] query: set bdata.X = layers['{counts_layer}']")
    SCANVI.prepare_query_anndata(bd, ref_model_dir)
    scanvi_query = SCANVI.load_query_data(
        adata=bd,
        reference_model=ref_model_dir,
        inplace_subset_query_vars=bool(inplace_subset_query_vars),
    )
    print("[prescreen] Loaded query model OK.")
    return scanvi_query, bd


def train_query_model(
    scanvi_query,
    max_epochs: int,
    plan_kwargs: dict | None = None,
    early_stopping: bool = False,
    early_stopping_patience: int = 10,
):
    if plan_kwargs is None:
        plan_kwargs = {"weight_decay": 0.0}
    print(f"[prescreen] Training query model: max_epochs={max_epochs}, plan_kwargs={plan_kwargs}")
    scanvi_query.train(
        max_epochs=int(max_epochs),
        plan_kwargs=plan_kwargs,
        early_stopping=bool(early_stopping),
        early_stopping_patience=int(early_stopping_patience) if early_stopping else None,
    )
    print("[prescreen] Query training done.")
    return scanvi_query


def predict_soft(scanvi_model, adata_like, batch_size: int = 1024) -> pd.DataFrame:
    probs = scanvi_model.predict(adata_like, soft=True, batch_size=int(batch_size))
    if not isinstance(probs, pd.DataFrame):
        probs = pd.DataFrame(probs, index=adata_like.obs_names)
    return probs.reindex(index=adata_like.obs_names)
