from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from bridge.cls import CLSContext, CLSResult
from bridge.cls.report import compare_reports, write_report
from bridge.common.results import CLSComponentResult
from tests.helpers import DummyAnnData


def _component(name: str, score: float, score_df: pd.DataFrame | None = None, meta: dict | None = None) -> CLSComponentResult:
    if score_df is None:
        score_df = pd.DataFrame({"batch": ["b1"], "n_cells": [10], f"s{name}": [score]})
    return CLSComponentResult(component=name, score_df=score_df, global_score=score, meta=meta or {})


def _cls_result(tmp_path: Path) -> tuple[CLSResult, CLSContext]:
    components = {
        "A": _component("A", 0.8, pd.DataFrame({"batch": ["b1"], "n_cells": [10], "sA1_mean": [0.82], "sA2_ks": [0.78], "sA": [0.8]})),
        "B": _component("B", 0.9, pd.DataFrame({"batch": ["b1"], "n_cells": [10], "r": [0.8], "sB": [0.9]})),
        "C": _component("C", 0.85, pd.DataFrame({"batch": ["b1"], "n_cells": [10], "AUC_org": [0.93], "sC": [0.85]}), {"auc_ref_details": {"AUC_ref": 0.9}}),
        "D": _component("D", 0.7, pd.DataFrame({"batch": ["b1"], "n_candidate": [10], "sD_query": [0.8], "sD_ref": [0.62], "sD": [0.7]})),
        "E": _component("E", 0.6, pd.DataFrame({"branch": ["main"], "branch_weight": [1.0], "E_dev": [0.6]})),
        "F": _component("F", 0.75, pd.DataFrame({"batch": ["b1"], "n_cells": [10], "J": [0.7], "ra": [0.8], "sF": [0.75]})),
    }
    result = CLSResult(
        component_results=components,
        component_payloads={k: v.to_payload("demo") for k, v in components.items()},
        summary=pd.DataFrame([{"dataset_id": "demo", "weighted_total_cls": 0.77}]),
        manifest={"dataset_id": "demo"},
        weighted_total_cls=0.77,
        output_paths={"summary_csv": str(tmp_path / "summary.csv"), "manifest_json": str(tmp_path / "manifest.json")},
    )
    ctx = CLSContext(
        bdata=DummyAnnData(pd.DataFrame({"is_candidate_mDA": [True, False]}, index=["q1", "q2"])),
        adata_ref=DummyAnnData(pd.DataFrame(index=["r1", "r2"])),
        target_class="mDA",
        output_dir=tmp_path,
        dataset_id="demo",
    )
    return result, ctx


def test_cls_report_writes_single_dataset_figures_manifest_and_warnings(tmp_path):
    result, ctx = _cls_result(tmp_path)

    report = write_report(result=result, ctx=ctx, output_dir=tmp_path / "report", prefix="demo")

    assert Path(report.markdown_report).exists()
    assert Path(report.manifest_json).exists()
    assert Path(report.figures["component_scores_bar"]).exists()
    assert Path(report.figures["component_scores_heatmap"]).exists()
    assert Path(report.figures["component_A_identity"]).exists()
    assert Path(report.figures["component_E_pseudotime"]).exists()
    assert "component_F_activity_alignment" not in report.figures

    manifest = json.loads(Path(report.manifest_json).read_text(encoding="utf-8"))
    assert manifest["summary"]["weighted_total_cls"] == 0.77
    assert any("component F" in warning for warning in manifest["warnings"])


def _write_component_json(base: Path, dataset_id: str, component: str, score: float) -> None:
    comp_dir = base / dataset_id / component
    comp_dir.mkdir(parents=True, exist_ok=True)
    payload = {"component": component, "dataset_id": dataset_id, "global_score": score, "meta": {}}
    (comp_dir / f"component_{component}_global.json").write_text(json.dumps(payload), encoding="utf-8")


def test_compare_reports_computes_weighted_cls_and_writes_comparison_figures(tmp_path):
    scores = {
        "sphere": {"A": 0.8, "B": 0.9, "C": 0.85, "D": 0.7, "E": 0.6, "F": 0.75},
        "macro": {"A": 0.65, "B": 0.92, "C": 0.9, "D": 0.72, "E": 0.74, "F": 0.76},
    }
    for dataset_id, comps in scores.items():
        for component, score in comps.items():
            _write_component_json(tmp_path, dataset_id, component, score)

    report = compare_reports(
        protocols=[
            {"name": "SphereDiff", "dataset_id": "sphere", "step3_dir": tmp_path},
            {"name": "MacroDiff", "dataset_id": "macro", "step3_dir": tmp_path},
        ],
        output_dir=tmp_path / "comparison",
        prefix="cls_comparison",
    )

    assert Path(report.tables["component_scores"]).exists()
    assert Path(report.figures["comparison_radar"]).exists()
    assert Path(report.figures["comparison_weighted_cls"]).exists()
    assert Path(report.figures["comparison_heatmap"]).exists()
    df = pd.read_csv(report.tables["component_scores"])
    assert set(df["Protocol"]) == {"SphereDiff", "MacroDiff"}
    assert df["CLS"].between(0, 1).all()


def test_compare_reports_warns_when_component_artifact_is_missing(tmp_path):
    _write_component_json(tmp_path, "sphere", "A", 0.8)

    report = compare_reports(
        protocols=[{"name": "SphereDiff", "dataset_id": "sphere", "step3_dir": tmp_path}],
        output_dir=tmp_path / "comparison",
        prefix="cls_comparison",
    )

    manifest = json.loads(Path(report.manifest_json).read_text(encoding="utf-8"))
    assert any("missing" in warning.lower() for warning in manifest["warnings"])



def test_cls_report_public_notebook_helpers(tmp_path):
    from bridge.cls.report import build_component_score_table, build_interpretation, plot_component_A, plot_component_scores_bar, plot_component_scores_heatmap, plot_weighted_cls

    result, ctx = _cls_result(tmp_path)
    score_df = build_component_score_table(result)
    interpretation = build_interpretation(result)
    fig_bar = plot_component_scores_bar(score_df)
    fig_heatmap = plot_component_scores_heatmap(score_df)
    fig_weighted = plot_weighted_cls(result.weighted_total_cls)
    fig_a = plot_component_A(result.component_results["A"])

    assert score_df["Component"].tolist()[:2] == ["A", "B"]
    assert "overview" in interpretation
    assert fig_bar is not None
    assert fig_heatmap is not None
    assert fig_weighted is not None
    assert fig_a is not None

def _write_component_batch(base: Path, dataset_id: str, component: str, df: pd.DataFrame) -> None:
    comp_dir = base / dataset_id / component
    comp_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(comp_dir / f"component_{component}_batch.csv", index=False)


def _write_component_genes(base: Path, dataset_id: str, df: pd.DataFrame) -> None:
    comp_dir = base / dataset_id / "E"
    comp_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(comp_dir / "component_E_genes.csv", index=False)


def test_compare_reports_writes_thesis_style_component_diagnostics(tmp_path):
    for idx, dataset_id in enumerate(["sphere", "macro"]):
        scores = {"A": 0.8 - idx * 0.05, "B": 0.9, "C": 0.95, "D": 0.75, "E": 0.7, "F": 0.76}
        for component, score in scores.items():
            _write_component_json(tmp_path, dataset_id, component, score)
        _write_component_batch(
            tmp_path,
            dataset_id,
            "A",
            pd.DataFrame({"batch": ["b1", "b2"], "n_cells": [20, 30], "sA1_mean": [0.86, 0.92], "sA2_ks": [0.62, 0.72]}),
        )
        _write_component_batch(
            tmp_path,
            dataset_id,
            "C",
            pd.DataFrame({"batch": ["b1", "b2"], "n_candidate": [20, 30], "AUC_org": [0.96, 0.98], "AUC_ref": [0.97, 0.97], "sC": [0.99, 0.99]}),
        )
        _write_component_batch(
            tmp_path,
            dataset_id,
            "D",
            pd.DataFrame({"batch": ["b1", "b2"], "n_candidate": [20, 30], "sD_query": [0.85, 0.9], "sD_ref": [0.7, 0.75], "sD": [0.77, 0.82]}),
        )
        _write_component_genes(
            tmp_path,
            dataset_id,
            pd.DataFrame({"gene": [f"G{i}" for i in range(30)], "rho": [(-1 + i / 15) for i in range(30)]}),
        )

    report = compare_reports(
        protocols=[
            {"name": "SphereDiff", "dataset_id": "sphere", "step3_dir": tmp_path},
            {"name": "MacroDiff", "dataset_id": "macro", "step3_dir": tmp_path},
        ],
        output_dir=tmp_path / "comparison_with_batches",
        prefix="cls_comparison",
    )

    for key in [
        "comparison_component_scores",
        "comparison_weighted_contribution",
        "comparison_component_A_identity",
        "comparison_component_C_transfer_auc",
        "comparison_component_D_neighborhood",
        "comparison_component_E_pseudotime",
    ]:
        assert key in report.figures
        assert Path(report.figures[key]).exists()
