from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import to_rgb
from matplotlib.patches import Rectangle

from bridge.tool_packages.p0_02_cell_state.hierarchical_composition import (
    HierarchicalCellStateCompositionDataV1,
)
from bridge.tool_packages.p0_02_cell_state.visualization_data import (
    CellStateEvidenceMatrixData,
    CellStateEvidenceMatrixRecord,
    CellStateEvidenceMatrixRecordV2,
    HierarchicalCellStateVisualizationDataV1,
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
    pivot = source.pivot(index="label", columns="source_id", values="fraction").fillna(
        0
    )
    fig, axis = plt.subplots(
        figsize=(8.8, max(3.8, 0.28 * len(pivot))), constrained_layout=True
    )
    if pivot.empty:
        axis.text(0.5, 0.5, "Unavailable", ha="center", va="center")
    else:
        pivot.plot.barh(
            ax=axis, width=0.78, color=["#2B7A78", "#E59F45", "#6C63A8", "#5B8E7D"]
        )
        axis.set_xlabel(f"{label_level} shadow top-label fraction")
        axis.set_ylabel("")
        axis.legend(title="Reference source", frameon=False)
    axis.spines[["top", "right"]].set_visible(False)
    return _save(fig, output_stem)


def render_reference_support(
    support: pd.DataFrame, output_stem: Path
) -> tuple[Path, Path]:
    summary = support.groupby(["source_id", "label"], observed=True)[
        "spearman_support"
    ].median()
    pivot = summary.unstack("label")
    fig, axis = plt.subplots(
        figsize=(max(7.5, 0.42 * len(pivot.columns)), 3.2), constrained_layout=True
    )
    if pivot.empty:
        axis.text(0.5, 0.5, "Unavailable", ha="center", va="center")
    else:
        image = axis.imshow(
            pivot.to_numpy(), aspect="auto", cmap="RdBu_r", vmin=-1, vmax=1
        )
        axis.set_xticks(
            np.arange(len(pivot.columns)),
            [_short(item) for item in pivot.columns],
            rotation=45,
            ha="right",
        )
        axis.set_yticks(np.arange(len(pivot.index)), pivot.index)
        axis.set_xlabel("L1 state")
        fig.colorbar(image, ax=axis, label="Median Spearman support", shrink=0.8)
    return _save(fig, output_stem)


def render_marker_evidence(
    marker: pd.DataFrame,
    evidence: pd.DataFrame,
    output_stem: Path,
) -> tuple[Path, Path]:
    joined = marker.merge(
        evidence[["observation_id", "consensus_label"]], on="observation_id", how="left"
    )
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
        axis.set_xticks(
            np.arange(len(pivot.columns)),
            [_short(item) for item in pivot.columns],
            rotation=45,
            ha="right",
        )
        axis.set_yticks(
            np.arange(len(pivot.index)), [_short(item) for item in pivot.index]
        )
        axis.set_xlabel("Reference consensus support")
        fig.colorbar(
            image, ax=axis, label="Median positive-marker expression", shrink=0.8
        )
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
    axis.bar(
        [item.replace("_", " ") for item in counts.index],
        counts.values,
        color=[colors.get(item, "#5B8E7D") for item in counts.index],
    )
    axis.set_ylabel("Observations")
    axis.tick_params(axis="x", rotation=20)
    axis.spines[["top", "right"]].set_visible(False)
    return _save(fig, output_stem)


def _save(fig, output_stem: Path) -> tuple[Path, Path]:
    svg = output_stem.with_suffix(".svg")
    png = output_stem.with_suffix(".png")
    with plt.rc_context({"svg.hashsalt": "BRIDGE-P0-02"}):
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


_FIGURE_RC = {
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
    "font.size": 8.0,
    "axes.labelcolor": "#20242B",
    "axes.titlecolor": "#20242B",
    "text.color": "#20242B",
    "xtick.color": "#626A73",
    "ytick.color": "#20242B",
    "axes.linewidth": 0.65,
    "patch.linewidth": 0.65,
    "lines.linewidth": 1.2,
    "xtick.major.size": 2.5,
    "ytick.major.size": 2.5,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "legend.frameon": False,
    "axes.grid": False,
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
}
_INK = "#20242B"
_MUTED = "#69717B"
_HAIRLINE = "#E8EBEF"
_UNKNOWN = "#C8CDD4"
_CONFLICT = "#B64B54"
_EVIDENCE_BLUE = "#4A7596"
_EVIDENCE_TEAL = "#5F9FA4"
_EVIDENCE_AMBER = "#C6A04F"
_EVIDENCE_PURPLE = "#9A82BB"
_FAMILY_COLORS = {
    "radial_glia": "#65A68F",
    "neuroblast": "#DE866B",
    "neuron": "#5B8FCB",
    "glial": "#9A82BB",
    "vascular": "#C6A04F",
    "immune": "#C87598",
    "other": "#7C8798",
}
_RELATIONSHIP_COLORS = {
    SourceRelationship.PRIMARY: "#4A7596",
    SourceRelationship.DERIVED_CONTAINS_PRIMARY: "#A9C3D4",
    SourceRelationship.DEPENDENT_LABEL_TRANSFER: "#94C6BD",
    SourceRelationship.INDEPENDENT_EXTERNAL: "#B7A8CE",
}
_RELATIONSHIP_LABELS = {
    SourceRelationship.PRIMARY: "primary",
    SourceRelationship.DERIVED_CONTAINS_PRIMARY: "contains primary",
    SourceRelationship.DEPENDENT_LABEL_TRANSFER: "label transfer",
    SourceRelationship.INDEPENDENT_EXTERNAL: "independent",
}


def render_source_state_evidence_matrix(
    profile: CellStateEvidenceMatrixData,
    output_stem: Path,
) -> tuple[Path, Path, Path]:
    """Render a compact audit of source lineage and state-level assessment."""

    states = _ordered_evidence_states(profile.states)
    sources = list(profile.sources)
    records = {
        (record.state_id, record.source_id): record for record in profile.records
    }
    positions = _evidence_row_positions(states)
    independent = _independent_assessed_state_ids(profile)
    height = max(7.0, 2.05 + 0.235 * len(states))

    with plt.rc_context(_FIGURE_RC):
        fig = plt.figure(figsize=(7.2, height), facecolor="white")
        label_axis = fig.add_axes([0.035, 0.145, 0.255, 0.675])
        matrix_axis = fig.add_axes([0.300, 0.145, 0.365, 0.675])
        header_axis = fig.add_axes([0.300, 0.825, 0.365, 0.090])
        count_axis = fig.add_axes([0.690, 0.145, 0.090, 0.675])
        independent_axis = fig.add_axes([0.790, 0.145, 0.105, 0.675])
        review_axis = fig.add_axes([0.905, 0.145, 0.080, 0.675])
        key_axis = fig.add_axes([0.035, 0.068, 0.950, 0.065])

        fig.text(
            0.035,
            0.974,
            "Cell-state definitions across registered reference sources",
            fontsize=10.5,
            weight="bold",
            ha="left",
            va="top",
        )
        fig.text(
            0.035,
            0.946,
            (
                "Label occurrence, dependent concordance and independent assessment "
                "are shown separately; this is not product-specific support."
            ),
            fontsize=7.4,
            color=_MUTED,
            ha="left",
            va="top",
        )
        fig.text(
            0.035,
            0.921,
            (
                "Only the current annotation source contains state-level records; "
                "no independent state assessment has yet been run."
                if not independent
                else "Independent state-level assessments are shown where available."
            ),
            fontsize=7.4,
            color=_CONFLICT if not independent else _EVIDENCE_TEAL,
            weight="bold",
            ha="left",
            va="top",
        )

        _draw_source_header(header_axis, sources)
        _draw_evidence_state_labels(label_axis, states, positions)
        _draw_source_state_matrix(matrix_axis, states, sources, records, positions)
        _draw_evidence_side_columns(
            count_axis,
            independent_axis,
            review_axis,
            states,
            positions,
            independent,
        )
        _draw_evidence_key(key_axis)

        fig.text(
            0.035,
            0.036,
            (
                "The current label source, derived context and spatial label transfer "
                "are not independent validation. Not assessed is not negative evidence. "
                "* Provisional internal name: Glioblast."
            ),
            fontsize=6.5,
            color=_MUTED,
            ha="left",
            va="bottom",
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
        presentation = (
            {
                "record_id": record.record_id,
                "record_scientific_status": record.scientific_status,
                "record_applicability": record.applicability,
                "record_missingness": record.missingness,
            }
            if isinstance(record, CellStateEvidenceMatrixRecordV2)
            else {}
        )
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
                "source_dependency_ids_json": _json_cell(source.dependency_source_ids),
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
                **presentation,
                "assessment_state": record.assessment_state.value,
                "evidence_role": record.evidence_role.value,
                "evidence_state": record.evidence_state.value,
                "summary": record.summary,
                "reason_codes_json": _json_cell(record.reason_codes),
                "channels_json": _json_cell(
                    [channel.model_dump(mode="json") for channel in record.channels]
                ),
                "record_evidence_ids_json": _json_cell(record.evidence_ids),
            }
        )
    pd.DataFrame(rows).to_csv(path, sep="\t", index=False)
    return path


def _ordered_evidence_states(states):
    ordered = sorted(states, key=lambda state: state.order)
    broad = [state for state in ordered if state.level == "L1"]
    detailed = [state for state in ordered if state.level == "L2"]
    result = []
    used: set[str] = set()
    for state in broad:
        result.append(state)
        for child in detailed:
            if _parent_state_id(child.state_id) == state.state_id:
                result.append(child)
                used.add(child.state_id)
    result.extend(state for state in detailed if state.state_id not in used)
    return result


def _parent_state_id(state_id: str) -> str | None:
    if state_id.startswith("L2:RG_"):
        return "L1:Radial_Glia"
    if state_id.startswith(("L2:Nb_", "L2:IPC_")):
        return "L1:Neuroblast"
    return None


def _evidence_group(state) -> str:
    if state.level == "L2":
        return "Progenitor and glial states"
    return state.row_group


def _evidence_row_positions(states) -> list[float]:
    positions: list[float] = []
    cursor = 0.0
    previous_group = None
    for state in states:
        group = _evidence_group(state)
        if previous_group is not None and group != previous_group:
            cursor += 0.55
        positions.append(cursor)
        cursor += 1.0
        previous_group = group
    return positions


def _draw_source_header(axis, sources) -> None:
    axis.set_xlim(-0.5, len(sources) - 0.5)
    axis.set_ylim(0, 1)
    axis.axis("off")
    for x, source in enumerate(sources):
        axis.add_patch(
            Rectangle(
                (x - 0.39, 0.04),
                0.78,
                0.075,
                facecolor=_RELATIONSHIP_COLORS[source.relationship],
                edgecolor="none",
            )
        )
        axis.text(
            x,
            0.78,
            _two_line_label(source.short_name),
            ha="center",
            va="center",
            fontsize=6.2,
            weight="bold",
            linespacing=1.05,
        )
        axis.text(
            x,
            0.25,
            _RELATIONSHIP_LABELS[source.relationship],
            ha="center",
            va="center",
            fontsize=5.4,
            color=_MUTED,
        )


def _two_line_label(value: str) -> str:
    words = value.split()
    if len(words) < 2:
        return value
    split = max(1, len(words) // 2)
    return " ".join(words[:split]) + "\n" + " ".join(words[split:])


def _draw_evidence_state_labels(axis, states, positions) -> None:
    axis.set_xlim(0, 1)
    axis.set_ylim(max(positions) + 0.55, -0.55)
    axis.axis("off")
    axis.set_title(
        "Cell state",
        loc="left",
        fontsize=6.8,
        weight="bold",
        color=_MUTED,
        pad=5,
    )
    for state, y in zip(states, positions, strict=True):
        detailed = state.level == "L2"
        color = _family_color(state.state_id)
        if detailed:
            axis.plot([0.060, 0.105], [y, y], color=color, lw=0.75)
            x = 0.125
        else:
            axis.plot([0.010, 0.035], [y, y], color=color, lw=2.5)
            x = 0.050
        axis.text(
            x,
            y,
            _friendly_state_name(state.display_name),
            ha="left",
            va="center",
            fontsize=6.45 if detailed else 6.7,
            weight="normal" if detailed else "bold",
            color=_INK,
        )


def _draw_source_state_matrix(axis, states, sources, records, positions) -> None:
    axis.set_xlim(-0.5, len(sources) - 0.5)
    axis.set_ylim(max(positions) + 0.55, -0.55)
    axis.set_xticks([])
    axis.set_yticks([])
    axis.spines[:].set_visible(False)

    for x in range(len(sources)):
        axis.axvline(x, color=_HAIRLINE, lw=0.45, zorder=0)
    for state, y in zip(states, positions, strict=True):
        axis.axhline(y + 0.5, color=_HAIRLINE, lw=0.38, zorder=0)
        for x, source in enumerate(sources):
            _draw_matrix_mark(axis, x, y, records[(state.state_id, source.source_id)])


def _draw_matrix_mark(axis, x: float, y: float, record) -> None:
    state = record.assessment_state
    evidence = record.evidence_state
    if state is MatrixAssessmentState.SOURCE_ANCHORED:
        axis.scatter(
            [x],
            [y],
            s=38,
            marker="o",
            color=_EVIDENCE_BLUE,
            edgecolors="white",
            linewidths=0.45,
            zorder=3,
        )
    elif state is MatrixAssessmentState.SUPPORT:
        face = (
            _EVIDENCE_TEAL
            if evidence is EvidenceState.MEASURED
            else _tint(_EVIDENCE_TEAL, 0.45)
        )
        axis.scatter(
            [x],
            [y],
            s=42,
            marker="s",
            facecolors=face,
            edgecolors=_EVIDENCE_TEAL,
            linewidths=0.7,
            zorder=3,
        )
    elif state is MatrixAssessmentState.OPPOSITION:
        axis.scatter(
            [x],
            [y],
            s=48,
            marker="x",
            color=_CONFLICT,
            linewidths=1.15,
            zorder=3,
        )
    elif state is MatrixAssessmentState.CONFLICT:
        alert = evidence is EvidenceState.ALERT
        axis.scatter(
            [x],
            [y],
            s=46,
            marker="D",
            facecolors=_tint(_EVIDENCE_AMBER, 0.35) if alert else "white",
            edgecolors=_CONFLICT if alert else _EVIDENCE_AMBER,
            linewidths=0.9,
            zorder=3,
        )
    elif evidence is EvidenceState.PRIOR_ONLY:
        axis.scatter(
            [x],
            [y],
            s=35,
            marker="o",
            facecolors="white",
            edgecolors=_EVIDENCE_PURPLE,
            linewidths=0.8,
            zorder=3,
        )
    elif evidence is EvidenceState.UNAVAILABLE:
        axis.text(
            x,
            y,
            "/",
            ha="center",
            va="center",
            fontsize=8.0,
            color="#A7ADB4",
            zorder=3,
        )
    elif evidence is EvidenceState.UNKNOWN:
        axis.text(
            x,
            y,
            "?",
            ha="center",
            va="center",
            fontsize=6.8,
            color="#9EA5AD",
            zorder=3,
        )
    else:
        axis.text(
            x,
            y,
            "·",
            ha="center",
            va="center",
            fontsize=8.0,
            color="#C5CAD0",
            zorder=2,
        )


def _draw_evidence_side_columns(
    count_axis,
    independent_axis,
    review_axis,
    states,
    positions,
    independent: set[str],
) -> None:
    for axis in (count_axis, independent_axis, review_axis):
        axis.set_xlim(0, 1)
        axis.set_ylim(max(positions) + 0.55, -0.55)
        axis.axis("off")
    count_axis.set_title(
        "Current\nlabel n", fontsize=6.1, weight="bold", color=_MUTED, pad=5
    )
    independent_axis.set_title(
        "Independent\nassessment", fontsize=6.1, weight="bold", color=_MUTED, pad=5
    )
    review_axis.set_title("Review", fontsize=6.1, weight="bold", color=_MUTED, pad=5)
    for state, y in zip(states, positions, strict=True):
        count_axis.text(
            0.5,
            y,
            _compact_count(state.primary_n_observations),
            ha="center",
            va="center",
            fontsize=6.1,
            color=_INK,
        )
        assessed = state.state_id in independent
        independent_axis.text(
            0.5,
            y,
            "●" if assessed else "—",
            ha="center",
            va="center",
            fontsize=6.5,
            color=_EVIDENCE_TEAL if assessed else "#B7BDC4",
        )
        review_axis.text(
            0.5,
            y,
            str(state.review_state).replace("_", " "),
            ha="center",
            va="center",
            fontsize=5.4,
            color=_CONFLICT if str(state.review_state) == "pending" else _MUTED,
        )


def _compact_count(value: int | None) -> str:
    if value is None:
        return "—"
    if value >= 10_000:
        return f"{value / 1000:.0f}k"
    if value >= 1_000:
        return f"{value / 1000:.1f}k"
    return str(value)


def _draw_evidence_key(axis) -> None:
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.axis("off")
    _draw_key_symbol(
        axis, 0.00, 0.72, "o", _EVIDENCE_BLUE, _EVIDENCE_BLUE, "label present"
    )
    _draw_key_symbol(
        axis, 0.17, 0.72, "s", _EVIDENCE_TEAL, _EVIDENCE_TEAL, "support · measured"
    )
    _draw_key_symbol(
        axis,
        0.39,
        0.72,
        "s",
        _tint(_EVIDENCE_TEAL, 0.45),
        _EVIDENCE_TEAL,
        "support · inferred",
    )
    _draw_key_symbol(
        axis,
        0.60,
        0.72,
        "D",
        _tint(_EVIDENCE_AMBER, 0.35),
        _CONFLICT,
        "conflict · alert",
    )
    _draw_key_symbol(axis, 0.78, 0.72, "x", _CONFLICT, _CONFLICT, "opposition")

    _draw_key_symbol(
        axis, 0.00, 0.22, "D", "white", _EVIDENCE_AMBER, "conflict · unknown"
    )
    _draw_key_symbol(axis, 0.21, 0.22, "o", "white", _EVIDENCE_PURPLE, "prior only")
    _draw_key_text(axis, 0.36, 0.22, "·", "#C5CAD0", "not assessed · missing")
    _draw_key_text(axis, 0.60, 0.22, "?", "#9EA5AD", "not assessed · unknown")
    _draw_key_text(axis, 0.83, 0.22, "/", "#A7ADB4", "not assessed · unavailable")


def _draw_key_symbol(axis, x, y, marker, face, edge, label) -> None:
    if marker == "x":
        axis.scatter([x + 0.012], [y], s=28, marker=marker, color=edge, linewidths=0.9)
    else:
        axis.scatter(
            [x + 0.012],
            [y],
            s=28,
            marker=marker,
            facecolors=face,
            edgecolors=edge,
            linewidths=0.8,
        )
    axis.text(x + 0.030, y, label, fontsize=5.75, va="center")


def _draw_key_text(axis, x, y, symbol, color, label) -> None:
    axis.text(x + 0.012, y, symbol, fontsize=8, color=color, ha="center", va="center")
    axis.text(x + 0.030, y, label, fontsize=5.75, va="center")


def _friendly_state_name(value: str) -> str:
    names = {
        "Radial_Glia": "Radial glia",
        "Endothelial_Cell": "Endothelial cell",
        "Immune_Cell": "Immune cell",
        "Smooth_Muscle": "Smooth muscle",
        "Neuron_DA": "Dopaminergic neuron",
        "Neuron_GABA": "GABAergic neuron",
        "Neuron_Glut": "Glutamatergic neuron",
        "Neuron_Glut_GABA": "Glut/GABA neuron",
        "Neuron_OMTN": "Oculomotor/trochlear neuron",
        "Neuron_ChAT": "Cholinergic neuron",
        "Neuron_Sero": "Serotonergic neuron",
    }
    if value.startswith("Developmental gliogenic progenitor"):
        return "Gliogenic progenitor*"
    return names.get(value, value.replace("_", " "))


def _family_color(state_id: str) -> str:
    key = state_id.split(":", 1)[-1]
    if key.startswith("RG_") or key == "Radial_Glia":
        return _FAMILY_COLORS["radial_glia"]
    if key.startswith(("Nb_", "IPC_")) or key == "Neuroblast":
        return _FAMILY_COLORS["neuroblast"]
    if key.startswith("Neuron_"):
        return _FAMILY_COLORS["neuron"]
    if key in {"Astrocyte", "Glioblast", "OPC", "Oligo"}:
        return _FAMILY_COLORS["glial"]
    if key in {
        "Endothelial_Cell",
        "Pericyte",
        "Smooth_Muscle",
        "Fibroblast",
    }:
        return _FAMILY_COLORS["vascular"]
    if key == "Immune_Cell":
        return _FAMILY_COLORS["immune"]
    return _FAMILY_COLORS["other"]


def _tint(color: str, fraction: float) -> str:
    rgb = np.asarray(to_rgb(color))
    mixed = rgb + (1.0 - rgb) * fraction
    return "#{:02X}{:02X}{:02X}".format(*(np.clip(mixed, 0, 1) * 255).astype(int))


def _save_matrix_figure(fig, output_stem: Path) -> tuple[Path, Path, Path]:
    svg = output_stem.with_suffix(".svg")
    png = output_stem.with_suffix(".png")
    pdf = output_stem.with_suffix(".pdf")
    with plt.rc_context({"svg.hashsalt": "BRIDGE-P0-02"}):
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


def render_hierarchical_composition(
    profile: (
        HierarchicalCellStateCompositionDataV1
        | HierarchicalCellStateVisualizationDataV1
    ),
    output_stem: Path,
) -> tuple[Path, Path, Path]:
    """Render a compact taxonomy-aligned reference fingerprint."""

    groups, states, broad_count, matrix, conflict, unavailable = _reference_matrix(
        profile
    )
    items = _visible_reference_items(states, broad_count, matrix, conflict, unavailable)
    positions = np.arange(len(items), dtype=float)
    n_groups = len(groups)
    single_group = n_groups == 1
    height = max(5.8, 1.75 + 0.255 * len(items))

    with plt.rc_context(_FIGURE_RC):
        fig = plt.figure(figsize=(9.2, height), facecolor="white")
        label_axis = fig.add_axes([0.035, 0.155, 0.260, 0.675])
        if single_group:
            matrix_axis = None
            overall_axis = fig.add_axes([0.315, 0.155, 0.300, 0.675])
            parent_axis = fig.add_axes([0.665, 0.155, 0.300, 0.675])
        else:
            matrix_axis = fig.add_axes([0.315, 0.155, 0.650, 0.675])
            overall_axis = None
            parent_axis = None

        fig.text(
            0.035,
            0.974,
            "Cell-state correspondence profile",
            fontsize=10.5,
            weight="bold",
            ha="left",
            va="top",
        )
        fig.text(
            0.035,
            0.946,
            "Broad cell classes with regional subtype detail",
            fontsize=7.6,
            color=_MUTED,
            ha="left",
            va="top",
        )
        fig.text(
            0.035,
            0.917,
            _reference_summary(states, broad_count, matrix, conflict),
            fontsize=7.7,
            color=_INK,
            weight="bold",
            ha="left",
            va="top",
        )
        fig.text(
            0.965,
            0.946,
            "Unknown / out-of-reference detection: not assessed",
            fontsize=6.7,
            color=_CONFLICT,
            weight="bold",
            ha="right",
            va="top",
        )

        _draw_reference_taxonomy(label_axis, states, items, positions)
        if single_group and overall_axis is not None and parent_axis is not None:
            _draw_reference_dot_columns(
                overall_axis,
                parent_axis,
                states,
                matrix[0],
                float(conflict[0]),
                float(unavailable[0]),
                items,
                positions,
            )
        elif matrix_axis is not None:
            _draw_reference_fingerprint(
                matrix_axis,
                groups,
                states,
                matrix,
                conflict,
                unavailable,
                items,
                positions,
            )

        zero_broad = sum(
            bool(
                np.all(np.isfinite(matrix[:, index]))
                and np.allclose(matrix[:, index], 0.0)
            )
            for index in range(broad_count)
        )
        if single_group:
            mark_note = (
                "Point position and direct labels encode correspondence on a common scale. "
                f"{zero_broad} registered broad classes with 0% are omitted from this view "
                "and retained in the accompanying table."
            )
            denominator_note = (
                "The left panel uses the complete product as denominator for broad "
                "classes and regional subtypes; the right panel expresses each subtype "
                "within its broad parent. Values are not calibrated identity probabilities."
            )
        else:
            mark_note = (
                "Circle area encodes correspondence within each submitted or exploratory "
                "group; values of 8% or more are labelled. "
                f"{zero_broad} registered broad classes with 0% are retained in the table."
            )
            denominator_note = (
                "Each column uses its own product-group denominator. Broad classes and "
                "regional subtypes remain separate correspondence levels. Values are not "
                "calibrated identity probabilities."
            )
        fig.text(
            0.035,
            0.090,
            mark_note,
            fontsize=6.5,
            color=_MUTED,
            ha="left",
            va="bottom",
        )
        fig.text(
            0.035,
            0.054,
            denominator_note,
            fontsize=6.5,
            color=_MUTED,
            ha="left",
            va="bottom",
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
        "profile_denominator_scope": profile.denominator_scope,
        "source_conflict_assessed": profile.source_conflict_assessed,
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
                "denominator_scope": record.denominator_scope,
                "count": record.count,
                "group_denominator": None,
                "group_fraction": None,
                "record_whole_product_denominator": record.whole_product_denominator,
                "whole_product_fraction": record.whole_product_fraction,
                "parent_denominator": record.parent_denominator,
                "parent_fraction": record.parent_fraction,
                "supporting_source_ids_json": _json_cell(record.supporting_source_ids),
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
                "partition_id": (
                    "root" if record.level == "L1" else record.parent_state_id
                ),
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
                "denominator_scope": (
                    "resolved broad-state observations within product group"
                    if record.level == "L2"
                    else "product group observations"
                ),
                "count": record.count,
                "group_denominator": record.group_denominator,
                "group_fraction": record.group_fraction,
                "record_whole_product_denominator": record.whole_product_denominator,
                "whole_product_fraction": record.whole_product_fraction,
                "parent_denominator": record.parent_denominator,
                "parent_fraction": record.parent_fraction,
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


@dataclass(frozen=True)
class _ReferenceStateColumn:
    state_id: str
    display_name: str
    kind: str
    reference_level: str
    parent_state_id: str | None


def write_hierarchical_visualization_table(
    profile: HierarchicalCellStateVisualizationDataV1,
    path: Path,
) -> Path:
    """Write the exact row-by-reference presentation grid."""

    base = {
        "object_version": profile.object_version,
        "schema_ref": profile.schema_ref,
        "profile_id": profile.profile_id,
        "producer_run_ref": profile.producer_run_ref,
        "source_profile_ref": profile.source_profile_ref,
        "source_profile_sha256": profile.source_profile_sha256,
        "scientific_status": profile.scientific_status,
        "observation_unit": profile.observation_unit,
        "whole_product_denominator": profile.whole_product_denominator,
        "profile_denominator_scope": profile.denominator_scope,
        "grouping_state": profile.grouping.state,
        "grouping_source": profile.grouping.source,
        "grouping_key": profile.grouping.grouping_key,
        "grouping_hash": profile.grouping.grouping_hash,
        "profile_evidence_ids_json": _json_cell(profile.evidence_ids),
        "profile_limitations_json": _json_cell(profile.limitations),
        "profile_alt_text": profile.alt_text,
        "profile_long_description": profile.long_description,
    }
    rows = [
        {**base, **record.model_dump(mode="json")}
        for record in sorted(
            profile.records,
            key=lambda item: (item.row_order, item.column_order),
        )
    ]
    pd.DataFrame(rows).to_csv(path, sep="\t", index=False)
    return path


def _reference_matrix(
    profile: (
        HierarchicalCellStateCompositionDataV1
        | HierarchicalCellStateVisualizationDataV1
    ),
):
    if isinstance(profile, HierarchicalCellStateVisualizationDataV1):
        return _presentation_reference_matrix(profile)

    ordered_states = [
        record
        for record in sorted(profile.composition_records, key=lambda item: item.order)
        if record.record_kind == "state"
    ]
    broad_states = [record for record in ordered_states if record.level == "L1"]
    state_records = broad_states + [
        record for record in ordered_states if record.level == "L2"
    ]
    states = [
        _ReferenceStateColumn(
            state_id=record.state_id,
            display_name=record.display_name,
            kind="state",
            reference_level=record.level,
            parent_state_id=record.parent_state_id,
        )
        for record in state_records
    ]
    broad_count = len(broad_states)
    if profile.groups:
        records = {
            (record.group_id, record.state_id): record
            for record in profile.group_records
            if record.state_id is not None
        }
        statuses = {
            (record.group_id, record.resolution_state): record
            for record in profile.group_records
            if record.level == "L1" and record.state_id is None
        }
        matrix = np.asarray(
            [
                [
                    (
                        _fraction_or_nan(
                            records[(group.group_id, state.state_id)].group_fraction
                        )
                        if (group.group_id, state.state_id) in records
                        else 0.0
                    )
                    for state in states
                ]
                for group in profile.groups
            ],
            dtype=float,
        )
        conflict = np.asarray(
            [
                (
                    _fraction_or_nan(
                        statuses[(group.group_id, "source_conflict")].group_fraction
                    )
                    if profile.source_conflict_assessed
                    else np.nan
                )
                for group in profile.groups
            ],
            dtype=float,
        )
        unavailable = np.asarray(
            [
                _fraction_or_nan(
                    statuses[(group.group_id, "unavailable")].group_fraction
                )
                for group in profile.groups
            ],
            dtype=float,
        )
        return (
            list(profile.groups),
            states,
            broad_count,
            matrix,
            conflict,
            unavailable,
        )

    whole = {
        "display_name": "Whole product",
        "count": profile.whole_product_denominator,
        "whole_product_fraction": 1.0,
    }
    matrix = np.asarray(
        [[_fraction_or_nan(record.whole_product_fraction) for record in state_records]],
        dtype=float,
    )
    status = {
        record.resolution_state: _fraction_or_nan(record.whole_product_fraction)
        for record in profile.composition_records
        if record.record_kind == "resolution" and record.partition_id == "root"
    }
    return (
        [whole],
        states,
        broad_count,
        matrix,
        np.asarray(
            [
                (
                    status.get("source_conflict", 0.0)
                    if profile.source_conflict_assessed
                    else np.nan
                )
            ]
        ),
        np.asarray([status.get("unavailable", 0.0)]),
    )


def _fraction_or_nan(value: float | None) -> float:
    return np.nan if value is None else float(value)


def _presentation_reference_matrix(
    profile: HierarchicalCellStateVisualizationDataV1,
):
    row_metadata = {}
    column_metadata = {}
    records = {}
    for record in profile.records:
        row_metadata.setdefault(
            record.row_id,
            {
                "order": record.row_order,
                "display_name": record.row_display_name,
                "count": record.row_count,
                "whole_product_fraction": record.row_whole_product_fraction,
            },
        )
        column_metadata.setdefault(
            record.column_id,
            {
                "order": record.column_order,
                "display_name": record.column_display_name,
                "kind": record.column_kind,
                "reference_level": record.reference_level,
                "parent_state_id": record.parent_state_id,
            },
        )
        records[(record.row_id, record.column_id)] = record

    rows = [
        value
        for _, value in sorted(row_metadata.items(), key=lambda item: item[1]["order"])
    ]
    row_ids = [
        row_id
        for row_id, _ in sorted(row_metadata.items(), key=lambda item: item[1]["order"])
    ]
    ordered_columns = [
        (column_id, value)
        for column_id, value in sorted(
            column_metadata.items(), key=lambda item: item[1]["order"]
        )
        if value["kind"] in {"state", "subtype_unresolved", "subtype_unavailable"}
    ]
    broad_columns = [
        item for item in ordered_columns if item[1]["reference_level"] == "L1"
    ]
    detailed_columns = [
        item for item in ordered_columns if item[1]["reference_level"] != "L1"
    ]
    state_columns = broad_columns + detailed_columns
    states = [
        _ReferenceStateColumn(
            state_id=column_id,
            display_name=str(value["display_name"]),
            kind=str(value["kind"]),
            reference_level=str(value["reference_level"]),
            parent_state_id=value["parent_state_id"],
        )
        for column_id, value in state_columns
    ]
    matrix = np.asarray(
        [
            [
                _fraction_or_nan(records[(row_id, column_id)].fraction)
                for column_id, _ in state_columns
            ]
            for row_id in row_ids
        ],
        dtype=float,
    )
    conflict_id = next(
        column_id
        for column_id, value in column_metadata.items()
        if value["kind"] == "source_conflict"
    )
    unavailable_id = next(
        column_id
        for column_id, value in column_metadata.items()
        if value["kind"] == "unavailable"
    )
    conflict = np.asarray(
        [
            (
                np.nan
                if records[(row_id, conflict_id)].fraction is None
                else float(records[(row_id, conflict_id)].fraction)
            )
            for row_id in row_ids
        ],
        dtype=float,
    )
    unavailable = np.asarray(
        [
            _fraction_or_nan(records[(row_id, unavailable_id)].fraction)
            for row_id in row_ids
        ],
        dtype=float,
    )
    broad_count = len(broad_columns)
    return rows, states, broad_count, matrix, conflict, unavailable


def _visible_reference_items(
    states,
    broad_count: int,
    matrix: np.ndarray,
    conflict: np.ndarray,
    unavailable: np.ndarray,
) -> list[tuple[str, int]]:
    broad_indices = sorted(
        (
            index
            for index in range(broad_count)
            if bool(np.any(matrix[:, index] > 0) or np.any(np.isnan(matrix[:, index])))
        ),
        key=lambda index: _broad_state_rank(states[index].state_id),
    )
    items: list[tuple[str, int]] = []
    used: set[int] = set()
    for index in broad_indices:
        items.append(("state", index))
        used.add(index)
        parent_id = states[index].state_id
        for child_index in range(broad_count, len(states)):
            if states[child_index].parent_state_id == parent_id:
                items.append(("state", child_index))
                used.add(child_index)
    for index in range(broad_count, len(states)):
        if index not in used and bool(
            np.any(matrix[:, index] > 0) or np.any(np.isnan(matrix[:, index]))
        ):
            items.append(("state", index))
    if bool(np.any(np.isfinite(conflict))):
        items.append(("conflict", -1))
    if bool(np.any(unavailable > 0) or np.any(np.isnan(unavailable))):
        items.append(("unavailable", -1))
    return items


_BROAD_STATE_ORDER = (
    "L1:Astrocyte",
    "L1:Glioblast",
    "L1:Radial_Glia",
    "L1:Neuroblast",
    "L1:OPC",
    "L1:Oligo",
    "L1:Neuron_DA",
    "L1:Neuron_GABA",
    "L1:Neuron_Glut",
    "L1:Neuron_Glut_GABA",
    "L1:Neuron_OMTN",
    "L1:Neuron_ChAT",
    "L1:Neuron_Sero",
    "L1:Endothelial_Cell",
    "L1:Pericyte",
    "L1:Smooth_Muscle",
    "L1:Fibroblast",
    "L1:Immune_Cell",
)


def _broad_state_rank(state_id: str) -> int:
    try:
        return _BROAD_STATE_ORDER.index(state_id)
    except ValueError:
        return len(_BROAD_STATE_ORDER)


def _draw_reference_taxonomy(axis, states, items, positions) -> None:
    axis.set_xlim(0, 1)
    axis.set_ylim(len(items) - 0.5, -0.5)
    axis.axis("off")
    axis.set_title(
        "Reference state",
        loc="left",
        fontsize=6.8,
        weight="bold",
        color=_MUTED,
        pad=5,
    )

    child_groups: dict[str, list[float]] = {}
    for (kind, index), y in zip(items, positions, strict=True):
        if kind != "state":
            continue
        state = states[index]
        if state.parent_state_id:
            child_groups.setdefault(state.parent_state_id, []).append(float(y))
    parent_y = {
        states[index].state_id: float(y)
        for (kind, index), y in zip(items, positions, strict=True)
        if kind == "state" and states[index].reference_level == "L1"
    }
    for parent_id, child_y in child_groups.items():
        if parent_id not in parent_y:
            continue
        color = _family_color(parent_id)
        axis.plot(
            [0.075, 0.075],
            [parent_y[parent_id] + 0.22, max(child_y)],
            color=_tint(color, 0.35),
            lw=0.75,
        )

    for (kind, index), y in zip(items, positions, strict=True):
        if kind == "state":
            state = states[index]
            detailed = state.reference_level == "L2"
            color = _reference_state_color(state)
            if detailed:
                axis.plot([0.075, 0.125], [y, y], color=_tint(color, 0.25), lw=0.75)
                x = 0.145
            else:
                axis.plot([0.010, 0.042], [y, y], color=color, lw=2.8)
                x = 0.060
            axis.text(
                x,
                y,
                _reference_state_label(state),
                ha="left",
                va="center",
                fontsize=6.45 if detailed else 6.8,
                weight="normal" if detailed else "bold",
                color=_INK,
            )
        else:
            color = _CONFLICT if kind == "conflict" else _UNKNOWN
            axis.plot([0.010, 0.042], [y, y], color=color, lw=2.8)
            axis.text(
                0.060,
                y,
                (
                    "Broad-state correspondence unresolved\n(sources disagree)"
                    if kind == "conflict"
                    else "Correspondence unavailable"
                ),
                ha="left",
                va="center",
                fontsize=6.7,
                weight="bold",
                color=_INK,
            )


def _draw_reference_fingerprint(
    axis,
    groups,
    states,
    matrix,
    conflict,
    unavailable,
    items,
    positions,
) -> None:
    axis.set_xlim(-0.5, len(groups) - 0.5)
    axis.set_ylim(len(items) - 0.5, -0.5)
    axis.set_yticks([])
    axis.set_xticks(
        np.arange(len(groups)),
        [_reference_group_label(group) for group in groups],
        fontsize=6.5,
    )
    axis.xaxis.tick_top()
    axis.tick_params(axis="x", length=0, pad=7)
    if len(groups) > 4:
        plt.setp(axis.get_xticklabels(), rotation=52, ha="left", rotation_mode="anchor")
    axis.set_title(
        "Share within each product group",
        fontsize=6.8,
        weight="bold",
        color=_MUTED,
        pad=5,
    )
    axis.spines[:].set_visible(False)
    for x in range(len(groups)):
        axis.axvline(x, color=_HAIRLINE, lw=0.55, zorder=0)
    for y in positions:
        axis.axhline(y + 0.5, color=_HAIRLINE, lw=0.38, zorder=0)

    for (kind, index), y in zip(items, positions, strict=True):
        values = _reference_item_values(kind, index, matrix, conflict, unavailable)
        state = states[index] if kind == "state" else None
        color = (
            _reference_state_color(state)
            if state is not None
            else (_CONFLICT if kind == "conflict" else _UNKNOWN)
        )
        marker = "o" if kind == "state" else ("D" if kind == "conflict" else "s")
        for x, value in enumerate(values):
            if np.isnan(value):
                axis.text(
                    x, y, "—", ha="center", va="center", color="#B7BDC4", fontsize=7
                )
                continue
            if value <= 0:
                axis.scatter(
                    [x],
                    [y],
                    s=10,
                    marker="o",
                    facecolors="white",
                    edgecolors="#C5CAD0",
                    linewidths=0.55,
                    zorder=2,
                )
                continue
            axis.scatter(
                [x],
                [y],
                s=max(14.0, 330.0 * float(value)),
                marker=marker,
                facecolors=color if kind != "conflict" else _tint(color, 0.55),
                edgecolors=_INK if kind == "state" else color,
                linewidths=0.55 if kind == "state" else 0.9,
                alpha=0.96,
                zorder=3,
            )
            if len(groups) > 1 and value >= 0.08:
                axis.text(
                    x,
                    y,
                    f"{100 * value:.0f}",
                    ha="center",
                    va="center",
                    fontsize=5.1,
                    weight="bold",
                    color="white" if value >= 0.24 else _INK,
                    zorder=4,
                )


def _draw_reference_dot_columns(
    overall_axis,
    parent_axis,
    states,
    values,
    conflict: float,
    unavailable: float,
    items,
    positions,
) -> None:
    for axis, title in (
        (overall_axis, "Share of complete product (%)"),
        (parent_axis, "Share within broad class (%)"),
    ):
        axis.set_xlim(-3, 108)
        axis.set_ylim(len(items) - 0.5, -0.5)
        axis.set_yticks([])
        axis.set_xticks([0, 25, 50, 75, 100])
        axis.set_xticklabels(["0", "25", "50", "75", "100"], fontsize=6.2)
        axis.set_title(title, fontsize=6.8, weight="bold", color=_MUTED, pad=8)
        axis.spines[["top", "right", "left"]].set_visible(False)
        axis.spines["bottom"].set_color(_HAIRLINE)
        axis.tick_params(axis="x", colors=_MUTED, length=2.5, width=0.55)
        for tick in (0, 25, 50, 75, 100):
            axis.axvline(tick, color=_HAIRLINE, lw=0.45, zorder=0)
        for y in positions:
            axis.axhline(y + 0.5, color=_HAIRLINE, lw=0.35, zorder=0)

    index_by_state = {state.state_id: index for index, state in enumerate(states)}
    for (kind, index), y in zip(items, positions, strict=True):
        if kind == "state":
            value = float(values[index])
            state = states[index]
            color = _reference_state_color(state)
            parent_value = None
            if state.parent_state_id in index_by_state:
                denominator = float(values[index_by_state[state.parent_state_id]])
                parent_value = (
                    value / denominator
                    if np.isfinite(value)
                    and np.isfinite(denominator)
                    and denominator > 0
                    else None
                )
            marker = "o"
        else:
            value = conflict if kind == "conflict" else unavailable
            color = _CONFLICT if kind == "conflict" else _UNKNOWN
            parent_value = None
            marker = "D" if kind == "conflict" else "s"
        _draw_fraction_point(overall_axis, y, value, color, marker)
        if parent_value is not None:
            _draw_fraction_point(parent_axis, y, parent_value, color, "o")
        else:
            parent_axis.text(
                0,
                y,
                "—",
                ha="center",
                va="center",
                fontsize=6.4,
                color="#B7BDC4",
            )


def _draw_fraction_point(axis, y: float, value: float, color: str, marker: str) -> None:
    if np.isnan(value):
        axis.text(0, y, "—", ha="center", va="center", color="#B7BDC4", fontsize=6.5)
        return
    x = 100.0 * value
    if value <= 0:
        axis.scatter(
            [0],
            [y],
            s=15,
            marker="o",
            facecolors="white",
            edgecolors="#BFC5CC",
            linewidths=0.65,
            zorder=2,
        )
    else:
        axis.hlines(
            y,
            0,
            x,
            color=_tint(color, 0.72),
            lw=0.85,
            zorder=1,
        )
        axis.scatter(
            [x],
            [y],
            s=34,
            marker=marker,
            facecolors=color if marker != "D" else _tint(color, 0.45),
            edgecolors=_INK if marker == "o" else color,
            linewidths=0.55 if marker == "o" else 0.85,
            zorder=3,
        )
    right_edge = x > 91
    axis.text(
        x - 2.0 if right_edge else x + 2.0,
        y,
        f"{x:.1f}%",
        ha="right" if right_edge else "left",
        va="center",
        fontsize=6.25,
        weight="bold" if value >= 0.1 else "normal",
        color=color if value > 0 else _MUTED,
    )


def _reference_item_values(kind, index, matrix, conflict, unavailable):
    if kind == "state":
        return matrix[:, index]
    if kind == "conflict":
        return conflict
    return unavailable


def _reference_state_label(state: _ReferenceStateColumn) -> str:
    if state.kind == "subtype_unresolved":
        return "Subtype unresolved"
    if state.kind == "subtype_unavailable":
        return "Subtype unavailable"
    return _friendly_state_name(state.display_name)


def _reference_state_color(state: _ReferenceStateColumn) -> str:
    base = _family_color(state.state_id)
    if state.reference_level == "L1":
        return base
    shade = 0.12 + 0.08 * (sum(map(ord, state.state_id)) % 4)
    return _tint(base, shade)


def _reference_group_label(group) -> str:
    name = group["display_name"] if isinstance(group, dict) else group.display_name
    count = group["count"] if isinstance(group, dict) else group.count
    return f"{name}\nn = {int(count):,}"


def _reference_summary(states, broad_count, matrix, conflict) -> str:
    if len(matrix) != 1:
        return f"{len(matrix)} submitted or exploratory groups · correspondence shown per group"
    ranked = sorted(
        (
            (float(matrix[0, index]), _friendly_state_name(states[index].display_name))
            for index in range(broad_count)
            if matrix[0, index] > 0
        ),
        reverse=True,
    )
    parts = [f"{label} {100 * value:.1f}%" for value, label in ranked[:2]]
    if np.isfinite(conflict[0]):
        parts.append(
            f"broad-state correspondence unresolved {100 * conflict[0]:.1f}% "
            "(sources disagree)"
        )
    return " · ".join(parts)


def _percent(value: float | None) -> str:
    if value is None or np.isnan(value):
        return "—"
    return f"{100 * value:.1f}%"
