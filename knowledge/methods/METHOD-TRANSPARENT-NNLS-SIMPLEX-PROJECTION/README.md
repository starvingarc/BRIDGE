# Transparent NNLS/simplex projection

| Field | Value |
|---|---|
| Method ID | `METHOD-TRANSPARENT-NNLS-SIMPLEX-PROJECTION` |
| Modules | P0-02 |
| Scientific status | shortlisted |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | EF-CS-CONTINUOUS |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

cell-state evidence

## Inputs

held-out internal centroids/programs + query

## Outputs

non-negative weights, residual and reference distance

## Boundaries

Weights are not probabilities; retain reconstruction residual.

## Environment

Python 单细胞核心环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [nnls — SciPy v1.18.0 Manual](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.nnls.html) (`SOURCE-7C36532509F2E059`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
