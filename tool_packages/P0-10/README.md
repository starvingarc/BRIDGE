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
| EnvironmentSpec | `ENV-EVIDENCE-v0.1` (`health_check_passed`) |
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
SHA-256 checksum, Schema URI and matching object version.

| Role | Schema | Meaning |
|---|---|---|
| `report_draft` | `bridge://schemas/report-draft/v0.1` | Ordered plain-text ClaimBlocks, ValueBindings and optional human review decisions |
| `evidence_graph_manifest` | `bridge://schemas/case-evidence-graph-manifest/v0.1` | P0-09 Case graph manifest whose hashes, graph and EvidenceRecord projection pass the read-only integrity boundary |
| `claim_policy_spec` | `bridge://schemas/claim-policy-spec/v0.1` | Claim-type, severity, bilingual text and comparison rules; the object must equal the policy in the packaged release contract |
| `statement_registry` | `bridge://schemas/statement-registry/v0.1` | Fixed boundary statements and language variants; the object must equal the registry in the packaged release contract |

Expression assets, free Markdown, caller templates, top-level MeasurementSpecs
and arbitrary parameters are refused. A report hash mismatch, wrong role,
duplicate or changed input, unsupported media type, path alias, Schema mismatch
or checksum mismatch produces a failed run with a typed reason code.

## Deterministic checks

The verifier runs these checks in a fixed order:

1. Report hash, four-object binding and complete P0-09 graph integrity.
2. Claim/ProductCase-to-Evidence and Statement references.
3. Evidence lifecycle, applicability, tier and reported state.
4. One-field/one-span `Decimal` bindings for each rendered value, unit,
   denominator or interval endpoint.
5. Unbound numeric tokens and descriptive-versus-inferential comparison scope.
6. Bounded Unicode bilingual policy patterns and exact Statement exceptions.
7. Whole-report private-content checks, packaged policy/statement authority and
   authorized resolution of policy review items.
8. Full ClaimBlock reconstruction with the packaged renderer, then
   release-state aggregation.

A human decision cannot clear a hard blocker. LLM judgment, OPA, free-Markdown
recovery, web rendering, OCR and media checks do not enter the v0.1 formal path.

## Output

A successful verifier execution emits one checksummed
`claim_verifier_run_result.json` artifact. It contains:

- `ClaimVerificationResult` with deterministic check IDs, reason codes,
  claim-to-Evidence map, public-export eligibility, the packaged release
  contract hash and the exact benchmark ID/hash;
- one structured `VerifiedReport` only for `verified` or
  `verified_with_warnings`; redundant counts and rendered-text hashes are not
  stored because they can be derived from the checks and immutable artifact.

`release_blocked` is a successful verification finding, not an executor
failure. A policy or Statement Registry that does not match the packaged
release contract is rejected before verification.
No measurement, domain score or visualization is created.

## Method benchmark and selection

The machine-readable fact source is packaged as
`bridge.tool_packages.p0_10_claim_verifier.resources/benchmark_v0.1.json`.
Its human projection is [BENCHMARK.md](https://github.com/starvingarc/BRIDGE/blob/main/tool_packages/P0-10/BENCHMARK.md).

| Field | Value |
|---|---|
| Benchmark ID | `P0-10-BENCHMARK-v0.1` |
| Benchmark version | `0.1.0` |
| Benchmark JSON SHA-256 | `bb25a8d4a272f051e2918fd18999d7bbe424259258c3353dbc258f528f0edc26` |
| Current benchmark state | `server_validated_candidate` |
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

The exact server wheel, public record, synthetic controls and five single-thread
timing repetitions have been validated. A separate anonymous internal
engineering report supplied three exact aggregate claims through the four-object
contract; two one-thread repetitions were byte-identical and produced no
blocker, review item or warning. No private path, old score report or P0-02
controlled data enters the benchmark. The selected default remains unset.

Server evidence: [P0-10 candidate validation, 2026-08-14](https://github.com/starvingarc/BRIDGE/blob/main/docs/validation/p0_10_claim_verifier_20260814.md).

Detailed requirement:
`docs/bridge_spec_v0.1/claim_verifier_task_card.md`.
