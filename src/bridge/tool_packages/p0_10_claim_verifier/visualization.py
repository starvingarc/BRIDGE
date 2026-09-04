from __future__ import annotations

import csv
import hashlib
import json
import sys
import textwrap
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle
from matplotlib.text import Text

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_10_claim_verifier.visualization_data import (
    CLAIM_CHECK_MATRIX_COMPONENT_REF,
    CLAIM_VERIFIER_VISUALIZATION_DATA_SCHEMA_REF,
    FINDING_CONTEXT_COMPONENT_REF,
    NUMERIC_CORRESPONDENCE_COMPONENT_REF,
    P010_COMPONENT_BINDINGS,
    ClaimCheckCategory,
    ClaimVerifierVisualizationDataV1,
    FindingState,
    P010VisualizationArtifactSet,
    ReportCheckDimension,
    _p010_artifact_id,
    _p010_visualization_id,
)
from bridge.toolkit.contracts import ArtifactManifest, EvidenceState
from bridge.toolkit.visualization import (
    FigureRegistry,
    VisualizationAccessibility,
    VisualizationArtifactV2,
    VisualizationDataBinding,
    VisualizationRenderBinding,
)


_RENDERER_ID = "bridge.matplotlib.claim-verifier"
_RENDERER_VERSION = "0.1.0"
_EXPORT_PROFILE_ID = "bridge-static-scientific-figure-v0.1"
_FONT_RELATIVE_PATH = Path("fonts/NotoSansCJKsc-VF.ttf")
_FONT_FAMILY = "Noto Sans CJK SC"
_FONT_SHA256 = "990c807e79c25662a5a9ecf7f971baeb2bf2eab9a559e5ecf15cdfdb8561d21f"
_WIDTH = 180.3 / 25.4
_BACKGROUND = "#FFFFFF"
_TEXT = "#25353C"
_MUTED = "#66767D"
_ROW = "#F7F9F9"
_COLORS = {
    FindingState.NO_FINDING.value: ("#EEF1F2", "#42545C"),
    FindingState.WARNING.value: ("#F5E7BE", "#684F18"),
    FindingState.REVIEW_REQUIRED.value: ("#E4D8EE", "#543C68"),
    FindingState.BLOCKED.value: ("#F0D1CB", "#74372F"),
    "exact_identity_under_current_rules": ("#DCE9F2", "#2F556A"),
    "source_not_cited_numeric_not_assessed": ("#E6E8E9", "#46545B"),
    "source_numeric_unavailable": ("#E6E8E9", "#46545B"),
    "canonical_numeric_mismatch": ("#F0D1CB", "#74372F"),
    "unit_mismatch": ("#F0D1CB", "#74372F"),
    "rendered_numeric_mismatch": ("#F0D1CB", "#74372F"),
    "numeric_source_not_scalar": ("#E4D8EE", "#543C68"),
}
_RC = {
    "font.family": ["sans-serif"],
    "pdf.fonttype": 42,
    "svg.fonttype": "path",
    "svg.hashsalt": "BRIDGE-P0-10",
    "axes.linewidth": 0.6,
}


class VisualizationFontUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class _FontBinding:
    properties: FontProperties
    family: str
    sha256: str


@dataclass(frozen=True)
class PreparedClaimVerifierVisualizations:
    payloads: dict[str, bytes]
    artifacts: tuple[ArtifactManifest, ...]


@dataclass(frozen=True)
class _Component:
    ref: str
    slug: str
    records_path: str
    table_name: str
    title: str
    limit: int


_COMPONENT_METADATA = {
    CLAIM_CHECK_MATRIX_COMPONENT_REF: (
        "claim_verifier_claim_check_matrix.tsv",
        "Report and statement checks under the current rules",
        25,
    ),
    NUMERIC_CORRESPONDENCE_COMPONENT_REF: (
        "claim_verifier_numeric_correspondence.tsv",
        "Correspondence of reported values to cited evidence",
        30,
    ),
    FINDING_CONTEXT_COMPONENT_REF: (
        "claim_verifier_finding_context.tsv",
        "Recorded findings and their report context",
        24,
    ),
}
_COMPONENTS = tuple(
    _Component(ref, slug, records_path, *_COMPONENT_METADATA[ref])
    for ref, slug, records_path in P010_COMPONENT_BINDINGS
)
_TAKEAWAYS = {
    CLAIM_CHECK_MATRIX_COMPONENT_REF: (
        "Report cells describe successful-run eligibility preconditions; claim cells "
        "show deterministic findings in five user-facing review dimensions."
    ),
    NUMERIC_CORRESPONDENCE_COMPONENT_REF: (
        "Evidence-side canonical values and units remain paired with the exact "
        "ReportDraft binding spans without tolerance, scaling or inferred rounding."
    ),
    FINDING_CONTEXT_COMPONENT_REF: (
        "Each finding remains linked to its rule, claim and exact text span when "
        "the deterministic check identified one."
    ),
}
_LIMITATIONS = {
    CLAIM_CHECK_MATRIX_COMPONENT_REF: [
        "No finding means only that the current deterministic rules emitted no finding.",
        "Report-level cells are successful-run eligibility preconditions, not independent scientific evidence.",
        "Finding counts are audit counts, not evidence amount or a product-quality score.",
        "This matrix does not validate biological truth or authorize publication.",
    ],
    NUMERIC_CORRESPONDENCE_COMPONENT_REF: [
        "Exact identity checks value, unit and rendered span only; it does not establish scientific appropriateness.",
        "Uncited or unavailable source values remain not assessed rather than being treated as zero.",
        "The figure does not recalculate any upstream measurement.",
    ],
    FINDING_CONTEXT_COMPONENT_REF: [
        "Claim text is retained for local review and is not public-export clearance.",
        "Checks without an exact span remain claim-level findings and are not assigned a fabricated span.",
        "The absence of a finding is not a privacy, safety or release conclusion.",
    ],
}


def prepare_claim_verifier_visualizations(
    *,
    profile: ClaimVerifierVisualizationDataV1,
    output_dir: Path,
    run_id: str,
    tool_version: str,
) -> PreparedClaimVerifierVisualizations:
    if profile.producer_run_ref != f"run:{run_id}":
        raise ValueError("visualization profile does not bind the producer run")
    font = _load_font()
    final_dir = output_dir / run_id
    payloads: dict[str, bytes] = {}
    artifacts: list[ArtifactManifest] = []

    data_name = "claim_verifier_visualization_data.json"
    data_payload = canonical_json_bytes(profile.model_dump(mode="json"), indent=2)
    payloads[data_name] = data_payload
    data_artifact = _manifest(
        run_id,
        "claim-verifier-visualization-data",
        "claim_verifier_visualization_data",
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
        CLAIM_CHECK_MATRIX_COMPONENT_REF: _render_claim_matrix,
        NUMERIC_CORRESPONDENCE_COMPONENT_REF: _render_numeric_correspondence,
        FINDING_CONTEXT_COMPONENT_REF: _render_finding_context,
    }
    with matplotlib.rc_context(rc=_RC):
        for component in _COMPONENTS:
            component_evidence_ids = _component_evidence_ids(profile, component.ref)
            table_payload = _table(profile, component.ref)
            payloads[component.table_name] = table_payload
            table_artifact = _manifest(
                run_id,
                f"claim-verifier-{component.slug}-table",
                "visualization_table",
                final_dir / component.table_name,
                "text/tab-separated-values",
                table_payload,
                component_evidence_ids,
            )
            tables[component.ref] = table_artifact
            artifacts.append(table_artifact)

            records = _records(profile, component.ref)
            reason = _static_render_reason(component, records)
            render_reasons[component.ref] = reason
            figure = (
                _fallback_figure(component, reason)
                if reason is not None
                else renderers[component.ref](profile)
            )
            _apply_font(figure, font.properties)
            for extension, (media_type, render_payload) in _render_payloads(
                figure
            ).items():
                filename = f"claim_verifier_{component.slug}.{extension}"
                payloads[filename] = render_payload
                artifact = _manifest(
                    run_id,
                    f"claim-verifier-{component.slug}-{extension}",
                    "visualization_render",
                    final_dir / filename,
                    media_type,
                    render_payload,
                    component_evidence_ids,
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
            font=font,
        )
        for component in _COMPONENTS
    ]
    artifact_set = P010VisualizationArtifactSet(
        artifact_set_id=f"p0-10-visualizations:{run_id.removeprefix('run-')}",
        data_profile_artifact_id=data_artifact.artifact_id,
        data_profile_sha256=data_artifact.sha256,
        visualizations=visualizations,
    )
    artifact_set_name = "p0_10_visualization_artifact_set.json"
    artifact_set_payload = canonical_json_bytes(
        artifact_set.model_dump(mode="json"), indent=2
    )
    payloads[artifact_set_name] = artifact_set_payload
    artifacts.append(
        _manifest(
            run_id,
            "p0-10-visualization-artifact-set",
            "visualization_artifact_set",
            final_dir / artifact_set_name,
            "application/json",
            artifact_set_payload,
            profile.evidence_ids,
        )
    )
    return PreparedClaimVerifierVisualizations(payloads, tuple(artifacts))


def _load_font() -> _FontBinding:
    path = Path(sys.prefix) / _FONT_RELATIVE_PATH
    try:
        if not path.is_file() or path.is_symlink():
            raise VisualizationFontUnavailable("declared CJK font is unavailable")
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        properties = FontProperties(fname=str(path))
        family = properties.get_name()
    except (OSError, RuntimeError, ValueError) as exc:
        raise VisualizationFontUnavailable("declared CJK font is unavailable") from exc
    if digest != _FONT_SHA256 or family != _FONT_FAMILY:
        raise VisualizationFontUnavailable("declared CJK font does not match contract")
    return _FontBinding(properties=properties, family=family, sha256=digest)


def _records(profile, ref):
    if ref == CLAIM_CHECK_MATRIX_COMPONENT_REF:
        return list(profile.check_matrix_records)
    if ref == NUMERIC_CORRESPONDENCE_COMPONENT_REF:
        return list(profile.numeric_records)
    return list(profile.finding_records)


def _component_evidence_ids(
    profile: ClaimVerifierVisualizationDataV1, ref: str
) -> list[str]:
    records = _records(profile, ref)
    if not records:
        return [profile.source_result_ref]
    return sorted({item for record in records for item in record.evidence_ids})


def _static_render_reason(component: _Component, records: list) -> str | None:
    if len(records) > component.limit:
        return "static_render_requires_complete_table_fallback"
    if component.ref == FINDING_CONTEXT_COMPONENT_REF and any(
        len(textwrap.wrap(record.claim_text, 72)) > 4 for record in records
    ):
        return "static_render_requires_complete_table_fallback"
    return None


def _table(profile, ref) -> bytes:
    if ref == CLAIM_CHECK_MATRIX_COMPONENT_REF:
        rows = []
        for record in profile.check_matrix_records:
            nested_field = (
                "checks"
                if record.record_kind == "report_check_matrix"
                else "categories"
            )
            row = {
                key: value
                for key, value in record.model_dump(mode="json").items()
                if key != nested_field
            }
            for cell in getattr(record, nested_field):
                prefix = (
                    cell.dimension.value
                    if record.record_kind == "report_check_matrix"
                    else cell.category.value
                )
                row[f"{prefix}_state"] = cell.finding_state.value
                row[f"{prefix}_finding_count"] = cell.finding_count
                if record.record_kind == "claim_check_matrix":
                    row[f"{prefix}_check_ids"] = cell.check_ids
            rows.append(row)
    else:
        rows = [
            record.model_dump(mode="json")
            for record in _records(profile, ref)
        ]
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    if not fields:
        fields = _empty_table_fields(ref)
    buffer = StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=fields,
        delimiter="\t",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _table_cell(row.get(field)) for field in fields})
    return buffer.getvalue().encode()


def _empty_table_fields(ref: str) -> list[str]:
    if ref == NUMERIC_CORRESPONDENCE_COMPONENT_REF:
        return [
            "record_id",
            "claim_id",
            "binding_id",
            "source_evidence_ref",
            "source_field",
            "span_start",
            "span_end",
            "report_canonical_numeric_string",
            "report_unit",
            "evidence_canonical_numeric_string",
            "evidence_unit",
            "correspondence_state",
        ]
    return [
        "record_id",
        "claim_id",
        "check_id",
        "rule_id",
        "reason_code",
        "record_kind",
    ]


def _table_cell(value):
    if isinstance(value, (list, dict)):
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return "" if value is None else value


def _render_claim_matrix(profile: ClaimVerifierVisualizationDataV1):
    report_row = profile.check_matrix_records[0]
    rows = profile.check_matrix_records[1:]
    height = max(5.8, 3.8 + 0.42 * len(rows))
    figure = _base(
        _COMPONENTS[0].title,
        (
            f"4 report eligibility preconditions · {len(rows)} structured claims · "
            f"{profile.finding_count} finding records · no-finding is not an approval state"
        ),
        height,
        _TAKEAWAYS[CLAIM_CHECK_MATRIX_COMPONENT_REF],
    )

    report_axis = figure.add_axes((0.29, 0.70, 0.67, 0.10))
    report_axis.set_xlim(0, len(ReportCheckDimension))
    report_axis.set_ylim(1, 0)
    report_axis.set_xticks(
        [index + 0.5 for index in range(len(ReportCheckDimension))]
    )
    report_axis.set_xticklabels(
        [
            "Report schema\n+ content hash",
            "Evidence graph\nintegrity",
            "Policy\nauthority",
            "Statement registry\nauthority",
        ],
        fontsize=6.2,
    )
    report_axis.set_yticks([0.5])
    report_axis.set_yticklabels(
        ["Report eligibility\npreconditions"], fontsize=6.2
    )
    report_axis.tick_params(
        axis="x", top=True, labeltop=True, bottom=False, labelbottom=False
    )
    report_axis.tick_params(length=0, pad=4)
    for x, cell in enumerate(report_row.checks):
        fill, edge = _COLORS[cell.finding_state.value]
        report_axis.add_patch(
            Rectangle(
                (x + 0.08, 0.10),
                0.84,
                0.80,
                facecolor=fill,
                edgecolor=edge,
                linewidth=0.7,
            )
        )
        report_axis.text(
            x + 0.5,
            0.50,
            "—",
            ha="center",
            va="center",
            fontsize=7.0,
            color=edge,
        )
    for spine in report_axis.spines.values():
        spine.set_visible(False)

    axis = figure.add_axes((0.29, 0.17, 0.67, 0.43))
    categories = list(ClaimCheckCategory)
    axis.set_xlim(0, len(categories))
    axis.set_ylim(len(rows), 0)
    axis.set_xticks([index + 0.5 for index in range(len(categories))])
    axis.set_xticklabels(
        [
            "Claim structure\n+ authoring",
            "Evidence binding\n+ state",
            "Numeric value\n+ unit",
            "Comparison\nscope",
            "Wording\n+ statements",
        ],
        fontsize=6.2,
    )
    axis.tick_params(axis="x", top=True, labeltop=True, bottom=False, labelbottom=False)
    axis.set_yticks([index + 0.5 for index in range(len(rows))])
    axis.set_yticklabels(
        [
            f"{_short_ref(row.claim_ref)}\n{_label(row.claim_type)}"
            for row in rows
        ],
        fontsize=6.2,
    )
    axis.tick_params(length=0, pad=4)
    for y, row in enumerate(rows):
        for x, cell in enumerate(row.categories):
            fill, edge = _COLORS[cell.finding_state.value]
            axis.add_patch(
                Rectangle(
                    (x + 0.08, y + 0.10),
                    0.84,
                    0.80,
                    facecolor=fill,
                    edgecolor=edge,
                    linewidth=0.7,
                )
            )
            label = _finding_symbol(cell.finding_state, cell.finding_count)
            axis.text(
                x + 0.5,
                y + 0.50,
                label,
                ha="center",
                va="center",
                fontsize=7.0,
                color=edge,
                fontweight="bold" if cell.finding_count else "normal",
            )
    for spine in axis.spines.values():
        spine.set_visible(False)
    figure.text(
        0.29,
        0.105,
        "— no finding under current rules   ! warning   ? review required   "
        "× blocking; number = finding records",
        fontsize=6.4,
        color=_MUTED,
    )
    return figure


def _render_numeric_correspondence(profile: ClaimVerifierVisualizationDataV1):
    rows = profile.numeric_records
    if not rows:
        return _empty_figure(
            _COMPONENTS[1].title,
            "No numeric ValueBinding is present in this structured report.",
            "No numeric identity assessment was created; this is not a zero value.",
        )
    height = max(5.0, 2.8 + 0.76 * len(rows))
    figure = _base(
        _COMPONENTS[1].title,
        (
            f"{len(rows)} ValueBindings · Evidence canonical values are shown "
            "beside exact report spans"
        ),
        height,
        _TAKEAWAYS[NUMERIC_CORRESPONDENCE_COMPONENT_REF],
    )
    axis = figure.add_axes((0.045, 0.13, 0.91, 0.72))
    axis.set_xlim(0, 1)
    axis.set_ylim(len(rows), 0)
    axis.axis("off")
    headers = (
        (0.01, "Claim / binding"),
        (0.29, "Evidence canonical"),
        (0.54, "Report canonical + exact span"),
        (0.88, "Finding state"),
    )
    for x, label in headers:
        axis.text(x, -0.18, label, fontsize=6.6, color=_MUTED, fontweight="bold")
    for index, row in enumerate(rows):
        y = index + 0.08
        axis.add_patch(
            Rectangle(
                (0, y),
                1,
                0.82,
                facecolor=_ROW if index % 2 == 0 else _BACKGROUND,
                edgecolor="none",
            )
        )
        axis.text(
            0.01,
            y + 0.20,
            _short_ref(row.claim_ref),
            fontsize=6.5,
            color=_TEXT,
            fontweight="bold",
        )
        axis.text(
            0.01,
            y + 0.52,
            f"{_short_ref(row.binding_id)} · {row.source_field}",
            fontsize=5.9,
            color=_MUTED,
        )
        evidence_value = (
            "not available"
            if row.evidence_canonical_numeric_string is None
            else _value_unit(
                row.evidence_canonical_numeric_string,
                row.evidence_unit,
            )
        )
        axis.text(0.29, y + 0.30, evidence_value, fontsize=7.0, color=_TEXT)
        axis.text(
            0.29,
            y + 0.57,
            _short_ref(row.source_evidence_ref),
            fontsize=5.6,
            color=_MUTED,
        )
        axis.text(
            0.54,
            y + 0.22,
            _value_unit(
                row.report_canonical_numeric_string,
                row.report_unit,
            ),
            fontsize=7.0,
            color=_TEXT,
        )
        axis.text(
            0.54,
            y + 0.52,
            f"span [{row.span_start}, {row.span_end}) · “{_clip(row.report_rendered_text, 25)}”",
            fontsize=5.9,
            color=_MUTED,
        )
        fill, edge = _COLORS[row.correspondence_state.value]
        axis.add_patch(
            Rectangle(
                (0.875, y + 0.18),
                0.12,
                0.46,
                facecolor=fill,
                edgecolor=edge,
                linewidth=0.7,
            )
        )
        axis.text(
            0.935,
            y + 0.41,
            _numeric_label(row.correspondence_state.value),
            fontsize=5.5,
            color=edge,
            ha="center",
            va="center",
            wrap=True,
        )
    return figure


def _render_finding_context(profile: ClaimVerifierVisualizationDataV1):
    rows = sorted(
        profile.finding_records,
        key=lambda row: (row.claim_order, row.rule_id, row.reason_code, row.check_id),
    )
    if not rows:
        return _empty_figure(
            _COMPONENTS[2].title,
            "No finding records were emitted under the current deterministic rules.",
            "This does not establish biological validity, privacy or release suitability.",
        )
    height = max(5.2, 2.9 + 0.92 * len(rows))
    figure = _base(
        _COMPONENTS[2].title,
        f"{len(rows)} finding records · claim text remains local review context",
        height,
        _TAKEAWAYS[FINDING_CONTEXT_COMPONENT_REF],
    )
    axis = figure.add_axes((0.045, 0.13, 0.91, 0.72))
    axis.set_xlim(0, 1)
    axis.set_ylim(len(rows), 0)
    axis.axis("off")
    for index, row in enumerate(rows):
        y = index + 0.05
        fill, edge = _COLORS[row.display_state]
        axis.add_patch(
            Rectangle(
                (0, y),
                0.012,
                0.84,
                facecolor=edge,
                edgecolor="none",
            )
        )
        axis.add_patch(
            Rectangle(
                (0.014, y),
                0.986,
                0.84,
                facecolor=_ROW if index % 2 == 0 else _BACKGROUND,
                edgecolor="none",
            )
        )
        axis.text(
            0.03,
            y + 0.18,
            f"{_short_ref(row.claim_ref)} · {_label(row.outcome)}",
            fontsize=6.7,
            color=edge,
            fontweight="bold",
        )
        axis.text(
            0.03,
            y + 0.39,
            _human_label(row.reason_code),
            fontsize=6.0,
            color=_TEXT,
            fontweight="bold",
        )
        axis.text(
            0.03,
            y + 0.62,
            f"{row.reason_code} · {_short_ref(row.rule_id)}",
            fontsize=5.1,
            color=_MUTED,
        )
        if row.record_kind == "span_finding_context":
            span_text = (
                f"span [{row.span_start}, {row.span_end}) · "
                f"“{_clip(row.matched_text, 34)}”"
            )
        else:
            span_text = "no exact text span recorded"
        axis.text(0.45, y + 0.18, span_text, fontsize=6.2, color=edge)
        axis.text(
            0.45,
            y + 0.46,
            textwrap.fill(row.claim_text, 74),
            fontsize=5.7,
            color=_MUTED,
            va="top",
            linespacing=1.12,
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
    figure.text(0.045, 0.918, subtitle, fontsize=7.1, color=_MUTED, va="top")
    figure.text(
        0.045,
        0.026,
        textwrap.fill(footnote, 112),
        fontsize=6.1,
        color=_MUTED,
        va="bottom",
        linespacing=1.15,
    )
    return figure


def _empty_figure(title: str, message: str, limitation: str):
    figure = _base(
        title,
        "Records are not drawn in this static view.",
        4.7,
        limitation,
    )
    axis = figure.add_axes((0.07, 0.22, 0.86, 0.48))
    axis.axis("off")
    axis.text(
        0,
        0.62,
        message,
        fontsize=10.0,
        color=_TEXT,
        fontweight="bold",
        wrap=True,
    )
    return figure


def _fallback_figure(component: _Component, reason: str):
    return _empty_figure(
        component.title,
        "The complete typed table is retained without truncation.",
        (
            f"{reason}. No top-N selection or silent omission was applied to the "
            "static figure."
        ),
    )


def _apply_font(figure, properties: FontProperties) -> None:
    for item in figure.findobj(match=Text):
        size = item.get_fontsize()
        weight = item.get_fontweight()
        style = item.get_fontstyle()
        item.set_fontproperties(properties.copy())
        item.set_fontsize(size)
        item.set_fontweight(weight)
        item.set_fontstyle(style)


def _visualization_contract(
    *,
    profile: ClaimVerifierVisualizationDataV1,
    component: _Component,
    data_artifact: ArtifactManifest,
    table_artifact: ArtifactManifest,
    render_artifacts: dict[str, ArtifactManifest],
    run_id: str,
    tool_version: str,
    render_reason: str | None,
    font: _FontBinding,
) -> VisualizationArtifactV2:
    registry = FigureRegistry.load_default()
    registry.get(component.ref)
    records = _records(profile, component.ref)
    evidence_states = sorted(
        {record.evidence_state for record in records},
        key=lambda state: state.value,
    )
    missing_reasons = []
    applicability = "applicable"
    if component.ref == NUMERIC_CORRESPONDENCE_COMPONENT_REF and not records:
        evidence_states = [EvidenceState.UNAVAILABLE]
        missing_reasons.append("no_numeric_bindings_in_report")
        applicability = "not_assessed"
    elif not evidence_states:
        evidence_states = [EvidenceState.INFERRED]
    if {EvidenceState.UNKNOWN, EvidenceState.UNAVAILABLE} & set(evidence_states):
        missing_reasons.append("records_include_not_assessed_or_unavailable_evidence")
        applicability = "partially_applicable"
    if render_reason is not None:
        missing_reasons.append(render_reason)
        applicability = "partially_applicable"
    binding = VisualizationDataBinding(
        artifact_id=data_artifact.artifact_id,
        schema_ref=CLAIM_VERIFIER_VISUALIZATION_DATA_SCHEMA_REF,
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
        visualization_id=_p010_visualization_id(
            run_id.removeprefix("run-"), component.slug
        ),
        component_id=component.ref.split("@", 1)[0],
        component_version=component.ref.split("@", 1)[1],
        data_binding=binding,
        producer_tool_id="P0-10",
        producer_tool_version=tool_version,
        producer_run_ref=f"run:{run_id}",
        evidence_ids=_component_evidence_ids(profile, component.ref),
        evidence_states=evidence_states,
        scientific_status="candidate",
        applicability=applicability,
        missing_reason_codes=sorted(missing_reasons),
        insight_title=component.title,
        takeaway=_TAKEAWAYS[component.ref],
        limitations=_LIMITATIONS[component.ref],
        accessibility=VisualizationAccessibility(
            alt_text=f"{component.title}. {_TAKEAWAYS[component.ref]}",
            long_description=(
                f"{component.title}. {_TAKEAWAYS[component.ref]} The complete "
                "typed table retains record IDs, evidence bindings and exact "
                "finding semantics."
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
                config_sha256=_config_hash(component.ref, font),
            )
            for extension in ("svg", "png", "pdf")
        ],
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


def _config_hash(ref: str, font: _FontBinding) -> str:
    payload = canonical_json_bytes(
        {
            "component_ref": ref,
            "renderer": [_RENDERER_ID, _RENDERER_VERSION, _EXPORT_PROFILE_ID],
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "matplotlib_version": matplotlib.__version__,
            "matplotlib_rc": _RC,
            "font_family": font.family,
            "font_sha256": font.sha256,
            "colors": _COLORS,
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
        artifact_id=_p010_artifact_id(run_id.removeprefix("run-"), suffix),
        kind=kind,
        path=path,
        media_type=media_type,
        sha256=hashlib.sha256(payload).hexdigest(),
        evidence_ids=evidence_ids,
    )


def _short_ref(value: object) -> str:
    text = str(value)
    if len(text) <= 32:
        return text
    digest = hashlib.sha256(text.encode()).hexdigest()[:8]
    return f"{text[:11]}…{text[-9:]}·{digest}"


def _clip(value: str, width: int) -> str:
    return value if len(value) <= width else f"{value[: width - 1]}…"


def _label(value: object) -> str:
    return str(getattr(value, "value", value)).replace("_", " ")


def _human_label(value: object) -> str:
    text = _label(value).replace("-", " ")
    return text[:1].upper() + text[1:]


def _finding_symbol(state: FindingState, count: int) -> str:
    if state is FindingState.NO_FINDING:
        return "—"
    prefix = {
        FindingState.WARNING: "!",
        FindingState.REVIEW_REQUIRED: "?",
        FindingState.BLOCKED: "×",
    }[state]
    return f"{prefix} {count}"


def _value_unit(value: str, unit: str | None) -> str:
    if unit is None:
        return value
    return value + unit if unit in {"%", "‰"} else f"{value} {unit}"


def _numeric_label(value: str) -> str:
    return {
        "exact_identity_under_current_rules": "exact\nidentity",
        "source_not_cited_numeric_not_assessed": "not cited\nnot assessed",
        "source_numeric_unavailable": "source\nunavailable",
        "canonical_numeric_mismatch": "value\nmismatch",
        "unit_mismatch": "unit\nmismatch",
        "rendered_numeric_mismatch": "span\nmismatch",
        "numeric_source_not_scalar": "not scalar",
    }[value]
