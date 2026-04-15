from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from bridge.identity.results import IdentityProbabilities


def fit_isotonic_per_class(probs_ref_df, y_ref_series, class_names):
    calibrators = {}
    y_bin = pd.get_dummies(y_ref_series).reindex(index=probs_ref_df.index, columns=class_names).fillna(0)
    for cls in class_names:
        x = probs_ref_df[cls].values
        y = y_bin[cls].values
        if len(np.unique(x)) < 5 or y.sum() < 10:
            calibrators[cls] = None
            continue
        ir = IsotonicRegression(out_of_bounds="clip")
        ir.fit(x, y)
        calibrators[cls] = ir
    return calibrators


def apply_calibrators(probs_df, calibrators):
    cal = probs_df.copy()
    for cls, ir in calibrators.items():
        if ir is None:
            cal[cls] = probs_df[cls].values
        else:
            cal[cls] = ir.predict(probs_df[cls].values)
    cal = cal.clip(0, 1)
    cal = cal.div(cal.sum(axis=1).replace(0, 1.0), axis=0)
    return cal


def calibrate_probs(probs_ref: pd.DataFrame, y_ref_series: pd.Series, probs_query: pd.DataFrame):
    class_names = list(probs_ref.columns) if probs_ref is not None else list(probs_query.columns)
    calibrators = fit_isotonic_per_class(probs_ref, y_ref_series.astype(str), class_names)
    probs_ref_cal = apply_calibrators(probs_ref.reindex(columns=class_names).fillna(0), calibrators)
    probs_query_cal = apply_calibrators(probs_query.reindex(columns=class_names).fillna(0), calibrators)
    print("[identity_assessment] Calibration done.")
    return probs_ref_cal, probs_query_cal, calibrators


def build_identity_probabilities(
    probs_ref_raw: pd.DataFrame,
    probs_query_raw: pd.DataFrame,
    y_ref_series: pd.Series,
    target_class: str,
) -> IdentityProbabilities:
    probs_ref_cal, probs_query_cal, calibrators = calibrate_probs(
        probs_ref=probs_ref_raw,
        y_ref_series=y_ref_series,
        probs_query=probs_query_raw,
    )
    return IdentityProbabilities(
        probs_ref_raw=probs_ref_raw,
        probs_ref_cal=probs_ref_cal,
        probs_query_raw=probs_query_raw,
        probs_query_cal=probs_query_cal,
        class_names=list(probs_ref_cal.columns),
        target_class=target_class,
        calibrators=calibrators,
    )
