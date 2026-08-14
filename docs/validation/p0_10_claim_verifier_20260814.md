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
`7335445beb1204e42463a413dd76ac91cd652bc14072b104a10ad37d5475fe5b`.
All 18 rows bind their review state and reviewer to decision-payload SHA-256
`95a2a7d4a85808f560e4a1e47a15fec3503f6cbdc12d136c1eb1b5b2dba6e253`.

The BRIDGE core was measured end to end. Eight callable components were checked
inside that path rather than assigned misleading per-component runtimes. Nine
alternative methods remain `audit_only`, with explicit `benchmark_only`,
`deferred` or rejected dispositions. There is no aggregate score, aggregate
rank or selected default.

## Internal-report gap

No compatible authorized internal four-object report was present on the server.
The available older report artifacts use the retired Step2/Step3 score format
and cannot be treated as P0-10 evidence. They were not converted or reused.

Accordingly, the benchmark state is
`server_validated_public_candidate`, the internal row remains `not_run`, and the
package has not yet met the plan's complete-package requirement. Completing the
remaining run requires a private manifest identifying one authorized
`ReportDraft`, `EvidenceRecordSet`, `ClaimPolicySpec` and `StatementRegistry`.
Only anonymous input scale and aggregate results will be recorded publicly.

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
