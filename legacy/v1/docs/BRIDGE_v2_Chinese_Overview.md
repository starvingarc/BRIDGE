# BRIDGE v2 研究用途细胞产品评估系统中文说明

## 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档名称 | BRIDGE v2 研究用途细胞产品评估系统中文说明 |
| 文档版本 | Draft v0.3 |
| 适用版本 | BRIDGE v2.0-v2.3 |
| 读者 | 课题负责人、细胞产品研究人员、计算生物学开发者、模型验证人员、转化研究团队 |
| 用途 | 产品设计、研发评审、方法学论文准备、后续系统实现 |
| 关联英文文档 | `BRIDGE_v2_PRD.md`, `BRIDGE_v2_Scoring_Framework.md`, `BRIDGE_v2_Model_Architecture.md`, `BRIDGE_v2_Data_Validation_Plan.md`, `BRIDGE_v2_Test_Data_Inventory.md`, `BRIDGE_v2_Roadmap.md` |

## 1. 一句话定位

BRIDGE v2 是一个面向研究和转化研究的细胞产品评估系统。它以移植前单细胞转录组数据为主要输入，生成细胞产品画像、多维评分、证据置信度、风险提示和后续验证方向。

系统当前重点服务于帕金森病细胞治疗中的中脑多巴胺能祖细胞相关产品开发。它可以帮助研究者比较不同分化方案、不同批次、不同时间点的产品状态，也可以指出哪些证据充分、哪些证据缺失、哪些结果需要人工复核。

BRIDGE v2 的目标不是替代临床放行、GMP 质控、potency assay、动物实验或临床疗效评价。它提供的是基于单细胞数据的研究用途产品证据整理和 AI 辅助评分。


为了避免把模型输出误读成单一结论，v2 默认以产品画像和多维评分矩阵为核心。Integrated Product Readiness Score 只有在对应 ProductDefinitionCard、验证协议、校准锚点和证据置信度规则都锁定后才作为可选输出。

## 2. 建设背景

BRIDGE v1 已经可以从完整产品角度评估细胞组成、目标程序、风险相关成分和产品质量证据。v1 的优点是透明、可解释、规则清楚；局限是规则化程度较高，难以自然处理跨数据集泛化、模型不确定性、OOD 输入、弱监督学习、批次整合验证和持续迭代。

BRIDGE v2 在 v1 上增加一层 AI 产品能力：

- 保留 v1 作为透明基线和弱标签来源。
- 支持单时间点、多时间点、单批次、多批次输入。
- 支持批次效应诊断和受控整合。
- 输出多维评分，而不是一开始锁定单一总分。
- 报告不确定性、证据置信度和模型适用范围。
- 通过新数据、专家反馈和验证结果持续迭代。

## 3. 适用范围和边界

### 3.1 可以用于什么

BRIDGE v2 可以用于以下研究和转化研究场景：

- 分析移植前细胞产品的单细胞转录组组成。
- 比较不同分化方案、批次或时间点的产品画像。
- 识别目标细胞状态、非目标细胞状态和风险相关转录组信号。
- 给出多维评分和证据置信度。
- 生成后续实验或工艺优化假设。
- 为方法学论文提供可复现的分析和验证框架。

### 3.2 不能用于什么

BRIDGE v2 当前不用于：

- 临床批放行或 GMP 批放行。
- 患者治疗决策、剂量决策或临床风险分层。
- 患者疗效、行为学改善或临床获益预测。
- 替代 potency assay 或 potency lot-release assay。
- 判断临床安全性、无菌、遗传稳定性、体内分布、长期肿瘤形成风险。
- 无人工审查的移植窗口或工艺变更决策。

如果未来要进入临床决策或放行用途，需要重新定义 intended use、验证方案、质量体系和监管路径。

## 4. 系统总体架构

BRIDGE v2 采用五层架构。读者可以把它理解为从“数据能不能用”到“产品是否值得继续验证”的完整链条。

```text
输入兼容层
-> 生物表征层
-> AI 评分层
-> 优化支持层
-> 学习闭环和生命周期治理层
```

| 层级 | 主要任务 | 主要输出 |
| --- | --- | --- |
| 输入兼容层 | 读取不同格式和不同完整度的单细胞数据，识别缺失项和可评分范围 | 数据清单、缺失项、兼容性状态 |
| 生物表征层 | 识别细胞组成、目标程序、非目标状态、风险相关信号和轨迹证据 | 产品特征表、细胞状态解释、参考映射结果 |
| AI 评分层 | 将生物证据转换为多维分数，报告不确定性和适用边界 | 多维评分矩阵、证据置信度、模型解释 |
| 优化支持层 | 指出影响评分的关键因素，提出后续验证方向 | 驱动因素、候选时间点、后续实验假设 |
| 学习闭环层 | 管理数据版本、模型版本、验证报告和变更记录 | 数据卡、模型卡、验证报告、变更日志 |

## 5. 输入数据如何处理

BRIDGE v2 的基础输入是完整细胞产品的单细胞转录组数据，优先支持 `.h5ad`。后续可以适配 Seurat RDS、10x matrix 和批量数据清单。

系统需要尽量获得以下信息：

- 表达矩阵和基因 ID。
- raw counts 或 normalized expression。
- sample、product、protocol、batch、lot、donor、timepoint 等元数据。
- 测序 run、library batch、chemistry、platform 等技术批次信息。
- 如果已有细胞注释，可以作为参考，但不作为唯一真值。

BRIDGE v2 支持四类常见输入：

| 输入情况 | 系统如何处理 | 可以回答的问题 |
| --- | --- | --- |
| 单时间点单批次 | 生成单个产品画像和受限评分 | 该产品当前像什么，证据是否充分 |
| 单时间点多批次 | 逐样本评分，再比较批间一致性 | 同一方案是否稳定，是否有异常批次 |
| 多时间点单批次 | 逐时间点评分，再看时间轨迹 | 产品是否向目标状态收敛 |
| 多时间点多批次 | 同时分析轨迹和批间稳健性 | 哪个时间点更稳定，方案是否可重复 |

关键原则是：系统先做每个样本的产品画像，再汇总到批次、时间点和方案层面。不同批次或不同时间点的细胞不能在评分前简单合并，否则异常批次或真实轨迹信号会被平均掉。

当前服务器上的可测试数据已经整理到 `BRIDGE_v2_Test_Data_Inventory.md`。这份清单把数据分成几类：可以立刻测试的 h5ad、已有 BRIDGE v1 结果、阴性或非目标对照、BrainSTEM 参考稳健性数据、已经下载但还需要转换的数据。开发时建议先用小型 smoke test 跑通输入和评分输出，再逐步扩大到多时间点、多批次和参考稳健性测试。

## 6. 批次整合策略

BRIDGE v2 可以做批次整合，但不会把所有批次差异都当成噪音去掉。

系统首先区分两类变量：

| 变量类型 | 例子 | 处理方式 |
| --- | --- | --- |
| 技术变量 | 建库批次、测序 run、平台、chemistry、lane | 可以在检查混杂后用于校正或建模 |
| 产品变量 | 分化方案、产品批次、lot、donor、处理条件、时间点、目标产品类型 | 默认保留，用于评分、轨迹和工艺稳健性分析 |

如果某个技术变量和产品变量完全重合，例如所有 D25 样本都在同一个测序 run 中，系统不能自动判断差异来自技术还是生物。此时报告应标记为“无法可靠区分”，并降低相关结论的证据置信度。

批次整合主要用于：

- 参考映射。
- 细胞状态对齐。
- 可视化。
- OOD 判断。
- 跨样本寻找相似细胞群。

评分证据仍需回到 raw 或 normalized expression。例如 target marker、off-target marker、风险相关基因程序、转录组效力相关代理证据，都不能只依赖整合后的 latent space。

## 7. 输出结果

BRIDGE v2 的核心输出是一组可追溯的产品证据。单一总分只在验证条件满足时作为补充输出。

| 输出 | 内容 |
| --- | --- |
| 数据清单 | 输入文件、表达层、基因映射、元数据、缺失项、兼容性状态 |
| 产品画像 | 完整产品组成、目标程序、非目标状态、风险相关信号 |
| 多维评分矩阵 | 每个评分维度的原始证据、标准化分数、不确定性和解释 |
| 批次整合报告 | 哪些变量被校正、哪些变量被保留、是否存在混杂、是否疑似过校正 |
| 约束和警示报告 | OOD、低证据置信度、风险提示、人工复核触发原因 |
| 模型卡和数据卡 | 模型版本、数据来源、验证结果、适用范围和已知限制 |
| 验证报告 | 数据划分、校准、ablation、失败案例、人工复核结果 |

Integrated Product Readiness Score 可以作为候选研究输出，但只有在验证报告明确支持时才输出。默认情况下，BRIDGE v2 应优先展示多维评分矩阵和证据状态。

## 8. 多维评分框架

BRIDGE v2 使用多维评分来描述产品状态。每个分数都应包含原始证据、标准化分数、不确定性、缺失数据状态和解释。

| 维度 | 说明 | 重要边界 |
| --- | --- | --- |
| 目标身份评分 | 产品是否符合预设的目标细胞程序，例如中脑多巴胺能祖细胞相关程序 | 目标程序必须由 ProductDefinitionCard 定义 |
| 转录组效力相关代理评分 | 产品是否具有与预设作用机制相关的转录组证据 | 不构成 potency assay 或疗效证明 |
| 纯度和非目标成分评分 | 非目标、off-axis 或风险相关细胞群的负担 | 不替代纯度放行检测 |
| 转录组风险信号评分 | 残留多能性、异常增殖、严重非神经污染等转录组信号 | 不构成临床安全结论 |
| 工艺稳健性评分 | 不同批次、时间点或方案重复中产品画像是否稳定 | 缺少重复时只能输出受限证据 |
| 证据置信度评分 | 数据质量、基因覆盖、细胞数、元数据、时间点、批次结构和模型不确定性 | 用于限制结论强度 |

这些维度不是简单相加。某些维度是约束项，例如严重风险信号或证据不足时，系统应限制或暂缓 integrated score。

## 9. 目标产品定义

BRIDGE v2 需要为每类目标产品建立 ProductDefinitionCard。对 `PD_mDA_progenitor_v1` 来说，至少需要定义：

- 目标细胞阶段：移植前中脑多巴胺能祖细胞或前体细胞。
- 目标身份证据：floor-plate、ventral midbrain、DA lineage 相关程序。
- 成熟窗口：过早、合适、过成熟都应有不同解释。
- A9/A10 或相关亚型证据：在数据允许时作为补充证据，而不是强行要求所有输入都能判断。
- 非目标或风险状态：残留多能性、明显非神经污染、严重 off-axis 状态、异常增殖未定向状态等。
- 外部 QC 证据：viability、karyotype、CNV、WGS/WES、无菌、release assay、动物或功能实验等字段。

ProductDefinitionCard 用于定义某个产品概念下哪些证据支持、哪些证据限制、哪些证据缺失。固定 marker 列表不能替代产品定义和证据分层。


对于稀有风险细胞，报告应区分“当前测序深度下未检测到”和“有正交证据支持其缺失”。对于不属于已知目标或风险类别的可疑细胞群，v2 应进入 open-world review queue，由模型证据和人工复核共同决定后续解释。

## 10. 重要生物学解释原则

某些 marker 或细胞状态不能天然视为负向证据。系统需要先判断细胞状态和产品目标，再判断证据方向。

例如：

- MKI67 阳性细胞不一定是坏信号。若它们属于合理的目标祖细胞群，可能符合产品阶段；若它们伴随残留多能性、未定向增殖或异常生长程序，才应作为风险提示。
- SOX2/NES 阳性祖细胞也不一定是坏信号。对于祖细胞产品，它们可能是目标阶段的一部分；只有当它们缺少中脑/DA lineage 锚点，或显示不受控扩张，才应降低成熟度或风险解释。
- DA lineage 信号也不是越高越好。移植前产品通常需要处在合适的发育窗口，过早和过成熟都可能影响后续验证价值。

因此，BRIDGE v2 的评分逻辑应是：

```text
先判断细胞状态和目标产品概念
再判断证据方向
最后给出分数、置信度和解释
```

## 11. 外部 QC 和证据等级

单细胞转录组可以描述产品组成和转录组状态，但不能覆盖所有产品质量证据。BRIDGE v2 应允许接收外部 QC 信息，并将其纳入证据置信度。

重要外部证据包括：

- 细胞活率、凋亡和冻融后状态。
- karyotype、CNV、WGS/WES 或其他遗传稳定性证据。
- 无菌、支原体、内毒素等放行相关检测。
- residual pluripotency 的正交检测。
- release assay 和功能实验。
- 动物 graft、fiber density、PET、行为学或其他下游证据。
- biodistribution、tumorigenicity、GLP safety 等安全资料。

这些证据缺失时，系统不应把产品直接判为失败，但必须降低相关结论的证据置信度。尤其是稀有风险细胞，报告应写成“在当前测序深度下未检测到”，避免写成“完全不存在”。

## 12. AI 模型和学习闭环

BRIDGE v2 的 AI 由几类能力组成：

- BRIDGE v1 规则基线：作为透明对照和弱标签来源。
- 参考映射和细胞状态识别：帮助理解输入产品像什么。
- 多维评分模型：将产品特征转化为可校准的分数。
- 不确定性和 OOD 检测：判断模型是否在适用范围内。
- 解释模块：指出哪些细胞状态、基因程序或数据质量因素驱动了分数。
- 学习闭环：新数据、专家反馈和验证结果进入下一版模型。

系统应优先复用成熟工具，避免重写已有底层算法。例如，细胞注释和参考映射可以适配 CellTypist、SingleR、scVI/scANVI、scArches、Symphony 等；基因程序评分可以适配 decoupler、UCell、AUCell 等；批次整合评估可以参考 scIB/scib-metrics。

BRIDGE 的核心价值在于统一数据契约、证据追踪、模型校准、产品层汇总和报告解释。

## 13. 证据置信度、OOD 和人工复核

BRIDGE v2 需要区分“产品生物学不好”和“证据不足”。例如，缺少时间点、缺少 batch metadata 或只有 normalized layer，通常应降低证据置信度，而不是直接给负面生物学结论。

系统应分别报告以下不确定性来源：

- 基因覆盖不足。
- 细胞数不足。
- 关键元数据缺失。
- 技术批次和产品变量混杂。
- 输入样本超出参考空间。
- 模型预测不稳定。
- 弱标签冲突或专家意见不一致。

以下情况应触发人工复核：

- OOD 明显升高。
- 风险相关转录组信号较强。
- 证据置信度很低。
- 模型输出和 BRIDGE v1 规则明显分歧。
- 批次整合疑似抹除了真实产品差异。
- 样本用于关键方案排序或方法学报告核心结论。

人工复核应记录复核人、触发原因、复核结论、是否影响模型版本或评分 schema。

## 14. 验证计划

BRIDGE v2 的验证不应只看模型分数高不高，还要看结论是否可复现、可校准、可解释，并且是否能在不同数据集和不同方案之间泛化。

验证数据应覆盖：

- 核心 mDA product-like 数据。
- 多时间点分化方案。
- 单时间点移植前产品。
- 多批次或多 lot 产品。
- 技术批次挑战数据。
- 负控和 off-target 数据。
- 参考鲁棒性数据。
- 未来 outcome-linked 数据。

关键验证方式包括：

- leave-dataset-out。
- leave-protocol-out。
- leave-timepoint-out。
- leave-lot-out 或 leave-batch-out。
- leave-publication-out。
- leave-source-cell-line-out。
- negative-control holdout。
- 缺失数据模拟。
- 细胞下采样。
- 基因重叠模拟。
- integration sensitivity panel。
- calibration 和 OOD 验证。
- 专家盲法复核。

对批次整合，应比较不整合、保守整合、scVI/scANVI/scArches 和 reference-only mapping 等策略。报告需要同时展示 batch removal 和 biological conservation，不能只看整合后图上是否混得好。

论文版验证还需要锁定验证协议，包括冻结测试集、预先定义阈值、排除规则、分析版本和人工复核流程。

## 15. 版本路线图

BRIDGE v2 可以按阶段推进。

| 阶段 | 目标 | 当前状态 |
| --- | --- | --- |
| Phase 0 | 完成产品、评分、模型、验证、路线图文档 | 已完成初稿 |
| Phase 0.5 | 把审查发现的当前可实现问题写入现有文档 | 当前优先工作 |
| Phase 1 | 形成 rule-aligned 的产品画像 MVP | 可基于 v1 派生特征实现 |
| Phase 2 | 整理私有和公开候选数据，形成验证面板 | 依赖数据下载和清洗 |
| Phase 3 | 训练 v2.1 AI calibration model | 依赖验证数据和弱标签治理 |
| Phase 4 | 形成论文版 BRIDGE v2 | 需要冻结验证协议和可复现报告 |
| Phase 5+ | 引入产品级 set model、时间轨迹模型和优化模型 | 依赖更多标签、批次和 outcome-linked 数据 |

当前阶段优先做能直接落实的事情：

- 让 integrated score 变成验证合格后才输出的候选结果。
- 增加 ProductDefinitionCard 设计。
- 增加外部 QC 字段。
- 增加 rare-event 表述。
- 增加非单调移植窗口逻辑。
- 增加 score contract。
- 增加 OOD 和不确定性分解。
- 增加 integration sensitivity panel。
- 增加弱标签治理和人工复核 SOP。

依赖未来数据或实验的内容放入后续计划，包括 outcome-linked 校准、功能实验关联、graft/PET/行为学关联、正式 GLP 安全证据、Bayesian optimization 或临床用途验证。

## 16. 主要风险和控制

| 风险 | 控制方式 |
| --- | --- |
| 高分被误读为可移植或可放行 | 报告中明确研究用途边界，默认展示多维评分和证据置信度 |
| 转录组 proxy 被误读为 potency assay | 使用“转录组效力相关代理证据”，并要求外部证据分层 |
| 批次整合抹掉真实产品差异 | 保护 product lot、protocol、timepoint 等变量，报告 overcorrection 检查 |
| 稀有风险细胞漏检 | 报告 sampled-depth caveat，并结合正交检测 |
| 模型学习到实验室或文献来源特征 | 使用 leave-publication、leave-protocol、leave-source-cell-line 等划分 |
| 规则偏差传给 AI 模型 | 建立弱标签治理和专家复核机制 |
| 用户输入只有单时间点 | 支持受限评分，降低轨迹证据置信度，不硬失败 |

## 17. 参考框架和资料

BRIDGE v2 借鉴以下框架，但不声明已经满足任何监管提交要求：

- FDA Good Machine Learning Practice：AI/ML 生命周期、数据代表性、独立测试、透明性和监控。
- FDA Cellular and Gene Therapy Potency Guidance：potency assurance 的多因素证据策略。
- ICH Q8/Q9：QTPP、CQA、质量风险管理和产品开发逻辑。
- TRIPOD+AI：预测模型开发和验证报告。
- DECIDE-AI：早期 AI 决策支持系统的人机协作和失败模式报告。
- scIB / single-cell integration best practices：批次去除和生物信号保留的双目标验证。
- scArches / Symphony：query-to-reference mapping 和冻结参考空间。

相关链接：

- FDA GMLP: https://www.fda.gov/medical-devices/software-medical-device-samd/good-machine-learning-practice-medical-device-development-guiding-principles
- FDA Potency Assurance: https://www.fda.gov/regulatory-information/search-fda-guidance-documents/potency-assurance-cellular-and-gene-therapy-products
- TRIPOD+AI: https://www.bmj.com/content/385/bmj-2023-078378
- DECIDE-AI: https://www.nature.com/articles/s41591-022-01772-9
- scIB benchmark: https://www.nature.com/articles/s41592-021-01336-8
- scArches: https://www.nature.com/articles/s41587-021-01001-7
- Symphony: https://www.nature.com/articles/s41467-021-25957-x
