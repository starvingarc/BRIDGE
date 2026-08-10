# bridge-amax Server Card

## Identity

| 字段 | 当前值 |
| --- | --- |
| Logical server ID | `bridge-amax` |
| Hostname | `amax` |
| 审计日期 | 2026-08-03 |
| OS | Ubuntu 20.04.1 LTS |
| Kernel | Linux 5.15.0-113-generic |
| 主要用途 | BRIDGE 数据审计、单细胞/空间分析、模型运行和报告生成 |
| 状态 | `active_internal_server` |

本卡片不记录 IP、用户、凭据或服务器文件路径。

## Hardware

| 资源 | 配置 |
| --- | --- |
| CPU | 2 x Intel Xeon Gold 6330 @ 2.00 GHz |
| CPU topology | 56 physical cores / 112 threads |
| Memory | 约 1.0 TiB；审计时约 601 GiB available |
| GPU | 2 x NVIDIA GeForce RTX 3090 |
| GPU memory | 24,576 MiB per GPU |
| NVIDIA driver | 535.183.01 |
| Driver-reported CUDA | 12.2 |

## Storage Capacity

| Logical volume | Total | Available at audit | Utilization | BRIDGE policy |
| --- | ---: | ---: | ---: | --- |
| `volume_primary` | 37 TB | 11 TB | 71% | active code、models、curated references 与常用 outputs |
| `volume_secondary` | 73 TB | 9.3 TB | 87% | large raw/public/spatial archives；新增大对象前必须估算空间 |

容量是审计快照，不是配额保证。Agent 的 `AnalysisPlan` 必须在大规模训练、转换、CellBender、pySCENIC 或空间任务前记录预计输入、临时空间和最终产物大小。

## Runtime Policy

1. 核心 P0 默认使用 `pytorch` 环境。
2. 空间、pySCENIC、LIANA、trajectory 和 R 方法使用独立环境，禁止为方便而把全部依赖装入一个环境。
3. 正式 Tool Run 记录 environment ID、解释器版本、关键包版本、GPU ID、seed、参数 hash 和 input/output hash。
4. 环境存在不代表已通过 BRIDGE health check；以各 Environment Card 的状态为准。
5. 长任务需要 checkpoint、独立日志和可恢复输出，避免依赖持续 SSH 连接。
6. 不在文档、public-safe report、prompt 或 Agent memory 中暴露服务器绝对路径。
7. 原始数据保持只读；正式工具写入 case-specific artifact area，不覆盖输入。

## Scheduling Classes

| Class | 建议资源 | 例子 |
| --- | --- | --- |
| `interactive_cpu` | <= 8 threads，<= 32 GiB | manifest、QC summary、report、small scoring |
| `batch_cpu` | 8-56 cores，按任务声明内存 | pseudobulk、large Scanpy、LIANA、pySCENIC steps |
| `single_gpu` | 1 GPU，显存预算 <= 24 GiB | scVI query mapping、cell2location、CellBender |
| `dual_gpu_research` | 2 GPU，仅显式实验 | 大 reference training；P0 不默认使用 |
| `large_memory` | > 256 GiB，必须预估临时对象 | million-cell reference preprocessing |

Agent 不自行决定执行授权策略；它必须提供资源估计和风险，由后续权限设计决定是否自动运行或请求确认。

## Operational Risks

| 风险 | 当前影响 | 控制 |
| --- | --- | --- |
| Ubuntu 基础系统较旧 | 新包/编译器/CUDA 组合可能不兼容 | 使用冻结 conda environment 或 container；避免原地大升级 |
| 环境版本跨度大 | AnnData/Scanpy object serialization 可能漂移 | 每个工具固定 environment；跨环境用标准 artifact schema |
| `pytorch` 环境依赖较宽 | 更新单包可能触发连锁变化 | 导出 explicit lock、建立 health check 和不可变 release snapshot |
| 次级存储利用率高 | 空间/原始 droplet/模型任务可能耗尽空间 | 运行前空间预算、临时文件清理和 retention policy |
| 2 x 24 GiB GPU | 超大 reference 训练需分块或 CPU/offload | P0 采用冻结 reference/query mapping；大训练单独立项 |
| 远程连接可能中断 | 前台长任务可能失去控制 | 使用可恢复 batch runner、checkpoint 和状态记录 |

## Minimum Health Check

每次正式 release 至少验证：

```text
server identity and OS
CPU/RAM/GPU visibility
storage free-space gate
conda environment existence
key package import and version
small read-only fixture run
artifact schema validation
GPU smoke test where applicable
```

Health check 输出必须使用逻辑环境和 artifact ID；public-safe 输出不保留服务器路径。
