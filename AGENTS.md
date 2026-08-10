# BRIDGE Agent Handbook

本文件是 BRIDGE 仓库内所有 Coding Agent 的第一入口。开始工作前先阅读本文件、`PLANS.md` 与 `docs/index.md`。

BRIDGE 采用“代码、稳定文档、临时计划同步演进”的协作方式：

- 代码、Schema、测试和真实运行证据说明系统当前真实能力。
- `docs/` 保存已经确认、未来仍可复用的科学与工程事实。
- `plans/` 只描述当前分支准备如何改变系统。
- 任务卡、方法卡、安装成功、Fixture、Mock 或短 smoke 均不能冒充科学验证通过。

## 实现原则

- 默认选择满足当前合同的最小实现；先删重复，再加抽象。
- 没有两个真实调用方时，不新增通用层、包装类或配置字段。
- 同一事实只保留一个人工维护源，其余内容必须确定性生成。
- 不提交未调用代码、提前设计的扩展点或仅为“以后可能需要”的依赖。

## 快速索引

- 产品原则与科学边界：`docs/product-principles.md`
- 高层工具合同：`docs/tool-contract.md`
- 隐私、来源与可追溯性：`docs/privacy-and-provenance.md`
- 质量与验证基线：`docs/quality-baseline.md`
- 文档维护：`docs/documentation-guide.md`
- 重大决定：`docs/decision-log.md`
- 当前活动计划：`PLANS.md`

## 事实优先级

发生冲突时，不得凭印象继续开发。按以下顺序判断：

1. 真实运行产物、冻结 Schema、自动测试和可复现验证记录。
2. 已冻结的 `ProductDefinitionCard`、`MeasurementSpec`、reference、prior 与工具合同。
3. `docs/BRIDGE_v2_PRD.md` 和本手册链接的稳定文档。
4. 任务卡、方法卡、Registry 和候选设计文档。
5. 当前分支的临时计划。
6. README、历史代码、Notebook、Fixture、Mock 和旧报告。

若高优先级来源互相冲突，停止扩大改动，在活动计划和决定记录中写明冲突，并由科学负责人确认。计划不能静默推翻稳定合同。

## 仓库地图

| 路径 | 职责 |
|---|---|
| `src/bridge/toolkit/` | 公共对象、Registry、运行器、产物与知识检索 |
| `src/bridge/tool_packages/` | 12 个高层科学工具包；底层方法不直接暴露给 Agent |
| `tool_packages/` | 人可读 Tool Card、输入输出、环境、可视化与验证合同 |
| `knowledge/` | 去重后的 Method Card、Source Card 与版本化检索索引 |
| `schemas/` | 对外 JSON Schema；语义变更必须版本化 |
| `tests/` | 当前活动实现的可执行合同与回归测试 |
| `docs/` | 稳定科学和工程事实 |
| `plans/` | 当前主题分支的临时实施计划 |
| `legacy/` | 历史实现，仅供追溯；不安装、不测试、不调用 |

`src/bridge/toolkit/contracts.py`、公开 JSON Schema、Tool ID、状态枚举、`MeasurementSpec` 和知识 Source ID 是高冲突表面，默认单写者。

## 多 Agent 协作

并行工作前，主 Agent 必须冻结：

- 目标、Definition of Done 与明确非目标；
- 每个 Agent 的可写路径、禁止路径和唯一整合者；
- 输入输出 Schema、版本、验证命令和停止条件；
- 数据、reference、prior、sealed test 与 competitor-isolated 边界。

不同 Agent 不得同时改写同一高冲突文件。现有未提交改动视为用户或其他 Agent 的成果，不得覆盖、回退、暂存或顺手整理。整合者必须重新运行跨模块验证，不能把子 Agent 自报当作证据。

## 科学与声明护栏

- BRIDGE 当前提供细胞治疗产品的研究性转录组证据，不输出临床疗效、安全性、validated potency、GMP 放行或绝对产品排名。
- 当前没有冻结任何 P0 `ScoreContract`。在独立验证前，`domain_score` 必须为 `null`，`score_state` 只能是 `shadow` 或 `unavailable`。
- LLM 可以规划、检索和解释；确定性工具拥有数字、分母、阈值、状态、版本和 Evidence ID。
- `negative`、`missing`、`unknown`、`unavailable` 与 `alert` 不得互换，缺失证据不得补零。
- cell 不能充当 biological replicate；重复不足时只能是 `descriptive_only` 或 `not_estimable`。
- graft 是独立后验证据，不回填移植前评分、阈值、训练或校准。
- sealed competitor 数据和 competitor reproduction 不得流入 BRIDGE 的 reference、marker、prior、RAG、阈值或正式证据。
- 同一 Evidence Family 必须去重，工具数量不能成为多数投票。

## 工具与知识规则

- Agent 只调用注册的高层 Tool Package，不直接拼装 Scanpy、R 包或模型命令。
- 未实现工具返回 `not_implemented`，不得伪造 `MeasurementResult`。
- 输入不足返回 `unavailable`、`not_assessed` 或明确 eligibility reason，不把技术不足解释为产品失败。
- 正式运行只读取本地版本化知识快照；实时联网结果只能用于候选策展。
- 每个 Method Card 必须记录官方文档、源码、论文或 `not_applicable` 原因、版本、许可、输入输出、边界和来源状态。
- 安装成功只表示环境可用，不表示方法科学验证通过。

## 隐私与来源

- 不提交私有数据、服务器绝对路径、用户名、内部样本 ID、token、SOP 原文、受限全文或未授权素材。
- Fixture 必须是合成、脱敏、公开或明确授权的最小数据，并记录用途和 checksum。
- 运行时内部 manifest 可以引用受控资产；public-safe 对象必须通过字段白名单重新生成。
- 原始输入不可修改。派生产物采用追加式版本、内容哈希和显式 provenance。

## 文档与计划

- `docs/` 只写已实现或已批准的稳定事实；未来工作写入活动计划或明确标注 `candidate/proposed`。
- 复杂任务在 `plans/<branch-slug>.md` 中记录范围、验收、决定和验证，并由 `PLANS.md` 索引。
- Schema、科学边界、隐私、评分或公开导出规则变化时，同一变更必须更新测试和稳定文档。
- 重大且难以逆转的决定追加到 `docs/decision-log.md`，不得覆盖历史决定。

## 验证与交付

最小工程门禁：

```bash
python -m pytest -q
python -m bridge.toolkit.cli list --json
python -m bridge.toolkit.cli knowledge validate
git diff --check
```

按改动补充 Schema、知识引用、输入格式、source/modality holdout、OOD、下采样、reference/preprocessing sensitivity、隐私扫描与图表渲染检查。

任务完成必须同时满足：代码、测试、合同和稳定文档一致；验证命令可复现；未验证项和风险明确；没有覆盖他人改动；结论不超出实际证据。
