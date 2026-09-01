from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "bridge-p0-02-v0.1"
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch, Rectangle

from bridge.tool_packages.p0_02_cell_state.hierarchical_composition import (
    HierarchicalCellStateCompositionDataV1,
)
from bridge.tool_packages.p0_02_cell_state.visualization_data import (
    CellStateEvidenceMatrixData,
    CellStateEvidenceMatrixRecord,
    EvidenceRole,
    MatrixAssessmentState,
    SourceRelationship,
)
from bridge.toolkit.contracts import EvidenceState


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


def _independent_assessed_state_ids(
    profile: CellStateEvidenceMatrixData,
) -> set[str]:
    independent_ids = {
        source.source_id
        for source in profile.sources
        if source.relationship is SourceRelationship.INDEPENDENT_EXTERNAL
    }
    return {
        record.state_id
        for record in profile.records
        if record.source_id in independent_ids
        and record.evidence_role is EvidenceRole.EXTERNAL_HOLDOUT
        and record.assessment_state is not MatrixAssessmentState.NOT_ASSESSED
    }


_MATRIX_RC = {
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 8.3,
    "axes.labelcolor": "#223746",
    "axes.titlecolor": "#223746",
    "text.color": "#223746",
    "xtick.color": "#667783",
    "ytick.color": "#344955",
    "axes.linewidth": 0.7,
    "svg.fonttype": "none",
}
_MATRIX_INK = "#223746"
_MATRIX_MUTED = "#667783"
_MATRIX_GRID = "#DCE4E7"
_MATRIX_TEAL = "#2B7A78"
_MATRIX_TEAL_LIGHT = "#8FC4BF"
_MATRIX_PURPLE = "#6C63A8"
_MATRIX_AMBER = "#A46C20"
_MATRIX_VERMILION = "#B9553F"
_MATRIX_UNAVAILABLE = "#A8B2B8"
_RELATIONSHIP_COLORS = {
    SourceRelationship.PRIMARY: "#2B7A78",
    SourceRelationship.DERIVED_CONTAINS_PRIMARY: "#DDE5E8",
    SourceRelationship.DEPENDENT_LABEL_TRANSFER: "#C9E1DE",
    SourceRelationship.INDEPENDENT_EXTERNAL: "#E9E5F1",
}
_RELATIONSHIP_LABELS = {
    SourceRelationship.PRIMARY: "PRIMARY\nannotation",
    SourceRelationship.DERIVED_CONTAINS_PRIMARY: "DERIVED\ncontains primary",
    SourceRelationship.DEPENDENT_LABEL_TRANSFER: "DEPENDENT\nlabel transfer",
    SourceRelationship.INDEPENDENT_EXTERNAL: "INDEPENDENT\nexternal",
}


def render_source_state_evidence_matrix(
    profile: CellStateEvidenceMatrixData,
    output_stem: Path,
) -> tuple[Path, Path, Path]:
    """Render the source-aware state matrix without treating sources as votes."""

    states = sorted(profile.states, key=lambda state: state.order)
    sources = list(profile.sources)
    records = {
        (record.state_id, record.source_id): record
        for record in profile.records
    }
    height = max(10.2, 4.2 + 0.30 * len(states))
    independent_count = len(_independent_assessed_state_ids(profile))
    assessment_summary = (
        f"Independent assessment is recorded for {independent_count}/"
        f"{profile.denominator} states; source roles and dependencies remain explicit."
        if independent_count
        else "No independent held-out state assessment is recorded in this profile."
    )
    with plt.rc_context(_MATRIX_RC):
        fig = plt.figure(figsize=(13.2, height), facecolor="#FAFAF8")
        matrix_axis = fig.add_axes([0.245, 0.13, 0.43, 0.64])
        header_axis = fig.add_axes([0.245, 0.785, 0.43, 0.12])
        summary_axis = fig.add_axes([0.72, 0.13, 0.245, 0.775])

        fig.text(
            0.055,
            0.962,
            "Cell-state evidence coverage across registered pre-transplant sources",
            fontsize=17,
            weight="bold",
            ha="left",
            va="top",
            color="#172B3A",
        )
        fig.text(
            0.055,
            0.932,
            assessment_summary,
            fontsize=10,
            ha="left",
            va="top",
            color=_MATRIX_MUTED,
        )

        _draw_source_header(header_axis, sources)
        _draw_source_state_matrix(matrix_axis, states, sources, records)
        _draw_matrix_summary(summary_axis, profile, sources, records)

        fig.text(
            0.055,
            0.047,
            "Primary, derived and label-transfer-dependent sources are not independent validation. "
            "Literature-prior cells do not report held-out performance; inspect source "
            "families and dependencies in the table.",
            fontsize=7.7,
            ha="left",
            va="bottom",
            color=_MATRIX_MUTED,
        )
        fig.text(
            0.055,
            0.024,
            "Not assessed is not negative evidence. Cells are evidence records, not votes; "
            "source-family dependencies must be preserved.",
            fontsize=7.7,
            ha="left",
            va="bottom",
            color=_MATRIX_MUTED,
            weight="bold",
        )
        return _save_matrix_figure(fig, output_stem)


def _json_cell(value) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def write_source_state_evidence_table(
    profile: CellStateEvidenceMatrixData,
    path: Path,
) -> Path:
    """Write a lossless, renderer-independent TSV fallback."""

    source_by_id = {source.source_id: source for source in profile.sources}
    state_by_id = {state.state_id: state for state in profile.states}
    source_order = {
        source.source_id: index for index, source in enumerate(profile.sources)
    }
    record_order = {
        (record.state_id, record.source_id): index
        for index, record in enumerate(profile.records)
    }
    rows = []
    for record in sorted(
        profile.records,
        key=lambda item: (
            state_by_id[item.state_id].order,
            source_order[item.source_id],
        ),
    ):
        source = source_by_id[record.source_id]
        state = state_by_id[record.state_id]
        rows.append(
            {
                "object_version": profile.object_version,
                "schema_ref": profile.schema_ref,
                "profile_id": profile.profile_id,
                "producer_run_ref": profile.producer_run_ref,
                "primary_source_id": profile.primary_source_id,
                "profile_scientific_status": profile.scientific_status,
                "profile_review_state": profile.review_state,
                "profile_denominator": profile.denominator,
                "profile_denominator_unit": profile.denominator_unit,
                "profile_evidence_ids_json": _json_cell(profile.evidence_ids),
                "profile_limitations_json": _json_cell(profile.limitations),
                "profile_alt_text": profile.alt_text,
                "profile_long_description": profile.long_description,
                "source_order": source_order[source.source_id],
                "source_id": source.source_id,
                "source_family_id": source.source_family_id,
                "source_display_name": source.display_name,
                "source_short_name": source.short_name,
                "source_assay": source.assay,
                "source_scope": source.scope,
                "source_relationship": source.relationship.value,
                "source_availability": source.availability.value,
                "source_observation_unit": source.observation_unit,
                "source_n_observations": source.n_observations,
                "source_dependency_ids_json": _json_cell(
                    source.dependency_source_ids
                ),
                "source_evidence_ids_json": _json_cell(source.evidence_ids),
                "source_limitation": source.limitation,
                "state_order": state.order,
                "state_id": state.state_id,
                "state_display_name": state.display_name,
                "state_level": state.level,
                "state_row_group": state.row_group,
                "state_primary_n_observations": state.primary_n_observations,
                "state_review_state": state.review_state,
                "state_evidence_ids_json": _json_cell(state.evidence_ids),
                "state_review_notes_json": _json_cell(state.review_notes),
                "record_order": record_order[(record.state_id, record.source_id)],
                "assessment_state": record.assessment_state.value,
                "evidence_role": record.evidence_role.value,
                "evidence_state": record.evidence_state.value,
                "summary": record.summary,
                "reason_codes_json": _json_cell(record.reason_codes),
                "channels_json": _json_cell(
                    [
                        channel.model_dump(mode="json")
                        for channel in record.channels
                    ]
                ),
                "record_evidence_ids_json": _json_cell(record.evidence_ids),
            }
        )
    pd.DataFrame(rows).to_csv(path, sep="\t", index=False)
    return path


def _draw_source_header(axis, sources) -> None:
    axis.set_xlim(-0.5, len(sources) - 0.5)
    axis.set_ylim(0, 1)
    axis.axis("off")
    for x, source in enumerate(sources):
        relationship_color = _RELATIONSHIP_COLORS[source.relationship]
        dark = source.relationship is SourceRelationship.PRIMARY
        box = FancyBboxPatch(
            (x - 0.43, 0.13),
            0.86,
            0.55,
            boxstyle="round,pad=0.02,rounding_size=0.035",
            facecolor=relationship_color,
            edgecolor="none",
        )
        axis.add_patch(box)
        text_color = "white" if dark else _MATRIX_INK
        axis.text(
            x,
            0.56,
            source.short_name,
            ha="center",
            va="center",
            fontsize=8.4,
            weight="bold",
            color=text_color,
        )
        unit = source.observation_unit
        count = (
            f"{source.n_observations:,} {unit}"
            if source.n_observations is not None
            else unit
        )
        axis.text(
            x,
            0.34,
            count,
            ha="center",
            va="center",
            fontsize=6.8,
            color=text_color if dark else _MATRIX_MUTED,
        )
        axis.text(
            x,
            0.79,
            _RELATIONSHIP_LABELS[source.relationship],
            ha="center",
            va="center",
            fontsize=5.8,
            linespacing=1.05,
            weight="bold",
            color=_MATRIX_TEAL if dark else _MATRIX_MUTED,
        )
        axis.text(
            x,
            0.02,
            source.availability.value.replace("_", " "),
            ha="center",
            va="bottom",
            fontsize=6.5,
            color=_MATRIX_MUTED,
        )


def _draw_source_state_matrix(axis, states, sources, records) -> None:
    positions: list[float] = []
    groups: list[dict[str, float | str]] = []
    cursor = 0.0
    current_group = None
    for state in states:
        if state.row_group != current_group:
            if positions:
                cursor += 0.72
            groups.append(
                {
                    "name": state.row_group,
                    "header_y": cursor - 0.58,
                    "first_y": cursor,
                    "last_y": cursor,
                }
            )
            current_group = state.row_group
        positions.append(cursor)
        groups[-1]["last_y"] = cursor
        cursor += 1.0

    axis.set_xlim(-0.5, len(sources) - 0.5)
    axis.set_ylim(cursor - 0.45, -0.95)
    axis.set_xticks([])
    axis.set_yticks(
        positions,
        [
            ("   " if state.level == "L2" else "") + state.display_name
            for state in states
        ],
    )
    axis.tick_params(axis="y", length=0, pad=7)
    axis.spines[:].set_visible(False)

    relationship_tints = {
        SourceRelationship.PRIMARY: "#F1F7F6",
        SourceRelationship.DERIVED_CONTAINS_PRIMARY: "#F5F7F7",
        SourceRelationship.DEPENDENT_LABEL_TRANSFER: "#F1F7F6",
        SourceRelationship.INDEPENDENT_EXTERNAL: "#F8F6FA",
    }
    for x, source in enumerate(sources):
        axis.axvspan(
            x - 0.47,
            x + 0.47,
            color=relationship_tints[source.relationship],
            zorder=0,
        )

    group_colors = ["#547A90", "#6C63A8", "#8C7465", "#C18432"]
    for group_index, group in enumerate(groups):
        color = group_colors[group_index % len(group_colors)]
        header_y = float(group["header_y"])
        first_y = float(group["first_y"])
        last_y = float(group["last_y"])
        axis.axhspan(
            header_y - 0.24,
            header_y + 0.20,
            color="#FAFAF8",
            zorder=1,
        )
        axis.plot(
            [-0.59, -0.59],
            [first_y - 0.34, last_y + 0.34],
            color=color,
            lw=3.2,
            solid_capstyle="butt",
            clip_on=False,
        )
        axis.text(
            -0.46,
            header_y,
            str(group["name"]).upper(),
            ha="left",
            va="center",
            fontsize=6.5,
            weight="bold",
            color=color,
            zorder=4,
        )

    for y, state in zip(positions, states, strict=True):
        for x, source in enumerate(sources):
            _draw_matrix_mark(
                axis,
                x,
                y,
                records[(state.state_id, source.source_id)],
            )
        axis.axhline(y - 0.5, color="#E8ECEE", lw=0.42, zorder=1)
        axis.axhline(y + 0.5, color="#E8ECEE", lw=0.42, zorder=1)

    for x in np.arange(-0.5, len(sources), 1):
        axis.axvline(x, color=_MATRIX_GRID, lw=0.55, zorder=1)


def _draw_matrix_mark(
    axis,
    x: float,
    y: float,
    record: CellStateEvidenceMatrixRecord,
    *,
    size: float = 180,
    label_size: float = 6.8,
) -> None:
    state = record.assessment_state
    if state is MatrixAssessmentState.SOURCE_ANCHORED:
        axis.scatter(
            [x], [y], s=size, marker="o", color=_MATRIX_TEAL,
            edgecolors="white", linewidths=0.8, zorder=3,
        )
        axis.text(
            x, y, "A", ha="center", va="center", color="white",
            fontsize=label_size, weight="bold", zorder=4,
        )
    elif state is MatrixAssessmentState.SUPPORT:
        color = (
            _MATRIX_TEAL
            if record.evidence_state is EvidenceState.MEASURED
            else _MATRIX_TEAL_LIGHT
        )
        axis.scatter(
            [x], [y], s=size, marker="s", color=color,
            edgecolors=_MATRIX_TEAL, linewidths=0.9, zorder=3,
        )
        axis.text(
            x, y, "S", ha="center", va="center", color=_MATRIX_INK,
            fontsize=label_size, weight="bold", zorder=4,
        )
    elif state is MatrixAssessmentState.OPPOSITION:
        axis.text(
            x, y, "×", ha="center", va="center", color=_MATRIX_VERMILION,
            fontsize=label_size * 1.8, weight="bold", zorder=4,
        )
    elif state is MatrixAssessmentState.CONFLICT:
        axis.scatter(
            [x], [y], s=size, marker="D", color="#E6B96B",
            edgecolors=_MATRIX_AMBER, linewidths=0.9, zorder=3,
        )
        label = "A" if record.evidence_state is EvidenceState.ALERT else "?"
        axis.text(
            x, y, label, ha="center", va="center", color=_MATRIX_INK,
            fontsize=label_size, weight="bold", zorder=4,
        )
    elif record.evidence_state is EvidenceState.PRIOR_ONLY:
        axis.scatter(
            [x], [y], s=size * 0.82, marker="o", facecolors="white",
            edgecolors=_MATRIX_PURPLE, linewidths=1.1, zorder=3,
        )
        axis.text(
            x, y, "P", ha="center", va="center", color=_MATRIX_PURPLE,
            fontsize=label_size, weight="bold", zorder=4,
        )
    elif record.evidence_state is EvidenceState.MISSING:
        axis.scatter(
            [x], [y], s=size * 0.72, marker="o", facecolors="white",
            edgecolors=_MATRIX_UNAVAILABLE, linewidths=1.0, zorder=3,
        )
        axis.text(
            x, y, "M", ha="center", va="center", color=_MATRIX_MUTED,
            fontsize=label_size, weight="bold", zorder=4,
        )
    elif record.evidence_state is EvidenceState.UNKNOWN:
        axis.scatter(
            [x], [y], s=size * 0.72, marker="D", facecolors="white",
            edgecolors=_MATRIX_UNAVAILABLE, linewidths=1.0, zorder=3,
        )
        axis.text(
            x, y, "?", ha="center", va="center", color=_MATRIX_MUTED,
            fontsize=label_size, weight="bold", zorder=4,
        )
    else:
        axis.scatter(
            [x], [y], s=size * 0.55, marker="_",
            color=_MATRIX_UNAVAILABLE, linewidths=1.6, zorder=3,
        )


def _draw_matrix_summary(axis, profile, sources, records) -> None:
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.axis("off")
    primary = profile.primary_source_id
    primary_count = sum(
        record.assessment_state is MatrixAssessmentState.SOURCE_ANCHORED
        for record in records.values()
        if record.source_id == primary
    )
    spatial_states = {
        record.state_id
        for record in records.values()
        if record.evidence_role is EvidenceRole.DEPENDENT_SPATIAL_CONCORDANCE
        and record.assessment_state is MatrixAssessmentState.SUPPORT
    }
    independent_states = _independent_assessed_state_ids(profile)

    axis.text(0.0, 0.96, "Current coverage", fontsize=10.5, weight="bold")
    _summary_number(
        axis, 0.88, primary_count, profile.denominator,
        "states present in primary\nannotation", _MATRIX_TEAL,
    )
    _summary_number(
        axis, 0.75, len(spatial_states), profile.denominator,
        "states with dependent label-\nprogram lookup", "#4F9892",
    )
    _summary_number(
        axis, 0.62, len(independent_states), profile.denominator,
        "states assessed in independent\nheld-out data", _MATRIX_PURPLE,
    )

    axis.plot([0, 1], [0.53, 0.53], color=_MATRIX_GRID, lw=0.8)
    axis.text(0.0, 0.49, "Cell meaning", fontsize=9.4, weight="bold")
    legend = [
        (MatrixAssessmentState.SOURCE_ANCHORED, None, EvidenceState.MEASURED, "Primary annotation present"),
        (MatrixAssessmentState.SUPPORT, None, EvidenceState.MEASURED, "Support · measured"),
        (MatrixAssessmentState.SUPPORT, None, EvidenceState.INFERRED, "Support · inferred"),
        (MatrixAssessmentState.NOT_ASSESSED, "prior", EvidenceState.PRIOR_ONLY, "Literature prior only"),
        (MatrixAssessmentState.CONFLICT, None, EvidenceState.ALERT, "Conflict · alert"),
        (MatrixAssessmentState.CONFLICT, None, EvidenceState.UNKNOWN, "Conflict · unknown"),
        (MatrixAssessmentState.OPPOSITION, None, EvidenceState.NEGATIVE, "Opposition · negative"),
        (MatrixAssessmentState.NOT_ASSESSED, None, EvidenceState.MISSING, "Not assessed · missing"),
        (MatrixAssessmentState.NOT_ASSESSED, None, EvidenceState.UNKNOWN, "Not assessed · unknown"),
        (MatrixAssessmentState.NOT_ASSESSED, None, EvidenceState.UNAVAILABLE, "Not assessed · unavailable"),
    ]
    for index, (state, special, evidence, label) in enumerate(legend):
        y = 0.43 - index * 0.037
        role = (
            EvidenceRole.LITERATURE_PRIOR
            if special == "prior"
            else EvidenceRole.DERIVED_CONTEXT
        )
        dummy = next(iter(records.values())).model_copy(
            update={
                "assessment_state": state,
                "evidence_role": role,
                "evidence_state": evidence,
            }
        )
        _draw_matrix_mark(axis, 0.06, y, dummy, size=62, label_size=5.4)
        axis.text(0.14, y, label, va="center", fontsize=6.8, color=_MATRIX_INK)

    axis.add_patch(
        FancyBboxPatch(
            (0.0, 0.002),
            0.98,
            0.062,
            boxstyle="round,pad=0.012,rounding_size=0.02",
            facecolor="#F1F3F4",
            edgecolor="none",
        )
    )
    takeaway = (
        "Independent assessments are present; inspect support,\n"
        "opposition and conflict state by state."
        if independent_states
        else "No independent held-out assessment is recorded;\n"
        "absence of conflict cannot be inferred."
    )
    axis.text(
        0.025,
        0.033,
        takeaway,
        va="center",
        fontsize=7.1,
        color=_MATRIX_MUTED,
        wrap=True,
    )


def _summary_number(axis, y: float, numerator: int, denominator: int, label: str, color: str) -> None:
    axis.text(0.0, y, f"{numerator}/{denominator}", fontsize=18, weight="bold", color=color, va="top")
    axis.text(0.30, y - 0.003, label, fontsize=7.6, color=_MATRIX_INK, va="top", wrap=True)


def _save_matrix_figure(fig, output_stem: Path) -> tuple[Path, Path, Path]:
    svg = output_stem.with_suffix(".svg")
    png = output_stem.with_suffix(".png")
    pdf = output_stem.with_suffix(".pdf")
    fig.savefig(
        svg,
        bbox_inches="tight",
        facecolor="#FAFAF8",
        metadata={"Creator": "BRIDGE", "Date": None},
    )
    fig.savefig(
        png,
        dpi=300,
        bbox_inches="tight",
        facecolor="#FAFAF8",
        metadata={"Software": "BRIDGE"},
    )
    fig.savefig(
        pdf,
        dpi=300,
        bbox_inches="tight",
        facecolor="#FAFAF8",
        metadata={
            "Creator": "BRIDGE",
            "Producer": "BRIDGE",
            "CreationDate": None,
            "ModDate": None,
        },
    )
    plt.close(fig)
    return svg, png, pdf

_REFERENCE_RC = {
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 8.5,
    "axes.labelcolor": "#20343F",
    "text.color": "#20343F",
    "xtick.color": "#5E707A",
    "ytick.color": "#20343F",
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
}
_REFERENCE_BACKGROUND = "#FCFBF8"
_REFERENCE_INK = "#20343F"
_REFERENCE_MUTED = "#667982"
_REFERENCE_GRID = "#DCE4E3"
_REFERENCE_CMAP = LinearSegmentedColormap.from_list(
    "bridge_reference_correspondence",
    ["#F6F4EF", "#DCEDE8", "#A8D9D0", "#62B9B5", "#187A7C"],
)
_GROUP_COLORS = (
    "#75C7C1",
    "#F0A39E",
    "#E9C66A",
    "#9AB9E8",
    "#B69ED7",
    "#8BC6A7",
    "#DEA4C6",
    "#91BDD9",
    "#D9AE78",
    "#AAB8B4",
)


def render_hierarchical_composition(
    profile: HierarchicalCellStateCompositionDataV1,
    output_stem: Path,
) -> tuple[Path, Path, Path]:
    """Render a fixed-order group-by-reference evidence matrix."""

    rows, states, matrix, conflict, unavailable = _reference_matrix(profile)
    n_rows, n_states = matrix.shape
    width = max(12.8, 7.6 + 0.47 * n_states)
    height = max(6.3, 3.5 + 0.56 * n_rows)
    y = np.arange(n_rows)

    with plt.rc_context(_REFERENCE_RC):
        fig = plt.figure(figsize=(width, height), facecolor=_REFERENCE_BACKGROUND)
        grid = fig.add_gridspec(
            1,
            4,
            left=0.045,
            right=0.975,
            bottom=0.19,
            top=0.77,
            width_ratios=(2.7, 2.3, max(5.2, 0.52 * n_states), 3.75),
            wspace=0.04,
        )
        label_axis = fig.add_subplot(grid[0, 0])
        share_axis = fig.add_subplot(grid[0, 1], sharey=label_axis)
        matrix_axis = fig.add_subplot(grid[0, 2], sharey=label_axis)
        summary_axis = fig.add_subplot(grid[0, 3], sharey=label_axis)

        fig.text(
            0.045,
            0.955,
            "Reference-state correspondence across product groups",
            ha="left",
            va="top",
            fontsize=17,
            weight="bold",
            color="#172B36",
        )
        fig.text(
            0.045,
            0.912,
            _grouping_subtitle(profile),
            ha="left",
            va="top",
            fontsize=9.3,
            color=_REFERENCE_MUTED,
        )
        fig.text(
            0.045,
            0.875,
            (
                f"n = {profile.whole_product_denominator:,} "
                f"{profile.observation_unit} · candidate reference evidence · "
                "values are correspondence fractions, not identity probabilities"
            ),
            ha="left",
            va="top",
            fontsize=8.7,
            color=_REFERENCE_MUTED,
        )

        _draw_group_labels(label_axis, rows, y)
        _draw_group_shares(share_axis, rows, y)
        image = _draw_reference_cells(matrix_axis, matrix, states, y)
        _draw_reference_summary(
            summary_axis,
            rows,
            states,
            matrix,
            conflict,
            unavailable,
            y,
        )

        colorbar = fig.colorbar(
            image,
            ax=matrix_axis,
            orientation="horizontal",
            fraction=0.05,
            pad=0.30,
            aspect=28,
        )
        colorbar.set_label("Fraction of each product group", fontsize=7.7)
        colorbar.set_ticks([0, 0.25, 0.5, 0.75, 1])
        colorbar.set_ticklabels(["0", "25%", "50%", "75%", "100%"])
        colorbar.ax.tick_params(labelsize=7, length=2)
        colorbar.outline.set_linewidth(0.5)
        colorbar.outline.set_edgecolor(_REFERENCE_GRID)

        fig.text(
            0.045,
            0.075,
            (
                "A cell contributes to a broad reference state only when its "
                "candidate set resolves to one state. Multiple candidates and "
                "unavailable correspondence remain separate."
            ),
            ha="left",
            va="bottom",
            fontsize=7.6,
            color=_REFERENCE_MUTED,
        )
        fig.text(
            0.975,
            0.075,
            "Unknown / OOD and detail beyond the reviewed vocabulary: not assessed",
            ha="right",
            va="bottom",
            fontsize=7.6,
            weight="bold",
            color=_REFERENCE_MUTED,
        )
        return _save_matrix_figure(fig, output_stem)


def write_hierarchical_composition_table(
    profile: HierarchicalCellStateCompositionDataV1,
    path: Path,
) -> Path:
    """Write whole-product and group-level evidence in one long-form table."""

    base = {
        "object_version": profile.object_version,
        "schema_ref": profile.schema_ref,
        "profile_id": profile.profile_id,
        "producer_run_ref": profile.producer_run_ref,
        "scientific_status": profile.scientific_status,
        "observation_unit": profile.observation_unit,
        "whole_product_denominator": profile.whole_product_denominator,
        "denominator_scope": profile.denominator_scope,
        "input_view_ref": profile.input_view_ref,
        "input_view_sha256": profile.input_view_sha256,
        "annotation_vocabulary_ref": profile.annotation_vocabulary_ref,
        "annotation_vocabulary_sha256": profile.annotation_vocabulary_sha256,
        "grouping_state": profile.grouping.state,
        "grouping_source": profile.grouping.source,
        "grouping_key": profile.grouping.grouping_key,
        "grouping_hash": profile.grouping.grouping_hash,
        "grouping_reason_codes_json": _json_cell(profile.grouping.reason_codes),
    }
    display_names = {
        record.state_id: record.display_name
        for record in profile.composition_records
        if record.state_id is not None
    }
    rows: list[dict[str, object]] = []
    for record in sorted(profile.composition_records, key=lambda item: item.order):
        rows.append(
            {
                **base,
                "scope": "whole_product",
                "group_id": None,
                "group_display_name": None,
                "record_id": record.record_id,
                "partition_id": record.partition_id,
                "state_id": record.state_id,
                "display_name": record.display_name,
                "reference_level": record.level,
                "parent_state_id": record.parent_state_id,
                "resolution_state": record.resolution_state,
                "evidence_state": record.evidence_state.value,
                "applicability": record.applicability,
                "missingness": record.missingness,
                "count": record.count,
                "group_denominator": None,
                "group_fraction": None,
                "record_whole_product_denominator": record.whole_product_denominator,
                "whole_product_fraction": record.whole_product_fraction,
                "parent_denominator": record.parent_denominator,
                "parent_fraction": record.parent_fraction,
                "supporting_source_ids_json": _json_cell(
                    record.supporting_source_ids
                ),
                "prediction_sets_json": _json_cell(
                    [item.model_dump(mode="json") for item in record.prediction_sets]
                ),
                "evidence_ids_json": _json_cell(record.evidence_ids),
                "reason_codes_json": _json_cell(record.reason_codes),
            }
        )
    groups = {group.group_id: group for group in profile.groups}
    for record in profile.group_records:
        group = groups[record.group_id]
        rows.append(
            {
                **base,
                "scope": "product_group",
                "group_id": record.group_id,
                "group_display_name": group.display_name,
                "record_id": record.record_id,
                "partition_id": "root" if record.level == "L1" else record.parent_state_id,
                "state_id": record.state_id,
                "display_name": (
                    display_names.get(record.state_id, "")
                    if record.state_id is not None
                    else record.resolution_state.replace("_", " ")
                ),
                "reference_level": record.level,
                "parent_state_id": record.parent_state_id,
                "resolution_state": record.resolution_state,
                "evidence_state": record.evidence_state.value,
                "applicability": record.applicability,
                "missingness": record.missingness,
                "count": record.count,
                "group_denominator": record.group_denominator,
                "group_fraction": record.group_fraction,
                "record_whole_product_denominator": record.whole_product_denominator,
                "whole_product_fraction": record.whole_product_fraction,
                "parent_denominator": None,
                "parent_fraction": None,
                "supporting_source_ids_json": "[]",
                "prediction_sets_json": _json_cell(
                    [item.model_dump(mode="json") for item in record.prediction_sets]
                ),
                "evidence_ids_json": _json_cell(record.evidence_ids),
                "reason_codes_json": _json_cell(record.reason_codes),
            }
        )
    pd.DataFrame(rows).to_csv(path, sep="\t", index=False)
    return path


def _reference_matrix(profile: HierarchicalCellStateCompositionDataV1):
    states = [
        record
        for record in sorted(profile.composition_records, key=lambda item: item.order)
        if record.record_kind == "state" and record.level == "L1"
    ]
    if profile.groups:
        records = {
            (record.group_id, record.state_id): record
            for record in profile.group_records
            if record.level == "L1" and record.state_id is not None
        }
        statuses = {
            (record.group_id, record.resolution_state): record
            for record in profile.group_records
            if record.level == "L1" and record.state_id is None
        }
        matrix = np.asarray(
            [
                [
                    records[(group.group_id, state.state_id)].group_fraction
                    for state in states
                ]
                for group in profile.groups
            ],
            dtype=float,
        )
        conflict = np.asarray(
            [
                statuses[(group.group_id, "source_conflict")].group_fraction
                for group in profile.groups
            ],
            dtype=float,
        )
        unavailable = np.asarray(
            [
                statuses[(group.group_id, "unavailable")].group_fraction
                for group in profile.groups
            ],
            dtype=float,
        )
        return list(profile.groups), states, matrix, conflict, unavailable

    whole = {
        "display_name": "Whole product",
        "count": profile.whole_product_denominator,
        "whole_product_fraction": 1.0,
    }
    matrix = np.asarray(
        [[state.whole_product_fraction or 0.0 for state in states]],
        dtype=float,
    )
    status = {
        record.resolution_state: record.whole_product_fraction or 0.0
        for record in profile.composition_records
        if record.record_kind == "resolution" and record.partition_id == "root"
    }
    return (
        [whole],
        states,
        matrix,
        np.asarray([status.get("source_conflict", 0.0)]),
        np.asarray([status.get("unavailable", 0.0)]),
    )


def _draw_group_labels(axis, rows, y: np.ndarray) -> None:
    axis.set_xlim(0, 1)
    axis.set_ylim(len(rows) - 0.5, -0.5)
    axis.axis("off")
    axis.set_title(
        "Submitted or exploratory group",
        loc="left",
        pad=12,
        fontsize=8,
        weight="bold",
        color=_REFERENCE_MUTED,
    )
    for index, (row, position) in enumerate(zip(rows, y, strict=True)):
        display_name = (
            row["display_name"] if isinstance(row, dict) else row.display_name
        )
        count = row["count"] if isinstance(row, dict) else row.count
        axis.add_patch(
            Rectangle(
                (0.0, position - 0.30),
                0.025,
                0.60,
                color=_GROUP_COLORS[index % len(_GROUP_COLORS)],
                lw=0,
            )
        )
        axis.text(
            0.06,
            position - 0.08,
            str(display_name),
            ha="left",
            va="center",
            fontsize=8.3,
            weight="bold",
            color=_REFERENCE_INK,
        )
        axis.text(
            0.06,
            position + 0.20,
            f"n = {int(count):,}",
            ha="left",
            va="center",
            fontsize=7.1,
            color=_REFERENCE_MUTED,
        )


def _draw_group_shares(axis, rows, y: np.ndarray) -> None:
    fractions = np.asarray(
        [
            (
                row["whole_product_fraction"]
                if isinstance(row, dict)
                else row.whole_product_fraction
            )
            for row in rows
        ],
        dtype=float,
    )
    colors = [_GROUP_COLORS[index % len(_GROUP_COLORS)] for index in range(len(rows))]
    axis.barh(y, 100 * fractions, height=0.44, color=colors, edgecolor="white", lw=0.4)
    axis.set_xlim(0, 100)
    axis.set_ylim(len(rows) - 0.5, -0.5)
    axis.set_yticks([])
    axis.set_xticks([0, 25, 50, 75, 100])
    axis.set_xticklabels(["0", "25", "50", "75", "100"], fontsize=6.8)
    axis.set_xlabel("Share of product (%)", fontsize=7.5, labelpad=7)
    axis.set_title(
        "Whole-product share",
        pad=12,
        fontsize=8,
        weight="bold",
        color=_REFERENCE_MUTED,
    )
    axis.grid(axis="x", color=_REFERENCE_GRID, lw=0.55, zorder=0)
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.spines["bottom"].set_color(_REFERENCE_GRID)
    for position, fraction in zip(y, fractions, strict=True):
        axis.text(
            min(100 * fraction + 1.2, 91),
            position,
            f"{100 * fraction:.1f}%",
            ha="left",
            va="center",
            fontsize=7,
            color=_REFERENCE_INK,
        )


def _draw_reference_cells(axis, matrix, states, y):
    image = axis.imshow(
        matrix,
        aspect="auto",
        interpolation="nearest",
        cmap=_REFERENCE_CMAP,
        vmin=0,
        vmax=1,
    )
    axis.set_ylim(len(y) - 0.5, -0.5)
    axis.set_yticks([])
    axis.set_xticks(
        np.arange(len(states)),
        [_display_state(record.display_name) for record in states],
        rotation=52,
        ha="left",
        rotation_mode="anchor",
        fontsize=7,
    )
    axis.xaxis.tick_top()
    axis.tick_params(axis="x", pad=5, length=0)
    axis.set_title(
        "Broad reference states",
        pad=12,
        fontsize=8,
        weight="bold",
        color=_REFERENCE_MUTED,
    )
    axis.set_xticks(np.arange(-0.5, len(states), 1), minor=True)
    axis.set_yticks(np.arange(-0.5, len(y), 1), minor=True)
    axis.grid(which="minor", color=_REFERENCE_BACKGROUND, linewidth=1.0)
    axis.tick_params(which="minor", bottom=False, left=False)
    for row_index, values in enumerate(matrix):
        top = _top_indices(values)
        for rank, column_index in enumerate(top, start=1):
            axis.add_patch(
                Rectangle(
                    (column_index - 0.47, row_index - 0.47),
                    0.94,
                    0.94,
                    fill=False,
                    edgecolor="#18343F" if rank == 1 else "#6C7C84",
                    linewidth=1.0 if rank == 1 else 0.65,
                )
            )
            axis.text(
                column_index,
                row_index,
                str(rank),
                ha="center",
                va="center",
                fontsize=6.8,
                weight="bold",
                color="#132B35",
            )
    for spine in axis.spines.values():
        spine.set_visible(False)
    return image


def _draw_reference_summary(
    axis,
    rows,
    states,
    matrix,
    conflict,
    unavailable,
    y,
) -> None:
    axis.set_xlim(0, 1)
    axis.set_ylim(len(rows) - 0.5, -0.5)
    axis.axis("off")
    axis.set_title(
        "Leading correspondence and assessment",
        loc="left",
        pad=12,
        fontsize=8,
        weight="bold",
        color=_REFERENCE_MUTED,
    )
    for row_index, (position, values) in enumerate(zip(y, matrix, strict=True)):
        top = _top_indices(values)
        if top:
            first = top[0]
            first_text = (
                f"1  {_display_state(states[first].display_name)}  "
                f"{100 * values[first]:.1f}%"
            )
            if len(top) > 1:
                second = top[1]
                separation = values[first] - values[second]
                second_text = (
                    f"2  {_display_state(states[second].display_name)}  "
                    f"{100 * values[second]:.1f}%  ·  Δ {100 * separation:.1f} pp"
                )
            else:
                second_text = "2  —"
        else:
            first_text = "No single broad state resolved"
            second_text = ""
        resolved = float(values.sum())
        axis.text(
            0,
            position - 0.18,
            first_text,
            ha="left",
            va="center",
            fontsize=7.3,
            weight="bold",
            color=_REFERENCE_INK,
        )
        axis.text(
            0,
            position + 0.05,
            second_text,
            ha="left",
            va="center",
            fontsize=6.9,
            color=_REFERENCE_MUTED,
        )
        axis.text(
            0,
            position + 0.27,
            (
                f"resolved {100 * resolved:.1f}% · multiple "
                f"{100 * conflict[row_index]:.1f}% · unavailable "
                f"{100 * unavailable[row_index]:.1f}%"
            ),
            ha="left",
            va="center",
            fontsize=6.5,
            color=_REFERENCE_MUTED,
        )


def _top_indices(values: np.ndarray) -> list[int]:
    positive = [int(index) for index in np.flatnonzero(values > 0)]
    return sorted(positive, key=lambda index: (-float(values[index]), index))[:2]


def _grouping_subtitle(profile: HierarchicalCellStateCompositionDataV1) -> str:
    if profile.grouping.source == "user_label":
        return "User-provided group labels are preserved; reference evidence does not overwrite them."
    if profile.grouping.source == "exploratory_leiden":
        return "Exploratory expression groups organize the view; clustering does not assign identity."
    return "No reliable grouping was available; the complete post-QC product is shown as one row."


def _display_state(value: str) -> str:
    if value.startswith(("RG_", "Nb_", "IPC_")):
        return value
    return value.replace("_", " ")
