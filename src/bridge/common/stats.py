from __future__ import annotations

import numpy as np
from scipy.stats import pearsonr
from sklearn.metrics import roc_auc_score


def safe_weighted_mean(values, weights) -> float:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if values.size == 0:
        return float("nan")
    denom = weights.sum()
    if denom <= 0:
        return float(np.nanmean(values))
    return float(np.nansum(values * (weights / denom)))


def normalize_weights(weights):
    weights = np.asarray(weights, dtype=float)
    denom = weights.sum()
    if denom <= 0:
        return np.zeros_like(weights, dtype=float)
    return weights / denom


def safe_pearson(x, y) -> float:
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]
    if x.size < 2:
        return float("nan")
    if np.std(x) < 1e-12 or np.std(y) < 1e-12:
        return float("nan")
    r, _ = pearsonr(x, y)
    return float(r)


def safe_auc(y_true, y_score) -> float:
    y_true = np.asarray(y_true, dtype=int).ravel()
    y_score = np.asarray(y_score, dtype=float).ravel()
    mask = np.isfinite(y_true) & np.isfinite(y_score)
    y_true = y_true[mask]
    y_score = y_score[mask]
    if y_true.size < 2 or np.unique(y_true).size < 2:
        return float("nan")
    try:
        return float(roc_auc_score(y_true, y_score))
    except Exception:
        return float("nan")
