# P0-06 Process Integrity

## Purpose

Measure stage-conditioned process programs and transcriptomic review signals.

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

**Input:** QC-qualified expression, Cell-State evidence, confirmed developmental context, ProtocolIR metadata, and versioned process-program knowledge.

**Output:** State-conditioned program evidence, residual-pluripotency LOD, cycling identity, confounding record, and transcriptomic review flags.

**Runtime behavior:** Discoverable contract only; `run` returns `not_implemented` without scientific results.

## Refusal Conditions

Missing stage context for stage-dependent interpretation, insufficient marker/program coverage, or process attribution without protocol metadata.

Missing, unknown, unavailable, negative, and alert states remain distinct. No package may infer a clinical, safety, potency, GMP-release, or absolute product-ranking claim.

## Visualization Contract

Program effect profiles, state-stratified distributions, rare-state LOD, process covariates, review flags, and sensitivity.

Every formal chart must retain its data version, denominator, units, evidence references, and missing-state semantics.

## Validation Before Freeze

Perturbation direction recovery, pluripotent-cell spike-ins, source/cell-line/modality holdouts, program overlap, and false-flag testing.

Method documentation and accessible sources do not constitute benchmark completion. The registered method IDs are returned by `bridge-tool describe P0-06`.

## Detailed Scientific Requirement

Repository document: `docs/bridge_spec_v0.1/process_integrity_task_card.md`.
