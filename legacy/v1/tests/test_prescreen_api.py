from __future__ import annotations

import pandas as pd

from bridge.prescreen import PrescreenResult, build_prescreen_summary, prescreen
from tests.helpers import DummyAnnData


def test_prescreen_public_imports_do_not_require_scvi_at_import_time():
    assert callable(prescreen)
    assert PrescreenResult.__name__ == "PrescreenResult"


def test_build_prescreen_summary_counts_candidates():
    adata = DummyAnnData(
        pd.DataFrame(
            {
                "step1_pred_cell_type": ["Radial Glia", "Neuroblast", "Radial Glia"],
                "step1_prescreen": ["RG_candidate", "non_RG", "RG_candidate"],
            },
            index=["c1", "c2", "c3"],
        )
    )

    summary = build_prescreen_summary(adata, rg_label="Radial Glia", train_query=False, max_epochs=0)

    assert summary["query_count"] == 3
    assert summary["rg_candidate_count"] == 2
    assert summary["non_rg_count"] == 1
    assert summary["rg_candidate_fraction"] == 2 / 3
    assert summary["predicted_label_counts"] == {"Radial Glia": 2, "Neuroblast": 1}
    assert summary["training"] == {"train_query": False, "max_epochs": 0}
