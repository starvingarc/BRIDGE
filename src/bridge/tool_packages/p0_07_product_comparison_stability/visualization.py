from __future__ import annotations

import csv
import hashlib
import json
import math
import textwrap
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.transforms import blended_transform_factory

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_07_product_comparison_stability.visualization_data import (
    COMPARABILITY_COMPONENT_REF,
    METHOD_EVIDENCE_COMPONENT_REF,
    METRIC_DIFFERENCES_COMPONENT_REF,
    PRODUCT_COMPARISON_VISUALIZATION_DATA_SCHEMA_REF,
    ComparisonDesignRecord,
    MethodEvidenceRecord,
    MetricDifferenceRecord,
    MetricStabilityVisualizationRecord,
    P007VisualizationArtifactSet,
    PreparationMetricRecord,
    ProductComparisonVisualizationDataV1,
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
_WIDTH = 180.3 / 25.4
_BACKGROUND = "#FFFFFF"
_TEXT = "#24323A"
_MUTED = "#68757C"
_GRID = "#DCE2E3"
_ROW = "#F7F8F7"
_GROUP_COLORS = (
    ("#A9C7E8", "#315F8A"),
    ("#F3B8A6", "#A4533D"),
    ("#A9D8C3", "#39765F"),
    ("#C9BFDD", "#665780"),
)
_RC = {
    "font.family": ["DejaVu Sans"],
    "font.sans-serif": ["DejaVu Sans"],
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
    "svg.hashsalt": "BRIDGE-P0-07",
}


@dataclass(frozen=True)
class PreparedProductComparisonVisualizations:
    payloads: dict[str, bytes]
    artifacts: tuple[ArtifactManifest, ...]


@dataclass(frozen=True)
class _RecordGroup:
    label: str
    model: type
    path: str


@dataclass(frozen=True)
class _Component:
    ref: str
    slug: str
    records_path: str
    table_name: str
    title: str
    groups: tuple[_RecordGroup, ...]


@dataclass(frozen=True)
class _MethodPoint:
    axis_id: str
    task_id: str
    method_id: str
    analytical_role: str
    estimate_name: str
    value: float | None
    unit: str
    assessment_state: str
    group_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]


_COMPONENTS = (
    _Component(
        COMPARABILITY_COMPONENT_REF,
        "comparability",
        "design_records",
        "product_comparison_comparability.tsv",
        "Comparison eligibility and declared confounding structure",
        (_RecordGroup("comparison_design", ComparisonDesignRecord, "design_records"),),
    ),
    _Component(
        METRIC_DIFFERENCES_COMPONENT_REF,
        "metric-differences",
        "difference_records",
        "product_comparison_metric_differences.tsv",
        "Declared analysis-unit values and descriptive group differences",
        (
            _RecordGroup(
                "preparation_metric", PreparationMetricRecord, "preparation_records"
            ),
            _RecordGroup(
                "metric_difference", MetricDifferenceRecord, "difference_records"
            ),
            _RecordGroup(
                "metric_stability",
                MetricStabilityVisualizationRecord,
                "stability_records",
            ),
        ),
    ),
    _Component(
        METHOD_EVIDENCE_COMPONENT_REF,
        "method-evidence",
        "method_records",
        "product_comparison_method_evidence.tsv",
        "Method-specific descriptive effect, distance, and dispersion evidence",
        (_RecordGroup("method_evidence", MethodEvidenceRecord, "method_records"),),
    ),
)
_TAKEAWAYS = {
    COMPARABILITY_COMPONENT_REF: (
        "Declared equality, context and confounding checks show whether between-product "
        "numeric differences may be interpreted."
    ),
    METRIC_DIFFERENCES_COMPONENT_REF: (
        "Declared analysis-unit values, arithmetic group means, observed min-max ranges and legal "
        "raw differences remain on metric-specific axes."
    ),
    METHOD_EVIDENCE_COMPONENT_REF: (
        "Method outputs remain separated by analytical role, estimate and unit; "
        "unavailable tasks remain explicit."
    ),
}
_LIMITATIONS = {
    COMPARABILITY_COMPONENT_REF: [
        "Eligibility is conditional on supplied design metadata and is not a product-quality grade.",
        "Missing metadata is not evidence that groups match.",
        "The comparison remains descriptive and produces no score or rank.",
    ],
    METRIC_DIFFERENCES_COMPONENT_REF: [
        "Observed analysis-unit ranges are not confidence intervals.",
        "A single declared analysis unit supports description only, not stability or inference.",
        "Numeric direction does not imply quality, safety, potency, efficacy or release.",
    ],
    METHOD_EVIDENCE_COMPONENT_REF: [
        "Different methods and units are not placed on a shared scale or ranked.",
        "Method outputs are not independent biological evidence.",
        "Cells and technical captures are not biological replicates.",
    ],
}


def prepare_product_comparison_visualizations(
    *,
    profile: ProductComparisonVisualizationDataV1,
    output_dir: Path,
    run_id: str,
    tool_version: str,
) -> PreparedProductComparisonVisualizations:
    final_dir = output_dir / run_id
    payloads: dict[str, bytes] = {}
    artifacts: list[ArtifactManifest] = []
    data_name = "product_comparison_visualization_data.json"
    data_payload = canonical_json_bytes(profile.model_dump(mode="json"), indent=2)
    payloads[data_name] = data_payload
    data_artifact = _manifest(
        run_id,
        "product-comparison-visualization-data",
        "product_comparison_visualization_data",
        final_dir / data_name,
        "application/json",
        data_payload,
        profile.evidence_ids,
    )
    artifacts.append(data_artifact)

    tables: dict[str, ArtifactManifest] = {}
    renders: dict[tuple[str, str], ArtifactManifest] = {}
    render_reasons: dict[str, str | None] = {}
    renderers = {
        COMPARABILITY_COMPONENT_REF: _render_comparability,
        METRIC_DIFFERENCES_COMPONENT_REF: _render_metric_differences,
        METHOD_EVIDENCE_COMPONENT_REF: _render_method_evidence,
    }
    with matplotlib.rc_context(rc=_RC):
        for component in _COMPONENTS:
            table_payload = _table(profile, component.groups)
            payloads[component.table_name] = table_payload
            tables[component.ref] = _manifest(
                run_id,
                f"product-comparison-{component.slug}-table",
                "visualization_table",
                final_dir / component.table_name,
                "text/tab-separated-values",
                table_payload,
                profile.evidence_ids,
            )
            artifacts.append(tables[component.ref])
            reason = _static_render_reason(profile, component.ref)
            render_reasons[component.ref] = reason
            figure = (
                _empty_figure(
                    component.title,
                    "Static capacity was exceeded; the complete result is in the typed table.",
                    [reason],
                    component.ref,
                )
                if reason
                else renderers[component.ref](profile)
            )
            for extension, (media_type, render_payload) in _render_payloads(
                figure
            ).items():
                name = f"product_comparison_{component.slug}.{extension}"
                payloads[name] = render_payload
                artifact = _manifest(
                    run_id,
                    f"product-comparison-{component.slug}-{extension}",
                    "visualization_render",
                    final_dir / name,
                    media_type,
                    render_payload,
                    profile.evidence_ids,
                )
                artifacts.append(artifact)
                renders[(component.ref, extension)] = artifact

    visualizations = [
        _visualization_contract(
            profile,
            component,
            data_artifact,
            tables[component.ref],
            {
                extension: renders[(component.ref, extension)]
                for extension in ("svg", "png", "pdf")
            },
            run_id,
            tool_version,
            render_reasons[component.ref],
        )
        for component in _COMPONENTS
    ]
    registry = FigureRegistry.load_default()
    for visualization in visualizations:
        registry.validate_artifact(visualization)
    artifact_set = P007VisualizationArtifactSet(
        artifact_set_id=f"p0-07-visualizations:{run_id.removeprefix('run-')}",
        data_profile_artifact_id=data_artifact.artifact_id,
        data_profile_sha256=data_artifact.sha256,
        visualizations=visualizations,
    )
    set_name = "product_comparison_visualization_artifact_set.json"
    set_payload = canonical_json_bytes(artifact_set.model_dump(mode="json"), indent=2)
    payloads[set_name] = set_payload
    artifacts.append(
        _manifest(
            run_id,
            "product-comparison-visualization-artifact-set",
            "visualization_artifact_set",
            final_dir / set_name,
            "application/json",
            set_payload,
            profile.evidence_ids,
        )
    )
    return PreparedProductComparisonVisualizations(payloads, tuple(artifacts))


def _table(profile, groups):
    fields, rows = ["record_type"], []
    for group in groups:
        fields.extend(name for name in group.model.model_fields if name not in fields)
        rows.extend(
            {"record_type": group.label, **row.model_dump(mode="json")}
            for row in getattr(profile, group.path)
        )
    buffer = StringIO(newline="")
    writer = csv.DictWriter(
        buffer, fieldnames=fields, delimiter="\t", lineterminator="\n"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _table_cell(value) for key, value in row.items()})
    return buffer.getvalue().encode()


def _table_cell(value):
    if isinstance(value, (list, dict)):
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    return "" if value is None else value


def _static_render_reason(profile, ref):
    groups = _group_ids(profile)
    if ref == COMPARABILITY_COMPONENT_REF:
        too_large = len(groups) > 4 or len(profile.design_records) > 16
    elif ref == METRIC_DIFFERENCES_COMPONENT_REF:
        too_large = len(groups) > 4 or len(profile.difference_records) > 8
    else:
        points = _method_points(profile.method_records)
        axes = {point.axis_id for point in points}
        too_large = len(points) > 24 or len(axes) > 10
    return "static_render_requires_table_fallback" if too_large else None


def _base(title, subtitle, height, ref):
    figure = plt.figure(figsize=(_WIDTH, height), facecolor=_BACKGROUND)
    figure.text(
        0.045, 0.965, title, fontsize=11.1, fontweight="bold", color=_TEXT, va="top"
    )
    if subtitle:
        figure.text(0.045, 0.918, subtitle, fontsize=7.5, color=_MUTED, va="top")
    figure.text(
        0.045,
        0.025,
        textwrap.fill(_footnote(ref), width=106),
        fontsize=6.35,
        color=_MUTED,
        va="bottom",
        linespacing=1.18,
    )
    return figure


def _empty_figure(title, message, reasons, ref):
    figure = _base(title, "", 4.7, ref)
    axis = figure.add_axes((0.075, 0.18, 0.85, 0.60))
    axis.axis("off")
    axis.text(0, 0.72, "—  not assessed", fontsize=14, fontweight="bold", color=_MUTED)
    axis.text(0, 0.48, message, fontsize=9.2, color=_TEXT)
    axis.text(
        0,
        0.27,
        textwrap.fill(" · ".join(_label(reason) for reason in reasons if reason), 94),
        fontsize=7.2,
        color=_MUTED,
        va="top",
    )
    return figure


def _render_comparability(profile):
    records = sorted(
        profile.design_records,
        key=lambda row: (_dimension_rank(row.dimension_kind), row.dimension_id),
    )
    if not records:
        return _empty_figure(
            _COMPONENTS[0].title,
            "Comparison design and confounding metadata were not assessed.",
            ["comparison_design_not_assessed"],
            COMPARABILITY_COMPONENT_REF,
        )
    groups = _group_ids(profile)
    roles = _group_roles(profile)
    eligibility = _value(profile.comparison_eligibility)
    figure = _base(
        _COMPONENTS[0].title,
        f"Interpretation: {_eligibility_text(eligibility)} · declared metadata only",
        max(5.2, 3.10 + 0.48 * len(records)),
        COMPARABILITY_COMPONENT_REF,
    )
    axis = figure.add_axes((0.035, 0.135, 0.93, 0.69))
    axis.set(xlim=(0, 1), ylim=(-0.75, len(records) + 1.05))
    axis.axis("off")
    left, right, status_start = 0.02, 0.985, 0.84
    group_start = 0.30
    group_width = (status_start - group_start) / max(len(groups), 1)
    axis.text(
        left,
        len(records) + 0.46,
        "Declared comparison condition",
        fontsize=6.6,
        fontweight="bold",
        color=_TEXT,
        va="center",
    )
    for index, group_id in enumerate(groups):
        center = group_start + group_width * (index + 0.5)
        axis.text(
            center,
            len(records) + 0.58,
            _display_id(group_id),
            fontsize=6.5,
            fontweight="bold",
            color=_TEXT,
            ha="center",
            va="center",
        )
        axis.text(
            center,
            len(records) + 0.25,
            _label(roles.get(group_id, "declared group")),
            fontsize=5.8,
            color=_MUTED,
            ha="center",
            va="center",
        )
    axis.text(
        (status_start + right) / 2,
        len(records) + 0.46,
        "Assessment",
        fontsize=6.6,
        fontweight="bold",
        color=_TEXT,
        ha="center",
        va="center",
    )
    axis.plot([left, right], [len(records) + 0.02] * 2, color=_TEXT, linewidth=0.8)
    for edge in (group_start, status_start, right):
        axis.plot(
            [edge, edge], [-0.48, len(records) + 0.72], color=_GRID, linewidth=0.55
        )
    for index, record in enumerate(records):
        y = len(records) - index - 1
        if index % 2:
            axis.add_patch(
                Rectangle(
                    (left, y - 0.43),
                    right - left,
                    0.86,
                    facecolor=_ROW,
                    edgecolor="none",
                    zorder=-2,
                )
            )
        axis.plot([left, right], [y - 0.43] * 2, color=_GRID, linewidth=0.45)
        axis.text(
            left,
            y + 0.10,
            textwrap.fill(_display_id(record.dimension_id), width=25),
            fontsize=6.5,
            fontweight="bold",
            color=_TEXT,
            va="center",
        )
        axis.text(
            left,
            y - 0.22,
            _dimension_label(record.dimension_kind),
            fontsize=5.7,
            color=_MUTED,
            va="center",
        )
        values = {item.group_id: item.values for item in record.values_by_group}
        for group_index, group_id in enumerate(groups):
            center = group_start + group_width * (group_index + 0.5)
            axis.text(
                center,
                y,
                _value_lines(values.get(group_id, [])),
                fontsize=5.8,
                color=_TEXT if values.get(group_id) else _MUTED,
                ha="center",
                va="center",
                linespacing=1.04,
            )
        marker, color, state_label = _assessment_style(record)
        center = status_start + 0.027
        hollow = record.design_state in {
            "metadata_missing",
            "not_recorded",
            "inconsistent",
        }
        axis.scatter(
            center,
            y,
            s=29,
            marker=marker,
            facecolor=_BACKGROUND if hollow else color,
            edgecolor=color,
            linewidth=0.9,
        )
        axis.text(
            center + 0.025,
            y,
            textwrap.fill(state_label, width=17),
            fontsize=5.9,
            color=_TEXT if record.design_state == "matched" else _MUTED,
            va="center",
        )
    return figure


def _render_metric_differences(profile):
    differences = sorted(
        profile.difference_records,
        key=lambda row: (
            row.unit,
            row.denominator_kind,
            row.metric_id,
            row.comparator_group_id,
        ),
    )
    if not differences:
        return _empty_figure(
            _COMPONENTS[1].title,
            "No metric contrast records were produced; supplied analysis-unit records remain in the table.",
            ["metric_differences_not_assessed"],
            METRIC_DIFFERENCES_COMPONENT_REF,
        )
    contextual = _value(profile.comparison_eligibility) == "contextual_comparator"
    subtitle = (
        "Declared analysis-unit points · diamonds are arithmetic group means · lines are observed min-max, not confidence intervals"
        + (" · contextual comparison only" if contextual else "")
    )
    figure = _base(
        _COMPONENTS[1].title,
        subtitle,
        max(5.3, 2.95 + 1.32 * len(differences)),
        METRIC_DIFFERENCES_COMPONENT_REF,
    )
    grid = figure.add_gridspec(
        len(differences),
        2,
        left=0.19,
        right=0.965,
        bottom=0.18,
        top=0.82,
        width_ratios=(2.25, 1.0),
        wspace=0.31,
        hspace=1.03,
    )
    colors = _group_color_map(profile)
    for index, difference in enumerate(differences):
        absolute = figure.add_subplot(grid[index, 0])
        delta = figure.add_subplot(grid[index, 1])
        _metric_absolute_axis(absolute, profile, difference, colors)
        _metric_delta_axis(delta, difference, colors, contextual)
    return figure


def _metric_absolute_axis(axis, profile, difference, colors):
    group_ids = (difference.baseline_group_id, difference.comparator_group_id)
    preparation_by_id = {row.record_id: row for row in profile.preparation_records}
    stability_by_id = {row.record_id: row for row in profile.stability_records}
    linked_preparations = [
        preparation_by_id[record_id]
        for record_id in difference.preparation_record_ids
    ]
    linked_stability = [
        stability_by_id[record_id] for record_id in difference.stability_record_ids
    ]
    rows_by_group = {
        group_id: [
            row for row in linked_preparations if row.group_id == group_id
        ]
        for group_id in group_ids
    }
    stability_by_group = {row.group_id: row for row in linked_stability}
    values = [
        float(row.raw_value)
        for rows in rows_by_group.values()
        for row in rows
        if row.raw_value is not None and row.assessment_state == "available"
    ]
    low, high = _numeric_limits(values)
    axis.set(xlim=(low, high), ylim=(-0.65, 1.65))
    axis.set_yticks((1, 0))
    axis.set_yticklabels(
        [
            f"{_display_id(group_id)}\n{_analysis_unit_summary(rows_by_group[group_id])}"
            for group_id in group_ids
        ],
        fontsize=5.9,
    )
    axis.tick_params(axis="y", length=0, pad=5, colors=_TEXT)
    axis.tick_params(axis="x", labelsize=5.9, colors=_MUTED)
    _clean_axis(axis)
    axis.set_title(
        f"{_display_id(difference.metric_id)}\n{_label(difference.denominator_kind)}",
        fontsize=6.8,
        fontweight="bold",
        loc="left",
        color=_TEXT,
        pad=4,
    )
    axis.set_xlabel(_label(difference.unit), fontsize=5.9, color=_MUTED, labelpad=2)
    means = {
        difference.baseline_group_id: difference.baseline_value,
        difference.comparator_group_id: difference.comparator_value,
    }
    for y, group_id in zip((1, 0), group_ids, strict=True):
        rows = [
            row
            for row in rows_by_group[group_id]
            if row.raw_value is not None and row.assessment_state == "available"
        ]
        fill, edge = colors[group_id]
        if not rows:
            axis.text(
                0.03,
                y,
                "— unavailable",
                transform=blended_transform_factory(axis.transAxes, axis.transData),
                fontsize=6.2,
                color=_MUTED,
                va="center",
            )
            continue
        row_values = [float(row.raw_value) for row in rows]
        stability = stability_by_group[group_id]
        if stability.assessed_analysis_unit_count > 1:
            axis.plot(
                [float(stability.observed_min), float(stability.observed_max)],
                [y, y],
                color=edge,
                linewidth=1.5,
                solid_capstyle="round",
                zorder=1,
            )
        offsets = _point_offsets(len(row_values))
        axis.scatter(
            row_values,
            [y + offset for offset in offsets],
            s=18,
            marker="o",
            facecolor=fill,
            edgecolor=edge,
            linewidth=0.65,
            zorder=2,
        )
        if means[group_id] is not None:
            axis.scatter(
                float(means[group_id]),
                y,
                s=35,
                marker="D",
                facecolor=_BACKGROUND,
                edgecolor=edge,
                linewidth=1.15,
                zorder=3,
            )


def _metric_delta_axis(axis, difference, colors, contextual):
    axis.set_ylim((-0.6, 0.6))
    axis.set_yticks([])
    axis.tick_params(axis="x", labelsize=5.9, colors=_MUTED)
    _clean_axis(axis)
    axis.set_title(
        "Comparator minus baseline",
        fontsize=6.4,
        fontweight="bold",
        loc="left",
        color=_TEXT,
        pad=4,
    )
    state = _value(difference.comparison_state)
    if difference.raw_delta is None or difference.assessment_state != "available":
        axis.set(xlim=(0, 1))
        axis.axis("off")
        axis.text(0, 0.14, f"— {_label(state)}", fontsize=6.5, color=_MUTED)
        reason = " · ".join(_label(item) for item in difference.reason_codes[:2])
        axis.text(
            0,
            -0.12,
            textwrap.fill(reason, 38),
            fontsize=5.5,
            color=_MUTED,
            va="top",
        )
        return
    value = float(difference.raw_delta)
    extent = max(abs(value) * 1.45, 0.1)
    axis.set_xlim((-extent, extent))
    axis.axvline(0, color=_GRID, linewidth=0.8, zorder=0)
    fill, edge = colors[difference.comparator_group_id]
    axis.scatter(
        value,
        0,
        s=36,
        facecolor=fill,
        edgecolor=edge,
        linewidth=0.9,
        zorder=2,
    )
    axis.annotate(
        f"{value:+.3g}",
        (value, 0),
        xytext=(0, 9),
        textcoords="offset points",
        ha="center",
        fontsize=6.5,
        fontweight="bold",
        color=_TEXT,
    )
    axis.set_xlabel(_label(difference.unit), fontsize=5.9, color=_MUTED, labelpad=2)
    if contextual:
        for spine in axis.spines.values():
            spine.set_linestyle((0, (3, 2)))
        axis.text(
            0.99,
            0.05,
            "context only",
            transform=axis.transAxes,
            ha="right",
            fontsize=5.5,
            color=_MUTED,
        )


def _render_method_evidence(profile):
    points = _method_points(profile.method_records)
    if not points:
        return _empty_figure(
            _COMPONENTS[2].title,
            "Method runtime was not supplied or no method estimate was assessable.",
            ["method_runtime_not_supplied"],
            METHOD_EVIDENCE_COMPONENT_REF,
        )
    axes: dict[str, list[_MethodPoint]] = {}
    for point in points:
        axes.setdefault(point.axis_id, []).append(point)
    ordered = sorted(axes.items(), key=lambda item: _method_axis_sort(item[1][0]))
    ncols = 2 if len(ordered) > 1 else 1
    nrows = math.ceil(len(ordered) / ncols)
    figure = _base(
        _COMPONENTS[2].title,
        "Each analytical task, estimate and unit retains its own axis · open rows are not assessed, not zero",
        max(5.2, 3.10 + 2.15 * nrows),
        METHOD_EVIDENCE_COMPONENT_REF,
    )
    grid = figure.add_gridspec(
        nrows,
        ncols,
        left=0.19,
        right=0.965,
        bottom=0.14,
        top=0.82,
        wspace=0.58,
        hspace=0.96,
    )
    colors = _group_color_map(profile)
    for index, (_, axis_points) in enumerate(ordered):
        axis = figure.add_subplot(grid[index // ncols, index % ncols])
        _method_axis(axis, axis_points, colors)
    if len(ordered) % ncols:
        figure.add_subplot(grid[-1, -1]).axis("off")
    return figure


def _method_points(records):
    points: list[_MethodPoint] = []
    raw_seen = set()
    for record in records:
        method = _value(record.method_id)
        points.append(
            _MethodPoint(
                axis_id=record.display_axis_id,
                task_id=record.task_id,
                method_id=method,
                analytical_role=_value(record.analytical_role),
                estimate_name=record.estimate_name or f"{method} assessment",
                value=(
                    float(record.estimate_value)
                    if record.estimate_value is not None
                    else None
                ),
                unit=record.estimate_unit or "not assessed",
                assessment_state=_value(record.assessment_state),
                group_ids=tuple(record.group_ids),
                reason_codes=tuple(record.reason_codes),
            )
        )
        raw_key = (record.task_id, record.raw_delta_unit)
        if record.raw_delta is not None and raw_key not in raw_seen:
            raw_seen.add(raw_key)
            unit = record.raw_delta_unit or "declared metric unit"
            points.append(
                _MethodPoint(
                    axis_id=f"{record.task_id}:raw_delta:{unit}",
                    task_id=record.task_id,
                    method_id=method,
                    analytical_role="raw_group_difference",
                    estimate_name="raw comparator-minus-baseline difference",
                    value=float(record.raw_delta),
                    unit=unit,
                    assessment_state="available",
                    group_ids=tuple(record.group_ids),
                    reason_codes=(),
                )
            )
    return points


def _method_axis(axis, points, colors):
    points = sorted(points, key=lambda point: point.task_id)
    values = [point.value for point in points if point.value is not None]
    low, high = _method_limits(points[0].estimate_name, values)
    axis.set(xlim=(low, high), ylim=(-0.65, len(points) - 0.35))
    ys = list(reversed(range(len(points))))
    axis.set_yticks(ys, [_display_id(point.task_id) for point in points], fontsize=5.8)
    axis.tick_params(axis="y", length=0, pad=4, colors=_TEXT)
    axis.tick_params(axis="x", labelsize=5.8, colors=_MUTED)
    _clean_axis(axis)
    if low < 0 < high:
        axis.axvline(0, color=_GRID, linewidth=0.75, zorder=0)
    first = points[0]
    axis.set_title(
        f"{_label(first.estimate_name)}\n{_method_label(first.method_id)}",
        fontsize=6.6,
        fontweight="bold",
        loc="left",
        color=_TEXT,
        pad=4,
    )
    axis.set_xlabel(_label(first.unit), fontsize=5.8, color=_MUTED, labelpad=2)
    transform = blended_transform_factory(axis.transAxes, axis.transData)
    for y, point in zip(ys, points, strict=True):
        if point.value is None or point.assessment_state != "available":
            axis.text(
                0.02,
                y,
                "— not assessed",
                transform=transform,
                fontsize=6.0,
                color=_MUTED,
                va="center",
            )
            if point.reason_codes:
                axis.text(
                    0.98,
                    y,
                    textwrap.shorten(_label(point.reason_codes[0]), 34),
                    transform=transform,
                    fontsize=5.2,
                    color=_MUTED,
                    ha="right",
                    va="center",
                )
            continue
        group_id = point.group_ids[-1] if point.group_ids else "method"
        fill, edge = colors.get(group_id, _GROUP_COLORS[0])
        axis.scatter(
            point.value,
            y,
            s=31,
            facecolor=fill,
            edgecolor=edge,
            linewidth=0.9,
            zorder=2,
        )
        axis.annotate(
            f"{point.value:.3g}",
            (point.value, y),
            xytext=(5, 0),
            textcoords="offset points",
            fontsize=5.8,
            color=_TEXT,
            va="center",
        )


def _visualization_contract(
    profile,
    component,
    data_artifact,
    table_artifact,
    render_artifacts,
    run_id,
    tool_version,
    render_reason,
):
    records = _component_records(profile, component.ref)
    evidence_states = sorted({_value(row.evidence_state) for row in records}) or [
        "unavailable"
    ]
    reasons = {reason for row in records for reason in row.reason_codes}
    if not records:
        reasons.add(
            "method_runtime_not_supplied"
            if component.ref == METHOD_EVIDENCE_COMPONENT_REF
            else f"{component.slug.replace('-', '_')}_not_assessed"
        )
    if render_reason:
        reasons.add(render_reason)
    if {"missing", "unknown", "unavailable"}.intersection(
        evidence_states
    ) and not reasons:
        reasons.add(f"{component.slug.replace('-', '_')}_evidence_unavailable")
    binding = {
        COMPARABILITY_COMPONENT_REF: {"value_field": "assessment_state"},
        METRIC_DIFFERENCES_COMPONENT_REF: {
            "value_field": "raw_delta",
            "unit_field": "unit",
        },
        METHOD_EVIDENCE_COMPONENT_REF: {
            "value_field": "estimate_value",
            "unit_field": "estimate_unit",
        },
    }[component.ref]
    data_binding = VisualizationDataBinding(
        artifact_id=data_artifact.artifact_id,
        schema_ref=PRODUCT_COMPARISON_VISUALIZATION_DATA_SCHEMA_REF,
        object_version="0.1.0",
        sha256=data_artifact.sha256,
        records_path=component.records_path,
        record_lookup_key="record_id",
        evidence_ids_field="evidence_ids",
        evidence_state_field="evidence_state",
        scientific_status_field="scientific_status",
        missingness_field="missingness",
        applicability_field="applicability",
        **binding,
    )
    component_id, component_version = component.ref.split("@", 1)
    takeaway = _TAKEAWAYS[component.ref]
    return VisualizationArtifactV2(
        visualization_id=f"visualization:{run_id}:{component.slug}",
        component_id=component_id,
        component_version=component_version,
        data_binding=data_binding,
        producer_tool_id="P0-07",
        producer_tool_version=tool_version,
        producer_run_ref=f"run:{run_id}",
        evidence_ids=profile.evidence_ids,
        evidence_states=evidence_states,
        scientific_status="candidate",
        applicability=_component_applicability(records, render_reason),
        missing_reason_codes=sorted(reasons),
        insight_title=component.title,
        takeaway=takeaway,
        limitations=_LIMITATIONS[component.ref],
        accessibility=VisualizationAccessibility(
            alt_text=f"{component.title}. {takeaway}",
            long_description=(
                f"{component.title}. {takeaway} The typed table preserves every value, "
                "assessment state, reason code, unit and evidence reference."
            ),
            table_artifact_id=table_artifact.artifact_id,
            data_sha256=data_artifact.sha256,
        ),
        renders=[
            VisualizationRenderBinding(
                artifact_id=render_artifacts[extension].artifact_id,
                media_type=render_artifacts[extension].media_type,
                renderer_id=_RENDERER_ID,
                renderer_version=_RENDERER_VERSION,
                export_profile_id=_EXPORT_PROFILE_ID,
                data_sha256=data_artifact.sha256,
                config_sha256=_config_hash(component.ref),
            )
            for extension in ("svg", "png", "pdf")
        ],
    )


def _component_records(profile, ref):
    if ref == COMPARABILITY_COMPONENT_REF:
        return list(profile.design_records)
    if ref == METRIC_DIFFERENCES_COMPONENT_REF:
        return [
            *profile.preparation_records,
            *profile.difference_records,
            *profile.stability_records,
        ]
    return list(profile.method_records)


def _component_applicability(records, render_reason):
    if not records:
        return "not_assessed"
    states = {_value(row.applicability) for row in records}
    if render_reason or len(states) > 1:
        return "partially_applicable"
    state = states.pop()
    allowed = {
        "applicable",
        "partially_applicable",
        "not_assessed",
        "not_applicable",
    }
    return state if state in allowed else "partially_applicable"


def _render_payloads(figure):
    outputs = {}
    try:
        for extension, media_type in (
            ("svg", "image/svg+xml"),
            ("png", "image/png"),
            ("pdf", "application/pdf"),
        ):
            buffer = BytesIO()
            metadata = {"Creator": "BRIDGE"}
            if extension == "svg":
                metadata["Date"] = None
                figure.savefig(buffer, format="svg", metadata=metadata)
            elif extension == "png":
                figure.savefig(
                    buffer,
                    format="png",
                    dpi=220,
                    metadata={"Software": "BRIDGE"},
                )
            else:
                metadata.update({"CreationDate": None, "ModDate": None})
                figure.savefig(buffer, format="pdf", metadata=metadata)
            outputs[extension] = (media_type, buffer.getvalue())
    finally:
        plt.close(figure)
    return outputs


def _group_ids(profile):
    roles = _group_roles(profile)
    values = set(roles)
    for row in profile.design_records:
        values.update(item.group_id for item in row.values_by_group)
    for row in profile.difference_records:
        values.update((row.baseline_group_id, row.comparator_group_id))
    rank = {"baseline": 0, "comparator": 1, "reference_ood": 2}
    return sorted(values, key=lambda value: (rank.get(roles.get(value, ""), 9), value))


def _group_roles(profile):
    return {row.group_id: _value(row.group_role) for row in profile.preparation_records}


def _group_color_map(profile):
    return {
        group_id: _GROUP_COLORS[index % len(_GROUP_COLORS)]
        for index, group_id in enumerate(_group_ids(profile))
    }


def _assessment_style(record):
    state = record.design_state
    return {
        "matched": ("o", "#4F858D", "matched"),
        "required_mismatch": ("X", "#735A78", "required values differ"),
        "contextual_mismatch": ("^", "#C08A43", "context differs"),
        "metadata_missing": ("o", "#929A9F", "metadata missing"),
        "completely_confounded": ("X", "#735A78", "completely confounded"),
        "overlap_present": ("D", "#6C7A89", "declared overlap (confounder)"),
        "declared": ("o", "#4F858D", "declared"),
        "not_recorded": ("o", "#929A9F", "not recorded"),
        "inconsistent": ("D", "#929A9F", "inconsistent"),
    }[state]


def _dimension_rank(value):
    return {
        "required_equal": 0,
        "contextual": 1,
        "confounder": 2,
        "independence": 3,
    }.get(_value(value), 9)


def _dimension_label(value):
    return {
        "required_equal": "required to match",
        "contextual": "declared context",
        "confounder": "declared confounder",
        "independence": "analysis-unit independence",
    }.get(_value(value), _label(value))


def _eligibility_text(value):
    return {
        "strictly_comparable": "descriptive numeric differences are supported by the supplied contract",
        "contextual_comparator": "numeric differences are contextual, not a like-for-like comparison",
        "reference_or_ood": "reference/OOD context only; no between-product difference is estimated",
        "not_comparable": "groups may be shown side by side, but no numeric difference is estimated",
        "not_estimable": "declared confounding prevents attribution of a numeric difference",
    }.get(value, _label(value))


def _value_lines(values):
    if not values:
        return "— not supplied"
    return "\n".join(textwrap.fill(_display_id(value), width=18) for value in values)


def _numeric_limits(values):
    if not values:
        return -1.0, 1.0
    low, high = min(values), max(values)
    pad = max((high - low) * 0.13, abs(low) * 0.04, abs(high) * 0.04, 0.05)
    return low - pad, high + pad


def _analysis_unit_summary(rows):
    assessed = [
        row
        for row in rows
        if row.raw_value is not None and row.assessment_state == "available"
    ]
    kinds = {_value(row.source_unit_kind) for row in rows}
    noun = next(iter(kinds)) if len(kinds) == 1 else "analysis unit"
    total = len(rows)
    if not assessed:
        return f"no assessed {noun}s"
    if len(assessed) < total:
        return f"n={len(assessed)}/{total} assessed {noun}s"
    suffix = "" if len(assessed) == 1 else "s"
    return f"n={len(assessed)} {noun}{suffix}"


def _point_offsets(count):
    if count <= 1:
        return [0.0] * count
    width = min(0.20, 0.025 * (count - 1))
    step = (2 * width) / (count - 1)
    return [-width + index * step for index in range(count)]


def _method_limits(name, values):
    label = name.lower().replace("_", " ").replace("-", " ")
    if "spearman" in label or "rho" in label:
        return -1.0, 1.0
    if "jensen" in label:
        return 0.0, 1.0
    if any(word in label for word in ("distance", "coefficient", "deviation ratio")):
        high = max(values, default=1.0)
        return 0.0, max(high * 1.25, 0.1)
    extent = max((abs(value) for value in values), default=1.0)
    return -max(extent * 1.25, 0.1), max(extent * 1.25, 0.1)


def _method_axis_sort(point):
    return (point.analytical_role, point.method_id, point.estimate_name, point.unit)


def _method_label(value):
    return {
        "CMP-EFFECT": "sample-level effect",
        "CMP-JS": "Jensen-Shannon distance",
        "CMP-CORR": "Spearman profile agreement",
        "CMP-WASS-1D": "one-dimensional Wasserstein distance",
        "STAB-CV": "robust descriptive dispersion",
    }.get(value, _label(value))


def _clean_axis(axis):
    axis.grid(False)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["left"].set_visible(False)
    axis.spines["bottom"].set_color(_GRID)
    axis.spines["bottom"].set_linewidth(0.7)


def _footnote(ref):
    prefix = "— = not assessed/unavailable; ? = unknown; neither means zero. "
    if ref == COMPARABILITY_COMPONENT_REF:
        return (
            prefix
            + "Eligibility is conditional on supplied metadata and is not a quality, release or ranking decision."
        )
    if ref == METRIC_DIFFERENCES_COMPONENT_REF:
        return (
            prefix
            + "Points are observed analysis units; lines are observed min-max ranges, not confidence intervals. Independence is not assumed unless explicitly declared; a single analysis unit is descriptive only."
        )
    return (
        prefix
        + "Each task, estimate and unit has its own scale. Methods are not ranked or counted as independent evidence; cells are not biological replicates."
    )


def _config_hash(ref):
    source = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    payload = canonical_json_bytes(
        {
            "component_ref": ref,
            "renderer": [_RENDERER_ID, _RENDERER_VERSION, _EXPORT_PROFILE_ID],
            "source_sha256": source,
            "matplotlib_version": matplotlib.__version__,
            "matplotlib_rc": _RC,
            "group_colors": _GROUP_COLORS,
            "figure_width_in": _WIDTH,
        }
    )
    return hashlib.sha256(payload).hexdigest()


def _display_id(value):
    return str(value).rsplit(":", 1)[-1]


def _label(value):
    return _value(value).replace("_", " ").replace("-", " ")


def _value(value):
    return str(getattr(value, "value", value))


def _manifest(run_id, suffix, kind, path, media_type, payload, evidence_ids):
    return ArtifactManifest(
        artifact_id=f"artifact:{run_id}:{suffix}",
        kind=kind,
        path=path,
        media_type=media_type,
        sha256=hashlib.sha256(payload).hexdigest(),
        evidence_ids=evidence_ids,
    )
