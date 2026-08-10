# UCell

| Field | Value |
|---|---|
| Method ID | `METHOD-UCELL-7F85E7` |
| Modules | P0-02, P0-03 |
| Scientific status | benchmark, shortlisted |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | EF-CS-MARKER, marker_program, regional_program |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

cell-state evidence | regional fidelity | target identity

## Inputs

expression matrix + internal gene sets | ranked expression

## Outputs

per-cell enrichment | per-cell program score | per-cell signature scores

## Boundaries

Same marker evidence family as AUCell/decoupler when gene sets overlap. | coverage failure | low gene coverage -> unavailable

## Environment

R/Bioconductor 方法环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [Bioconductor - UCell](https://bioconductor.org/packages/UCell/) (`SOURCE-598043E92403096B`)
- [GitHub - carmonalab/UCell: Gene set scoring for single-cell data · GitHub](https://github.com/carmonalab/UCell) (`SOURCE-8F82BF28D373D537`)
- [UCell: Robust and scalable single-cell gene signature scoring](https://doi.org/10.1016/j.csbj.2021.06.043) (`SOURCE-ABC0906A229AA505`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
