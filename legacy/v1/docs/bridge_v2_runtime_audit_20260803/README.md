# BRIDGE Runtime 与 Environment Cards

## 总览

| Environment ID | 当前环境名 | 解释器 | 主要用途 | 审计状态 | Card |
| --- | --- | --- | --- | --- | --- |
| `ENV-PYTORCH-v0.1` | `pytorch` | Python 3.12.12 | P0 主运行、Scanpy、scVI、报告、部分空间依赖 | `existing_needs_freeze` | [pytorch](environments/pytorch.md) |
| `ENV-SPATIAL-v0.1` | `spatial` | Python 3.10.14 | SpatialData、Squidpy、cell2location | `existing_needs_fixture_validation` | [spatial](environments/spatial.md) |
| `ENV-PYSCENIC-v0.1` | `pyscenic_stable_20260601` | Python 3.10.20 | pySCENIC 0.12.1 | `existing_stable_candidate` | [pyscenic_stable](environments/pyscenic_stable.md) |
| `ENV-LIANA-v0.1` | `liana` | Python 3.10.0 | communication potential | `existing_shadow` | [liana](environments/liana.md) |
| `ENV-DECOUPLER-v0.1` | `decoupler` | Python 3.12.9 | TF/pathway activity | `existing_shadow` | [decoupler](environments/decoupler.md) |
| `ENV-CELLRANK-v0.1` | `cellrank` | Python 3.10.18 | trajectory/fate evidence | `existing_conditional` | [cellrank](environments/cellrank.md) |
| `ENV-SCVELO-v0.1` | `scvelo` | Python 3.9.19 | RNA velocity | `existing_development_build` | [scvelo](environments/scvelo.md) |
| `ENV-R43-v0.1` | `r4.3` | R 4.3.3 | Seurat/Bioconductor 与 R-only candidates | `existing_partial` | [r4.3](environments/r4.3.md) |
| `ENV-CELLTYPIST-v0.1` | `celltypist` | Python 3.12.12 | supervised annotation channel | `existing_candidate` | [celltypist](environments/celltypist.md) |
| `ENV-CELLBENDER-v0.1` | proposed | 待冻结 | raw droplet background correction | `not_installed` | [cellbender](environments/cellbender.md) |
| `ENV-AGENT-v0.1` | proposed | 待确定 | Agent orchestration、retrieval、audit API | `design_pending_with_agent_team` | [agent-runtime](environments/agent-runtime.md) |

## Environment Card 必需字段

```text
environment_id / environment_name / state / audit_date
purpose / owner / interpreter
key_packages / GPU_requirement / resource_class
registered_tool_ids
input_artifact_types / output_artifact_types
compatibility_constraints / known_risks
health_check / freeze_requirements / update_policy
```

## 跨环境 Artifact 合同

不同环境不得通过 Python pickle 或进程内对象共享正式结果。允许的跨环境格式：

- h5ad/zarr：表达矩阵与结构化 annotation，必须记录 AnnData/Zarr 版本。
- parquet/CSV/TSV：表格；必须附 schema 与 dtype manifest。
- JSON/YAML：Card、plan、run record、MeasurementResult 与 report manifest。
- loom：仅 pySCENIC 必需时使用，需同时保存转换 manifest。
- model directory/archive：必须保存 framework/version/checksum 和 compatibility note。

## 冻结要求

每个 `formal` 环境版本需要：

1. explicit package lock 或 container digest。
2. 关键工具的 import/version health check。
3. BRIDGE fixture 的输入、预期输出和 schema check。
4. CPU/GPU requirement 与最大验证规模。
5. 环境变更 changelog；禁止在同一 environment ID 中静默升级。

当前卡片是运行现状审计。除 `pytorch` 的软件回归测试外，其他环境尚不能被描述为 BRIDGE 正式验证环境。
