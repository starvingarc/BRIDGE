from __future__ import annotations

import csv
import hashlib
import json
import textwrap
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.patches import Rectangle

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_08_evidence_sufficiency.visualization_data import (
    DOMAIN_AXES_COMPONENT_REF,
    EVIDENCE_SUFFICIENCY_VISUALIZATION_DATA_SCHEMA_REF,
    INTERPRETATION_REQUIREMENTS_COMPONENT_REF,
    MEASUREMENT_STATES_COMPONENT_REF,
    EvidenceAxisId,
    EvidenceSufficiencyVisualizationDataV1,
    P008VisualizationArtifactSet,
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
_TEXT = "#26343B"
_MUTED = "#69767C"
_ROW = "#F7F8F8"
_STATE_COLORS = {
    "available": ("#DCEAF3", "#446C83"),
    "limited": ("#F5E7C8", "#8B6B34"),
    "constrained": ("#F2D8D0", "#9B5B4B"),
    "not_assessed": ("#E8E9EA", "#747B80"),
}
_REQUIREMENT_COLORS = {
    "missing": ("#E7E8EA", "#6F777C"),
    "blocking": ("#F2D8D0", "#9B5B4B"),
    "limiting": ("#F5E7C8", "#8B6B34"),
    "review_required": ("#E7DDF0", "#705B83"),
}
_MEASUREMENT_COLORS = {
    "measured": "#A8CBE2",
    "inferred": "#C9B8DD",
    "prior_only": "#F1C7A8",
    "negative": "#9FD4CC",
    "missing": "#D8DADD",
    "unknown": "#C7CCD0",
    "unavailable": "#ECEDEE",
    "alert": "#E5A99B",
}
_RC = {
    "font.family": ["DejaVu Sans"],
    "font.sans-serif": ["DejaVu Sans"],
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
    "svg.hashsalt": "BRIDGE-P0-08",
}


@dataclass(frozen=True)
class PreparedEvidenceSufficiencyVisualizations:
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
        DOMAIN_AXES_COMPONENT_REF,
        "domain-axes",
        "axis_records",
        "evidence_sufficiency_domain_axes.tsv",
        "Evidence conditions for interpretation by analysis domain",
    ),
    _Component(
        INTERPRETATION_REQUIREMENTS_COMPONENT_REF,
        "interpretation-requirements",
        "requirement_records",
        "evidence_sufficiency_interpretation_requirements.tsv",
        "Evidence gaps and interpretation limits by analysis domain",
    ),
    _Component(
        MEASUREMENT_STATES_COMPONENT_REF,
        "measurement-states",
        "measurement_state_records",
        "evidence_sufficiency_measurement_states.tsv",
        "Upstream measurement-result states linked to each analysis domain",
    ),
)
_TAKEAWAYS = {
    DOMAIN_AXES_COMPONENT_REF: (
        "Input, method, reference/prior and interpretation conditions remain "
        "separate and scoped to the bound MeasurementSpec and declared use."
    ),
    INTERPRETATION_REQUIREMENTS_COMPONENT_REF: (
        "Root missing, limiting, blocking and review-required conditions are shown "
        "without inventing a causal edge to any individual source record."
    ),
    MEASUREMENT_STATES_COMPONENT_REF: (
        "Counts describe MeasurementResult references attached to each domain "
        "profile; they are not counts of independent evidence."
    ),
}
_LIMITATIONS = {
    DOMAIN_AXES_COMPONENT_REF: [
        "The four states are conditional on the bound MeasurementSpec, declared context and current candidate interpretation rules.",
        "An apparently favorable state is not a product-quality, safety, efficacy or release conclusion.",
        "No cross-domain score or ranking is calculated.",
    ],
    INTERPRETATION_REQUIREMENTS_COMPONENT_REF: [
        "Only root reasons from missing, blocking and limiting profile buckets are shown.",
        "A requirement record does not identify which individual source caused it.",
        "Review-required is an interpretation class and remains separate from catalog severity.",
    ],
    MEASUREMENT_STATES_COMPONENT_REF: [
        "Counts are domain-profile MeasurementResult references, not biological replicates or independent evidence.",
        "One source object reused by several domains is counted once in each linked domain profile.",
        "Zero means no bound reference in that profile; it is not proof of biological absence.",
    ],
}


def prepare_evidence_sufficiency_visualizations(
    *,
    profile: EvidenceSufficiencyVisualizationDataV1,
    output_dir: Path,
    run_id: str,
    tool_version: str,
) -> PreparedEvidenceSufficiencyVisualizations:
    final_dir = output_dir / run_id
    payloads: dict[str, bytes] = {}
    artifacts: list[ArtifactManifest] = []
    data_name = "evidence_sufficiency_visualization_data.json"
    data_payload = canonical_json_bytes(profile.model_dump(mode="json"), indent=2)
    payloads[data_name] = data_payload
    data_artifact = _manifest(
        run_id,
        "evidence-sufficiency-visualization-data",
        "evidence_sufficiency_visualization_data",
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
        DOMAIN_AXES_COMPONENT_REF: _render_domain_axes,
        INTERPRETATION_REQUIREMENTS_COMPONENT_REF: _render_requirements,
        MEASUREMENT_STATES_COMPONENT_REF: _render_measurement_states,
    }
    with matplotlib.rc_context(rc=_RC):
        for component in _COMPONENTS:
            table_payload = _table(profile, component.ref)
            payloads[component.table_name] = table_payload
            tables[component.ref] = _manifest(
                run_id,
                f"evidence-sufficiency-{component.slug}-table",
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
                    "Static capacity was exceeded; the complete result remains in the typed table.",
                    [reason],
                    component.ref,
                )
                if reason
                else renderers[component.ref](profile)
            )
            for extension, (media_type, render_payload) in _render_payloads(
                figure
            ).items():
                name = f"evidence_sufficiency_{component.slug}.{extension}"
                payloads[name] = render_payload
                artifact = _manifest(
                    run_id,
                    f"evidence-sufficiency-{component.slug}-{extension}",
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
    artifact_set = P008VisualizationArtifactSet(
        artifact_set_id=f"p0-08-visualizations:{run_id.removeprefix('run-')}",
        data_profile_artifact_id=data_artifact.artifact_id,
        data_profile_sha256=data_artifact.sha256,
        visualizations=visualizations,
    )
    set_name = "evidence_sufficiency_visualization_artifact_set.json"
    set_payload = canonical_json_bytes(artifact_set.model_dump(mode="json"), indent=2)
    payloads[set_name] = set_payload
    artifacts.append(
        _manifest(
            run_id,
            "evidence-sufficiency-visualization-artifact-set",
            "visualization_artifact_set",
            final_dir / set_name,
            "application/json",
            set_payload,
            profile.evidence_ids,
        )
    )
    return PreparedEvidenceSufficiencyVisualizations(payloads, tuple(artifacts))


def _table(profile, component_ref):
    if component_ref == DOMAIN_AXES_COMPONENT_REF:
        records = [row.model_dump(mode="json") for row in profile.axis_records]
    elif component_ref == MEASUREMENT_STATES_COMPONENT_REF:
        records = [
            row.model_dump(mode="json") for row in profile.measurement_state_records
        ]
    else:
        displays = {row.reason_code: row for row in profile.reason_display_records}
        records = []
        for row in profile.requirement_records:
            record = row.model_dump(mode="json")
            display = displays[row.reason_code]
            record["description"] = display.description
            record["remediation"] = display.remediation
            records.append(record)
    fields = []
    for record in records:
        for field in record:
            if field not in fields:
                fields.append(field)
    if not fields:
        fields = [
            "record_id",
            "profile_ref",
            "reason_code",
            "requirement_class",
            "catalog_axis",
            "catalog_severity",
            "description",
            "remediation",
        ]
    buffer = StringIO(newline="")
    writer = csv.DictWriter(
        buffer, fieldnames=fields, delimiter="\t", lineterminator="\n"
    )
    writer.writeheader()
    for record in records:
        writer.writerow(
            {key: _table_cell(record.get(key)) for key in fields}
        )
    return buffer.getvalue().encode()


def _table_cell(value):
    if isinstance(value, (list, dict)):
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    return "" if value is None else value


def _static_render_reason(profile, ref):
    if ref == DOMAIN_AXES_COMPONENT_REF:
        too_large = len(profile.domain_bindings) > 5 or len(profile.axis_records) > 20
    elif ref == INTERPRETATION_REQUIREMENTS_COMPONENT_REF:
        too_large = len(profile.requirement_records) > 24
    else:
        states = {row.measurement_evidence_state for row in profile.measurement_state_records}
        too_large = (
            len(profile.domain_bindings) > 5
            or len(states) > 8
            or len(profile.measurement_state_records) > 40
        )
    return "static_render_requires_table_fallback" if too_large else None


def _base(title, subtitle, height, ref):
    figure = plt.figure(figsize=(_WIDTH, height), facecolor=_BACKGROUND)
    figure.text(
        0.045, 0.965, title, fontsize=11.1, fontweight="bold", color=_TEXT, va="top"
    )
    if subtitle:
        figure.text(
            0.045, 0.918, subtitle, fontsize=7.35, color=_MUTED, va="top"
        )
    figure.text(
        0.045,
        0.025,
        textwrap.fill(_footnote(ref), width=108),
        fontsize=6.25,
        color=_MUTED,
        va="bottom",
        linespacing=1.18,
    )
    return figure


def _empty_figure(title, message, reasons, ref):
    figure = _base(title, "", 4.7, ref)
    axis = figure.add_axes((0.075, 0.18, 0.85, 0.60))
    axis.axis("off")
    axis.text(
        0, 0.72, "—  static view unavailable", fontsize=13, fontweight="bold", color=_MUTED
    )
    axis.text(0, 0.48, message, fontsize=9.0, color=_TEXT)
    axis.text(
        0,
        0.27,
        textwrap.fill(" · ".join(_label(reason) for reason in reasons if reason), 94),
        fontsize=7.1,
        color=_MUTED,
        va="top",
    )
    return figure


def _no_requirements_figure():
    figure = _base(
        _COMPONENTS[1].title,
        "Root conditions returned under the current candidate interpretation rules.",
        4.7,
        INTERPRETATION_REQUIREMENTS_COMPONENT_REF,
    )
    axis = figure.add_axes((0.075, 0.18, 0.85, 0.60))
    axis.axis("off")
    axis.text(
        0, 0.64, "No root interpretation requirement was returned",
        fontsize=11.2, fontweight="bold", color=_TEXT,
    )
    axis.text(
        0, 0.39,
        "This absence is scoped to the supplied profiles and is not release authorization.",
        fontsize=8.0, color=_MUTED,
    )
    return figure


def _render_domain_axes(profile):
    bindings = profile.domain_bindings
    records = {(row.profile_ref, row.axis_id): row for row in profile.axis_records}
    columns = (
        (EvidenceAxisId.INPUT_DATA, "Input data"),
        (EvidenceAxisId.METHOD_VALIDATION, "Method validation\nand robustness"),
        (EvidenceAxisId.REFERENCE_PRIOR, "Reference and\nprior fit"),
        (EvidenceAxisId.INTERPRETATION, "Current interpretation\ncondition"),
    )
    figure = _base(
        _COMPONENTS[0].title,
        "Each state is conditional on its bound measurement and declared context.",
        max(4.9, 3.45 + 0.72 * len(bindings)),
        DOMAIN_AXES_COMPONENT_REF,
    )
    axis = figure.add_axes((0.035, 0.145, 0.94, 0.68))
    axis.set_xlim(-1.78, 4.02)
    axis.set_ylim(-0.65, len(bindings) + 0.65)
    axis.axis("off")
    for column_index, (_, label) in enumerate(columns):
        axis.text(
            column_index + 0.5,
            len(bindings) + 0.20,
            label,
            ha="center",
            va="bottom",
            fontsize=6.55,
            fontweight="bold",
            color=_TEXT,
            linespacing=1.1,
        )
    for row_index, binding in enumerate(bindings):
        y = len(bindings) - row_index - 1
        axis.text(
            -1.72,
            y + 0.5,
            textwrap.fill(binding.domain_label, width=30),
            ha="left",
            va="center",
            fontsize=6.7,
            fontweight="bold",
            color=_TEXT,
            wrap=True,
        )
        for column_index, (axis_id, _) in enumerate(columns):
            record = records[(binding.profile_ref, axis_id)]
            fill, edge = _state_style(record.source_state)
            axis.add_patch(
                Rectangle(
                    (column_index + 0.035, y + 0.08),
                    0.93,
                    0.84,
                    facecolor=fill,
                    edgecolor=edge,
                    linewidth=0.8,
                )
            )
            axis.text(
                column_index + 0.5,
                y + 0.55,
                _short_state(axis_id, record.source_state),
                ha="center",
                va="center",
                fontsize=6.15,
                fontweight="bold",
                color=_TEXT,
                linespacing=1.1,
            )
            if record.reason_codes:
                axis.text(
                    column_index + 0.5,
                    y + 0.24,
                    f"{len(record.reason_codes)} recorded condition"
                    + ("s" if len(record.reason_codes) != 1 else ""),
                    ha="center",
                    va="center",
                    fontsize=5.3,
                    color=_MUTED,
                )
    return figure


def _render_requirements(profile):
    records = profile.requirement_records
    if not records:
        return _no_requirements_figure()
    domain_order = {
        item.profile_ref: index for index, item in enumerate(profile.domain_bindings)
    }
    domain_labels = {
        item.profile_ref: item.domain_label for item in profile.domain_bindings
    }
    displays = {item.reason_code: item for item in profile.reason_display_records}
    class_order = {
        "blocking": 0,
        "review_required": 1,
        "missing": 2,
        "limiting": 3,
    }
    records = sorted(
        records,
        key=lambda row: (
            domain_order[row.profile_ref],
            class_order[row.requirement_class.value],
            row.reason_code,
        ),
    )
    height = max(5.2, 3.25 + 0.70 * len(records))
    figure = _base(
        _COMPONENTS[1].title,
        "Root conditions only; review-required and catalog severity remain separate.",
        height,
        INTERPRETATION_REQUIREMENTS_COMPONENT_REF,
    )
    axis = figure.add_axes((0.025, 0.12, 0.955, 0.73))
    axis.set_xlim(0, 1)
    axis.set_ylim(-0.5, len(records) + 0.60)
    axis.axis("off")
    headers = (
        (0.02, "Analysis domain"),
        (0.225, "Condition class"),
        (0.36, "Current evidence condition"),
        (0.69, "Evidence needed or retained"),
    )
    for x, label in headers:
        axis.text(
            x, len(records) + 0.18, label, fontsize=6.3, fontweight="bold", color=_TEXT
        )
    for index, record in enumerate(records):
        y = len(records) - index - 1
        if index % 2 == 0:
            axis.add_patch(
                Rectangle((0.01, y - 0.02), 0.98, 0.92, color=_ROW, zorder=0)
            )
        display = displays[record.reason_code]
        fill, edge = _REQUIREMENT_COLORS[record.requirement_class.value]
        axis.text(
            0.02,
            y + 0.44,
            textwrap.fill(domain_labels[record.profile_ref], 23),
            fontsize=5.95,
            color=_TEXT,
            va="center",
        )
        axis.add_patch(
            Rectangle(
                (0.225, y + 0.20),
                0.115,
                0.46,
                facecolor=fill,
                edgecolor=edge,
                linewidth=0.75,
            )
        )
        axis.text(
            0.2825,
            y + 0.43,
            _label(record.requirement_class.value),
            fontsize=5.45,
            fontweight="bold",
            color=_TEXT,
            ha="center",
            va="center",
            wrap=True,
        )
        axis.text(
            0.36,
            y + 0.44,
            textwrap.fill(display.description, 43),
            fontsize=5.55,
            color=_TEXT,
            va="center",
            linespacing=1.12,
        )
        axis.text(
            0.69,
            y + 0.44,
            textwrap.fill(display.remediation, 39),
            fontsize=5.55,
            color=_TEXT,
            va="center",
            linespacing=1.12,
        )
    return figure


def _render_measurement_states(profile):
    bindings = profile.domain_bindings
    states = list(profile.measurement_state_records[:8])
    state_order = [row.measurement_evidence_state for row in states]
    records = {
        (row.profile_ref, row.measurement_evidence_state): row
        for row in profile.measurement_state_records
    }
    figure = _base(
        _COMPONENTS[2].title,
        "Counts are domain-profile MeasurementResult references, not independent evidence.",
        max(4.9, 3.45 + 0.68 * len(bindings)),
        MEASUREMENT_STATES_COMPONENT_REF,
    )
    axis = figure.add_axes((0.035, 0.145, 0.94, 0.68))
    axis.set_xlim(-2.0, len(state_order) + 0.06)
    axis.set_ylim(-0.65, len(bindings) + 0.70)
    axis.axis("off")
    for column_index, state in enumerate(state_order):
        axis.text(
            column_index + 0.5,
            len(bindings) + 0.22,
            _label(state.value),
            ha="center",
            va="bottom",
            fontsize=5.7,
            fontweight="bold",
            color=_TEXT,
            rotation=28,
        )
    for row_index, binding in enumerate(bindings):
        y = len(bindings) - row_index - 1
        axis.text(
            -1.94,
            y + 0.48,
            binding.domain_label,
            fontsize=6.45,
            fontweight="bold",
            color=_TEXT,
            ha="left",
            va="center",
        )
        axis.text(
            -0.12,
            y + 0.48,
            f"n={binding.measurement_result_reference_count}",
            fontsize=5.5,
            color=_MUTED,
            ha="right",
            va="center",
        )
        for column_index, state in enumerate(state_order):
            record = records[(binding.profile_ref, state)]
            color = _MEASUREMENT_COLORS[state.value]
            axis.add_patch(
                Rectangle(
                    (column_index + 0.08, y + 0.10),
                    0.84,
                    0.76,
                    facecolor=(color if record.reference_count else "#F5F6F6"),
                    edgecolor=color,
                    linewidth=0.75,
                    hatch=("///" if record.reference_count == 0 else None),
                )
            )
            axis.text(
                column_index + 0.5,
                y + 0.48,
                str(record.reference_count),
                fontsize=7.2,
                fontweight="bold",
                color=_TEXT,
                ha="center",
                va="center",
            )
    return figure


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
    records = _component_records(profile, component.ref)
    evidence_states = sorted({_value(row.evidence_state) for row in records})
    reasons = {reason for row in records for reason in row.reason_codes}
    if not records:
        evidence_states = ["inferred"]
        reasons.add("no_root_interpretation_requirements_returned")
    if render_reason:
        reasons.add(render_reason)
    if {"missing", "unknown", "unavailable"}.intersection(evidence_states) and not reasons:
        reasons.add(f"{component.slug.replace('-', '_')}_evidence_unavailable")
    value_field = {
        DOMAIN_AXES_COMPONENT_REF: "source_state",
        INTERPRETATION_REQUIREMENTS_COMPONENT_REF: "requirement_class",
        MEASUREMENT_STATES_COMPONENT_REF: "reference_count",
    }[component.ref]
    binding = VisualizationDataBinding(
        artifact_id=data_artifact.artifact_id,
        schema_ref=EVIDENCE_SUFFICIENCY_VISUALIZATION_DATA_SCHEMA_REF,
        object_version="0.1.0",
        sha256=data_artifact.sha256,
        records_path=component.records_path,
        record_lookup_key="record_id",
        evidence_ids_field="evidence_ids",
        value_field=value_field,
        evidence_state_field="evidence_state",
        scientific_status_field="scientific_status",
        missingness_field="missingness",
        applicability_field="applicability",
    )
    component_id, component_version = component.ref.split("@", 1)
    takeaway = _TAKEAWAYS[component.ref]
    return VisualizationArtifactV2(
        visualization_id=f"visualization:{run_id}:{component.slug}",
        component_id=component_id,
        component_version=component_version,
        data_binding=binding,
        producer_tool_id="P0-08",
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
                f"{component.title}. {takeaway} The typed table preserves all "
                "states, counts, reason codes, scopes and catalog bindings."
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
    if ref == DOMAIN_AXES_COMPONENT_REF:
        return list(profile.axis_records)
    if ref == INTERPRETATION_REQUIREMENTS_COMPONENT_REF:
        return list(profile.requirement_records)
    return list(profile.measurement_state_records)


def _component_applicability(records, render_reason):
    if render_reason:
        return "partially_applicable"
    if not records:
        return "applicable"
    states = {_value(row.applicability) for row in records}
    if states == {"not_assessed"}:
        return "not_assessed"
    return "applicable" if states == {"applicable"} else "partially_applicable"


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


def _state_style(state):
    if state in {
        "adequate",
        "validated_applicable",
        "applicable",
        "sufficient",
        "not_required",
    }:
        return _STATE_COLORS["available"]
    if state in {"limited", "candidate_applicable", "partially_applicable"}:
        return _STATE_COLORS["limited"]
    if state in {"insufficient", "unstable", "inapplicable", "not_applicable"}:
        return _STATE_COLORS["constrained"]
    return _STATE_COLORS["not_assessed"]


def _short_state(axis_id, state):
    scoped_labels = {
        EvidenceAxisId.INPUT_DATA: {
            "adequate": "Adequate\nfor required input",
            "limited": "Limited\nfor required input",
            "insufficient": "Insufficient\nfor required input",
            "not_assessed": "Not assessed\nfor required input",
        },
        EvidenceAxisId.INTERPRETATION: {
            "sufficient": "Sufficient\nunder current rules",
            "limited": "Limited\nunder current rules",
            "insufficient": "Insufficient\nunder current rules",
            "not_assessed": "Not assessed\nunder current rules",
        },
    }
    if state in scoped_labels.get(axis_id, {}):
        return scoped_labels[axis_id][state]
    labels = {
        "validated_applicable": "Validated\nfor declared use",
        "candidate_applicable": "Candidate\nfor declared use",
        "unstable": "Unstable\nin sensitivity checks",
        "applicable": "Applicable\nto declared context",
        "partially_applicable": "Partly applicable\nto declared context",
        "inapplicable": "Inapplicable\nto declared context",
        "not_required": "Not required\nby this specification",
        "not_applicable": "Not applicable\nto this context",
        "not_assessed": "Not assessed\nfor this scope",
    }
    return labels.get(state, _label(state))


def _footnote(ref):
    if ref == DOMAIN_AXES_COMPONENT_REF:
        return (
            "States are conditional on the bound MeasurementSpec, declared use and "
            "current candidate rules. No domain score, cross-domain rank or product "
            "decision is produced."
        )
    if ref == INTERPRETATION_REQUIREMENTS_COMPONENT_REF:
        return (
            "Only root profile conditions are shown. The figure does not infer which "
            "source caused a reason; review-required is distinct from catalog severity."
        )
    return (
        "Counts are MeasurementResult references within each domain profile, not "
        "independent evidence or biological replicates. Zero is not biological absence."
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
            "state_colors": _STATE_COLORS,
            "requirement_colors": _REQUIREMENT_COLORS,
            "measurement_colors": _MEASUREMENT_COLORS,
            "figure_width_in": _WIDTH,
        }
    )
    return hashlib.sha256(payload).hexdigest()


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
