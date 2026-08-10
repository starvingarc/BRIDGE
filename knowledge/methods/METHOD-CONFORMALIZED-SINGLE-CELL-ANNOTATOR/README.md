# Conformalized single-cell annotator

| Field | Value |
|---|---|
| Method ID | `METHOD-CONFORMALIZED-SINGLE-CELL-ANNOTATOR` |
| Modules | P0-02, P0-05 |
| Scientific status | benchmark, deferred |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | EF-CS-CONFORMAL, conformal_prediction |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

cell-state evidence | unknown and OOD

## Inputs

Frozen nonconformity score and calibration split | reference/query + base classifier + calibration

## Outputs

Prediction set, coverage and abstention | sets, p-values and OOD indicators

## Boundaries

Exchangeability assumptions require source-aware testing | No formal use until license and reproducibility are resolved.

## Environment

Python 单细胞核心环境；工具专用隔离环境 | 工具专用隔离环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [Conformal inference for reliable single cell RNA-seq annotation - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12506889/) (`SOURCE-3B21FB4F52405CDF`)
- [GitHub - digital-medicine-research-group-UNAV/conformalized_single_cell_annotator: Single cell annotator · GitHub](https://github.com/digital-medicine-research-group-UNAV/conformalized_single_cell_annotator) (`SOURCE-9D5FAC47951F09B3`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
