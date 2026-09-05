# BRIDGE P0-05 Off-target Control 任务卡

| 字段 | 内容 |
|---|---|
| Task ID | `TASK-OFFTARGET-v0.4` |
| 文档版本 | `0.4` |
| 日期 | 2026-09-05 |
| 状态 | `candidate / executable shadow` |
| 上游 | P0-02 V2/V3、预计算 evidence bundle 与可选方法运行对象 |
| 输出 | `OffTargetControlProfile v0.2`；可选 checksummed `MeasurementResultV2`；方法模式另含 `OffTargetMethodBundle v0.1`；两种模式均含 typed visualization data、精确 TSV 与静态图 |

## 1. 生物学问题与当前边界

P0-05 回答一个受限问题：在同一个声明主分母内，外部产品定义所声明的
`target`、`acceptable_adjacent`、`known_off_target` 和
`role_unresolved` 组成、unknown 原因以及预声明稀有状态的检测边界是什么。

兼容模式只聚合已经计算好的细胞状态证据。方法模式进一步执行透明的描述性
区间、independence-group bootstrap、hard/soft sensitivity、输入 spike-in 的
候选检测限、单状态至少一个细胞的二项采样规划以及多来源 OOD 状态协调。两种模式均不读取表达
矩阵、不重新注释细胞、不训练 OOD 模型，也不输出临床安全、疗效、potency、
GMP 放行或产品排序结论。

`known_off_target` 只表示该状态在当前版本产品定义中不是目标组成，不等同于
已证实危害。`role_unresolved` 表示身份可描述但产品角色未定；unknown 表示
身份证据不能可靠解析，两者不得合并。

## 2. 外部生物学决定

实现只固定四个通用产品角色及结果状态，不固定任何具体细胞状态、标签到角色
的映射、证据类别、解释方向、unknown 原因或数值阈值。

这些决定全部由两个 checksummed 对象提供：

- `StateRoleMap v0.1`：逐个 `state_id` 声明产品角色、证据类别、解释方向
  和来源；其版本与 `ProductDefinitionCard` 绑定。
- `OffTargetAssessmentSpec v0.1`：绑定精确 StateRoleMap checksum，声明主
  分母、允许的 unknown 原因、需要检查的稀有状态、允许的检测限与假阳性上限，
  以及缺校准时返回 `cannot_exclude` 或 `not_assessed`。

后续生物学审核只需发布新对象版本；不得通过修改包内条件分支来改变产品定义。

## 3. 精确输入合同

请求必须是 `ToolRequestV2`。`legacy_aggregation` 恰好包含原有六个对象；
`method_runtime` 恰好包含十个对象，并将 P0-02 输入升级为 V3。每个
`StructuredInputRef` 均需绝对普通文件路径、Schema URI、对象版本和 SHA-256。

| role | 模式 | Schema / 关键绑定 |
|---|---|---|
| `product_case` | 两者 | ProductDefinition、assay、MeasurementSpec；方法模式另绑定 BiologicalUnitManifest |
| `product_definition_card` | 两者 | supported assay 与 StateRoleMap ref |
| `state_role_map` | 两者 | state-role assignments、证据类别、方向与 provenance |
| `off_target_assessment_spec` | 两者 | map ref/hash、分母、unknown allowlist、rare-state rules |
| `cell_state_evidence_profile` | 两者 | legacy 为 V2；方法模式为 V3，含 composition 与 DataView lineage |
| `off_target_evidence_bundle` | 两者 | 上游 ref/hash、分母、state/unknown observations、supplied calibration |
| `biological_unit_manifest` | 方法及任何投影运行 | P0-01 生成的 immutable `declared` analysis-unit 与 independence-group mapping |
| `biological_unit_attestation_receipt` | 方法 | data owner/caller 对 `analysis_execution` 设计的显式声明；绑定 manifest/assignment/DataView/observation digest、逐项确认、attestor、UTC 时间与外部 attestation ref/hash |
| `off_target_method_spec` | 方法 | 方法选择、置信度、bootstrap 次数、planning target、OOD channel→family→upstream hash/method/reference 绑定与规则 |
| `off_target_method_input` | 方法 | unit-level soft/hard composition、spike-in trials、仅含 channel ID/state/reason 的 OOD observations |
| `measurement_spec` | 两者可选 | 独立 P0-05 MeasurementSpecV2；须匹配 assay、产品适用范围、P0-05、三类投影 metric 及 BiologicalUnitManifest 的 analysis/independence/observation units |

`OffTargetEvidenceBundle` 是上游计算结果的最小交接面。它包含 soft mass 与
observed count，但不携带角色判断。完整覆盖状态下，state 与 unknown 的 soft
mass 和 count 必须分别闭合到声明分母；部分覆盖必须显式标为 `partial` 或
`not_assessed`。

## 4. 确定性处理

1. 校验所选模式的六个或十个文件、Schema、版本、媒体类型和 checksum。
2. 校验 ProductCase → ProductDefinitionCard → StateRoleMap、assay、
   MeasurementSpec、P0-02 profile 和 bundle 的引用及 checksum 血缘。
3. 方法模式须提供 P0-01 `declared` manifest 和独立 attestation receipt；其 `decision` 必须为 `confirmed`、`attestation_scope` 必须为 `analysis_execution`、四项设计确认必须完整，并与 manifest、assignment、DataView、observation digest 和 unit contract 完全一致。旧 `reviewed/frozen` manifest 不能代替该收据。
4. 投影请求须提供 BiologicalUnitManifest，并核对 MeasurementSpec 的 analysis unit、independence group 及 scRNA/snRNA observation unit；P0-05 domain spec 与 ProductCase 中的 P0-02 source spec 保持独立。
5. 拒绝未映射 state、未声明 unknown reason、未声明的 rare calibration、
   inactive spec 或分母不一致。
6. 按外部 StateRoleMap 将预计算 state observations 确定性求和。
7. 只有 composition coverage 为 `complete` 时才计算角色 fraction。
8. unknown 只按外部 allowlist 中实际出现的 reason 汇总。
9. 方法模式核对 DataView、BiologicalUnitManifest、unit-level 与 aggregate counts。
10. 执行描述性 exact interval、hard/soft sensitivity 与 independence-group bootstrap。
11. 每个 spike-in 浓度只允许每个 independence group 一次，计算候选检测限与单状态二项规划；按 MethodSpec 固定的上游来源族协调 OOD 状态。
12. 从同一 typed visualization data 生成精确 TSV 与 SVG/PNG/PDF，在发布前再次检查输入 checksum 并原子写入全部 artifact。

相同输入内容与 random seed 产生相同 run ID、input hash 和 artifact hash；
方法模式下 random seed 是运行指纹的一部分。

## 5. 输出合同

两种模式都生成 checksummed `off_target_control_profile.json`，同时作为
`ToolRunV2.result` 返回；方法模式原子增加
`off_target_method_bundle.json`。

P0-05 v0.5.2 始终返回 profile v0.2。未提供 MeasurementSpec 时明确记录
`not_requested` 且不生成 normalized measurement；提供并通过校验时，每条现有
role、unknown 和 rare-state 记录各生成一个 checksummed MeasurementResultV2。

| 字段 | 含义 |
|---|---|
| upstream refs/hashes | ProductCase、Card、RoleMap、AssessmentSpec、P0-02 profile 与 evidence bundle 的精确绑定 |
| `primary_denominator` | denominator ID、细胞数、soft mass 与单位 |
| `role_composition` | 四个通用角色的 soft mass、observed count、fraction、assessment 与 exclusion 状态 |
| `unknown_profile` | unknown 总量及调用方声明的原因分解 |
| `rare_state_profile` | observed count、soft fraction、calibration ref/hash、LOD/假阳性/UCB 与检测状态 |
| `reason_codes` | coverage、零观测、缺观测和校准限制 |
| `evidence_state` | 固定 `shadow` |
| `score_state` / `domain_score` | 固定 `unavailable` / `null` |
| measurement projection | 缺失或不可用保持 null，不补零；所有结果仍为 `score_state=unavailable` / `domain_score=null` |

方法 bundle 另含：

| 字段 | 含义 |
|---|---|
| `executions` | selector、canonical method ref、实际实现、包版本、状态与 reason code |
| `composition_intervals` | descriptive cell-count interval 与 independence-group bootstrap |
| `hard_soft_sensitivity` | 同一角色 hard fraction 与 soft fraction 的差异 |
| `rare_intervals` / `spike_in_calibrations` | 稀有状态描述区间、检出命中率曲线与 candidate detection limit |
| `planning_records` | 单一预声明状态至少观察一个细胞所需的观察数，以及独立随机抽样、完美检测假设；不是 SCOPIT |
| `ood_disagreement` / `ood_ensemble` | 来源族分歧与外部有序规则的协调结果 |

## 6. 缺失、零值与检测语义

- composition 不完整：保留已观察 soft mass/count，但 fraction 为 `null`，
  assessment 为 `not_assessed`。
- 某角色或 unknown 为零：`exclusion_state=cannot_exclude`，不得表述为不存在。
- rare state 有合格校准且 count 大于零：`detected`。
- rare state 有合格校准且 count 为零：`not_detected_above_lod`，同时保留
  supplied upper bound 和“零观测不等于不存在”原因。
- rare calibration 缺失或不满足外部阈值：`cannot_exclude` 或
  `not_assessed`。
- rare observation 行缺失：`not_assessed`，不得自动补零。

## 7. 拒答与非目标

以下情况在 eligibility 阶段 fail closed：V1 请求、表达资产、任意 parameters、
对象数量/role/Schema/version 不符、checksum 漂移、跨对象引用不一致、未映射
state、未允许 unknown reason、未声明 calibration、inactive spec、方法对象不完整、attestation receipt 缺失或未确认、attestation/manifest/assignment/DataView/observation/unit 绑定漂移、
analysis-unit/independence-group 漂移、同一状态/浓度内重复 spike-in independence group、OOD channel/upstream lineage 不匹配或 aggregate count 不闭合。

本版本不承担：

- P0-02 注释、soft assignment 或 OOD 推断；
- reference、preprocessing 或 assay sensitivity 重算；
- replicate-level 假设检验、剂量反应或风险模型；
- 稀有状态 discovery、spike-in 构建或 calibration fitting；
- deep OOD 模型训练、阈值学习或 catalog candidate 的自动选择；
- P0-06 增殖/应激信号、P0-07 比较或 P0-12 graft 解释；
- 任何正式分数、临床安全或发布授权。

## 8. 验证与后续科学工作

当前工程验证使用完全合成的结构化对象，覆盖两个模式、八个 selector、角色映射
可替换性、完整/部分分母、analysis-unit 与 independence-group 血缘、exact 与
bootstrap interval、hard/soft sensitivity、独立组 spike-in、单状态二项规划、checksummed OOD 协调、零/缺失、
checksum、attestation receipt 和外部记录摘要绑定、seeded deterministic reuse 和篡改。该验证仅证明接口、计算路径与
fail-closed 语义可执行。

在任何科学冻结前仍需独立完成：真实全制剂分母审查、StateRoleMap 生物学审核、
source-family/OOD holdout、known-mixture 组成误差、稀有状态 spike-in 与假阳性
校准、reference/preprocessing/assay sensitivity，以及对每个产品定义版本的签名
审核。以上未完成项不阻塞第一版工具调用，但阻止 formal evidence 与发布声明。

## 9. BiologicalUnitAttestationReceipt 边界

该收据记录 data owner/caller 对四项 biological-unit 设计作出的显式、可追溯声明。runtime 只验证收据结构，以及它与 manifest、assignment、DataView、observation digest、unit contract 和外部 attestation 摘要的绑定；不认证 attestor 身份，也不验证外部记录来源的真实性。部署层负责将已认证的对话或工作流记录映射为 `attestation_ref` 与 `attestation_sha256`。该收据不证明生物学真值、独立审核或科学发布、临床、GMP、疗效、安全、potency 权限。可选 `caveats` 仅保存简短限制，不改变 `confirmed` 语义。
