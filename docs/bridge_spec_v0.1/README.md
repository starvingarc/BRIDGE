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
| [P0-01 输入审计与 QC](input_audit_qc_task_card.md) | 输入、QC、拒答与 readiness 合同 |
| [P0-02 Cell-State Evidence](cell_state_annotation_task_card.md) | 状态证据、方法 benchmark 与释放边界 |
| [P0-03 目标与区域身份](target_regional_identity_task_card.md) | 目标谱系与区域支持合同 |
| [P0-04 发育兼容性](developmental_compatibility_task_card.md) | 发育窗口与比较合同 |
| [P0-05 Off-target Control](off_target_control_task_card.md) | 外部角色/阈值驱动的全制剂组成、unknown 与稀有状态边界 |
| [P0-06 Proliferation & Stress Response](proliferation_stress_response_task_card.md) | 增殖、应激反应程序和复核信号合同 |
| [P0-07 产品比较与稳定性](product_comparison_stability_task_card.md) | 可比性、分析单位与敏感性合同 |
| [P0-08 Evidence Sufficiency](evidence_sufficiency_task_card.md) | 数据、模型与 prior 充分性门禁 |
| [P0-09 Evidence Compiler](evidence_compiler_task_card.md) | 原子证据、来源和冲突协调 |
| [P0-10 Claim Verifier](claim_verifier_task_card.md) | 数字、主张和发布核验 |
| [P0-11 Public-safe Export](public_safe_export_task_card.md) | 字段白名单和公开导出 |
| [P0-12 Graft Assessment](graft_assessment_task_card.md) | 独立后验 graft 证据边界 |
| [公开 JSON Schema](../../src/bridge/resources/schemas/) | Agent、证据、比较、可视化和运行对象合同 |
| [Tool Package Cards](../../src/bridge/tool_packages/cards/) | 当前可调用工具、输入输出和实现状态 |
| [Active Methods](../../knowledge/active-methods.md) | P0-01、P0-02、P0-03、P0-04、P0-07、P0-08 与 P0-09 当前选定方法 |
| [Conda 环境合同](../../environments/README.md) | 当前运行能力所需的最小环境与待建环境 |

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
