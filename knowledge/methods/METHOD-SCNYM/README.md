# scNym

| Field | Value |
|---|---|
| Method ID | `METHOD-SCNYM` |
| Modules | P0-02 |
| Scientific status | benchmark |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | EF-CS-DEEP-CLASSIFIER |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

cell-state evidence

## Inputs

labeled reference + unlabeled query counts

## Outputs

cell labels and classifier outputs

## Boundaries

Query adaptation must not leak sealed evaluation labels.

## Environment

R/Bioconductor 方法环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [Identifying phenotype-associated subpopulations by integrating bulk and single-cell sequencing data | Nature Biotechnology](https://www.nature.com/articles/s41587-021-01091-3) (`SOURCE-6D025FA9A522E832`)
- [GitHub - calico/scnym: Semi-supervised adversarial neural networks for classification of single cell transcriptomics data · GitHub](https://github.com/calico/scnym) (`SOURCE-8D01DB00B7ED936C`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
