from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
import hashlib
import re
from typing import Annotated, Any, Literal, Self

from pydantic import (
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.toolkit.contracts import EvidenceState, FrozenModel


SHA256_PATTERN = r"^[0-9a-f]{64}$"
EVIDENCE_REF_PATTERN = r"^evidence:[a-f0-9]{24}@[1-9][0-9]*$"
CLAIM_REF_PATTERN = r"^claim:[A-Za-z0-9._:-]+@[A-Za-z0-9._:-]+$"
PRODUCT_CASE_REF_PATTERN = r"^product-case:[A-Za-z0-9._:-]+@[A-Za-z0-9._:-]+$"
STATEMENT_REF_PATTERN = r"^statement:[A-Za-z0-9._:-]+@[A-Za-z0-9._:-]+$"
REPORT_REF_PATTERN = r"^report:[A-Za-z0-9._:-]+@[A-Za-z0-9._:-]+$"
DECIMAL_STRING_PATTERN = (
    r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$"
)
PLAIN_UNIT_PATTERN = r"^[^0-9\s\r\n](?:[^0-9\r\n]*[^0-9\s\r\n])?$"
MAX_DECIMAL_DIGITS = 128
MAX_DECIMAL_ADJUSTED_EXPONENT = 128
EXTERNAL_BENCHMARK_ID = "P0-10-BENCHMARK-v0.1"
EXTERNAL_BENCHMARK_SHA256 = (
    "908da7e8c8141e5f44e230315134d53fb63dbc6856b37e06a3b227fe2af51baa"
)
FREE_MARKUP = re.compile(
    r"(?:^|\s)(?:#{1,6}|[-+*>]|\d+[.)])\s"
    r"|\[[^]\n]+\]\([^\n)]+\)"
    r"|(?:\*\*|__|~~|`)"
    r"|(?<!\w)[*_](?=\S)"
    r"|<\s*/?\s*[A-Za-z!][^>]*>"
)

EvidenceRef = Annotated[str, Field(pattern=EVIDENCE_REF_PATTERN)]
StatementRef = Annotated[str, Field(pattern=STATEMENT_REF_PATTERN)]


class ReportAudience(StrEnum):
    INTERNAL_RESEARCH = "internal_research"
    PUBLIC_CANDIDATE = "public_candidate"


class ReportLanguage(StrEnum):
    ZH = "zh"
    EN = "en"
    MIXED = "mixed"


class AuthoringChannel(StrEnum):
    DETERMINISTIC_RENDERER = "deterministic_renderer"
    HUMAN_EDIT = "human_edit"
    IMPORTED_DRAFT = "imported_draft"


class ClaimType(StrEnum):
    MEASUREMENT = "measurement_claim"
    DOMAIN_INTERPRETATION = "domain_interpretation"
    DESCRIPTIVE_COMPARISON = "descriptive_comparison"
    INFERENTIAL_COMPARISON = "inferential_comparison"
    AVAILABILITY = "availability_claim"
    ALERT = "alert_claim"
    PRIOR_OR_LITERATURE = "prior_or_literature_claim"
    METHOD = "method_claim"
    RECOMMENDATION = "recommendation_hypothesis"
    GRAFT_RETROSPECTIVE = "graft_retrospective_claim"
    POLICY_OR_BOUNDARY = "policy_or_boundary_statement"
    VISUALIZATION_CAPTION = "visualization_caption"


class ComparisonMode(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    DESCRIPTIVE_ONLY = "descriptive_only"
    INFERENTIAL = "inferential"


class ReleaseState(StrEnum):
    NOT_ASSESSED = "not_assessed"
    RELEASE_BLOCKED = "release_blocked"
    REVIEW_REQUIRED = "review_required"
    VERIFIED_WITH_WARNINGS = "verified_with_warnings"
    VERIFIED = "verified"


class PublicExportEligibility(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    NOT_ASSESSED = "not_assessed"


class CheckSeverity(StrEnum):
    HARD_BLOCKER = "hard_blocker"
    REVIEW = "review"
    WARNING = "warning"


class CheckOutcome(StrEnum):
    BLOCKED = "blocked"
    REVIEW_REQUIRED = "review_required"
    WARNING = "warning"


class ValueBinding(FrozenModel):
    binding_id: str = Field(pattern=r"^binding:[A-Za-z0-9._:-]+$")
    source_evidence_ref: EvidenceRef
    source_field: Literal[
        "value", "numerator", "denominator", "interval_lower", "interval_upper"
    ]
    canonical_numeric_string: str = Field(
        min_length=1,
        max_length=256,
        pattern=DECIMAL_STRING_PATTERN,
    )
    raw_unit: str | None = Field(default=None, pattern=PLAIN_UNIT_PATTERN)
    text_span: tuple[StrictInt, StrictInt]

    @field_validator("canonical_numeric_string")
    @classmethod
    def decimal_string_is_finite(cls, value: str) -> str:
        try:
            number = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("numeric binding requires a decimal string") from exc
        if not number.is_finite():
            raise ValueError("numeric binding requires a finite decimal string")
        if (
            len(number.as_tuple().digits) > MAX_DECIMAL_DIGITS
            or abs(number.adjusted()) > MAX_DECIMAL_ADJUSTED_EXPONENT
        ):
            raise ValueError("numeric binding is outside the supported decimal range")
        return value

    @field_validator("text_span")
    @classmethod
    def text_span_is_ordered(
        cls, value: tuple[int, int]
    ) -> tuple[int, int]:
        if value[0] < 0 or value[1] <= value[0]:
            raise ValueError("text_span must be a non-empty forward range")
        return value


class ClaimBlock(FrozenModel):
    claim_id: str = Field(pattern=r"^claim-block:[A-Za-z0-9._:-]+$")
    claim_version: str = Field(min_length=1)
    claim_ref: str = Field(pattern=CLAIM_REF_PATTERN)
    product_case_ref: str = Field(pattern=PRODUCT_CASE_REF_PATTERN)
    claim_type: ClaimType
    text: str = Field(min_length=1)
    language: ReportLanguage
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    statement_refs: list[StatementRef] = Field(default_factory=list)
    value_bindings: list[ValueBinding] = Field(default_factory=list)
    reported_evidence_state: EvidenceState | None = None
    comparison_mode: ComparisonMode = ComparisonMode.NOT_APPLICABLE
    authoring_channel: AuthoringChannel

    @field_validator("text")
    @classmethod
    def text_is_plain_structured_content(cls, value: str) -> str:
        if FREE_MARKUP.search(value) or any(
            marker in value for marker in ("\n", "\r")
        ):
            raise ValueError("claim text must be one plain structured paragraph")
        return value

    @field_validator("evidence_refs", "statement_refs")
    @classmethod
    def refs_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("claim references must be unique")
        return value

    @field_validator("value_bindings")
    @classmethod
    def bindings_are_unique(cls, value: list[ValueBinding]) -> list[ValueBinding]:
        ids = [item.binding_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("value bindings must be unique")
        spans = sorted(item.text_span for item in value)
        if any(left[1] > right[0] for left, right in zip(spans, spans[1:])):
            raise ValueError("value binding text spans must not overlap")
        return value

    @model_validator(mode="after")
    def binding_spans_are_within_claim_text(self) -> Self:
        if any(binding.text_span[1] > len(self.text) for binding in self.value_bindings):
            raise ValueError("value binding text spans must be within claim text")
        return self


class ReportDraft(FrozenModel):
    object_version: Literal["0.1.0"]
    report_id: str = Field(pattern=r"^report:[A-Za-z0-9._:-]+$")
    report_version: str = Field(pattern=r"^[A-Za-z0-9._:-]+$")
    content_hash: str = Field(pattern=SHA256_PATTERN)
    audience: ReportAudience
    language: ReportLanguage
    evidence_record_set_ref: str = Field(min_length=1)
    claim_policy_ref: str = Field(min_length=1)
    statement_registry_ref: str = Field(min_length=1)
    claim_blocks: list[ClaimBlock] = Field(min_length=1)
    renderer_id: str = Field(min_length=1)
    renderer_version: str = Field(min_length=1)
    authoring_channel: AuthoringChannel
    created_at: datetime

    @field_validator("claim_blocks")
    @classmethod
    def claims_are_unique(cls, value: list[ClaimBlock]) -> list[ClaimBlock]:
        ids = [item.claim_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("claim blocks must be unique")
        return value

    @model_validator(mode="after")
    def content_hash_matches(self) -> Self:
        expected = report_content_hash(self.model_dump(mode="json"))
        if self.content_hash != expected:
            raise ValueError("report content_hash does not match the structured report")
        return self

    @property
    def ref(self) -> str:
        return f"{self.report_id}@{self.report_version}"


def report_content_hash(payload: dict[str, Any]) -> str:
    content = dict(payload)
    content.pop("content_hash", None)
    return hashlib.sha256(canonical_json_bytes(content)).hexdigest()


class ClaimTypePolicy(FrozenModel):
    claim_type: ClaimType
    requires_evidence: StrictBool
    allowed_evidence_states: list[EvidenceState]
    allowed_comparison_modes: list[ComparisonMode]

    @field_validator("allowed_evidence_states", "allowed_comparison_modes")
    @classmethod
    def values_are_unique(cls, value: list[Any]) -> list[Any]:
        if len(value) != len(set(value)):
            raise ValueError("policy enum lists must be unique")
        return value


class TextRule(FrozenModel):
    rule_id: str = Field(pattern=r"^rule:[A-Za-z0-9._:-]+$")
    version: str = Field(min_length=1)
    languages: list[ReportLanguage] = Field(min_length=1)
    pattern: str = Field(min_length=1, max_length=500)
    severity: CheckSeverity
    reason_code: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    except_statement_refs: list[str] = Field(default_factory=list)


class ClaimPolicySpec(FrozenModel):
    object_version: Literal["0.1.0"]
    policy_id: str = Field(pattern=r"^claim-policy:[A-Za-z0-9._:-]+$")
    policy_version: str = Field(min_length=1)
    active: StrictBool
    claim_type_policies: list[ClaimTypePolicy] = Field(min_length=1)
    text_rules: list[TextRule]
    descriptive_forbidden_patterns: list[str]

    @field_validator("claim_type_policies")
    @classmethod
    def claim_policies_are_unique(
        cls, value: list[ClaimTypePolicy]
    ) -> list[ClaimTypePolicy]:
        kinds = [item.claim_type for item in value]
        if len(kinds) != len(set(kinds)):
            raise ValueError("claim type policies must be unique")
        return value

    @field_validator("text_rules")
    @classmethod
    def rules_are_unique(cls, value: list[TextRule]) -> list[TextRule]:
        ids = [(item.rule_id, item.version) for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("text rules must be unique")
        return value

    @property
    def ref(self) -> str:
        return f"{self.policy_id}@{self.policy_version}"


class RegisteredStatement(FrozenModel):
    statement_id: str = Field(pattern=r"^statement:[A-Za-z0-9._:-]+$")
    statement_version: str = Field(min_length=1)
    texts: dict[ReportLanguage, str]
    allowed_claim_types: list[ClaimType]
    approved: StrictBool

    @field_validator("texts")
    @classmethod
    def statement_texts_are_nonempty(
        cls, value: dict[ReportLanguage, str]
    ) -> dict[ReportLanguage, str]:
        if not value or any(not text.strip() for text in value.values()):
            raise ValueError("registered statements require non-empty text")
        return value

    @property
    def ref(self) -> str:
        return f"{self.statement_id}@{self.statement_version}"


class StatementRegistry(FrozenModel):
    object_version: Literal["0.1.0"]
    registry_id: Literal["BRIDGE-STATEMENT-REGISTRY-v0.1"]
    registry_version: Literal["0.1.0"]
    statements: list[RegisteredStatement]

    @field_validator("statements")
    @classmethod
    def statements_are_unique(
        cls, value: list[RegisteredStatement]
    ) -> list[RegisteredStatement]:
        refs = [item.ref for item in value]
        if len(refs) != len(set(refs)):
            raise ValueError("registered statements must be unique")
        return value

    @property
    def ref(self) -> str:
        return f"{self.registry_id}@{self.registry_version}"


class ClaimVerifierReleaseContract(FrozenModel):
    contract_id: Literal["P0-10-RELEASE-CONTRACT-v0.1"]
    contract_version: Literal["0.1.0"]
    renderer_id: Literal["BRIDGE-REPORT-DRAFT-RENDERER-v0.1"]
    renderer_version: Literal["0.1.0"]
    measurement_language: Literal["en"]
    claim_policy: ClaimPolicySpec
    statement_registry: StatementRegistry

    @model_validator(mode="after")
    def authority_is_active(self) -> Self:
        if not self.claim_policy.active:
            raise ValueError("release contract requires an active claim policy")
        return self


def _check_record_json_schema(schema: dict[str, Any]) -> None:
    pairs = {
        "blocked": "hard_blocker",
        "review_required": "review",
        "warning": "warning",
    }
    schema["allOf"] = [
        {
            "if": {
                "properties": {"outcome": {"const": outcome}},
                "required": ["outcome"],
            },
            "then": {"properties": {"severity": {"const": severity}}},
        }
        for outcome, severity in pairs.items()
    ]


class ClaimCheckRecord(FrozenModel):
    model_config = ConfigDict(json_schema_extra=_check_record_json_schema)

    check_id: str = Field(pattern=r"^check:[a-f0-9]{16}$")
    claim_id: str = Field(pattern=r"^claim-block:[A-Za-z0-9._:-]+$")
    rule_id: str = Field(pattern=r"^rule:[A-Za-z0-9._:-]+$")
    rule_version: str = Field(min_length=1)
    outcome: CheckOutcome
    severity: CheckSeverity
    reason_code: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    text_span: tuple[StrictInt, StrictInt] | None = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    statement_ref: StatementRef | None = None

    @field_validator("evidence_refs")
    @classmethod
    def evidence_refs_are_unique_and_sorted(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("check evidence_refs must be unique and sorted")
        return value

    @field_validator("text_span")
    @classmethod
    def check_text_span_is_ordered(
        cls, value: tuple[int, int] | None
    ) -> tuple[int, int] | None:
        if value is not None and (value[0] < 0 or value[1] <= value[0]):
            raise ValueError("check text_span must be a non-empty forward range")
        return value

    @model_validator(mode="after")
    def outcome_matches_severity(self) -> Self:
        expected = {
            CheckOutcome.BLOCKED: CheckSeverity.HARD_BLOCKER,
            CheckOutcome.REVIEW_REQUIRED: CheckSeverity.REVIEW,
            CheckOutcome.WARNING: CheckSeverity.WARNING,
        }[self.outcome]
        if self.severity is not expected:
            raise ValueError("check outcome does not match severity")
        return self


def _outcome_schema(*outcomes: str) -> dict[str, Any]:
    value = {"const": outcomes[0]} if len(outcomes) == 1 else {"enum": list(outcomes)}
    return {"properties": {"outcome": value}, "required": ["outcome"]}


def _state_rule(
    state: str,
    checks: dict[str, Any],
    eligibility: str | list[str],
) -> dict[str, Any]:
    eligibility_schema = (
        {"const": eligibility}
        if isinstance(eligibility, str)
        else {"enum": eligibility}
    )
    return {
        "if": {
            "properties": {"release_state": {"const": state}},
            "required": ["release_state"],
        },
        "then": {
            "properties": {
                "check_records": checks,
                "public_export_eligibility": eligibility_schema,
            }
        },
    }


def _claim_verification_json_schema(schema: dict[str, Any]) -> None:
    schema["allOf"] = [
        _state_rule("not_assessed", {"maxItems": 0}, "not_assessed"),
        _state_rule(
            "release_blocked",
            {"contains": _outcome_schema("blocked")},
            "ineligible",
        ),
        _state_rule(
            "review_required",
            {
                "contains": _outcome_schema("review_required"),
                "not": {"contains": _outcome_schema("blocked")},
            },
            "ineligible",
        ),
        _state_rule(
            "verified_with_warnings",
            {
                "contains": _outcome_schema("warning"),
                "not": {
                    "contains": _outcome_schema("blocked", "review_required")
                },
            },
            ["eligible", "ineligible"],
        ),
        _state_rule(
            "verified",
            {
                "not": {
                    "contains": _outcome_schema(
                        "blocked", "review_required", "warning"
                    )
                }
            },
            ["eligible", "ineligible"],
        ),
        {
            "if": {
                "properties": {
                    "report_audience": {"const": "public_candidate"},
                    "release_state": {
                        "enum": ["verified", "verified_with_warnings"]
                    },
                },
                "required": ["report_audience", "release_state"],
            },
            "then": {
                "properties": {
                    "public_export_eligibility": {"const": "eligible"}
                }
            },
        },
        {
            "if": {
                "properties": {
                    "public_export_eligibility": {"const": "eligible"}
                },
                "required": ["public_export_eligibility"],
            },
            "then": {
                "properties": {
                    "report_audience": {"const": "public_candidate"},
                    "release_state": {
                        "enum": ["verified", "verified_with_warnings"]
                    },
                }
            },
        },
        {
            "if": {
                "properties": {
                    "report_audience": {"const": "internal_research"},
                    "release_state": {"not": {"const": "not_assessed"}},
                },
                "required": ["report_audience", "release_state"],
            },
            "then": {
                "properties": {
                    "public_export_eligibility": {"const": "ineligible"}
                }
            },
        },
    ]


class ClaimVerificationResult(FrozenModel):
    model_config = ConfigDict(json_schema_extra=_claim_verification_json_schema)

    object_version: Literal["0.1.0"]
    verification_id: str = Field(pattern=r"^claim-verification:[a-f0-9]{16}$")
    verifier_version: Literal["0.1.0"]
    benchmark_id: Literal[EXTERNAL_BENCHMARK_ID]
    benchmark_sha256: Literal[EXTERNAL_BENCHMARK_SHA256]
    release_contract_id: Literal["P0-10-RELEASE-CONTRACT-v0.1"]
    release_contract_sha256: Literal[
        "c8a9237652cba4e6b3eb1c4f4215437980f0f480a0944d232abddeef5c4236c8"
    ]
    report_draft_ref: str = Field(pattern=REPORT_REF_PATTERN)
    report_content_hash: str = Field(pattern=SHA256_PATTERN)
    report_audience: ReportAudience
    evidence_graph_id: str = Field(min_length=1)
    evidence_graph_version: StrictInt = Field(ge=1)
    evidence_graph_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    claim_policy_ref: Literal["claim-policy:p0-10-public@0.1.0"]
    statement_registry_ref: Literal[
        "BRIDGE-STATEMENT-REGISTRY-v0.1@0.1.0"
    ]
    release_state: ReleaseState
    check_records: list[ClaimCheckRecord] = Field(
        json_schema_extra={"uniqueItems": True}
    )
    public_export_eligibility: PublicExportEligibility

    @model_validator(mode="after")
    def state_matches_checks(self) -> Self:
        check_ids = [record.check_id for record in self.check_records]
        if check_ids != sorted(set(check_ids)):
            raise ValueError("check records must have unique sorted IDs")
        outcomes = {record.outcome for record in self.check_records}
        if self.release_state is ReleaseState.NOT_ASSESSED:
            if self.check_records or (
                self.public_export_eligibility
                is not PublicExportEligibility.NOT_ASSESSED
            ):
                raise ValueError(
                    "not_assessed requires no checks and not_assessed export eligibility"
                )
            return self
        expected = (
            ReleaseState.RELEASE_BLOCKED
            if CheckOutcome.BLOCKED in outcomes
            else ReleaseState.REVIEW_REQUIRED
            if CheckOutcome.REVIEW_REQUIRED in outcomes
            else ReleaseState.VERIFIED_WITH_WARNINGS
            if CheckOutcome.WARNING in outcomes
            else ReleaseState.VERIFIED
        )
        if self.release_state is not expected:
            raise ValueError("release_state does not match check outcomes")
        if (
            expected in {ReleaseState.RELEASE_BLOCKED, ReleaseState.REVIEW_REQUIRED}
            and self.public_export_eligibility is not PublicExportEligibility.INELIGIBLE
        ):
            raise ValueError("blocked or review-required results are not export eligible")
        if self.public_export_eligibility is PublicExportEligibility.NOT_ASSESSED:
            raise ValueError("assessed results cannot have not_assessed export eligibility")
        eligible = self.release_state in {
            ReleaseState.VERIFIED,
            ReleaseState.VERIFIED_WITH_WARNINGS,
        } and self.report_audience is ReportAudience.PUBLIC_CANDIDATE
        expected_eligibility = (
            PublicExportEligibility.ELIGIBLE
            if eligible
            else PublicExportEligibility.INELIGIBLE
        )
        if self.public_export_eligibility is not expected_eligibility:
            raise ValueError(
                "export eligibility does not match report audience and release state"
            )
        return self

    def matches_report_draft(self, report: ReportDraft) -> bool:
        return (
            self.report_draft_ref == report.ref
            and self.report_content_hash == report.content_hash
            and self.report_audience is report.audience
        )


PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/report-draft/v0.1": ReportDraft,
    "bridge://schemas/claim-policy-spec/v0.1": ClaimPolicySpec,
    "bridge://schemas/statement-registry/v0.1": StatementRegistry,
    "bridge://schemas/claim-verification-result/v0.1": ClaimVerificationResult,
}
