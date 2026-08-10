# AUCell

| Field | Value |
|---|---|
| Method ID | `METHOD-AUCELL-65EAB4` |
| Modules | P0-02, P0-03 |
| Scientific status | catalog_only, conditional |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | EF-CS-MARKER, marker_program |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

cell-state evidence | target identity

## Inputs

expression rankings + internal gene sets | ranked expression

## Outputs

AUC activity per cell/program | AUC enrichment

## Boundaries

Do not count as orthogonal evidence to UCell with identical programs. | dropout/coverage failure

## Environment

R/Bioconductor 方法环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [SCENIC: single-cell regulatory network inference and clustering | Nature Methods](https://doi.org/10.1038/nmeth.4463) (`SOURCE-77821AB119E6D209`)
- [Bioconductor - AUCell](https://bioconductor.org/packages/AUCell/) (`SOURCE-ABD9CAE39371E6FC`)
- [GitHub - aertslab/AUCell: AUCell: score single cells with gene regulatory networks · GitHub](https://github.com/aertslab/AUCell) (`SOURCE-F3EE836B5F3D8DDC`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
