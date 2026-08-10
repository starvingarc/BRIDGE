# SoupX

| Field | Value |
|---|---|
| Method ID | `METHOD-SOUPX` |
| Modules | P0-01 |
| Scientific status | candidate |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | ambient_rna_model |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

input audit and QC

## Inputs

droplet_ready | raw + filtered droplets; clusters/context; capture_id

## Outputs

contamination estimate 与替代 corrected sensitivity view

## Boundaries

缺 empty droplets、cluster/context 或 assay 不适用

## Environment

R/Bioconductor 方法环境

## Curation Notes

The license was corrected from the older registry value using the official repository.

## Official Sources

- [SoupX removes ambient RNA contamination from droplet-based single-cell RNA sequencing data](https://doi.org/10.1093/gigascience/giaa151) (`SOURCE-60C12579FBBA3C8F`)
- [GitHub - constantAmateur/SoupX: R package to quantify and remove cell free mRNAs from droplet based scRNA-seq data · GitHub](https://github.com/constantAmateur/SoupX) (`SOURCE-8DCDA813C557E2CC`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
