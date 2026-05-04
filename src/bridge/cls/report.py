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

_THESIS_PROTOCOL_COLOR_MAP = {
    "SphereDiff (CSC 2025)": "#a0d8ef",
    "MacroDiff (unpublished)": "#ffb6c1",
    "MSK-DA01 (CSC 2021)": "#b8e0d2",
    "SphereDiff": "#a0d8ef",
    "MacroDiff": "#ffb6c1",
    "MSK-DA01": "#b8e0d2",
}

_COMPONENT_COLORS = {
    "A": "#F28C5E",
    "B": "#A7C7E7",
    "C": "#B5D0F2",
    "D": "#C6E5D9",
    "E": "#F6C1C7",
    "F": "#D8B4E2",
}


def _short_protocol_name(protocol: Any) -> str:
    text = str(protocol).split(" (")[0]
    if text.startswith("BRIDGE-"):
        text = text[len("BRIDGE-") :]
    return text


def _protocol_color(protocol: Any, index: int = 0) -> str:
    text = str(protocol)
    if text in _THESIS_PROTOCOL_COLOR_MAP:
        return _THESIS_PROTOCOL_COLOR_MAP[text]
    short = _short_protocol_name(text)
    if short in _THESIS_PROTOCOL_COLOR_MAP:
        return _THESIS_PROTOCOL_COLOR_MAP[short]
    return DEFAULT_PROTOCOL_COLORS[index % len(DEFAULT_PROTOCOL_COLORS)]


def _component_color(component: str) -> str:
    return _COMPONENT_COLORS.get(str(component).upper(), "#bdbdbd")


def _hide_top_right_spines(ax: Any) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def _scale_marker_sizes(values: Any, *, min_size: float = 55.0, max_size: float = 240.0) -> np.ndarray:
    series = pd.to_numeric(pd.Series(values), errors="coerce").fillna(0.0).astype(float)
    if series.empty:
        return np.array([], dtype=float)
    lo = float(series.min())
    hi = float(series.max())
    if not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo:
        return np.full(series.shape[0], (min_size + max_size) / 2.0)
    return min_size + (series.to_numpy() - lo) / (hi - lo) * (max_size - min_size)


def _optional_gaussian_kde():
    try:
        from scipy.stats import gaussian_kde
    except Exception:
        return None
    return gaussian_kde


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


def _save_figure_or_none(fig: Any, path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    if fig is None:
        return None
    return save_figure(fig, path_base, formats=formats, dpi=dpi)


def _save_component_bar(score_df: pd.DataFrame, path_base: Path, *, formats: Sequence[str], dpi: int) -> str:
    return save_figure(plot_component_scores_bar(score_df), path_base, formats=formats, dpi=dpi)


def _save_component_heatmap(score_df: pd.DataFrame, path_base: Path, *, title: str, formats: Sequence[str], dpi: int) -> str:
    return save_figure(plot_component_scores_heatmap(score_df, title=title), path_base, formats=formats, dpi=dpi)


def _save_weighted_summary(weighted_total_cls: float | None, path_base: Path, *, formats: Sequence[str], dpi: int) -> str:
    return save_figure(plot_weighted_cls(weighted_total_cls), path_base, formats=formats, dpi=dpi)


def _save_weighted_contribution(
    score_df: pd.DataFrame,
    path_base: Path,
    *,
    formats: Sequence[str],
    dpi: int,
    cls_weights: Mapping[str, float] | None = None,
    protocol_label: str = "Dataset",
) -> str | None:
    return _save_figure_or_none(
        plot_weighted_contribution(score_df, cls_weights=cls_weights, protocol_label=protocol_label),
        path_base,
        formats=formats,
        dpi=dpi,
    )


def _save_component_a(result: Any, path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    return _save_figure_or_none(plot_component_A(result), path_base, formats=formats, dpi=dpi)


def _save_component_b(result: Any, path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    return _save_figure_or_none(plot_component_B(result), path_base, formats=formats, dpi=dpi)


def _save_component_c(result: Any, path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    return _save_figure_or_none(plot_component_C(result), path_base, formats=formats, dpi=dpi)


def _save_component_d(result: Any, path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    return _save_figure_or_none(plot_component_D(result), path_base, formats=formats, dpi=dpi)


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
    return _save_figure_or_none(plot_component_E(result, ctx), path_base, formats=formats, dpi=dpi)


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
    return _save_figure_or_none(plot_component_F_activity(result, ctx, warnings), path_base, formats=formats, dpi=dpi)


def _save_component_f1(result: Any, path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    return _save_figure_or_none(plot_component_F1_regulon_overlap(result), path_base, formats=formats, dpi=dpi)


def _save_component_f2(result: Any, path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    return _save_figure_or_none(plot_component_F2_activity_alignment(result), path_base, formats=formats, dpi=dpi)


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
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    plot_df = score_df.copy()
    plot_df["Component"] = plot_df["Component"].astype(str).str.upper()
    plot_df = plot_df.sort_values("Component", key=lambda s: s.map(lambda x: _component_sort_key(str(x))))
    x = np.arange(plot_df.shape[0])
    scores = pd.to_numeric(plot_df["Score"], errors="coerce").fillna(0.0).to_numpy()
    colors = [_component_color(component) for component in plot_df["Component"]]
    ax.bar(x, scores, color=colors, edgecolor="white", linewidth=0.8, alpha=0.95)
    ax.set_xticks(x)
    ax.set_xticklabels(plot_df["Component"].tolist())
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Component global score")
    for xpos, value in zip(x, scores):
        ax.text(xpos, min(value + 0.015, 0.98), f"{value:.3f}", ha="center", va="bottom", fontsize=9)
    _hide_top_right_spines(ax)
    fig.tight_layout()
    return fig


def plot_component_scores_heatmap(score_df: pd.DataFrame, title: str = "CLS component heatmap"):
    plt = import_pyplot()
    plot_df = score_df.copy()
    plot_df["Component"] = plot_df["Component"].astype(str).str.upper()
    plot_df = plot_df.sort_values("Component", key=lambda s: s.map(lambda x: _component_sort_key(str(x))))
    values = pd.to_numeric(plot_df["Score"], errors="coerce").fillna(0.0).to_numpy()[:, None]
    labels = [f"{row.Component}  {row.Label}" for row in plot_df.itertuples()]
    fig, ax = plt.subplots(figsize=(3.9, max(3.8, 0.62 * len(labels))))
    image = ax.imshow(values, aspect="auto", vmin=0, vmax=1, cmap="coolwarm")
    ax.set_xticks([0])
    ax.set_xticklabels(["Score"])
    ax.set_yticks(np.arange(len(labels)))
    ax.set_yticklabels(labels)
    for i, value in enumerate(values[:, 0]):
        ax.text(0, i, f"{value:.3f}", ha="center", va="center", fontsize=10, bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.8))
    cbar = fig.colorbar(image, ax=ax, fraction=0.075, pad=0.08)
    cbar.set_label("Global score (0-1)")
    ax.set_title(title)
    ax.set_xticks(np.arange(-0.5, 1, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(labels), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.3)
    ax.tick_params(which="minor", bottom=False, left=False)
    _hide_top_right_spines(ax)
    fig.tight_layout()
    return fig


def plot_weighted_cls(weighted_total_cls: float | None):
    plt = import_pyplot()
    value = 0.0 if weighted_total_cls is None else float(weighted_total_cls)
    fig, ax = plt.subplots(figsize=(4.4, 4.5))
    ax.bar(["Dataset"], [value], color="#a0d8ef", edgecolor="white", linewidth=0.8)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("CLS (weighted)")
    ax.text(0, min(value + 0.015, 0.98), "n/a" if weighted_total_cls is None else f"{value:.3f}", ha="center", va="bottom", fontsize=11, bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="none", alpha=0.85))
    _hide_top_right_spines(ax)
    fig.tight_layout()
    return fig


def plot_weighted_contribution(score_df: pd.DataFrame, cls_weights: Mapping[str, float] | None = None, protocol_label: str = "Dataset"):
    if score_df.empty:
        return None
    weights = DEFAULT_CLS_WEIGHTS if cls_weights is None else {str(k).upper(): float(v) for k, v in cls_weights.items()}
    plot_df = score_df.copy()
    plot_df["Component"] = plot_df["Component"].astype(str).str.upper()
    plot_df = plot_df[plot_df["Component"].isin(_COMPONENTS)].copy()
    if plot_df.empty:
        return None
    score_map = dict(zip(plot_df["Component"], pd.to_numeric(plot_df["Score"], errors="coerce").fillna(0.0)))
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(4.6, 4.3))
    bottom = 0.0
    for component in _COMPONENTS:
        if component not in score_map or component not in weights:
            continue
        value = float(score_map[component]) * float(weights[component])
        ax.bar([0], [value], bottom=[bottom], color=_component_color(component), edgecolor="white", linewidth=0.8, label=f"{component} (w={weights[component]:.3f})")
        if value >= 0.03:
            ax.text(0, bottom + value / 2, f"{value:.2f}", ha="center", va="center", fontsize=9, bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="none", alpha=0.85))
        bottom += value
    ax.text(0, min(bottom + 0.015, 0.98), f"{bottom:.3f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_xticks([0])
    ax.set_xticklabels([protocol_label])
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Weighted contribution to CLS")
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False, fontsize=9)
    _hide_top_right_spines(ax)
    fig.tight_layout()
    return fig


def plot_component_A(result: Any):
    df = getattr(result, "score_df", pd.DataFrame())
    if not {"sA1_mean", "sA2_ks"}.issubset(df.columns):
        return None
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(6.0, 5.0))
    sizes = _scale_marker_sizes(df["n_cells"] if "n_cells" in df.columns else np.ones(df.shape[0]), min_size=90, max_size=250)
    ax.scatter(df["sA1_mean"].astype(float), df["sA2_ks"].astype(float), s=sizes, color="#a0d8ef", edgecolor="black", linewidth=0.9, alpha=0.92, zorder=3)
    if "batch" in df.columns:
        for _, row in df.iterrows():
            ax.annotate(str(row["batch"]), xy=(float(row["sA1_mean"]), float(row["sA2_ks"])), xytext=(5, 5), textcoords="offset points", fontsize=8, bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.78))
    ax.axvline(0.8, linestyle="--", linewidth=1.2, color="gray", alpha=0.6)
    ax.axhline(0.8, linestyle="--", linewidth=1.2, color="gray", alpha=0.6)
    x_vals = pd.to_numeric(df["sA1_mean"], errors="coerce")
    y_vals = pd.to_numeric(df["sA2_ks"], errors="coerce")
    ax.set_xlim(max(0.0, min(0.6, float(x_vals.min()) - 0.05)), 1.02)
    ax.set_ylim(max(0.0, min(0.2, float(y_vals.min()) - 0.05)), 1.02)
    ax.set_xlabel("A1 (weighted mean agreement)")
    ax.set_ylabel("A2 (weighted KS agreement)")
    score = _finite_float(getattr(result, "global_score", None))
    if score is not None:
        ax.text(0.98, 0.06, f"A={score:.3f}", transform=ax.transAxes, ha="right", va="bottom", fontsize=10, bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="none", alpha=0.85))
    _hide_top_right_spines(ax)
    fig.tight_layout()
    return fig


def plot_component_B(result: Any):
    df = getattr(result, "score_df", pd.DataFrame())
    if "sB" not in df.columns:
        return None
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    labels = df["batch"].astype(str) if "batch" in df.columns else pd.Series([str(i) for i in range(len(df))])
    ax.bar(labels, df["sB"].astype(float), color="#A7C7E7", edgecolor="white", linewidth=0.8)
    if "r" in df.columns:
        ax.plot(labels, df["r"].astype(float), color="#F28C5E", marker="o", linewidth=1.6, label="r")
        ax.legend(frameon=False)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Component B pseudo-bulk agreement")
    ax.tick_params(axis="x", rotation=35)
    ax.grid(axis="y", alpha=0.22, linewidth=0.7)
    _hide_top_right_spines(ax)
    fig.tight_layout()
    return fig


def _auc_reference_from_result(result: Any, df: pd.DataFrame) -> float | None:
    meta = getattr(result, "meta", {}) or {}
    if isinstance(meta, Mapping):
        details = meta.get("auc_ref_details")
        if isinstance(details, Mapping):
            value = _finite_float(details.get("AUC_ref"))
            if value is not None:
                return value
    if "AUC_ref" in df.columns:
        value = _finite_float(pd.to_numeric(df["AUC_ref"], errors="coerce").mean())
        if value is not None:
            return value
    return None


def plot_component_C(result: Any):
    df = getattr(result, "score_df", pd.DataFrame())
    if "AUC_org" not in df.columns:
        return None
    auc_ref = _auc_reference_from_result(result, df)
    if auc_ref is None:
        auc_ref = 1.0
    plot_df = df.copy()
    plot_df["AUC_org"] = pd.to_numeric(plot_df["AUC_org"], errors="coerce")
    plot_df = plot_df[np.isfinite(plot_df["AUC_org"])].copy()
    if plot_df.empty:
        return None
    plot_df["delta"] = np.abs(plot_df["AUC_org"] - float(auc_ref))
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(6.3, 5.0))
    ax.axhline(float(auc_ref), linestyle="--", linewidth=1.3, color="gray", alpha=0.7, zorder=1)
    xmax = max(0.05, min(0.25, float(plot_df["delta"].max()) * 1.2 + 0.01))
    xx = np.linspace(0, xmax, 200)
    ax.plot(xx, float(auc_ref) + xx, linestyle="--", linewidth=1.1, color="gray", alpha=0.55, zorder=1)
    ax.plot(xx, float(auc_ref) - xx, linestyle="--", linewidth=1.1, color="gray", alpha=0.55, zorder=1)
    ax.scatter([0], [float(auc_ref)], s=80, color="white", edgecolor="black", linewidth=1.0, zorder=4, label="Ref baseline")
    sizes = _scale_marker_sizes(plot_df["n_candidate"] if "n_candidate" in plot_df.columns else np.ones(plot_df.shape[0]), min_size=65, max_size=150)
    ax.scatter(plot_df["delta"], plot_df["AUC_org"], s=sizes, color="#B5D0F2", edgecolor="black", linewidth=0.8, alpha=0.92, zorder=3, label="Query batch")
    if "batch" in plot_df.columns:
        for _, row in plot_df.iterrows():
            ax.annotate(str(row["batch"]), xy=(float(row["delta"]), float(row["AUC_org"])), xytext=(4, -10), textcoords="offset points", fontsize=8)
    score = _finite_float(getattr(result, "global_score", None))
    if score is not None:
        ax.text(0.70, 0.96, f"sC={score:.3f}", transform=ax.transAxes, ha="left", va="top", fontsize=11, bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="none", alpha=0.85))
    ax.set_xlabel("|Delta| = |AUC_org - AUC_ref|")
    ax.set_ylabel("AUC")
    ax.set_xlim(-0.005, xmax)
    ax.set_ylim(max(0.0, min(0.75, float(plot_df["AUC_org"].min()) - 0.05)), 1.02)
    secax = ax.secondary_xaxis("top", functions=(lambda x: 1 - x, lambda x: 1 - x))
    secax.set_xlabel("sC = 1 - |Delta|")
    ax.legend(frameon=False, loc="lower left")
    _hide_top_right_spines(ax)
    fig.tight_layout()
    return fig


def plot_component_D(result: Any):
    df = getattr(result, "score_df", pd.DataFrame())
    if not {"sD_query", "sD_ref"}.issubset(df.columns):
        return None
    plot_df = df.copy()
    plot_df["sD_query"] = pd.to_numeric(plot_df["sD_query"], errors="coerce")
    plot_df["sD_ref"] = pd.to_numeric(plot_df["sD_ref"], errors="coerce")
    plot_df = plot_df[np.isfinite(plot_df["sD_query"]) & np.isfinite(plot_df["sD_ref"])].copy()
    if plot_df.empty:
        return None
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(6.2, 5.2))
    sizes = _scale_marker_sizes(plot_df["n_candidate"] if "n_candidate" in plot_df.columns else np.ones(plot_df.shape[0]), min_size=80, max_size=260)
    ax.scatter(plot_df["sD_query"], plot_df["sD_ref"], s=sizes, color="#C6E5D9", edgecolor="black", linewidth=0.8, alpha=0.92, zorder=3)
    levels = [0.6, 0.7, 0.8, 0.9]
    xx = np.linspace(0.001, 1.0, 400)
    for level in levels:
        yy = (level ** 2) / xx
        mask = (yy >= 0) & (yy <= 1.02)
        ax.plot(xx[mask], yy[mask], linestyle="--", linewidth=1.0, color="gray", alpha=0.55, zorder=1)
        xr = 0.92
        yr = (level ** 2) / xr
        if 0 < yr < 1.02:
            ax.text(xr, yr, f"sD={level:.1f}", fontsize=9, color="gray", ha="left", va="center")
    if "batch" in plot_df.columns:
        for _, row in plot_df.iterrows():
            ax.annotate(str(row["batch"]), xy=(float(row["sD_query"]), float(row["sD_ref"])), xytext=(5, 5), textcoords="offset points", fontsize=8, bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.78))
    score = _finite_float(getattr(result, "global_score", None))
    if score is not None:
        ax.text(0.01, 0.98, f"sD_global={score:.3f}", transform=ax.transAxes, ha="left", va="top", fontsize=10, bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="none", alpha=0.85))
    xmin = max(0.0, min(0.4, float(plot_df["sD_query"].min()) - 0.05))
    ymin = max(0.0, min(0.4, float(plot_df["sD_ref"].min()) - 0.05))
    ax.set_xlim(xmin, 1.02)
    ax.set_ylim(ymin, 1.02)
    ax.set_xlabel("sD_query (candidate neighborhood consistency)")
    ax.set_ylabel("sD_ref (reference target enrichment)")
    _hide_top_right_spines(ax)
    fig.tight_layout()
    return fig


def _format_gene_block(df: pd.DataFrame, *, top_n: int = 8, per_line: int = 3) -> str:
    if "rho" not in df.columns:
        return "No rho values available."
    work = df.copy()
    work["rho"] = pd.to_numeric(work["rho"], errors="coerce")
    work = work[np.isfinite(work["rho"])].copy()
    if work.empty:
        return "No finite rho values available."
    gene_col = "gene" if "gene" in work.columns else work.columns[0]
    work[gene_col] = work[gene_col].astype(str)
    ordered = work.sort_values("rho", ascending=False)
    top_pos = ordered.head(top_n)[[gene_col, "rho"]].values.tolist()
    top_neg = sorted(ordered.tail(top_n)[[gene_col, "rho"]].values.tolist(), key=lambda item: item[1])

    def lines(items: list[list[Any]]) -> list[str]:
        out: list[str] = []
        for i in range(0, len(items), per_line):
            block = items[i : i + per_line]
            out.append("   ".join([f"{gene} ({rho:+.2f})" for gene, rho in block]))
        return out

    return "Top + genes:\n" + "\n".join(lines(top_pos)) + "\nTop - genes:\n" + "\n".join(lines(top_neg))


def _plot_gene_rho_density(gene_frames: Mapping[str, pd.DataFrame], scores: Mapping[str, float | None] | None = None):
    usable: list[tuple[str, pd.DataFrame]] = []
    for protocol, genes in gene_frames.items():
        if "rho" not in genes.columns:
            continue
        work = genes.copy()
        work["rho"] = pd.to_numeric(work["rho"], errors="coerce")
        work = work[np.isfinite(work["rho"])].copy()
        if work.shape[0] >= 3:
            usable.append((protocol, work))
    if not usable:
        return None
    plt = import_pyplot()
    kde = _optional_gaussian_kde()
    fig_height = max(5.2, 1.35 * len(usable) + 1.4)
    fig, ax = plt.subplots(figsize=(13.2, fig_height))
    xx = np.linspace(-1, 1, 450)
    for i, (protocol, genes) in enumerate(usable):
        color = _protocol_color(protocol, i)
        rho = genes["rho"].to_numpy(dtype=float)
        score = None if scores is None else scores.get(protocol)
        label = _short_protocol_name(protocol)
        if score is not None and math.isfinite(float(score)):
            label = f"{label} (sE={float(score):.3f})"
        if kde is not None and np.nanstd(rho) > 1e-9:
            yy = kde(rho)(xx)
            ax.plot(xx, yy, color=color, lw=2.4, label=label)
            ax.fill_between(xx, yy, color=color, alpha=0.28)
        else:
            ax.hist(rho, bins=30, density=True, histtype="stepfilled", color=color, alpha=0.28, label=label)
            ax.hist(rho, bins=30, density=True, histtype="step", color=color, linewidth=2.0)
        text_y = 0.98 - i * (0.90 / max(len(usable), 1))
        ax.text(
            1.03,
            text_y,
            f"{_short_protocol_name(protocol)}\n" + _format_gene_block(genes, top_n=6 if len(usable) >= 4 else 8),
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=7.2 if len(usable) >= 4 else 8.2,
            linespacing=1.25,
            bbox=dict(boxstyle="round,pad=0.5", facecolor="white", edgecolor=color, linewidth=1.4),
            clip_on=False,
        )
    ax.axvline(0, linestyle="--", lw=1.2, color="gray", alpha=0.7)
    ax.set_xlim(-1, 1)
    ax.set_xlabel("Gene-level Spearman rho (ref vs organoid smoothed trends)")
    ax.set_ylabel("Density")
    ax.legend(frameon=False, loc="upper left")
    _hide_top_right_spines(ax)
    fig.tight_layout(rect=[0, 0, 0.70, 1])
    return fig


def plot_component_E(result: Any, ctx: Any | None = None):
    genes_path = _component_e_genes_path(result, ctx) if ctx is not None else None
    if genes_path is not None:
        genes = pd.read_csv(genes_path)
        if "rho" in genes.columns:
            score = _finite_float(getattr(result, "global_score", None))
            fig = _plot_gene_rho_density({"Dataset": genes}, {"Dataset": score})
            if fig is not None:
                return fig
    df = getattr(result, "score_df", pd.DataFrame())
    score_col = "E_dev" if "E_dev" in df.columns else ("sE" if "sE" in df.columns else None)
    if score_col is None:
        return None
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(5.8, 3.8))
    labels = df["branch"].astype(str) if "branch" in df.columns else pd.Series([str(i) for i in range(len(df))])
    ax.bar(labels, df[score_col].astype(float), color="#F6C1C7", edgecolor="white", linewidth=0.8)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Component E pseudotime structure")
    ax.tick_params(axis="x", rotation=35)
    ax.grid(axis="y", alpha=0.22, linewidth=0.7)
    _hide_top_right_spines(ax)
    fig.tight_layout()
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
    ax.barh(top.index[::-1], top.values[::-1], color="#D8B4E2", edgecolor="white", linewidth=0.6)
    ax.set_xlabel("Mean query AUCell")
    ax.set_title("Component F regulon activity diagnostics")
    _hide_top_right_spines(ax)
    fig.tight_layout()
    return fig


def plot_component_F1_regulon_overlap(result: Any):
    df = getattr(result, "score_df", pd.DataFrame())
    if "J" not in df.columns:
        return None
    plot_df = df.copy()
    plot_df["J"] = pd.to_numeric(plot_df["J"], errors="coerce")
    plot_df = plot_df[np.isfinite(plot_df["J"])].copy()
    if plot_df.empty:
        return None
    labels = plot_df["batch"].astype(str).tolist() if "batch" in plot_df.columns else [str(i) for i in range(plot_df.shape[0])]
    x = np.arange(plot_df.shape[0])
    size_source = plot_df["n_reg_used"] if "n_reg_used" in plot_df.columns else (plot_df["n_cells"] if "n_cells" in plot_df.columns else np.ones(plot_df.shape[0]))
    sizes = _scale_marker_sizes(size_source, min_size=90, max_size=260)
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(max(5.6, 0.95 * len(labels) + 2.2), 4.4))
    ax.scatter(x, plot_df["J"], s=sizes, color="#D8B4E2", edgecolor="black", linewidth=0.8, zorder=3, label="J")
    for i, value in enumerate(plot_df["J"]):
        ax.text(x[i], min(float(value) + 0.035, 0.98), f"{float(value):.3f}", ha="center", va="bottom", fontsize=9)
    score = _finite_float(getattr(result, "global_score", None))
    if score is not None:
        ax.text(0.02, 0.96, f"sF={score:.3f}", transform=ax.transAxes, ha="left", va="top", fontsize=10, bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="none", alpha=0.9))
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylim(0.0, 1.02)
    ax.set_ylabel("Mean Jaccard overlap")
    ax.set_title("Component F1: regulon target overlap")
    ax.grid(axis="y", alpha=0.22, linewidth=0.7)
    _hide_top_right_spines(ax)
    fig.tight_layout()
    return fig


def plot_component_F2_activity_alignment(result: Any):
    df = getattr(result, "score_df", pd.DataFrame())
    if "ra" not in df.columns:
        return None
    plot_df = df.copy()
    plot_df["ra"] = pd.to_numeric(plot_df["ra"], errors="coerce")
    plot_df = plot_df[np.isfinite(plot_df["ra"])].copy()
    if plot_df.empty:
        return None
    labels = plot_df["batch"].astype(str).tolist() if "batch" in plot_df.columns else [str(i) for i in range(plot_df.shape[0])]
    x = np.arange(plot_df.shape[0])
    size_source = plot_df["n_cells"] if "n_cells" in plot_df.columns else np.ones(plot_df.shape[0])
    sizes = _scale_marker_sizes(size_source, min_size=90, max_size=260)
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(max(5.6, 0.95 * len(labels) + 2.2), 4.4))
    ax.axhline(0.0, linestyle="--", linewidth=1.0, color="gray", alpha=0.45, zorder=1)
    ax.scatter(x, plot_df["ra"], s=sizes, marker="s", color="#A7C7E7", edgecolor="black", linewidth=0.8, zorder=3, label="ra")
    for i, value in enumerate(plot_df["ra"]):
        ax.text(x[i], min(float(value) + 0.045, 0.96), f"{float(value):.3f}", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ymin = min(-0.05, float(plot_df["ra"].min()) - 0.08)
    ymax = max(0.2, float(plot_df["ra"].max()) + 0.08)
    ax.set_ylim(max(-1.0, ymin), min(1.0, ymax))
    ax.set_ylabel("Regulon activity correlation (ra)")
    ax.set_title("Component F2: regulon activity alignment")
    ax.grid(axis="y", alpha=0.22, linewidth=0.7)
    _hide_top_right_spines(ax)
    fig.tight_layout()
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
        path = _save_weighted_contribution(
            score_df,
            figdir / f"{prefix}.weighted_contribution",
            formats=formats,
            dpi=dpi,
            protocol_label=getattr(ctx, "dataset_id", prefix),
        )
        if path:
            figures["weighted_contribution"] = path

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
        path = _save_component_f1(component_f, figdir / f"{prefix}.component_F1_regulon_overlap", formats=formats, dpi=dpi)
        if path:
            figures["component_F1_regulon_overlap"] = path
        path = _save_component_f2(component_f, figdir / f"{prefix}.component_F2_activity_alignment", formats=formats, dpi=dpi)
        if path:
            figures["component_F2_activity_alignment"] = path

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


def _component_global_path(step3_dir: str | Path, dataset_id: str, component: str) -> Path:
    return Path(step3_dir) / dataset_id / component / f"component_{component}_global.json"


def _component_batch_path(step3_dir: str | Path, dataset_id: str, component: str) -> Path:
    return Path(step3_dir) / dataset_id / component / f"component_{component}_batch.csv"


def _component_genes_path(step3_dir: str | Path, dataset_id: str, component: str = "E") -> Path:
    return Path(step3_dir) / dataset_id / component / f"component_{component}_genes.csv"


def _read_component_payload(step3_dir: str | Path, dataset_id: str, component: str) -> dict[str, Any] | None:
    path = _component_global_path(step3_dir, dataset_id, component)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _read_component_score(step3_dir: str | Path, dataset_id: str, component: str) -> float | None:
    payload = _read_component_payload(step3_dir, dataset_id, component)
    if payload is None:
        return None
    return _finite_float(payload.get("global_score"))


def _read_component_batch(step3_dir: str | Path, dataset_id: str, component: str) -> pd.DataFrame | None:
    path = _component_batch_path(step3_dir, dataset_id, component)
    if not path.exists():
        return None
    return pd.read_csv(path)


def _protocol_records(protocols: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for protocol in protocols:
        name = str(protocol.get("name") or protocol.get("dataset_id") or "protocol")
        dataset_id = str(protocol.get("dataset_id") or name)
        step3_dir = protocol.get("step3_dir")
        if step3_dir is None:
            raise ValueError(f"Protocol {name!r} is missing step3_dir.")
        records.append({"name": name, "dataset_id": dataset_id, "step3_dir": step3_dir})
    return records


def plot_protocol_component_scores(df: pd.DataFrame):
    if df.empty:
        return None
    plt = import_pyplot()
    components = [component for component in _COMPONENTS if component in df.columns]
    if not components:
        return None
    x = np.arange(len(components))
    n_protocols = max(len(df), 1)
    bar_width = min(0.75 / n_protocols, 0.22)
    fig, ax = plt.subplots(figsize=(10.2, 4.2))
    for idx, row in df.reset_index(drop=True).iterrows():
        offset = (idx - (n_protocols - 1) / 2.0) * bar_width
        values = pd.to_numeric(row[components], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        ax.bar(x + offset, values, width=bar_width, label=row["Protocol"], alpha=0.95, color=_protocol_color(row["Protocol"], idx))
    ax.set_xticks(x)
    ax.set_xticklabels(components)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Component global score")
    ax.legend(frameon=False, bbox_to_anchor=(1.02, 0.5), loc="center left")
    _hide_top_right_spines(ax)
    fig.tight_layout()
    return fig


def plot_protocol_weighted_cls(df: pd.DataFrame):
    if df.empty or "CLS" not in df.columns:
        return None
    plt = import_pyplot()
    plot_df = df.sort_values("CLS", ascending=False).reset_index(drop=True)
    x = np.arange(plot_df.shape[0])
    fig, ax = plt.subplots(figsize=(max(5.2, 1.15 * len(plot_df)), 5.4))
    values = pd.to_numeric(plot_df["CLS"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    bars = ax.bar(x, values, color=[_protocol_color(row.Protocol, idx) for idx, row in enumerate(plot_df.itertuples())], edgecolor="white", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([_short_protocol_name(value) for value in plot_df["Protocol"]], rotation=20, ha="right")
    ax.set_ylabel("CLS (weighted)")
    ax.set_ylim(0, 1.0)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, min(value + 0.015, 0.98), f"{value:.3f}", ha="center", va="bottom", fontsize=10, bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="none", alpha=0.85))
    _hide_top_right_spines(ax)
    fig.tight_layout()
    return fig


def plot_protocol_weighted_contribution(df: pd.DataFrame, cls_weights: Mapping[str, float] | None = None):
    if df.empty:
        return None
    weights = DEFAULT_CLS_WEIGHTS if cls_weights is None else {str(k).upper(): float(v) for k, v in cls_weights.items()}
    components = [component for component in _COMPONENTS if component in df.columns and component in weights]
    if not components:
        return None
    plot_df = df.sort_values("CLS", ascending=False).reset_index(drop=True)
    x = np.arange(plot_df.shape[0])
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(max(6.4, 1.15 * len(plot_df) + 2.2), 4.2))
    bottom = np.zeros(plot_df.shape[0], dtype=float)
    for component in components:
        scores = pd.to_numeric(plot_df[component], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        vals = scores * float(weights[component])
        ax.bar(x, vals, bottom=bottom, color=_component_color(component), edgecolor="white", linewidth=0.8, label=f"{component} (w={weights[component]:.3f})")
        for idx, value in enumerate(vals):
            if value >= 0.03:
                ax.text(x[idx], bottom[idx] + value / 2, f"{value:.2f}", ha="center", va="center", fontsize=9, bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="none", alpha=0.85))
        bottom += vals
    for idx, value in enumerate(pd.to_numeric(plot_df["CLS"], errors="coerce").fillna(pd.Series(bottom)).to_numpy(dtype=float)):
        ax.text(x[idx], min(value + 0.015, 0.98), f"{value:.3f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([_short_protocol_name(value) for value in plot_df["Protocol"]], rotation=20, ha="right")
    ax.set_ylabel("Weighted contribution to CLS")
    ax.set_ylim(0, 1.0)
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False, fontsize=9)
    _hide_top_right_spines(ax)
    fig.tight_layout()
    return fig


def plot_protocol_component_heatmap(df: pd.DataFrame):
    if df.empty:
        return None
    components = [component for component in _COMPONENTS if component in df.columns]
    if not components:
        return None
    protocol_order = df["Protocol"].tolist()
    matrix = df.set_index("Protocol").loc[protocol_order, components].astype(float).to_numpy().T
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(max(6.2, 1.15 * len(protocol_order) + 2.0), 4.6))
    image = ax.imshow(matrix, aspect="auto", vmin=0, vmax=1, cmap="coolwarm")
    ax.set_xticks(np.arange(len(protocol_order)))
    ax.set_xticklabels([_short_protocol_name(value) for value in protocol_order], rotation=20, ha="right")
    ax.set_yticks(np.arange(len(components)))
    ax.set_yticklabels([f"{component}  {COMPONENT_LABELS[component]}" for component in components])
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, f"{matrix[i, j]:.3f}", ha="center", va="center", fontsize=10, bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.8))
    cbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Global score (0-1)")
    ax.set_xticks(np.arange(-0.5, len(protocol_order), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(components), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.5)
    ax.tick_params(which="minor", bottom=False, left=False)
    _hide_top_right_spines(ax)
    fig.tight_layout()
    return fig


def plot_protocol_radar(df: pd.DataFrame):
    if df.empty:
        return None
    labels = [component for component in _COMPONENTS if component in df.columns]
    if not labels:
        return None
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False)
    angles_closed = np.concatenate((angles, [angles[0]]))
    plt = import_pyplot()
    fig = plt.figure(figsize=(12, 10), facecolor="white")
    ax = fig.add_subplot(111, polar=True, facecolor="white")
    for idx, row in df.reset_index(drop=True).iterrows():
        vals = pd.to_numeric(row[labels], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        vals = np.concatenate((vals, [vals[0]]))
        color = _protocol_color(row["Protocol"], idx)
        ax.plot(angles_closed, vals, "o-", linewidth=3, markersize=7, label=row["Protocol"], color=color)
        ax.fill(angles_closed, vals, color=color, alpha=0.25)
    ax.set_thetagrids(np.degrees(angles), [f"{component}: {COMPONENT_LABELS[component]}" for component in labels], fontsize=15, fontweight="medium")
    ax.set_ylim(0, 1.0)
    ax.tick_params(axis="x", pad=55)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=10, alpha=0.7)
    ax.grid(True, linestyle="-", linewidth=1.2, alpha=0.5, color="gray")
    ax.spines["polar"].set_visible(False)
    ax.legend(loc="upper right", bbox_to_anchor=(1.32, 1.10), fontsize=12, frameon=True, fancybox=True, edgecolor="black")
    fig.tight_layout()
    return fig


def plot_protocol_component_A(summary_df: pd.DataFrame):
    if summary_df.empty or not {"Protocol", "A1", "A2", "A_global"}.issubset(summary_df.columns):
        return None
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(6.0, 5.0))
    for idx, row in summary_df.reset_index(drop=True).iterrows():
        ax.scatter(row["A1"], row["A2"], s=120, color=_protocol_color(row["Protocol"], idx), edgecolor="black", linewidth=1.0, zorder=3)
    offsets = [(0.04, 0.06), (0.04, -0.08), (-0.18, 0.05), (-0.04, 0.14)]
    for idx, row in summary_df.reset_index(drop=True).iterrows():
        short = _short_protocol_name(row["Protocol"])
        dx, dy = offsets[idx % len(offsets)]
        if "DemoDiff" in short:
            dx, dy = (-0.04, 0.14)
        elif short == "MSK-DA01":
            dx, dy = (-0.18, 0.05)
        ax.annotate(
            f"{short}\nA={float(row['A_global']):.3f}",
            xy=(float(row["A1"]), float(row["A2"])),
            xytext=(float(row["A1"]) + dx, float(row["A2"]) + dy),
            textcoords="data",
            ha="left",
            va="center",
            fontsize=10,
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="none", alpha=0.9),
            arrowprops=dict(arrowstyle="-", linewidth=1, color="gray", shrinkA=4, shrinkB=4),
        )
    ax.axvline(0.8, linestyle="--", linewidth=1.2, color="gray", alpha=0.6)
    ax.axhline(0.8, linestyle="--", linewidth=1.2, color="gray", alpha=0.6)
    ax.set_xlim(max(0.0, min(0.6, float(summary_df["A1"].min()) - 0.05)), 1.02)
    ax.set_ylim(max(0.0, min(0.2, float(summary_df["A2"].min()) - 0.05)), 1.02)
    ax.set_xlabel("A1 (weighted mean agreement)")
    ax.set_ylabel("A2 (weighted KS agreement)")
    _hide_top_right_spines(ax)
    fig.tight_layout()
    return fig


def plot_protocol_component_B(batch_df: pd.DataFrame, global_df: pd.DataFrame):
    if batch_df.empty or not ({"r", "sB"} & set(batch_df.columns)):
        return None
    metric = "r" if "r" in batch_df.columns else "sB"
    plot_df = batch_df.copy().reset_index(drop=True)
    plot_df[metric] = pd.to_numeric(plot_df[metric], errors="coerce")
    plot_df = plot_df[np.isfinite(plot_df[metric])].copy()
    if plot_df.empty:
        return None
    protocols = plot_df["Protocol"].drop_duplicates().tolist()
    x_map = {protocol: idx for idx, protocol in enumerate(protocols)}
    rng = np.random.default_rng(0)
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(max(6.4, 1.05 * len(protocols) + 2.4), 4.8))
    for idx, protocol in enumerate(protocols):
        sub = plot_df[plot_df["Protocol"] == protocol]
        jitter = rng.normal(0, 0.035, size=sub.shape[0]) if sub.shape[0] > 1 else np.zeros(sub.shape[0])
        size_source = sub["n_cells"] if "n_cells" in sub.columns else np.ones(sub.shape[0])
        sizes = _scale_marker_sizes(size_source, min_size=80, max_size=220)
        ax.scatter(np.full(sub.shape[0], x_map[protocol]) + jitter, sub[metric], s=sizes, color=_protocol_color(protocol, idx), edgecolor="black", linewidth=0.8, alpha=0.92, label=_short_protocol_name(protocol), zorder=3)
    if not global_df.empty and "sB_global" in global_df.columns:
        for _, row in global_df.iterrows():
            protocol = row["Protocol"]
            if protocol in x_map:
                value = _finite_float(row["sB_global"])
                if value is not None:
                    ax.text(x_map[protocol], 0.04, f"sB={value:.3f}", ha="center", va="bottom", fontsize=9, bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="none", alpha=0.85))
    ax.set_xticks(np.arange(len(protocols)))
    ax.set_xticklabels([_short_protocol_name(protocol) for protocol in protocols], rotation=20, ha="right")
    ax.set_ylabel("Pseudo-bulk Pearson r" if metric == "r" else "Pseudo-bulk score sB")
    ax.set_title("Component B: pseudo-bulk expression agreement")
    ax.set_ylim(-1.0 if metric == "r" and float(plot_df[metric].min()) < 0 else 0.0, 1.02)
    ax.grid(axis="y", alpha=0.22, linewidth=0.7)
    _hide_top_right_spines(ax)
    fig.tight_layout()
    return fig


def plot_protocol_component_C(batch_df: pd.DataFrame, global_df: pd.DataFrame, auc_ref: float | None = None):
    if batch_df.empty or "AUC_org" not in batch_df.columns:
        return None
    plot_df = batch_df.copy()
    plot_df["AUC_org"] = pd.to_numeric(plot_df["AUC_org"], errors="coerce")
    if auc_ref is None:
        if "AUC_ref" in plot_df.columns:
            auc_ref = _finite_float(pd.to_numeric(plot_df["AUC_ref"], errors="coerce").mean())
        if auc_ref is None:
            auc_ref = 1.0
    plot_df["delta"] = np.abs(plot_df["AUC_org"] - float(auc_ref))
    plot_df = plot_df[np.isfinite(plot_df["delta"]) & np.isfinite(plot_df["AUC_org"])].copy()
    if plot_df.empty:
        return None
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(6.6, 5.2))
    ax.axhline(float(auc_ref), linestyle="--", linewidth=1.3, color="gray", alpha=0.7, zorder=1)
    xmax = max(0.25, float(plot_df["delta"].max()) * 1.05)
    xx = np.linspace(0, xmax, 200)
    ax.plot(xx, float(auc_ref) + xx, linestyle="--", linewidth=1.1, color="gray", alpha=0.55, zorder=1)
    ax.plot(xx, float(auc_ref) - xx, linestyle="--", linewidth=1.1, color="gray", alpha=0.55, zorder=1)
    ax.scatter([0], [float(auc_ref)], s=70, color="white", edgecolor="black", linewidth=1.0, zorder=4, label="Ref baseline")
    rng = np.random.default_rng(0)
    for idx, protocol in enumerate(plot_df["Protocol"].drop_duplicates().tolist()):
        sub = plot_df[plot_df["Protocol"] == protocol]
        jitter = rng.normal(0, 0.004, size=sub.shape[0])
        ax.scatter(sub["delta"].values + jitter, sub["AUC_org"].values, s=45, color=_protocol_color(protocol, idx), edgecolor="black", linewidth=0.8, alpha=0.9, zorder=3, label=_short_protocol_name(protocol))
    y0 = 0.98
    for idx, row in global_df.reset_index(drop=True).iterrows():
        ax.text(0.72, y0 - idx * 0.07, f"{_short_protocol_name(row['Protocol'])}: sC={float(row['sC_global']):.3f}", transform=ax.transAxes, ha="left", va="top", fontsize=10, bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="none", alpha=0.85))
    ax.set_xlabel("|Delta| = |AUC_org - AUC_ref|")
    ax.set_ylabel("AUC")
    ax.set_xlim(-0.01, xmax)
    ax.set_ylim(0.0, 1.02)
    secax = ax.secondary_xaxis("top", functions=(lambda x: 1 - x, lambda x: 1 - x))
    secax.set_xlabel("sC = 1 - |Delta|")
    ax.legend(frameon=False, loc="lower left")
    _hide_top_right_spines(ax)
    fig.tight_layout()
    return fig


def plot_protocol_component_D(batch_df: pd.DataFrame, global_df: pd.DataFrame):
    if batch_df.empty or not {"sD_query", "sD_ref"}.issubset(batch_df.columns):
        return None
    plot_df = batch_df.copy()
    plot_df["sD_query"] = pd.to_numeric(plot_df["sD_query"], errors="coerce")
    plot_df["sD_ref"] = pd.to_numeric(plot_df["sD_ref"], errors="coerce")
    plot_df = plot_df[np.isfinite(plot_df["sD_query"]) & np.isfinite(plot_df["sD_ref"])].copy()
    if plot_df.empty:
        return None
    sizes = _scale_marker_sizes(plot_df["n_candidate"] if "n_candidate" in plot_df.columns else np.ones(plot_df.shape[0]), min_size=55, max_size=260)
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(6.4, 5.4))
    for idx, protocol in enumerate(plot_df["Protocol"].drop_duplicates().tolist()):
        sub = plot_df[plot_df["Protocol"] == protocol]
        ax.scatter(sub["sD_query"], sub["sD_ref"], s=sizes[sub.index.to_numpy()], color=_protocol_color(protocol, idx), edgecolor="black", linewidth=0.8, alpha=0.9, label=_short_protocol_name(protocol), zorder=3)
    xx = np.linspace(0.001, 1.0, 400)
    for level in [0.6, 0.7, 0.8, 0.9]:
        yy = (level ** 2) / xx
        mask = (yy >= 0) & (yy <= 1.02)
        ax.plot(xx[mask], yy[mask], linestyle="--", linewidth=1.0, color="gray", alpha=0.55, zorder=1)
        xr = 0.92
        yr = (level ** 2) / xr
        if 0 < yr < 1.02:
            ax.text(xr, yr, f"sD={level:.1f}", fontsize=9, color="gray", ha="left", va="center")
    y0 = 0.98
    for idx, row in global_df.reset_index(drop=True).iterrows():
        ax.text(0.0, y0 - idx * 0.07, f"{_short_protocol_name(row['Protocol'])}: sD_global={float(row['sD_global']):.3f}", transform=ax.transAxes, ha="left", va="top", fontsize=10, bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="none", alpha=0.85))
    ax.set_xlabel("sD_query (candidate neighborhood consistency)")
    ax.set_ylabel("sD_ref (reference target enrichment)")
    ax.set_xlim(max(0.0, min(0.4, float(plot_df["sD_query"].min()) - 0.05)), 1.02)
    ax.set_ylim(max(0.0, min(0.4, float(plot_df["sD_ref"].min()) - 0.05)), 1.02)
    ax.legend(frameon=False, loc="lower left")
    _hide_top_right_spines(ax)
    fig.tight_layout()
    return fig


def plot_protocol_component_E(gene_frames: Mapping[str, pd.DataFrame], scores: Mapping[str, float | None] | None = None):
    return _plot_gene_rho_density(gene_frames, scores)


def plot_protocol_component_F1(batch_df: pd.DataFrame, global_df: pd.DataFrame):
    if batch_df.empty or "J" not in batch_df.columns:
        return None
    plot_df = batch_df.copy().reset_index(drop=True)
    plot_df["J"] = pd.to_numeric(plot_df["J"], errors="coerce")
    plot_df = plot_df[np.isfinite(plot_df["J"])].copy()
    if plot_df.empty:
        return None
    protocols = plot_df["Protocol"].drop_duplicates().tolist()
    x_map = {protocol: idx for idx, protocol in enumerate(protocols)}
    rng = np.random.default_rng(0)
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(max(6.4, 1.05 * len(protocols) + 2.4), 4.8))
    for idx, protocol in enumerate(protocols):
        sub = plot_df[plot_df["Protocol"] == protocol]
        jitter = rng.normal(0, 0.035, size=sub.shape[0]) if sub.shape[0] > 1 else np.zeros(sub.shape[0])
        size_source = sub["n_reg_used"] if "n_reg_used" in sub.columns else (sub["n_cells"] if "n_cells" in sub.columns else np.ones(sub.shape[0]))
        sizes = _scale_marker_sizes(size_source, min_size=80, max_size=220)
        ax.scatter(np.full(sub.shape[0], x_map[protocol]) + jitter, sub["J"], s=sizes, color=_protocol_color(protocol, idx), edgecolor="black", linewidth=0.8, alpha=0.92, label=_short_protocol_name(protocol), zorder=3)
    if not global_df.empty and "sF_global" in global_df.columns:
        for _, row in global_df.iterrows():
            protocol = row["Protocol"]
            if protocol in x_map:
                value = _finite_float(row["sF_global"])
                if value is not None:
                    ax.text(x_map[protocol], 0.04, f"sF={value:.3f}", ha="center", va="bottom", fontsize=9, bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="none", alpha=0.85))
    ax.set_xticks(np.arange(len(protocols)))
    ax.set_xticklabels([_short_protocol_name(protocol) for protocol in protocols], rotation=20, ha="right")
    ax.set_ylim(0.0, 1.02)
    ax.set_ylabel("Mean Jaccard overlap")
    ax.set_title("Component F1: regulon target overlap")
    ax.grid(axis="y", alpha=0.22, linewidth=0.7)
    _hide_top_right_spines(ax)
    fig.tight_layout()
    return fig


def plot_protocol_component_F2(batch_df: pd.DataFrame, global_df: pd.DataFrame):
    if batch_df.empty or "ra" not in batch_df.columns:
        return None
    plot_df = batch_df.copy().reset_index(drop=True)
    plot_df["ra"] = pd.to_numeric(plot_df["ra"], errors="coerce")
    plot_df = plot_df[np.isfinite(plot_df["ra"])].copy()
    if plot_df.empty:
        return None
    protocols = plot_df["Protocol"].drop_duplicates().tolist()
    x_map = {protocol: idx for idx, protocol in enumerate(protocols)}
    rng = np.random.default_rng(0)
    plt = import_pyplot()
    fig, ax = plt.subplots(figsize=(max(6.4, 1.05 * len(protocols) + 2.4), 4.8))
    ax.axhline(0.0, linestyle="--", linewidth=1.0, color="gray", alpha=0.45, zorder=1)
    for idx, protocol in enumerate(protocols):
        sub = plot_df[plot_df["Protocol"] == protocol]
        jitter = rng.normal(0, 0.035, size=sub.shape[0]) if sub.shape[0] > 1 else np.zeros(sub.shape[0])
        size_source = sub["n_cells"] if "n_cells" in sub.columns else np.ones(sub.shape[0])
        sizes = _scale_marker_sizes(size_source, min_size=80, max_size=220)
        ax.scatter(np.full(sub.shape[0], x_map[protocol]) + jitter, sub["ra"], s=sizes, marker="s", color=_protocol_color(protocol, idx), edgecolor="black", linewidth=0.8, alpha=0.92, label=_short_protocol_name(protocol), zorder=3)
    ax.set_xticks(np.arange(len(protocols)))
    ax.set_xticklabels([_short_protocol_name(protocol) for protocol in protocols], rotation=20, ha="right")
    ymin = min(-0.05, float(plot_df["ra"].min()) - 0.08)
    ymax = max(0.2, float(plot_df["ra"].max()) + 0.08)
    ax.set_ylim(max(-1.0, ymin), min(1.0, ymax))
    ax.set_ylabel("Regulon activity correlation (ra)")
    ax.set_title("Component F2: regulon activity alignment")
    ax.grid(axis="y", alpha=0.22, linewidth=0.7)
    _hide_top_right_spines(ax)
    fig.tight_layout()
    return fig


def _save_comparison_component_scores(df: pd.DataFrame, path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    return _save_figure_or_none(plot_protocol_component_scores(df), path_base, formats=formats, dpi=dpi)


def _save_comparison_bar(df: pd.DataFrame, path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    return _save_figure_or_none(plot_protocol_weighted_cls(df), path_base, formats=formats, dpi=dpi)


def _save_comparison_weighted_contribution(df: pd.DataFrame, path_base: Path, *, cls_weights: Mapping[str, float] | None, formats: Sequence[str], dpi: int) -> str | None:
    return _save_figure_or_none(plot_protocol_weighted_contribution(df, cls_weights=cls_weights), path_base, formats=formats, dpi=dpi)


def _save_comparison_heatmap(df: pd.DataFrame, path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    return _save_figure_or_none(plot_protocol_component_heatmap(df), path_base, formats=formats, dpi=dpi)


def _save_radar(df: pd.DataFrame, path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    return _save_figure_or_none(plot_protocol_radar(df), path_base, formats=formats, dpi=dpi)


def _save_comparison_component_a(protocols: Sequence[Mapping[str, Any]], path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    rows: list[dict[str, Any]] = []
    for record in _protocol_records(protocols):
        batch = _read_component_batch(record["step3_dir"], record["dataset_id"], "A")
        score = _read_component_score(record["step3_dir"], record["dataset_id"], "A")
        if batch is None or score is None or not {"sA1_mean", "sA2_ks"}.issubset(batch.columns):
            continue
        weights = pd.to_numeric(batch["n_cells"], errors="coerce").fillna(1.0).clip(lower=1.0) if "n_cells" in batch.columns else pd.Series(np.ones(batch.shape[0]))
        rows.append(
            {
                "Protocol": record["name"],
                "A1": float(np.average(pd.to_numeric(batch["sA1_mean"], errors="coerce").fillna(0.0), weights=weights)),
                "A2": float(np.average(pd.to_numeric(batch["sA2_ks"], errors="coerce").fillna(0.0), weights=weights)),
                "A_global": float(score),
            }
        )
    return _save_figure_or_none(plot_protocol_component_A(pd.DataFrame(rows)), path_base, formats=formats, dpi=dpi)


def _save_comparison_component_b(protocols: Sequence[Mapping[str, Any]], path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    batches: list[pd.DataFrame] = []
    globals_: list[dict[str, Any]] = []
    for record in _protocol_records(protocols):
        batch = _read_component_batch(record["step3_dir"], record["dataset_id"], "B")
        score = _read_component_score(record["step3_dir"], record["dataset_id"], "B")
        if batch is None or score is None or not ({"r", "sB"} & set(batch.columns)):
            continue
        batch = batch.copy()
        batch["Protocol"] = record["name"]
        batches.append(batch)
        globals_.append({"Protocol": record["name"], "sB_global": float(score)})
    if not batches:
        return None
    return _save_figure_or_none(plot_protocol_component_B(pd.concat(batches, ignore_index=True), pd.DataFrame(globals_)), path_base, formats=formats, dpi=dpi)


def _save_comparison_component_c(protocols: Sequence[Mapping[str, Any]], path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    batches: list[pd.DataFrame] = []
    globals_: list[dict[str, Any]] = []
    auc_refs: list[float] = []
    for record in _protocol_records(protocols):
        batch = _read_component_batch(record["step3_dir"], record["dataset_id"], "C")
        payload = _read_component_payload(record["step3_dir"], record["dataset_id"], "C")
        score = _finite_float(payload.get("global_score")) if payload else None
        if batch is None or score is None or "AUC_org" not in batch.columns:
            continue
        batch = batch.copy()
        batch["Protocol"] = record["name"]
        batches.append(batch)
        globals_.append({"Protocol": record["name"], "sC_global": float(score)})
        details = (payload.get("meta", {}) or {}).get("auc_ref_details", {}) if payload else {}
        auc_ref = _finite_float(details.get("AUC_ref")) if isinstance(details, Mapping) else None
        if auc_ref is None and "AUC_ref" in batch.columns:
            auc_ref = _finite_float(pd.to_numeric(batch["AUC_ref"], errors="coerce").mean())
        if auc_ref is not None:
            auc_refs.append(auc_ref)
    if not batches:
        return None
    auc_ref = float(np.mean(auc_refs)) if auc_refs else None
    return _save_figure_or_none(plot_protocol_component_C(pd.concat(batches, ignore_index=True), pd.DataFrame(globals_), auc_ref), path_base, formats=formats, dpi=dpi)


def _save_comparison_component_d(protocols: Sequence[Mapping[str, Any]], path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    batches: list[pd.DataFrame] = []
    globals_: list[dict[str, Any]] = []
    for record in _protocol_records(protocols):
        batch = _read_component_batch(record["step3_dir"], record["dataset_id"], "D")
        score = _read_component_score(record["step3_dir"], record["dataset_id"], "D")
        if batch is None or score is None or not {"sD_query", "sD_ref"}.issubset(batch.columns):
            continue
        batch = batch.copy()
        batch["Protocol"] = record["name"]
        batches.append(batch)
        globals_.append({"Protocol": record["name"], "sD_global": float(score)})
    if not batches:
        return None
    combined = pd.concat(batches, ignore_index=True)
    return _save_figure_or_none(plot_protocol_component_D(combined, pd.DataFrame(globals_)), path_base, formats=formats, dpi=dpi)


def _save_comparison_component_e(protocols: Sequence[Mapping[str, Any]], path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    gene_frames: dict[str, pd.DataFrame] = {}
    scores: dict[str, float | None] = {}
    for record in _protocol_records(protocols):
        genes_path = _component_genes_path(record["step3_dir"], record["dataset_id"], "E")
        if not genes_path.exists():
            continue
        genes = pd.read_csv(genes_path)
        if "rho" not in genes.columns:
            continue
        gene_frames[record["name"]] = genes
        scores[record["name"]] = _read_component_score(record["step3_dir"], record["dataset_id"], "E")
    return _save_figure_or_none(plot_protocol_component_E(gene_frames, scores), path_base, formats=formats, dpi=dpi)


def _save_comparison_component_f1(protocols: Sequence[Mapping[str, Any]], path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    batches: list[pd.DataFrame] = []
    globals_: list[dict[str, Any]] = []
    for record in _protocol_records(protocols):
        batch = _read_component_batch(record["step3_dir"], record["dataset_id"], "F")
        score = _read_component_score(record["step3_dir"], record["dataset_id"], "F")
        if batch is None or score is None or "J" not in batch.columns:
            continue
        batch = batch.copy()
        batch["Protocol"] = record["name"]
        batches.append(batch)
        globals_.append({"Protocol": record["name"], "sF_global": float(score)})
    if not batches:
        return None
    return _save_figure_or_none(plot_protocol_component_F1(pd.concat(batches, ignore_index=True), pd.DataFrame(globals_)), path_base, formats=formats, dpi=dpi)


def _save_comparison_component_f2(protocols: Sequence[Mapping[str, Any]], path_base: Path, *, formats: Sequence[str], dpi: int) -> str | None:
    batches: list[pd.DataFrame] = []
    globals_: list[dict[str, Any]] = []
    for record in _protocol_records(protocols):
        batch = _read_component_batch(record["step3_dir"], record["dataset_id"], "F")
        score = _read_component_score(record["step3_dir"], record["dataset_id"], "F")
        if batch is None or score is None or "ra" not in batch.columns:
            continue
        batch = batch.copy()
        batch["Protocol"] = record["name"]
        batches.append(batch)
        globals_.append({"Protocol": record["name"], "sF_global": float(score)})
    if not batches:
        return None
    return _save_figure_or_none(plot_protocol_component_F2(pd.concat(batches, ignore_index=True), pd.DataFrame(globals_)), path_base, formats=formats, dpi=dpi)


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
        path = _save_comparison_component_scores(df, figdir / f"{prefix}.component_scores", formats=formats, dpi=dpi)
        if path:
            figures["comparison_component_scores"] = path
        path = _save_radar(df, figdir / f"{prefix}.radar", formats=formats, dpi=dpi)
        if path:
            figures["comparison_radar"] = path
        path = _save_comparison_bar(df, figdir / f"{prefix}.weighted_cls", formats=formats, dpi=dpi)
        if path:
            figures["comparison_weighted_cls"] = path
        path = _save_comparison_weighted_contribution(df, figdir / f"{prefix}.weighted_contribution", cls_weights=cls_weights, formats=formats, dpi=dpi)
        if path:
            figures["comparison_weighted_contribution"] = path
        path = _save_comparison_heatmap(df, figdir / f"{prefix}.component_heatmap", formats=formats, dpi=dpi)
        if path:
            figures["comparison_heatmap"] = path
        path = _save_comparison_component_a(protocols, figdir / f"{prefix}.component_A_identity", formats=formats, dpi=dpi)
        if path:
            figures["comparison_component_A_identity"] = path
        path = _save_comparison_component_b(protocols, figdir / f"{prefix}.component_B_pseudobulk", formats=formats, dpi=dpi)
        if path:
            figures["comparison_component_B_pseudobulk"] = path
        path = _save_comparison_component_c(protocols, figdir / f"{prefix}.component_C_transfer_auc", formats=formats, dpi=dpi)
        if path:
            figures["comparison_component_C_transfer_auc"] = path
        path = _save_comparison_component_d(protocols, figdir / f"{prefix}.component_D_neighborhood", formats=formats, dpi=dpi)
        if path:
            figures["comparison_component_D_neighborhood"] = path
        path = _save_comparison_component_e(protocols, figdir / f"{prefix}.component_E_pseudotime", formats=formats, dpi=dpi)
        if path:
            figures["comparison_component_E_pseudotime"] = path
        path = _save_comparison_component_f1(protocols, figdir / f"{prefix}.component_F1_regulon_overlap", formats=formats, dpi=dpi)
        if path:
            figures["comparison_component_F1_regulon_overlap"] = path
        path = _save_comparison_component_f2(protocols, figdir / f"{prefix}.component_F2_activity_alignment", formats=formats, dpi=dpi)
        if path:
            figures["comparison_component_F2_activity_alignment"] = path

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
