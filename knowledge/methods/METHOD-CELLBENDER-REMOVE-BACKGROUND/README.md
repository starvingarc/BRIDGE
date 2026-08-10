# CellBender remove-background

| Field | Value |
|---|---|
| Method ID | `METHOD-CELLBENDER-REMOVE-BACKGROUND` |
| Modules | P0-01 |
| Scientific status | conditional |
| Source status | `registered` |
| License status | `reported` |
| Version | `0.3.2` (`reported`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | ambient_rna_model |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

input audit and QC

## Inputs

droplet_ready | capture_id; raw droplet matrix; expected cells; chemistry

## Outputs

corrected counts、posterior、metrics、report 与敏感性视图

## Boundaries

缺 raw droplets、环境/GPU 不满足、已知问题未核对

## Environment

工具专用隔离环境

## Curation Notes

Version 0.3.2 is the documentation baseline; the known 0.3.1 incorrect-matrix issue must remain in version review.

## Official Sources

- [GitHub - broadinstitute/CellBender: CellBender is a software package for eliminating technical artifacts from high-throughput single-cell RNA sequencing (scRNA-seq) data. · GitHub](https://github.com/broadinstitute/CellBender) (`SOURCE-253A5D604B96C934`)
- [Unsupervised removal of systematic background noise from droplet-based single-cell experiments using CellBender | Nature Methods](https://doi.org/10.1038/s41592-023-01943-7) (`SOURCE-5DF43B30192FA6D8`)
- [Usage — CellBender 0.3.2 documentation](https://cellbender.readthedocs.io/en/latest/usage/index.html) (`SOURCE-E938F2B26E6E0751`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
