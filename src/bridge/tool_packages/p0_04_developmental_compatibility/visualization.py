from __future__ import annotations

import csv
from dataclasses import dataclass
from io import BytesIO, StringIO
import hashlib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import numpy as np

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_04_developmental_compatibility.roles import (
    DevelopmentStageRole,
)
from bridge.tool_packages.p0_04_developmental_compatibility.visualization_data import (
    DEVELOPMENTAL_VISUALIZATION_DATA_SCHEMA_REF,
    P004VisualizationArtifactSet,
    REFERENCE_COMPONENT_REF,
    STAGE_COMPONENT_REF,
    TIMEPOINT_COMPONENT_REF,
    DevelopmentalCompatibilityVisualizationDataV1,
)
from bridge.toolkit.contracts import ArtifactManifest, EvidenceState
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
_BACKGROUND = "#FBFAF7"
_TEXT = "#25323A"
_MUTED = "#64727B"
_GRID = "#DDE3E5"
_STAGE_COLORS = {
    DevelopmentStageRole.EARLIER: "#8FBBD3",
    DevelopmentStageRole.WITHIN_WINDOW: "#62AA9D",
    DevelopmentStageRole.LATER: "#E2A66A",
    DevelopmentStageRole.BRANCH_SHIFT: "#B59AC7",
    DevelopmentStageRole.UNRESOLVED: "#AAB4BD",
}
_ROLE_ORDER = (
    DevelopmentStageRole.EARLIER,
    DevelopmentStageRole.WITHIN_WINDOW,
    DevelopmentStageRole.LATER,
    DevelopmentStageRole.BRANCH_SHIFT,
    DevelopmentStageRole.UNRESOLVED,
)
_ORDERED_ROLES = frozenset(_ROLE_ORDER[:3])
_MATPLOTLIB_RC = {
    "font.family": ["DejaVu Sans"],
    "font.sans-serif": ["DejaVu Sans"],
    "axes.titleweight": "bold",
    "pdf.fonttype": 42,
    "svg.fonttype": "path",
    "svg.hashsalt": "BRIDGE-P0-04",
}


@dataclass(frozen=True)
class PreparedDevelopmentalCompatibilityVisualizations:
    payloads: dict[str, bytes]
    artifacts: tuple[ArtifactManifest, ...]


@dataclass(frozen=True)
class _Component:
    ref: str
    slug: str
    records_path: str
    table_name: str
    render_title: str


_COMPONENTS = (
    _Component(
        STAGE_COMPONENT_REF,
        "window-composition",
        "stage_records",
        "developmental_compatibility_window_composition.tsv",
        "Cell-state composition relative to the declared developmental window",
    ),
    _Component(
        REFERENCE_COMPONENT_REF,
        "reference-stage-summary",
        "reference_records",
        "developmental_compatibility_reference_stage_summary.tsv",
        "Highest expression-similarity labels in each selected reference (uncalibrated)",
    ),
    _Component(
        TIMEPOINT_COMPONENT_REF,
        "observed-sampling-points",
        "sampling_point_records",
        "developmental_compatibility_observed_sampling_points.tsv",
        "Cell-state composition across declared product sampling points",
    ),
)


def prepare_developmental_compatibility_visualizations(
    *,
    profile: DevelopmentalCompatibilityVisualizationDataV1,
    output_dir: Path,
    run_id: str,
    tool_version: str,
) -> PreparedDevelopmentalCompatibilityVisualizations:
    final_dir = output_dir / run_id
    payloads: dict[str, bytes] = {}
    artifacts: list[ArtifactManifest] = []

    data_name = "developmental_compatibility_visualization_data.json"
    data_payload = canonical_json_bytes(profile.model_dump(mode="json"), indent=2)
    payloads[data_name] = data_payload
    data_artifact = _manifest(
        run_id,
        "developmental-compatibility-visualization-data",
        "developmental_compatibility_visualization_data",
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
            table_payload = _table(profile, component)
            payloads[component.table_name] = table_payload
            table_artifact = _manifest(
                run_id,
                f"developmental-{component.slug}-table",
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
                    component.render_title,
                    "The exact result is available in the typed JSON and table.",
                    [render_reason],
                )
            elif component.ref == STAGE_COMPONENT_REF:
                figure = _render_stage_figure(profile)
            elif component.ref == REFERENCE_COMPONENT_REF:
                figure = _render_reference_figure(profile)
            else:
                figure = _render_timepoint_figure(profile)

            for extension, (media_type, payload) in _render_payloads(figure).items():
                name = f"developmental_compatibility_{component.slug}.{extension}"
                payloads[name] = payload
                artifact = _manifest(
                    run_id,
                    f"developmental-{component.slug}-{extension}",
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

    artifact_set = P004VisualizationArtifactSet(
        artifact_set_id=f"p0-04-visualizations:{run_id.removeprefix('run-')}",
        data_profile_artifact_id=data_artifact.artifact_id,
        data_profile_sha256=data_artifact.sha256,
        visualizations=visualizations,
    )
    artifact_set_name = "developmental_compatibility_visualization_artifact_set.json"
    artifact_set_payload = canonical_json_bytes(
        artifact_set.model_dump(mode="json"), indent=2
    )
    payloads[artifact_set_name] = artifact_set_payload
    artifacts.append(
        _manifest(
            run_id,
            "developmental-compatibility-visualization-artifact-set",
            "visualization_artifact_set",
            final_dir / artifact_set_name,
            "application/json",
            artifact_set_payload,
            profile.evidence_ids,
        )
    )
    return PreparedDevelopmentalCompatibilityVisualizations(
        payloads=payloads,
        artifacts=tuple(artifacts),
    )


def _table(profile, component):
    fields = [
        "assessment_state",
        "assessment_applicability",
        "assessment_reason_codes",
        "record_type",
        *_table_fields(component.ref),
    ]
    state, applicability, reasons = _component_assessment(
        profile,
        component.ref,
    )
    records = list(getattr(profile, component.records_path))
    rows = [
        {
            "record_type": {
                STAGE_COMPONENT_REF: "stage_role",
                REFERENCE_COMPONENT_REF: "reference_stage_similarity",
                TIMEPOINT_COMPONENT_REF: "sampling_point",
            }[component.ref],
            **record.model_dump(mode="json"),
        }
        for record in records
    ]
    if component.ref == STAGE_COMPONENT_REF:
        rows.extend(
            {
                "record_type": "cell_state_resolution",
                "record_id": record.record_id,
                "component_ref": STAGE_COMPONENT_REF,
                "unit": "observations",
                "denominator_kind": "whole_product",
                "denominator_label": "All evaluated observations",
                "display_name": record.display_name,
                "numerator": record.count,
                "denominator": record.denominator,
                "fraction": record.fraction,
                "denominator_scope": "selected_data_view",
                "interval_state": "not_estimable",
                "evidence_state": "inferred",
                "missingness": "available",
                "scientific_status": "candidate",
                "applicability": (
                    "applicable"
                    if profile.window_review_state == "confirmed"
                    else "partially_applicable"
                ),
                "reason_codes": [],
                "evidence_ids": record.evidence_ids,
                "resolution_state": record.resolution_state,
            }
            for record in profile.resolution_records
        )
    elif component.ref == REFERENCE_COMPONENT_REF:
        rows.extend(
            {
                "record_type": "registered_reference_stage",
                "component_ref": REFERENCE_COMPONENT_REF,
                **record.model_dump(mode="json"),
            }
            for record in profile.registered_reference_stages
        )
    if not rows:
        rows = [{}]

    output = StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=fields,
        delimiter="	",
        lineterminator="\n",
        extrasaction="ignore",
    )
    writer.writeheader()
    for row in rows:
        payload = {
            "assessment_state": state,
            "assessment_applicability": applicability,
            "assessment_reason_codes": reasons,
            **row,
        }
        writer.writerow(
            {field: _table_value(payload.get(field)) for field in fields}
        )
    return output.getvalue().encode("utf-8")


def _component_assessment(profile, component_ref):
    if component_ref == STAGE_COMPONENT_REF:
        state = profile.stage_composition_state
        base_applicability = (
            "applicable"
            if profile.window_review_state == "confirmed"
            else "partially_applicable"
        )
        reasons = set(profile.stage_composition_reason_codes)
        records = profile.stage_records
    elif component_ref == REFERENCE_COMPONENT_REF:
        state = profile.reference_support_state
        base_applicability = profile.reference_support_applicability
        reasons = set(profile.reference_support_reason_codes)
        records = profile.reference_records
    else:
        state = profile.sampling_point_state
        reasons = {
            *profile.sampling_point_reason_codes,
            profile.continuous_time_reason_code,
        }
        records = profile.sampling_point_records
        timepoint_count = len({record.timepoint_id for record in records})
        base_applicability = "applicable" if timepoint_count >= 2 else "not_assessed"
        if timepoint_count == 1:
            reasons.add("single_sampling_point_dynamic_change_unavailable")
        elif timepoint_count == 0:
            reasons.add(
                "timepoint_series_not_supplied"
                if profile.timepoint_series_ref is None
                else "sampling_point_composition_unavailable"
            )

    reasons.update(
        reason
        for record in records
        for reason in record.reason_codes
    )
    if not records:
        return state, "not_assessed", sorted(reason for reason in reasons if reason)

    record_applicability = {record.applicability for record in records}
    if record_applicability == {"applicable"}:
        records_state = "applicable"
    elif record_applicability == {"not_assessed"}:
        records_state = "not_assessed"
    else:
        records_state = "partially_applicable"
    if "not_assessed" in {base_applicability, records_state}:
        applicability = (
            "not_assessed"
            if base_applicability == records_state == "not_assessed"
            else "partially_applicable"
        )
    elif "partially_applicable" in {base_applicability, records_state}:
        applicability = "partially_applicable"
    else:
        applicability = "applicable"
    if component_ref == TIMEPOINT_COMPONENT_REF and timepoint_count < 2:
        applicability = "not_assessed"
    return state, applicability, sorted(reason for reason in reasons if reason)

def _table_value(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return value


def _table_fields(component_ref):
    if component_ref == STAGE_COMPONENT_REF:
        return [
            "record_id",
            "component_ref",
            "resolution_state",
            "denominator_kind",
            "denominator_label",
            "stage_role",
            "axis_group",
            "display_name",
            "numerator",
            "denominator",
            "fraction",
            "denominator_scope",
            "unit",
            "interval_lower",
            "interval_upper",
            "interval_state",
            "evidence_state",
            "missingness",
            "scientific_status",
            "applicability",
            "reason_codes",
            "evidence_ids",
        ]
    if component_ref == REFERENCE_COMPONENT_REF:
        return [
            "record_id",
            "analysis_unit_ref",
            "component_ref",
            "label",
            "stage_role",
            "ordinal_rank",
            "profile_id",
            "source_id",
            "assay",
            "anatomy",
            "reference_scope",
            "top_label",
            "top_stage_role",
            "top_ordinal_rank",
            "top_spearman_support",
            "top_cosine_support",
            "runner_up_label",
            "runner_up_stage_role",
            "runner_up_ordinal_rank",
            "margin",
            "shared_genes",
            "output_semantics",
            "evidence_state",
            "missingness",
            "applicability",
            "scientific_status",
            "reason_codes",
            "evidence_ids",
        ]
    return [
        "record_id",
        "timepoint_id",
        "timepoint_order",
        "component_ref",
        "timepoint_label",
        "time_basis",
        "independence_group_count",
        "denominator_kind",
        "denominator_label",
        "stage_role",
        "axis_group",
        "display_name",
        "numerator",
        "denominator",
        "fraction",
        "denominator_scope",
        "interval_state",
        "evidence_state",
        "unit",
        "interval_lower",
        "interval_upper",
        "missingness",
        "applicability",
        "reason_codes",
        "scientific_status",
        "evidence_ids",
    ]


def _static_render_reason(profile, component_ref):
    if component_ref == REFERENCE_COMPONENT_REF:
        groups = {
            (record.source_id, record.assay, record.profile_id)
            for record in profile.reference_records
        }
        units_by_group = {
            group: {
                record.analysis_unit_ref
                for record in profile.reference_records
                if (record.source_id, record.assay, record.profile_id) == group
            }
            for group in groups
        }
        if (
            len(groups) > 8
            or max((len(units) for units in units_by_group.values()), default=0) > 30
            or len(profile.reference_records) > 180
        ):
            return "static_render_requires_table_fallback"
    if component_ref == TIMEPOINT_COMPONENT_REF:
        if len({record.timepoint_id for record in profile.sampling_point_records}) > 8:
            return "static_render_requires_table_fallback"
    return None


def _render_stage_figure(profile):
    if not profile.stage_records:
        return _empty_figure(
            "Cell-state composition relative to the declared developmental window",
            "The developmental-window composition could not be assessed.",
            profile.stage_composition_reason_codes,
        )
    by_key = {
        (record.stage_role, record.denominator_kind): record
        for record in profile.stage_records
    }
    y_by_role = {
        DevelopmentStageRole.EARLIER: 4.25,
        DevelopmentStageRole.WITHIN_WINDOW: 3.15,
        DevelopmentStageRole.LATER: 2.05,
        DevelopmentStageRole.BRANCH_SHIFT: 0.65,
        DevelopmentStageRole.UNRESOLVED: -0.45,
    }
    fig = plt.figure(figsize=(12.0, 6.8), facecolor=_BACKGROUND)
    ax = fig.add_axes((0.26, 0.25, 0.68, 0.55), facecolor=_BACKGROUND)
    for role, y in y_by_role.items():
        ax.axhspan(
            y - 0.40,
            y + 0.40,
            color=_STAGE_COLORS[role],
            alpha=0.12 if role is DevelopmentStageRole.WITHIN_WINDOW else 0.07,
            linewidth=0,
        )
    ax.axvline(
        108,
        color="#CAD2D7",
        linewidth=0.9,
        linestyle=(0, (2, 2)),
    )
    ax.text(
        117,
        4.64,
        "Not assessable",
        ha="center",
        va="bottom",
        fontsize=7.5,
        color=_MUTED,
    )
    for role in _ROLE_ORDER:
        y = y_by_role[role]
        for denominator_kind, offset, filled in (
            ("whole_product", 0.13, True),
            ("target_related", -0.13, False),
        ):
            record = by_key[(role, denominator_kind)]
            color = _STAGE_COLORS[role]
            if record.fraction is None:
                ax.scatter(
                    [117],
                    [y + offset],
                    marker="x",
                    s=62,
                    linewidths=1.7,
                    color="#8A969E",
                    zorder=4,
                )
                ax.text(
                    120,
                    y + offset,
                    "NA",
                    va="center",
                    fontsize=8.2,
                    color=_MUTED,
                )
                continue
            x = 100 * record.fraction
            ax.scatter(
                [x],
                [y + offset],
                s=112 if filled else 92,
                marker="o",
                facecolors=color if filled else _BACKGROUND,
                edgecolors=color,
                linewidths=1.9,
                zorder=4,
            )
            label = f"{x:.1f}% · {record.numerator:,}/{record.denominator:,}"
            if x > 78:
                ax.text(
                    x - 1.7,
                    y + offset,
                    label,
                    ha="right",
                    va="center",
                    fontsize=8.1,
                    color=_TEXT,
                )
            else:
                ax.text(
                    x + 1.7,
                    y + offset,
                    label,
                    ha="left",
                    va="center",
                    fontsize=8.1,
                    color=_TEXT,
                )

    ax.axhline(1.35, color="#C9D0D4", linewidth=1.1)
    ax.text(
        -8.0,
        1.45,
        "Off the ordered stage axis",
        fontsize=8.1,
        fontweight="bold",
        color=_MUTED,
        va="bottom",
    )
    ax.set_yticks([y_by_role[role] for role in _ROLE_ORDER])
    ax.set_yticklabels(
        [by_key[(role, "whole_product")].display_name for role in _ROLE_ORDER],
        fontsize=9.2,
        color=_TEXT,
    )
    ax.set_xlim(0, 132)
    ax.set_ylim(-1.05, 4.85)
    ax.set_xticks(np.arange(0, 101, 20))
    ax.set_xticklabels([f"{value}%" for value in range(0, 101, 20)], fontsize=8.5)
    ax.set_xlabel("Share of the stated denominator", fontsize=9.2, color=_MUTED)
    ax.xaxis.grid(True, color=_GRID, linewidth=0.8)
    ax.yaxis.grid(False)
    ax.tick_params(axis="y", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.text(
        0.07,
        0.94,
        "Cell-state composition relative to the declared developmental window",
        fontsize=16,
        fontweight="bold",
        color=_TEXT,
    )
    fig.text(
        0.07,
        0.875,
        "Descriptive composition after candidate state-to-stage-role mapping; "
        "not a biological-age estimate.",
        fontsize=9.6,
        color=_MUTED,
    )
    fig.text(
        0.95,
        0.925,
        f"Window status: {profile.window_review_state}",
        ha="right",
        fontsize=8.5,
        color=_TEXT,
        bbox={
            "boxstyle": "round,pad=0.38",
            "facecolor": "#EFF2F5",
            "edgecolor": "#C7D0D6",
        },
    )
    whole_denominator = by_key[
        (DevelopmentStageRole.EARLIER, "whole_product")
    ].denominator
    target_denominator = by_key[
        (DevelopmentStageRole.EARLIER, "target_related")
    ].denominator
    target_share = (
        "NA"
        if whole_denominator == 0
        else f"{100 * target_denominator / whole_denominator:.1f}% of all"
    )
    fig.legend(
        handles=[
            Line2D(
                [0],
                [0],
                marker="o",
                linestyle="none",
                markerfacecolor="#5D8998",
                markeredgecolor="#5D8998",
                markersize=7.5,
                label=f"All evaluated observations (N={whole_denominator:,})",
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                linestyle="none",
                markerfacecolor=_BACKGROUND,
                markeredgecolor="#5D8998",
                markeredgewidth=1.7,
                markersize=7.5,
                label=(f"Target-related subset (n={target_denominator:,}; {target_share})"),
            ),
        ],
        loc="upper left",
        bbox_to_anchor=(0.065, 0.842),
        frameon=False,
        ncol=2,
        fontsize=8.6,
        handletextpad=0.5,
        columnspacing=1.6,
    )
    resolution_colors = {
        "supported": "#62AA9D",
        "unknown": "#8FBBD3",
        "ood": "#D98E83",
        "unresolved": "#B59AC7",
        "unavailable": "#AAB4BD",
    }
    fig.legend(
        handles=[
            Line2D(
                [0],
                [0],
                marker="s",
                linestyle="none",
                markerfacecolor=resolution_colors[record.resolution_state],
                markeredgecolor="#FFFFFF",
                markersize=7,
                label=(
                    f"{record.display_name}: {record.count:,} "
                    f"({100 * record.fraction:.1f}%)"
                ),
            )
            for record in profile.resolution_records
        ],
        title="Cell-state evidence resolution · whole product",
        loc="lower left",
        bbox_to_anchor=(0.065, 0.075),
        frameon=False,
        ncol=min(5, max(1, len(profile.resolution_records))),
        fontsize=7.5,
        title_fontsize=8.0,
        handletextpad=0.35,
        columnspacing=1.0,
    )
    fig.text(
        0.07,
        0.025,
        (
            "Stage roles are candidate mappings. Ordered categories and off-axis states "
            "remain separate; observation counts are not biological replicates and do "
            "not provide composition confidence intervals."
        ),
        fontsize=7.9,
        color=_MUTED,
    )
    return fig


def _render_reference_figure(profile):
    title = (
        "Highest expression-similarity labels in each selected reference "
        "(uncalibrated)"
    )
    if not profile.reference_records:
        return _empty_figure(
            title,
            "Reference-stage expression similarity was not available.",
            profile.reference_support_reason_codes,
        )

    groups = {}
    for record in profile.reference_records:
        key = (record.source_id, record.assay, record.profile_id)
        groups.setdefault(key, []).append(record)
    ordered_groups = sorted(groups)
    max_rows = max(len(records) for records in groups.values())
    panel_height = max(2.25, 0.36 * max_rows + 1.0)
    height = max(5.8, 2.25 + panel_height * len(ordered_groups))
    fig, axes = plt.subplots(
        len(ordered_groups),
        1,
        figsize=(13.4, height),
        squeeze=False,
        facecolor=_BACKGROUND,
    )
    axes = axes[:, 0].tolist()
    cmap = LinearSegmentedColormap.from_list(
        "bridge_stage_support",
        ["#D18A78", "#F2EFE8", "#4D9A8D"],
    )
    norm = Normalize(vmin=-1.0, vmax=1.0)

    definitions_by_profile = {}
    for item in profile.registered_reference_stages:
        definitions_by_profile.setdefault(item.profile_id, []).append(item)

    for panel_index, (ax, key) in enumerate(
        zip(axes, ordered_groups, strict=True)
    ):
        records = sorted(groups[key], key=lambda item: item.analysis_unit_ref)
        _, _, profile_id = key
        definitions = sorted(
            definitions_by_profile.get(profile_id, []),
            key=lambda item: (item.ordinal_rank, item.label),
        )
        if definitions:
            ranks = sorted({item.ordinal_rank for item in definitions})
            labels_by_rank = {}
            for item in definitions:
                labels_by_rank.setdefault(item.ordinal_rank, set()).add(item.label)
        else:
            ranks = sorted(
                {
                    rank
                    for record in records
                    for rank in (
                        record.top_ordinal_rank,
                        record.runner_up_ordinal_rank,
                    )
                    if rank is not None
                }
            ) or [0]
            labels_by_rank = {}
            for record in records:
                if record.top_ordinal_rank is not None:
                    labels_by_rank.setdefault(
                        record.top_ordinal_rank, set()
                    ).add(record.top_label)
                if record.runner_up_ordinal_rank is not None:
                    labels_by_rank.setdefault(
                        record.runner_up_ordinal_rank, set()
                    ).add(record.runner_up_label)

        x_by_rank = {rank: index for index, rank in enumerate(ranks)}
        y_positions = np.arange(len(records))[::-1]
        x_min, x_max = 0, len(ranks) - 1
        x_not_assessed = x_max + 1.0
        x_detail = x_max + 1.75
        ax.axvline(
            x_not_assessed - 0.48,
            color="#CAD2D7",
            linewidth=0.9,
            linestyle=(0, (2, 2)),
        )
        ax.text(
            x_not_assessed,
            len(records) - 0.10,
            "Not assessable",
            ha="center",
            va="bottom",
            fontsize=7.2,
            color=_MUTED,
        )
        unit_labels = _unique_short_labels(
            [record.analysis_unit_ref for record in records]
        )
        for y_pos, record in zip(y_positions, records, strict=True):
            if record.top_ordinal_rank is None:
                ax.scatter(
                    [x_not_assessed],
                    [y_pos],
                    marker="s",
                    s=52,
                    facecolors="#EEF1F2",
                    edgecolors="#8A969E",
                    linewidths=1.0,
                )
                reason = ", ".join(
                    _display_label(item) for item in record.reason_codes
                )
                ax.text(
                    x_detail,
                    y_pos,
                    reason or "reference evidence unavailable",
                    ha="left",
                    va="center",
                    fontsize=7.5,
                    color=_MUTED,
                )
                continue

            unavailable = record.evidence_state is EvidenceState.UNAVAILABLE
            ax.scatter(
                [x_by_rank[record.top_ordinal_rank]],
                [y_pos],
                s=92,
                c=[
                    "#EEF1F2"
                    if record.top_spearman_support is None
                    else cmap(norm(record.top_spearman_support))
                ],
                edgecolors="#C67B3F" if unavailable else "#FFFFFF",
                linewidths=2.0 if unavailable else 0.9,
                zorder=4,
            )
            if record.runner_up_ordinal_rank is not None:
                ax.scatter(
                    [x_by_rank[record.runner_up_ordinal_rank]],
                    [y_pos],
                    s=40,
                    facecolors="none",
                    edgecolors="#77858E",
                    linewidths=1.2,
                    zorder=3,
                )
            margin = "NA" if record.margin is None else f"{record.margin:.2f}"
            similarity = (
                "NA"
                if record.top_spearman_support is None
                else f"{record.top_spearman_support:.2f}"
            )
            detail = (
                f"ρ={similarity}  Δ={margin}  {record.shared_genes:,} genes"
            )
            flags = []
            if (
                record.top_spearman_support is not None
                and record.top_spearman_support <= 0
            ):
                flags.append("non-positive similarity")
            if unavailable:
                flags.extend(_display_label(item) for item in record.reason_codes)
            if flags:
                detail += "  ·  " + ", ".join(flags)
            ax.text(
                x_detail,
                y_pos,
                detail,
                ha="left",
                va="center",
                fontsize=7.5,
                color=_TEXT if not unavailable else "#8A5C34",
            )

        ax.set_yticks(y_positions)
        ax.set_yticklabels(unit_labels)
        ax.set_xticks(range(len(ranks)))
        ax.set_xticklabels(
            [
                "\n".join(
                    sorted(
                        label
                        for label in labels_by_rank.get(rank, {"not registered"})
                        if label
                    )
                )
                for rank in ranks
            ],
            fontsize=7.5,
        )
        ax.set_xlim(x_min - 0.55, x_max + 4.7)
        ax.set_ylim(-0.65, max(len(records) - 0.20, 0.85))
        ax.xaxis.grid(True, color=_GRID, linewidth=0.8)
        ax.yaxis.grid(False)
        ax.tick_params(axis="y", length=0, labelsize=7.7)
        for spine in ax.spines.values():
            spine.set_visible(False)

        source_id, assay, profile_id = key
        first = records[0]
        ax.set_title(
            f"{_source_label(source_id)} · {assay}",
            loc="left",
            fontsize=10.2,
            color=_TEXT,
            pad=18,
        )
        ax.text(
            0.0,
            1.015,
            f"{_short_id(profile_id)} · {first.anatomy} · {first.reference_scope}",
            transform=ax.transAxes,
            fontsize=7.5,
            color=_MUTED,
            va="bottom",
        )
        if panel_index == len(axes) - 1:
            ax.set_xlabel(
                "Registered category order — not elapsed time",
                fontsize=8.3,
                color=_MUTED,
                labelpad=8,
            )

    fig.subplots_adjust(
        top=0.80,
        bottom=0.12,
        left=0.20,
        right=0.83,
        hspace=1.05,
    )
    fig.text(0.065, 0.95, title, fontsize=15.2, fontweight="bold", color=_TEXT)
    fig.text(
        0.065,
        0.905,
        (
            "● highest label; ○ runner-up. Forced ranking among supplied labels; "
            "there is no calibrated rejection or age probability."
        ),
        fontsize=9.2,
        color=_MUTED,
    )
    color_ax = fig.add_axes((0.875, 0.32, 0.016, 0.34))
    scalar = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    colorbar = fig.colorbar(scalar, cax=color_ax)
    colorbar.set_label("Spearman expression similarity", fontsize=8.0)
    colorbar.ax.tick_params(labelsize=7.3)
    fig.text(
        0.065,
        0.045,
        (
            "Reliability ledger: each row reports similarity, top–runner-up margin, "
            "shared genes and evidence reasons. Sources and assays are not pooled; "
            "OOD and calibration are not assessed."
        ),
        fontsize=8.1,
        color=_MUTED,
    )
    return fig

def _render_timepoint_figure(profile):
    title = "Descriptive composition across declared product sampling points"
    if not profile.sampling_point_records:
        if profile.timepoint_series_ref is None:
            message = (
                "A sampling-point series was not supplied. Dynamic change cannot be assessed."
            )
        else:
            message = (
                "The supplied sampling-point series could not yield assessable composition."
            )
        return _empty_figure(
            title,
            message,
            _component_assessment(profile, TIMEPOINT_COMPONENT_REF)[2],
        )
    records = profile.sampling_point_records
    timepoints = sorted(
        {
            (record.timepoint_order, record.timepoint_id, record.timepoint_label)
            for record in records
        }
    )
    if len(timepoints) < 2:
        return _empty_figure(
            title,
            (
                "Only one categorical sampling point was supplied. Its cross-sectional "
                "composition remains available in the table; change over time is not assessable."
            ),
            [
                "single_sampling_point_dynamic_change_unavailable",
                profile.continuous_time_reason_code,
            ],
        )

    width = min(16.0, max(12.2, 8.8 + 0.72 * len(timepoints)))
    fig, axes = plt.subplots(
        1,
        2,
        figsize=(width, 6.35),
        sharey=True,
        facecolor=_BACKGROUND,
    )
    display_roles = tuple(reversed(_ROLE_ORDER))
    y_by_role = {
        role: index + (0.65 if role in _ORDERED_ROLES else 0.0)
        for index, role in enumerate(display_roles)
    }
    for ax, denominator_kind in zip(
        axes,
        ("whole_product", "target_related"),
        strict=True,
    ):
        selected = [
            record
            for record in records
            if record.denominator_kind == denominator_kind
        ]
        by_key = {
            (record.timepoint_id, record.stage_role): record
            for record in selected
        }
        for x, (_, timepoint_id, _) in enumerate(timepoints):
            for role in display_roles:
                y = y_by_role[role]
                record = by_key[(timepoint_id, role)]
                if record.fraction is None:
                    patch = Rectangle(
                        (x - 0.45, y - 0.38),
                        0.90,
                        0.76,
                        facecolor="#EEF1F2",
                        edgecolor="#98A3AA",
                        hatch="///",
                        linewidth=0.8,
                    )
                    label = "—"
                    text_color = _MUTED
                else:
                    patch = Rectangle(
                        (x - 0.45, y - 0.38),
                        0.90,
                        0.76,
                        facecolor=_STAGE_COLORS[role],
                        edgecolor="#FFFFFF",
                        linewidth=0.9,
                        alpha=0.10 + 0.82 * record.fraction,
                    )
                    label = f"{100 * record.fraction:.0f}%"
                    text_color = _TEXT
                ax.add_patch(patch)
                ax.text(
                    x,
                    y,
                    label,
                    ha="center",
                    va="center",
                    fontsize=7.6,
                    color=text_color,
                    fontweight="bold",
                )

        labels = []
        for _, timepoint_id, label in timepoints:
            record = by_key[(timepoint_id, DevelopmentStageRole.EARLIER)]
            labels.append(
                f"{label}\n{record.denominator:,} observations\n"
                f"{record.independence_group_count} independent groups"
            )
        ax.set_xticks(np.arange(len(timepoints)))
        ax.set_xticklabels(labels, fontsize=7.4)
        ax.set_xlim(-0.55, len(timepoints) - 0.45)
        ax.set_ylim(-0.65, max(y_by_role.values()) + 0.65)
        ax.set_title(
            (
                "All evaluated observations"
                if denominator_kind == "whole_product"
                else "Target-related subset"
            ),
            fontsize=10.3,
            color=_TEXT,
            pad=12,
        )
        ax.tick_params(axis="both", length=0)
        ax.grid(False)
        for spine in ax.spines.values():
            spine.set_visible(False)

    axes[0].set_yticks([y_by_role[role] for role in display_roles])
    axes[0].set_yticklabels(
        [
            {
                DevelopmentStageRole.EARLIER: "Earlier than window",
                DevelopmentStageRole.WITHIN_WINDOW: "Within window",
                DevelopmentStageRole.LATER: "Later than window",
                DevelopmentStageRole.BRANCH_SHIFT: "Different branch",
                DevelopmentStageRole.UNRESOLVED: "Not resolved",
            }[role]
            for role in display_roles
        ],
        fontsize=8.4,
    )
    fig.subplots_adjust(
        left=0.17,
        right=0.97,
        bottom=0.23,
        top=0.78,
        wspace=0.14,
    )
    fig.text(0.065, 0.93, title, fontsize=15.5, fontweight="bold", color=_TEXT)
    fig.text(
        0.065,
        0.885,
        (
            "Numbers are percentages within each panel denominator. Tiles are "
            "categorical summaries; no curve or interpolation is drawn."
        ),
        fontsize=9.3,
        color=_MUTED,
    )
    fig.text(
        0.065,
        0.055,
        (
            "Sampling-point order is categorical. The current contract has no numeric "
            "experimental-time axis, so it does not support a continuous trend, "
            "direction of change or in-vivo age conversion."
        ),
        fontsize=8.1,
        color=_MUTED,
    )
    return fig

def _empty_figure(title, message, reasons):
    fig = plt.figure(figsize=(11.4, 4.9), facecolor=_BACKGROUND)
    ax = fig.add_axes((0.08, 0.16, 0.84, 0.67))
    ax.axis("off")
    ax.text(0, 0.86, title, fontsize=15.5, fontweight="bold", color=_TEXT)
    ax.text(0, 0.59, message, fontsize=11, fontweight="bold", color=_MUTED)
    reason_text = " · ".join(_display_label(reason) for reason in sorted(set(reasons)) if reason)
    ax.text(
        0,
        0.39,
        reason_text or "No assessable records were produced.",
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
                    bbox_inches="tight",
                    metadata={"Date": None, "Creator": "BRIDGE"},
                )
            elif extension == "png":
                fig.savefig(
                    buffer,
                    format="png",
                    dpi=220,
                    bbox_inches="tight",
                    metadata={"Software": "BRIDGE"},
                )
            else:
                fig.savefig(
                    buffer,
                    format="pdf",
                    bbox_inches="tight",
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
    component_id, component_version = component.ref.split("@", 1)
    records = getattr(profile, component.records_path)
    fallback_state, applicability, assessment_reasons = _component_assessment(
        profile, component.ref
    )
    reasons = set(assessment_reasons)
    if component.ref == STAGE_COMPONENT_REF:
        numerator_field = "numerator"
        denominator_field = "denominator"
        denominator_scope_field = "denominator_scope"
        value_field = None
        denominator_label = "Displayed whole-product or target-related denominator"
        denominator_scope = "evaluated_product_or_target_related_subset"
        unit = "observations"
        takeaway = "Both denominators are shown explicitly; off-axis states remain separate."
    elif component.ref == REFERENCE_COMPONENT_REF:
        numerator_field = denominator_field = denominator_scope_field = None
        value_field = "top_spearman_support"
        denominator_label = denominator_scope = None
        unit = "expression similarity"
        takeaway = "Highest and runner-up similarity labels remain separated by source and assay."
    else:
        numerator_field = "numerator"
        denominator_field = "denominator"
        denominator_scope_field = "denominator_scope"
        value_field = None
        denominator_label = "Displayed sampling-point denominator"
        denominator_scope = "declared_sampling_point_view"
        unit = "observations"
        takeaway = "Observed sampling points are shown without a continuous-time interpolation."

    evidence_states = sorted(
        {record.evidence_state for record in records} or {fallback_state},
        key=str,
    )
    if render_reason:
        reasons.add(render_reason)
        if applicability == "applicable":
            applicability = "partially_applicable"
        takeaway = "The exact result remains available in the typed JSON and table."

    data_binding = VisualizationDataBinding(
        artifact_id=data_artifact.artifact_id,
        schema_ref=DEVELOPMENTAL_VISUALIZATION_DATA_SCHEMA_REF,
        object_version="0.1.0",
        sha256=data_artifact.sha256,
        records_path=component.records_path,
        record_lookup_key="record_id",
        evidence_ids_field="evidence_ids",
        value_field=value_field,
        numerator_field=numerator_field,
        denominator_field=denominator_field,
        denominator_scope_field=denominator_scope_field,
        unit_field="unit" if component.ref != REFERENCE_COMPONENT_REF else None,
        evidence_state_field="evidence_state",
        scientific_status_field="scientific_status",
        missingness_field="missingness",
        applicability_field="applicability",
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
    limitations = [
        "Stage categories depend on the externally supplied developmental window and state map.",
        "Reference similarity is not a calibrated biological age, probability "
        "or future-fate estimate.",
        "Observation counts are not biological replicates and do not provide "
        "composition confidence intervals.",
    ]
    return VisualizationArtifactV2(
        visualization_id=f"visualization:{run_id}:{component.slug}",
        component_id=component_id,
        component_version=component_version,
        data_binding=data_binding,
        producer_tool_id="P0-04",
        producer_tool_version=tool_version,
        producer_run_ref=f"run:{run_id}",
        evidence_ids=profile.evidence_ids,
        evidence_states=evidence_states,
        scientific_status="candidate",
        applicability=applicability,
        missing_reason_codes=sorted(reasons),
        denominator_label=denominator_label,
        denominator_scope=denominator_scope,
        unit=unit,
        insight_title=component.render_title,
        takeaway=takeaway,
        limitations=limitations,
        accessibility=VisualizationAccessibility(
            alt_text=component.render_title,
            long_description=(
                f"{component.render_title}. {takeaway} "
                "The table contains exact primary values and assessment reasons; "
                "the typed JSON retains component provenance and supplemental records."
            ),
            table_artifact_id=table_artifact.artifact_id,
            data_sha256=data_artifact.sha256,
        ),
        renders=renders,
    )


def _config_sha256(component_ref):
    payload = canonical_json_bytes(
        {
            "component_ref": component_ref,
            "renderer_id": _RENDERER_ID,
            "renderer_version": _RENDERER_VERSION,
            "export_profile_id": _EXPORT_PROFILE_ID,
            "renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "matplotlib_version": matplotlib.__version__,
            "numpy_version": np.__version__,
            "matplotlib_rc": _MATPLOTLIB_RC,
            "stage_colors": {role.value: color for role, color in _STAGE_COLORS.items()},
        }
    )
    return hashlib.sha256(payload).hexdigest()


def _source_label(value):
    label = str(value)
    return _display_label(label.split(":", 1)[-1])


def _short_id(value):
    label = str(value).split(":", 1)[-1].split("@", 1)[0]
    return label if len(label) <= 38 else f"{label[:35]}…"


def _unique_short_labels(values):
    bases = [_short_id(value) for value in values]
    totals = {base: bases.count(base) for base in set(bases)}
    seen = {}
    labels = []
    for base in bases:
        seen[base] = seen.get(base, 0) + 1
        labels.append(
            base
            if totals[base] == 1
            else f"{base} · {seen[base]}/{totals[base]}"
        )
    return labels


def _display_label(value):
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
