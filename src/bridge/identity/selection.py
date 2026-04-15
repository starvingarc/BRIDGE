from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve

from bridge.identity.results import IdentitySelectionResult, IdentityThresholds


def calibrate_threshold_from_ref(p_ref_cal_series, y_ref_series, target_class, target_precision=0.8):
    y_true = (y_ref_series == target_class).astype(int)
    precision, _, thresholds = precision_recall_curve(y_true, p_ref_cal_series)
    valid = precision >= target_precision
    if valid.any():
        idxs = np.where(valid)[0]
        idx = idxs[-1]
        if idx == 0:
            return float(thresholds.min()) if len(thresholds) > 0 else 0.9
        return float(thresholds[max(0, idx - 1)])
    return float(np.percentile(p_ref_cal_series, 90))


def estimate_u_from_std(std_df_or_series, q=75, u_min=0.005):
    u_raw = float(np.nanpercentile(np.asarray(std_df_or_series).astype(float), q))
    return max(u_raw, float(u_min)), u_raw


def compute_candidate_mask(mean_org: pd.DataFrame, std_org: pd.DataFrame, Hnorm: pd.Series, target_class: str, t: float, u: float, v: float, obs_index):
    is_p = mean_org[target_class] >= float(t)
    is_u = std_org[target_class] <= float(u)
    is_h = Hnorm <= float(v)
    return (is_p & is_u & is_h).reindex(obs_index).fillna(False)


def select_target_candidates(mean_org, std_org, entropy_norm, target_class, thresholds, obs_index):
    candidate_mask = compute_candidate_mask(
        mean_org=mean_org,
        std_org=std_org,
        Hnorm=entropy_norm,
        target_class=target_class,
        t=thresholds.threshold_t,
        u=thresholds.threshold_u,
        v=thresholds.threshold_v,
        obs_index=obs_index,
    )
    return IdentitySelectionResult(
        candidate_mask=candidate_mask,
        thresholds=thresholds,
        target_class=target_class,
    )
