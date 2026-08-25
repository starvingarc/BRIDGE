# P0-01 Server Integration Record

**Date:** 2026-08-10

**Tool:** `P0-01` version `0.1.0`
**Environment contract:** `ENV-P0-CORE-v0.1`

Two public logical assets were exercised read-only with declared `layers/counts`, `count_ready` semantics and assay-specific candidate MeasurementSpecs.

| Logical asset | Assay | Shape | Observation contract | Gene-set coverage | Candidate view | Artifacts | Input hash |
|---|---|---:|---|---|---|---:|---|
| GSE76381 La Manno iPS-mDA product subset | scRNA-seq | 337 x 14,726 | `n_cells`; `QC-feature-set-scRNA-human-symbol-v0.1` | 0 mitochondrial; 125 ribosomal genes | `unavailable`: required mitochondrial set absent | 8 | unchanged |
| GSE200610 graft nucleus engineering subset | snRNA-seq | 114 x 53,008 | `n_nuclei`; `QC-feature-set-snRNA-human-symbol-v0.1` | 26 mitochondrial; 200 ribosomal genes | `candidate`: 114 nuclei | 9 | unchanged |

Both runs returned seven raw measurements, two registered visualizations, `score_state=unavailable` and `domain_score=null`. Visualization denominators were respectively `declared cells` and `declared nuclei`. The 114 nuclei are a derived engineering subset of the Storm paper cohort of 14,414 nuclei from 12 animals; 114 is neither study scale nor a biological benchmark denominator. A subset manifest and checksum remain required before reuse. The scRNA run also verifies that absent gene-set coverage is represented as unavailable evidence rather than a zero fraction or a passed filter. The record verifies input reading, assay-specific MeasurementSpec and feature policies, raw metric generation, immutable inputs and artifact checksums for these two objects.

This is an engineering integration check, not a biological benchmark, reference validation or product-quality conclusion. At the time of this run, independent rebuild validation of the generic Conda contract was still pending. The later environment and engineering status is recorded in [Server reproducibility validation, 2026-08-12](server_reproducibility_20260812.md).

## Additive V2 lineage output closeout — 2026-08-25

P0-01 package `0.1.2` writes `qc_readiness_profile_v2.json` in addition to the unchanged v0.1 `ToolRun.result` and `qc_readiness_profile.json`. For `analysis_ready` and `count_ready`, the v2 profile binds the exact immutable input checksum, declared matrix location/semantics, observation count and observation-ID digest. The current candidate h5ad is not misrepresented as a selected subset because it contains candidate flags without removing rows. For `droplet_ready`, `selected_data_view` remains null until cell calling defines cells.

When `asset.metadata.biological_unit_lineage` supplies a complete versioned declaration, including an explicit capture mapping for `count_ready`, the run also writes `biological_unit_assignment.json` and `biological_unit_manifest.json`. A preparation/analysis unit may span multiple captures only under one coherent independence contract, while capture pooling across biological sources remains unavailable. For `count_ready`, typed capture refs must define the same bidirectional observation partition as the row-complete caller-declared capture IDs actually used by QC/Scrublet; labels may differ, but a split, merge or unavailable QC partition leaves only v2 lineage unavailable. Assignment bytes are checksummed into the manifest; manifest bytes are checksummed into the `DataViewBinding`; all additive files are checksummed in the existing artifact manifest. The versioned `structured_output_index.json` makes the generated v2 objects discoverable without changing v0.1 `ArtifactManifest` or `ToolRun`. P0-01 fixes `lineage_state=declared` and leaves review-gate fields null. Missing or invalid lineage metadata yields an explicit v2 `unavailable` reason without blocking a legal v0.1 run or leaving partial lineage artifacts.

Package `0.1.2` adds adversarial coverage for null/blank/sentinel capture values, multi-capture typed bindings, typed-versus-QC capture split/merge refusal, pooled-source refusal, zero-count fraction semantics, mixed-feature 10x MTX inputs, canonical directory digests, immutable snapshot reads, final input rechecks, staging cleanup, deterministic bundle reuse and mismatched-bundle refusal.

Exact source SHA, wheel identities, validation logs and checksummed server-evidence manifests are recorded in the PR and private server evidence store. This tracked record deliberately does not prewrite or self-embed a wheel digest.

This closeout is engineering contract evidence only. Caller declarations have not been confirmed against real manufacturing records; constant refs do not prove that every observation shares one source; and `declared` does not establish reviewed/frozen authority, biological independence, an estimand, product quality, potency, safety or release suitability.
