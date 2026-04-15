from __future__ import annotations

import numpy as np
import pandas as pd


def ensemble_mean_std(ensemble_list):
    arrs = np.stack([df.values for df in ensemble_list], axis=0)
    mean = arrs.mean(axis=0)
    if len(ensemble_list) == 1:
        std = np.zeros_like(mean, dtype=float)
    else:
        std = arrs.std(axis=0, ddof=1)
    cols = ensemble_list[0].columns
    idx = ensemble_list[0].index
    return pd.DataFrame(mean, index=idx, columns=cols), pd.DataFrame(std, index=idx, columns=cols)


def approx_std_from_p(p_series, N_eff=20.0):
    p = p_series.values
    std = np.sqrt(p * (1.0 - p) / float(N_eff))
    return pd.Series(std, index=p_series.index)


def run_query_ensemble(
    ref_model_dir,
    bdata,
    calibrators,
    class_names,
    M=5,
    max_epochs=100,
    plan_kwargs=None,
    early_stopping=True,
    early_stopping_patience=10,
    seed_base=0,
):
    import scvi

    if plan_kwargs is None:
        plan_kwargs = {"weight_decay": 0.0}
    ensemble_prob_list = []
    for i in range(M):
        print(f"[identity_assessment] Ensemble model {i + 1}/{M}...")
        scvi.settings.seed = seed_base + i * 42
        try:
            scanvi_temp = scvi.model.SCANVI.load_query_data(
                adata=bdata,
                reference_model=ref_model_dir,
                inplace_subset_query_vars=True,
            )
            scanvi_temp.train(
                max_epochs=max_epochs,
                plan_kwargs=plan_kwargs,
                early_stopping=bool(early_stopping),
                early_stopping_patience=int(early_stopping_patience) if early_stopping else None,
            )
            probs_temp = scanvi_temp.predict(bdata, soft=True)
            if not isinstance(probs_temp, pd.DataFrame):
                probs_temp = pd.DataFrame(probs_temp, index=bdata.obs_names, columns=class_names)
            from bridge.identity.calibration import apply_calibrators

            probs_temp_cal = apply_calibrators(
                probs_temp.reindex(columns=class_names).fillna(0),
                calibrators,
            )
            ensemble_prob_list.append(probs_temp_cal)
            print(f"[identity_assessment] Ensemble model {i + 1} done.")
        except Exception as exc:
            print(f"[identity_assessment] Ensemble model {i + 1} failed: {exc}")
            continue
    return ensemble_prob_list


def predictive_entropy_norm(p_df: pd.DataFrame):
    p = np.clip(p_df.values, 1e-12, 1.0)
    k = p.shape[1]
    entropy = -np.sum(p * np.log(p), axis=1)
    entropy_norm = entropy / np.log(k)
    return pd.Series(entropy_norm, index=p_df.index, name="Hnorm")
