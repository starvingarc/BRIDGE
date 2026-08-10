# BRIDGE v2 Object Schemas

| 项目 | 内容 |
| --- | --- |
| 受控主规范 | [BRIDGE v2 PRD](../BRIDGE_v2_PRD.md) |
| 状态 | `schema_contract_draft` |
| 规则 | 所有对象追加式版本管理；正式记录不可静默覆盖 |

本文件保留完整目标对象模型。当前可执行合同以仓库根目录 `schemas/` 和 `src/bridge/toolkit/contracts.py` 为准；尚未实现的对象仍属于设计草案。

## 1. 通用字段与状态

所有正式对象包含：

```text
object_id / object_version / schema_version
created_at / created_by / parent_object_refs
content_hash / status / provenance_refs
```

| 枚举 | 值 |
| --- | --- |
| `evidence_state` | `measured`, `inferred`, `prior_only`, `negative`, `missing`, `unknown`, `unavailable`, `alert` |
| `score_state` | `available`, `shadow`, `unavailable` |
| `comparison_eligibility` | `strictly_comparable`, `contextual_comparator`, `reference_or_OOD`, `not_comparable`, `not_estimable` |
| `comparison_mode` | `descriptive_only`, `inferential` |
| `reconciliation_state` | `stable`, `consensus_supported`, `integration_sensitive`, `unstable` |

数据资产的四个状态字段必须分开保存：`availability`、`metadata_status`、`access_policy`、`evaluation_eligibility`。

当前版本禁止非空 `domain_score`，也禁止 `score_state=available`。`shadow` 仅表示候选证据；未来若引入数值评分，必须由新的冻结 ScoreContract 和 Schema 版本启用。

## 2. ProductCase

| 字段 | 要求 |
| --- | --- |
| `case_id`, `case_version` | 必需，稳定 ID 与追加式版本 |
| `product_definition_ref` | 必需，经研究者确认的 Card ID/版本 |
| `preparations[]` | donor/cell line、sample、preparation、lot、batch、protocol、timepoint、biological/technical replicate |
| `data_role`, `evaluation_eligibility` | 必需，不从文件名推断 |
| `assay_modality`, `specimen_type`, `sampling_context` | 必需 |
| `source_accession`, `asset_version`, `checksum` | 必需的来源与数据指纹 |
| `source_family`, `leakage_group` | 必需，约束 reference、开发、校准与 sealed test |
| `reference_policy`, `prior_snapshot_refs` | 必需 |
| `protocol_ref`, `grafts[]`, `preparation_graft_links[]` | 条件字段；graft linkage 必须显式 |
| `missing_fields[]`, `user_confirmations[]` | 必需，记录缺失与人工确认 |

## 3. AnalysisPlan

`AnalysisPlan` 记录 ProductCase 版本、任务图、运行/跳过原因、分析单位、tool/reference/prior、MeasurementSpec、ScoreContract、环境、资源、联网需求、权限、失败条件、停止条件和预注册替代路径。计划确认后生成不可变版本；计划外任务创建新版本。

## 4. MeasurementSpec 与 ScoreContract

`MeasurementSpec` 至少包含：

```text
measurement_spec_id / version / scientific_question
applicable_product_cards / input_contract / analysis_unit
raw_metric_definition / numerator / denominator / direction
uncertainty_method / minimum_data / missing_behavior
tool_refs / reference_refs / prior_refs / validation_ref
```

未来的 `ScoreContract` 至少包含：

```text
score_contract_id / version / measurement_spec_ref
output_name=domain_score / range=0..100
transform / anchors_or_thresholds / monotonicity
applicability_gate / score_state_rules
minimum_replicates_for_inference / sensitivity_requirements
prohibited_interpretations / reviewer / validation_ref
```

当前 P0 不计算 `domain_score`。`MeasurementSpec` 或未来的 `ScoreContract` 不可用时不得计算、推断或补值。

## 5. MeasurementResult 与 Evidence Record

`MeasurementResult` 保存 raw metric、分子/分母、区间、固定为空的 `domain_score`、`score_state`、evidence state、方法与全部版本引用。

`EvidenceRecord` 在此基础上增加 Evidence ID、claim target、`derived_from`、evidence family、适用范围、支持/反对方向、冲突、缺失和 artifact 引用。LLM 不能创建或修改数值字段。

## 6. 产品与比较对象

`ProductEvidenceObject` 汇总一个 ProductCase 的 P0/P1/P2 结果、gates、alerts、Evidence Sufficiency、CaseEvidenceGraph 和合同快照。

`CaseEvidenceGraph` 与 `ComparisonEvidenceGraph` 保存节点、边、evidence family 和 reconciliation state；允许关系为 `derived_from`、`supports`、`contradicts`、`depends_on`、`same_evidence_family`、`applicable_to` 和 `missing_for`。

`ComparisonRecord` 至少保存：

```text
comparison_id / version / case_refs
common_contract_snapshot
comparison_eligibility / comparison_mode
design_and_confounding_check
raw_metric_and_score_differences / effect_sizes
inferential_results_if_eligible
reconciliation_state / comparison_graph_ref
```

跨版本结果必须在同一冻结合同下重跑。每组只有一个独立 preparation 时，`comparison_mode=descriptive_only`。

## 7. 展示、建议与报告对象

- `VisualizationArtifact`：component ID/version、Evidence IDs、数据版本、单位、分母、区间、缺失状态、过滤条件、导出文件和审核状态。
- `RecommendationCard`：最多三项；保存支持与反对 Evidence IDs、假设、预期结果、反驳条件、资源和人工确认。
- `VerifiedReport`：ProductCase/ComparisonRecord、图表、claim-evidence map、禁止主张检查、public-safe 状态和发布确认。

## 8. 失败与不可变性

- schema/file 错误阻止对应对象发布，但保留失败记录。
- missing、unknown、unavailable、negative 和 alert 不得互换。
- 新证据、合同或人工修正创建新版本；旧报告和 ComparisonRecord 保持可重现。
