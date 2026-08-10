# limma-voom

| Field | Value |
|---|---|
| Method ID | `METHOD-LIMMA-VOOM` |
| Modules | P0-06, P0-07, P0-12 |
| Scientific status | benchmark, conditional |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | EF-METHOD-PSEUDOBULK-LM, state_pseudobulk |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

graft assessment | process programs | state and program comparison

## Inputs

Filtered raw pseudobulk counts + design | Pseudobulk counts and design matrix | sample-level counts/expression

## Outputs

Log-CPM effects and moderated statistics | effect sizes and FDR | logFC, precision-weighted statistic and FDR

## Boundaries

 | Mean-variance and low-count behavior require checks | Repeated measures require an explicit correlation or mixed-model design

## Environment

R/Bioconductor 方法环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [Bioconductor - limma](https://bioconductor.org/packages/release/bioc/html/limma.html) (`SOURCE-79B6FDF0CA09A4C4`)
- [https://git.bioconductor.org/packages/limma](https://git.bioconductor.org/packages/limma) (`SOURCE-E7BB7BBA8653422C`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
