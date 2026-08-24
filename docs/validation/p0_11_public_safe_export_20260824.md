# P0-11 allowlist-first public JSON candidate validation — 2026-08-24

## Question

Can P0-11 deterministically rebuild a minimal public candidate from a P0-10
eligible report without copying internal identifiers or encoding disclosure
choices in code?

This is engineering validation. Synthetic text, aliases and policies do not
approve a real disclosure or publication.

## Candidate interface

The tool accepts ReportDraft, ClaimVerificationResult and PublicExportSpec via
`ToolRequestV2`. It emits one PublicSafeReport JSON candidate, no measurement,
visualization, archive or upload.

## Controls

- exact role, Schema, version, checksum and receipt/report/policy binding;
- claim/type/evidence-state allowlist and exact alias replacement;
- source identifier omission and unselected-claim omission;
- configured prohibited literals plus a bounded path/namespace/credential guard;
- P0-10 warning degradation, strict booleans and typed refusal;
- deterministic reuse, input mutation and immutable output checks;
- source and installed-wheel execution.

## Evidence status

No local project code was run. Exact GitHub run and test counts will be recorded
after generated projections and final branch head pass `repository-gates`.

## Release boundary

P0-11 remains `candidate`. `ready_for_confirmation` is not `exported`; the tool
does not authorize, upload or scientifically validate public content.
