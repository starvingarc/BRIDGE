# Environment Card: pytorch

| 字段 | 内容 |
| --- | --- |
| Environment ID | `ENV-PYTORCH-v0.1` |
| Environment name | `pytorch` |
| 审计日期 | 2026-08-03 |
| 状态 | `existing_needs_freeze` |
| Owner | `pending_assignment`；正式冻结前指定维护人 |
| Interpreter | Python 3.12.12 |
| GPU | 可见 2 张 GPU；PyTorch CUDA smoke test 通过 |
| Resource class | `interactive_cpu` / `batch_cpu` / `single_gpu` |
| Registered tool IDs | `ANNDATA-IO`, `SCANPY-QC`, `SCANPY-PREPROCESS`, `SCRUBLET`, `SCANVI-MAPPER`, BRIDGE core services |
| Input artifact types | ProductCase JSON/YAML、h5ad/zarr、frozen model/reference |
| Output artifact types | h5ad/zarr、parquet/TSV、MeasurementResult JSON、report artifacts |
| Update policy | 新依赖快照使用新 Environment ID，不在 v0.1 中静默升级 |

## Purpose

BRIDGE P0 默认环境：ProductCase validation、AnnData/Scanpy、reference mapping、pseudobulk、domain assessment、报告和软件测试。

## Audited Stack

| Package | Version |
| --- | --- |
| anndata | 0.12.6 |
| scanpy | 1.11.5 |
| scrublet | 0.2.3 |
| scvi-tools | 1.4.0.post1 |
| torch | 2.9.1+cu128 |
| decoupler | 2.1.4 |
| cellrank | 2.1.0 |
| scvelo | 0.3.3 |
| SpatialData | 0.5.0 |
| Squidpy | 1.6.6 |
| cell2location | 0.1.5 |

PyTorch 报告 CUDA runtime 12.8，服务器 driver 报告 CUDA 12.2，但当前 `torch.cuda.is_available()` 为 true 且识别 2 张 GPU。正式冻结前仍需运行实际 scVI fixture，不能只依据可见性判断兼容。

## Registered Tool Scope

- `ANNDATA-IO`、`SCANPY-QC`、`SCANPY-PREPROCESS`、`SCRUBLET`。
- BRIDGE schema、pseudobulk、OOD、composition、robustness、evidence 和 report services。
- `SCANVI-MAPPER` 与小型/中型 query mapping。
- 环境内空间和轨迹包只作兼容储备；正式空间/轨迹任务优先使用专用环境。

## Known Risks

- 依赖范围很宽，单包升级可能改变 AnnData serialization、Torch/CUDA 或 scverse 行为。
- 环境中存在多个专业包，不代表对应 BRIDGE Tool Card 已验证。
- CellBender 未安装；不得把 Scrublet 或 Scanpy QC 当作 ambient removal。
- 当前远端代码 `71 passed, 3 warnings` 仅是软件回归，不是科学验证。

## Health Check

```bash
conda run -n pytorch python -c "import anndata, scanpy, scvi, torch; print(anndata.__version__, scanpy.__version__, scvi.__version__, torch.__version__, torch.cuda.is_available())"
conda run -n pytorch python -m pytest -q
```

## Freeze Requirements

- 导出 explicit package lock 和 pip/conda provenance。
- 运行 small h5ad、sparse matrix、scANVI query 与 report fixture。
- 保存 Torch/CUDA/GPU smoke output。
- 新版本使用新的 Environment ID，不原地覆盖 v0.1。
