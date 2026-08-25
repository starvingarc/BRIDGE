# BRIDGE P0-05 Off-target Control 任务卡

| 字段 | 内容 |
|---|---|
| Task ID | `TASK-OFFTARGET-v0.2` |
| 文档版本 | `0.2` |
| 日期 | 2026-08-25 |
| 状态 | `candidate / executable shadow` |
| 上游 | P0-02 `CellStateEvidenceProfileV2` 与预计算 evidence bundle |
| 输出 | `OffTargetControlProfile v0.1` |

## 1. 生物学问题与当前边界

P0-05 回答一个受限问题：在同一个全制剂分母内，外部产品定义所声明的
`target`、`acceptable_adjacent`、`known_off_target` 和
`role_unresolved` 组成、unknown 原因以及预声明稀有状态的检测边界是什么。

第一版只聚合已经计算好的细胞状态证据，不读取表达矩阵、不重新注释细胞、
不训练 OOD 模型，也不拟合稀有状态校准。它不输出临床安全、疗效、potency、
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

请求必须是 `ToolRequestV2`，且恰好包含六个
`application/json` `StructuredInputRef`。每个引用均需绝对普通文件路径、
Schema URI、对象版本和 SHA-256。

| role | Schema | 关键字段与绑定 |
|---|---|---|
| `product_case` | `bridge://schemas/product-case/v0.1` | ProductDefinition、assay、MeasurementSpec、case provenance |
| `product_definition_card` | `bridge://schemas/product-definition-card/v0.1` | supported assay 与 StateRoleMap ref |
| `state_role_map` | `bridge://schemas/state-role-map/v0.1` | state-role assignments、证据类别、方向与 provenance |
| `off_target_assessment_spec` | `bridge://schemas/off-target-assessment-spec/v0.1` | map ref/hash、分母 ID、unknown allowlist、rare-state rules |
| `cell_state_evidence_profile` | `bridge://schemas/cell-state-evidence-profile/v0.2` | P0-02 profile ID、assay、MeasurementSpec version、观测数 |
| `off_target_evidence_bundle` | `bridge://schemas/off-target-evidence-bundle/v0.1` | 上游对象 ref/hash、分母、state/unknown observations、rare calibration |

`OffTargetEvidenceBundle` 是上游计算结果的最小交接面。它包含 soft mass 与
observed count，但不携带角色判断。完整覆盖状态下，state 与 unknown 的 soft
mass 和 count 必须分别闭合到声明分母；部分覆盖必须显式标为 `partial` 或
`not_assessed`。

## 4. 确定性处理

1. 校验六个文件的 Schema、版本、媒体类型和 checksum。
2. 校验 ProductCase → ProductDefinitionCard → StateRoleMap、assay、
   MeasurementSpec、P0-02 profile 和 bundle 的引用及 checksum 血缘。
3. 拒绝未映射 state、未声明 unknown reason、未声明的 rare calibration、
   inactive spec 或分母不一致。
4. 按外部 StateRoleMap 将预计算 state observations 确定性求和。
5. 只有 composition coverage 为 `complete` 时才计算角色 fraction。
6. unknown 只按外部 allowlist 中实际出现的 reason 汇总。
7. rare-state 结果只使用外部 rule 与预计算 calibration 比较，不拟合新参数。
8. 在发布前再次检查所有输入 checksum，原子写入一个 JSON 结果。

相同输入内容产生相同 run ID、input hash 和结果 artifact hash。

## 5. 输出合同

成功运行生成一个 checksummed
`off_target_control_profile.json`，同时作为 `ToolRunV2.result` 返回。

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

该版本不产生 `MeasurementResult`、图表或第二种结果表示。

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
state、未允许 unknown reason、未声明 calibration、inactive spec 或分母不一致。

本版本不承担：

- P0-02 注释、soft assignment 或 OOD 推断；
- reference、preprocessing 或 assay sensitivity 重算；
- bootstrap、组间推断、剂量反应或风险模型；
- 稀有状态 discovery、spike-in 构建或 calibration fitting；
- P0-06 增殖/应激信号、P0-07 比较或 P0-12 graft 解释；
- 任何正式分数、临床安全或发布授权。

## 8. 验证与后续科学工作

当前工程验证使用完全合成的结构化对象，覆盖角色映射可替换性、完整/部分分母、
unknown allowlist、rare detection、校准缺失/不合格、零观测、血缘、checksum、
输出复用和篡改。该验证仅证明接口与 fail-closed 语义可执行。

在任何科学冻结前仍需独立完成：真实全制剂分母审查、StateRoleMap 生物学审核、
source-family/OOD holdout、known-mixture 组成误差、稀有状态 spike-in 与假阳性
校准、reference/preprocessing/assay sensitivity，以及对每个产品定义版本的签名
审核。以上未完成项不阻塞第一版工具调用，但阻止 formal evidence 与发布声明。
