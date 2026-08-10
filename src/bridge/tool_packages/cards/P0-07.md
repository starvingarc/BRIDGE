# P0-07 Product Comparison & Stability

## Purpose

Compare products, timepoints and preparations under an explicit comparability contract.

## Contract

| Field | Value |
|---|---|
| Package version | `0.1.0` |
| Runtime state | `scaffold` |
| Scientific state | `candidate` |
| Optional | `no` |
| EnvironmentSpec | `ENV-P0-CORE-v0.1` |
| Input schema | `bridge://schemas/tool-request/v0.1` |
| Output schema | `bridge://schemas/tool-run/v0.1` |

**Input:** Version-matched ProductEvidenceObjects, comparability contract, independent preparation map, domain raw evidence, and Evidence Sufficiency states.

**Output:** Versioned ComparisonRecord with comparability mode, deltas, effect sizes, intervals, stability, Pareto state, and sensitivity evidence.

**Runtime behavior:** Discoverable contract only; `run` returns `not_implemented` without scientific results.

## Refusal Conditions

Contract mismatch, complete protocol/lab/batch confounding, absent independent preparation, or inferential claims from descriptive-only data.

Missing, unknown, unavailable, negative, and alert states remain distinct. No package may infer a clinical, safety, potency, GMP-release, or absolute product-ranking claim.

## Visualization Contract

Effect-size forest, composition differences, timelines, batch distances, program heatmaps, Pareto matrix, and integration sensitivity.

Every formal chart must retain its data version, denominator, units, evidence references, and missing-state semantics.

## Validation Before Freeze

Known shifts and nulls, paired/unpaired designs, insufficient replication, over-correction checks, and independent-versus-joint consistency.

Method documentation and accessible sources do not constitute benchmark completion. The registered method IDs are returned by `bridge-tool describe P0-07`.

## Detailed Scientific Requirement

Repository document: `docs/bridge_v2_spec_v0.1/product_comparison_stability_task_card.md`.
