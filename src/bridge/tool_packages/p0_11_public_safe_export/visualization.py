from __future__ import annotations

import csv
import hashlib
import json
import textwrap
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path
import re
from xml.etree import ElementTree

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.patches import Rectangle

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_11_public_safe_export.visualization_data import (
    ARTIFACT_STATUS_COMPONENT_REF,
    AUDIT_COMPONENT_BINDINGS,
    CHECK_DISPLAY_NAMES,
    FieldProjectionState,
    LOCAL_EXPORT_STATE_COMPONENT_REF,
    LocalExportStep,
    LocalExportStepState,
    PUBLIC_SAFE_EXPORT_VISUALIZATION_DATA_SCHEMA_REF,
    REGISTERED_CHECKS_COMPONENT_REF,
    REPORT_COMPONENT_BINDINGS,
    REPORT_FIELD_PROJECTION_COMPONENT_REF,
    REASON_DISPLAY_NAMES,
    ArtifactAuditVisualizationDataV1,
    ArtifactDisplayState,
    P011VisualizationArtifactSet,
    PublicSafeExportMode,
    PublicSafeExportVisualizationDataV1,
    RegisteredCheckDisplayState,
    ReportExportVisualizationDataV1,
    _p011_artifact_id,
    _p011_visualization_id,
)
from bridge.toolkit.contracts import ArtifactManifest, EvidenceState
from bridge.toolkit.visualization import (
    FigureRegistry,
    VisualizationAccessibility,
    VisualizationArtifactV2,
    VisualizationDataBinding,
    VisualizationRenderBinding,
)


_RENDERER_ID = "bridge.matplotlib.public-safe-export"
_RENDERER_VERSION = "0.1.0"
_EXPORT_PROFILE_ID = "bridge-static-scientific-figure-v0.1"
_WIDTH = 180.3 / 25.4
_BACKGROUND = "#FFFFFF"
_TEXT = "#26363D"
_MUTED = "#68777D"
_RULE = "#D7DEDF"
_ROW = "#F7F9F9"
_STATES = {
    "included": ("#DDEFE8", "#235C4B"),
    "omitted_by_policy": ("#F5E2C2", "#76551D"),
    "not_applicable_in_source": ("#ECEEEF", "#59666B"),
    "completed": ("#E2ECEF", "#355C67"),
    "no_registered_rule_blocked": ("#DDEFE8", "#235C4B"),
    "awaiting_matching_candidate_hash": ("#F5E2C2", "#76551D"),
    "matching_candidate_hash_supplied": ("#E2ECEF", "#355C67"),
    "written_locally": ("#E2ECEF", "#355C67"),
    "not_performed_by_tool": ("#ECEEEF", "#59666B"),
    "blocked_by_registered_rule": ("#F1D8D4", "#7B3832"),
    "not_applicable": ("#ECEEEF", "#59666B"),
}
_RC = {
    "font.family": ["DejaVu Sans"],
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
    "svg.hashsalt": "BRIDGE-P0-11",
    "axes.linewidth": 0.6,
}
_CHECK_DISPLAY_ORDER = (
    "METHOD-OS-CLI",
    "METHOD-FORMAT-GATE",
    "METHOD-CUSTOM-DETERMINISTIC-RULES",
    "METHOD-JSONSCHEMA-HASHLIB",
    "METHOD-MARKDOWN-PARSER-REGEX",
    "METHOD-URL-PARSER-ALLOWLIST",
    "METHOD-CSV-DETERMINISTIC-RULE",
    "METHOD-CUSTOM-SVG-INSPECTOR",
)
if set(_CHECK_DISPLAY_ORDER) != set(CHECK_DISPLAY_NAMES):
    raise RuntimeError("registered check display order is incomplete")

_FIELD_LABELS = {
    "claim_type": "Claim type",
    "text": "Claim text",
    "language": "Language",
    "statement_refs": "Statement references",
    "reported_evidence_state": "Evidence state",
    "comparison_mode": "Comparison scope",
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
    "stroke-linecap",
    "stroke-linejoin",
    "stroke-opacity",
    "stroke-width",
    "text-anchor",
}
_STEP_LABELS = {
    LocalExportStep.ALLOWLIST_PROJECTION: "Allowlist projection",
    LocalExportStep.REGISTERED_LEAK_RULES: "Registered disclosure-pattern checks",
    LocalExportStep.CANDIDATE_HASH_MATCH: "Exact candidate-hash match",
    LocalExportStep.LOCAL_CANDIDATE_FILES: "Local candidate files",
    LocalExportStep.NETWORK_UPLOAD: "Network upload",
}
_STEP_STATE_LABELS = {
    LocalExportStepState.COMPLETED: "completed",
    LocalExportStepState.NO_REGISTERED_RULE_BLOCKED: "no registered rule blocked",
    LocalExportStepState.AWAITING_MATCHING_CANDIDATE_HASH: "awaiting matching candidate hash",
    LocalExportStepState.MATCHING_CANDIDATE_HASH_SUPPLIED: "matching candidate hash supplied",
    LocalExportStepState.WRITTEN_LOCALLY: "written locally",
    LocalExportStepState.NOT_PERFORMED_BY_TOOL: "not performed by this tool",
}


@dataclass(frozen=True)
class PreparedPublicSafeExportVisualizations:
    payloads: dict[str, bytes]
    artifacts: tuple[ArtifactManifest, ...]


@dataclass(frozen=True)
class _Component:
    ref: str
    slug: str
    records_path: str
    table_name: str
    title: str


_COMPONENT_METADATA = {
    REPORT_FIELD_PROJECTION_COMPONENT_REF: (
        "public_safe_export_report_field_projection.tsv",
        "Claim-content field projection under the current policy",
    ),
    LOCAL_EXPORT_STATE_COMPONENT_REF: (
        "public_safe_export_local_export_state.tsv",
        "Candidate hash and local-file state",
    ),
    ARTIFACT_STATUS_COMPONENT_REF: (
        "public_safe_export_artifact_status.tsv",
        "Candidate artifact status under registered checks",
    ),
    REGISTERED_CHECKS_COMPONENT_REF: (
        "public_safe_export_registered_checks.tsv",
        "Registered checks by candidate artifact",
    ),
}
_TAKEAWAYS = {
    REPORT_FIELD_PROJECTION_COMPONENT_REF: (
        "Six policy-controlled claim fields are shown for every claim. Claim text "
        "values are not shown; fixed public IDs and aliases are rebuilt separately. "
        "Structural and provenance fields are outside this matrix; retention is not "
        "wording or scientific approval."
    ),
    LOCAL_EXPORT_STATE_COMPONENT_REF: (
        "The ledger separates deterministic candidate construction, exact hash "
        "matching and local file creation from network publication. A matching "
        "value only matches this candidate digest (report bytes, policy hash and "
        "target channel); it does not authenticate who supplied it or constitute "
        "approval."
    ),
    ARTIFACT_STATUS_COMPONENT_REF: (
        "Each candidate artifact is shown with its declared format, executed audit "
        "count and any registered rule that blocked it. File contents and original "
        "identifiers are not shown; no-block is not general privacy, safety or "
        "publication approval."
    ),
    REGISTERED_CHECKS_COMPONENT_REF: (
        "Every artifact-check pair has an explicit no-block, blocked or "
        "not-applicable state; an empty cell never carries meaning. File contents "
        "and original identifiers are not shown, and no-block is not general "
        "privacy, safety or publication approval."
    ),
}
_LIMITATIONS = {
    REPORT_FIELD_PROJECTION_COMPONENT_REF: [
        "Retained means present in the local public-report candidate under the current allowlist.",
        "A retained field is not an approval of the wording or underlying scientific claim.",
        "Claim text and original identifiers are excluded from this visualization.",
    ],
    LOCAL_EXPORT_STATE_COMPONENT_REF: [
        "Hash matching requires the exact 64-character candidate hash.",
        "A matching value only matches this candidate digest (report bytes, policy hash and target channel); "
        "it does not authenticate who supplied it or constitute approval.",
        "Local candidate files are not publication approval and are not uploaded by this tool.",
        "The ToolRun execution receipt is internal and is not a public-safe artifact.",
    ],
    ARTIFACT_STATUS_COMPONENT_REF: [
        "No registered rule blocked is limited to the checks that actually ran.",
        "Audit counts are descriptive counts, not a risk score or completeness percentage.",
        "Original artifact identifiers, paths, source references and content are excluded.",
    ],
    REGISTERED_CHECKS_COMPONENT_REF: [
        "Not applicable means that a registered check did not apply to that file format.",
        "No registered rule blocked is not a general privacy, safety or publication decision.",
        "The complete typed table is authoritative when the static figure uses fallback.",
    ],
}


def prepare_public_safe_export_visualizations(
    *,
    profile: ReportExportVisualizationDataV1 | ArtifactAuditVisualizationDataV1,
    output_dir: Path,
    run_id: str,
    tool_version: str,
) -> PreparedPublicSafeExportVisualizations:
    if profile.producer_run_ref != f"run:{run_id}":
        raise ValueError("visualization profile does not bind the producer run")
    bindings = (
        REPORT_COMPONENT_BINDINGS
        if profile.mode is PublicSafeExportMode.REPORT_EXPORT
        else AUDIT_COMPONENT_BINDINGS
    )
    components = tuple(
        _Component(ref, slug, path, *_COMPONENT_METADATA[ref])
        for ref, slug, path in bindings
    )
    final_dir = output_dir / run_id
    payloads: dict[str, bytes] = {}
    artifacts: list[ArtifactManifest] = []

    data_name = "public_safe_export_visualization_data.json"
    root_profile = PublicSafeExportVisualizationDataV1(root=profile)
    data_payload = canonical_json_bytes(root_profile.model_dump(mode="json"), indent=2)
    payloads[data_name] = data_payload
    data_artifact = _manifest(
        run_id,
        "public-safe-export-visualization-data",
        "public_safe_export_visualization_data",
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
        REPORT_FIELD_PROJECTION_COMPONENT_REF: _render_field_projection,
        LOCAL_EXPORT_STATE_COMPONENT_REF: _render_local_export_state,
        ARTIFACT_STATUS_COMPONENT_REF: _render_artifact_status,
        REGISTERED_CHECKS_COMPONENT_REF: _render_registered_checks,
    }
    with matplotlib.rc_context(rc=_RC):
        for component in components:
            evidence_ids = _component_evidence_ids(profile, component.ref)
            table_payload = _table(profile, component.ref)
            payloads[component.table_name] = table_payload
            table_artifact = _manifest(
                run_id,
                f"public-safe-export-{component.slug}-table",
                "visualization_table",
                final_dir / component.table_name,
                "text/tab-separated-values",
                table_payload,
                evidence_ids,
            )
            tables[component.ref] = table_artifact
            artifacts.append(table_artifact)

            reason = _static_render_reason(profile, component.ref)
            render_reasons[component.ref] = reason
            figure = (
                _fallback_figure(component, reason)
                if reason is not None
                else renderers[component.ref](profile)
            )
            for extension, (media_type, render_payload) in _render_payloads(
                figure
            ).items():
                filename = f"public_safe_export_{component.slug}.{extension}"
                payloads[filename] = render_payload
                artifact = _manifest(
                    run_id,
                    f"public-safe-export-{component.slug}-{extension}",
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
        for component in components
    ]
    registry = FigureRegistry.load_default()
    for visualization in visualizations:
        registry.validate_artifact(visualization)

    artifact_set = P011VisualizationArtifactSet(
        mode=profile.mode,
        artifact_set_id=f"p0-11-visualizations:{run_id.removeprefix('run-')}",
        data_profile_artifact_id=data_artifact.artifact_id,
        data_profile_sha256=data_artifact.sha256,
        visualizations=visualizations,
    )
    artifact_set_name = "p0_11_visualization_artifact_set.json"
    artifact_set_payload = canonical_json_bytes(
        artifact_set.model_dump(mode="json"), indent=2
    )
    payloads[artifact_set_name] = artifact_set_payload
    artifacts.append(
        _manifest(
            run_id,
            "p0-11-visualization-artifact-set",
            "visualization_artifact_set",
            final_dir / artifact_set_name,
            "application/json",
            artifact_set_payload,
            profile.evidence_ids,
        )
    )
    return PreparedPublicSafeExportVisualizations(payloads, tuple(artifacts))


def _records(profile, ref):
    if ref == REPORT_FIELD_PROJECTION_COMPONENT_REF:
        return list(profile.field_records)
    if ref == LOCAL_EXPORT_STATE_COMPONENT_REF:
        return list(profile.state_records)
    if ref == ARTIFACT_STATUS_COMPONENT_REF:
        return list(profile.artifact_records)
    if ref == REGISTERED_CHECKS_COMPONENT_REF:
        return list(profile.check_records)
    raise KeyError(ref)


def _component_evidence_ids(profile, ref: str) -> list[str]:
    return sorted(
        {
            evidence_id
            for record in _records(profile, ref)
            for evidence_id in record.evidence_ids
        }
    )


def _static_render_reason(profile, ref: str) -> str | None:
    if (
        ref == REPORT_FIELD_PROJECTION_COMPONENT_REF
        and profile.claim_count > 18
    ):
        return "static_render_requires_complete_table_fallback"
    if (
        ref == ARTIFACT_STATUS_COMPONENT_REF
        and any(
            len(record.reason_codes) > 1 for record in profile.artifact_records
        )
    ):
        return "static_render_requires_complete_table_fallback"
    return None


def _table(profile, ref: str) -> bytes:
    rows = [record.model_dump(mode="json") for record in _records(profile, ref)]
    for row in rows:
        if ref == LOCAL_EXPORT_STATE_COMPONENT_REF:
            row["candidate_hash"] = profile.candidate_hash
        if ref in {ARTIFACT_STATUS_COMPONENT_REF, REGISTERED_CHECKS_COMPONENT_REF}:
            row["reason_labels"] = [
                REASON_DISPLAY_NAMES[reason] for reason in row["reason_codes"]
            ]
    fields = list(rows[0]) if rows else ["record_id", "display_state"]
    buffer = StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=fields,
        delimiter="\t",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _table_cell(value) for key, value in row.items()})
    return buffer.getvalue().encode()


def _table_cell(value):
    if isinstance(value, (list, dict)):
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return "" if value is None else value


def _render_field_projection(profile: ReportExportVisualizationDataV1):
    rows_by_claim = {}
    for record in profile.field_records:
        rows_by_claim.setdefault(record.claim_display_id, []).append(record)
    claims = list(rows_by_claim)
    height = max(4.9, 2.8 + 0.34 * len(claims))
    counts = {
        state: sum(
            record.projection_state is state for record in profile.field_records
        )
        for state in FieldProjectionState
    }
    figure = _base(
        _COMPONENT_METADATA[REPORT_FIELD_PROJECTION_COMPONENT_REF][1],
        (
            f"Claims: {profile.claim_count} · {counts[FieldProjectionState.INCLUDED]} "
            "retained · "
            f"{counts[FieldProjectionState.OMITTED_BY_POLICY]} not retained by policy · "
            f"{counts[FieldProjectionState.NOT_APPLICABLE_IN_SOURCE]} no source value"
        ),
        height,
        _TAKEAWAYS[REPORT_FIELD_PROJECTION_COMPONENT_REF],
    )
    axis = figure.add_axes((0.20, 0.18, 0.76, 0.64))
    fields = list(rows_by_claim[claims[0]])
    axis.set_xlim(0, len(fields))
    axis.set_ylim(len(claims), 0)
    axis.set_xticks([index + 0.5 for index in range(len(fields))])
    axis.set_xticklabels(
        [textwrap.fill(_FIELD_LABELS[record.field.value], 14) for record in fields],
        fontsize=5.9,
        rotation=0,
        ha="center",
    )
    axis.tick_params(axis="x", top=True, labeltop=True, bottom=False, labelbottom=False)
    axis.set_yticks([index + 0.5 for index in range(len(claims))])
    axis.set_yticklabels(claims, fontsize=6.6)
    axis.tick_params(length=0, pad=4)
    symbols = {
        FieldProjectionState.INCLUDED: "●",
        FieldProjectionState.OMITTED_BY_POLICY: "○",
        FieldProjectionState.NOT_APPLICABLE_IN_SOURCE: "—",
    }
    for y, claim in enumerate(claims):
        for x, record in enumerate(rows_by_claim[claim]):
            fill, edge = _STATES[record.projection_state.value]
            axis.add_patch(
                Rectangle(
                    (x + 0.06, y + 0.08),
                    0.88,
                    0.84,
                    facecolor=fill,
                    edgecolor=edge,
                    linewidth=0.7,
                )
            )
            axis.text(
                x + 0.5,
                y + 0.5,
                symbols[record.projection_state],
                ha="center",
                va="center",
                fontsize=8.5,
                color=edge,
            )
    for spine in axis.spines.values():
        spine.set_visible(False)
    figure.text(
        0.20,
        0.105,
        "● retained   ○ not retained by policy   — no source value",
        fontsize=6.5,
        color=_MUTED,
    )
    return figure


def _render_local_export_state(profile: ReportExportVisualizationDataV1):
    figure = _base(
        _COMPONENT_METADATA[LOCAL_EXPORT_STATE_COMPONENT_REF][1],
        "Local file state · no network upload · not publication approval",
        5.4,
        _TAKEAWAYS[LOCAL_EXPORT_STATE_COMPONENT_REF],
    )
    axis = figure.add_axes((0.055, 0.14, 0.89, 0.68))
    axis.set_xlim(0, 1)
    axis.set_ylim(5, 0)
    axis.axis("off")
    for index, record in enumerate(profile.state_records):
        y = index + 0.08
        if record.step is LocalExportStep.NETWORK_UPLOAD:
            axis.plot([0, 1], [y - 0.13, y - 0.13], color=_RULE, linewidth=0.9)
            axis.text(
                0,
                y - 0.21,
                "Outside this tool's scope",
                fontsize=5.8,
                color=_MUTED,
                va="bottom",
            )
        fill, edge = _STATES[record.state.value]
        axis.add_patch(
            Rectangle(
                (0, y),
                1,
                0.72,
                facecolor=_ROW if index % 2 == 0 else _BACKGROUND,
                edgecolor="none",
            )
        )
        axis.add_patch(
            Rectangle(
                (0.01, y + 0.14),
                0.035,
                0.35,
                facecolor=fill,
                edgecolor=edge,
                linewidth=0.8,
            )
        )
        axis.text(
            0.07,
            y + 0.24,
            _STEP_LABELS[record.step],
            fontsize=7.1,
            color=_TEXT,
            fontweight="bold",
        )
        axis.text(
            0.07,
            y + 0.49,
            _STEP_STATE_LABELS[record.state],
            fontsize=6.3,
            color=edge,
        )
    figure.text(
        0.055,
        0.082,
        "Candidate hash  "
        + profile.candidate_hash[:32]
        + "\n"
        + " " * 24
        + profile.candidate_hash[32:],
        fontsize=6.2,
        color=_TEXT,
        family="DejaVu Sans",
    )
    return figure


def _render_artifact_status(profile: ArtifactAuditVisualizationDataV1):
    height = max(4.9, 2.9 + 0.58 * profile.artifact_count)
    blocked = sum(
        record.audit_state is ArtifactDisplayState.BLOCKED_BY_REGISTERED_RULE
        for record in profile.artifact_records
    )
    figure = _base(
        _COMPONENT_METADATA[ARTIFACT_STATUS_COMPONENT_REF][1],
        (
            f"Candidate artifacts: {profile.artifact_count} · {blocked} with a "
            "registered blocking finding · counts are not risk scores"
        ),
        height,
        _TAKEAWAYS[ARTIFACT_STATUS_COMPONENT_REF],
    )
    axis = figure.add_axes((0.045, 0.14, 0.91, 0.70))
    axis.set_xlim(0, 1)
    axis.set_ylim(profile.artifact_count, 0)
    axis.axis("off")
    headers = (
        (0.01, "Candidate", "left"),
        (0.18, "Declared format", "left"),
        (0.37, "Bytes", "right"),
        (0.42, "Executed checks", "left"),
        (0.59, "State and registered reasons", "left"),
    )
    for x, label, alignment in headers:
        axis.text(
            x,
            -0.13,
            label,
            fontsize=6.1,
            color=_MUTED,
            fontweight="bold",
            ha=alignment,
        )
    for index, record in enumerate(profile.artifact_records):
        y = index + 0.08
        fill, edge = _STATES[record.audit_state.value]
        axis.add_patch(
            Rectangle(
                (0, y),
                1,
                0.78,
                facecolor=_ROW if index % 2 == 0 else _BACKGROUND,
                edgecolor="none",
            )
        )
        axis.add_patch(
            Rectangle(
                (0.005, y + 0.08),
                0.012,
                0.62,
                facecolor=edge,
                edgecolor="none",
            )
        )
        axis.text(
            0.03,
            y + 0.38,
            record.artifact_display_id,
            fontsize=6.8,
            color=_TEXT,
            fontweight="bold",
            va="center",
        )
        axis.text(0.18, y + 0.38, record.declared_format.value.upper(), fontsize=6.5, va="center")
        axis.text(
            0.37,
            y + 0.38,
            f"{record.byte_count:,}",
            fontsize=6.5,
            ha="right",
            va="center",
        )
        axis.text(
            0.48,
            y + 0.38,
            str(record.check_count),
            fontsize=6.5,
            ha="center",
            va="center",
        )
        if record.reason_codes:
            if len(record.reason_codes) != 1:
                raise ValueError("artifact status requires complete-table fallback")
            reason = REASON_DISPLAY_NAMES[record.reason_codes[0]]
            state_label = "× blocked by registered rule"
        else:
            reason = ""
            state_label = "○ no registered rule blocked"
        axis.text(
            0.59,
            y + 0.27,
            state_label,
            fontsize=6.2,
            color=edge,
            fontweight="bold",
            va="center",
        )
        axis.text(
            0.59,
            y + 0.53,
            reason,
            fontsize=5.5,
            color=_MUTED,
            va="center",
        )
    return figure


def _render_registered_checks(profile: ArtifactAuditVisualizationDataV1):
    records_by_artifact = {}
    for record in profile.check_records:
        records_by_artifact.setdefault(record.artifact_display_id, {})[
            record.method_id
        ] = record
    artifacts = list(records_by_artifact)
    methods = [
        method
        for method in _CHECK_DISPLAY_ORDER
        if method in {record.method_id for record in profile.check_records}
    ]
    height = max(5.2, 3.1 + 0.42 * len(artifacts))
    figure = _base(
        _COMPONENT_METADATA[REGISTERED_CHECKS_COMPONENT_REF][1],
        (
            f"Candidate artifacts: {len(artifacts)} × registered checks: {len(methods)} · "
            "every cell has an explicit state"
        ),
        height,
        _TAKEAWAYS[REGISTERED_CHECKS_COMPONENT_REF],
    )
    axis = figure.add_axes((0.18, 0.19, 0.78, 0.60))
    axis.set_xlim(0, len(methods))
    axis.set_ylim(len(artifacts), 0)
    axis.set_xticks([index + 0.5 for index in range(len(methods))])
    axis.set_xticklabels(
        [textwrap.fill(CHECK_DISPLAY_NAMES[method], 18) for method in methods],
        fontsize=5.4,
        rotation=30,
        ha="left",
    )
    axis.tick_params(axis="x", top=True, labeltop=True, bottom=False, labelbottom=False)
    axis.set_yticks([index + 0.5 for index in range(len(artifacts))])
    axis.set_yticklabels(artifacts, fontsize=6.5)
    axis.tick_params(length=0, pad=4)
    symbol = {
        RegisteredCheckDisplayState.NO_REGISTERED_RULE_BLOCKED: "○",
        RegisteredCheckDisplayState.BLOCKED_BY_REGISTERED_RULE: "×",
        RegisteredCheckDisplayState.NOT_APPLICABLE: "—",
    }
    for y, artifact in enumerate(artifacts):
        for x, method in enumerate(methods):
            record = records_by_artifact[artifact][method]
            fill, edge = _STATES[record.check_state.value]
            axis.add_patch(
                Rectangle(
                    (x + 0.07, y + 0.09),
                    0.86,
                    0.82,
                    facecolor=fill,
                    edgecolor=edge,
                    linewidth=0.7,
                )
            )
            axis.text(
                x + 0.5,
                y + 0.5,
                symbol[record.check_state],
                ha="center",
                va="center",
                fontsize=8.4,
                color=edge,
                fontweight=(
                    "bold"
                    if record.check_state
                    is RegisteredCheckDisplayState.BLOCKED_BY_REGISTERED_RULE
                    else "normal"
                ),
            )
    for spine in axis.spines.values():
        spine.set_visible(False)
    figure.text(
        0.18,
        0.105,
        "○ no registered block   × blocked   — not applicable",
        fontsize=6.4,
        color=_MUTED,
    )
    return figure


def _base(title: str, subtitle: str, height: float, footnote: str):
    figure = plt.figure(figsize=(_WIDTH, height), facecolor=_BACKGROUND)
    figure.text(
        0.045,
        0.962,
        title,
        fontsize=11.0,
        fontweight="bold",
        color=_TEXT,
        va="top",
    )
    figure.text(0.045, 0.917, subtitle, fontsize=7.0, color=_MUTED, va="top")
    figure.text(
        0.045,
        0.025,
        textwrap.fill(footnote, 112),
        fontsize=6.0,
        color=_MUTED,
        va="bottom",
        linespacing=1.15,
    )
    return figure


def _fallback_figure(component: _Component, reason: str):
    figure = _base(
        component.title,
        "The complete typed table is retained without truncation.",
        4.7,
        (
            f"{reason}. No top-N selection or silent omission was applied to the "
            "static figure."
        ),
    )
    axis = figure.add_axes((0.07, 0.22, 0.86, 0.48))
    axis.axis("off")
    axis.text(
        0,
        0.62,
        "This bounded static view cannot show every record legibly.\n"
        "Use the complete TSV table for the full candidate.",
        fontsize=9.0,
        color=_TEXT,
        fontweight="bold",
    )
    return figure


def _visualization_contract(
    *,
    profile,
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
    ) or [EvidenceState.INFERRED]
    missing_reasons = [render_reason] if render_reason else []
    applicability = "partially_applicable" if render_reason else "applicable"
    alt_text, long_description = _accessibility_text(profile, component.ref)
    binding = VisualizationDataBinding(
        artifact_id=data_artifact.artifact_id,
        schema_ref=PUBLIC_SAFE_EXPORT_VISUALIZATION_DATA_SCHEMA_REF,
        object_version="0.1.0",
        sha256=data_artifact.sha256,
        records_path=component.records_path,
        record_lookup_key="record_id",
        evidence_ids_field="evidence_ids",
        value_field="display_state",
        evidence_state_field="evidence_state",
        scientific_status_field="scientific_status",
        missingness_field="missingness",
        applicability_field="applicability",
    )
    return VisualizationArtifactV2(
        visualization_id=_p011_visualization_id(
            run_id.removeprefix("run-"), component.slug
        ),
        component_id=component.ref.split("@", 1)[0],
        component_version=component.ref.split("@", 1)[1],
        data_binding=binding,
        producer_tool_id="P0-11",
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
    )


def _accessibility_text(profile, ref: str) -> tuple[str, str]:
    if ref == REPORT_FIELD_PROJECTION_COMPONENT_REF:
        counts = {
            state: sum(
                record.projection_state is state for record in profile.field_records
            )
            for state in FieldProjectionState
        }
        summary = (
            f"Claims: {profile.claim_count}; fields: "
            f"{counts[FieldProjectionState.INCLUDED]} retained, "
            f"{counts[FieldProjectionState.OMITTED_BY_POLICY]} policy-omitted, "
            f"{counts[FieldProjectionState.NOT_APPLICABLE_IN_SOURCE]} no source "
            "value. Values hidden; retention is not wording/scientific approval."
        )
    elif ref == LOCAL_EXPORT_STATE_COMPONENT_REF:
        hash_state = (
            "matching candidate hash supplied"
            if profile.candidate_hash_state.value
            == "matching_candidate_hash_supplied"
            else "awaiting matching candidate hash"
        )
        summary = (
            f"Five-step local export ledger; {hash_state}; network upload is "
            "not performed by this tool. Hash matching does not authenticate a "
            "reviewer or approve publication."
        )
    elif ref == ARTIFACT_STATUS_COMPONENT_REF:
        blocked = sum(
            record.audit_state
            is ArtifactDisplayState.BLOCKED_BY_REGISTERED_RULE
            for record in profile.artifact_records
        )
        summary = (
            f"Candidate artifact count: {profile.artifact_count}; {blocked} with a "
            "registered blocking finding. No-block applies only to registered "
            "checks and is not a privacy, safety or publication decision."
        )
    else:
        counts = {
            state: sum(
                record.check_state is state for record in profile.check_records
            )
            for state in RegisteredCheckDisplayState
        }
        summary = (
            f"Candidate artifact count: {profile.artifact_count}; registered "
            f"check count: {profile.registered_method_count}; cells: "
            f"{counts[RegisteredCheckDisplayState.BLOCKED_BY_REGISTERED_RULE]} "
            "blocked, "
            f"{counts[RegisteredCheckDisplayState.NO_REGISTERED_RULE_BLOCKED]} "
            "no registered block, and "
            f"{counts[RegisteredCheckDisplayState.NOT_APPLICABLE]} not applicable. "
            "No-block is limited to the listed checks."
        )
    alt_text = f"{_COMPONENT_METADATA[ref][1]}. {summary}"
    long_description = (
        f"{alt_text} {_TAKEAWAYS[ref]} The complete typed TSV preserves every "
        "record, evidence binding and exact display state."
    )
    return alt_text, long_description


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
            else:
                metadata.update(
                    {"CreationDate": None, "ModDate": None, "Producer": "BRIDGE"}
                )
                figure.savefig(buffer, format="pdf", metadata=metadata)
                payload = buffer.getvalue()
            if extension == "png":
                payload = buffer.getvalue()
            outputs[extension] = (media_type, payload)
    finally:
        plt.close(figure)
    return outputs


def _sanitize_svg(payload: bytes) -> bytes:
    text = payload.decode("utf-8")
    text = re.sub(r"<!DOCTYPE[^>]*>\s*", "", text, count=1, flags=re.DOTALL)
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


def _config_hash(ref: str) -> str:
    payload = canonical_json_bytes(
        {
            "component_ref": ref,
            "renderer": [_RENDERER_ID, _RENDERER_VERSION, _EXPORT_PROFILE_ID],
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "matplotlib_version": matplotlib.__version__,
            "matplotlib_rc": _RC,
            "font_family": "DejaVu Sans",
            "colors": _STATES,
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
        artifact_id=_p011_artifact_id(run_id.removeprefix("run-"), suffix),
        kind=kind,
        path=path,
        media_type=media_type,
        sha256=hashlib.sha256(payload).hexdigest(),
        evidence_ids=evidence_ids,
    )
