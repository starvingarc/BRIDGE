# Environment Card: Agent Runtime Proposed

| 字段 | 内容 |
| --- | --- |
| Environment ID | `ENV-AGENT-v0.1` |
| Environment name | proposed，尚未建立 |
| 审计日期 | 2026-08-03 |
| 状态 | `design_pending_with_agent_team` |
| Owner | `joint_assignment_pending` |
| Framework/model | 未选择 |
| Interpreter/key packages | `pending_architecture_decision` |
| GPU requirement | 待定；取决于本地模型/远程 API 部署 |
| Resource class | `interactive_cpu` / `batch_cpu`；本地模型方案另行评估 |
| Registered tool IDs | `BRIDGE-CASE-VALIDATOR`, `EVIDENCE-COMPILER`, `DOMAIN-ASSESSOR`, `COMPARABILITY-GATE`, `CLAIM-VERIFIER`, `PUBLIC-SAFE-EXPORT`（proposed services） |
| Input artifact types | ProductCase、registry snapshots、ToolRun/Evidence records |
| Output artifact types | AnalysisPlan、Case Evidence Graph、report/audit artifacts |
| Update policy | framework/model/prompt/tool contract 分别版本化；不覆盖已发布 case |

## Intended Purpose

承载 Agent orchestration、结构化表单/API、Tool Registry router、本地知识检索、Case Evidence Graph、报告生成、Claim Verifier 和审计日志。

## Required Capabilities

- 支持 `AG-F01` 至 `AG-F13` 的结构化输入输出。
- 使用 JSON Schema/Pydantic 等确定性 schema validation。
- 调用远端工具时只传递逻辑 asset/artifact ID，不把服务器路径发送给模型。
- 本地知识检索、实时联网检索和沙盒探索使用独立 namespace。
- 数字从 Evidence Record 自动渲染，LLM 不重新计算或手工转写。
- 保存 model、prompt、tool call、retrieval、output、verifier 和人工修改记录。

## Isolation Requirements

| 通道 | 可读内容 | 可写内容 | 能否影响正式评分 |
| --- | --- | --- | --- |
| Formal execution | confirmed ProductCase、frozen registry、registered artifacts | versioned ToolRun/Evidence artifacts | 是，由确定性工具决定 |
| Local retrieval | approved knowledge snapshots | retrieval record | 只能按 allowed use |
| Live web | public web、official sources | transient evidence/curation queue | 否 |
| Sandbox | case 的只读脱敏视图 | exploratory artifact | 否 |
| Verifier | report + evidence allowlist | verified/release_blocked result | 只控制发布 |

## Open Decisions

- 单 Agent、多 Agent或 workflow engine 的具体框架。
- 本地模型、远程 API 或混合模型的部署方式。
- 工具调用的分级授权、长任务确认和资源配额。
- prompt injection、secrets、network allowlist 和 sandbox 技术实现。
- graph store、vector store、relational metadata store 的选型。

这些选型不得改变 ProductCase、MeasurementResult、Agent capability 和 audit contracts。

## Minimum Acceptance Fixture

1. 多时间点、多批次 pretransplant case。
2. 同一 case 关联 graft snRNA，但正式 pretransplant score 不变化。
3. 缺关键 metadata 时只追问必要问题并拒绝正式运行。
4. 实时检索命中一篇新论文，但 score snapshot 保持不变。
5. 沙盒输出只能出现在 exploratory section。
6. 报告中一个数字被篡改时 Verifier 阻止发布。

环境建立后需新增具体版本、依赖 lock、model/provider card、privacy review 和可重复 fixture。
