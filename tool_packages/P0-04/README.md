# P0-04 Developmental Compatibility

## Purpose

Measure compatibility with a researcher-confirmed developmental window.

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

**Input:** Confirmed DevelopmentWindowSpec, Cell-State soft composition, fetal references, real in-vitro timepoints, and optional lineage calibration data.

**Output:** Static or time-course developmental profile, two denominators, window/earlier/later/branch-shift fractions, reference-stage support, and sensitivity.

**Runtime behavior:** Discoverable contract only; `run` returns `not_implemented` without scientific results.

**Method selection:** No method is selected while this package remains a scaffold.

## Refusal Conditions

Unconfirmed window, single timepoint requested as a trajectory, insufficient replicates for inference, or unsupported fetal-age conversion.

Missing, unknown, unavailable, negative, and alert states remain distinct. No package may infer a clinical, safety, potency, GMP-release, or absolute product-ranking claim.

## Visualization Contract

Stage composition, real-D timeline, reference-stage support, program trends, sensitivity, and calibration-only lineage alluvial plots.

Every formal chart must retain its data version, denominator, units, evidence references, and missing-state semantics.

## Validation Before Freeze

Source/timepoint/state holdouts, mixtures, branch shifts, downsampling, modality swaps, and replicate-aware lineage-transition reconstruction.

Method documentation and accessible sources do not constitute benchmark completion. No method is registered or selected until benchmark-bound execution exists.

## Detailed Scientific Requirement

Repository document: `docs/bridge_spec_v0.1/developmental_compatibility_task_card.md`.
