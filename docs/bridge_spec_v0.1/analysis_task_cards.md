# BRIDGE Analysis Task Cards

| 项目 | 内容 |
| --- | --- |
| 受控主规范 | [BRIDGE PRD](../BRIDGE_PRD.md) |
| 状态 | `contract_draft` |
| 适用版本 | PRD v0.1，2026-08-04 revision |

本文件登记分析任务合同。它不代表工具已经完成安装、benchmark 或科学验证；当前所有任务均不得发布 `domain_score`。

## 1. 通用任务合同

每张 Task Card 必须记录：

```text
task_id / task_version / status
scientific_question / applicable_product_cards
input_schema / analysis_unit / denominator
tool_ids / environment_id
reference_snapshot_refs / prior_snapshot_refs
measurement_spec_ref / score_contract_ref
raw_metrics / uncertainty / evidence_state
failure_conditions / missing_behavior / fallback_policy
evidence_family_ids / visualization_ids
benchmark_manifest / validation_report / reviewer
```

状态枚举：

| 状态 | 允许用途 |
| --- | --- |
| `candidate` | 方法开发和 benchmark |
| `conditional` | 满足指定输入条件时运行，结果默认不晋升 |
| `shadow` | 可展示候选 raw metrics，但不进入 P0 正式协调或评分 |
| `frozen` | 通过任务级分析验证，可生成绑定 MeasurementSpec 的正式 raw evidence；评分仍需未来独立合同 |
| `deferred` | 当前版本不运行 |

## 2. P0 核心任务

| Task ID | 科学问题与主要输出 | 分析单位/分母 | 当前状态 |
| --- | --- | --- | --- |
| `TASK-INTAKE-QC` | 数据结构、层含义、样本层级、基因覆盖、QC、Data Readiness | sample/preparation；完整输入对象 | `candidate` |
| `TASK-CELL-STATE` | Anatomy、Lineage、Development、Process 四轴 prediction set、unknown 和方法分歧 | cell，随后聚合至 sample/preparation | `candidate` |
| `TASK-TARGET-IDENTITY` | target 与 acceptable-adjacent soft fraction、区间和适用性 | 全部合格移植前细胞 | `candidate` |
| `TASK-REGIONAL-FIDELITY` | vMB/floor-plate 支持、区域偏移和冲突证据 | ProductDefinitionCard 规定的完整制剂或目标相关分母 | `candidate` |
| `TASK-DEVELOPMENT` | 阶段组成、目标窗口偏离和 reference support | sample/preparation；研究者确认窗口 | `candidate` |
| `TASK-OFFTARGET` | known off-target、unknown、rare-state LOD/UCB | 全部合格移植前细胞 | `candidate` |
| `TASK-PROCESS` | stage-conditioned process burden 和 TranscriptomicReviewFlag | sample/preparation 与 state-specific views | `candidate` |
| `TASK-EVIDENCE-SUFFICIENCY` | Data Readiness、Model Robustness、Prior Applicability 和 sufficiency state | 每个 product x domain | `candidate` |
| `TASK-COMPARISON` | 可比性、`comparison_mode`、效应大小、稳定性和推断统计资格 | sample/preparation | `candidate` |
| `TASK-EVIDENCE-COMPILER` | schema-valid MeasurementResult、Evidence Record 和 Evidence Graph | 每次 ToolRun 与结论 | `candidate` |
| `TASK-CLAIM-VERIFIER` | 数字、Evidence ID、状态、比较资格和禁止主张核验 | report/claim | `candidate` |
| `TASK-PUBLIC-SAFE` | 由字段白名单生成脱敏摘要 | VerifiedReport | `candidate` |

五个 P0 域均必须保留 raw metrics、分母、区间、`score_state`、`MeasurementSpec` 和证据状态。当前 `domain_score` 始终为 `null`；候选方法结果使用 `shadow` 或 `unavailable`，不能保存候选域分数。

## 3. P1/P2 与独立后验任务

| Task ID | 输出 | P0 发布规则 |
| --- | --- | --- |
| `TASK-REGULATORY` | TF activity、regulon、motif/ChIP support | raw metrics，`score_state=shadow` |
| `TASK-FUNCTIONAL` | pathway footprint 与目标阶段功能程序 | raw metrics，`score_state=shadow` |
| `TASK-METABOLIC` | 线粒体与代谢转录 proxy | raw metrics，`score_state=shadow` |
| `TASK-ASSAY-TRANSLATION` | surface/secreted marker 与检测候选 | 解释和 Recommendation Card |
| `TASK-COMMUNICATION` | communication potential | 解离 scRNA 只作 shadow；LIANA 与 CellPhoneDB 共享 evidence family |
| `TASK-SPATIAL` | Spatial Reference Concordance | donor、section、ROI 和坐标合同满足后发布证据 |
| `TASK-GRAFT` | graft 组成、成熟与异常状态 | 独立 `GraftAssessment`，不回填移植前分域分数 |

Communication Potential 的独立校验必须来自 receiver-response、空间邻接、蛋白或干预证据；共享 ligand-receptor 数据库或同一方法的不同实现不算独立证据。

## 4. 自动替代与晋升

- 自动替代只处理执行故障，且替代工具必须预注册并共享相同输入、MeasurementSpec、ScoreContract 和验证范围。
- 输入不满足合同直接返回 `unavailable`；其他方法结果保持 `exploratory`。
- 晋升为 `frozen` 至少通过 source holdout、OOD、missing-input、下采样、rare-state、reference/preprocessing swap、许可和 claim review。
- 每次晋升生成新的 Task Card、MeasurementSpec、ScoreContract 和 validation report 版本，不覆盖旧版本。
