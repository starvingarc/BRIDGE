# CopyKAT

| Field | Value |
|---|---|
| Method ID | `METHOD-COPYKAT` |
| Modules | P0-06 |
| Scientific status | deferred |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | `unassigned` |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

CNV shadow

## Inputs

Raw UMI matrix; preferably per sample; optional known normal cells

## Outputs

Relative CNV matrix and aneuploid/diploid/undefined labels

## Boundaries

Cancer-oriented assumptions; batch sensitivity; expression-derived label is not genomic stability evidence

## Environment

R/Bioconductor 方法环境；工具专用隔离环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [GitHub - navinlabcode/copykat · GitHub](https://github.com/navinlabcode/copykat) (`SOURCE-51CA1C1AE8164E06`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
