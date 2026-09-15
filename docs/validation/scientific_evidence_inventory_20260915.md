# Scientific Evidence Inventory — 2026-09-15

## Scientific question

Which current BRIDGE tools have produced interpretable observations on genuine
product data, and which claims remain blocked by scientific inputs, validation
or review?

## Code and evidence baseline

- Repository: `starvingarc/BRIDGE`.
- Isolated branch: `scientific-evidence-audit`.
- Baseline: `5720670b13bd7c70abb95ebbe8937e326ba893db` from current
  `origin/main`.
- This inventory is read-only with respect to raw data, historical artifacts,
  algorithms, thresholds, schemas and scientific qualification.

## Data used

1. Current repository contracts, task cards, active plans, package cards and
   validation records for P0-02 through P0-06.
2. The maintained P0-02 development review v1.1 and its exact assessment record.
3. Preserved private D28 artifacts under the authorized server evidence store,
   including QC, cell-state and exploratory-process manifests, profiles,
   summaries and requests. Raw inputs and historical outputs were not modified.
4. Current Git history and extant branches, inspected for a newer P0-02
   development or locked-evaluation result.

## Actual observations

### P0-02 candidate qualification

The evaluated CellTypist/energy candidate used 61,455 Chen scRNA reference
observations and six source-sample rotations. Held-out source-label accuracy was
0.7522, macro-F1 0.7415 and selective precision 0.7547. Candidate retention was
0.5163; unknown and unavailable fractions were 0.1265 and 0.3573.

Across four development-OOD panels, mean energy AUROC ranged from 0.3377 to
0.7315 and FPR at 95% OOD recall from 0.7514 to 0.9346. The versioned candidate
failed selective-precision, rejection and count-thinning entry criteria. Locked
evaluation was not run and no state was qualified. This is a result about the
named candidate and assessment version, not a permanent verdict on P0-02.

### Genuine D28 chain

The preserved input was a 6,247-observation by 33,538-feature GSE204796 D28
count matrix. Candidate technical QC selected 5,588 observations (89.45%) and
excluded 659 while retaining all features. The source contains one sample ID,
one capture ID and one culture-day value. Preparation, donor, cell line, lot,
pooling and biological independence are not bound; independent `n` remains null.

The installed P0-02 run produced source-specific candidate state evidence and
marker summaries on the same 5,588 observation IDs. The maintained seven
priority L2 states are parent-only; these labels are not validated product
identities or a target-purity measurement. This genuine run used P0-02 0.5.5;
current source reports P0-02 0.6.1. The later CellTypist/energy candidate and
development assessment are separate evidence, and no genuine-product 0.6.x run
was found.

The installed P0-06 exploratory run used the same selected observations and the
fixed Seurat v5.5.1 S/G2M lists with complete gene coverage. Predicted phases
were G1 3,411, S 995 and G2M 1,182; S+G2M was 38.96% of selected observations.
This supports the narrow statement that the selected expression signatures show
heterogeneous cell-cycle-associated activity. It does not measure division rate,
G0, purity, stress, fitness, tumorigenicity, safety, potency or release fitness.
Scanpy and decoupler outputs use different units but the same RNA evidence
family, so they are not independent confirmations. The genuine run used P0-06
0.8.1; current source reports 0.8.2. The associated QC run used P0-01 0.1.5,
while current source reports 0.1.6. The preserved results are exact-version
historical evidence, not automatic current-version real-run acceptance.

### P0-03 through P0-05

P0-03 target/regional, P0-04 developmental and P0-05 off-target runtimes execute
their documented arithmetic and methods and fail closed on tested contract
violations. Their current validation fixtures are synthetic. No genuine D28
product result was found for these domains. Product roles, developmental window,
unit lineage, target/regional programs and off-target calibration are not
sufficiently bound for product interpretation.

An older private P0-03 visualization summarized real-derived MacroDiff,
SphereDiff and Studer label counts with a draft role map. It explicitly marked
reference support as partial or not assessed and intervals as not estimable.
This can demonstrate source-label-conditioned counting on real-derived inputs,
but it is not a current source-bound target/regional measurement and cannot
validate the labels or product roles.

Older P0-04 MacroDiff/SphereDiff/Studer figures reused real-derived cell counts,
but their ProductCase, DataView checksums, biological-unit manifest, reviewer,
window and provenance were explicit `demo`/`fully-synthetic` objects. They are
visualization and contract demonstrations, not genuine developmental evidence.
The inspected P0-05 visualization used a ten-observation `demo` profile and
synthetic calibration hashes, so it is synthetic rather than real-product
evidence.

## Three most important gaps

### 1. Identity/rejection candidate has not qualified — directly verifiable

The exact P0-02 candidate failed development entry; no newer qualifying or
locked result exists on the repository state reviewed. This blocks claims that
the D28 source labels are biologically accurate product identities.

### 2. Product role and developmental window are unresolved — scientific judgment

ProductDefinitionCard remains draft, all seven priority L2 roles are unresolved,
and DevelopmentWindowSpec is not confirmed. The development review supports
broad radial-glial or neuroblast parents only. A user/scientific-owner decision
is required before candidate role- or window-conditioned arithmetic is meaningful.

### 3. Genuine design and calibration inputs are missing — missing data

The D28 selected view has one observed sample/capture but no bound preparation
or biological-unit manifest. P0-03–P0-05 lack genuine product runs; P0-06 lacks
stress input and inferential replication. Cells cannot supply the missing
independent units. The missing relationships and measurements remain unknown or
unavailable, not zero.

## Supported conclusions

- BRIDGE can reproducibly preserve and execute a genuine D28 technical-QC,
  candidate cell-state and descriptive cell-cycle chain with exact observation
  correspondence at the preserved P0-01 0.1.5 / P0-02 0.5.5 / P0-06 0.8.1
  versions.
- The P0-02 development assessment provides useful negative evidence about one
  candidate's rejection/selective-performance limits.
- P0-06 can report a descriptive, gene-set-conditioned cell-cycle profile on the
  selected D28 view.
- P0-03–P0-05 have executable engineering contracts but no current genuine D28
  biological conclusion.

## Questions still unanswered

- Which state definitions and product roles should be accepted for this product?
- Does the intended product window include early neuroblasts or progenitors only?
- What are the genuine preparation, sample, capture, donor/cell-line, lot,
  pooling and independence relationships?
- Can a revised P0-02 candidate pass source-aware rejection and preprocessing
  sensitivity, then an untuned locked evaluation?
- What calibrated target/regional, off-target and stress measurements are valid
  for this product and assay?

## Validation evidence

The authoritative records and artifacts used were:

- `docs/validation/cell_state_development_20260911.md` and
  `development_review_v1_1.json` for the exact candidate, state decisions and
  development-entry outcome;
- `docs/validation/p0_02_cell_state_evidence.md` for real reference/product/OOD
  runs and external-source unit limits;
- P0-03–P0-06 validation histories for the synthetic-runtime boundaries;
- preserved private D28 `completion-summary.json`, measurement summary, ToolRun
  manifests and result profiles; current SHA-256 values were recomputed for the
  selected summary, receipt, manifests and profiles;
- current Git history through `origin/main` at the baseline above.

Current source discovery reported P0-01 0.1.6, P0-02 0.6.1, P0-03 0.4.1,
P0-04 0.5.1, P0-05 0.6.0 and P0-06 0.8.2. Knowledge validation reported 354
methods, 396 bindings, no dangling method/source references and zero formally
eligible methods. Repository policy checks passed.

A current-source targeted suite covering P0-02 development qualification and
validation, P0-03 through P0-06 runtimes, shared contracts and registry behavior
passed 527 tests in 579.08 seconds, with 191 dependency deprecation/future
warnings and no test failures. Passing these engineering checks does not change
any scientific state described here.
