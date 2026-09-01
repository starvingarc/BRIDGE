from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_05_off_target_control.visualization_data import (
    OFF_TARGET_VISUALIZATION_DATA_SCHEMA_REF,
    OOD_COMPONENT_REF,
    PRODUCT_COMPONENT_REF,
    RARE_COMPONENT_REF,
    OffTargetControlVisualizationDataV1,
    P005VisualizationArtifactSet,
)
from bridge.toolkit.contracts import ArtifactManifest
from bridge.toolkit.visualization import (
    FigureRegistry,
    VisualizationAccessibility,
    VisualizationArtifactV2,
    VisualizationDataBinding,
    VisualizationRenderBinding,
)

_RENDERER_ID = "bridge.matplotlib"
_RENDERER_VERSION = "0.1.0"
_EXPORT_PROFILE_ID = "bridge-static-scientific-figure-v0.1"
_FIGURE_WIDTH_IN = 7.1
_TITLE_SIZE = 11.2
_BACKGROUND = "#FCFBF8"
_TEXT = "#24323A"
_MUTED = "#68757C"
_GRID = "#DCE2E3"
_ROLE_COLORS = {
    "target": "#4F9D91",
    "acceptable_adjacent": "#9AC6A8",
    "known_off_target": "#6CA6CD",
    "role_unresolved": "#C0A4D5",
    "identity_unknown": "#8D73B5",
}
_STATE_COLORS = {
    "supported": "#4F9D91",
    "unknown": "#8D73B5",
    "ood": "#D39B67",
    "unavailable": "#B8C0C5",
    "conflict": "#C96F5B",
}
_STATE_MARKERS = {
    "supported": "o",
    "unknown": "D",
    "ood": "s",
    "unavailable": "_",
    "conflict": "x",
}
_STATE_LABELS = {
    "supported": "within supplied support",
    "unknown": "unknown",
    "ood": "outside supplied support",
    "unavailable": "not assessed",
    "conflict": "conflicting channels",
}
_OOD_STATE_LABELS = {
    "supported": "within support",
    "unknown": "unknown",
    "ood": "outside support",
    "unavailable": "not assessed",
    "conflict": "channel conflict",
}
_RARE_STATE_LABELS = {
    "detected": "detected",
    "not_detected_above_lod": (
        "not detected above supplied\nvalidated detection limit"
    ),
    "cannot_exclude": "cannot exclude",
    "not_assessed": "not assessed",
}
_MATPLOTLIB_RC = {
    "font.family": ["DejaVu Sans"],
    "font.sans-serif": ["DejaVu Sans"],
    "axes.titleweight": "bold",
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
    "svg.hashsalt": "BRIDGE-P0-05",
}


@dataclass(frozen=True)
class PreparedOffTargetControlVisualizations:
    payloads: dict[str, bytes]
    artifacts: tuple[ArtifactManifest, ...]


@dataclass(frozen=True)
class _Component:
    ref: str
    slug: str
    records_path: str
    table_name: str
    title: str


_COMPONENTS = (
    _Component(
        PRODUCT_COMPONENT_REF,
        "product-accounting",
        "product_records",
        "off_target_control_product_accounting.tsv",
        "Product composition relative to the declared target",
    ),
    _Component(
        RARE_COMPONENT_REF,
        "rare-state-detectability",
        "rare_state_records",
        "off_target_control_rare_state_detectability.tsv",
        "Rare-state observations and distinct detection boundaries",
    ),
    _Component(
        OOD_COMPONENT_REF,
        "ood-source-agreement",
        "ood_channel_records",
        "off_target_control_ood_source_agreement.tsv",
        "Reference-support and unknown-state signals by source family",
    ),
)


def prepare_off_target_control_visualizations(
    *,
    profile: OffTargetControlVisualizationDataV1,
    output_dir: Path,
    run_id: str,
    tool_version: str,
) -> PreparedOffTargetControlVisualizations:
    final_dir = output_dir / run_id
    payloads: dict[str, bytes] = {}
    artifacts: list[ArtifactManifest] = []
    data_name = "off_target_control_visualization_data.json"
    data_payload = canonical_json_bytes(profile.model_dump(mode="json"), indent=2)
    payloads[data_name] = data_payload
    data_artifact = _manifest(
        run_id,
        "off-target-control-visualization-data",
        "off_target_control_visualization_data",
        final_dir / data_name,
        "application/json",
        data_payload,
        profile.evidence_ids,
    )
    artifacts.append(data_artifact)

    table_artifacts = {}
    render_artifacts = {}
    render_reasons = {}
    with matplotlib.rc_context(rc=_MATPLOTLIB_RC):
        for component in _COMPONENTS:
            table_payload = _table(profile, component.ref)
            payloads[component.table_name] = table_payload
            table_artifact = _manifest(
                run_id,
                f"off-target-{component.slug}-table",
                "visualization_table",
                final_dir / component.table_name,
                "text/tab-separated-values",
                table_payload,
                profile.evidence_ids,
            )
            artifacts.append(table_artifact)
            table_artifacts[component.ref] = table_artifact
            render_reason = _static_render_reason(profile, component.ref)
            render_reasons[component.ref] = render_reason
            if render_reason:
                figure = _empty_figure(
                    component.title,
                    "The complete result remains available in the typed JSON and table.",
                    [render_reason],
                )
            elif component.ref == PRODUCT_COMPONENT_REF:
                figure = _render_product_accounting(profile)
            elif component.ref == RARE_COMPONENT_REF:
                figure = _render_rare_state_detectability(profile)
            else:
                figure = _render_ood_source_agreement(profile)
            for extension, (media_type, payload) in _render_payloads(figure).items():
                name = f"off_target_control_{component.slug}.{extension}"
                payloads[name] = payload
                artifact = _manifest(
                    run_id,
                    f"off-target-{component.slug}-{extension}",
                    "visualization_render",
                    final_dir / name,
                    media_type,
                    payload,
                    profile.evidence_ids,
                )
                artifacts.append(artifact)
                render_artifacts[(component.ref, extension)] = artifact

    visualizations = [
        _visualization_contract(
            profile=profile,
            component=component,
            data_artifact=data_artifact,
            table_artifact=table_artifacts[component.ref],
            render_artifacts={
                extension: render_artifacts[(component.ref, extension)]
                for extension in ("svg", "png", "pdf")
            },
            run_id=run_id,
            tool_version=tool_version,
            render_reason=render_reasons[component.ref],
        )
        for component in _COMPONENTS
    ]
    registry = FigureRegistry.load_default()
    for visualization in visualizations:
        registry.validate_artifact(visualization)

    artifact_set = P005VisualizationArtifactSet(
        artifact_set_id=f"p0-05-visualizations:{run_id.removeprefix('run-')}",
        data_profile_artifact_id=data_artifact.artifact_id,
        data_profile_sha256=data_artifact.sha256,
        visualizations=visualizations,
    )
    set_name = "off_target_control_visualization_artifact_set.json"
    set_payload = canonical_json_bytes(
        artifact_set.model_dump(mode="json"), indent=2
    )
    payloads[set_name] = set_payload
    artifacts.append(
        _manifest(
            run_id,
            "off-target-control-visualization-artifact-set",
            "visualization_artifact_set",
            final_dir / set_name,
            "application/json",
            set_payload,
            profile.evidence_ids,
        )
    )
    return PreparedOffTargetControlVisualizations(
        payloads=payloads,
        artifacts=tuple(artifacts),
    )


def _static_render_reason(profile, component_ref):
    if component_ref == PRODUCT_COMPONENT_REF:
        too_large = len(profile.product_records) + len(profile.unknown_reason_records) > 16
    elif component_ref == RARE_COMPONENT_REF:
        too_large = len(profile.rare_state_records) > 12
    else:
        too_large = (
            len(profile.ood_channel_records) > 12
            or len(profile.ood_family_records) > 10
        )
    return "static_render_requires_table_fallback" if too_large else None


def _table(profile, component_ref):
    if component_ref == PRODUCT_COMPONENT_REF:
        groups = (
            ("product_role", profile.product_records),
            ("unknown_reason", profile.unknown_reason_records),
        )
    elif component_ref == RARE_COMPONENT_REF:
        groups = (
            ("rare_state", profile.rare_state_records),
            ("spike_in_detection_hit_rate", profile.spike_in_detection_records),
        )
    else:
        groups = (
            ("ood_channel", profile.ood_channel_records),
            ("declared_source_family", profile.ood_family_records),
        )
    rows = [
        {"record_type": record_type, **item.model_dump(mode="json")}
        for record_type, records in groups
        for item in records
    ]
    if component_ref == OOD_COMPONENT_REF and profile.ood_disagreement is not None:
        rows.append(
            {
                "record_type": "supplied_state_disagreement",
                **profile.ood_disagreement.model_dump(mode="json"),
            }
        )
    if component_ref == OOD_COMPONENT_REF and profile.ood_coordination is not None:
        rows.append(
            {
                "record_type": "ordered_external_rule_coordination",
                **profile.ood_coordination.model_dump(mode="json"),
            }
        )
    fields = [
        "record_type",
        *sorted({key for row in rows for key in row if key != "record_type"}),
    ]
    buffer = StringIO(newline="")
    writer = csv.DictWriter(
        buffer, fieldnames=fields, delimiter="\t", lineterminator="\n"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: (
                    json.dumps(
                        value,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    if isinstance(value, (list, dict))
                    else "" if value is None else value
                )
                for key, value in row.items()
            }
        )
    return buffer.getvalue().encode()


def _render_product_accounting(profile):
    main = list(profile.product_records)
    reasons = list(profile.unknown_reason_records)
    rows = [*main, *reasons]
    fig = plt.figure(
        figsize=(_FIGURE_WIDTH_IN, max(5.2, 3.2 + 0.42 * len(rows))),
        facecolor=_BACKGROUND,
    )
    fig.text(
        0.065,
        0.965,
        "Product composition relative to the declared target",
        fontsize=_TITLE_SIZE,
        fontweight="bold",
        color=_TEXT,
    )
    complete = (
        profile.composition_coverage_state.value == "complete"
        and profile.unknown_coverage_state.value == "complete"
        and all(record.fraction is not None for record in main)
    )
    fig.text(
        0.065,
        0.905,
        (
            f"Candidate explanatory view · declared denominator: {profile.denominator_id} · "
            f"role map: {profile.role_map_review_state}\n"
            f"Cell count n={profile.denominator_count:,}; total soft-assignment mass="
            f"{profile.denominator_soft_mass:,.2f} (percentage denominator).\n"
        )
        + (
            "Categories close within the declared denominator."
            if complete
            else "Coverage is incomplete; missing fractions are not zero."
        ),
        fontsize=8.1,
        linespacing=1.3,
        color=_MUTED,
        va="top",
    )
    strip = fig.add_axes((0.31, 0.75, 0.62, 0.035))
    strip.set(xlim=(0, 1), ylim=(0, 1))
    strip.axis("off")
    if complete:
        left = 0.0
        for record in main:
            if record.fraction is None:
                raise ValueError("complete product accounting requires every fraction")
            width = record.fraction
            strip.add_patch(
                Rectangle(
                    (left, 0),
                    width,
                    1,
                    facecolor=_ROLE_COLORS[str(record.category)],
                    edgecolor=_BACKGROUND,
                    linewidth=1,
                )
            )
            left += width
        strip.text(
            1,
            1.4,
            "Soft assignment mass; mutually exclusive accounting categories",
            ha="right",
            va="bottom",
            fontsize=7.4,
            color=_MUTED,
        )
    else:
        strip.add_patch(
            Rectangle(
                (0, 0),
                1,
                1,
                facecolor="#F1F2F0",
                edgecolor=_GRID,
                hatch="//",
            )
        )
        strip.text(
            0.5,
            0.5,
            "No percentage closure shown",
            ha="center",
            va="center",
            fontsize=8,
            color=_MUTED,
        )

    ax = fig.add_axes((0.31, 0.245, 0.44, 0.44))
    status_ax = fig.add_axes((0.77, 0.245, 0.18, 0.44), sharey=ax)
    y_positions = list(reversed(range(len(rows))))
    ax.set(xlim=(-0.01, 1.01), ylim=(-0.8, len(rows) - 0.2))
    ax.set_xlabel(
        "Soft-assignment fraction of the declared primary denominator",
        fontsize=8.5,
        color=_MUTED,
    )
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1], ["0", "25", "50", "75", "100"])
    ax.set_yticks(
        y_positions,
        [
            item.display_name if item in main else f"   ↳ {item.display_name}"
            for item in rows
        ],
        fontsize=8.7,
    )
    ax.grid(axis="x", color=_GRID, linewidth=0.7)
    ax.tick_params(axis="x", colors=_MUTED, labelsize=7.8)
    ax.tick_params(axis="y", length=0, colors=_TEXT)
    for spine in ax.spines.values():
        spine.set_visible(False)

    for y, record in zip(y_positions, rows, strict=True):
        if record in main:
            color = _ROLE_COLORS[str(record.category)]
            if record.fraction is not None:
                if record.soft_interval_lower is not None:
                    ax.plot(
                        [record.soft_interval_lower, record.soft_interval_upper],
                        [y, y],
                        color=color,
                        linewidth=2.2,
                        solid_capstyle="round",
                    )
                ax.scatter(
                    record.fraction,
                    y,
                    s=54,
                    color=color,
                    edgecolor="white",
                    linewidth=0.8,
                    zorder=3,
                )
                if record.count_fraction is not None:
                    if record.count_interval_lower is not None:
                        ax.plot(
                            [record.count_interval_lower, record.count_interval_upper],
                            [y - 0.16, y - 0.16],
                            color=_TEXT,
                            linewidth=0.9,
                            linestyle=(0, (2, 2)),
                        )
                    ax.scatter(
                        record.count_fraction,
                        y - 0.16,
                        marker="D",
                        s=24,
                        facecolor=_BACKGROUND,
                        edgecolor=_TEXT,
                        linewidth=0.8,
                        zorder=3,
                    )
                ax.text(
                    min(0.99, record.fraction + 0.025),
                    y,
                    f"{record.fraction * 100:.1f}%",
                    fontsize=7.8,
                    va="center",
                    color=_TEXT,
                )
            else:
                ax.text(
                    0.02,
                    y,
                    "not assessed",
                    fontsize=8,
                    color=_MUTED,
                    va="center",
                )
            status_parts = [
                (
                    "observed"
                    if record.exclusion_state.value == "observed"
                    else "0 observed;\ncannot exclude"
                )
            ]
            if record.soft_interval_state == "not_assessed":
                status_parts.append("soft interval\nnot assessed")
            if record.count_interval_state == "not_assessed":
                status_parts.append("count interval\nnot assessed")
            if str(record.category) == "known_off_target":
                status_parts.append("component identities\nnot assessed")
            status = "\n".join(status_parts)
        else:
            color = _ROLE_COLORS["identity_unknown"]
            if record.fraction is not None:
                ax.scatter(
                    record.fraction,
                    y,
                    marker="d",
                    s=30,
                    facecolor=_BACKGROUND,
                    edgecolor=color,
                    linewidth=1.2,
                    zorder=3,
                )
                ax.text(
                    min(0.99, record.fraction + 0.025),
                    y,
                    f"{record.fraction * 100:.1f}%",
                    fontsize=7.5,
                    va="center",
                    color=_MUTED,
                )
            else:
                ax.text(
                    0.02,
                    y,
                    "not assessed",
                    fontsize=7.6,
                    color=_MUTED,
                    va="center",
                )
            status = (
                f"{record.observed_count:,} observed\n"
                "nested; not additive\ninterval not assessed"
            )
        status_ax.text(
            0, y, status, va="center", fontsize=6.6, color=_MUTED, linespacing=1.12
        )
    status_ax.set_xlim(0, 1)
    status_ax.axis("off")
    fig.text(
        0.31, 0.715, "● soft assignment", fontsize=7.4, color=_TEXT
    )
    fig.text(
        0.51,
        0.715,
        "◇ hard cell-count sensitivity",
        fontsize=7.4,
        color=_MUTED,
    )
    fig.text(
        0.065,
        0.115,
        (
            "Known non-target means outside the current declared product definition.\n"
            "This is not a harm or safety assessment."
        ),
        fontsize=7.9,
        color=_TEXT,
        linespacing=1.3,
    )
    fig.text(
        0.065,
        0.045,
        (
            "Intervals describe the selected denominator; missing values are not zero.\n"
            "Cell-count intervals do not represent biological-replicate uncertainty."
        ),
        fontsize=7.2,
        linespacing=1.3,
        color=_MUTED,
    )
    return fig


def _render_rare_state_detectability(profile):
    rows = list(profile.rare_state_records)
    if not rows:
        return _empty_figure(
            "Rare-state observations and distinct detection boundaries",
            "No rare-state rules were supplied for this assessment.",
            profile.rare_component_reason_codes,
        )
    curves = list(profile.spike_in_detection_records)
    fig = plt.figure(
        figsize=(
            _FIGURE_WIDTH_IN,
            max(5.8, 3.5 + 0.72 * len(rows) + (1.8 if curves else 0)),
        ),
        facecolor=_BACKGROUND,
    )
    fig.text(
        0.065,
        0.955,
        "Rare-state observations and distinct detection boundaries",
        fontsize=_TITLE_SIZE,
        fontweight="bold",
        color=_TEXT,
    )
    fig.text(
        0.065,
        0.915,
        (
            f"Candidate explanatory view · denominator: {profile.denominator_id}, "
            f"n={profile.denominator_count:,} cells\n"
            "Detection boundaries retain their distinct source and interpretation."
        ),
        fontsize=8.6,
        linespacing=1.35,
        color=_MUTED,
        va="top",
    )
    main_bottom = 0.46 if curves else 0.22
    main_height = 0.31 if curves else 0.55
    ax = fig.add_axes((0.27, main_bottom, 0.46, main_height))
    status_ax = fig.add_axes((0.75, main_bottom, 0.21, main_height), sharey=ax)
    values = [
        value
        for row in rows
        for value in (
            row.count_fraction,
            row.count_interval_upper,
            row.supplied_validated_detection_limit_fraction,
            row.supplied_zero_observation_upper_bound_fraction,
            row.spike_in_candidate_detection_limit_fraction,
        )
        if value is not None
    ]
    xmax = min(1.0, max(0.02, max(values, default=0.01) * 1.22))
    y_positions = list(reversed(range(len(rows))))
    ax.set(xlim=(-xmax * 0.025, xmax), ylim=(-0.7, len(rows) - 0.25))
    ax.set_yticks(y_positions, [row.display_name for row in rows], fontsize=8.7)
    ax.set_xlabel(
        "Observed-cell fraction of the declared primary denominator",
        fontsize=8.5,
        color=_MUTED,
    )
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", labelsize=7.8, colors=_MUTED)
    ax.grid(axis="x", color=_GRID, linewidth=0.7)
    for spine in ax.spines.values():
        spine.set_visible(False)

    for y, row in zip(y_positions, rows, strict=True):
        if row.count_fraction is not None:
            if row.count_interval_lower is not None:
                ax.plot(
                    [row.count_interval_lower, row.count_interval_upper],
                    [y, y],
                    color="#4D7087",
                    linewidth=1.6,
                    solid_capstyle="round",
                )
            ax.scatter(
                row.count_fraction,
                y,
                s=45,
                color="#6CA6CD",
                edgecolor="white",
                linewidth=0.8,
                zorder=4,
            )
        elif row.observed_count is None:
            ax.text(
                xmax * 0.02,
                y,
                "not assessed",
                fontsize=8,
                color=_MUTED,
                va="center",
            )
        if row.count_fraction is not None and row.observed_count == 0:
            ax.scatter(
                0,
                y,
                s=44,
                facecolor=_BACKGROUND,
                edgecolor=_TEXT,
                linewidth=1,
                zorder=5,
            )
            upper = row.supplied_zero_observation_upper_bound_fraction
            if upper is not None:
                ax.plot(
                    [0, upper],
                    [y + 0.13, y + 0.13],
                    color="#8D73B5",
                    linewidth=1.4,
                )
                ax.plot(
                    [upper, upper],
                    [y + 0.06, y + 0.20],
                    color="#8D73B5",
                    linewidth=1,
                )
        validated = row.supplied_validated_detection_limit_fraction
        if validated is not None:
            ax.scatter(
                validated, y + 0.18, marker="s", s=25, color=_TEXT, zorder=5
            )
            ax.plot(
                [validated, validated],
                [y + 0.08, y + 0.29],
                color=_TEXT,
                linewidth=0.8,
            )
        candidate = row.spike_in_candidate_detection_limit_fraction
        if candidate is not None:
            ax.scatter(
                candidate,
                y - 0.18,
                marker="^",
                s=32,
                facecolor=_BACKGROUND,
                edgecolor="#D39B67",
                linewidth=1.2,
                zorder=5,
            )
            ax.plot(
                [candidate, candidate],
                [y - 0.29, y - 0.08],
                color="#D39B67",
                linewidth=0.9,
                linestyle=(0, (2, 2)),
            )
        state_label = _RARE_STATE_LABELS[row.detection_state.value]
        if row.count_fraction is None:
            status_lines = [
                "not assessed"
                if row.observed_count is None
                else (
                    f"{row.observed_count:,} observed in supplied subset\n"
                    "fraction not assessed"
                )
            ]
        else:
            status_lines = [
                f"{row.observed_count:,}/{profile.denominator_count:,} · {state_label}"
            ]
        if row.count_interval_state == "available":
            status_lines.append(
                f"count interval {row.count_interval_lower:.1%}–{row.count_interval_upper:.1%}"
            )
        else:
            status_lines.append("count interval: not assessed")
        validated = row.supplied_validated_detection_limit_fraction
        status_lines.append(
            f"validated limit {validated:.1%}"
            if validated is not None
            else "validated limit: not supplied"
        )
        upper = row.supplied_zero_observation_upper_bound_fraction
        if row.observed_count == 0:
            status_lines.append(
                f"zero-observation UB {upper:.1%}"
                if upper is not None
                else "zero-observation UB: not supplied"
            )
        candidate = row.spike_in_candidate_detection_limit_fraction
        status_lines.append(
            f"spike-in candidate {candidate:.1%}"
            if candidate is not None
            else "spike-in candidate: not assessed"
        )
        status_ax.text(
            0,
            y,
            "\n".join(status_lines),
            va="center",
            fontsize=6.4,
            color=_MUTED,
            linespacing=1.12,
        )
    status_ax.set_xlim(0, 1)
    status_ax.axis("off")

    legend = [
        Line2D(
            [0], [0], marker="o", color="none", markerfacecolor="#6CA6CD",
            markeredgecolor="white", label="Observed fraction"
        ),
        Line2D(
            [0], [0], color="#4D7087", linewidth=1.6, label="Count interval"
        ),
        Line2D(
            [0], [0], marker="s", color="none", markerfacecolor=_TEXT,
            markeredgecolor=_TEXT, label="Validated detection limit"
        ),
        Line2D(
            [0], [0], marker="^", color="none", markerfacecolor=_BACKGROUND,
            markeredgecolor="#D39B67", label="Spike-in candidate limit"
        ),
        Line2D(
            [0], [0], color="#8D73B5", linewidth=1.4, marker="|",
            markeredgewidth=1.0, label="Zero-observation upper bound"
        ),
    ]
    fig.legend(
        handles=legend,
        loc="upper left",
        bbox_to_anchor=(0.27, 0.865),
        frameon=False,
        ncol=3,
        fontsize=6.6,
        handletextpad=0.4,
        columnspacing=1.2,
    )

    if curves:
        curve_ax = fig.add_axes((0.27, 0.17, 0.46, 0.14))
        states = sorted({row.state_id for row in curves})
        colors = ["#4F9D91", "#8D73B5", "#D39B67", "#6CA6CD", "#C96F5B"]
        for index, state_id in enumerate(states):
            color = colors[index % len(colors)]
            group = sorted(
                [row for row in curves if row.state_id == state_id],
                key=lambda row: row.spike_fraction,
            )
            curve_ax.plot(
                [row.spike_fraction for row in group],
                [row.detection_hit_rate for row in group],
                marker="o",
                markersize=3.8,
                linewidth=1.3,
                color=color,
                label=state_id,
            )
            for row in group:
                curve_ax.plot(
                    [row.spike_fraction, row.spike_fraction],
                    [row.detection_lower, row.detection_upper],
                    color=color,
                    linewidth=0.8,
                )
        curve_ax.set_ylim(-0.03, 1.03)
        curve_ax.set_xlabel("Supplied spike fraction", fontsize=7.8, color=_MUTED)
        curve_ax.set_ylabel("Detection hit rate", fontsize=7.8, color=_MUTED)
        curve_ax.tick_params(labelsize=7, colors=_MUTED)
        curve_ax.grid(color=_GRID, linewidth=0.6)
        curve_ax.spines["top"].set_visible(False)
        curve_ax.spines["right"].set_visible(False)
        curve_ax.legend(frameon=False, fontsize=6.8, loc="lower right")
        fig.text(
            0.27,
            0.35,
            "Spike-in detection hit rate · candidate, partially applicable",
            fontsize=7.4,
            fontweight="bold",
            color=_TEXT,
        )
        fig.text(
            0.27,
            0.325,
            (
                "At-least-one detection across declared independent groups; not recovery efficiency."
            ),
            fontsize=6.4,
            color=_MUTED,
            wrap=True,
        )
    fig.text(
        0.065,
        0.045,
        (
            "Zero observed does not establish absence. A supplied zero-observation upper bound is sample-specific.\n"
            "It is not a detection limit; a spike-in candidate limit remains exploratory."
        ),
        fontsize=7.1,
        linespacing=1.3,
        color=_MUTED,
    )
    return fig


def _render_ood_source_agreement(profile):
    channels = list(profile.ood_channel_records)
    families = list(profile.ood_family_records)
    if not channels:
        return _empty_figure(
            "Reference-support and unknown-state signals by source family",
            "Unknown-state methods were not assessed for this run.",
            profile.ood_component_reason_codes,
        )
    fig = plt.figure(
        figsize=(_FIGURE_WIDTH_IN, max(5.3, 3.5 + 0.48 * len(families))),
        facecolor=_BACKGROUND,
    )
    fig.text(
        0.065,
        0.95,
        "Reference-support and unknown-state signals by source family",
        fontsize=_TITLE_SIZE,
        fontweight="bold",
        color=_TEXT,
    )
    fig.text(
        0.065,
        0.908,
        (
            "Candidate inferred coordination · channel lineage retained.\n"
            "Declared source-family labels do not establish independence."
        ),
        fontsize=8.2,
        linespacing=1.35,
        color=_MUTED,
        va="top",
    )
    channel_ids = [item.channel_id for item in channels]
    family_ids = [item.source_family_id for item in families]
    channel_family_pairs = {
        (item.source_family_id, item.channel_id) for item in channels
    }
    ax = fig.add_axes((0.27, 0.32, 0.41, 0.42))
    summary_ax = fig.add_axes((0.71, 0.32, 0.24, 0.42), sharey=ax)
    y_by_family = {
        family_id: len(family_ids) - index - 1
        for index, family_id in enumerate(family_ids)
    }
    x_by_channel = {
        channel_id: index for index, channel_id in enumerate(channel_ids)
    }
    ax.set(
        xlim=(-0.5, len(channel_ids) - 0.5),
        ylim=(-0.6, len(family_ids) - 0.15),
    )
    ax.set_xticks(
        range(len(channel_ids)),
        [_short_label(value) for value in channel_ids],
        rotation=0,
        ha="center",
        fontsize=7.3,
    )
    ax.set_yticks(
        list(y_by_family.values()),
        [_short_label(value) for value in family_ids],
        fontsize=8.5,
    )
    ax.tick_params(length=0)
    ax.grid(color=_GRID, linewidth=0.6)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for family_id in family_ids:
        for channel_id in channel_ids:
            if (family_id, channel_id) not in channel_family_pairs:
                ax.scatter(
                    x_by_channel[channel_id],
                    y_by_family[family_id],
                    marker=".",
                    s=16,
                    color=_GRID,
                    zorder=2,
                )
    for record in channels:
        state = record.channel_state
        ax.scatter(
            x_by_channel[record.channel_id],
            y_by_family[record.source_family_id],
            marker=_STATE_MARKERS[state],
            s=100 if state == "unavailable" else 70,
            color=_STATE_COLORS[state],
            facecolor=_BACKGROUND if state == "unknown" else _STATE_COLORS[state],
            linewidth=1.2,
            zorder=4,
        )
    for family in families:
        state = family.family_state
        y = y_by_family[family.source_family_id]
        summary_ax.scatter(
            0.06,
            y,
            marker=_STATE_MARKERS[state],
            s=65,
            color=_STATE_COLORS[state],
            zorder=4,
        )
        summary_ax.text(
            0.17,
            y,
            (
                f"{_OOD_STATE_LABELS[state]}\n"
                f"{family.assessed_channel_count}/{family.channel_count} channels assessed"
            ),
            va="center",
            fontsize=8,
            color=_TEXT,
        )
    summary_ax.set_xlim(0, 1)
    summary_ax.axis("off")
    fig.text(
        0.71,
        0.785,
        "Declared family state",
        fontsize=7.5,
        fontweight="bold",
        color=_TEXT,
    )
    fig.legend(
        handles=[
            Line2D(
                [0],
                [0],
                marker=_STATE_MARKERS[state],
                color="none",
                markeredgecolor=color,
                markerfacecolor=_BACKGROUND if state == "unknown" else color,
                label=_OOD_STATE_LABELS[state],
            )
            for state, color in _STATE_COLORS.items()
        ],
        loc="upper left",
        bbox_to_anchor=(0.27, 0.85),
        frameon=False,
        ncol=3,
        fontsize=6.8,
        handletextpad=0.3,
        columnspacing=1,
    )
    disagreement = profile.ood_disagreement
    if disagreement is None or disagreement.assessment_state == "not_assessed":
        agreement_text = "Cross-family agreement: not assessed"
    else:
        agreement_text = (
            f"Cross-family agreement: {disagreement.distinct_source_family_count} declared families · "
            + (
                "disagreement observed"
                if disagreement.disagreement
                else "no disagreement observed in supplied states"
            )
        )
    fig.text(
        0.27,
        0.245,
        "Faint dot: channel belongs to another declared source family (not applicable).",
        fontsize=7.2,
        color=_MUTED,
    )
    fig.text(
        0.065, 0.195, agreement_text, fontsize=8.2, fontweight="bold", color=_TEXT
    )
    if profile.ood_coordination is None:
        coordination = "Ordered external-rule coordination: not assessed"
    else:
        record = profile.ood_coordination
        coordination = (
            "Ordered external-rule coordination: "
            f"{record.decision_state.value.replace('_', ' ')}"
        )
        if record.matched_reason_id:
            coordination += f" · rule {record.matched_reason_id}"
    fig.text(
        0.065, 0.155, coordination, fontsize=8.2, fontweight="bold", color=_TEXT
    )
    fig.text(
        0.065,
        0.075,
        (
            "This panel coordinates supplied states; it does not estimate OOD probability, cell prevalence or majority truth.\n"
            "It does not assess identity, safety or quality."
        ),
        fontsize=7.0,
        linespacing=1.3,
        color=_MUTED,
    )
    return fig


def _empty_figure(title, message, reasons):
    fig = plt.figure(figsize=(_FIGURE_WIDTH_IN, 4.9), facecolor=_BACKGROUND)
    ax = fig.add_axes((0.08, 0.16, 0.84, 0.67))
    ax.axis("off")
    ax.text(0, 0.86, title, fontsize=_TITLE_SIZE, fontweight="bold", color=_TEXT)
    ax.text(0, 0.59, message, fontsize=11, fontweight="bold", color=_MUTED)
    ax.text(
        0,
        0.38,
        " · ".join(_label(reason) for reason in sorted(set(reasons)) if reason)
        or "No assessable records were produced.",
        fontsize=9.2,
        color=_MUTED,
        wrap=True,
    )
    ax.text(
        0,
        0.16,
        "Missing evidence is not displayed as zero.",
        fontsize=8.6,
        color="#87939A",
    )
    return fig


def _render_payloads(fig):
    outputs = {}
    try:
        for extension, media_type in (
            ("svg", "image/svg+xml"),
            ("png", "image/png"),
            ("pdf", "application/pdf"),
        ):
            buffer = BytesIO()
            if extension == "svg":
                fig.savefig(
                    buffer,
                    format="svg",
                    metadata={"Date": None, "Creator": "BRIDGE"},
                )
            elif extension == "png":
                fig.savefig(
                    buffer,
                    format="png",
                    dpi=220,
                    metadata={"Software": "BRIDGE"},
                )
            else:
                fig.savefig(
                    buffer,
                    format="pdf",
                    metadata={
                        "Creator": "BRIDGE",
                        "CreationDate": None,
                        "ModDate": None,
                    },
                )
            outputs[extension] = (media_type, buffer.getvalue())
    finally:
        plt.close(fig)
    return outputs


def _visualization_contract(
    *,
    profile,
    component,
    data_artifact,
    table_artifact,
    render_artifacts,
    run_id,
    tool_version,
    render_reason,
):
    state, applicability, reasons = _component_state(profile, component.ref)
    if render_reason:
        reasons.add(render_reason)
        if applicability == "applicable":
            applicability = "partially_applicable"
    if component.ref == PRODUCT_COMPONENT_REF:
        binding = {
            "numerator_field": "soft_mass",
            "denominator_field": "denominator_soft_mass",
            "denominator_scope_field": "denominator_scope",
            "interval_lower_field": "soft_interval_lower",
            "interval_upper_field": "soft_interval_upper",
            "interval_semantics": (
                "Soft-assignment mass with independence-group bootstrap interval; "
                "hard cell-count sensitivity remains an explicitly secondary field."
            ),
        }
        denominator_label = (
            f"{profile.denominator_id}; n={profile.denominator_count} cells; "
            f"total soft-assignment mass={profile.denominator_soft_mass:.6g}"
        )
        takeaway = (
            "Declared roles and identity unknown remain separate; soft assignment "
            "and hard cell-count sensitivity appear only when assessable."
        )
        limitations = [
            "Known non-target means outside the current declared product definition, not harmful or unsafe.",
            "Cell-count intervals describe the selected denominator and are not biological-replicate uncertainty.",
            "Role unresolved, identity unknown and OOD are distinct states.",
        ]
    elif component.ref == RARE_COMPONENT_REF:
        binding = {
            "numerator_field": "observed_count",
            "denominator_field": "denominator_count",
            "denominator_scope_field": "denominator_scope",
            "interval_lower_field": "count_interval_lower",
            "interval_upper_field": "count_interval_upper",
            "interval_semantics": (
                "Selected-capture cell-count interval; supplied detection limits, "
                "zero-observation upper bounds and candidate spike-in limits are separate."
            ),
        }
        denominator_label = (
            f"{profile.denominator_id}; n={profile.denominator_count} cells"
        )
        takeaway = (
            "Observed abundance, supplied limits and exploratory spike-in limits "
            "remain distinct; zero observed never establishes absence."
        )
        limitations = [
            "Zero-observation upper bounds are sample-specific and are not detection limits.",
            "Spike-in hit rate is not recovery efficiency and its candidate limit is not validated.",
            "Missing rare-state rows are not rendered as zero.",
        ]
    else:
        binding = {"value_field": "channel_state"}
        denominator_label = None
        takeaway = (
            "Each channel retains declared source-family, method, reference and "
            "upstream-result lineage before external-rule coordination."
        )
        limitations = [
            "Declared source-family labels do not prove biological or statistical independence.",
            "Supplied channel states are not OOD probabilities, cell fractions or biological truth.",
            "External-rule coordination does not establish identity, safety or product quality.",
        ]
    component_id, component_version = component.ref.split("@", 1)
    data_binding = VisualizationDataBinding(
        artifact_id=data_artifact.artifact_id,
        schema_ref=OFF_TARGET_VISUALIZATION_DATA_SCHEMA_REF,
        object_version="0.1.0",
        sha256=data_artifact.sha256,
        records_path=component.records_path,
        record_lookup_key="record_id",
        evidence_ids_field="evidence_ids",
        unit_field="unit" if component.ref != OOD_COMPONENT_REF else None,
        evidence_state_field="evidence_state",
        scientific_status_field="scientific_status",
        missingness_field="missingness",
        applicability_field="applicability",
        **binding,
    )
    renders = [
        VisualizationRenderBinding(
            artifact_id=render_artifacts[extension].artifact_id,
            media_type=render_artifacts[extension].media_type,
            renderer_id=_RENDERER_ID,
            renderer_version=_RENDERER_VERSION,
            export_profile_id=_EXPORT_PROFILE_ID,
            data_sha256=data_artifact.sha256,
            config_sha256=_config_sha256(component.ref),
        )
        for extension in ("svg", "png", "pdf")
    ]
    return VisualizationArtifactV2(
        visualization_id=f"visualization:{run_id}:{component.slug}",
        component_id=component_id,
        component_version=component_version,
        data_binding=data_binding,
        producer_tool_id="P0-05",
        producer_tool_version=tool_version,
        producer_run_ref=f"run:{run_id}",
        evidence_ids=profile.evidence_ids,
        evidence_states=[state],
        scientific_status="candidate",
        applicability=applicability,
        missing_reason_codes=sorted(reasons),
        denominator_label=denominator_label,
        denominator_scope=(
            "declared_primary_denominator" if denominator_label else None
        ),
        unit="cells" if denominator_label else None,
        insight_title=component.title,
        takeaway=takeaway,
        limitations=limitations,
        accessibility=VisualizationAccessibility(
            alt_text=f"{component.title}. {takeaway}",
            long_description=(
                f"{component.title}. {takeaway} The exact TSV contains every "
                "value, state and reason code; typed JSON retains provenance."
            ),
            table_artifact_id=table_artifact.artifact_id,
            data_sha256=data_artifact.sha256,
        ),
        renders=renders,
    )


def _component_state(profile, component_ref):
    if component_ref == PRODUCT_COMPONENT_REF:
        return (
            profile.product_component_state,
            profile.product_component_applicability,
            set(profile.product_component_reason_codes),
        )
    if component_ref == RARE_COMPONENT_REF:
        return (
            profile.rare_component_state,
            profile.rare_component_applicability,
            set(profile.rare_component_reason_codes),
        )
    return (
        profile.ood_component_state,
        profile.ood_component_applicability,
        set(profile.ood_component_reason_codes),
    )


def _config_sha256(component_ref):
    payload = canonical_json_bytes(
        {
            "component_ref": component_ref,
            "renderer_id": _RENDERER_ID,
            "renderer_version": _RENDERER_VERSION,
            "export_profile_id": _EXPORT_PROFILE_ID,
            "renderer_source_sha256": hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
            "matplotlib_version": matplotlib.__version__,
            "matplotlib_rc": _MATPLOTLIB_RC,
            "role_colors": _ROLE_COLORS,
            "state_colors": _STATE_COLORS,
            "state_markers": _STATE_MARKERS,
        }
    )
    return hashlib.sha256(payload).hexdigest()


def _short_label(value):
    label = str(value).split(":", 1)[-1]
    return label if len(label) <= 24 else f"{label[:21]}…"


def _label(value):
    return str(value).replace("_", " ").replace("-", " ")


def _manifest(run_id, suffix, kind, path, media_type, payload, evidence_ids):
    return ArtifactManifest(
        artifact_id=f"artifact:{run_id}:{suffix}",
        kind=kind,
        path=path,
        media_type=media_type,
        sha256=hashlib.sha256(payload).hexdigest(),
        evidence_ids=evidence_ids,
    )
