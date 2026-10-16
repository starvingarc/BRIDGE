# BRIDGE 工具使用与输出指南

## 先分清三层

**高层工具包**是 Agent 可以调用的分析入口；**底层方法**是工具包实际执行的计算；
**知识目录条目**是供选择和策展的方法资料。目录里有名字，不表示该方法已接入运行。
以下列出全部 12 个高层入口，并展开五域使用的计算；准确字段和版本以各 Tool Card、
Schema 和代码为准，本页不维护第二套输入合同。

工具产生的真实结果可以成为研究证据，不必先取得正式科学资格。但需要区分：

1. **已实现**：存在可以执行的代码。
2. **已运行**：有对应输入、方法版本、执行状态和校验和的实际回执。
3. **已入图**：图中存在可追溯到该回执和结果的记录；仅列出附件不等于数值已入图。
4. **已验收**：实际用户流程、图中数值、来源和报告经过核对。

合成输入的方法测试只能证明工程行为，不能替代真实样本验收。`shadow`、
`exploratory`、`unknown` 和 `unavailable` 应原样保留；进入图不代表身份、临床效果或放行资格得到确认。

## 全部高层工具：输入、用途、输出与代码

| 工具与用途 | 怎样使用 / 必需资料 | 主要输出 | 文档与代码入口 |
|---|---|---|---|
| P0-01 输入质控 | 声明 H5AD/10x 数据、矩阵含义、实验类型及已知样本信息；可选的过滤和 doublet 检查需明确启用 | 细胞/基因 QC 指标、可分析性、选定数据视图、图表和来源索引；信息充分时另有生物学单位对象 | [工具卡](../src/bridge/tool_packages/cards/P0-01.md) · [执行代码](../src/bridge/tool_packages/p0_01_input_qc/executor.py) |
| P0-02 细胞状态证据 | QC 选定的表达数据、声明的来源家族、方法定义及适用 reference | 候选标签与组成、未知/拒绝状态、参考相关性及标记辅助证据、候选测量；满足对应输入时才有 V3 交接结果 | [工具卡](../src/bridge/tool_packages/cards/P0-02.md) · [执行代码](../src/bridge/tool_packages/p0_02_cell_state/executor.py) · [候选路径](../src/bridge/tool_packages/p0_02_cell_state/candidate_runtime.py) |
| P0-03 目标身份与区域一致性 | P0-02 V3、共享产品角色定义、明确的区域分子/分母、QC 与分析单位；表达模式另需表达语义和 reference/program 配置 | 三种不同分母的组成比例；表达模式另有参考支持、NNLS 权重、程序活性及稳健性结果 | [工具卡](../src/bridge/tool_packages/cards/P0-03.md) · [入口](../src/bridge/tool_packages/p0_03_target_regional/adapter.py) · [方法](../src/bridge/tool_packages/p0_03_target_regional/method_runtime.py) |
| P0-04 发育阶段适配性 | P0-02 V3、外部定义的预期窗口、状态到阶段映射及分析单位；表达模式另需阶段 reference/program 配置 | 全产品与目标相关两种分母的阶段组成；参考阶段支持、序数基线、程序活性和区间/不可评估原因 | [工具卡](../src/bridge/tool_packages/cards/P0-04.md) · [入口](../src/bridge/tool_packages/p0_04_developmental_compatibility/adapter.py) · [方法](../src/bridge/tool_packages/p0_04_developmental_compatibility/method_runtime.py) |
| P0-05 全产品与非目标组成 | 与 P0-03 共用角色定义；选择预计算汇总、真实方法或硬计数路径；方法/硬计数路径需真实单位声明回执 | 角色组成、未知与未解决项、稀有群体计数/检出边界、OOD 协调；硬计数不制造软概率 | [工具卡](../src/bridge/tool_packages/cards/P0-05.md) · [入口](../src/bridge/tool_packages/p0_05_off_target_control/adapter.py) · [方法](../src/bridge/tool_packages/p0_05_off_target_control/method_runtime.py) |
| P0-06 增殖与应激 | 产品模式需外部 ProgramSpec、阶段/状态与单位输入；探索模式接受来源绑定的 S/G2M 或候选多程序资源及选定表达视图 | 程序分数、覆盖率、均值/分位数、周期预测与比例、方法执行记录；各模式的适用边界分别保留 | [工具卡](../src/bridge/tool_packages/cards/P0-06.md) · [入口](../src/bridge/tool_packages/p0_06_proliferation_stress_response/adapter.py) · [方法](../src/bridge/tool_packages/p0_06_proliferation_stress_response/method_runtime.py) |
| P0-07 产品比较与稳定性 | 已登记的多个产品结果、可比性规则、相同度量/分母及样本单位；不直接重跑单细胞分析 | 合法的组间差异、组成距离、相关性和稳定性摘要；无绝对排名 | [工具卡](../src/bridge/tool_packages/cards/P0-07.md) · [入口](../src/bridge/tool_packages/p0_07_product_comparison_stability/adapter.py) |
| P0-08 证据充分性 | 每个待评估域的输入绑定、实际测量、QC、方法验证和先验记录 | 逐域证据充分性、开放要求及可视化；不新增生物学测量 | [工具卡](../src/bridge/tool_packages/cards/P0-08.md) · [入口](../src/bridge/tool_packages/p0_08_evidence_sufficiency/adapter.py) |
| P0-09 证据图编译与查询 | 真实测量及来源目录、证据家族、论断/协调规则、P0-08 结果；追加时提供旧图 | 图与校验清单、证据/缺口/协调记录；查询模式返回已有图的检索结果，不重算分析 | [工具卡](../src/bridge/tool_packages/cards/P0-09.md) · [入口](../src/bridge/tool_packages/p0_09_evidence_compiler/adapter.py) |
| P0-10 报告声明核验 | 同版本图、结构化报告草稿、打包的措辞政策和声明库 | 数值、单位、分母、引用与允许措辞的核验；研究报告路径产出同快照 HTML/JSON/CSV/SVG | [工具卡](../src/bridge/tool_packages/cards/P0-10.md) · [入口](../src/bridge/tool_packages/p0_10_claim_verifier/adapter.py) |
| P0-11 公开材料准备 | 符合条件的报告与导出规则，或明确指定的待检查文件 | 本地公开候选文件/清单或审计结果；不自动发布，也不授予发布权限 | [工具卡](../src/bridge/tool_packages/cards/P0-11.md) · [入口](../src/bridge/tool_packages/p0_11_public_safe_export/adapter.py) |
| P0-12 移植后证据 | 可选；需真实移植物、动物、时间点及结果，表达路径另需匹配的 reference/program 输入 | 移植物组成、参考支持、标记程序与图表；缺失时明确 not_provided，不回填移植前评估 | [工具卡](../src/bridge/tool_packages/cards/P0-12.md) · [入口](../src/bridge/tool_packages/p0_12_graft_assessment/adapter.py) |

## 五域方法逐项说明

P0-03 贡献“目标身份”和“区域一致性”两个域，P0-04、P0-05、P0-06 各贡献一个。
P0-02 是共同基础，不能代替这五域。以下别名在相应工具的 MethodSpec 中选择，
不是让 Agent 绕过高层入口直接拼装命令。

### 目标身份与区域一致性：P0-03

实际入口为 `run_target_regional_methods`，见上表的方法代码。表达结果写入
`target_regional_method_bundle.json`，与三种组成比例的测量文件分开保存。

| 方法 | 需要什么 / 实际计算 | 得到什么 |
|---|---|---|
| TRG-PBCORR | 声明单位的 pseudobulk 与目标 reference；Spearman/cosine | 参考标签、支持值、第一/第二候选差距、共同基因数 |
| REG-PBCORR | 独立指定的区域 reference；同样的相关性计算 | 区域参考支持，不能用目标标签替代区域证据 |
| TRG-NNLS | 匹配表达语义的 reference centroids、外部残差适用界限；SciPy NNLS | 非负归一化权重、相对残差及适用状态；不是自动确认的纯度 |
| TRG-DECOUPLER | 明确的带符号目标程序卡；decoupler ULM | 活性、p 值、实际 marker 覆盖 |
| REG-DECOUPLER | 明确的区域程序卡；decoupler ULM | 区域程序活性与覆盖 |
| TRG-BOOTSTRAP | 合法 NNLS 结果及声明的独立组；重采样 | 区间；只有一个独立组时仅描述，不制造生物学区间 |
| REG-CROSSREF | 多个明确的区域 reference 结果 | 标签一致性及支持值范围，不作多数投票 |
| REG-MODALITY | 外部声明的上下文/特征匹配组 | 模态间一致性；仅有 scRNA/snRNA 名称不同不足以运行 |

### 发育阶段：P0-04

实际入口为 `run_development_methods`。额外结果位于
`development_method_bundle.json`；预期窗口及阶段角色必须来自外部定义，不能把培养天数换算为成熟程度。

| 方法 | 需要什么 / 实际计算 | 得到什么 |
|---|---|---|
| DEV-PSEUDOBULK-CORR | 声明单位、阶段 reference、阶段角色/次序；Spearman/cosine | 每单位的参考阶段支持、差距、覆盖 |
| DEV-ORDINAL | 上述资料及来源分组留出验证回执；scikit-learn 累积二分类逻辑回归 | 未校准序数分布与期望次序；缺验证回执则不执行 |
| DEV-PROGRAM | 发育程序卡及 pseudobulk；decoupler ULM | 程序活性、p 值、覆盖 |
| DEV-BOOTSTRAP | 可用阶段支持及声明的独立组；NumPy 重采样 | 窗口内支持区间或描述性状态 |
| TIME-PROGRAM | 当前仅保留兼容选择器 | not_assessed；没有数值实验时间合同 |
| TIME-GAM-PY | 当前仅保留兼容选择器 | not_assessed；不声称已拟合真实时间轨迹 |

### 全产品与非目标组成：P0-05

方法入口为 `execute_methods`，结果位于 `off_target_method_bundle.json`。
它消费真实上游结果和明确的校准输入，不自己训练新分类器或生成 spike-in 实验。

| 方法 | 需要什么 / 实际计算 | 得到什么 |
|---|---|---|
| COMP-EXACT | 角色细胞计数；Clopper–Pearson | 描述性细胞计数区间，不是重复层面的误差 |
| COMP-HARD-SENS | 同范围的硬计数与软组成 | 硬/软组成差异 |
| COMP-HBOOT | 声明的独立组及单位组成 | 按独立组 bootstrap 的组成区间 |
| RARE-EXACT | 稀有状态计数与分母 | 描述性区间；零观察不等于不存在 |
| RARE-SPIKEIN | 实际 spike-in 试验及外部接受规则 | 检出率曲线和候选检出限；缺试验不能生成 |
| RARE-BINOMIAL-AT-LEAST-ONE | 指定比例/概率目标 | 至少观察到一个细胞的单状态二项规划；不是 SCOPIT |
| OOD-DISAGREE | 有来源家族及 checksum 的多个 OOD 渠道 | 来源间分歧；同一家族重复输出不算独立证据 |
| OOD-ENSEMBLE | 上述渠道及外部有序规则 | 协调结果与原因，不等于深度 OOD 分类器 |

### 增殖与应激：P0-06

方法入口为 `run_process_methods`。产品方法模式写入 `process_method_bundle.json`；
独立周期探索模式写入 `exploratory_process_profile.json` 与逐观测分数 Parquet。
同一种评分方法可以处理不同的已声明程序，但不能因为评分器存在就宣称七个程序家族都已测量。

| 方法 | 实际计算 | 得到什么 |
|---|---|---|
| PROC-SCORE-SCANPY | `scanpy.tl.score_genes`，配置的程序与背景对照 | 分数、均值/中位数/分位数、基因覆盖和分组来源 |
| PROC-SCORE-DECOUPLER | `decoupler.mt.ulm`，配置的程序和权重 | ULM 活性摘要及覆盖；量纲不能与 Scanpy 分数直接比较 |
| PROC-CYCLE-SCANPY | `scanpy.tl.score_genes_cell_cycle`，明确的 S/G2M 基因表 | 每个细胞的周期预测及 S/G2M 分数 |
| PROC-CYCLE-AGG | 在声明范围汇总预测标签 | G1/S/G2M 计数、总数和 S/G2M 比例；不等于真实分裂速率 |

七家族为多能性样、周期、解离/热休克、氧化应激、缺氧、未折叠蛋白反应、凋亡相关程序。
周期探索入口执行 S/G2M；多程序探索另有 ROS、缺氧、UPR 和凋亡相关记录。
多能性样与解离／热休克的后续描述性执行见
[程序台账的 2026-09-26 增量](../src/bridge/tool_packages/p0_06_proliferation_stress_response/resources/CANDIDATE_PROGRAM_LEDGER.md)，
保存结果的入图/解释范围见[PR #8 收口记录](validation/step7_evidence_coordinator_20260911.md#source-bound-program-continuation--2026-09-26)。
七族有执行记录不等于全部方法都有可用数值、完整 Web 联合验收或产品适用性已验证；
按方法不适用的结果仍保留 null。UCell、AUCell、CNV 等目录候选也不能写成已执行。
后续通路富集是独立待办，不将现有程序评分冒充 GSEA；范围见
[能力 TODO](../plans/step7-evidence-coordinator.md#capability-todo)。

## 其他工具实际做什么

| 工具 | 实际计算或操作 | 不能混淆的边界 |
|---|---|---|
| P0-01 | 结构/矩阵检查、逐细胞计数与基因数等 QC、声明范围内的汇总；可选 Scrublet/筛选 | 未启用、资料不足或未运行的检查不能写成通过；QC 不等于产品质量 |
| P0-02 | 候选 CellTypist 分类、energy/OOD 拒绝诊断；辅助路径的来源分开相关性和 marker/program 支持 | 候选模型开发验证与本次 query 输出分开；参考方法一致不等于独立确认 |
| P0-07 CMP-EFFECT | Hedges-g 引擎，比较独立样本/制备的数值序列 | 细胞不能代替独立样本 |
| P0-07 CMP-JS | SciPy Jensen–Shannon 距离，比较相同标签上的组成概率向量 | 需要同一组成定义与标签集合 |
| P0-07 CMP-CORR | SciPy Spearman，比较匹配特征的 pseudobulk | 相关不等于产品等效 |
| P0-07 CMP-WASS-1D | SciPy 一维 Wasserstein 距离 | 要求有序标量分布；不是通用细胞整合 |
| P0-07 STAB-CV | NumPy 均值、标准差、中位数和绝对偏差 | CV 需要有意义零点的比率量纲；分母不可用则不计算 |
| P0-08 | 确定性应用数据、方法和先验充分性规则，保留逐域缺口 | 不运行表达分析、不制造测量 |
| P0-09 | 编译来源/测量/论断/缺口关系、追加历史、读取已有图 | 图连线不是因果；记录数不是独立证据数 |
| P0-10 | 核对声明与图中数值、单位、分母、区间、生命周期及允许措辞 | 引用和数值一致不代表自由文本的科学解释正确 |
| P0-11 | 白名单重建报告；按格式/披露规则审计 JSON、Markdown、CSV、SVG | 只准备本地候选，不上传、不自动获得公开资格 |
| P0-12 | AnnData/Scanpy 读取；按声明技术样本聚合；外部概率列的软组成；匹配聚合语义的 Spearman；外部 marker 均值/覆盖 | 不训练分类器；技术样本不算独立动物；不重新执行移植物 QC |

P0-07 的 R/Bioconductor、Bayesian/mixed-model、差异丰度等目录候选，以及 P0-04
的轨迹/velocity/OT 候选，不代表相应高层适配器已经执行这些方法。查目录时应同时
核对包内代码和该次回执中的实际方法集合。

## 怎样运行与核对输出

网页用户确认资料和有界计划后，由 Agent 调用上述高层工具。开发者可用同一个 Registry：

```bash
bridge-tool describe P0-03
bridge-tool input-contract P0-03
bridge-tool validate --request /absolute/path/to/request.json
bridge-tool run --request /absolute/path/to/request.json
```

Python 使用同一入口，先检查资格再执行，不直接绕过工具包调用底层方法：

```python
import json
from pathlib import Path
from bridge.toolkit.registry import ToolRegistry

registry = ToolRegistry.load_default()
payload = json.loads(Path("/absolute/path/to/request.json").read_text())
request = registry.parse_request(payload)
eligibility = registry.check_eligibility(request)
if eligibility.eligible:
    run = registry.run(request)
    print(run.execution_state, run.reason_codes)
    for artifact in run.artifacts:
        print(artifact.kind, artifact.path, artifact.sha256)
else:
    print(eligibility.reason_codes)
```

示例文件位于 [examples/requests](../examples/requests/)，含占位路径和 checksum，
不能直接用来证明实际样本已运行。P0-01/P0-02 与后续工具的请求版本不同，以各工具卡为准。

代码通常分为 `adapter.py`（检查输入与发布）、`executor.py`（汇总/测量）、
`method_runtime.py`（真实计算）、`models.py`/`method_models.py`（结果结构）、
`visualization_data.py`/`visualization.py`（图表）。并非每包都有全部文件；上表链接是实际入口。

核对一次执行应依次查看：请求与输入 hash → ToolRun 状态及逐方法原因 → 完整结果 JSON/
method bundle → 测量文件 → 图中的记录/来源关系 → 同版本报告。`partial` 时要逐方法检查，
不能把整个工具当失败，也不能把所有方法都报成功。

## 结果进入证据图的实际边界

- **标准测量**：保留 MeasurementSpec、数值、单位、分母、状态、输入视图及 ToolRun/Artifact
  hash，经 P0-08 与 P0-09 形成来源绑定的证据；缺失不是零，候选不是正式结论。
- **方法明细**：相关性、NNLS、程序活性等可能只存在于 method bundle。
  附件可下载不等于每条方法结果已经成为图中的可查询记录，必须逐项核对转换及来源指针。
- **图与网页接入**：工具包具备图可用输出，不表示当前网页已构造所需输入或纳入执行范围。
  相关连接代码见 [原生观测入图](../src/bridge/web/native_evidence.py)、
  [科学输入整理](../src/bridge/web/scientific_inputs.py) 和
  [评估协调](../src/bridge/web/assessment.py)。
- **科学资格**：来源一致只证明“工具在该输入上得到了这个结果”，不能单独证明产品纯度、
  发育适配、安全或疗效。相同表达数据产生的多个方法结果保留共享证据家族。

当前原生路径已包含 P0-02 候选测量、P0-03 来源绑定参考相似度、P0-04/P0-05
保存的发育参考／标记上下文与整视图标签计数，以及 P0-06 周期和多程序观察。
其中描述性上下文不能冒充已确认的发育窗口或目标／非目标角色评估；方法明细也
不能仅因存在于附件中就视为已入图。已保存输出的入图证据见
[技术视图验证](validation/technical_view_evidence.md)与[程序验证](validation/candidate_programs.md)；
当前组合 Web 流程的最终验收仍见[主线计划](../plans/step7-evidence-coordinator.md)。
私有样本回执、路径和截图不进入仓库。

## 工具合同与验证入口

以下链接保留工具导航锚点，便于从其他文档直接定位验证记录。
日期较早的记录只证明其对应版本；测试文件存在不表示本次运行了全部测试。
公共机器接口以 Schema 与 `input-contract` 为准，共享状态见[高层工具合同](tool-contract.md)。

<a id="p0-01"></a>
### P0-01 质控验证

[服务器集成记录](validation/p0_01_server_integration_20260810.md)。

<a id="p0-02"></a>
### P0-02 细胞状态验证

[服务器集成与候选验证记录](validation/p0_02_cell_state_evidence.md)。

<a id="p0-03"></a>
### P0-03 目标与区域方法验证

[汇总与表达方法记录](validation/p0_03_target_regional.md) · [真实方法执行测试](../tests/test_p0_03_expression_methods.py)。

<a id="p0-04"></a>
### P0-04 发育方法验证

[候选验证记录](validation/p0_04_developmental_compatibility.md) · [真实方法执行测试](../tests/test_p0_04_expression_methods.py)。

<a id="p0-05"></a>
### P0-05 组成与稀有状态方法验证

[计数、声明与候选记录](validation/p0_05_off_target_control.md) · [真实方法执行测试](../tests/test_p0_05_real_methods.py)。

<a id="p0-06"></a>
### P0-06 程序与周期方法验证

[来源绑定与测量记录](validation/p0_06_proliferation_stress_response.md) · [真实方法执行测试](../tests/test_p0_06_real_methods.py)。七家族要求见 [PRD 第 6.3 节](BRIDGE_PRD.md#63-分析计划与任务执行)。

<a id="p0-07"></a>
### P0-07 比较验证

[可比性与执行测试](../tests/test_p0_07_product_comparison_stability.py)。

<a id="p0-08"></a>
### P0-08 证据充分性验证

[Case 绑定验证记录](validation/p0_08_case_binding_v0.5.md)。

<a id="p0-09"></a>
### P0-09 证据图验证

[充分性结果接入记录](validation/p0_09_sufficiency_v2_ingestion_v0.4.md)。

<a id="p0-10"></a>
### P0-10 报告核验验证

[声明核验测试](../tests/test_p0_10_claim_verifier.py)。

<a id="p0-11"></a>
### P0-11 公开候选准备验证

[导出与审计测试](../tests/test_p0_11_public_safe_export.py)。

<a id="p0-12"></a>
### P0-12 移植后分支验证

[移植物评估测试](../tests/test_p0_12_graft_assessment.py)。

更多版本化记录见[验证索引](validation/README.md)，目录候选来源见
[方法短名单](../knowledge/active-methods.md)。


<a id="expression-exploration"></a>

## 表达探索与样本条件比较

在输入面板选择“UMAP、群标记与样本条件比较”，复用已确认的质控后 H5AD。
该模式不需要细胞身份参考；分群列留空时生成探索性 Leiden，指定已有分群时保留
原标签。可选择批次、样本等注释列及基因着色。已有二维坐标必须显式选择并声明
适用于当前表达数据；否则重新计算。原始计数使用总量 10,000 标准化及自然对数
log1p，已标准化输入必须明确声明 log1p，不重复标准化。

同一入口提供两种不同问题：群对其余群的 Wilcoxon marker 排序，以及同一细胞类型
内两条件的样本比较。后者由比较工具包的计算模块使用原始计数按样本求和，
通过 PyDESeq2 0.5.4 运行条件模型，可加入批次。每组至少三个保留样本、
用户确认生物学独立性且设计可估计时才输出条件性推断；否则保留等权样本平均
CPM 的描述性差异，p 值与校正 p 值为空。每样本默认至少 10 个该类型细胞。
目前支持同一 H5AD 内的非配对两条件设计；不支持配对、重复测量或跨会话合并。

表达探索复用已有图表注册、来源校验、表格预览与 SVG/PNG/PDF 导出。
默认交互图最多显示 5,000 个点，完整坐标表、群计数和分析使用全部所选细胞。
marker 图最多显示 40 个排名条目，差异表达图最多 20,000 个有估计值的基因，
完整表保留相应输出；显示缺失不补零。输入文件、选定视图、随机种子、参数和
依赖版本保存在分析结果中；原始数据不修改。该模式不生成产品域分数或身份结论。

实现边界：输入参数由 [表达合同](../src/bridge/tool_packages/_expression_contracts.py)
统一定义，Web 与工具校验直接使用它，不通过计算入口获取参数模型。
[共享数据规则](../src/bridge/tool_packages/_expression_data.py) 只负责矩阵与注释列校验；
探索与样本比较分别依赖它，比较模块不反向依赖探索包。
计算返回具名结果对象，分别携带完整表与展示数据；结果对象负责摘要序列化，
绘图层负责来源绑定和导出，运行入口负责 QC 与原子发布。
调整参数及默认值时修改表达合同；调整计算结果时同步其消费方和接口回归，
不在运行入口重新维护一套摘要字段排除清单。

安装选项为 .[qc,expression]。方法维护源是现有知识目录；官方参考：
[Scanpy](https://scanpy.readthedocs.io/en/1.10.x/tutorials/basics/clustering.html)、
[PyDESeq2](https://pydeseq2.readthedocs.io/en/stable/)。
合成回归只验证工程与数值边界，真实数据科学验收和部署另行进行。
