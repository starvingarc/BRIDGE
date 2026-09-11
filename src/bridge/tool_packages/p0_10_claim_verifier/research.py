"""Version-bound, private research delivery over the canonical evidence graph.

This module is consumed by the registered P0-10 adapter. It neither qualifies
biology nor inherits the legacy verifier's external benchmark validity.
"""
from __future__ import annotations

import csv
from datetime import datetime
import hashlib
from html import escape
from importlib.resources import files
from io import StringIO
import json
from pathlib import Path
import re
import textwrap
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from bridge.tool_packages._structured_runtime import canonical_json_bytes, read_regular_bytes
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    CaseEvidenceGraphManifest, EvidenceRecord, EvidenceRecordSet,
    contains_unsafe_reference,
)
from bridge.tool_packages.p0_09_evidence_compiler.queries import EvidenceGraphQueries
from bridge.tool_packages.p0_10_claim_verifier.models import (
    AuthoringChannel, ClaimBlock, ClaimPolicySpec, ClaimVerificationResult,
    ClaimVerifierReleaseContract, ReportDraft, StatementRegistry, ReleaseState,
    ReportAudience, PublicExportEligibility, report_content_hash,
)
from bridge.toolkit.contracts import FrozenModel

RESEARCH_RESULT_SCHEMA_REF = "bridge://schemas/research-claim-verification-result/v0.2"
RESEARCH_STATEMENT_SCHEMA_REF = "bridge://schemas/research-statement-registry/v0.2"
RESEARCH_SNAPSHOT_SCHEMA_REF = "bridge://schemas/research-analysis-snapshot/v0.2"
RESEARCH_POLICY_REF = "claim-policy:p0-10-research@0.2.0"
RESEARCH_CONTRACT_ID = "P0-10-RESEARCH-RELEASE-CONTRACT-v0.2"
RESEARCH_RENDERER_ID = "BRIDGE-RESEARCH-REPORT-RENDERER-v0.2"
RESEARCH_CONTRACT_FILENAME = "research_release_contract_v0.2.json"
APPROVED_RESEARCH_CONTRACT_SHA256 = "af41cccfdcc9810e3a73dc71bd5c18428d833d42cee68d40e09935c87baae7a3"

# Inputs are logical references, never identities or paths. Refuse active content
# even though every renderer also escapes text and never emits links.
_HOSTILE = re.compile(
    r"<[^>]*>|(?<![A-Za-z0-9_-])(?:https?|javascript|data|file):|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"
    r"|(?:password|passwd|secret|token|api[_-]?key)\s*[:=]",
    re.IGNORECASE,
)
_STATE_ZH = {
    "measured": "实测", "inferred": "推断", "prior_only": "仅先验",
    "negative": "阴性证据", "missing": "缺失", "unknown": "未知",
    "unavailable": "不可用", "alert": "警示",
}


class ResearchStatementRegistry(StatementRegistry):
    object_version: Literal["0.2.0"] = "0.2.0"
    registry_id: Literal["BRIDGE-RESEARCH-STATEMENT-REGISTRY-v0.2"]
    registry_version: Literal["0.2.0"]


class ResearchReleaseContract(ClaimVerifierReleaseContract):
    contract_id: Literal["P0-10-RESEARCH-RELEASE-CONTRACT-v0.2"]
    contract_version: Literal["0.2.0"]
    renderer_id: Literal["BRIDGE-RESEARCH-REPORT-RENDERER-v0.2"]
    renderer_version: Literal["0.2.0"]
    measurement_language: Literal["zh"]
    statement_registry: ResearchStatementRegistry


class ResearchClaimVerificationResult(ClaimVerificationResult):
    object_version: Literal["0.2.0"]
    verifier_version: Literal["0.2.0"]
    benchmark_id: None = None
    benchmark_sha256: None = None
    scientific_validation: Literal["not_qualified"] = "not_qualified"
    release_contract_id: Literal["P0-10-RESEARCH-RELEASE-CONTRACT-v0.2"]
    release_contract_sha256: Literal["af41cccfdcc9810e3a73dc71bd5c18428d833d42cee68d40e09935c87baae7a3"]
    report_audience: Literal[ReportAudience.INTERNAL_RESEARCH]
    claim_policy_ref: Literal["claim-policy:p0-10-research@0.2.0"]
    statement_registry_ref: Literal["BRIDGE-RESEARCH-STATEMENT-REGISTRY-v0.2@0.2.0"]
    public_export_eligibility: Literal[PublicExportEligibility.INELIGIBLE]
    snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _safe_content(value: Any) -> None:
    if contains_unsafe_reference(value):
        raise ValueError("unsafe_research_content")
    if isinstance(value, str):
        if _HOSTILE.search(value) or any(ord(c) < 32 and c not in "\t\n\r" for c in value):
            raise ValueError("unsafe_research_content")
    elif isinstance(value, dict):
        for key, item in value.items():
            _safe_content(key)
            _safe_content(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _safe_content(item)


class ResearchAnalysisSnapshot(FrozenModel):
    """Immutable canonical JSON strings retain source types and exact values."""

    object_version: Literal["0.2.0"] = "0.2.0"
    renderer_id: Literal["BRIDGE-RESEARCH-REPORT-RENDERER-v0.2"] = RESEARCH_RENDERER_ID
    release_contract_sha256: Literal["af41cccfdcc9810e3a73dc71bd5c18428d833d42cee68d40e09935c87baae7a3"]
    audience: Literal["internal_research"] = "internal_research"
    scientific_validation: Literal["not_qualified"] = "not_qualified"
    domain_score: None = None
    input_revision: str = Field(pattern=r"^[A-Za-z0-9._:-]+$")
    graph_id: str
    graph_version: int = Field(ge=1)
    graph_manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    report_content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    graph_manifest_json: str
    source_evidence_record_set_json: str
    evidence_requirement_set_json: str
    reconciliation_record_set_json: str
    report_draft_json: str
    snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def bound_snapshot(self) -> Self:
        payload = self.model_dump(mode="json")
        payload.pop("snapshot_sha256")
        if self.snapshot_sha256 != _digest(payload):
            raise ValueError("snapshot_digest_mismatch")
        for key in ("graph_manifest_json", "source_evidence_record_set_json",
                    "evidence_requirement_set_json", "reconciliation_record_set_json", "report_draft_json"):
            _safe_content(json.loads(getattr(self, key)))
        manifest = CaseEvidenceGraphManifest.model_validate_json(self.graph_manifest_json)
        if hashlib.sha256(self.graph_manifest_json.encode("utf-8")).hexdigest() != self.graph_manifest_sha256:
            raise ValueError("snapshot_manifest_hash_mismatch")
        for artifact, raw in (
            (manifest.evidence_records, self.source_evidence_record_set_json),
            (manifest.evidence_requirements, self.evidence_requirement_set_json),
            (manifest.reconciliation_records, self.reconciliation_record_set_json),
        ):
            if hashlib.sha256(raw.encode("utf-8")).hexdigest() != artifact.sha256:
                raise ValueError("snapshot_source_hash_mismatch")
        record_set = EvidenceRecordSet.model_validate_json(self.source_evidence_record_set_json)
        if record_set.graph_id != self.graph_id or record_set.graph_version != self.graph_version:
            raise ValueError("snapshot_record_set_mismatch")
        draft = ReportDraft.model_validate_json(self.report_draft_json)
        if draft.evidence_record_set_ref != f"{record_set.record_set_id}@{record_set.record_set_version}":
            raise ValueError("snapshot_record_set_mismatch")
        records = json.loads(self.source_evidence_records_json)
        for record in records:
            parsed = EvidenceRecord.model_validate(record)
            if parsed.product_case_ref != manifest.product_case_ref:
                raise ValueError("snapshot_case_mismatch")
        if (manifest.graph_id != self.graph_id or manifest.graph_version != self.graph_version
                or draft.report_version != self.input_revision
                or draft.content_hash != self.report_content_hash):
            raise ValueError("snapshot_binding_mismatch")
        return self

    @property
    def source_evidence_records_json(self) -> str:
        return _json(json.loads(self.source_evidence_record_set_json)["records"])

    @property
    def missing_requirements_json(self) -> str:
        return _json(json.loads(self.evidence_requirement_set_json)["requirements"])

    @property
    def reconciliation_records_json(self) -> str:
        return _json(json.loads(self.reconciliation_record_set_json)["records"])


def research_release_contract_bytes() -> bytes:
    payload = files("bridge.tool_packages.p0_10_claim_verifier.resources").joinpath(
        RESEARCH_CONTRACT_FILENAME).read_bytes()
    if hashlib.sha256(payload).hexdigest() != APPROVED_RESEARCH_CONTRACT_SHA256:
        raise ValueError("research_release_contract_invalid")
    return payload


def load_research_release_contract() -> ResearchReleaseContract:
    return ResearchReleaseContract.model_validate_json(research_release_contract_bytes())


def _json(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def _report_id(manifest_sha256: str, input_revision: str) -> str:
    return "report:research-" + _digest([manifest_sha256, input_revision])[:24]


def research_record_claim(record: EvidenceRecord) -> ClaimBlock:
    # Reuse the numeric normalization checked by the original verifier. The raw
    # source JSON remains in the snapshot; display normalization is never raw data.
    from bridge.tool_packages.p0_10_claim_verifier.verifier import _canonical_decimal, _join_numeric_unit

    text = f"{record.metric_id}；状态={_STATE_ZH[record.evidence_state.value]}（{record.evidence_state.value}）；关系={record.relation.value}"
    bindings = []
    numeric_fields = [
        ("value", record.value, record.unit, "值"),
        ("numerator", record.numerator, None, "分子"),
        ("denominator", record.denominator, None, "分母"),
        ("interval_lower", None if record.interval is None else record.interval.lower, record.unit, "区间下界"),
        ("interval_upper", None if record.interval is None else record.interval.upper, record.unit, "区间上界"),
    ]
    for field, value, unit, label in numeric_fields:
        text += f"；{label}="
        if value is None:
            text += "未提供"
            continue
        canonical = _canonical_decimal(value)
        if canonical is None or isinstance(value, bool):
            raise ValueError("unsupported_research_numeric_value")
        rendered = _join_numeric_unit(canonical, unit)
        start = len(text)
        text += rendered
        bindings.append({
            "binding_id": f"binding:{record.evidence_id.removeprefix('evidence:')}:{field}",
            "source_evidence_ref": record.ref, "source_field": field,
            "canonical_numeric_string": canonical, "raw_unit": unit,
            "text_span": [start, len(text)],
        })
    text += "。"
    _safe_content(text)
    return ClaimBlock(
        claim_id="claim-block:" + record.evidence_id.removeprefix("evidence:"),
        claim_version="0.2.0", claim_ref=record.claim_ref.ref,
        product_case_ref=record.product_case_ref.ref,
        claim_type="measurement_claim" if record.value is not None else "availability_claim",
        text=text, language="zh", evidence_refs=[record.ref], value_bindings=bindings,
        reported_evidence_state=record.evidence_state, authoring_channel="deterministic_renderer",
    )


def _make_draft(*, manifest: CaseEvidenceGraphManifest, manifest_sha256: str,
                evidence_set: EvidenceRecordSet, input_revision: str, created_at: Any) -> ReportDraft:
    contract = load_research_release_contract()
    blocks = [
        research_record_claim(record) for record in evidence_set.records
        if record.lifecycle_state.value == "active" and record.applicability.value == "applicable"
    ]
    statement = contract.statement_registry.statements[0]
    blocks.append(ClaimBlock(
        claim_id="claim-block:research-boundary", claim_version="0.2.0",
        claim_ref="claim:research-boundary@0.2.0", product_case_ref=manifest.product_case_ref.ref,
        claim_type="policy_or_boundary_statement", text=statement.texts["zh"],
        language="zh", statement_refs=[statement.ref], authoring_channel="deterministic_renderer",
    ))
    payload = dict(
        object_version="0.1.0", report_id=_report_id(manifest_sha256, input_revision),
        report_version=input_revision, audience="internal_research", language="zh",
        evidence_record_set_ref=f"{evidence_set.record_set_id}@{evidence_set.record_set_version}",
        claim_policy_ref=contract.claim_policy.ref, statement_registry_ref=contract.statement_registry.ref,
        claim_blocks=[b.model_dump(mode="json") for b in blocks], renderer_id=contract.renderer_id,
        renderer_version=contract.renderer_version, authoring_channel="deterministic_renderer",
        created_at=created_at.isoformat() if isinstance(created_at, datetime) else created_at,
    )
    # Normalize timestamp before hashing, as ReportDraft serializes UTC as Z.
    if isinstance(payload["created_at"], str):
        payload["created_at"] = payload["created_at"].replace("+00:00", "Z")
    payload["content_hash"] = report_content_hash(payload)
    return ReportDraft.model_validate(payload)


def _read_graph(graph_manifest_path: Path):
    manifest_raw = read_regular_bytes(graph_manifest_path)
    graph = EvidenceGraphQueries.open(graph_manifest_path)
    manifest = CaseEvidenceGraphManifest.model_validate_json(manifest_raw)
    manifest_sha256 = hashlib.sha256(manifest_raw).hexdigest()
    # Guard the interval between canonical validation and attachment reads.
    payloads = {}
    for name in ("evidence_records", "evidence_requirements", "reconciliation_records",
                 "graph_nodes", "graph_edges"):
        artifact = getattr(manifest, name)
        raw = read_regular_bytes(graph_manifest_path.parent / artifact.filename)
        if hashlib.sha256(raw).hexdigest() != artifact.sha256:
            raise ValueError("graph_changed_during_snapshot")
        payloads[name] = raw
    if read_regular_bytes(graph_manifest_path) != manifest_raw:
        raise ValueError("graph_changed_during_snapshot")
    if json.loads(payloads["evidence_records"]) != graph.evidence_record_set.model_dump(mode="json"):
        raise ValueError("graph_changed_during_snapshot")
    payloads["manifest"] = manifest_raw
    return manifest, manifest_sha256, graph.evidence_record_set, payloads


def build_research_draft(*, graph_manifest_path: Path, input_revision: str,
                         created_at: datetime | str) -> ReportDraft:
    manifest, digest, evidence_set, _ = _read_graph(graph_manifest_path)
    _safe_content(evidence_set.model_dump(mode="json"))
    return _make_draft(manifest=manifest, manifest_sha256=digest,
                       evidence_set=evidence_set, input_revision=input_revision, created_at=created_at)


def build_research_snapshot(*, graph_manifest_path: Path, report: ReportDraft) -> ResearchAnalysisSnapshot:
    manifest, digest, evidence_set, backing = _read_graph(graph_manifest_path)
    payload = dict(
        object_version="0.2.0", renderer_id=RESEARCH_RENDERER_ID,
        release_contract_sha256=APPROVED_RESEARCH_CONTRACT_SHA256,
        audience="internal_research", scientific_validation="not_qualified", domain_score=None,
        input_revision=report.report_version, graph_id=manifest.graph_id, graph_version=manifest.graph_version,
        graph_manifest_sha256=digest, report_content_hash=report.content_hash,
        graph_manifest_json=backing["manifest"].decode("utf-8"),
        source_evidence_record_set_json=backing["evidence_records"].decode("utf-8"),
        evidence_requirement_set_json=backing["evidence_requirements"].decode("utf-8"),
        reconciliation_record_set_json=backing["reconciliation_records"].decode("utf-8"),
        report_draft_json=_json(report.model_dump(mode="json")),
    )
    payload["snapshot_sha256"] = _digest(payload)
    return ResearchAnalysisSnapshot.model_validate(payload)


def research_draft_matches_graph(report: ReportDraft, snapshot: ResearchAnalysisSnapshot) -> bool:
    # Full equality ensures omitted opposing evidence, altered/missing bindings,
    # unversioned interpretations and omitted boundaries cannot verify.
    manifest = CaseEvidenceGraphManifest.model_validate_json(snapshot.graph_manifest_json)
    records = [EvidenceRecord.model_validate(r) for r in json.loads(snapshot.source_evidence_records_json)]
    # Build expected claims without inventing a parallel graph representation.
    expected = [research_record_claim(r) for r in records
                if r.lifecycle_state.value == "active" and r.applicability.value == "applicable"]
    statement = load_research_release_contract().statement_registry.statements[0]
    expected.append(ClaimBlock(
        claim_id="claim-block:research-boundary", claim_version="0.2.0",
        claim_ref="claim:research-boundary@0.2.0", product_case_ref=manifest.product_case_ref.ref,
        claim_type="policy_or_boundary_statement", text=statement.texts["zh"], language="zh",
        statement_refs=[statement.ref], authoring_channel="deterministic_renderer",
    ))
    return (
        report.report_id == _report_id(snapshot.graph_manifest_sha256, snapshot.input_revision)
        and report.audience is ReportAudience.INTERNAL_RESEARCH
        and report.language.value == "zh"
        and report.authoring_channel is AuthoringChannel.DETERMINISTIC_RENDERER
        and report.renderer_id == RESEARCH_RENDERER_ID and report.renderer_version == "0.2.0"
        and report.claim_blocks == expected
    )


def _csv_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def render_research_snapshot(*, snapshot: ResearchAnalysisSnapshot,
                             result: ResearchClaimVerificationResult) -> dict[str, bytes]:
    # Revalidation also rejects callers using Pydantic model_copy/model_construct
    # to circumvent frozen model validators.
    snapshot = ResearchAnalysisSnapshot.model_validate(snapshot.model_dump(mode="json"))
    result = ResearchClaimVerificationResult.model_validate(result.model_dump(mode="json"))
    draft = ReportDraft.model_validate_json(snapshot.report_draft_json)
    if (
        result.release_state not in {ReleaseState.VERIFIED, ReleaseState.VERIFIED_WITH_WARNINGS}
        or not result.matches_report_draft(draft)
        or result.snapshot_sha256 != snapshot.snapshot_sha256
        or result.evidence_graph_id != snapshot.graph_id
        or result.evidence_graph_version != snapshot.graph_version
        or result.evidence_graph_manifest_sha256 != snapshot.graph_manifest_sha256
        or not research_draft_matches_graph(draft, snapshot)
    ):
        raise ValueError("unverified_or_mismatched_research_snapshot")
    records = json.loads(snapshot.source_evidence_records_json)
    payload = snapshot.model_dump(mode="json")
    rows = []
    for record in records:
        row = {field: record.get(field) for field in (
            "evidence_id", "evidence_version", "metric_id", "value", "numerator", "denominator",
            "unit", "evidence_state", "relation", "lifecycle_state", "evidence_tier",
        )}
        row["row_type"] = "evidence"
        row["source_json"] = _json(record)
        rows.append(row)
    for row_type, raw in (("missing_requirement", snapshot.missing_requirements_json),
                          ("reconciliation", snapshot.reconciliation_records_json)):
        for item in json.loads(raw):
            rows.append({"row_type": row_type, "source_json": _json(item)})
    if not rows:
        rows.append({"row_type": "metadata"})
    for row in rows:
        row.update(snapshot_sha256=snapshot.snapshot_sha256, graph_id=snapshot.graph_id,
                   graph_version=snapshot.graph_version, graph_manifest_sha256=snapshot.graph_manifest_sha256,
                   input_revision=snapshot.input_revision, report_content_hash=snapshot.report_content_hash)
    fields = ["row_type", "evidence_id", "evidence_version", "metric_id", "value", "numerator", "denominator",
              "unit", "evidence_state", "relation", "lifecycle_state", "evidence_tier", "source_json",
              "snapshot_sha256", "graph_id", "graph_version", "graph_manifest_sha256",
              "input_revision", "report_content_hash"]
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows({k: _csv_cell(v) for k, v in row.items()} for row in rows)
    paragraphs = "".join("<p>" + escape(block.text) + "</p>" for block in draft.claim_blocks)
    metadata = (
        f"快照 SHA-256：{snapshot.snapshot_sha256} | 图：{snapshot.graph_id}@{snapshot.graph_version}"
        f" | 图清单 SHA-256：{snapshot.graph_manifest_sha256} | 输入修订：{snapshot.input_revision}"
        f" | 报告 SHA-256：{snapshot.report_content_hash}"
    )
    # Exact source records and missing/opposing provenance remain separately
    # inspectable in every full report; no fabricated bar widths or summaries.
    sections = "".join("<h2>" + title + "</h2><pre>" + escape(json.dumps(json.loads(value),
        ensure_ascii=False, sort_keys=True, indent=2)) + "</pre>" for title, value in (
        ("原始证据与相反证据", snapshot.source_evidence_records_json),
        ("缺失证据要求", snapshot.missing_requirements_json),
        ("协调记录（不等于候选解释验证）", snapshot.reconciliation_records_json),
    ))
    html = (
        '<!doctype html><html lang="zh"><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
        '<title>内部研究证据报告</title><style>body{font-family:serif;margin:2em;line-height:1.6}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere}p{overflow-wrap:anywhere}'
        '@media print{body{margin:0}h2{break-after:avoid}}</style>'
        '<body><h1>内部研究证据报告</h1><p>' + escape(metadata) + "</p>"
        + paragraphs + sections + "</body></html>"
    )
    svg_lines = [metadata, *[block.text for block in draft.claim_blocks],
                 "完整来源、缺失要求与协调记录见同一快照 JSON；未验证候选解释不得作为已验证结论。"]
    # SVG consists only of text, metadata and a root; no foreignObject, links,
    # scripts, animation, external fonts, images or computed evidence geometry.
    svg_lines = [part for line in svg_lines for part in textwrap.wrap(line, width=90, break_long_words=True)]
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="' + str(60 + 32 * len(svg_lines)) + '">'
    svg += "<metadata>" + escape(_json(payload)) + "</metadata>"
    svg += "".join(f'<text x="16" y="{32 + i * 32}" font-size="14">' + escape(line) + "</text>"
                   for i, line in enumerate(svg_lines))
    svg += "</svg>"
    return {
        "research_report.html": html.encode("utf-8"),
        "research_report.json": canonical_json_bytes(payload, indent=2),
        "research_report.csv": stream.getvalue().encode("utf-8"),
        "research_report.svg": svg.encode("utf-8"),
    }
