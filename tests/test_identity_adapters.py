from __future__ import annotations

import pandas as pd

from bridge.identity.adapters import write_identity_outputs_to_obs
from tests.helpers import DummyAnnData


def test_write_identity_outputs_to_obs_preserves_step2_column_contract():
    bdata = DummyAnnData(pd.DataFrame(index=["c2", "c1"]))
    mean_org = pd.DataFrame({"mDA": [0.2, 0.9]}, index=["c1", "c2"])
    std_org = pd.DataFrame({"mDA": [0.08, 0.01]}, index=["c1", "c2"])
    hnorm = pd.Series([0.6, 0.2], index=["c1", "c2"], name="Hnorm")
    is_candidate = pd.Series([False, True], index=["c1", "c2"])
    probs_query_cal = pd.DataFrame({"mDA": [0.3, 0.95]}, index=["c1", "c2"])

    write_identity_outputs_to_obs(
        bdata,
        "mDA",
        mean_org,
        std_org,
        hnorm,
        is_candidate,
        probs_query_cal=probs_query_cal,
    )

    assert bdata.obs["is_candidate_mDA"].tolist() == [True, False]
    assert bdata.obs["p_mean_mDA"].tolist() == [0.9, 0.2]
    assert bdata.obs["p_std_mDA"].tolist() == [0.01, 0.08]
    assert bdata.obs["p_cal_mDA"].tolist() == [0.95, 0.3]
    assert bdata.obs["Hnorm"].tolist() == [0.2, 0.6]
