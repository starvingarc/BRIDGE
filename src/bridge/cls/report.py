from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from bridge.cls.api import DEFAULT_CLS_WEIGHTS
from bridge.reporting import COMPONENT_LABELS, DEFAULT_PROTOCOL_COLORS, ReportResult, ensure_dir, write_json, write_markdown, write_table
from bridge.reporting.core import import_pyplot, save_figure

_COMPONENTS = ("A", "B", "C", "D", "E", "F")


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except Exception:
        return None
    if not math.isfinite(number):
        return None
    return number


def _component_sort_key(component: str) -> tuple[int, str]:
    component = str(component).upper()
    try:
        return (_COMPONENTS.index(component), component)
    except ValueError:
        return (len(_COMPONENTS), component)


def _component_score_frame(component_results: Mapping[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for component, result in sorted(component_results.items(), key=lambda item: _component_sort_key(item[0])):
        comp = str(component).upper()
        rows.append(
            {
                "Component": comp,
                "Label": COMPONENT_LABELS.get(comp, comp),
                "Score": _finite_float(getattr(result, "global_score", np.nan)),
            }
        )
    return pd.DataFrame(rows)


def _weighted_total(scores: Mapping[str, Any], cls_weights: Mapping[str, float] | None = None) -> float | None:
    weights = DEFAULT_CLS_WEIGHTS if cls_weights is None else {str(k).upper(): float(v) for k, v in cls_weights.items()}
    pairs: list[tuple[float, float]] = []
    for component, value in scores.items():
        comp = str(component).upper()
        score = _finite_float(value)
        weight = weights.get(comp)
        if score is None or weight is None:
            continue
        pairs.append((score, float(weight)))
    if not pairs:
        return None
    denom = sum(weight for _, weight in pairs)
    if denom <= 0:
        return None
    total = sum(score * weight for score, weight in pairs) / denom
    return float(round(total, 12))


def _save_component_bar(score_df: pd.DataFrame, path_base: Path, *, formats: Sequence[str], dpi: int) -> str:
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    labels = [f"{row.Component}\n{row.Label}" for row in score_df.itertuples()]
    scores = score_df["Score"].astype(float).fillna(0.0).to_numpy()
    colors = ["#4c72b0", "#55a868", "#c44e52", "#8172b2", "#ccb974", "#64b5cd"][: len(scores)]
    bars = ax.bar(labels, scores, color=colors, edgecolor="#333333", linewidth=0.7)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Component score")
    ax.set_title("CLS component scores")
    ax.grid(axis="y", alpha=0.25, linewidth=0.7)
    for bar, score in zip(bars, scores):
        ax.text(bar.get_x() + bar.get_width() / 2, min(score + 0.025, 1.02), f"{score:.2f}", ha="center", va="bottom", fontsize=9)
    return save_figure(fig, path_base, formats=formats, dpi=dpi)


def _save_component_heatmap(score_df: pd.DataFrame, path_base: Path, *, title: str, formats: Sequence[str], dpi: int) -> str:
    plt = import_pyplot()
    values = score_df["Score"].astype(float).fillna(0.0).to_numpy()[None, :]
    fig, ax = plt.subplots(figsize=(7.6, 2.5))
    image = ax.imshow(values, vmin=0, vmax=1, cmap="YlGnBu", aspect="auto")
    ax.set_xticks(np.arange(len(score_df)))
    ax.set_xticklabels([f"{row.Component}: {row.Label}" for row in score_df.itertuples()], rotation=35, ha="right")
    ax.set_yticks([0])
    ax.set_yticklabels(["Score"])
    for idx, value in enumerate(values[0]):
        ax.text(idx, 0, f"{value:.2f}", ha="center", va="center", color="#1f1f1f", fontsize=9)
    ax.set_title(title)
    fig.colorbar(image, ax=ax, fraction=0.035, pad=0.04, label="Score")
    return save_figure(fig, path_base, formats=formats, dpi=dpi)


def _save_weighted_summary(weighted_total_cls: float | None, path_base: Path, *, formats: Sequence[str], dpi: int) -> str:
    plt = import_pyplot()
    value = 0.0 if weighted_total_cls is None else float(weighted_total_cls)
    fig, ax = plt.subplots(figsize=(5.0, 3.0))
    ax.bar(["Weighted CLS"], [value], color="#4c72b0", edgecolor="#333333", linewidth=0.7)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Weighted CLS summary")
    ax.text(0, min(value + 0.03, 1.02), "n/a" if weighted_total_cls is None else f"{value:.3f}", ha="center", va="bottom", fontsize=11)
    ax.grid(axis="y", alpha=0.25, linewidth=0.7)
    return save_figure(fig, path_base, formats=formats, dpi=dpi)


def _save_component_a(result: Any, path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    df = getattr(result, "score_df", pd.DataFrame())
    if not {"sA1_mean", "sA2_ks"}.issubset(df.columns):
        return None
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(5.2, 4.6))
    size = df["n_cells"].astype(float).clip(lower=10) if "n_cells" in df.columns else pd.Series(np.repeat(30, len(df)))
    ax.scatter(df["sA1_mean"], df["sA2_ks"], s=size * 4, color="#4c72b0", alpha=0.75, edgecolor="white", linewidth=0.7)
    if "batch" in df.columns:
        for _, row in df.iterrows():
            ax.annotate(str(row["batch"]), (row["sA1_mean"], row["sA2_ks"]), xytext=(4, 4), textcoords="offset points", fontsize=8)
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("A1 mean target probability")
    ax.set_ylabel("A2 distribution similarity")
    ax.set_title("Component A identity alignment")
    ax.grid(alpha=0.25, linewidth=0.7)
    return save_figure(fig, path_base, formats=formats, dpi=dpi)


def _save_component_b(result: Any, path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    df = getattr(result, "score_df", pd.DataFrame())
    if "sB" not in df.columns:
        return None
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    labels = df["batch"].astype(str) if "batch" in df.columns else pd.Series([str(i) for i in range(len(df))])
    ax.bar(labels, df["sB"].astype(float), color="#55a868", edgecolor="#333333", linewidth=0.6)
    if "r" in df.columns:
        ax.plot(labels, df["r"].astype(float), color="#c44e52", marker="o", linewidth=1.4, label="r")
        ax.legend(frameon=False)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Component B pseudo-bulk agreement")
    ax.tick_params(axis="x", rotation=35)
    ax.grid(axis="y", alpha=0.25, linewidth=0.7)
    return save_figure(fig, path_base, formats=formats, dpi=dpi)


def _save_component_c(result: Any, path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    df = getattr(result, "score_df", pd.DataFrame())
    if not {"AUC_org", "sC"}.issubset(df.columns):
        return None
    auc_ref = None
    meta = getattr(result, "meta", {}) or {}
    if isinstance(meta, Mapping):
        details = meta.get("auc_ref_details")
        auc_ref = details.get("AUC_ref") if isinstance(details, Mapping) else None
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(5.6, 4.4))
    x = df["AUC_org"].astype(float)
    y = df["sC"].astype(float)
    ax.scatter(x, y, s=65, color="#8172b2", alpha=0.8, edgecolor="white", linewidth=0.7)
    if auc_ref is not None:
        ax.axvline(float(auc_ref), color="#333333", linestyle="--", linewidth=1.0, label="Reference AUC")
        ax.legend(frameon=False)
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Query AUC")
    ax.set_ylabel("Component C score")
    ax.set_title("Component C transferability")
    ax.grid(alpha=0.25, linewidth=0.7)
    return save_figure(fig, path_base, formats=formats, dpi=dpi)


def _save_component_d(result: Any, path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    df = getattr(result, "score_df", pd.DataFrame())
    if not {"sD_query", "sD_ref"}.issubset(df.columns):
        return None
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(5.4, 4.7))
    sizes = df["n_candidate"].astype(float).clip(lower=5) * 4 if "n_candidate" in df.columns else pd.Series(np.repeat(45, len(df)))
    ax.scatter(df["sD_query"], df["sD_ref"], s=sizes, color="#64b5cd", alpha=0.78, edgecolor="white", linewidth=0.7)
    for iso in (0.4, 0.6, 0.8):
        ax.plot([0, 1], [iso, iso], color="#bdbdbd", linewidth=0.7, linestyle=":")
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Query neighborhood structure")
    ax.set_ylabel("Reference neighborhood structure")
    ax.set_title("Component D neighborhood concordance")
    ax.grid(alpha=0.25, linewidth=0.7)
    return save_figure(fig, path_base, formats=formats, dpi=dpi)


def _component_e_genes_path(result: Any, ctx: Any) -> Path | None:
    meta = getattr(result, "meta", {}) or {}
    for key in ("genes_csv", "component_E_genes_csv"):
        value = meta.get(key) if isinstance(meta, Mapping) else None
        if value:
            path = Path(value)
            if path.exists():
                return path
    path = Path(ctx.output_dir) / ctx.dataset_id / "E" / "component_E_genes.csv"
    return path if path.exists() else None


def _save_component_e(result: Any, ctx: Any, path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    genes_path = _component_e_genes_path(result, ctx)
    plt = import_pyplot()
    if genes_path is not None:
        genes = pd.read_csv(genes_path)
        if "rho" in genes.columns:
            fig, ax = plt.subplots(figsize=(5.8, 3.8))
            ax.hist(genes["rho"].dropna().astype(float), bins=30, color="#ccb974", edgecolor="white", alpha=0.9)
            ax.axvline(0, color="#333333", linestyle="--", linewidth=1.0)
            ax.set_xlabel("Gene-level pseudotime correlation")
            ax.set_ylabel("Gene count")
            ax.set_title("Component E pseudotime gene agreement")
            return save_figure(fig, path_base, formats=formats, dpi=dpi)
    df = getattr(result, "score_df", pd.DataFrame())
    score_col = "E_dev" if "E_dev" in df.columns else ("sE" if "sE" in df.columns else None)
    if score_col is None:
        return None
    fig, ax = plt.subplots(figsize=(5.8, 3.8))
    labels = df["branch"].astype(str) if "branch" in df.columns else pd.Series([str(i) for i in range(len(df))])
    ax.bar(labels, df[score_col].astype(float), color="#ccb974", edgecolor="#333333", linewidth=0.6)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Component E pseudotime structure")
    ax.tick_params(axis="x", rotation=35)
    ax.grid(axis="y", alpha=0.25, linewidth=0.7)
    return save_figure(fig, path_base, formats=formats, dpi=dpi)


def _component_f_query_path(result: Any, ctx: Any) -> Path | None:
    meta = getattr(result, "meta", {}) or {}
    for key in ("query_aucell_csv", "aucell_csv"):
        value = meta.get(key) if isinstance(meta, Mapping) else None
        if value:
            path = Path(value)
            if path.exists():
                return path
    path = Path(ctx.output_dir) / ctx.dataset_id / "F" / "query_aucell.csv"
    return path if path.exists() else None


def _save_component_f_activity(result: Any, ctx: Any, path_base: Path, *, formats: Sequence[str], dpi: int, warnings: list[str]) -> str | None:
    query_path = _component_f_query_path(result, ctx)
    if query_path is None:
        warnings.append("component F activity alignment skipped because query_aucell.csv is not available.")
        return None
    if getattr(ctx, "ref_sceniclike", None) is None:
        warnings.append("component F activity alignment skipped because CLSContext.ref_sceniclike is not available.")
        return None
    aucell = pd.read_csv(query_path, index_col=0)
    numeric = aucell.select_dtypes(include=["number"])
    if numeric.empty:
        warnings.append("component F activity alignment skipped because query_aucell.csv has no numeric regulon activity columns.")
        return None
    top = numeric.mean(axis=0).sort_values(ascending=False).head(20)
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(7.0, max(3.5, 0.25 * len(top))))
    ax.barh(top.index[::-1], top.values[::-1], color="#dd8452", edgecolor="#333333", linewidth=0.5)
    ax.set_xlabel("Mean query AUCell")
    ax.set_title("Component F regulon activity diagnostics")
    return save_figure(fig, path_base, formats=formats, dpi=dpi)


def _score_interpretation(score_df: pd.DataFrame, weighted_total_cls: float | None) -> dict[str, str]:
    if score_df.empty:
        return {
            "overview": "CLS reporting completed without component scores.",
            "decomposition": "No component-level structure was available for interpretation.",
        }
    ordered = score_df.dropna(subset=["Score"]).sort_values("Score", ascending=False)
    if ordered.empty:
        top_text = "component scores were not finite"
        low_text = "component scores were not finite"
    else:
        top = ordered.iloc[0]
        low = ordered.iloc[-1]
        top_text = f"Component {top['Component']} ({top['Label']}, {top['Score']:.3f}) showed the strongest concordance signal"
        low_text = f"Component {low['Component']} ({low['Label']}, {low['Score']:.3f}) contributed the most visible structural divergence"
    total = "not available" if weighted_total_cls is None else f"{weighted_total_cls:.3f}"
    return {
        "overview": f"The weighted CLS was {total}, summarizing concordance across identity, expression, transferability, neighborhood, pseudotime, and regulon axes.",
        "decomposition": f"{top_text}; {low_text}. This decomposition is intended to explain which biological axes align or diverge, rather than to reduce protocols to a simple ranking.",
    }


def build_component_score_table(result: Any) -> pd.DataFrame:
    return _component_score_frame(getattr(result, "component_results", {}) or {})


def build_interpretation(result: Any, cls_weights: Mapping[str, float] | None = None) -> dict[str, str]:
    score_df = build_component_score_table(result)
    weighted_total_cls = _finite_float(getattr(result, "weighted_total_cls", None))
    if weighted_total_cls is None and not score_df.empty:
        weighted_total_cls = _weighted_total(dict(zip(score_df["Component"], score_df["Score"])), cls_weights)
    return _score_interpretation(score_df, weighted_total_cls)


def plot_component_scores_bar(score_df: pd.DataFrame):
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    labels = [f"{row.Component}\n{row.Label}" for row in score_df.itertuples()]
    scores = score_df["Score"].astype(float).fillna(0.0).to_numpy()
    colors = ["#4c72b0", "#55a868", "#c44e52", "#8172b2", "#ccb974", "#64b5cd"][: len(scores)]
    bars = ax.bar(labels, scores, color=colors, edgecolor="#333333", linewidth=0.7)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Component score")
    ax.set_title("CLS component scores")
    ax.grid(axis="y", alpha=0.25, linewidth=0.7)
    for bar, score in zip(bars, scores):
        ax.text(bar.get_x() + bar.get_width() / 2, min(score + 0.025, 1.02), f"{score:.2f}", ha="center", va="bottom", fontsize=9)
    return fig


def plot_component_scores_heatmap(score_df: pd.DataFrame, title: str = "CLS component heatmap"):
    plt = import_pyplot()
    values = score_df["Score"].astype(float).fillna(0.0).to_numpy()[None, :]
    fig, ax = plt.subplots(figsize=(7.6, 2.5))
    image = ax.imshow(values, vmin=0, vmax=1, cmap="YlGnBu", aspect="auto")
    ax.set_xticks(np.arange(len(score_df)))
    ax.set_xticklabels([f"{row.Component}: {row.Label}" for row in score_df.itertuples()], rotation=35, ha="right")
    ax.set_yticks([0])
    ax.set_yticklabels(["Score"])
    for idx, value in enumerate(values[0]):
        ax.text(idx, 0, f"{value:.2f}", ha="center", va="center", color="#1f1f1f", fontsize=9)
    ax.set_title(title)
    fig.colorbar(image, ax=ax, fraction=0.035, pad=0.04, label="Score")
    return fig


def plot_weighted_cls(weighted_total_cls: float | None):
    plt = import_pyplot()
    value = 0.0 if weighted_total_cls is None else float(weighted_total_cls)
    fig, ax = plt.subplots(figsize=(5.0, 3.0))
    ax.bar(["Weighted CLS"], [value], color="#4c72b0", edgecolor="#333333", linewidth=0.7)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Weighted CLS summary")
    ax.text(0, min(value + 0.03, 1.02), "n/a" if weighted_total_cls is None else f"{value:.3f}", ha="center", va="bottom", fontsize=11)
    ax.grid(axis="y", alpha=0.25, linewidth=0.7)
    return fig


def plot_component_A(result: Any):
    df = getattr(result, "score_df", pd.DataFrame())
    if not {"sA1_mean", "sA2_ks"}.issubset(df.columns):
        return None
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(5.2, 4.6))
    size = df["n_cells"].astype(float).clip(lower=10) if "n_cells" in df.columns else pd.Series(np.repeat(30, len(df)))
    ax.scatter(df["sA1_mean"], df["sA2_ks"], s=size * 4, color="#4c72b0", alpha=0.75, edgecolor="white", linewidth=0.7)
    if "batch" in df.columns:
        for _, row in df.iterrows():
            ax.annotate(str(row["batch"]), (row["sA1_mean"], row["sA2_ks"]), xytext=(4, 4), textcoords="offset points", fontsize=8)
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("A1 mean target probability")
    ax.set_ylabel("A2 distribution similarity")
    ax.set_title("Component A identity alignment")
    ax.grid(alpha=0.25, linewidth=0.7)
    return fig


def plot_component_B(result: Any):
    df = getattr(result, "score_df", pd.DataFrame())
    if "sB" not in df.columns:
        return None
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    labels = df["batch"].astype(str) if "batch" in df.columns else pd.Series([str(i) for i in range(len(df))])
    ax.bar(labels, df["sB"].astype(float), color="#55a868", edgecolor="#333333", linewidth=0.6)
    if "r" in df.columns:
        ax.plot(labels, df["r"].astype(float), color="#c44e52", marker="o", linewidth=1.4, label="r")
        ax.legend(frameon=False)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Component B pseudo-bulk agreement")
    ax.tick_params(axis="x", rotation=35)
    ax.grid(axis="y", alpha=0.25, linewidth=0.7)
    return fig


def plot_component_C(result: Any):
    df = getattr(result, "score_df", pd.DataFrame())
    if not {"AUC_org", "sC"}.issubset(df.columns):
        return None
    auc_ref = None
    meta = getattr(result, "meta", {}) or {}
    if isinstance(meta, Mapping):
        details = meta.get("auc_ref_details")
        auc_ref = details.get("AUC_ref") if isinstance(details, Mapping) else None
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(5.6, 4.4))
    ax.scatter(df["AUC_org"].astype(float), df["sC"].astype(float), s=65, color="#8172b2", alpha=0.8, edgecolor="white", linewidth=0.7)
    if auc_ref is not None:
        ax.axvline(float(auc_ref), color="#333333", linestyle="--", linewidth=1.0, label="Reference AUC")
        ax.legend(frameon=False)
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Query AUC")
    ax.set_ylabel("Component C score")
    ax.set_title("Component C transferability")
    ax.grid(alpha=0.25, linewidth=0.7)
    return fig


def plot_component_D(result: Any):
    df = getattr(result, "score_df", pd.DataFrame())
    if not {"sD_query", "sD_ref"}.issubset(df.columns):
        return None
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(5.4, 4.7))
    sizes = df["n_candidate"].astype(float).clip(lower=5) * 4 if "n_candidate" in df.columns else pd.Series(np.repeat(45, len(df)))
    ax.scatter(df["sD_query"], df["sD_ref"], s=sizes, color="#64b5cd", alpha=0.78, edgecolor="white", linewidth=0.7)
    for iso in (0.4, 0.6, 0.8):
        ax.plot([0, 1], [iso, iso], color="#bdbdbd", linewidth=0.7, linestyle=":")
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Query neighborhood structure")
    ax.set_ylabel("Reference neighborhood structure")
    ax.set_title("Component D neighborhood concordance")
    ax.grid(alpha=0.25, linewidth=0.7)
    return fig


def plot_component_E(result: Any, ctx: Any | None = None):
    genes_path = _component_e_genes_path(result, ctx) if ctx is not None else None
    plt = import_pyplot()
    if genes_path is not None:
        genes = pd.read_csv(genes_path)
        if "rho" in genes.columns:
            fig, ax = plt.subplots(figsize=(5.8, 3.8))
            ax.hist(genes["rho"].dropna().astype(float), bins=30, color="#ccb974", edgecolor="white", alpha=0.9)
            ax.axvline(0, color="#333333", linestyle="--", linewidth=1.0)
            ax.set_xlabel("Gene-level pseudotime correlation")
            ax.set_ylabel("Gene count")
            ax.set_title("Component E pseudotime gene agreement")
            return fig
    df = getattr(result, "score_df", pd.DataFrame())
    score_col = "E_dev" if "E_dev" in df.columns else ("sE" if "sE" in df.columns else None)
    if score_col is None:
        return None
    fig, ax = plt.subplots(figsize=(5.8, 3.8))
    labels = df["branch"].astype(str) if "branch" in df.columns else pd.Series([str(i) for i in range(len(df))])
    ax.bar(labels, df[score_col].astype(float), color="#ccb974", edgecolor="#333333", linewidth=0.6)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Component E pseudotime structure")
    ax.tick_params(axis="x", rotation=35)
    ax.grid(axis="y", alpha=0.25, linewidth=0.7)
    return fig


def plot_component_F_activity(result: Any, ctx: Any, warnings: list[str] | None = None):
    local_warnings = [] if warnings is None else warnings
    query_path = _component_f_query_path(result, ctx)
    if query_path is None:
        local_warnings.append("component F activity alignment skipped because query_aucell.csv is not available.")
        return None
    if getattr(ctx, "ref_sceniclike", None) is None:
        local_warnings.append("component F activity alignment skipped because CLSContext.ref_sceniclike is not available.")
        return None
    aucell = pd.read_csv(query_path, index_col=0)
    numeric = aucell.select_dtypes(include=["number"])
    if numeric.empty:
        local_warnings.append("component F activity alignment skipped because query_aucell.csv has no numeric regulon activity columns.")
        return None
    top = numeric.mean(axis=0).sort_values(ascending=False).head(20)
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(7.0, max(3.5, 0.25 * len(top))))
    ax.barh(top.index[::-1], top.values[::-1], color="#dd8452", edgecolor="#333333", linewidth=0.5)
    ax.set_xlabel("Mean query AUCell")
    ax.set_title("Component F regulon activity diagnostics")
    return fig


def write_report(
    *,
    result: Any,
    ctx: Any,
    output_dir: str | Path,
    prefix: str = "bridge",
    formats: Sequence[str] = ("png",),
    dpi: int = 300,
) -> ReportResult:
    outdir = ensure_dir(output_dir)
    figdir = ensure_dir(outdir / "figures")
    tabledir = ensure_dir(outdir / "tables")
    warnings: list[str] = []
    figures: dict[str, str] = {}
    tables: dict[str, str] = {}

    component_results = getattr(result, "component_results", {}) or {}
    score_df = _component_score_frame(component_results)
    tables["component_scores"] = write_table(score_df, tabledir / f"{prefix}.component_scores.csv")
    summary = getattr(result, "summary", None)
    if isinstance(summary, pd.DataFrame) and not summary.empty:
        tables["summary"] = write_table(summary, tabledir / f"{prefix}.summary.csv")

    weighted_total_cls = _finite_float(getattr(result, "weighted_total_cls", None))
    if weighted_total_cls is None and not score_df.empty:
        weighted_total_cls = _weighted_total(dict(zip(score_df["Component"], score_df["Score"])))

    if not score_df.empty:
        figures["component_scores_bar"] = _save_component_bar(score_df, figdir / f"{prefix}.component_scores_bar", formats=formats, dpi=dpi)
        figures["component_scores_heatmap"] = _save_component_heatmap(
            score_df,
            figdir / f"{prefix}.component_scores_heatmap",
            title="CLS component heatmap",
            formats=formats,
            dpi=dpi,
        )
        figures["weighted_cls"] = _save_weighted_summary(weighted_total_cls, figdir / f"{prefix}.weighted_cls", formats=formats, dpi=dpi)

    component_a = component_results.get("A")
    if component_a is not None:
        path = _save_component_a(component_a, figdir / f"{prefix}.component_A_identity", formats=formats, dpi=dpi)
        if path:
            figures["component_A_identity"] = path
    component_b = component_results.get("B")
    if component_b is not None:
        path = _save_component_b(component_b, figdir / f"{prefix}.component_B_pseudobulk", formats=formats, dpi=dpi)
        if path:
            figures["component_B_pseudobulk"] = path
    component_c = component_results.get("C")
    if component_c is not None:
        path = _save_component_c(component_c, figdir / f"{prefix}.component_C_transfer_auc", formats=formats, dpi=dpi)
        if path:
            figures["component_C_transfer_auc"] = path
    component_d = component_results.get("D")
    if component_d is not None:
        path = _save_component_d(component_d, figdir / f"{prefix}.component_D_neighborhood", formats=formats, dpi=dpi)
        if path:
            figures["component_D_neighborhood"] = path
    component_e = component_results.get("E")
    if component_e is not None:
        path = _save_component_e(component_e, ctx, figdir / f"{prefix}.component_E_pseudotime", formats=formats, dpi=dpi)
        if path:
            figures["component_E_pseudotime"] = path
    component_f = component_results.get("F")
    if component_f is not None:
        path = _save_component_f_activity(
            component_f,
            ctx,
            figdir / f"{prefix}.component_F_activity_alignment",
            formats=formats,
            dpi=dpi,
            warnings=warnings,
        )
        if path:
            figures["component_F_activity_alignment"] = path

    interpretation = _score_interpretation(score_df, weighted_total_cls)
    markdown_lines = [
        f"# Step3 CLS Report: {prefix}",
        "",
        "## Summary",
        f"- Dataset: `{getattr(ctx, 'dataset_id', prefix)}`",
        f"- Target class: `{getattr(ctx, 'target_class', 'n/a')}`",
        f"- Weighted CLS: {weighted_total_cls if weighted_total_cls is not None else 'n/a'}",
        "",
        "## Component Scores",
        score_df.to_markdown(index=False) if not score_df.empty else "No component scores were available.",
        "",
        "## Interpretation",
        interpretation["overview"],
        "",
        interpretation["decomposition"],
    ]
    if warnings:
        markdown_lines.extend(["", "## Notes"] + [f"- {warning}" for warning in warnings])

    manifest = {
        "report_type": "cls_single_dataset",
        "prefix": prefix,
        "dataset_id": getattr(ctx, "dataset_id", prefix),
        "target_class": getattr(ctx, "target_class", None),
        "figures": figures,
        "tables": tables,
        "warnings": warnings,
        "summary": {
            "weighted_total_cls": weighted_total_cls,
            "component_scores": score_df.to_dict(orient="records"),
        },
        "interpretation": interpretation,
    }
    markdown_report = write_markdown(markdown_lines, outdir / f"{prefix}.cls_report.md")
    manifest_json = write_json(manifest, outdir / f"{prefix}.cls_report_manifest.json")
    return ReportResult(figures=figures, tables=tables, markdown_report=markdown_report, manifest_json=manifest_json, interpretation=interpretation)


def _read_component_score(step3_dir: str | Path, dataset_id: str, component: str) -> float | None:
    path = Path(step3_dir) / dataset_id / component / f"component_{component}_global.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _finite_float(payload.get("global_score"))


def _save_comparison_bar(df: pd.DataFrame, path_base: Path, *, formats: Sequence[str], dpi: int) -> str:
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(max(5.5, 1.2 * len(df)), 4.0))
    colors = DEFAULT_PROTOCOL_COLORS[: len(df)]
    ax.bar(df["Protocol"], df["CLS"].fillna(0.0), color=colors, edgecolor="#333333", linewidth=0.7)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Weighted CLS")
    ax.set_title("Protocol-level weighted CLS")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25, linewidth=0.7)
    return save_figure(fig, path_base, formats=formats, dpi=dpi)


def _save_comparison_heatmap(df: pd.DataFrame, path_base: Path, *, formats: Sequence[str], dpi: int) -> str:
    plt = import_pyplot()
    values = df[list(_COMPONENTS)].astype(float).fillna(0.0).to_numpy()
    fig, ax = plt.subplots(figsize=(7.8, max(3.0, 0.55 * len(df) + 1.5)))
    image = ax.imshow(values, vmin=0, vmax=1, cmap="YlGnBu", aspect="auto")
    ax.set_xticks(np.arange(len(_COMPONENTS)))
    ax.set_xticklabels([f"{c}: {COMPONENT_LABELS[c]}" for c in _COMPONENTS], rotation=35, ha="right")
    ax.set_yticks(np.arange(len(df)))
    ax.set_yticklabels(df["Protocol"])
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j]:.2f}", ha="center", va="center", fontsize=8, color="#1f1f1f")
    ax.set_title("Protocol component score heatmap")
    fig.colorbar(image, ax=ax, fraction=0.035, pad=0.04, label="Score")
    return save_figure(fig, path_base, formats=formats, dpi=dpi)


def _save_radar(df: pd.DataFrame, path_base: Path, *, formats: Sequence[str], dpi: int) -> str:
    plt = import_pyplot()
    labels = list(_COMPONENTS)
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(6.2, 6.2), subplot_kw={"polar": True})
    for idx, row in df.iterrows():
        values = [float(row[component]) if pd.notna(row[component]) else 0.0 for component in labels]
        values += values[:1]
        color = DEFAULT_PROTOCOL_COLORS[idx % len(DEFAULT_PROTOCOL_COLORS)]
        ax.plot(angles, values, color=color, linewidth=1.8, label=row["Protocol"])
        ax.fill(angles, values, color=color, alpha=0.12)
    ax.set_ylim(0, 1.0)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([f"{c}\n{COMPONENT_LABELS[c]}" for c in labels], fontsize=9)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0.25", "0.50", "0.75", "1.00"], fontsize=8)
    ax.set_title("CLS component profile by protocol", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.28, 1.10), frameon=False)
    return save_figure(fig, path_base, formats=formats, dpi=dpi)


def _comparison_interpretation(df: pd.DataFrame) -> dict[str, str]:
    if df.empty:
        return {
            "overview": "No protocol-level CLS records were available for comparison.",
            "decomposition": "No component-level structure was available for interpretation.",
        }
    best_row = df.sort_values("CLS", ascending=False).iloc[0]
    component_means = df[list(_COMPONENTS)].mean(numeric_only=True).sort_values(ascending=False)
    strongest = component_means.index[0] if not component_means.empty else "n/a"
    weakest = component_means.index[-1] if not component_means.empty else "n/a"
    return {
        "overview": f"The comparison summarizes weighted CLS across {len(df)} protocols. {best_row['Protocol']} had the highest aggregate score in this set ({best_row['CLS']:.3f}), but the report is intended to expose multidimensional structure rather than a simple winner-takes-all ranking.",
        "decomposition": f"Across protocols, component {strongest} ({COMPONENT_LABELS.get(strongest, strongest)}) was the most consistently aligned axis, whereas component {weakest} ({COMPONENT_LABELS.get(weakest, weakest)}) showed the largest relative divergence and should guide biological follow-up.",
    }


def compare_reports(
    *,
    protocols: Sequence[Mapping[str, Any]],
    output_dir: str | Path,
    prefix: str = "cls_comparison",
    cls_weights: Mapping[str, float] | None = None,
    formats: Sequence[str] = ("png",),
    dpi: int = 300,
) -> ReportResult:
    outdir = ensure_dir(output_dir)
    figdir = ensure_dir(outdir / "figures")
    tabledir = ensure_dir(outdir / "tables")
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    for protocol in protocols:
        name = str(protocol.get("name") or protocol.get("dataset_id") or "protocol")
        dataset_id = str(protocol.get("dataset_id") or name)
        step3_dir = protocol.get("step3_dir")
        if step3_dir is None:
            raise ValueError(f"Protocol {name!r} is missing step3_dir.")
        row: dict[str, Any] = {"Protocol": name, "dataset_id": dataset_id, "step3_dir": str(step3_dir)}
        component_scores: dict[str, float | None] = {}
        for component in _COMPONENTS:
            score = _read_component_score(step3_dir, dataset_id, component)
            if score is None:
                warnings.append(f"Protocol {name} is missing component {component} artifact.")
            row[component] = score
            component_scores[component] = score
        row["CLS"] = _weighted_total(component_scores, cls_weights)
        rows.append(row)

    df = pd.DataFrame(rows)
    tables = {"component_scores": write_table(df, tabledir / f"{prefix}.component_scores.csv")}
    figures: dict[str, str] = {}
    if not df.empty:
        figures["comparison_radar"] = _save_radar(df, figdir / f"{prefix}.radar", formats=formats, dpi=dpi)
        figures["comparison_weighted_cls"] = _save_comparison_bar(df, figdir / f"{prefix}.weighted_cls", formats=formats, dpi=dpi)
        figures["comparison_heatmap"] = _save_comparison_heatmap(df, figdir / f"{prefix}.component_heatmap", formats=formats, dpi=dpi)

    interpretation = _comparison_interpretation(df)
    markdown_lines = [
        f"# CLS Protocol Comparison: {prefix}",
        "",
        "## Summary",
        df[["Protocol", "CLS", *_COMPONENTS]].to_markdown(index=False) if not df.empty else "No protocols were provided.",
        "",
        "## Interpretation",
        interpretation["overview"],
        "",
        interpretation["decomposition"],
    ]
    if warnings:
        markdown_lines.extend(["", "## Notes"] + [f"- {warning}" for warning in warnings])

    manifest = {
        "report_type": "cls_protocol_comparison",
        "prefix": prefix,
        "protocols": [
            {key: str(value) if isinstance(value, Path) else value for key, value in dict(protocol).items()}
            for protocol in protocols
        ],
        "figures": figures,
        "tables": tables,
        "warnings": warnings,
        "summary": {"protocol_count": len(rows), "weighted_cls": df[["Protocol", "CLS"]].to_dict(orient="records") if not df.empty else []},
        "interpretation": interpretation,
    }
    markdown_report = write_markdown(markdown_lines, outdir / f"{prefix}.cls_comparison_report.md")
    manifest_json = write_json(manifest, outdir / f"{prefix}.cls_comparison_manifest.json")
    return ReportResult(figures=figures, tables=tables, markdown_report=markdown_report, manifest_json=manifest_json, interpretation=interpretation)
