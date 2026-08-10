# Environment Card: decoupler

| 字段 | 内容 |
| --- | --- |
| Environment ID | `ENV-DECOUPLER-v0.1` |
| Environment name | `decoupler` |
| 审计日期 | 2026-08-03 |
| 状态 | `existing_shadow` |
| Owner | `pending_assignment` |
| Interpreter | Python 3.12.9 |
| GPU requirement | 无；默认 CPU |
| Resource class | `interactive_cpu` / `batch_cpu` |
| Registered tool IDs | `DECOUPLER-TF`, `DECOUPLER-PROGENY` |
| Input artifact types | pseudobulk/expression matrix、signed prior network snapshot |
| Output artifact types | activity parquet/TSV、coverage table、MeasurementResult JSON |
| Update policy | 工具方法或 prior snapshot 变更时创建新版本并重跑 fixture |

## Audited Stack

| Package | Version |
| --- | --- |
| decoupler | 2.0.6 |
| anndata | 0.11.3 |
| scanpy | 1.10.4 |

## Purpose

在 sample/lot x cell-state pseudobulk 上运行 signed TF-target activity、PROGENy pathway footprint 和其他经审核 prior network。

## Input Contract

- sample/state pseudobulk 或明确支持的 expression matrix。
- network columns、edge direction/weight、source version 和 evidence family。
- minimum weighted edge/gene coverage 与 matched null。

## Outputs

- regulator/pathway estimate、statistic、coverage、method、sample/state ID。
- prior snapshot、shared evidence family、reference/source holdout stability。

## Boundaries

- inferred activity 不等于 TF binding、protein activation 或 pathway flux。
- CollecTRI/DoRothEA/PROGENy 各自保留来源许可和 context。
- 未通过 held-out direction 与 robustness validation 时保持 shadow。

## Health Check

```bash
conda run -n decoupler python -c "import decoupler, anndata, scanpy; print(decoupler.__version__, anndata.__version__, scanpy.__version__)"
```

正式冻结需固定 decoupler 版本、method、network snapshot 和 deterministic pseudobulk fixture。
