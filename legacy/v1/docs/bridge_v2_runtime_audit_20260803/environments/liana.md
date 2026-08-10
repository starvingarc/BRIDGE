# Environment Card: liana

| 字段 | 内容 |
| --- | --- |
| Environment ID | `ENV-LIANA-v0.1` |
| Environment name | `liana` |
| 审计日期 | 2026-08-03 |
| 状态 | `existing_shadow` |
| Owner | `pending_assignment` |
| Interpreter | Python 3.10.0 |
| GPU requirement | 无；默认 CPU |
| Resource class | `batch_cpu` |
| Registered tool IDs | `LIANA` |
| Input artifact types | h5ad、sample/state labels、frozen ligand-receptor resource |
| Output artifact types | edge parquet/TSV、consensus summary、MeasurementResult JSON |
| Update policy | 方法、resource 或底层 decoupler 变更时使用新 Environment ID |

## Audited Stack

| Package | Version |
| --- | --- |
| liana | 1.5.1 |
| anndata | 0.11.4 |
| scanpy | 1.11.2 |
| decoupler | 2.0.6 |

## Purpose

在每个 sample/lot 内推断 ligand-receptor communication potential，并进行跨样本的描述性或预注册统计比较。

## Input Contract

- normalized expression、明确的 sample/lot 与 sender/receiver state labels。
- 每个 state 的 minimum cell/pseudobulk coverage。
- frozen ligand-receptor resource 与 license-filtered snapshot。
- Protocol IR 中的外源培养因子，避免将培养基信号归因于细胞分泌。

## Outputs

- method-specific scores、consensus rank、expression proportion、resource provenance。
- sample-level edge table、stability、context mismatch 和 validation queue。

## Boundaries

- 输出名称为 `communication_potential`。
- ligand/receptor 共表达不证明真实通讯、空间邻接或因果作用。
- 多种方法共享同一 resource 时不重复计权。
- 当前只进入解释层和 shadow panel。

## Health Check

```bash
conda run -n liana python -c "import liana, anndata, scanpy; print(liana.__version__, anndata.__version__, scanpy.__version__)"
```

冻结前需完成多样本 fixture、resource snapshot、external factor node 和 missing-state abstention 测试。
