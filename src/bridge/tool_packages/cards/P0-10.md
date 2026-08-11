# P0-10 Claim Verifier

## Purpose

Verify that report claims, values and visualizations match evidence and policy.

## Contract

| Field | Value |
|---|---|
| Package version | `0.1.0` |
| Runtime state | `scaffold` |
| Scientific state | `candidate` |
| Optional | `no` |
| EnvironmentSpec | `ENV-EVIDENCE-v0.1` |
| Input schema | `bridge://schemas/tool-request/v0.1` |
| Output schema | `bridge://schemas/tool-run/v0.1` |

**Input:** Structured ReportDraft, ClaimBlocks, ValueBindings, evidence/knowledge/statement references, chart artifacts, and policy versions.

**Output:** ClaimVerificationResult and immutable VerifiedReport reference with blockers, warnings, traceability map, and release state.

**Runtime behavior:** Discoverable contract only; `run` returns `not_implemented` without scientific results.

**Method selection:** No method is selected while this package remains a scaffold.

## Refusal Conditions

Numeric mismatch, invalid evidence, state substitution, unsupported inference, prohibited claim, graft leakage, or unresolved semantic review.

Missing, unknown, unavailable, negative, and alert states remain distinct. No package may infer a clinical, safety, potency, GMP-release, or absolute product-ranking claim.

## Visualization Contract

Claim-to-evidence map, check results, blocked text spans, chart-binding status, and human-review queue.

Every formal chart must retain its data version, denominator, units, evidence references, and missing-state semantics.

## Validation Before Freeze

Exact value copying, bilingual fixtures, prohibited claims, chart bindings, LLM failure, immutable report hashes, and blocker non-override.

Method documentation and accessible sources do not constitute benchmark completion. The registered method IDs are returned by `bridge-tool describe P0-10`.

## Detailed Scientific Requirement

Repository document: `docs/bridge_spec_v0.1/claim_verifier_task_card.md`.
