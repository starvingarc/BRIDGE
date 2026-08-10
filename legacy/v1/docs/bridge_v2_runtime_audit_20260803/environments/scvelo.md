# Environment Card: scvelo

| 字段 | 内容 |
| --- | --- |
| Environment ID | `ENV-SCVELO-v0.1` |
| Environment name | `scvelo` |
| 审计日期 | 2026-08-03 |
| 状态 | `existing_development_build` |
| Owner | `pending_assignment` |
| Interpreter | Python 3.9.19 |
| scVelo | 0.3.3.dev4+gd3e81d9 |
| GPU requirement | 可 CPU；大对象/动力学模型可评估 1 GPU |
| Resource class | `batch_cpu` / `single_gpu` |
| Registered tool IDs | `SCVELO`（exploratory/conditional） |
| Input artifact types | h5ad/loom with spliced and unspliced layers |
| Output artifact types | velocity/latent-time tables、h5ad、MeasurementResult JSON |
| Update policy | development build 不原地晋升；正式版使用新 Environment ID |

## Purpose

为具有 spliced/unspliced layers 且 chemistry、preprocessing 和动态假设可审计的数据提供 RNA velocity 探索或条件性证据。

## Input Contract

- raw or compatible spliced/unspliced counts。
- gene filtering、moments、sample/batch、timepoint 和 cell-state metadata。
- 明确 steady-state、stochastic 或 dynamical model 的选择依据。

## Boundaries

- 普通 h5ad、normalized-only matrix 或缺少 splicing layers 时拒绝运行。
- development build 不进入正式 BRIDGE release。
- velocity arrows、latent time 和 inferred direction 不等于 lineage tracing。
- 结果必须与 real timepoint、SISBAR 或其他独立证据比较。

## Health Check

```bash
conda run -n scvelo python -c "import scvelo, anndata, scanpy; print(scvelo.__version__, anndata.__version__, scanpy.__version__)"
```

## Freeze Requirements

- 新建 stable release environment，不以当前 development build 作为正式版本。
- 固定 loom/h5ad conversion、splicing layer schema 和 small velocity fixture。
- 对 key conclusions 运行 model/parameter sensitivity，并保持 `conditional` 状态。
