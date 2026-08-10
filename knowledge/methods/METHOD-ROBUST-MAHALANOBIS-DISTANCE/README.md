# Robust Mahalanobis distance

| Field | Value |
|---|---|
| Method ID | `METHOD-ROBUST-MAHALANOBIS-DISTANCE` |
| Modules | P0-05 |
| Scientific status | benchmark |
| Source status | `registered` |
| License status | `unresolved` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | reference_distance |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

unknown and OOD

## Inputs

Frozen feature space and class covariance

## Outputs

Global/class-conditional distance

## Boundaries

High-dimensional covariance needs shrinkage

## Environment

Python 单细胞核心环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [GitHub - scikit-learn/scikit-learn: scikit-learn: machine learning in Python · GitHub](https://github.com/scikit-learn/scikit-learn) (`SOURCE-8E773AA72402B28A`)
- [2.6. Covariance estimation — scikit-learn 1.9.0 documentation](https://scikit-learn.org/stable/modules/covariance.html) (`SOURCE-A42E12136D831320`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
