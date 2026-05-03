from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from bridge.prescreen import PrescreenResult
from bridge.prescreen.report import write_report
from tests.helpers import DummyAnnData


def test_prescreen_report_writes_manifest_markdown_and_summary_table(tmp_path):
    obs = pd.DataFrame(
        {
            "step1_pred_cell_type": ["Radial Glia", "Neuroblast", "Radial Glia"],
            "step1_pred_maxp": [0.91, 0.73, 0.82],
            "step1_rg_prob": [0.91, 0.15, 0.82],
            "step1_is_rg": [True, False, True],
            "step1_prescreen": ["RG_candidate", "non_RG", "RG_candidate"],
        },
        index=["c1", "c2", "c3"],
    )
    result = PrescreenResult(
        adata=DummyAnnData(obs),
        probabilities=pd.DataFrame({"Radial Glia": [0.91, 0.15, 0.82], "Neuroblast": [0.09, 0.85, 0.18]}, index=obs.index),
        annotations=obs.copy(),
        summary={
            "query_count": 3,
            "rg_candidate_count": 2,
            "non_rg_count": 1,
            "rg_candidate_fraction": 2 / 3,
            "predicted_label_counts": {"Radial Glia": 2, "Neuroblast": 1},
        },
        output_paths={},
    )

    report = write_report(result=result, output_dir=tmp_path, prefix="demo")

    assert Path(report.markdown_report).exists()
    assert Path(report.manifest_json).exists()
    assert Path(report.tables["predicted_label_counts"]).exists()
    assert Path(report.figures["prescreen_counts"]).exists()
    assert "cell_type_umap" not in report.figures

    markdown = Path(report.markdown_report).read_text(encoding="utf-8")
    banned = ["accuracy", "recall", "confusion", "crosstab"]
    assert all(word not in markdown.lower() for word in banned)
    manifest = json.loads(Path(report.manifest_json).read_text(encoding="utf-8"))
    assert manifest["summary"]["rg_candidate_count"] == 2



def test_prescreen_report_public_notebook_helpers():
    from bridge.prescreen.report import build_interpretation, build_report_tables, plot_prediction_confidence, plot_prescreen_counts

    obs = pd.DataFrame(
        {
            "step1_pred_cell_type": ["Radial Glia", "Neuroblast", "Radial Glia"],
            "step1_pred_maxp": [0.91, 0.73, 0.82],
            "step1_prescreen": ["RG_candidate", "non_RG", "RG_candidate"],
        },
        index=["c1", "c2", "c3"],
    )
    result = PrescreenResult(
        adata=DummyAnnData(obs),
        probabilities=pd.DataFrame(index=obs.index),
        annotations=obs.copy(),
        summary={"query_count": 3, "rg_candidate_count": 2, "non_rg_count": 1, "rg_candidate_fraction": 2 / 3},
        output_paths={},
    )

    tables = build_report_tables(result)
    interpretation = build_interpretation(result)
    fig_counts = plot_prescreen_counts(result)
    fig_conf = plot_prediction_confidence(result)

    assert set(tables) == {"predicted_label_counts", "prescreen_counts"}
    assert tables["prescreen_counts"]["count"].sum() == 3
    assert "overview" in interpretation
    assert fig_counts is not None
    assert fig_conf is not None
