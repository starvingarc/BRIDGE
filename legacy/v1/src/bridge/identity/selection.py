from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve

from bridge.identity.results import IdentitySelectionResult, IdentityThresholds


def calibrate_threshold_from_ref(p_ref_cal_series, y_ref_series, target_class, target_precision=0.8, threshold_beta=0.5):
    scores = pd.Series(p_ref_cal_series).astype(float)
    labels = pd.Series(y_ref_series).reindex(scores.index).astype(str)
    y_true = (labels == str(target_class)).astype(int)
    if int(y_true.sum()) == 0:
        return float(np.percentile(scores, 90))

    precision, recall, thresholds = precision_recall_curve(y_true, scores)
    if len(thresholds) == 0:
        return 0.9

    # precision_recall_curve adds a final artificial point with no threshold that
    # corresponds to selecting no cells. Use real thresholds only, then choose the
    # best F-beta point among thresholds that meet the requested precision. beta<1
    # favors precision, but still avoids collapsing recall to zero.
    precision_t = precision[:-1]
    recall_t = recall[:-1]
    valid = precision_t >= float(target_precision)
    if valid.any():
        beta2 = float(threshold_beta) ** 2
        f_beta = (1.0 + beta2) * precision_t * recall_t / (beta2 * precision_t + recall_t + 1e-12)
        valid_idxs = np.where(valid)[0]
        best_idx = valid_idxs[int(np.nanargmax(f_beta[valid_idxs]))]
        return float(thresholds[best_idx])
    return float(np.percentile(scores, 90))


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
