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
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from matplotlib.transforms import blended_transform_factory

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_06_proliferation_stress_response.visualization_data import (
    CELL_CYCLE_COMPONENT_REF,
    PROGRAM_EVIDENCE_COMPONENT_REF,
    PROGRAM_SCORE_COMPONENT_REF,
    PROLIFERATION_STRESS_VISUALIZATION_DATA_SCHEMA_REF,
    CellCycleVisualizationRecord,
    MethodAgreementVisualizationRecord,
    P006VisualizationArtifactSet,
    ProgramEvidenceVisualizationRecord,
    ProgramScoreVisualizationRecord,
    ProliferationStressVisualizationDataV1,
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
_BG, _TEXT, _MUTED, _GRID = "#FCFBF8", "#24323A", "#68757C", "#DCE2E3"
_ACCENT, _LIGHT, _PURPLE = "#4F858D", "#B9CFD2", "#7A6997"
_METHOD_COLORS = {
    "PROC-SCORE-SCANPY": "#3F7C94",
    "PROC-SCORE-DECOUPLER": "#77619B",
}
_PHASE_STYLES = {
    "G1": ("#AEB6BA", ""),
    "S": ("#5B94AF", "///"),
    "G2M": ("#806D9C", "xx"),
}
_RC = {
    "font.family": ["DejaVu Sans"],
    "font.sans-serif": ["DejaVu Sans"],
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
    "svg.hashsalt": "BRIDGE-P0-06",
}


@dataclass(frozen=True)
class PreparedProliferationStressVisualizations:
    payloads: dict[str, bytes]
    artifacts: tuple[ArtifactManifest, ...]


@dataclass(frozen=True)
class _Group:
    label: str
    model: type
    path: str


@dataclass(frozen=True)
class _Component:
    ref: str
    slug: str
    path: str
    table: str
    title: str
    groups: tuple[_Group, ...]


_COMPONENTS = (
    _Component(
        PROGRAM_EVIDENCE_COMPONENT_REF,
        "program-evidence",
        "program_evidence_records",
        "proliferation_stress_program_evidence.tsv",
        "Stage- and cell-state-conditioned transcriptomic program evidence",
        (
            _Group(
                "program_evidence",
                ProgramEvidenceVisualizationRecord,
                "program_evidence_records",
            ),
        ),
    ),
    _Component(
        PROGRAM_SCORE_COMPONENT_REF,
        "program-score-summary",
        "program_score_records",
        "proliferation_stress_program_score_summary.tsv",
        "Transcriptomic program scores in the selected expression view",
        (
            _Group(
                "program_score",
                ProgramScoreVisualizationRecord,
                "program_score_records",
            ),
            _Group(
                "method_agreement_table_only",
                MethodAgreementVisualizationRecord,
                "method_agreement_records",
            ),
        ),
    ),
    _Component(
        CELL_CYCLE_COMPONENT_REF,
        "cell-cycle",
        "cell_cycle_records",
        "proliferation_stress_cell_cycle.tsv",
        "Transcriptionally assigned cell-cycle phases",
        (_Group("cell_cycle", CellCycleVisualizationRecord, "cell_cycle_records"),),
    ),
)
_LIMITS = {
    PROGRAM_EVIDENCE_COMPONENT_REF: (
        (
            "Assessment, gene coverage, LOD, evidence state, process attribution and "
            "shadow routing remain explicit; the reference envelope was not assessed."
        ),
        [
            "Reference envelopes were not assessed.",
            "Process attribution is conditional or unresolved, not causal.",
            "Shadow flags are not safety, potency or release decisions.",
        ],
    ),
    PROGRAM_SCORE_COMPONENT_REF: (
        (
            "Method-specific medians and cell intervals keep whole-view and candidate-state "
            "scope separate without putting Scanpy and ULM on one scale."
        ),
        [
            "Cell distributions are not confidence intervals or independent biological replicates.",
            "Scanpy control-adjusted expression and decoupler ULM t-values are not directly comparable.",
            "Reference envelopes and biological-unit uncertainty were not assessed.",
        ],
    ),
    CELL_CYCLE_COMPONENT_REF: (
        (
            "G1, S and G2M assignments are shown with n, mean phase scores and gene "
            "coverage for each declared analysis unit."
        ),
        [
            "S plus G2M is an assigned fraction, not an observed division or proliferation rate.",
            "Cells are not independent biological replicates.",
            "Reference envelopes were not assessed.",
        ],
    ),
}


def prepare_proliferation_stress_visualizations(
    *,
    profile: ProliferationStressVisualizationDataV1,
    output_dir: Path,
    run_id: str,
    tool_version: str,
) -> PreparedProliferationStressVisualizations:
    final_dir = output_dir / run_id
    payloads: dict[str, bytes] = {}
    artifacts: list[ArtifactManifest] = []
    data_name = "proliferation_stress_visualization_data.json"
    data = canonical_json_bytes(profile.model_dump(mode="json"), indent=2)
    payloads[data_name] = data
    data_artifact = _manifest(
        run_id,
        "proliferation-stress-visualization-data",
        "proliferation_stress_visualization_data",
        final_dir / data_name,
        "application/json",
        data,
        profile.evidence_ids,
    )
    artifacts.append(data_artifact)
    tables, renders, reasons = {}, {}, {}
    renderers = {
        PROGRAM_EVIDENCE_COMPONENT_REF: _render_program_evidence,
        PROGRAM_SCORE_COMPONENT_REF: _render_program_scores,
        CELL_CYCLE_COMPONENT_REF: _render_cell_cycle,
    }
    with matplotlib.rc_context(rc=_RC):
        for component in _COMPONENTS:
            table = _table(profile, component.groups)
            payloads[component.table] = table
            tables[component.ref] = _manifest(
                run_id,
                f"proliferation-stress-{component.slug}-table",
                "visualization_table",
                final_dir / component.table,
                "text/tab-separated-values",
                table,
                profile.evidence_ids,
            )
            artifacts.append(tables[component.ref])
            reasons[component.ref] = _fallback_reason(profile, component.ref)
            figure = (
                _empty(
                    component.title,
                    "This result exceeds static capacity; use the typed table.",
                    [reasons[component.ref]],
                    component.ref,
                )
                if reasons[component.ref]
                else renderers[component.ref](profile)
            )
            for extension, (media_type, rendered) in _render_payloads(figure).items():
                name = f"proliferation_stress_{component.slug}.{extension}"
                payloads[name] = rendered
                artifact = _manifest(
                    run_id,
                    f"proliferation-stress-{component.slug}-{extension}",
                    "visualization_render",
                    final_dir / name,
                    media_type,
                    rendered,
                    profile.evidence_ids,
                )
                renders[(component.ref, extension)] = artifact
                artifacts.append(artifact)
    visualizations = [
        _contract(
            profile,
            component,
            data_artifact,
            tables[component.ref],
            {ext: renders[(component.ref, ext)] for ext in ("svg", "png", "pdf")},
            run_id,
            tool_version,
            reasons[component.ref],
        )
        for component in _COMPONENTS
    ]
    registry = FigureRegistry.load_default()
    for visualization in visualizations:
        registry.validate_artifact(visualization)
    artifact_set = P006VisualizationArtifactSet(
        artifact_set_id=f"p0-06-visualizations:{run_id.removeprefix('run-')}",
        data_profile_artifact_id=data_artifact.artifact_id,
        data_profile_sha256=data_artifact.sha256,
        visualizations=visualizations,
    )
    set_name = "proliferation_stress_visualization_artifact_set.json"
    set_data = canonical_json_bytes(artifact_set.model_dump(mode="json"), indent=2)
    payloads[set_name] = set_data
    artifacts.append(
        _manifest(
            run_id,
            "proliferation-stress-visualization-artifact-set",
            "visualization_artifact_set",
            final_dir / set_name,
            "application/json",
            set_data,
            profile.evidence_ids,
        )
    )
    return PreparedProliferationStressVisualizations(payloads, tuple(artifacts))


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
        writer.writerow(
            {
                key: (
                    json.dumps(
                        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    )
                    if isinstance(value, (list, dict))
                    else ""
                    if value is None
                    else value
                )
                for key, value in row.items()
            }
        )
    return buffer.getvalue().encode()


def _fallback_reason(profile, ref):
    if ref == PROGRAM_EVIDENCE_COMPONENT_REF:
        too_large = len(profile.program_evidence_records) > 16
    elif ref == PROGRAM_SCORE_COMPONENT_REF:
        facets = {
            (_value(row.method_id), row.program_id, row.score_unit)
            for row in profile.program_score_records
        }
        too_large = len(profile.program_score_records) > 36 or len(facets) > 10
    else:
        too_large = len(profile.cell_cycle_records) > 18
    return "static_render_requires_table_fallback" if too_large else None


def _base(title, subtitle, height, ref):
    fig = plt.figure(figsize=(_WIDTH, height), facecolor=_BG)
    fig.text(
        0.04, 0.965, title, fontsize=11.2, fontweight="bold", color=_TEXT, va="top"
    )
    if subtitle:
        fig.text(0.04, 0.915, subtitle, fontsize=7.6, color=_MUTED, va="top")
    fig.text(
        0.04,
        0.025,
        textwrap.fill(_footnote(ref), width=96),
        fontsize=6.65,
        color=_MUTED,
        va="bottom",
        linespacing=1.22,
    )
    return fig


def _empty(title, message, reasons, ref):
    fig = _base(title, "", 4.9, ref)
    ax = fig.add_axes((0.07, 0.17, 0.86, 0.61))
    ax.axis("off")
    ax.text(0, 0.72, "—  not assessed", fontsize=14, fontweight="bold", color=_MUTED)
    ax.text(0, 0.48, message, fontsize=9.4, color=_TEXT)
    reason = " · ".join(_label(item) for item in sorted(set(reasons)) if item)
    ax.text(
        0,
        0.28,
        textwrap.fill(reason or "No assessable records were produced.", width=88),
        fontsize=7.4,
        color=_MUTED,
        va="top",
    )
    return fig


def _render_program_evidence(profile):
    rows = sorted(
        profile.program_evidence_records,
        key=lambda row: (
            row.program_id,
            _scope_rank(row.analysis_scope),
            row.cell_state_id or "",
            row.stage_id,
        ),
    )
    if not rows:
        return _empty(
            "Stage- and cell-state-conditioned transcriptomic program evidence",
            "Program evidence was not assessed in this run.",
            profile.program_evidence_component_reason_codes,
            PROGRAM_EVIDENCE_COMPONENT_REF,
        )
    fig = _base(
        "Stage- and cell-state-conditioned transcriptomic program evidence",
        "What was assessed and unresolved · supplied metrics retain their own units · reference envelope not assessed",
        max(5.0, 2.75 + 0.43 * len(rows)),
        PROGRAM_EVIDENCE_COMPONENT_REF,
    )
    ax = fig.add_axes((0.025, 0.14, 0.95, 0.69))
    ax.set(xlim=(0, 1), ylim=(-0.72, len(rows) + 0.85))
    ax.axis("off")
    edges = (0.01, 0.205, 0.29, 0.395, 0.505, 0.615, 0.69, 0.765, 0.875, 0.995)
    headers = (
        "Program / scope / state",
        "Assessment",
        "Supplied\nresult",
        "Gene coverage",
        "Reference\nenvelope",
        "LOD",
        "Evidence\nstate",
        "Process\nattribution",
        "Shadow review\nrouting",
    )
    for index, header in enumerate(headers):
        x = edges[0] + 0.007 if index == 0 else (edges[index] + edges[index + 1]) / 2
        ax.text(
            x,
            len(rows) + 0.48,
            header,
            ha="left" if index == 0 else "center",
            va="center",
            fontsize=6.1,
            fontweight="bold",
            color=_TEXT,
            linespacing=1.05,
        )
    ax.plot([edges[0], edges[-1]], [len(rows) + 0.05] * 2, color=_TEXT, linewidth=0.8)
    for edge in edges[1:-1]:
        ax.plot([edge, edge], [-0.42, len(rows) + 0.68], color=_GRID, linewidth=0.55)
    for index, record in enumerate(rows):
        y = len(rows) - index - 1
        if index % 2:
            ax.add_patch(
                Rectangle(
                    (edges[0], y - 0.43),
                    edges[-1] - edges[0],
                    0.86,
                    facecolor="#F5F4F0",
                    edgecolor="none",
                    zorder=-2,
                )
            )
        ax.plot([edges[0], edges[-1]], [y - 0.43] * 2, color=_GRID, linewidth=0.45)
        ax.text(
            edges[0] + 0.007,
            y + 0.12,
            _id_label(record.program_id, 23),
            fontsize=7.15,
            fontweight="bold",
            color=_TEXT,
            va="center",
        )
        ax.text(
            edges[0] + 0.007,
            y - 0.17,
            _scope_label(record, evidence=True),
            fontsize=6.15,
            color=_MUTED,
            va="center",
        )
        assessed = record.assessment_state == "available"
        center = (edges[1] + edges[2]) / 2
        ax.scatter(
            center,
            y + 0.12,
            s=22,
            marker="o",
            facecolor=_ACCENT if assessed else _BG,
            edgecolor=_ACCENT if assessed else _MUTED,
            linewidth=0.9,
        )
        ax.text(
            center,
            y - 0.16,
            "available" if assessed else "— not assessed",
            fontsize=6.25,
            color=_TEXT if assessed else _MUTED,
            ha="center",
            va="center",
            linespacing=1.0,
        )
        ax.text(
            (edges[2] + edges[3]) / 2,
            y,
            _result(record),
            ha="center",
            va="center",
            fontsize=5.9,
            color=_TEXT,
            linespacing=1.02,
        )
        _coverage(ax, edges[3] + 0.008, edges[4] - 0.008, y, record)
        values = (
            "—\nnot assessed",
            _state(record.lod_state),
            _state(record.source_evidence_state),
            _process(record),
            _review(record),
        )
        for column, value in enumerate(values, start=4):
            ax.text(
                (edges[column] + edges[column + 1]) / 2,
                y,
                value,
                ha="center",
                va="center",
                fontsize=6.05,
                color=_MUTED if value.startswith("—") else _TEXT,
                linespacing=1.04,
            )
    return fig


def _coverage(ax, x0, x1, y, record):
    width = (x1 - x0) * 0.63
    ax.add_patch(Rectangle((x0, y - 0.08), width, 0.16, color="#E9EDEB", ec="none"))
    ax.add_patch(
        Rectangle(
            (x0, y - 0.08), width * record.gene_coverage, 0.16, color=_LIGHT, ec="none"
        )
    )
    threshold = x0 + width * record.minimum_gene_coverage
    ax.plot([threshold] * 2, [y - 0.12, y + 0.12], color=_TEXT, linewidth=0.7)
    ax.text(
        x1,
        y,
        f"{record.gene_coverage * 100:.0f}%\nmin {record.minimum_gene_coverage * 100:.0f}%",
        ha="right",
        va="center",
        fontsize=5.7,
        color=_TEXT,
        linespacing=1.0,
    )


def _render_program_scores(profile):
    rows = list(profile.program_score_records)
    if not any(
        row.assessment_state == "available" and row.median is not None for row in rows
    ):
        return _empty(
            "Transcriptomic program scores in the selected expression view",
            "Program-score methods were not assessed in this run.",
            profile.program_score_component_reason_codes,
            PROGRAM_SCORE_COMPONENT_REF,
        )
    groups = {}
    for record in rows:
        groups.setdefault(
            (_value(record.method_id), record.program_id, record.score_unit), []
        ).append(record)
    ordered = sorted(
        groups.items(),
        key=lambda item: (item[0][1], _method_rank(item[0][0]), item[0][2]),
    )
    ncols = 2 if len(ordered) > 1 else 1
    nrows = math.ceil(len(ordered) / ncols)
    fig = _base(
        "Transcriptomic program scores in the selected expression view",
        f"Median + {_quantile(profile)} cell interval · cell distribution; not a confidence interval",
        max(5.6, 3.45 + 2.15 * nrows),
        PROGRAM_SCORE_COMPONENT_REF,
    )
    fig.legend(
        handles=[
            Line2D(
                [0],
                [0],
                marker="o",
                markersize=5,
                markerfacecolor=_ACCENT,
                markeredgecolor=_ACCENT,
                linestyle="none",
                label="whole selected view",
            ),
            Line2D(
                [0],
                [0],
                marker="D",
                markersize=5,
                markerfacecolor=_BG,
                markeredgecolor=_PURPLE,
                linestyle="none",
                label="candidate state subset",
            ),
        ],
        loc="upper left",
        bbox_to_anchor=(0.045, 0.885),
        ncol=2,
        frameon=False,
        fontsize=7.0,
        handletextpad=0.45,
        columnspacing=1.4,
    )
    grid = fig.add_gridspec(
        nrows,
        ncols,
        left=0.185,
        right=0.965,
        bottom=0.15,
        top=0.80,
        wspace=0.68,
        hspace=1.03,
    )
    for index, ((method, program, unit), records) in enumerate(ordered):
        _score_facet(
            fig.add_subplot(grid[index // ncols, index % ncols]),
            method,
            program,
            unit,
            records,
        )
    if len(ordered) % ncols:
        fig.add_subplot(grid[-1, -1]).axis("off")
    return fig


def _score_facet(ax, method, program, unit, records):
    records = sorted(
        records,
        key=lambda row: (
            _scope_rank(row.analysis_scope),
            row.analysis_unit_ref,
            row.cell_state_id or "",
        ),
    )
    values = [
        value
        for record in records
        for value in (
            record.cell_distribution_lower_quantile,
            record.median,
            record.cell_distribution_upper_quantile,
        )
        if value is not None
    ]
    low, high = _numeric_limits(values)
    ys = list(reversed(range(len(records))))
    color = _METHOD_COLORS.get(method, _ACCENT)
    ax.set(xlim=(low, high), ylim=(-0.65, len(records) - 0.35))
    ax.set_yticks(
        ys,
        [
            f"{_id_label(row.analysis_unit_ref, 16)}\n{_scope_label(row)}"
            for row in records
        ],
        fontsize=6.2,
    )
    ax.tick_params(axis="y", length=0, pad=4, colors=_TEXT)
    ax.tick_params(axis="x", labelsize=6.3, colors=_MUTED)
    ax.grid(axis="x", color=_GRID, linewidth=0.65)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title(
        f"{_id_label(program, 20)}\n{_method_label(method)} · own axis",
        fontsize=7.2,
        color=_TEXT,
        loc="left",
        pad=7,
    )
    ax.set_xlabel(_unit_label(unit), fontsize=6.5, color=_MUTED)
    transform = blended_transform_factory(ax.transAxes, ax.transData)
    for y, row in zip(ys, records, strict=True):
        complete = (
            row.assessment_state == "available"
            and row.median is not None
            and row.cell_distribution_lower_quantile is not None
            and row.cell_distribution_upper_quantile is not None
        )
        if complete:
            ax.plot(
                [
                    row.cell_distribution_lower_quantile,
                    row.cell_distribution_upper_quantile,
                ],
                [y, y],
                color=color,
                linewidth=2.1,
                solid_capstyle="round",
            )
            state_specific = _value(row.analysis_scope) != "whole_product"
            ax.scatter(
                row.median,
                y,
                marker="D" if state_specific else "o",
                s=31,
                facecolor=_BG if state_specific else color,
                edgecolor=_PURPLE if state_specific else color,
                linewidth=1.0,
                zorder=3,
            )
            note = f"n={row.n_observations:,} · genes {row.observed_gene_count}/{row.declared_gene_count}"
        else:
            ax.text(
                0.02,
                y,
                "— not assessed",
                transform=transform,
                fontsize=6.3,
                color=_MUTED,
                va="center",
            )
            note = "— not assessed"
        ax.text(
            0.99,
            y + 0.28,
            note,
            transform=transform,
            ha="right",
            va="center",
            fontsize=5.6,
            color=_MUTED,
            bbox={"facecolor": _BG, "edgecolor": "none", "pad": 0.5},
        )


def _render_cell_cycle(profile):
    rows = sorted(
        profile.cell_cycle_records,
        key=lambda row: (
            _scope_rank(row.analysis_scope),
            row.analysis_unit_ref,
            row.cell_state_id or "",
        ),
    )
    if not any(
        row.assessment_state == "available" and row.g1_fraction is not None
        for row in rows
    ):
        return _empty(
            "Transcriptionally assigned cell-cycle phases",
            "Cell-cycle assignment was not assessed in this run.",
            profile.cell_cycle_component_reason_codes,
            CELL_CYCLE_COMPONENT_REF,
        )
    fig = _base(
        "Transcriptionally assigned cell-cycle phases",
        "Composition by analysis unit · candidate state subsets remain separate from the whole selected view",
        max(5.4, 3.35 + 0.50 * len(rows)),
        CELL_CYCLE_COMPONENT_REF,
    )
    fig.legend(
        handles=[
            Patch(facecolor=color, edgecolor="white", hatch=hatch, label=phase)
            for phase, (color, hatch) in _PHASE_STYLES.items()
        ],
        loc="upper left",
        bbox_to_anchor=(0.235, 0.885),
        ncol=3,
        frameon=False,
        fontsize=7.0,
        handlelength=1.4,
        columnspacing=1.25,
    )
    grid = fig.add_gridspec(
        1,
        2,
        left=0.235,
        right=0.97,
        bottom=0.18,
        top=0.79,
        width_ratios=(3.1, 2.45),
        wspace=0.07,
    )
    ax, info = fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1])
    ys = list(reversed(range(len(rows))))
    ax.set(xlim=(0, 1.13), ylim=(-0.68, len(rows) - 0.30))
    ax.set_yticks(
        ys,
        [
            f"{_id_label(row.analysis_unit_ref, 18)}\n{_scope_label(row)}"
            for row in rows
        ],
        fontsize=6.4,
    )
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1], ["0", "25", "50", "75", "100%"])
    ax.tick_params(axis="x", labelsize=6.5, colors=_MUTED)
    ax.tick_params(axis="y", length=0, pad=5, colors=_TEXT)
    ax.grid(axis="x", color=_GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for y, row in zip(ys, rows, strict=True):
        if row.assessment_state != "available" or row.g1_fraction is None:
            ax.add_patch(
                Rectangle(
                    (0, y - 0.25),
                    1,
                    0.50,
                    facecolor="#F1F2F0",
                    edgecolor=_GRID,
                    hatch="//",
                )
            )
            ax.text(
                0.5,
                y,
                "— not assessed",
                ha="center",
                va="center",
                fontsize=6.6,
                color=_MUTED,
            )
            continue
        left = 0.0
        for phase, fraction in (
            ("G1", row.g1_fraction),
            ("S", row.s_fraction),
            ("G2M", row.g2m_fraction),
        ):
            color, hatch = _PHASE_STYLES[phase]
            ax.barh(
                y,
                fraction,
                left=left,
                height=0.52,
                color=color,
                edgecolor="white",
                linewidth=0.7,
                hatch=hatch,
            )
            if fraction >= 0.085:
                ax.text(
                    left + fraction / 2,
                    y,
                    f"{fraction * 100:.0f}%",
                    ha="center",
                    va="center",
                    fontsize=5.8,
                    color="#FFFFFF" if phase != "G1" else _TEXT,
                    fontweight="bold",
                )
            left += fraction
        ax.text(
            1.015,
            y,
            f"n={row.n_observations:,}",
            fontsize=6.0,
            color=_MUTED,
            va="center",
        )
    info.set(xlim=(0, 1), ylim=ax.get_ylim())
    info.axis("off")
    headers = (
        (0.15, "Assigned S+G2M\nfraction"),
        (0.53, "Mean S / G2M\nscore"),
        (0.86, "S / G2M gene\ncoverage"),
    )
    for x, label in headers:
        info.text(
            x,
            len(rows) - 0.08,
            label,
            ha="center",
            va="bottom",
            fontsize=6.1,
            fontweight="bold",
            color=_TEXT,
            linespacing=1.05,
        )
    for y, row in zip(ys, rows, strict=True):
        values = (
            (
                _percent(row.cycling_fraction),
                f"{_number(row.mean_s_score)} / {_number(row.mean_g2m_score)}",
                f"{_percent(row.s_gene_coverage)} / {_percent(row.g2m_gene_coverage)}",
            )
            if row.assessment_state == "available"
            else ("—", "— / —", "— / —")
        )
        for (x, _), value in zip(headers, values, strict=True):
            info.text(
                x,
                y,
                value,
                ha="center",
                va="center",
                fontsize=6.2,
                color=_MUTED if value.startswith("—") else _TEXT,
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
            metadata = {"Creator": "BRIDGE"}
            if extension == "svg":
                metadata["Date"] = None
                fig.savefig(buffer, format="svg", metadata=metadata)
            elif extension == "png":
                fig.savefig(
                    buffer, format="png", dpi=220, metadata={"Software": "BRIDGE"}
                )
            else:
                metadata.update({"CreationDate": None, "ModDate": None})
                fig.savefig(buffer, format="pdf", metadata=metadata)
            outputs[extension] = (media_type, buffer.getvalue())
    finally:
        plt.close(fig)
    return outputs


def _contract(
    profile,
    component,
    data_artifact,
    table_artifact,
    render_artifacts,
    run_id,
    tool_version,
    render_reason,
):
    state, reasons = _component_state(profile, component.ref)
    if render_reason:
        reasons.add(render_reason)
    evidence_states, applicability = _artifact_states(state)
    if render_reason and applicability == "applicable":
        applicability = "partially_applicable"
    if "unavailable" in evidence_states and not reasons:
        reasons.add(f"{component.slug.replace('-', '_')}_not_assessed")
    binding = {"value_field": "value", "unit_field": "unit"}
    if component.ref == PROGRAM_SCORE_COMPONENT_REF:
        binding = {
            "value_field": "median",
            "unit_field": "score_unit",
            "interval_lower_field": "cell_distribution_lower_quantile",
            "interval_upper_field": "cell_distribution_upper_quantile",
            "interval_semantics": "Selected-view cell distribution; not a confidence interval.",
        }
    elif component.ref == CELL_CYCLE_COMPONENT_REF:
        binding = {"value_field": "cycling_fraction"}
    data_binding = VisualizationDataBinding(
        artifact_id=data_artifact.artifact_id,
        schema_ref=PROLIFERATION_STRESS_VISUALIZATION_DATA_SCHEMA_REF,
        object_version="0.1.0",
        sha256=data_artifact.sha256,
        records_path=component.path,
        record_lookup_key="record_id",
        evidence_ids_field="evidence_ids",
        evidence_state_field="evidence_state",
        scientific_status_field="scientific_status",
        missingness_field="assessment_state",
        applicability_field="assessment_state",
        **binding,
    )
    component_id, component_version = component.ref.split("@", 1)
    takeaway, limitations = _LIMITS[component.ref]
    renders = [
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
    ]
    return VisualizationArtifactV2(
        visualization_id=f"visualization:{run_id}:{component.slug}",
        component_id=component_id,
        component_version=component_version,
        data_binding=data_binding,
        producer_tool_id="P0-06",
        producer_tool_version=tool_version,
        producer_run_ref=f"run:{run_id}",
        evidence_ids=profile.evidence_ids,
        evidence_states=evidence_states,
        scientific_status="candidate",
        applicability=applicability,
        missing_reason_codes=sorted(reasons),
        insight_title=component.title,
        takeaway=takeaway,
        limitations=limitations,
        accessibility=VisualizationAccessibility(
            alt_text=f"{component.title}. {takeaway}",
            long_description=(
                f"{component.title}. {takeaway} The typed TSV retains every assessment "
                "and reason code; typed JSON retains provenance and boundaries."
            ),
            table_artifact_id=table_artifact.artifact_id,
            data_sha256=data_artifact.sha256,
        ),
        renders=renders,
    )


def _component_state(profile, ref):
    if ref == PROGRAM_EVIDENCE_COMPONENT_REF:
        return profile.program_evidence_component_state, set(
            profile.program_evidence_component_reason_codes
        )
    if ref == PROGRAM_SCORE_COMPONENT_REF:
        return profile.program_score_component_state, set(
            profile.program_score_component_reason_codes
        )
    return profile.cell_cycle_component_state, set(
        profile.cell_cycle_component_reason_codes
    )


def _artifact_states(state):
    return {
        "available": (["inferred"], "applicable"),
        "partial": (["inferred", "unavailable"], "partially_applicable"),
        "not_assessed": (["unavailable"], "not_assessed"),
    }[state]


def _config_hash(ref):
    source = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    payload = canonical_json_bytes(
        {
            "component_ref": ref,
            "renderer": [_RENDERER_ID, _RENDERER_VERSION, _EXPORT_PROFILE_ID],
            "source_sha256": source,
            "matplotlib_version": matplotlib.__version__,
            "matplotlib_rc": _RC,
            "method_colors": _METHOD_COLORS,
            "phase_styles": _PHASE_STYLES,
            "figure_width_in": _WIDTH,
        }
    )
    return hashlib.sha256(payload).hexdigest()


def _footnote(ref):
    prefix = (
        "— = not assessed/unavailable; ? = unresolved/unknown; neither means zero. "
    )
    if ref == PROGRAM_EVIDENCE_COMPONENT_REF:
        return prefix + (
            "Source metrics/units are not cross-row comparable. Reference envelope not "
            "assessed; candidate/shadow routing does not establish safety, potency or release."
        )
    if ref == PROGRAM_SCORE_COMPONENT_REF:
        return prefix + (
            "Intervals are cell distributions, not confidence intervals. Scanpy and ULM "
            "use separate axes; candidate/shadow results are descriptive."
        )
    return prefix + (
        "S+G2M is assigned cycling fraction, not proliferation rate. Candidate/shadow "
        "results are descriptive; reference envelopes are not assessed."
    )


def _scope_label(record, evidence=False):
    whole = _value(record.analysis_scope) == "whole_product"
    if whole:
        scope = "whole product" if evidence else "whole selected view"
    else:
        scope = f"{'state' if evidence else 'candidate state'} {_id_label(record.cell_state_id or '?', 10)}"
    return f"{scope} · stg {_id_label(record.stage_id, 9)}" if evidence else scope


def _result(record):
    if record.assessment_state != "available":
        return "—\nnot assessed"
    parts = []
    if record.value is not None:
        parts.append(_number(record.value))
        if record.unit:
            parts.append(_id_label(record.unit, 14))
    if record.numerator is not None:
        parts.append(f"{record.numerator}/{record.denominator}")
    return "\n".join(parts) if parts else "?\nunresolved"


def _process(record):
    state = _value(record.process_attribution)
    if state == "conditional_association":
        suffix = (
            f"\n{len(record.process_step_ids)} step(s)"
            if record.process_step_ids
            else ""
        )
        return f"conditional\nassociation{suffix}"
    if state == "cannot_attribute":
        return "? cannot\nattribute"
    if state in {"not_requested", "not_assessed"}:
        return "— not\nrequested"
    return _state(state)


def _review(record):
    label = {
        "transcriptomic_review_flag": "review flag",
        "not_detected_above_lod": "not detected\nabove LOD",
        "cannot_resolve": "? unresolved",
        "not_assessed": "— not assessed",
    }.get(_value(record.review_flag_state), _state(record.review_flag_state))
    return label + (
        f"\n→ {len(record.orthogonal_follow_up_refs)} follow-up"
        if record.orthogonal_follow_up_refs
        else ""
    )


def _state(value):
    state = _value(value)
    return {
        "not_assessed": "—\nnot assessed",
        "unavailable": "—\nunavailable",
        "unknown": "?\nunknown",
        "cannot_resolve": "?\nunresolved",
        "not_detected_above_lod": "not detected\nabove LOD",
    }.get(state, textwrap.fill(_label(state), width=14))


def _quantile(profile):
    if profile.lower_quantile_probability is None:
        return "declared quantile"
    return f"q{profile.lower_quantile_probability * 100:g}–q{profile.upper_quantile_probability * 100:g}"


def _numeric_limits(values):
    if not values:
        return -1.0, 1.0
    low, high = min(values), max(values)
    pad = max((high - low) * 0.12, abs(low) * 0.03, abs(high) * 0.03, 0.05)
    return low - pad, high + pad


def _method_label(value):
    return {
        "PROC-SCORE-SCANPY": "Scanpy score_genes",
        "PROC-SCORE-DECOUPLER": "decoupler ULM",
    }.get(value, _label(value))


def _unit_label(value):
    return {
        "scanpy_control_adjusted_expression": "control-adjusted expression",
        "decoupler_ulm_t_value": "ULM t-value",
    }.get(value, _label(value))


def _method_rank(value):
    return {
        "PROC-SCORE-SCANPY": 0,
        "PROC-SCORE-DECOUPLER": 1,
    }.get(value, 9)


def _scope_rank(value):
    return 0 if _value(value) == "whole_product" else 1


def _value(value):
    return str(getattr(value, "value", value))


def _number(value):
    return "—" if value is None else f"{value:.2f}"


def _percent(value):
    return "—" if value is None else f"{value * 100:.1f}%"


def _short(value, maximum):
    value = str(value)
    return value if len(value) <= maximum else f"{value[: maximum - 1]}…"


def _id_label(value, maximum):
    value = str(value)
    tail = value.rsplit(":", 1)[-1]
    return tail if len(tail) <= maximum else f"…{tail[-(maximum - 1) :]}"


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
