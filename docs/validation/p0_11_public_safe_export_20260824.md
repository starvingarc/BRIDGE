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

No local project code was run. The bounded closure implementation at
`fd00fc41d6511259f61f2ec5becfe548c8c021bd` was transferred as a Git archive
to `/data1` and exercised there from both the exact source tree and a clean
wheel installation. The installed package resolved from the temporary
environment's `site-packages`, outside the source checkout. The wheel SHA-256
was `7b04814f84ef4bbdd3f8eaa1f338caf3b018c8ddbe0eecb9d64254d36faec2d6`.

| Gate | Current result |
|---|---|
| Source focused chain | 184 P0-03/P0-04/P0-05/P0-06/P0-07/P0-11 tests passed |
| Source complete pytest | 1,143 passed; 3 existing dependency warnings |
| Installed-wheel complete pytest | 1,143 passed; 2 dependency warnings |
| 12-tool discovery | passed; exactly 12 |
| Public and packaged Schemas | 71 registered Schemas; byte-mirrored generated copies packaged with the wheel |
| Knowledge validation | passed; no dangling method/source refs; 0 formal-eligible methods |
| Repository policy and committed diff | passed |

The closure reuses the shared publication scanner and applies it recursively to
the complete reconstructed payload before candidate hashing. Absolute and
home-relative paths, credential-like values, internal namespaces and leaks in
nested non-prose fields are rejected without suppressing valid `public-*` IDs.

The PR remains Draft. These results establish deterministic projection and
packaging, not approval of a disclosure policy or public release.

## Release boundary

P0-11 remains `candidate`. `ready_for_confirmation` is not `exported`; the tool
does not authorize, upload or scientifically validate public content.
