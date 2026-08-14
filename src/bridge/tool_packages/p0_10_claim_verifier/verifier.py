from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP
import hashlib
from typing import Iterable

from jinja2 import Environment, StrictUndefined
import regex

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    contains_unsafe_reference,
    EvidenceApplicability,
    EvidenceLifecycleState,
    EvidenceRecord,
    EvidenceRecordSet,
    EvidenceTier,
)
from bridge.tool_packages.p0_10_claim_verifier.models import (
    CheckOutcome,
    CheckSeverity,
    ClaimBlock,
    ClaimCheckRecord,
    ClaimPolicySpec,
    ClaimType,
    ClaimVerificationResult,
    ClaimVerifierRunResult,
    ComparisonMode,
    HumanReviewDecision,
    NumericFormatSpec,
    PublicExportEligibility,
    RegisteredStatement,
    ReleaseState,
    ReportAudience,
    ReportDraft,
    ReportLanguage,
    StatementRegistry,
    ValueBinding,
    VerifiedClaim,
    VerifiedReport,
)


VERIFIER_VERSION = "0.1.0"
NUMERIC_TOKEN = regex.compile(
    r"(?<![\p{L}\p{N}_])[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?%?(?![\p{L}\p{N}_])",
    regex.VERSION1,
)
REPORT_TEMPLATE = Environment(
    autoescape=False,
    undefined=StrictUndefined,
    keep_trailing_newline=True,
).from_string("{% for claim in claims %}{{ claim.text }}{% if not loop.last %}\n\n{% endif %}{% endfor %}\n")


def verify_report(
    *,
    report: ReportDraft,
    evidence_set: EvidenceRecordSet,
    policy: ClaimPolicySpec,
    statements: StatementRegistry,
    benchmark_id: str,
    benchmark_sha256: str,
    run_id: str,
) -> ClaimVerifierRunResult:
    verification_id = f"claim-verification:{run_id.removeprefix('run-')}"
    if not policy.active:
        verification = ClaimVerificationResult(
            object_version="0.1.0",
            verification_id=verification_id,
            verifier_version=VERIFIER_VERSION,
            benchmark_id=benchmark_id,
            benchmark_sha256=benchmark_sha256,
            report_draft_ref=report.ref,
            report_content_hash=report.content_hash,
            claim_policy_ref=policy.ref,
            statement_registry_ref=statements.ref,
            release_state=ReleaseState.NOT_ASSESSED,
            blocker_count=0,
            review_count=0,
            warning_count=0,
            check_records=[],
            claim_evidence_map={claim.claim_id: claim.evidence_refs for claim in report.claim_blocks},
            public_export_eligibility=PublicExportEligibility.NOT_ASSESSED,
        )
        return ClaimVerifierRunResult(
            object_version="0.1.0",
            benchmark_id=benchmark_id,
            benchmark_sha256=benchmark_sha256,
            verification=verification,
            verified_report=None,
        )

    evidence = {record.ref: record for record in evidence_set.records}
    statement_by_ref = {statement.ref: statement for statement in statements.statements}
    claim_policy = {item.claim_type: item for item in policy.claim_type_policies}
    review_decisions = {
        (item.claim_id, item.rule_id): item for item in report.human_review_decisions
    }
    checks: list[ClaimCheckRecord] = []
    for claim in report.claim_blocks:
        if contains_unsafe_reference(claim.model_dump(mode="json")):
            checks.append(
                _block(claim, "rule:private-content", "unsafe_scientific_reference")
            )
        resolved = [evidence[ref] for ref in claim.evidence_refs if ref in evidence]
        checks.extend(
            _check_claim_contract(
                claim,
                resolved,
                evidence,
                statement_by_ref,
                claim_policy,
            )
        )
        checks.extend(_check_value_bindings(claim, evidence, policy))
        checks.extend(_check_comparison_scope(claim, policy))
        checks.extend(
            _check_text_rules(
                claim,
                policy,
                statement_by_ref,
                review_decisions,
            )
        )

    blocker_count = sum(item.outcome is CheckOutcome.BLOCKED for item in checks)
    review_count = sum(
        item.outcome is CheckOutcome.REVIEW_REQUIRED for item in checks
    )
    warning_count = sum(item.outcome is CheckOutcome.WARNING for item in checks)
    if blocker_count:
        release_state = ReleaseState.RELEASE_BLOCKED
    elif review_count:
        release_state = ReleaseState.REVIEW_REQUIRED
    elif warning_count:
        release_state = ReleaseState.VERIFIED_WITH_WARNINGS
    else:
        release_state = ReleaseState.VERIFIED

    verified_report: VerifiedReport | None = None
    verified_report_ref: str | None = None
    if release_state in {ReleaseState.VERIFIED, ReleaseState.VERIFIED_WITH_WARNINGS}:
        rendered = REPORT_TEMPLATE.render(claims=report.claim_blocks)
        verified_report_id = f"verified-report:{run_id.removeprefix('run-')}"
        verified_report_ref = f"{verified_report_id}@0.1.0"
        verified_report = VerifiedReport(
            object_version="0.1.0",
            verified_report_id=verified_report_id,
            report_draft_ref=report.ref,
            report_content_hash=report.content_hash,
            verification_id=verification_id,
            claim_policy_ref=policy.ref,
            statement_registry_ref=statements.ref,
            claims=[
                VerifiedClaim(
                    claim_id=claim.claim_id,
                    text=claim.text,
                    evidence_refs=claim.evidence_refs,
                    statement_refs=claim.statement_refs,
                )
                for claim in report.claim_blocks
            ],
            rendered_markdown=rendered,
            rendered_sha256=hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
        )

    verification = ClaimVerificationResult(
        object_version="0.1.0",
        verification_id=verification_id,
        verifier_version=VERIFIER_VERSION,
        benchmark_id=benchmark_id,
        benchmark_sha256=benchmark_sha256,
        report_draft_ref=report.ref,
        report_content_hash=report.content_hash,
        claim_policy_ref=policy.ref,
        statement_registry_ref=statements.ref,
        release_state=release_state,
        blocker_count=blocker_count,
        review_count=review_count,
        warning_count=warning_count,
        check_records=sorted(checks, key=lambda item: item.check_id),
        claim_evidence_map={claim.claim_id: claim.evidence_refs for claim in report.claim_blocks},
        public_export_eligibility=(
            PublicExportEligibility.ELIGIBLE
            if report.audience is ReportAudience.PUBLIC_CANDIDATE
            and release_state in {ReleaseState.VERIFIED, ReleaseState.VERIFIED_WITH_WARNINGS}
            else PublicExportEligibility.INELIGIBLE
        ),
        verified_report_ref=verified_report_ref,
    )
    return ClaimVerifierRunResult(
        object_version="0.1.0",
        benchmark_id=benchmark_id,
        benchmark_sha256=benchmark_sha256,
        verification=verification,
        verified_report=verified_report,
    )


def _check_claim_contract(
    claim: ClaimBlock,
    resolved: list[EvidenceRecord],
    evidence: dict[str, EvidenceRecord],
    statements: dict[str, RegisteredStatement],
    policies: dict[ClaimType, object],
) -> list[ClaimCheckRecord]:
    checks: list[ClaimCheckRecord] = []
    policy = policies.get(claim.claim_type)
    if policy is None:
        checks.append(_block(claim, "rule:claim-type-policy", "claim_type_policy_missing"))
        return checks
    if policy.requires_evidence and not claim.evidence_refs:
        checks.append(_block(claim, "rule:evidence-binding", "claim_evidence_required"))
    for ref in claim.evidence_refs:
        record = evidence.get(ref)
        if record is None:
            checks.append(
                _block(claim, "rule:evidence-binding", "evidence_ref_not_found", evidence_refs=[ref])
            )
            continue
        if record.lifecycle_state is not EvidenceLifecycleState.ACTIVE:
            checks.append(
                _block(claim, "rule:evidence-lifecycle", "evidence_not_active", evidence_refs=[ref])
            )
        if record.applicability is not EvidenceApplicability.APPLICABLE:
            checks.append(
                _block(claim, "rule:evidence-applicability", "evidence_not_applicable", evidence_refs=[ref])
            )
        if claim.intended_release_tier == "formal" and record.evidence_tier is not EvidenceTier.FORMAL:
            checks.append(
                _block(
                    claim,
                    "rule:evidence-tier",
                    "nonformal_evidence_used_for_formal_claim",
                    evidence_refs=[ref],
                )
            )
        if record.evidence_state not in policy.allowed_evidence_states:
            checks.append(
                _block(claim, "rule:evidence-state-policy", "evidence_state_not_allowed", evidence_refs=[ref])
            )
    if resolved:
        states = {item.evidence_state for item in resolved}
        if len(states) > 1:
            checks.append(
                _block(claim, "rule:evidence-state", "mixed_evidence_states_require_separate_claims")
            )
        elif claim.reported_evidence_state is None:
            checks.append(_block(claim, "rule:evidence-state", "reported_evidence_state_required"))
        elif claim.reported_evidence_state not in states:
            checks.append(_block(claim, "rule:evidence-state", "evidence_state_mismatch"))
        product_refs = {item.product_case_ref.ref for item in resolved}
        if len(product_refs) > 1:
            checks.append(_block(claim, "rule:case-scope", "cross_case_evidence_forbidden"))
    if claim.comparison_mode not in policy.allowed_comparison_modes:
        checks.append(_block(claim, "rule:comparison-mode", "comparison_mode_not_allowed"))
    checks.extend(_check_statement_bindings(claim, statements))
    return checks


def _check_statement_bindings(
    claim: ClaimBlock, statements: dict[str, RegisteredStatement]
) -> list[ClaimCheckRecord]:
    checks: list[ClaimCheckRecord] = []
    resolved: list[RegisteredStatement] = []
    for ref in claim.statement_refs:
        statement = statements.get(ref)
        if statement is None:
            checks.append(_block(claim, "rule:statement-binding", "statement_ref_not_found"))
            continue
        resolved.append(statement)
        if not statement.approved:
            checks.append(_block(claim, "rule:statement-binding", "statement_not_approved"))
        if claim.claim_type not in statement.allowed_claim_types:
            checks.append(_block(claim, "rule:statement-binding", "statement_claim_type_mismatch"))
    if claim.claim_type is ClaimType.POLICY_OR_BOUNDARY:
        if len(resolved) != 1:
            checks.append(_block(claim, "rule:statement-binding", "exactly_one_statement_required"))
        elif resolved[0].texts.get(claim.language) != claim.text:
            checks.append(_block(claim, "rule:statement-text", "registered_statement_text_mismatch"))
    return checks


def _check_value_bindings(
    claim: ClaimBlock,
    evidence: dict[str, EvidenceRecord],
    policy: ClaimPolicySpec,
) -> list[ClaimCheckRecord]:
    checks: list[ClaimCheckRecord] = []
    for binding in claim.value_bindings:
        record = evidence.get(binding.source_evidence_ref)
        if binding.source_evidence_ref not in claim.evidence_refs:
            checks.append(_block(claim, "rule:value-binding", "binding_evidence_not_cited"))
            continue
        if record is None:
            continue
        reason = _numeric_binding_reason(binding, record)
        if reason is not None:
            checks.append(
                _block(
                    claim,
                    "rule:numeric-fidelity",
                    reason,
                    evidence_refs=[binding.source_evidence_ref],
                )
            )
        if binding.rendered_value not in claim.text:
            checks.append(_block(claim, "rule:rendered-value", "rendered_value_not_in_claim"))
    if (
        policy.require_all_numeric_tokens_bound
        and claim.claim_type is not ClaimType.POLICY_OR_BOUNDARY
    ):
        covered = _binding_spans(claim)
        for match in NUMERIC_TOKEN.finditer(claim.text, timeout=0.05):
            if not any(start <= match.start() and match.end() <= end for start, end in covered):
                checks.append(
                    _block(
                        claim,
                        "rule:numeric-binding-completeness",
                        "unbound_numeric_token",
                        text_span=(match.start(), match.end()),
                    )
                )
    return checks


def _numeric_binding_reason(
    binding: ValueBinding, evidence: EvidenceRecord
) -> str | None:
    source = getattr(evidence, binding.source_field)
    if source is None or isinstance(source, bool):
        return "numeric_source_unavailable"
    try:
        source_number = Decimal(str(source))
    except Exception:
        return "numeric_source_not_scalar"
    if Decimal(binding.canonical_numeric_string) != source_number:
        return "canonical_numeric_mismatch"
    if binding.raw_unit != evidence.unit:
        return "unit_mismatch"
    if evidence.denominator is None:
        if binding.denominator_numeric_string is not None:
            return "denominator_mismatch"
    elif binding.denominator_numeric_string is None or Decimal(
        binding.denominator_numeric_string
    ) != Decimal(str(evidence.denominator)):
        return "denominator_mismatch"
    if evidence.interval is None:
        if binding.interval_lower_numeric_string is not None:
            return "interval_mismatch"
    elif (
        binding.interval_lower_numeric_string is None
        or Decimal(binding.interval_lower_numeric_string) != Decimal(str(evidence.interval.lower))
        or Decimal(binding.interval_upper_numeric_string) != Decimal(str(evidence.interval.upper))
    ):
        return "interval_mismatch"
    if binding.rendered_value != _render_decimal(source_number, binding.format_spec):
        return "rendered_numeric_mismatch"
    return None


def _render_decimal(value: Decimal, spec: NumericFormatSpec) -> str:
    if spec.scale == "percent":
        value *= Decimal(100)
    quantum = Decimal(1).scaleb(-spec.decimal_places)
    rounding = ROUND_HALF_EVEN if spec.rounding == "half_even" else ROUND_HALF_UP
    rendered = format(value.quantize(quantum, rounding=rounding), f".{spec.decimal_places}f")
    return rendered + spec.suffix


def _binding_spans(claim: ClaimBlock) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for binding in claim.value_bindings:
        start = 0
        while True:
            start = claim.text.find(binding.rendered_value, start)
            if start < 0:
                break
            end = start + len(binding.rendered_value)
            spans.append((start, end))
            start = end
    return spans


def _check_comparison_scope(
    claim: ClaimBlock, policy: ClaimPolicySpec
) -> list[ClaimCheckRecord]:
    checks: list[ClaimCheckRecord] = []
    if claim.claim_type is ClaimType.DESCRIPTIVE_COMPARISON and claim.comparison_mode is not ComparisonMode.DESCRIPTIVE_ONLY:
        checks.append(_block(claim, "rule:comparison-contract", "descriptive_claim_mode_mismatch"))
    if claim.claim_type is ClaimType.INFERENTIAL_COMPARISON and claim.comparison_mode is not ComparisonMode.INFERENTIAL:
        checks.append(_block(claim, "rule:comparison-contract", "inferential_claim_mode_mismatch"))
    if claim.comparison_mode is ComparisonMode.DESCRIPTIVE_ONLY:
        for pattern in policy.descriptive_forbidden_patterns:
            try:
                match = regex.search(pattern, claim.text, regex.IGNORECASE | regex.VERSION1, timeout=0.05)
            except (regex.error, TimeoutError):
                checks.append(_block(claim, "rule:descriptive-scope", "policy_pattern_invalid"))
                continue
            if match is not None:
                checks.append(
                    _block(
                        claim,
                        "rule:descriptive-scope",
                        "inferential_language_in_descriptive_claim",
                        text_span=(match.start(), match.end()),
                    )
                )
    return checks


def _check_text_rules(
    claim: ClaimBlock,
    policy: ClaimPolicySpec,
    statements: dict[str, RegisteredStatement],
    decisions: dict[tuple[str, str], HumanReviewDecision],
) -> list[ClaimCheckRecord]:
    checks: list[ClaimCheckRecord] = []
    for rule in policy.text_rules:
        if claim.language not in rule.languages and ReportLanguage.MIXED not in rule.languages:
            continue
        if _rule_exception_applies(claim, rule.except_statement_refs, statements):
            continue
        try:
            matches = list(
                regex.finditer(
                    rule.pattern,
                    claim.text,
                    regex.IGNORECASE | regex.VERSION1,
                    timeout=0.05,
                )
            )
        except (regex.error, TimeoutError):
            checks.append(_block(claim, rule.rule_id, "policy_pattern_invalid", rule.version))
            continue
        for match in matches:
            decision = decisions.get((claim.claim_id, rule.rule_id))
            checks.append(
                _text_rule_record(
                    claim,
                    rule.rule_id,
                    rule.version,
                    rule.reason_code,
                    rule.severity,
                    (match.start(), match.end()),
                    decision,
                    policy.authorized_reviewer_roles,
                )
            )
    return checks


def _rule_exception_applies(
    claim: ClaimBlock,
    exception_refs: Iterable[str],
    statements: dict[str, RegisteredStatement],
) -> bool:
    for ref in set(claim.statement_refs).intersection(exception_refs):
        statement = statements.get(ref)
        if statement is not None and statement.approved and statement.texts.get(claim.language) == claim.text:
            return True
    return False


def _text_rule_record(
    claim: ClaimBlock,
    rule_id: str,
    rule_version: str,
    reason_code: str,
    severity: CheckSeverity,
    text_span: tuple[int, int],
    decision: HumanReviewDecision | None,
    authorized_roles: list[str],
) -> ClaimCheckRecord:
    outcome = {
        CheckSeverity.HARD_BLOCKER: CheckOutcome.BLOCKED,
        CheckSeverity.REVIEW: CheckOutcome.REVIEW_REQUIRED,
        CheckSeverity.WARNING: CheckOutcome.WARNING,
    }[severity]
    review_ref: str | None = None
    detail = reason_code
    if severity is CheckSeverity.REVIEW and decision is not None:
        review_ref = decision.reviewer_ref
        if decision.reviewer_role not in authorized_roles:
            detail = "reviewer_role_not_authorized"
        elif decision.decision == "approved":
            outcome = CheckOutcome.CLEARED_BY_REVIEW
            detail = decision.reason
        else:
            outcome = CheckOutcome.BLOCKED
            severity = CheckSeverity.HARD_BLOCKER
            detail = "human_review_rejected"
    return _record(
        claim,
        rule_id,
        rule_version,
        outcome,
        severity,
        reason_code,
        text_span=text_span,
        detail=detail,
        human_review_ref=review_ref,
    )


def _block(
    claim: ClaimBlock,
    rule_id: str,
    reason_code: str,
    rule_version: str = "0.1.0",
    *,
    text_span: tuple[int, int] | None = None,
    evidence_refs: list[str] | None = None,
) -> ClaimCheckRecord:
    return _record(
        claim,
        rule_id,
        rule_version,
        CheckOutcome.BLOCKED,
        CheckSeverity.HARD_BLOCKER,
        reason_code,
        text_span=text_span,
        evidence_refs=evidence_refs,
        detail=reason_code,
    )


def _record(
    claim: ClaimBlock,
    rule_id: str,
    rule_version: str,
    outcome: CheckOutcome,
    severity: CheckSeverity,
    reason_code: str,
    *,
    text_span: tuple[int, int] | None = None,
    evidence_refs: list[str] | None = None,
    detail: str,
    human_review_ref: str | None = None,
) -> ClaimCheckRecord:
    identity = {
        "claim_id": claim.claim_id,
        "rule_id": rule_id,
        "rule_version": rule_version,
        "reason_code": reason_code,
        "text_span": text_span,
        "evidence_refs": sorted(evidence_refs or []),
    }
    check_id = "check:" + hashlib.sha256(canonical_json_bytes(identity)).hexdigest()[:16]
    return ClaimCheckRecord(
        check_id=check_id,
        claim_id=claim.claim_id,
        rule_id=rule_id,
        rule_version=rule_version,
        outcome=outcome,
        severity=severity,
        reason_code=reason_code,
        text_span=text_span,
        evidence_refs=sorted(evidence_refs or []),
        detail=detail,
        human_review_ref=human_review_ref,
    )
