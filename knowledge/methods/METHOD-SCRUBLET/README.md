# Scrublet

| Field | Value |
|---|---|
| Method ID | `METHOD-SCRUBLET` |
| Modules | P0-01 |
| Scientific status | conditional |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | transcriptome_doublet |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

input audit and QC

## Inputs

count_ready | confirmed capture_id; raw UMI counts; expected rate provenance

## Outputs

per-capture score/class 与方法分歧

## Boundaries

多 capture 混跑、counts 不合格、阈值不稳定

## Environment

Python 单细胞核心环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [GitHub - swolock/scrublet: Detect doublets in single-cell RNA-seq data · GitHub](https://github.com/swolock/scrublet) (`SOURCE-313A6EA2863FB1A5`)
- [Redirecting](https://doi.org/10.1016/j.cels.2018.11.005) (`SOURCE-3A759A54DF40BD26`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
