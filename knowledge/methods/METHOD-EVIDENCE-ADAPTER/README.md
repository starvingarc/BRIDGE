# evidence adapter

| Field | Value |
|---|---|
| Method ID | `METHOD-EVIDENCE-ADAPTER` |
| Modules | P0-08 |
| Scientific status | conditional |
| Source status | `registered` |
| License status | `review_required` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | conformal_prediction, integration_sensitivity |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

evidence sufficiency

## Inputs

versioned scConform/conformal output | versioned scIB metric bundle

## Outputs

Model Robustness checks | integration sensitivity evidence

## Boundaries

交换性前提和验证范围必须记录 | 只适用于运行联合分析的任务；不把单个整合分数当稳定性

## Environment

Evidence 与报告治理环境；工具专用隔离环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [GitHub - YosefLab/scib-metrics: Accelerated, Python-only, single-cell integration benchmarking metrics · GitHub](https://github.com/yoseflab/scib-metrics) (`SOURCE-117D984F88B25939`)
- [Conformal inference for reliable single cell RNA-seq annotation - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12506889/) (`SOURCE-3B21FB4F52405CDF`)
- [Benchmarking atlas-level data integration in single-cell genomics | Nature Methods](https://www.nature.com/articles/s41592-021-01336-8) (`SOURCE-3FCB760E87E66418`)
- [GitHub - ccb-hms/scConform: Uncertainty quantification for cell type annotation using conformal inference · GitHub](https://github.com/ccb-hms/scConform) (`SOURCE-96E2387F9ACB60E1`)
- [API — scib-metrics](https://scib-metrics.readthedocs.io/en/stable/api.html) (`SOURCE-B9469DE829336BA6`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
