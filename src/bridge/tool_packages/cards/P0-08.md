# P0-08 Evidence Sufficiency

## Purpose

Apply deterministic data, model and prior sufficiency gates.

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

**Input:** QCReadinessProfile, domain MeasurementResults, benchmark and sensitivity records, and frozen reference/prior/contract versions.

**Output:** Per-domain EvidenceSufficiencyProfile across data readiness, model robustness, and prior applicability, with deterministic reason codes.

**Runtime behavior:** Discoverable contract only; `run` returns `not_implemented` without scientific results.

## Refusal Conditions

Missing gate specification, absent required upstream record, non-applicable method/prior, or unstable evidence needed for interpretation.

Missing, unknown, unavailable, negative, and alert states remain distinct. No package may infer a clinical, safety, potency, GMP-release, or absolute product-ranking claim.

## Visualization Contract

Three-axis sufficiency matrix, blocking reasons, domain state summary, and upstream evidence trace.

Every formal chart must retain its data version, denominator, units, evidence references, and missing-state semantics.

## Validation Before Freeze

Independent domain gating, missing-state semantics, evidence-family de-duplication, legacy-score exclusion, and deterministic repeatability.

Method documentation and accessible sources do not constitute benchmark completion. The registered method IDs are returned by `bridge-tool describe P0-08`.

## Detailed Scientific Requirement

Repository document: `docs/bridge_spec_v0.1/evidence_sufficiency_task_card.md`.
