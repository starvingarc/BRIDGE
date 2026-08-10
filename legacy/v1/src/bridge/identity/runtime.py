from __future__ import annotations

import numpy as np
import pandas as pd


def _import_scvi_stack():
    import torch
    import scvi
    from scvi.model import SCANVI

    return torch, scvi, SCANVI


def set_identity_seed(seed: int = 0):
    torch, scvi, _ = _import_scvi_stack()
    np.random.seed(seed)
    torch.manual_seed(seed)
    scvi.settings.seed = seed
    print(f"[identify] Seed set to {seed}")


def load_scanvi_ref_model(ref_model_dir: str, adata, counts_layer="counts", set_X_to_counts=True):
    _, _, SCANVI = _import_scvi_stack()
    print(f"[identify] Loading SCANVI ref model from: {ref_model_dir}")
    ad = adata.copy()
    if set_X_to_counts:
        ad.X = ad.layers[counts_layer].copy()
        print("[identify] ref: set adata.X = layers['counts']")
    scanvi_ref = SCANVI.load(ref_model_dir, adata=ad)
    print("[identify] Loaded ref model OK.")
    return scanvi_ref, ad


def prepare_and_load_scanvi_query_model(
    ref_model_dir: str,
    bdata,
    counts_layer="counts",
    set_X_to_counts=True,
    inplace_subset_query_vars=True,
):
    _, scvi, _ = _import_scvi_stack()
    print(f"[identify] Preparing query AnnData against ref model: {ref_model_dir}")
    bd = bdata.copy()
    if set_X_to_counts:
        bd.X = bd.layers[counts_layer].copy()
        print("[identify] query: set bdata.X = layers['counts']")
    scvi.model.SCANVI.prepare_query_anndata(bd, ref_model_dir)
    scanvi_query = scvi.model.SCANVI.load_query_data(
        adata=bd,
        reference_model=ref_model_dir,
        inplace_subset_query_vars=bool(inplace_subset_query_vars),
    )
    print("[identify] Loaded query model OK (needs training).")
    return scanvi_query, bd


def train_query_model(
    scanvi_query,
    max_epochs=100,
    plan_kwargs=None,
    early_stopping=False,
    early_stopping_patience=10,
):
    if plan_kwargs is None:
        plan_kwargs = {"weight_decay": 0.0}
    print(f"[identify] Training query model: max_epochs={max_epochs}, plan_kwargs={plan_kwargs}")
    scanvi_query.train(
        max_epochs=max_epochs,
        plan_kwargs=plan_kwargs,
        early_stopping=bool(early_stopping),
        early_stopping_patience=int(early_stopping_patience) if early_stopping else None,
    )
    print("[identify] Query training done.")
    return scanvi_query


def evaluate_ref_accuracy(scanvi_ref, adata_ref, ref_label_key="cell_subtype"):
    preds_ref = scanvi_ref.predict(adata_ref)
    acc = float(np.mean(preds_ref == adata_ref.obs[ref_label_key].astype(str)))
    print(f"[identify] Reference accuracy: {acc:.4f}")
    return acc


def predict_soft(scanvi_model, adata_like):
    probs = scanvi_model.predict(adata_like, soft=True)
    if not isinstance(probs, pd.DataFrame):
        probs = pd.DataFrame(probs, index=adata_like.obs_names)
    return probs


def attach_target_prob(adata_like, probs_df: pd.DataFrame, target_class: str, obs_key="target_prob"):
    adata_like.obs[obs_key] = probs_df.loc[adata_like.obs_names, target_class].astype(float).values
