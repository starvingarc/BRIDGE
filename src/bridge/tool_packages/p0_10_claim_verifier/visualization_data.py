from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    EvidenceRecord,
    EvidenceRecordSet,
)
from bridge.tool_packages.p0_10_claim_verifier.models import (
    CheckOutcome,
    ClaimBlock,
    ClaimCheckRecord,
    ClaimType,
    ClaimVerificationResult,
    ReportAudience,
    ReportDraft,
    ReportLanguage,
)
from bridge.tool_packages.p0_10_claim_verifier.verifier import (
    _canonical_decimal,
    _join_numeric_unit,
    _numeric_source,
)
from bridge.toolkit.contracts import EvidenceState, FrozenModel
from bridge.toolkit.visualization import VisualizationArtifactV2


CLAIM_VERIFIER_VISUALIZATION_DATA_SCHEMA_REF = (
    "bridge://schemas/claim-verifier-visualization-data/v0.1"
)
P010_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF = (
    "bridge://schemas/p0-10-visualization-artifact-set/v0.1"
)
CLAIM_CHECK_MATRIX_COMPONENT_REF = (
    "bridge.claim-verifier.claim-check-matrix@0.1.0"
)
NUMERIC_CORRESPONDENCE_COMPONENT_REF = (
    "bridge.claim-verifier.numeric-correspondence@0.1.0"
)
FINDING_CONTEXT_COMPONENT_REF = (
    "bridge.claim-verifier.finding-context@0.1.0"
)
P010_COMPONENT_REFS = (
    CLAIM_CHECK_MATRIX_COMPONENT_REF,
    NUMERIC_CORRESPONDENCE_COMPONENT_REF,
    FINDING_CONTEXT_COMPONENT_REF,
)
P010_COMPONENT_BINDINGS = (
    (
        CLAIM_CHECK_MATRIX_COMPONENT_REF,
        "claim-check-matrix",
        "check_matrix_records",
    ),
    (
        NUMERIC_CORRESPONDENCE_COMPONENT_REF,
        "numeric-correspondence",
        "numeric_records",
    ),
    (FINDING_CONTEXT_COMPONENT_REF, "finding-context", "finding_records"),
)


def _p010_artifact_id(digest: str, suffix: str) -> str:
    return f"artifact:run-{digest}:{suffix}"


def _p010_visualization_id(digest: str, slug: str) -> str:
    return f"visualization:run-{digest}:{slug}"


_SHA256 = r"^[0-9a-f]{64}$"
_RECORD_ID = r"^[a-z][a-z0-9.-]+$"
_EVIDENCE_REF = r"^evidence:[a-f0-9]{24}@[1-9][0-9]*$"


class ClaimCheckCategory(StrEnum):
    CLAIM_STRUCTURE_AND_AUTHORING = "claim_structure_and_authoring"
    EVIDENCE_BINDING_AND_STATE = "evidence_binding_and_state"
    NUMERIC_AND_UNIT = "numeric_and_unit"
    COMPARISON_SCOPE = "comparison_scope"
    WORDING_AND_STATEMENTS = "wording_and_statements"


class ReportCheckDimension(StrEnum):
    REPORT_SCHEMA_AND_HASH = "report_schema_and_hash"
    EVIDENCE_GRAPH_INTEGRITY = "evidence_graph_integrity"
    POLICY_AUTHORITY = "policy_authority"
    STATEMENT_REGISTRY_AUTHORITY = "statement_registry_authority"


class FindingState(StrEnum):
    NO_FINDING = "no_finding_under_current_rules"
    WARNING = "warning_finding"
    REVIEW_REQUIRED = "review_required_finding"
    BLOCKED = "blocking_finding"


class NumericCorrespondenceState(StrEnum):
    EXACT = "exact_identity_under_current_rules"
    NOT_CITED = "source_not_cited_numeric_not_assessed"
    SOURCE_UNAVAILABLE = "source_numeric_unavailable"
    CANONICAL_MISMATCH = "canonical_numeric_mismatch"
    UNIT_MISMATCH = "unit_mismatch"
    RENDERED_MISMATCH = "rendered_numeric_mismatch"
    SOURCE_NOT_SCALAR = "numeric_source_not_scalar"


class CitationState(StrEnum):
    CITED = "cited"
    NOT_CITED = "not_cited"


def _sorted_unique(values: list[str], field_name: str) -> list[str]:
    if values != sorted(set(values)):
        raise ValueError(f"{field_name} must be sorted and unique")
    return values


class _VisualizationRecord(FrozenModel):
    record_id: str = Field(pattern=_RECORD_ID)
    evidence_ids: list[str] = Field(min_length=1)
    evidence_state: EvidenceState
    scientific_status: Literal["candidate"] = "candidate"
    missingness: Literal["available", "unavailable"]
    applicability: Literal["applicable", "partially_applicable", "not_assessed"]
    display_state: str = Field(min_length=1)

    @field_validator("evidence_ids")
    @classmethod
    def evidence_ids_are_sorted(cls, values: list[str]) -> list[str]:
        return _sorted_unique(values, "evidence_ids")


class ClaimCategoryCell(FrozenModel):
    category: ClaimCheckCategory
    finding_state: FindingState
    finding_count: int = Field(ge=0)
    check_ids: list[str]

    @field_validator("check_ids")
    @classmethod
    def check_ids_are_sorted(cls, values: list[str]) -> list[str]:
        return _sorted_unique(values, "check_ids")

    @model_validator(mode="after")
    def count_matches_ids(self) -> Self:
        if self.finding_count != len(self.check_ids):
            raise ValueError("category finding count must equal check IDs")
        if (self.finding_count == 0) != (
            self.finding_state is FindingState.NO_FINDING
        ):
            raise ValueError("no-finding state must match an empty check set")
        return self


class ReportCheckCell(FrozenModel):
    dimension: ReportCheckDimension
    finding_state: Literal[FindingState.NO_FINDING] = FindingState.NO_FINDING
    finding_count: Literal[0] = 0


class ReportCheckMatrixRecord(_VisualizationRecord):
    record_kind: Literal["report_check_matrix"] = "report_check_matrix"
    report_draft_ref: str = Field(min_length=1)
    report_content_hash: str = Field(pattern=_SHA256)
    assessment_scope: Literal["successful_run_eligibility_preconditions"] = (
        "successful_run_eligibility_preconditions"
    )
    checks: list[ReportCheckCell] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def report_eligibility_ledger_is_complete(self) -> Self:
        if [cell.dimension for cell in self.checks] != list(ReportCheckDimension):
            raise ValueError("report matrix requires four fixed dimensions in order")
        if self.display_state != FindingState.NO_FINDING.value:
            raise ValueError(
                "successful-run report checks use the bounded no-finding state"
            )
        if (
            self.evidence_state is not EvidenceState.INFERRED
            or self.missingness != "available"
            or self.applicability != "applicable"
        ):
            raise ValueError("report checks require the fixed successful-run axes")
        return self


class ClaimCheckMatrixRecord(_VisualizationRecord):
    record_kind: Literal["claim_check_matrix"] = "claim_check_matrix"
    claim_order: int = Field(ge=1)
    claim_id: str = Field(min_length=1)
    claim_ref: str = Field(min_length=1)
    claim_type: ClaimType
    claim_text: str = Field(min_length=1)
    cited_evidence_refs: list[str]
    binding_source_refs: list[str]
    categories: list[ClaimCategoryCell] = Field(min_length=5, max_length=5)
    check_ids: list[str]
    finding_count: int = Field(ge=0)

    @field_validator("cited_evidence_refs", "binding_source_refs", "check_ids")
    @classmethod
    def set_like_fields_are_sorted(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)

    @model_validator(mode="after")
    def category_ledger_is_complete(self) -> Self:
        if [cell.category for cell in self.categories] != list(ClaimCheckCategory):
            raise ValueError("claim matrix requires five fixed categories in order")
        expected_ids = sorted(
            check_id for cell in self.categories for check_id in cell.check_ids
        )
        if self.check_ids != expected_ids or self.finding_count != len(expected_ids):
            raise ValueError("claim matrix checks must equal the category-cell union")
        finding_state = _highest_finding_state(
            [cell.finding_state for cell in self.categories]
        )
        if self.display_state != finding_state.value:
            raise ValueError("claim display state must equal its highest finding state")
        if (
            self.evidence_state is not _finding_evidence_state(finding_state)
            or self.missingness != "available"
            or self.applicability != "applicable"
        ):
            raise ValueError("claim finding state and evidence axes disagree")
        return self


CheckMatrixRecord = Annotated[
    ReportCheckMatrixRecord | ClaimCheckMatrixRecord,
    Field(discriminator="record_kind"),
]


class NumericCorrespondenceRecord(_VisualizationRecord):
    record_kind: Literal["numeric_correspondence"] = "numeric_correspondence"
    claim_order: int = Field(ge=1)
    claim_id: str = Field(min_length=1)
    claim_ref: str = Field(min_length=1)
    binding_id: str = Field(min_length=1)
    source_evidence_ref: str = Field(pattern=_EVIDENCE_REF)
    source_field: Literal[
        "value", "numerator", "denominator", "interval_lower", "interval_upper"
    ]
    citation_state: CitationState
    span_start: int = Field(ge=0)
    span_end: int = Field(gt=0)
    report_rendered_text: str
    report_canonical_numeric_string: str = Field(min_length=1)
    report_unit: str | None
    evidence_canonical_numeric_string: str | None
    evidence_unit: str | None
    correspondence_state: NumericCorrespondenceState
    check_ids: list[str]
    reason_codes: list[str]

    @field_validator("check_ids", "reason_codes")
    @classmethod
    def set_like_fields_are_sorted(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)

    @model_validator(mode="after")
    def numeric_fields_are_coherent(self) -> Self:
        if self.span_end - self.span_start != len(self.report_rendered_text):
            raise ValueError("numeric span length must equal the rendered text length")
        if self.display_state != self.correspondence_state.value:
            raise ValueError("numeric display state must equal correspondence state")
        state = self.correspondence_state
        if state is NumericCorrespondenceState.EXACT:
            if (
                self.citation_state is not CitationState.CITED
                or self.missingness != "available"
                or self.applicability != "applicable"
                or self.report_canonical_numeric_string
                != self.evidence_canonical_numeric_string
                or self.report_unit != self.evidence_unit
                or self.report_rendered_text
                != _join_numeric_unit(
                    self.report_canonical_numeric_string, self.report_unit
                )
                or self.reason_codes
                or self.check_ids
            ):
                raise ValueError("exact correspondence axes or values disagree")
            return self

        expected_reason = {
            NumericCorrespondenceState.NOT_CITED: "binding_evidence_not_cited",
            NumericCorrespondenceState.SOURCE_NOT_SCALAR: "numeric_source_not_scalar",
            NumericCorrespondenceState.CANONICAL_MISMATCH: "canonical_numeric_mismatch",
            NumericCorrespondenceState.UNIT_MISMATCH: "unit_mismatch",
            NumericCorrespondenceState.RENDERED_MISMATCH: "rendered_numeric_mismatch",
        }.get(state)
        if state is NumericCorrespondenceState.NOT_CITED:
            if (
                self.reason_codes != [expected_reason]
                or len(self.check_ids) != 1
                or self.citation_state is not CitationState.NOT_CITED
                or self.evidence_state is not EvidenceState.ALERT
                or self.applicability != "not_assessed"
                or self.missingness
                != (
                    "unavailable"
                    if self.evidence_canonical_numeric_string is None
                    else "available"
                )
            ):
                raise ValueError("uncited numeric binding axes disagree")
            return self
        if state is NumericCorrespondenceState.SOURCE_UNAVAILABLE:
            valid_reason_path = (
                self.reason_codes == ["numeric_source_unavailable"]
                and len(self.check_ids) == 1
            ) or (
                self.reason_codes == ["source_evidence_record_unavailable"]
                and not self.check_ids
            )
            if (
                not valid_reason_path
                or self.citation_state is not CitationState.CITED
                or self.evidence_state is not EvidenceState.UNAVAILABLE
                or self.missingness != "unavailable"
                or self.applicability != "not_assessed"
                or self.evidence_canonical_numeric_string is not None
            ):
                raise ValueError("unavailable numeric source axes disagree")
            return self
        if state is NumericCorrespondenceState.SOURCE_NOT_SCALAR:
            if (
                self.reason_codes != [expected_reason]
                or len(self.check_ids) != 1
                or self.citation_state is not CitationState.CITED
                or self.evidence_state is not EvidenceState.UNAVAILABLE
                or self.missingness != "unavailable"
                or self.applicability != "not_assessed"
                or self.evidence_canonical_numeric_string is not None
            ):
                raise ValueError("unavailable numeric source axes disagree")
            return self
        if self.reason_codes != [expected_reason] or len(self.check_ids) != 1:
            raise ValueError(
                "numeric mismatch requires one matching deterministic finding"
            )
        if (
            self.citation_state is not CitationState.CITED
            or self.evidence_state is not EvidenceState.ALERT
            or self.missingness != "available"
            or self.applicability != "applicable"
            or self.evidence_canonical_numeric_string is None
        ):
            raise ValueError("numeric mismatch axes disagree")
        if state is NumericCorrespondenceState.CANONICAL_MISMATCH and (
            self.report_canonical_numeric_string
            == self.evidence_canonical_numeric_string
        ):
            raise ValueError("canonical mismatch requires different numeric values")
        if state is NumericCorrespondenceState.UNIT_MISMATCH and (
            self.report_canonical_numeric_string
            != self.evidence_canonical_numeric_string
            or self.report_unit == self.evidence_unit
        ):
            raise ValueError("unit mismatch requires equal values and different units")
        if state is NumericCorrespondenceState.RENDERED_MISMATCH and (
            self.report_canonical_numeric_string
            != self.evidence_canonical_numeric_string
            or self.report_unit != self.evidence_unit
            or self.report_rendered_text
            == _join_numeric_unit(
                self.report_canonical_numeric_string, self.report_unit
            )
        ):
            raise ValueError("rendered mismatch requires only rendered text to differ")
        return self


class _FindingContextBase(_VisualizationRecord):
    claim_order: int = Field(ge=1)
    claim_id: str = Field(min_length=1)
    claim_ref: str = Field(min_length=1)
    claim_type: ClaimType
    claim_text: str = Field(min_length=1)
    check_id: str = Field(min_length=1)
    rule_id: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    outcome: Literal["blocked", "review_required", "warning"]
    severity: Literal["hard_blocker", "review", "warning"]
    reason_code: str = Field(min_length=1)
    binding_id: str | None = None
    source_evidence_refs: list[str]
    statement_ref: str | None = None

    @field_validator("source_evidence_refs")
    @classmethod
    def source_refs_are_sorted(cls, values: list[str]) -> list[str]:
        return _sorted_unique(values, "source_evidence_refs")

    @model_validator(mode="after")
    def finding_axes_are_coherent(self) -> Self:
        expected = {
            "blocked": ("hard_blocker", FindingState.BLOCKED.value),
            "review_required": ("review", FindingState.REVIEW_REQUIRED.value),
            "warning": ("warning", FindingState.WARNING.value),
        }[self.outcome]
        if (self.severity, self.display_state) != expected:
            raise ValueError("finding outcome, severity and display state disagree")
        finding_state = {
            "blocked": FindingState.BLOCKED,
            "review_required": FindingState.REVIEW_REQUIRED,
            "warning": FindingState.WARNING,
        }[self.outcome]
        if (
            self.evidence_state is not _finding_evidence_state(finding_state)
            or self.missingness != "available"
            or self.applicability != "applicable"
        ):
            raise ValueError("finding state and evidence axes disagree")
        return self


class SpanFindingContextRecord(_FindingContextBase):
    record_kind: Literal["span_finding_context"] = "span_finding_context"
    span_start: int = Field(ge=0)
    span_end: int = Field(gt=0)
    matched_text: str = Field(min_length=1)

    @model_validator(mode="after")
    def matched_text_is_exact_claim_slice(self) -> Self:
        if (
            self.span_end <= self.span_start
            or self.span_end > len(self.claim_text)
            or self.claim_text[self.span_start : self.span_end] != self.matched_text
        ):
            raise ValueError("finding span must match the exact claim-text slice")
        return self


class ClaimFindingContextRecord(_FindingContextBase):
    record_kind: Literal["claim_finding_context"] = "claim_finding_context"
    no_span_reason: Literal["check_has_no_exact_text_span"] = (
        "check_has_no_exact_text_span"
    )


FindingContextRecord = Annotated[
    SpanFindingContextRecord | ClaimFindingContextRecord,
    Field(discriminator="record_kind"),
]


class ClaimVerifierVisualizationDataV1(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[CLAIM_VERIFIER_VISUALIZATION_DATA_SCHEMA_REF] = (
        CLAIM_VERIFIER_VISUALIZATION_DATA_SCHEMA_REF
    )
    visualization_profile_id: str = Field(
        pattern=r"^claim-verifier-visualization:[a-f0-9]{16}$"
    )
    producer_tool_id: Literal["P0-10"] = "P0-10"
    producer_tool_version: str = Field(min_length=1)
    producer_run_ref: str = Field(pattern=r"^run:run-[a-f0-9]{16}$")
    source_result_ref: str = Field(pattern=r"^claim-verification:[a-f0-9]{16}$")
    source_result_version: Literal["0.1.0"] = "0.1.0"
    source_result_sha256: str = Field(pattern=_SHA256)
    report_draft_ref: str = Field(min_length=1)
    report_content_hash: str = Field(pattern=_SHA256)
    report_audience: ReportAudience
    report_language: ReportLanguage
    claim_count: int = Field(ge=1)
    binding_count: int = Field(ge=0)
    finding_count: int = Field(ge=0)
    check_matrix_records: list[CheckMatrixRecord] = Field(min_length=2)
    numeric_records: list[NumericCorrespondenceRecord]
    finding_records: list[FindingContextRecord]
    source_evidence_refs: list[str]
    evidence_ids: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    check_counts_are_audit_counts_not_evidence_amount: Literal[True] = True
    no_finding_is_limited_to_current_deterministic_rules: Literal[True] = True
    visualization_artifacts_are_not_public_export_clearance: Literal[True] = True
    domain_score: None = None

    @field_validator("source_evidence_refs", "evidence_ids", "limitations")
    @classmethod
    def set_like_fields_are_sorted(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)

    @model_validator(mode="after")
    def records_are_complete_and_conserved(self) -> Self:
        digest = self.visualization_profile_id.rsplit(":", 1)[1]
        if (
            self.producer_run_ref != f"run:run-{digest}"
            or self.source_result_ref != f"claim-verification:{digest}"
        ):
            raise ValueError(
                "visualization profile, producer run and source result digests must agree"
            )
        report_rows = [
            row
            for row in self.check_matrix_records
            if isinstance(row, ReportCheckMatrixRecord)
        ]
        claim_rows = [
            row
            for row in self.check_matrix_records
            if isinstance(row, ClaimCheckMatrixRecord)
        ]
        if len(report_rows) != 1 or not isinstance(
            self.check_matrix_records[0], ReportCheckMatrixRecord
        ):
            raise ValueError("matrix must begin with exactly one report-level record")
        report_row = report_rows[0]
        if (
            report_row.report_draft_ref != self.report_draft_ref
            or report_row.report_content_hash != self.report_content_hash
        ):
            raise ValueError("report matrix must bind the top-level report identity")
        if self.claim_count != len(claim_rows):
            raise ValueError("claim count must equal matrix claim rows")
        if self.binding_count != len(self.numeric_records):
            raise ValueError("binding count must equal numeric rows")
        if self.finding_count != len(self.finding_records):
            raise ValueError("finding count must equal finding rows")
        if [row.claim_order for row in claim_rows] != list(
            range(1, self.claim_count + 1)
        ):
            raise ValueError("claim matrix must preserve report order")
        claim_by_id = {row.claim_id: row for row in claim_rows}
        if len(claim_by_id) != len(claim_rows):
            raise ValueError("claim matrix claim IDs must be unique")
        for record in [*self.numeric_records, *self.finding_records]:
            claim = claim_by_id.get(record.claim_id)
            if claim is None:
                raise ValueError("numeric and finding rows must resolve to a claim row")
            if (record.claim_order, record.claim_ref) != (
                claim.claim_order,
                claim.claim_ref,
            ):
                raise ValueError("numeric and finding rows must preserve claim identity")
        findings_by_claim: dict[str, list[FindingContextRecord]] = {}
        for finding in self.finding_records:
            findings_by_claim.setdefault(finding.claim_id, []).append(finding)
        expected_ids = {
            "check_matrix_records": [
                "report-matrix.001",
                *[
                    f"claim-matrix.{index:03d}"
                    for index in range(1, self.claim_count + 1)
                ],
            ],
            "numeric_records": [
                f"numeric.{index:03d}"
                for index in range(1, self.binding_count + 1)
            ],
            "finding_records": [
                f"finding.{index:03d}"
                for index in range(1, self.finding_count + 1)
            ],
        }
        for field_name, expected in expected_ids.items():
            actual = [item.record_id for item in getattr(self, field_name)]
            if actual != expected:
                raise ValueError(f"{field_name} IDs must be stable and ordered")
        matrix_check_ids = sorted(
            check_id
            for row in claim_rows
            for check_id in row.check_ids
        )
        finding_check_ids = sorted(row.check_id for row in self.finding_records)
        if matrix_check_ids != finding_check_ids:
            raise ValueError("matrix and finding rows must conserve every check exactly once")
        finding_by_check = {row.check_id: row for row in self.finding_records}
        if len(finding_by_check) != len(self.finding_records):
            raise ValueError("finding check IDs must be unique")
        if report_row.evidence_ids != [self.source_result_ref]:
            raise ValueError("report row evidence IDs must bind only the source receipt")
        numeric_sources_by_claim: dict[str, set[str]] = {}
        for numeric in self.numeric_records:
            numeric_sources_by_claim.setdefault(numeric.claim_id, set()).add(
                numeric.source_evidence_ref
            )
        for claim in claim_rows:
            claim_findings = findings_by_claim.get(claim.claim_id, [])
            if claim.binding_source_refs != sorted(
                numeric_sources_by_claim.get(claim.claim_id, set())
            ):
                raise ValueError("claim binding refs must equal its numeric source union")
            if claim.evidence_ids != _evidence_ids(
                self.source_result_ref,
                [*claim.cited_evidence_refs, *claim.binding_source_refs],
            ):
                raise ValueError("claim row evidence IDs must exactly bind its refs")
            for cell in claim.categories:
                category_findings = [
                    finding
                    for finding in claim_findings
                    if _category_for_rule_id(finding.rule_id) is cell.category
                ]
                expected_check_ids = sorted(
                    finding.check_id for finding in category_findings
                )
                expected_state = _highest_finding_state(
                    [FindingState(finding.display_state) for finding in category_findings]
                )
                if (
                    cell.check_ids != expected_check_ids
                    or cell.finding_count != len(expected_check_ids)
                    or cell.finding_state is not expected_state
                ):
                    raise ValueError("claim category cells must be recomputed from rules")
            if any(
                finding.claim_type is not claim.claim_type
                or finding.claim_text != claim.claim_text
                for finding in claim_findings
            ):
                raise ValueError("finding claim type and text must match its claim row")
        numeric_by_binding = {
            (row.claim_id, row.binding_id): row for row in self.numeric_records
        }
        if len(numeric_by_binding) != len(self.numeric_records):
            raise ValueError("claim and binding pairs must be unique")
        for numeric in self.numeric_records:
            claim = claim_by_id[numeric.claim_id]
            if (
                numeric.span_end > len(claim.claim_text)
                or claim.claim_text[numeric.span_start : numeric.span_end]
                != numeric.report_rendered_text
            ):
                raise ValueError("numeric span must match the canonical claim text")
            if numeric.evidence_ids != _evidence_ids(
                self.source_result_ref, [numeric.source_evidence_ref]
            ):
                raise ValueError("numeric row evidence IDs must exactly bind its source")
            if numeric.source_evidence_ref not in claim.binding_source_refs:
                raise ValueError("numeric source must occur in the claim binding refs")
            expected_citation = (
                CitationState.CITED
                if numeric.source_evidence_ref in claim.cited_evidence_refs
                else CitationState.NOT_CITED
            )
            if numeric.citation_state is not expected_citation:
                raise ValueError("numeric citation state must match the claim citations")
            matched = [
                finding
                for finding in self.finding_records
                if finding.claim_id == numeric.claim_id
                and finding.binding_id == numeric.binding_id
            ]
            if any(
                not isinstance(finding, SpanFindingContextRecord)
                or finding.source_evidence_refs != [numeric.source_evidence_ref]
                or (finding.span_start, finding.span_end)
                != (numeric.span_start, numeric.span_end)
                for finding in matched
            ):
                raise ValueError("binding findings must match numeric source and span")
            if numeric.check_ids != sorted(finding.check_id for finding in matched):
                raise ValueError("numeric check IDs must equal its binding findings")
            finding_reasons = sorted({finding.reason_code for finding in matched})
            absent_record_reason = (
                numeric.correspondence_state
                is NumericCorrespondenceState.SOURCE_UNAVAILABLE
                and numeric.reason_codes == ["source_evidence_record_unavailable"]
                and not numeric.check_ids
                and not matched
            )
            if numeric.reason_codes != finding_reasons and not absent_record_reason:
                raise ValueError("numeric reason codes must equal its binding findings")
        for finding in self.finding_records:
            if finding.binding_id is None:
                continue
            numeric = numeric_by_binding.get((finding.claim_id, finding.binding_id))
            if numeric is None or not isinstance(finding, SpanFindingContextRecord):
                raise ValueError("binding finding must resolve to a numeric row")
            if (
                finding.source_evidence_refs != [numeric.source_evidence_ref]
                or finding.matched_text != numeric.report_rendered_text
                or (finding.span_start, finding.span_end)
                != (numeric.span_start, numeric.span_end)
            ):
                raise ValueError("binding finding reverse mapping is inconsistent")
        for finding in self.finding_records:
            if finding.evidence_ids != _evidence_ids(
                self.source_result_ref, finding.source_evidence_refs
            ):
                raise ValueError("finding row evidence IDs must exactly bind its refs")
        records = [
            *self.check_matrix_records,
            *self.numeric_records,
            *self.finding_records,
        ]
        expected_evidence_ids = sorted(
            {evidence_id for row in records for evidence_id in row.evidence_ids}
        )
        if self.evidence_ids != expected_evidence_ids:
            raise ValueError("top-level evidence IDs must equal the record union")
        expected_source_refs = sorted(
            {
                ref
                for row in claim_rows
                for ref in [*row.cited_evidence_refs, *row.binding_source_refs]
            }
            | {
                row.source_evidence_ref
                for row in self.numeric_records
            }
            | {
                ref
                for row in self.finding_records
                for ref in row.source_evidence_refs
            }
        )
        if self.source_evidence_refs != expected_source_refs:
            raise ValueError("source evidence refs must equal the record union")
        return self


class P010VisualizationArtifactSet(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[P010_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF] = (
        P010_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF
    )
    artifact_set_id: str = Field(pattern=r"^p0-10-visualizations:[a-f0-9]{16}$")
    data_profile_artifact_id: str = Field(min_length=1)
    data_profile_sha256: str = Field(pattern=_SHA256)
    visualizations: list[VisualizationArtifactV2] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def artifact_set_is_exactly_bound(self) -> Self:
        if [item.component_ref for item in self.visualizations] != list(
            P010_COMPONENT_REFS
        ):
            raise ValueError("artifact set must contain the three P0-10 components")
        if any(
            item.data_binding.artifact_id != self.data_profile_artifact_id
            or item.data_binding.sha256 != self.data_profile_sha256
            for item in self.visualizations
        ):
            raise ValueError("visualizations must bind the exact data profile")
        expected_media = ["image/svg+xml", "image/png", "application/pdf"]
        if any(
            [render.media_type for render in item.renders] != expected_media
            for item in self.visualizations
        ):
            raise ValueError("each visualization requires one ordered SVG, PNG and PDF")
        visualization_ids = [item.visualization_id for item in self.visualizations]
        if len(visualization_ids) != len(set(visualization_ids)):
            raise ValueError("visualization IDs must be unique")
        table_ids = [
            item.accessibility.table_artifact_id for item in self.visualizations
        ]
        if len(table_ids) != len(set(table_ids)):
            raise ValueError("visualization table artifact IDs must be unique")
        if self.data_profile_artifact_id in table_ids:
            raise ValueError("data and table artifact IDs must be disjoint")
        producer_contracts = {
            (
                item.producer_tool_id,
                item.producer_tool_version,
                item.producer_run_ref,
            )
            for item in self.visualizations
        }
        digest = self.artifact_set_id.rsplit(":", 1)[1]
        if self.data_profile_artifact_id != _p010_artifact_id(
            digest, "claim-verifier-visualization-data"
        ):
            raise ValueError("data profile artifact ID must bind the artifact-set run")
        for item, (_component_ref, slug, records_path) in zip(
            self.visualizations, P010_COMPONENT_BINDINGS, strict=True
        ):
            if item.visualization_id != _p010_visualization_id(digest, slug):
                raise ValueError("visualization ID must bind its run and component")
            if item.data_binding.records_path != records_path:
                raise ValueError("visualization records path must match its component")
            if item.accessibility.table_artifact_id != _p010_artifact_id(
                digest, f"claim-verifier-{slug}-table"
            ):
                raise ValueError("table artifact ID must match its component")
            expected_render_ids = [
                _p010_artifact_id(digest, f"claim-verifier-{slug}-{extension}")
                for extension in ("svg", "png", "pdf")
            ]
            if [render.artifact_id for render in item.renders] != expected_render_ids:
                raise ValueError("render artifact IDs must match format and component")
        expected_producer = (
            "P0-10",
            self.visualizations[0].producer_tool_version,
            f"run:run-{digest}",
        )
        if producer_contracts != {expected_producer}:
            raise ValueError("visualizations must share the artifact-set producer run")
        render_ids = [
            render.artifact_id
            for item in self.visualizations
            for render in item.renders
        ]
        if len(render_ids) != len(set(render_ids)):
            raise ValueError("visualization render artifact IDs must be unique")
        if set(render_ids).intersection(
            {self.data_profile_artifact_id, *table_ids}
        ):
            raise ValueError("data, table and render artifact IDs must be disjoint")
        return self


def build_claim_verifier_visualization_data(
    *,
    run_id: str,
    tool_version: str,
    report: ReportDraft,
    evidence_set: EvidenceRecordSet,
    result: ClaimVerificationResult,
) -> ClaimVerifierVisualizationDataV1:
    digest = run_id.removeprefix("run-")
    if result.verification_id != f"claim-verification:{digest}":
        raise ValueError("result and producer run digests must agree")
    if not result.matches_report_draft(report):
        raise ValueError("result does not bind the supplied report")
    evidence_by_ref = {record.ref: record for record in evidence_set.records}
    checks_by_claim: dict[str, list[ClaimCheckRecord]] = {}
    for check in result.check_records:
        checks_by_claim.setdefault(check.claim_id, []).append(check)

    receipt_id = result.verification_id
    matrix_records: list[CheckMatrixRecord] = [
        ReportCheckMatrixRecord(
            record_id="report-matrix.001",
            report_draft_ref=report.ref,
            report_content_hash=report.content_hash,
            checks=[
                ReportCheckCell(dimension=dimension)
                for dimension in ReportCheckDimension
            ],
            evidence_ids=[receipt_id],
            evidence_state=EvidenceState.INFERRED,
            missingness="available",
            applicability="applicable",
            display_state=FindingState.NO_FINDING.value,
        )
    ]
    numeric_rows: list[tuple[int, str, NumericCorrespondenceRecord]] = []

    for claim_order, claim in enumerate(report.claim_blocks, start=1):
        checks = checks_by_claim.get(claim.claim_id, [])
        cells = []
        for category in ClaimCheckCategory:
            category_checks = [
                check for check in checks if _check_category(check) is category
            ]
            cells.append(
                ClaimCategoryCell(
                    category=category,
                    finding_state=_finding_state(category_checks),
                    finding_count=len(category_checks),
                    check_ids=sorted(check.check_id for check in category_checks),
                )
            )
        source_refs = sorted(
            {
                *claim.evidence_refs,
                *(binding.source_evidence_ref for binding in claim.value_bindings),
            }
        )
        matrix_records.append(
            ClaimCheckMatrixRecord(
                record_id=f"claim-matrix.{claim_order:03d}",
                claim_order=claim_order,
                claim_id=claim.claim_id,
                claim_ref=claim.claim_ref,
                claim_type=claim.claim_type,
                claim_text=claim.text,
                cited_evidence_refs=sorted(claim.evidence_refs),
                binding_source_refs=sorted(
                    {binding.source_evidence_ref for binding in claim.value_bindings}
                ),
                categories=cells,
                check_ids=sorted(check.check_id for check in checks),
                finding_count=len(checks),
                evidence_ids=_evidence_ids(receipt_id, source_refs),
                evidence_state=_finding_evidence_state(_finding_state(checks)),
                missingness="available",
                applicability="applicable",
                display_state=_finding_state(checks).value,
            )
        )
        for binding in claim.value_bindings:
            record = evidence_by_ref.get(binding.source_evidence_ref)
            related_checks = [
                check
                for check in checks
                if check.rule_id in {"rule:value-binding", "rule:numeric-fidelity"}
                and check.text_span == binding.text_span
                and binding.source_evidence_ref in check.evidence_refs
            ]
            citation_state = (
                CitationState.CITED
                if binding.source_evidence_ref in claim.evidence_refs
                else CitationState.NOT_CITED
            )
            evidence_canonical = (
                None
                if record is None
                else _canonical_decimal(_numeric_source(record, binding.source_field))
            )
            state = _numeric_state(
                citation_state=citation_state,
                record=record,
                evidence_canonical=evidence_canonical,
                checks=related_checks,
            )
            start, end = binding.text_span
            reason_codes = sorted(check.reason_code for check in related_checks)
            if record is None and citation_state is CitationState.CITED:
                reason_codes = ["source_evidence_record_unavailable"]
            numeric_rows.append(
                (
                    claim_order,
                    binding.binding_id,
                    NumericCorrespondenceRecord(
                        record_id="numeric.pending",
                        claim_order=claim_order,
                        claim_id=claim.claim_id,
                        claim_ref=claim.claim_ref,
                        binding_id=binding.binding_id,
                        source_evidence_ref=binding.source_evidence_ref,
                        source_field=binding.source_field,
                        citation_state=citation_state,
                        span_start=start,
                        span_end=end,
                        report_rendered_text=claim.text[start:end],
                        report_canonical_numeric_string=(
                            binding.canonical_numeric_string
                        ),
                        report_unit=binding.raw_unit,
                        evidence_canonical_numeric_string=evidence_canonical,
                        evidence_unit=None if record is None else record.unit,
                        correspondence_state=state,
                        check_ids=sorted(check.check_id for check in related_checks),
                        reason_codes=reason_codes,
                        evidence_ids=_evidence_ids(
                            receipt_id, [binding.source_evidence_ref]
                        ),
                        evidence_state=_numeric_evidence_state(state, record),
                        missingness=(
                            "unavailable"
                            if evidence_canonical is None
                            else "available"
                        ),
                        applicability=(
                            "not_assessed"
                            if state
                            in {
                                NumericCorrespondenceState.NOT_CITED,
                                NumericCorrespondenceState.SOURCE_UNAVAILABLE,
                                NumericCorrespondenceState.SOURCE_NOT_SCALAR,
                            }
                            else "applicable"
                        ),
                        display_state=state.value,
                    ),
                )
            )

    numeric_records = [
        row.model_copy(update={"record_id": f"numeric.{index:03d}"})
        for index, (_claim_order, _binding_id, row) in enumerate(
            sorted(numeric_rows, key=lambda item: (item[0], item[1])),
            start=1,
        )
    ]
    finding_records = _finding_records(
        report=report,
        result=result,
        receipt_id=receipt_id,
    )
    records = [*matrix_records, *numeric_records, *finding_records]
    source_refs = sorted(
        {
            ref
            for row in matrix_records
            if isinstance(row, ClaimCheckMatrixRecord)
            for ref in [*row.cited_evidence_refs, *row.binding_source_refs]
        }
        | {row.source_evidence_ref for row in numeric_records}
        | {
            ref
            for row in finding_records
            for ref in row.source_evidence_refs
        }
    )
    result_payload = canonical_json_bytes(result.model_dump(mode="json"), indent=2)
    return ClaimVerifierVisualizationDataV1(
        visualization_profile_id=f"claim-verifier-visualization:{digest}",
        producer_tool_version=tool_version,
        producer_run_ref=f"run:{run_id}",
        source_result_ref=result.verification_id,
        source_result_sha256=hashlib.sha256(result_payload).hexdigest(),
        report_draft_ref=report.ref,
        report_content_hash=report.content_hash,
        report_audience=report.audience,
        report_language=report.language,
        claim_count=len(report.claim_blocks),
        binding_count=len(numeric_records),
        finding_count=len(finding_records),
        check_matrix_records=matrix_records,
        numeric_records=numeric_records,
        finding_records=finding_records,
        source_evidence_refs=source_refs,
        evidence_ids=sorted(
            {evidence_id for row in records for evidence_id in row.evidence_ids}
        ),
        limitations=sorted(
            {
                "check_counts_are_audit_counts_not_evidence_amount",
                "exact_numeric_correspondence_does_not_validate_scientific_interpretation",
                "no_finding_means_no_record_under_current_deterministic_rules_only",
                "report_text_context_remains_local_and_is_not_public_export_clearance",
                "this_tool_does_not_recompute_biological_measurements",
            }
        ),
        domain_score=None,
    )


def _finding_records(
    *,
    report: ReportDraft,
    result: ClaimVerificationResult,
    receipt_id: str,
) -> list[FindingContextRecord]:
    claim_by_id = {
        claim.claim_id: (order, claim)
        for order, claim in enumerate(report.claim_blocks, start=1)
    }
    rows: list[FindingContextRecord] = []
    for index, check in enumerate(
        sorted(result.check_records, key=lambda item: item.check_id),
        start=1,
    ):
        claim_order, claim = claim_by_id[check.claim_id]
        state = _finding_state([check])
        common = {
            "record_id": f"finding.{index:03d}",
            "claim_order": claim_order,
            "claim_id": claim.claim_id,
            "claim_ref": claim.claim_ref,
            "claim_type": claim.claim_type,
            "claim_text": claim.text,
            "check_id": check.check_id,
            "rule_id": check.rule_id,
            "rule_version": check.rule_version,
            "outcome": check.outcome.value,
            "severity": check.severity.value,
            "reason_code": check.reason_code,
            "binding_id": _binding_id_for_check(claim, check),
            "source_evidence_refs": check.evidence_refs,
            "statement_ref": check.statement_ref,
            "evidence_ids": _evidence_ids(receipt_id, check.evidence_refs),
            "evidence_state": _finding_evidence_state(state),
            "missingness": "available",
            "applicability": "applicable",
            "display_state": state.value,
        }
        if check.text_span is None:
            rows.append(ClaimFindingContextRecord(**common))
        else:
            start, end = check.text_span
            rows.append(
                SpanFindingContextRecord(
                    **common,
                    span_start=start,
                    span_end=end,
                    matched_text=claim.text[start:end],
                )
            )
    return rows


def _binding_id_for_check(
    claim: ClaimBlock,
    check: ClaimCheckRecord,
) -> str | None:
    if (
        check.rule_id not in {"rule:value-binding", "rule:numeric-fidelity"}
        or check.text_span is None
    ):
        return None
    matches = [
        binding.binding_id
        for binding in claim.value_bindings
        if binding.text_span == check.text_span
        and binding.source_evidence_ref in check.evidence_refs
    ]
    return matches[0] if len(matches) == 1 else None


def _check_category(check: ClaimCheckRecord) -> ClaimCheckCategory:
    return _category_for_rule_id(check.rule_id)


def _category_for_rule_id(rule_id: str) -> ClaimCheckCategory:
    if rule_id in {"rule:deterministic-authoring", "rule:claim-type-policy"}:
        return ClaimCheckCategory.CLAIM_STRUCTURE_AND_AUTHORING
    if rule_id in {
        "rule:evidence-binding",
        "rule:evidence-lifecycle",
        "rule:evidence-applicability",
        "rule:evidence-tier",
        "rule:evidence-state-policy",
        "rule:evidence-state",
        "rule:claim-scope",
        "rule:case-scope",
    }:
        return ClaimCheckCategory.EVIDENCE_BINDING_AND_STATE
    if rule_id in {"rule:value-binding", "rule:numeric-fidelity"}:
        return ClaimCheckCategory.NUMERIC_AND_UNIT
    if rule_id in {
        "rule:comparison-mode",
        "rule:comparison-contract",
        "rule:descriptive-scope",
    }:
        return ClaimCheckCategory.COMPARISON_SCOPE
    if rule_id in {
        "rule:statement-binding",
        "rule:statement-text",
        "rule:prohibited-clinical",
        "rule:ambiguous-superiority",
    }:
        return ClaimCheckCategory.WORDING_AND_STATEMENTS
    raise ValueError(f"unregistered claim-check rule: {rule_id}")


def _finding_state(checks) -> FindingState:
    outcomes = {
        check.outcome if isinstance(check, ClaimCheckRecord) else None
        for check in checks
    }
    if CheckOutcome.BLOCKED in outcomes or FindingState.BLOCKED in checks:
        return FindingState.BLOCKED
    if CheckOutcome.REVIEW_REQUIRED in outcomes or FindingState.REVIEW_REQUIRED in checks:
        return FindingState.REVIEW_REQUIRED
    if CheckOutcome.WARNING in outcomes or FindingState.WARNING in checks:
        return FindingState.WARNING
    return FindingState.NO_FINDING


def _highest_finding_state(states: list[FindingState]) -> FindingState:
    for state in (
        FindingState.BLOCKED,
        FindingState.REVIEW_REQUIRED,
        FindingState.WARNING,
    ):
        if state in states:
            return state
    return FindingState.NO_FINDING


def _finding_evidence_state(state: FindingState) -> EvidenceState:
    return {
        FindingState.BLOCKED: EvidenceState.ALERT,
        FindingState.REVIEW_REQUIRED: EvidenceState.UNKNOWN,
        FindingState.WARNING: EvidenceState.INFERRED,
        FindingState.NO_FINDING: EvidenceState.INFERRED,
    }[state]


def _numeric_state(
    *,
    citation_state: CitationState,
    record: EvidenceRecord | None,
    evidence_canonical: str | None,
    checks: list[ClaimCheckRecord],
) -> NumericCorrespondenceState:
    if citation_state is CitationState.NOT_CITED:
        return NumericCorrespondenceState.NOT_CITED
    if record is None or evidence_canonical is None:
        reason_codes = {check.reason_code for check in checks}
        if "numeric_source_not_scalar" in reason_codes:
            return NumericCorrespondenceState.SOURCE_NOT_SCALAR
        return NumericCorrespondenceState.SOURCE_UNAVAILABLE
    reason_codes = {check.reason_code for check in checks}
    for reason, state in (
        ("canonical_numeric_mismatch", NumericCorrespondenceState.CANONICAL_MISMATCH),
        ("unit_mismatch", NumericCorrespondenceState.UNIT_MISMATCH),
        ("rendered_numeric_mismatch", NumericCorrespondenceState.RENDERED_MISMATCH),
        ("numeric_source_not_scalar", NumericCorrespondenceState.SOURCE_NOT_SCALAR),
        ("numeric_source_unavailable", NumericCorrespondenceState.SOURCE_UNAVAILABLE),
    ):
        if reason in reason_codes:
            return state
    return NumericCorrespondenceState.EXACT


def _numeric_evidence_state(
    state: NumericCorrespondenceState,
    record: EvidenceRecord | None,
) -> EvidenceState:
    if state in {
        NumericCorrespondenceState.SOURCE_UNAVAILABLE,
        NumericCorrespondenceState.SOURCE_NOT_SCALAR,
    }:
        return EvidenceState.UNAVAILABLE
    if state is NumericCorrespondenceState.EXACT and record is not None:
        return record.evidence_state
    return EvidenceState.ALERT


def _evidence_ids(receipt_id: str, refs: list[str]) -> list[str]:
    return sorted({receipt_id, *(ref.split("@", 1)[0] for ref in refs)})


PUBLIC_VISUALIZATION_SCHEMA_MODELS = {
    CLAIM_VERIFIER_VISUALIZATION_DATA_SCHEMA_REF: ClaimVerifierVisualizationDataV1,
    P010_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF: P010VisualizationArtifactSet,
}
