# P0-02 Server Integration Record

**Date:** 2026-08-11
**Tool:** `P0-02` version `0.3.0`
**Environment contract:** `ENV-P0-CORE-v0.1`

## Reference snapshot

Candidate snapshot `REF-PD-vMB-CELLSTATE-v0.2` was rebuilt from audited source assets. It contains separate scRNA and snRNA primary profiles, modality-specific L2 refinement profiles, one dependent combined-modality sensitivity profile, and planned regional context records.

| Profile | Included observations | Samples | Selected genes | Excluded |
|---|---:|---:|---:|---:|
| Chen vMB scRNA L1 | 61,455 | 6 | 2,018 | 0 |
| Chen vMB snRNA L1 | 85,465 | 6 | 2,032 | 2,002 unresolved |
| Chen RG/Nb scRNA L2 | 14,565 | 6 | 2,036 | 25 unresolved |
| Chen RG/Nb snRNA L2 | 505 | 5 | 2,042 | 0 |
| La Manno fetal VM scRNA L1 | 1,210 | 7 | 2,029 | 767 unmapped |
| Chen combined sensitivity | 146,920 | 12 | 2,028 | 2,002 unresolved |

Profile, vocabulary and marker artifacts reproduce the preceding candidate snapshot byte-for-byte. The new manifest adds the complete competitor denylist and remains free of source paths. Agent runtime rejects this candidate snapshot by default; it was enabled only for this science-team validation.

## Real-data runs

All inputs first had a checksum-bound `QCReadinessProfile`. Every P0-02 run preserved the input, emitted 16 checksummed artifacts and five registered visualizations, and kept `domain_score=null`, `score_state=shadow` and `open_set_state=not_assessed`.

| Logical asset | Role | Shape | Consensus supported | Source conflict | Wall time | Peak RSS |
|---|---|---:|---:|---:|---:|---:|
| GSE204796 pre-transplant time course | product development | 37,397 x 33,538 | 64.52% | 35.48% | 55 s | 6.1 GiB |
| GSE190729 cerebral organoid | developmental OOD | 17,636 x 33,538 | 10.63% | 89.37% | 25 s | 2.9 GiB |
| GSE221853 neural crest | lineage OOD | 29,857 x 24,297 | 47.97% | 52.03% | 49 s | 9.4 GiB |

For GSE204796, source-conflict fractions changed across the declared time course: D8 46.82%, D14 51.22%, D21 19.50%, D28 33.23% and D35 31.70%. This verifies time-dependent output, not an optimal harvest day.

The two OOD runs remain shadow candidate sets rather than final assignments. Their conflict fractions are diagnostic observations only; open-set calibration and an OOD decision threshold have not been frozen.

## Leakage and reproducibility checks

- A 337-cell GSE76381 iPS-mDA query declared as `LAMANNO-2016` excluded the La Manno fetal reference before computation. Only the Chen primary source remained, so consensus and source-conflict measurements returned `unavailable` rather than zero.
- L2 output obeyed the L1 Radial_Glia/Neuroblast parent set, and L1/L2 compositions retained separate denominators in all three main runs.
- Reference Evidence Families were de-duplicated; the Chen combined profile remained sensitivity-only.
- All output artifact hashes, reference checksums and input hashes validated after execution.
- Repeating the full GSE204796 request produced the same run ID and all 16 artifact hashes.
- The full repository suite collected and passed 68 tests in the server Python 3.12 scientific environment.

This historical record establishes an executable, traceable shadow baseline. It does not establish a frozen annotation method, calibrated OOD detector, formal domain score, product ranking, clinical efficacy, safety, potency or release decision. At the time of this run, independent rebuild validation of `ENV-P0-CORE-v0.1` was still pending. The later environment and engineering status is recorded in [Server reproducibility validation, 2026-08-12](server_reproducibility_20260812.md).
