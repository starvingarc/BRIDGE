# DESeq2

| Field | Value |
|---|---|
| Method ID | `METHOD-DESEQ2` |
| Modules | P0-06, P0-07 |
| Scientific status | benchmark, shadow |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | EF-METHOD-PSEUDOBULK-NB, state_pseudobulk |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

process programs | state and program comparison

## Inputs

Integer pseudobulk counts + design | Raw pseudobulk counts and design matrix

## Outputs

Log2 fold changes, tests and adjusted p-values | log2FC, shrinkage-compatible results and FDR

## Boundaries

Complex repeated measures are limited | Raw integer counts only; same NB evidence family as edgeR for evidence counting

## Environment

R/Bioconductor 方法环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [GitHub - thelovelab/DESeq2: Differential expression of RNA-seq data using the Negative Binomial · GitHub](https://github.com/thelovelab/DESeq2) (`SOURCE-691DE6E6AD7691BA`)
- [Bioconductor - DESeq2](https://bioconductor.org/packages/release/bioc/html/DESeq2.html) (`SOURCE-784042283429707B`)
- [https://git.bioconductor.org/packages/DESeq2](https://git.bioconductor.org/packages/DESeq2) (`SOURCE-FD18FB3B17C7348C`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
