# Product Evidence Qualification

**Status:** awaiting_qualified_product_evidence.
**Goal:** Determine which transcriptomic observations support the intended
product identity, developmental window and process claims.

## Current boundary

The private interface can carry candidate observations into a versioned evidence
graph and a claim-checked research report. This engineering path does not qualify
the underlying method or product. Exact acceptance scope is tracked in the
[mainline plan](step7-evidence-coordinator.md) and
[validation records](../docs/validation/README.md).

Protocol intent, user-confirmed facts, source labels and exploratory cycle
measurements remain distinct from observed batch execution, validated identity,
independent replication and formal product evidence.

## Remaining scientific work

- [ ] Resolve the [cell-state method qualification](p0-02-cell-state-scientific-freeze.md)
  before promoting candidate labels to product identity.
- [ ] Bind the intended VM/mDA progenitor and early-neuroblast roles to
  source-supported identity criteria. Evaluate developmental compatibility
  independently; culture duration is not fetal age.
- [ ] Establish genuine preparation/sample/capture and biological-unit records,
  including pooling and cross-timepoint relationships where needed. Unknown
  independence remains unknown.
- [ ] Review product-specific programs, their positive and negative evidence,
  feature coverage and measurement units. The packaged Seurat cycle resource
  supports exploratory phase observations, not all process axes or division rate.
- [ ] Validate applicable target/regional, developmental, whole-product and
  source-bound process modes on the exact selected DataView and denominators.
  Unmeasured or filtered genes cannot supply negative evidence.
- [ ] Establish independent product-specific claim and score requirements before
  any qualified report or public export. Until then, domain scores remain null.
- [ ] Supply genuine comparable product arms and authorized linked graft data
  when those questions are in scope. Graft evidence remains post-transplant and
  does not backfill pre-transplant scores or training.

<a id="mdapro-genitor-review"></a>

## mDA 祖细胞产品定义：来源审阅草案

**范围：** hPSC 来源、中脑多巴胺能祖细胞／前体产品。以下是待科学负责人审阅的
依据与实现缺口，不是可执行角色映射、合格标准或新的测量结果。现有
[产品上下文草案](../src/bridge/tool_packages/p0_02_cell_state/resources/product_context_review_draft.yaml)
继续保持 `pending` / `execution_allowed: false`；
[v1.1 来源审阅](../src/bridge/tool_packages/p0_02_cell_state/resources/development_review_v1_1.json)
的 `parent_only` 和 `role_unresolved` 不因本文自动升级。

### 原始依据与可复用范围

| 来源 | 支持的判断 | 不应直接搬用 |
|---|---|---|
| [Kirkeby et al., 2017](https://doi.org/10.1016/j.stem.2016.09.004) | 常用腹侧底板标志不足以单独预测移植物结果；区域身份需要更细证据 | 不将 FOXA2/LMX1A/CORIN 阳性直接等同于合格 mDA 祖细胞，也不移植论文阈值作为放行标准 |
| [Xu et al., 2022](https://www.jci.org/articles/view/156768) | 区分早／晚 mDA 祖细胞与 DA 神经元；LMX1A、FOXA2、EN1、OTX2 的联合背景以及 CLSTN2／PTPRO 的阶段相关证据可供策展 | 特定方案的培养日不能换算人体发育年龄；候选标志不是通用逐细胞阈值，动物移植结果不是本产品安全性证明 |
| [La Manno et al., 2016](https://doi.org/10.1016/j.cell.2016.09.027) | 人体发育参考支持祖细胞、神经母细胞和 DA 神经元阶段的区分 | 已有参考来源不是新增独立验证；不能按标签相似性把现有 RG/Nb 亚类直接重命名为该图谱状态 |

已阅读 Xu 作者仓库的
[README](https://github.com/MichaelPeibo/mDA-time-course-scRNA-seq/blob/ab3df1839833ea235497ec1508533c34ddfffa52/README.md)、
[Seurat 分析](https://github.com/MichaelPeibo/mDA-time-course-scRNA-seq/blob/ab3df1839833ea235497ec1508533c34ddfffa52/Methods_seurat_scripts.R)
及 [MetaNeighbor 比较](https://github.com/MichaelPeibo/mDA-time-course-scRNA-seq/blob/ab3df1839833ea235497ec1508533c34ddfffa52/metaneighbour/metaneighbour_with_manno_woday51.R)。
代码分别提取早／晚祖细胞 marker，并将神经元与祖细胞分开进行参考比较。
可复用的是分层问题和方法依据；原脚本含特定数据的 cluster 排除、QC 阈值和环境依赖，
不能原样作为 BRIDGE 的通用注释器。该提交树未见 LICENSE，本次不复制代码或数据。
数据编号以论文 Data availability 为准：GSE204795、GSE204796；仓库 README 重复写了前者。
纳入资源前仍须核对许可、预处理及与已有 reference 的重叠，不能默认属于独立验证集。

### 待审阅的角色与阶段解释

下表是产品层推断建议，不是论文提供的现成标签映射。marker 需按现有测量规范计算
覆盖与联合程序证据；不得临时改成“任一基因表达大于零”或以掉零代替反证。

| 现有观测或候选类别 | 当前可说什么 | 成为产品角色所缺内容 |
|---|---|---|
| 中脑腹侧底板／mDA 谱系证据与祖细胞／前体程序一致 | 候选目标定义；身份、区域与阶段分别保留依据 | 将上述来源落实到具体状态、测量规范、适用范围与经审阅的角色；目前尚无可直接导入的正式映射 |
| L1 Radial_Glia、Neuroblast、Glioblast | 粗粒度组成，不能整类计为 mDA 祖细胞 | mDA 限定性证据与竞争区域／谱系证据，不能只凭神经前体身份 |
| RG_mFP、RG_mBMP、RG_mBIP、Nb_mFP、Nb_mBMP、Nb_mBIP、Nb_mAP | 现有审阅仅支持父级判断，继续未确定 | 亚类定义、来源一致性与身份依据；补代码计数也不会解除 `parent_only` |
| L1 Neuron_DA | DA 神经元家族线索，不自动等于祖细胞目标 | 中脑区域与早／晚阶段证据；是否将早期 DA 神经元视为可接受相邻状态需产品负责人确认 |
| 有支持的其他神经元、胶质或血管谱系 | 可审阅为与本目标不符的组成，不等于有害 | 可靠身份与本产品角色映射；来源候选标签不能直接成为确证非目标细胞 |
| 冲突、未知、参考外、未测量 | 各自保留，说明覆盖缺口 | 不补零、不并入非目标；应激／周期也不单独决定身份角色 |

发育窗口本轮只界定为待确认的祖细胞／前体范围，不指定胎龄数值。
需另行绑定来源阶段及其年龄定义、映射方法与不确定性；不能用培养天数或
`Neuron_DA` 一个粗标签判定符合窗口，更不能据此预测所有后续分化去向。

### 代码已具备什么，仍缺什么

来源审阅以 `82d1fb6` 为基线；分层视图及计数事实已随 P0-02 0.6.2 更新：

- [composition_records_v3](../src/bridge/tool_packages/p0_02_cell_state/metrics.py)
  只接受 L1，分母绑定完整 selected DataView；已有 L2 分层计算尚未进入该 V3 composition。
- [分层产物生成](../src/bridge/tool_packages/p0_02_cell_state/executor.py)
  在 0.6.2 复用 V3 的 selected DataView 标识与输入文件哈希，校验父子计数，
  并在组成表标记不重叠的合计行。原 `input_hash` 也是输入文件校验和，并非运行哈希；
  此修正不将 L2 接入产品角色核算，也不改变科学映射。
- [全产品计数合同](../src/bridge/tool_packages/p0_05_off_target_control/models.py)
  明确只接受 canonical L1 整批分母，并对 `consensus_supported_only` 聚合角色。
  [目标评估](../src/bridge/tool_packages/p0_03_target_regional/executor.py) 同样消费 V3 composition。
  因此仅审阅细分角色，不能直接得到整批 mDA 祖细胞比例。相似度和程序证据仍可提供
  描述性支持，但不是目标细胞计数的替代物。

下一增量先确认哪些具体状态确有来源支持；若需要 L2，复用现有分层结果补齐
**细分状态到整批产品的角色核算**：绑定准确 selected DataView、父类可细分范围、
子类计数、整批分母及未确定部分，再由现有目标评估、组成和证据图消费。
不得将 L1 与其 L2 子类重复相加，不以子集比例冒充整批比例，不重做细胞分类。
任何接口／Schema 变化仍需按现有合同版本化。科学映射和计数接线是两个独立完成条件。

完成标准是同一已保存输入上数值与分母可追溯、未确定部分保留、研究者能读懂
“哪些支持目标、哪些不符、哪些还不知道”。角色定义和独立验证是科学资格要求；
诚实保留未判定状态的单产品工程闭环可以先行验收，不能用工程验收补齐科学缺口。
不会因为本文、CI 或角色审批通过，就宣称科学资格或移植适用性已经成立。

## Acceptance

Each newly claimed mode needs source-bound scientific inputs, genuine measurements
and an observed user flow. Research-report verification establishes consistency
with those inputs, not efficacy, safety, validated potency or GMP release.
QC limitations remain explicit; a small doublet prediction is not proof of
complete removal, and missing raw droplets leave ambient/cell-calling questions
unassessed. Historical inputs and receipts remain immutable.
