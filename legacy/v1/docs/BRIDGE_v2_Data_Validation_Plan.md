# BRIDGE v2 Data and Validation Plan

## Purpose

This document defines how BRIDGE v2 SHALL be validated as an iterative research-use and translational AI scoring system. The validation plan is designed to support a manuscript and future preclinical translational development. It SHALL NOT be used to claim clinical release qualification.

The central validation question is:

```text
Does BRIDGE v2 produce quantitative, calibrated, biologically plausible, and generalizable product-readiness scores across heterogeneous single-cell datasets?
```

## Validation Principles

BRIDGE v2 validation SHALL follow these principles:

- Evaluate complete products, not only favorable target subsets.
- Separate rule baseline performance from AI-calibrated performance.
- Test generalization across datasets, protocols, timepoints, and controls.
- Treat missing data explicitly.
- Report uncertainty, calibration, and OOD behavior.
- Preserve versioned data and model manifests.
- Keep all claims bounded as research-use and translational.

## Five-Layer Validation Map

Validation SHALL cover every layer of the BRIDGE v2 product architecture.

```text
Input Compatibility Layer
-> Biological Representation Layer
-> AI Scoring Layer
-> Optimization & Recommendation Layer
-> Learning Loop / Lifecycle Governance Layer
```

| Layer | Validation Responsibility |
| --- | --- |
| Input Compatibility Layer | Verify that h5ad, converted Seurat, single-timepoint, multi-timepoint, sparse-metadata, and normalized-only inputs produce correct manifests and eligibility states. |
| Biological Representation Layer | Verify that reference mapping, controlled batch integration, gene programs, cell-state features, product summaries, and trajectory features remain stable across datasets and platforms while preserving product-relevant biology. |
| AI Scoring Layer | Verify score calibration, held-out generalization, uncertainty, OOD behavior, and improvement over transparent baselines. |
| Optimization & Recommendation Layer | Verify that recommendations are supported by score drivers, timepoint comparisons, and expert-reviewed biological plausibility. |
| Learning Loop / Lifecycle Governance Layer | Verify that each model version has a dataset manifest, model card, validation report, changelog, and documented intended-use boundary. |

## Dataset Strata

The validation set SHALL be organized into strata rather than one mixed dataset pool.

The current internal test-data snapshot is maintained in `BRIDGE_v2_Test_Data_Inventory.md`. That inventory separates immediately usable h5ad files from raw downloaded data, existing BRIDGE v1 trial outputs, negative controls, reference-robustness resources, and future conversion candidates.

| Stratum | Purpose | Examples |
| --- | --- | --- |
| Core mDA product-like datasets | Positive or near-positive product-readiness anchors. | Pre-transplant mDA progenitor-oriented differentiation datasets. |
| Time-course protocols | Test trajectory-aware scoring and collection-window suggestions. | Multi-day differentiation datasets such as D8-D35 or D20-D60 protocols. |
| Single-timepoint products | Test compatibility with realistic final-sample submissions. | Day-before-transplant or one-timepoint pre-transplant samples. |
| Multi-lot or multi-batch products | Test cross-lot process robustness and outlier-lot detection. | Multiple independent product lots at one or more shared timepoints. |
| Technical batch challenge sets | Test controlled technical correction without removing biology. | Datasets with known library batches, sequencing runs, chemistries, or platforms that are not fully confounded with protocol/timepoint. |
| Negative/off-target controls | Test specificity and safety gate behavior. | Cortical organoid, whole-brain organoid, motor neuron, neural crest, mesenchymal, non-neural, or non-midbrain datasets. |
| Reference robustness datasets | Test mapping stability across platforms and developmental references. | Human fetal brain, midbrain, organoid, disease-model, and public BrainSTEM-style references. |
| Future outcome-linked datasets | Calibrate transcriptomic product evidence against downstream biology. | Post-transplant snRNA-seq, graft composition, electrophysiology, behavioral assays, imaging, survival, or maturation evidence. |

## Data Manifest Requirements

Every dataset entering validation SHALL have a dataset card or manifest with:

- dataset_id
- source accession or internal identifier
- assay type
- species
- cell source
- differentiation protocol
- timepoints
- sample and batch structure
- product lot or manufacturing batch structure
- technical batch variables
- protected product variables
- confounding status between technical and biological variables
- integration eligibility state
- product-like or control role
- raw and normalized layer availability
- gene identifier type
- cell count and gene count
- known annotations
- intended validation role
- caveats and exclusion reasons

Private paths and raw unpublished matrices SHALL NOT be exposed in public documentation or benchmark artifacts.


External QC metadata SHOULD be represented when available, including viability, thaw state, enrichment/sorting method, karyotype/CNV/WGS/WES evidence, sterility/mycoplasma/endotoxin status, residual pluripotency assays, release-assay panel results, and downstream graft/function evidence. Missing external QC should reduce relevant evidence confidence, not automatically fail the transcriptomic profile.

## Split Strategy

Validation SHALL prevent leakage from protocol, dataset, and timepoint structure.

### Leave-Dataset-Out

Train on all but one dataset and test on the held-out dataset.

Purpose:

- Test cross-study generalization.
- Detect overfitting to dataset-specific preprocessing or annotation style.

### Leave-Protocol-Out

Hold out all samples from one differentiation protocol or source lab.

Purpose:

- Test whether the model generalizes to a new protocol.
- Support the claim that BRIDGE v2 evaluates product biology rather than memorizing protocol identity.

### Leave-Timepoint-Out

For time-course protocols, hold out selected timepoints.

Purpose:

- Test whether trajectory-aware models can interpolate or rank collection windows.
- Compare single-timepoint mode against multi-timepoint mode.

### Leave-Lot-Out or Leave-Batch-Out

For datasets with multiple product lots or manufacturing batches, hold out one product lot or batch at a time.

Purpose:

- Test product-level generalization across independent manufacturing replicates.
- Detect whether the model memorizes lot-specific technical artifacts.
- Support Process Robustness Score validation without treating product lots as nuisance batch effects.

### Negative-Control Holdout

Hold out entire classes of off-target controls.

Purpose:

- Test whether safety constraints and Purity / Off-target Score generalize to unseen off-axis biology.


### Leave-Publication, Source-Line, Sponsor, and Donor Holdouts

Hold out all samples from one publication, source cell line, sponsor/product family, or donor where metadata allow.

Purpose:

- Detect leakage through lab-specific preprocessing, cell-line identity, publication style, or product-family signatures.
- Support claims that BRIDGE v2 evaluates product biology rather than memorizing a study or sponsor context.

### Future Outcome Holdout

If downstream graft or functional evidence becomes available, hold it out from initial score training.

Purpose:

- Evaluate whether transcriptomic product scores correlate with downstream evidence without overfitting.
- Keep outcome-linked claims separate from reference-based claims.

## Evaluation Metrics

| Validation Target | Metrics |
| --- | --- |
| Product-like vs off-target separation | AUROC, AUPRC, balanced accuracy, score distribution separation. |
| Protocol ranking | Spearman correlation, Kendall tau, pairwise ranking accuracy. |
| Domain score calibration | Reliability curves, expected calibration error, Brier score where probabilistic labels exist. |
| Integrated score stability | Bootstrap confidence intervals, replicate variance, sensitivity to cell subsampling. |
| Missing-data robustness | Score degradation curves under layer, metadata, timepoint, and gene-dropout simulations. |
| Batch integration quality | Technical batch mixing metrics paired with biological-conservation metrics, overcorrection checks, and protected-variable variance preservation. |
| OOD detection | OOD AUROC, false reassurance rate, embedding-distance thresholds. |
| Agreement with BRIDGE v1 | Correlation, disagreement analysis, expert-reviewed divergence cases. |
| Explainability quality | Expert review of top drivers, off-target detection consistency, gene-program plausibility. |
| Score-integration method selection | Compare profile-only, constrained additive, MCDA-style, and learned calibrated index variants. |

## Baselines

BRIDGE v2 SHALL be compared against:

- BRIDGE v1 rule-based Product Score.
- Simple marker or gene-set scores.
- Pseudo-bulk nearest-reference similarity.
- Standard tabular ML models using biologically informed features.
- Optional foundation-model embeddings.
- Combined models with and without BRIDGE v1 features.

The manuscript SHALL NOT present a complex model as better unless it outperforms simple and biologically interpretable baselines on held-out validation.

## Batch Integration Validation

BRIDGE v2 SHALL validate batch integration as a controlled representation procedure. A batch-corrected embedding SHALL NOT be considered successful only because technical batches mix well.

Validation SHALL report:

- variables corrected
- variables preserved
- variables withheld from correction because of confounding
- integration method and version
- reference model version when reference mapping is used
- biological-conservation metrics
- overcorrection warnings
- effect on downstream domain scores

Required checks:

| Check | Purpose |
| --- | --- |
| Technical batch mixing | Confirm that nuisance variables such as sequencing run or chemistry do not dominate latent structure. |
| Protected-variable conservation | Confirm that protocol, product lot, timepoint, donor, treatment, and target-program variation are not removed by default. |
| Marker-program conservation | Confirm that target, off-target, risk-flag, and potency-related proxy programs remain visible after mapping. |
| Negative-control separation | Confirm that off-target controls are not pulled into product-like reference neighborhoods. |
| Trajectory conservation | Confirm that true timepoint ordering and maturation direction are not flattened by correction. |
| Lot outlier preservation | Confirm that abnormal product lots remain detectable after integration. |
| Score sensitivity | Compare scores derived with no integration, technical-only integration, and protected-variable correction attempts. |

If technical and biological variables are fully confounded, the validation report SHALL mark integration as limited or withheld for that variable and SHALL reduce Evidence Confidence for affected claims.


A required integration sensitivity panel SHOULD compare at least: no integration, conservative technical-only correction, reference-only mapping, and one deep generative mapping method when feasible. Reports SHALL include protected-variable conservation metrics such as product signature rank correlation, target/off-target score shrinkage, timepoint trend preservation, lot-variance preservation, marker-program retention, and rare-state preservation.

## Ablation Plan

Required ablations:

| Ablation | Question |
| --- | --- |
| No AI calibration | How much does BRIDGE v2 improve over BRIDGE v1 rules? |
| No target-anchor features | Does the model rely on biologically relevant identity evidence? |
| No off-target/safety features | Does safety specificity degrade? |
| No time-course features | How much does trajectory evidence improve protocol ranking? |
| Single-timepoint mode only | Can the model still evaluate final product samples? |
| No foundation embeddings | Are optional foundation features actually useful? |
| No metadata features | Is the model robust without protocol or batch metadata? |
| No integration | Does reference mapping or controlled integration improve annotation without changing expression-derived score drivers? |
| Technical-only integration vs protected-variable correction | Does correcting only technical nuisance variables preserve product-relevant biology better than broad correction? |
| Cell subsampling | How stable are scores at lower cell counts? |
| Gene overlap simulation | How sensitive is scoring to platform and gene-space differences? |

## Missing-Data Validation

The validation plan SHALL explicitly test:

- single-timepoint inputs
- missing cell-type labels
- missing raw counts
- missing batch metadata
- missing protocol metadata
- low gene overlap
- low cell count
- inconsistent timepoint labels
- normalized-only matrices

Expected behavior:

- Core product scoring SHALL continue when enough expression evidence exists.
- Missing temporal or batch evidence SHALL reduce Evidence Confidence rather than become negative biological evidence.
- Severe incompatibility SHALL produce an unscorable or low-confidence result rather than a falsely precise score.

## Score Integration, Calibration, and Uncertainty

Calibration SHALL be evaluated at two levels:

1. Domain-level calibration: whether each score corresponds to expected biological evidence.
2. Integrated-score calibration: whether score bands correspond to product-like, borderline, or off-target categories in held-out data.

The BRIDGE v2 total score SHALL be finalized only after comparing candidate integration methods:

- profile-first scorecard without a total score
- constrained additive index
- MCDA-style expert-weighted index
- learned calibrated index

The selected method SHALL improve interpretability, calibration, ranking, or held-out generalization relative to the BRIDGE v1 baseline and simple scorecards.

Required uncertainty outputs:

- score interval
- evidence state
- OOD flag
- bootstrap stability
- model ensemble disagreement
- explanation confidence

The Evidence Confidence constraint SHALL be calibrated so that low-confidence results are clearly separated from low-quality biological products.

## Reporting Alignment

BRIDGE v2 validation reports SHOULD align with:

- GMLP: representative data, independent testing, transparency, monitoring, lifecycle management.
- TRIPOD+AI: transparent reporting of prediction model development and validation.
- DECIDE-AI: early-stage decision-support evaluation, especially human-AI workflow and failure modes.

For manuscript reporting, the validation section SHALL state:

- data sources and inclusion criteria
- split strategy
- baseline models
- model versions
- missing-data handling
- calibration methods
- uncertainty methods
- failure modes
- intended use and non-goals

## Acceptance Criteria for Paper-Ready BRIDGE v2

## Locked Validation Protocol

Before any paper-ready score threshold or integrated score is reported, BRIDGE v2 SHALL freeze a validation protocol that specifies included datasets, excluded datasets, split strategy, hypotheses, score contracts, threshold-locking rules, manual-review procedure, software versions, random seeds, and allowed post hoc analyses. Any change after locking SHALL be recorded as exploratory or trigger a new validation version.

Human review SHALL be part of the validation protocol for OOD, rare-state, and weak-label conflict cases. Reports should compare AI-alone, human-alone when possible, and human+AI workflows for difficult cases.


The paper-ready version SHALL meet these criteria:

- All datasets have dataset cards or manifests.
- The model is evaluated with leave-dataset-out and leave-protocol-out validation.
- Negative controls lower product-readiness scores and trigger interpretable off-target explanations.
- Single-timepoint and multi-timepoint inputs are both supported.
- AI-calibrated scoring is compared with BRIDGE v1 and simple baselines.
- Candidate total-score integration methods are compared before one is selected.
- Calibration and uncertainty are reported.
- Foundation model features, if used, are supported by ablation evidence.
- Boundary statements prevent clinical overclaiming.

## References

- [BRIDGE v2 Product Requirements Document](BRIDGE_v2_PRD.md)
- [BRIDGE v2 Model Architecture](BRIDGE_v2_Model_Architecture.md)
- [FDA: Good Machine Learning Practice for Medical Device Development](https://www.fda.gov/medical-devices/software-medical-device-samd/good-machine-learning-practice-medical-device-development-guiding-principles)
- [TRIPOD+AI statement](https://www.bmj.com/content/385/bmj-2023-078378)
- [DECIDE-AI reporting guideline](https://www.nature.com/articles/s41591-022-01772-9)
- [Single-cell best practices: data integration](https://www.sc-best-practices.org/cellular_structure/integration.html)
- [Luecken et al., Nature Methods 2022: scIB integration benchmark](https://www.nature.com/articles/s41592-021-01336-8)
- [Lotfollahi et al., Nature Biotechnology 2021: scArches reference mapping](https://www.nature.com/articles/s41587-021-01001-7)
- [Kang et al., Nature Communications 2021: Symphony reference mapping](https://www.nature.com/articles/s41467-021-25957-x)
