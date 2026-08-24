# P0-01 Input Audit & QC

## Purpose

Validate expression inputs and emit a QC readiness profile.

## Contract

| Field | Value |
|---|---|
| Package version | `0.1.0` |
| Runtime state | `implemented` |
| Scientific state | `candidate` |
| Optional | `no` |
| EnvironmentSpec | `ENV-P0-CORE-v0.1` |
| Input schema | `bridge://schemas/tool-request/v0.1` |
| Output schema | `bridge://schemas/tool-run/v0.1` |

**Input:** A declared h5ad, 10x H5, or 10x MTX asset; input level, assay, matrix semantics, sample/capture metadata, gene-identifier source, and output location.

**Output:** Raw structural and QC metrics, `QCReadinessProfile`, physical candidate data views when a candidate MeasurementSpec is selected, visualizations, and a checksummed artifact manifest. Each published view has a `DataViewBinding` with its artifact checksum, matrix semantics, exact cell count and deterministic cell-index checksum; a QC-selected view is a real subset, not a renamed pointer to the all-cells matrix.

**Runtime behavior:** Executable candidate; it emits raw measurements and never emits a domain score.

## Refusal Conditions

Unreadable or ambiguous matrix, duplicate identifiers, invalid count semantics, missing assay, inconsistent sample/capture/batch/preparation hierarchy, unsupported MeasurementSpec/input-level pairing, an incomplete declared gene-symbol column, or an output directory nested inside a directory input. Each capture must map to one declared parent value, and each preparation must map to one sample; one biological sample may legitimately have multiple preparations.

Missing, unknown, unavailable, negative, and alert states remain distinct. No package may infer a clinical, safety, potency, GMP-release, or absolute product-ranking claim.

## Visualization Contract

Per-sample QC distributions and counts-versus-detected-genes diagnostics with explicit denominators.

Every formal chart must retain its data version, denominator, units, evidence references, and missing-state semantics.

## Validation Before Freeze

Format fixtures, scRNA/snRNA contracts, matrix-semantic failures, deterministic reruns, input immutability, and optional Scrublet eligibility.

Method documentation and accessible sources do not constitute benchmark completion. The registered method IDs are returned by `bridge-tool describe P0-01`.

## Detailed Scientific Requirement

Repository document: `docs/bridge_spec_v0.1/input_audit_qc_task_card.md`.
