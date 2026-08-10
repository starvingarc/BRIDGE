# BRIDGE v2 Knowledge Registry

## 文档信息

| 项目 | 内容 |
| --- | --- |
| Registry 版本 | `KNOWLEDGE-v0.1` |
| 审计日期 | 2026-08-03 |
| 运行原则 | 正式评估只读取版本化本地 snapshot；实时联网内容不改变当次分域评估分数 |
| 首个应用 | PD hPSC-mDA 产品的身份、区域、发育、组成、过程和机制解释 |

本表中的数据库为候选来源。只有完成版本、许可、上下文、证据家族和专家审核的记录，才进入正式 `BiologicalPriorRegistry`。

## 一、Knowledge Card 合同

```text
knowledge_id / snapshot_id / source_version / retrieval_date
knowledge_type / subject / relation / object / direction
species / anatomy / developmental_stage / cell_state / assay
source_database / source_record_id / source_url
publication_id / evidence_type / evidence_grade
evidence_family_id / upstream_sources
license / redistribution_policy / required_attribution
allowed_use: Q | E | D | G
context_match / contraindications / conflicts
curation_state / reviewer / approval_date
content_hash
```

Allowed use：

| 代码 | 用途 | 规则 |
| --- | --- | --- |
| `Q` | Quantification | 可以产生 raw metric；发布正式 `domain_score` 仍需冻结的 MeasurementSpec 与 ScoreContract |
| `E` | Explanation | 可以解释观测和机制冲突，不改变分数 |
| `D` | Diagnostic direction | 可以指出需要补充哪类证据，不直接给出工艺剂量 |
| `G` | Gate/Alert | 控制适用性、拒答或独立警报，不取反后并入总分 |

## 二、快照设计

| Snapshot ID | 内容 | P0 状态 | 默认用途 |
| --- | --- | --- | --- |
| `KB-CORE-ID-v1` | gene ID、Cell Ontology、anatomy ontology、产品 ontology crosswalk | `proposed_P0` | `Q/E/G` |
| `KB-PD-DEVELOPMENT-v1` | 独立人胚 vMB reference、专家 marker/program、阶段和 off-axis ontology | `proposed_P0` | `Q/E/G` |
| `KB-RISK-PROCESS-v1` | stage-aware risk/process programs 与 severity rules | `proposed_P0` | `Q/E/G` |
| `KB-REGULATORY-v1` | TF-target、motif、ChIP/cCRE、regulon evidence | `proposed_P1` | `shadow Q/E` |
| `KB-PATHWAY-METABOLIC-v1` | pathway footprint、functional programs、metabolic/mitochondrial knowledge | `proposed_P1` | `shadow Q/E` |
| `KB-INTERCELL-v1` | ligand-receptor、complex、ECM、receiver-response | `proposed_P1` | `E/D` |
| `KB-ASSAYABILITY-v1` | surfaceome、secretome、protein localization 和 assay translation | `proposed_P1` | `E/D` |
| `KB-PERTURB-v1-draft` | compound-target-action 与 perturbation signatures | `deferred_for_scoring` | `E/D` |

每次正式运行引用具体 snapshot ID 与 content hash，禁止使用 `latest` 作为不可追溯版本。

## 三、标识符与 Ontology

| Knowledge ID | 官方来源 | 内容 | 许可/使用条件 | BRIDGE 用途 | 状态 |
| --- | --- | --- | --- | --- | --- |
| `KB-HGNC` | [HGNC downloads](https://www.genenames.org/download/) | approved symbol、alias、previous symbol、HGNC ID | 按 HGNC 官方使用条款与引用要求冻结 | gene symbol normalization；`Q/E/G` | `candidate_P0` |
| `KB-ENSEMBL` | [Ensembl data access](https://www.ensembl.org/info/index.html) | Ensembl gene/transcript ID、assembly、biotype | 数据开放；软件 Apache-style；保存 release | feature mapping、genome build；`Q/E/G` | `candidate_P0` |
| `KB-CELL-ONTOLOGY` | [Cell Ontology](https://cell-ontology.github.io/) | 标准 cell type concept 与层级 | CC BY 4.0；保存 dated release | state hierarchy 与 ontology distance；`Q/E/G` | `candidate_P0` |
| `KB-UBERON` | [Uberon releases](https://uberon.github.io/downloads.html) | multi-species anatomy 与 anatomical relations | OBO open-license release；保留 release LICENSE | midbrain/forebrain/hindbrain 等区域关系；`Q/E/G` | `candidate_P0` |
| `KB-GO` | [Gene Ontology downloads](https://geneontology.org/docs/download-ontology/) | biological process、molecular function、cellular component | [CC BY 4.0](https://geneontology.org/docs/go-citation-policy/)，必须记录 dated release | program annotation 与解释；`E`，验证后 shadow `Q` | `candidate_P1` |

Cell Ontology 和 Uberon 不能直接覆盖 BRIDGE 的产品状态定义。团队必须建立一个版本化 crosswalk，将专家定义的 PD-mDA state 映射至标准 ontology，并保留无法一一对应的内部概念。

## 四、PD 发育、解剖与产品知识

| Knowledge ID | 来源 | 记录内容 | Allowed use | 状态与限制 |
| --- | --- | --- | --- | --- |
| `KB-CHEN-VMB-STATE` | Chen vMB sc/sn + 专家审核 | target、acceptable adjacent、off-axis state、marker 与 stage evidence | `Q/E/G` | P0 核心；需与 sample/reference lineage 一起冻结 |
| `KB-INDEPENDENT-VMB` | Braun、Zeng、La Manno、Birtele 等独立研究 | anatomy、developmental stage、state/program 支持 | `Q/E/G` | source-specific；共享细胞/论文时去重 |
| `KB-PD-PRODUCT-CARD` | 湿实验团队 | intended stage、产品成分、不可接受状态、critical alerts | `Q/E/G` | 必须人工批准；论文中的“product”命名不能自动进入 |
| `KB-SISBAR-TRANSITION` | SISBAR lineage data | 直接观测的 state transition support | `Q/E` | 仅限匹配实验与阶段，不外推最佳收获日 |
| `KB-PROTOCOL-IR` | 用户 SOP 与培养 metadata | 因子、小分子、基质、时间、washout、冻存/复苏 | `E/D/G` | 未知字段保持 unknown；不按实验室惯例补全 |
| `KB-SPATIAL-ANATOMY` | hEB58、后续空间与 marker 染色 | marker/state 的组织位置和 ROI evidence | `E`，验证后 `Q` | 当前同胚胎 section 不构成独立重复 |

### Clean-room 规则

- 竞争研究的论文、代码、reference、marker/program、标签、模型、阈值和权重不进入 BRIDGE prior、RAG、训练或校准。
- 合法取得的竞争 query 数据只能作为 `competitor_sealed_test`，必须在 BRIDGE snapshot、算法和报告规则冻结后运行。
- 当前 query 对应原论文的作者结论和产品标签，在结果冻结前不得进入分析检索上下文。
- 竞争论文可以出现在背景综述和差异化讨论中，但其方法内容不转写为 BRIDGE 算法合同。

## 五、调控先验

| Knowledge ID | 官方来源 | 内容 | 许可/血缘风险 | Allowed use | 状态 |
| --- | --- | --- | --- | --- | --- |
| `KB-JASPAR` | [JASPAR](https://jaspar.elixir.no/) | curated non-redundant TF binding profiles | CC BY 4.0 | motif edge support；`E`，验证后 shadow `Q` | `candidate_P1` |
| `KB-CISTARGET` | [Aerts Lab cisTarget databases](https://resources.aertslab.org/cistarget/databases/) | genome-wide motif/track rankings 与 motif-TF annotation | 必须冻结数据库版本、genome 与许可文件 | pySCENIC motif pruning；`E` | `candidate_P1` |
| `KB-HOCOMOCO` | [HOCOMOCO](https://hocomoco12.autosome.org/) | human/mouse TF binding models | snapshot 前完成当前 license 与 redistribution 审计 | motif sensitivity channel；`E` | `candidate_license_review` |
| `KB-COLLECTRI` | [OmniPath CollecTRI](https://omnipathdb.org/) | signed TF-target interactions | composite resource，继承上游来源许可；不能只记录聚合库 | decoupler TF activity；shadow `Q/E` | `candidate_P1` |
| `KB-DOROTHEA` | [OmniPath/DoRothEA](https://omnipathdb.org/) | confidence-graded signed TF-target interactions | OmniPath 标记为 informal/source-dependent license，需逐源审计 | independent TF activity sensitivity；`E` | `candidate_license_review` |
| `KB-ENCODE` | [ENCODE](https://www.encodeproject.org/) | cCRE、ChIP-seq、eCLIP 与实验 metadata | [公开数据使用政策](https://www.encodeproject.org/about/data-use-policy/)，需引用 accession | external edge annotation；`E` | `candidate_P1` |
| `KB-REMAP-CHIPATLAS` | ReMap / ChIP-Atlas official releases | aggregated ChIP binding evidence | 各 release 与上游实验许可逐项审计 | edge corroboration；`E` | `candidate_license_review` |
| `KB-PYSCENIC-REGULON` | Chen/independent data-driven regulons | GRN、motif-pruned regulon、AUCell | 必须记录 parent expression 与 motif DB | 独立 data-driven channel；shadow `Q/E` | `candidate_P1` |

解释层必须区分：TF expression、signed TF activity、data-driven regulon、motif support、ChIP/cCRE support。没有 ATAC/multiome 时，motif 或 ChIP prior 不能证明 query 中 enhancer 开放或 TF 占位。

## 六、Pathway、功能与代谢知识

| Knowledge ID | 官方来源 | 内容 | 许可/版本规则 | Allowed use | 状态 |
| --- | --- | --- | --- | --- | --- |
| `KB-REACTOME` | [Reactome downloads](https://reactome.org/download-data) | curated reactions、complexes、pathway hierarchy | Creative Commons license agreement；使用季度/Zenodo release | process explanation；`E`，验证后 shadow `Q` | `candidate_P1` |
| `KB-PROGENY` | [OmniPath PROGENy](https://explore.omnipathdb.org/) | perturbation-derived pathway footprints | OmniPath Explorer 标示 Apache-2.0；冻结版本 | signed pathway activity；shadow `Q/E` | `candidate_P1` |
| `KB-SIGNOR` | [SIGNOR via OmniPath](https://omnipathdb.org/) | signed directed signaling relations | 源数据 CC BY 4.0；保留原 source IDs | mechanism-chain explanation；`E` | `candidate_P1` |
| `KB-MSIGDB` | [MSigDB license terms](https://www.gsea-msigdb.org/gsea/license_terms_list.jsp) | curated/hallmark/ontology gene sets | release-specific license；部分 gene sets 有附加条款 | sensitivity/interpretation；`E` | `candidate_license_review` |
| `KB-KEGG` | [KEGG licensing](https://www.pathway.jp/en/licensing.html) | pathway、reaction 与 compound knowledge | 再分发和部分使用需要订阅/许可 | 不进入默认本地 snapshot | `deferred_license` |
| `KB-MITOCARTA` | Broad MitoCarta release | mitochondrial localization/function | 冻结 release、citation 与官方 terms | mitochondrial program；shadow `Q/E` | `candidate_P1` |
| `KB-EXPERT-FUNCTION` | 专家定义并有来源的程序卡 | dopamine synthesis、vesicle、axon、synapse、excitability 等 | 每个 gene/edge 记录来源和方向 | program completeness/coherence；shadow `Q/E` | `proposed_P1` |

Reactome/GO 成员关系主要用于解释。进入量化时必须指定方向、background、gene coverage、null 和验证，不以简单基因均值替代 pathway activity。

## 七、细胞通讯与微环境知识

| Knowledge ID | 官方来源 | 内容 | 许可/血缘规则 | Allowed use | 状态 |
| --- | --- | --- | --- | --- | --- |
| `KB-OMNIPATH-INTERCELL` | [OmniPath](https://omnipathdb.org/) | ligand、receptor、ECM、complex、contact 与 intercellular roles | 聚合服务无统一 data license，每条记录继承上游许可 | communication potential；`E/D` | `candidate_P1` |
| `KB-CELLPHONEDB-DATA` | [CellPhoneDB](https://cellphonedb.readthedocs.io/) | curated ligand-receptor interactions、多亚基 complexes | 软件 MIT；数据库 release 与上游来源单独冻结 | complex audit；`E` | `candidate_P1` |
| `KB-LIANA-RESOURCE` | [LIANA](https://liana-py.readthedocs.io/) | 统一的 ligand-receptor resources 与 method consensus | 软件 GPL-3.0；每个 underlying resource 保留 provenance | method consensus；`E` | `candidate_P1` |
| `KB-NICHENET` | NicheNet official resources | ligand-receptor-target prior | 记录网络来源、物种和 license | receiver-response hypothesis；`E/D` | `candidate_P2` |
| `KB-EXTERNAL-CULTURE` | Protocol IR | 外源 SHH/FGF/WNT modulators、growth factors 和 matrix | 用户提供，版本化 | external environment node；`E/G` | `proposed_P1` |

同一 ligand-receptor edge 经 OmniPath、LIANA 和 CellPhoneDB 重复出现时共享 evidence family，不能视为三份独立证据。解离 scRNA 只支持通信潜势；空间邻接、阻断或蛋白测量到位后才能升级证据等级。

## 八、Surfaceome、Secretome 与 assay translation

| Knowledge ID | 官方来源 | 内容 | 许可/使用要求 | Allowed use | 状态 |
| --- | --- | --- | --- | --- | --- |
| `KB-HPA` | [Human Protein Atlas downloads](https://www.proteinatlas.org/about/download) | tissue/cell expression、subcellular、secretome 和 protein class | [CC BY 4.0](https://www.proteinatlas.org/about/licence)；部分第三方数据另有限制 | surface/secretory potential；`E/D` | `candidate_P1` |
| `KB-UNIPROT` | [UniProt](https://www.uniprot.org/) | protein sequence、subcellular location、signal peptide、function | [CC BY 4.0](https://www.uniprot.org/help/license)；保留 accession/release | protein localization support；`E/D` | `candidate_P1` |
| `KB-HUMAN-SECRETOME` | [HPA Human Secretome](https://github.com/human-protein-atlas/human-secretome) | predicted secreted/membrane/intracellular classification | 按 HPA 与仓库 release 条款引用 | secretory potential；`E/D` | `candidate_P1` |
| `KB-CSPA-SURFY` | CSPA/SURFY official releases | cell-surface protein candidates | 每个资源独立完成 license 与版本审计 | flow panel candidates；`E/D` | `candidate_license_review` |
| `KB-ASSAY-CATALOG` | 团队抗体、flow/IF/qPCR/ELISA 经验卡 | assay availability、species/reactivity、control、LOD/LOQ | 内部版本化，不含供应商受限内容再分发 | evidence-gap translation；`D` | `proposed_P1` |

mRNA 只支持 surface/secretory potential。flow、CITE-seq、IF、ELISA 或蛋白组结果到位后，才建立 measured protein evidence。

## 九、小分子、靶点与扰动知识

P0 暂不自动输出工艺优化。该知识域先建立可审计底座，为未来诊断和人工设计实验服务。

| Knowledge ID | 官方来源 | 内容 | 许可/上下文 | Allowed use | 状态 |
| --- | --- | --- | --- | --- | --- |
| `KB-CHEMBL` | [ChEMBL](https://www.ebi.ac.uk/chembl/) | compound-target bioactivity、assay、action context | [CC BY-SA 3.0](https://chembl.github.io/chembl-licensing/)；必须记录 release、assay、species 和 directness | target/action context；`E/D` | `candidate_P2` |
| `KB-PUBCHEM` | [PubChem downloads](https://pubchem.ncbi.nlm.nih.gov/docs/downloads) | compound IDs、structures、BioAssay 与 contributor annotations | NCBI policy；内容许可可能随 contributor 变化 | identifier crosswalk；`E` | `candidate_P2` |
| `KB-DGIDB` | [DGIdb](https://dgidb.org/about/overview/data-accessibility) | drug-gene interactions 与 druggable categories | code MIT；数据开放但上游 source 许可逐项保留 | candidate target lookup；`E/D` | `candidate_P2` |
| `KB-LINCS-CMAP` | LINCS/CLUE official releases | perturbational expression signatures | 必须完成账户、下载、API 和 redistribution terms 审计 | context-matched signature interpretation；`E/D` | `candidate_terms_review` |
| `KB-DRUGBANK` | [DrugBank academic access](https://go.drugbank.com/academic_research) | drug、target、enzyme、transporter 等 | 需要许可且限制再分发；当前 academic download 状态需复核 | 默认不纳入本地可分发 snapshot | `deferred_license` |
| `KB-PERTURB-PUBLIC` | 匹配神经/mDA 的公开 perturbation studies | treated/control、dose、time、cell context、response | study-specific license 与 source independence | future diagnostic calibration；`E/D` | `proposed_P2` |

所有候选必须报告 target expression、cell-state selectivity、mechanism direction、cell type/dose/time context mismatch 和冲突。CMap 或公开论文浓度不得直接转写为 mDA 培养剂量。

## 十、证据等级

| Evidence grade | 最低要求 | 可支持的表述 |
| --- | --- | --- |
| `measured_current_case` | 当前 case 的直接 assay 结果 | “当前样本检测到……” |
| `computed_current_case` | 注册工具从当前 case 计算，完整 provenance | “算法估计/计算……” |
| `matched_external` | 物种、区域、阶段、cell state、assay 高匹配的独立证据 | “独立证据支持该解释……” |
| `partial_context` | 仅部分上下文匹配 | “提供候选机制解释……” |
| `prior_only` | 数据库/文献中存在，但当前样本未测 | “外部知识提示……” |
| `conflicted` | 来源间方向或适用范围冲突 | “现有证据不一致……” |

Agent 不得将 `prior_only` 写成当前产品观测，也不得将 `partial_context` 用作窄置信区间的正式量化证据。

## 十一、Evidence family 去重

以下记录视为同一或相关 evidence family：

- 同一 PMID/DOI、accession、donor、实验或 supplementary table 的重复收录。
- OmniPath、LIANA、CellPhoneDB 等聚合库共享的上游 interaction。
- 同一 reference 训练出的不同 classifier 或 embedding。
- marker、regulon、pathway 中复用相同上游实验或大量相同 genes/edges。
- source data 与其 filtered、sampled、integrated 或 pseudobulk derivative。

`evidence_family_id` 用于相关性上限、冲突展示和防止重复计权，不用于删除不同层级的可解释证据。

## 十二、本地检索与离线策展

### 正式运行

1. 根据 ProductCase 生成 species/anatomy/stage/cell-state/assay filters。
2. 只检索 Card 允许的 snapshot。
3. 返回 source record、allowed use、context match、conflicts 和 evidence family。
4. 将命中写入 `KnowledgeRetrievalRecord`。
5. 任何 `Q/G` 结果仍由确定性 MeasurementSpec 计算。

### 实时联网

Agent 可以查找新论文、数据库更新或冲突来源，并生成：

```text
retrieval_query / trigger
source_url / publication_id / retrieval_time
extracted_claim / context_match / conflict
license_note / proposed_allowed_use
state = transient_external_evidence
```

实时结果只能用于解释和策展候选。它不能进入当次分域评估分数、阈值或 gate。

### 离线 Curator

1. 回到原始论文或官方数据库记录。
2. 核查方向、物种、区域、阶段、assay、统计单位和限制。
3. 核查许可、再分发和引用要求。
4. 分配 evidence family 与 allowed use。
5. 由生物学 reviewer 批准或拒绝。
6. 生成新 snapshot 和 changelog。

## 十三、Snapshot 晋升检查

- 每个条目都有稳定 source ID、版本、retrieval date 和 content hash。
- 每个 Q/G prior 有匹配的 MeasurementSpec 和独立验证计划。
- 聚合库保留所有上游来源与许可，不以聚合库名称遮蔽限制。
- query study、competitor denylist 和 validation 数据未泄漏进 prior derivation。
- 冲突知识保留，不以多数投票静默删除。
- 所有可再分发内容满足 attribution 与 share-alike 要求。
- 未通过 license、context 或专家审核的条目保持 draft/deferred。
