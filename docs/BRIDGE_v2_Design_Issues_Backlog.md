# BRIDGE v2 Design Issues Backlog

## Purpose

This backlog records design issues identified after literature, guideline, repository, and subagent review. It is not a request to create many additional documents. The default action is to update the existing BRIDGE v2 documents directly:

- `BRIDGE_v2_PRD.md`
- `BRIDGE_v2_Scoring_Framework.md`
- `BRIDGE_v2_Model_Architecture.md`
- `BRIDGE_v2_Data_Validation_Plan.md`
- `BRIDGE_v2_Roadmap.md`
- `BRIDGE_v2_Chinese_Overview.md`

Separate files should be created only when a topic becomes a reusable schema or controlled artifact, such as a target-program `ProductDefinitionCard` template.

## Design Decision

BRIDGE v2 should remain a compact document system. The next revision should patch the current documents rather than expand into many disconnected documents.

| Decision | Current Position |
| --- | --- |
| Product name | BRIDGE v2 |
| Product positioning | Research-use / translational AI-assisted product scoring |
| Default output | Profile-first score matrix |
| Integrated score | Optional and validation-locked; not a default required output |
| Batch integration | Controlled integration with protected product variables |
| AI claim | Supported by learning signals, validation, uncertainty, OOD handling, and lifecycle governance |

## Execution Allocation

Issues are assigned to one of three execution windows:

| Window | Meaning | Default Handling |
| --- | --- | --- |
| Now | Can be implemented immediately as documentation, schema, report contract, validation protocol, or rule-baseline behavior | Patch existing BRIDGE v2 docs in the next pass |
| Next | Requires implementation work or available candidate datasets, but does not require outcome-linked clinical/preclinical evidence | Add to v2.1-v2.2 release gates |
| Later | Requires future orthogonal assays, graft/function/outcome-linked data, prospective validation, or mature optimization data | Keep in Roadmap / future plan; do not overclaim in current docs |

### Now: Directly Patch Existing Documents

These items are immediately actionable because they are primarily specification, reporting, schema, or validation-design work.

| ID | Action | Target Existing Documents |
| --- | --- | --- |
| SCORE-001 | Make integrated score optional and validation-eligible rather than required by default | PRD, Scoring Framework, Chinese Overview |
| BIOL-001 | Add ProductDefinitionCard requirements and a first `PD_mDA_progenitor_v1` schema outline | PRD, Model Architecture, Scoring Framework, Chinese Overview |
| BIOL-003 | Add external QC fields to Product Data Manifest and Evidence Confidence | PRD, Chinese Overview, Data Validation Plan |
| BIOL-004 | Add rare-event detection language and sampled-depth caveats | Scoring Framework, Chinese Overview |
| BIOL-005 | Add open-world / rare-state discovery mode | Model Architecture, Scoring Framework, Chinese Overview |
| BIOL-006 | Define non-monotonic transplant-window logic | Scoring Framework, Model Architecture, Chinese Overview |
| AI-001 | Add score contract requirements for each score domain | Scoring Framework, Data Validation Plan |
| AI-002 | Decompose OOD and uncertainty states | Model Architecture, Data Validation Plan, Chinese Overview |
| INT-001 | Add integration sensitivity panel | Data Validation Plan, Roadmap |
| INT-002 | Add `integration_intent` field | PRD, Model Architecture, Chinese Overview |
| INT-003 | Define quantitative protected-variable conservation metrics | Data Validation Plan, Chinese Overview |
| INT-004 | Add cell-state-aware integration metrics | Data Validation Plan |
| VAL-001 | Add locked validation protocol requirements | Data Validation Plan, Roadmap |
| VAL-002 | Add leave-publication, leave-source-cell-line, leave-sponsor/product-family, and leave-donor splits | Data Validation Plan |
| WS-001 | Add weak-label governance requirements | Model Architecture, Data Validation Plan, Chinese Overview |
| HR-001 | Add human review SOP requirements | Chinese Overview, Data Validation Plan |
| GOV-001 | Add change classes, drift checks, retraining triggers, and rollback criteria | Roadmap, Data Validation Plan, Chinese Overview |
| TOOL-001 to TOOL-003 | Define adapter-first strategy for annotation, gene scoring, and integration benchmarks | Model Architecture, Roadmap |

### Next: Implement After Data Inventory or Prototype Work

These items should become v2.1-v2.2 release gates after candidate datasets and a prototype scoring workflow exist.

| ID | Action | Release Window |
| --- | --- | --- |
| TOOL-004 | Evaluate foundation embeddings through ablation with fixed checkpoints and provenance | v2.1-v2.2 |
| TOOL-005 | Prototype product-as-bag MIL / Set Transformer only after product-level labels or expert rankings exist | v2.2 |
| BIOL-001-impl | Convert ProductDefinitionCard from schema to executable target-program registry | v2.1 |
| AI-001-impl | Calibrate score bands and abstention thresholds on frozen validation data | v2.1 |
| INT-001-impl | Run integration sensitivity panel on selected benchmark datasets | v2.1 |
| WS-001-impl | Build label-function registry and expert adjudication workflow | v2.1 |

### Later: Keep in Roadmap / Future Plan

These items require evidence or operational maturity that is not available at the current documentation stage.

| ID | Deferred Item | Reason |
| --- | --- | --- |
| BIOL-002-late | Functional assay, graft/fiber/PET, and exploratory clinical correlation tiers | Requires orthogonal downstream evidence |
| BIOL-003-late | GLP safety, biodistribution, tumorigenicity, WGS/WES/CNV acceptance criteria | Requires external QC datasets and formal safety evidence |
| TOOL-006 | Bayesian optimization / active learning for process optimization | Requires process variable action space, replicate policy, assay noise estimates, and feedback data |
| OUTCOME-001 | Outcome-calibrated readiness or efficacy-linked scoring | Requires future outcome-linked data; current system SHALL NOT claim therapeutic efficacy prediction |
| CLIN-001 | Clinical release or GMP decision support | Requires separate intended use, formal validation, quality system, and regulatory pathway |

## Patch Status for This Branch

This isolated v2 design branch has patched the immediate documentation-level issues into the main v2 documents. Items marked `Now` remain in the backlog as traceability records; implementation-specific work is still assigned to later roadmap phases.

| Area | Branch Status |
| --- | --- |
| Integrated score | Reframed as validation-eligible optional output; score matrix is the default public output. |
| ProductDefinitionCard | Added to PRD, Model Architecture, Scoring Framework context, and Chinese Overview. |
| External QC and rare-event language | Added to manifest, scoring, validation, and Chinese overview documents. |
| Product-window logic | Added as non-monotonic scoring guidance for pre-transplant products. |
| OOD and uncertainty | Decomposed into input, technical, biological, target-program, rare-state, and epistemic states. |
| Integration strategy | Added `integration_intent`, sensitivity panel, and protected-variable conservation requirements. |
| Weak-label and human review governance | Added to model and validation requirements; executable registry remains future implementation. |
| Public data inventory | Rewritten as a public-safe validation strata document without private server paths. |

## High-Priority Issues

| ID | Priority | Issue | Why It Matters | Proposed Direct Update |
| --- | --- | --- | --- | --- |
| BIOL-001 | P0 | Target program definition is still too generic | `PD_mDA_progenitor_v1` needs product-specific marker logic for floor-plate / ventral midbrain identity, A9-vs-A10 subtype evidence, rostral-caudal patterning, and stage-specific maturity | Add a `ProductDefinitionCard` section or template; update PRD, Scoring Framework, Model Architecture, and Chinese Overview |
| BIOL-002 | P0 | Transcriptomic potency-related proxy needs evidence tiers | A transcriptome-only signal may be biologically plausible but not correlated with graft function, fiber density, PET, or clinical outcomes | Add evidence tiers: transcriptomic plausibility, functional assay correlation, graft/fiber/PET correlation, exploratory clinical correlation |
| BIOL-003 | P0 | External safety and QC evidence is under-specified | scRNA-seq cannot assess karyotype, CNV, WGS/WES cancer variants, sterility, viability, biodistribution, tumorigenicity, GLP safety, or release assays | Add external QC fields to manifest and Evidence Confidence; keep these separate from transcriptomic risk flags |
| BIOL-004 | P0 | Rare-risk absence could be overcalled | scRNA-seq has limited sensitivity for rare residual pluripotent cells or rare high-risk contaminants | Require rare-event confidence language: "not detected at sampled depth" rather than "absent" unless supported by orthogonal assays |
| SCORE-001 | P0 | Total score remains too tempting | A single score can visually overpower missing potency, safety, or external QC evidence | Change required output from "total score with gates" to "integrated score if validation-eligible"; default to score matrix |
| VAL-001 | P0 | Validation needs a locked protocol layer | Paper-readiness requires frozen test sets, pre-specified hypotheses, threshold-locking, exclusion rules, blinded expert review, and analysis versioning | Add locked validation protocol requirements to Data Validation Plan and Roadmap |
| AI-001 | P0 | Score contract is not explicit enough | Each score needs calibration, uncertainty, abstention, score bands, and false-reassurance monitoring | Add a score contract table for each domain score and optional integrated score |
| AI-002 | P0 | OOD and uncertainty are too aggregated | Low gene overlap, missing metadata, technical shift, biological off-axis state, epistemic uncertainty, and weak-label noise require different actions | Add decomposed OOD/uncertainty taxonomy and action rules |

## Medium-Priority Issues

| ID | Priority | Issue | Why It Matters | Proposed Direct Update |
| --- | --- | --- | --- | --- |
| BIOL-005 | P1 | Off-target taxonomy should be discovery-oriented | Predefined classes may miss astrocyte-like, perivascular-like, mixed, damaged, or novel rare states | Add open-world / rare-state discovery mode and unknown-state review queue |
| BIOL-006 | P1 | Transplant-window scoring should be non-monotonic | More mature DA-lineage signal is not always better for a transplantable progenitor product | Define an optimal developmental window instead of monotonic maturity scoring |
| META-001 | P1 | Clinical product context metadata is incomplete | Cryopreservation, thaw stress, passage, dose, delivery route, HLA/immunosuppression, viability, and release assays affect interpretation | Extend manifest optional fields and evidence caveats |
| INT-001 | P1 | Integration strategy needs sensitivity panel | A single integrated embedding is not enough to prove robust interpretation | Add panel: unintegrated baseline, conservative RPCA/Harmony, scVI/scANVI/scArches, Symphony reference-only mapping |
| INT-002 | P1 | Integration intent is not explicit | Batch correction, atlas integration, reference mapping, and exploratory clustering remove different variation | Require an `integration_intent` field before integration |
| INT-003 | P1 | Protected-variable conservation needs quantitative metrics | Configuration alone does not prove product biology survived correction | Add product signature rank correlation, score shrinkage, timepoint trend preservation, lot variance preservation, and marker retention |
| INT-004 | P1 | Integration metrics should be cell-state-aware | Global batch mixing can reward overcorrection | Add within-cell-state batch mixing and rare-state preservation checks |
| VAL-002 | P1 | More leakage splits are needed | Model may learn sponsor, publication, source cell line, or lab-specific signatures | Add leave-publication, leave-source-cell-line, leave-sponsor/product-family, leave-donor splits |
| WS-001 | P1 | Weak supervision needs label governance | BRIDGE v1 as teacher can transmit rule bias unless label functions are audited | Add label-function registry, coverage/conflict stats, teacher-bias audit, expert adjudication SOP, inter-rater agreement, and frozen gold benchmark |
| HR-001 | P1 | Human review workflow needs SOP-level detail | Trigger rules exist, but override, adjudication, reviewer variability, and audit trail are not fully specified | Add reviewer roles, override handling, adjudication states, and human+AI vs AI-alone evaluation |
| GOV-001 | P1 | Lifecycle governance needs operating procedures | Data/model/schema/report changes need clear change classes, retraining triggers, rollback criteria, and calibration drift checks | Add PCCP-style change classes and monitoring triggers |

## Tooling and Engineering Risks

| ID | Priority | Issue | Recommended Direction |
| --- | --- | --- | --- |
| TOOL-001 | P1 | Avoid reinventing annotation and reference mapping | Use adapters around CellTypist, SingleR, scVI/scANVI/scArches, Symphony, Azimuth, or popV-style consensus where appropriate |
| TOOL-002 | P1 | Avoid hand-rolled gene-program scoring | Use or benchmark decoupler, UCell/pyUCell, AUCell, VISION, cNMF, or equivalent methods |
| TOOL-003 | P1 | Integration benchmark should reuse existing metrics | Use scIB / scib-metrics / Open Problems style metrics where applicable, with BRIDGE-specific protected-variable additions |
| TOOL-004 | P2 | Foundation model embeddings require strict contracts | Record checkpoint, tokenization, gene universe, preprocessing, output layer, species/domain, license, and ablation result |
| TOOL-005 | P2 | Product-as-bag modeling should reuse MIL/set-model libraries | Consider torchmil, DeepSets, Set Transformer, or equivalent, with strict donor/batch/protocol leakage controls |
| TOOL-006 | P2 | Optimization layer needs experimental action schema | Before using Ax/BoTorch, define action space, constraints, assay noise, replicate policy, batch acquisition, and wet-lab feedback schema |

## Suggested Immediate Patch Order

1. Patch `BRIDGE_v2_PRD.md` and `BRIDGE_v2_Chinese_Overview.md` to make integrated score optional and add external QC / ProductDefinitionCard requirements.
2. Patch `BRIDGE_v2_Scoring_Framework.md` to add score contracts, non-monotonic transplant-window logic, rare-event language, and potency evidence tiers.
3. Patch `BRIDGE_v2_Model_Architecture.md` to add ProductDefinitionCard schema, OOD decomposition, label governance, and adapter-based tool strategy.
4. Patch `BRIDGE_v2_Data_Validation_Plan.md` to add locked validation protocol, integration sensitivity panel, leakage splits, and score reliability thresholds.
5. Patch `BRIDGE_v2_Roadmap.md` to make these requirements release gates for paper-ready BRIDGE v2.

## Key Sources

- FDA Good Machine Learning Practice: https://www.fda.gov/medical-devices/software-medical-device-samd/good-machine-learning-practice-medical-device-development-guiding-principles
- FDA Potency Assurance for Cellular and Gene Therapy Products: https://www.fda.gov/regulatory-information/search-fda-guidance-documents/potency-assurance-cellular-and-gene-therapy-products
- FDA Potency Tests for Cellular and Gene Therapy Products: https://www.fda.gov/files/vaccines%2C%20blood%20%26%20biologics/published/Final-Guidance-for-Industry--Potency-Tests-for-Cellular-and-Gene-Therapy-Products.pdf
- TRIPOD+AI: https://www.bmj.com/content/385/bmj-2023-078378
- DECIDE-AI: https://www.nature.com/articles/s41591-022-01772-9
- scIB integration benchmark: https://www.nature.com/articles/s41592-021-01336-8
- scArches reference mapping: https://www.nature.com/articles/s41587-021-01001-7
- Symphony reference mapping: https://www.nature.com/articles/s41467-021-25957-x
- Single-cell graft composition in Parkinson disease model: https://doi.org/10.1038/s41467-020-16225-5
- iPSC-derived dopaminergic cells for Parkinson disease trial: https://www.nature.com/articles/s41586-025-08700-0
- Snorkel weak supervision: https://arxiv.org/abs/1711.10160
- Model Cards: https://arxiv.org/abs/1810.03993
- Datasheets for Datasets: https://arxiv.org/abs/1803.09010
