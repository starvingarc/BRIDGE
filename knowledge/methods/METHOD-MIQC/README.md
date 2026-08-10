# miQC

| Field | Value |
|---|---|
| Method ID | `METHOD-MIQC` |
| Modules | P0-01 |
| Scientific status | conditional |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | cell_qc_probabilistic |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

input audit and QC

## Inputs

count_ready | detected genes; mitochondrial fraction; sample grouping

## Outputs

low-quality probability 与边界敏感性

## Boundaries

模型不收敛、分布不适配或 snRNA 未验证

## Environment

R/Bioconductor 方法环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [Bioconductor - miQC](https://bioconductor.org/packages/release/bioc/html/miQC.html) (`SOURCE-4BDFBC65F86B0170`)
- [miQC: An adaptive probabilistic framework for quality control of single-cell RNA-sequencing data | PLOS Computational Biology](https://doi.org/10.1371/journal.pcbi.1009290) (`SOURCE-87591346EB6A9221`)
- [GitHub - greenelab/miQC: Flexible, probablistic metrics for quality control of scRNA-seq data · GitHub](https://github.com/greenelab/miQC) (`SOURCE-BF79B578EC72D5CE`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
