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
