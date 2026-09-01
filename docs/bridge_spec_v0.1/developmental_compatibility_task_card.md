# BRIDGE P0 Developmental Compatibility 任务卡

| 字段 | 内容 |
| --- | --- |
| Task ID | `TASK-DEVELOPMENT-v0.1` |
| Task document version | `0.4` |
| 日期 | 2026-09-01 |
| Package version | `P0-04 0.4.0` |
| Runtime / scientific state | `implemented` / `candidate shadow` |
| 首个实例 | 移植前 hPSC-derived VM floor-plate/mDA 产品 |
| Current input | checksummed `ProductCase`、`ProductDefinitionCard`、`DevelopmentWindowSpec`、`DevelopmentStateMap`、`MeasurementSpecV2`、`CellStateEvidenceProfileV3`；可选 timepoint series、H5AD 与 `DevelopmentMethodSpec` |
| Current result | `bridge://schemas/developmental-compatibility-result/v0.2` |
| Detailed runtime contract | [P0-04 Tool Card](../../src/bridge/tool_packages/cards/P0-04.md) |

> Package v0.4 keeps stage roles and channel selection external, executes
> transparent reference, program and uncertainty methods, and publishes typed
> data plus three deterministic figures. Ordered sampling-point labels are
> categorical: continuous-time analysis remains unavailable because the current
> contract does not record numeric time, unit and origin. Lineage calibration,
> isolated trajectory methods and `domain_score` remain unavailable.

The current package is a developmental-window and reference-similarity profile,
not a biological-age estimator. It does not convert in-vitro days to GW/PCW,
infer future fate or calibrate OOD. Reference correlation, ordinal support,
window composition and ordered sampling points remain separate evidence families.

## 1. 任务目标与边界

本模块判断待评产品的转录组状态对研究者确认发育窗口的支持程度，并区分窗口前、窗口内、窗口后、分支偏移和未解析状态。v0.4 已封装可调用的透明基线方法，但不制定 0-100 分数。

- 发育相容性是相对于 `ProductDefinitionCard` 的条件化证据，不寻找跨产品通用的最优阶段。
- 人胎 reference 定义生物学状态轴；体外时间序列只用于过程校准和同条件比较。
- 体外 `D` 与体内 `GW/PCW` 分别保存，不能相互换算。
- 目标窗口未确认时仍可输出发育画像，但 `domain_score=null`、`score_state=unavailable`。
- 当前没有疗效、功能或安全性真值，本模块不输出相关结论。

## 2. `DevelopmentWindowSpec`

`ProductDefinitionCard` 必须引用一个版本化 `DevelopmentWindowSpec`。Agent 可以预选模板并展示依据，研究者确认后才能发布窗口相容性结果。

| 模板 ID | 研究问题 | 候选状态范围 | 默认状态 |
| --- | --- | --- | --- |
| `early_patterning_progenitor` | 是否处于早期区域化和底板建立阶段 | 早期 patterning、floor-plate establishment 及相邻状态 | `candidate` |
| `transplantable_mFP_mDA_progenitor` | 是否支持移植用 mFP/mDA progenitor 窗口 | mFP progenitor、mDA-committed progenitor 及经审核的相邻状态 | `default_preselected + freeze_required` |
| `immature_mDA` | 是否进入未成熟 mDA 神经元阶段 | immature mDA 及经审核的过渡状态 | `candidate` |

每个窗口至少记录：`window_spec_id`、目标产品、允许的内部状态、`earlier/within/later/branch_shift` 映射、适用 assay、reference snapshot、依据、reviewer、确认时间和版本。具体状态角色必须经发育生物学审核，不能仅由 marker 或标签名称自动生成。

## 3. 输入与当前资产

### 3.1 必要输入

- 已确认的 `ProductDefinitionCard` 和 `DevelopmentWindowSpec`。
- `all_cells_view` 与可用时的 `eligible_cells_view`。
- Cell-State soft assignment、prediction set、unknown/OOD 和方法分歧。
- sample、preparation、batch、cell line/donor、biological replicate 与真实 `D/Stage`。
- 冻结的 expression/count view、内部 `DevelopmentStateMap`、reference 与方法版本。

### 3.2 当前可用资产

| 资产 | 主要内容 | 本模块用途 | 关键限制 |
| --- | --- | --- | --- |
| Chen vMB scRNA reference | GW7/8/9/12/16/20；61,455 cells | 早中期状态轴 | 与 snRNA reference 的胎龄不重叠完整 |
| Chen vMB snRNA reference | GW14/16/18/20/24/25；87,467 nuclei | 中晚期状态轴 | assay 与胎龄耦合 |
| Chen neurogenesis derived set | GW7-GW25；83,017 profiles | 状态、阶段和历史轨迹候选 | 派生对象，不作独立证据重复计数 |
| La Manno VM reference | PCW6-11；1,977 cells | 独立来源敏感性 | 规模小、平台较旧 |
| 体外 mDA 时间序列 | D0-D120 的多研究 2D/3D 数据 | 真实时间趋势和过程比较 | 方案、cell line、平台及重复结构不同 |
| SISBAR lineage assets | 三个相邻阶段的独立 split-barcoding 实验 | 轨迹方法校准 | 不能拼成一条连续克隆轨迹 |
| sealed competitor test | D16/D25/D40 | 冻结后外部测试 | 不进入 reference、prior、方法选择或阈值调整 |

完整数据条目、规模、角色和状态由 tracked
[Data/Reference Registry](data_reference_registry.md) 维护。仓库外归档工作簿不是运行合同。

## 4. 分析流程

```mermaid
flowchart LR
    A["确认 ProductCase 与发育窗口"] --> B["读取冻结的 Cell-State evidence"]
    B --> C["双分母阶段组成"]
    B --> D["分来源与分模态 reference-stage support"]
    B --> E{"是否存在真实多时间点"}
    E -->|否| F["static_profile；动态证据 not_assessed"]
    E -->|是| G["descriptive_timecourse；inferential unavailable"]
    C --> I["方法与 reference 敏感性"]
    D --> I
    F --> I
    G --> I
    I --> J["DevelopmentalCompatibilityProfile"]
    K["SISBAR 独立校准轨"] --> L["LineageCalibrationRecord"]
```

## 5. 方法组合

v0.4 的 `DevelopmentMethodSpec` 以版本化外部对象选择 reference profile、
reference label 的角色/顺序、program card、采样点顺序和方法。当前直接执行
`DEV-PSEUDOBULK-CORR`、`DEV-ORDINAL`、`DEV-PROGRAM`、
`DEV-BOOTSTRAP`；运行结果记录软件版本、覆盖度、独立单位和 reason code。
`TIME-PROGRAM` 和 `TIME-GAM-PY` 保留为兼容性枚举，但在数值时间合同形成
前返回 typed `not_assessed`。

### 5.1 窗口组成

- 读取 Cell-State soft composition，并按 `DevelopmentStateMap` 聚合为 `earlier`、`within_window`、`later`、`branch_shift` 和 `unresolved`。
- 主分母为 target-related cells；同时报告全部 eligible product cells 的组成，不能只展示富集后的目标子集。
- 当前输出为精确 numerator、denominator 和 fraction，不发布组成区间。
- `branch_shift` 与 `unresolved` 不属于 earlier → within-window → later 连续轴。

### 5.2 Reference-stage support

- 对每个 sample/preparation 构建 pseudobulk，并分别对每个 reference source 与 modality 计算阶段支持分布。
- source-aware ordinal classifier 作为独立阶段映射通道。v0.4 不在运行时完成
  校准或 held-out benchmark；只有外部、版本化、已审核且通过的
  source-group-held-out evidence receipt 精确绑定所有选定 profile 和至少两个
  source 时才执行，否则返回 typed `not_assessed`。
- 当前输出每个分析单位、来源和 assay 的 top label、runner-up、Spearman/cosine similarity、margin 和 shared genes；不输出完整阶段支持分布或最高支持区间。
- RAPToR 作为 `shadow` 候选，必须使用 BRIDGE 自有 reference 重新验证后才可解释。
- v0.4 直接执行 sample/preparation pseudobulk 的 Spearman/cosine 支持，以及
  scikit-learn 累积二分类 logistic ordinal baseline。ordinal 输出明确标记为
  `uncalibrated_baseline` 并引用 gate receipt；两者均只输出 reference
  support，不作胎龄换算。
- 任一选定 profile 覆盖不足，或同一 analysis unit 在不同 source/assay 的
  top stage role 不一致时，该 unit 的综合 reference support 为 `unavailable`；
  分来源记录仍保留用于审计，不进行平均或静默补齐。

### 5.3 有序采样点

- 当前接口按外部提供的 sampling-point ID、顺序和标签展示聚合阶段组成。
- `timepoint_order` 只用于确定类别顺序，不能作为连续数值时间进入拟合。
- 缺少数值时间、单位、起算基准或逐独立样本观测时，连续趋势统一返回
  `not_assessed`；pseudotime 不能替代实验时间。
- 后续若增加数值时间合同，模型单位必须是 sample/preparation，不是 cell，
  且原始点必须与描述性拟合同时展示。

### 5.4 轨迹与转变方法

DPT/PAGA、Palantir、Slingshot、VIA、CellRank、moscot/WOT、tradeSeq、CellAlign、TrAGEDy 和 scVelo 纳入方法目录，但初始状态为 `benchmark`、`conditional` 或 `shadow`。它们可用于方向、分支、动态程序或跨时间耦合的校验，不默认进入正式 Developmental Compatibility 指标。

现有 DPT、Palantir 和 CellRank 产物登记为 `historical_candidate`。由于 scRNA/snRNA 与胎龄耦合，并且 root/terminal state 含人工设定，必须重新按冻结合同验证。

### 5.5 SISBAR 校准轨

- Adapter 将表达对象与 `Cell.Barcode`、`Virus.Barcode`、`Cluster.Id` lineage 表显式连接。
- Stage I-II、II-III、III-IV 是三个独立实验；每个 experiment/replicate 单独生成 observed transition matrix。
- 输出 clone coverage、barcode multiplicity、匹配率、转变矩阵和不确定性；禁止跨实验拼接克隆。
- SISBAR 只用于评测轨迹方法和构建有适用性门槛的 transition prior，不进入普通产品的正式域结果。
- CoSpar 是 lineage/state 联合分析的 `shadow` 候选。普通产品没有 lineage barcode 时，不输出克隆命运结论。

## 6. 输出合同

### 6.1 `DevelopmentalCompatibilityProfile`

| 字段 | 含义 |
| --- | --- |
| `analysis_mode` | `static_profile` / `descriptive_timecourse`；v0.4 不产生 `inferential_timecourse` |
| `window_spec_id` | 研究者确认的窗口、版本和确认记录 |
| `target_related_denominator` | target-related cells/weights、数量与视图 |
| `whole_product_denominator` | 全部 eligible product cells、数量与视图 |
| `stage_fractions` | 两套分母下的 earlier、window、later、branch-shift、unresolved 精确计数与比例 |
| `reference_stage_support` | method-bundle binding 与可用性状态 |
| `method bundle` | 分 source/assay 的 top-stage similarity、runner-up、margin、覆盖度及方法状态 |
| `timecourse_profile` | 按外部采样点顺序聚合的双分母组成与独立组数量 |
| `sensitivity` | reference、modality、preprocessing、方法和 QC view 敏感性 |
| `evidence_state` | `available` / `shadow` / `unavailable` |
| `domain_score` | 固定为 `null`，等待独立 `ScoreContract` |
| `provenance` | Card、window、tool、reference、environment、参数和 Evidence ID |

### 6.2 `LineageCalibrationRecord`

保存 experiment、replicate、相邻 stage pair、barcode join 结果、clone coverage、multiplicity、observed transition matrix、方法预测、edge recovery、方向一致性、校准度和 provenance。它与普通产品 profile 分库存储。

## 7. 运行环境

| 环境 | 用途 | 当前状态 |
| --- | --- | --- |
| `ENV-DEVELOPMENT-PY-v0.2` | composition、pseudobulk、scikit-learn、decoupler、Matplotlib | `health_check_passed`；v0.4 执行环境 |
| `ENV-DEVELOPMENT-CELLRANK-v0.1` | CellRank 条件性轨迹验证 | `proposed_conditional` |
| `ENV-DEVELOPMENT-VELOCITY-v0.1` | RNA velocity 研究性验证 | `proposed_exploratory`；独立冻结稳定版本 |
| `ENV-DEVELOPMENT-VIA-v0.1` | VIA shadow benchmark | `proposed_shadow` |
| `ENV-DEVELOPMENT-BIOC-v0.1` | Slingshot、tradeSeq、speckle/propeller、RAPToR | `proposed_isolated` |
| `ENV-DEVELOPMENT-OT-v0.1` | moscot/JAX 隔离运行 | `proposed_isolated` |
| `ENV-DEVELOPMENT-LINEAGE-v0.1` | SISBAR adapter 与 CoSpar | `proposed_isolated` |

这些工具不应全部混装在一个环境。Python core、R/Bioconductor、JAX/OT、lineage 和 velocity 分别冻结，环境间只交换版本化 h5ad/Parquet/TSV、矩阵和 JSON manifest。

## 8. Web 必备可视化

- 双分母阶段画像，显示精确计数、各自分母，并将 `branch_shift` 和
  `unresolved` 与有序阶段分开。
- 分 reference source/assay 的 top-stage similarity summary，直接显示
  runner-up、margin、shared genes、冲突和 unavailable；不称概率或年龄。
- 按外部声明顺序排列的聚合采样点组成；单采样点和缺少数值时间轴时明确显示
  连续动态证据 `not_assessed`。
- 完整 stage-support heatmap、发育程序参考包络、逐样本趋势、方法敏感性和
  SISBAR transition 仍为后续合同，不在当前图形中暗示已实现。

每张正式图绑定 Evidence ID、输入版本、分母、单位、窗口、reference、方法和缺失状态。单时间点界面必须明确显示动态证据 `not_assessed`。

## 9. 拒答与降级规则

- `DevelopmentWindowSpec` 未确认：只输出候选发育画像，不发布窗口相容性结论。
- Cell-State evidence 不可用或 target-related 分母不足：相应组成返回 `unavailable`。
- 单时间点：`analysis_mode=static_profile`，不输出时间进展或转变证据。
- 无足够独立重复：最多 `descriptive_timecourse`，细胞数不能代替 biological replicate。
- 缺少数值实验时间、单位或起算基准：连续时间方法返回 `not_assessed`。
- ordinal 缺少通过审核且精确绑定的 source-group-held-out receipt：该方法
  `not_assessed`，不得把运行内拟合解释为已校准预测。
- reference profile 覆盖不足或 source/modality 的 top stage role 冲突：
  对应 analysis unit 为 `unavailable`，不得用可用 source 静默补齐。
- 缺少 lineage barcode：不输出克隆关系、命运或 observed transition。
- sealed competitor test 不参与任何方法选择、reference 构建、prior 或阈值调整。

## 10. Benchmark 与冻结要求

| 验证项 | 最低要求 |
| --- | --- |
| 数据拆分 | source、donor、lab、cell line 和 modality holdout；禁止 cell-level random split 充当外部验证 |
| 阶段与窗口 | leave-one-timepoint-out、leave-one-state-out，以及早/窗内/晚/branch/OOD 混合测试 |
| 稳健性 | cell/gene 下采样、reference swap、modality split、preprocessing/QC view 和随机种子敏感性 |
| 时间序列 | 单时间点正确降级；重复不足不发布 inferential 结果；样本层模型不把 cell 当重复 |
| SISBAR adapter | barcode 唯一性、join rate、experiment/replicate 隔离和 observed transition 重建 |
| 轨迹校准 | 对 SISBAR observed transitions 评测 edge recovery、方向一致性与校准度 |
| 数据隔离 | sealed competitor test 到 reference、prior、训练、调参和阈值的数据流为零 |
| 工程冻结 | tool、environment、window、reference、MeasurementSpec、参数、seed、schema 和验收阈值均版本化 |

未通过验证的方法保持 `candidate`、`conditional`、`shadow` 或 `historical_candidate`。只有冻结方法才能写入正式 Evidence Graph。

## 11. 主要官方来源

- Scanpy DPT/PAGA: https://scanpy.readthedocs.io/en/stable/generated/scanpy.tl.dpt.html ; https://scanpy.readthedocs.io/en/stable/generated/scanpy.tl.paga.html
- Palantir: https://palantir.readthedocs.io/
- CellRank RealTimeKernel: https://cellrank.readthedocs.io/en/stable/api/_autosummary/kernels/cellrank.kernels.RealTimeKernel.html
- scVelo: https://scvelo.readthedocs.io/
- Slingshot / tradeSeq: https://bioconductor.org/packages/slingshot/ ; https://bioconductor.org/packages/tradeSeq/
- speckle/propeller: https://bioconductor.org/packages/speckle/
- scCODA: https://pertpy.readthedocs.io/en/latest/tutorials/notebooks/sccoda.html
- RAPToR: https://github.com/LBMC/RAPToR ; https://www.nature.com/articles/s41592-022-01540-0
- moscot / WOT: https://moscot.readthedocs.io/en/stable/ ; https://github.com/broadinstitute/wot
- VIA: https://github.com/ShobiStassen/VIA
- CellAlign / TrAGEDy: https://www.nature.com/articles/nmeth.4628 ; https://github.com/No2Ross/TrAGEDy
- SISBAR / GSE221592: https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE221592 ; https://www.sciencedirect.com/science/article/pii/S1934590923000449
- CoSpar: https://cospar.readthedocs.io/en/latest/
