# P0-02 Cell-State Scientific Freeze Pilot

**Date:** 2026-08-11
**Status:** `awaiting_biological_review`
**Scope:** development-only scRNA pilot; no scientific release

## Data boundary

The pilot used donor-aware rotations from the Chen scRNA reference, four declared development OOD datasets and one behavior-only product time course.

| Logical asset | Role | Observations |
|---|---|---:|
| Chen vMB scRNA L1 | development reference | 61,455 |
| Chen RG/Nb scRNA L2 | development reference | 11,366 |
| GSE190729 | development OOD | 17,636 |
| GSE221853 | development OOD | 29,857 |
| GSE267791 | development OOD | 1,341 |
| GSE224152 | development OOD | 1,771 |
| GSE204796 | behavior-only time course | 37,397 |

The La Manno source-family holdout and three locked OOD families were not opened. The sealed competitor test was not opened and had no data flow into reference construction, method selection, marker review or gate design.

## Biological review draft

- 25 Review Cards were generated: 18 L1 states and seven priority L2 states.
- All cards remain `pending`; no state is frozen.
- `Neuron_Chat` is normalized to `Neuron_ChAT`.
- 328 historical conflicts remain excluded and auditable, including 25 RG-to-Pericyte records.
- The L1 marker snapshot remains `shadow_candidate`. `Neuron_ChAT` and `Neuron_OMTN` lack reviewed negative markers, and `Neuron_Glut_GABA` has no marker card.
- The seven L2 states have no frozen positive and negative marker cards. Their maximum future release state remains `provisional_frozen` until independent evidence is available.
- ProductDefinitionCard and StateRoleMap review are pending, so Target Identity and Regional Fidelity are not executed.

## Pilot execution

The final run uses `CELLSTATE-BENCHMARK-scRNA-pilot-v0.2`, source-and-sample isolation, separate calibration partitions and the two declared Cell-State environment contracts.

| Record | Value |
|---|---|
| Run | `CELLSTATE-PILOT-e45ada3778e2` |
| Split manifest SHA-256 | `84685ea4ee2cea136ed973562c6a9a7ddd631fd9201f245befcc34e55de06504` |
| Evidence run | `CELLSTATE-EVIDENCE-3268ddfd0caf` |
| Locked assets opened | `false` |
| Sealed assets opened | `false` |

| Method | L1 accuracy / macro-F1 / composition MAE | L2 accuracy / macro-F1 / composition MAE | Calibration or OOD observation |
|---|---|---|---|
| Source-specific correlation | 0.671 / 0.583 / 0.037 | 0.531 / 0.500 / 0.088 | forced assignment; development-OOD false reassurance 1.000 |
| Marker/program evidence | 0.427 / 0.399 / 0.080 | not assessed | forced assignment; development-OOD false reassurance 1.000 |
| CellTypist custom | 0.829 / 0.799 / 0.010 | 0.747 / 0.776 / 0.045 | forced assignment; development-OOD false reassurance 1.000 |
| scmap | 0.651 / 0.560 / 0.035 | 0.549 / 0.500 / 0.106 | OOD not assessed |
| scANVI | 0.803 / 0.745 / 0.014 | 0.810 / 0.811 / 0.039 | transductive; ECE 0.141 / 0.084; OOD not assessed |
| Symphony | 0.730 / 0.635 / 0.024 | 0.721 / 0.746 / 0.054 | OOD not assessed |
| scConform over scANVI | 0.803 / 0.745 / 0.014 | 0.810 / 0.811 / 0.039 | coverage 0.902 / 0.833; mean set size 1.284 / 1.162 |
| SingleR | `resource_not_viable` | partial output excluded | no complete L1 result after the 3,600-second development budget |

SingleR and scmap belong to the same reference-similarity Evidence Family. scConform is a calibration layer over scANVI probabilities and is not counted as an independent biological evidence source. Pareto diagnostics are development observations only; no method is selected or frozen from this pilot.

## Remaining blockers

1. Biological Review Cards, ProductDefinitionCard and StateRoleMap require BRIDGE and Chen-team review.
2. FreezeGateSpec is an unsigned proposal. Thresholds are not approved.
3. Gene masking, sample-preserving downsampling and preprocessing-swap sensitivity are `not_assessed` pending a signed sensitivity specification.
4. Current inductive methods either force OOD assignments or lack an OOD assessment; scConform L2 coverage is below its nominal 0.90 target.
5. The locked runner remains fail-closed; source holdout and locked OOD testing have not run.
6. No state has passed an approved per-state gate. L2 lacks an independent external label source.

Therefore `CELLSTATE-scRNA-v1.0` and its release manifest do not exist as approved runtime assets. P0-02 remains executable shadow evidence, `domain_score=null`, and P0-03 remains blocked. This pilot does not validate efficacy, safety, potency, GMP release or product quality.

## Engineering verification

- Repeated summaries were byte-identical and retained Evidence ID `CELLSTATE-EVIDENCE-3268ddfd0caf`.
- Evidence artifact SHA-256: `ffe78a0ba64f632b4cb25191062e91fc053de22e11bf4aa5b5f9e91a864e1590`.
- Local Python 3.12 suite: 171 passed, 3 warnings.
- Server Python 3.12 suite: 171 passed, 2 warnings.
