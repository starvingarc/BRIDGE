# Product Evidence Mainline

**Status:** engineering_accepted_human_review_pending.
**Goal:** Accept one real single-product assessment from confirmed input through
evidence, explanation, report and correction. The [PRD](../docs/BRIDGE_PRD.md#6-agent-功能需求)
owns product behavior; this plan owns unfinished delivery.

## Current implementation

Upload, fact confirmation, approval and QC have bounded acceptance. Candidate
cell states, source-bound reference similarity, development context, whole-view
composition and all seven process families have implementations and recorded
descriptive runs. Graph queries and append-only history, cited explanations,
version-bound reports, confirmed corrections and five expandable result cards
are integrated. One authorized saved case has now completed the fixed-version
engineering flow through explanation, report and a name-only correction;
see the [bounded closeout record](../docs/validation/step7_evidence_coordinator_20260911.md#single-product-engineering-closeout--2026-10-04).
Independent wet-lab reader acceptance and scientific qualification remain open.

Engineering checks and review belong to the corresponding PR and exact-commit
CI. Scientific observations and source limitations belong to
[validation records](../docs/validation/README.md). Do not copy test counts,
per-commit repair diaries or migration inventories into this plan.

## Current delivery: single-product research workspace

The engineering closeout of queue item 2 covers PRD 6.7–6.10 for one saved case. It keeps
scientific tools and schemas unchanged: one reading path connects the five-domain
portrait, versioned explanations, exact evidence navigation and current reports.
Current versus historical report access remains server-owned. Confirmed input
corrections must preserve old bytes and remove their current-result status.

Acceptance uses the registered Web/tool flow and existing synthetic inputs, plus
an authorized internal saved case where its inputs and resources remain valid.
The frontend must support keyboard navigation and narrow screens, show unavailable
states without fabricated scores, and present the same report snapshot online and
offline. Independent reader acceptance, scientific qualification and optional later analyses remain governed by
the checklist below and the qualification plan. No production service change is part
of this delivery.

## Current delivery dependencies

### Fine-state accounting

P0-02 0.6.2 aligns hierarchical artifacts with the typed QC DataView, checks
parent/child count conservation and marks non-overlapping whole-view rows in
the existing TSV. The input checksum retains its file identity; no classifier
or scientific role assignment changes. The V3 handoff still contains only L1
composition. The saved hierarchy now also reaches P0-03 explicit role accounting
and the existing evidence/display path; reviewed scientific mapping remains outstanding.

Engineering wiring and scientific mapping are separate dependencies. A
source-supported mDA-progenitor target/region definition is still required.
The current v1.1 review permits bounded broad-family interpretation; seven fine
RG/Nb labels remain parent-only. User confirmation must not promote a candidate
to reviewed identity, developmental stage or product purity. See
[scientific qualification](product-evidence-validation.md).
The source review records the scientific definition gap; the capability queue
below owns future delivery and does not imply those capabilities are implemented.

### Source-bound program continuation

the implementation review supplies source pinning,
saved sufficiency-result reuse, distinct graph records and bounded explanations
for pluripotency and dissociation/heat-shock observations. Unavailable method
values remain null. Its [versioned record](../docs/validation/step7_evidence_coordinator_20260911.md#source-bound-program-continuation--2026-09-26)
is the evidence source; do not repeat unchanged measurements.
For native saved-observation continuation, a scope can freeze the next P008
inputs and permit P009 append to resolve their verified result after execution.
The consumer uses only pinned roots and actual admissions in that scope;
historical explicit selections and receipts remain unchanged. Other source-bound
program continuation paths still require their own acceptance.

<a id="capability-todo"></a>

## 能力核对与开发待办（2026-09-28）

**核对基线：** 集成源码 `82d1fb67c2cfdd7c312e6f2f8eee12d525926867`；
`6afde88` 只补充产品定义来源文档。随后 P0-02 0.6.2 已修正分层视图绑定与父子计数，
其余缺口仍按下表维护。以下为源码核对，不是本轮执行测试、
真实数据验收、部署或科学资格声明。“未接入”指当前工具实现与调用链未发现相应能力，
不代表知识目录没有方法条目。总体阶段继续只维护 [ROADMAP](../docs/ROADMAP.md)。

本节是能力决策与 feature 队列的唯一维护源；科学资格仍由
[产品资格计划](product-evidence-validation.md)维护，旧真实流程验收项继续保留。
所有新分析都经已有高层工具、结果合同和证据路径进入 Agent，不让 LLM 直接拼接底层命令。
先补产品评估，再逐个 feature 整合；未开工项不提前增加依赖、空接口或重复注册表。

### 已有实现与明确缺口

路径均为仓库内开发入口；方法名仅用于开发文档，不直接成为用户界面的标题。

| 能力 | 当前代码事实 | 确认的目标及待办 |
|---|---|---|
| QC | [执行器](../src/bridge/tool_packages/p0_01_input_qc/executor.py)已有指标、按 capture 的 Scrublet、筛选视图；上游 QC、cell calling、ambient 状态仍未评估 | 核对并复用已有处理记录，只补缺失步骤；原始数据或明确要求才重新完整 QC。处理过不等于质控通过 |
| 标准化／HVG／PCA | [grouping.py](../src/bridge/tool_packages/p0_02_cell_state/grouping.py)已有 Scanpy 标准化、HVG、PCA、邻居图 | 从局部分群准备补成可复用的后台准备流程；核对输入/参数适用性，保留高级设置，不逐项追问 |
| UMAP／分群 | 表达探索入口已有 UMAP／Leiden、显式坐标复用、分群/注释/QC/基因着色和完整群计数，复用工具图表及导出 | 加交互 UMAP，按类型、批次、QC、基因着色，与组成/证据联动；合适的坐标/分群复用，否则补算；暂不加 Louvain |
| 批次整合 | 已有按 capture 的 HVG 和分群偏倚检查；[scANVI 适配器](../src/bridge/tool_packages/p0_02_cell_state/method_adapter.py)拒绝 external query，不能当作用户整合流程 | 多批次先建议、确认后执行；保留前后结果，不消除方案真实差异，不用整合后的值冒充原始 counts |
| 细胞注释 | [candidate_runtime.py](../src/bridge/tool_packages/p0_02_cell_state/candidate_runtime.py)已有 CellTypist、拒绝/未知及 marker 支持；[executor.py](../src/bridge/tool_packages/p0_02_cell_state/executor.py)已有条件性 L2 | 自动大类→有依据的细分状态；仅追问关键歧义。复用现有模型，不因新增 UI 自动升级候选身份 |
| 目标／非目标 | [V3 composition](../src/bridge/tool_packages/p0_02_cell_state/metrics.py)只承接 L1；[硬计数合同](../src/bridge/tool_packages/p0_05_off_target_control/models.py)限制 canonical L1 分母 | 已有细分状态整批候选核算；仍需审阅后接入角色核算；组成与目标符合程度分层展示，同谱系阶段不符、其他谱系、未确定部分分开 |
| 发育／成熟度 | [方法运行器](../src/bridge/tool_packages/p0_04_developmental_compatibility/method_runtime.py)有参考支持、受限序数分类、程序及 bootstrap；时间趋势仍返回缺少实验时间合同 | 展示参考阶段、批内成熟状态分布和目标符合程度；不给无验证的精确孕周，不把越成熟等同越好 |
| 增殖／应激 | [方法运行器](../src/bridge/tool_packages/p0_06_proliferation_stress_response/method_runtime.py)已有 Scanpy/ULM/周期；七族的描述性执行范围见前述 PR #8 记录 | 保留七族覆盖与不同单位，完成当前产品的图/解释连接；不是新增一套评分，也不等于七族均有可用数值或科学资格 |
| 整体分母 | [角色核算](../src/bridge/tool_packages/p0_05_off_target_control/models.py)已有 selected-view 数量与比例约束 | 默认全部纳入分析的细胞为分母，未知和非目标保留；谱系内比例仅辅助。展示上传/排除/纳入数及可计算的筛选前后组成；不冒充整批绝对产量 |
| 差异表达 | 表达探索入口已有群 marker、同一 H5AD 内同类型细胞的两条件 pseudobulk/PyDESeq2；样本不足或混杂仅描述 | 跨会话 cohort 和配对设计仍待比较入口；真实数据科学验收独立进行 |
| 通路／富集 | 已有预定义 Scanpy/ULM 程序评分；未见差异表达后 GSEA/ORA 运行链 | 保留评分，补 DE 后的通路解释、驱动基因和现成图；默认主要发现，可展开全部结果。缺少重复不能借富集恢复方案效应的统计资格 |
| 组成／差异丰度 | 比较模块已有 JS 距离、样本效应与离散程度；未见 scCODA/Milo 接入 | 产品比较核心：比例差、独立批次分布及条件性统计；组成变化不等于绝对产量变化 |
| 轨迹／分化倾向 | 当前细胞状态/发育运行模块未见拟时序或 CellRank 调用 | 连续状态及可信起点满足时自动建议，展示轨迹、分支、基因变化；CellRank 可选，不要求先跑 RNA velocity，不把拟时序当真实时间/移植命运 |
| 空间参考 | [区域执行器](../src/bridge/tool_packages/p0_03_target_regional/executor.py)仍返回空间投射未评估 | 保留适用空间参考辅助区域判断；参考表达相似性不等于真实位置。用户自有空间分析后置 |
| 证据独立性 | [充分性执行器](../src/bridge/tool_packages/p0_08_evidence_sufficiency/executor.py)已有同族去重/冲突 | 复用规则，默认显示支持依据、限制与分歧、还缺什么；相同数据上的工具数量不加票 |
| 缺失与科学状态 | [展示合同](../src/bridge/tool_packages/p0_08_evidence_sufficiency/visualization_data.py)保留缺失、依赖与科学边界 | 区分尚未评估、本次未检出、暂不能确定；简短原因和优先补充动作。限制跟随具体结论，技术验证按需展开，不生成无依据的合格/可移植判断 |
| 证据图 | [EvidenceGraph.tsx](../frontend/src/components/EvidenceGraph.tsx)与 [graphData.ts](../frontend/src/components/graphData.ts)已有 Cytoscape、邻接展开、全图及版本 | 不重建图系统；补结果判断→具体图节点的直接定位，默认围绕该判断展示证据与来源，全图按需查看，历史不冒充当前有效版本 |
| 结论核查 | [verifier.py](../src/bridge/tool_packages/p0_10_claim_verifier/verifier.py)已有结构化报告的数值/单位、引用、范围与措辞核查 | 对话产品判断与报告一致，默认后台核查；覆盖全对话的链路待核对/补齐。依据不足收窄结论而非丢弃结果，已展示结论的实质变化保留历史并提示 |
| 产品比较体验 | 已有比较工具及 [条件输入](../src/bridge/web/conditional_inputs.py)，不是完整跨实验对照体验 | 按维度展示改善/退步/不确定，允许部分可比；区分自己的方案迭代和跨论文对照，不总排名。公开数据须先登记授权/适用性并确认 cohort |
| 实验／方案关联 | [PRD 6.2](../docs/BRIDGE_PRD.md#62-productcase-建立)已有批次中心要求；不把现有 session 当已完成方案版本模型 | 一个实际批次的实验会话关联方案/版本；新批次独立建案、跨案比较，面板保留实验信息；分析版本与方案版本分开 |
| 移植后关联 | [analysis.py](../src/bridge/tool_packages/p0_12_graft_assessment/analysis.py)与 [输入模型](../src/bridge/tool_packages/p0_12_graft_assessment/analysis_models.py)已有单移植物描述分析 | 保留后续多批次/动物/时间点关联；供宿主身份与可比性明确后比较，旧移植前结果不覆盖，检出比例不作存活率 |
| 细胞通讯 | 未见 LIANA/CellChat 执行链 | 后置可选 LIANA+ 机制探索；潜在通讯不作功能/移植效果证明，不拼无关宿主参考声称真实通讯 |
| 暂不纳入 | 不为工具数量增加范围 | scVelo、CITE-seq、ATAC 暂不建设；保留 CellRank 的非 velocity 路径评估，不误删相关历史来源信息 |

### 一次一个 feature 的执行队列

这是优先级与完成标准，不是全部功能同时开工的授权，也不预先固定新 API。
每项开工前读对应 Tool Card/科学任务卡、相关论文与候选库源码/许可；如需改公共合同，
先定输入输出及兼容边界。使用已有测试和保存结果，只检查本项受影响行为。

- [ ] **1. 细分状态到整批目标核算（候选组成已实现，角色映射待审阅）。**
  复用 P0-02 的 L2 及已修正的 selected DataView 绑定，贯通 P0-03/P0-05 与现有画像/证据。
  科学定义依赖 [来源审阅与角色缺口](product-evidence-validation.md#mdapro-genitor-review)；
  分层分类、阶段符合度和四类产品角色不可混成一套未经审阅的新枚举。
  完成标准：父子不重复计数、子集比例不冒充整体；目标/阶段不符/其他谱系/未知可追溯；
  `parent_only` 不升级，科学映射未就绪也能诚实交付候选核算，不声称目标纯度已成立。
  已实现：保存层级组成到不重叠整批分区、描述性测量、现有图与网页展示；
  沿用来源审阅限定，不重跑矩阵，不改变旧回执。旧版本通过显式绑定兼容读取。
  P0-03 已接入同一保存分区及显式审核角色映射，逐行保留未判定原因、完整分母和映射来源，
  并进入现有网页/证据链；映射未覆盖时目标比例保持 null。
  未完成：当前真实产品经审核的细分身份/阶段/角色定义；不能将工程连接作为目标纯度验收。
- [x] **2. 单产品五域与证据闭环收口（单例工程范围）。**
  依赖 1 的可用输出；复用 P0-03～P0-10、[AssessmentPanel](../frontend/src/components/AssessmentPanel.tsx)
  及图组件，完成发育三部分、七族程序、简明缺口、判断定位和对话/报告核查的一致性。
  结果及解释引用已可按精确运行/测量或图版本定位现有证据图节点；缺失或歧义明确提示。
  追加图的五域缺口沿用同一产品仍有效的已有观察，尊重撤销与替代；新增一域不清空其他域的覆盖，
  保留不可用状态与独立验证缺口。
  同一保存案例、固定源码下的测量核对、解释引用、报告及名称更正链路已走查，
  复用原测量与图，历史字节不变；湿实验研究者独立确认与自由文本科学审阅仍按下方清单保留。
- [ ] **3. 处理记录复用与后台准备。**
  依赖 QC 数据视图，复用 P0-01 与 grouping；核对已有 QC/标准化/HVG/PCA 记录、
  输入细胞/基因/参数和表达语义，只补缺失步骤，保留高级设置及筛选影响。
  完成标准：适用旧结果被复用、不适用有原因，raw counts 不覆盖，不重复标准化。
- [ ] **4. 交互 UMAP 组成视图。**
  第一批已接入表达探索、交互着色和分群筛选、完整群计数及原有来源/表格/导出；\n  仍待自动核验已有处理记录适用性，以及五域证据联动。依赖 1、3。
  完成标准：类型/批次/QC/基因切换、组成与证据联动，抽样显示不改变统计分母。
- [ ] **5. 实验批次／方案版本与比较入口。**
  依赖 2；复用现有 ProductCase、session 与比较工具，补关系及持续可见的实验面板。
  完成标准：旧/新方案批次独立保留，版本明确；登记公开 comparator 并确认 cohort；
  各维度分别显示改善/退步/不确定和不可比原因，无综合排名。
- [ ] **6. 样本级组成／差异丰度比较。**
  依赖 1、5 及独立单位记录；优先评估 Pertpy/scCODA，非预先锁定统计模型。
  完成标准：逐样本比例与差值；重复不足/完全混杂仅描述，未知不丢失，
  模型适用性及参考类别选择可追溯；Milo 不因候选清单而自动一并引入。
- [ ] **7. 群 marker 与方案间差异表达。**
  第一批已支持同一 H5AD 内群 marker 和非配对两条件样本比较；跨会话批次关系仍待 5。\n  依赖 3、5；marker 是解释性线索，方案 DE 在同类细胞内按独立样本汇总原始 counts。
  完成标准：复用成熟 Scanpy/DESeq2 类实现，输出效应、适用统计与来源；
  不使用批次整合值冒充 counts，不用细胞级重复给方案效应造显著性。
- [ ] **8. 差异表达后的通路解释。**
  依赖 7；评估 GSEApy 等现成工具/图，沿用知识与资源目录，不另建基因集注册表。
  完成标准：基因集版本、背景/排序、驱动基因和适用统计可追溯，默认重点发现可展开，
  结果进图；同源 DE 与富集不计独立验证，不代替已有七族程序。
- [ ] **9. 经确认的批次整合。**
  依赖 3 和真实批次/方案信息；出现跨批可比性阻断时可优先于 6～8，但仍单独 feature。
  完成标准：先建议、确认后运行，保留前后状态与生物差异、原始表达及高级参数；
  方案与批次完全混杂时不宣称可通过整合消除混杂。
- [ ] **10. 条件性轨迹与分化倾向。**
  依赖 1、3 及可信起点/状态覆盖；先实现一条适用的拟时序路径，再评估 CellRank
  的 PseudotimeKernel 等非 velocity 路径，不同时堆多套轨迹算法。
  完成标准：轨迹/分支/基因趋势、方向依据及限制可读；数据不足不硬连；
  继承同一拟时序的 CellRank 输出不作独立验证，不能推断未覆盖终点或真实移植命运。
- [ ] **11. 空间参考辅助区域证据。**
  依赖 2 与合规、版本化且适用的空间参考；复用区域证据路径。
  完成标准：来源/切片/区域与相依关系明确，辅助参考与产品实测位置分开。
- [ ] **后续可选：LIANA+ 通讯；自有空间数据；移植前后关联。**
  核心评估与比较后，再按真实问题各开独立 feature。复用现有 graft 分析和合适的
  成熟库，不将通讯预测或移植后组成反向升级为移植前安全/疗效结论。

### 方法复用入口与交付纪律

以下为后续实现时的阅读入口，不表示已集成、已定版本或已完成许可审查：

- [Scanpy](https://scanpy.readthedocs.io/en/stable/api.html)：预处理、UMAP、分群与 marker。
- [scAgent](https://github.com/deepmind11/scAgent)：已读 QC 封装与 MIT 许可；
  其他模块逐项审查后再复用，不搬其默认阈值替代本项目合同。
- [CellAgent/scOmni](https://github.com/cellagent659/cellagent)：流程参考；
  未确认复制许可前不直接搬源码，同名项目的目录清单不作为成熟度证据。
- [单细胞 DE 实践](https://www.sc-best-practices.org/conditions/differential-gene-expression/)、
  [PyDESeq2](https://github.com/owkin/PyDESeq2)、
  [Pertpy/scCODA](https://pertpy.scverse.org/en/latest/tutorials/notebooks/sccoda.html)、
  [GSEApy](https://gseapy.readthedocs.io/en/latest/introduction.html)：样本级比较与富集候选。
- [Palantir](https://palantir.readthedocs.io/en/latest/)、
  [CellRank 非 velocity 教程](https://cellrank.readthedocs.io/en/stable/notebooks/tutorials/kernels/300_pseudotime.html)、
  [LIANA+](https://liana.readthedocs.io/en/stable/)：条件性/后续功能候选。

每项交付一条工具结果→证据→用户解释的完整链路，同步 README，定向检查通过后
提交 PR，获授权合并后再做下一项。不为已经通过且未变化的状态增加验证轮次，
不新增仅镜像实现的测试、临时报告或重复计划。只用合成/授权可分享材料入库；
模型配置、内部路径及真实样本仍在受控环境。工程集成、部署和科学资格分别记录。

## Acceptance checklist

- [x] Current Web continuation admits saved P003/P004/P005/P006 observations with
  exact producer/artifact bindings and honest biological-unit semantics.
- [x] Every core domain and all seven programs have a visible measured, missing,
  unavailable or unassessed state; absence is never rendered as zero or opposition.
- [x] Values and dependencies survive graph append/query; old inputs, receipts,
  graph versions and report bytes remain intact.
- [x] Real model/tool feedback updates explanations from evidence within the
  approved scope; invalid or unsupported claims are rejected without losing results.
  Structured action/citation rejection and versioned feedback are checked; expert
  review of biological interpretations remains open. Expression detection rates
  must not be treated as cell-type proportions, and unlike score scales cannot
  be compared by sign to establish biological disagreement.
- [x] Existing figures and method-specific tables match canonical values and
  expose readable labels, sources, limitations and accessible details.
- [ ] Independent wet-lab researcher acceptance confirms the result portrait,
  evidence graph, interpretation wording and report readability. The agent-led
  engineering walk-through does not satisfy this human-review requirement.

## Scientific and operating boundaries

Candidate observations and consistent reports do not establish identity accuracy,
stage compatibility, independent replication, clinical safety/efficacy, release
qualification or a ScoreContract. Domain scores remain null; shared RNA methods
are not independent votes. Scientific work remains in
[product qualification](product-evidence-validation.md) and
[cell-state qualification](p0-02-cell-state-scientific-freeze.md).

Do not repeat valid computation or broaden tests without an affected behavior.
Record exact source/resource versions and unverified boundaries; private sample
values, receipts and paths stay outside Git. Previous release/restart permissions
and deadlines in historical plans are not continuing deployment authorization.

Stable interfaces: [Web](../docs/web-preview.md), [Agent](../docs/agent-integration.md),
[tool guide](../docs/tool-packages.md). Version-bound scientific evidence:
[validation index](../docs/validation/README.md). Completed construction history
remains in Git; this plan contains only integrated scope and outstanding acceptance.
