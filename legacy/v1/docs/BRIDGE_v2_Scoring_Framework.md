# BRIDGE v2 Scoring Framework

## Purpose

This document defines the first BRIDGE v2 scoring design. The goal is to provide quantitative, multidimensional, and interpretable product-readiness scores for pre-transplant Parkinson's disease mDA cell products while preserving the transparent BRIDGE v1 baseline.

The score is intended for research-use and translational product evaluation. It SHALL NOT be used as a clinical release criterion, a validated potency assay, or a therapeutic efficacy prediction.

## Relationship to BRIDGE v1

Earlier BRIDGE v1 documentation used a gated baseline that combined target-program, safety, and product-quality evidence. BRIDGE v2 treats that as a transparent historical baseline, not as the final v2 formula. A pure multiplicative gate may be too brittle for a heterogeneous AI-assisted product system: a modestly low gate can collapse the total score, and the formula does not by itself express uncertainty, missing evidence, calibration, or partially independent CQA evidence.

BRIDGE v2 keeps the profile-first philosophy and adds:

- A broader multidimensional score matrix.
- Explicit evidence confidence.
- Missing-data-aware scoring.
- AI calibration and uncertainty.
- Iterative model improvement.

BRIDGE v1 remains the transparent baseline and weak-label teacher. BRIDGE v2 SHALL report where its AI-calibrated score agrees with or diverges from the v1 score.

## Evidence-Informed Scoring Policy

The v2 score integration SHALL be designed after reviewing cell-therapy potency, CQA, and quality-risk-management evidence:

- Potency assurance for cellular and gene therapy products is science- and risk-based, and FDA describes it as a multifaceted strategy covering process design, process control, materials, in-process testing, and lot-release assays.
- FDA potency testing guidance recognizes that a single assay may not adequately measure potency for complex products and allows an assay matrix of complementary biological and analytical assays when correlated with relevant biological activity.
- ICH Q8/Q9-style product development starts from QTPP and potential CQAs, then updates CQA prioritization as product and process understanding increases.
- Regenerative medicine CQA identification is difficult because identity, purity, viability, sterility, and biological activity may not have simple in vitro-to-in vivo mappings.
- Structured decision models such as MCDA can make trade-offs transparent and auditable, but there is no universal consensus method; weights and thresholds need validation.

Therefore, BRIDGE v2 SHALL NOT lock a single total-score formula before validation. It SHALL maintain a score matrix and evaluate alternative score-integration models.

## Five-Layer Scoring Map

| Layer | Scoring Responsibility |
| --- | --- |
| Input Compatibility Layer | Determines whether the input can be scored, partially scored, or only profiled. |
| Biological Representation Layer | Produces cell-state, gene-program, trajectory, and reference-similarity evidence. |
| AI Scoring Layer | Converts evidence into calibrated domain scores, gates, total score, and uncertainty. |
| Optimization & Recommendation Layer | Explains which biological or technical factors drive the score and what could improve it. |
| Learning Loop / Lifecycle Governance Layer | Tracks score versioning, calibration, validation, monitoring, and model updates. |

## Domain Scores

Each domain score is reported on a 0-100 scale. Higher is better unless explicitly described as a raw risk metric. Raw risk metrics SHALL be converted into higher-is-better safety or purity scores before entering the final score.



Each score domain SHALL have a score contract before implementation:

| Contract Field | Requirement |
| --- | --- |
| raw evidence | The metric, denominator, expression layer, reference model, and product subset used. |
| directionality | Whether higher raw values support, weaken, or non-monotonically affect product readiness. |
| normalization | Calibration anchors or transformation used to map raw evidence to 0-100. |
| uncertainty | Bootstrap, ensemble, calibration, or model-disagreement estimate when available. |
| missing-data state | Complete, partial, minimal, low compatibility, or unavailable. |
| abstention rule | Conditions under which the domain or integrated score is withheld. |
| false-reassurance check | Negative-control, rare-event, or OOD behavior that must be monitored. |
| report language | Human-readable interpretation and intended-use boundary. |

The integrated score has the strictest contract: it may be reported only when domain contracts, calibration anchors, safety constraints, and evidence-confidence rules are locked for the model version.

| Domain | Main Evidence | Higher Score Means |
| --- | --- | --- |
| Target Identity Score | Target-anchor probability, stable target fraction, mDA progenitor markers, reference similarity. | The complete product strongly matches the intended mDA progenitor-oriented program. |
| Transcriptomic Potency-Related Proxy Score | Product-window coherence, DA-lineage maturation, mechanism-relevant gene programs, benchmark similarity. | The product has transcriptomic features expected for a transplant-suitable progenitor or precursor product; this does not constitute a potency assay. |
| Purity / Off-target Score | Off-axis neural burden, non-midbrain burden, serotonergic-like, motor neuron, neural crest, mesenchymal or non-neural states. | Risk-relevant off-target populations are limited. |
| Transcriptomic Risk Flag Score | Residual pluripotency, unresolved proliferative uncommitted cells, severe non-neural contamination, high-risk stress or abnormal growth signals. | Hard transcriptomic risk flags are absent or low; this does not constitute a clinical safety conclusion. |
| Process Robustness Score | Batch consistency, sample consistency, time-course directionality, stable target trajectory. | The product profile is reproducible or moves coherently toward the intended state. |
| Evidence Confidence Score | Cell count, gene overlap, layer availability, metadata completeness, timepoint coverage, reference compatibility, OOD and model uncertainty. | The result is supported by sufficient and compatible evidence. |

## Batch Integration and Scoring Boundaries

Batch integration SHALL be treated as a representation and diagnostic procedure, not as a default replacement for scoring evidence.

| Scoring Component | Integration Use | Required Boundary |
| --- | --- | --- |
| Target Identity Score | May use reference mapping and integrated latent neighborhoods to support cell-state assignment. | Target marker and gene-program evidence SHALL remain traceable to raw or normalized expression. |
| Transcriptomic potency-related proxy evidence | May use mapped cell states to define the relevant denominator. | The proxy score SHALL NOT be computed only from corrected expression or latent coordinates. |
| Purity / Off-target Score | May use integration to align rare off-target states across samples. | Off-target marker evidence SHALL be verified in raw or normalized expression space. |
| Transcriptomic Risk Flag Score | May use integration to localize suspicious clusters for review. | Risk flags SHALL be based on expression-level evidence and SHALL NOT be removed by batch correction. |
| Process Robustness Score | SHALL compare per-sample and per-lot profiles after technical confound checks. | Product lots, protocols, donors, and timepoints SHALL NOT be corrected away as nuisance variables by default. |
| Evidence Confidence Score | SHALL incorporate integration eligibility, confounding status, and overcorrection checks. | Confounded batch/timepoint/protocol designs SHALL reduce evidence confidence rather than produce a falsely precise score. |

The default aggregation order SHALL be:

```text
per-sample Product Profile
-> per-lot or per-batch summary
-> per-timepoint trajectory summary
-> protocol-level robustness summary
```

BRIDGE v2 SHALL NOT pool all cells across product lots, timepoints, or protocols before product scoring. Pooling may be used only for explicitly documented exploratory visualization or reference-building workflows, not for sample-level product-readiness evidence.

## Integrated Score Strategy

BRIDGE v2 SHALL report a total or integrated score only as a calibrated product-readiness index. The initial documentation SHALL define requirements and candidate integration methods, not a final mathematical formula.

```text
BRIDGE v2 Integrated Product Readiness Score
= score_integration_model(domain_scores, safety_constraints, evidence_state, uncertainty)
```

Candidate integration methods:

| Candidate | Description | When Useful | Main Caveat |
| --- | --- | --- | --- |
| Profile-first scorecard | Report domains, gates, uncertainty, and no single total score unless validation supports it. | Earliest research stage and confusing OOD cases. | Harder to rank products. |
| Constrained additive index | Weighted domain score with safety and evidence constraints acting as caps, flags, or report states. | Manuscript-friendly first total score. | Weights SHALL be justified and calibrated. |
| MCDA-style model | Explicit stakeholder/scientific weights over identity, transcriptomic potency-related proxy evidence, purity/off-target burden, transcriptomic risk flags, robustness, and evidence quality. | Transparent trade-off documentation. | Still partly expert-driven. |
| Learned calibrated index | ML model trained on weak labels, expert review, controls, protocol rankings, and future outcome-linked evidence. | Later AI version after enough validation data. | Requires careful leakage control and calibration. |

The recommended first paper-ready path is:

```text
domain score matrix
+ safety/evidence constraints
+ provisional constrained additive or MCDA-style index
+ validation against BRIDGE v1, controls, protocol rankings, and expert review
```

This keeps a total score available for comparison while making it clear that the formula is provisional and evidence-calibrated.

## Safety Constraints

Safety evidence SHALL protect the total score from being rescued by a strong target subset when the complete product contains severe risk-relevant evidence. In v2, this does not have to be implemented as a simple multiplier. Safety may instead act as a cap, constraint, warning state, or hard research-use exclusion depending on validation.

Default gate states:

| State | Possible Score Role | Example Evidence |
| --- | --- | --- |
| Pass | No cap; safety domain contributes normally. | No hard safety flag; safety score is high. |
| Caution | Cap total score band or require warning label. | Moderate off-target or proliferative burden that needs review. |
| Warning | Strong cap, low-confidence state, or manual review requirement. | Strong unresolved risk signal but not enough evidence for a hard fail. |
| Research fail | Withhold positive product-readiness score. | Residual pluripotency-like core evidence, severe non-neural contamination, or uninterpretable high-risk profile. |

A research fail means the transcriptomic profile is not suitable for a positive BRIDGE v2 product-readiness score. It does not mean a clinical safety conclusion has been validated.

## Evidence Confidence Constraint

The Evidence Confidence constraint expresses whether the score is well supported by the submitted data. It SHALL distinguish a biologically weak product from an under-evidenced product.

| Evidence State | Possible Score Role | Meaning |
| --- | --- | --- |
| Complete | Full score eligible. | Strong gene overlap, usable counts or normalized layer, sufficient cells, meaningful metadata, and time-course or replicate support when expected. |
| Partial | Score eligible with confidence interval and caveats. | Core scoring works, but some optional layers, metadata, or timepoints are missing. |
| Minimal | Score eligible only as a limited-evidence estimate. | Single-timepoint or sparse metadata input; product scoring is possible but optimization claims are limited. |
| Low compatibility | Total score may be capped or withheld. | Low gene overlap, ambiguous sample identity, or strong OOD signal; report SHALL emphasize uncertainty. |
| Unscorable | No total score; profile-only error report. | Matrix, gene mapping, or cell count is insufficient for meaningful reference mapping. |

Single-timepoint products SHOULD usually fall into Partial or Minimal rather than Unscorable, provided expression data are compatible.


## Product-Window Logic

For pre-transplant PD cell products, developmental-window evidence SHALL be non-monotonic. More mature DA-lineage signal is not automatically better, and more progenitor signal is not automatically safer. The product definition SHALL distinguish at least three states:

| Window State | Interpretation | Score Behavior |
| --- | --- | --- |
| Too early or poorly patterned | Neural progenitor or proliferative programs without sufficient ventral midbrain / DA-lineage anchoring. | Low target identity or low product-window score, with patterning guidance. |
| Coherent transplant-suitable progenitor or precursor window | Target-anchor, floor-plate-like, and DA-lineage evidence are present without dominant off-target or over-mature burden. | Eligible for high target and product-window scores when evidence confidence is adequate. |
| Over-mature or off-window | Strong neuron/neuroblast or mature DA signal dominates the product before transplant, or target progenitor pool is depleted. | Product-window score may decrease even if DA-lineage markers are high. |

The report SHALL describe the apparent window and its uncertainty rather than treating maturation as a one-way positive axis.

## Rare-Event and Open-World Risk Reporting

Rare high-risk populations require special language. BRIDGE v2 SHALL report residual pluripotency-like, neural-crest/peripheral, serotonergic-like, robust non-neural, or abnormal proliferative uncommitted signals with sample-depth caveats. A report may say `not detected at the sampled depth`; it SHALL NOT claim that a rare risk state is absent unless supported by orthogonal evidence or a validation protocol.

The system SHALL also maintain an open-world review queue for suspicious cell clusters that do not match known target, adjacent, or predefined risk states. Unknown-state reports SHOULD include marker programs, nearest references, abundance, confidence, and whether human review is required.

## Missing-Data Strategy

BRIDGE v2 SHALL distinguish between missing evidence and negative evidence.

| Missing Item | Score Behavior | Report Behavior |
| --- | --- | --- |
| Missing time course | Do not set trajectory score to zero; reduce evidence confidence and disable trajectory claims. | State that collection-window optimization is limited. |
| Missing batch metadata | Process robustness becomes sample-internal only. | State that batch consistency cannot be assessed. |
| Missing raw counts | Use normalized evidence when valid; mark count-dependent diagnostics partial. | Report affected metrics. |
| Missing cell-type labels | Use reference mapping and model-derived labels. | State that user-provided labels were unavailable. |
| Low gene overlap | Lower evidence confidence; withhold total score if too severe. | Report overlap fraction and affected programs. |
| Missing outcome data | No penalty for BRIDGE v2 product scoring. | State that score is reference-based, not outcome-calibrated. |

## AI Calibration Stages

The scoring system SHOULD evolve in stages:

| Stage | Description | Role |
| --- | --- | --- |
| BRIDGE v2.0 rule-aligned baseline | Existing BRIDGE v1 gates and product-quality domains plus explicit evidence-confidence constraint. | Transparent baseline and weak-label teacher. |
| BRIDGE v2.1 AI calibrator | Tabular or shallow ML model trained on BRIDGE v1 metrics, public positive/negative controls, protocol rankings, and expert review. | Learns calibrated domain scores and improves generalization. |
| BRIDGE v2.2 product-level model | Cell encoder plus product-level MIL or Set Transformer with uncertainty heads. | Learns from cell distributions directly while preserving interpretability. |
| BRIDGE v2.3 optimization model | Active-learning or Bayesian optimization layer using protocol, timepoint, and perturbation metadata. | Suggests how to improve differentiation or collection strategy. |

## Report Requirements

Every BRIDGE v2 score report SHALL include:

- Domain score table.
- Safety and evidence constraint table.
- Raw evidence table.
- Normalized evidence table.
- Missing-data table.
- Uncertainty and OOD table.
- Top positive score drivers.
- Top negative score drivers.
- Score-integration method and version.
- Statement of whether the total score is provisional, calibrated, or withheld.
- Clear boundary statement.

Required boundary statement:

```text
BRIDGE v2 scores are research-use, transcriptome-based product-readiness evidence for comparing and optimizing pre-transplant PD cell products. Any integrated total score is provisional until validated and calibrated. The score SHALL NOT be used as a clinical release criterion, validated potency assay, or therapeutic efficacy prediction.
```

## References

- [BRIDGE v1 Product Evaluation Framework](product_score_v1.md)
- [BRIDGE v2 Product Requirements Document](BRIDGE_v2_PRD.md)
- [FDA: Potency Assurance for Cellular and Gene Therapy Products](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/potency-assurance-cellular-and-gene-therapy-products)
- [FDA: Potency Tests for Cellular and Gene Therapy Products](https://www.fda.gov/files/vaccines%2C%20blood%20%26%20biologics/published/Final-Guidance-for-Industry--Potency-Tests-for-Cellular-and-Gene-Therapy-Products.pdf)
- [FDA: ICH Q8(R2) Pharmaceutical Development](https://www.fda.gov/media/71535/download)
- [FDA: Q9(R1) Quality Risk Management](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/q9r1-quality-risk-management)
- [Single-cell best practices: data integration](https://www.sc-best-practices.org/cellular_structure/integration.html)
- [Luecken et al., Nature Methods 2022: scIB integration benchmark](https://www.nature.com/articles/s41592-021-01336-8)
