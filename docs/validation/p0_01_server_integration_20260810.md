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

P0-01 package `0.1.1` now writes `qc_readiness_profile_v2.json` in addition to the unchanged v0.1 `ToolRun.result` and `qc_readiness_profile.json`. For `analysis_ready` and `count_ready`, the v2 profile binds the exact immutable input checksum, declared matrix location/semantics, observation count and observation-ID digest. The current candidate h5ad is not misrepresented as a selected subset because it contains candidate flags without removing rows. For `droplet_ready`, `selected_data_view` remains null until cell calling defines cells.

When `asset.metadata.biological_unit_lineage` supplies a complete versioned declaration, the run also writes `biological_unit_assignment.json` and `biological_unit_manifest.json`. Assignment bytes are checksummed into the manifest; manifest bytes are checksummed into the `DataViewBinding`; all additive files are checksummed in the existing artifact manifest. P0-01 fixes `lineage_state=declared` and leaves review-gate fields null. Missing or invalid lineage metadata yields an explicit v2 `unavailable` reason without blocking a legal v0.1 run or leaving partial lineage artifacts.

Validation at the final source state:

- P0-01 plus shared scientific-contract tests: `69 passed, 3 warnings`.
- Full source suite after merging current `main`: `1010 passed, 3 warnings`.
- The generated v2 profile, assignment and manifest payloads passed their packaged Draft 2020-12 JSON Schemas.
- Deterministic reruns matched checksums for the full artifact set, including declared lineage artifacts.
- Parameterized failure cases covered absent metadata, absent mapped columns, missing source/analysis/independence reference sources, source mismatch and an illegal capture independence group; all preserved the v0.1 result and emitted only v2 `unavailable` lineage.
- Input checksums were unchanged before and after successful lineage generation.

The three warnings are the pre-existing duplicate-gene fixture warning and two SciPy sparse-matrix deprecations. No catalog, shared runtime, shared contract, schema registry or exporter file changed.

This closeout is engineering contract evidence only. Caller declarations have not been confirmed against real manufacturing records; constant refs do not prove that every observation shares one source; and `declared` does not establish reviewed/frozen authority, biological independence, an estimand, product quality, potency, safety or release suitability.
