# Environment Card: celltypist

| 字段 | 内容 |
| --- | --- |
| Environment ID | `ENV-CELLTYPIST-v0.1` |
| Environment name | `celltypist` |
| 审计日期 | 2026-08-03 |
| 状态 | `existing_candidate` |
| Owner | `pending_assignment` |
| Interpreter | Python 3.12.12 |
| GPU requirement | 无；默认 CPU |
| Resource class | `interactive_cpu` / `batch_cpu` |
| Registered tool IDs | `CELLTYPIST`（candidate） |
| Input artifact types | normalized h5ad/matrix、frozen source-aware model |
| Output artifact types | prediction/uncertainty parquet、MeasurementResult JSON |
| Update policy | model、label ontology、calibration 或 package 任一变更即生成新版本 |

## Audited Stack

| Package | Version |
| --- | --- |
| celltypist | 1.7.1 |
| scanpy | 1.11.5 |
| anndata | 0.12.6 |

## Purpose

提供一个监督式 cell-state evidence channel。BRIDGE 需要使用自建、版本化、source-aware 的 PD/development model；通用 immune 或 tissue model 不作为 PD 产品真值。

## Input Contract

- 与训练模型一致的 normalization、gene identifiers 和 feature overlap。
- frozen model、training sources、labels、ontology crosswalk 和 calibration set。
- query sample、assay、specimen 与 sampling context。

## Outputs

- predicted label、decision/probability evidence、margin、gene coverage 和 OOD diagnostics。
- model ID、training source family、calibration version 和 conflicts。

## Boundaries

- 模型标签不等于真实 cell identity。
- training/reference source 与 query 重叠时不作为独立 validation。
- 低 confidence、model disagreement 或 marker conflict 必须保留 unknown。

## Health Check

```bash
conda run -n celltypist python -c "import celltypist, scanpy, anndata; print(celltypist.__version__, scanpy.__version__, anndata.__version__)"
```

正式采用前需训练 source-aware model，并完成 leave-source-out、calibration、OOD 与 rare-state tests。
