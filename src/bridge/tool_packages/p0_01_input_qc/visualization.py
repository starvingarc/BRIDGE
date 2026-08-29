from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "bridge-p0-01-v0.1"
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

INK = "#223746"
MUTED = "#667783"
GRID = "#DCE4E7"
PALE = "#F3F6F6"
TEAL = "#2B7A78"
TEAL_LIGHT = "#8FC4BF"
AMBER = "#9B6518"
VERMILION = "#B9553F"
UNAVAILABLE = "#5F707A"

FIGURE_RC = {
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 8.5,
    "axes.labelcolor": INK,
    "axes.titlecolor": INK,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.linewidth": 0.7,
    "svg.fonttype": "none",
}

DENSITY_CMAP = LinearSegmentedColormap.from_list(
    "bridge_qc_density",
    ["#EDF4F3", "#A6CFCA", "#4B9592", "#285E67", INK],
)
_MATPLOTLIB_VERSION = tuple(int(part) for part in matplotlib.__version__.split(".")[:2])
_VIOLIN_DIRECTION = (
    {"orientation": "horizontal"}
    if _MATPLOTLIB_VERSION >= (3, 10)
    else {"vert": False}
)

METRICS = (
    (
        "total_counts",
        "Total counts",
        "counts",
        "log10(count + 1)",
        lambda values: np.log10(values + 1.0),
    ),
    (
        "detected_genes",
        "Detected genes",
        "genes",
        "log10(genes + 1)",
        lambda values: np.log10(values + 1.0),
    ),
    (
        "mitochondrial_fraction",
        "Mitochondrial transcripts",
        "fraction",
        "% of counts",
        lambda values: values * 100.0,
    ),
    (
        "ribosomal_fraction",
        "Ribosomal transcripts",
        "fraction",
        "% of counts",
        lambda values: values * 100.0,
    ),
    (
        "top_20_gene_fraction",
        "Top-20 gene concentration",
        "fraction",
        "% of counts",
        lambda values: values * 100.0,
    ),
)

FLAG_LABELS = {
    "flag_zero_total_counts": "Zero total counts",
    "flag_low_detected_genes": "Low detected genes",
    "flag_high_detected_genes": "High detected genes",
    "flag_high_mitochondrial_fraction": "High mitochondrial fraction",
}


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


def render_analysis_eligibility(
    *,
    declared_observations: int,
    flags: pd.DataFrame | None,
    view_states: Mapping[str, str],
    output_stem: Path,
    observation_unit: str,
    structure_state: str = "eligible",
    count_metrics_state: str = "available",
) -> tuple[Path, Path]:
    with plt.rc_context(FIGURE_RC):
        fig, (flow_axis, view_axis) = plt.subplots(
            1,
            2,
            figsize=(10.2, 4.4),
            gridspec_kw={"width_ratios": [2.15, 1.0]},
        )
        fig.subplots_adjust(left=0.055, right=0.98, top=0.74, bottom=0.17, wspace=0.22)
        _figure_heading(
            fig,
            "Observation retention and analysis eligibility",
            "Technical eligibility and candidate QC status; no observations are removed by this view.",
        )

        flow_axis.set_xlim(-0.15, 2.2)
        flow_axis.set_ylim(-0.55, 0.65)
        flow_axis.axis("off")
        nodes = (
            ("Declared input", f"{declared_observations:,} {observation_unit}", "available"),
            ("Structure + matrix semantics", structure_state, structure_state),
            ("Per-observation QC metrics", count_metrics_state, count_metrics_state),
        )
        for index, (label, value, state) in enumerate(nodes):
            color = _state_color(state)
            if index:
                flow_axis.plot([index - 0.84, index - 0.16], [0.32, 0.32], color=GRID, lw=2.2, zorder=0)
            flow_axis.scatter(index, 0.32, s=350, color="white", edgecolor=color, linewidth=2.4, zorder=2)
            flow_axis.scatter(index, 0.32, s=62, color=color, edgecolor="none", zorder=3)
            flow_axis.text(index, 0.03, label, ha="center", va="top", weight="bold", fontsize=8.2)
            flow_axis.text(index, -0.13, value.replace("_", " "), ha="center", va="top", color=MUTED, fontsize=8)

        flow_axis.text(0.0, -0.36, "Candidate QC status (not a filter)", weight="bold", fontsize=8.3)
        bar_left, bar_width = 0.0, 2.0
        eligible, review = _candidate_counts(flags, declared_observations)
        if eligible is None:
            flow_axis.barh(-0.49, bar_width, left=bar_left, height=0.12, color=PALE, edgecolor=UNAVAILABLE)
            flow_axis.text(1.0, -0.49, "Unavailable", ha="center", va="center", color=MUTED, fontsize=8)
        else:
            eligible_width = bar_width * eligible / max(declared_observations, 1)
            review_width = bar_width - eligible_width
            flow_axis.barh(-0.49, eligible_width, left=bar_left, height=0.12, color=TEAL, edgecolor="none")
            flow_axis.barh(
                -0.49,
                review_width,
                left=bar_left + eligible_width,
                height=0.12,
                color=AMBER,
                edgecolor="none",
            )
            flow_axis.text(
                bar_left,
                -0.63,
                f"Candidate-eligible  {eligible:,} "
                f"({_format_percentage(eligible, declared_observations)})",
                ha="left",
                va="top",
                color=TEAL,
                weight="bold",
            )
            flow_axis.text(
                bar_left + bar_width,
                -0.63,
                f"Flagged for review  {review:,} "
                f"({_format_percentage(review, declared_observations)})",
                ha="right",
                va="top",
                color=AMBER,
                weight="bold",
            )

        view_axis.axis("off")
        view_axis.set_xlim(0, 1)
        view_axis.set_ylim(0, 1)
        view_axis.text(0.0, 0.94, "Downstream data views", weight="bold", fontsize=10.2)
        view_axis.text(0.0, 0.84, "Availability is reported; stability is not inferred.", color=MUTED, fontsize=8)
        for row, (label, state) in enumerate(view_states.items()):
            y = 0.67 - row * 0.19
            color = _state_color(state)
            view_axis.scatter(0.035, y, s=58, color=color, edgecolor="white", linewidth=0.7)
            view_axis.text(0.10, y + 0.025, label, va="center", weight="bold", fontsize=8.3)
            view_axis.text(0.10, y - 0.055, state.replace("_", " "), va="center", color=MUTED, fontsize=8)
        view_axis.text(
            0.0,
            0.03,
            f"Denominator: {declared_observations:,} declared {observation_unit}.",
            color=MUTED,
            fontsize=7.8,
        )
        return _save_figure(fig, output_stem)


def render_qc_distributions(
    metrics: pd.DataFrame,
    groups: pd.Series,
    output_stem: Path,
    *,
    observation_unit: str,
) -> tuple[Path, Path]:
    if len(metrics) != len(groups):
        raise ValueError("metrics and groups must contain the same observations")
    group_values = groups.astype("string").fillna("Unavailable").to_numpy()
    group_order = sorted(pd.unique(group_values).tolist(), key=_capture_sort_key)
    positions = np.arange(len(group_order))
    group_labels = [
        f"{group}  n={int(np.sum(group_values == group)):,}"
        for group in group_order
    ]

    with plt.rc_context(FIGURE_RC):
        fig, axes = plt.subplots(
            1,
            len(METRICS),
            figsize=(13.2, max(4.2, 2.5 + 0.43 * len(group_order))),
            sharey=True,
        )
        fig.subplots_adjust(left=0.105, right=0.99, top=0.76, bottom=0.16, wspace=0.16)
        _figure_heading(
            fig,
            "Quality-metric distributions by capture",
            "Distributions, median and interquartile range are shown separately for each caller-declared capture.",
        )

        for axis, (column, title, _, display_unit, transform) in zip(
            axes, METRICS, strict=True
        ):
            available_groups = 0
            for position, group in zip(positions, group_order, strict=True):
                values = pd.to_numeric(metrics.loc[group_values == group, column], errors="coerce").dropna()
                transformed = transform(values.to_numpy(dtype=float))
                transformed = transformed[np.isfinite(transformed)]
                if not len(transformed):
                    axis.text(
                        0.02,
                        position,
                        "Unavailable",
                        transform=axis.get_yaxis_transform(),
                        ha="left",
                        va="center",
                        color=UNAVAILABLE,
                        fontsize=7.4,
                    )
                    continue
                available_groups += 1
                _draw_raincloud(axis, transformed, float(position))
            axis.set_title(title, loc="left", fontsize=9.1, weight="bold", pad=8)
            axis.set_xlabel(display_unit, fontsize=7.8)
            axis.set_yticks(positions, group_labels)
            axis.invert_yaxis()
            axis.xaxis.grid(True, color=GRID, lw=0.65)
            axis.set_axisbelow(True)
            axis.spines[["top", "right", "left"]].set_visible(False)
            axis.tick_params(axis="y", length=0)
            if not available_groups:
                axis.text(0.5, 0.5, "Unavailable", transform=axis.transAxes, ha="center", va="center", color=MUTED)
        axes[0].set_ylabel("Caller-declared capture", labelpad=9)
        fig.text(
            0.105,
            0.035,
            f"Denominator: {len(metrics):,} declared {observation_unit}; points are a deterministic display subsample.",
            color=MUTED,
            fontsize=7.8,
        )
        return _save_figure(fig, output_stem)


def render_qc_relationships(
    metrics: pd.DataFrame,
    output_stem: Path,
    *,
    flags: pd.DataFrame | None = None,
    candidate_rules: Mapping[str, float] | None = None,
    observation_unit: str,
) -> tuple[Path, Path]:
    review_overlay_available = flags is not None and any(
        column in flags.columns for column in FLAG_LABELS
    )
    subtitle = (
        "Hexagons show observation density; amber outlines show a deterministic "
        "subset of candidate-review observations, capped at 60 per panel."
        if review_overlay_available
        else (
            "Hexagons show observation density; the candidate-review overlay is unavailable."
        )
    )
    with plt.rc_context(FIGURE_RC):
        fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.6))
        fig.subplots_adjust(left=0.08, right=0.96, top=0.74, bottom=0.19, wspace=0.34)
        _figure_heading(
            fig,
            "Library complexity and mitochondrial transcript fraction",
            subtitle,
        )
        review_mask = _review_mask(flags, metrics.index)
        counts = pd.to_numeric(metrics["total_counts"], errors="coerce")
        genes = pd.to_numeric(metrics["detected_genes"], errors="coerce")
        common = counts.gt(0) & genes.gt(0)
        first_hex = _hexbin_or_unavailable(
            axes[0],
            counts[common],
            genes[common],
            "Total counts",
            "Detected genes",
            xscale="log",
            yscale="log",
        )
        axes[0].set_title("A  Library complexity", loc="left", weight="bold", fontsize=9.3)
        _overlay_review(
            axes[0],
            counts,
            genes,
            common & review_mask,
        )
        if candidate_rules:
            minimum_genes = float(candidate_rules["min_detected_genes"])
            maximum_genes = float(candidate_rules["max_detected_genes"])
            _threshold_line(
                axes[0],
                minimum_genes,
                f"Candidate minimum: {minimum_genes:,.0f}",
                x_position=0.02,
            )
            _threshold_line(
                axes[0],
                maximum_genes,
                f"Candidate maximum: {maximum_genes:,.0f}",
            )

        mitochondrial = pd.to_numeric(metrics["mitochondrial_fraction"], errors="coerce") * 100.0
        mito_common = counts.gt(0) & mitochondrial.notna()
        second_hex = _hexbin_or_unavailable(
            axes[1],
            counts[mito_common],
            mitochondrial[mito_common],
            "Total counts",
            "Mitochondrial transcripts (% of counts)",
            xscale="log",
        )
        axes[1].set_title("B  Mitochondrial transcript fraction", loc="left", weight="bold", fontsize=9.3)
        _overlay_review(
            axes[1],
            counts,
            mitochondrial,
            mito_common & review_mask,
        )
        if candidate_rules and mitochondrial.notna().any():
            maximum_mito = 100.0 * float(candidate_rules["max_mitochondrial_fraction"])
            _threshold_line(
                axes[1],
                maximum_mito,
                f"Candidate maximum: {maximum_mito:g}%",
            )

        for axis, hexbin in zip(axes, (first_hex, second_hex), strict=True):
            axis.spines[["top", "right"]].set_visible(False)
            if hexbin is None:
                continue
            occupancy = np.asarray(hexbin.get_array(), dtype=float)
            if occupancy.size and np.ptp(occupancy) > 0:
                colorbar = fig.colorbar(hexbin, ax=axis, pad=0.025, fraction=0.046)
                if colorbar.solids is not None:
                    colorbar.solids.set_rasterized(False)
                colorbar.set_label(f"{observation_unit.capitalize()} per hexagon", fontsize=7.5)
                colorbar.outline.set_visible(False)
            else:
                axis.text(
                    0.98,
                    0.02,
                    "One observation per occupied hexagon",
                    transform=axis.transAxes,
                    ha="right",
                    va="bottom",
                    color=MUTED,
                    fontsize=7.2,
                )
        fig.text(
            0.08,
            0.045,
            f"Denominator: {len(metrics):,} declared {observation_unit}. "
            "Review thresholds were predefined for this run and do not remove observations.",
            color=MUTED,
            fontsize=7.8,
        )
        return _save_figure(fig, output_stem)


def flag_intersection_table(flags: pd.DataFrame) -> pd.DataFrame:
    """Return exact, deterministically ordered intersections of candidate flags."""

    flag_columns = [column for column in FLAG_LABELS if column in flags.columns]
    if not flag_columns:
        raise ValueError("at least one candidate QC flag is required")
    combinations = (
        flags[flag_columns]
        .fillna(False)
        .astype(bool)
        .value_counts(sort=False)
        .rename("count")
        .reset_index()
    )
    combinations["n_flags"] = combinations[flag_columns].sum(axis=1)
    return combinations.sort_values(
        ["count", "n_flags", *flag_columns],
        ascending=[False, True, *([False] * len(flag_columns))],
        kind="stable",
    ).reset_index(drop=True)


def render_qc_flag_intersections(
    flags: pd.DataFrame,
    output_stem: Path,
    *,
    observation_unit: str,
) -> tuple[Path, Path]:
    flag_columns = [column for column in FLAG_LABELS if column in flags.columns]
    combinations = flag_intersection_table(flags)
    if len(combinations) == 1 and int(combinations.iloc[0]["n_flags"]) == 0:
        return _render_no_candidate_flags(
            len(flags),
            output_stem,
            observation_unit=observation_unit,
        )
    x_values = np.arange(len(combinations))
    colors = [TEAL if row.n_flags == 0 else AMBER for row in combinations.itertuples()]

    with plt.rc_context(FIGURE_RC):
        fig = plt.figure(figsize=(max(7.4, 0.6 * len(combinations) + 3.0), 5.5))
        grid = fig.add_gridspec(2, 1, height_ratios=[2.1, 1.2], hspace=0.08)
        bar_axis = fig.add_subplot(grid[0])
        matrix_axis = fig.add_subplot(grid[1], sharex=bar_axis)
        fig.subplots_adjust(left=0.24, right=0.98, top=0.76, bottom=0.14)
        _figure_heading(
            fig,
            "QC-flag combinations and observation counts",
            "Bars are mutually exclusive intersections; individual candidate flags may overlap.",
        )

        counts = combinations["count"].to_numpy(dtype=int)
        bar_axis.bar(x_values, counts, width=0.68, color=colors, edgecolor="none")
        use_log_scale = (
            len(counts) > 1
            and counts.min() > 0
            and counts.max() / counts.min() >= 100
        )
        if use_log_scale:
            bar_axis.set_yscale("log")
        for x_value, (count, row) in enumerate(
            zip(counts, combinations.itertuples(), strict=True)
        ):
            y_value = (
                count * 1.16
                if use_log_scale
                else count + max(counts.max(initial=0) * 0.025, 0.5)
            )
            label = f"{count:,}\n({_format_percentage(count, len(flags))})"
            if row.n_flags == 0:
                label += "\nNo candidate flag"
            bar_axis.text(x_value, y_value, label, ha="center", va="bottom", fontsize=7.8)
        scale_note = " (log scale)" if use_log_scale else ""
        bar_axis.set_ylabel(f"Declared {observation_unit}{scale_note}")
        bar_axis.set_xticks([])
        bar_axis.yaxis.grid(True, color=GRID, lw=0.65)
        bar_axis.set_axisbelow(True)
        bar_axis.spines[["top", "right"]].set_visible(False)

        y_values = np.arange(len(flag_columns))
        for x_value, row in combinations.iterrows():
            active = []
            for y_value, column in zip(y_values, flag_columns, strict=True):
                is_active = bool(row[column])
                matrix_axis.scatter(
                    x_value,
                    y_value,
                    s=42 if is_active else 18,
                    color=AMBER if is_active else GRID,
                    edgecolor="none",
                    zorder=2,
                )
                if is_active:
                    active.append(y_value)
            if len(active) > 1:
                matrix_axis.plot([x_value, x_value], [min(active), max(active)], color=AMBER, lw=1.5, zorder=1)
        matrix_axis.set_yticks(y_values, [FLAG_LABELS[column] for column in flag_columns])
        matrix_axis.invert_yaxis()
        matrix_axis.set_xticks(x_values, [str(index + 1) for index in x_values])
        bar_axis.tick_params(axis="x", bottom=False, labelbottom=False)
        matrix_axis.set_xlabel("Exclusive flag combination")
        matrix_axis.tick_params(axis="y", length=0)
        matrix_axis.spines[["top", "right", "bottom", "left"]].set_visible(False)
        matrix_axis.xaxis.grid(True, color=PALE, lw=0.6)
        fig.text(
            0.24,
            0.035,
            f"Denominator: {len(flags):,} declared {observation_unit}; teal denotes no candidate flag, amber denotes review flags.",
            color=MUTED,
            fontsize=7.8,
        )
        return _save_figure(fig, output_stem)


def _render_no_candidate_flags(
    declared: int,
    output_stem: Path,
    *,
    observation_unit: str,
) -> tuple[Path, Path]:
    with plt.rc_context(FIGURE_RC):
        fig, axis = plt.subplots(figsize=(7.4, 3.6))
        fig.subplots_adjust(left=0.08, right=0.96, top=0.69, bottom=0.19)
        _figure_heading(
            fig,
            "QC-flag combinations and observation counts",
            "No declared observation met any candidate review rule.",
        )
        axis.axis("off")
        axis.plot(
            [0.0, 1.0],
            [0.48, 0.48],
            transform=axis.transAxes,
            color=TEAL_LIGHT,
            lw=12,
            solid_capstyle="round",
        )
        axis.text(
            0.0,
            0.7,
            "No candidate QC flags observed",
            transform=axis.transAxes,
            fontsize=12,
            weight="bold",
        )
        axis.text(
            0.0,
            0.24,
            f"{declared:,} of {declared:,} declared {observation_unit} (100.0%)",
            transform=axis.transAxes,
            color=MUTED,
            fontsize=9,
        )
        fig.text(
            0.08,
            0.055,
            "Candidate thresholds support review; this result is not a biological quality, safety or potency conclusion.",
            color=MUTED,
            fontsize=7.8,
        )
        return _save_figure(fig, output_stem)


def render_unavailable_figure(
    output_stem: Path,
    *,
    title: str,
    reason: str,
    denominator: str,
) -> tuple[Path, Path]:
    """Render an explicit unavailable state without encoding it as zero."""

    with plt.rc_context(FIGURE_RC):
        fig, axis = plt.subplots(figsize=(8.2, 3.4))
        fig.subplots_adjust(left=0.07, right=0.97, top=0.68, bottom=0.18)
        _figure_heading(fig, title, "The required technical input is unavailable; no quantitative value is shown.")
        axis.axis("off")
        axis.plot([0.02, 0.12], [0.58, 0.58], color=UNAVAILABLE, lw=4, solid_capstyle="round")
        axis.text(0.16, 0.62, "Unavailable", transform=axis.transAxes, weight="bold", fontsize=11)
        axis.text(0.16, 0.43, reason, transform=axis.transAxes, color=MUTED, fontsize=8.5)
        axis.text(0.02, 0.04, f"Denominator: {denominator}.", transform=axis.transAxes, color=MUTED, fontsize=7.8)
        return _save_figure(fig, output_stem)


def _candidate_counts(
    flags: pd.DataFrame | None,
    declared_observations: int,
) -> tuple[int | None, int | None]:
    if flags is None or "bridge_qc_candidate_eligible" not in flags:
        return None, None
    eligible = int(flags["bridge_qc_candidate_eligible"].fillna(False).astype(bool).sum())
    return eligible, max(declared_observations - eligible, 0)


def _format_percentage(count: int, total: int) -> str:
    if total <= 0:
        return "unavailable"
    percentage = 100.0 * count / total
    precision = 2 if 0.0 < percentage < 1.0 else 1
    return f"{percentage:.{precision}f}%"


def _capture_sort_key(label: str) -> tuple[int, int | str]:
    suffix = label.rsplit("Capture ", 1)
    if len(suffix) == 2 and suffix[1].isdigit():
        return 0, int(suffix[1])
    return 1, label


def _review_mask(flags: pd.DataFrame | None, index: pd.Index) -> pd.Series:
    if flags is None:
        return pd.Series(False, index=index)
    columns = [column for column in FLAG_LABELS if column in flags.columns]
    if not columns:
        return pd.Series(False, index=index)
    return flags[columns].fillna(False).astype(bool).any(axis=1).reindex(index, fill_value=False)


def _draw_raincloud(axis: plt.Axes, values: np.ndarray, position: float) -> None:
    if len(values) > 1 and float(np.nanmax(values)) > float(np.nanmin(values)):
        violin = axis.violinplot(
            [values],
            positions=[position],
            widths=0.62,
            showmeans=False,
            showmedians=False,
            showextrema=False,
            bw_method=0.28,
            **_VIOLIN_DIRECTION,
        )
        for body in violin["bodies"]:
            body.set_facecolor(TEAL_LIGHT)
            body.set_edgecolor("none")
            body.set_alpha(0.72)
    display = values[_display_indices(len(values), 110)]
    offsets = (((np.arange(len(display)) * 0.61803398875) % 1.0) - 0.5) * 0.28
    axis.scatter(display, position + offsets, s=7, color=TEAL, alpha=0.48, edgecolor="none")
    q1, median, q3 = np.quantile(values, [0.25, 0.5, 0.75])
    axis.plot([q1, q3], [position, position], color=INK, lw=2.2, solid_capstyle="round", zorder=4)
    axis.scatter(median, position, s=26, color="white", edgecolor=INK, linewidth=1.1, zorder=5)


def _display_indices(size: int, maximum: int) -> np.ndarray:
    if size <= maximum:
        return np.arange(size)
    return np.linspace(0, size - 1, maximum, dtype=int)


def _hexbin_or_unavailable(
    axis: plt.Axes,
    x_values: pd.Series,
    y_values: pd.Series,
    x_label: str,
    y_label: str,
    *,
    xscale: str = "linear",
    yscale: str = "linear",
):
    if x_values.empty or y_values.empty:
        axis.axis("off")
        axis.text(0.5, 0.52, "Unavailable", ha="center", va="center", weight="bold", transform=axis.transAxes)
        axis.text(0.5, 0.42, "Required per-observation metric is missing.", ha="center", va="center", color=MUTED, transform=axis.transAxes)
        return None
    hexbin = axis.hexbin(
        x_values.to_numpy(dtype=float),
        y_values.to_numpy(dtype=float),
        gridsize=34,
        mincnt=1,
        bins="log",
        xscale=xscale,
        yscale=yscale,
        cmap=DENSITY_CMAP,
        linewidths=0,
    )
    axis.set_xlabel(x_label)
    axis.set_ylabel(y_label)
    return hexbin


def _overlay_review(
    axis: plt.Axes,
    x_values: pd.Series,
    y_values: pd.Series,
    mask: pd.Series,
) -> None:
    valid = mask.to_numpy(dtype=bool) & x_values.notna().to_numpy() & y_values.notna().to_numpy()
    selected = np.flatnonzero(valid)
    selected = selected[_display_indices(len(selected), 60)]
    if len(selected):
        axis.scatter(
            x_values.iloc[selected],
            y_values.iloc[selected],
            s=15,
            facecolors="none",
            edgecolors=AMBER,
            linewidths=0.6,
            alpha=0.68,
        )


def _threshold_line(
    axis: plt.Axes,
    value: float,
    label: str,
    *,
    x_position: float = 0.98,
) -> None:
    axis.axhline(value, color=AMBER, lw=0.9, ls=(0, (3, 2)), alpha=0.9)
    axis.text(
        x_position,
        value,
        label,
        transform=axis.get_yaxis_transform(),
        ha="left" if x_position < 0.5 else "right",
        va="bottom",
        color=AMBER,
        fontsize=7.1,
        bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.8, "alpha": 0.82},
    )


def _state_color(state: str) -> str:
    normalized = state.lower()
    if normalized in {"available", "eligible", "measured"}:
        return TEAL
    if normalized in {"candidate", "review_required", "partial"}:
        return AMBER
    if normalized in {"failed", "invalid"}:
        return VERMILION
    return UNAVAILABLE


def _figure_heading(fig: plt.Figure, title: str, subtitle: str) -> None:
    fig.text(0.055, 0.94, title, ha="left", va="top", fontsize=13.0, weight="bold", color=INK)
    fig.text(0.055, 0.875, subtitle, ha="left", va="top", fontsize=8.5, color=MUTED)


def _save_figure(fig: plt.Figure, output_stem: Path) -> tuple[Path, Path]:
    svg = output_stem.with_suffix(".svg")
    png = output_stem.with_suffix(".png")
    fig.savefig(svg, bbox_inches="tight", pad_inches=0.08, metadata={"Date": None})
    fig.savefig(
        png,
        dpi=300,
        bbox_inches="tight",
        pad_inches=0.08,
        facecolor="white",
        metadata={"Software": "BRIDGE"},
    )
    plt.close(fig)
    return svg, png
