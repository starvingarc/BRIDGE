# BRIDGE v2 Test Data Inventory

## Document Status

| Item | Value |
| --- | --- |
| Snapshot date | 2026-06-16 |
| Scope | Public-safe validation inventory template and current dataset strata |
| Intended use | BRIDGE v2 development planning, validation design, and manuscript-method preparation |
| Boundary | This document does not expose private server paths, raw unpublished matrices, or controlled-access assets. The operational inventory is maintained privately outside the public repository. |

## Purpose

This inventory describes the dataset classes BRIDGE v2 needs for product-level validation. It is intentionally public-safe: it records accessions, biological roles, conversion states, and intended validation use without local storage paths.

The inventory answers three questions:

1. Which data classes are needed to test a pre-transplant PD cell-product evaluation system?
2. Which public datasets already provide product-like, time-course, BrainSTEM, or negative-control evidence?
3. Which datasets still need conversion, metadata curation, or validation before they can become benchmark assets?

## Dataset Status Vocabulary

| Status | Meaning |
| --- | --- |
| ready_h5ad_private | Converted h5ad exists in the private validation workspace and has passed basic read/QC checks. |
| downloaded_private | Source files have been downloaded privately, but conversion or metadata curation is not complete. |
| manifest_only | Source has been identified, but large raw files or controlled assets are not downloaded into the working set. |
| candidate_to_add | Dataset appears relevant but needs source verification, download, and conversion. |
| public_derived_only | Public release should contain derived metrics or manifests only, not raw private data. |

## Core Validation Strata

| Stratum | Purpose | Example Datasets | Current Status |
| --- | --- | --- | --- |
| Product-like PD/mDA differentiation | Positive or near-positive anchors for mDA progenitor-oriented products. | SphereDiff / Chen CSC 2025, MacroDiff, MSK-DA01, GSE204796, GSE227071, GSE76381, E-MTAB-14729 | Mixed: internal/published protocols and several public h5ad conversions are available privately; additional metadata curation continues. |
| BrainSTEM-style mDA query/reference datasets | Cross-study mapping, two-step reference robustness, and fetal midbrain context. | BrainSTEM query datasets such as Fernandes, Fiorenzano, Jerber, Tiklova, Toh/in-house style records | Query and reference-mini assets are being used privately; full references should remain manifest-only unless required. |
| Time-course differentiation protocols | Test collection-window and non-monotonic developmental-window logic. | Multi-day mDA protocols such as D16/D25/D40, D0/D12/D17/D35, D16/D28/D62-like series | Candidate time-course assets are available privately; timepoint labels require careful publication-level curation. |
| Single-timepoint final products | Test realistic pre-transplant product submissions with limited temporal evidence. | Day-before-transplant or final differentiation samples from PD/mDA protocols | Supported by the v2 input contract; evidence confidence should reflect missing trajectory data. |
| Multi-batch or multi-lot products | Test process robustness, outlier-lot detection, and protected-variable handling. | Protocols with multiple product lots, source lines, donors, or manufacturing batches | Needs stronger manifest curation before model training. |
| Non-midbrain neural controls | Ensure cortical, whole-brain, motor-neuron, spinal, or other neural products do not receive false positive PD/mDA scores. | Cerebral/cortical organoid datasets, motor-neuron differentiation, spinal cord neural datasets, whole-brain organoids | Several public controls are converted privately; more can be added as negative-control coverage expands. |
| Non-neural or peripheral controls | Test hard off-target and risk-control behavior. | Mesenchymal stromal cells, neural crest/peripheral lineage, non-neural contamination-like datasets | Several public controls are converted privately; rare-event sensitivity remains a validation question. |
| Future outcome-linked evidence | v1.5+ calibration against post-transplant and functional readouts. | Graft snRNA-seq, electrophysiology, behavior, imaging, fiber-density, PET, or survival evidence | Reserved for later calibration; not part of current clinical efficacy claims. |

## Minimum Dataset Card Fields

Every dataset entering BRIDGE v2 validation should have a dataset card with:

- dataset_id
- accession or source record
- publication or laboratory source
- assay type and species
- cell source and differentiation scheme summary
- product-like, control, reference, or outcome-linked role
- timepoint or stage labels as described by the source publication
- whether the sample represents a pre-transplant product
- product lot, batch, donor, source-line, treatment, and technical-batch metadata when available
- raw counts and normalized layer availability
- gene identifier type and gene-overlap notes
- conversion status and QC status
- intended validation use
- caveats, exclusion reasons, and missing external QC fields

## MVP Validation Set

The first BRIDGE v2 validation pass should use a balanced, not exhaustive, set:

1. A fast smoke-test set with one small product-like sample and two clear negative controls.
2. At least one single-timepoint pre-transplant PD/mDA product-like dataset.
3. At least one multi-timepoint mDA differentiation protocol.
4. At least one BrainSTEM-style mapping/reference robustness dataset.
5. At least two non-midbrain neural controls.
6. At least one peripheral or non-neural off-target control.
7. A small subset of internal/published strong protocols used only through private, path-free manifests and derived metrics.

This MVP is intended to test input compatibility, target-program evidence, off-target specificity, rare-state warnings, evidence confidence, integration boundaries, and v1-v2 disagreement review.

## Public Benchmark Policy

Raw private data, private storage paths, and unpublished matrices should not be committed to the public repository. Public benchmark artifacts should use one of the following forms:

| Artifact Type | Public-Safe Content |
| --- | --- |
| dataset card | Accession, source, biological role, assay, timepoint summary, caveats, and license notes. |
| derived metric table | Product-level features, normalized scores, uncertainty, and warning states with no cell-level private matrix. |
| synthetic or demo h5ad | Explicitly generated demonstration data with no private raw-cell leakage. |
| validation summary | Aggregate results, split definitions, score distributions, and failure-mode descriptions. |
| manifest template | Required metadata fields and validation roles without local paths. |

## Known Caveats

- Publication timepoint labels must be curated from source methods before comparing transplant-window behavior.
- Public dataset annotations are heterogeneous and should be treated as evidence, not ground truth.
- Existing v1 outputs are useful baselines and weak labels; they are not final v2 training labels.
- Single-cell transcriptomics alone cannot validate sterility, karyotype, genomic stability, biodistribution, tumorigenicity, long-term safety, or clinical efficacy.
- Rare-risk absence should be reported as `not detected at sampled depth` unless orthogonal evidence supports stronger language.
