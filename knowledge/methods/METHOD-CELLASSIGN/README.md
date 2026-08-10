# CellAssign

| Field | Value |
|---|---|
| Method ID | `METHOD-CELLASSIGN` |
| Modules | P0-02 |
| Scientific status | benchmark |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | EF-CS-MARKER-CLASSIFIER |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

cell-state evidence

## Inputs

raw counts + marker matrix + batch design

## Outputs

known-class posterior

## Boundaries

Requires a separate compatibility lock; posterior is not an OOD guarantee.

## Environment

工具专用隔离环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [Automated, probabilistic assignment of scRNA-seq to cell types • cellassign](https://irrationone.github.io/cellassign/) (`SOURCE-735E387AD20013E5`)
- [Probabilistic cell-type assignment of single-cell RNA-seq for tumor microenvironment profiling | Nature Methods](https://www.nature.com/articles/s41592-019-0529-1) (`SOURCE-E944C254C1D112FF`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
