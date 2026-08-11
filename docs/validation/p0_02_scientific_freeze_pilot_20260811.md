# P0-02 Cell-State Evidence Pilot

**Date:** 2026-08-11

**Status:** `awaiting_biological_review`

**Scope:** development-only scRNA-seq pilot; no scientific release

## Biological question

Can fetal ventral-midbrain references identify intended states in a pre-transplant
hPSC-mDA product and refuse cells whose identity lies outside the reference?

Reliable answers are required before BRIDGE can report target-cell composition,
regional fidelity, developmental compatibility or off-target composition.

## Data and biological controls

| Logical asset | Biological role | Cells/profiles |
|---|---|---:|
| Chen vMB scRNA L1 | Broad fetal ventral-midbrain states | 61,455 |
| Chen RG/Nb scRNA L2 | Seven priority progenitor and neuroblast states | 11,366 |
| GSE190729 | Cortical/cerebral OOD | 17,636 |
| GSE221853 | Neural-crest OOD | 29,857 |
| GSE267791 | Motor-neuron OOD | 1,341 |
| GSE224152 | Mesenchymal OOD | 1,771 |
| GSE204796 | Product differentiation time course; behavior check only | 37,397 |

The La Manno source-family holdout, three locked OOD families and the sealed
competitor test were not opened. They had no influence on reference construction,
marker review, method selection or proposed gates.

## What the pilot found

### Broad fetal ventral-midbrain states

CellTypist and scANVI recovered many L1 labels across donor-aware internal splits.
CellTypist had the lowest product-composition error among the inductive methods,
while scANVI also performed well. These are development observations, not evidence
that either method is ready for product use.

### Fine RG/Nb-derived states

scANVI separated the seven L2 states more accurately than the transparent
correlation and marker baselines. Its pilot was transductive, however, and no
independent external label source has yet confirmed these fine states. scConform,
used only as a prediction-set/hierarchical coverage layer over a preregistered base
classifier, covered 83.3% of L2 true labels against a nominal 90% target. This does
not establish a standalone OOD detector or sufficient abstention behavior.

### Unrelated cells are still forced into known labels

The tested inductive correlation, marker and CellTypist channels assigned all four
OOD datasets to known fetal ventral-midbrain labels instead of refusing them. Their
development-OOD false-reassurance rate was 1.0. This is the most important current
failure: a confident label may still represent cortex, motor neuron, neural crest
or mesenchymal identity.

### Marker evidence is incomplete

Twenty-five state cards exist, covering 18 L1 states and seven priority L2 states,
but all remain pending. `Neuron_ChAT` and `Neuron_OMTN` lack reviewed negative
markers; `Neuron_Glut_GABA` has no complete marker card; and all seven L2 states
lack frozen positive and negative marker cards. The marker channel therefore cannot
yet serve as an independent biological check.

## Meaning for product evaluation

BRIDGE can currently produce an exploratory, source-aware view of how product cells
relate to fetal ventral-midbrain states. It cannot yet formally state:

- what fraction of a product is the intended mDA lineage;
- whether the product has the intended ventral-midbrain regional identity;
- what fraction is a known off-target lineage;
- whether an unassigned or unusual population is truly absent.

The output remains `shadow`, `domain_score=null`. It does not validate product
efficacy, safety, potency, GMP release or overall quality.

## Biological issues still unresolved

1. The definitions, developmental context and marker logic of all 25 states remain under review.
2. ProductDefinitionCard and StateRoleMap are not approved, so cell-state labels cannot yet be translated into target, adjacent or off-target product roles.
3. The 328 historical conflicts remain excluded, including 25 RG-to-Pericyte records.
4. Current methods either force OOD assignments or lack a completed OOD assessment.
5. Gene masking, sample-preserving downsampling and preprocessing sensitivity remain unassessed.
6. Locked external-source and OOD tests have not run.

No state has passed an approved per-state gate. P0-03 remains blocked until the
biological definitions and locked-test rules are fixed and the locked test is
completed without tuning.

## Method details

Accuracy measures overall label recovery, macro-F1 gives rare states equal weight,
and composition MAE measures error in the estimated product composition.

| Method | L1 accuracy / macro-F1 / composition MAE | L2 accuracy / macro-F1 / composition MAE | Limitation for product use |
|---|---|---|---|
| Source-specific correlation | 0.671 / 0.583 / 0.037 | 0.531 / 0.500 / 0.088 | Forced OOD assignment |
| Marker/program evidence | 0.427 / 0.399 / 0.080 | Not assessed | Incomplete marker cards; forced OOD assignment |
| CellTypist custom | 0.829 / 0.799 / 0.010 | 0.747 / 0.776 / 0.045 | Forced OOD assignment |
| scmap | 0.651 / 0.560 / 0.035 | 0.549 / 0.500 / 0.106 | OOD not assessed |
| scANVI | 0.803 / 0.745 / 0.014 | 0.810 / 0.811 / 0.039 | Transductive pilot; OOD not assessed |
| Symphony | 0.730 / 0.635 / 0.024 | 0.721 / 0.746 / 0.054 | OOD not assessed |
| scConform over scANVI | 0.803 / 0.745 / 0.014 | 0.810 / 0.811 / 0.039 | Coverage 0.902 / 0.833; not independent biological evidence |
| SingleR | No complete L1 result | Partial L2 output excluded | Exceeded the 3,600-second development budget |

SingleR and scmap belong to the same reference-similarity evidence family.
scConform wraps the preregistered scANVI base probabilities to assess prediction-set
coverage and is not counted as an independent OOD detector or biological evidence
source. No method was selected or frozen from this pilot.

## Engineering record

| Record | Value |
|---|---|
| Pilot run | `CELLSTATE-PILOT-e45ada3778e2` |
| Evidence run | `CELLSTATE-EVIDENCE-3268ddfd0caf` |
| Split manifest SHA-256 | `84685ea4ee2cea136ed973562c6a9a7ddd631fd9201f245befcc34e55de06504` |
| Evidence artifact SHA-256 | `ffe78a0ba64f632b4cb25191062e91fc053de22e11bf4aa5b5f9e91a864e1590` |
| Locked assets opened | `false` |
| Sealed assets opened | `false` |
| Historical local Python 3.12 suite | 171 passed, 3 warnings; diagnostic only, not current formal evidence |
| Server Python 3.12 suite | 171 passed, 2 warnings |

Repeated summaries were byte-identical and retained the same Evidence ID.
