# BRIDGE v0.1 文档包

**版本：** v0.1

**审计日期：** 2026-08-03
**用途：** 供 BRIDGE 生物学团队、算法团队和智能体合作团队共同评审。

本目录是 [BRIDGE PRD](../BRIDGE_PRD.md) 的实施附件包。PRD 是当前唯一主规范；附件提供数据、工具、知识、对象、可视化和环境事实，不得改变 PRD 的科学边界或产品合同。

## 文档地图

| 文档 | 回答的问题 |
| --- | --- |
| [唯一主规范：BRIDGE PRD](../BRIDGE_PRD.md) | BRIDGE 评估什么、Agent 必须实现什么、系统边界在哪里 |
| [数据与 Reference Registry](data_reference_registry.md) | 当前有哪些数据和 reference、彼此是什么血缘、分别允许做什么 |
| [Tool Registry](tool_registry.md) | 每类分析需求可调用什么工具、需要什么输入、何时拒答 |
| [Knowledge Registry](knowledge_registry.md) | 外部知识如何版本化、可用于量化还是解释、许可边界是什么 |
| [Analysis Task Cards](analysis_task_cards.md) | 每项分析的科学问题、输入合同、MeasurementSpec、失败和晋升规则 |
| [Object Schemas](object_schemas.md) | ProductCase、证据、比较、可视化、建议和报告的最小对象合同 |
| [Visualization Registry](visualization_registry.md) | Web 与正式报告可调用的图表组件及数据绑定要求 |
| [Conda 环境合同](../../environments/README.md) | 当前运行能力所需的最小环境与待建环境 |
| [v0.1 桌面走查记录](validation_walkthrough_v0.1.md) | 湿实验与 Agent 实现两种视角下哪些已闭环、哪些需要真实团队确认 |

## 状态词

| 状态 | 含义 |
| --- | --- |
| `adopted` | 已进入 P0 正式工具或正式合同候选，可用于受控运行 |
| `candidate` | 科学用途合理，需完成数据适配、验证和版本冻结 |
| `conditional` | 只有满足特定输入或证据条件时才可运行 |
| `shadow` | 可生成并列候选证据，但不能进入正式协调或发布域分数 |
| `frozen` | 完成任务级分析验证并绑定 MeasurementSpec；若未来另有经验证的 ScoreContract，必须独立版本化 |
| `deferred` | 当前数据或验证条件不足，后续版本再考虑 |
| `excluded` | 当前 Context of Use 中明确不使用 |

## 文档边界

- 文档只记录脱敏的逻辑资产 ID、公开 accession、环境名称和状态。
- 文档不记录服务器绝对路径、个人目录、凭据、IP 地址或私有元数据值。
- 本文档包是方法与实现交接规范，不代表任一算法已获得临床、GMP、potency 或产品放行验证。
- 发现与实际服务器、数据或软件不一致时，以重新审计生成的新卡片版本为准，不静默覆盖 v0.1。
