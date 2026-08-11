# P0-05 Off-target Control

## Purpose

Describe whole-product non-target composition, OOD and rare-state detectability.

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

**Input:** Frozen Cell-State prediction sets, ProductDefinitionCard role table, eligible-cell denominator, and rare-state/OOD calibration records.

**Output:** Whole-product soft composition, role-resolved non-target evidence, unknown reasons, rare-state detection limits, and sensitivity.

**Runtime behavior:** Discoverable contract only; `run` returns `not_implemented` without scientific results.

## Refusal Conditions

Missing full-product denominator, unresolved product role, uncalibrated OOD method, or a zero observation presented as biological absence.

Missing, unknown, unavailable, negative, and alert states remain distinct. No package may infer a clinical, safety, potency, GMP-release, or absolute product-ranking claim.

## Visualization Contract

Whole-product composition, off-axis drill-down, unknown reasons, OOD calibration, rare-state LOD/UCB, and method sensitivity.

Every formal chart must retain its data version, denominator, units, evidence references, and missing-state semantics.

## Validation Before Freeze

Real OOD panels, source-family holdouts, known mixtures, rare-state spike-ins, downsampling, and reference/preprocessing swaps.

Method documentation and accessible sources do not constitute benchmark completion. The registered method IDs are returned by `bridge-tool describe P0-05`.

## Detailed Scientific Requirement

Repository document: `docs/bridge_spec_v0.1/off_target_control_task_card.md`.
