# BRIDGE P0 Target Identity 与 Regional Fidelity 任务卡

| 字段 | 内容 |
| --- | --- |
| Task ID | `TASK-TARGET-IDENTITY-v0.1`；`TASK-REGIONAL-FIDELITY-v0.1` |
| 文档版本 | `0.4 visualization candidate update` |
| 日期 | 2026-09-01 |
| 状态 | `candidate` |
| 首个实例 | 移植前 hPSC-derived VM floor-plate/mDA progenitor |
| 上游输入 | 11 个 checksummed 核心 JSON；表达模式另加 1 个 analysis-ready H5AD 与 1 个 `TargetRegionalMethodSpec` |
| 主要输出 | `TargetRegionalEvidenceResult`、3 类 `MeasurementResultV2`、typed visualization data 与 artifact set；表达模式另加 `TargetRegionalMethodBundle` |

## 0. 当前可执行候选

P0-03 v0.4.0 提供两个兼容入口：

- **聚合模式**：读取 11 个 checksummed JSON，发布三个分母明确的
  `MeasurementResultV2` 与 `TargetRegionalEvidenceResult`。
- **表达模式**：在同一合同上增加 QC-selected H5AD 和
  `TargetRegionalMethodSpec`，执行 target/regional pseudobulk correlation、
  target NNLS、target/regional decoupler ULM、independence-group bootstrap、
  cross-reference 与 scRNA/snRNA sensitivity，并发布
  `TargetRegionalMethodBundle`。

两套 reference 集合、program card、coverage minima、状态角色和区域集合均由
版本化输入给出。代码不包含具体状态名、marker、产品阈值或固定正向角色。下文
PD-mDA 内容仍是待审核科学候选，改变生物学定义时应更新输入对象而非执行器。

表达模式还要求调用方声明版本化的表达语义合同；该合同把 query、reference、
归一化/变换和基因标识命名空间绑定为一个可审核的可比性声明。`REG-MODALITY`
只比较显式匹配的 feature view 与 context group，不再以 assay 名不同代替匹配设计。
NNLS 的 relative L2 residual 上限同样来自外部 applicability contract；缺少合同或
超过上限时返回 typed `not_assessed`/`unknown`，不把系数送入 bootstrap。

表达矩阵中的 observation IDs 必须与 P0-01/P0-02 DataView 及
`BiologicalUnitAssignmentArtifact` 完全一致。Pseudobulk 按其中的
`analysis_unit_ref` 聚合；bootstrap 按 `independence_group_ref` 重采样。只有
一个独立单位时只发布 `descriptive_only`，不伪造区间。

上游 `unknown`/`ood`、缺失映射和零分母仍保持 typed
`not_assessed`/`unavailable`，不得补零。旧 Cell-State v0.1/v0.2 profile 不是
兼容入口。

空间投射尚未进入本版本。所有数值仍为 `shadow`，`domain_score=null`；真实
方法可执行不等于 reference、program 或产品结论已经过生物学验证。

v0.4.0 同时从同一 typed data object 生成两类正式图形：完整产品的角色及具名区域
状态组成，以及按 target identity / regional fidelity、reference source 和 assay
分开的表达支持矩阵。图、精确 TSV 与 JSON 绑定同一 hash；未评估、部分可用和
草案审核状态不会被隐藏。相关性只表示 reference-conditioned expression support，
不称为身份概率，也不生成胎儿组织坐标。

## 1. 任务目标

本模块把 Cell-State 的状态证据解释为两个独立的产品评估问题：

- **Target Identity**：完整制剂中有多少细胞支持 ProductDefinitionCard 声明的目标细胞身份。
- **Regional Fidelity**：目标相关细胞是否支持预期的腹侧中脑/底板区域身份，主要偏移到哪里。

两项任务合并交付，但分别保存分母、raw metrics、不确定性和证据状态。当前阶段只整理并验证方法，不制定 0-100 分数或阈值。

## 2. 评估边界

- Cell-State 模块负责生成 prediction set、连续权重、方法分歧和 unknown；本模块负责依据 ProductDefinitionCard 解释这些证据。
- Target Identity 分母来自所选 P0-02 composition channel，并由输入记录显式携带。
- Regional Fidelity 分母由 `TargetRegionalAssessmentSpec` 指定的 state-ID 集合组成；同时单列完整制剂中的区域支持比例。
- 区域身份、细胞谱系和发育阶段分别判断。体外分化日不能自动换算为 GW/PCW。
- 体外产品 scRNA 投射到人胚空间参考称为 **Spatial Reference Projection**，不表示产品具有真实组织空间结构。
- 非目标细胞和异常状态传递给 Off-target Control 与 Proliferation & Stress Response，不在本模块重复定义。
- 输出仅表示转录组证据相容性，不表示临床疗效、安全性、potency、GMP 放行或绝对产品优劣。

## 3. 当前 Reference

| Reference | 数据与范围 | 本模块用途 | 当前状态与限制 |
| --- | --- | --- | --- |
| `REF-CHEN-VMB-SC-v1` | scRNA-seq；GW7/8/9/12/16/20；人腹侧中脑；61,455 cells | 早期 target、区域和邻近状态 | `freeze_required`；需冻结 annotation 与样本表 |
| `REF-CHEN-VMB-SN-v1` | snRNA-seq；GW14/16/18/20/24/25；人腹侧中脑；87,467 nuclei | 中晚期神经元和 DA 状态 | sc/sn 与胎龄耦合，需模态敏感性分析 |
| `REF-CHEN-RGNB-v1` | Chen reference 派生 RG/Nb 子集；14 states；15,095 profiles | mFP、mBMP、mBIP 及间脑状态 | 派生对象，不作为独立证据重复计数 |
| `REF-LAMANNO-2016-v1` | scRNA-seq；PCW6-11；人胎腹侧中脑；1,977 cells | 独立 VM sensitivity reference | 平台较旧、规模较小 |
| `REF-BRAUN-2023-v1` | scRNA-seq；PCW5-14；第一孕期全脑 | forebrain/midbrain/hindbrain 区域背景 | 全脑 reference 不能替代 VM 产品定义 |
| `REF-ZENG-2023-v1` | scRNA-seq；PCW3-12；全胚、全头和全脑 | 早期区域与非神经背景 | 区域标签与版本仍需冻结 |
| `REF-SPATIAL-HEB58-ANNOT-v0.1-draft` | Visium HD segmented profiles；GW7 人胚中脑；2 sections；385,361 profiles、18,085 genes、20 个最终标签 | 空间 marker、区域锚定和投射 benchmark | `available + freeze_required`；两张切片来自同一胚胎，不能作为两个生物重复 |
| `REF-SPATIAL-CHEN-CS-v1` | 计划中的冠状/矢状空间数据；单时间点 | 后续切面和 ROI 稳健性 | `pending_data` |

`REF-SPATIAL-HEB58-ANNOT-v0.1-draft` 的最终 `cell_type` 覆盖中脑 FP/BP/AP/RP、MHB、后脑、前脑/间脑及非神经状态。对象同时保留两套模型初注释和人工空间修订标签；正式冻结前需补齐标签定义、人工修订记录、切片方向、ROI、处理版本和 checksum。

## 4. ProductDefinitionCard、共享 StateRoleMap 与区域集合

P0-03 复用 P0-05 唯一的 `StateRoleMap` Schema，不在本模块重复定义同 URI
合同。产品角色与区域归属仍是两个外部审核轴：

| 外部对象 | 责任 |
| --- | --- |
| `StateRoleMap.product_role` | `target` / `acceptable_adjacent` / `known_off_target` / `role_unresolved` |
| `TargetRegionalAssessmentSpec` | 绑定 StateRoleMap ref/checksum，并显式列出区域分子、区域分母与 whole-product 区域 state IDs |
| Developmental Compatibility | 单独判断 stage，不写入 StateRoleMap |
| Proliferation & Stress Response | 单独判断 process，不写入 StateRoleMap |

首张 Card 的候选逻辑为：`RG_mFP`、`Nb_mFP` 和早期/成熟 `Neuron_DA` 分别报告，不合并成一个目标比例；mFP progenitor 提供主要 target/region 支持，`Nb_mFP` 和早期 DA 状态是否属于 target 或 `acceptable_adjacent` 由研究者确认。`mBMP/mBIP`、AP、MHB、前脑、间脑和后脑先作为待核实的区域状态或偏移方向，不依据标签名称直接冻结角色。所有映射必须经生物学审核，文献 marker 不能单独决定角色。

## 5. 分析流程

```mermaid
flowchart LR
    A["QC 合格的产品与样本层级"] --> B["确认 ProductDefinitionCard、StateRoleMap 与 assessment spec"]
    B --> C["读取冻结的 Cell-State evidence"]
    C --> D["Target Identity：完整制剂 soft composition"]
    C --> E["Regional Fidelity：target-related 区域证据"]
    E --> F{"空间 reference 是否适用"}
    F -->|是| G["Spatial Reference Projection"]
    F -->|否| H["记录 unavailable 与原因"]
    D --> I["Evidence Graph 去重与冲突协调"]
    E --> I
    G --> I
    H --> I
    I --> J["Profiles、Web 图表与证据缺口"]
```

## 6. Target Identity 工具组合

表中短 ID 来自主目录的 `tool_id`，运行时作为 method selector；Tool Package
Spec 使用知识快照中的规范化 `METHOD-*` ID，二者通过 catalog alias 对应。


| 能力 | 方法 ID / 软件 | 当前调用位置 | 输出 |
| --- | --- | --- | --- |
| 状态角色与组成 | `TRG-ROLEMAP` / soft composition | P0-03 聚合模式直接执行 | target/adjacent/unresolved 分母与比例 |
| Target reference similarity | `TRG-PBCORR` | P0-03 表达模式直接执行 | Spearman/cosine、margin、shared genes |
| 连续身份 | `TRG-NNLS` / SciPy | P0-03 表达模式直接执行 | state weights、relative L2 residual 与 applicability state |
| Signed program | `TRG-DECOUPLER` / decoupler ULM | P0-03 表达模式直接执行 | activity、p-value 与 marker coverage |
| 不确定性 | `TRG-BOOTSTRAP` | P0-03 表达模式直接执行 | independence-group interval 或 `descriptive_only` |
| 分类/映射/open-set | CellTypist、scANVI、SingleR、scmap、Symphony、scConform | P0-02 benchmark adapter；P0-03 只消费其已绑定 evidence | prediction、similarity、mapping 与 abstention evidence |
| 其他候选 | UCell、AUCell、popV、scArches | catalog only；本版本不直接执行 | 尚无 P0-03 runtime artifact |

共享 marker、reference 或训练数据的方法归入同一 evidence family，不按工具数量重复加权。

## 7. Regional Fidelity 工具组合

### 7.1 转录组区域证据

| 能力 | 方法 ID / 软件 | 当前调用位置 | 输出 |
| --- | --- | --- | --- |
| Regional role aggregation | `REG-ROLEMAP` | P0-03 聚合模式直接执行 | target-region 与 whole-product 比例 |
| Regional reference similarity | `REG-PBCORR` | P0-03 表达模式直接执行 | label support、margin、shared genes |
| Signed regional program | `REG-DECOUPLER` / decoupler ULM | P0-03 表达模式直接执行 | activity 与 coverage |
| Reference robustness | `REG-CROSSREF` | P0-03 表达模式直接执行 | label agreement 与 support range |
| Modality robustness | `REG-MODALITY` | P0-03 表达模式直接执行 | declared matched-group agreement 或 typed refusal |
| 分类、映射与 open-set | CellTypist、scANVI、SingleR、Symphony、scConform | P0-02 benchmark adapter；P0-03 消费已绑定 evidence | regional prediction/mapping evidence |
| Ontology crosswalk | UBERON/HsapDv | catalog only；当前不执行 | 尚无 runtime artifact |

区域偏移必须报告具体方向；reference coverage 不足时返回 `unknown` 或
`unavailable`。

### 7.2 Spatial Reference Projection

| 方法 | 在 BRIDGE 中的候选角色 | 关键限制 |
| --- | --- | --- |
| BRIDGE correlation/cosine/kNN baseline | 透明的 cell/state-to-spatial-profile 基线 | 需做 shared-gene、distance 和 OOD gate |
| Tangram | 直接空间投射首轮候选；输出 cell/cluster-to-location probability | 官方要求 sc/sn 与空间数据来自相同组织/区域；跨样本产品投射需严格适用性检查 |
| SpaOTsc | optimal transport 独立校验候选 | 依赖较旧，需隔离环境；映射质量必须单独验证 |
| CellTrek | R/Seurat cell charting benchmark | 共嵌入和参数敏感性需测试；不默认优于透明基线 |
| CytoSPACE | optimization-based assignment benchmark | hard assignment 可能强制映射 OOD 细胞，必须设置拒答/残差通道 |
| cell2location | 空间 reference 构建、注释与区域 abundance 校验 | 主要解决空间数据的 cell-type abundance，不作为产品细胞直接坐标投射主方法 |
| SpatialData / Squidpy | 空间对象管理、邻域/marker/ROI 质控和可视化 | 属于 reference QC，不单独证明产品区域身份 |

Web 可以突出展示 cell-level 投射图；正式可比较 raw metrics 先按 sample/state 聚合，并同时显示拟合质量和不确定性。

## 8. 输出合同

### 8.1 `TargetIdentityProfile`

| 字段 | 含义 |
| --- | --- |
| `denominator` | 全部 eligible product cells 及数量 |
| `target_soft_fraction` | target 权重之和/分母 |
| `acceptable_adjacent_soft_fraction` | acceptable adjacent 权重之和/分母 |
| `unresolved_fraction` | unknown、ambiguous 或 Card 未映射部分 |
| `interval` | sample-preserving bootstrap 或预注册等价区间 |
| `method_evidence` | 各独立 evidence family 的原始输出 |
| `evidence_state` | `available` / `negative` / `unknown` / `missing` / `unavailable` / `shadow` |

### 8.2 `RegionalFidelityProfile`

| 字段 | 含义 |
| --- | --- |
| `target_related_denominator` | target + acceptable adjacent 细胞/权重 |
| `target_region_soft_fraction` | target region 权重/target-related 分母 |
| `acceptable_region_soft_fraction` | 邻近可接受区域权重/target-related 分母 |
| `regional_shift_profile` | 前脑、间脑、MHB、后脑等偏移方向及权重 |
| `whole_product_target_region_support` | target region 权重/全部 eligible cells；单列展示 |
| `reference_sensitivity` | reference、模态、预处理和方法切换后的结果变化 |
| `evidence_state` | 与 Target Identity 相同的证据状态枚举 |

### 8.3 `SpatialReferenceProjectionProfile`

保存 `shared_gene_coverage`、ROI/location probability、projection entropy、reconstruction/holdout fit、residual、section consistency、method disagreement、`applicability_state` 和全部 provenance。若适用性 gate 未通过，不发布定向区域结论。

## 9. 运行环境

P0-03 v0.4.0 的聚合与当前表达方法均在冻结的
`ENV-CELLSTATE-PY-v0.1` 中运行。AnnData 负责 H5AD I/O，NumPy/pandas/SciPy
负责 pseudobulk、correlation、NNLS 和 bootstrap，decoupler 负责 ULM。

SpatialData、Squidpy、Tangram、SpaOTsc、CellTrek、CytoSPACE 和 cell2location
仍是空间阶段候选。它们尚无 P0-03 runtime artifact，也不属于当前环境；进入实现
时必须分别冻结兼容环境和 fixture。

所有运行保留环境 ID、软件版本、随机种子、资源记录和输出 checksum。安装成功不等于方法通过科学验证。

## 10. 当前可视化与后续下钻

P0-03 v0.4.0 当前生成：

- **产品相关细胞组成与区域状态图**：同时显示完整产品中
  target、acceptable adjacent、known off-target、unresolved、unknown、OOD 和
  unavailable 的比例，以及具名 reference state 在完整产品中的比例；仅在区域
  分母可用时另示 target-related observations 内部比例。
- **细胞状态与中脑区域的 reference 支持图**：按 target identity 与 regional
  fidelity 分面，并按 reference source、assay 和 developmental context 分列；
  单元格显示 analysis-unit pseudobulk Spearman 中位数和可用单位数，未评估项
  显式显示为 NA。

产品组成图显示 StateRoleMap 审核状态；两图均提供 typed JSON、精确 TSV、
SVG、PNG 和 PDF。观察数不作为生物学重复；缺少独立 product/preparation 时不画 composition
置信区间。reference correlation 不解释为校准的身份概率、胎龄或组织空间位置。

program activity、连续身份权重、NNLS residual、方法敏感性与真正的 spatial
reference projection 仍保留为后续下钻；只有具备合格空间输入和适用性证据时才
显示空间投射。空间图必须注明“参考投射，不代表产品具有真实组织空间结构”。

## 11. Benchmark 与冻结要求

| 验证项 | 最低要求 |
| --- | --- |
| StateRoleMap | 湿实验/发育生物学审核；角色、依据、版本和 reviewer 完整 |
| Target Identity | source/lab/donor holdout、真实 OOD、人工混合、下采样和组成误差 |
| Regional Fidelity | close-region OOD、region holdout、reference swap、matched scRNA/snRNA sensitivity 和具体偏移方向准确性 |
| Spatial projection | spatial-cell pseudo-query、held-out genes、leave-section-out、ROI/crop sensitivity、随机种子和 method swap |
| hEB58 reference | 两切片按同一胚胎处理；标签 provenance、方向、ROI、annotation 与 checksum 冻结 |
| 拒答 | shared genes 不足、OOD、拟合差或方法冲突时返回 `unknown`/`unavailable`，不强制映射 |
| 一致性 | cell-level 图与 sample/state 聚合结果可追溯，独立运行与联合比较不改写原始 evidence |

未完成这些验证前，输出保持 raw metrics 或 `shadow`。0-100 `domain_score` 的公式、方向和阈值在独立 ScoreContract 中另行开发。

## 12. 主要官方来源

- [Tangram documentation](https://tangram-sc.readthedocs.io/)、[Tangram source](https://github.com/broadinstitute/Tangram)、[Tangram paper](https://www.nature.com/articles/s41592-021-01264-7)
- [SpaOTsc source](https://github.com/zcang/SpaOTsc)、[SpaOTsc paper](https://www.nature.com/articles/s41467-020-15968-5)
- [CellTrek source](https://github.com/navinlabcode/CellTrek)、[CellTrek paper](https://www.nature.com/articles/s41587-022-01233-1)
- [CytoSPACE source](https://github.com/digitalcytometry/cytospace)、[CytoSPACE paper](https://www.nature.com/articles/s41587-023-01697-9)
- [cell2location documentation](https://cell2location.readthedocs.io/)、[SpatialData](https://spatialdata.scverse.org/)、[Squidpy](https://squidpy.readthedocs.io/)
- [La Manno et al. 2016](https://doi.org/10.1016/j.cell.2016.09.027)、[Kirkeby et al. 2017](https://doi.org/10.1016/j.stem.2016.09.004)、[CORIN sorting study](https://pmc.ncbi.nlm.nih.gov/articles/PMC3964289/)
