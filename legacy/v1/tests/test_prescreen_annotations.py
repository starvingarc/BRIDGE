from __future__ import annotations

import pandas as pd

from bridge.prescreen.api import build_prescreen_annotations, write_prescreen_outputs_to_obs
from tests.helpers import DummyAnnData


def test_build_prescreen_annotations_reindexes_probabilities_to_obs_order():
    adata = DummyAnnData(pd.DataFrame(index=["c2", "c1"]))
    probs = pd.DataFrame(
        {
            "Radial Glia": [0.1, 0.9],
            "Neuroblast": [0.8, 0.05],
        },
        index=["c1", "c2"],
    )

    annotations = build_prescreen_annotations(adata, probs, rg_label="Radial Glia")

    assert list(annotations.index) == ["c2", "c1"]
    assert annotations.loc["c2", "step1_pred_cell_type"] == "Radial Glia"
    assert annotations.loc["c1", "step1_pred_cell_type"] == "Neuroblast"
    assert annotations.loc["c2", "step1_prescreen"] == "RG_candidate"
    assert annotations.loc["c1", "step1_prescreen"] == "non_RG"


def test_missing_rg_column_gets_zero_rg_probability():
    adata = DummyAnnData(pd.DataFrame(index=["c1", "c2"]))
    probs = pd.DataFrame({"Neuroblast": [0.8, 0.9]}, index=["c1", "c2"])

    annotations = build_prescreen_annotations(adata, probs, rg_label="Radial Glia")

    assert annotations["step1_rg_prob"].tolist() == [0.0, 0.0]
    assert annotations["step1_prescreen"].tolist() == ["non_RG", "non_RG"]


def test_write_prescreen_outputs_to_obs_preserves_obs_order():
    adata = DummyAnnData(pd.DataFrame(index=["c2", "c1"]))
    probs = pd.DataFrame(
        {
            "Radial Glia": [0.1, 0.9],
            "Neuroblast": [0.8, 0.05],
        },
        index=["c1", "c2"],
    )

    write_prescreen_outputs_to_obs(adata, probs, rg_label="Radial Glia")

    assert list(adata.obs.index) == ["c2", "c1"]
    assert adata.obs["step1_pred_cell_type"].tolist() == ["Radial Glia", "Neuroblast"]
    assert adata.obs["step1_is_rg"].tolist() == [True, False]
    assert adata.obs["step1_prescreen"].tolist() == ["RG_candidate", "non_RG"]
