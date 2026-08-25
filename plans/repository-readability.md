# Repository Readability

## Goal

Make the public repository understandable from the README through each of the 12
P0 packages without changing a runtime interface, Schema, scientific status or
release claim.

## Scope

- Turn the README and documentation index into short reader-oriented entrypoints.
- Add one indexed P0 tool map and one concise landing page inside every package.
- Keep each Tool Card as the authoritative detailed input/output contract.
- Fix active status, naming, source and reference drift in stable documentation.
- Group validation records and complete the example-request index.
- Add minimal contribution and private security-reporting guidance.

## Non-goals

- No tool, Schema, method, threshold, score or scientific-release change.
- No rewrite of historical validation records or decision history.
- No new documentation framework, website, generator layer or dependency.
- No `CITATION.cff` until authorship and preferred-citation metadata are supplied.

## Acceptance

- P0-01 through P0-12 each have a package landing page linked to their Tool Card,
  scientific task card, example request and current validation record.
- The README distinguishes engineering execution from candidate/shadow science.
- Current documentation no longer describes implemented packages as scaffolds or
  the converted Birtele asset as unconverted.
- Repository policy, generated-document parity, full tests, 12-tool discovery,
  knowledge validation, link/privacy checks and `git diff --check` pass on
  `/data1` and GitHub CI.

## Status

Implementation and `/data1` validation are complete at
`dc3eeea51eed57115dd789c0e0c97886ca6241c3`:

- full suite: 1,221 passed with 8 pre-existing warning instances;
- 12-tool discovery, repository policy, knowledge validation and diff checks:
  passed;
- Tool Card and knowledge generation: idempotent;
- isolated wheel build/import: passed with 12 installed tools.

GitHub exact-head CI and human review remain pending. Status:
`implementation_complete_review_pending`.
