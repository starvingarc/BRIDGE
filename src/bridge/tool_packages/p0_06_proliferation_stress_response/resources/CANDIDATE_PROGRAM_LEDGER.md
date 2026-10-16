# P0-06 七类程序资源台账（2026-09-23，候选）

本台账只核查可追溯来源、当前真实输入和可解释范围；不冻结 `ProgramSpec`、阈值、发育窗口或产品角色，不授予正式评分资格。`source located`、`content frozen`、`method executed`、`scientifically qualified` 是四种不同状态。

下表保留候选来源初审；后续资源冻结与执行状态以“Hallmark 描述性执行”和“两种原始 CSV 的候选适配”节为准。

| PRD 程序族 | 精确候选来源与许可 | 原始定义和场景 | 来源初审状态 | 不能据此声称 |
| --- | --- | --- | --- | --- |
| `PROC-PLURI` residual pluripotency-like | Hu et al. 2020 的 human ESC 26-gene Table S1 [原文](https://pmc.ncbi.nlm.nih.gov/articles/PMC7260443/)；文章/补充材料标为 CC BY-NC-ND 4.0。另有 Reactome [R-HSA-452723](https://reactome.org/content/detail/R-HSA-452723)，其数据库数据 [CC0](https://reactome.org/license)。 | 前者是 ESC/fibroblast 对照中的先验 marker，不是 PD-mDA 中残留细胞检出器；后者仅为通路成员。 | 未在包内冻结可再分发的方向性签名，未执行。需要同来源 D0 spike-in、阶段匹配阴性、稀有态 LOD 和 P0-02 身份交叉验证。 | 残留比例、转化/致瘤性、产品不合格。 |
| `PROC-CYCLE` stage-conditioned cell cycle | 包内 `seurat-cell-cycle-v5.5.1-candidate.json`，SHA-256 `0a5c8381d7fab6f2d7ab97bbf95af45953be4c8f49df6ec578bf2c70c75dff73`；[Seurat MIT](https://github.com/satijalab/seurat/blob/main/LICENSE.md)。 | Seurat `cc.genes.updated.2019` 原样 S/G2M 符号；Scanpy phase 和两种不同单位的分数。 | 资源已冻结为 candidate；selected-view 描述性方法已有运行证据。发育阶段、角色和生物学独立性须分别核实。 | 分裂速率、异常增殖、静息证明、独立重复或发布资格。 |
| `PROC-DISSOC` dissociation/heat-shock | O'Flanagan et al. 2019 [论文](https://pmc.ncbi.nlm.nih.gov/articles/PMC6796327/) CC BY 4.0；[作者源码仓库](https://github.com/kieranrcampbell/scrnaseq-digestion-paper) 的 `coregene_df-FALSE-v3.csv` 在 commit `a623cd950e18191ad69a5b2c0fab343248893f81`，下载字节 SHA-256 `8c9dcbda7c2e797d70071f23f645581727892f49a15602a5dfda1e8cc7dbde17`，仓库未声明 LICENSE。 | 37°C collagenase 对比 6°C protease、肿瘤/PDX 细胞；512 行，其中 507 up、5 down；三个 `gene_symbol=NA`，故不能直接当 512 个唯一人类符号。 | 原始候选数据可追溯，但 repo 再分发许可、符号清理与 PD-mDA 协议可比性未解决；未打包或运行。 | 没有 protocol/可比对照时的解离归因；“压力即质量缺陷”。 |
| `PROC-OXSTRESS` oxidative/acute stress | MSigDB human [HALLMARK_REACTIVE_OXYGEN_SPECIES_PATHWAY](https://www.gsea-msigdb.org/gsea/msigdb/human/geneset/HALLMARK_REACTIVE_OXYGEN_SPECIES_PATHWAY)，49 genes；Hallmark 适用 [CC BY 4.0 条款](https://www.gsea-msigdb.org/gsea/msigdb_license_terms.jsp)。Reactome [ROS detoxification](https://reactome.org/content/detail/R-HSA-3299685) 为 CC0 通路成员，不是方向性响应签名。 | Hallmark 描述“ROS 诱导上调”基因；并非 MPP+/rotenone 或 PD-mDA 专用，药物诱导与内源氧化状态不能混同。 | 官方来源及许可已定位；精确 release、成员文件 hash、当前 view 覆盖和扰动方向校验未冻结；未运行。 | 氧化损伤程度、通用产品质量、工艺归因。 |
| `PROC-HYPOXIA` hypoxia | Abou Khouzam et al. 2021 [Table 2](https://pmc.ncbi.nlm.nih.gov/articles/PMC8173254/) CC BY，8 个上调基因：`DDIT4, LDHA, MXI1, NDRG1, P4HA1, PGK1, SLC2A1, VEGFA`。MSigDB human [HALLMARK_HYPOXIA](https://www.gsea-msigdb.org/gsea/msigdb/human/geneset/HALLMARK_HYPOXIA) 是另一个候选，不作为同源独立证据重复计数。 | 原文在 14 种癌细胞系 1% O2/24h 与胰腺癌 bulk 数据中验证；原文肿瘤 HS 是跨样本 median 二值化后求和，不能直接照搬为单细胞分数。 | 可考虑“跨场景候选基因程序表达”；尚未验证 PD-mDA 适用性，基因可映射本身不授予科学资格。 | 实测氧张力、原文 HS 复现、胰腺癌阈值转移、PD-mDA 低氧判定。 |
| `PROC-UPR` unfolded protein response | MSigDB human [HALLMARK_UNFOLDED_PROTEIN_RESPONSE](https://www.gsea-msigdb.org/gsea/msigdb/human/geneset/HALLMARK_UNFOLDED_PROTEIN_RESPONSE)，113 genes；Hallmark [CC BY 4.0](https://www.gsea-msigdb.org/gsea/msigdb_license_terms.jsp)。Reactome [R-HSA-381119](https://reactome.org/content/detail/R-HSA-381119) 仅为通路。 | MSigDB 定义为 UPR 中上调基因；包含来自多组织/扰动的 founder/refinement 来源，并非 PD-mDA 特异。 | 精确 release、内容 hash、基因覆盖和 tunicamycin/非 UPR 对照敏感性未冻结；未运行。 | ER stress 功能确证、药物应答程度、质量或安全结论。 |
| `PROC-APOPTOSIS` apoptosis-related | MSigDB human [HALLMARK_APOPTOSIS](https://www.gsea-msigdb.org/gsea/msigdb/human/geneset/HALLMARK_APOPTOSIS)，161 genes；Hallmark [CC BY 4.0](https://www.gsea-msigdb.org/gsea/msigdb_license_terms.jsp)。Reactome [R-HSA-109581](https://reactome.org/content/detail/R-HSA-109581) 为 CC0 通路成员。 | 官方描述为介导 caspase 凋亡的基因，非一致上调的死亡状态签名；既含促凋亡也含存活/调节作用。 | 可作为机制成员表达的候选，不能把等权单细胞分数解释为 apoptosis rate；无匹配活/死、Annexin V 或 caspase 真值；未运行。 | 细胞死亡比例、存活率、细胞毒性或临床安全。 |

## 当前输入与最小复用路径

### Hallmark 描述性执行

P006 0.10.0 的注册入口支持 source-bound 多程序描述。使用 MSigDB 官方
[2026.1.Hs Hallmark JSON](https://data.broadinstitute.org/gsea-msigdb/msigdb/release/2026.1.Hs/h.all.v2026.1.Hs.json)，
SHA-256 `bc465ea8f94009689abdff725ffa16bbd9a38a7d13a876d046727fae49f61f2c`，
适用 [CC BY 4.0 条款](https://www.gsea-msigdb.org/gsea/msigdb_license_terms.jsp)。
固定资源中 ROS、UPR、apoptosis、hypoxia 分别有 49、113、161、200 个成员。
四程序已有受控真实输入的 Scanpy/ULM 执行证据，不是产品适用性验证。
本次 hypoxia 指 Hallmark 200-gene 候选，不是上表的八基因方法复现。
运行 `PROC-ROS` 为该具体 ROS 签名的标识，不等同整个 `PROC-OXSTRESS` 程序族。

本轮明确选择 `observed_subset`：记录完整资源、成员 hash、实际采用基因、
覆盖比例、缺失与歧义；子集输出不能称完整签名。均值和分位数不是活跃比例，
凋亡成员表达不是死亡比例。0.10.0 当时尚未运行多能性和解离程序；新增执行见下节。
方法、测量和图均只提供探索性 RNA 观察，不改变正式评分资格。

- selected view 是技术观察集合，其 observation 数量不能充当独立生物学重复。S+G2M fraction 及 S/G2M 的 Scanpy/decoupler 均值描述同一 view；不同单位不得平均。具体样本数值、输入位置与运行回执保留在受控私有验证记录中。
- 产品条件化运行可复用现有 `ProgramRule`（成员/权重 SHA、适用 scope/state/stage、覆盖/LOD、provenance）→ `ProgramSpec` → `ProcessMethodSpec` → `method_runtime_source_bound`。它必须先绑定确认的 `ProductDefinitionCard`、`DevelopmentWindowSpec`、P0-02 V3 lineage、BiologicalUnit manifest/assignment/attestation 与匹配的 MeasurementSpec；不得为运行而虚构 stage、sample 或独立重复。
- 在这些合同尚未齐备时，已批准的 exploratory 路径仅输出“候选基因程序表达”及 source/hash、基因覆盖、方法单位、实际 view、`biological_independence=unknown`、`n_independent=null`；不得标成七族全部 measured。Reactome membership 只能输出 descriptive pathway-expression，不能替代方向性 stress signature。

## 建议的下一步

### 两种原始 CSV 的候选适配（2026-09-26）

P006 0.11.0 新增 `directed_programs`，输入 v0.3、程序 profile v0.2、
result union v0.3；旧 Hallmark 输入与行为不变。原始来源仅在受控环境保存，
未确认再分发许可不等于计算输入未就绪。以下适配不授予产品适用性资格：

- PLURI：Europe PMC `PMC7260443/supplementaryFiles` 中 `mmc1.csv`，
  SHA-256 `cf32f7cee11034e669d331e028b85f071d0babeb27ed7d547dca1d048d4114a0`。
  `external_gene.x` 的 26 个唯一非空成员，使用候选 membership +1，
  不是原文拟合权重。CC BY-NC-ND 4.0 来源表不随包再分发。
- DISSOC：上述固定作者 commit 的原始 CSV；按 `sign(logFC)` 使用 507 正向、
  5 负向成员，不借用原文效应大小作本视图校准。3 个源符号 NA 保留 Ensembl
  member ID 和未解析原因；其余 509 符号唯一。正式补充 PDF 未提供完整成员表，
  不把论文许可自动扩展到仓库 CSV。Scanpy 对该有向签名返回不适用/null，
  ULM 才计算有向可观测子集；不另造 up-only 签名。

`observed_subset` 保留原始分母、源方向、未解析和未匹配成员、实际 scored
feature/direction 列表及 SHA；`complete_only` 对缺失/未解析成员不评分。
输入不猜 alias、不补零、不虚构 stage、对照或独立重复。残留比例、检出限、
解离归因和产品质量仍需额外科学验证，不是本候选表达执行的前置条件。

注册入口的两次受控真实视图执行已完成：PLURI 覆盖 24/26，Scanpy 与 ULM
均有数值；DISSOC 覆盖 465/512（461 正向、4 负向），44 个已知符号未匹配、
3 个源成员未解析，ULM 有数值，Scanpy 按合同不适用，因此该 ToolRun 为
`partial`。二者同属一个 query RNA evidence family，独立性 unknown。
仅新增这两个程序，没有重算原五类；未验证新结果的 P008/P009、Web 接入或
生物学效度。标准回执、源文件及逐观测结果留在受控环境，不进入 Git。

技术 view 合同已建立，下一科学缺口是匹配正负对照中的方向、稳健性和场景迁移验证。尚无证据把 D28 直接映射为发育窗口，或用这些分数判定中脑多巴胺能祖细胞／前体是否合格。低氧八基因仍只是另一个跨场景候选，不作为默认低氧检查或正式结论。
