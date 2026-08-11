# P0-02 Cell-State Evidence

## Purpose

Produce source-aware reference and marker-program evidence against the internal hierarchical annotation vocabulary.

## Contract

| Field | Value |
|---|---|
| Package version | `0.4.0` |
| Runtime state | `implemented` |
| Scientific state | `candidate` |
| Optional | `no` |
| EnvironmentSpec | `ENV-P0-CORE-v0.1` |
| Input schema | `bridge://schemas/tool-request/v0.1` |
| Output schema | `bridge://schemas/tool-run/v0.1` |

**Input:** QC-qualified expression views, declared scRNA/snRNA modality, internal annotation vocabulary, frozen reference candidates, and provenance.

**Output:** Hierarchical prediction sets, soft assignments, uncertainty, method disagreement, unknown reasons, and product-level composition evidence.

**Runtime behavior:** Executable candidate; it emits raw measurements and never emits a domain score.

## Refusal Conditions

Reference or vocabulary mismatch, absent required genes, unresolved modality shift, or no method combination passing the state-axis benchmark.

Missing, unknown, unavailable, negative, and alert states remain distinct. No package may infer a clinical, safety, potency, GMP-release, or absolute product-ranking claim.

## Visualization Contract

Prediction-set composition, reference support, method agreement, uncertainty, OOD, and label-provenance views.

Every formal chart must retain its data version, denominator, units, evidence references, and missing-state semantics.

## Validation Before Freeze

Source/lab/modality holdouts, leave-one-state-out, rare-state mixtures, calibration, OOD detection, and product-composition error.

Method documentation and accessible sources do not constitute benchmark completion. The registered method IDs are returned by `bridge-tool describe P0-02`.

## Detailed Scientific Requirement

Repository document: `docs/bridge_spec_v0.1/cell_state_annotation_task_card.md`.
