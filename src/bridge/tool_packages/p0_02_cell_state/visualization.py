from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "bridge-p0-02-v0.1"
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def render_composition(
    composition: pd.DataFrame,
    output_stem: Path,
    *,
    label_level: str,
) -> tuple[Path, Path]:
    source = composition[
        (composition["view"] == "source_specific")
        & (composition["label_level"] == label_level)
    ].copy()
    pivot = source.pivot(index="label", columns="source_id", values="fraction").fillna(0)
    fig, axis = plt.subplots(figsize=(8.8, max(3.8, 0.28 * len(pivot))), constrained_layout=True)
    if pivot.empty:
        axis.text(0.5, 0.5, "Unavailable", ha="center", va="center")
    else:
        pivot.plot.barh(ax=axis, width=0.78, color=["#2B7A78", "#E59F45", "#6C63A8", "#5B8E7D"])
        axis.set_xlabel(f"{label_level} shadow top-label fraction")
        axis.set_ylabel("")
        axis.legend(title="Reference source", frameon=False)
    axis.spines[["top", "right"]].set_visible(False)
    return _save(fig, output_stem)


def render_reference_support(support: pd.DataFrame, output_stem: Path) -> tuple[Path, Path]:
    summary = support.groupby(["source_id", "label"], observed=True)["spearman_support"].median()
    pivot = summary.unstack("label")
    fig, axis = plt.subplots(figsize=(max(7.5, 0.42 * len(pivot.columns)), 3.2), constrained_layout=True)
    if pivot.empty:
        axis.text(0.5, 0.5, "Unavailable", ha="center", va="center")
    else:
        image = axis.imshow(pivot.to_numpy(), aspect="auto", cmap="RdBu_r", vmin=-1, vmax=1)
        axis.set_xticks(np.arange(len(pivot.columns)), [_short(item) for item in pivot.columns], rotation=45, ha="right")
        axis.set_yticks(np.arange(len(pivot.index)), pivot.index)
        axis.set_xlabel("L1 state")
        fig.colorbar(image, ax=axis, label="Median Spearman support", shrink=0.8)
    return _save(fig, output_stem)


def render_marker_evidence(
    marker: pd.DataFrame,
    evidence: pd.DataFrame,
    output_stem: Path,
) -> tuple[Path, Path]:
    joined = marker.merge(evidence[["observation_id", "consensus_label"]], on="observation_id", how="left")
    joined["consensus_label"] = joined["consensus_label"].fillna("No consensus")
    pivot = joined.pivot_table(
        index="state_id",
        columns="consensus_label",
        values="positive_mean_expression",
        aggfunc="median",
    )
    fig, axis = plt.subplots(
        figsize=(max(6.5, 0.45 * len(pivot.columns)), max(4.0, 0.3 * len(pivot))),
        constrained_layout=True,
    )
    if pivot.empty:
        axis.text(0.5, 0.5, "Unavailable", ha="center", va="center")
    else:
        image = axis.imshow(pivot.fillna(0).to_numpy(), aspect="auto", cmap="YlGnBu")
        axis.set_xticks(np.arange(len(pivot.columns)), [_short(item) for item in pivot.columns], rotation=45, ha="right")
        axis.set_yticks(np.arange(len(pivot.index)), [_short(item) for item in pivot.index])
        axis.set_xlabel("Reference consensus support")
        fig.colorbar(image, ax=axis, label="Median positive-marker expression", shrink=0.8)
    return _save(fig, output_stem)


def render_conflicts(evidence: pd.DataFrame, output_stem: Path) -> tuple[Path, Path]:
    counts = evidence["support_state"].value_counts()
    fig, axis = plt.subplots(figsize=(6.4, 3.8), constrained_layout=True)
    colors = {
        "consensus_supported": "#2B7A78",
        "single_source_supported": "#6C63A8",
        "source_conflict": "#E59F45",
        "unavailable": "#A9ADB3",
    }
    axis.bar([item.replace("_", " ") for item in counts.index], counts.values, color=[colors.get(item, "#5B8E7D") for item in counts.index])
    axis.set_ylabel("Observations")
    axis.tick_params(axis="x", rotation=20)
    axis.spines[["top", "right"]].set_visible(False)
    return _save(fig, output_stem)


def _save(fig, output_stem: Path) -> tuple[Path, Path]:
    svg = output_stem.with_suffix(".svg")
    png = output_stem.with_suffix(".png")
    fig.savefig(svg, bbox_inches="tight", metadata={"Date": None})
    fig.savefig(png, dpi=180, bbox_inches="tight", metadata={"Software": "BRIDGE"})
    plt.close(fig)
    return svg, png


def _short(value: str) -> str:
    return str(value).split(":", 1)[-1]
