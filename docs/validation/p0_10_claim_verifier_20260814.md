# P0-10 Report Claim Verifier candidate validation — 2026-08-14

## Question tested

Can the packaged BRIDGE report checker deterministically confirm that a
structured claim preserves its cited value, unit, denominator, interval,
evidence state, comparison mode and permitted wording, while refusing invalid
or prohibited content?

This is an engineering and reporting validation. It does not establish that the
underlying biological evidence is true, sufficient or clinically meaningful.

## Exact build

| Item | Value |
|---|---|
| Branch | `p0-10-claim-verifier` |
| Validated implementation commit | `d73427059e93f879061ccf28fa9f127a97b662da` |
| Base `main` | `9fa004eeff6ef78d6e737f47f458ae134ec58ba2` |
| Complete-history transfer bundle SHA-256 | `479221bda165d4deecacec901fea589726181fa727d6c6b9fa097538fdf08d82` |
| Git archive SHA-256 | `edb5790bda2e8ae60c18b76a8c92542d9066da686c70586e28833bf5755fbfdd` |
| Wheel | `bridge-0.2.0.dev0-py3-none-any.whl` |
| Wheel SHA-256 | `834b04f72e3d1026519f8e557c8d5a8162e21a169b38e166f9d0d8ee54c5aa04` |
| Evidence environment contract SHA-256 | `c3398ecb4961defec894eede7c1fdda046168687b9219bed53c0f68a91324d8f` |
| Explicit environment export SHA-256 | `9ec04a55bb5d6fdb9174a34d07807d810f6d22eb98bf2d7189433d4635cb20ec` |
| Server evidence manifest | 80 entries; SHA-256 `9a8932925640484a8f7bbfddc234a35d27d47991e21f4f84299da051a880c672` |

The wheel was built from the exact Git archive without dependency resolution,
installed into `ENV-EVIDENCE-v0.1`, loaded from that environment's
`site-packages`, and passed dependency consistency checks. The environment used
Python 3.12.13 and the exact versions in its committed contract, including
Pydantic 2.12.5, jsonschema 4.25.1, Jinja2 3.1.6 and regex 2026.7.19.

## Inputs and controls

The public run used one structured engineering claim from the committed server
reproducibility record. Its `ReportDraft`, `EvidenceRecordSet`,
`ClaimPolicySpec` and `StatementRegistry` were materialized as four immutable
JSON objects with exact SHA-256 references.

The synthetic suite exercised 25 predeclared claim or contract controls,
including:

- value, unit, denominator, interval, rounding and rendered-value changes;
- unbound numbers and evidence-state substitution;
- descriptive wording presented as inferential or causal;
- English, Chinese and mixed-language prohibited claims;
- an exact registered boundary-statement exception;
- authorized review-only resolution and hard-blocker non-override;
- Markdown, raw HTML and nested-template inputs;
- inactive policy, content-hash drift, changed input and existing-output drift.

No P0-02 controlled or sealed data, old 0–100 score report, patient/donor
identifier, private path or private content was used.

## Observations

| Gate | Result |
|---|---|
| P0-08/P0-09/P0-10 installed-wheel tests in `ENV-EVIDENCE-v0.1` | `634 passed` in 33.36 s |
| Complete installed-wheel suite | `929 passed, 1 warning` in 83.82 s |
| Environment, Schema/Card parity, registry and example gates | `22 passed` in 1.47 s |
| Tool discovery | 12 packages; P0-01, P0-02, P0-08, P0-09 and P0-10 implemented |
| P0-10 runtime components | 9 registered methods/components |
| Knowledge snapshot | valid; 354 methods, 387 sources, 396 bindings, no dangling references |
| Repository size | 317 tracked files against a 325-file current budget |
| Generators | benchmark, Schema, Tool Card and knowledge generators were repeatable with no diff |
| Repository policy before this record | only the missing P0-10 validation-record requirement remained |

The single warning is the existing AnnData duplicate-gene-name warning in a
negative QC fixture. It is unrelated to P0-10.

The first knowledge-generator preflight omitted its required command-line paths
and exited before building the archive. The corrected repository-defined
invocation was clean and repeatable. This was a validation-command error, not a
package failure.

## Runtime and determinism

Five fresh processes used separate output directories and explicit one-thread
limits for OMP, OpenBLAS, MKL and NumExpr.

| Measurement | Exact-commit replication |
|---|---:|
| Wall-clock median | 1.89 s |
| Wall-clock range | 1.70–2.13 s |
| CPU-time median | 1.86 s |
| Peak RAM | 208.43 MB |
| Peak VRAM | 0 MB |
| Result artifact size | 2,004 B |

All five runs had the same run ID, input hash and result-artifact SHA-256. The
artifact SHA-256 was
`b7ce161949963381487a0e58e2fd90416af85d8dbee22c4ce4b4e59a280dff85`.
The packaged benchmark reports an earlier five-run median of 1.93 s and range
of 1.71–2.18 s; the exact-commit replication remained inside that range.

## Method table and current decision

The machine-readable fact source is `P0-10-BENCHMARK-v0.1`, file SHA-256
`4c5ef92f72fce8659c0a0aafa90ede62172e600fe5f4e506a4c224e2121e6ff7`.
All 18 rows bind their review state and reviewer to decision-payload SHA-256
`f8b1a9c6946afddb9005d396037fef8af84b36ff27a0cd1137db27ac196fc373`.

The BRIDGE core was measured end to end. Eight callable components were checked
inside that path rather than assigned misleading per-component runtimes. Nine
alternative methods remain `audit_only`, with explicit `benchmark_only`,
`deferred` or rejected dispositions. There is no aggregate score, aggregate
rank or selected default.

## Anonymous internal report

One server-only engineering report supplied three exact aggregate claims: 929
installed-wheel tests passed, 12 Tool Packages were discovered, and the packaged
knowledge snapshot contained 354 methods. The report used checksummed
`ReportDraft`, `EvidenceRecordSet`, `ClaimPolicySpec` and `StatementRegistry`
objects. Its source manifest SHA-256 was
`5dd856ad463a689e8c5a437454eb0df81eaa378a63e12d5281b80435ce5ec1f2` and
its request SHA-256 was
`e5095c116866fba5eb6e2935989a196c4819c5a165c2bac345a7ced91d7bebae`.
Private paths and object contents remain server-only.

The completed benchmark was generated at commit
`aeb981bc237bd08bd731fd4bd364bee110a4eb93`. Its Git archive SHA-256 was
`8109ea7ccf9802f538ed958e56cea3943c1e96fb2d495ef93e6a26926affa7e7`;
the installed wheel SHA-256 was
`6202634cef5cd8c602d2b4a859d558d6fc2058b4aad68a8d0b15366ac0520141`.
Two explicit one-thread runs produced the same run ID, input hash, ToolRun bytes
and 2,934-byte result artifact. Both returned `verified` with zero blockers,
review items or warnings. Because the report audience was internal,
`public_export_eligibility` correctly remained `ineligible`.

| Internal-report measurement | Result |
|---|---:|
| Claims | 3 |
| Wall-clock median | 2.085 s |
| Wall-clock range | 2.02–2.15 s |
| CPU-time median | 2.055 s |
| Peak RAM | 211.96 MB |
| Peak VRAM | 0 MB |
| Result artifact SHA-256 | `d1b9c40f783dde4c8767b3b2a176665b20bd6f0e78d2ce874a9358707e3f033c` |

The retired Step2/Step3 score reports were not converted or reused, and no
P0-02 controlled or sealed data was opened. The benchmark state is now
`server_validated_candidate`; all nine callable components bind the anonymous
internal case. This completes the package-level internal-run requirement but
does not select a default method.

## Review-hardening addendum — 2026-08-15

Draft-PR review identified seven release-boundary gaps. Commit
`4e95bd46c1554be8b71375bf87dbb73b6c93622e` addresses them without adding a
new framework or implementation module:

- P0-10 now accepts the P0-09 Case graph manifest and opens its checksummed
  graph artifacts; a standalone `EvidenceRecordSet` is no longer an input;
- each claim binds one registered Claim and ProductCase, and every cited
  EvidenceRecord must match both;
- each numeric binding names one source field and one exact, non-overlapping
  text span; arbitrary display suffixes and bundled denominator/interval
  assertions were removed;
- human- or imported-authored prose requires review, while the complete
  `ReportDraft`, including review metadata, is checked before publication;
- broken or self-referential output symlinks return stable failure codes; and
- the repository limit is a fixed 320 tracked files rather than increasing as
  more tools become executable.

The exact Git archive SHA-256 was
`ae138edd6ef9e9671b7e7c40b9587cce395b6d62412a773973203112b325d84e`.
The resulting wheel SHA-256 was
`b0f169d10e478176d2c69ec5616d8162e50daa15157a486ade4f4c516407b721`.
It was installed from `site-packages` in both the evidence and full-suite
validation environments. The private evidence manifest contains 543 files and
has SHA-256
`4ef475c2bd0364ec81d39197f992ca1ba8fb4caf2f818a7e48176d445223fb45`.

| Review-hardening gate | Result |
|---|---|
| P0-09/P0-10/shared-runtime installed-wheel tests | `293 passed` in 12.97 s |
| Complete installed-wheel suite | `940 passed, 1 warning` in 84.52 s |
| Tool discovery | 12 packages; P0-01, P0-02, P0-08, P0-09 and P0-10 implemented |
| Knowledge and repository policy | valid; 354 methods, 387 sources, 396 bindings; policy passed |
| Generated projections | Tool Cards, Schemas and P0-10 benchmark each rendered twice with no diff |
| Repository size | 318 tracked files against the fixed 320-file limit |

For the anonymous engineering check, the installed P0-09 wheel generated one
Case graph containing the 940-test, 12-package and 354-method records. It
accepted all three records and rejected none; the Case manifest SHA-256 was
`7d538783f3e1fb0eff2fa1dac44a61db4a79a2ae95a358e8a1059faf43b8d617`.
The records remain `shadow` and the report claims are `internal_candidate`;
P0-10 `verified` therefore means only that the text matches those supplied
records and policies.

Five one-thread P0-10 processes produced byte-identical ToolRuns with zero
blockers, review items or warnings. Wall-clock median was 2.51 s (range
2.24–2.53 s), CPU-time median was 2.48 s, peak RAM was 226.0 MB and the
3,394-byte result artifact had SHA-256
`c61e881e57f0231c342d0d661a33b69188a0d8b859ea18e633f493e5099ceb33`.
The earlier bare-record-set run above is retained as historical evidence for
the prior interface; it is not accepted by the hardened interface.

## Release-authority addendum — 2026-08-15

A second Draft-PR review found five remaining ways in which a caller or an
invalid result object could overstate what P0-10 had checked. Commit
`7a6bb063627925e2c51ed862faaa108ffd14044b` addresses those findings while
keeping the implementation package-local:

- the accepted `ClaimPolicySpec`, `StatementRegistry`, renderer version and
  template are now pinned by packaged release contract
  `P0-10-RELEASE-CONTRACT-v0.1`;
- a deterministic claim must equal the complete package-rendered ClaimBlock,
  so a caller cannot append unverified scientific prose;
- numeric lexemes adjacent to letters or underscores, including `192tests`,
  `192cells`, `1e3cells` and `192_tests`, cannot bypass numeric binding;
- the result models and public Schemas reject impossible combinations of check
  severity, release state, export eligibility and VerifiedReport presence; and
- the task card now describes only the implemented structured-text interface,
  not future media or review-record fields.

| Exact-commit item | Value |
|---|---|
| Complete-history transfer bundle SHA-256 | `aecb6531019466cb8af0e1368ff0636b98284205a04986a5729f20bdc65e8a26` |
| Git archive SHA-256 | `b6ae9eac1648b6ff12e15558dca4f9cd0ccde40ee6a18e3af9a211e3ef371176` |
| Wheel SHA-256 | `bf20cac695dfe5fdbb869d62558a4da5968a7e62f09a406c475628c89a90896e` |
| Evidence environment contract SHA-256 | `c3398ecb4961defec894eede7c1fdda046168687b9219bed53c0f68a91324d8f` |
| Private evidence manifest | 571 entries; SHA-256 `57794498244ddccf16325ba34fc9171a934a07f04118d7f92e8a8476eb538f53` |

The wheel was built from that exact Git archive and loaded from
`site-packages` in both validation environments. Two complete generator rounds
left the worktree unchanged.

| Release-authority gate | Result |
|---|---|
| P0-09/P0-10/shared-runtime installed-wheel tests | `301 passed` in 16.35 s |
| Complete installed-wheel suite | `948 passed, 1 warning` in 100.79 s |
| Schema, Tool Card, benchmark and example parity | `8 passed` in 2.01 s |
| Null domain-score guards | `5 passed` in 1.51 s |
| Tool discovery | 12 packages; P0-01, P0-02, P0-08, P0-09 and P0-10 implemented |
| Knowledge and repository policy | valid; 354 methods, 387 sources, 396 bindings, no dangling references; policy passed |
| Repository size and privacy | 319 tracked files against the fixed 320-file limit; absolute private-path scan passed |

The one warning remains the unrelated AnnData duplicate-gene-name warning in a
negative QC fixture.

The exact wheel was also run five times with one-thread limits against the
same anonymous three-claim engineering input. The input retains its immutable
929-test evidence record; the newer 948-test suite result above was not
silently substituted. All five runs were eligible, returned `verified` with no
check records, and remained `public_export_eligibility=ineligible`. They shared
run ID `run-fa336d612b6cff05`, input hash
`fa336d612b6cff05ad49b70e8a97d8785452b5ef3ea164d55cacf3ecaba3df6f`
and 2,648-byte result SHA-256
`857a076f9e64dc1ace3c46f9099df47fb682cc39743db8e895afe8cc79af2b40`.

| Exact-wheel internal replication | Result |
|---|---:|
| Wall-clock median | 2.48 s |
| Wall-clock range | 2.10–2.58 s |
| CPU-time median | 2.45 s |
| CPU-time range | 2.08–2.55 s |
| Peak RAM | 225.32 MB |
| Peak VRAM | 0 MB |

The packaged benchmark remains `P0-10-BENCHMARK-v0.1`, SHA-256
`bb25a8d4a272f051e2918fd18999d7bbe424259258c3353dbc258f528f0edc26`.
Its selected default remains `none`; this validation does not supply developer
approval for a default method.

## Boundaries

- A `verified` result means correspondence to supplied evidence and policy, not
  biological truth, scientific sufficiency or publication approval.
- Hard blockers cannot be cleared by human review.
- Free Markdown, LLM decisions, webpages, OCR, images, SVG and caller-supplied
  templates are unavailable in v0.1.
- The tool does not recompute measurements and does not establish efficacy,
  safety, potency, GMP release, a best product or an overall ranking.
- `domain_score` remains `null`; no P0-02 state, threshold or controlled test
  set was changed or opened.

This record is added after the validated implementation commit. The publication
commit must pass the same repository and installed-wheel gates before a Draft PR
is opened.
