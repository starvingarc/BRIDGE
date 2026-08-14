# P0-10 Report Claim Verifier

| Field | Value |
|---|---|
| Branch | `p0-10-claim-verifier` |
| Baseline | `9fa004eeff6ef78d6e737f47f458ae134ec58ba2` |
| Status | `public_validation_complete_internal_input_pending` |

## Biological and reporting question

Can BRIDGE determine, without re-analysing upstream data, whether every
structured report claim preserves its cited evidence value, unit, denominator,
interval, evidence state, comparison scope and approved wording?

## First complete package

- Accept exactly four checksummed structured inputs: `ReportDraft`, an
  `EvidenceRecordSet`, an active `ClaimPolicySpec`, and a
  `StatementRegistry`.
- Use Pydantic/JSON Schema for contracts, `Decimal` for exact numeric checks,
  deterministic bilingual rules for prohibited wording, and a controlled
  renderer for the immutable verified report.
- Emit `ClaimVerificationResult` plus a `VerifiedReport` only when no blocker or
  unresolved review item remains. A hard blocker cannot be waived.
- Record the packaged benchmark ID and byte hash in every successful or partial
  result.

## Explicit non-goals

- Do not accept free Markdown, infer claims with an LLM, inspect webpages, run
  OCR, or upload/export a report in v0.1.
- Do not recompute scientific measurements or decide clinical efficacy,
  safety, potency, GMP release, product quality or overall ranking.
- Do not add a shared benchmark framework before P0-06 becomes its second real
  caller.
- Do not use P0-02 controlled test data, modify another Tool Package, or start
  the next Tool Package branch.

## Work

1. [x] Define the four input objects, check records, verification result,
   verified report and run-result Schema.
2. [x] Implement deterministic eligibility, claim/source binding, exact numeric
   and state checks, comparison constraints, prohibited wording, immutable
   output and typed failures.
3. [x] Add a versioned packaged benchmark JSON plus generated `BENCHMARK.md`,
   including method decisions, failure behavior and resource fields.
4. [x] Update the Tool spec, detailed Tool Card, example request, generators,
   package data and focused tests without introducing a general framework.
5. [x] Build and install the exact wheel on the server; run the complete suite,
   benchmark fixtures, determinism/resource measurements and repository gates.
6. [ ] Run one authorized internal four-object report, add the public-safe server
   validation record and open one Draft PR.

## Acceptance

- The package uses `ToolRequestV2`/`ToolRunV2`, owns its adapter and result
  Schema, remains `candidate`, and always keeps `domain_score=null`.
- Numeric, unit, denominator, interval, evidence-state, comparison-scope and
  prohibited-wording fixtures have deterministic reason codes.
- Changing any input byte invalidates the prior run identity; identical inputs
  produce byte-identical scientific JSON within the documented timestamp
  boundary.
- Benchmark JSON is the fact source, its Markdown projection is reproducible,
  and the Tool Card identifies the exact benchmark version and hash.
- All task-card methods have a measured, smoke-tested, benchmark-only, deferred
  or unavailable disposition. No aggregate score or cross-task ranking exists.
- The server validates a clean exact SHA: full tests, 12-tool discovery,
  knowledge, policy, Schema/Card parity, examples, benchmark parity, wheel
  smoke and private-information scan.

## Human decision still required

BRIDGE may recommend a default candidate from task-specific evidence, but this
branch does not treat a recommendation as developer approval. If no method is
explicitly approved during PR review, the candidate package may merge with its
default selection left unset.
