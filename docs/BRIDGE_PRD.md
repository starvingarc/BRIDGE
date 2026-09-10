# BRIDGE 细胞治疗产品评估智能体 PRD v0.1

| 项目 | 内容 |
| --- | --- |
| 项目全称 | Brain-Referenced In vivo-to-in vitro Developmental Guidance and Evaluation |
| 产品形态 | 科学评估智能体（Scientific Agent） |
| 文档版本 | `v0.1` |
| 修订日期 | 2026-09-10 |
| 状态 | `current_primary_specification` |
| 适用范围 | 研究用途的细胞治疗产品转录组评估；PD hPSC-mDA 为首个实例 |
| 文档权威性 | 本文档是 BRIDGE 当前唯一主规范；Registry 和 Task Card 是受其约束的实施附件 |

> **当前实现边界：** BRIDGE 已有 12 个确定性 P0 工具包。私有 Web 在既定范围内已验收研究问题、资料、必要追问、来源事实确认、范围/资源审批与 QC，并提供可核对的 protocol 表示。下游图驱动研究闭环、内部 comparator 选择和 qualified report/export 是已批准目标，不是当前完整能力；现有候选缺失图与 blocked 内部报告不等于产品评估完成。当前没有冻结 P0 ScoreContract，所有活动模块保持 domain_score=null。精确证据见[验证记录](validation/README.md)，剩余科学工作见[活动计划](../plans/product-evidence-validation.md)。

## 目录

1. [项目目标](#1-项目目标)
2. [现有资源](#2-现有资源)
3. [评估内容](#3-评估内容)
4. [分析工具与知识库](#4-分析工具与知识库)
5. [部署与运行要求](#5-部署与运行要求)
6. [Agent 功能需求](#6-agent-功能需求)
7. [附录](#7-附录)

## 1. 项目目标

### 1.1 要解决的问题

体外分化获得的细胞治疗产品通常包含多种细胞状态。不同分化方案、时间点和批次之间可能同时存在目标细胞比例、区域身份、发育程度、离轴分化和过程应激等差异。

现有评估通常依赖少量 marker、人工注释或单一参考数据，难以系统回答以下问题：

- 产品中实际包含哪些细胞。
- 目标细胞是否具有正确的区域和谱系身份。
- 产品处于什么发育状态。
- 是否存在 off-target、unknown 或异常细胞状态。
- 不同方案、时间点和批次的差异来自哪里。
- 哪些结论有充分证据，哪些仍需补充实验。

BRIDGE 希望将分散的数据、分析工具和外部知识组织成统一、可追溯的评估流程。

### 1.2 产品定位

BRIDGE 是面向细胞治疗产品的科学评估智能体。

系统通过 Agent 完成案例确认、分析规划、工具调用、知识检索、证据整合和报告生成。具体指标由注册的分析工具计算，Agent 负责选择合适的工具和知识来源，并将结果解释为湿实验人员可以理解和核查的结论。

BRIDGE 面向不同类型的细胞治疗产品扩展。PD hPSC-mDA 作为首个完整应用，通过替换产品定义、参考数据和领域知识，可进一步支持其他疾病和细胞产品。

#### 主要使用者与职责边界

主要使用者是正在开发、分化和检测细胞治疗产品的湿实验研究人员。其问题是
“这批制剂包含什么、与我的目标是否相符、哪些信号需要复核、下一步补什么”，
而不是“应该上传哪一份内部 JSON 或调用哪个 P0 工具”。生信分析人员可检查
矩阵声明、样本关系和证据来源；Agent 开发者负责让这些检查可靠地发生，不替代
研究者确认实验事实，也不替代科学审阅者批准状态定义与解释规则。

研究者提供产品意图和只有实验记录能回答的事实。Agent 推荐来源可追溯的
候选定义，解释选择后果，并组织已批准任务。确定性工具拥有数值、分母、状态、
版本和来源绑定。Web 把这些对象转为可理解的提问、核对卡和结果；内部对象名、
文件路径、hash 和工具编号只在技术详情中出现，不是普通使用者完成流程的前提。

### 1.3 PD hPSC-mDA 首个应用场景

当前版本主要评估移植前的 hPSC-mDA 分化细胞，并支持比较不同分化方案、时间点、批次和 preparation。

系统重点分析：

- 中脑腹侧底板和 mDA 谱系身份。
- 前后轴、背腹轴和邻近脑区身份。
- 祖细胞、未成熟神经元和成熟神经元等发育状态。
- target、acceptable adjacent、off-target 和 unknown 组成。
- residual pluripotency、异常增殖、应激和其他过程异常。
- 调控、通路、代谢、通讯及空间支持证据。
- 结果对 reference、模型和分析方法的稳定性。

当发现目标身份不足、发育状态不匹配或异常程序升高时，BRIDGE 可以提出可验证的改进假设和补充实验，例如需要核查的细胞群、marker、通路或处理环节。系统不直接给出未经验证的小分子剂量和处理时序。

### 1.4 输入与输出

#### 用户需要提供

| 输入类型 | 内容 |
| --- | --- |
| 产品数据 | 移植前完整制剂的 scRNA-seq 数据 |
| 产品定义 | 预期细胞类型、目标状态和产品用途 |
| 样本信息 | 细胞系、分化方案、时间点、批次和 preparation |
| 数据说明 | assay、表达矩阵、metadata 字段及已知预处理过程 |

Agent 首先检查输入是否完整，并向用户确认会影响分析设计的关键信息。

#### 用户可选补充

用户可以补充自己的：

- 发育参考或对照数据。
- 空间转录组和组织染色数据。
- 与移植前 preparation 明确关联的 graft scRNA-seq/snRNA-seq。
- 新批次、新时间点或新的分化方案。

新增资源需要经过数据审计和适用性检查，并与系统预置资源分别记录。系统不会在来源不明确时自动合并数据。

graft 数据只进入独立后验分析，不用于修改移植前分域评估分数。

#### 输出

BRIDGE 输出四类结果：

| 类型 | 含义 |
| --- | --- |
| `Q - Quantification` | 目标身份、发育状态、组成、过程警报和稳定性等量化结果 |
| `E - Explanation` | 差异驱动因素、相关生物过程、支持证据和冲突证据 |
| `R - Recommendation` | 可验证的改进假设、补充测量和下一步验证实验 |
| `G - Gate/Alert` | 数据不可用、证据不足、OOD、关键异常和停止条件 |

最终报告包括产品多维画像、条件化产品比较、主要问题、证据充分性、结果来源和当前不可得结论。

BRIDGE 当前不输出临床疗效、安全性、validated potency、GMP 放行结论或跨场景绝对产品排名。

## 2. 现有资源

### 2.1 数据资源总览

BRIDGE 已整理的数据分为六类。各类数据的角色不同，不会因为都能转换为 h5ad 而被混合使用。

| 数据类别 | 主要内容 | 在 BRIDGE 中的用途 | 是否作为移植前产品输入 |
| --- | --- | --- | --- |
| 发育 reference | 人胎腹侧中脑、全脑和早期胚胎 scRNA-seq/snRNA-seq | 定义区域、谱系、发育和邻近状态 | 否 |
| 移植前产品数据 | 多实验室、方案、时间点和批次的体外分化 scRNA-seq | 产品画像、方案比较和稳定性评测 | 是，需按 sample/preparation 建立案例 |
| 空间与正交数据 | 空间转录组、组织染色和解剖信息 | 验证 marker 的空间特异性和组织位置 | 否 |
| 机制校准数据 | 谱系条形码、应激、扰动和疾病背景数据 | 校准阶段、转变、风险和鲁棒性证据 | 否 |
| OOD 数据 | 皮层、脊髓、运动神经元、神经嵴和 MSC 等 | 检验特异性、unknown 和拒答能力 | 否 |
| graft 数据 | 动物移植后的人源 graft scRNA-seq/snRNA-seq | 独立后验分析 | 否 |

每项数据在 Data/Reference Registry 中分别记录四类状态：`availability` 表示文件或对象是否可获得，`metadata_status` 表示样本合同是否完整，`access_policy` 表示访问和披露限制，`evaluation_eligibility` 表示能否进入 reference、开发、校准、sealed test 或正式比较。下表中的 `available` 只表示本地对象可读取或可运行，不等于已经获得正式评估资格。

### 2.2 人胎发育参考数据

| 数据家族 | Assay 与材料 | 发育时间与解剖范围 | 当前规模 | 主要用途 | 状态与限制 |
| --- | --- | --- | ---: | --- | --- |
| Chen vMB scRNA | scRNA-seq，whole cells | GW7/8/9/12/16/20；人胚腹侧中脑 | 61,455 cells | 早期区域、祖细胞和目标/邻近程序 | `available`；需冻结样本表、ROI 和 annotation |
| Chen vMB snRNA | snRNA-seq，nuclei | GW14/16/18/20/24/25；人胚腹侧中脑 | 87,467 nuclei | 中晚期神经元和 DA subtype coverage | `available`；与 scRNA 为不同胚胎 |
| Chen vMB combined | scRNA-seq + snRNA-seq 整合对象 | 12 个非配对胚胎、10 个孕周；腹侧中脑 | 148,922 profiles | state ontology、reference mapping 和发育背景 | 派生对象；年龄与模态存在混杂 |
| Chen RG/Nb states | 从 Chen sc/sn 派生的状态集 | 腹侧中脑；14 个区域 RG/Nb states | 15,095 profiles | mFP/mBIP/mBMP 目标和邻近状态 | 不作为独立 reference 计数 |
| Chen neurogenesis states | 从 Chen sc/sn 派生的神经发生状态集 | 腹侧中脑发育 | 83,017 profiles | DA/GABA/Glut/RG/Nb 状态和发育程序 | candidate；不是因果谱系真值 |
| Braun et al., 2023 (`EGAS00001004107`; HCA `cbd2911f-252b-4428-abde-69e270aefdfc`) | scRNA-seq；论文另含 spatial | PCW5-14；第一孕期全脑多区域 | 1,548,209 cells | 全脑区域和广谱离轴背景 | `available`；全脑 reference 不替代 vMB reference |
| Zeng et al., 2023 (`GSE155121`) | scRNA-seq；PCW4 10x spatial | PCW3-12；全胚、全头和全脑 | 400,141 human cells | 早期胚胎、神经管、脑和非神经背景 | `available`；区域与年龄标签需冻结 |
| La Manno et al., 2016 (`GSE76381`) | 人胎 VM scRNA-seq | PCW6-11；腹侧中脑 | 1,977 fetal cells | 独立经典 VM 发育 reference | `available`；旧平台且样本量较小 |
| Birtele et al., 2022 (`GSE192405`) | 人胎 VM scRNA-seq 与原代培养 | 6-11 周 post-conception；腹侧中脑 | 13 个 GEO samples；processed CSV 可用 | 原代胎儿 VM maturation external-source 候选 | `converted_conditionally_approved`；raw reads 不公开；仅允许 source/stage-level holdout 与 provisional-group sensitivity，不允许 biological-replicate 或 donor-level inference |

旧 Step1 reference 由 Chen legacy scRNA、Braun 和 Zeng 构建，full object 为 2,011,383 profiles。其 350,000-cell train、100,000-cell technical holdout 和 523,478-profile regional RG 仅用于旧流程复现、软件回归和血缘审计，不视为新 BRIDGE 的独立生物学验证。

### 2.3 主要移植前 mDA 产品样数据

| 数据家族 | 起始细胞、体系与目标产物 | Assay 与体外时间 | 当前规模 | BRIDGE 用途 | 状态与限制 |
| --- | --- | --- | ---: | --- | --- |
| Xu/Chen 2022 (`GSE204796`) | hPSC；2D/神经球 mDA 分化；VM floor-plate/mDA progenitors | scRNA-seq；D8/D14/D21/D28/D35 | 37,397 cells | 发育时间序列和方法开发 | `available`；五个时间点分开建案，graft 分开 |
| Studer/Tabar Boost vs Boost+ (`E-MTAB-14729`) | hPSC；2D Boost/Boost+ mDA 分化；VM floor-plate/mDA progenitors | scRNA-seq；D16/D25/D40 | 26,303 cells | 冻结后的 sealed competitor test | `sealed`；仅在 BRIDGE 合同冻结后运行，不进入 RAG、reference、prior、训练、校准或调参 |
| Storm/Parmar RC17 (`GSE200610`) | RC17 hESC；2D VM 分化；移植用 VM floor-plate/mDA progenitors | scRNA-seq D16；multiome D16/D18 | D16 scRNA 8,166 cells | 单时间点临床相关比较 | `sealed`；不等于患者 GMP lot，graft 与 multiome 分层 |
| LR-USC mDA scRNA (`GSE227070`; parent SuperSeries `GSE227071`) | H9 hESC 和 4X lineage-restricted USC；2D mDA 分化 | scRNA-seq；D16/D28/D62 | 48,196 cells | cell-source、stage 和 protocol shift | `available`；本 scRNA query 不含 GBX2-KO；D62 与 D16/D28 不视为同一产品阶段 |
| La Manno in-vitro (`GSE76381`) | hESC/iPSC；2D mDA 分化；VM progenitors/mDA neurons | scRNA-seq；hESC D0/D12/D17/D35，iPSC D42/D63 | 2,052 cells | 历史时间序列和平台 sanity check | `available`；样本量小，不支持 rare-state 正式比较 |
| Jerber population-scale iPSC DA (`EGAS00001002885`; `EGAD00001006157`) | 215 条 iPSC lines；pooled 2D mDA 分化 | scRNA-seq；D11/D30/D52，D52 含 rotenone block | 765,851 cells | donor、batch、timepoint 和扰动鲁棒性 | `available`；需按 donor/batch/condition 去重 |
| BrainSTEM Toh (`GSE281535`) | hPSC；3D midbrain organoid；midbrain/mDA lineage | scRNA-seq；D20/D25/D30/D40/D50/D60 | 34,702 cells；48 sequencing sublibraries，每个时间点 8 个 | 2D/3D domain shift 和时间点描述 | `available`；在 biological sample/organoid/replicate map 冻结前，48 个 sublibraries 不得称为 48 个生物学重复，只能作 timepoint-level descriptive analysis |
| Fiorenzano VM organoid (`GSE168323`) | hPSC；3D VM organoid；VM/mDA neurons 及前体 | scRNA-seq；D15/D30/D60/D90/D120 | 91,034 cells | organoid trajectory 和区域比较 | `available`；organoid 不与 2D product 直接排名 |
| SphereDiff（陈跃军组，Cell Stem Cell 研究关联） | hPSC；3D sphere differentiation；mDA progenitors | scRNA-seq；论文原始序列位于受控项目 `HRA008865`；BRIDGE v1 对象为 D28 | v1 对象 9,547 cells；`count_ready` 对应关系尚未闭合 | 已发表研究关联的历史比较 | `analysis_ready_only`；关联 Zhang et al., Cell Stem Cell 2025；完成样本对应后再进入 `count_ready` 分析 |
| MacroDiff（陈跃军组内部数据） | hPSC；内部两类 mDA differentiation protocol；mDA progenitors | scRNA-seq；Protocol A 为 D14/D21/D28，Protocol B 为 D28 | 六个 `count_ready` capture 共 78,542 个 cell-called barcodes；v1 下游对象 57,464 cells | 内部时间序列和跨 protocol 证据 | `restricted_internal`、`internal_unpublished`；capture 结构本身不证明 biological-replicate independence |
| Tiklová pre-graft RC17 (`GSE118412`) | RC17 hESC；2D VM 分化；VM/mDA progenitors | Smart-seq2/scRNA-seq；D16 | 404 hESC-derived cells | 与长期 graft 显式关联的历史 sanity check | `available`；样本量小且平台较旧；同源 fetal VM 256 cells 作为 reference，不计入产品分母 |
| Studer/MSK-DA01 protocol-linked D16 | D16 分化样本；已发表 MSK-DA01/Studer floor-plate 方案作为 protocol context | scRNA-seq；D16 | `count_ready` 矩阵 11,087 个 cell-called barcodes；v1 下游对象 9,046 cells | 已发表方案背景比较 | `restricted_source`；Piao et al., Cell Stem Cell 2021 支持产品与方案背景，但不确定该测序对象的论文数据归属 |

### 2.4 空间转录组与染色验证

| 数据家族 | 数据类型 | 时间与解剖范围 | 当前规模/状态 | BRIDGE 用途 | 关键限制 |
| --- | --- | --- | --- | --- | --- |
| Chen hEB58 | Visium HD segmented tissue profiles | GW7；人胚中脑，section 2/9 | 225,107 + 186,054 = 411,161 profiles；18,085 probes；`available` | marker 空间特异性、解剖锚定和算法可行性 | 两张切片来自同一胚胎；方向和 ROI 待冻结 |
| Chen 冠状/矢状空间数据 | 人胚中脑空间转录组 | 单时间点；冠状和矢状切面 | `pending`；数据等待返回 | donor/section-aware anatomical reference | 返回后需登记 assay、donor、section、ROI 和 QC |
| Chen 人胚中脑 marker 染色 | IF/IHC | 具体 GW/PCW、切面和 ROI 待样本表冻结 | 实验进行中 | 验证 mDA、底板、区域边界和非目标 marker | 样本、抗体批次和成像条件冻结前不进入量化 |
| Braun 2023 spatial | 论文公开空间数据 | PCW5-14 第一孕期全脑 | 论文级可用；本地 spatial 版本待冻结 | 全脑解剖和区域 context | 不以论文图像代替可运行 snapshot |
| Zeng 2023 PCW4 spatial | 10x spatial | PCW4；全胚/全头/早期脑 | 公开数据；待独立版本与 ROI 审计 | early anatomy context | 不与体外产品直接比较 |

空间和染色数据当前主要用于 reference 构建和正交验证。单一胚胎的多张切片不视为多个生物学重复。

### 2.5 OOD 与机制校准数据

#### 机制与风险校准

| 数据家族 | 体系与时间 | 当前规模 | 用途 | 限制 |
| --- | --- | ---: | --- | --- |
| SISBAR (`GSE207921`) | H9 hESC mDA 分化 + lineage barcode；D13/D21/D30/D45 | 47,155 cells | stage transition 和 lineage-state consistency | 只支持实际观测到的转变 |
| SISBAR replicates (`GSE221592`) | H9 hESC mDA 分化 + lineage barcode；Stage I-IV | 168,805 cells | replicate-aware transition calibration | combined 和 split objects 不重复计数 |
| LMX1A/BFP sorting + MPP+ (`GSE249360`) | iPSC mDA；sorting groups；basal/MPP+ 24 h | 1,530 cells | sorting/stress 边界 | 确切分化 D 待核实 |
| Opioid-exposed midbrain organoid (`GSE260711`) | iPSC midbrain organoid；D53 acute、D77 chronic、D79 withdrawal | 20,322 cells | perturbation 与 stress robustness | 药物暴露不是产品质量标签 |

#### 跨体系与疾病背景鲁棒性

| 数据家族 | 体系与时间 | 当前规模 | 用途 | 限制 |
| --- | --- | ---: | --- | --- |
| FOUNDIN-PD / Bressan | 多供体 iPSC mDA；本地主要为 D65 | 416,216 cells | donor 和 disease-context robustness | 来源版本与正式 accession 待冻结 |
| Fernandes PD models | iPSC dopaminergic neurons；D47 子集 | 2,728 cells | disease/stress context | 只代表当前子集 |
| PINK1 mDA (`GSE183248`) | PD/control iPSC mDA；D6/D15/D21 等 | 3,324-cell local subset | mutation/stage robustness | 子集不代表完整研究 |
| LRRK2 midbrain organoid (`GSE133894`) | WT/LRRK2-G2019S iPSC organoid；D35/D70 | 10,517 cells | organoid disease/region robustness | 来源映射已修正，需保留 provenance |
| Familial-PD mDA (`GSE213569`) | familial-PD/control iPSC mDA；D48 | 11,066-cell control subset | control/source robustness | 本地只含 control 子集 |
| VM-striatum-cortex assembloid (`GSE219247`) | hPSC assembloid；D60 VM 子集 | 1,244 cells | multi-region domain shift | 只代表 fVmidbrain 子集 |
| MIRO1/RHOT1 PD organoid (`GSE264097`) | patient/isogenic/healthy-control iPSC midbrain organoid；D60 | 原始数据已下载 | mitochondrial 和 neuron-astrocyte disease-context robustness | `pending`；尚未转换，疾病模型不作为产品质量标签 |

#### Negative/OOD panel

| 数据家族 | Assay、时间与生物场景 | 当前规模 | OOD 用途 | 状态/限制 |
| --- | --- | ---: | --- | --- |
| Fan fetal cortex (`GSE120046`) | scRNA-seq；PCW7-28；人胎大脑皮层 | 13,124 cells | in-vivo forebrain/cortex OOD | `available` |
| Connected cerebral organoids (`GSE190729`) | scRNA-seq；体外时间待核实；cerebral organoid | 17,636 cells | cortical/cerebral OOD | `available`；timepoint metadata 待补 |
| Reproducible cortical organoids (`GSE129519`) | scRNA-seq；3 个月；dorsal forebrain/cortex | 10,000 sampled cells | high-quality cortical OOD | 两个 cell line 各 5,000 sampled |
| hiPSC motor neurons (`GSE267791`) | scRNA-seq；D 待核实；spinal motor neurons | 1,341 cells | neuronal but non-mDA OOD | `available`；样本量小，timepoint metadata 待补 |
| Developing human spinal cord (`GSE188516`) | scRNA-seq + snRNA-seq；PCW17-18；脊髓 | 20,000 sampled profiles | ventral CNS but non-midbrain OOD | 保留 sc/sn 模态区别 |
| Neural crest/sympathoadrenal (`GSE221853`) | scRNA-seq；D0-D28；hESC trunk neural crest | 29,857 cells | peripheral neural-crest OOD | `available` |
| Bone-marrow MSC (`GSE224152`) | scRNA-seq；成人骨髓 MSC | 1,771 cells | non-neural/mesenchymal OOD | `available`；样本量小 |
| Whole-brain organoids (`GSE86153`) | scRNA-seq；3/6 个月；heterogeneous brain organoid | 10,000 sampled cells | heterogeneous brain OOD | 每个时间点 5,000 sampled |
| hESC neural lineages (`GSE86982`) | scRNA-seq；D 待核实；前脑及中/后脑神经谱系 | 2,365 cells | difficult neural/caudal OOD | `available`；timepoint metadata 待补 |

OOD 数据用于检验 BRIDGE 能否识别非目标生物场景，不代表“低质量 PD 产品”。评测需以 study、sample 和 timepoint 分组，不使用 cell-level random split 冒充外部验证。

#### 待转换、受控或排除资源

| 数据家族 | 当前状态 | 处理方式 |
| --- | --- | --- |
| `GSE75140`、`GSE218457`、`GSE138002`、`GSE132672` | 原始或 processed 数据已下载，待转换/核实 | 作为 cortex、retina 和 organoid OOD reserve |
| `GSE160625`、`GSE75748` | 已下载，待转换 | 作为 mesoderm/endoderm severe OOD reserve |
| Nishimura/Arenas 与 Ásgrímsdóttir datasets | `controlled_access` | 获得合法访问和 sample map 前不宣称可运行 |
| Luo fetal cerebellum (`GSE198565`) | `excluded` | 来源论文已撤稿，隔离于 reference、prior 和 benchmark |
| `GSE216323` scATAC archive | `excluded`；当前模态不适用 | 不作为当前 scRNA 产品输入 |

### 2.6 移植后 graft 数据

| 数据家族 | 宿主与模型 | Graft assay | 移植后时间 | 主要覆盖状态 | 与移植前 preparation 的关系 |
| --- | --- | --- | --- | --- | --- |
| Xu/Chen (`GSE204796`) | PD 小鼠模型 | human EGFP+ graft scRNA-seq | 4 个月 | mDA neurons 和 off-target neuronal states | 同一研究家族；sorted/unsorted preparation map 冻结后作后验比较 |
| Boost/Boost+ (`E-MTAB-14729`) | 6-OHDA 大鼠模型 | human graft snRNA-seq | 1/9 个月 | graft maturation、mDA subtype 和 off-target context | 按 Boost/Boost+ preparation 显式关联；仅在主评估冻结后查看 |
| Storm/Parmar (`GSE200610`) | 6-OHDA 大鼠 PD 模型 | human graft snRNA-seq + lineage barcode context | 3/6 个月 | DA neurons、astrocytes、VLMCs 等 | 来源于 RC17 D18 preparation；按 preparation/barcode 显式关联 |
| Tiklová (`GSE118412`, `GSE132758`) | 大鼠 PD 模型 | Smart-seq2/scRNA-seq | 6/12 个月 | DA neurons、astrocytes、VLMCs 及其他 graft-derived cells | 来源 D16 VM preparation；移植前 404-cell block 见 2.3，graft 原始块待转换 |

graft 的分析单位为 `animal/graft x post-transplant timepoint`。只有在存在明确的来源 preparation 和连接证据时，Agent 才能生成 preparation-graft 描述性关联。graft 结果不用于回填移植前分域评估分数、训练标签或疗效/安全性结论。

#### 公开数据主要来源

| 数据 | 短引用 | DOI |
| --- | --- | --- |
| Braun 2023 | Braun et al., *Science* (2023) | [10.1126/science.adf1226](https://doi.org/10.1126/science.adf1226) |
| Zeng 2023 / `GSE155121` | Zeng et al., *Cell Stem Cell* (2023) | [10.1016/j.stem.2023.04.016](https://doi.org/10.1016/j.stem.2023.04.016) |
| La Manno / `GSE76381` | La Manno et al., *Cell* (2016) | [10.1016/j.cell.2016.09.027](https://doi.org/10.1016/j.cell.2016.09.027) |
| Birtele / `GSE192405` | Birtele et al., *Development* (2022) | [10.1242/dev.200504](https://doi.org/10.1242/dev.200504) |
| SISBAR / `GSE207921`, `GSE221592` | You et al., *Cell Stem Cell* (2023) | [10.1016/j.stem.2023.02.007](https://doi.org/10.1016/j.stem.2023.02.007) |
| Xu/Chen / `GSE204796` | Xu et al., *JCI* (2022) | [10.1172/JCI156768](https://doi.org/10.1172/JCI156768) |
| Boost/Boost+ / `E-MTAB-14729` | Kim et al., *JCI* (2026) | [10.1172/JCI190954](https://doi.org/10.1172/JCI190954) |
| Storm/Parmar / `GSE200610` | Storm et al., *Science Advances* (2024) | [10.1126/sciadv.adn3057](https://doi.org/10.1126/sciadv.adn3057) |
| LR-USC scRNA / `GSE227070`（parent SuperSeries `GSE227071`） | Maimaitili et al., *Nature Communications* (2023) | [10.1038/s41467-023-43471-0](https://doi.org/10.1038/s41467-023-43471-0) |
| Jerber population-scale DA | Jerber et al., *Nature Genetics* (2021) | [10.1038/s41588-021-00801-6](https://doi.org/10.1038/s41588-021-00801-6) |
| BrainSTEM Toh / `GSE281535` | Toh et al., *Science Advances* (2025) | [10.1126/sciadv.adu7944](https://doi.org/10.1126/sciadv.adu7944) |
| Fiorenzano / `GSE168323` | Fiorenzano et al., *Nature Communications* (2021) | [10.1038/s41467-021-27464-5](https://doi.org/10.1038/s41467-021-27464-5) |
| SphereDiff / Chen 组 Cell Stem Cell 研究 | Zhang et al., *Cell Stem Cell* (2025) | [10.1016/j.stem.2025.10.001](https://doi.org/10.1016/j.stem.2025.10.001) |
| MSK-DA01 product/protocol context | Piao et al., *Cell Stem Cell* (2021) | [10.1016/j.stem.2021.01.004](https://doi.org/10.1016/j.stem.2021.01.004) |
| LMX1A/BFP + MPP+ / `GSE249360` | Cardo et al., *Cells* (2023) | [10.3390/cells12242860](https://doi.org/10.3390/cells12242860) |
| Opioid organoid / `GSE260711` | Kim et al., *Advanced Science* (2024) | [10.1002/advs.202400847](https://doi.org/10.1002/advs.202400847) |
| FOUNDIN-PD | Bressan et al., *Cell Genomics* (2023) | [10.1016/j.xgen.2023.100261](https://doi.org/10.1016/j.xgen.2023.100261) |
| Fernandes PD models | Fernandes et al., *Cell Reports* (2020) | [10.1016/j.celrep.2020.108263](https://doi.org/10.1016/j.celrep.2020.108263) |
| PINK1 mDA / `GSE183248` | Novak et al., *Communications Biology* (2022) | [10.1038/s42003-021-02973-7](https://doi.org/10.1038/s42003-021-02973-7) |
| LRRK2 organoid / `GSE133894` | Zagare et al., *American Journal of Human Genetics* (2022) | [10.1016/j.ajhg.2021.12.009](https://doi.org/10.1016/j.ajhg.2021.12.009) |
| Familial-PD mDA / `GSE213569` | Virdi et al., *npj Parkinson's Disease* (2022) | [10.1038/s41531-022-00423-7](https://doi.org/10.1038/s41531-022-00423-7) |
| VM-striatum-cortex assembloid / `GSE219247` | Reumann et al., *Nature Methods* (2023) | [10.1038/s41592-023-02080-x](https://doi.org/10.1038/s41592-023-02080-x) |
| MIRO1/RHOT1 PD organoid / `GSE264097` | Zagare et al., *npj Systems Biology and Applications* (2025) | [10.1038/s41540-025-00509-x](https://doi.org/10.1038/s41540-025-00509-x) |
| Fan cortex / `GSE120046` | Fan et al., *Science Advances* (2020) | [10.1126/sciadv.aaz2978](https://doi.org/10.1126/sciadv.aaz2978) |
| Connected cerebral organoid / `GSE190729` | Osaki et al., *Nature Communications* (2024) | [10.1038/s41467-024-46787-7](https://doi.org/10.1038/s41467-024-46787-7) |
| Cortical organoid / `GSE129519` | Velasco et al., *Nature* (2019) | [10.1038/s41586-019-1289-x](https://doi.org/10.1038/s41586-019-1289-x) |
| Motor neuron / `GSE267791` | Hayakawa-Yano et al., *PNAS* (2024) | [10.1073/pnas.2401531121](https://doi.org/10.1073/pnas.2401531121) |
| Human spinal cord / `GSE188516` | Andersen et al., *Nature Neuroscience* (2023) | [10.1038/s41593-023-01311-w](https://doi.org/10.1038/s41593-023-01311-w) |
| Neural crest / `GSE221853` | Saldana-Guerrero et al., *Nature Communications* (2024) | [10.1038/s41467-024-47945-7](https://doi.org/10.1038/s41467-024-47945-7) |
| Bone-marrow MSC / `GSE224152` | Fiévet et al., *Stem Cell Research & Therapy* (2023) | [10.1186/s13287-023-03437-x](https://doi.org/10.1186/s13287-023-03437-x) |
| Whole-brain organoid / `GSE86153` | Quadrato et al., *Nature* (2017) | [10.1038/nature22047](https://doi.org/10.1038/nature22047) |
| hESC neural lineages / `GSE86982` | Furchtgott et al., *eLife* (2017) | [10.7554/eLife.20488](https://doi.org/10.7554/eLife.20488) |
| Cerebral organoid/neocortex / `GSE75140` | Camp et al., *PNAS* (2015) | [10.1073/pnas.1520760112](https://doi.org/10.1073/pnas.1520760112) |
| Human retina / `GSE138002` | Lu et al., *Developmental Cell* (2020) | [10.1016/j.devcel.2020.04.009](https://doi.org/10.1016/j.devcel.2020.04.009) |
| Cortical organoid stress / `GSE132672` | Bhaduri et al., *Nature* (2020) | [10.1038/s41586-020-1962-0](https://doi.org/10.1038/s41586-020-1962-0) |
| hiPSC chondrogenesis / `GSE160625` | Wu et al., *Nature Communications* (2021) | [10.1038/s41467-020-20598-y](https://doi.org/10.1038/s41467-020-20598-y) |
| hESC definitive endoderm / `GSE75748` | Chu et al., *Genome Biology* (2016) | [10.1186/s13059-016-1033-x](https://doi.org/10.1186/s13059-016-1033-x) |
| Commercial neural organoids / `GSE218457` | 公开 GEO 记录 | DOI 待核实 |
| Nishimura/Arenas | Nishimura et al., *Stem Cell Reports* (2023) | [10.1016/j.stemcr.2022.10.016](https://doi.org/10.1016/j.stemcr.2022.10.016) |
| Ásgrímsdóttir radial glia | Ásgrímsdóttir et al., *Nature Neuroscience* (2026) | [10.1038/s41593-026-02200-8](https://doi.org/10.1038/s41593-026-02200-8) |
| Luo fetal cerebellum / `GSE198565` | Luo et al., *Nature* (2022；已撤稿) | [10.1038/s41586-022-05487-2](https://doi.org/10.1038/s41586-022-05487-2) |
| hPSC teratoma scATAC / `GSE216323` | Liu et al., *Stem Cell Reports* (2023) | [10.1016/j.stemcr.2023.10.018](https://doi.org/10.1016/j.stemcr.2023.10.018) |
| Tiklová graft / `GSE118412`, `GSE132758` | Tiklová et al., *Nature Communications* (2020) | [10.1038/s41467-020-16225-5](https://doi.org/10.1038/s41467-020-16225-5) |

## 3. 评估内容

BRIDGE 以完整移植前 preparation 为评估对象，以 sample/preparation 为比较单位。各评估域分别输出 raw metrics、分域评估分数、证据充分性和限制，任何域的高分都不能抵消 unknown、证据不足或关键警报。

### 3.1 评估结果结构

每项评估结果包含：

- 可直接解释的 raw metrics 和分母。
- 输入充分且通过任务级分析验证时发布的 0-100 `domain_score`。
- 样本差异、模型差异和 reference 敏感性等不确定性。
- 当前证据状态、适用范围和限制。
- 可追溯的数据、分析结果、知识来源、`MeasurementSpec` 和 `ScoreContract` 版本。

`domain_score` 是各评估域独立的分数，只表示产品在已确认 ProductDefinitionCard、reference、prior 和测量合同下，对该域转录组证据要求的符合程度。它不表示临床效度、产品质量真值、疗效、安全性或 potency。

| `score_state` | `domain_score` | 发布含义 |
| --- | --- | --- |
| `available` | 0-100 | 已通过任务级分析验证，可作为正式分域分数发布 |
| `shadow` | 可有候选数值 | 方法或合同仍在验证，只能用于开发和辅助解释 |
| `unavailable` | `null` | 输入、适用性或必要证据不足，不计算也不补值 |

BRIDGE 的核心评估架构包括：

| 阶段 | 评估域 | 主要回答的问题 |
| --- | --- | --- |
| P0 | Target Identity | 完整制剂中有多少细胞支持声明的目标身份 |
| P0 | Regional Fidelity | 目标相关细胞是否具有正确的解剖区域身份 |
| P0 | Developmental Compatibility | 产品是否与研究者确认的目标发育窗口相容 |
| P0 | Off-target Control | 已知离轴状态的组成和负担如何 |
| P0 | Proliferation & Stress Response | 在不重新判定细胞身份或组成的前提下，是否出现偏离目标阶段背景、需要复核的增殖、应激、死亡相关程序或残余多能性样信号 |
| P1 | Regulatory Coherence | 产品是否具有与目标身份和阶段相容的调控状态 |
| P1 | Functional Program Readiness | 目标相关功能程序是否完整且方向一致 |
| P1 | Metabolic Integrity | 代谢和线粒体状态是否与目标阶段相容 |
| P1 | Assay Translatability | 计算结果能否转化为可执行的检测和分选指标 |
| P2 | Niche Compatibility | 产品内部通讯潜势及其空间支持是否与预期发育环境相容 |
| Gate | Unknown/OOD | 当前 reference 和模型不能可靠解释多少细胞 |
| Gate | Critical Alerts | 是否存在必须单独核查的高关注转录信号 |
| Gate | Evidence Sufficiency | 当前数据和证据是否足以支持相应结论 |

P0/P1/P2 表示实现和验证顺序，不表示科学重要性。五个 P0 域未来分别建立冻结的 `MeasurementSpec` 和 `ScoreContract`；P1 和 P2 域当前只展示 raw metrics、证据状态与缺口。完成独立分析验证后，才可通过新版本合同引入分域评分。

BRIDGE 不计算综合总分，也不生成跨场景绝对产品排名。

### 3.2 数据质量与可分析性

Agent 首先检查表达矩阵、数据层含义、基因标识、样本层级、metadata、细胞数量、基因覆盖、基础 QC 和稀有状态检测能力，并确定哪些评估模块可以运行。

该步骤输出 Data Readiness、可运行模块和证据缺口。技术质量不足不会被解释为生物学低分；受影响的结果标记为 `unavailable` 或降低证据充分性。

### 3.3 目标细胞与区域身份

Target Identity 评估完整制剂中支持预期细胞身份的比例，并将 acceptable adjacent 状态单独报告。

Regional Fidelity 评估腹侧中脑及底板区域支持，同时展示间脑、后脑、前脑或外周谱系等区域偏移。

报告包含 target 和 adjacent 组成、区域支持、主要偏移方向、不确定性及冲突证据。目标 marker 表达不足、模型不一致或 reference 覆盖不足分别说明。

### 3.4 发育状态与目标窗口

Agent 根据产品用途、分化阶段和已有独立证据，在交流过程中向用户提供多个候选目标窗口。

在已确认 PD-mDA 产品意图且有适用来源时，Agent 可以优先建议“移植用 VM floor-plate/mDA progenitor”，并说明更早的 patterning progenitor 或更晚的 immature mDA 候选窗口。建议不自动提交，也不预先认定当前产品适合哪个窗口；研究者必须显式确认。

研究者确认目标窗口后，BRIDGE 才计算 Developmental Compatibility 的 raw metrics 和发育画像。当前仍保持 `domain_score=null`；未确认窗口时继续报告主要发育状态与候选窗口依据，但该域 `score_state=unavailable`。

体外分化日与人胎 GW/PCW 分别保留，系统不自动换算，也不根据现有数据宣称全局最佳收获阶段。

### 3.5 完整制剂组成与 OOD

组成分析以全部移植前细胞为分母，区分：

- `target`
- `acceptable_adjacent`
- `known_off_target`
- `unknown`

报告展示各类比例、主要 off-target 状态、模型分歧和 unknown 组成。稀有异常状态同时报告当前细胞数支持的检测能力，区分“未检测到”和“当前数据无法排除”。

unknown 不自动计为 target 或已知 off-target。当 unknown 过高或 reference 覆盖不足时，Off-target Control 返回 `unavailable`，并由 Unknown/OOD gate 提示。

### 3.6 增殖、应激反应与关键警报

Proliferation & Stress Response 在已有 Cell-State 与组成证据基础上，评估与目标阶段相联系的增殖、stress、hypoxia、UPR、apoptosis、EMT 和其他转录程序偏移；它不重新判定细胞身份或计算 off-target 比例。

残余多能性样信号、严重异常增殖、明显非神经污染及无法解释的样本冲突进入 Critical Alerts。

Critical Alerts 独立展示，不被其他域的高分抵消。报告只能称为需要进一步核查的转录组证据，不能解释为临床安全性或肿瘤风险结论。

### 3.7 知识增强核心域

知识增强模块当前形成独立的 raw evidence panel，用于解释与 ProductDefinitionCard 中声明目标的相容程度。它们不采用“信号越强越好”的统一规则，也不生成候选分数。

| 评估域 | 主要内容 | 当前证据目标 | 解释边界 |
| --- | --- | --- | --- |
| Regulatory Coherence | TF 状态、调控网络、motif 和外部调控证据 | 目标身份和阶段所需调控程序的一致性 | inferred activity 不等于真实 TF 占位 |
| Functional Program Readiness | patterning、神经发生、dopamine、轴突、突触等程序 | 目标阶段相关功能程序的完整性和方向一致性 | 不等于实际功能或 potency |
| Metabolic Integrity | 线粒体、氧化还原、能量代谢、mitophagy 和代谢应激 | 代谢状态与目标阶段的相容程度 | 不等于真实代谢通量 |
| Assay Translatability | surfaceome、secretome、marker 组合和跨样本稳定性 | 计算结果转化为 flow、IF 或其他检测方案的可行性 | 高分表示更容易检测，不表示产品质量更高 |
| Niche Compatibility | sender-receiver、receiver response、ECM 和空间位置支持 | 产品内部互作潜势与预期发育环境的相容程度 | 不等于真实通讯或移植后微环境重建 |

每个域分别保存：

- `measured`：当前样本中直接测得的表达或蛋白证据。
- `inferred`：由模型和知识库推断的调控、通路、代谢或通讯状态。
- `prior_only`：外部知识支持，但当前样本尚未直接验证的关系。

P1/P2 当前保留 raw metrics、`domain_score=null`、`score_state=shadow/unavailable` 和证据缺口。只有满足数据覆盖、上下文匹配、跨样本稳定性和独立分析验证要求时，才可通过新的 `MeasurementSpec` 和 `ScoreContract` 引入正式分域评分。

对于仅有解离 scRNA-seq 的产品，Niche Compatibility 不发布正式分数，只报告 Communication Potential；其 `score_state` 保持 `shadow`。获得 receiver-response、空间、共培养或其他正交证据并完成分析验证后再晋升。

同一上游数据或知识来源支持多个域时，应标记为共享 evidence family，不能描述为多项相互独立的证据。

### 3.8 产品比较与稳定性

产品比较需要具有相容的 ProductDefinitionCard、目标窗口、sampling context 和 assay。统计和比较单位为 sample/preparation，单个细胞不作为独立生物学重复。

系统可以比较同一目标阶段下的不同方案和批次，也可以描述同一方案随时间的变化。输出包括：

- 各 P0 域的 raw metric 差异；只有未来同一冻结 ScoreContract 下才比较 `domain_score`。
- P1/P2 raw evidence 的探索性差异，并明确展示 `score_state=shadow/unavailable`。
- 主要细胞状态、程序和知识证据驱动因素。
- 批次、时间点、reference 和模型选择的影响。
- 结果的稳定性和不可比较项。

不满足可比条件时返回 `not_comparable`。不同目标窗口、产品类型或 assay 之间不强制排序。

### 3.9 证据充分性与改进建议

Evidence Sufficiency 分别展示 Data Readiness、Model Robustness 和 Prior Applicability，不合并成产品质量分。

| 状态 | 含义 |
| --- | --- |
| `negative` | 已完成适用且有足够检测能力的测量，未获得预先定义的目标证据 |
| `missing` | 必需的数据、metadata 或测量尚未提供 |
| `unknown` | 当前 reference、模型或知识不能可靠解释该状态 |
| `unavailable` | 因适用性、数据质量或前置条件不足，当前结果不能计算 |
| `alert` | 检测到需要人工复核和正交验证的高关注信号 |

当知识库覆盖不足、上下文不匹配或不同知识来源冲突时，相应知识增强域返回 `unavailable` 或保持 shadow，不能转换为低产品分数。

Agent 根据已获得的证据解释主要差异，提出可证伪的改进假设、补充测量和下一步验证实验。建议必须说明依据、预期观察结果和能够区分的解释，不直接给出未经验证的小分子剂量或处理时序。

### 3.10 graft 独立后验分析

graft 仅在存在明确 preparation-to-graft 关联时进行描述性分析。分析单位为 `animal/graft x post-transplant timepoint`，输出 graft 组成、成熟状态、异常状态及其与来源 preparation 的支持或冲突证据。

graft 的 scRNA-seq 和 snRNA-seq 需要分别处理。其结果不回填移植前分域评估分数、阈值或训练标签，也不用于生成疗效或安全性结论。

## 4. 分析工具与知识库

本章只确定分析任务、推荐工具组合、基本流程和发布条件。工具版本、参数、环境、许可证、完整输入条件、benchmark 及官方资料统一记录在 [P0 科学规格索引](bridge_spec_v0.1/README.md) 链接的任务卡、Tool Package Card 与知识快照中。

### 4.1 使用原则

- Agent 根据 ProductCase 选择已注册的分析任务。
- 每项任务先完成方法 benchmark，再冻结正式方法和独立校验方法。
- 工具与适用的 reference、ontology 或知识快照绑定使用。
- 每个正式 `domain_score` 必须绑定冻结的 `MeasurementSpec` 和 `ScoreContract`。
- 确定性工具负责计算，LLM 负责编排、检索、解释和报告。
- 输入或证据不足时返回 `unavailable`，不临时替换方法。
- 实时联网信息不改变当次分域评估分数。

### 4.2 P0 核心分析任务

| 分析任务 | 推荐工具与流程 | 主要输出 |
| --- | --- | --- |
| 输入审计与 QC | BRIDGE Case Validator → [AnnData](https://anndata.readthedocs.io/) → [Scanpy QC](https://scanpy.readthedocs.io/en/stable/api/scanpy.pp.calculate_qc_metrics.html)；Scrublet 条件运行 | Data Readiness、可运行模块和数据缺口 |
| Cell-State Evidence | 按 Anatomy、Lineage、Development 和 Process 分轴；透明基线、分类/映射方法及 ontology/open-set 方法分别 benchmark | 层级 prediction set、方法分歧和 unknown |
| 目标与区域身份 | Cell-State evidence → ProductDefinitionCard → marker 与独立 reference 校验 | Target Identity、Regional Fidelity |
| 发育状态 | 真实时间点组成与 pseudobulk → 发育 reference；[CellRank](https://cellrank.readthedocs.io/) 和 [scVelo](https://scvelo.readthedocs.io/) 条件运行 | 发育组成和 Developmental Compatibility |
| 完整制剂组成 | 对全部细胞聚合 target、adjacent、off-target 和 unknown，并估计稀有状态检测能力 | 组成比例、置信区间和 Off-target Control |
| 增殖与应激反应 | 阶段条件化的增殖、stress、hypoxia、UPR、apoptosis 等程序；CNV 工具保持 shadow | Proliferation & Stress Response 和 Critical Alerts |
| 产品比较 | sample/preparation 级 pseudobulk、组成比较、下采样及 reference/preprocessing swap | 差异驱动因素和稳定性 |

Cell-State 各状态轴分别比较 marker/program、reference correlation、监督分类、reference mapping、ontology-aware 和开放集方法；基础模型暂作为 shadow 候选。完成 source holdout、OOD、校准和跨模态测试后再冻结正式方法。

### 4.3 知识增强分析任务

| 分析任务 | 推荐工具与知识 | 发布条件 |
| --- | --- | --- |
| Regulatory Coherence | [decoupler](https://decoupler.readthedocs.io/) + CollecTRI；[pySCENIC](https://github.com/aertslab/pySCENIC) 独立校验；multiome 条件下使用 SCENIC+ | 区分表达、activity、regulon 和外部 motif/ChIP 证据 |
| Functional Program Readiness | 冻结功能程序 + AUCell；PROGENy、Reactome 和 GO 用于通路推断与解释 | 不解释为真实功能或 potency |
| Metabolic Integrity | MitoCarta 程序与 pseudobulk expression；flux 工具保持 shadow | 无代谢组或示踪时不称为真实通量 |
| Communication Potential | [LIANA](https://liana-py.readthedocs.io/)；CellPhoneDB 作为共享方法/知识家族的审计通道；receiver-response、空间或正交实验作为独立校验 | 解离 scRNA 只发布通讯潜势；共享 ligand-receptor 来源不重复计权 |
| 空间证据 | [SpatialData](https://spatialdata.scverse.org/) → cell2location → Squidpy | donor、section、坐标和 reference 满足要求后发布 |
| Assay Translatability | [HPA](https://www.proteinatlas.org/about/download) + [UniProt](https://www.uniprot.org/help/api_queries) + 产品表达和内部 assay catalog | 蛋白验证前只输出候选检测指标 |
| 改进假设 | 产品缺口 + Protocol IR + ChEMBL、PubChem、DGIdb 和扰动知识 | 最多三项可验证假设，不形成产品分数或给出剂量及时序 |

所有知识增强结果分别标记为 `measured`、`inferred` 或 `prior_only`。未经任务级验证的结果保持 shadow。

### 4.4 graft、证据与报告

| 分析任务 | 基本流程 | 边界 |
| --- | --- | --- |
| graft 后验分析 | 确认 preparation linkage → graft-specific QC 和状态映射 → animal/graft 级组成与状态比较 | 不回填移植前分域评估分数或训练标签 |
| Evidence 编译 | 工具结果、reference 和知识命中 → Evidence Record → Case Evidence Graph | 数字和来源必须可追溯 |
| 报告与 Claim 核验 | 确定性规则核对数字、比较资格和证据状态；LLM 生成受约束解释 | LLM 无权修改分数或批准发布 |
| Public-safe 输出 | 从字段白名单直接生成公开摘要 | 禁止输出私有 metadata、内部编号和路径 |

### 4.5 附录任务卡

每项分析任务建立独立任务卡，并由 [P0 科学规格索引](bridge_spec_v0.1/README.md) 导航，记录：

- 科学问题和适用场景。
- 官方文档、官方源码和方法依据。
- 候选工具比较与推荐理由。
- 输入、reference 和知识库依赖。
- 完整分析流程、参数和输出结构。
- 失败条件、拒答规则和结果边界。
- benchmark、验证数据和晋升标准。
- 软件版本、运行环境、资源和许可证。

只有状态为 `frozen` 且绑定有效 `MeasurementSpec` 和 `ScoreContract` 的任务卡可以发布正式 `domain_score`；`candidate`、`conditional` 和 `shadow` 结果只用于方法开发或辅助解释。

## 5. 部署与运行要求

BRIDGE 不依赖特定主机或固定硬件。每次工具运行必须绑定版本化的
`environment_spec_id`，并记录工具版本、输入 checksum、方法与 reference
版本及产物 manifest，使同一请求可以在兼容环境中复核。

部署环境需要满足以下要求：

- Python 版本、系统依赖和可选加速依赖由环境规范声明。
- CPU、内存、GPU 和临时存储按所选工具、数据规模及 reference 估算。
- 未公开数据与内部运行信息保留在受控环境；公开报告和仓库内容不得包含内部路径、凭据或私有标识。
- 资源不足、环境不兼容或输入不可访问时必须明确失败，不得静默降级为科学结论。

## 6. Agent 功能需求

BRIDGE 以 Web 作为主要交互界面。LLM 是主动的、证据驱动的研究协调者；
注册的高层工具拥有数值、分母、阈值、状态、版本和 Evidence ID。系统可以采用
单 Agent 或多 Agent 实现，但不得让模型文本取代确定性工具合同。

> **当前与目标必须分开：** 现有私有 Web 在既定范围内已验收下述主线第 1–6
> 步，包括 protocol 的可核对表示；这些步骤不重新设计或重做。第 7–10 步的
> 图驱动反馈循环、内部 comparator 推荐与确认、合格报告和导出是已批准目标。
> 当前已有的工具菜单、图组件、候选缺失图和 blocked 内部报告不能证明该闭环已接通。
> 精确现状见[验证记录](validation/README.md)，未完成科学工作见
> [Product Evidence Validation](../plans/product-evidence-validation.md)。

### 6.1 Agent 总体工作流

主线保持十步，不因内部对象或工具编号改变：

1. **Research question / 研究问题**：明确评估对象、要回答的问题和用途边界。
2. **Materials / 资料与数据**：登记不可变数据、protocol、metadata、reference
   与来源。
3. **Agent understanding and necessary questions / Agent 理解与必要追问**：
   只追问会改变资格、分析设计或解释的问题。
4. **Sourced fact confirmation / 有来源的事实确认**：研究者核对一份简洁的
   实验背景摘要，可整体确认或逐项修改。
5. **Scoped plan / 有边界的计划**：确认问题、总体范围、资源上限、停止条件和
   独立审批。
6. **QC / 输入质控**：运行注册 QC，显示实际观察、分母、限制和更新后的资格。
7. **Cell-state and product assessment / 细胞状态与产品评估**：逐域推进，
   每域标记 runnable、missing input 或 unavailable。
8. **Interpretation / 解释**：围绕证据图维护竞争假设、冲突、缺口和下一动作。
9. **Report delivery / 报告交付**：同一分析版本的结果页、简洁结论和完整报告。
10. **Corrections / 修正**：记录事实变化、影响范围和经确认的局部重算新版本。

第 1–6 步的当前验收只证明其既定输入、确认、审批、QC 和 protocol 表示流程；
不证明下游产品域已测量或报告可发布。第 7–10 步是产品目标合同；其中已有的
独立组件仍按各自验证记录报告，不把局部实现写成完整闭环。

在既定授权、范围和资源上限内，Agent 可自主继续已批准任务。QC 后必须重新计算
并展示实际 eligibility。扩大问题范围、资源上限、联网权限、比较队列或运行
未批准工具时，必须先申请新批准。

#### 6.1.1 主线逐步合同：用户动作与开发责任

| 步骤 | 研究人员看到什么、做什么 | Agent 与工具责任 | 停止或继续条件 |
|---|---|---|---|
| 1–2 | 描述问题并提供资料；可声明不知道 | Agent 登记原件、来源和声明，不从文件名猜 counts、样本关系或用途 | 损坏、不可读或矩阵语义不明时说明具体原因 |
| 3–4 | 审阅一份简洁、带来源的实验背景摘要；整体确认或逐项编辑 | Agent 区分 source fact absent 与 explicit-but-unparseable，标出冲突、不确定性和来源；只保留已确认事实 | 以后只追问新近变得 consequential 的信息；已知未知不反复追问 |
| 5 | 确认问题、总体分析范围、资源上限、复用项、停止条件和未批准计划 | Agent 绑定精确输入版本、reference、方法与资源；确认不等于执行 | 范围或资源扩大必须重新批准 |
| 6 | 查看 QC 观察、完整分母、限制及资格更新 | 工具计算 QC；Agent 显示 QC 前后 eligibility 的变化 | 不可填的输入或资源缺口明确停止；技术不足不解释为产品失败 |
| 7 | 看到全部 P0 核心维度及 runnable、missing input、unavailable 状态 | 分别评估 cell state、target identity、regional identity、developmental compatibility、whole-product/non-target composition、proliferation and stress；comparison 与 graft 有条件进入 | 五个 knowledge-enhancement dimensions 不替代本验收门 |
| 8 | 持续查看多维画像、关键发现、冲突和必要问题 | Agent 从 Evidence Graph 检索证据，维护小型竞争假设集，选择可区分假设的注册工具，把经验证输出写回图并更新解释 | 不按 LLM confidence 停止，不把同源方法数当独立票数 |
| 9 | 获得同一版本的结果页、简洁结论和可下载完整报告 | 报告绑定图、方法、来源、限制、下一动作及不完整/不可评估项 | 默认不发布、不分享；不满足声明或导出条件时保持 blocked |
| 10 | 先看到事实改动及受影响维度、比较和报告版本，再审阅局部更新计划 | 用户确认后才重算；旧版本保留，未受影响证据复用 | 事实或范围改变后的重算不同于既定事实/范围内的自主检查 |

每个停止说明都包括已知、未知、缺口、受影响结论、停止原因和可行下一步。预定义
evidence requirements、无法补齐的证据缺口或资源上限可以触发停止；LLM 自信度
不能。工具故障只允许合同中已批准的重试或替代路径。

#### 6.1.2 两个贯穿示例与验收方式

**单产品：** 研究者上传一个 D28 产品。独立培养关系未知时保留 unknown。
Agent 可完成已批准 QC 并展示候选 cell-state 对应，但在状态/角色审阅完成前，
不能把它换算成产品纯度或五域正式测量。验收检查原件、来源、分母、审批、实际
ToolRun、页面和报告版本是否一致。

**后续比较：** 研究者希望把新产品与已登记公开产品比较。Agent 先推荐 eligible
comparators、background-only objects 和 excluded objects 及原因，由用户确认
cohort。论文公开本身不等于登记、可比或获准使用；两个文件也不等于两个独立批次。

### 6.2 ProductCase 建立

QC 前必须确认 research question、overall analysis scope 和 resource ceiling。
ProductCase 保留产品目标、采样语境、assay/矩阵语义、sample/preparation/capture
关系、来源与访问策略；不知道的关系保持 unknown，cell 不能充当 biological replicate。

Agent 默认提供一份简洁的 sourced experimental-background summary，分别标记：

- 原文未提供的 source fact；
- 原文明示但当前 explicit-but-unparseable 的 fact；
- 多来源冲突、不确定或只适用于特定条件的 fact；
- 用户补充、系统观察和来源文本各自的身份。

研究者可以一次确认整份摘要，也可以逐项编辑。确认只记录事实版本，不自动批准
分析。后续只在信息新近影响 eligibility、方法、解释或资源时再问；保留 unknown
而不重复提问。

Protocol BPL 是来源绑定、可版本化和人工核对的计划过程表示。它不是本批执行记录、
产品身份、实验独立性或生物学验证；固定编译器通过也不证明语义完整。具体合同见
[已批准 BPL 设计](superpowers/specs/2026-09-09-protocol-bpl-design.md)。

如缺少 role rules，Agent 结合 P0-02 证据、已确认产品目标和可追溯材料，提出
role candidates 及其后果。用户核对不会提升候选科学等级。P0-03 与 P0-05 必须
消费同一个 eligible、reviewed role definition，不能各自循环发明角色。

### 6.3 分析计划与任务执行

AnalysisPlan 说明运行/跳过项、输入与版本、reference、MeasurementSpec、
分析单位、资源、联网与权限、复用、停止条件和允许的替代路径。QC 后的 eligibility
变化形成显式计划更新；未改变授权与资源时可自主继续，扩大范围则重新批准。

批准后的目标执行是反馈循环：

1. 从当前 Evidence Graph 检索支持、反对、缺失与冲突；
2. 识别缺口并维护少量相互竞争、可反驳的假设；
3. 选择最能区分假设的已注册高层工具；
4. 由工具验证输入并生成数值、分母、状态、版本和 Evidence ID；
5. 验证产物后写回图，更新画像、解释和下一动作。

存在图组件、工具菜单或一次编译不证明循环已连接。不得让 Agent 直接拼装底层
Scanpy/R 命令、修改工具值或把未执行域伪造成 MeasurementResult。

Step 7 总是提出现有 P0 核心维度：cell state；target 与 regional identity；
developmental compatibility；whole-product/non-target composition；
proliferation and stress。每项显示 runnable、missing input 或 unavailable。
Comparison 与 graft 仅在适用且获准时进入。状态描述覆盖所有 major cell classes，
只随证据细化；regional、developmental、proliferation 和 stress 轴保持分开，
upper-level 与 unresolved identity 不得被强制归入 target/non-target。

P0-06 对七个核心 program families 分别报告 measured 或 unavailable：
pluripotency-like、cell cycle、dissociation/heat-shock、oxidative stress、
hypoxia、unfolded-protein response、apoptosis-related。S/G2M 不能代表全部评估，
也不能证明真实增殖、安全性或 potency。

### 6.4 产品数据库与多产品比较

默认比较是 new product 与 eligible、internally registered published products，
不是要求用户同时上传多个产品。Agent 推荐：

- usable comparators；
- 仅作背景的 background-only objects；
- excluded objects 及逐项原因。

用户确认 cohort 后才执行。Publication alone is not registration,
comparability or permission。用户指定 reference/comparator 与系统默认对象分开
记录。sealed 与 competitor-isolated 数据始终排除在 reference、prior、校准、
正式 Evidence Graph 和比较队列之外。

默认 reference selection 使用一个经过审阅、内部对齐的 multi-source reference
system：共同定义与 decision rules、逐对象 applicability checks、source/version
traceability，以及无法消解的 genuine conflicts。它是已批准目标，不表示当前
candidate references 已 scientifically frozen。Agent 在获批范围内检查方法分歧，
展示实质差异，而不以多数票消解。

相同且适用的 measurement contract 下复用有效证据。版本或 measurement
definition 不同则提出 alignment/recomputation 方案，说明资源并取得批准；旧结果
保留，新结果另建版本。比较不替代 query product 的独立评估，也不形成绝对排名。

### 6.5 Evidence Graph 与冲突协调

Case/Comparison Evidence Graph 记录实体、MeasurementResult、来源、方法、
版本、证据家族、支持、反对、missingness、uncertainty、conflict 与 reconciliation。
同一 Evidence Family 去重；相关方法不计作独立投票。

Agent 主动查询图、识别缺口并推动 6.3 的反馈循环。停止只由预定义证据要求、
无法补齐的 evidence gap、资格或 resource limit 触发，并说明已知、未知与原因。
任何一项都不能由 LLM confidence 替代。

默认 reference 中的真实冲突继续保留；无法协调时降级解释范围或返回
unavailable/not_assessed。科学工具负责事实和数值，Agent 只组织问题、选择和解释。

### 6.6 Visualization Composer 与 Web 交互

#### 用户问题与默认阅读顺序

结果页是持续更新的 multidimensional portrait。每个维度都显示 state、
observation、limitations 和 next action。默认先回答数据能否分析和产品包含
什么，再回答身份/区域、发育、whole-product、proliferation/stress、证据缺口、
条件化 comparison/graft 和下一动作。Chat 只突出 consequential findings、
conflicts 和 necessary questions；不把技术日志重复成叙述。

#### 核心图表体系

| 维度 | 默认问题 |
|---|---|
| 输入与 cell state | 数据能否分析；主要 cell classes、状态、unknown/OOD 与 unresolved 是什么 |
| Target / regional | 目标谱系和区域证据是否符合 reviewed definition |
| Development | 与 reviewed developmental window 是否相容 |
| Whole product | 非目标、未知、稀有状态的完整分母是什么 |
| Proliferation / stress | 七个 program families 哪些 measured、conflicted 或 unavailable |
| Evidence / report | 结论有何支持、反对、缺口、声明与导出阻塞 |
| Conditional branches | 已确认 comparison cohort 或 linked graft 能回答什么 |

#### 阅读、交互与证据状态

从任一维度都能沿本地 evidence chain 下钻：support、opposition、missingness、
uncertainty、actual values 与 denominators、figures、methods、sources 和
versions。页面标明 same-family dependence，并允许进入相关 Evidence Graph
节点。关键值不能只放在 hover 中；键盘、触控与可下载表格应能获得同一信息。

不得使用综合总分、绝对排名、雷达图或红绿灯式产品等级。missing/unavailable
不画成 0；negative、missing、unknown、unavailable 与 alert 分开。candidate、
shadow 和 exploratory 始终显示文字状态，所有 active domain 保持
domain_score=null。

#### 正式图形的数据绑定

正式图形消费 typed、checksummed visualization data artifact；Web 与静态导出
使用同一数据。当前 registry 的 43 个组件（36 typed_candidate、7
legacy_untyped）是审计记录，不是证据得分或完整交互验收。完整数据绑定和图族
验收见[Visualization Data Contract](../plans/visualization-data-contract.md)及其
[验证记录](validation/visualization_data_contract_20260828.md)。

#### 出版、无障碍与实现顺序

先验收科学问题、数据绑定、分母、区间、缺失状态、表格 fallback 和确定性静态
SVG/PDF/PNG，再实现 Web 布局和交互。颜色不能单独表达状态；desktop、mobile、
静态导出和机器可读表格必须表达同一观察与限制。未登记组件只作 exploratory，
不得进入正式报告。

### 6.7 解释、建议与迭代

Agent 保持少量 competing hypotheses，并为每个假设记录支持、反对、缺失、
区分性下一工具、预期观察和反驳条件。建议优先补足会改变决策的事实或测量，
最多展示三项可执行 next actions；不提供未经验证的小分子剂量或处理时序。

方法不一致时，先确认是否属于相同定义、输入、分母和适用范围，再分别展示结果
及其实质差异。共同输入或同源 reference 必须标注依赖，不能把方法数量当置信度。

Agent 应主动检查可用 linked post-transplant data 的 relevance 与 eligibility，
提出它能回答的问题和所需资源；只有用户把它纳入批准范围后才执行。graft 是独立
后验证据，永不回填移植前评分、阈值、训练、校准或判断。

### 6.8 报告核验与发布

默认交付同时包含：

- 可下钻的 result page；
- concise conclusion；
- 与同一 analysis version 绑定的 downloadable full report；
- figures、methods、sources、limitations、next actions；
- 明确的 incomplete 和 unassessable parts。

默认不自动 publish 或 share。Claim Verifier 检查数值/单位/状态与 Evidence ID
对应、比较资格、exploratory 越界、禁止主张和 public-safe 字段。失败保持
release_blocked；P0-11 只生成或审计本地候选，不验证授权身份，也不执行发布。

事实修正先记录 change，列出受影响 dimensions、comparisons 与 report versions，
然后提出 partial update plan。用户确认后才重算；旧版本保留，未受影响证据复用。
这与 unchanged facts/scope 下 Agent 的自主检查明确分开。

### 6.9 P0 验收要求

**当前流程验收：** 第 1–6 步在既定范围内已接受；验证记录分别说明源代码、
安装、真实运行和科学含义。不得由此声称第 7–10 步闭环、内部 comparator 选择或
qualified export 已完成。

**下游目标验收：**

- 真实上传案例能从 reviewed facts/QC 进入完整 Step 7 核心维度，并逐项呈现
  runnable、missing input、unavailable、measured 与限制；
- Evidence Graph 反馈循环真实连接，工具输出经验证写回，竞争假设和解释随证据更新；
- 默认内部 reference/comparator 系统经过审阅、对齐、适用性检查和来源版本绑定；
- 报告页、结论与下载报告绑定同一版本，事实修正只重算受影响依赖；
- 至少一名湿实验用户和一名 Agent 实现者完成真实 Web、证据与报告走查。

**科学资格仍独立：** ProductDefinitionCard、role/window 定义、五个 domain 的
MeasurementSpec/ScoreContract、source/modality holdout、OOD、下采样、
reference/preprocessing sensitivity 和预注册阈值必须分别冻结并验证。重复不足
保持 descriptive_only/not_estimable；正式 domain_score 仅在上述资格满足后
可产生。系统不输出临床疗效、安全性、validated potency、GMP 放行或跨场景
绝对产品排名。

## 7. 附录

| 附录 | 文档 | 用途 |
| --- | --- | --- |
| A | [数据与 Reference Registry](bridge_spec_v0.1/data_reference_registry.md) | 数据角色、血缘、状态、访问与评测资格 |
| B | [Tool Package Cards](../src/bridge/tool_packages/cards/) | 工具、输入、输出、边界、环境和实现状态 |
| C | [Knowledge Catalog](../knowledge/README.md) | 打包知识快照、当前方法短名单与策展入口 |
| D | [Conda Environment Contracts](../environments/README.md) | 工具运行所需的通用 Conda 环境合同 |
| E | [P0 Scientific Specifications](bridge_spec_v0.1/README.md) | 各分析任务合同、验证要求和发布状态 |
| F | [Public JSON Schemas](../src/bridge/resources/schemas/) | 当前 Agent、证据、比较、可视化和运行对象合同 |
| G | [Validation Records](validation/) | 当前工程集成和科学 pilot 证据 |
