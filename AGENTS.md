# BRIDGE Agent Handbook

本文件是 Coding Agent 的执行入口。人类协作者的 Issue、分支、PR 和验收流程以 [CONTRIBUTING](CONTRIBUTING.md) 为准；Agent 同样遵守该流程。

## 开工与完成

1. 检查当前分支、HEAD、远端及 `git status --short --branch`，读关联 Issue 和现有改动。未提交成果属于用户或其他协作者，不覆盖、回退或顺手暂存。
2. 明确目标、非目标、可写范围与完成标准。先找已有实现和维护源，再决定是否新增文件；简单修正文档不另建计划。
3. 按下表读取本次任务需要的合同。PRD 规定产品目标，冻结合同约束科学行为，代码和真实记录说明实际能力；三者冲突时明确报告，不能将现有错误当作新规范。涉及科学合同的冲突交科学负责人确认后再改。
4. 完成一条完整链路后集中审查，按 [开发指南](docs/DEVELOPMENT.md#检查与内部验收) 做与修改及具体风险相称的检查，保留必要安全与科学验证，复用适用的已有结果和测试。相关检查通过即交付；仅在有新修改、新失败或具体未解决风险时重跑或扩大验证。同一失败须有新假设才重试。
5. 交付范围、变更、验证结果、未验证项和风险。进展以实际交付、解除阻塞或改变下一步的新证据为准；合理 CI 等待除外。实现、推送、开 PR、合并、部署是不同授权；Agent 不因完成代码而自行合并或改动运行服务。

| 任务 | 必须读取的维护源 |
|---|---|
| 首次配置、启动、测试 | [开发入口](docs/DEVELOPMENT.md)、[前端入口](frontend/README.md)、[Web 配置](docs/web-preview.md) |
| 产品流程、五域评估、交互 | [PRD 第 6 节](docs/BRIDGE_PRD.md#6-agent-功能需求)、相关工具合同 |
| 科学方法、输入输出、证据 | [工具指南](docs/tool-packages.md)、对应包 Spec / Tool Card / 科学任务卡 / 验证记录 |
| 资源、模型、reference、知识 | [数据与资源](docs/DATA.md)、[数据参考注册表](docs/bridge_spec_v0.1/data_reference_registry.md) |
| 隐私、导出、安全 | [隐私与来源](docs/privacy-and-provenance.md)、[安全报告](SECURITY.md) |
| 继续未完成工作 | [活动计划](plans/README.md)、当前分支及关联 PR；核对当前提交，不以旧状态代替现场证据 |
| 发行或部署 | [版本与发布](docs/RELEASE.md)、[总体路线图](docs/ROADMAP.md)；部署另行授权 |

## 实现原则

- 模块之间低耦合：各自拥有数据和职责，通过少量稳定输入输出协作；不读取另一模块的内部状态，不把整个应用协调器传入新的独立模块。
- HTTP 处理协议与鉴权，执行模块调度已注册任务，存储负责持久化，科学工具负责测量，展示消费结果合同。依赖从装配入口注入，避免循环导入和隐式全局共享。
- 跨模块修改先明确字段、版本、失败语义和责任人，由唯一整合者接线。拆分以降低修改传播为标准，不以文件数或转发层数为标准。
- 选择满足当前合同的最小实现；先删重复，再加抽象。没有两个真实调用方时，不新增通用层、包装类或配置字段，不提交未调用代码和预设依赖。
- 同一事实只保留一个人工维护源；其余内容确定性生成或链接引用。仓库检查读取 Git 跟踪文件和合同，不另建逐文件清单、重复根目录或嵌套 Agent 指令。
- 用户界面用生物学问题和功能名称；`P0`、Tool ID、Schema 等保留在必要的开发文档或诊断详情中。开发仓库 README 面向协作者，产品界面面向研究用户。

## 代码与合同归属

下表列出最常访问的路径，不穷尽 `src/bridge/` 的全部子包。

| 路径 | 职责 |
|---|---|
| `src/bridge/toolkit/` | 公共对象、Registry、运行器、产物、知识检索 |
| `src/bridge/tool_packages/` | 高层科学工具、Spec、Tool Card、包内资源 |
| `src/bridge/web/` | 应用装配、HTTP、会话、产物访问与任务调度，不改科学测量语义 |
| `frontend/` | 对话、结果和证据图展示 |
| `src/bridge/resources/schemas/` | 打包的对外 JSON Schema，语义变更须版本化 |
| `knowledge/` | 策展输入与确定性知识重建 |
| `scripts/`、`tests/` | 生成与仓库检查、可执行合同及回归；不是 Agent 科学工具 |

- 机器接口由 Schema/package spec 定义，运行用法与拒绝原因由 Tool Card 定义，生物学问题与验证设计由科学任务卡定义，特定版本的实际证据由验证记录定义。修改生成物前先找维护源。
- `scripts/render_tool_cards.py` 生成 P0-01、P0-02、P0-08；其他工具的详细卡是人工维护源，该脚本只校验、不覆盖。
- 知识策展输入为 `knowledge/catalog/`；运行时读打包快照，`knowledge/active-methods.md` 是生成短名单。按生成脚本重建，保留 capability bindings 和 alias ambiguity，不按名称猜测合并。
- 快照重建须确定性通过来源、隐私及悬空引用检查；不存受限全文或展开的重复 Method/Source 树。缺少论文、许可或版本时保留缺失，不猜测补齐。

## 科学与声明护栏

- BRIDGE 提供细胞治疗产品的研究性转录组证据，不输出临床疗效、安全性、validated potency、GMP 放行或绝对产品排名。
- 当前没有冻结任何 P0 `ScoreContract`。独立验证前，`domain_score` 为 `null`，`score_state` 只能为 `shadow` 或 `unavailable`。
- 分化链指标（五级条件比例与其乘积）是按版本冻结、带分子分母的原始测量，不是 `domain_score`；缺失级别为 `null` 并说明原因，见 [研究内对象](plans/research-objects.md)。
- LLM 负责规划、检索和解释；确定性工具拥有数字、分母、阈值、状态、版本和 Evidence ID。
- `negative`、`missing`、`unknown`、`unavailable`、`alert` 不可互换，缺失证据不补零。cell 不是 biological replicate；重复不足只能是 `descriptive_only` 或 `not_estimable`。
- graft 是独立后验证据，不回填移植前评分、阈值、训练或校准。
- sealed competitor 数据隔离。公开方法 metadata 与经验证的授权 query 输出可分别进入检索和证据图，但图中记录不授予训练、校准、独立验证或科学资格；外部 reproduction 不反向修改当轮模型、reference、marker、prior 或阈值。
- 同一 Evidence Family 去重，工具数量不能成为多数投票。安装、Fixture、Mock、smoke 和工程连接均不等于科学验证通过。
- Agent 调用已注册高层 Tool Package，不直接拼装 Scanpy、R 包或模型命令。未实现返回 `not_implemented`，不得伪造 `MeasurementResult`；输入不足返回明确 eligibility reason、`unavailable` 或 `not_assessed`，不解释为产品失败。
- 正式科学测量只读本地版本化知识快照。范围内显式批准的公共文献检索可进入版本化研究解释，保存来源、读取内容与适用条件；不得改变测量、reference、prior、阈值或评分。进入正式知识快照仍须候选策展和科学审阅。打包 Method 记录官方文档、源码、论文或 `not_applicable` 原因、版本、许可、输入输出、边界和来源状态。

## 数据与来源护栏

- 私有仓库也不存凭据、部署模型配置、服务器内部路径、真实用户数据、会话、私有样本身份、原始模型响应、运行回执或私有截图。协作者自行配置模型服务；代码权限不等于数据权限。
- 最小 Fixture 仅使用合成、公开或经明确授权可共享的数据，记录用途和 checksum；脱敏本身不等于获准共享。已提供的合成协作数据见 [examples/demo](examples/demo/README.md)，新增数据仍需来源审查，不以数据交付冒充完整流程或科学验证通过。
- 原始输入不可修改；派生产物采用追加式版本、内容哈希与显式 provenance。运行 manifest 用逻辑资产引用受控输入，public-safe 对象按字段白名单重建。
- 真实数据验收在获准环境检出准确提交执行；仓库仅保留获准共享的验证摘要。任何公私仓库同步都必须经过发布审查，不能自动双向同步。

## 并行协作与文档维护

- 需要并行时先固定各方可写路径、输入输出版本、验收命令、停止条件和唯一整合者；明确 reference、prior、sealed test 与 competitor-isolated 边界。按完整模块分工，不按单个文件反复派审查。
- 工作台 M1 的前端与后端可写范围及接口以 [研究内对象](plans/research-objects.md) 为准；接口变化先改该文档。
- `contracts.py`、公开 Schema、Tool ID、状态枚举、`MeasurementSpec`、知识 Source ID 默认单写者。不同 Agent 不在同一工作树并发修改；整合者验证跨模块行为，不能把子 Agent 自报当作通过证据。
- 复杂或高风险任务的计划规则见 [CONTRIBUTING](CONTRIBUTING.md#计划与文档)。已有计划先恢复或移交，不能覆盖重建；`plans/README.md` 以计划路径为唯一键。
- 稳定事实进入 `docs/` 并从索引可达；总体阶段只维护 `docs/ROADMAP.md`，工作台功能顺序与状态只维护 `plans/user-journey.md`。文档采用项目叙述，不写会话转述、个人要求或已完成施工日记。
- Schema、科学边界、隐私、评分或导出规则变更时，同步更新合同、测试和稳定文档；重大不可逆决定追加 `docs/decision-log.md`，不覆盖历史。
- 科学任务说明生物学问题、数据与对照、实际观察、评估含义和未回答问题。纯工程／文档任务说明行为变化和工程检查，不编造生物学结果。未经约定，不将待办指派给外部合作者。
- 完成须满足代码、合同、文档一致，验证范围明确，未覆盖他人成果，声明不超出证据；完整部署或科学资格仍未验证时明确标注。
