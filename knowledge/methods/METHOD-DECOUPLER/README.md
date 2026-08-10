# decoupler

| Field | Value |
|---|---|
| Method ID | `METHOD-DECOUPLER` |
| Modules | P0-02, P0-03, P0-06 |
| Scientific status | candidate, shortlisted |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | EF-CS-MARKER, EF-METHOD-DECOUPLER, marker_program, regional_program |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

cell-state evidence | process programs | regional fidelity | target identity

## Inputs

AnnData/matrix + gene sets or weighted networks | expression + weighted programs | expression matrix + signed gene-set/network | normalized expression

## Outputs

Backend-specific activity/enrichment matrix | activity estimate | activity estimates | method-specific activity scores

## Boundaries

Overlapping networks remain one evidence family. | decoupler is a framework, not one estimand; do not merge backend scores silently | prior mismatch -> unavailable | prior not applicable -> unavailable

## Environment

Python 单细胞核心环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [decoupler - Ensemble of methods to infer enrichment scores — decoupler](https://decoupler.readthedocs.io/en/stable/) (`SOURCE-04A40A3EA813DFC3`)
- [decoupler - Ensemble of methods to infer enrichment scores — decoupler](https://decoupler.readthedocs.io/) (`SOURCE-12DE29B346731E30`)
- [GitHub - scverse/decoupler: Python package to perform enrichment analysis from omics data. · GitHub](https://github.com/scverse/decoupler) (`SOURCE-881745EC28A79E0D`)
- [decoupleR: ensemble of computational methods to infer biological activities from omics data](https://doi.org/10.1093/bioadv/vbac016) (`SOURCE-A310627711269361`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
