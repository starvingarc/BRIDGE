# P0-12 Optional Graft Assessment

## Purpose

Characterize optional post-transplant graft evidence without backfilling product results.

## Contract

| Field | Value |
|---|---|
| Package version | `0.1.0` |
| Runtime state | `scaffold` |
| Scientific state | `candidate` |
| Optional | `yes` |
| EnvironmentSpec | `ENV-P0-CORE-v0.1` |
| Input schema | `bridge://schemas/tool-request/v0.1` |
| Output schema | `bridge://schemas/tool-run/v0.1` |

**Input:** Optional GraftCase with explicit host/model/animal/timepoint/species/preparation linkage plus modality-matched fetal references.

**Output:** Independent GraftAssessment, whole-graft composition, fetal/mDA support, maturation evidence, sensitivity, and optional descriptive linkage record.

**Runtime behavior:** Discoverable contract only; `run` returns `not_implemented` without scientific results.

## Refusal Conditions

No graft returns `not_provided`; missing animal IDs or confounded designs force descriptive mode; implicit preparation linkage is forbidden.

Missing, unknown, unavailable, negative, and alert states remain distinct. No package may infer a clinical, safety, potency, GMP-release, or absolute product-ranking claim.

## Visualization Contract

Whole-graft composition, mDA/reference support, maturation programs, animal/timepoint variation, sensitivity, and linkage Evidence Graph.

Every formal chart must retain its data version, denominator, units, evidence references, and missing-state semantics.

## Validation Before Freeze

Metadata contracts, source/lab/modality holdouts, mixtures, species contamination, downsampling, reference swaps, and no score backfill.

Method documentation and accessible sources do not constitute benchmark completion. The registered method IDs are returned by `bridge-tool describe P0-12`.

## Detailed Scientific Requirement

Repository document: `docs/bridge_v2_spec_v0.1/graft_assessment_task_card.md`.
