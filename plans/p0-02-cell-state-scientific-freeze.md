# P0-02 External-Source Freeze Candidate

| Field | Value |
|---|---|
| Branch | `codex/bridge-scientific-freeze` |
| Status | `awaiting_biological_review` |
| Owner | BRIDGE core |

## Biological question

Can reviewed fetal ventral-midbrain states support source-aware annotation of a
pre-transplant hPSC-mDA product while unrelated neural and non-neural cells are
rejected as unknown?

This candidate is the prerequisite for later Target Identity, Regional Fidelity,
Developmental Compatibility and Off-target Control analyses. It is not a released
cell-state method.

## Current evidence and unresolved biology

- Chen vMB scRNA-seq provides 61,455 cells for broad L1 development work.
- Chen RG/Nb scRNA-seq provides 11,366 cells for seven priority L2 development
  states.
- Development OOD includes cortical organoid, neural crest, motor-neuron and
  mesenchymal datasets.
- GSE204796 is a behavior-only time course; it does not validate a product stage.
- Current inductive methods force the development OOD panels into known fetal VM
  labels.
- Fine RG/Nb support is incomplete. Unresolved Nb boundaries remain
  `provisional` or `unavailable` and cannot support formal regional claims.
- snRNA-seq remains a cross-modality shadow analysis.

No method, state, threshold or product role is frozen. Current observations do not
support formal target-cell, regional-fidelity or off-target composition claims.

## Candidate engineering design

The fixed candidate comparison will use:

- CellTypist as the sole inductive base classifier;
- source-specific correlation and marker evidence as sensitivity channels;
- energy score as the primary OOD channel and kNN distance as a sensitivity;
- scANVI only as a transductive benchmark;
- scConform only for marginal and classwise prediction-set coverage, not as an
  independent OOD detector or biological evidence source.

## External-source candidate

- External holdout: the processed Birtele `GSE192405` matrix plus the La Manno
  source family.
- BrainSTEM, HDNA and CapybaraBrain are related development/competitor artifacts;
  they are not independent external validation for this release candidate.
- Locked OOD families remain unopened.
- Sealed `E-MTAB-14729` remains unopened and cannot influence labels, methods,
  thresholds, calibration or tuning.

The preregistered report must include:

- macro-F1, hierarchical accuracy and composition MAE;
- AUROC, AUPR and FPR@95TPR for OOD assessment;
- marginal and classwise coverage plus prediction-set size;
- exact-to-parent-to-unknown rejection behavior.

## Biological review and execution gate

1. Review all 25 state cards, including definitions, parent-child relations,
   developmental context, positive markers, negative markers and confounders.
2. Review and approve the ProductDefinitionCard and StateRoleMap before translating
   states into target, adjacent or off-target roles.
3. Keep the 328 historical conflicts excluded, including 25 RG-to-Pericyte records.
4. Freeze per-state acceptance, parent fallback, abstention and unknown rules.
5. Sign the FreezeGate.
6. Only then implement and run the locked external-source/OOD runner once, without
   tuning.

P0-03 remains blocked until P0-02 has a valid release manifest. If review or locked
evaluation fails, affected states remain `shadow`, `provisional` or `unavailable`.

## Scientific boundaries

- The candidate evaluates analytical reliability and rejection behavior, not
  product efficacy, safety, potency, GMP release or absolute quality.
- Differentiation day is not converted into fetal age.
- Cells, nuclei and sequencing sublibraries are not biological replicates.
- BrainSTEM/HDNA/CapybaraBrain cannot count as independent validation.
- Competitor-isolated artifacts cannot enter BRIDGE reference construction, RAG,
  priors, training, calibration, tuning or formal Evidence Graphs.

## Engineering status

- Locked-runner implementation and execution are pending the biological review and
  signed FreezeGate.
- Formal tests, deterministic projection regeneration and environment rebuild
  validation are reserved for server Task 5.
- `ENV-P0-CORE-v0.1` remains `rebuild_validation_required` until Task 5 records
  server rebuild validation. The dedicated cell-state environments retain their
  existing health-check status; Task 5 still owes adapter checks.
- Historical local runs are diagnostic only and are not current formal evidence.
- Runtime remains fail-closed without approved review, gate and release records.
