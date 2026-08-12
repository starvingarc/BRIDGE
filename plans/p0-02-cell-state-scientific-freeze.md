# P0-02 External-Source Freeze Candidate

| Field | Value |
|---|---|
| Branch | `codex/p0-02-cell-state-freeze` |
| Status | `biological_review_in_progress` |
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

## Birtele asset preparation gate

The official `GSE192405` processed archive contains 13 count-matrix CSV files
with 77,804 unique cells and a shared ordered set of 25,032 genes. Raw reads are
not public. Publication totals reconcile the four primary matrices into 6-week,
8-week and 11-week analysis groups. Table S1 and the public filenames also
constrain cultured samples into 7-week, 7.3-week and 8-week candidate groups,
but `GSM5746439` and conflicting `GSM5746445` cannot be assigned uniquely
between the latter two. These mappings are `provisional_inferred`, not verified
donor identities.

The project scientific lead conditionally approved this mapping for source-level
holdout, stage-level description and provisional-group sensitivity only. Every
formal `biological_unit_id` remains null and every sample remains
`replicate_eligibility=not_estimable`. The decision cannot support donor-level
inference or promote a method, state, threshold or product role. The evidence is
recorded in the [external-source asset validation](../docs/validation/p0_02_external_source_asset_20260812.md).

Before state-card biological review begins—and before the FreezeGate can be
signed or any locked runner can be implemented or run—the processed
`GSE192405` asset must have:

1. a processed-CSV conversion manifest that identifies every source file and the
   deterministic conversion step;
2. checksums for every original processed file and every converted output;
3. a frozen 13-sample sample/unit map that distinguishes GEO sample, biological
   unit and any technical subdivision;
4. a source-family and transitive-leakage audit covering Birtele, La Manno and all
   reference/development derivatives;
5. converted-object schema validation and QC validation with explicit matrix,
   feature, observation and sample-unit semantics.

All five preparation items passed engineering validation and the constrained
biological review. The FreezeGate nevertheless remains unsigned, and the locked
runner must not be implemented or run until state and product-context review is
complete.

## Biological review and execution gate

After the Birtele asset preparation gate passes:

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

- The Birtele conversion, checksum, QC and lineage-audit implementation is
  complete; its source/stage-only use is conditionally approved with
  provisional groups and no biological-replicate inference.
- Locked-runner implementation and execution are pending the biological review and
  signed FreezeGate.
- Task 5 server engineering validation is complete at implementation
  `0029ff46841d5b92630ee4e5750ba2fe73961c03`; the formal suite, deterministic
  projections, wheel installation and repository gates passed as recorded in the
  [server reproducibility validation](../docs/validation/server_reproducibility_20260812.md).
- Core, Python adapter and R adapter health checks are complete. The adapter
  checks were data-free and do not promote a scientific method.
- Historical local runs are diagnostic only and are not current formal evidence.
- Runtime remains fail-closed without approved review, gate and release records.
