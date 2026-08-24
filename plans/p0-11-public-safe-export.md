# P0-11 Internal Review Projection closeout

## Goal

Make P0-11 callable as a narrow, contract-validated internal review projection
without representing it as authenticated, public-safe or release-authorized.
Selected claims, review aliases, allowed claim/evidence types and prohibited
literals remain checksummed policy inputs rather than code constants.

The filename is retained only to preserve links from the stacked Draft history.

## Interface

The executable slice accepts exactly one ReportDraft, one eligible
ClaimVerificationResult, the exact P0-10 ToolRunV2 that produced it and one
ReviewProjectionSpec. It creates one new
`ContractValidatedReviewProjection`; it never mutates or copies the source
report.

The output omits source report/claim/ProductCase/Evidence/binding identifiers,
retains exact verified claim text and numeric bindings, and always declares:

- producer authentication `not_available`;
- release authority `not_configured`;
- distribution `internal_review_only`;
- projection state `review_required`.

## Explicit non-goals

- no automatic publication, upload, confirmation or release authority;
- no claim rewriting, translation or arbitrary redaction;
- no universal credential, PII or semantic-leak detector;
- no CSV, Markdown, archive, figure, SVG/HTML or media handling;
- no biological verification, score, rank or release decision.

## Deliverables

- module-local models, executor and adapter;
- public/packaged ReviewProjectionSpec and
  ContractValidatedReviewProjection Schemas;
- four-input documentation-only request, detailed Tool Card and validation
  record;
- exact P0-10 run/result/artifact checksum binding and adversarial tests;
- one integrator Draft PR; no automatic merge.

## Closure state

Implementation and focused `/data1` tests are complete. Final combined SHA,
clean-wheel whole-repository validation, GitHub required check and independent
biology/scRNA/AI4S re-review remain the closure gates. Any public disclosure or
distribution system remains a separate future workstream with its own authority
and audit contract.
