from __future__ import annotations

import pandas as pd

from bridge.identity.uncertainty import ensemble_mean_std


def test_ensemble_mean_std_preserves_axes_and_handles_single_member():
    df = pd.DataFrame({"A": [0.2, 0.3], "B": [0.8, 0.7]}, index=["x", "y"])
    mean_df, std_df = ensemble_mean_std([df])
    assert list(mean_df.index) == ["x", "y"]
    assert list(mean_df.columns) == ["A", "B"]
    assert mean_df.equals(df)
    assert std_df.loc["x", "A"] == 0.0
