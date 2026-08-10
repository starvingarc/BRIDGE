# CellTypist custom model

| Field | Value |
|---|---|
| Method ID | `METHOD-CELLTYPIST-CUSTOM-MODEL` |
| Modules | P0-03 |
| Scientific status | shortlisted |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | regional_classifier, supervised_classifier |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

regional fidelity | target identity

## Inputs

log-normalized query | query expression

## Outputs

decision/probability + soft composition | regional probability/prediction

## Boundaries

closed-set forcing -> abstain via gate | generic pretrained model forbidden

## Environment

Python 单细胞核心环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [GitHub - Teichlab/celltypist: A tool for semi-automatic cell type classification · GitHub](https://github.com/Teichlab/celltypist) (`SOURCE-883BB6875D4A88E3`)
- [Welcome to CellTypist’s documentation! — celltypist 1.7.1 documentation](https://celltypist.readthedocs.io/) (`SOURCE-ADE98F747EEEDD28`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
