# Environment Card: CellBender Proposed

| 字段 | 内容 |
| --- | --- |
| Environment ID | `ENV-CELLBENDER-v0.1` |
| Environment name | proposed，尚未建立 |
| 审计日期 | 2026-08-03 |
| 状态 | `not_installed` |
| Owner | `pending_assignment` |
| Interpreter/key packages | `pending_freeze` |
| GPU requirement | 推荐单 GPU；按 raw matrix 规模估算显存和时间 |
| Resource class | `single_gpu` |
| Registered tool IDs | `CELLBENDER-RB`（proposed） |
| Input artifact types | unfiltered raw droplet count matrix + capture metadata |
| Output artifact types | corrected matrix、posterior/metrics/log、MeasurementResult JSON |
| Update policy | 创建后冻结 release/lock；参数合同或版本变更时创建新 Environment ID |

## Intended Purpose

在用户提供未过滤 raw droplet matrix 时运行 CellBender `remove-background`，形成与原始 counts 并列的 sensitivity view。

官方说明：[CellBender usage](https://cellbender.readthedocs.io/en/latest/usage/)；软件许可证 BSD-3-Clause。

## Input Contract

- 未过滤、UMI-based raw droplet count matrix。
- chemistry、expected cell count、sample/capture ID 和原始 quantification metadata。
- 每个 capture 独立运行。

## Outputs

- corrected full/filtered matrix、posterior、metrics、report、log 和 checkpoint manifest。
- original/corrected counts 对照、parameter sensitivity 和 downstream effect summary。

## Boundaries

- 只有 filtered h5ad 或 normalized matrix 时不运行。
- 背景校正不替代 viability、doublet 或样本质量检查。
- corrected matrix 不静默覆盖原始 counts。
- 具体 release 必须经过官方已知问题检查和 BRIDGE fixture；不默认使用 `latest`。

## Proposed Health Check

```bash
conda run -n cellbender cellbender remove-background --help
conda run -n cellbender python -c "import cellbender, torch; print(torch.cuda.is_available())"
```

创建环境属于后续部署任务，v0.1 不声明该能力可用。
