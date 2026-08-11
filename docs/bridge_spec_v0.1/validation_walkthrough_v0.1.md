# BRIDGE v0.1 桌面走查记录

> **记录状态：historical walkthrough。** 本记录保存 2026-08-03 的桌面走查，不构成 2026-08-04 PRD 修订后的真实用户验收；当前验收要求以 [BRIDGE PRD](../BRIDGE_PRD.md) 为准。

## 走查性质

| 项目 | 内容 |
| --- | --- |
| 版本 | `WALKTHROUGH-v0.1` |
| 日期 | 2026-08-03 |
| 范围 | 主规范、Data/Reference、Tool、Knowledge、Server 与 Environment Cards |
| 方式 | 作者桌面走查：分别模拟湿实验用户与 Agent 实现团队的完整任务 |
| 边界 | 这不是真实湿实验用户或合作团队的签字验收 |

## 一、湿实验用户视角

### 模拟任务

1. 导入一个具有多个分化时间点和批次的移植前 scRNA 数据集。
2. 声明产品目标、样本层级、取样时点和允许的比较范围。
3. 查看目标/区域身份、发育状态、全制剂组成、unknown、process alerts 和 evidence sufficiency。
4. 追溯一个异常到原始指标、分母、reference、先验与限制。
5. 可选关联 graft snRNA，确认它仅出现在独立后验页面。

### 走查结论

- 主流程已按“产品定义 -> 数据资格 -> 证据画像 -> 差异解释 -> 证据缺口”组织。
- 报告语义明确区分 `negative`、`missing`、`unknown`、`unavailable` 和 `alert`。
- 已明确 P0 不生成综合总分或产品排名，也不输出疗效、安全性、potency 或 GMP 放行结论。
- 已明确 graft 不得回填移植前评分、训练标签或阈值校准。
- 用户可以看到“为什么得出这个判断”和“还需要补什么测量”，不会将数据库知识误当成当前样本测量。

### 需真实湿实验用户确认

- 首张 PD `ProductDefinitionCard` 的 intended stage、mandatory domains 和不可接受状态。
- 表单中哪些术语需要显示中文解释，哪些字段必须在上机前记录。
- 报告第一屏的信息顺序，alert 和 evidence gap 是否符合实际决策习惯。
- 用于理解“未检测到”与“没有检测”的真实案例和表达方式。

## 二、Agent 实现团队视角

### 模拟任务

1. 从 schema-valid `ProductCase` 生成 `AnalysisPlan`。
2. 仅路由到 Tool Registry 中与数据资格、状态和环境相符的工具。
3. 合并 ToolRun、KnowledgeRetrievalRecord 和缺失/冲突为 Evidence Record 及 Case Evidence Graph。
4. 由确定性组件计算指标和域状态，LLM 只负责计划、检索、解释和受约束报告。
5. 用 Claim Verifier 阻止数字改写、无来源声明、missing-as-negative 和 graft leakage。

### 走查结论

- `AG-F01` 至 `AG-F13` 已提供输入、行为、输出和拒答边界，不强制单 Agent 或多 Agent 框架。
- Tool、Knowledge、Reference、Environment 和 Evidence 使用独立版本；正式运行可按 ID 追溯。
- 本地知识 snapshot、实时联网和沙盒探索通道已分离，后两者不能改变当次正式评分。
- 11 张 Environment Card 已补齐责任、资源等级、工具 ID、输入输出、限制、健康检查和更新策略。
- 旧 Step0-3、CLS 和 product baseline 已标记为历史/原型资产，不会被 Agent 当成新科学合同。

### 需合作团队确认

- Agent framework、model/provider、graph/vector/relational store 选型。
- 工具的自动执行、人工确认、长任务配额和失败恢复策略。
- 敏感数据是否可进入模型上下文，以及本地/远程模型的隔离边界。
- JSON Schema/Pydantic、artifact store、审计日志和公开导出的具体实现。
- P0 Tool Card 的 fixture、资源预算和晋升顺序。

## 三、文档自动检查

| 检查 | v0.1 结果 |
| --- | --- |
| 必需文档与 11 张 Environment Card | 通过 |
| `AG-F01` 至 `AG-F13` | 通过 |
| Environment -> Tool ID 交叉引用 | 通过 |
| 相对 Markdown 链接 | 通过 |
| 服务器绝对路径、用户名、IP 和凭据扫描 | 通过 |
| 未解析占位标记与隐性占位总分 | 通过 |

## 四、结论

v0.1 已达到“可交给双方开始评审和原型拆分”的文档状态。正式进入实现前，需由至少一名湿实验使用者和一名 Agent 实现者完成真实走查，将结论追加到新版本，不覆盖本记录。
