from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "bridge-p0-01-v0.1"
import matplotlib.pyplot as plt
import pandas as pd


def render_qc_overview(
    metrics: pd.DataFrame,
    output_stem: Path,
    *,
    observation_unit: str,
) -> tuple[Path, Path]:
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.2), constrained_layout=True)
    fields = [
        ("total_counts", "Total counts"),
        ("detected_genes", "Detected genes"),
        ("mitochondrial_fraction", "Mitochondrial fraction"),
    ]
    for axis, (column, label) in zip(axes, fields, strict=True):
        values = metrics[column].dropna()
        if values.empty:
            axis.text(0.5, 0.5, "Unavailable", ha="center", va="center", transform=axis.transAxes)
        else:
            axis.hist(values, bins=min(30, max(5, len(values))), color="#3B7C8C", edgecolor="white")
        axis.set_xlabel(label)
        axis.set_ylabel(observation_unit.capitalize())
        axis.spines[["top", "right"]].set_visible(False)
    svg = output_stem.with_suffix(".svg")
    png = output_stem.with_suffix(".png")
    fig.savefig(svg, bbox_inches="tight", metadata={"Date": None})
    fig.savefig(png, dpi=180, bbox_inches="tight", metadata={"Software": "BRIDGE"})
    plt.close(fig)
    return svg, png


def render_counts_genes_scatter(metrics: pd.DataFrame, output_stem: Path) -> tuple[Path, Path]:
    fig, axis = plt.subplots(figsize=(5.2, 4.2), constrained_layout=True)
    mitochondrial = metrics["mitochondrial_fraction"]
    if mitochondrial.notna().any():
        points = axis.scatter(
            metrics["total_counts"],
            metrics["detected_genes"],
            c=mitochondrial,
            cmap="viridis",
            s=18,
            alpha=0.8,
        )
        fig.colorbar(points, ax=axis, label="Mitochondrial fraction")
    else:
        axis.scatter(
            metrics["total_counts"],
            metrics["detected_genes"],
            color="#3B7C8C",
            s=18,
            alpha=0.8,
        )
        axis.text(0.02, 0.98, "Mitochondrial metric unavailable", va="top", transform=axis.transAxes)
    axis.set_xlabel("Total counts")
    axis.set_ylabel("Detected genes")
    axis.spines[["top", "right"]].set_visible(False)
    svg = output_stem.with_suffix(".svg")
    png = output_stem.with_suffix(".png")
    fig.savefig(svg, bbox_inches="tight", metadata={"Date": None})
    fig.savefig(png, dpi=180, bbox_inches="tight", metadata={"Software": "BRIDGE"})
    plt.close(fig)
    return svg, png
