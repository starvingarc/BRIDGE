from __future__ import annotations

import pandas as pd

from bridge.identity.adapters import write_identity_outputs_to_obs
from tests.helpers import DummyAnnData


def test_write_identity_outputs_to_obs_preserves_order_and_columns():
    adata = DummyAnnData(pd.DataFrame(index=["c2", "c1"]))
    mean_org = pd.DataFrame({"RG": [0.1, 0.9]}, index=["c1", "c2"])
    std_org = pd.DataFrame({"RG": [0.01, 0.02]}, index=["c1", "c2"])
    hnorm = pd.Series([0.3, 0.4], index=["c1", "c2"])
    mask = pd.Series([True, False], index=["c1", "c2"])
    probs_query_cal = pd.DataFrame({"RG": [0.11, 0.91]}, index=["c1", "c2"])
    write_identity_outputs_to_obs(adata, "RG", mean_org, std_org, hnorm, mask, probs_query_cal=probs_query_cal)
    assert list(adata.obs.index) == ["c2", "c1"]
    assert "is_candidate_RG" in adata.obs.columns
    assert "p_mean_RG" in adata.obs.columns
    assert "p_std_RG" in adata.obs.columns
    assert "p_cal_RG" in adata.obs.columns
    assert "Hnorm" in adata.obs.columns
