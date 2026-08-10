# BRIDGE v2 Roadmap

## Purpose

This roadmap stages BRIDGE v2 from a documentation-backed product concept to a paper-ready AI scoring system and then to a preclinical translational product-optimization platform.

The roadmap keeps BRIDGE v2 in a research-use and translational product-scoring position until a separate formal validation program supports stronger claims.

The roadmap is organized around the five-layer architecture:

```text
Input Compatibility Layer
-> Biological Representation Layer
-> AI Scoring Layer
-> Optimization & Recommendation Layer
-> Learning Loop / Lifecycle Governance Layer
```

BRIDGE v2 SHOULD improve iteratively:

```text
new data -> error analysis -> expert feedback -> model update -> validation -> versioned release
```

## Phase 0: Framework Documentation

Status: In progress on the isolated `v2-product-evaluation` design branch.

Goal: define the product, score, model, validation, and roadmap before implementation.

Deliverables:

- `BRIDGE_v2_PRD.md`
- `BRIDGE_v2_Scoring_Framework.md`
- `BRIDGE_v2_Model_Architecture.md`
- `BRIDGE_v2_Data_Validation_Plan.md`
- `BRIDGE_v2_Roadmap.md`

Exit criteria:

- The five-layer architecture is consistent across all documents.
- BRIDGE v1 is clearly preserved as the transparent baseline and weak-label teacher.
- Clinical boundary statements are visible.

- Public v2 documents contain no private server paths or unpublished raw-data locations.

## Phase 0.5: Immediate Design Hardening

Goal: incorporate review findings that can be handled immediately through existing document updates, schema definitions, and report contracts.

This phase should not create many new standalone documents. It should patch the current BRIDGE v2 documents directly and use `BRIDGE_v2_Design_Issues_Backlog.md` as the issue tracker.

Immediate deliverables:

- ProductDefinitionCard requirements and first `PD_mDA_progenitor_v1` schema outline.
- Integrated score changed from default required output to validation-eligible optional output; score matrix remains the default public output.
- External QC fields added to Product Data Manifest and Evidence Confidence.
- Rare-event reporting language for low-frequency risk states.
- Non-monotonic transplant-window scoring logic.
- Open-world / rare-state discovery requirements.
- Score contract requirements for each score domain.
- Decomposed OOD and uncertainty taxonomy.
- Integration intent and integration sensitivity panel requirements.
- Locked validation protocol requirements.
- Weak-label governance and human review SOP requirements.
- Adapter-first strategy for annotation, gene-program scoring, and integration benchmarking.

Exit criteria:

- Each immediate issue in `BRIDGE_v2_Design_Issues_Backlog.md` is either patched into an existing document or explicitly deferred with a release window.
- No current document implies that transcriptomic evidence alone is a potency assay, clinical safety conclusion, or therapeutic efficacy prediction.
- The report contract makes integrated scores optional until validation-locked.

## Phase 1: MVP Product Profile Upgrade

Goal: make BRIDGE v2 usable as a documentation-aligned, rule-baseline product profile system before training new models.

Layer deliverables:

| Layer | Deliverable |
| --- | --- |
| Input Compatibility Layer | Product Data Manifest for h5ad inputs, with layer, gene, metadata, timepoint, lot/batch structure, integration eligibility, and score-eligibility checks. |
| Biological Representation Layer | Derived feature tables from BRIDGE v1 outputs, gene programs, composition, risk groups, and technical/protected variable classification. |
| AI Scoring Layer | v2.0 score report using BRIDGE v1 rules, multidimensional domains, and explicit evidence-confidence constraints. |
| Optimization & Recommendation Layer | Rule-based top drivers and missing-data recommendations. |
| Learning Loop / Lifecycle Governance Layer | Dataset card and model card templates. |

Exit criteria:

- A complete product h5ad SHALL produce a BRIDGE v2-style report.
- A single-timepoint dataset is scored with reduced temporal evidence confidence rather than failed by default.
- A multi-timepoint dataset produces a per-timepoint comparison table.
- A multi-lot or multi-batch dataset produces per-sample profiles and a cross-lot robustness summary without pooling all cells before scoring.

## Phase 2: Private Dataset Inventory and Benchmark Panel

Goal: organize the growing candidate data repository into validation-ready strata.

Layer deliverables:

| Layer | Deliverable |
| --- | --- |
| Input Compatibility Layer | Conversion and QC summaries for product-like, time-course, single-timepoint, multi-lot, technical batch challenge, control, and reference datasets. |
| Biological Representation Layer | Harmonized derived features across datasets plus Integration Report prototypes. |
| AI Scoring Layer | Rule-baseline trial runs across all selected datasets. |
| Optimization & Recommendation Layer | First protocol and timepoint comparison examples. |
| Learning Loop / Lifecycle Governance Layer | Private dataset inventory and public-safe derived benchmark policy. |

Exit criteria:

- At least two product-like datasets, two time-course datasets, two single-timepoint datasets, one multi-lot or multi-batch dataset class, one technical batch challenge class, and multiple negative-control classes are represented.
- Public artifacts contain derived metrics only and do not expose private paths or raw unpublished matrices.

## Phase 3: BRIDGE v2.1 AI Calibration Model

Goal: train the first AI model that calibrates BRIDGE v1 features into multidimensional BRIDGE v2 scores.

Layer deliverables:

| Layer | Deliverable |
| --- | --- |
| Input Compatibility Layer | Fixed feature schema and missingness mask. |
| Biological Representation Layer | Stable product-level feature matrix and controlled integration/reference-mapping policy. |
| AI Scoring Layer | AI calibration model for domain scores, safety/evidence constraints, candidate integrated score methods, uncertainty, and feature attribution. |
| Optimization & Recommendation Layer | Score-driver explanations based on feature attribution and benchmark comparison. |
| Learning Loop / Lifecycle Governance Layer | Model card, training manifest, validation report, and changelog. |

Exit criteria:

- AI calibration is compared against BRIDGE v1 and simple baselines.
- Leave-dataset-out and leave-protocol-out validation are reported.
- Batch integration biological-conservation and overcorrection checks are reported when integration is used.
- Negative controls are separated from product-like datasets.
- Calibration and uncertainty are shown.

## Phase 4: Paper-Ready BRIDGE v2

Goal: prepare the manuscript-grade AI product system.

Deliverables:

- Reproducible scoring workflow.
- Dataset and model cards.
- Multidimensional score reports.
- Held-out validation results.
- Ablation table.
- Candidate score-integration comparison.
- Batch integration report with variables corrected, variables preserved, confounding status, and overcorrection checks.
- Missing-data robustness analysis.
- Foundation-model ablation if foundation embeddings are used.
- Clinical boundary and intended-use statements.

Exit criteria:

- The manuscript SHALL support AI-assisted, quantitative, explainable, and iteratively improvable product-readiness scoring claims.
- The manuscript SHALL NOT claim clinical release qualification, validated potency assay status, or patient-level efficacy prediction.

## Phase 5: BRIDGE v2.2 Product-Level Set Model

Goal: add a cell-distribution-aware model that learns from complete products rather than only derived summary metrics.

Layer deliverables:

| Layer | Deliverable |
| --- | --- |
| Input Compatibility Layer | Cell-level feature schema and scalable sampling policy. |
| Biological Representation Layer | Cell encoder and product embeddings. |
| AI Scoring Layer | MIL, DeepSets, or Set Transformer model with multi-task heads. |
| Optimization & Recommendation Layer | Cell-state contribution and counterfactual removal explanations. |
| Learning Loop / Lifecycle Governance Layer | Model registry and drift monitoring plan. |

Exit criteria:

- Product-level model outperforms or complements the BRIDGE v2.1 calibrator on held-out validation.
- Cell-state explanations are biologically plausible.
- Uncertainty remains visible.

## Phase 6: BRIDGE v2.2.5 Time-Course and Collection-Window Model

Goal: use multi-timepoint protocols to support transplant-window and trajectory-aware scoring.

Deliverables:

- Per-timepoint product embeddings.
- Trajectory score.
- Timepoint ranking.
- Off-target expansion or resolution analysis.
- Single-timepoint fallback mode.

Exit criteria:

- Multi-timepoint inputs provide additional value over single-timepoint mode.
- Single-timepoint inputs remain supported with lower temporal evidence confidence.

## Phase 7: BRIDGE v2.3 Optimization and Active Learning

Goal: move from evaluation to AI-assisted protocol optimization.

Candidate capabilities:

- Suggest which timepoint to profile next.
- Suggest which off-target state SHOULD be experimentally reduced.
- Prioritize protocols for downstream assays.
- Use Bayesian optimization or active learning when process variables become available.
- Connect pre-transplant features to future graft or functional evidence.

Exit criteria:

- Recommendations are framed as experimental hypotheses.
- Optimization models are validated against held-out protocol or time-course evidence.
- Outcome-linked claims remain separated from reference-based scoring.

Deferred until this phase or later:

- Bayesian optimization or active learning based on real process variables.
- Experimental action-space definition with constraints, replicate policy, assay noise, and batch acquisition logic.
- Outcome-linked score calibration when graft, functional, imaging, or clinical exploratory evidence becomes available.

## Phase 8: Preclinical Translational System

Goal: prepare BRIDGE v2 for more formal preclinical and CQA-style use.

Deliverables:

- Expanded validation with internal and public datasets.
- Locked score schema for specific model versions.
- Model monitoring and retraining policy.
- Human review workflow.
- Audit-ready model cards and dataset cards.
- Optional integration with downstream functional or graft data.
- External QC linkage including genomic integrity, CNV/WGS/WES status, release-assay panel, biodistribution, tumorigenicity, and GLP safety summaries when available.

Exit criteria:

- The system SHALL support translational product comparison and CQA discovery within the defined research-use scope.
- The system SHALL NOT claim validated clinical release unless a separate formal validation program is completed.

## Roadmap Risks

| Risk | Mitigation |
| --- | --- |
| Rule-based baseline dominates AI model. | Treat this as a valid result; publish AI calibration only where it improves generalization, calibration, or uncertainty. |
| Foundation embeddings do not improve performance. | Keep them optional and report ablations. |
| Dataset heterogeneity causes unstable scores. | Use manifests, missingness masks, OOD detection, controlled integration, and evidence confidence gates. |
| Batch integration removes true product differences. | Protect product lot, protocol, donor, treatment, and timepoint variables by default; validate biological conservation and overcorrection checks. |
| Time-course data are sparse. | Support single-timepoint mode and avoid overclaiming trajectory conclusions. |
| Clinical claims exceed evidence. | Keep intended use, boundary statements, and validation scope visible in every report. |

## References

- [BRIDGE v2 Product Requirements Document](BRIDGE_v2_PRD.md)
- [BRIDGE v2 Scoring Framework](BRIDGE_v2_Scoring_Framework.md)
- [BRIDGE v2 Model Architecture](BRIDGE_v2_Model_Architecture.md)
- [BRIDGE v2 Data and Validation Plan](BRIDGE_v2_Data_Validation_Plan.md)
