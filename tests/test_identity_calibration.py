from __future__ import annotations

import pandas as pd

from bridge.identity.calibration import apply_calibrators, fit_isotonic_per_class


def test_fit_isotonic_per_class_falls_back_for_low_support():
    probs = pd.DataFrame({"A": [0.1, 0.2, 0.3, 0.4], "B": [0.9, 0.8, 0.7, 0.6]}, index=list("wxyz"))
    y = pd.Series(["A", "B", "A", "B"], index=probs.index)
    calibrators = fit_isotonic_per_class(probs, y, ["A", "B"])
    assert calibrators["A"] is None
    assert calibrators["B"] is None


def test_apply_calibrators_normalizes_rows():
    probs = pd.DataFrame({"A": [0.8, 0.2], "B": [0.2, 0.8]}, index=["c1", "c2"])
    calibrated = apply_calibrators(probs, {"A": None, "B": None})
    assert ((calibrated >= 0.0) & (calibrated <= 1.0)).all().all()
    assert calibrated.sum(axis=1).round(6).tolist() == [1.0, 1.0]
