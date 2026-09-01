from __future__ import annotations

import csv
from dataclasses import dataclass
from io import BytesIO, StringIO
import hashlib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_03_target_regional.visualization_data import (
    P003VisualizationArtifactSet,
    ProductRoleCompositionRecord,
    REFERENCE_COMPONENT_REF,
    RegionalStateCompositionRecord,
    ROLE_COMPONENT_REF,
    TARGET_REGIONAL_VISUALIZATION_DATA_SCHEMA_REF,
    TargetRegionalVisualizationDataV1,
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
_ROLE_COLORS = {
    "target": "#4F9D91",
    "acceptable_adjacent": "#97C9A9",
    "known_off_target": "#E4958D",
    "role_unresolved": "#B6A6D8",
    "unknown": "#99A7B8",
    "ood": "#D5B78E",
    "unavailable": "#C8CDD2",
}
_ROLE_MARKERS = {
    "target": "o",
    "acceptable_adjacent": "s",
    "known_off_target": "^",
    "role_unresolved": "D",
    "unknown": "X",
    "ood": "P",
    "unavailable": "h",
}
_LEVEL_LABELS = {
    "L1": "broad cell families",
    "L2": "detailed cell states",
    "L3": "fine-grained cell states",
}
_MAX_PRODUCT_CHANNELS = 8
_MAX_STATES_PER_CHANNEL = 60
_MAX_TOTAL_PRODUCT_STATES = 120
_MAX_PROFILES_PER_SCOPE = 12
_MAX_STATES_PER_SCOPE = 100
_MATPLOTLIB_RC = {
    "font.family": ["DejaVu Sans"],
    "font.sans-serif": ["DejaVu Sans"],
    "pdf.fonttype": 42,
    "svg.fonttype": "path",
    "svg.hashsalt": "BRIDGE-P0-03",
}


@dataclass(frozen=True)
class PreparedTargetRegionalVisualizations:
    payloads: dict[str, bytes]
    artifacts: tuple[ArtifactManifest, ...]


def _role_static_render_reason(
    profile: TargetRegionalVisualizationDataV1,
) -> str | None:
    channel_ids = {record.channel_id for record in profile.product_records}
    state_counts = {
        channel_id: sum(
            isinstance(record, RegionalStateCompositionRecord)
            and record.channel_id == channel_id
            for record in profile.product_records
        )
        for channel_id in channel_ids
    }
    exceeds_page = (
        len(channel_ids) > _MAX_PRODUCT_CHANNELS
        or max(state_counts.values(), default=0) > _MAX_STATES_PER_CHANNEL
        or sum(state_counts.values()) > _MAX_TOTAL_PRODUCT_STATES
    )
    return "static_render_requires_table_fallback" if exceeds_page else None


def _reference_static_render_reason(
    profile: TargetRegionalVisualizationDataV1,
) -> str | None:
    for scope in {record.evidence_scope for record in profile.reference_records}:
        scoped = [
            record
            for record in profile.reference_records
            if record.evidence_scope == scope
        ]
        if (
            len({record.profile_id for record in scoped}) > _MAX_PROFILES_PER_SCOPE
            or len({record.state_id for record in scoped}) > _MAX_STATES_PER_SCOPE
        ):
            return "static_render_requires_table_fallback"
    return None


def _render_table_fallback_figure(title: str):
    fig = plt.figure(figsize=(11.2, 4.8), facecolor="#FCFBF8")
    ax = fig.add_axes((0.08, 0.15, 0.84, 0.68))
    ax.axis("off")
    ax.text(
        0,
        0.82,
        title,
        fontsize=15,
        fontweight="bold",
        color="#24313A",
    )
    ax.text(
        0,
        0.56,
        "This result is too large for a single static page.",
        fontsize=12,
        fontweight="bold",
        color="#59666E",
    )
    ax.text(
        0,
        0.38,
        (
            "Use the exact TSV or typed JSON to inspect every channel, state, "
            "reference and missing-data reason."
        ),
        fontsize=10,
        color="#65717A",
        wrap=True,
    )
    return fig


def prepare_target_regional_visualizations(
    *,
    profile: TargetRegionalVisualizationDataV1,
    output_dir: Path,
    run_id: str,
    tool_version: str,
) -> PreparedTargetRegionalVisualizations:
    final_dir = output_dir / run_id
    payloads: dict[str, bytes] = {}
    artifacts: list[ArtifactManifest] = []

    data_name = "target_regional_visualization_data.json"
    data_payload = canonical_json_bytes(profile.model_dump(mode="json"), indent=2)
    payloads[data_name] = data_payload
    data_artifact = _manifest(
        run_id,
        "target-regional-visualization-data",
        "target_regional_visualization_data",
        final_dir / data_name,
        "application/json",
        data_payload,
        profile.evidence_ids,
    )
    artifacts.append(data_artifact)

    role_table_name = "target_regional_product_roles.tsv"
    role_table = _role_table(profile)
    payloads[role_table_name] = role_table
    role_table_artifact = _manifest(
        run_id,
        "target-regional-product-roles-table",
        "visualization_table",
        final_dir / role_table_name,
        "text/tab-separated-values",
        role_table,
        profile.evidence_ids,
    )
    artifacts.append(role_table_artifact)

    reference_table_name = "target_regional_reference_fingerprint.tsv"
    reference_table = _reference_table(profile)
    payloads[reference_table_name] = reference_table
    reference_table_artifact = _manifest(
        run_id,
        "target-regional-reference-table",
        "visualization_table",
        final_dir / reference_table_name,
        "text/tab-separated-values",
        reference_table,
        profile.evidence_ids,
    )
    artifacts.append(reference_table_artifact)

    role_render_reason = _role_static_render_reason(profile)
    reference_render_reason = _reference_static_render_reason(profile)
    with matplotlib.rc_context(rc=_MATPLOTLIB_RC):
        role_figure = (
            _render_table_fallback_figure(
                "Product composition relative to the declared regional identity"
            )
            if role_render_reason
            else _render_role_figure(profile)
        )
        reference_figure = (
            _render_table_fallback_figure(
                "Reference support for cell and midbrain regional states"
            )
            if reference_render_reason
            else _render_reference_figure(profile)
        )
        role_renders = _render_payloads(role_figure)
        reference_renders = _render_payloads(reference_figure)
    render_artifacts = {}
    for slug, rendered in (
        ("product-roles", role_renders),
        ("reference-fingerprint", reference_renders),
    ):
        for extension, (media_type, payload) in rendered.items():
            name = f"target_regional_{slug}.{extension}"
            payloads[name] = payload
            artifact = _manifest(
                run_id,
                f"target-regional-{slug}-{extension}",
                "visualization_render",
                final_dir / name,
                media_type,
                payload,
                profile.evidence_ids,
            )
            artifacts.append(artifact)
            render_artifacts[(slug, extension)] = artifact

    data_hash = data_artifact.sha256
    visualizations = [
        _visualization_contract(
            profile=profile,
            component_ref=ROLE_COMPONENT_REF,
            data_artifact=data_artifact,
            table_artifact=role_table_artifact,
            render_artifacts={
                extension: render_artifacts[("product-roles", extension)]
                for extension in ("svg", "png", "pdf")
            },
            run_id=run_id,
            tool_version=tool_version,
            data_hash=data_hash,
            render_reason=role_render_reason,
        ),
        _visualization_contract(
            profile=profile,
            component_ref=REFERENCE_COMPONENT_REF,
            data_artifact=data_artifact,
            table_artifact=reference_table_artifact,
            render_artifacts={
                extension: render_artifacts[("reference-fingerprint", extension)]
                for extension in ("svg", "png", "pdf")
            },
            run_id=run_id,
            tool_version=tool_version,
            data_hash=data_hash,
            render_reason=reference_render_reason,
        ),
    ]
    registry = FigureRegistry.load_default()
    for visualization in visualizations:
        registry.validate_artifact(visualization)

    artifact_set = P003VisualizationArtifactSet(
        artifact_set_id=f"p0-03-visualizations:{run_id.removeprefix('run-')}",
        data_profile_artifact_id=data_artifact.artifact_id,
        data_profile_sha256=data_hash,
        visualizations=visualizations,
    )
    artifact_set_name = "target_regional_visualization_artifact_set.json"
    artifact_set_payload = canonical_json_bytes(
        artifact_set.model_dump(mode="json"), indent=2
    )
    payloads[artifact_set_name] = artifact_set_payload
    artifacts.append(
        _manifest(
            run_id,
            "target-regional-visualization-artifact-set",
            "visualization_artifact_set",
            final_dir / artifact_set_name,
            "application/json",
            artifact_set_payload,
            profile.evidence_ids,
        )
    )
    return PreparedTargetRegionalVisualizations(
        payloads=payloads,
        artifacts=tuple(artifacts),
    )


def _role_table(profile):
    output = StringIO(newline="")
    fields = [
        "record_type",
        "channel_id",
        "composition_view",
        "source_id",
        "label_level",
        "role_map_review_state",
        "channel_assessment_state",
        "channel_reason_codes",
        "category_or_state",
        "display_name",
        "product_role",
        "is_target_related",
        "is_target_region",
        "count",
        "product_denominator",
        "fraction_of_product",
        "target_related_denominator",
        "fraction_of_target_related",
        "interval_state",
        "evidence_state",
        "reason_codes",
    ]
    writer = csv.DictWriter(
        output,
        fieldnames=fields,
        delimiter="\t",
        lineterminator="\n",
    )
    writer.writeheader()
    for record in profile.product_records:
        row = {
            "channel_id": record.channel_id,
            "composition_view": record.composition_view,
            "source_id": record.source_id or "",
            "label_level": record.label_level,
            "role_map_review_state": profile.role_map_review_state,
            "channel_assessment_state": record.channel_assessment_state,
            "channel_reason_codes": ";".join(record.channel_reason_codes),
            "display_name": record.display_name,
            "count": "" if record.count is None else record.count,
            "product_denominator": record.product_denominator,
            "fraction_of_product": (
                "" if record.fraction_of_product is None else record.fraction_of_product
            ),
            "interval_state": record.interval_state,
            "evidence_state": record.evidence_state,
            "reason_codes": ";".join(record.reason_codes),
        }
        if isinstance(record, ProductRoleCompositionRecord):
            row.update(
                record_type="product_role",
                category_or_state=record.category,
                product_role=record.category,
                is_target_related="",
                is_target_region="",
                target_related_denominator="",
                fraction_of_target_related="",
            )
        else:
            row.update(
                record_type="reference_state",
                category_or_state=record.state_id,
                product_role=record.product_role,
                is_target_related=record.is_target_related,
                is_target_region=record.is_target_region,
                target_related_denominator=(
                    ""
                    if record.target_related_denominator is None
                    else record.target_related_denominator
                ),
                fraction_of_target_related=(
                    ""
                    if record.fraction_of_target_related is None
                    else record.fraction_of_target_related
                ),
            )
        writer.writerow(row)
    return output.getvalue().encode("utf-8")


def _reference_table(profile):
    output = StringIO(newline="")
    fields = [
        "record_type",
        "evidence_scope",
        "profile_id",
        "source_id",
        "assay",
        "anatomy",
        "developmental_time",
        "state_id",
        "display_name",
        "median_spearman_support",
        "minimum_spearman_support",
        "maximum_spearman_support",
        "range_semantics",
        "n_analysis_units",
        "n_available_analysis_units",
        "shared_genes",
        "evidence_state",
        "applicability",
        "reason_codes",
    ]
    writer = csv.DictWriter(
        output,
        fieldnames=fields,
        delimiter="\t",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerow(
        {
            "record_type": "reference_assessment",
            "display_name": "Reference support assessment",
            "evidence_state": profile.reference_support_state,
            "applicability": profile.reference_support_applicability,
            "reason_codes": ";".join(profile.reference_support_reason_codes),
        }
    )
    for record in profile.reference_records:
        writer.writerow(
            {
                "record_type": "reference_state_support",
                "evidence_scope": record.evidence_scope,
                "profile_id": record.profile_id,
                "source_id": record.source_id,
                "assay": record.profile_assay,
                "anatomy": record.anatomy,
                "developmental_time": record.developmental_time,
                "state_id": record.state_id,
                "display_name": record.display_name,
                "median_spearman_support": (
                    ""
                    if record.median_spearman_support is None
                    else record.median_spearman_support
                ),
                "minimum_spearman_support": (
                    ""
                    if record.minimum_spearman_support is None
                    else record.minimum_spearman_support
                ),
                "maximum_spearman_support": (
                    ""
                    if record.maximum_spearman_support is None
                    else record.maximum_spearman_support
                ),
                "range_semantics": record.range_semantics,
                "n_analysis_units": record.n_analysis_units,
                "n_available_analysis_units": record.n_available_analysis_units,
                "shared_genes": record.shared_genes,
                "evidence_state": record.evidence_state,
                "applicability": record.applicability,
                "reason_codes": ";".join(record.reason_codes),
            }
        )
    return output.getvalue().encode("utf-8")


def _render_role_figure(profile):
    channels = sorted({record.channel_id for record in profile.product_records})
    grouped_records = []
    for channel_id in channels:
        role_records = [
            record
            for record in profile.product_records
            if isinstance(record, ProductRoleCompositionRecord)
            and record.channel_id == channel_id
        ]
        state_records = [
            record
            for record in profile.product_records
            if isinstance(record, RegionalStateCompositionRecord)
            and record.channel_id == channel_id
        ]
        grouped_records.append((role_records, state_records))
    row_heights = [
        max(3.2, 0.36 * max(len(role_records), len(state_records)) + 0.8)
        for role_records, state_records in grouped_records
    ]
    height = max(5.2, sum(row_heights) + 1.7)
    fig = plt.figure(figsize=(13.6, height), facecolor="#FCFBF8")
    grid = fig.add_gridspec(
        len(channels),
        2,
        left=0.08,
        right=0.97,
        top=0.81,
        bottom=0.12,
        width_ratios=(0.92, 1.45),
        height_ratios=row_heights,
        hspace=0.68,
        wspace=0.36,
    )
    fig.text(
        0.08,
        0.95,
        "Product composition relative to the declared regional identity",
        fontsize=16,
        fontweight="bold",
        color="#24313A",
    )
    fig.text(
        0.08,
        0.905,
        (
            f"Product case: {_source_label(profile.product_case_ref.object_id)}  |  Fractions use the selected "
            "product denominator; declared roles are not identity probabilities"
        ),
        fontsize=9.2,
        color="#5B6870",
    )
    fig.text(
        0.97,
        0.95,
        f"Product role map: {_status_label(profile.role_map_review_state)}",
        ha="right",
        fontsize=8.5,
        fontweight="bold",
        color="#53616A",
        bbox={"boxstyle": "round,pad=0.35", "fc": "#EEE9F7", "ec": "none"},
    )
    for row_index, (role_records, state_records) in enumerate(grouped_records):
        _draw_role_axis(fig.add_subplot(grid[row_index, 0]), role_records)
        _draw_state_axis(fig.add_subplot(grid[row_index, 1]), state_records)
    fig.text(
        0.08,
        0.045,
        (
            "Intervals are not estimable without independent product or preparation "
            "replicates. Spatial projection is not assessed in this result."
        ),
        fontsize=8.5,
        color="#65717A",
    )
    return fig


def _draw_role_axis(ax, records):
    ax.set_facecolor("#FCFBF8")
    labels = [_display_label(record.display_name) for record in records]
    y = np.arange(len(records))[::-1]
    for position, record in zip(y, records, strict=True):
        value = (
            np.nan
            if record.fraction_of_product is None
            else 100 * record.fraction_of_product
        )
        color = _ROLE_COLORS[record.category.value]
        marker = _ROLE_MARKERS[record.category.value]
        if np.isfinite(value):
            ax.plot(
                [0, value],
                [position, position],
                color="#D7DADD",
                lw=1.0,
                zorder=1,
            )
            ax.scatter(
                value,
                position,
                s=92,
                marker=marker,
                facecolor=color,
                edgecolor="#FFFFFF",
                linewidth=0.9,
                zorder=3,
            )
            label_to_left = value >= 78
            ax.text(
                value - 2.0 if label_to_left else min(value + 2.0, 102),
                position,
                f"{record.count}/{record.product_denominator}  {value:.1f}%",
                ha="right" if label_to_left else "left",
                va="center",
                fontsize=8.2,
                color="#34434C",
            )
        else:
            ax.text(
                1,
                position,
                "not assessed",
                va="center",
                fontsize=8.2,
                color="#7A8389",
            )
    ax.set_yticks(y, labels, fontsize=8.3)
    ax.set_xlim(0, 112)
    ax.set_xticks([0, 25, 50, 75, 100], labels=["0", "25", "50", "75", "100%"])
    ax.tick_params(axis="x", labelsize=7.5, colors="#758087")
    ax.grid(axis="x", color="#E6E4DF", lw=0.7)
    source = _source_label(records[0].source_id)
    ax.set_title(
        "Product composition by declared role",
        loc="left",
        fontsize=9.8,
        fontweight="bold",
        color="#2B3942",
        pad=18,
    )
    ax.text(
        0,
        1.01,
        f"{_LEVEL_LABELS[records[0].label_level]}  |  {source}  |  "
        f"evidence: {_status_label(records[0].channel_assessment_state)}",
        transform=ax.transAxes,
        fontsize=7.4,
        color="#66727A",
    )
    for spine in ax.spines.values():
        spine.set_visible(False)


def _draw_state_axis(ax, states):
    ax.set_facecolor("#FCFBF8")
    if not states:
        ax.axis("off")
        ax.text(
            0.02,
            0.5,
            "Regional reference-state composition not assessed",
            transform=ax.transAxes,
            fontsize=10,
            color="#78838A",
        )
        return
    ordered = sorted(
        states,
        key=lambda record: (
            not record.is_target_related,
            not record.is_target_region,
            -record.fraction_of_product,
            record.display_name,
        ),
    )
    y = np.arange(len(ordered))[::-1]
    for position, record in zip(y, ordered, strict=True):
        color = _ROLE_COLORS[record.product_role.value]
        product_value = 100 * record.fraction_of_product
        ax.scatter(
            product_value,
            position,
            s=72,
            facecolor=color,
            edgecolor="#FFFFFF",
            linewidth=0.8,
            zorder=3,
        )
        ax.text(
            min(product_value + 1.5, 103),
            position + 0.13,
            f"{product_value:.1f}%",
            va="center",
            fontsize=7.5,
            color="#34434C",
        )
        if record.fraction_of_target_related is not None:
            target_value = 100 * record.fraction_of_target_related
            ax.scatter(
                target_value,
                position - 0.22,
                s=42,
                facecolor="none",
                edgecolor=color,
                linewidth=1.2,
                zorder=3,
            )
            ax.text(
                min(target_value + 1.5, 103),
                position - 0.22,
                f"{target_value:.1f}% of target-related",
                va="center",
                fontsize=6.7,
                color="#59666E",
            )
    labels = [
        f"{_display_label(record.display_name)}"
        f"{'  |  target region' if record.is_target_region else ''}"
        for record in ordered
    ]
    ax.set_yticks(y, labels, fontsize=8)
    ax.set_xlim(0, 108)
    ax.set_xticks([0, 25, 50, 75, 100], labels=["0", "25", "50", "75", "100%"])
    ax.tick_params(axis="x", labelsize=7.5, colors="#758087")
    ax.grid(axis="x", color="#E6E4DF", lw=0.7)
    ax.set_title(
        "Reference-associated cell states",
        loc="left",
        fontsize=9.8,
        fontweight="bold",
        color="#2B3942",
        pad=18,
    )
    ax.text(
        0,
        1.01,
        "Filled marker: whole product  |  open marker: target-related cells",
        transform=ax.transAxes,
        fontsize=7.4,
        color="#66727A",
    )
    for spine in ax.spines.values():
        spine.set_visible(False)


def _render_reference_figure(profile):
    records = list(profile.reference_records)
    scope_order = {"target_identity": 0, "regional_fidelity": 1}
    scopes = sorted(
        {record.evidence_scope for record in records},
        key=lambda scope: (scope_order.get(scope, 99), scope),
    )
    largest_scope = max(
        (
            len(
                {
                    record.state_id
                    for record in records
                    if record.evidence_scope == scope
                }
            )
            for scope in scopes
        ),
        default=0,
    )
    height = max(6.8, 3.1 + 0.36 * largest_scope)
    fig = plt.figure(figsize=(15.0, height), facecolor="#FCFBF8")
    fig.text(
        0.075,
        0.95,
        "Reference support for cell and midbrain regional states",
        fontsize=16,
        fontweight="bold",
        color="#24313A",
    )
    fig.text(
        0.075,
        0.91,
        (
            f"Product case: {_source_label(profile.product_case_ref.object_id)}  |  Median pseudobulk "
            "Spearman correlation; states are ordered by median support"
        ),
        fontsize=9.2,
        color="#5B6870",
    )
    fig.text(
        0.97,
        0.95,
        f"Reference evidence: {_status_label(profile.reference_support_applicability)}",
        ha="right",
        fontsize=8.5,
        fontweight="bold",
        color="#53616A",
        bbox={"boxstyle": "round,pad=0.35", "fc": "#E8F0F4", "ec": "none"},
    )
    if not records:
        ax = fig.add_axes((0.075, 0.2, 0.85, 0.58))
        ax.axis("off")
        ax.text(
            0.02,
            0.72,
            "Reference-state expression support was not assessed",
            fontsize=15,
            fontweight="bold",
            color="#59666E",
        )
        reasons = ", ".join(
            _reason_label(reason) for reason in profile.reference_support_reason_codes
        )
        ax.text(
            0.02,
            0.58,
            reasons or "No assessable reference-state records were produced.",
            fontsize=10,
            color="#7A838A",
            wrap=True,
        )
    else:
        grid = fig.add_gridspec(
            1,
            len(scopes),
            left=0.16,
            right=0.93,
            top=0.78,
            bottom=0.14,
            wspace=0.72,
        )
        axes = []
        image = None
        cmap = LinearSegmentedColormap.from_list(
            "bridge_support", ["#8293C5", "#F7F5EF", "#D77F73"]
        ).with_extremes(bad="#D6D9DC")
        for index, scope in enumerate(scopes):
            scope_records = [
                record for record in records if record.evidence_scope == scope
            ]
            profiles = sorted(
                {
                    (
                        record.profile_id,
                        record.source_id,
                        record.profile_assay,
                        record.developmental_time,
                    )
                    for record in scope_records
                }
            )
            state_pairs = {
                (record.state_id, record.display_name) for record in scope_records
            }
            state_support = {}
            for state_id, _ in state_pairs:
                values = [
                    record.median_spearman_support
                    for record in scope_records
                    if record.state_id == state_id
                    and record.median_spearman_support is not None
                ]
                state_support[state_id] = float(np.median(values)) if values else np.nan
            states = sorted(
                state_pairs,
                key=lambda item: (
                    not np.isfinite(state_support[item[0]]),
                    (
                        -state_support[item[0]]
                        if np.isfinite(state_support[item[0]])
                        else 0
                    ),
                    item[1],
                ),
            )
            profile_index = {
                profile_id: column
                for column, (profile_id, _, _, _) in enumerate(profiles)
            }
            state_index = {state_id: row for row, (state_id, _) in enumerate(states)}
            matrix = np.full((len(states), len(profiles)), np.nan)
            record_by_cell = {}
            for record in scope_records:
                row = state_index[record.state_id]
                column = profile_index[record.profile_id]
                matrix[row, column] = (
                    np.nan
                    if record.median_spearman_support is None
                    else record.median_spearman_support
                )
                record_by_cell[(row, column)] = record
            ax = fig.add_subplot(grid[0, index])
            axes.append(ax)
            image = ax.imshow(
                np.ma.masked_invalid(matrix),
                vmin=-1,
                vmax=1,
                cmap=cmap,
                aspect="auto",
            )
            ax.set_yticks(
                np.arange(len(states)),
                [_display_label(display_name) for _, display_name in states],
                fontsize=8,
            )
            ax.set_xticks(
                np.arange(len(profiles)),
                [
                    f"{_source_label(source)}\n"
                    f"{_display_label(assay)} | {_display_label(time)}"
                    for _, source, assay, time in profiles
                ],
                fontsize=7.3,
            )
            ax.tick_params(top=True, bottom=False, labeltop=True, labelbottom=False)
            for row in range(matrix.shape[0]):
                for column in range(matrix.shape[1]):
                    record = record_by_cell.get((row, column))
                    value = matrix[row, column]
                    label = (
                        "—"
                        if record is None
                        else (
                            f"{value:.2f}\nn={record.n_available_analysis_units}/"
                            f"{record.n_analysis_units}"
                            if np.isfinite(value)
                            else f"NA\nn=0/{record.n_analysis_units}"
                        )
                    )
                    ax.text(
                        column,
                        row,
                        label,
                        ha="center",
                        va="center",
                        fontsize=6.8,
                        linespacing=1.2,
                        color=(
                            "#25323A"
                            if not np.isfinite(value) or abs(value) < 0.52
                            else "#FFFFFF"
                        ),
                    )
            ax.set_xticks(np.arange(-0.5, len(profiles), 1), minor=True)
            ax.set_yticks(np.arange(-0.5, len(states), 1), minor=True)
            ax.grid(which="minor", color="#FFFFFF", linewidth=1.2)
            ax.tick_params(which="minor", bottom=False, left=False)
            ax.set_title(
                {
                    "target_identity": "Cell-state identity support",
                    "regional_fidelity": "Midbrain regional support",
                }.get(scope, _display_label(scope).title()),
                loc="left",
                fontsize=10,
                fontweight="bold",
                color="#2B3942",
                pad=12,
            )
            for spine in ax.spines.values():
                spine.set_visible(False)
        colorbar = fig.colorbar(image, ax=axes, fraction=0.025, pad=0.025)
        colorbar.set_label("Spearman correlation", fontsize=8)
        colorbar.ax.tick_params(labelsize=7)
    fig.text(
        0.075,
        0.055,
        (
            "Exact analysis-unit ranges and shared-gene counts are in the table. "
            "An em dash denotes a state/reference combination that was not produced. "
            "Correlation is not a calibrated identity probability or spatial position."
        ),
        fontsize=8.5,
        color="#65717A",
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
    component_ref,
    data_artifact,
    table_artifact,
    render_artifacts,
    run_id,
    tool_version,
    data_hash,
    render_reason,
):
    component_id, component_version = component_ref.split("@", 1)
    role_component = component_ref == ROLE_COMPONENT_REF
    records = profile.product_records if role_component else profile.reference_records
    if role_component:
        evidence_states = sorted(
            {record.evidence_state for record in records},
            key=str,
        )
        reasons = sorted(
            {
                *(
                    reason
                    for record in records
                    for reason in record.reason_codes
                    if record.evidence_state
                    in {
                        EvidenceState.MISSING,
                        EvidenceState.UNKNOWN,
                        EvidenceState.UNAVAILABLE,
                    }
                ),
                *(
                    reason
                    for record in records
                    for reason in record.channel_reason_codes
                    if record.channel_assessment_state != "complete"
                ),
            }
        )
        record_applicability = {record.applicability for record in records}
        applicability = (
            "applicable"
            if record_applicability == {"applicable"}
            else (
                "not_assessed"
                if record_applicability == {"not_assessed"}
                else "partially_applicable"
            )
        )
    else:
        evidence_states = sorted(
            {record.evidence_state for record in records}
            or {profile.reference_support_state},
            key=str,
        )
        reasons = sorted(
            {
                *profile.reference_support_reason_codes,
                *(
                    reason
                    for record in records
                    for reason in record.reason_codes
                    if record.evidence_state
                    in {
                        EvidenceState.MISSING,
                        EvidenceState.UNKNOWN,
                        EvidenceState.UNAVAILABLE,
                    }
                ),
            }
        )
        applicability = profile.reference_support_applicability

    if render_reason:
        reasons = sorted({*reasons, render_reason})
        if applicability == "applicable":
            applicability = "partially_applicable"

    bindings = VisualizationDataBinding(
        artifact_id=data_artifact.artifact_id,
        schema_ref=TARGET_REGIONAL_VISUALIZATION_DATA_SCHEMA_REF,
        object_version="0.1.0",
        sha256=data_hash,
        records_path="product_records" if role_component else "reference_records",
        record_lookup_key="record_id",
        evidence_ids_field="evidence_ids",
        value_field=None if role_component else "median_spearman_support",
        numerator_field="count" if role_component else None,
        denominator_field="product_denominator" if role_component else None,
        denominator_scope_field="denominator_scope" if role_component else None,
        unit_field="unit" if role_component else None,
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
            data_sha256=data_hash,
            config_sha256=_config_sha256(component_ref),
        )
        for extension in ("svg", "png", "pdf")
    ]
    title = (
        "Product composition relative to the declared regional identity"
        if role_component
        else "Reference support for cell states and midbrain regional identity"
    )
    takeaway = (
        (
            "The full result remains available in the exact table and typed JSON; "
            "the static page was replaced by a size-safe fallback."
        )
        if render_reason
        else (
            "Counts use the selected product view and preserve unresolved observations."
            if role_component
            else "Support values remain separated by reference source, assay and evidence scope."
        )
    )
    limitations = [
        "Candidate state and product-role definitions have not completed scientific release review.",
        "Observation counts are not biological replicates and do not provide composition confidence intervals.",
        "Reference-conditioned support does not establish product position in fetal tissue, potency, efficacy or safety.",
    ]
    return VisualizationArtifactV2(
        visualization_id=f"visualization:{run_id}:{component_id.rsplit('.', 1)[-1]}",
        component_id=component_id,
        component_version=component_version,
        data_binding=bindings,
        producer_tool_id="P0-03",
        producer_tool_version=tool_version,
        producer_run_ref=f"run:{run_id}",
        evidence_ids=profile.evidence_ids,
        evidence_states=evidence_states,
        scientific_status="candidate",
        applicability=applicability,
        missing_reason_codes=reasons,
        denominator_label="selected product view" if role_component else None,
        denominator_scope="selected_product_view" if role_component else None,
        unit="observations" if role_component else "correlation",
        insight_title=title,
        takeaway=takeaway,
        limitations=limitations,
        accessibility=VisualizationAccessibility(
            alt_text=title,
            long_description=(
                f"{title}. {takeaway} "
                "The table fallback contains exact values, states and reason codes."
            ),
            table_artifact_id=table_artifact.artifact_id,
            data_sha256=data_hash,
        ),
        renders=renders,
    )


def _config_sha256(component_ref):
    renderer_source_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    payload = canonical_json_bytes(
        {
            "component_ref": component_ref,
            "renderer_id": _RENDERER_ID,
            "renderer_version": _RENDERER_VERSION,
            "export_profile_id": _EXPORT_PROFILE_ID,
            "renderer_source_sha256": renderer_source_sha256,
            "matplotlib_version": matplotlib.__version__,
            "numpy_version": np.__version__,
            "matplotlib_rc": _MATPLOTLIB_RC,
            "role_colors": _ROLE_COLORS,
            "role_markers": _ROLE_MARKERS,
            "level_labels": _LEVEL_LABELS,
        }
    )
    return hashlib.sha256(payload).hexdigest()


def _display_label(value):
    return str(value).replace("_", " ").replace("-", " ")


def _source_label(value):
    if not value:
        return "all reference sources"
    label = str(value)
    if ":" in label:
        label = label.split(":", 1)[1]
    return _display_label(label)


def _reason_label(value):
    labels = {
        "count_ready_expression_not_available": (
            "A count-based expression matrix was not available for reference comparison."
        ),
        "reference_support_not_available": (
            "Reference-state expression support was not available for this input."
        ),
        "reference_state_support_not_available": (
            "Reference-state expression support was not available for this input."
        ),
        "static_render_requires_table_fallback": (
            "The result is available in the exact table and typed JSON; "
            "the static page exceeded its safe display size."
        ),
    }
    return labels.get(str(value), _display_label(value))


def _status_label(value):
    labels = {
        "applicable": "available",
        "partially_applicable": "partial",
        "not_assessed": "not assessed",
        "not_applicable": "not applicable",
        "draft": "draft",
        "approved": "approved",
        "partial": "partial",
        "unavailable": "unavailable",
    }
    return labels.get(str(value), _display_label(value))


def _manifest(
    run_id,
    suffix,
    kind,
    path,
    media_type,
    payload,
    evidence_ids,
):
    return ArtifactManifest(
        artifact_id=f"artifact:{run_id}:{suffix}",
        kind=kind,
        path=path,
        media_type=media_type,
        sha256=hashlib.sha256(payload).hexdigest(),
        evidence_ids=evidence_ids,
    )
