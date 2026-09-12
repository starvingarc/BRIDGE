# Cell-State Development Decisions and Rejection Assessment

## Scientific finding

The tested CellTypist / energy candidate does not meet the development-entry
criteria for locked evaluation. Its source-label recovery and domain-shift
diagnostics remain available as research observations. They do not establish
biological identity, target composition, developmental compatibility or a
qualified state release.

The versioned [development review](../../src/bridge/tool_packages/p0_02_cell_state/resources/development_review_v1_1.json)
is the maintained source for 25 state decisions, citations, marker programs and
limitations. Seven L2 labels support parent-only interpretation; unresolved
boundaries and zero-observation classes remain unavailable. GABA or glutamatergic
programs alone do not establish an off-target lineage. Intended VM/mDA progenitors
and early neuroblasts are evaluated separately from developmental stage.
Source-label target and window mappings remain unavailable, not zero.

Review v1.1 corrects product-role semantics without changing the archived v1.0
training run, weights or validation outcomes. Historical per-cell role fields
retain their original review version. Legacy signed and pending review records
are unchanged.

## Data and design

The development run used 61,455 CHEN scRNA-seq reference observations and six
source-sample rotations, each with four training samples, one calibration sample
and one test sample. Sample and developmental age are confounded. These are not
six independent source families. Fold 01 was fixed as the query model before
fitting; no best-fold selection is permitted.

The model feature panel was the ordered intersection of reference and
development-OOD gene identifiers, without using OOD expression values for
feature selection. Counts were normalized over the original feature panel
before subsetting. The common panel contained 12,528 genes; one fold retained
12,526 expressed training features. Historical source conflicts remained
excluded.

The fixed calibration used alpha 0.05, at least 20 correct calibration examples
for each class margin, and minimum feature coverage 0.9. CellTypist OvR scores
were not converted to a categorical posterior. Energy was the primary rejection
heuristic; training-only PCA/kNN distance was a sensitivity channel, not an
independent vote. Count thinning, library-size scaling and gene masking reused
the fitted models.

Acceptance thresholds in the development-entry policy were recorded after the
development run and before any locked evaluation. This is an exploratory
development assessment, not a preregistered confirmatory result. No behavior,
locked or sealed asset was used to fit or select the candidate.

## Observed results

Across held-out reference observations, forced source-label accuracy was 0.7522
and macro-F1 was 0.7415. Candidate retention was 0.5163, with selective precision
0.7547. Unknown and unavailable fractions were 0.1265 and 0.3573. Composition
L1 error including unresolved mass was 1.0708.

The four OOD panels denote dataset-level domain shift, not independently
verified cellwise absence from the reference taxonomy. Their accepted fractions
must not be described as biologically incorrect assignments for every cell.

| Development panel | Mean energy AUROC, OOD positive | Mean FPR at 95% OOD recall | Mean candidate retention |
|---|---:|---:|---:|
| GSE190729 | 0.5239 | 0.7789 | 0.7791 |
| GSE221853 | 0.3377 | 0.9346 | 0.6138 |
| GSE224152 | 0.7315 | 0.7514 | 0.2798 |
| GSE267791 | 0.3483 | 0.8737 | 0.8157 |

Energy discrimination, OOD retention, reference selective precision and
count-thinning sensitivity failed the entry policy. kNN sensitivity does not
rescue those failures. No score direction or threshold was changed to turn the
observations into a pass. Locked testing was not run and no state was qualified.

The verifier recomputed calibration, held-out classification and continuous OOD
metrics from checksummed prediction artifacts and model bundles. Sensitivity
summaries remain producer-recorded rather than independently recomputed by that
verifier. The development summary is content-bound by
`766b16971a99e5b38cded611ee748ac071b1ba860a370263ab6ed1fdb75e51ac`.

## Runtime scope and engineering evidence

Cell-state runtime 0.6.0 adds a separate candidate measurement contract. It binds
the fixed model, calibration, verified development receipt, current review and
typed QC DataView. All 25 scientific-release states remain unavailable.
Source correlation retains its own auxiliary run; its original receipt and
artifacts are reused on compatible replay. Current reviewed gene-detection
measurements remain separate from legacy auxiliary marker cards.

The completed candidate-module check passed five tests covering registered
execution, immutable replay, source overlap, receipt tampering, fixed-fold
selection and missing-gene semantics. Eight portable runtime tests passed in the
preceding combined check; its single candidate replay failure was corrected by
reusing the original auxiliary receipt rather than regenerating its timestamp.

The actual fold-01 model loaded and produced finite outputs in
`bridge-p0-core-v0.2`, where CellTypist was not installed. That check used a
synthetic query and establishes portable inference only, not scientific
validation or real-product acceptance. Model fitting still uses the separate
CellTypist training environment.

## Remaining scope

Real-product multi-method graph feedback, a same-version verified research
report and browser correction acceptance are not established by this record.
Fine-state parent-fallback source-group diagnostics and independent
identity/window validation remain separate from source-label recovery.
