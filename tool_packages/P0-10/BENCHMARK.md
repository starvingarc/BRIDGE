# P0-10 Method Benchmark

- Benchmark ID: `P0-10-BENCHMARK-v0.1`
- Version: `0.1.0`
- JSON SHA-256: `3c5ac1c25b86027c32522a1d1774c2c6f32dbc9c363b6aa6585328e54aa5e9df`
- State: `awaiting_server_validation`
- Selected default: `none`
- Aggregate score/rank: `null` / `null`

Methods are compared only within the same analysis task. Resource values
are observations, not a cross-task score. A candidate recommendation is not
a default selection unless the developer decision explicitly says so.

## Data cases

| Case | Class | Public accession or reference | Claims | Replicates | Scope |
|---|---|---|---:|---:|---|
| PUBLIC-SERVER-REPRO-20260812 | public_record | docs/validation/server_reproducibility_20260812.md | 3 | not applicable | Public engineering-result claims with exact counts, units and boundaries. |
| SYNTHETIC-P0-10-CONTROLS-v0.1 | synthetic_control | tests/test_p0_10_claim_verifier.py | 18 | not applicable | Numeric, unit, denominator, interval, state, bilingual wording, comparison and review controls. |
| INTERNAL-ANONYMIZED-REPORT-v0.1 | internal_anonymized | not public | 0 | not applicable | Awaiting an authorized server-only structured report; no private path or identifier is committed. |

## Bilingual prohibited-claim rules

| Method | Version / license | Role and evidence | Failure / abstention | Runtime and resources | BRIDGE recommendation | Human decision |
|---|---|---|---|---|---|---|
| BRIDGE bilingual rule set (`METHOD-INTERNAL-RULESET`) | 0.1.0; MIT | Severity, exception and reviewer-resolution rules.; not_run; prohibited_claim_leak_count=None | Hard rules block release; review rules require an authorized reviewer.; Unresolved semantics remain review_required. | not measured | default_candidate | approved: Approved as the formal deterministic rule layer. |
| regex (`METHOD-UNICODE-REGEX-ENGINE`) | unresolved; Apache-2.0 AND CNRI-Python | Unicode bilingual pattern matching and span location.; not_run; fixture_false_negative_count=None | Invalid or timed-out policy patterns block release.; Complex unresolved meaning is sent to human review, not guessed. | not measured | default_candidate | approved: Approved as the callable Unicode pattern engine with bounded execution time. |
| Open Policy Agent (`METHOD-POLICY-ENGINE`) | unresolved; Apache-2.0 | Policy-as-code comparison only.; audit_only; audit_complete=documentation only | Must not become a network service dependency.; Policy evaluation only; no semantic inference. | not measured | deferred | pending: No OPA binary or frozen Rego parity suite is available for v0.1. |
| LLM semantic-review adapter (`METHOD-PROVIDER-NEUTRAL-ADAPTER`) | unresolved; provider-dependent | Future semantic flag sensitivity only.; audit_only; formal_path=excluded | Provider failure would require human review; never a release pass.; Flags ambiguity only; no deterministic decision. | not measured | deferred | rejected: LLM judgment is excluded from the v0.1 formal path and cannot clear blockers. |

## Controlled report rendering

| Method | Version / license | Role and evidence | Failure / abstention | Runtime and resources | BRIDGE recommendation | Human decision |
|---|---|---|---|---|---|---|
| BRIDGE controlled renderer (`METHOD-INTERNAL-RENDERER`) | 0.1.0; MIT | Immutable verified Markdown projection.; not_run; byte_identical_repeat=None | No VerifiedReport is emitted for blocked or review-required content.; Unsupported media return unavailable outside this package. | not measured | default_candidate | approved: Approved as the fixed renderer; templates cannot come from callers. |
| Jinja2 (`METHOD-TEMPLATE-ENGINE`) | 3.1; BSD-3-Clause | Fixed controlled template rendering.; not_run; template_escape_fixture_pass_rate=None | StrictUndefined fails instead of inserting missing content.; Caller templates are not accepted. | not measured | default_candidate | approved: Approved only behind the fixed BRIDGE template. |
| markdown-it-py (`METHOD-MARKDOWN-PARSER`) | 4.0; MIT | Audit of future imported Markdown only.; audit_only; formal_path=excluded | Imported Markdown remains an unverified candidate.; Cannot recover missing claim bindings. | not measured | deferred | rejected: Free Markdown import is explicitly outside v0.1. |
| Playwright (`METHOD-BROWSER-AUTOMATION`) | unresolved; Apache-2.0 | Future visual render validation only.; audit_only; formal_path=excluded | Returns unavailable rather than silently skipping media.; No OCR or pixel-derived scientific values. | not measured | deferred | rejected: Web and media rendering are unavailable in v0.1. |

## Deterministic release aggregation

| Method | Version / license | Role and evidence | Failure / abstention | Runtime and resources | BRIDGE recommendation | Human decision |
|---|---|---|---|---|---|---|
| BRIDGE Claim Verifier Core (`METHOD-INTERNAL-DETERMINISTIC-ENGINE-33C959`) | 0.1.0; MIT | Ordered deterministic checks and release-state aggregation.; not_run; blocker_non_override_rate=None, deterministic_repeat_match=None | Fail closed on invalid contracts; report findings without converting them into a score.; Returns not_assessed for an inactive policy and review_required for unresolved semantic rules. | not measured | default_candidate | approved: The implementation plan approves this as a formal candidate, not as a selected default. |

## Exact numeric and unit fidelity

| Method | Version / license | Role and evidence | Failure / abstention | Runtime and resources | BRIDGE recommendation | Human decision |
|---|---|---|---|---|---|---|
| BRIDGE numeric fidelity rules (`METHOD-INTERNAL-NUMERIC-ENGINE`) | 0.1.0; MIT | Bind and compare numeric report values to EvidenceRecord fields.; not_run; numeric_mutation_detection_rate=None | Any value, unit, denominator, interval or rendering mismatch blocks release.; Unsupported unit conversion is refused. | not measured | default_candidate | approved: Approved as the exact numeric candidate; no floating tolerance is allowed. |
| Python Decimal (`METHOD-STANDARD-LIBRARY`) | Python 3.12; PSF-2.0 | Exact decimal construction, scaling and rounding.; not_run; rounding_fixture_pass_rate=None | Non-finite or non-decimal strings are rejected.; Unknown conversions remain unavailable. | not measured | default_candidate | approved: Approved as the callable decimal implementation. |
| Pint (`METHOD-UNIT-LIBRARY`) | unresolved; BSD-3-Clause | Candidate registered unit conversion.; audit_only; audit_complete=license and interface only | Must fail closed for unregistered conversions.; Unknown units must be rejected. | not measured | deferred | pending: A reviewed unit registry and conversion fixtures are not yet available. |

## External factuality audit

| Method | Version / license | Role and evidence | Failure / abstention | Runtime and resources | BRIDGE recommendation | Human decision |
|---|---|---|---|---|---|---|
| FActScore (`METHOD-FACTUALITY-PACKAGE`) | unresolved; MIT | Atomic factuality benchmark audit.; audit_only; audit_complete=documentation and license | Never clears a BRIDGE hard blocker.; External benchmark semantics only. | not measured | benchmark_only | pending: External task definitions do not replace BRIDGE structured policy checks. |
| RefChecker (`METHOD-HALLUCINATION-CHECKER`) | unresolved; Apache-2.0 | Reference-consistency benchmark audit.; audit_only; audit_complete=documentation and license | Never clears a BRIDGE hard blocker.; Triplet/reference benchmark only. | not measured | benchmark_only | pending: Not part of the deterministic v0.1 decision path. |
| AlignScore (`METHOD-FACTUAL-CONSISTENCY-MODEL`) | unresolved; MIT | Text alignment benchmark audit.; audit_only; audit_complete=documentation and license | Never clears a BRIDGE hard blocker.; Text-alignment benchmark only. | not measured | benchmark_only | pending: Not part of the deterministic v0.1 decision path. |
| SciFact (`METHOD-SCIENTIFIC-CLAIM-DATASET-CODE`) | unresolved; repository and data terms require review | Scientific-claim benchmark reference.; audit_only; audit_complete=documentation; data terms pending | Dataset performance never clears a BRIDGE hard blocker.; External English benchmark only. | not measured | benchmark_only | pending: The English scientific-claim dataset is a benchmark reference, not a release rule. |

## Structured contract validation

| Method | Version / license | Role and evidence | Failure / abstention | Runtime and resources | BRIDGE recommendation | Human decision |
|---|---|---|---|---|---|---|
| Pydantic (`METHOD-SCHEMA-LIBRARY`) | 2.12; MIT | Typed object and enum validation.; not_run; invalid_fixture_rejection_rate=None | Rejects missing, extra or invalid typed fields.; Unknown fields are rejected rather than guessed. | not measured | default_candidate | approved: Approved as a callable formal-candidate component by the implementation plan. |
| jsonschema (`METHOD-SCHEMA-VALIDATOR`) | 4.25; MIT | Independent JSON Schema validation.; not_run; schema_parity=None | Rejects output that does not match the published result Schema.; No inference outside the published Schema. | not measured | sensitivity_candidate | approved: Approved as the independent public-Schema validation channel. |

## Stability and applicability

P0-10 consumes structured report objects rather than expression matrices.
Cell, gene and sequencing-depth downsampling are therefore recorded as
not applicable instead of being imitated with claim deletion. Deterministic
reruns, positive/negative controls, missing-input behavior, bilingual rules,
policy/reference swaps and denominator changes remain package-specific gates.

The benchmark does not establish clinical validity, safety, potency, GMP
release, a best product or an overall method ranking.
