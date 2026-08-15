# P0-10 Report Claim Verifier

| Field | Value |
|---|---|
| Branch | `p0-10-claim-verifier` |
| Baseline | `9fa004eeff6ef78d6e737f47f458ae134ec58ba2` |
| Status | `draft_review` |

## Biological and reporting question

Can BRIDGE determine, without re-analysing upstream data, whether every
structured report claim preserves its cited evidence value, unit, denominator,
interval, evidence state, comparison scope and approved wording?

## First complete package

- Accept exactly four checksummed structured inputs: `ReportDraft`, a verified
  P0-09 Case graph manifest, a `ClaimPolicySpec`, and a `StatementRegistry`;
  the latter two must equal the approved versions in the packaged release
  contract.
- Use Pydantic/JSON Schema for contracts, identity-only `Decimal` checks,
  deterministic bilingual rules for prohibited wording, and direct
  package-owned ClaimBlock reconstruction.
- Emit one `ClaimVerificationResult` receipt that binds the original ReportDraft,
  P0-09 graph manifest, audience, checks and export eligibility. A hard blocker
  cannot be waived and ReportDraft cannot grant reviewer authority.
- Record the packaged benchmark ID and byte hash in every successful or partial
  result.

## Explicit non-goals

- Do not accept free Markdown, infer claims with an LLM, inspect webpages, run
  OCR, or upload/export a report in v0.1.
- Do not recompute scientific measurements or decide clinical efficacy,
  safety, potency, GMP release, product quality or overall ranking.
- Do not add a shared benchmark framework before P0-06 becomes its second real
  caller.
- Do not use P0-02 controlled test data, implement another Tool Package, or
  start the next Tool Package branch. The P0-11 task card may only be corrected
  to consume the original ReportDraft plus this receipt.

## Work

1. [x] Define the four structured inputs, check records and the single
   `ClaimVerificationResult` receipt Schema.
2. [x] Implement deterministic eligibility, claim/source binding, exact numeric
   and state checks, comparison constraints, prohibited wording, immutable
   output and typed failures.
3. [x] Add a versioned packaged benchmark JSON plus generated `BENCHMARK.md`,
   including method decisions, failure behavior and resource fields.
4. [x] Update the Tool spec, detailed Tool Card, example request, generators,
   package data and focused tests without introducing a general framework.
5. [x] Build and install the exact wheel on the server; run the complete suite,
   benchmark fixtures, determinism/resource measurements and repository gates.
6. [x] Add the public-safe server validation record for the public and synthetic
   candidate gates.
7. [x] Run one authorized internal four-object report.
8. [x] Open one Draft PR after the internal run is represented in the benchmark.
9. [x] Address the seven blocking Draft-PR findings and repeat exact-SHA server
   validation with an authoritative P0-09 Case graph.
10. [x] Address the five second-round release-boundary findings: approved input
    authority, full ClaimBlock reconstruction, adjacent numeric lexemes,
    self-consistent result objects and current-only task-card wording.
11. [x] Validate the exact implementation commit and wheel and update the
    public record.
12. [x] Push the reviewed changes and request focused re-review.
13. [x] Apply the final one-pass deletion-first review scope: derive the public
    evidence tier from audience, remove caller numeric/reviewer/release-tier
    authority, delete the lossy VerifiedReport copy, bind one receipt to the
    graph manifest and publish one pre-hashed byte sequence.
14. [x] Regenerate projections and validate the exact implementation commit and
    wheel on the server, including the complete adversarial matrix and repeated
    anonymous run.
15. [ ] Push the validated revision and request focused re-review; merge only
    after separate authorization.

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
