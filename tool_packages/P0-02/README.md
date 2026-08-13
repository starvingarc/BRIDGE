# P0-02 Cell-State Evidence

## Biological purpose

Test whether a pre-transplant product supports reviewed fetal ventral-midbrain cell
states while leaving unrelated neural and non-neural cells unresolved.

## Current biological status

- Broad fetal VM states can be explored in donor-held-out internal scRNA-seq data.
- Fine RG/Nb-derived states remain provisional because marker and external-source
  support are incomplete.
- Current inductive methods force cortical, motor-neuron, neural-crest and
  mesenchymal OOD cells into known fetal VM labels.
- Formal target, regional-fidelity and off-target composition conclusions are
  therefore unavailable.

No state or method is frozen. The next scientific step is review of the 25 state
definitions and marker cards, followed by locked external-source and OOD testing.

## Tool purpose

Produce source-aware reference and marker-program evidence against the internal hierarchical annotation vocabulary.

## Contract

| Field | Value |
|---|---|
| Package version | `0.4.8` |
| Runtime state | `implemented` |
| Scientific state | `candidate` |
| Freeze state | `biological_review_in_progress` |
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

The unsealed scRNA pilot is complete. No state or method is frozen; biological review, signed gates and locked testing remain required.

## Detailed Scientific Requirement

Repository document: `docs/bridge_spec_v0.1/cell_state_annotation_task_card.md`.
