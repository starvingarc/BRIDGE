# scConform

| Field | Value |
|---|---|
| Method ID | `METHOD-SCCONFORM` |
| Modules | P0-02, P0-05 |
| Scientific status | benchmark, shortlisted |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | EF-CS-CONFORMAL, conformal_prediction |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

cell-state evidence | unknown and OOD

## Inputs

Reference, labels and ontology-compatible input | base-classifier scores + independent calibration + optional hierarchy

## Outputs

Calibrated annotation and rejection evidence | prediction sets and coverage diagnostics

## Boundaries

Calibration split must be source-independent and frozen. | Requires isolated current Bioconductor stack

## Environment

工具专用隔离环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [Bioconductor - scConform](https://bioconductor.org/packages/scConform/) (`SOURCE-C716978CEA210234`)
- [[2410.23786] Conformal inference for cell type annotation with graph-structured constraints](https://arxiv.org/abs/2410.23786) (`SOURCE-E16C46604A21CC4D`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
