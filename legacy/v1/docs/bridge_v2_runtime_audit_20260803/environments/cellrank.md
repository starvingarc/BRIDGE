# Environment Card: cellrank

| 字段 | 内容 |
| --- | --- |
| Environment ID | `ENV-CELLRANK-v0.1` |
| Environment name | `cellrank` |
| 审计日期 | 2026-08-03 |
| 状态 | `existing_conditional` |
| Owner | `pending_assignment` |
| Interpreter | Python 3.10.18 |
| GPU requirement | 取决于底层 kernel/model；默认 CPU |
| Resource class | `batch_cpu` / `single_gpu` |
| Registered tool IDs | `CELLRANK` |
| Input artifact types | h5ad、time/state metadata、validated kernel inputs |
| Output artifact types | transition/fate tables、state model、MeasurementResult JSON |
| Update policy | kernel、root/terminal contract 或 package 版本变更时创建新版本 |

## Audited Stack

| Package | Version |
| --- | --- |
| cellrank | 2.0.7 |
| scvelo | 0.3.3 |
| anndata | 0.11.4 |
| scanpy | 1.11.2 |

## Purpose

使用 real-time、pseudotime、velocity 或其他经验证 kernel 生成 trajectory/fate evidence。P0 不依赖该环境发布核心产品分数。

## Input Contract

- 明确 kernel 来源、state/timepoint、sample/batch 和 root/terminal assumptions。
- 使用 velocity 时必须有适配的 spliced/unspliced 数据。
- 使用 real-time kernel 时必须保留真实时间和 biological replicate。

## Outputs

- transition matrix、macrostate、fate probability、driver candidates 与稳定性。
- kernel、root/terminal、sample/source holdout 和 sensitivity records。

## Boundaries

- trajectory/fate probability 是模型证据，不证明真实细胞谱系。
- 体外 D 不数值换算为 GW/PCW。
- 缺少时间、lineage 或 velocity 支持时只允许探索。
- SISBAR 直接 lineage evidence 与 CellRank inference 分层保存。

## Health Check

```bash
conda run -n cellrank python -c "import cellrank, scvelo, anndata; print(cellrank.__version__, scvelo.__version__, anndata.__version__)"
```

冻结前需使用真实多时间点 fixture 检查 sample-preserving transition、source holdout 和结果重复性。
