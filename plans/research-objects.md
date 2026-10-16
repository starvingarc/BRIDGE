# 研究内对象与工作台接口

**状态：** `quick_mapping_backend_candidate; frontend_and_scientific_acceptance_pending`。M1 的对象模型与 HTTP 合同。产品方向见
[BRIDGE 产品设计](bridge-product-design.md)；本文是前后端共同遵守的接口依据。

## 1. 目标

让工作台显示真实的一轮分化：研究者录入方案、开始一轮分化、按天取样、上传数据，系统把样本映射到图谱并给出
分化链结果；Agent 能读取这些对象并在用户确认后创建或修改它们。

非目标：探索层沙箱、分级共享记忆、移植后分析、公网多用户权限。现有会话、评估、报告流程保持不变，新对象只
通过引用关联它们。

## 2. 前后端边界

| 部分 | 可写范围 | 交付 |
|---|---|---|
| 后端 | `src/bridge/web/**`、`src/bridge/**` 中新增的映射与指标模块、`tests/*.py`、相关后端文档 | 存储、HTTP、映射流水线、Agent 行动、后端测试 |
| 前端与界面 | `frontend/**`、`plans/`、`docs/` 中界面与设计文档、`examples/` 素材 | 工作台读写真实对象、录入流程、前端测试、设计更新 |

同一工作树不并行写入；接口变化先改本文，再改代码。`contracts.py`、公开 Schema 与状态枚举保持单写者（后端）。

## 3. 对象

所有对象属于一个研究（`research_id`），沿用研究的账号归属与鉴权；ID 为 32 位小写十六进制。时间为 ISO 8601，
日期为 `YYYY-MM-DD`。执行确认或来源核对后的版本内容不可修改，只能产生新版本。

### 3.1 Protocol 与 ProtocolVersion

```json
{
  "id": "…", "research_id": "…", "name": "Protocol A", "origin": "lab | literature",
  "citation": {"title": "…", "doi": "…"} | null,
  "latest_version_id": "…", "versions": [ProtocolVersionSummary]
}
```

```json
{
  "id": "…", "protocol_id": "…", "version": 3, "status": "draft | confirmed",
  "based_on_version_id": "…" | null, "label": "Boost+" | null, "change_note": "延长 SHH 窗口 2 天",
  "total_days": 28 | null,
  "stages": [{"index": 1, "start_day": 0, "end_day": 4}],
  "reagents": [{
    "id": "…", "name": "CHIR99021", "short": "CHIR", "pathway": "smad | wnt | fgf | shh | notch | maturation | other",
    "kind": "molecule | protein | supplement", "dose_text": "1.5 μM", "start_day": 3, "end_day": 13,
    "catalog_id": "chir99021" | null, "unconfirmed": ["dose_text"], "source_locator": "p.4 Table 1" | null
  }],
  "operations": [{"day": 16, "kind": "feed | passage | sample | freeze | other", "note": "取样后换液"}],
  "provenance": {"material_id": "…" | null, "formalization_version_id": "…" | null},
  "confirmed_at": "…" | null, "unconfirmed": ["source_review", "total_days", "stages", "operations"]
}
```

- `stages` 缺省时按默认窗口（I: D0–4，II: D5–10，III: D11–16，IV: D17 起）。
  前端方案图的阶段分段跟随 `stages`；培养箱优先显示 Run 的 `stage_index`，为 `null` 时按 `stages` 计算。
- `unconfirmed` 列出需研究者核对的字段；存在未核对字段时不能确认。
- 由上传文档生成时复用现有 protocol 形式化（BPL 草稿、编译、来源检查），`provenance` 指向其版本。
- 草稿试剂的 `start_day`／`end_day` 可为 `null`，表示未知，不能替换成 D0；已知端仍须在总天数内。
  存在未知端时执行确认返回 `protocol_incomplete`；来源已核对版本可显式绑定回顾性 Run（7.8），执行 Run 仍须确认。
- `catalog_id` 只引用 `examples/protocol-visualization` 小分子库中已有条目；未匹配为 `null`，不按名称猜测。

### 3.2 Run（一轮分化）

```json
{
  "id": "…", "research_id": "…", "name": "第 3 轮", "protocol_version_id": "…", "cell_line": "H9",
  "start_date": "2026-09-26" | null, "state": "planned | expanding | differentiating | frozen | grafted | ended",
  "graft": {"date": "…", "host": "rat", "site": "striatum"} | null,
  "day": 16, "stage_index": 3
}
```

- 执行轮次的 `day` 与 `stage_index` 由服务端按 `start_date` 与当日日期计算（时区为部署时区），不入库；回顾性轮次为 null（7.8）。
- `today` 由 `operations` 与试剂窗口的起止推导（加入、撤除、换液、取样），服务端返回 `today: [{kind, label}]`。

### 3.3 Sample

```json
{
  "id": "…", "run_id": "…", "day": 16, "collected_on": "2026-10-12", "assay": "scRNA-seq | snRNA-seq",
  "material_id": "…" | null, "session_id": "…" | null, "assessment_id": "…" | null
}
```

数据文件复用研究资料（`material_id`）；不复制原始矩阵。

`assessment_request`：该样本最近一次图谱映射申请 `{"action_id": "…", "status": "pending | approved | running | done | declined | failed"}` 或 `null`。
`/workbench` 只返回待确认的 action，前端靠此字段显示已确认但尚未完成的映射，避免重复申请。

### 3.4 AtlasAssessment（样本映射到图谱）

```json
{
  "id": "…", "sample_id": "…", "status": "awaiting_approval | running | done | failed | unavailable",
  "versions": {"atlas": "…", "naming": "…", "metrics": "chain-v1"},
  "chain": [{"level": 0, "name": "脱离多能", "numerator": 9810, "denominator": 9900, "value": 0.991}],
  "target_fraction": 0.25,
  "gestation": [{"cell_type": "RG_mFP", "weeks": {"7": 0.62, "8": 0.31}, "outside_reference": 0.07}],
  "tree_position": {"RG_mFP": 0.3, "Nb_mFP": 0.35, "Nb_mBIP": 0.35},
  "mapped_cells": [[x, y, z, node_index]],
  "alerts": [{"kind": "pluripotency | proliferation", "value": 0.002}],
  "evidence_ids": ["…"], "failure": {"code": "…", "message": "…"} | null
}
```

- `chain` 为五级条件比例；缺失级别给 `value: null` 与原因，不补 0。`target_fraction` 为五级乘积，任一级缺失时为 `null`。
- `mapped_cells` 至多 600 个，使用 `/api/workbench/devtree` 的坐标系与节点索引，仅用于展示。
- 标准映射在数据关联且输入与固定参考满足资格后自动运行，不生成待确认项；改变参考或探索性分析仍需确认。结果版本化，旧结果保留。

### 3.5 Lead（线索）与 ProposedAction（等你确认）

```json
{"id": "…", "run_id": "…", "sample_id": "…" | null, "chain_level": 3, "summary": "底板化偏低",
 "status": "open | resolved | dismissed", "created_by": "agent | system"}
```

```json
{"id": "…", "research_id": "…", "title": "SHH 靶基因梯度分析", "context": {"run_id": "…", "sample_id": "…"},
 "tier": "formal | exploratory", "estimate": "约 3 分钟",
 "kind": "atlas_assessment | analysis | protocol_draft | object_change",
 "status": "pending | approved | running | done | declined | failed", "result_ref": "…" | null}
```

- Agent 提出的创建或修改（方案草案、新一轮、样本登记、评估请求）一律先成为 ProposedAction，用户确认后执行。
- `exploratory` 在 M1 只作标记，沙箱执行属后续工作。

流程层面的变更提议（样本先登记后关联数据、标准映射自动运行、每轮对话绑定）见[工作台流程](workbench-flow.md)，落地后并入本合同。

## 4. HTTP

前缀 `/api/researches/{rid}`。错误沿用现有 `{"detail": code}` 语义：404 不存在或无权，409 版本冲突或状态不允许，
422 输入不合法。写操作的 `expected_version` 与对象修订号规则见第 7 节。
对象或研究不存在时返回具体错误码（如 `research_not_found`、`run_not_found`），不得返回框架默认的 `Not Found`：
前端以默认 `Not Found`（未注册路由）或 405 判断接口尚未上线并回退示例。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/workbench` | 培养箱一次取齐：protocols（含最新版本）、runs（含 day/stage/today）、每轮最新样本与评估摘要、open leads、pending actions |
| POST | `/protocols` | `{name, origin, citation?}` 或 `{material_id}`（从上传文档生成草稿） |
| GET | `/protocols/{pid}` | 方案与全部版本 |
| POST | `/protocols/{pid}/versions` | 基于某版本创建草稿 `{based_on_version_id, changes}` |
| PATCH | `/protocols/{pid}/versions/{vid}` | 修改草稿（含核对 `unconfirmed` 字段） |
| POST | `/protocols/{pid}/versions/{vid}/confirm` | 确认版本；存在未核对字段时 409 |
| POST | `/runs` | `{protocol_version_id, name, cell_line?, start_date?, state}` |
| PATCH | `/runs/{id}` | 状态、开始日期、移植信息 |
| POST | `/runs/{id}/samples` | `{day, assay, material_id?, collected_on?}` |
| PATCH | `/samples/{id}` | `{material_id, expected_version}`，取样后关联数据；细则见 7.6 |
| POST | `/samples/{id}/assessments` | 生成 `atlas_assessment` 类 ProposedAction |
| GET | `/assessments/{id}` | 评估详情 |
| POST | `/samples/{id}/mapping` | 补齐声明或重试标准快速映射 |
| POST | `/actions/{id}/approve` · `/actions/{id}/decline` | 确认或拒绝待执行项 |
| PATCH | `/leads/{id}` | 解决或忽略线索 |

Agent 对话通过研究／轮次固定绑定的 Session 使用既有消息接口，服务端注入相应对象上下文；详见 7.7。
Agent 创建与修改研究对象的行动仍属于后续增量，不能由自然语言回复宣称已执行。

## 5. 前端行为

- 工作台优先读取 `/workbench`；接口不存在（404/405）时显示标注为示例的数据，存在但为空时显示空状态引导上传方案。
- 培养箱卡片对应 Run；无 Run 的方案在方案库中显示。阶段动画由 `stage_index` 与最新评估的底板化比例驱动。
- 发育树路径由各样本评估的 `tree_position` 连成；取样点视图用 `mapped_cells` 做飞落动画，透镜显示 `chain` 与 `gestation`。
- 方案图直接渲染 ProtocolVersion；`unconfirmed` 字段在胶囊上以虚线标出，确认按钮在全部核对后可用。
- 一轮的控制条位于发育树与方案图上方：样本按天显示映射状态（未映射、等你确认、已确认、映射中、已完成），可登记样本（选择或上传 H5AD，可一并申请映射）、冻存、记录移植、结束。
- 线索气泡、确认队列与对话分别对应 Lead、ProposedAction 与带 `context` 的会话消息。

## 6. 验收

- 后端：对象读写、版本不可变、鉴权隔离、`expected_version` 冲突、ProposedAction 确认前不执行、评估版本化与缺失语义的测试。
- 映射：在合成数据与一份获准的实验室样本上跑通；留一胚胎孕周验证与自洽性检验（阳性、阴性、时间方向）分别记录，
  不把工程跑通写成科学资格。
- 前端：真实接口与示例回退两种模式的组件测试；录入、确认、开始一轮、登记样本、确认评估的完整走查。

## 7. M1 对象存储与接口细化（#131）

- 所有对象返回 revision（从 1 开始的并发修订号），与 ProtocolVersion 的方案序号 version 分开。
  修改请求用 expected_version 匹配目标对象的 revision；不匹配返回 409 object_version_conflict。
  缺少或类型不合法的 expected_version 返回 422。
- 创建方案返回 Protocol（latest 与 versions 均为完整 ProtocolVersion）；创建时同时生成第 1 版空草稿，
  total_days: null 表示尚未填写（旧客户端传入 0 会规范化为 null）。执行确认前须填写正整数总天数和试剂剂量、时间窗口、操作日期，
  且版本及所有试剂的 unconfirmed 均为空。手工录入不生成文档 provenance；
  material_id 文档导入生成带来源的第 1 版草稿，核对规则和错误语义见第 7.5 节。
- 新建无父对象的方案／Run 使用 expected_version: 0。新版本匹配 Protocol 的修订号；
  草稿 PATCH／confirm 匹配该 ProtocolVersion；登记样本匹配 Run；申请评估匹配 Sample；
  Run／Lead PATCH 匹配自身。每次成功写入递增受修改对象的修订号。
  新版本、草稿编辑及确认也递增 Protocol 的修订号，防止基于旧方案状态创建新版本。
- ProposedAction 的内容在 pending 期间不可修改。approve／decline 兼容现有前端的空 JSON：
  以不可变 action ID 和 pending 状态原子决定一次；重复或相反决定返回 409 action_not_pending。
  也可传 expected_version，此时额外匹配 action 的修订号。不得重用此例外更新可编辑对象。
- 创建执行 Run 只接受本研究已确认的 ProtocolVersion；回顾性 Run 接受来源已核对版本（7.8），均永久绑定该版本。工作台 protocols 为每个方案一条，
  latest 是最新版本，versions 包含全部版本；消费者必须通过 versions 找 Run 绑定的历史版本，
  不能仅按 latest.id 关联，否则创建新草稿后旧 Run 会消失。
- /workbench 固定返回 protocols/runs/samples/assessments/leads/actions 六个数组。
  samples 保留全部取样点（按 day、创建时间排序），assessment_id 指向该样本最新评估；
  返回其关联的评估，Lead 仅 open，Action 仅 pending。空研究全部为空，不返回示例或伪造评估。
- 申请评估只创建 pending ProposedAction，确认前不运行任何科学工具。
  #131 的 approve 仅持久化 approved 状态，result_ref 仍为 null；执行与评估结果由 #132 接入。
  相同样本已有 pending／approved／running 请求时返回 409 assessment_request_active。
  不伪造 AtlasAssessment、分化链或映射结果；无结果的评估详情返回 404 assessment_not_found。
- day 是部署时区当前日期减开始日期；无开始日期为 null，开始前可以为负。
  仅在 differentiating 且 0 <= day <= total_days 时给 stage_index/today，其余为 null/空数组。
  自定义阶段窗口两端含当天、不得重叠；默认阶段采用第 3.1 节窗口。
  试剂窗口也两端包含，start_day 当天提示加入，end_day + 1 当天提示撤除（仍在总天数内）。
  原始窗口不被展示推导回写。
- 手工草稿 PATCH 可修改 change_note/total_days/stages/reagents/operations；新版本的 changes 使用相同字段。
  服务端生成版本身份、状态、provenance 与确认时间，客户端不能伪造这些字段。
  试剂缺省 ID 时由服务端分配，已有 ID 须为 32 位小写十六进制且在该版本内唯一。
  非 null 的 catalog_id 须精确存在于现有小分子库；未匹配应传 null。未安装该素材库时拒绝非 null 绑定。
- 样本的 material_id 必须属于同一研究并为 H5AD；仅保存引用，不复制矩阵，不自动创建会话。
  Lead 由后端可信生产者登记，HTTP 仅允许将 open 线索改为 resolved/dismissed。
- 对象保存在研究私有目录独立的版本化存储文件，原有研究资料和会话不迁移。单进程服务的共享锁串行化
  读、检查修订号和写入，原子替换防止部分文件写入；重启后从持久化状态读取。

### 7.5 文档导入草稿与来源核对（#133）

POST /protocols {material_id, expected_version: 0} 读取同一研究内方案资料，
使用当前账号选定模型生成 BPL 与结构字段，经固定编译器及来源覆盖检查后保存草稿。
不需要先上传 H5AD；模型请求期间不持有全局对象锁；失败不创建 Protocol。

ProtocolVersion 增加 unconfirmed 列表，可选项为 source_review、total_days、stages、operations。
手工及旧存储版本默认为空；PATCH 和新版本 changes 可显式更新此列表。
导入版本至少保留 source_review；研究者核对原文、缺项与转换结果后才能显式清空，或用 7.8 的来源核对动作记录版本级核对。
试剂现有 unconfirmed 同时生效，任一列表非空均禁止确认。
模型给出的剂量、名称及摘录须逐字存在于对应片段，日数须在摘录中出现。
此检查只证明字面来源，不证明字段关联正确；所有导入试剂字段仍待人工确认。
未知剂量为空；未知试剂 start_day/end_day 为 null，并标记对应字段待确认，不能执行。
试剂窗口字段允许 null 以保留缺失；确认要求两端均已填写，不能通过清空标记绕过。
无日期操作同时保留在形式化步骤和 operations（day: null、timing_text、source_locator），不进入日程；不从相对时长推算绝对日数。
阶段仅取原文明确阶段；缺失时为空且标为待确认。
小分子只精确匹配库中唯一名称或别名，不从库补剂量或窗口。

GET /protocols/{pid}/versions/{vid}/formalization 返回只读来源记录：
步骤、原文定位、问题、编译诊断、来源绑定及 BPL。无来源版本返回 404。
研究权限和内容哈希均在服务端核验，不返回模型原始回执、凭据或内部路径。
派生版本沿用来源记录，不声称用户修改后的字段已经由该记录重新验证。

固定错误：protocol_material_required (422)、protocol_source_invalid (422)、
protocol_import_invalid (422)、protocol_provider_unavailable (502)、
protocol_compiler_unavailable (503)、protocol_formalization_not_found (404)、
protocol_formalization_unavailable (409)、protocol_formalization_limit (413)。前端需展示版本级待核对项及来源记录；
仅清空试剂标记不足以确认导入版本。


### 7.6 样本取样后关联数据

`PATCH /samples/{id}` 接受 `{material_id, expected_version, mapping_input?}`。修订号属于 Sample；关联必须引用同一研究中
已经上传且内容哈希未变的 H5AD。成功后样本修订号增加，原始文件不复制、不修改。重复关联返回
409 `sample_has_material`，过期修订号返回 409 `object_version_conflict`，损坏或丢失的文件返回
409 `research_material_unavailable`；失败不改变任何对象。多样本拆分与 `scope` 待实现，不静默忽略拆分条件。

Sample 的 `status` 根据持久化数据与实际评估派生：无数据为 `collected`；数据已关联且无运行结果为
`data_attached`；实际评估 `running` 为 `mapping`，`done` 为 `done`，`failed` 或 `unavailable` 为 `failed`。
旧样本不需迁移，创建、关联与 `/workbench` 返回相同含义。`assessment_request` 继续展示历史请求。

标准映射由已注册工具执行：先完成输入 QC，再调用快速映射 v0。创建带数据的 Sample 或关联数据后，
仅在输入声明、固定参考和当前树版本满足要求时自动开始。缺配置为 `standard_mapping_not_configured`，
缺声明为 `mapping_input_required`，参考缺失／模态不符为 `mapping_reference_unavailable`，树版本不符为
`mapping_tree_mismatch`，并发容量已满为 `mapping_worker_busy`。这些状态保留 `data_attached`，在
`assessment_availability: {status: "unavailable", code: "…"}` 中说明原因；不是样本科学失败。
现存 `/assessments` 请求入口仅保留兼容，不触发自动计算。

研究资料上传与详情中的 H5AD 公开元数据提供实际检查到的 `locations`（如 `X`、`layers/counts`），不包含文件路径或内容哈希；历史记录未保存此项时省略，不猜测补齐。矩阵位置不声明原始计数语义，仍由用户确认。

#### 快速映射输入与重试

创建／关联时可提供以下声明，Sample 返回同一 `mapping_input`（未声明时为 `null`）：

```json
{"matrix_location": "X", "matrix_semantics": "raw_counts", "sample_context": "pre_graft", "source_family_id": "DECLARED-SOURCE-FAMILY"}
```

`matrix_location` 为 `X` 或 `layers/<name>`；必须声明原始计数，不从数值外观猜测其科学语义。
`pre_graft + scRNA-seq` 仅使用 `REF-CHEN-VMB-SC-v1`；`post_graft + snRNA-seq` 仅使用
`REF-CHEN-VMB-SN-v1`。不跨模态回退。混合文件应先在私有环境按可核对的来源拆分，网页暂不接受 `scope`。

`POST /samples/{id}/mapping` 接受 `{expected_version, mapping_input?}`，用于补齐首次声明或重试。
已有声明不可换成不同输入；成功结果不自动重算。正在运行／已有成功结果返回 409 `mapping_already_started`。
启动后立即返回 Sample 和持久化 `assessment_id`；前端轮询研究工作台或评估详情。
失败重试只有实际启动才产生新 assessment ID，旧尝试仍可 GET。重试被前置条件或容量阻挡时保留旧
`failed` 状态与 assessment ID，同时用 `assessment_availability` 说明本次未能启动的原因；前端应展示该
当前原因而非只显示旧失败。重启将中断任务标为 `mapping_interrupted`，不能恢复成成功；
迟到的旧进程结果不能覆盖新尝试。账户隔离与原始材料校验适用于所有入口。

#### 快速映射结果与树展示

成功的 AtlasAssessment 额外包含 `tool_run_id`、`method_label: "快速映射 v0"`、
`scientific_status: "candidate"`、`ood_status: "not_calibrated"`、`n_cells`、`n_tree_cells`、
`shared_genes`、`selected_genes`、`reference_genes_not_measured`、`query_genes_not_in_reference`、
`tree_unavailable_cells`、`normalization` 与 `limitations`。`versions` 含固定 reference ID、atlas、naming、
method、tree、features、projection 和 `metrics: "not_computed"`。

`GET /api/workbench/devtree` 返回 `version`（规范化树内容哈希）。前端仅在它等于
`assessment.versions.tree` 时显示 `mapped_cells`；否则说明树版本不匹配。坐标逐点来自同模态、同转移标签的
已有树参考细胞，是参考邻居展示，不是 query 的 scVI 投影或重建发育轨迹。`tree_position` 分母为全部 query
细胞，树外标签不强行放入神经节点；位置比例之和因此可以小于 1。最多 600 个点只是显示抽样。

孕周分布为近邻参考细胞组成，`gestation[].status` 为 `uncalibrated_neighbor_distribution`，
`outside_reference` 保持 `null`。当前五级 `chain` 的分子、分母和值均为 `null`，原因 `chain_not_computed`，
`target_fraction` 为 `null`；无已校准 OOD、链指标或分化质量结论。完整逐细胞结果、原始细胞 ID 和运行路径留在
私有产物中，公开投影采用白名单。每次读取重新核对结果与工具回执，损坏时返回 409 `mapping_result_unavailable`。

方法与资源准备见[快速图谱映射](../docs/quick-atlas-mapping.md)。

快速映射成功同时产生统一 Analysis 索引：索引与 AtlasAssessment 的 done 状态在同一对象存储提交，
共享工具回执与结果文件，不复制结果、不伪造 Session。Assessment 增加 `analysis_id`；分析列表与详情
按 [Analysis 合同](../docs/sample-analysis-api.md#10-标准映射分析来源)读取。历史成功映射启动时核验后补索引；
失败或中断尝试不登记。已有索引的来源损坏时保留历史并返回 unavailable，不退回另一结果或空列表。


### 7.7 研究与轮次对话接入现有 Agent

- `GET/POST /api/researches/{rid}/conversation` 与
  `GET/POST /api/researches/{rid}/runs/{run_id}/conversation` 返回完整的现有 Session 对象。
  GET 不创建会话，未绑定时为 404 `conversation_not_found`；POST 接受空对象并幂等创建或返回绑定会话。
  请求不得提供会话 ID、所有者或任意上下文；研究和 Run 必须属于当前账户及同一研究。
- Session 增加 `conversation_kind: "research" | "run" | null` 与 `run_id: string | null`。
  普通历史会话保持 null，不能因为已关联 research_id 就被自动选为总对话。绑定由服务端创建并持久化，
  与首次会话保存一起原子写入；单进程服务内并发 POST 只创建一条。归档保留原绑定；明确删除后可重新创建。
- 客户端仍通过 `POST /api/sessions/{sid}/messages {text}` 与既有停止、状态和结果接口使用 Agent。
  不接受客户端每条消息改绑对象。原第 4 节的任意 context 提议由固定会话绑定替代。
- 每次普通提问构造当前范围的 `workbench_context`：研究信息、绑定轮次、其准确方案版本及直接父版本、
  已登记样本、评估执行状态、开放线索和待确认行动。总对话读取本研究对象；轮次对话仅读取本轮及其方案。
  不读取其他会话消息、不复制原始数据、不将可见资料自动设为已确认分析输入。
  方案新草稿不替换 Run 绑定的历史版本。方案差异来自已存版本，保留 change_note 的用户记录属性。
- 对象上下文是登记事实与工作流状态，线索是候选解释，pending 行动不是授权。
  数值科学结果仍须通过现有回执校验与 result_summary 接入；仅有 AtlasAssessment 状态或 ID 不构成已验证证据。
  本增量不增加 Agent 对研究对象的写动作，不执行标准映射，不改变分化链定义。
- 上下文为带版本和摘要哈希的私有快照，与触发的用户消息关联。模型返回前重新核对对象上下文；
  内容改变时保留原快照并拒收过期回复，提示重新提问。取消继续使用既有 control epoch，迟到回复不得覆盖停止状态。
- 对象上下文上限 48 KiB（UTF-8 JSON），超限返回明确 unavailable 与范围、对象数量及缩小范围提示，
  不静默裁剪。该上限只针对新增对象上下文，不宣称完成 #100 的总模型预算或长期决策压缩。
  旧会话、工具授权、原有配额和执行恢复语义保持兼容。

模型上下文使用独立的递归字段白名单，边界见
[隐私与来源](../docs/privacy-and-provenance.md#bound-workbench-conversation-purpose)：
仅包含该范围登记的方案内容、轮次/取样信息、线索和工作流状态；不发送细胞系、
资料/会话绑定、来源定位、私有 provenance、文件哈希、评估测量值或未知嵌套字段。
记录名称和备注仍可能识别研究，不能称为匿名数据。该用途不放宽科学结果共享权限。

前端培养箱使用研究总对话，聚焦 Run 时使用该轮次对话，在原有侧栏恢复消息、发送和停止。
发育树快捷问题只预填当前取样点问题，经发送调用真实 Agent；不会生成本地示例解释。
分析输入、精确批准和结果查看继续由“打开完整会话”进入既有界面。切换账户、研究或轮次时
丢弃旧请求的界面回写；发送响应丢失时先读取会话核对是否已接纳，读取也失败则禁止盲目重发。

## 8. Sample analysis lineage (#115, first backend slice)

Analysis registration is additive and does not change the six workbench arrays,
Sample.assessment_id, mapping approval, current adoption, evidence graphs or reports.
A registered analysis binds one exact completed ToolRun to an explicitly selected
Sample and thereby its Run and confirmed ProtocolVersion. A session is not an
experimental batch. Multiple tool runs are not silently grouped into an analysis
or counted as independent replicates.

The sample analysis endpoints and frontend handoff are maintained in
[Sample analysis API](../docs/sample-analysis-api.md). The first slice registers
and reads existing verified results; launching analyses continues through the
existing session plan/approval executor. Cross-session selection is specified below;
scientific comparator eligibility, retry grouping and adoption remain separate work.

## 9. Cross-session analysis cohort selection (#115)

Cohorts save explicit analysis selections across sessions in the same owned research.
They pin analysis IDs and snapshot hashes, not the newest result. Roles reuse
ComparisonGroupRole (baseline/comparator/reference_ood) but are intended comparison
roles, not scientific data permissions. At least one baseline and one non-baseline
member are required. Multiple analyses of one Sample remain one Sample; independence
counts stay unknown without verified ProductCase/biological-unit bindings.

POST /api/researches/{rid}/analysis-cohorts accepts expected_version=0 and members
[{analysis_id, snapshot_sha256, role}]. It returns a pending immutable selection with
a digest, revision and per-member availability. POST /analysis-cohorts/{id}/confirm
requires its expected_version and digest, rechecks all sources, and only confirms
the saved selection. GET collection/detail restores history across service restarts.
Correct a selection by creating a new cohort; earlier selections are retained.

This slice cannot construct a ProductEvidenceBundle, infer scientific comparability,
grant source permissions, adopt results or execute P0-07. Available registered analyses
are background_only with explicit missing-contract reasons; unavailable sources are
excluded and prevent confirmation. The response always exposes execution_available=false.
Newer analysis versions do not stale an older choice; missing/invalidated sources make
it unavailable without deleting the recorded decision. Existing conditional comparison
selection and exact plan approval remain the execution authority.

### 9.1 Binding a cohort to an existing comparison proposal

POST /api/researches/{rid}/analysis-cohorts/{cid}/comparison-proposals accepts
session_id, cohort_digest, expected_revision (the target session input revision),
an existing P0-07 Selection, and members [{analysis_id, bundle_input_id}].
The confirmed cohort and target session must belong to the same research/owner.
Every cohort member maps to exactly one selected registered product-evidence bundle;
the target session already holds these curated bundles, manifest and comparison spec.
No metrics are extracted from QC displays and no objects are silently transferred.

Bundles explicitly declare sample:<Sample.id>, run:<Run.id>, and
protocol-version:<ProtocolVersion.id> references, plus analysis:<Analysis.id> in
provenance_refs; each uses object_version 1.0.0 for this logical identity convention.
The analysis snapshot remains pinned by the cohort. These are user-declared
attributions, not proof that BRIDGE recomputed the uploaded metric values.
Sample assay, registered in-vitro sampling day and intended manifest group role must match; one Sample cannot become
multiple product-comparison units through repeated analyses.

The server stores this binding inside the existing conditional proposal digest chain.
The response is the existing proposal DTO with cohort_binding attached.
Existing conditional confirm/prepare and exact plan approval remain mandatory.
Confirmation, preparation and queued execution recheck the cohort and source analyses.
A changed/deleted source makes the proposal stale and prevents a new execution;
old cohort decisions and results remain historical records. Existing P0-07 rules
continue to decide numeric comparability, confounding and method independence.

### #132 树上 marker 表达补充合同

固定现有发育树形状与坐标。P0-02 在已声明的原始计数上沿用该次映射的共同基因集、
归一化目标和 log1p；在 HVG 选择与中心化之前提取默认面板
FOXA2、LMX1A、OTX2、EN1、CORIN、SHH、NR4A2、TH、DDC、PITX3。
表达仅用于着色，不改变标签、坐标、chain 或任何分数。本版固定默认面板；任意基因选择尚未接入。

`AtlasAssessment.marker_expression` 为可选的可用性/版本/基因/内容哈希/点数摘要。
新接口 `GET /api/researches/{rid}/assessments/{aid}/marker-expression` 在研究所有权检查后返回
已绑定 ToolRun 的不可变表达产物；每次读取校验回执、产物哈希、路径及树/特征集绑定。
未运行、失败或旧结果无表达产物为 404 `marker_expression_unavailable`，损坏为 409
`mapping_result_unavailable`。旧结果不自动重算，表达损坏不抹去仍有效的映射摘要。

表达产物 `object_version=0.1.0`：
- `genes` 为矩阵列顺序；`gene_status` 包含 `available` 或 `not_in_shared_gene_space`，
  `missing_from` 指明 query/reference 哪一方未测。未进入共同基因集的值为 null，实测零保留 0。
- `sample.values` 行序严格对应同一评估的 `mapped_cells`（最多 600 点），取样本自身表达。
- `reference.tree_cell_indices` 是同一树 `cells` 的零基行号，与 `reference.values` 逐行对应；
  仅包含实际映射参考中的细胞，未包含的树点按 `not_in_mapping_reference` 显示缺失，不能补零。
- `tree_version`、`feature_set_sha256`、`normalization` 与评估一致。前端叠加前必须核对当前树版本。
  不同共同基因集的表达尺度不能直接当作同一次归一化，也不是批次校正后的绝对表达比较。

不得向该接口返回原始细胞 ID、供者、私有路径或输入文件名。表达矩阵不注入工作台 Agent 上下文。


### 样本详情自动 QC 接线

功能②沿用既有后台标准分析，在 P0-01 的完成回执落盘后独立登记 sample_qc Analysis，
无需会话；后续映射失败不删除已完成 QC。各来源共用样本内登记序号，保持精确输入、
工具/环境、参数、回执及结果哈希，登记不等于采用。既有成功 QC 在启动时核验补索引，
包括映射失败的尝试；无有效 QC 来源不补，GET 不写入、不重算。

后端提供 QC 摘要、PNG 图、Parquet 表格及有界预览、脱敏 profile JSON；账号权限、
来源损坏降级和文件路由见 [样本分析接口第 11 节](../docs/sample-analysis-api.md#11-样本详情中的自动-qc)。
原始矩阵、日志及内部路径不进入公开 DTO。后端不改 QC 科学语义、参考或原始数据，
不新增独立 QC 调度；标准分析未满足启动资格时不会产生自动 QC。
前端在 Sample 详情读取 analyses，按 source_kind 展示固定版本；无需虚构 session_id。
三套预设数据与 PC 浏览器的功能验收仍按 [用户旅程](user-journey.md) 进行。


### 样本双细胞与细胞周期供数

mapping_input 可选声明 capture_id（单个真实捕获批次）或 capture_id_column（obs 列），两者互斥；
gene_symbol_column 可选指定 var 基因符号列。声明随原始材料冻结，不把一个文件推定为一个捕获批次。
P0-01 开启现有 Scrublet 候选检测，保持原始全部细胞，不自动过滤；无批次信息沿用 not_assessed。
双细胞分数与标签仍在 QC Parquet，observation_id 是原始 obs 名称的关联键。

P0-06 使用既有、版本固定的 Seurat updated-2019 基因集候选和 all_observations 视图，
以 exploratory_process 模式执行；不生成领域评分、不将周期标签用于质量剔除。
完成回执独立登记为 sample_cell_cycle Analysis，提供脱敏 profile 和逐细胞 Parquet，
包括 cycle_S_score、cycle_G2M_score、phase。缺失或歧义基因按工具原合同处理，不修改基因集。
周期失败不阻断 QC 或映射；重启仅核验补索引，不重算。前端只对实际有值的结果绘图。

### 7.8 文献来源核对与回顾性轮次（#137）

来源核对与实验执行是两个独立门槛。`status: draft|confirmed` 继续表示执行确认；
新增只读 `source_review: {status: pending|reviewed, reviewed_at: string|null, note: string}`。
`POST /protocols/{pid}/versions/{vid}/source-review {expected_version, note}` 记录当前账号对
具体版本的来源核对声明，note 必填，说明核对范围和仍未知之处；须有文献 citation 或上传文档 provenance。
该动作不补值，仅移除旧 unconfirmed 中的 source_review 标记，其余待核对项保留；不改变 confirmed 状态，
不证明原文已完整披露或配方可复现。
已核对版本内容冻结；再次核对或 PATCH 返回 `protocol_version_immutable`，修订须创建新版本。
新版本保留出处、继承说明和父版本 ID，但 source_review 回到 pending。完整版本仍可走 confirm；
旧 confirmed 版本不自动升级为来源已核对。

`execution_readiness: {status: ready|incomplete|needs_review, reasons: string[]}` 由服务端派生，
与来源核对独立；ready 仅表示当前结构字段齐全且待核对项清空，真正开始执行仍需 confirm。
缺失 total_days 返回 null；兼容旧客户端传入 0，但规范化为 null。未知剂量继续为空字符串，
未知试剂窗口和操作 day 为 null。操作增加 source_locator，试剂/操作可保留 timing_text；
相对时间文字不自动换算成绝对日数，未知操作日期也阻止执行确认。

试剂增加 `field_provenance` 数组，每项包含 `field: dose_text|start_day|end_day`、
`kind: direct|recipe_reference`、`source_ref`、`source_locator`、`recipe_locator: string|null`。
recipe_reference 必须填写被引用配方的定位；这是核对者记录的来源链，不能称为模型独立提取或实验验证。
同一字段只能有一条出处，未知值不得登记已获得出处。派生版本保留这条链；改变对应值时必须同步
提交新出处或显式清除该字段出处，不能在旧出处下静默换值。客户端不可设置 source_review 或 readiness。

Run 增加不可变 `purpose: execution|retrospective`，缺省和旧记录为 execution。
execution 保持 confirmed 门槛；retrospective 须显式指定且版本 source_review 为 reviewed，
否则返回 `protocol_source_not_reviewed`。回顾性轮次不推断当前 day/stage，不生成 today 执行提醒；
样本 day 是用户登记的实际取样日，不受未知配方终点限制。它可登记、关联数据并走既有 QC/映射入口，
仍逐项满足原有输入、参考与测量资格；来源核对不赋予科学可比性或训练/校准权限。
模型上下文须包含 purpose、source_review.status 和 execution_readiness，保持来源定位等私有字段排除。

日常实验沿用“确认方案即记录实验”，同一方案重复执行使用“再做一批”，界面不显示“轮”。
确认时按既有流程依次调用 confirm 和 POST /runs；本节不增加独立记录入口、执行/回顾性模式选择，
也不要求日常记录增加 source-review 步骤或状态徽章。
文献来源核对与 retrospective 用于公开数据整理和历史数据导入，缺失值及引用链按上述后端合同保留。
前端交互沿用既有方案，后端按实际对接需求提供数据与接口信息。

### 7.9 样本基础分析与对话接力

样本关联 H5AD 后，服务先检查已登记的计数声明，再自动调用已注册的基础工具。
QC / 双细胞 / 细胞周期 / 样本自身 UMAP 与 Leiden 不以参考图谱配置成功为前提；缺少参考只阻止映射。
原始数据与已完成 Analysis 保留，不自动筛除细胞、不推断 capture 或改写矩阵语义。
上传到资料库仍只保存资料；关联到具体样本才确定本流程的归属。

Sample DTO 增加可空 `workflow`：`status`（running / needs_input / needs_review / complete）、
`attempt_id`、`issues`（step / code / message / fields）、`session_id` 与 `agent_state`
（pending / scheduled / unavailable / paused / delivered，未交给 Agent 时为 null）。
该字段描述整个分析流程，不是逐图状态；图继续只使用已验证的 Analysis 结果。
模型仅收到白名单问题与已登记的样本身份，不收到原始矩阵、细胞标识、私有路径或未经验证的数值。
需要补充声明或研究判断时，使用所属实验已有对话；后台自动发起一次有界处理。
模型服务不可用、对话忙碌或输入仍未知不删除结果，不无限重试，不自动改变科学输入。

`POST /api/researches/{rid}/samples/{id}/workflow` 接受 `expected_version` 与可选完整
`mapping_input`，用于补充信息后继续，或在排除故障后重试。使用 MappingInput 提交完整必需字段及需补充或纠正的可选字段；
可选字段显式 null 表示撤回该声明，省略表示保留。仅用户提交可改变声明，模型回复本身不能写入。
补充或纠正声明经校验后创建新尝试，旧尝试绑定其原始声明，旧 Analysis 仍可验证。
相同声明且已有运行中/已完成的尝试不会再次计算；失败后的显式重试保留旧尝试。
已有 `/mapping` 行为保留为映射重试兼容入口。

Agent 使用现有对话输入澄清、工具规划和授权边界；普通基础步骤不调用模型。
复杂分析仍由注册工具计算，不因一次自动接力获得无限分析或改变阈值的权限。
接口交接只要求在现有样本/对话交互中消费问题、提交声明、定位结果，不新增独立面板。

样本内发起的对话消息可在既有 `POST /api/sessions/{sid}/messages` 传 `sample_id`。
服务验证研究/实验归属，复用该资料的会话输入，冻结本次提议计划的样本绑定。
执行完成后，仅将该计划中可验证、输入匹配的结果登记回目标样本；同文件、同日或同对话
不是把结果登记到其他样本的依据。不传 sample_id 的普通对话不隐式沿用上次样本目标。


Agent 构建沿用 #34 机制索引与 #98/#100/#102/#106/#111 的接口边界：Sample.workflow
只是样本基础步骤的派生状态，不是研究问题完成合同，不重建 Todo、授权或预算真相源。
complete 表示适用基础步骤已结束，不能表示所有科学测量可用或研究问题已解决。
已知细胞数不足保留工具原因，不单独反复触发模型。自动接力每个尝试/问题集合最多一次，
失败不隐式重试；取消与重启保留待核对状态，不自动恢复。完整问题级完成合同、长期记忆、
跨阶段用量账本和耐久恢复仍由相应 Issue 承接，本节不核销这些任务。

既有 clarification 卡增加可选 sample_id，服务器按当前样本焦点绑定，客户端不能指定。
样本卡复用原 answer/revise/cancel 路径；count_semantics 对应 matrix_semantics，新增
sample_context（pre_graft/post_graft）及 capture_id 问题字段。source_family_id/capture_id
仅自由填写，选项为空；matrix/列名选项来自文件。提交会继续已声明的基础计算，文案需与普通
intake 卡的“提交不启动分析”区分。缺少剩余必需字段时服务生成下一张卡，不额外调用模型。
未知会保存并停止，用户可 revise 后继续；重复答案幂等，样本版本变化后旧卡不可写入。


### 样本自身细胞图谱供数

QC 后复用已注册 P0-02 表达探索，在独立受限子进程中计算全样本 UMAP 与 Leiden。
完成回执登记 source_kind=sample_cell_atlas；results 中的 expression_cells.parquet
提供 observation_id、umap_1、umap_2、leiden，沿用原始全部细胞与观察顺序。
参数、随机种子、方法版本、原始输入与上游 QC 绑定保留；来源失效返回 409。
精确字段、资源与失败边界见 [样本分析接口第 13 节](../docs/sample-analysis-api.md#13-样本自身-umap-与-leiden-供数)。
前端按 observation_id 与 QC/周期关联；不增加用户声明或独立操作步骤，不把参考树坐标当样本 UMAP。

### 样本聚类 Marker 与按基因供数

沿用同一个 sample_cell_atlas Analysis 和同一次 Leiden 结果，不新增工作流步骤。
已登记 P0-02 的探索性 Marker 排序补充 Parquet 下载；基因颜色与点图数据读取同次
工具生成的完整表达产物。按 analysis_id、material_sha256 与 observation_id 绑定，
不把参考树表达或绘图抽样当成样本全量表达。HTTP 只读取已测量结果，不执行科学计算。

新增 GET /api/researches/{rid}/analyses/{aid}/genes（query、offset、limit）提供精确特征ID检索；
GET /api/researches/{rid}/analyses/{aid}/gene-expression（重复 gene 参数，1–32个）
提供原始顺序 observation_ids、同次 leiden 和各基因的完整 log1p 表达值及分群
mean_log1p/fraction_expressing。原始计数按每细胞总量1万再自然log1p；平均值包括群内零值，
比例分母为群内所有细胞，表达定义为大于0。不存在的ID返回not_found与null，不冒充全零。
所有权失败404，未生成表达产物404，绑定或哈希失效409；读接口不写入、不重算。
细胞级 Wilcoxon/BH 排序只用于本样本探索描述，不作为独立生物重复或条件效应推断。
详细字段、排序及限制维护于 docs/sample-analysis-api.md。
