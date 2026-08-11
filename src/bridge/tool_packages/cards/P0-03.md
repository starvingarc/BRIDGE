# P0-03 Target Identity & Regional Fidelity

## Purpose

Measure target lineage identity and ventral-midbrain regional support.

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

**Input:** Frozen Cell-State evidence, ProductDefinitionCard, internal ventral-midbrain vocabulary, and eligible reference/spatial evidence.

**Output:** Separate target-lineage and regional-fidelity raw evidence, conflicts, uncertainty, sensitivity, and applicability state.

**Runtime behavior:** Discoverable contract only; `run` returns `not_implemented` without scientific results.

## Refusal Conditions

Unconfirmed product target, insufficient reference coverage, unresolved regional vocabulary, or unstable evidence across registered channels.

Missing, unknown, unavailable, negative, and alert states remain distinct. No package may infer a clinical, safety, potency, GMP-release, or absolute product-ranking claim.

## Visualization Contract

Target and regional composition, reference support, spatial support, evidence conflicts, and method/reference sensitivity.

Every formal chart must retain its data version, denominator, units, evidence references, and missing-state semantics.

## Validation Before Freeze

Anatomical/source holdouts, OOD regions, marker masking, reference swaps, modality checks, and source-family de-duplication.

Method documentation and accessible sources do not constitute benchmark completion. The registered method IDs are returned by `bridge-tool describe P0-03`.

## Detailed Scientific Requirement

Repository document: `docs/bridge_spec_v0.1/target_regional_identity_task_card.md`.
