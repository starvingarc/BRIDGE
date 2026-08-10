# BRIDGE v2 Visualization Registry

| 项目 | 内容 |
| --- | --- |
| 受控主规范 | [BRIDGE v2 PRD](../BRIDGE_v2_PRD.md) |
| 状态 | `component_contract_draft` |
| 正式入口 | BRIDGE Web 与版本化报告 |

Visualization Composer 只能将注册组件写入正式报告。未注册图表可作为 `exploratory` 展示，完成数据绑定和视觉审核后再晋升。

## 1. 组件合同

每个组件记录：

```text
component_id / version / status
scientific_question / task_ids / accepted_artifact_types
required_evidence_fields / aggregation_unit / denominator
chart_type / interaction / export_formats
missing_unknown_alert_encoding
validation_checks / accessibility / reviewer
```

每张正式图表必须显示或可下钻获得 Evidence ID、数据和合同版本、分析单位、分母、单位、不确定性、过滤条件和证据状态。

## 2. P0 核心组件

| Component ID | 主要图表 | 正式用途 |
| --- | --- | --- |
| `VIZ-CASE-STATUS` | 域 x 状态矩阵 | 展示 P0 可用性、gates、alerts 和阻塞原因 |
| `VIZ-COMPOSITION` | 带区间的堆叠条形图 | target、acceptable、off-target 和 unknown 完整制剂组成 |
| `VIZ-IDENTITY-REGION` | 分层 dot/heatmap | target identity、区域支持、偏移和方法分歧 |
| `VIZ-DEVELOPMENT` | 状态占据与真实 D 时间轴 | 发育组成、目标窗口和时间变化；D 不换算为 GW/PCW |
| `VIZ-PROCESS-ALERT` | 程序 burden 与 alert matrix | stage-conditioned process evidence 和关键警报 |
| `VIZ-DOMAIN-SCORES` | 未来五域 aligned bar/small multiples | `deferred`；当前无域分数，不注册为正式图表 |
| `VIZ-ROBUSTNESS` | sensitivity interval/forest plot | reference、model、preprocessing 和下采样敏感性 |
| `VIZ-COMPARISON` | effect-size forest 与分域差异 | `descriptive_only` 或 `inferential` 比较，显式显示模式 |
| `VIZ-EVIDENCE-GRAPH` | 可筛选证据网络 | 来源、支持、冲突、同源和缺失证据下钻 |
| `VIZ-MISSING-NEGATIVE` | evidence-state matrix | 区分 negative、missing、unknown、unavailable 和 alert |

## 3. 条件与 Shadow 组件

| Component ID | 条件 | 发布状态 |
| --- | --- | --- |
| `VIZ-SPATIAL` | 坐标、section、donor、ROI 和 reference 合同完整 | evidence panel；未验证映射保持 shadow |
| `VIZ-COMMUNICATION` | sender/receiver state 和冻结 LR resource | communication potential；不得表示真实通讯 |
| `VIZ-REGULATORY` | TF-target/motif snapshot 与覆盖合格 | measured/inferred/prior-only 分层展示 |
| `VIZ-GRAFT` | animal/graft/timepoint 与 preparation linkage 明确 | 独立后验页面，不与移植前分母或分域分数合并 |

LIANA 与 CellPhoneDB 共享方法或 ligand-receptor 来源时必须使用同一 evidence-family 标记，图中不得呈现为两项独立验证。

## 4. 晋升与视觉核验

- 优先使用分析工具官方绘图接口和数据结构；组件实现需记录官方文档与源码版本。
- 自动检查数据绑定、分母、单位、尺度、排序、缺失值、色彩语义、文本溢出和导出一致性。
- `descriptive_only` 图表不得显示推断显著性；`score_state=shadow` 的候选分数不得与正式 P0 分数使用相同发布样式。
- Critical Alerts 和 unavailable 不得被高分遮蔽，unknown 不得并入 target 或 off-target。
- 图表在桌面与移动 Web、SVG/PNG 和 CSV 导出中保持相同数据语义。

候选实现可参考 [Scanpy plotting](https://scanpy.readthedocs.io/en/latest/tutorials/plotting/core.html)、[CellRank plotting](https://cellrank.readthedocs.io/en/stable/api/plotting.html)、[LIANA](https://liana-py.readthedocs.io/en/latest/api.html)、[Squidpy](https://squidpy.readthedocs.io/en/stable/api.html)、[Vitessce](https://vitessce.io/docs/) 和 [Cytoscape.js](https://js.cytoscape.org/)。参考实现不自动获得正式组件资格。
