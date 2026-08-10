# CellTypist custom classifier

| Field | Value |
|---|---|
| Method ID | `METHOD-CELLTYPIST-CUSTOM-CLASSIFIER` |
| Modules | P0-02 |
| Scientific status | shortlisted |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | EF-CS-LINEAR-CLASSIFIER |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

cell-state evidence

## Inputs

internal labeled reference + normalized query | L1 then eligible L2 states

## Outputs

labels, decision scores and sigmoid matrix | labels, decision matrix and calibrated prediction set

## Boundaries

Do not use generic pretrained labels as truth. | No generic pretrained label truth

## Environment

Python 单细胞核心环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [GitHub - Teichlab/celltypist: A tool for semi-automatic cell type classification · GitHub](https://github.com/Teichlab/celltypist) (`SOURCE-883BB6875D4A88E3`)
- [CellTypist | automated cell type annotation for scRNA-seq datasets](https://www.celltypist.org/) (`SOURCE-DDE3AC775483E17E`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
