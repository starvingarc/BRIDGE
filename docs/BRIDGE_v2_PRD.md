# BRIDGE v2 Product Requirements Document

## Status and Positioning

BRIDGE v2 is the proposed research-use and translational AI-assisted product-scoring version of BRIDGE. It extends the current BRIDGE v1 Product Profile and BRIDGE Product Score with iterative machine learning, uncertainty assessment, and product-optimization support.

BRIDGE v2 SHALL NOT be used as a clinical lot-release system, a validated potency assay, or a therapeutic efficacy predictor. Its first product goal is to make single-cell evidence for pre-transplant Parkinson's disease cell products quantitative, comparable, explainable, and improvable over time.

The first target program is:

```text
PD_mDA_progenitor_v1
```

The intended product class is pre-transplant stem-cell-derived dopaminergic progenitor or precursor products for Parkinson's disease research and translational development.

## Product Vision

BRIDGE v2 SHALL address five practical questions for a cell-product developer:

1. Is the submitted product transcriptomically compatible with an mDA progenitor-oriented product concept?
2. Which target and off-target cell states drive the product profile?
3. How strong is the evidence, given the available data quality and timepoint coverage?
4. Which protocol, batch, or collection time appears more suitable for product development?
5. How should the model improve after new datasets, expert review, or downstream evidence become available?

The system SHALL start from transparent BRIDGE v1 rules and evolve toward AI-calibrated scoring. The rules remain visible as a baseline and weak-label teacher rather than being hidden behind a black-box score.

## Five-Layer Product Architecture

```text
Input Compatibility Layer
-> Biological Representation Layer
-> AI Scoring Layer
-> Optimization & Recommendation Layer
-> Learning Loop / Lifecycle Governance Layer
```

| Layer | Product Role | Main User Value |
| --- | --- | --- |
| Input Compatibility Layer | Accept heterogeneous single-cell datasets and convert them into a scored product manifest. | Users can submit realistic public or internal datasets without manual reformatting into one perfect schema. |
| Biological Representation Layer | Convert cells, samples, protocols, and timepoints into biologically meaningful features and embeddings. | The model sees target identity, off-target burden, maturation, safety, and trajectory evidence rather than raw labels alone. |
| AI Scoring Layer | Produce multidimensional domain scores, uncertainty, evidence confidence, and an integrated-score eligibility state. | Users receive quantitative product-readiness evidence with transparent caveats before any optional total score is shown. |
| Optimization & Recommendation Layer | Identify score drivers and propose protocol-level or data-collection next steps. | Users can decide which timepoint, batch, or off-target issue to investigate next. |
| Learning Loop / Lifecycle Governance Layer | Version datasets, models, score definitions, validation results, and model cards. | The product can improve while preserving reproducibility and scientific traceability. |

## Target Users

| User | Needs | Required Output |
| --- | --- | --- |
| Cell-product scientist | Compare differentiation schemes and timepoints. | Product profile, multidimensional score, target/off-target drivers, suggested optimization focus. |
| Translational research lead | Decide which protocol deserves deeper validation. | Ranked product summaries, evidence tiers, uncertainty, and boundary statements. |
| Computational biologist | Inspect model behavior and failure cases. | Feature tables, embeddings, OOD warnings, explainability reports, validation splits. |
| CMC-oriented analyst | Connect transcriptomic evidence to CQA-style reasoning. | Domain scores mapped to identity, purity, safety, potency proxy, robustness, and evidence quality. |
| Manuscript author | Present an AI-assisted product framework without overclaiming clinical validation. | Reproducible methods, model card, validation plan, and reporting checklist alignment. |

## Core Use Cases

### Product Readiness Scoring

Given one pre-transplant product h5ad file, BRIDGE v2 SHALL return a product profile with 0-100 domain scores, evidence confidence, uncertainty, raw metric tables, and an integrated-score eligibility state. A single integrated score is optional and SHALL be shown only when the validation protocol supports it.

### Protocol and Timepoint Comparison

Given several samples from one or more differentiation protocols, the system SHOULD compare product-readiness trajectories and identify candidate collection windows.

### Single-Timepoint Assessment

Given only a day-before-transplant or final pre-transplant sample, the system SHALL still score the product when expression data are compatible. Missing temporal evidence SHALL reduce evidence confidence and disable trajectory-specific conclusions rather than cause a hard failure.

### Multi-Timepoint Trajectory Assessment

Given a time-course dataset, the system SHOULD evaluate whether the product moves toward a coherent mDA progenitor-oriented state, whether off-target states expand or resolve, and which timepoint appears most product-like.

### Negative-Control and Off-Target Stress Testing

Given non-midbrain, cortical organoid, motor neuron, neural crest, mesenchymal, or other off-target controls, the system SHOULD produce low product-readiness scores and interpretable off-target explanations.

## Input Requirements

The preferred input is an AnnData `.h5ad` file representing the complete product sample. Future adapters may support Seurat RDS, 10x directories, and dataset manifests.

Required minimum:

- Cell-by-gene expression matrix.
- Gene identifiers that can be mapped to human gene symbols or Ensembl IDs.
- Enough cells and genes to support reference mapping or a documented low-confidence state.

Recommended inputs:

- Raw counts or a counts layer.
- Normalized layer such as `logcounts`.
- Sample, protocol, product lot, manufacturing batch, donor, timepoint, treatment, library batch, sequencing run, chemistry, and platform metadata when available.
- Existing cell-type annotations when available, treated as optional evidence rather than ground truth.

Supported input patterns:

| Pattern | Expected Behavior |
| --- | --- |
| Rich time-course dataset | Full product and trajectory assessment. |
| Single final pre-transplant sample | Product score with reduced temporal evidence confidence. |
| Single timepoint with multiple product lots or batches | Cross-lot product-profile consistency, outlier-lot detection, and process-robustness evidence without trajectory claims. |
| Multiple timepoints with multiple product lots or batches | Per-sample profiles, within-lot trajectories, cross-lot trajectory robustness, and candidate collection-window prioritization for research validation. |
| Missing cell-type labels | Reference mapping and model-derived labels are used; label absence is reported. |
| Missing raw counts | Expression and mapping proceed when possible; count-dependent metrics are marked partial. |
| Sparse metadata | Product manifest records missing fields and limits protocol-level conclusions. |
| Low gene overlap | Score may be withheld or heavily confidence-gated if compatibility is too low. |


## ProductDefinitionCard Requirement

Every BRIDGE v2 run SHALL be tied to a versioned `ProductDefinitionCard`. The card defines the biological product concept before scoring starts, so that marker direction, developmental-window interpretation, and risk handling are not inferred ad hoc from one dataset.

For the default `PD_mDA_progenitor_v1` program, the first card SHOULD include:

| Field | Required Content |
| --- | --- |
| target_program | Pre-transplant ventral midbrain / floor-plate-like dopaminergic progenitor or precursor product concept. |
| target_anchor_set | Accepted reference anchors such as RG_mFP, floor-plate-like mDA progenitor states, and closely related ventral midbrain precursor states. |
| adjacent_or_deviation_states | Mesencephalon non-floor-plate, MHB, ventral hindbrain, forebrain or diencephalic progenitors, immature DA neuron or neuroblast-like off-window states. |
| transcriptomic_support | Marker programs, reference mapping, expression concordance, regulon evidence, and product-level composition metrics used as research evidence. |
| hard_safety_flags | Residual pluripotency with convergent evidence, serotonergic-like contamination, neural-crest/peripheral fate, robust non-neural contamination, and abnormal uncommitted proliferative clusters. |
| product_window_logic | Transplant-window suitability is non-monotonic: too immature, coherent progenitor-like, and over-mature states receive different interpretations. |
| external_qc_fields | Optional viability, enrichment/sorting method, release-assay panel, karyotype/CNV/WGS/WES, sterility/mycoplasma/endotoxin, cryopreservation/thaw status, graft/function evidence, and known assay caveats. |
| score_policy | Which domains are eligible for scoring, which evidence is missing, when an integrated score may be withheld, and when human review is required. |

The ProductDefinitionCard is a software evaluation profile, not a new biological cell-type label. Fixed marker lists may support the card, but they do not replace it.

## Batch Integration Policy

BRIDGE v2 SHALL support controlled single-cell batch integration, but it SHALL NOT treat all batch labels as nuisance variables. Product lots, differentiation batches, protocols, donors, treatments, and timepoints may represent the product biology being evaluated and SHALL be protected from default correction unless a validation protocol explicitly classifies them as technical artifacts.

The Product Data Manifest SHALL classify metadata variables into:

| Variable Class | Examples | Default Action |
| --- | --- | --- |
| Technical nuisance variables | library batch, sequencing run, chemistry, platform, lane, operator when not part of the biological question | Eligible for correction or covariate modeling after confounding checks. |
| Protected product variables | product lot, manufacturing batch, protocol, donor, treatment, timepoint, target program | Preserved for scoring, robustness, trajectory, and protocol comparison. |
| Ambiguous or confounded variables | a sequencing run that contains only one timepoint, one lot, or one protocol | No automatic correction; report reduced evidence confidence or require manual review. |

BRIDGE v2 SHALL use integration primarily for reference mapping, cell-state alignment, visualization, OOD assessment, and neighborhood-level interpretation. Direct marker programs, transcriptomic risk flags, potency-related proxy evidence, and score drivers SHALL remain traceable to raw or normalized expression evidence. The system SHALL NOT pool all cells across product lots or timepoints before scoring; it SHALL score each sample first and then aggregate at lot, trajectory, and protocol levels.


Before any integration run, the manifest SHALL record an `integration_intent` such as reference mapping, exploratory visualization, technical-nuisance correction, cross-platform alignment, or rare-state review. Each intent SHALL define which variables are eligible for correction, which variables are protected, which score domains may use the integrated representation, and which conclusions remain expression-space only.

## Output Requirements

BRIDGE v2 SHALL produce:

- Product Data Manifest.
- BRIDGE v2 Product Profile.
- Batch Integration Report when more than one sample, lot, run, platform, or timepoint is provided.
- Multidimensional score table.
- Integrated Product Readiness Score eligibility state; when validation-locked, optional integrated score with gates and confidence.
- Raw metric table and normalized metric table.
- Missing-data and OOD warning table.
- Explanation of top positive and negative score drivers.
- Recommendation summary for protocol or data-collection improvement.
- Model card and dataset card references for the model version used.

Every reported score SHALL include:

- Raw evidence.
- Normalized score.
- Directionality.
- Weight or gate role.
- Uncertainty or confidence state.
- Missing-data state.
- Human-readable interpretation.

## Scoring Requirements

The scoring system SHALL be multidimensional and quantitative. The minimum first-pass score domains are:

| Domain | Meaning |
| --- | --- |
| Target Identity Score | How strongly the product matches the intended mDA progenitor-oriented program. |
| Potency Proxy Score | Transcriptomic evidence related to maturation window, DA-lineage functionality, and transplant-suitable progenitor state. |
| Purity / Off-target Score | Degree to which non-target and risk-relevant off-axis states are limited. |
| Safety Score | Absence of residual pluripotency, severe non-neural contamination, unresolved proliferative uncommitted states, or other transcriptomic safety flags. |
| Process Robustness Score | Consistency across batches, samples, or timepoints when such evidence exists. |
| Evidence Confidence Score | Data completeness, compatibility, sample size, gene overlap, timepoint coverage, and model uncertainty. |

The total score SHALL NOT be treated as a fixed hand-written formula at the product-definition stage. The BRIDGE v1-style gated expression is useful as a transparent baseline, but BRIDGE v2 SHALL evaluate score-integration strategies empirically before freezing the total score.

```text
BRIDGE v2 Integrated Product Readiness Score
= calibrated integration of domain scores, safety constraints, evidence confidence, and uncertainty
```

The exact integration method, weight policy, and gate behavior are design candidates to be validated in `BRIDGE_v2_Scoring_Framework.md` and `BRIDGE_v2_Data_Validation_Plan.md`.

## Non-Goals

BRIDGE v2 SHALL NOT claim to:

- Define a clinical release specification.
- Replace GMP release testing, sterility, viability, potency, safety, or identity assays.
- Predict patient-level therapeutic efficacy.
- Replace animal, graft, electrophysiology, imaging, or clinical follow-up evidence.
- Certify a product as safe for transplantation.
- Treat a foundation model embedding as sufficient proof of artificial intelligence.

## Clinical and Regulatory Framing

BRIDGE v2 SHOULD follow the spirit of Good Machine Learning Practice for AI/ML-enabled medical software development: representative data, independent testing, transparency, monitoring, and lifecycle governance. It SHOULD also borrow reporting discipline from TRIPOD+AI and DECIDE-AI when describing model development, validation, and early decision-support evaluation.

The appropriate first manuscript claim is:

```text
BRIDGE v2 is a research-use, AI-assisted framework for quantitative, explainable, and iteratively improvable assessment of pre-transplant PD cell products from single-cell transcriptomic data.
```

## Success Criteria

The documentation and later implementation SHALL be considered successful when:

- A user can understand how BRIDGE v2 extends BRIDGE v1 without replacing the v1 baseline.
- Single-timepoint and multi-timepoint datasets are both explicitly supported.
- The score is multidimensional, quantitative, and gated by safety and evidence confidence.
- The AI component is described as a learning system with validation, not as a label attached to fixed rules.
- The product has a clear path from MVP to paper-ready model to preclinical translational refinement.

## References

- [BRIDGE v1 Product Evaluation Framework](product_score_v1.md)
- [FDA: Potency Assurance for Cellular and Gene Therapy Products](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/potency-assurance-cellular-and-gene-therapy-products)
- [FDA: Good Machine Learning Practice for Medical Device Development](https://www.fda.gov/medical-devices/software-medical-device-samd/good-machine-learning-practice-medical-device-development-guiding-principles)
- [TRIPOD+AI statement](https://www.bmj.com/content/385/bmj-2023-078378)
- [DECIDE-AI reporting guideline](https://www.nature.com/articles/s41591-022-01772-9)
- [Single-cell best practices: data integration](https://www.sc-best-practices.org/cellular_structure/integration.html)
- [Luecken et al., Nature Methods 2022: scIB integration benchmark](https://www.nature.com/articles/s41592-021-01336-8)
