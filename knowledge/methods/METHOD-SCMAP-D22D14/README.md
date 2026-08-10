# scmap

| Field | Value |
|---|---|
| Method ID | `METHOD-SCMAP-D22D14` |
| Modules | P0-02, P0-03 |
| Scientific status | benchmark, conditional |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | EF-CS-SIMILARITY, reference_similarity |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

cell-state evidence | target identity

## Inputs

indexed reference + query with shared genes | query + reference centroids/cells

## Outputs

similarity + unassigned | similarity and unassigned status

## Boundaries

Thresholds must be recalibrated on BRIDGE holdouts. | low similarity -> unassigned

## Environment

R/Bioconductor 方法环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [GitHub - hemberg-lab/scmap: A tool for unsupervised projection of single cell RNA-seq data · GitHub](https://github.com/hemberg-lab/scmap) (`SOURCE-96D15DBBF0883283`)
- [Bioconductor - scmap](https://bioconductor.org/packages/scmap/) (`SOURCE-AE39867F33144D37`)
- [scmap: projection of single-cell RNA-seq data across data sets | Nature Methods](https://www.nature.com/articles/nmeth.4644) (`SOURCE-DC18F601A84A0A9B`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
