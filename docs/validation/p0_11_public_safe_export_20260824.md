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

No local project code was run. GitHub Actions run
[`32689491713`](https://github.com/starvingarc/BRIDGE/actions/runs/32689491713)
validated implementation head `52ba293` through the PR merge ref on Ubuntu and
Python 3.12. The installed package resolved from `site-packages`, outside the
source checkout.

| Gate | Current result |
|---|---|
| Installed-wheel focused chain | 159 P0-03/P0-04/P0-05/P0-06/P0-07/P0-11 tests passed |
| Complete pytest | 1,118 passed; 3 existing dependency warnings |
| 12-tool discovery | passed; exactly 12 |
| Public and packaged Schemas | 71 registered Schemas; byte-mirrored generated copies packaged with the wheel |
| Knowledge validation | passed; no dangling method/source refs; 0 formal-eligible methods |
| Repository policy and committed diff | passed |

The PR remains Draft. These results establish deterministic projection and
packaging, not approval of a disclosure policy or public release.

## Release boundary

P0-11 remains `candidate`. `ready_for_confirmation` is not `exported`; the tool
does not authorize, upload or scientifically validate public content.
