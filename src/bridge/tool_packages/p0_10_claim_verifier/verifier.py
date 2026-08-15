from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
from importlib.resources import files
from typing import Iterable

import regex

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    EvidenceApplicability,
    EvidenceLifecycleState,
    EvidenceRecord,
    EvidenceRecordSet,
    EvidenceTier,
)
from bridge.tool_packages.p0_10_claim_verifier.models import (
    AuthoringChannel,
    CheckOutcome,
    CheckSeverity,
    ClaimBlock,
    ClaimCheckRecord,
    ClaimPolicySpec,
    ClaimTypePolicy,
    ClaimType,
    ClaimVerificationResult,
    ClaimVerifierReleaseContract,
    ComparisonMode,
    MAX_DECIMAL_ADJUSTED_EXPONENT,
    MAX_DECIMAL_DIGITS,
    PublicExportEligibility,
    RegisteredStatement,
    ReleaseState,
    ReportAudience,
    ReportDraft,
    ReportLanguage,
    StatementRegistry,
    ValueBinding,
)


VERIFIER_VERSION = "0.1.0"
RELEASE_CONTRACT_FILENAME = "release_contract_v0.1.json"
APPROVED_RELEASE_CONTRACT_SHA256 = (
    "c8a9237652cba4e6b3eb1c4f4215437980f0f480a0944d232abddeef5c4236c8"
)


def release_contract_bytes() -> bytes:
    return files(
        "bridge.tool_packages.p0_10_claim_verifier.resources"
    ).joinpath(RELEASE_CONTRACT_FILENAME).read_bytes()


def release_contract_sha256() -> str:
    return hashlib.sha256(release_contract_bytes()).hexdigest()


def load_release_contract() -> ClaimVerifierReleaseContract:
    payload = release_contract_bytes()
    if hashlib.sha256(payload).hexdigest() != APPROVED_RELEASE_CONTRACT_SHA256:
        raise ValueError("release contract does not match the approved package record")
    return ClaimVerifierReleaseContract.model_validate_json(payload)


def verify_report(
    *,
    report: ReportDraft,
    evidence_set: EvidenceRecordSet,
    policy: ClaimPolicySpec,
    statements: StatementRegistry,
    release_contract: ClaimVerifierReleaseContract,
    release_contract_hash: str,
    benchmark_id: str,
    benchmark_sha256: str,
    run_id: str,
    evidence_graph_id: str,
    evidence_graph_version: int,
    evidence_graph_manifest_sha256: str,
) -> ClaimVerificationResult:
    verification_id = f"claim-verification:{run_id.removeprefix('run-')}"
    evidence = {record.ref: record for record in evidence_set.records}
    statement_by_ref = {statement.ref: statement for statement in statements.statements}
    claim_policy = {item.claim_type: item for item in policy.claim_type_policies}
    checks: list[ClaimCheckRecord] = []
    for claim in report.claim_blocks:
        resolved = [evidence[ref] for ref in claim.evidence_refs if ref in evidence]
        checks.extend(
            _check_authoring(
                report,
                claim,
                resolved,
                statement_by_ref,
                release_contract,
            )
        )
        checks.extend(
            _check_claim_contract(
                report.audience,
                claim,
                resolved,
                evidence,
                statement_by_ref,
                claim_policy,
            )
        )
        checks.extend(_check_value_bindings(claim, evidence))
        checks.extend(_check_comparison_scope(claim, policy))
        checks.extend(
            _check_text_rules(
                claim,
                policy,
                statement_by_ref,
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

    return ClaimVerificationResult(
        object_version="0.1.0",
        verification_id=verification_id,
        verifier_version=VERIFIER_VERSION,
        benchmark_id=benchmark_id,
        benchmark_sha256=benchmark_sha256,
        release_contract_id=release_contract.contract_id,
        release_contract_sha256=release_contract_hash,
        report_draft_ref=report.ref,
        report_content_hash=report.content_hash,
        report_audience=report.audience,
        evidence_graph_id=evidence_graph_id,
        evidence_graph_version=evidence_graph_version,
        evidence_graph_manifest_sha256=evidence_graph_manifest_sha256,
        claim_policy_ref=policy.ref,
        statement_registry_ref=statements.ref,
        release_state=release_state,
        check_records=sorted(checks, key=lambda item: item.check_id),
        public_export_eligibility=(
            PublicExportEligibility.ELIGIBLE
            if report.audience is ReportAudience.PUBLIC_CANDIDATE
            and release_state in {ReleaseState.VERIFIED, ReleaseState.VERIFIED_WITH_WARNINGS}
            else PublicExportEligibility.INELIGIBLE
        ),
    )


def _check_authoring(
    report: ReportDraft,
    claim: ClaimBlock,
    resolved: list[EvidenceRecord],
    statements: dict[str, RegisteredStatement],
    contract: ClaimVerifierReleaseContract,
) -> list[ClaimCheckRecord]:
    if (
        report.authoring_channel is not AuthoringChannel.DETERMINISTIC_RENDERER
        or claim.authoring_channel is not AuthoringChannel.DETERMINISTIC_RENDERER
    ):
        return [
            _review_required(
                claim,
                "rule:deterministic-authoring",
                "non_deterministic_authoring_requires_review",
            )
        ]
    if (
        report.renderer_id != contract.renderer_id
        or report.renderer_version != contract.renderer_version
    ):
        return [
            _review_required(
                claim,
                "rule:deterministic-authoring",
                "unapproved_renderer_requires_review",
            )
        ]
    expected = _render_authoritative_claim(claim, resolved, statements, contract)
    if expected is None:
        return [
            _review_required(
                claim,
                "rule:deterministic-authoring",
                "unsupported_deterministic_claim_requires_review",
            )
        ]
    if claim.text != expected:
        return [
            _block(
                claim,
                "rule:deterministic-authoring",
                "deterministic_claim_text_mismatch",
            )
        ]
    return []


def _render_authoritative_claim(
    claim: ClaimBlock,
    resolved: list[EvidenceRecord],
    statements: dict[str, RegisteredStatement],
    contract: ClaimVerifierReleaseContract,
) -> str | None:
    if claim.claim_type is ClaimType.POLICY_OR_BOUNDARY and len(claim.statement_refs) == 1:
        statement = statements.get(claim.statement_refs[0])
        return None if statement is None else statement.texts.get(claim.language)
    if (
        claim.claim_type is not ClaimType.MEASUREMENT
        or claim.language.value != contract.measurement_language
        or len(resolved) != 1
        or len(claim.value_bindings) != 1
    ):
        return None
    record = resolved[0]
    binding = claim.value_bindings[0]
    if (
        binding.source_evidence_ref != record.ref
        or binding.source_field != "value"
        or record.value is None
        or isinstance(record.value, bool)
    ):
        return None
    value = _render_identity_numeric(record.value, record.unit)
    if value is None:
        return None
    return f"{record.metric_id}: {value}."


def _check_claim_contract(
    audience: ReportAudience,
    claim: ClaimBlock,
    resolved: list[EvidenceRecord],
    evidence: dict[str, EvidenceRecord],
    statements: dict[str, RegisteredStatement],
    policies: dict[ClaimType, ClaimTypePolicy],
) -> list[ClaimCheckRecord]:
    checks: list[ClaimCheckRecord] = []
    policy = policies.get(claim.claim_type)
    if policy is None:
        checks.append(_block(claim, "rule:claim-type-policy", "claim_type_policy_missing"))
        return checks
    if not claim.evidence_refs:
        reason = (
            "formal_evidence_required_for_public_candidate"
            if audience is ReportAudience.PUBLIC_CANDIDATE
            else "claim_evidence_required"
        )
        if audience is ReportAudience.PUBLIC_CANDIDATE or policy.requires_evidence:
            checks.append(_block(claim, "rule:evidence-binding", reason))
    for ref in claim.evidence_refs:
        record = evidence.get(ref)
        if record is None:
            checks.append(
                _block(
                    claim,
                    "rule:evidence-binding",
                    "evidence_ref_not_found",
                    evidence_refs=[ref],
                )
            )
            continue
        if record.lifecycle_state is not EvidenceLifecycleState.ACTIVE:
            checks.append(
                _block(claim, "rule:evidence-lifecycle", "evidence_not_active", evidence_refs=[ref])
            )
        if record.applicability is not EvidenceApplicability.APPLICABLE:
            checks.append(
                _block(
                    claim,
                    "rule:evidence-applicability",
                    "evidence_not_applicable",
                    evidence_refs=[ref],
                )
            )
        if (
            audience is ReportAudience.PUBLIC_CANDIDATE
            and record.evidence_tier is not EvidenceTier.FORMAL
        ):
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
                _block(
                    claim,
                    "rule:evidence-state-policy",
                    "evidence_state_not_allowed",
                    evidence_refs=[ref],
                )
            )
        if record.claim_ref.ref != claim.claim_ref:
            checks.append(
                _block(
                    claim,
                    "rule:claim-scope",
                    "claim_evidence_semantic_mismatch",
                    evidence_refs=[ref],
                )
            )
        if record.product_case_ref.ref != claim.product_case_ref:
            checks.append(
                _block(
                    claim,
                    "rule:case-scope",
                    "product_case_evidence_mismatch",
                    evidence_refs=[ref],
                )
            )
    if resolved:
        states = {item.evidence_state for item in resolved}
        if len(states) > 1:
            checks.append(
                _block(
                    claim,
                    "rule:evidence-state",
                    "mixed_evidence_states_require_separate_claims",
                )
            )
        elif claim.reported_evidence_state is None:
            checks.append(_block(claim, "rule:evidence-state", "reported_evidence_state_required"))
        elif claim.reported_evidence_state not in states:
            checks.append(_block(claim, "rule:evidence-state", "evidence_state_mismatch"))
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
            checks.append(
                _block(
                    claim,
                    "rule:statement-binding",
                    "statement_ref_not_found",
                    statement_ref=ref,
                )
            )
            continue
        resolved.append(statement)
        if not statement.approved:
            checks.append(
                _block(
                    claim,
                    "rule:statement-binding",
                    "statement_not_approved",
                    statement_ref=ref,
                )
            )
        if claim.claim_type not in statement.allowed_claim_types:
            checks.append(
                _block(
                    claim,
                    "rule:statement-binding",
                    "statement_claim_type_mismatch",
                    statement_ref=ref,
                )
            )
    if claim.claim_type is ClaimType.POLICY_OR_BOUNDARY:
        if len(resolved) != 1:
            checks.append(_block(claim, "rule:statement-binding", "exactly_one_statement_required"))
        elif resolved[0].texts.get(claim.language) != claim.text:
            checks.append(
                _block(
                    claim,
                    "rule:statement-text",
                    "registered_statement_text_mismatch",
                )
            )
    return checks


def _check_value_bindings(
    claim: ClaimBlock,
    evidence: dict[str, EvidenceRecord],
) -> list[ClaimCheckRecord]:
    checks: list[ClaimCheckRecord] = []
    for binding in claim.value_bindings:
        record = evidence.get(binding.source_evidence_ref)
        if binding.source_evidence_ref not in claim.evidence_refs:
            checks.append(_block(claim, "rule:value-binding", "binding_evidence_not_cited"))
            continue
        if record is None:
            continue
        start, end = binding.text_span
        rendered = claim.text[start:end] if end <= len(claim.text) else ""
        reason = _numeric_binding_reason(binding, record, rendered)
        if reason is not None:
            checks.append(
                _block(
                    claim,
                    "rule:numeric-fidelity",
                    reason,
                    evidence_refs=[binding.source_evidence_ref],
                )
            )
    return checks


def _numeric_binding_reason(
    binding: ValueBinding, evidence: EvidenceRecord, rendered: str
) -> str | None:
    source = _numeric_source(evidence, binding.source_field)
    if source is None or isinstance(source, bool):
        return "numeric_source_unavailable"
    canonical = _canonical_decimal(source)
    if canonical is None:
        return "numeric_source_not_scalar"
    if binding.canonical_numeric_string != canonical:
        return "canonical_numeric_mismatch"
    if binding.raw_unit != evidence.unit:
        return "unit_mismatch"
    if rendered != _join_numeric_unit(canonical, binding.raw_unit):
        return "rendered_numeric_mismatch"
    return None


def _numeric_source(evidence: EvidenceRecord, source_field: str) -> object:
    if source_field == "interval_lower":
        return None if evidence.interval is None else evidence.interval.lower
    if source_field == "interval_upper":
        return None if evidence.interval is None else evidence.interval.upper
    return getattr(evidence, source_field)


def _canonical_decimal(value: object) -> str | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite() or (
        len(number.as_tuple().digits) > MAX_DECIMAL_DIGITS
        or abs(number.adjusted()) > MAX_DECIMAL_ADJUSTED_EXPONENT
    ):
        return None
    rendered = format(number, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered in {"-0", "+0"} else rendered


def _join_numeric_unit(value: str, raw_unit: str | None) -> str:
    if raw_unit is None:
        return value
    return value + raw_unit if raw_unit in {"%", "‰"} else f"{value} {raw_unit}"


def _render_identity_numeric(value: object, raw_unit: str | None) -> str | None:
    canonical = _canonical_decimal(value)
    return None if canonical is None else _join_numeric_unit(canonical, raw_unit)


def _check_comparison_scope(
    claim: ClaimBlock, policy: ClaimPolicySpec
) -> list[ClaimCheckRecord]:
    checks: list[ClaimCheckRecord] = []
    if (
        claim.claim_type is ClaimType.DESCRIPTIVE_COMPARISON
        and claim.comparison_mode is not ComparisonMode.DESCRIPTIVE_ONLY
    ):
        checks.append(_block(claim, "rule:comparison-contract", "descriptive_claim_mode_mismatch"))
    if (
        claim.claim_type is ClaimType.INFERENTIAL_COMPARISON
        and claim.comparison_mode is not ComparisonMode.INFERENTIAL
    ):
        checks.append(_block(claim, "rule:comparison-contract", "inferential_claim_mode_mismatch"))
    if claim.comparison_mode is ComparisonMode.DESCRIPTIVE_ONLY:
        for pattern in policy.descriptive_forbidden_patterns:
            try:
                match = regex.search(
                    pattern,
                    claim.text,
                    regex.IGNORECASE | regex.VERSION1,
                    timeout=0.05,
                )
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
            checks.append(
                _text_rule_record(
                    claim,
                    rule.rule_id,
                    rule.version,
                    rule.reason_code,
                    rule.severity,
                    (match.start(), match.end()),
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
        if (
            statement is not None
            and statement.approved
            and statement.texts.get(claim.language) == claim.text
        ):
            return True
    return False


def _text_rule_record(
    claim: ClaimBlock,
    rule_id: str,
    rule_version: str,
    reason_code: str,
    severity: CheckSeverity,
    text_span: tuple[int, int],
) -> ClaimCheckRecord:
    outcome = {
        CheckSeverity.HARD_BLOCKER: CheckOutcome.BLOCKED,
        CheckSeverity.REVIEW: CheckOutcome.REVIEW_REQUIRED,
        CheckSeverity.WARNING: CheckOutcome.WARNING,
    }[severity]
    return _record(
        claim,
        rule_id,
        rule_version,
        outcome,
        severity,
        reason_code,
        text_span=text_span,
    )


def _block(
    claim: ClaimBlock,
    rule_id: str,
    reason_code: str,
    rule_version: str = "0.1.0",
    *,
    text_span: tuple[int, int] | None = None,
    evidence_refs: list[str] | None = None,
    statement_ref: str | None = None,
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
        statement_ref=statement_ref,
    )


def _review_required(
    claim: ClaimBlock, rule_id: str, reason_code: str
) -> ClaimCheckRecord:
    return _record(
        claim,
        rule_id,
        "0.1.0",
        CheckOutcome.REVIEW_REQUIRED,
        CheckSeverity.REVIEW,
        reason_code,
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
    statement_ref: str | None = None,
) -> ClaimCheckRecord:
    identity = {
        "claim_id": claim.claim_id,
        "rule_id": rule_id,
        "rule_version": rule_version,
        "reason_code": reason_code,
        "text_span": text_span,
        "evidence_refs": sorted(evidence_refs or []),
        "statement_ref": statement_ref,
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
        statement_ref=statement_ref,
    )
