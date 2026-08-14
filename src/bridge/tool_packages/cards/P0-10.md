# P0-10 Claim Verifier

## Purpose

Verify that each structured report claim preserves its cited Evidence value, unit,
denominator, interval, evidence state, comparison scope and approved wording.

## Contract

| Field | Value |
|---|---|
| Package version | `0.1.0` |
| Runtime state | `implemented` |
| Scientific state | `candidate` |
| Optional | `no` |
| EnvironmentSpec | `ENV-EVIDENCE-v0.1` (`proposed`) |
| Input envelope | `bridge://schemas/tool-request/v0.2` |
| Output envelope | `bridge://schemas/tool-run/v0.2` |
| Result schema | `bridge://schemas/claim-verifier-run-result/v0.1` |
| Adapter | `bridge.tool_packages.p0_10_claim_verifier.adapter:adapter` |

The SDK entry points are `ToolRegistry.load_default().check_eligibility(request)`
and `.run(request)` with `ToolRequestV2`. The CLI equivalents are:

```bash
bridge-tool validate --request /absolute/path/to/p0_10_request.json
bridge-tool run --request /absolute/path/to/p0_10_request.json
```

The committed example is documentation-only and contains placeholder paths and
checksums: `examples/requests/p0_10_claim_verifier.json`.

## Structured inputs

P0-10 accepts exactly four immutable `application/json` objects. Every
`StructuredInputRef` requires an absolute regular-file path, exact lowercase
SHA-256 checksum, Schema URI and `object_version=0.1.0`.

| Role | Schema | Meaning |
|---|---|---|
| `report_draft` | `bridge://schemas/report-draft/v0.1` | Ordered plain-text ClaimBlocks, ValueBindings and optional human review decisions |
| `evidence_record_set` | `bridge://schemas/evidence-record-set/v0.1` | Versioned upstream EvidenceRecords produced by the evidence compiler |
| `claim_policy_spec` | `bridge://schemas/claim-policy-spec/v0.1` | Claim-type, severity, bilingual text and comparison rules |
| `statement_registry` | `bridge://schemas/statement-registry/v0.1` | Approved fixed boundary statements and exact language variants |

Expression assets, free Markdown, caller templates, top-level MeasurementSpecs
and arbitrary parameters are refused. A report hash mismatch, wrong role,
duplicate or changed input, unsupported media type, path alias, Schema mismatch
or checksum mismatch produces a failed run with a typed reason code.

## Deterministic checks

The verifier runs these checks in a fixed order:

1. Report hash and four-object binding.
2. Claim-to-Evidence and Statement references.
3. Evidence lifecycle, applicability, tier and reported state.
4. Exact `Decimal` value, unit, denominator, interval, rounding and rendered
   value fidelity.
5. Unbound numeric tokens and descriptive-versus-inferential comparison scope.
6. Bounded Unicode bilingual policy patterns and exact Statement exceptions.
7. Authorized human resolution of review-only findings.
8. Release-state aggregation and controlled Jinja rendering.

A human decision cannot clear a hard blocker. LLM judgment, OPA, free-Markdown
recovery, web rendering, OCR and media checks do not enter the v0.1 formal path.

## Output

A successful verifier execution emits one checksummed
`claim_verifier_run_result.json` artifact. It contains:

- `ClaimVerificationResult` with deterministic check IDs, reason codes,
  blocker/review/warning counts, claim-to-Evidence map and public-export
  eligibility;
- `VerifiedReport` only for `verified` or `verified_with_warnings`;
- the exact packaged benchmark ID and benchmark JSON SHA-256.

`release_blocked` is a successful verification finding, not an executor
failure. An inactive policy returns `not_assessed` and a partial ToolRun.
No measurement, domain score or visualization is created.

## Method benchmark and selection

The machine-readable fact source is packaged as
`bridge.tool_packages.p0_10_claim_verifier.resources/benchmark_v0.1.json`.
Its human projection is [BENCHMARK.md](https://github.com/starvingarc/BRIDGE/blob/main/tool_packages/P0-10/BENCHMARK.md).

| Field | Value |
|---|---|
| Benchmark ID | `P0-10-BENCHMARK-v0.1` |
| Benchmark version | `0.1.0` |
| Benchmark JSON SHA-256 | `3c5ac1c25b86027c32522a1d1774c2c6f32dbc9c363b6aa6585328e54aa5e9df` |
| Current benchmark state | `awaiting_server_validation` |
| Selected default | `none` |
| Aggregate score/rank | `null` / `null` |

Methods are grouped by structured-contract validation, numeric fidelity,
bilingual rules, controlled rendering, release aggregation and external
factuality audit. Candidate approval does not select a default. Changing a
default requires a new benchmark version and PR; prior tables and results remain
immutable.

## Refusal and scientific boundary

Hard blockers include missing or invalid Evidence, inactive/superseded or
inapplicable Evidence used as formal support, state substitution, numeric/unit/
denominator/interval drift, unbound numbers, inferential wording in a
descriptive comparison, prohibited clinical or ranking claims, graft leakage,
private paths and any change after verification.

The tool verifies correspondence to existing evidence and policy. It does not
validate biological truth, recompute an analysis, infer efficacy, safety,
potency or GMP release, or compare products. `domain_score` remains `null`
and `score_state` remains unavailable.

## Validation boundary

The package remains a candidate until the exact wheel is built and tested on the
server, deterministic reruns and five timing repetitions are recorded, the
public record and an authorized anonymized internal report are run, and the
benchmark JSON and Markdown projection are updated from that evidence.

Detailed requirement:
`docs/bridge_spec_v0.1/claim_verifier_task_card.md`.
