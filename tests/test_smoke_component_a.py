from __future__ import annotations

import json

import pandas as pd

from bridge.cls.component_a import compute_A_and_save
from tests.helpers import DummyAnnData


def test_smoke_identity_outputs_to_component_a_wrapper(tmp_path):
    b_obs = pd.DataFrame(
        {
            "Sample": ["S1", "S1", "S2", "S2"],
            "is_candidate_RG": [True, True, True, True],
            "p_mean_RG": [0.9, 0.8, 0.7, 0.75],
        },
        index=["b1", "b2", "b3", "b4"],
    )
    ref_obs = pd.DataFrame({"cell_subtype": ["RG", "RG", "OTHER"]}, index=["r1", "r2", "r3"])
    bdata = DummyAnnData(b_obs)
    adata_ref = DummyAnnData(ref_obs)
    probs_ref_cal = pd.DataFrame({"RG": [0.95, 0.9, 0.1]}, index=ref_obs.index)
    score_df, global_score, payload = compute_A_and_save(
        bdata=bdata,
        adata_ref=adata_ref,
        probs_ref_cal=probs_ref_cal,
        target_class="RG",
        outdir=str(tmp_path),
        dataset_id="demo",
        min_cells_per_batch=2,
    )
    assert not score_df.empty
    assert 0.0 <= global_score <= 1.0
    json_path = tmp_path / "demo" / "A" / "component_A_global.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["component"] == "A"
    assert payload["component"] == "A"
