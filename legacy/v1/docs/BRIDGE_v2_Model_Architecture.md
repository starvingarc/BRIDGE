# BRIDGE v2 Model Architecture

## Purpose

This document defines the planned AI model architecture for BRIDGE v2. The goal is to move beyond fixed rule-based scoring while keeping the biological evidence, score drivers, and uncertainty visible.

The architecture is designed for iterative development. The first implementation can be a calibrated machine-learning layer on top of BRIDGE v1 features. Later versions can add cell-level encoders, product-level set models, time-course encoders, and active-learning optimization.

The model architecture is intended for research-use and translational product scoring. It SHALL NOT be used as a clinical release model or a standalone therapeutic-efficacy predictor.

## Architecture Overview

```text
Input Compatibility Layer
-> Biological Representation Layer
-> AI Scoring Layer
-> Optimization & Recommendation Layer
-> Learning Loop / Lifecycle Governance Layer
```

Model artifacts SHALL be versioned separately from BRIDGE v1 rule definitions. Every model release SHALL include a model card, training data manifest, validation report, and intended-use statement.

## Input Compatibility Layer

This layer prepares heterogeneous datasets for modeling. It SHALL produce a Product Data Manifest before any AI score is generated.

Required responsibilities:

- Detect matrix shape, gene identifiers, layers, and sparsity.
- Identify available counts or normalized expression layers.
- Map gene identifiers to a common gene space.
- Detect sample, protocol, product lot, manufacturing batch, donor, timepoint, treatment, technical library batch, sequencing run, chemistry, platform, and operator metadata where possible.
- Record missing metadata rather than silently inventing it.
- Flag low gene overlap, low cell count, invalid layers, or ambiguous product grouping.
- Classify metadata variables as technical nuisance variables, protected product variables, or ambiguous/confounded variables.
- Record whether integration is allowed, withheld, or limited for each variable.

Output:

```text
ProductDataManifest
```

Minimum manifest fields:

- dataset_id
- sample_id or product_id
- available_layers
- gene_id_type
- mapped_gene_count
- cell_count
- metadata_fields
- timepoint_coverage
- batch_coverage
- technical_batch_variables
- protected_product_variables
- confounding_status
- integration_eligibility_state
- input_quality_flags
- score_eligibility_state



Optional external QC fields SHOULD be accepted when available and carried into Evidence Confidence rather than silently ignored:

- viability and thaw status
- sorting or enrichment method
- release-assay panel metadata
- residual pluripotency orthogonal assays
- karyotype, CNV, WGS, WES, or comparable genomic-stability evidence
- sterility, mycoplasma, and endotoxin status
- graft, electrophysiology, behavior, imaging, or other downstream evidence for future calibration
- reviewer notes and known dataset caveats

### ProductDefinitionCard Schema

The model SHALL require a `ProductDefinitionCard` before scoring. A minimal schema is:

```yaml
program_id: PD_mDA_progenitor_v1
version: 0.1.0
intended_product_class: pre-transplant mDA progenitor or precursor product
target_anchor_set: []
adjacent_states: []
off_target_states: []
hard_safety_flags: []
gene_programs: []
reference_assets: []
external_qc_fields: []
score_domains: []
abstention_rules: []
human_review_triggers: []
known_limitations: []
```

The card SHALL be versioned with the model and report. Changing the card changes the score definition and requires a documented validation update.

## Biological Representation Layer

This layer turns single-cell matrices into biologically meaningful model inputs.

### Cell-Level Representations

Candidate feature families:

- BRIDGE Step1 broad cell-state predictions.
- BRIDGE Step2 target-anchor probabilities, entropy, variability, and stable target calls.
- Marker and gene-program scores for mDA progenitor identity, DA-lineage maturation, pluripotency, proliferation, stress, serotonergic, motor neuron, neural crest, mesenchymal, and non-neural states.
- Expression and regulon concordance metrics.
- scVI or scANVI latent coordinates when trained reference models are available.
- Optional single-cell foundation model embeddings, such as scGPT, Geneformer, UCE, or related models, only after benchmarking against simpler baselines.

### Batch Integration and Reference Mapping

BRIDGE v2 SHALL implement controlled batch integration rather than unconditional batch removal. The system SHALL distinguish technical nuisance variables from protected product variables before fitting or applying any integration model.

Default variable policy:

| Variable Type | Examples | Default Model Action |
| --- | --- | --- |
| Technical nuisance | library batch, sequencing run, chemistry, platform, lane | Eligible for correction or covariate modeling after confounding checks. |
| Protected product biology | protocol, product lot, manufacturing batch, donor, treatment, target program, timepoint | Preserved for product scoring, robustness, trajectory, and protocol comparison. |
| Ambiguous/confounded | sequencing run fully aligned with one timepoint, protocol, lot, or source dataset | No automatic correction; mark evidence as limited and require manual review when relevant. |

The representation layer SHALL maintain four evidence spaces:

| Evidence Space | Primary Use | Scoring Boundary |
| --- | --- | --- |
| Raw or normalized expression space | Marker programs, risk flags, pseudo-bulk signatures, transcriptomic potency-related proxy evidence | Primary source for biological score drivers. |
| Reference mapping space | Cell-state annotation, target compatibility, OOD relative to frozen references | Used for alignment and interpretation; not sufficient alone for final scores. |
| Integrated latent space | Visualization, neighborhood alignment, cross-sample cell-state matching, technical artifact diagnostics | SHALL NOT replace expression-derived risk or potency-related evidence. |
| Sample/lot/timepoint summary space | Cross-lot robustness, trajectory evidence, protocol-level aggregation | Built from per-sample profiles; no direct pooling of all cells before scoring. |

Supported integration methods MAY include scVI/scANVI, scArches, Symphony, Harmony, Seurat RPCA, or equivalent reference-mapping approaches. Each use SHALL be versioned and accompanied by an Integration Report containing variables corrected, variables preserved, confounding checks, biological-conservation checks, and overcorrection warnings.

### Product-Level Representations

The model SHALL summarize the complete product, not only a favorable target subset.

Product-level inputs SHOULD include:

- Cell-state composition.
- Stable target fraction.
- Target-anchor distribution.
- Off-target and safety burden.
- Pseudo-bulk gene-program scores.
- Distributional statistics across cells, not only means.
- Metadata-derived protocol, timepoint, and batch features.
- Missingness indicators for absent metadata or absent layers.

### Temporal Representations

For multi-timepoint datasets, the model SHOULD add:

- Timepoint-specific product profiles.
- Direction of target-program enrichment.
- Expansion or resolution of off-target states.
- Maturation trajectory features.
- Candidate transplant-window comparison.

For single-timepoint datasets, the temporal branch SHALL be masked. Missing time-course evidence SHALL reduce evidence confidence but SHALL NOT be treated as a negative biological finding.

## AI Scoring Layer

The AI Scoring Layer SHOULD use progressively stronger models.

### BRIDGE v2.1: AI Calibration Model

The first AI model SHOULD be a calibrated product-level model trained on derived features.

Preferred model family:

- Regularized logistic or ordinal models for interpretable baselines.
- Random forest or gradient boosting for non-linear calibration.
- Isotonic or Platt calibration for probability and confidence outputs.

Inputs:

- BRIDGE v1 raw metrics and gates.
- Product composition features.
- Safety and off-target features.
- Evidence quality features.
- Dataset and protocol metadata where leakage-safe.

Outputs:

- Domain scores.
- Safety and evidence constraint recommendations.
- Candidate integrated score calibration.
- Confidence intervals or uncertainty bands.
- Feature attribution.

### BRIDGE v2.2: Product-Level Set Model

The next model SHOULD learn directly from cell distributions while preserving product-level interpretability.

Preferred architecture:

```text
cell encoder
-> cell-state and gene-program embeddings
-> product aggregator (DeepSets, attention MIL, or Set Transformer)
-> multi-task scoring heads
-> uncertainty and OOD heads
```

Multi-task heads:

- target identity
- potency proxy
- purity / off-target
- safety
- process robustness
- evidence confidence
- total score
- OOD / uncertainty

The product aggregator SHALL receive the complete product distribution. It SHALL NOT be trained only on target-prescreened cells.

### BRIDGE v2.2.5: Time-Course Model

For protocols with multiple timepoints:

```text
per-timepoint product encoder
-> temporal encoder
-> trajectory score
-> collection-window recommendation
```

The temporal encoder MAY be simple at first: ordered product embeddings with masked missing timepoints. More complex recurrent or transformer encoders SHOULD only be used after enough time-course protocols are available.

### BRIDGE v2.3: Optimization Model

The optimization model SHOULD be added only after enough protocol metadata, time-course data, or perturbation/process data exist.

Candidate methods:

- Bayesian optimization over protocol variables.
- Active learning to prioritize new timepoints or assays.
- Counterfactual simulation constrained by observed protocols.
- Ranking models for protocol or collection-window selection.

Optimization recommendations SHALL be framed as hypotheses for experimental follow-up.

## Training Signals

BRIDGE v2 SHOULD combine weak, expert, and future downstream labels.

| Signal | Source | Role |
| --- | --- | --- |
| BRIDGE v1 score and domains | Existing rule-based framework. | Weak-label teacher and baseline. |
| Positive product-like datasets | Known mDA progenitor-oriented protocols. | Product-readiness anchors. |
| Negative/off-target controls | Cortical organoid, motor neuron, neural crest, mesenchymal, non-neural, or off-axis datasets. | Specificity and safety testing. |
| Protocol rankings | Known relative protocol or timepoint suitability from literature or expert review. | Pairwise or ordinal supervision. |
| Expert review | Manual curation of confusing cases. | Error correction and calibration. |
| Outcome-linked evidence | Future graft, electrophysiology, behavioral, or post-transplant data. | v1.5+ calibration, not initial clinical prediction. |

## Weak Supervision Strategy

BRIDGE v1 SHALL remain available. It SHALL provide:

- Initial domain labels.
- Hard safety heuristics.
- Product-composition anchors.
- Transparent baseline scores.
- Failure cases for model comparison.

The AI model SHALL be evaluated against BRIDGE v1 rather than assumed superior. A useful model SHOULD improve at least one of:

- Cross-dataset generalization.
- Protocol ranking.
- Negative-control separation.
- Calibration.
- Missing-data robustness.
- Expert-reviewed biological plausibility.


Weak-label governance SHALL include a label-function registry, coverage and conflict statistics, frozen expert-reviewed benchmark cases, teacher-bias audits, and adjudication notes for cases where BRIDGE v1 and v2 disagree. Expert overrides SHALL be recorded as review evidence, not silently converted into ground truth.

## OOD and Uncertainty

BRIDGE v2 SHALL report uncertainty because public and internal single-cell datasets vary strongly in assay, processing, annotation, gene coverage, and protocol metadata.

Preferred uncertainty methods:

- Bootstrap over cells within a product.
- Ensemble models across random seeds or feature subsets.
- Calibration curves and expected calibration error.
- Distance to reference and training-set embeddings.
- OOD classifier trained on known non-target and low-compatibility datasets.
- Conformal-style score intervals when validation data are sufficient.

Uncertainty SHALL affect the Evidence Confidence constraint and report language.


BRIDGE v2 SHALL decompose OOD states because different failures require different actions:

| OOD State | Typical Trigger | Default Action |
| --- | --- | --- |
| input incompatibility | Low gene overlap, invalid layers, too few cells, ambiguous matrix orientation. | Withhold affected scores or produce profile-only report. |
| technical shift | Platform, chemistry, mapping, or preprocessing differs strongly from validation data. | Lower evidence confidence; run integration sensitivity checks. |
| biological off-target | Product maps to non-target neural or non-neural states. | Score as off-target evidence rather than treating as technical failure. |
| target-program mismatch | Product is a plausible cell therapy product but not the declared target program. | Report mismatch and ask for a different ProductDefinitionCard when appropriate. |
| rare-state warning | Small suspicious population has high-risk markers or unknown identity. | Flag for human review and avoid overconfident absence claims. |
| model epistemic uncertainty | Ensemble disagreement, poor calibration region, or weak-label conflict. | Increase score interval or withhold integrated score. |

## Explainability

The system SHALL explain scores at several levels:

| Level | Explanation |
| --- | --- |
| Domain | Which score domains drive the total score. |
| Cell state | Which target or off-target populations contribute most. |
| Gene program | Which biological programs support or weaken the score. |
| Dataset quality | Which missing or low-quality inputs reduce evidence confidence. |
| Model behavior | Whether AI-calibrated scoring agrees with BRIDGE v1 and why it differs. |

Possible methods:

- SHAP or permutation importance for tabular calibration models.
- Attention or cell-contribution summaries for MIL models.
- Counterfactual removal of cell-state groups.
- Gene-program contribution tables.
- Local comparison to benchmark products and negative controls.

## Foundation Models

Foundation models may be useful as optional representation modules, but they SHALL NOT be the sole AI claim.

Rules for use:

- Treat foundation model embeddings as candidate features.
- Benchmark them against BRIDGE v1 features and simpler biologically informed ML baselines.
- Report ablations with and without foundation embeddings.
- Do not claim improved performance unless validation supports it.
- Keep gene-program and reference-based explanations visible.


## Adapter-First Tool Strategy

BRIDGE v2 SHOULD wrap mature tools through adapters rather than reimplementing core single-cell algorithms. Annotation and reference mapping adapters may target CellTypist, SingleR, scVI/scANVI/scArches, Symphony, Azimuth, or consensus-style tools. Gene-program adapters may target decoupler, UCell, AUCell, VISION, cNMF, or comparable methods. Integration-quality adapters SHOULD reuse scIB or scib-metrics where possible, then add BRIDGE-specific protected-variable and rare-state checks.

Each adapter SHALL record tool version, parameters, input layer, gene universe, and output confidence. Adapter output is evidence for BRIDGE; it is not automatically the BRIDGE score.

## Model Release Requirements

Every model version SHALL include:

- model_id and semantic version
- training dataset manifest
- excluded validation datasets
- feature schema
- score schema
- intended use
- known failure modes
- calibration results
- OOD behavior
- changelog from previous version

## References

- [BRIDGE v2 Product Requirements Document](BRIDGE_v2_PRD.md)
- [BRIDGE v2 Scoring Framework](BRIDGE_v2_Scoring_Framework.md)
- [FDA: Good Machine Learning Practice for Medical Device Development](https://www.fda.gov/medical-devices/software-medical-device-samd/good-machine-learning-practice-medical-device-development-guiding-principles)
- [Luecken et al., Nature Methods 2022: scIB integration benchmark](https://www.nature.com/articles/s41592-021-01336-8)
- [Lotfollahi et al., Nature Biotechnology 2021: scArches reference mapping](https://www.nature.com/articles/s41587-021-01001-7)
- [Kang et al., Nature Communications 2021: Symphony reference mapping](https://www.nature.com/articles/s41467-021-25957-x)
- [Benchmarking foundation cell models for post-perturbation RNA-seq prediction](https://link.springer.com/article/10.1186/s12864-025-11600-2)
