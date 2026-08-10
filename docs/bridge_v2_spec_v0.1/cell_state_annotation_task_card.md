# BRIDGE P0 Cell-State Annotation 任务卡

| 字段 | 内容 |
| --- | --- |
| Task ID | `TASK-CELL-STATE-v0.1` |
| 文档版本 | `0.1` |
| 日期 | 2026-08-06 |
| 状态 | `candidate` |
| 适用范围 | 移植前 scRNA-seq / snRNA-seq；PD hPSC-mDA 为首个实例 |
| Annotation snapshot | `BRIDGE-PD-vMB-ANNOTATION-v0.1-draft` |
| 主要输出 | `CellStateEvidenceProfile` |
| 当前实现 | P0-02 v0.2 透明 shadow baseline；复杂方法待统一 benchmark |

## 1. 任务目标

本任务使用团队已有的人腹侧中脑 annotation 和 reference，识别待评产品中的细胞身份、区域归属、发育状态、过程状态及 unknown/OOD，并聚合为产品组成证据。

P0 不预设某一种注释方法更优。候选方法先按相同标签、reference、holdout 和输出合同进行 benchmark，再冻结可用于正式分析的方法组合。Cell-State 结果只表示转录组证据，不直接表示临床疗效、安全性、potency 或放行结论。

## 2. 内部 Annotation

### 2.1 使用原则

- Web、报告和正式输出使用 BRIDGE 内部名称。
- CL、UBERON、HsapDv 和 GO 只建立 `exact`、`broader`、`narrower`、`related` 或 `unmapped` crosswalk，不覆盖内部名称。
- 每个标签记录来源、人工注释、标签迁移、人工协调、派生子集或模型预测等 provenance。
- 当前标签均为 `freeze_required`，完成生物学定义、marker、父子关系和审核记录后才能冻结。

### 2.2 当前标签层级

| 层级 | 来源 | 规模 | 当前角色 | 状态 |
| --- | --- | ---: | --- | --- |
| L1 broad `cell_type` | 团队统一 vocabulary；运行时按 source-specific reference 分开支持 | 18 类 | P0 shadow 候选 | `freeze_required` |
| L2 RG/Nb-derived states | `REF-CHEN-RGNB-v1` | 15,095 cells；14 类 | P0 正式候选 | `freeze_required` |
| L3 neurogenesis subsubtypes | `REF-CHEN-NEUROGENESIS-SUBSUB-v1-draft` | 77,382 cells；16 类 | 细粒度候选 | `shadow` |

L1 包含：`Astrocyte`、`Endothelial_Cell`、`Fibroblast`、`Glioblast`、`Immune_Cell`、`Neuroblast`、`Neuron_Chat`、`Neuron_DA`、`Neuron_GABA`、`Neuron_Glut`、`Neuron_Glut_GABA`、`Neuron_OMTN`、`Neuron_Sero`、`OPC`、`Oligo`、`Pericyte`、`Radial_Glia`、`Smooth_Muscle`。

L2 包含：`RG_mFP`、`RG_mBMP`、`RG_mBIP`、`RG_dHyp`、`RG_dTha`、`Nb_mFP`、`Nb_mBMP`、`Nb_mBIP`、`Nb_mAP`、`Nb_dHyp`、`Nb_dTha`、`IPC_m1`、`IPC_m2`、`Pericyte`。

L3 包含：`RG_mFP`、`RG_mBMP`、`RG_mBIP`、`Nb_mFP`、`Nb_mBMP`、`Nb_mBIP`、`Neuron_DA`、`Neuron_Glut`、`Neuron_Glut_H`、`Neuron_Glut_L`、`Neuron_Glut_N`、`Neuron_Glut_P`、`Neuron_Glut_S`、`Neuron_Glut_GABA`、`Neuron_GABA`、`Neuron_GABA_O`。

正式冻结前需处理：`Neuron_Chat` 与历史 `Neuron_ChAT` 拼写、L2 中 328 个 broad/refined 层级不一致细胞、25 个 `Radial_Glia -> Pericyte` 记录、L3 缩写语义、reviewer/date/rationale/checksum 缺失，以及 scRNA/snRNA 与胎龄耦合。

## 3. Reference Inventory

| Reference ID | assay 与范围 | 规模 | 主要用途 | 限制 |
| --- | --- | ---: | --- | --- |
| `REF-CHEN-VMB-SC-v1` | scRNA-seq；GW7/8/9/12/16/20；人腹侧中脑 | 61,455 | 早期区域、祖细胞及 target/adjacent evidence | 与 snRNA 不是配对纵向数据 |
| `REF-CHEN-VMB-SN-v1` | snRNA-seq；GW14/16/18/20/24/25；人腹侧中脑 | 87,467 | 中晚期神经元与 DA 状态 | 与胎龄耦合，需模态敏感性分析 |
| `REF-CHEN-VMB-COMBINED-v1` | scRNA + snRNA 派生对象；GW7-GW25 | 148,922 | 跨模态 sensitivity view | source 对象的并集，不是独立证据，不进入来源共识 |
| `REF-CHEN-RGNB-v1` | combined 的 RG/Nb 派生子集 | 15,095 | L2 区域和谱系状态 | 父子层级待人工复核 |
| `REF-CHEN-NEUROGENESIS-v1` | combined 的 neurogenesis 派生子集 | 83,017 | 发育和轨迹背景 | 不代表 causal lineage truth |
| `REF-CHEN-NEUROGENESIS-SUBSUB-v1-draft` | neurogenesis 的 vMB 派生子集 | 77,382 | L3 shadow evidence | 模型版本和命名依据待冻结 |
| `REF-LAMANNO-2016-v1` | scRNA-seq；PCW6-11；人胎腹侧中脑 | 1,977 | scRNA 小型独立 VM primary source | 平台较旧、样本量有限 |
| `REF-BIRTELE-v1` | 人胎腹侧中脑；assay 与对象待转换审计 | 待核实 | 新版本独立 VM reference 候选 | 当前不进入首版 snapshot |
| `REF-BRAUN-2023-v1` | scRNA-seq；PCW5-14；第一孕期全脑 | 1,548,209 | 全脑区域与 off-axis 背景 | 不能替代腹侧中脑产品定义 |
| `REF-ZENG-2023-v1` | scRNA-seq；PCW3-12；全胚、头和脑 | 400,141 | 早期发育和 OOD 背景 | 本地统一标签仍需冻结 |

`source`、`derived`、`holdout` 和 `competitor` 必须分别登记。查询必须声明 `source_family_id`，运行时排除同 source-family reference；派生对象不能与父对象重复计数，同一 source family 的细胞不能随机拆分后充当外部验证。

## 4. 分析流程

当前可执行 baseline 固定为两条互补通道：source-specific pseudobulk Spearman/cosine support，以及版本化 marker/program evidence。它们分别保存，不转换为概率、不按工具数投票，也不设置未经验证的 OOD 阈值。scRNA 与 snRNA 使用独立 `MeasurementSpec`；Chen combined 对象只作 sensitivity。

```mermaid
flowchart LR
    A["QC 合格的产品与样本层级"] --> B["选择内部 annotation 和 eligible references"]
    B --> C["运行冻结的互补方法通道"]
    C --> D["开放集、OOD 与连续身份校准"]
    D --> E["按 evidence family 去重并协调冲突"]
    E --> F["细胞级 prediction set 与 unknown reason"]
    F --> G["sample/preparation 级组成及区间"]
    G --> H["CellStateEvidenceProfile 与 Web 可视化"]
```

1. 读取 `all_cells_view`、`eligible_cells_view`、样本层级、assay/specimen、annotation snapshot、reference snapshot 和 ProductDefinitionCard。
2. 根据标签轴分别评测解剖/区域、谱系/细胞身份、发育状态和过程状态，不要求一个分类器包办全部轴。
3. 运行预先注册的方法组合，保留每种工具原生的 score、distance、weight、label 和 uncertainty 语义。
4. 开放集模块生成 prediction set 和 unknown reason；连续身份模块同时保存权重、重建残差、reference distance 和区间。
5. Evidence Graph 按共享 marker、reference、训练数据和算法家族去重，保留方法分歧，不用多数票掩盖冲突。
6. 以完整声明的产品细胞为分母，聚合 target、acceptable adjacent、known off-target 和 unknown 比例及置信区间。

## 5. 方法目录与首轮短名单

完整方法级输入、输出、许可、维护状态、环境和官方来源记录在配套 Excel。目录覆盖：

| 方法家族 | 目录中的代表方法 | 首轮安排 |
| --- | --- | --- |
| Marker/program | 人工 marker、UCell、AUCell、decoupler、ScType、CellAssign、Garnett、SCSA、scSorter | 内部 program + UCell/decoupler 进入首轮 |
| 传统监督与相似度 | pseudobulk correlation、SingleR、scmap、CellTypist、CHETAH、scPred、scClassify、SciBet、scNym | correlation、CellTypist、SingleR/scmap 进入首轮 |
| Reference mapping | Seurat MapQuery、Symphony、scANVI、scArches、scPoli、Scanpy ingest | scANVI 与 Symphony 进入首轮 |
| 标签协调与共识 | CellHint、scHPL、scTriangulate、popV | popV 作为编排与共识 benchmark；共享证据先去重 |
| 连续与混合身份 | NNLS/simplex、cNMF、topic model、ACTIONet、Capybara、BRIDGE independent engine | 透明 NNLS 与 BRIDGE independent engine 进入首轮，cNMF 作 sensitivity |
| 开放集与不确定性 | OnClass、scConform、conformalized annotator、BRIDGE OOD rules | scConform 包装预注册分类器进入首轮 |
| 基础模型 | scGPT、Geneformer、UCE、TOSICA、SCimilarity、scFoundation、CellFM、CellPLM、scPRINT、Nicheformer | TOSICA、scGPT、SCimilarity 先作 `shadow` |
| 整合敏感性 | no-integration、Harmony、Scanorama、scVI/scANVI、CellHint、LIGER、BBKNN、ComBat、STACAS、Seurat RPCA、fastMNN | no-integration、Harmony、scVI；scIB/scib-metrics 负责诊断 |

首轮至少保留六类互补证据：透明 marker/program、透明 correlation、普通监督分类、独立相似度、reference mapping、开放集/连续身份。复杂模型必须与透明基线比较；Agent 不能在看到待评产品结果后临时选择最有利的方法。

## 6. Studer/CapybaraBrain 双轨隔离

### Track A：as-published competitor reproduction

- 固定 bioRxiv v1、官方仓库 commit、环境、输入和 checksum。
- 原文、README 与 workflow 参数存在不一致，论文称 93 个 program、当前 marker 资源为 92 项；因此分别记录 `paper_literal`、`repo_recommended` 和 `workflow_sweep`，不替作者合并成一个“唯一参数集”。
- 原始 reference、marker、标签、lineage map、阈值和输出仅进入 `competitor_reproduction` namespace。
- 缺失 CellTypist model、integration embedding 或完整配置时标记 `blocked_by_missing_artifact`。

### Track B：BRIDGE independent adaptation

- 可以评测 CellHint、CellTypist、NNLS、连续程序分解等公开的方法类型。
- 必须使用 BRIDGE 自有标签、reference、独立 marker、独立实现及 source/donor holdout calibration。
- 连续身份输出增加 reconstruction residual、reference distance、prediction set、unknown reason 和 bootstrap interval。
- Track A 的代码、atlas、marker、标签、lineage map、阈值和结果不得进入 BRIDGE 的 RAG、prior、训练、校准、调参或正式 Evidence Graph。

BRIDGE 的方法和评测合同冻结后，Track A 才能作为署名的外部 baseline 展示；sealed competitor test 不能反向修改当轮算法。

## 7. 输入与输出合同

### 7.1 必需输入

- `all_cells_view` 与可形成时的 `eligible_cells_view`。
- 冻结的 count/expression view 及其矩阵语义。
- sample、preparation、lot、batch、timepoint 和 biological replicate 层级。
- assay/specimen：scRNA 或 snRNA、whole cell 或 nucleus。
- annotation、reference、ProductDefinitionCard、calibration 和 OOD snapshot。

缺少任一方法所需输入时只跳过该方法；不能从文件名推断样本关系，也不能把缺失证据记为 negative。

### 7.2 `CellStateEvidenceProfile`

| 字段 | 含义 |
| --- | --- |
| `bridge_state_id` | 内部状态 ID 与层级 |
| `prediction_set` | 一个或多个相容状态；允许空集合 |
| `assignment_state` | `assigned` / `ambiguous` / `unknown` / `unavailable` |
| `unknown_reason` | `reference_gap` / `method_conflict` / `biological_unresolved` / `technical_unavailable` |
| `method_evidence` | 各方法原始 score、distance、weight 或 label |
| `calibration` | prediction-set coverage、set size 和适用性 |
| `method_disagreement` | 按独立 evidence family 汇总的方法分歧 |
| `composition` | target、adjacent、off-target、unknown 的比例、分母和区间 |
| `hybrid_identity` | 连续权重、残差及 discrete/hybrid/transitioning 候选；验证前为 `shadow` |
| `provenance` | tool、reference、annotation、environment、parameter 和 Evidence ID |

## 8. 运行环境

Cell-State 不适合塞进单一环境。环境间通过版本化 h5ad/Parquet/TSV 与 JSON manifest 交换结果。

| 环境 | 用途 | 当前状态 |
| --- | --- | --- |
| `ENV-CELLSTATE-PY-CORE-v0.1` | Scanpy、AnnData、scVI/scANVI、scIB、透明 Python 基线 | `proposed`；需建立 lock 与 health check |
| `ENV-CELLSTATE-CELLTYPIST-v0.1` | CellTypist custom model | `proposed_isolated` |
| `ENV-CELLSTATE-BIOC-v0.1` | UCell、SingleR、scmap、CHETAH、Symphony、Seurat 及相关 R 工具 | `proposed_isolated` |
| `ENV-CELLSTATE-CELLASSIGN-v0.1` | CellAssign 的 R/TensorFlow 依赖 | `proposed`；独立隔离 |
| `ENV-CELLSTATE-CONFORMAL-v0.1` | scConform 和 conformal calibration | `proposed`；独立隔离 |
| `ENV-CELLSTATE-CAPY-COMP-v0.1` | CapybaraBrain competitor reproduction | `proposed`；官方 Python 3.12 CPU 环境，完全隔离 |
| `ENV-CELLSTATE-CONTINUOUS-v0.1` | BRIDGE NNLS/NMF/archetypal 候选 | `proposed` |
| `ENV-CELLSTATE-FM-SHADOW-v0.1` | 基础模型 | `shadow`；按模型分别建环境并记录 GPU、权重和许可 |

当前服务器可提供 112 CPU、1 TiB RAM 和 2 张 24 GB GPU。正式运行仍需保存 environment ID、版本锁、随机种子和资源记录；安装成功不表示方法已经通过科学验证。

## 9. Web 必备可视化

- 内部 L1/L2/L3 annotation hierarchy 与冻结状态。
- 每种方法的 embedding overlay、prediction set 和 unknown reason。
- 方法一致性热图，并按 evidence family 标出共享依赖。
- holdout confusion matrix、层级错误、校准曲线和 prediction-set coverage。
- OOD dashboard、稀有状态 LOD 与失败原因。
- target/adjacent/off-target/unknown 组成及区间。
- 连续身份的 top1-top2 权重、残差和 hybrid 候选图。
- reference、preprocessing 和 integration sensitivity 图。
- 从图表下钻到 marker、distance、weight、冲突及 provenance 的 Evidence Graph。

所有正式图表绑定 Evidence ID、分母、单位、输入和方法版本；未注册图表保持 `exploratory`。

## 10. Benchmark 与冻结要求

| 验证项 | 要求 |
| --- | --- |
| Holdout | 按 study/source/lab/donor/modality 拆分；禁止随机拆同来源细胞冒充外部验证 |
| 层级预测 | 报告 hierarchical accuracy、macro-F1、层级错误和产品组成误差 |
| 校准与拒答 | 报告 calibration、prediction-set coverage/set size、leave-one-state-out 和真实 OOD 检出 |
| 稀有状态 | 使用 sample-preserving downsampling、spike-in 和 LOD/UCB；低于 LOD 时只能说不能排除 |
| 连续身份 | 使用人工混合与伪混合，评测 weight error、residual、discrete/hybrid/transitioning/unknown |
| 稳定性 | 运行 reference swap、preprocessing swap、no-integration/integration、随机种子和资源测试 |
| 基础模型 | 审计预训练数据重叠、权重许可、基因词表和数据出境，并与简单基线公平比较 |
| Competitor isolation | Track A 到内部 marker、calibration、RAG 和正式 Evidence Graph 的数据流必须为零 |

每个状态轴单独决定是否冻结方法。若没有方法达到预注册标准，该轴返回 `unavailable`；其余轴仍可继续。正式晋升还需通过许可、环境 fixture、Evidence Graph 去重和 claim review。

## 11. 主要官方来源

- [UCell](https://github.com/carmonalab/UCell)、[decoupler](https://github.com/scverse/decoupler)、[CellAssign](https://irrationone.github.io/cellassign/)
- [SingleR](https://bioconductor.org/packages/SingleR/)、[scmap](https://bioconductor.org/packages/scmap/)、[CellTypist](https://github.com/Teichlab/celltypist)、[CHETAH](https://bioconductor.org/packages/CHETAH/)
- [Seurat mapping](https://satijalab.org/seurat/articles/integration_mapping.html)、[Symphony](https://github.com/immunogenomics/symphony)、[scVI/scANVI](https://docs.scvi-tools.org/en/stable/api/reference/scvi.model.SCANVI.html)、[scArches](https://github.com/theislab/scarches)
- [CellHint](https://cellhint.readthedocs.io/)、[popV](https://github.com/YosefLab/popV)、[OnClass](https://github.com/wangshenguiuc/OnClass)、[scConform](https://bioconductor.org/packages/scConform/)
- [Capybara](https://github.com/morris-lab/Capybara)、[cNMF](https://github.com/dylkot/cNMF)、[ACTIONet](https://github.com/shmohammadi86/ACTIONet)
- [scGPT](https://github.com/bowang-lab/scGPT)、[Geneformer](https://huggingface.co/ctheodoris/Geneformer)、[TOSICA](https://github.com/JackieHanLab/TOSICA)、[SCimilarity](https://github.com/Genentech/scimilarity)
- [scIB](https://github.com/theislab/scib)、[Scanpy ingest](https://scanpy.readthedocs.io/en/stable/generated/scanpy.tl.ingest.html)
- [Studer/Bocchi bioRxiv v1](https://www.biorxiv.org/content/10.64898/2026.06.19.733041v1.full)、[CapybaraBrain](https://github.com/VittoriaDBocchi/CapybaraBrain)
