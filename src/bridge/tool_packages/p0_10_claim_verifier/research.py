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
from typing import Annotated, Any, Literal, Self

from pydantic import Field, model_validator

from bridge.tool_packages._structured_runtime import canonical_json_bytes, read_regular_bytes
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    CaseEvidenceGraphManifest, EvidenceRecord, EvidenceRecordSet,
    contains_unsafe_reference, VersionedObjectRef,
)
from bridge.tool_packages.p0_10_claim_verifier.models import (
    AuthoringChannel, ClaimBlock, ClaimPolicySpec, ClaimVerificationResult,
    ClaimVerifierReleaseContract, ReportDraft, StatementRegistry, ReleaseState,
    ReportAudience, PublicExportEligibility, report_content_hash,
)
from bridge.toolkit.contracts import FrozenModel, DataViewBinding

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


RESEARCH_CONTEXT_SCHEMA_REF = "bridge://schemas/research-report-context/v0.3"
RESEARCH_CONTEXT_SNAPSHOT_SCHEMA_REF = "bridge://schemas/research-analysis-snapshot/v0.3"


class ResearchProductFacts(FrozenModel):
    # Explicit allowlist: no protocol bodies, filenames, paths or free metadata.
    product_name: str | None = Field(default=None, max_length=160)
    product_family: str = "unknown"
    starting_cell_type: str | None = None
    cell_line: str | None = None
    culture_day: int | None = Field(default=None, ge=0, strict=True)
    sequencing_method: str | None = None
    protocol_name: str | None = None
    target_cell_type: str | None = None
    target_stage: str | None = None
    sampling_context: str = "unknown"
    independent_cultures: int | None = Field(default=None, ge=1, strict=True)
    culture_batch_column: str | None = None
    culture_batch_role: str = "unknown"
    assay: str = "unknown"
    matrix_location: str | None = None
    count_semantics: str = "unknown"
    source_family_id: str | None = None
    sample_id_column: str | None = None
    capture_id_column: str | None = None
    gene_symbol_column: str | None = None


class ResearchContextSource(FrozenModel):
    source_ref: str
    schema_ref: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    receipt_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class ResearchExplanation(FrozenModel):
    statement: str = Field(min_length=1, max_length=600)
    evidence_aliases: list[str]
    opposing_evidence_aliases: list[str] = Field(default_factory=list)
    missing_evidence_aliases: list[str] = Field(default_factory=list)
    expected_observation: str | None = None
    competing_explanation: str
    discriminating_check: str | None

    @property
    def is_evidence_gap(self) -> bool:
        # Display classification only: no new evidence, qualification or serialized fields.
        return (not self.evidence_aliases and bool(self.missing_evidence_aliases)
                and not self.opposing_evidence_aliases and self.expected_observation is None
                and self.discriminating_check is None)


class ResearchExplanationVersion(FrozenModel):
    object_version: Literal["1.0.0"] = "1.0.0"
    scope_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    input_revision: int = Field(ge=0, strict=True)
    hypotheses: list[ResearchExplanation]
    evidence_snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    qualification: Literal["proposed_explanation"] = "proposed_explanation"
    version: int = Field(ge=1, strict=True)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    predecessor_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    created_at: str

    @model_validator(mode="after")
    def content_binding(self) -> Self:
        payload = self.model_dump(mode="json", exclude={"version", "content_sha256", "predecessor_sha256", "created_at"})
        if self.content_sha256 != _digest(payload):
            raise ValueError("report_explanation_hash_mismatch")
        return self


class BiologicalFacts(FrozenModel):
    product_family: str
    starting_cell_type: str | None
    culture_day: int | None
    target_cell_type: str | None
    target_stage: str | None
    sampling_context: str
    independent_cultures: int | None
    assay: str
    sequencing_method: str | None


class BiologicalContext(FrozenModel):
    source: Literal["confirmed_intake"]
    input_revision: int
    facts: BiologicalFacts


from bridge.toolkit.literature import LiteratureSnapshot, LiteratureUse


class ResearchExplanationV11(ResearchExplanation):
    literature_support: list[LiteratureUse] = Field(default_factory=list, max_length=3)


class ResearchExplanationVersionV11(ResearchExplanationVersion):
    object_version: Literal["1.1.0"] = "1.1.0"
    hypotheses: list[ResearchExplanationV11]
    biological_context: BiologicalContext
    literature: LiteratureSnapshot

    @model_validator(mode="after")
    def literature_binding(self):
        if self.biological_context.input_revision != self.input_revision:
            raise ValueError("explanation_background_revision_mismatch")
        read = {row.source_ref for row in self.literature.sources if row.content_level == "abstract"}
        for row in self.hypotheses:
            refs = [use.source_ref for use in row.literature_support]
            if (len(refs) != len(set(refs)) or not set(refs) <= read
                    or row.is_evidence_gap and refs):
                raise ValueError("literature_support_not_read")
        return self


from bridge.toolkit.interpretation import EvidenceRelation, FeatureCoverageSnapshot, validate_relations, validate_feature_queries, interpretation_graph, InterpretationGraphRef, current_explanation


class ResearchExplanationV12(ResearchExplanationV11):
    evidence_relations: list[EvidenceRelation] = Field(default_factory=list, max_length=24)
    feature_queries: list[str] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def relation_binding(self):
        validate_feature_queries(self.feature_queries)
        return validate_relations(self)


class ResearchExplanationVersionV12(ResearchExplanationVersion):
    object_version: Literal["1.2.0"] = "1.2.0"
    hypotheses: list[ResearchExplanationV12]
    feature_coverage: FeatureCoverageSnapshot | None
    graph_ref: InterpretationGraphRef | None
    biological_context: BiologicalContext | None = None
    literature: LiteratureSnapshot | None = None

    @model_validator(mode="after")
    def semantic_binding(self):
        if self.feature_coverage is None and any(h.feature_queries for h in self.hypotheses):
            raise ValueError("feature_query_coverage_required")
        if self.feature_coverage is not None and self.feature_coverage.input_revision != self.input_revision:
            raise ValueError("feature_coverage_revision_mismatch")
        if self.biological_context is not None and self.biological_context.input_revision != self.input_revision:
            raise ValueError("explanation_background_revision_mismatch")
        read = {r.source_ref for r in self.literature.sources if r.content_level == "abstract"} if self.literature else set()
        if any(u.source_ref not in read for h in self.hypotheses for u in h.literature_support):
            raise ValueError("literature_support_not_read")
        return self


def parse_research_explanation(value):
    model = {"1.0.0": ResearchExplanationVersion, "1.1.0": ResearchExplanationVersionV11,
             "1.2.0": ResearchExplanationVersionV12}.get(value.get("object_version"))
    if model is None:
        raise ValueError("unsupported_explanation_version")
    return model.model_validate(value)


class ResearchCandidateDevelopment(FrozenModel):
    source_ref: str
    producer_run_ref: str
    development_gate_state: Literal["passed", "failed"]
    development_reason_codes: list[str]
    development_summary_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    development_review_version: str
    development_review_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    scientific_qualification: Literal["not_established"] = "not_established"


class ResearchCompositionMapping(FrozenModel):
    source_ref: str
    measurement_ref: str
    metric_id: str
    label: str
    assignment_state: str
    count: int = Field(ge=0, strict=True)
    denominator: int = Field(gt=0, strict=True)
    fraction: float = Field(ge=0, le=1)
    interpretation: Literal["candidate_method_output_only"] = "candidate_method_output_only"

    @model_validator(mode="after")
    def ratio_binding(self) -> Self:
        expected_metric = "candidate_composition_fraction_" + _digest({"label": self.label, "assignment_state": self.assignment_state})[:16]
        if self.metric_id != expected_metric:
            raise ValueError("report_composition_label_mapping_mismatch")
        if self.count > self.denominator or abs(self.fraction - self.count / self.denominator) > 1e-12:
            raise ValueError("report_composition_ratio_mismatch")
        return self


class ResearchProcessMean(FrozenModel):
    source_ref: str
    measurement_ref: str
    metric_id: str
    method_id: str
    program_id: str
    mean: float | None
    score_unit: str
    n_observations: int = Field(gt=0, strict=True)
    assessment_state: Literal["available", "not_assessed"]
    reason_codes: list[str]
    count_semantics: Literal["selected_observations_not_independent_replicates"] = "selected_observations_not_independent_replicates"

    @model_validator(mode="after")
    def availability_binding(self) -> Self:
        expected_metric = "native_mean_" + self.method_id.lower().replace("-", "_") + "_" + self.program_id.lower()
        if self.metric_id != expected_metric:
            raise ValueError("report_process_program_mapping_mismatch")
        if (self.assessment_state == "available") != (self.mean is not None):
            raise ValueError("report_process_mean_state_mismatch")
        return self


class _ResearchReportContextContent(FrozenModel):
    object_version: Literal["0.3.0"] = "0.3.0"
    context_id: str
    audience: Literal["internal_research"] = "internal_research"
    scientific_validation: Literal["not_qualified"] = "not_qualified"
    public_export_eligibility: Literal["ineligible"] = "ineligible"
    input_revision: str
    graph_id: str
    graph_version: int = Field(ge=1)
    graph_manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    product_case_ref: VersionedObjectRef
    confirmed_product_facts: ResearchProductFacts
    facts_qualification: Literal["researcher_confirmed_not_scientific_validation"] = "researcher_confirmed_not_scientific_validation"
    intake_source_ref: str
    data_view: DataViewBinding
    data_view_source_ref: str
    sources: list[ResearchContextSource] = Field(min_length=2)
    explanation_versions: list[ResearchExplanationVersion] = Field(default_factory=list)
    explanation_qualification: Literal["unverified"] = "unverified"
    candidate_development: list[ResearchCandidateDevelopment] = Field(default_factory=list)
    composition_mapping: list[ResearchCompositionMapping] = Field(default_factory=list)
    process_means: list[ResearchProcessMean] = Field(default_factory=list)

    @model_validator(mode="after")
    def source_bindings(self) -> Self:
        payload = self.model_dump(mode="json")
        if self.object_version in {"0.4.0", "0.5.0"}:
            # Literature has its own typed identity/hash contract and is rendered inert.
            # Keep the existing private-content checks on facts and model-written prose.
            for version in payload["explanation_versions"]:
                version.pop("literature", None)
        _safe_content(payload)
        sources = {row.source_ref for row in self.sources}
        if len(sources) != len(self.sources):
            raise ValueError("duplicate_report_context_source")
        required = {self.intake_source_ref, self.data_view_source_ref}
        required.update(row.source_ref for row in [*self.candidate_development, *self.composition_mapping, *self.process_means])
        if not required <= sources:
            raise ValueError("report_context_source_missing")
        histories = {}
        for row in self.explanation_versions:
            previous = histories.get(row.scope_digest)
            if (row.version != (previous.version + 1 if previous else 1)
                    or row.predecessor_sha256 != (previous.content_sha256 if previous else None)):
                raise ValueError("report_explanation_history_broken")
            histories[row.scope_digest] = row
        identities = [row.measurement_ref for row in [*self.composition_mapping, *self.process_means]]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate_report_context_measurement")
        return self


class ResearchReportContext(_ResearchReportContextContent):
    context_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def context_binding(self) -> Self:
        if self.context_sha256 != _digest(self.model_dump(mode="json", exclude={"context_sha256"})):
            raise ValueError("report_context_hash_mismatch")
        return self


class _ResearchReportContextContentV04(_ResearchReportContextContent):
    object_version: Literal["0.4.0"] = "0.4.0"
    explanation_versions: list[Annotated[ResearchExplanationVersion | ResearchExplanationVersionV11,
        Field(discriminator="object_version")]] = Field(default_factory=list)


class ResearchReportContextV04(_ResearchReportContextContentV04):
    context_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def context_binding(self):
        if self.context_sha256 != _digest(self.model_dump(mode="json", exclude={"context_sha256"})):
            raise ValueError("report_context_hash_mismatch")
        return self


class _ResearchReportContextContentV05(_ResearchReportContextContent):
    object_version: Literal["0.5.0"] = "0.5.0"
    explanation_versions: list[Annotated[ResearchExplanationVersion | ResearchExplanationVersionV11 | ResearchExplanationVersionV12,
        Field(discriminator="object_version")]] = Field(default_factory=list)


class ResearchReportContextV05(_ResearchReportContextContentV05):
    context_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def context_binding(self):
        if self.context_sha256 != _digest(self.model_dump(mode="json", exclude={"context_sha256"})):
            raise ValueError("report_context_hash_mismatch")
        return self


RESEARCH_CONTEXT_V05_SCHEMA_REF = "bridge://schemas/research-report-context/v0.5"
RESEARCH_CONTEXT_SNAPSHOT_V05_SCHEMA_REF = "bridge://schemas/research-analysis-snapshot/v0.5"


RESEARCH_CONTEXT_V04_SCHEMA_REF = "bridge://schemas/research-report-context/v0.4"
RESEARCH_CONTEXT_SNAPSHOT_V04_SCHEMA_REF = "bridge://schemas/research-analysis-snapshot/v0.4"


def parse_research_context(value):
    if isinstance(value, str):
        value = json.loads(value)
    model = {"0.4.0": ResearchReportContextV04, "0.5.0": ResearchReportContextV05}.get(value.get("object_version"), ResearchReportContext)
    return model.model_validate(value)


def seal_research_context(payload: dict):
    content, model = ((_ResearchReportContextContentV04, ResearchReportContextV04)
        if payload.get("object_version") == "0.4.0" else (_ResearchReportContextContent, ResearchReportContext))
    if payload.get("object_version") == "0.5.0":
        content, model = _ResearchReportContextContentV05, ResearchReportContextV05
    value = content.model_validate(payload).model_dump(mode="json")
    return model.model_validate({**value, "context_sha256": _digest(value)})


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


class ResearchAnalysisSnapshotV03(ResearchAnalysisSnapshot):
    """Additive private context; the approved numeric-claim contract stays v0.2."""

    object_version: Literal["0.3.0"] = "0.3.0"
    context_renderer_id: Literal["BRIDGE-RESEARCH-CONTEXT-RENDERER-v0.3"] = "BRIDGE-RESEARCH-CONTEXT-RENDERER-v0.3"
    report_context_json: str
    context_sections_json: str
    report_context_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def bound_context(self) -> Self:
        context = parse_research_context(self.report_context_json)
        if context.object_version != self.object_version:
            raise ValueError("snapshot_context_version_mismatch")
        if self.context_sections_json != _json(_context_sections(context)):
            raise ValueError("report_context_presentation_mismatch")
        if hashlib.sha256(self.report_context_json.encode()).hexdigest() != self.report_context_sha256:
            raise ValueError("snapshot_context_hash_mismatch")
        manifest = CaseEvidenceGraphManifest.model_validate_json(self.graph_manifest_json)
        evidence = EvidenceRecordSet.model_validate_json(self.source_evidence_record_set_json)
        _check_context_graph(context, manifest, self.graph_manifest_sha256, self.input_revision, evidence)
        draft = ReportDraft.model_validate_json(self.report_draft_json)
        if draft.report_id != _report_id(self.graph_manifest_sha256, self.input_revision, context):
            raise ValueError("snapshot_context_report_mismatch")
        return self


class ResearchAnalysisSnapshotV04(ResearchAnalysisSnapshotV03):
    object_version: Literal["0.4.0"] = "0.4.0"
    context_renderer_id: Literal["BRIDGE-RESEARCH-CONTEXT-RENDERER-v0.4"] = "BRIDGE-RESEARCH-CONTEXT-RENDERER-v0.4"


class ResearchAnalysisSnapshotV05(ResearchAnalysisSnapshotV03):
    object_version: Literal["0.5.0"] = "0.5.0"
    context_renderer_id: Literal["BRIDGE-RESEARCH-CONTEXT-RENDERER-v0.5"] = "BRIDGE-RESEARCH-CONTEXT-RENDERER-v0.5"
    interpretation_graph_json: str

    @model_validator(mode="after")
    def semantic_graph_binding(self):
        context = parse_research_context(self.report_context_json)
        if self.interpretation_graph_json != _json(interpretation_graph(context)):
            raise ValueError("interpretation_graph_context_mismatch")
        return self


def research_snapshot_model(version):
    return {"0.2.0": ResearchAnalysisSnapshot, "0.3.0": ResearchAnalysisSnapshotV03,
            "0.4.0": ResearchAnalysisSnapshotV04, "0.5.0": ResearchAnalysisSnapshotV05}[version]


def active_research_records(manifest, evidence):
    """Resolve append-only history before selecting current report evidence."""
    from bridge.tool_packages.p0_09_evidence_compiler.adapter import _validate_source_record_set

    effective = _validate_source_record_set(evidence, manifest)
    return [row for row in evidence.records
            if effective[row.ref].value == "active" and row.applicability.value == "applicable"]


def _check_context_graph(context, manifest, manifest_sha256, revision, evidence):
    context = parse_research_context(context.model_dump(mode="json"))
    if (context.graph_id != manifest.graph_id or context.graph_version != manifest.graph_version
            or context.graph_manifest_sha256 != manifest_sha256
            or context.product_case_ref != manifest.product_case_ref
            or context.input_revision != revision):
        raise ValueError("report_context_graph_binding_mismatch")
    for version in context.explanation_versions:
        if version.object_version in {"1.1.0", "1.2.0"} and version.biological_context is not None and str(version.input_revision) == context.input_revision:
            expected = {key: getattr(context.confirmed_product_facts, key)
                        for key in BiologicalFacts.model_fields}
            if version.biological_context.facts.model_dump(mode="json") != expected:
                raise ValueError("report_explanation_background_mismatch")
    for version in context.explanation_versions:
        coverage = getattr(version, "feature_coverage", None)
        if coverage is not None and str(version.input_revision) == context.input_revision:
            if (coverage.upload_sha256 != context.data_view.parent_asset_sha256
                    or coverage.matrix_location != context.data_view.matrix_location):
                raise ValueError("feature_coverage_input_binding_mismatch")
    records = {}
    for row in active_research_records(manifest, evidence):
        if (context.data_view.sample_or_preparation_ref is not None
                and row.sample_or_preparation_ref.ref != context.data_view.sample_or_preparation_ref):
            raise ValueError("report_context_specimen_mismatch")
        records.setdefault(row.measurement_result_ref.ref, []).append(row)
    for item in [*context.composition_mapping, *context.process_means]:
        matching = records.get(item.measurement_ref, [])
        if not matching or any(row.metric_id != item.metric_id for row in matching):
            raise ValueError("report_context_measurement_missing")
        for row in matching:
            if isinstance(item, ResearchCompositionMapping):
                if row.value != item.fraction or row.numerator != item.count or row.denominator != item.denominator:
                    raise ValueError("report_context_composition_value_mismatch")
            elif row.value != item.mean or row.unit != item.score_unit:
                raise ValueError("report_context_process_value_mismatch")
        if isinstance(item, ResearchProcessMean) and item.n_observations != context.data_view.n_observations:
            raise ValueError("report_context_process_count_mismatch")
    return context


def _context_sections(context):
    """Everything outside numeric claims is marked by provenance and status."""
    facts = context.confirmed_product_facts
    header = "产品事实（研究者确认，不等于科学验证）：产品名称=" + (facts.product_name or "未提供")
    development = [
        ("候选开发门槛失败" if row.development_gate_state == "failed" else "候选开发门槛通过（未科学合格）")
        + "；原因=" + ("、".join(row.development_reason_codes) or "未提供")
        for row in context.candidate_development]
    return [
        (header, facts.model_dump(mode="json")),
        ("具体数据视图（细胞数不等于独立培养数）", context.data_view.model_dump(mode="json")),
        ("候选开发状态：" + ("；".join(development) or "未提供"), [r.model_dump(mode="json") for r in context.candidate_development]),
        ("版本化解释历史（解释未验证；不得作为已验证结论）", [r.model_dump(mode="json") for r in context.explanation_versions]),
        ("组成标签对应（候选方法输出，不是合格身份或产品角色）", [r.model_dump(mode="json") for r in context.composition_mapping]),
        ("过程程序均值与实际观测数（非比例分母、非独立重复数）", [r.model_dump(mode="json") for r in context.process_means]),
        ("私有上下文来源与校验和", [r.model_dump(mode="json") for r in context.sources]),
    ]


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


def _report_id(manifest_sha256: str, input_revision: str, report_context=None) -> str:
    identity = [manifest_sha256, input_revision]
    if report_context is not None:
        identity.append(report_context.context_sha256)
    return "report:research-" + _digest(identity)[:24]


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
                evidence_set: EvidenceRecordSet, input_revision: str, created_at: Any,
                report_context: ResearchReportContext | None = None) -> ReportDraft:
    contract = load_research_release_contract()
    blocks = [
        research_record_claim(record) for record in active_research_records(manifest, evidence_set)
    ]
    statement = contract.statement_registry.statements[0]
    blocks.append(ClaimBlock(
        claim_id="claim-block:research-boundary", claim_version="0.2.0",
        claim_ref="claim:research-boundary@0.2.0", product_case_ref=manifest.product_case_ref.ref,
        claim_type="policy_or_boundary_statement", text=statement.texts["zh"],
        language="zh", statement_refs=[statement.ref], authoring_channel="deterministic_renderer",
    ))
    payload = dict(
        object_version="0.1.0", report_id=_report_id(manifest_sha256, input_revision, report_context),
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
    from bridge.tool_packages.p0_09_evidence_compiler.queries import EvidenceGraphQueries

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
                         created_at: datetime | str, report_context: ResearchReportContext | None = None) -> ReportDraft:
    manifest, digest, evidence_set, _ = _read_graph(graph_manifest_path)
    _safe_content(evidence_set.model_dump(mode="json"))
    if report_context is not None:
        report_context = _check_context_graph(report_context, manifest, digest, input_revision, evidence_set)
    return _make_draft(manifest=manifest, manifest_sha256=digest,
                       evidence_set=evidence_set, input_revision=input_revision, created_at=created_at,
                       report_context=report_context)


def build_research_snapshot(*, graph_manifest_path: Path, report: ReportDraft,
                            report_context: ResearchReportContext | None = None) -> ResearchAnalysisSnapshot:
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
    model = ResearchAnalysisSnapshot
    if report_context is not None:
        report_context = _check_context_graph(report_context, manifest, digest, report.report_version, evidence_set)
        raw = _json(report_context.model_dump(mode="json"))
        payload.update(object_version="0.3.0", context_renderer_id="BRIDGE-RESEARCH-CONTEXT-RENDERER-v0.3",
                       report_context_json=raw, context_sections_json=_json(_context_sections(report_context)),
                       report_context_sha256=hashlib.sha256(raw.encode()).hexdigest())
        model = ResearchAnalysisSnapshotV03
        if report_context.object_version == "0.4.0":
            payload.update(object_version="0.4.0", context_renderer_id="BRIDGE-RESEARCH-CONTEXT-RENDERER-v0.4")
            model = ResearchAnalysisSnapshotV04
        if report_context.object_version == "0.5.0":
            payload.update(object_version="0.5.0", context_renderer_id="BRIDGE-RESEARCH-CONTEXT-RENDERER-v0.5")
            model = ResearchAnalysisSnapshotV05
            payload["interpretation_graph_json"] = _json(interpretation_graph(report_context))
    payload["snapshot_sha256"] = _digest(payload)
    return model.model_validate(payload)


def research_draft_matches_graph(report: ReportDraft, snapshot: ResearchAnalysisSnapshot) -> bool:
    # Full equality ensures omitted opposing evidence, altered/missing bindings,
    # unversioned interpretations and omitted boundaries cannot verify.
    manifest = CaseEvidenceGraphManifest.model_validate_json(snapshot.graph_manifest_json)
    evidence = EvidenceRecordSet.model_validate_json(snapshot.source_evidence_record_set_json)
    # Build expected claims without inventing a parallel graph representation.
    expected = [research_record_claim(r) for r in active_research_records(manifest, evidence)]
    statement = load_research_release_contract().statement_registry.statements[0]
    expected.append(ClaimBlock(
        claim_id="claim-block:research-boundary", claim_version="0.2.0",
        claim_ref="claim:research-boundary@0.2.0", product_case_ref=manifest.product_case_ref.ref,
        claim_type="policy_or_boundary_statement", text=statement.texts["zh"], language="zh",
        statement_refs=[statement.ref], authoring_channel="deterministic_renderer",
    ))
    return (
        report.report_id == _report_id(snapshot.graph_manifest_sha256, snapshot.input_revision,
            parse_research_context(snapshot.report_context_json)
            if isinstance(snapshot, ResearchAnalysisSnapshotV03) else None)
        and report.audience is ReportAudience.INTERNAL_RESEARCH
        and report.language.value == "zh"
        and report.authoring_channel is AuthoringChannel.DETERMINISTIC_RENDERER
        and report.renderer_id == RESEARCH_RENDERER_ID and report.renderer_version == "0.2.0"
        and report.claim_blocks == expected
    )


def _csv_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text



def _context_report_html(context, records, paragraphs, sections, metadata):
    """Readable, inert presentation of the same verified private snapshot."""
    def text(value):
        return escape("未提供" if value is None else str(value))

    def table(headers, rows):
        return ("<table><thead><tr>" + "".join("<th scope=\"col\">" + text(v) + "</th>" for v in headers)
                + "</tr></thead><tbody>" + "".join("<tr>" + "".join("<td>" + text(v) + "</td>" for v in row)
                    + "</tr>" for row in rows) + "</tbody></table>")

    def percent(value):
        if value is None:
            return "暂无数值"
        scaled = value * 100
        number = f"{scaled:.3g}" if 0 < abs(scaled) < .01 else f"{scaled:.2f}".rstrip("0").rstrip(".")
        return number + "%"

    def count(value):
        return "未提供" if value is None else f"{value:,}"

    def ratio_result(row):
        value = row.get("value")
        if value is None:
            return "暂无数值"
        result = percent(value) if row.get("unit") == "fraction" else str(value)
        n, total = row.get("numerator"), row.get("denominator")
        if n is not None and total is not None:
            result += f"（{count(n)} 个 / 共 {count(total)} 个细胞）"
        return result

    facts = context.confirmed_product_facts
    sampling = {"process_sample": "分化过程样本", "final_preparation": "最终制备物",
                "unknown": "待确认"}.get(facts.sampling_context, facts.sampling_context)
    body = '<p class="eyebrow">BRIDGE · 研究报告</p><h1>' + text(facts.product_name or "产品研究报告") + "</h1>"
    body += "<h2>样本概况</h2>"
    body += table(("项目", "信息"), [
        ("目标细胞", facts.target_cell_type), ("预期阶段", facts.target_stage),
        ("样本类型", sampling), ("实验类型", facts.assay),
        ("纳入细胞", count(context.data_view.n_observations)),
        ("独立培养次数", facts.independent_cultures)])
    if any(row.development_gate_state == "failed" for row in context.candidate_development):
        body += "<p class=\"boundary\">候选方法的开发门槛失败，细胞标签待复核。</p>"
    if context.composition_mapping:
        states = {"candidate": "候选", "unknown": "未确定", "unavailable": "不可用"}
        body += "<h2>候选细胞组成</h2>"
        body += table(("类别", "状态", "细胞数", "占比"), [
            (row.label, states.get(row.assignment_state, row.assignment_state),
             f"{count(row.count)} / 共 {count(row.denominator)}", percent(row.fraction))
            for row in context.composition_mapping])
    native = {"native_s_g2m_fraction": "S/G2M 期细胞占比",
              "candidate_assignment_fraction": "获得候选注释的细胞占比"}
    numeric = [row for row in records if row.get("metric_id") in native]
    if numeric:
        body += "<h2>主要观察</h2>"
        body += table(("指标", "结果"), [(native[row["metric_id"]], ratio_result(row)) for row in numeric])
    if context.process_means:
        methods = {"PROC-SCORE-SCANPY": "相对背景表达 · Scanpy", "PROC-SCORE-DECOUPLER": "基因集关联 · ULM"}
        programs = {"S": "S 期", "G2M": "G2/M 期", "PROC-ROS": "氧化应激",
                    "PROC-UPR": "未折叠蛋白反应", "PROC-APOPTOSIS": "凋亡相关", "PROC-HYPOXIA": "缺氧",
                    "PROC-PLURIPOTENCY": "多能性", "PROC-DISSOCIATION": "解离 / 热休克"}
        units = {"scanpy_control_adjusted_expression": "对照校正表达得分",
                 "scanpy_relative_expression_score": "相对表达分数",
                 "decoupler_ulm_t_value": "单变量线性模型 t 值"}
        body += "<h2>增殖与应激</h2><details><summary>查看测量数值与方法</summary>"
        groups = {}
        for row in context.process_means:
            groups.setdefault((row.method_id, row.score_unit), []).append(row)
        for (method, unit), rows in groups.items():
            body += "<h3>" + text(methods.get(method, "方法名称待核对")) + "</h3>"
            body += "<p class=\"measure-unit\">" + text(units.get(unit, unit)) + "</p>"
            body += table(("程序", "平均得分", "细胞数"), [
                (programs.get(row.program_id, "程序名称待核对"),
                 "暂无数值" if row.mean is None else f"{row.mean:.4g}", count(row.n_observations))
                for row in rows])
        body += "</details>"
    body += "<h2>结果解读（尚待验证）</h2>"
    version = (current_explanation(context) if context.object_version == "0.5.0"
               else context.explanation_versions[-1] if context.explanation_versions else None)
    latest = version.hypotheses if version else []
    for row in latest:
        label = "待补充证据" if row.is_evidence_gap else "解读"
        body += "<article><h3>" + label + "</h3><p>" + text(row.statement) + "</p>"
        if row.competing_explanation or row.expected_observation:
            body += "<details><summary>解读依据与待确认事项</summary>"
            if row.competing_explanation:
                body += "<p>" + text(row.competing_explanation) + "</p>"
            if row.expected_observation:
                body += "<p>待检验观察：" + text(row.expected_observation) + "</p>"
            body += "</details>"
        for use in getattr(row, "literature_support", []):
            body += '<p>文献依据：<a href="#' + text(use.source_ref) + '">' + text(use.rationale) + "</a></p>"
            body += "<p>适用条件（待核对）：" + text("；".join(getattr(use, field) for field in
                ("species", "lineage", "stage", "experimental_context"))) + "</p>"
        relations = getattr(row, "evidence_relations", [])
        if relations:
            body += "<details><summary>证据如何支持或限制这项解释（待验证）</summary>"
            names = {"supports": "支持", "limits": "限制", "contradicts": "相反证据", "missing_for": "待补证据"}
            for relation in relations:
                body += "<p><strong>" + names[relation.relation] + "：</strong>" + text(relation.rationale) + "</p>"
                body += "<p>适用范围：" + text(relation.applicability) + "</p><small>来源：" + text(relation.evidence_alias) + "</small>"
            body += "</details>"
        body += "</article>"
    if not latest:
        body += "<p>暂无解读。</p>"
    coverage = getattr(version, "feature_coverage", None)
    if coverage is not None:
        body += "<details><summary>已核对的输入基因覆盖</summary><p>仅核对所选输入中的精确标识符；不代表表达、检测灵敏度或生物学缺失。</p>"
        states = {"present": "输入包含", "not_found": "未找到精确匹配", "unknown": "尚不能确定"}
        for item in coverage.results:
            body += "<p>" + text(item.identifier) + "：" + states[item.state] + "</p>"
        body += "</details>"
    bibliography = getattr(version, "literature", None)
    if bibliography is not None:
        body += "<h2>参考文献与适用范围</h2>"
        if not bibliography.sources:
            body += "<p>本轮未读取到可引用的文献摘要；这不表示不存在相关研究。</p>"
        for source in bibliography.sources:
            metadata_row = source.metadata
            body += '<article id="' + text(source.source_ref) + '"><h3><a href="' + text(source.url) + '" rel="noreferrer">'
            body += text(metadata_row.title) + "</a></h3>"
            body += "<p>" + text(metadata_row.authors or "作者未提供") + " · " + text(metadata_row.year or "年份未提供")
            body += " · " + text(metadata_row.journal or "期刊未提供") + "</p>"
            publication_notice = {
                "unknown": "撤稿与更正状态未完整提供，尚未核实。",
                "no_flag_reported": "来源未报告撤稿或更正标记，仍需核实。",
                "correction_reported": "来源报告更正信息，请核对更正内容。",
                "retraction_or_concern_reported": "来源报告撤稿或关注声明，不应据此确立机制解释。",
            }[metadata_row.publication_status]
            body += "<p>" + text(publication_notice) + "</p>"
            for correction in metadata_row.corrections or []:
                body += "<p>" + text(" · ".join(value for value in (
                    correction.type, correction.source, correction.id, correction.reference, correction.note) if value)) + "</p>"
            body += "<p>PMID：" + text(metadata_row.pmid) + "；DOI：" + text(metadata_row.doi or "未提供") + "</p>"
            body += "<p>" + ("已读取摘要" if source.content_level == "abstract" else "仅书目信息，不能支持机制解释")
            body += "；读取时间：" + text(source.retrieved_at) + "</p>"
            if source.abstract:
                body += "<details><summary>保存的摘要</summary><p>" + text(source.abstract) + "</p></details>"
            body += "</article>"
    # Preserve exact audit material as inert document data, outside the reader UI.
    body += '<template id="report-audit">' + paragraphs + sections + "<p>" + text(metadata) + "</p></template>"
    body += '<footer><p>资料版本 ' + text(context.input_revision) + "</p></footer>"
    return ('<!doctype html><html lang="zh"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
            '<title>内部研究证据报告</title><style>'
            '*{box-sizing:border-box}body{font-family:system-ui,sans-serif;max-width:72rem;margin:0 auto;padding:2rem;line-height:1.65;color:#1d1d1f;overflow-wrap:anywhere}'
            'h1{font-size:2rem;line-height:1.3}h2{margin-top:2rem;font-size:1.25rem}.eyebrow{color:#6e6e73;letter-spacing:.08em}'
            '.boundary{background:#f5f5f7;border-left:3px solid #86868b;padding:1rem}'
            'table{width:100%;table-layout:fixed;border-collapse:collapse;font-size:.9rem}th,td{text-align:left;vertical-align:top;padding:.65rem;border-bottom:1px solid #e5e5e7;overflow-wrap:anywhere}'
            'th{background:#f5f5f7}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.8rem}details{margin:.5rem 0 1rem} .measure-unit{color:#6e6e73;font-size:.85rem}summary{cursor:pointer;font-weight:600}'
            'footer{margin-top:2rem;border-top:1px solid #dce5df;font-size:.75rem;color:#52645c}'
            '@media(max-width:600px){body{padding:1rem}h1{font-size:1.6rem}th,td{padding:.4rem;font-size:.8rem}}'
            '@media print{body{max-width:none;padding:0;color:#000}h2{break-after:avoid}tr{break-inside:avoid}}'
            '</style><body data-layout-version="3">' + body + '</body></html>')


def render_research_snapshot(*, snapshot: ResearchAnalysisSnapshot,
                             result: ResearchClaimVerificationResult) -> dict[str, bytes]:
    # Revalidation also rejects callers using Pydantic model_copy/model_construct
    # to circumvent frozen model validators.
    model = research_snapshot_model(snapshot.object_version)
    snapshot = model.model_validate(snapshot.model_dump(mode="json"))
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
    manifest = CaseEvidenceGraphManifest.model_validate_json(snapshot.graph_manifest_json)
    evidence = EvidenceRecordSet.model_validate_json(snapshot.source_evidence_record_set_json)
    from bridge.tool_packages.p0_09_evidence_compiler.adapter import _validate_source_record_set

    effective = _validate_source_record_set(evidence, manifest)
    payload = snapshot.model_dump(mode="json")
    context = (parse_research_context(snapshot.report_context_json)
               if isinstance(snapshot, ResearchAnalysisSnapshotV03) else None)
    context_sections = [] if context is None else _context_sections(context)
    rows = []
    for record in records:
        row = {field: record.get(field) for field in (
            "evidence_id", "evidence_version", "metric_id", "value", "numerator", "denominator",
            "unit", "evidence_state", "relation", "lifecycle_state", "applicability", "evidence_tier",
        )}
        row["row_type"] = "evidence"
        ref = record["evidence_id"] + "@" + str(record["evidence_version"])
        row["effective_lifecycle_state"] = effective[ref].value
        row["source_json"] = _json(record)
        rows.append(row)
    for row_type, raw in (("missing_requirement", snapshot.missing_requirements_json),
                          ("reconciliation", snapshot.reconciliation_records_json)):
        for item in json.loads(raw):
            rows.append({"row_type": row_type, "source_json": _json(item)})
    for title, value in context_sections:
        rows.append({"row_type": "private_context", "source_json": _json({"section": title, "value": value})})
    if not rows:
        rows.append({"row_type": "metadata"})
    for row in rows:
        row.update(snapshot_sha256=snapshot.snapshot_sha256, graph_id=snapshot.graph_id,
                   graph_version=snapshot.graph_version, graph_manifest_sha256=snapshot.graph_manifest_sha256,
                   input_revision=snapshot.input_revision, report_content_hash=snapshot.report_content_hash)
    fields = ["row_type", "evidence_id", "evidence_version", "metric_id", "value", "numerator", "denominator",
              "unit", "evidence_state", "relation", "lifecycle_state", "effective_lifecycle_state",
              "applicability", "evidence_tier", "source_json",
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
    sections = "".join("<h2>" + escape(title) + "</h2><pre>" + escape(json.dumps(value,
        ensure_ascii=False, sort_keys=True, indent=2)) + "</pre>" for title, value in context_sections) + sections
    html = (
        '<!doctype html><html lang="zh"><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
        '<title>内部研究证据报告</title><style>body{font-family:serif;margin:2em;line-height:1.6}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere}p{overflow-wrap:anywhere}'
        '@media print{body{margin:0}h2{break-after:avoid}}</style>'
        '<body><h1>内部研究证据报告</h1><p>' + escape(metadata) + "</p>"
        + paragraphs + sections + "</body></html>"
    )
    if context is not None:
        current = [row.model_dump(mode="json") for row in active_research_records(manifest, evidence)]
        html = _context_report_html(context, current, paragraphs, sections, metadata)
    svg_lines = [metadata, *[title + "：" + _json(value) for title, value in context_sections],
                 *[block.text for block in draft.claim_blocks],
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
