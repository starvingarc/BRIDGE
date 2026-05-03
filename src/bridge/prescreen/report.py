from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from bridge.prescreen.api import NON_RG, PRESCREEN_COLUMN, RG_CANDIDATE
from bridge.reporting import ReportResult, ensure_dir, require_obs_columns, save_figure, save_optional_umap, write_json, write_markdown, write_table
from bridge.reporting.core import STEP_COLORS, fraction_text, import_pyplot, value_counts_frame


def _prescreen_count_figure(counts: pd.Series, path_base: Path, *, formats, dpi: int) -> str:
    plt = import_pyplot()
    labels = [RG_CANDIDATE, NON_RG]
    values = [int(counts.get(label, 0)) for label in labels]
    colors = [STEP_COLORS["on"], STEP_COLORS["off"]]
    fig, ax = plt.subplots(figsize=(5.6, 4.2))
    bars = ax.bar(labels, values, color=colors)
    ax.set_ylabel("Cells")
    ax.set_title("Step1 prescreening summary")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    total = sum(values)
    for bar, value in zip(bars, values):
        pct = (value / total * 100) if total else 0.0
        ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value}\n{pct:.1f}%", ha="center", va="bottom", fontsize=9)
    return save_figure(fig, path_base, formats=formats, dpi=dpi)


def _confidence_figure(obs: pd.DataFrame, path_base: Path, *, formats, dpi: int) -> str | None:
    if "step1_pred_maxp" not in obs.columns:
        return None
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(5.6, 4.0))
    vals = pd.to_numeric(obs["step1_pred_maxp"], errors="coerce").dropna()
    ax.hist(vals, bins=20, color=STEP_COLORS["accent"], edgecolor="white")
    ax.set_xlabel("Maximum predicted probability")
    ax.set_ylabel("Cells")
    ax.set_title("Step1 prediction confidence")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return save_figure(fig, path_base, formats=formats, dpi=dpi)


def _interpret(summary: dict[str, Any]) -> dict[str, str]:
    fraction = fraction_text(summary.get("rg_candidate_fraction"))
    rg_count = summary.get("rg_candidate_count", 0)
    query_count = summary.get("query_count", 0)
    return {
        "overview": (
            f"Step1 maps the in vitro sample to a whole-brain reference and separates broad RG-like candidates from non-RG cells. "
            f"In this run, {rg_count} of {query_count} cells ({fraction}) were retained as RG candidates."
        ),
        "boundary": (
            "This step is a prescreening and composition check for in vitro data. It should be interpreted as a routing and quality-control layer before target-specific identity assessment."
        ),
    }


def write_report(
    *,
    result,
    output_dir: str | Path,
    prefix: str = "bridge",
    formats=("png",),
    dpi: int = 300,
) -> ReportResult:
    outdir = ensure_dir(output_dir)
    figdir = ensure_dir(outdir / "figures")
    tabledir = ensure_dir(outdir / "tables")
    adata = result.adata
    require_obs_columns(adata, ["step1_pred_cell_type", PRESCREEN_COLUMN], context="Step1 report")

    summary = dict(result.summary)
    counts = adata.obs[PRESCREEN_COLUMN].astype(str).value_counts()
    predicted_counts = value_counts_frame(adata.obs["step1_pred_cell_type"], label="predicted_label")
    prescreen_counts = counts.rename_axis("prescreen_label").reset_index(name="count")

    tables = {
        "predicted_label_counts": write_table(predicted_counts, tabledir / f"{prefix}.predicted_label_counts.csv"),
        "prescreen_counts": write_table(prescreen_counts, tabledir / f"{prefix}.prescreen_counts.csv"),
    }
    figures: dict[str, str] = {
        "prescreen_counts": _prescreen_count_figure(counts, figdir / f"{prefix}.prescreen_counts", formats=formats, dpi=dpi),
    }
    conf = _confidence_figure(adata.obs, figdir / f"{prefix}.prediction_confidence", formats=formats, dpi=dpi)
    if conf is not None:
        figures["prediction_confidence"] = conf

    warnings: list[str] = []
    for column, key, cmap in [
        ("step1_pred_cell_type", "predicted_cell_type_umap", None),
        ("step1_pred_maxp", "prediction_confidence_umap", "Reds"),
        ("cell_type", "cell_type_umap", None),
    ]:
        if column not in adata.obs.columns:
            warnings.append(f"Skipped UMAP for missing column '{column}'.")
            continue
        umap = save_optional_umap(adata, color=column, path_base=figdir / f"{prefix}.{key}", title=column, cmap=cmap, formats=formats, dpi=dpi)
        if umap is None:
            warnings.append("Skipped UMAP figures because adata.obsm['X_umap'] is not available.")
            break
        figures[key] = umap

    interpretation = _interpret(summary)
    markdown = [
        f"# Step1 Prescreening Report: {prefix}",
        "",
        "## Summary",
        f"- Query cells: {summary.get('query_count', 'n/a')}",
        f"- RG candidates: {summary.get('rg_candidate_count', 'n/a')} ({fraction_text(summary.get('rg_candidate_fraction'))})",
        f"- Non-RG cells: {summary.get('non_rg_count', 'n/a')}",
        "",
        "## Interpretation",
        interpretation["overview"],
        "",
        interpretation["boundary"],
    ]
    markdown_report = write_markdown(markdown, outdir / f"{prefix}.step1_report.md")
    manifest = {
        "step": "step1_prescreen",
        "prefix": prefix,
        "figures": figures,
        "tables": tables,
        "summary": summary,
        "interpretation": interpretation,
        "warnings": warnings,
    }
    manifest_json = write_json(manifest, outdir / f"{prefix}.step1_report_manifest.json")
    return ReportResult(figures=figures, tables=tables, markdown_report=markdown_report, manifest_json=manifest_json, interpretation=interpretation)
