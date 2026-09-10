# BRIDGE Agent Handbook

本文件是 BRIDGE 仓库内所有 Coding Agent 的第一入口。开始工作前先阅读本文件、`plans/README.md` 与 `docs/README.md`。

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

## 用户文档与协作指令

- README 是面向用户的项目门面：说明可以解决的问题、实际使用入口、结果含义与适用边界，不充当开发进度、内部工具目录或 Agent 工作记录。
- 用户入口使用生物学问题和功能名称；`P0`、Tool ID、Schema 字段等内部术语只在确有需要的专业文档、合同或诊断详情中解释。
- 文档保持稳定的项目叙述视角，不写对话转述、人称漂移、个人要求或“按你的要求”等元话语。
- Agent 协作要求、开发约定与文档维护指令仅在本文件维护；其他文档可以引用，不重复抄写。产品行为、科学事实、数据来源和版本化合同仍保存在各自专业文档中。
- 目录名称体现实际职责；避免同名入口造成职责混淆。删除重复索引、重复事实和空转包装前先确认真实调用与唯一来源，保留可追溯的科学合同和验证记录。

## 开发环境与维护源

使用 Python 3.12，在隔离环境中安装当前改动需要的 extras；常用开发入口为：

~~~bash
python -m pip install -e ".[qc,test,freeze,evidence]"
~~~

浏览器目录的开发与构建命令见 [frontend](frontend/README.md)，服务配置见
[Web guide](docs/web-preview.md)。安装接口发生变化时还须核对构建后的 wheel。

- 每个工具包保留包入口、运行 Tool Card、科学任务卡、请求示例和验证记录。详细字段和拒绝原因由 Tool Card 维护，不复制成另一份合同。
- 公开 Schema 和知识投影按其维护源重新生成；不能只修改生成物。工具卡按实际来源区分：P0-01、P0-02、P0-08 由 `scripts/render_tool_cards.py` 生成；P0-03–P0-07、P0-09–P0-12 的详细卡本身是人工维护源，脚本只校验、不覆盖。
- 机器接口由 Schema/package spec 定义，运行使用与拒绝由 Tool Card 定义，生物学问题与验证设计由科学任务卡定义，特定版本的实际证据由验证记录定义。
- 产品工作流仅在 PRD 第 6 节维护；概览链接到合同，不重复完整流程。稳定文档须从文档索引或其已索引页面可达。
- 知识策展输入位于 `knowledge/catalog/`；运行时读取打包快照，`knowledge/active-methods.md` 为人工短名单。缺少论文、许可或版本时保留缺失，不凭推测补齐。

## 实现、审查与验证节奏

- 以完整模块或一条用户链路为实现和验收单位，先完成可用的整体，再集中审查、验证和修复。
- 迭代时只运行直接覆盖当前改动的必要检查；已有同一代码和环境的有效证据直接复用，不反复启动全套验证。
- 不为零碎改动、新文件、一次交接或单个修复反复派独立审查 Agent。相关发现成批交由原实现者修复，整条链路完成后统一审查，不另起逐项复核循环。
- 并行或顺序分工用于完整、边界明确的模块，不把上下文重建和重复验证当成工作进展。主整合者对最终跨模块证据负责。
- 本项目的代码、测试、预览和私有运行证据在受控服务器工作区中处理；不改动已有运行服务，推送、合并和部署仍需各自明确授权。

## 快速索引

稳定合同和使用文档见 [文档索引](docs/README.md)；未完成工作见 [活动计划](plans/README.md)。

## 事实优先级

发生冲突时，不得凭印象继续开发。按以下顺序判断：

1. 真实运行产物、冻结 Schema、自动测试和可复现验证记录。
2. 已冻结的 `ProductDefinitionCard`、`MeasurementSpec`、reference、prior 与工具合同。
3. `docs/BRIDGE_PRD.md` 和本手册链接的稳定文档。
4. 任务卡、方法卡、Registry 和候选设计文档。
5. 当前分支的临时计划。
6. README、历史代码、Notebook、Fixture、Mock 和旧报告。

若高优先级来源互相冲突，停止扩大改动，在活动计划和决定记录中写明冲突，并由科学负责人确认。计划不能静默推翻稳定合同。

## 仓库地图

当前仓库提供 BRIDGE 科学智能体的确定性 P0 工具底座，以及私有 Web preview
中已验收范围内的 intake、来源事实核对、protocol 表示、计划审批与 QC，以及
有限范围的证据协调与评估画像。后者的工程连接、真实输入验收和科学资格分开记录；
内部 comparator 选择及 qualified report/export 仍不是当前完整能力。

| 路径 | 职责 |
|---|---|
| `src/bridge/toolkit/` | 公共对象、Registry、运行器、产物与知识检索 |
| `src/bridge/web/` | 私有对话、上传、审批与现有 SDK 执行接入；不修改科学工具语义 |
| `frontend/` | 对话与真实工具产物的浏览器界面 |
| `src/bridge/tool_packages/` | 12 个高层科学工具包及其 Spec、Tool Card 和包内资源；底层方法不直接暴露给 Agent |
| `src/bridge/resources/schemas/` | 随 Python 包发布的对外 JSON Schema；语义变更必须版本化 |
| `knowledge/` | 方法目录策展、来源核验、当前 P0 短名单与知识快照重建输入 |
| `scripts/` | 仓库检查和确定性资源生成；不属于 Agent 可调用的科学工具 |
| `tests/` | 当前活动实现的可执行合同与回归测试 |
| `docs/` | 稳定科学和工程事实 |
| `plans/` | 当前主题分支的临时实施计划 |

`src/bridge/toolkit/contracts.py`、公开 JSON Schema、Tool ID、状态枚举、`MeasurementSpec` 和知识 Source ID 是高冲突表面，默认单写者。

## 多 Agent 协作

并行工作前，主 Agent 必须冻结：

- 目标、Definition of Done 与明确非目标；
- 每个 Agent 的可写路径、禁止路径和唯一整合者；
- 输入输出 Schema、版本、验证命令和停止条件；
- 数据、reference、prior、sealed test 与 competitor-isolated 边界。

不同 Agent 不得同时改写同一高冲突文件。现有未提交改动视为用户或其他 Agent 的成果，不得覆盖、回退、暂存或顺手整理。整合者必须重新运行跨模块验证，不能把子 Agent 自报当作证据。

### 分支、工作树与 PR

- `main` 是 BRIDGE 的唯一集成分支。当前重构通过主题分支和 Pull Request 取代旧实现；合入后不再维护独立品牌或平行的长期集成分支。
- 所有后续变更从最新 `origin/main` 创建职责单一的主题分支，并通过面向 `main` 的 Pull Request 合入。
- 推送到 GitHub 的主题分支不得使用 `codex/` 前缀；使用无主体标识的任务名，例如 `p0-06-proliferation-stress-response`。
- 禁止直接向集成分支 push 或 force push。合并 PR 是独立动作，不能因为实现、push 或开 PR 已获授权而自动执行。
- 开工前检查当前分支、HEAD、远端和 `git status --short --branch`。多人并行优先使用独立 worktree；不得让多个 Agent 在同一工作树并发改写文件。
- 共享分支禁止未经协商的历史重写。同步集成分支时只能在主题分支解决冲突，不得覆盖、丢弃或静默改写其他人的成果。
- PR 必须说明范围、稳定文档和计划影响、科学声明边界、验证命令与结果、未验证项和剩余风险。测试、科学评审或真实数据门禁未完成时使用 Draft PR。

### 计划与交付循环

- 跨多个合同或稳定文档、需要分阶段验收、涉及 Schema、隐私、评分、reference、locked/sealed data 或发布风险的工作必须先创建分支计划。
- 计划身份由主题分支和任务 slug 决定；已有同名计划时恢复或移交，不得覆盖重建。`plans/README.md` 以计划路径为唯一键。
- Draft PR 可以保留 `in_progress` 计划，但不得把未完成任务写成稳定能力。转为 Ready for Review 前，必须在计划中记录最终验证证据；未完成范围应继续保留为明确任务或拆入后续计划。
- 稳定事实同步写入 `docs/`，施工状态只写入 `plans/`。计划不能推翻稳定合同；若需要改变合同或科学边界，必须在 `docs/decision-log.md` 追加决定。
- 交付必须包含改动范围、关键决定、变更文件、验证证据、未验证项、风险和后续动作；“已实现”不能替代可复现证据。

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
- 每个打包 Method 记录必须包含官方文档、源码、论文或 `not_applicable` 原因、版本、许可、输入输出、边界和来源状态。
- 安装成功只表示环境可用，不表示方法科学验证通过。

## 隐私与来源

- 仓库内容由代码、Schema、文档和满足来源条件的最小 Fixture 构成。
- Fixture 来源限定为合成、脱敏、公开或明确授权的数据，并记录用途和 checksum。
- 运行时 manifest 以逻辑资产引用受控输入；public-safe 对象由字段白名单重新生成。
- 原始输入不可修改。派生产物采用追加式版本、内容哈希和显式 provenance。
- 私有路径、凭据、原始模型响应、运行回执、会话、截图、私有样本身份和部署细节不得进入公开仓库；公开对象通过字段白名单重建。

## 文档与计划

- `docs/` 只写已实现或已批准的稳定事实；未来工作写入活动计划或明确标注 `candidate/proposed`。
- 复杂任务在 `plans/<branch-slug>.md` 中记录范围、验收、决定和验证，并由 `plans/README.md` 索引。
- Schema、科学边界、隐私、评分或公开导出规则变化时，同一变更必须更新测试和稳定文档。
- 重大且难以逆转的决定追加到 `docs/decision-log.md`，不得覆盖历史决定。

活动计划只保存未完成施工状态。真正完成后，先把唯一可复用事实迁入稳定文档、
精确证据迁入验证记录，再把未解决科学工作接入活动计划，最后移除已完成日记并
修复链接；施工时间线留在 Git 历史。不得仅因验证记录较旧而删除它。

### 生物学优先的进度表达

计划、PR、Issue 和验证记录按以下顺序说明进展：生物学问题，使用的
数据/reference/对照，实际观察，体外产品评估含义，仍不能回答的问题，下一项
科学工作，最后再列代码、测试和提交状态。不得只用“框架完成”“合同冻结”或
“benchmark 通过”代替生物学结果；未明确约定时，不把待办指定给外部合作方。

## 验证与交付

最小工程门禁：

```bash
python -m pytest -q
python -m bridge.toolkit.cli list --json
python -m bridge.toolkit.cli knowledge validate
python scripts/check_repository.py
git diff --check
```

按改动补充 Schema、知识引用、输入格式、source/modality holdout、OOD、下采样、reference/preprocessing sensitivity、隐私扫描与图表渲染检查。

任务完成必须同时满足：代码、测试、合同和稳定文档一致；验证命令可复现；未验证项和风险明确；没有覆盖他人改动；结论不超出实际证据。
