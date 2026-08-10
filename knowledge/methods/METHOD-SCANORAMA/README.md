# Scanorama

| Field | Value |
|---|---|
| Method ID | `METHOD-SCANORAMA` |
| Modules | P0-02, P0-07 |
| Scientific status | benchmark, shadow |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | EF-CS-INTEGRATION, joint_representation |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

cell-state evidence | joint analysis shadow

## Inputs

Per-batch expression matrices | multiple matrices with shared genes

## Outputs

Corrected embedding/expression | integrated embedding/expression

## Boundaries

Corrected expression cannot silently replace frozen expression views. | Corrected expression is not used for formal pseudobulk DE

## Environment

Python 单细胞核心环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [Efficient integration of heterogeneous single-cell transcriptomes using Scanorama - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC6551256/) (`SOURCE-05B464CCAEACDC60`)
- [GitHub - brianhie/scanorama: Panoramic stitching of single cell data · GitHub](https://github.com/brianhie/scanorama) (`SOURCE-1BDA5FBB77D80B5F`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
