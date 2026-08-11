# P0-09 Evidence Compiler & Reconciler

## Purpose

Compile atomic evidence and reconcile conflicts by versioned rules.

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

**Input:** MeasurementResults, ToolRuns, Evidence Sufficiency, versioned contracts, references, priors, and artifact manifests.

**Output:** Atomic EvidenceRecords, immutable Case/Comparison Evidence Graph projections, and deterministic reconciliation states.

**Runtime behavior:** Discoverable contract only; `run` returns `not_implemented` without scientific results.

**Method selection:** No method is selected while this package remains a scaffold.

## Refusal Conditions

Invalid schema, dangling provenance, duplicate logical evidence, forbidden lifecycle/tier, or LLM-authored numeric/reconciliation changes.

Missing, unknown, unavailable, negative, and alert states remain distinct. No package may infer a clinical, safety, potency, GMP-release, or absolute product-ranking claim.

## Visualization Contract

Claim neighborhood, provenance, evidence-family grouping, conflicts, missing requirements, and comparison subgraphs.

Every formal chart must retain its data version, denominator, units, evidence references, and missing-state semantics.

## Validation Before Freeze

Idempotence, append-only correction, family de-duplication, missing-versus-zero semantics, graph round trips, and read-only Agent access.

Method documentation and accessible sources do not constitute benchmark completion. No method is registered or selected until benchmark-bound execution exists.

## Detailed Scientific Requirement

Repository document: `docs/bridge_spec_v0.1/evidence_compiler_task_card.md`.
