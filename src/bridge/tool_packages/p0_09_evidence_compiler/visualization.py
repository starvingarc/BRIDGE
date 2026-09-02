from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import textwrap

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.patches import Rectangle

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_09_evidence_compiler.visualization_data import (
    CLAIM_INTERPRETATION_COMPONENT_REF,
    EVIDENCE_COMPILER_VISUALIZATION_DATA_SCHEMA_REF,
    FAMILY_RELATIONS_COMPONENT_REF,
    REQUIREMENTS_EXCLUSIONS_COMPONENT_REF,
    EvidenceCompilerVisualizationDataV1,
    P009VisualizationArtifactSet,
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
_WIDTH = 180.3 / 25.4
_BACKGROUND = "#FFFFFF"
_TEXT = "#26343B"
_MUTED = "#69767C"
_ROW = "#F5F7F7"
_COLORS = {
    "resolved": ("#DCEAF3", "#52758A"),
    "limited": ("#F5E7C8", "#8B6B34"),
    "conflict": ("#F2D8D0", "#9B5B4B"),
    "not_assessed": ("#E8E9EA", "#747B80"),
    "supports": ("#DCEAF3", "#52758A"),
    "contradicts": ("#F2D8D0", "#9B5B4B"),
    "mixed": ("#E7DDF0", "#705B83"),
}
_RC = {
    "font.family": ["DejaVu Sans"],
    "font.sans-serif": ["DejaVu Sans"],
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
    "svg.hashsalt": "BRIDGE-P0-09",
}


@dataclass(frozen=True)
class PreparedEvidenceCompilerVisualizations:
    payloads: dict[str, bytes]
    artifacts: tuple[ArtifactManifest, ...]


@dataclass(frozen=True)
class _Component:
    ref: str
    slug: str
    records_path: str
    table_name: str
    title: str
    value_field: str
    limit: int


_COMPONENTS = (
    _Component(
        CLAIM_INTERPRETATION_COMPONENT_REF,
        "claim-interpretation",
        "claim_records",
        "evidence_compiler_claim_interpretation.tsv",
        "Interpretation state for each available reconciliation",
        "eligibility",
        20,
    ),
    _Component(
        FAMILY_RELATIONS_COMPONENT_REF,
        "family-relations",
        "family_relation_records",
        "evidence_compiler_family_relations.tsv",
        "Evidence-family relations within each available reconciliation",
        "relation",
        24,
    ),
    _Component(
        REQUIREMENTS_EXCLUSIONS_COMPONENT_REF,
        "requirements-exclusions",
        "requirements_exclusions_records",
        "evidence_compiler_requirements_exclusions.tsv",
        "Current evidence requirements and compilation exclusions",
        "record_kind",
        30,
    ),
)
_TAKEAWAYS = {
    CLAIM_INTERPRETATION_COMPONENT_REF: (
        "Each row reports one available reconciliation and the records, channels "
        "and open requirements used by it."
    ),
    FAMILY_RELATIONS_COMPONENT_REF: (
        "Records connected by declared family dependencies remain grouped as one "
        "possible influence; record and family counts are audit counts, not votes."
    ),
    REQUIREMENTS_EXCLUSIONS_COMPONENT_REF: (
        "Open requirements, claim-level exclusions and exact rejected inputs remain "
        "distinct, so missing evidence is not displayed as a measured zero."
    ),
}
_LIMITATIONS = {
    CLAIM_INTERPRETATION_COMPONENT_REF: [
        "Interpretations are scoped to the registered claim and current reconciliation specification.",
        "Registry claims without evidence or explicit requirements do not produce a row; absence is not zero or missing evidence.",
        "Included and excluded record counts are audit counts, not independent evidence.",
        "No cross-claim score, rank, product decision or release authorization is produced.",
    ],
    FAMILY_RELATIONS_COMPONENT_REF: [
        "Dependency components use the current evidence-family registry and may change in a later registry version.",
        "One component is a candidate independent influence, not proof of biological independence.",
        "Support and contradiction describe registered claim relations, not product safety or efficacy.",
    ],
    REQUIREMENTS_EXCLUSIONS_COMPONENT_REF: [
        "An open requirement is missing evidence, not a zero measurement.",
        "Reconciliation reason codes are claim-level and are not assigned to individual excluded records.",
        "Only sanitized rejected-input identifiers and their exact rejection reasons are displayed.",
    ],
}


def prepare_evidence_compiler_visualizations(
    *,
    profile: EvidenceCompilerVisualizationDataV1,
    output_dir: Path,
    run_id: str,
    tool_version: str,
) -> PreparedEvidenceCompilerVisualizations:
    final_dir = output_dir / run_id
    payloads: dict[str, bytes] = {}
    artifacts: list[ArtifactManifest] = []
    data_name = "evidence_compiler_visualization_data.json"
    data_payload = canonical_json_bytes(profile.model_dump(mode="json"), indent=2)
    payloads[data_name] = data_payload
    data_artifact = _manifest(
        run_id,
        "evidence-compiler-visualization-data",
        "visualization_data",
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
        CLAIM_INTERPRETATION_COMPONENT_REF: _render_claims,
        FAMILY_RELATIONS_COMPONENT_REF: _render_families,
        REQUIREMENTS_EXCLUSIONS_COMPONENT_REF: _render_requirements_exclusions,
    }
    with matplotlib.rc_context(rc=_RC):
        for component in _COMPONENTS:
            table_payload = _table(profile, component.ref)
            payloads[component.table_name] = table_payload
            table_artifact = _manifest(
                run_id,
                f"evidence-compiler-{component.slug}-table",
                "visualization_table",
                final_dir / component.table_name,
                "text/tab-separated-values",
                table_payload,
                profile.evidence_ids,
            )
            tables[component.ref] = table_artifact
            artifacts.append(table_artifact)
            records = _records(profile, component.ref)
            reason = _static_render_reason(component, records)
            render_reasons[component.ref] = reason
            figure = (
                _fallback_figure(component, reason)
                if reason
                else renderers[component.ref](profile)
            )
            for extension, (media_type, payload) in _render_payloads(figure).items():
                name = f"evidence_compiler_{component.slug.replace('-', '_')}.{extension}"
                payloads[name] = payload
                artifact = _manifest(
                    run_id,
                    f"evidence-compiler-{component.slug}-{extension}",
                    "visualization_render",
                    final_dir / name,
                    media_type,
                    payload,
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
    artifact_set = P009VisualizationArtifactSet(
        artifact_set_id=f"p0-09-visualizations:{run_id.removeprefix('run-')}",
        data_profile_artifact_id=data_artifact.artifact_id,
        data_profile_sha256=data_artifact.sha256,
        visualizations=visualizations,
    )
    set_name = "evidence_compiler_visualization_artifact_set.json"
    set_payload = canonical_json_bytes(artifact_set.model_dump(mode="json"), indent=2)
    payloads[set_name] = set_payload
    artifacts.append(
        _manifest(
            run_id,
            "evidence-compiler-visualization-artifact-set",
            "visualization_artifact_set",
            final_dir / set_name,
            "application/json",
            set_payload,
            profile.evidence_ids,
        )
    )
    return PreparedEvidenceCompilerVisualizations(payloads, tuple(artifacts))


def _records(profile, ref):
    if ref == CLAIM_INTERPRETATION_COMPONENT_REF:
        return list(profile.claim_records)
    if ref == FAMILY_RELATIONS_COMPONENT_REF:
        return list(profile.family_relation_records)
    return list(profile.requirements_exclusions_records)


def _static_render_reason(component, records):
    if len(records) > component.limit:
        return "static_render_requires_complete_table_fallback"
    if component.ref == REQUIREMENTS_EXCLUSIONS_COMPONENT_REF and any(
        len(
            textwrap.wrap(
                " · ".join(_label(item) for item in record.reason_codes)
                or "none recorded",
                48,
            )
        )
        > 3
        for record in records
    ):
        return "static_render_requires_complete_table_fallback"
    return None


def _table(profile, ref):
    records = [item.model_dump(mode="json") for item in _records(profile, ref)]
    fields: list[str] = []
    for record in records:
        for field in record:
            if field not in fields:
                fields.append(field)
    if not fields:
        fields = {
            CLAIM_INTERPRETATION_COMPONENT_REF: [
                "record_id",
                "claim_ref",
                "eligibility",
                "reconciliation_state",
                "direction",
                "included_record_count",
                "excluded_record_count",
                "open_requirement_count",
            ],
            FAMILY_RELATIONS_COMPONENT_REF: [
                "record_id",
                "claim_ref",
                "channel_role",
                "component_id",
                "family_refs",
                "evidence_refs",
                "relation",
                "participation",
            ],
            REQUIREMENTS_EXCLUSIONS_COMPONENT_REF: [
                "record_id",
                "record_kind",
                "claim_ref",
                "evidence_state",
                "reason_codes",
                "reason_attribution_scope",
            ],
        }[ref]
    buffer = StringIO(newline="")
    writer = csv.DictWriter(
        buffer, fieldnames=fields, delimiter="\t", lineterminator="\n"
    )
    writer.writeheader()
    for record in records:
        writer.writerow({field: _table_cell(record.get(field)) for field in fields})
    return buffer.getvalue().encode()


def _table_cell(value):
    if isinstance(value, (list, dict)):
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    return "" if value is None else value


def _base(title, subtitle, height, footnote):
    figure = plt.figure(figsize=(_WIDTH, height), facecolor=_BACKGROUND)
    figure.text(
        0.045, 0.965, title, fontsize=11.0, fontweight="bold", color=_TEXT, va="top"
    )
    figure.text(
        0.045,
        0.920,
        subtitle,
        fontsize=7.15,
        color=_MUTED,
        va="top",
    )
    figure.text(
        0.045,
        0.025,
        textwrap.fill(footnote, 112),
        fontsize=6.15,
        color=_MUTED,
        va="bottom",
        linespacing=1.18,
    )
    return figure


def _fallback_figure(component, reason):
    figure = _base(
        component.title,
        "The complete typed table is retained without truncation.",
        4.7,
        "The static figure capacity was exceeded. No top-N selection or silent omission was applied.",
    )
    axis = figure.add_axes((0.07, 0.20, 0.86, 0.55))
    axis.axis("off")
    axis.text(
        0,
        0.66,
        "Static figure uses the complete-table fallback",
        fontsize=11.0,
        fontweight="bold",
        color=_TEXT,
    )
    axis.text(0, 0.42, _label(reason), fontsize=8.0, color=_MUTED)
    return figure


def _render_claims(profile):
    records = sorted(
        profile.claim_records, key=lambda item: (item.claim_ref, item.record_id)
    )
    figure = _base(
        _COMPONENTS[0].title,
        "Available reconciliation state, direction, evidence-record accounting and open requirements.",
        max(4.8, 3.25 + 0.58 * max(1, len(records))),
        "Counts are compilation audit counts. They do not quantify independent evidence or product quality.",
    )
    axis = figure.add_axes((0.025, 0.13, 0.95, 0.72))
    axis.set_xlim(0, 1)
    axis.set_ylim(-0.4, max(1, len(records)) + 0.65)
    axis.axis("off")
    headers = (
        (0.02, "Registered claim"),
        (0.31, "Current interpretation"),
        (0.54, "Direction"),
        (0.66, "Channels"),
        (0.78, "Records"),
        (0.91, "Open"),
    )
    _headers(axis, headers, max(1, len(records)) + 0.24)
    if not records:
        _empty_row(axis, "No reconciliation record is available for this graph.")
        return figure
    for index, record in enumerate(records):
        y = len(records) - index - 1
        _row_background(axis, y, index)
        label = (
            f"{_short_ref(record.claim_ref)}\n{_label(record.claim_type)}\n"
            f"{_label(record.domain_id)}"
        )
        axis.text(0.02, y + 0.43, label, fontsize=5.25, color=_TEXT, va="center")
        state_label = (
            _label(record.reconciliation_state)
            if record.reconciliation_state
            else _label(record.eligibility)
        )
        style = (
            "conflict"
            if record.missingness == "conflict"
            else "limited"
            if record.missingness == "missing"
            else "not_assessed"
            if record.missingness == "not_assessed"
            else "resolved"
        )
        _badge(axis, 0.31, y + 0.19, 0.205, state_label, style)
        axis.text(
            0.59,
            y + 0.43,
            _label(record.direction or "not resolved"),
            fontsize=5.9,
            color=_TEXT,
            ha="center",
            va="center",
        )
        axis.text(
            0.715,
            y + 0.43,
            f"{record.eligible_channel_count}/{record.total_channel_count}",
            fontsize=6.4,
            color=_TEXT,
            ha="center",
            va="center",
        )
        axis.text(
            0.835,
            y + 0.43,
            f"{record.included_record_count} in · {record.excluded_record_count} out",
            fontsize=5.8,
            color=_TEXT,
            ha="center",
            va="center",
        )
        axis.text(
            0.94,
            y + 0.43,
            str(record.open_requirement_count),
            fontsize=7.0,
            fontweight="bold",
            color=_TEXT,
            ha="center",
            va="center",
        )
    return figure


def _render_families(profile):
    records = sorted(
        profile.family_relation_records,
        key=lambda item: (item.claim_ref, item.channel_role, item.component_id),
    )
    figure = _base(
        _COMPONENTS[1].title,
        "Dependency-connected family records remain grouped within each claim and channel.",
        max(4.8, 3.25 + 0.58 * max(1, len(records))),
        "A component is one possible independent influence under the current registry, not a vote or proof of independence.",
    )
    axis = figure.add_axes((0.025, 0.13, 0.95, 0.72))
    axis.set_xlim(0, 1)
    axis.set_ylim(-0.4, max(1, len(records)) + 0.65)
    axis.axis("off")
    headers = (
        (0.02, "Claim and channel"),
        (0.34, "Dependency component"),
        (0.57, "Relation"),
        (0.71, "Participation"),
        (0.86, "Families · records"),
    )
    _headers(axis, headers, max(1, len(records)) + 0.24)
    if not records:
        _empty_row(axis, "No included or excluded evidence-family relation is available.")
        return figure
    for index, record in enumerate(records):
        y = len(records) - index - 1
        _row_background(axis, y, index)
        axis.text(
            0.02,
            y + 0.43,
            f"{_short_ref(record.claim_ref)}\n{_label(record.channel_role)}",
            fontsize=5.65,
            color=_TEXT,
            va="center",
        )
        axis.text(
            0.34,
            y + 0.43,
            _short_ref(record.component_id),
            fontsize=5.7,
            color=_TEXT,
            va="center",
        )
        style = "mixed" if record.relation == "conflict" else record.relation
        _badge(axis, 0.57, y + 0.19, 0.115, _label(record.relation), style)
        _badge(
            axis,
            0.71,
            y + 0.19,
            0.12,
            _label(record.participation),
            "mixed" if record.participation == "mixed" else "resolved",
        )
        axis.text(
            0.91,
            y + 0.43,
            f"{len(record.family_refs)} · {record.raw_record_count}",
            fontsize=6.7,
            fontweight="bold",
            color=_TEXT,
            ha="center",
            va="center",
        )
    return figure


def _requirement_exclusion_sort_key(item):
    if item.record_kind == "requirement":
        return (
            "requirement",
            item.claim_ref,
            item.channel_role,
            item.requirement_key,
            item.requirement_ref,
        )
    return (
        "exclusion",
        item.claim_ref or "",
        item.source_id or "",
        item.exclusion_kind,
        item.record_id,
    )


def _render_requirements_exclusions(profile):
    records = sorted(
        profile.requirements_exclusions_records,
        key=_requirement_exclusion_sort_key,
    )
    figure = _base(
        _COMPONENTS[2].title,
        "Missing requirements, claim-level exclusions and exact rejected inputs are separate.",
        max(4.8, 3.25 + 0.61 * max(1, len(records))),
        "Missing evidence is not zero. Claim-level reasons are not assigned to individual excluded evidence records.",
    )
    axis = figure.add_axes((0.025, 0.13, 0.95, 0.72))
    axis.set_xlim(0, 1)
    axis.set_ylim(-0.4, max(1, len(records)) + 0.65)
    axis.axis("off")
    headers = (
        (0.02, "Record class"),
        (0.20, "Claim or source"),
        (0.48, "Current state"),
        (0.64, "Count"),
        (0.73, "Recorded reasons"),
    )
    _headers(axis, headers, max(1, len(records)) + 0.24)
    if not records:
        _empty_row(axis, "No requirement or compilation exclusion is recorded.")
        return figure
    for index, record in enumerate(records):
        y = len(records) - index - 1
        _row_background(axis, y, index)
        if record.record_kind == "requirement":
            record_class = "requirement"
            identity = (
                f"{_short_ref(record.claim_ref)}\n"
                f"{_label(record.channel_role)} · {_label(record.requirement_key)}\n"
                f"{_short_ref(record.requirement_ref)}"
            )
            state = record.requirement_state
            count = record.satisfying_record_count
            style = (
                "limited"
                if record.requirement_state == "open"
                else "not_assessed"
                if record.requirement_state == "not_applicable"
                else "resolved"
            )
        else:
            record_class = record.exclusion_kind
            identity = _short_ref(record.claim_ref or record.source_id or "unbound")
            state = _label(record.reason_attribution_scope)
            count = record.excluded_record_count
            style = (
                "conflict"
                if record.exclusion_kind == "input_rejection"
                else "not_assessed"
            )
        axis.text(
            0.02,
            y + 0.43,
            _label(record_class),
            fontsize=5.7,
            color=_TEXT,
            va="center",
        )
        axis.text(0.20, y + 0.43, identity, fontsize=5.7, color=_TEXT, va="center")
        _badge(axis, 0.48, y + 0.19, 0.135, _label(state), style)
        axis.text(
            0.675,
            y + 0.43,
            str(count),
            fontsize=6.8,
            fontweight="bold",
            color=_TEXT,
            ha="center",
            va="center",
        )
        reason = " · ".join(_label(item) for item in record.reason_codes) or "none recorded"
        axis.text(
            0.73,
            y + 0.43,
            textwrap.fill(reason, 48),
            fontsize=5.25,
            color=_TEXT,
            va="center",
            linespacing=1.08,
        )
    return figure


def _headers(axis, headers, y):
    for x, label in headers:
        axis.text(x, y, label, fontsize=6.1, fontweight="bold", color=_TEXT)


def _row_background(axis, y, index):
    if index % 2 == 0:
        axis.add_patch(Rectangle((0.01, y - 0.02), 0.98, 0.90, color=_ROW, zorder=0))


def _empty_row(axis, message):
    axis.text(0.02, 0.48, message, fontsize=8.0, color=_MUTED, va="center")


def _badge(axis, x, y, width, label, style):
    fill, edge = _COLORS[style]
    axis.add_patch(
        Rectangle(
            (x, y),
            width,
            0.48,
            facecolor=fill,
            edgecolor=edge,
            linewidth=0.75,
        )
    )
    axis.text(
        x + width / 2,
        y + 0.24,
        textwrap.fill(label, max(10, int(width * 90))),
        fontsize=5.25,
        fontweight="bold",
        color=_TEXT,
        ha="center",
        va="center",
        linespacing=1.0,
    )


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
    records = _records(profile, component.ref)
    evidence_states = sorted(
        {_value(item.evidence_state) for item in records}
        or {EvidenceState.UNAVAILABLE.value}
    )
    reasons = {reason for item in records for reason in item.reason_codes}
    if not records:
        reasons.add("no_records_for_visualization_component")
    if render_reason:
        reasons.add(render_reason)
    if {"missing", "unknown", "unavailable"}.intersection(evidence_states) and not reasons:
        reasons.add("component_contains_unresolved_evidence")
    binding = VisualizationDataBinding(
        artifact_id=data_artifact.artifact_id,
        schema_ref=EVIDENCE_COMPILER_VISUALIZATION_DATA_SCHEMA_REF,
        object_version="0.1.0",
        sha256=data_artifact.sha256,
        records_path=component.records_path,
        record_lookup_key="record_id",
        evidence_ids_field="evidence_ids",
        value_field=component.value_field,
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
        producer_tool_id="P0-09",
        producer_tool_version=tool_version,
        producer_run_ref=f"run:{run_id}",
        evidence_ids=profile.evidence_ids,
        evidence_states=evidence_states,
        scientific_status="candidate",
        applicability=_applicability(records, render_reason),
        missing_reason_codes=sorted(reasons),
        insight_title=component.title,
        takeaway=takeaway,
        limitations=_LIMITATIONS[component.ref],
        accessibility=VisualizationAccessibility(
            alt_text=f"{component.title}. {takeaway}",
            long_description=(
                f"{component.title}. {takeaway} The complete typed table retains "
                "all states, evidence references, scopes, counts and reason codes."
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


def _applicability(records, render_reason):
    if render_reason:
        return "partially_applicable"
    if not records:
        return "not_assessed"
    states = {_value(item.applicability) for item in records}
    if states == {"not_assessed"}:
        return "not_assessed"
    if states == {"not_applicable"}:
        return "not_applicable"
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


def _config_hash(ref):
    source = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    payload = canonical_json_bytes(
        {
            "component_ref": ref,
            "renderer": [_RENDERER_ID, _RENDERER_VERSION, _EXPORT_PROFILE_ID],
            "source_sha256": source,
            "matplotlib_version": matplotlib.__version__,
            "matplotlib_rc": _RC,
            "colors": _COLORS,
            "figure_width_in": _WIDTH,
        }
    )
    return hashlib.sha256(payload).hexdigest()


def _label(value):
    return _value(value).replace("_", " ").replace("-", " ")


def _value(value):
    return str(getattr(value, "value", value))


def _short_ref(value):
    if value is None:
        return "not recorded"
    text = str(value)
    if len(text) <= 34:
        return text
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return f"{text[:12]}…{text[-10:]}·{digest}"


def _manifest(run_id, suffix, kind, path, media_type, payload, evidence_ids):
    return ArtifactManifest(
        artifact_id=f"artifact:{run_id}:{suffix}",
        kind=kind,
        path=path,
        media_type=media_type,
        sha256=hashlib.sha256(payload).hexdigest(),
        evidence_ids=evidence_ids,
    )
