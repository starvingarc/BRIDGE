from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from bridge.reporting import ReportResult, ensure_dir, plot_umap, require_obs_columns, save_figure, save_optional_umap, write_json, write_markdown, write_table
from bridge.reporting.core import STEP_COLORS, fraction_text, import_pyplot, value_counts_frame

OBS_IDENTITY_COL = "pred_identity_meanorg"
OBS_IDENTITY_MAXP_COL = "pred_identity_meanorg_maxp"


def assign_mean_probability_identity(mean_prob: pd.DataFrame, uncertain_cutoff: float = 0.8) -> tuple[pd.Series, pd.Series]:
    probs = mean_prob.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    max_prob = probs.max(axis=1).astype(float)
    pred = probs.idxmax(axis=1).astype(str)
    pred.loc[max_prob < float(uncertain_cutoff)] = "Uncertain"
    return pred, max_prob


def _target_class(result, target_class: str | None) -> str:
    target = target_class or getattr(result.selection, "target_class", None) or result.summary.get("target_class")
    if not target:
        raise ValueError("target_class must be provided for Step2 identity report.")
    return str(target)


def _write_identity_predictions(bdata, mean_prob: pd.DataFrame, uncertain_cutoff: float) -> pd.DataFrame:
    pred, maxp = assign_mean_probability_identity(mean_prob, uncertain_cutoff=uncertain_cutoff)
    common = bdata.obs_names.intersection(pred.index)
    bdata.obs[OBS_IDENTITY_COL] = "Uncertain"
    bdata.obs.loc[common, OBS_IDENTITY_COL] = pred.loc[common].astype(str).values
    bdata.obs[OBS_IDENTITY_MAXP_COL] = float("nan")
    bdata.obs.loc[common, OBS_IDENTITY_MAXP_COL] = maxp.loc[common].astype(float).values
    return value_counts_frame(bdata.obs[OBS_IDENTITY_COL], label="pred_identity")


def build_report_tables(result, *, target_class: str | None = None, uncertain_cutoff: float = 0.8) -> dict[str, pd.DataFrame]:
    target = _target_class(result, target_class)
    bdata = result.bdata
    flag_col = f"is_candidate_{target}"
    pmean_col = f"p_mean_{target}"
    pstd_col = f"p_std_{target}"
    required = [flag_col, pmean_col, pstd_col, "Hnorm"]
    require_obs_columns(bdata, required, context="Step2 report")
    composition = _write_identity_predictions(bdata, result.uncertainty.mean_prob, uncertain_cutoff=uncertain_cutoff)
    summary = dict(result.summary)
    return {
        "candidate_summary": pd.DataFrame([
            {
                "query_count": summary.get("query_count"),
                "candidate_count": summary.get("candidate_count"),
                "non_candidate_count": summary.get("non_candidate_count"),
                "candidate_fraction": summary.get("candidate_fraction"),
                "target_class": target,
            }
        ]),
        "thresholds": pd.DataFrame([summary.get("thresholds", {})]),
        "identity_composition": composition,
    }


def build_interpretation(result_or_summary, *, target_class: str | None = None) -> dict[str, str]:
    summary = dict(getattr(result_or_summary, "summary", result_or_summary))
    target = target_class or summary.get("target_class") or "target class"
    return {
        "overview": (
            f"Step2 evaluates whether Step1 RG candidates have stably converged toward {target}. "
            f"The report combines target mean probability, prediction variability, and normalized entropy to describe identity stability."
        ),
        "candidate_selection": (
            f"The integrated filter retained {summary.get('candidate_count', 'n/a')} cells "
            f"({fraction_text(summary.get('candidate_fraction'))}) as high-confidence target candidates. "
            "Cells with high target probability but elevated variability or entropy should be interpreted as boundary, transitional, or competing-fate states rather than fully stable targets."
        ),
        "thresholds": (
            "The probability, uncertainty, and entropy thresholds jointly constrain confidence, stability, and distributional clarity before CLS scoring."
        ),
    }


def plot_candidate_fraction(result, *, target_class: str | None = None):
    target = _target_class(result, target_class)
    bdata = result.bdata
    flag_col = f"is_candidate_{target}"
    plt = import_pyplot()
    counts = bdata.obs[flag_col].astype(bool).value_counts()
    sizes = [int(counts.get(True, 0)), int(counts.get(False, 0))]
    labels = ["On-target", "Off-target"]
    colors = [STEP_COLORS["on"], STEP_COLORS["off"]]
    fig, ax = plt.subplots(figsize=(5.4, 5.0))
    wedges, _, _ = ax.pie(
        sizes, labels=None, autopct=lambda p: f"{p:.1f}%" if p >= 3 else "", pctdistance=0.65,
        startangle=90, colors=colors, wedgeprops={"width": 0.58, "edgecolor": "white"}, textprops={"color": "black", "fontsize": 11},
    )
    ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False)
    ax.set_title("Step2 candidate fraction")
    ax.axis("equal")
    return fig


def plot_metric_histograms(result, *, target_class: str | None = None, columns: list[str] | None = None):
    target = _target_class(result, target_class)
    bdata = result.bdata
    if columns is None:
        pcal_col = f"p_cal_{target}"
        columns = [f"p_mean_{target}", f"p_std_{target}", "Hnorm"] + ([pcal_col] if pcal_col in bdata.obs.columns else [])
    plt = import_pyplot()
    fig, axes = plt.subplots(1, len(columns), figsize=(4.2 * len(columns), 3.6))
    if len(columns) == 1:
        axes = [axes]
    cmaps = [STEP_COLORS["accent"], "#c44e52", "#4c72b0", "#55a868"]
    for ax, column, color in zip(axes, columns, cmaps):
        vals = pd.to_numeric(bdata.obs[column], errors="coerce").dropna()
        ax.hist(vals, bins=20, color=color, edgecolor="white")
        ax.set_title(column)
        ax.set_xlabel("Value")
        ax.set_ylabel("Cells")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return fig


def plot_identity_composition(composition: pd.DataFrame):
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    comp = composition.sort_values("count", ascending=False)
    ax.bar(comp["pred_identity"].astype(str), comp["count"], color=STEP_COLORS["accent"])
    ax.set_ylabel("Cells")
    ax.set_title("Mean-probability identity assignment")
    ax.tick_params(axis="x", rotation=35)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return fig


def plot_identity_umap(result, *, color: str, title: str | None = None, cmap: str | None = None):
    bdata = result.bdata
    if color not in bdata.obs.columns:
        return None
    return plot_umap(bdata, color=color, title=title or color, cmap=cmap)


def plot_mean_identity_umap(result):
    return plot_identity_umap(result, color=OBS_IDENTITY_COL, title="Mean-probability identity")


def plot_target_pmean_umap(result, *, target_class: str | None = None):
    target = _target_class(result, target_class)
    return plot_identity_umap(result, color=f"p_mean_{target}", title=f"Target mean probability: {target}", cmap="coolwarm")


def plot_target_pstd_umap(result, *, target_class: str | None = None):
    target = _target_class(result, target_class)
    return plot_identity_umap(result, color=f"p_std_{target}", title=f"Target probability variability: {target}", cmap="Reds")


def plot_entropy_umap(result):
    return plot_identity_umap(result, color="Hnorm", title="Normalized entropy", cmap="Blues")


def plot_candidate_umap(result, *, target_class: str | None = None):
    target = _target_class(result, target_class)
    return plot_identity_umap(result, color=f"is_candidate_{target}", title=f"Step2 candidates: {target}")


def _candidate_fraction_figure(result, target_class: str, path_base: Path, *, formats, dpi: int) -> str:
    return save_figure(plot_candidate_fraction(result, target_class=target_class), path_base, formats=formats, dpi=dpi)


def _metric_histograms(result, target_class: str, path_base: Path, *, formats, dpi: int) -> str:
    return save_figure(plot_metric_histograms(result, target_class=target_class), path_base, formats=formats, dpi=dpi)


def _composition_figure(composition: pd.DataFrame, path_base: Path, *, formats, dpi: int) -> str:
    return save_figure(plot_identity_composition(composition), path_base, formats=formats, dpi=dpi)


def write_report(
    *,
    result,
    output_dir: str | Path,
    prefix: str = "bridge",
    target_class: str | None = None,
    uncertain_cutoff: float = 0.8,
    formats=("png",),
    dpi: int = 300,
) -> ReportResult:
    outdir = ensure_dir(output_dir)
    figdir = ensure_dir(outdir / "figures")
    tabledir = ensure_dir(outdir / "tables")
    target_class = _target_class(result, target_class)
    bdata = result.bdata

    flag_col = f"is_candidate_{target_class}"
    pmean_col = f"p_mean_{target_class}"
    pstd_col = f"p_std_{target_class}"
    pcal_col = f"p_cal_{target_class}"
    required = [flag_col, pmean_col, pstd_col, "Hnorm"]
    require_obs_columns(bdata, required, context="Step2 report")

    table_frames = build_report_tables(result, target_class=target_class, uncertain_cutoff=uncertain_cutoff)
    tables = {name: write_table(frame, tabledir / f"{prefix}.{name}.csv") for name, frame in table_frames.items()}
    figures = {
        "candidate_fraction": _candidate_fraction_figure(result, target_class, figdir / f"{prefix}.candidate_fraction", formats=formats, dpi=dpi),
        "identity_composition": _composition_figure(table_frames["identity_composition"], figdir / f"{prefix}.identity_composition", formats=formats, dpi=dpi),
    }
    figures["probability_uncertainty_distributions"] = _metric_histograms(result, target_class, figdir / f"{prefix}.probability_uncertainty", formats=formats, dpi=dpi)

    warnings: list[str] = []
    for column, key, cmap in [
        (OBS_IDENTITY_COL, "identity_umap", None),
        (pmean_col, "target_pmean_umap", "coolwarm"),
        (pstd_col, "target_pstd_umap", "Reds"),
        ("Hnorm", "entropy_umap", "Blues"),
        (flag_col, "candidate_umap", None),
    ]:
        umap = save_optional_umap(bdata, color=column, path_base=figdir / f"{prefix}.{key}", title=column, cmap=cmap, formats=formats, dpi=dpi)
        if umap is None:
            warnings.append("Skipped Step2 UMAP figures because bdata.obsm['X_umap'] is not available.")
            break
        figures[key] = umap

    summary = dict(result.summary)
    interpretation = build_interpretation(summary, target_class=target_class)
    markdown = [
        f"# Step2 Identity Report: {prefix}",
        "",
        "## Summary",
        f"- Target class: {target_class}",
        f"- Query cells: {summary.get('query_count', 'n/a')}",
        f"- Candidate cells: {summary.get('candidate_count', 'n/a')} ({fraction_text(summary.get('candidate_fraction'))})",
        "",
        "## Interpretation",
        interpretation["overview"],
        "",
        interpretation["candidate_selection"],
        "",
        interpretation["thresholds"],
    ]
    markdown_report = write_markdown(markdown, outdir / f"{prefix}.step2_report.md")
    manifest = {
        "step": "step2_identity",
        "prefix": prefix,
        "target_class": target_class,
        "figures": figures,
        "tables": tables,
        "summary": summary,
        "interpretation": interpretation,
        "warnings": warnings,
    }
    manifest_json = write_json(manifest, outdir / f"{prefix}.step2_report_manifest.json")
    return ReportResult(figures=figures, tables=tables, markdown_report=markdown_report, manifest_json=manifest_json, interpretation=interpretation)
