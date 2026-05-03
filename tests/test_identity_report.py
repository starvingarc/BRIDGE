from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from bridge.identity.report import assign_mean_probability_identity, write_report
from bridge.identity.results import IdentityResult, IdentityThresholds
from tests.helpers import DummyAnnData


TARGET = "RG_Mesencephalon_FP"


def _identity_result() -> IdentityResult:
    obs = pd.DataFrame(
        {
            f"is_candidate_{TARGET}": [True, False, True],
            f"p_mean_{TARGET}": [0.92, 0.62, 0.86],
            f"p_std_{TARGET}": [0.02, 0.09, 0.03],
            f"p_cal_{TARGET}": [0.9, 0.55, 0.84],
            "Hnorm": [0.18, 0.71, 0.22],
        },
        index=["q1", "q2", "q3"],
    )
    bdata = DummyAnnData(obs)
    mean_prob = pd.DataFrame(
        {
            TARGET: [0.92, 0.62, 0.86],
            "RG_Hypothalamus": [0.05, 0.31, 0.08],
            "RG_MHB": [0.03, 0.07, 0.06],
        },
        index=obs.index,
    )
    thresholds = IdentityThresholds(
        threshold_t=0.75,
        threshold_u=0.05,
        threshold_v=0.8,
        u_raw=0.04,
        target_precision=0.8,
    )
    return IdentityResult(
        bdata=bdata,
        adata_ref=DummyAnnData(pd.DataFrame(index=["r1", "r2"])),
        probabilities=SimpleNamespace(probs_ref_cal=pd.DataFrame(), probs_query_cal=mean_prob),
        uncertainty=SimpleNamespace(mean_prob=mean_prob, std_prob=mean_prob * 0.05, entropy_norm=pd.Series([0.18, 0.71, 0.22], index=obs.index)),
        selection=SimpleNamespace(candidate_mask=pd.Series([True, False, True], index=obs.index), thresholds=thresholds, target_class=TARGET),
        summary={
            "query_count": 3,
            "target_class": TARGET,
            "candidate_count": 2,
            "non_candidate_count": 1,
            "candidate_fraction": 2 / 3,
            "thresholds": {"t": 0.75, "u": 0.05, "u_raw": 0.04, "v": 0.8, "target_precision": 0.8},
        },
        output_paths={},
    )


def test_assign_mean_probability_identity_marks_low_confidence_as_uncertain():
    mean_prob = pd.DataFrame({TARGET: [0.91, 0.72], "Other": [0.09, 0.28]}, index=["q1", "q2"])

    pred, maxp = assign_mean_probability_identity(mean_prob, uncertain_cutoff=0.8)

    assert pred.to_dict() == {"q1": TARGET, "q2": "Uncertain"}
    assert maxp.to_dict() == {"q1": 0.91, "q2": 0.72}


def test_identity_report_writes_thresholds_candidate_summary_and_figures(tmp_path):
    result = _identity_result()

    report = write_report(result=result, output_dir=tmp_path, prefix="demo", target_class=TARGET)

    assert Path(report.markdown_report).exists()
    assert Path(report.manifest_json).exists()
    assert Path(report.tables["candidate_summary"]).exists()
    assert Path(report.figures["candidate_fraction"]).exists()
    assert result.bdata.obs.loc["q2", "pred_identity_meanorg"] == "Uncertain"

    markdown = Path(report.markdown_report).read_text(encoding="utf-8")
    assert "identity stability" in markdown
    assert "threshold" in markdown.lower()
    manifest = json.loads(Path(report.manifest_json).read_text(encoding="utf-8"))
    assert manifest["summary"]["candidate_count"] == 2
    assert manifest["summary"]["thresholds"]["t"] == 0.75


def test_identity_report_requires_step2_obs_columns(tmp_path):
    result = _identity_result()
    del result.bdata.obs[f"p_std_{TARGET}"]

    with pytest.raises(KeyError, match="p_std"):
        write_report(result=result, output_dir=tmp_path, prefix="demo", target_class=TARGET)



def test_identity_report_public_notebook_helpers():
    from bridge.identity.report import build_interpretation, build_report_tables, plot_candidate_fraction, plot_identity_composition, plot_metric_histograms

    result = _identity_result()
    tables = build_report_tables(result, target_class=TARGET)
    interpretation = build_interpretation(result, target_class=TARGET)
    fig_fraction = plot_candidate_fraction(result, target_class=TARGET)
    fig_metrics = plot_metric_histograms(result, target_class=TARGET)
    fig_comp = plot_identity_composition(tables["identity_composition"])

    assert set(tables) == {"candidate_summary", "thresholds", "identity_composition"}
    assert tables["candidate_summary"].loc[0, "candidate_count"] == 2
    assert "candidate_selection" in interpretation
    assert fig_fraction is not None
    assert fig_metrics is not None
    assert fig_comp is not None
