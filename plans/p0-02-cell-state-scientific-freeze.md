# P0-02 External-Source Freeze Candidate

| Field | Value |
|---|---|
| Coordination | `main` and Issues #3, #5, #6, #7 and #8 |
| Status | `biological_review_in_progress` |
| Owner | BRIDGE core |

## Biological question

Can reviewed fetal ventral-midbrain states support source-aware annotation of a
pre-transplant hPSC-mDA product while unrelated neural and non-neural cells are
rejected as unknown?

This candidate is the prerequisite for later Target Identity, Regional Fidelity,
Developmental Compatibility and Off-target Control analyses. It is not a released
cell-state method.

## Current reference routing and unresolved biology

- Chen vMB scRNA-seq provides 61,455 cells and is the primary pre-transplant
  reference for ventral-midbrain identity and fine cell-state evidence.
- The existing 2,011,383-cell whole-cell scRNA reference integrates the legacy
  Chen snapshot with Braun 2023 and Zeng 2023. It provides broad brain-region and
  off-axis context after lineage review; because it contains Chen cells, it is
  not an independent vote in addition to the Chen reference.
- The current GW7 spatial reference contains 385,361 retained segmented profiles
  from two sections of one embryo. It supplies a separate anatomical evidence
  view, but its initial label transfer depended on the Chen scRNA reference.
- Chen RG/Nb scRNA-seq provides 11,366 cells for seven priority L2 development
  states.
- Development OOD includes cortical organoid, neural crest, motor-neuron and
  mesenchymal datasets.
- GSE204796 is a behavior-only time course; it does not validate a product stage.
- Current inductive methods force the development OOD panels into known fetal VM
  labels.
- Fine RG/Nb support is incomplete. Unresolved Nb boundaries remain
  `provisional` or `unavailable` and cannot support formal regional claims.
- The 87,467-nucleus GW14-25 reference is primarily reserved for an optional,
  separate post-transplant graft snRNA assessment. It is not part of the default
  pre-transplant cell-identity reference route. The 148,922-profile scRNA/snRNA
  integrated object is a candidate developmental-path, direction and branch
  reference for P0-04, but remains excluded from the P0-02 identity consensus.

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
  complete and documented at [P0-02 external-source preparation](../docs/bridge_spec_v0.1/external_source_preparation.md); its source/stage-only use is conditionally approved with provisional groups and no biological-replicate inference.
- P0-02 is now package version `0.4.9`. The rendered public and packaged cards
  consistently report `scientific_status=candidate` and
  `freeze_state=biological_review_in_progress`; they do not claim a scientific
  freeze, score availability or a non-null domain score.
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

## Product-centred visualization workstream — 2026-08-31

- The default user-facing result is a product-to-in-vivo correspondence composer:
  one product and one observation grouping, with each evidence axis supplied by
  its own typed, versioned producer result.
- P0-02 produces only the cell-identity/reference-evidence axis. P0-03 may later
  supply the anatomical-space axis and P0-04 the developmental-stage axis.
  Each missing axis remains `not_assessed` with a producer-specific reason.
- Studer-protocol D16 is the first review case because all 9,046 barcodes in its
  historical analysis object trace to the registered 11,087-barcode raw-count
  input. This establishes barcode lineage, not the biological identity or review
  status of its stored labels, clusters or UMAP. The same display design has also
  been exercised on MacroDiff and SphereDiff: all 57,464 retained MacroDiff
  barcodes trace to six registered count-ready captures, whereas the 9,547-cell
  SphereDiff object remains a historical analysis-ready control because its formal
  count-ready source is unresolved. These are display-generalisation checks, not
  input-QC reproduction or independent cell-identity validation.
- The first review case demonstrates two grouping views. The cluster view preserves
  clusters already stored in the historical analysis object and reports
  group-level reference similarity without forcing one identity per cluster. The
  label view preserves an `Idents`-derived provided grouping, cross-tabulates it
  against stored clusters, and keeps the original strings. Manual-review and
  user-submission provenance are pending; neither view is a calibrated
  probability, prediction set or cell-level assignment.
- Every displayed value retains its native semantics. Calibrated probabilities,
  prediction sets, mixture weights, similarities and distances are labelled
  separately; correlations and uncalibrated scores are not called probabilities.
- The final-RDS age labels and historical relabelling provenance are not yet
  reconciled. The developmental axis is therefore `not_assessed`; no stage
  support calculation or stage graphic is allowed before reconciliation.
- The current hEB58 panel is a candidate label-program lookup: product-group
  pseudobulk is compared with the mean expression programs of 20 current spatial
  work labels. The score is dependent on those labels and is not calibration,
  cell-to-location projection, anatomical localization, independent validation or
  a tissue coordinate. Product-to-space results require a validated P0-03 mapping
  method.
- CapybaraBrain is an isolated public-preprint method-comparison channel. Its
  official repository must be pinned. Before any run, a complete parameter vector
  must freeze `TOPK`, `alpha`, `min_weight`, hybrid/majority-vote settings,
  lineage map, input transform and reference hashes because the paper, README and
  code defaults conflict. Its 93-program output is a post-normalized NNLS
  reconstruction coefficient, not a probability, posterior or similarity.
  `discrete/hybrid/transitioning/unknown/unassigned/heterogeneous` are repository
  enum labels, not six independently validated biological states; `transitioning`
  reflects a curated lineage-map rule, not developmental direction. A missing
  CellTypist model blocks only the final A9 refinement/agreement step, while a
  missing integration embedding blocks only that display. Fetal atlas, HDNA and
  PCA/kNN remain separate artifacts.
- The source-by-state matrix is an evidence drill-down, not the first product view.

## P0-02 external-source preparation closeout — 2026-08-13

- Rebased the P0-02 history on `origin/main`, preserving the completed P0-06
  naming plan row and its decision-log record.
- Added the science-team command contract, required immutable inputs, outputs,
  checksums, provenance, stable failure reasons, examples and scientific
  boundaries to the indexed stable documentation.
- Full validation evidence is recorded in
  [P0-02 external-source preparation validation](../docs/validation/p0_02_external_source_preparation_20260813.md): focused contracts `39 passed in 2.56s`; full suite `214 passed, 3 warnings in 14.31s`; 12-tool discovery with only P0-01/P0-02 implemented; knowledge validation `valid=True` with 354 methods and 396 bindings; repository policy and `git diff --check` passed.
- The branch remains a Draft PR: merge is not authorized. Remaining biological
  work is review of 25 state cards, then ProductDefinitionCard and StateRoleMap;
  only a signed FreezeGate can authorize a single locked run.
