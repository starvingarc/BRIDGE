from __future__ import annotations

import csv
import hashlib
import json
import re
import textwrap
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path
from xml.etree import ElementTree

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.patches import Rectangle

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_12_graft_assessment.visualization_data import (
    GRAFT_ASSESSMENT_VISUALIZATION_DATA_SCHEMA_REF,
    P012_COMPONENT_BINDINGS,
    P012VisualizationArtifactSet,
    CompositionRowKind,
    GraftAssessmentVisualizationDataV1,
    GraftMolecularEvidenceRecord,
    GraftVisualizationMode,
    MolecularPanel,
    MolecularRowKind,
    REFERENCE_AND_PROGRAM_COMPONENT_REF,
    SPECIMEN_SCOPE_COMPONENT_REF,
    UPLOADED_PROFILE_COMPOSITION_COMPONENT_REF,
    _artifact_id,
    _visualization_id,
)
from bridge.toolkit.contracts import ArtifactManifest
from bridge.toolkit.visualization import (
    FigureRegistry,
    VisualizationAccessibility,
    VisualizationArtifactV2,
    VisualizationDataBinding,
    VisualizationRenderBinding,
)


_RENDERER_ID = "bridge.matplotlib.graft-assessment"
_RENDERER_VERSION = "0.1.0"
_EXPORT_PROFILE_ID = "bridge-static-scientific-figure-v0.1"
_WIDTH = 180.3 / 25.4
_BACKGROUND = "#FFFFFF"
_TEXT = "#26363D"
_MUTED = "#66767C"
_RULE = "#D8E0E2"
_ROW = "#F6F8F8"
_ACCENT = "#5A9EA6"
_UNASSIGNED = "#8D9699"
_UNAVAILABLE = "#ECEFF0"
_RC = {
    "font.family": ["DejaVu Sans"],
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
    "svg.hashsalt": "BRIDGE-P0-12",
    "axes.linewidth": 0.6,
}
_SVG_STYLE_PROPERTIES = {
    "fill",
    "fill-opacity",
    "font-family",
    "font-size",
    "font-weight",
    "opacity",
    "stroke",
    "stroke-dasharray",
    "stroke-dashoffset",
    "stroke-linecap",
    "stroke-linejoin",
    "stroke-opacity",
    "stroke-width",
    "text-anchor",
}


@dataclass(frozen=True)
class PreparedGraftAssessmentVisualizations:
    payloads: dict[str, bytes]
    artifacts: tuple[ArtifactManifest, ...]


@dataclass(frozen=True)
class _Component:
    ref: str
    slug: str
    records_path: str
    table_name: str
    title: str


_COMPONENTS = tuple(
    _Component(
        ref=ref,
        slug=slug,
        records_path=records_path,
        table_name={
            SPECIMEN_SCOPE_COMPONENT_REF: ("graft_assessment_specimen_scope.tsv"),
            UPLOADED_PROFILE_COMPOSITION_COMPONENT_REF: (
                "graft_assessment_uploaded_profile_composition.tsv"
            ),
            REFERENCE_AND_PROGRAM_COMPONENT_REF: (
                "graft_assessment_reference_and_program_expression.tsv"
            ),
        }[ref],
        title={
            SPECIMEN_SCOPE_COMPONENT_REF: (
                "Post-transplant specimen and interpretable scope"
            ),
            UPLOADED_PROFILE_COMPOSITION_COMPONENT_REF: (
                "Cell-state composition among uploaded graft-derived profiles"
            ),
            REFERENCE_AND_PROGRAM_COMPONENT_REF: (
                "Reference similarity and registered gene-program expression"
            ),
        }[ref],
    )
    for ref, slug, records_path in P012_COMPONENT_BINDINGS
)
_TAKEAWAYS = {
    SPECIMEN_SCOPE_COMPONENT_REF: (
        "The figure states which post-transplant material and metadata this run "
        "can interpret. Technical samples remain nested within the declared graft; "
        "they are not treated as independent biological replicates."
    ),
    UPLOADED_PROFILE_COMPOSITION_COMPONENT_REF: (
        "Points show supplied state-probability mass across all uploaded expression-"
        "profile rows. The display is pooled rather than sample weighted, and the "
        "unassigned remainder is not reclassified as a biological unknown state."
    ),
    REFERENCE_AND_PROGRAM_COMPONENT_REF: (
        "Reference-profile similarity and registered gene-program mean expression "
        "are separate descriptive measurements with separate scales. Neither panel "
        "provides calibrated cell identity, a developmental-age estimate or a "
        "functional assessment."
    ),
}
_LIMITATIONS = {
    SPECIMEN_SCOPE_COMPONENT_REF: [
        "Expression QC is reported as not reassessed when the source result says so.",
        "Species assignment and profile-selection handling are not inferred when absent from the result.",
        "Post-transplant results do not modify pre-transplant product evidence.",
    ],
    UPLOADED_PROFILE_COMPOSITION_COMPONENT_REF: [
        "Fractions use all uploaded expression-profile rows as the denominator.",
        "Probability-mass equivalents are not hard cell or nucleus counts.",
        "A zero supplied mass is not evidence of biological absence or a detection limit.",
        "Technical samples are not used as biological replicates; no interval or p value is inferred.",
    ],
    REFERENCE_AND_PROGRAM_COMPONENT_REF: [
        "Spearman correlation is a transcriptomic similarity measure and does not provide calibrated cell identity.",
        "Mean log1p_cp10k is registered-gene expression and does not establish developmental status or function.",
        "Gene coverage and shared-gene counts must be read with the displayed values.",
        "Technical samples are not biological replicates; no interval, p value or temporal trend is inferred.",
    ],
}


def prepare_graft_assessment_visualizations(
    profile: GraftAssessmentVisualizationDataV1,
    output_dir: Path,
    run_id: str,
    tool_version: str,
) -> PreparedGraftAssessmentVisualizations:
    if profile.producer_run_ref != f"run:{run_id}":
        raise ValueError("visualization profile does not bind the producer run")
    final_dir = output_dir / run_id
    payloads: dict[str, bytes] = {}
    artifacts: list[ArtifactManifest] = []

    data_name = "graft_assessment_visualization_data.json"
    data_payload = canonical_json_bytes(profile.model_dump(mode="json"), indent=2)
    payloads[data_name] = data_payload
    data_artifact = _manifest(
        run_id,
        "graft-assessment-visualization-data",
        "graft_assessment_visualization_data",
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
        SPECIMEN_SCOPE_COMPONENT_REF: _render_scope,
        UPLOADED_PROFILE_COMPOSITION_COMPONENT_REF: _render_composition,
        REFERENCE_AND_PROGRAM_COMPONENT_REF: _render_molecular,
    }
    with matplotlib.rc_context(rc=_RC):
        for component in _COMPONENTS:
            evidence_ids = _component_evidence_ids(profile, component.ref)
            table_payload = _table(profile, component.ref)
            payloads[component.table_name] = table_payload
            table_artifact = _manifest(
                run_id,
                f"graft-assessment-{component.slug}-table",
                "visualization_table",
                final_dir / component.table_name,
                "text/tab-separated-values",
                table_payload,
                evidence_ids,
            )
            artifacts.append(table_artifact)
            tables[component.ref] = table_artifact

            reason = _static_render_reason(profile, component.ref)
            render_reasons[component.ref] = reason
            figure = (
                _fallback_figure(component, reason)
                if reason is not None
                else renderers[component.ref](profile)
            )
            for extension, (
                media_type,
                render_payload,
            ) in _render_payloads(figure).items():
                filename = f"graft_assessment_{component.slug}.{extension}"
                payloads[filename] = render_payload
                artifact = _manifest(
                    run_id,
                    (f"graft-assessment-{component.slug}-{extension}"),
                    "visualization_render",
                    final_dir / filename,
                    media_type,
                    render_payload,
                    evidence_ids,
                )
                artifacts.append(artifact)
                renders[(component.ref, extension)] = artifact

    visualizations = [
        _visualization_contract(
            profile=profile,
            component=component,
            data_artifact=data_artifact,
            table_artifact=tables[component.ref],
            render_artifacts={
                extension: renders[(component.ref, extension)]
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

    artifact_set = P012VisualizationArtifactSet(
        artifact_set_id=("p0-12-visualizations:" + run_id.removeprefix("run-")),
        data_profile_artifact_id=data_artifact.artifact_id,
        data_profile_sha256=data_artifact.sha256,
        visualizations=visualizations,
    )
    artifact_set_name = "p0_12_visualization_artifact_set.json"
    artifact_set_payload = canonical_json_bytes(
        artifact_set.model_dump(mode="json"), indent=2
    )
    payloads[artifact_set_name] = artifact_set_payload
    artifacts.append(
        _manifest(
            run_id,
            "p0-12-visualization-artifact-set",
            "visualization_artifact_set",
            final_dir / artifact_set_name,
            "application/json",
            artifact_set_payload,
            profile.evidence_ids,
        )
    )
    return PreparedGraftAssessmentVisualizations(payloads, tuple(artifacts))


def _records(
    profile: GraftAssessmentVisualizationDataV1,
    component_ref: str,
):
    if component_ref == SPECIMEN_SCOPE_COMPONENT_REF:
        return list(profile.scope_records)
    if component_ref == UPLOADED_PROFILE_COMPOSITION_COMPONENT_REF:
        return list(profile.composition_records)
    if component_ref == REFERENCE_AND_PROGRAM_COMPONENT_REF:
        return list(profile.molecular_records)
    raise KeyError(component_ref)


def _component_evidence_ids(
    profile: GraftAssessmentVisualizationDataV1,
    component_ref: str,
) -> list[str]:
    return sorted(
        {
            evidence_id
            for record in _records(profile, component_ref)
            for evidence_id in record.evidence_ids
        }
    )


def _static_render_reason(
    profile: GraftAssessmentVisualizationDataV1,
    component_ref: str,
) -> str | None:
    records = _records(profile, component_ref)
    if component_ref == UPLOADED_PROFILE_COMPOSITION_COMPONENT_REF:
        if any(
            record.row_kind is CompositionRowKind.STATE_PROBABILITY_MASS
            and (len(record.label) > 20 or len(record.state_id or "") > 20)
            for record in profile.composition_records
        ):
            return "static_render_requires_complete_table_fallback"
        state_count = sum(
            record.row_kind is CompositionRowKind.STATE_PROBABILITY_MASS
            for record in profile.composition_records
        )
        if state_count > 30:
            return "static_render_requires_complete_table_fallback"
    if component_ref == REFERENCE_AND_PROGRAM_COMPONENT_REF:
        records = profile.molecular_records
        samples = {
            record.sample_id for record in records if record.sample_id is not None
        }
        profiles = {
            record.profile_id for record in records if record.profile_id is not None
        }
        programs = {
            record.program_id for record in records if record.program_id is not None
        }
        max_sample_length = max((len(value) for value in samples), default=0)
        max_profile_length = max((len(value) for value in profiles), default=0)
        max_program_length = max((len(value) for value in programs), default=0)
        profile_label_budget = len(profiles) * max_profile_length
        program_label_budget = len(programs) * max_program_length
        if (
            len(samples) > 12
            or max_sample_length > 12
            or len(profiles) > 8
            or len(programs) > 8
            or profile_label_budget > 64
            or max_profile_length > 32
            or max_program_length > 32
            or program_label_budget > 64
        ):
            return "static_render_requires_complete_table_fallback"
    return None


def _table(
    profile: GraftAssessmentVisualizationDataV1,
    component_ref: str,
) -> bytes:
    rows = [
        record.model_dump(mode="json") for record in _records(profile, component_ref)
    ]
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    stream = StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=fields,
        delimiter="\t",
        lineterminator="\n",
        extrasaction="raise",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                field: (
                    json.dumps(
                        value,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    if isinstance(value, (list, dict))
                    else ("" if value is None else str(value))
                )
                for field, value in row.items()
            }
        )
    return stream.getvalue().encode("utf-8")


def _render_scope(profile: GraftAssessmentVisualizationDataV1):
    records = profile.scope_records
    if profile.mode is GraftVisualizationMode.NOT_PROVIDED:
        figure = _base(
            _title(SPECIMEN_SCOPE_COMPONENT_REF),
            "No post-transplant input was supplied for this run.",
            4.8,
            _TAKEAWAYS[SPECIMEN_SCOPE_COMPONENT_REF],
        )
        _empty_panel(
            figure,
            (0.07, 0.24, 0.86, 0.46),
            "Post-transplant assessment not available",
            "Composition, reference similarity and registered gene-program "
            "expression remain not assessed.",
        )
        figure.text(
            0.07,
            0.17,
            "Effect on pre-transplant evidence: none",
            fontsize=6.4,
            color=_TEXT,
            fontweight="bold",
        )
        return figure

    height = max(6.3, 3.3 + 0.34 * len(records))
    subtitle = (
        "Expression-analysis scope; uploaded rows and technical samples "
        "are reported without inferring biological replication."
        if profile.mode is GraftVisualizationMode.EXPRESSION_ANALYSIS
        else "Structured post-transplant evidence; expression-derived "
        "quantities were not supplied to this analysis mode."
    )
    figure = _base(
        _title(SPECIMEN_SCOPE_COMPONENT_REF),
        subtitle,
        height,
        _TAKEAWAYS[SPECIMEN_SCOPE_COMPONENT_REF],
    )

    top = 0.78
    if profile.mode is GraftVisualizationMode.EXPRESSION_ANALYSIS:
        lookup = {record.field_id: record for record in records}
        nodes = [
            ("Animal", lookup["animal"].display_value),
            ("Graft", lookup["graft"].display_value),
            (
                "Post-transplant timepoint",
                lookup["post_transplant_timepoint"].display_value,
            ),
            (
                "Technical samples",
                lookup["technical_samples"].display_value,
            ),
        ]
        axis = figure.add_axes((0.055, top, 0.89, 0.115))
        axis.set_xlim(0, 4)
        axis.set_ylim(0, 1)
        axis.axis("off")
        for index, (label, value) in enumerate(nodes):
            if index:
                axis.plot(
                    [index - 0.08, index + 0.08],
                    [0.5, 0.5],
                    color=_RULE,
                    linewidth=1.1,
                )
            axis.add_patch(
                Rectangle(
                    (index + 0.08, 0.13),
                    0.84,
                    0.74,
                    facecolor="#EAF3F3",
                    edgecolor=_ACCENT,
                    linewidth=0.8,
                )
            )
            axis.text(
                index + 0.5,
                0.62,
                label,
                fontsize=5.6,
                color=_MUTED,
                ha="center",
            )
            axis.text(
                index + 0.5,
                0.36,
                _compact_display(value, 12),
                fontsize=6.4,
                color=_TEXT,
                fontweight="bold",
                ha="center",
            )

    axis = figure.add_axes(
        (
            0.055,
            0.13,
            0.89,
            (
                0.61
                if profile.mode is GraftVisualizationMode.EXPRESSION_ANALYSIS
                else 0.70
            ),
        )
    )
    axis.set_xlim(0, 1)
    axis.set_ylim(len(records), 0)
    axis.axis("off")
    for index, record in enumerate(records):
        y = index + 0.06
        unavailable = record.missingness == "unavailable"
        axis.add_patch(
            Rectangle(
                (0, y),
                1,
                0.82,
                facecolor=(
                    _UNAVAILABLE
                    if unavailable
                    else (_ROW if index % 2 == 0 else _BACKGROUND)
                ),
                edgecolor=_RULE if unavailable else "none",
                linewidth=0.45,
            )
        )
        axis.text(
            0.02,
            y + 0.42,
            record.label,
            fontsize=6.2,
            color=_MUTED,
            va="center",
        )
        axis.text(
            0.48,
            y + 0.42,
            _compact_display(record.display_value, 32),
            fontsize=6.3,
            color=_TEXT if not unavailable else _MUTED,
            fontweight="bold" if not unavailable else "normal",
            va="center",
        )
        if unavailable:
            axis.text(
                0.98,
                y + 0.42,
                "not assessed",
                fontsize=5.5,
                color=_MUTED,
                ha="right",
                va="center",
            )
    return figure


def _compact_display(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    side = (limit - 1) // 2
    return value[:side] + "…" + value[-side:]


def _render_composition(
    profile: GraftAssessmentVisualizationDataV1,
):
    records = [
        record
        for record in profile.composition_records
        if record.row_kind is not CompositionRowKind.COMPONENT_UNAVAILABLE
    ]
    figure = _base(
        _title(UPLOADED_PROFILE_COMPOSITION_COMPONENT_REF),
        (
            "Supplied probability mass · denominator: all uploaded "
            "expression-profile rows"
            + (f" (n={records[0].denominator_rows:,})" if records else "")
            + " · pooled across technical samples"
        ),
        max(5.0, 3.2 + 0.37 * max(1, len(records))),
        _TAKEAWAYS[UPLOADED_PROFILE_COMPOSITION_COMPONENT_REF],
    )
    if not records:
        _empty_panel(
            figure,
            (0.07, 0.24, 0.86, 0.46),
            "Cell-state composition not assessed",
            "No expression-derived state-probability mass is available "
            "in this analysis mode.",
        )
        return figure

    axis = figure.add_axes((0.28, 0.18, 0.50, 0.64))
    axis.set_xlim(0, 100)
    axis.set_ylim(len(records) - 0.5, -0.5)
    axis.set_yticks(range(len(records)))
    axis.set_yticklabels(
        [record.label for record in records],
        fontsize=6.2,
    )
    axis.set_xticks([0, 25, 50, 75, 100])
    axis.set_xticklabels(["0", "25", "50", "75", "100%"], fontsize=6.0)
    axis.grid(axis="x", color=_RULE, linewidth=0.55)
    axis.tick_params(length=0, pad=4)
    for spine in axis.spines.values():
        spine.set_visible(False)

    unassigned_index = next(
        (
            index
            for index, record in enumerate(records)
            if record.row_kind is CompositionRowKind.UNASSIGNED_PROBABILITY_MASS
        ),
        None,
    )
    if unassigned_index is not None and unassigned_index > 0:
        axis.axhline(
            unassigned_index - 0.5,
            color=_UNASSIGNED,
            linewidth=0.7,
            linestyle=(0, (2, 2)),
        )

    for index, record in enumerate(records):
        value = record.mean_fraction * 100
        is_unassigned = (
            record.row_kind is CompositionRowKind.UNASSIGNED_PROBABILITY_MASS
        )
        color = _UNASSIGNED if is_unassigned else _ACCENT
        axis.plot(
            [0, value],
            [index, index],
            color=_RULE,
            linewidth=1.0,
            zorder=1,
        )
        axis.scatter(
            [value],
            [index],
            s=32,
            color=color,
            edgecolor="#FFFFFF",
            linewidth=0.7,
            zorder=2,
        )
        axis.text(
            min(value + 2.0, 98.0),
            index,
            f"{value:.1f}%",
            fontsize=6.0,
            color=_TEXT,
            va="center",
            ha="left" if value <= 90 else "right",
        )
        axis.text(
            101.5,
            index,
            (f"mass-equivalent {record.probability_mass_equivalent:.1f}"),
            fontsize=5.3,
            color=_MUTED,
            va="center",
            clip_on=False,
        )
    figure.text(
        0.055,
        0.11,
        "Probability-mass equivalent is a soft sum, not a hard cell or nucleus count. "
        "Zero means the supplied mass was zero; it is not a detection-limit claim.",
        fontsize=5.6,
        color=_MUTED,
    )
    return figure


def _render_molecular(
    profile: GraftAssessmentVisualizationDataV1,
):
    figure = _base(
        _title(REFERENCE_AND_PROGRAM_COMPONENT_REF),
        (
            "Separate descriptive panels and scales · technical samples "
            "are not biological replicates"
        ),
        7.8,
        _TAKEAWAYS[REFERENCE_AND_PROGRAM_COMPONENT_REF],
    )
    reference_records = [
        record
        for record in profile.molecular_records
        if record.panel is MolecularPanel.REFERENCE_SIMILARITY
        and record.row_kind is not MolecularRowKind.COMPONENT_UNAVAILABLE
    ]
    program_records = [
        record
        for record in profile.molecular_records
        if record.panel is MolecularPanel.REGISTERED_GENE_PROGRAM_EXPRESSION
        and record.row_kind is not MolecularRowKind.COMPONENT_UNAVAILABLE
    ]
    if profile.reference_source_family_id is not None:
        figure.text(
            0.055,
            0.882,
            "Reference source · "
            + _compact_display(profile.reference_source_family_id, 24)
            + "    Program source · "
            + _compact_display(profile.marker_source_family_id or "not recorded", 24),
            fontsize=5.5,
            color=_MUTED,
        )
    figure.text(
        0.055,
        0.845,
        "A  Transcriptomic similarity to registered reference profiles",
        fontsize=8.2,
        color=_TEXT,
        fontweight="bold",
    )
    if reference_records:
        _reference_matrix(figure, reference_records, (0.15, 0.53, 0.68, 0.27))
    else:
        _empty_panel(
            figure,
            (0.08, 0.54, 0.84, 0.22),
            "Reference similarity not assessed",
            "No expression-derived reference comparison is available.",
        )

    figure.text(
        0.055,
        0.455,
        "B  Mean expression of registered gene programs",
        fontsize=8.2,
        color=_TEXT,
        fontweight="bold",
    )
    if program_records:
        _program_matrix(figure, program_records, (0.15, 0.15, 0.68, 0.25))
    else:
        _empty_panel(
            figure,
            (0.08, 0.17, 0.84, 0.20),
            "Registered gene-program expression not assessed",
            "No expression-derived registered gene-program summary is available.",
        )
    return figure


def _reference_matrix(
    figure,
    records: list[GraftMolecularEvidenceRecord],
    bounds,
) -> None:
    samples = sorted({record.sample_id for record in records})
    profiles = sorted({record.profile_id for record in records})
    by_key = {(record.sample_id, record.profile_id): record for record in records}
    axis = figure.add_axes(bounds)
    axis.set_xlim(0, len(profiles))
    axis.set_ylim(len(samples), 0)
    axis.set_xticks([index + 0.5 for index in range(len(profiles))])
    axis.set_xticklabels(profiles, fontsize=5.5, rotation=30, ha="left")
    axis.tick_params(
        axis="x",
        top=True,
        labeltop=True,
        bottom=False,
        labelbottom=False,
        length=0,
        pad=3,
    )
    axis.set_yticks([index + 0.5 for index in range(len(samples))])
    axis.set_yticklabels(samples, fontsize=5.8)
    axis.tick_params(axis="y", length=0, pad=3)
    cmap = matplotlib.colormaps["RdBu_r"]
    norm = Normalize(vmin=-1, vmax=1)
    for y, sample in enumerate(samples):
        for x, profile_id in enumerate(profiles):
            record = by_key[(sample, profile_id)]
            available = record.missingness == "available"
            axis.add_patch(
                Rectangle(
                    (x + 0.04, y + 0.05),
                    0.92,
                    0.90,
                    facecolor=(
                        cmap(norm(record.spearman_rho)) if available else _UNAVAILABLE
                    ),
                    edgecolor="#FFFFFF",
                    linewidth=0.8,
                )
            )
            label = (
                f"{record.spearman_rho:.2f}\nn={record.shared_gene_count}"
                if available
                else f"×\nn={record.shared_gene_count}"
            )
            axis.text(
                x + 0.5,
                y + 0.5,
                label,
                ha="center",
                va="center",
                fontsize=5.2,
                color=(
                    "#FFFFFF"
                    if available and abs(record.spearman_rho) > 0.55
                    else _TEXT
                ),
            )
    for spine in axis.spines.values():
        spine.set_visible(False)
    _color_legend(
        figure,
        (0.86, bounds[1] + 0.04, 0.11, 0.035),
        cmap,
        Normalize(-1, 1),
        "Spearman ρ",
        "-1",
        "1",
    )
    figure.text(
        0.86,
        bounds[1] + 0.12,
        "n = shared genes",
        fontsize=5.4,
        color=_MUTED,
    )


def _program_matrix(
    figure,
    records: list[GraftMolecularEvidenceRecord],
    bounds,
) -> None:
    samples = sorted({record.sample_id for record in records})
    programs = sorted({record.program_id for record in records})
    by_key = {(record.sample_id, record.program_id): record for record in records}
    available_values = [
        record.mean_log1p_cp10k
        for record in records
        if record.missingness == "available"
    ]
    if available_values:
        lower = min(available_values)
        upper = max(available_values)
        if lower == upper:
            lower -= 0.5
            upper += 0.5
    else:
        lower, upper = 0.0, 1.0
    cmap = matplotlib.colormaps["viridis"]
    norm = Normalize(vmin=lower, vmax=upper)

    axis = figure.add_axes(bounds)
    axis.set_xlim(-0.5, len(programs) - 0.5)
    axis.set_ylim(len(samples) - 0.5, -0.5)
    axis.set_xticks(range(len(programs)))
    axis.set_xticklabels(programs, fontsize=5.5, rotation=30, ha="left")
    axis.tick_params(
        axis="x",
        top=True,
        labeltop=True,
        bottom=False,
        labelbottom=False,
        length=0,
        pad=3,
    )
    axis.set_yticks(range(len(samples)))
    axis.set_yticklabels(samples, fontsize=5.8)
    axis.tick_params(axis="y", length=0, pad=3)
    for x in range(len(programs) + 1):
        axis.axvline(x - 0.5, color=_RULE, linewidth=0.45)
    for y in range(len(samples) + 1):
        axis.axhline(y - 0.5, color=_RULE, linewidth=0.45)
    for y, sample in enumerate(samples):
        for x, program_id in enumerate(programs):
            record = by_key[(sample, program_id)]
            if record.missingness == "available":
                axis.scatter(
                    [x],
                    [y],
                    s=18 + 100 * record.gene_coverage,
                    color=cmap(norm(record.mean_log1p_cp10k)),
                    edgecolor="#FFFFFF",
                    linewidth=0.65,
                    zorder=2,
                )
            else:
                axis.text(
                    x,
                    y,
                    "×",
                    ha="center",
                    va="center",
                    fontsize=7.0,
                    color=_MUTED,
                )
    for spine in axis.spines.values():
        spine.set_visible(False)
    if available_values:
        _color_legend(
            figure,
            (0.86, bounds[1] + 0.02, 0.11, 0.035),
            cmap,
            norm,
            "Mean log1p_cp10k",
            f"{lower:.2g}",
            f"{upper:.2g}",
        )
    else:
        figure.text(
            0.86,
            bounds[1] + 0.035,
            "× unavailable\nNo numeric value",
            fontsize=5.2,
            color=_MUTED,
        )
    legend_y = bounds[1] + 0.13
    figure.text(
        0.86,
        legend_y + 0.055,
        "Gene coverage",
        fontsize=5.5,
        color=_MUTED,
    )
    legend_axis = figure.add_axes((0.86, legend_y - 0.01, 0.11, 0.06))
    legend_axis.set_xlim(0, 1)
    legend_axis.set_ylim(0, 1)
    legend_axis.axis("off")
    for x, coverage in zip((0.13, 0.48, 0.83), (0.25, 0.5, 1.0)):
        legend_axis.scatter(
            [x],
            [0.58],
            s=18 + 100 * coverage,
            color="#AAB5B8",
            edgecolor="#FFFFFF",
            linewidth=0.6,
        )
        legend_axis.text(
            x,
            0.05,
            f"{coverage:.0%}",
            fontsize=4.8,
            color=_MUTED,
            ha="center",
        )


def _color_legend(
    figure,
    bounds,
    cmap,
    norm,
    title: str,
    lower_label: str,
    upper_label: str,
) -> None:
    axis = figure.add_axes(bounds)
    axis.set_xlim(0, 24)
    axis.set_ylim(0, 1)
    axis.axis("off")
    for index in range(24):
        value = norm.vmin + ((index + 0.5) / 24 * (norm.vmax - norm.vmin))
        axis.add_patch(
            Rectangle(
                (index, 0.18),
                1.03,
                0.42,
                facecolor=cmap(norm(value)),
                edgecolor="none",
            )
        )
    axis.text(
        0,
        0.90,
        title,
        fontsize=5.2,
        color=_MUTED,
        va="bottom",
    )
    axis.text(
        0,
        0.02,
        lower_label,
        fontsize=4.8,
        color=_MUTED,
        va="top",
    )
    axis.text(
        24,
        0.02,
        upper_label,
        fontsize=4.8,
        color=_MUTED,
        ha="right",
        va="top",
    )


def _empty_panel(
    figure,
    bounds,
    title: str,
    body: str,
) -> None:
    axis = figure.add_axes(bounds)
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.axis("off")
    axis.add_patch(
        Rectangle(
            (0, 0),
            1,
            1,
            facecolor=_UNAVAILABLE,
            edgecolor=_RULE,
            linewidth=0.7,
        )
    )
    axis.text(
        0.95,
        0.72,
        "×",
        fontsize=13.0,
        color=_UNASSIGNED,
        ha="right",
        va="center",
    )
    axis.text(
        0.05,
        0.62,
        title,
        fontsize=8.0,
        color=_TEXT,
        fontweight="bold",
    )
    axis.text(
        0.05,
        0.38,
        textwrap.fill(body, 88),
        fontsize=6.4,
        color=_MUTED,
    )


def _base(
    title: str,
    subtitle: str,
    height: float,
    footnote: str,
):
    figure = plt.figure(figsize=(_WIDTH, height), facecolor=_BACKGROUND)
    figure.text(
        0.045,
        0.965,
        title,
        fontsize=11.0,
        fontweight="bold",
        color=_TEXT,
        va="top",
    )
    figure.text(
        0.045,
        0.925,
        subtitle,
        fontsize=6.8,
        color=_MUTED,
        va="top",
    )
    figure.text(
        0.045,
        0.025,
        textwrap.fill(footnote, 112),
        fontsize=5.8,
        color=_MUTED,
        va="bottom",
        linespacing=1.15,
    )
    return figure


def _fallback_figure(
    component: _Component,
    reason: str,
):
    figure = _base(
        component.title,
        "The complete typed table is retained without truncation.",
        4.8,
        (
            f"{reason}. No top-N selection, clustering or silent "
            "omission was applied to the static figure."
        ),
    )
    _empty_panel(
        figure,
        (0.07, 0.24, 0.86, 0.44),
        "Complete-table view required",
        "This static export cannot show every record legibly. "
        "Use the complete TSV table for all supplied records.",
    )
    return figure


def _visualization_contract(
    *,
    profile: GraftAssessmentVisualizationDataV1,
    component: _Component,
    data_artifact: ArtifactManifest,
    table_artifact: ArtifactManifest,
    render_artifacts: dict[str, ArtifactManifest],
    run_id: str,
    tool_version: str,
    render_reason: str | None,
) -> VisualizationArtifactV2:
    records = _records(profile, component.ref)
    evidence_states = sorted(
        {record.evidence_state for record in records},
        key=lambda state: state.value,
    )
    missing_reasons = sorted(
        {
            *(reason for record in records for reason in record.reason_codes),
            *([render_reason] if render_reason else []),
        }
    )
    available_count = sum(record.missingness == "available" for record in records)
    if available_count == 0:
        applicability = "not_assessed"
    elif available_count < len(records) or render_reason:
        applicability = "partially_applicable"
    else:
        applicability = "applicable"

    binding_kwargs = {
        "artifact_id": data_artifact.artifact_id,
        "schema_ref": (GRAFT_ASSESSMENT_VISUALIZATION_DATA_SCHEMA_REF),
        "object_version": "0.1.0",
        "sha256": data_artifact.sha256,
        "records_path": component.records_path,
        "record_lookup_key": "record_id",
        "evidence_ids_field": "evidence_ids",
        "evidence_state_field": "evidence_state",
        "scientific_status_field": "scientific_status",
        "missingness_field": "missingness",
        "applicability_field": "applicability",
    }
    denominator_kwargs: dict[str, str] = {}
    if component.ref == UPLOADED_PROFILE_COMPOSITION_COMPONENT_REF:
        binding_kwargs.update(
            {
                "numerator_field": "probability_mass_equivalent",
                "denominator_field": "denominator_rows",
                "denominator_scope_field": "denominator_scope",
                "unit_field": "unit",
            }
        )
        denominator_kwargs = {
            "denominator_label": ("All uploaded expression-profile rows"),
            "denominator_scope": "all_uploaded_rows",
            "unit": "fraction",
        }
    else:
        binding_kwargs["value_field"] = "display_value"
        if component.ref == REFERENCE_AND_PROGRAM_COMPONENT_REF:
            binding_kwargs["unit_field"] = "unit"

    alt_text, long_description = _accessibility_text(profile, component.ref)
    return VisualizationArtifactV2(
        visualization_id=_visualization_id(run_id.removeprefix("run-"), component.slug),
        component_id=component.ref.split("@", 1)[0],
        component_version=component.ref.split("@", 1)[1],
        data_binding=VisualizationDataBinding(**binding_kwargs),
        producer_tool_id="P0-12",
        producer_tool_version=tool_version,
        producer_run_ref=f"run:{run_id}",
        evidence_ids=_component_evidence_ids(profile, component.ref),
        evidence_states=evidence_states,
        scientific_status="candidate",
        applicability=applicability,
        missing_reason_codes=missing_reasons,
        insight_title=component.title,
        takeaway=_TAKEAWAYS[component.ref],
        limitations=_LIMITATIONS[component.ref],
        accessibility=VisualizationAccessibility(
            alt_text=alt_text,
            long_description=long_description,
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
        **denominator_kwargs,
    )


def _accessibility_text(
    profile: GraftAssessmentVisualizationDataV1,
    component_ref: str,
) -> tuple[str, str]:
    if component_ref == SPECIMEN_SCOPE_COMPONENT_REF:
        unavailable = sum(
            record.missingness == "unavailable" for record in profile.scope_records
        )
        summary = (
            f"Mode: {profile.mode.value}; scope fields: "
            f"{len(profile.scope_records)}; not assessed: {unavailable}."
        )
    elif component_ref == UPLOADED_PROFILE_COMPOSITION_COMPONENT_REF:
        available = [
            record
            for record in profile.composition_records
            if record.mean_fraction is not None
        ]
        summary = (
            "Composition not assessed in this mode."
            if not available
            else (
                f"Supplied probability-mass rows: {len(available)}; "
                f"largest fraction: "
                f"{max(record.mean_fraction for record in available):.1%}; "
                "denominator is all uploaded expression-profile rows."
            )
        )
    else:
        references = sum(
            record.row_kind is MolecularRowKind.REFERENCE_SIMILARITY
            for record in profile.molecular_records
        )
        programs = sum(
            record.row_kind is MolecularRowKind.REGISTERED_GENE_PROGRAM_EXPRESSION
            for record in profile.molecular_records
        )
        summary = (
            f"Reference-comparison rows: {references}; registered "
            f"gene-program rows: {programs}; separate scales are used."
        )
    alt = f"{_title(component_ref)}. {summary}"
    long = (
        f"{alt} {_TAKEAWAYS[component_ref]} The complete typed TSV "
        "retains every row, source-result lineage and availability state."
    )
    return alt, long


def _title(component_ref: str) -> str:
    return next(
        component.title for component in _COMPONENTS if component.ref == component_ref
    )


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
                payload = _sanitize_svg(buffer.getvalue())
            elif extension == "png":
                figure.savefig(
                    buffer,
                    format="png",
                    dpi=220,
                    metadata={"Software": "BRIDGE"},
                )
                payload = buffer.getvalue()
            else:
                metadata.update(
                    {
                        "CreationDate": None,
                        "ModDate": None,
                        "Producer": "BRIDGE",
                    }
                )
                figure.savefig(buffer, format="pdf", metadata=metadata)
                payload = buffer.getvalue()
            outputs[extension] = (media_type, payload)
    finally:
        plt.close(figure)
    return outputs


def _sanitize_svg(payload: bytes) -> bytes:
    text = payload.decode("utf-8")
    text = re.sub(
        r"<!DOCTYPE[^>]*>\s*",
        "",
        text,
        count=1,
        flags=re.DOTALL,
    )
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        raise ValueError("generated SVG is invalid") from None
    root.attrib.pop("version", None)
    for parent in root.iter():
        for child in list(parent):
            if _svg_local_name(child.tag) in {"metadata", "style"}:
                parent.remove(child)
    for element in root.iter():
        style = element.attrib.pop("style", None)
        if style is None:
            continue
        for declaration in style.split(";"):
            if not declaration.strip():
                continue
            name, separator, value = declaration.partition(":")
            name = name.strip()
            value = value.strip()
            if (
                separator != ":"
                or name not in _SVG_STYLE_PROPERTIES
                or not value
                or "url(" in value.casefold()
            ):
                raise ValueError("generated SVG uses an unsupported style")
            element.set(name, value)
    ElementTree.register_namespace("", "http://www.w3.org/2000/svg")
    return ElementTree.tostring(
        root,
        encoding="utf-8",
        xml_declaration=True,
    )


def _svg_local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1]


def _config_hash(component_ref: str) -> str:
    payload = canonical_json_bytes(
        {
            "component_ref": component_ref,
            "renderer": [
                _RENDERER_ID,
                _RENDERER_VERSION,
                _EXPORT_PROFILE_ID,
            ],
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "matplotlib_version": matplotlib.__version__,
            "matplotlib_rc": _RC,
            "font_family": "DejaVu Sans",
            "colors": {
                "accent": _ACCENT,
                "unassigned": _UNASSIGNED,
                "unavailable": _UNAVAILABLE,
            },
            "figure_width_in": _WIDTH,
        }
    )
    return hashlib.sha256(payload).hexdigest()


def _manifest(
    run_id: str,
    suffix: str,
    kind: str,
    path: Path,
    media_type: str,
    payload: bytes,
    evidence_ids: list[str],
) -> ArtifactManifest:
    return ArtifactManifest(
        artifact_id=_artifact_id(run_id.removeprefix("run-"), suffix),
        kind=kind,
        path=path,
        media_type=media_type,
        sha256=hashlib.sha256(payload).hexdigest(),
        evidence_ids=evidence_ids,
    )
