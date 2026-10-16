# 样本分析历史接口与前端交接

本文是 #115 分析登记与跨会话名单的后端接口合同。研究对象入口见
[研究内对象](../plans/research-objects.md)。本阶段提供**已完成执行的登记与历史读取**：
一份样本可以保存多次独立分析，每条记录固定实际执行输入、工具版本、参数、结构化资源引用和结果文件来源。

分析发起继续使用既有会话计划与批准接口。本接口不会启动任务，也不等于采用结果。
跨会话名单见第 8 节，关联既有比较计划见第 9 节；公开 comparator、自动对齐重算、重试归组、当前采用及报告更新仍待后续。标准映射来源见第 10 节，自动 QC 来源与受控结果文件见第 11 节。
这里的 Analysis 是一次明确选择的 ToolRun；不能把一个会话、多个工具调用或失败重试自动推断成一轮实验。

## 1. 对接方式

前端负责分析列表、详情和进入结果的交互；后端负责身份、持久化、来源核验与错误语义。
现有 api.ts 的 request/ApiError、账号 Cookie、Origin 校验和 Artifact 类型可直接复用。

所有路径以 /api/researches/{rid} 为前缀：

| 方法 | 路径 | 请求或用途 |
|---|---|---|
| GET | /samples/{sample_id}/analysis-sources?session_id={sid} | 枚举指定会话中的执行回执及登记资格 |
| POST | /samples/{sample_id}/analyses | 登记一个已完成执行；请求见下文 |
| GET | /samples/{sample_id}/analyses | 返回该样本全部已登记分析，按登记先后排列 |
| GET | /analyses/{analysis_id} | 读取固定分析版本及当前来源可读性 |
| GET | /analyses/{analysis_id}/results/{result_id} | 读取自动 QC 的受控展示文件 |
| GET | /analyses/{analysis_id}/results/{result_id}/preview | 读取 QC 数据表的有界预览 |

GET 均不创建记录，不推断样本归属。跨研究或账号的会话不能用于登记。
会话可通过现有研究会话列表选择；服务端仍逐项核验实际输入。

~~~json
{
  "expected_version": 1,
  "session_id": "11111111111111111111111111111111",
  "receipt_id": "22222222222222222222222222222222"
}
~~~

expected_version 匹配 Sample.revision。receipt_id 来自 analysis-sources，
不含文件后缀；不要使用 tool.run_id、工具名称、结果文件名或 plan_id 替代。
客户端不能提交结果、参数、reference、Run 或 ProtocolVersion 来改写来源。

成功返回 AnalysisDTO。对同一样本重复提交同一 session_id + receipt_id，
返回原分析 ID；重复请求不会制造新版本，即使此时 Sample.revision 已变化。
新的执行回执产生新的分析 ID 与样本内 version 序号，即使参数及结果字节相同。
接口在同一服务锁下校验、去重和保存，不修改 Sample.revision。

## 2. 建议的 TypeScript DTO

以下为交接形状；将类型加入前端 objects.ts，四个请求加入 api.ts 即可。
Artifact 沿用既有类型；JSON 参数仅供显示，不能作为重执行请求。

~~~ts
type JsonValue = null | boolean | number | string | JsonValue[] | {[key: string]: JsonValue};

type AnalysisSourceDTO = {
  receipt_id: string;
  tool_id: string;
  execution_state: string;
  eligible: boolean;
  reason_code: string | null;
};

type AnalysisResultDTO = {
  id: string;
  source_artifact_id: string;
  sha256: string;
  display_sha256: string | null;
  artifact: Artifact | null;
  assessment?: {id: string; url: string} | null;
};

type AnalysisDTO = {
  source_kind: "session_execution" | "atlas_mapping" | "sample_qc";
  qc_summary?: {[key: string]: JsonValue} | null; // 第 11 节，共用既有 QC 摘要形状
  assessment_id?: string;
  mapping_versions?: {[key: string]: string};
  reference_manifest_sha256?: string;
  id: string;
  research_id: string;
  sample_id: string;
  run_id: string;
  protocol_version_id: string;
  revision: number;
  version: number;
  created_at: string;
  snapshot_sha256: string;
  session_id: string | null;
  receipt_id: string | null;
  receipt_sha256: string;
  plan_id: string | null;
  declaration_revision: number | null;
  execution_state: "succeeded" | "partial";
  tool: {id: string; version: string; run_id: string; environment_spec_id: string};
  material_id: string;
  material_sha256: string;
  measurement_spec_ref: string | null;
  random_seed: number;
  parameters: {[key: string]: JsonValue};
  parameters_sha256: string;
  input_assets: {
    asset_id: string; sha256: string; format: string; input_level: string;
    matrix_location: string | null; matrix_semantics: string | null;
    assay: string | null; data_view_id: string | null;
  }[];
  object_inputs: {
    input_id: string; role: string; schema_ref: string;
    object_version: string; sha256: string;
  }[];
  results: AnalysisResultDTO[];
  availability: {status: "available" | "unavailable"; reason_code: string | null};
};

// GET analysis-sources -> {sources: AnalysisSourceDTO[]}
// GET sample analyses -> {analyses: AnalysisDTO[]}
// POST registration / GET analysis detail -> AnalysisDTO
~~~

revision 本阶段固定为 1，不提供 PATCH；version 是样本内的登记序号，不是方案版本。
plan_id/declaration_revision 在旧回执没有记录时为 null，不能补猜。
results[].id 是分析内的稳定结果 ID；source_artifact_id 是原始执行产物 ID。
sha256 对应原始产物；display_sha256 对应用户可下载展示副本，两者可以不同。
parameters_sha256 钉住完整私有参数；显示副本会省略内部路径等内容。

## 3. 一个样本两次分析的调用顺序

1. 从 workbench 取 Sample.id、Sample.revision 和所属 Run；方案版本沿 Run.protocol_version_id 查找。
2. 沿用会话上传/选择研究资料、声明输入、生成计划、批准执行的已有流程。
3. 执行结束后调用 analysis-sources；仅对 eligible 为 true 的回执显示可登记操作。
4. 明确选择样本和执行后 POST 登记；已有用户明确指令即可，不要求再叠一次确认。
5. 样本列表区域单独 GET analyses，详情按 analysis_id 读取；用 results[].artifact 的既有
   URL 打开结果。不要拼原始文件路径，不要将 JSON 展示副本当成计算输入。
6. 第二次分析按相同流程登记，产生 version 2。version 1 及其结果继续存在；
   创建方案新草稿不会改变旧分析绑定的 ProtocolVersion。
7. 刷新、切换研究或重新登录后，以服务器返回内容恢复；空列表就是尚未登记。
   普通会话结果不自动回填，也不创建示例记录；标准映射的启动补索引见第 10 节。

current/adopted 字段在本阶段不存在。不能将 version 最大、created_at 最新或列表末项
解释成当前采用，不能因此替换 Sample.assessment_id、证据图或当前报告。
同一 Sample 多次分析仍然是同一样本，不能增加生物学重复数。

## 4. 版本与来源规则

- 服务端读取真实、已登记且状态为 succeeded/partial 的执行回执，验证回执内容、
  原始产物和展示副本。failed、running、not_implemented 等状态不能冒充完成结果。
- 固定保存原请求和回执哈希；输入包括实际矩阵 hash/location/semantics、
  data_view_id、工具与环境版本、测量定义、随机种子、参数及结构化资源的版本/hash。
- reference 的精确身份以 object_inputs 中实际保存的 role/version/hash 为准。
  没有结构化版本记录的旧执行不补写“当前 reference”，也不把环境版本当成图谱版本。
  参数展示副本会隐藏内部路径和敏感键；完整参数由 parameters_sha256 绑定。
- 首阶段只接受单资产执行。输入必须是该 Sample.material_id 在所选会话中的明确选择，
  或具有可核验历史 QC selected_data_view 来源的派生视图。相同文件字节、标题或日期
  不能代替 material_id 与来源关系。对象输入型执行和多资产 cohort 返回不匹配，等待后续合同。
  派生视图只由匹配 data_view_id、父输入身份和哈希的已核验 QC 来源建立关联；
  无关历史 QC 的缺失或损坏不影响该分析。所选来源无法核验时仍拒绝登记，并将已有分析标为不可用。
- 源资料、会话、矩阵和结果文件沿用现有存储，不复制原始矩阵。分析记录追加保存，
  不覆盖旧记录，不修改实验 Run、方案或现有会话结果。
- Analysis.version 是登记顺序。分析条件改变应执行新计划并登记新回执；
  重复 HTTP 请求去重仅解决重复提交，不表示已经实现失败重试/attempt 归组。
- 本接口中的 execution_state 表示工具执行结果，availability 只表示来源当前是否可核验；
  两者均不表示科学结论有效、reference 合格、评分可用或当前结果已被采用。

## 5. 来源不可用与错误处理

历史元数据和 snapshot_sha256 固定保存；详情读取时重新核验来源。
回执/产物被改写、会话被删除、结果被输入修订作废或来源不可读取时，返回：

~~~json
{
  "availability": {
    "status": "unavailable",
    "reason_code": "analysis_source_unavailable"
  }
}
~~~

同时 results[].artifact 为 null，保留结果 ID 与哈希。不显示可点击的有效结果入口，
不清空历史，不自动改用另一份结果。本阶段没有新的删除或采用接口。
现有历史报告的 acknowledgement_required/acknowledgement_url 仍然有效，
不能用分析详情跳过报告访问确认。

错误沿用现有 JSON detail/user_message：

| HTTP | detail | 前端处理 |
|---|---|---|
| 404 | research_not_found / sample_not_found / analysis_not_found | 不存在或无权，不能按示例回退 |
| 404 | analysis_session_not_found | 会话不属于当前研究/账号，或已删除 |
| 404 | analysis_source_not_found | 回执 ID 不存在 |
| 409 | object_version_conflict | 刷新 Sample 后重新核对；不要盲目改 revision 重试 |
| 409 | analysis_sample_input_mismatch | 换正确样本/会话；不要按文件名补关联 |
| 409 | analysis_source_not_completed | 尚无可登记的完成结果 |
| 409 | analysis_source_invalidated | 输入修订已使该结果失效，不能作为新记录登记 |
| 409 | analysis_source_unavailable / analysis_result_unavailable | 来源或结果不能核验/读取，保留现有历史 |
| 409 | analysis_store_unavailable / analysis_limit | 显示服务器提示，不回填空历史 |
| 422 | 请求字段验证错误 | 不接受缺失、非法 ID 或伪造参数/结果字段 |

## 6. 与现有前端及并行工作兼容

本阶段不改 frontend 文件；workbench 的六个数组和 Sample DTO 保持原样；Assessment 新增可选 analysis_id 见第 10 节。
Claude 的方案来源复核、nullable 天数、未核对字段，以及样本后补数据/标准映射可用性，
分别沿用其原接口；不要将 analysis 注册接成 requestAssessment 的替代品。

研究/Run 对话绑定接口仍由对应工作实现；会话分析登记只接收实际 session_id 并做所属研究核验；已绑定 Run 的会话还须匹配样本所属 Run，
不根据对话标题创建 Run、不自动把自由对话归到样本。前端可在任何现有会话完成后登记结果。

后端回归覆盖真实合成 QC 执行的两次登记、重启保留、方案新版本隔离、来源损坏/失效/
删除、错样本/错 Run 拒绝、并发重复提交、参数版本隔离和跨账号隔离。新分析列表的界面交互与浏览器验收由前端实现后完成；
这些工程检查不代表真实实验室数据或科学资格已验证。

## 8. 跨会话分析名单

此接口保存用户明确选定的精确版本，供后续比较准备使用。它不执行比较，
不生成 ProductCase 或实测 ProductEvidenceBundle，也不改变当前采用、图谱或报告。
即使名单 confirmed，execution_available 仍为 false；“确认名单”不能呈现成“批准计算”。

同一研究中任意会话的已登记分析均可选择。GET sample analyses 提供 analysis_id 和
snapshot_sha256；客户端不能用最新版本、Sample ID 或文件名替代这两个绑定值。
用户想纠正名单时创建新名单，原名单仍可读取；本阶段没有修改、删除或“当前名单”接口。
名单可包含会话执行、标准映射与自动 QC 分析；后两者的 session_id 为 null，应按 analysis_id 进入分析详情，不能拼接会话链接。

| 方法 | 路径（前缀同上） | 用途 |
|---|---|---|
| POST | /analysis-cohorts | 创建待确认的固定名单 |
| GET | /analysis-cohorts | 返回 {cohorts: AnalysisCohortDTO[]} |
| GET | /analysis-cohorts/{id} | 读取名单及当前来源可用性 |
| POST | /analysis-cohorts/{id}/confirm | 重新核验来源并记录确认 |

创建请求：
~~~ts
type CohortMember = {
  analysis_id: string;
  snapshot_sha256: string;
  role: "baseline" | "comparator" | "reference_ood";
};
// POST /analysis-cohorts
type CohortCreate = {expected_version: 0; members: CohortMember[]};
// POST /analysis-cohorts/{id}/confirm
type CohortConfirm = {expected_version: number; digest: string};

type AnalysisCohortDTO = {
  id: string; research_id: string; members: CohortMember[];
  digest: string; revision: number;
  status: "pending" | "confirmed";
  created_at: string; confirmed_at: string | null;
  entries: {
    analysis_id: string; sample_id: string; run_id: string;
    protocol_version_id: string; session_id: string | null; analysis_version: number;
    role: CohortMember["role"];
    category: "background_only" | "excluded";
    availability: {status: "available" | "unavailable"; reason_code: string | null};
    reason_codes: string[];
  }[];
  summary: {analysis_count: number; sample_count: number; independent_unit_count: null};
  availability: {status: "available" | "unavailable"; reason_code: string | null};
  reason_codes: string[];
  execution_available: false;
};
~~~

名单含 2–32 个不同 analysis_id，至少一个 baseline 和一个非 baseline。
这些 role 是用户希望如何组织比较的记录，沿用现有 ComparisonGroupRole；
不是数据许可、训练角色或独立性声明。不能据此取得公开 comparator 的使用权限。
确认需要返回的 digest 和 revision；revision 从 1 变为 2。成功后相同 digest 的
原确认请求可安全重放，返回原决定；来源后来不可用时，返回原决定及不可用状态，
不新增确认。创建请求无幂等键，响应丢失时先 GET 核对，不能盲目重建。

可读分析在本入口一律 background_only：名单记录本身没有绑定冻结比较规范、
实测产品证据包和独立单位记录。它不代替原有 conditional-inputs 的科学资格判断。
来源不可用时该项 excluded，待确认名单不能确认。已确认名单保留原决定/时间，
availability 另行变为 unavailable，不抹去历史、不替换来源。

| reason_code | 给用户解释的含义 |
|---|---|
| frozen_comparison_spec_required | 尚未绑定已冻结的比较规范 |
| product_analysis_context_required | 尚未绑定产品与分析上下文 |
| measured_comparison_evidence_required | 尚未绑定符合规范的实测产品证据包 |
| independence_not_recorded | 尚未核验独立单位；独立重复数未知 |
| multiple_analyses_same_sample | 名单包含同一样本的多个分析版本 |
| shared_input_bytes | 多项分析使用相同原始资料字节；不据此推断样本身份或独立性 |
| reference_ood_group_not_rankable | 参考或域外资料不能进入产品排名 |
| analysis_source_unavailable / cohort_source_unavailable | 所选来源当前无法核验 |

两次分析可属于同一样本，不能据分析数增加 biological replicate 数。
summary.sample_count 只按已登记 Sample ID 计数，不声称这些样本独立；
independent_unit_count 保持 null，细胞数、会话数、Run 数也不能代替它。
不同测量定义/参考如何对齐、重算成本及相应授权留给后续比较合同接入。

409 错误另包括 cohort_analysis_changed（analysis hash 不匹配）、
cohort_decision_changed（确认 digest 不匹配）、object_version_conflict、
cohort_store_unavailable 和 cohort_limit。其他研究/账号及不存在的分析/名单返回 404；
重复 analysis_id、成员数量或角色组合错误返回 422。前端处理沿用 ApiError。
每个研究最多保存 128 份名单，总文件不超过 1 MiB；超限拒绝写入，不截断历史。

Claude 接线：在样本分析列表选择明确版本，展示名单及上述限制，调用创建/确认，
刷新后由 GET 恢复。界面不得因 status=confirmed 启用“运行比较”或标记科学可比。
比较执行仍通过 conditional-inputs 选择核对、确认、生成计划和单独批准执行；跨会话名单关联已登记输入见第 9 节。

## 9. 把已确认名单接到比较计划

跨会话名单可以关联到一个比较会话中已经登记的结构化输入，并沿既有审批链运行 P0-07。
建议使用独立比较会话，保留各源会话的输入配置。此接口不复制文件、生成证据包或从 QC 图表
提取数字；目标会话的输入通过现有 analysis-inputs/objects 上传/登记，来源权限和校验继续有效。

~~~ts
type CohortComparisonRequest = {
  session_id: string;
  cohort_digest: string;
  expected_revision: number; // 目标会话 conditional_inputs.input_revision
  selection: Selection; // 既有 P0-07 legacy_comparison 或 method_runtime
  members: {analysis_id: string; bundle_input_id: string}[];
};
// POST /api/researches/{rid}/analysis-cohorts/{cid}/comparison-proposals
~~~

目标会话和名单必须属于同一个研究、同一个账号；名单必须已确认且源分析仍可核验。
每个名单成员一一对应一个已选 product_evidence_bundle，不能额外加入、漏掉或重复成员。
比较工具接受 2–20 个证据包；更大的名单需创建一个明确选定的子名单，接口不会静默截断。

证据包使用现有 ProductEvidenceBundle Schema。除现有科学合同字段外，该接线要求以下
明确关联；均由上传者声明，服务端检查与登记对象的一致性：

| 字段 | 必须对应的引用 |
|---|---|
| product_case.source_unit_kind | sample；本接口暂不推断 preparation 归属 |
| product_case.sample_or_preparation_ref | sample:<Sample.id> |
| batch_refs | 包含 run:<Run.id> |
| protocol_refs | 包含 protocol-version:<ProtocolVersion.id> |
| provenance_refs | 包含 analysis:<Analysis.id> |
| product_case.assay | 与已登记 Sample.assay 一致 |
| timepoint | basis=in_vitro_day，order 与 Sample.day 一致 |
| manifest 中该 bundle 的 group.role | 与名单为该 Analysis 记录的 role 一致 |

上述逻辑身份引用的 object_version 为 1.0.0；不要填写 Sample.revision 或样本内的分析序号。
精确执行版本仍由 Analysis ID 与名单中的 snapshot_sha256 绑定。
同一 Sample 的多个分析版本可保留在名单中，但不能在此产品比较入口充当多个分析单位。

该关联标记为 user_declared。服务端验证引用、文件完整性和既有比较合同，不声称已从
Analysis 结果中复算并证明每个上传 metric 的血缘，也不把 QC 自动升级为科学资格合格。
上传的实测证据、产品定义、reference 和独立单位声明仍需相应的来源与科学审查。

成功返回既有 ConditionalProposal DTO，另带：
~~~ts
type CohortBinding = {
  research_id: string; cohort_id: string; cohort_digest: string; session_id: string;
  attribution: "user_declared";
  members: {analysis_id: string; bundle_input_id: string}[];
};
// 返回的 proposal.cohort_binding，以及后续 Session.conditional_inputs.selections 中同一字段。
~~~

名单本身的 execution_available=false 保持原意：单独确认名单不能执行。
具体比较 proposal 的 category、execution_available、reasons 和 diagnostics 则来自现有
比较合同检查。时间点、度量定义、reference 或混杂条件不满足时，仍会返回背景/排除及原因，
不能因为名单已确认而改写为可比。带独立单位要求的方法继续执行原有方法门槛，
未声明独立单位时不能把样本或 bundle 数当成独立重复数。

调用顺序：

1. 读取目标会话的 analysis-inputs 与 conditional_inputs.input_revision，选择冻结比较规范、
   案例 manifest、全部 evidence bundles，以及适用的方法输入。
2. POST 本接口，得到带名单绑定的 proposal。保存 session_id、proposal.id 和 digest。
3. 沿用 POST /api/sessions/{sid}/conditional-inputs/confirm，发送 draft_id、draft_digest、
   expected_revision。此步骤核对具体科学输入，与先前的名单确认作用不同。
4. 以确认响应中的新 input_revision 调用同一路径的 prepare；得到 awaiting_approval 计划。
5. 沿用 /approve 的 plan_id + plan_digest 精确批准，再读取原会话状态和产物接口。
6. 刷新或重启后，从 GET /api/sessions/{sid} 的 conditional_inputs.selections 恢复，
   按 cohort_binding.cohort_id 查找；结果仍属于明确的目标会话。

名单关联随 conditional proposal 一起进入现有摘要链；确认、准备和排队执行入口均重新核验。
源分析/回执被删除、失效或绑定变更时，proposal 为 stale、execution_available=false，
不能发起新的执行。旧名单决定和已产出结果仍保留，不因存在新版本而自动重选。
已开始的计算不承诺因另一个会话删除源文件而即时撤销；历史来源可用性与结果保留另行显示。

新增拒绝原因包括 cohort_not_confirmed、cohort_bundle_binding_mismatch、
cohort_duplicate_sample、cohort_comparison_mode_required、cohort_comparison_session_not_found；
另沿用 cohort_decision_changed、cohort_source_unavailable 及 conditional-inputs 既有错误。
重复关联/错误请求形状返回 422，跨账号或研究的目标会话返回 404，名单或关联冲突返回 409。
此接口不会替用户批准计划、采用结果或更新报告；目标会话沿用既有输入修订与产物访问规则。

本接线不包含公开 comparator 授权登记、自动提取 ProductEvidenceBundle、重算成本估计、
自动重算或真实实验室数据的科学验收。


## 10. 标准映射分析来源

标准映射的 `source_kind` 为 `atlas_mapping`；会话为 `session_execution`，自动 QC 见第 11 节。旧会话记录缺少
该私有字段时按 session_execution 读取；原登记请求、精确回执去重及结果确认行为保持不变。
映射由受控后台 ToolRun 完成，session_id、receipt_id、plan_id、declaration_revision 为 null，
另有 assessment_id 指向原 AtlasAssessment。不得为兼容接口创建虚构会话或回执 ID。

映射成功与不可变分析索引在同一个 objects.json 原子提交。分析列表合并这类索引和
原 analyses.json 中的会话与 QC 记录，按样本内 version 排序；所有来源共用连续登记序号。
Assessment.analysis_id 与 Analysis.id 相互绑定；同一成功尝试只登记一次。分析登记不改变
现有当前评估的选择规则，也不把登记顺序解释为用户采用。后台失败或中断不产生成功索引。

服务启动时对尚无索引的历史 done 映射重新校验，补登记一次，原 Assessment ID、坐标、
回执、结果文件及样本 revision 均保持不变；无效来源不补登记。GET 只读取，不回填记录。
索引补写失败不伪装成已完成迁移，服务启动返回错误供操作者处理。

映射 Analysis 固定实际输入矩阵及声明、ToolRun/工具/环境/测量定义、随机种子、参数摘要，
并增加 mapping_versions（原结果的版本字典）与 reference_manifest_sha256。这些是方法和
参考来源信息，不代表科学资格或新指标。完整路径、细胞 ID、原始矩阵与回执继续只保留在私有存储。

results 中映射的单一主要结果保留原 artifact ID、sha256，display_sha256 为 null；
artifact 为 null，assessment 为 `{id, url}`，url 是已有的 `/api/researches/{rid}/assessments/{id}`。
前端按 source_kind 打开既有映射详情，不能把它当作会话 Artifact 下载地址。会话结果的
artifact 行为不变。映射结果不可读取时 assessment 也为 null，availability 为 unavailable；
固定 ID、版本、摘要和历史元数据保留。每次读取重新核验绑定回执、结果、输入与样本归属。

这项接线不运行新映射、不做当前采用、参考替换、自动比较或分化链判定，也不增加生物学重复数。


## 11. 样本详情中的自动 QC

现有标准分析后台在 QC 回执写入完成后，独立登记 `source_kind=sample_qc` 的 Analysis；
前端在样本详情读取同一个 analysis 列表即可获得 QC，不需要关联或创建会话。
登记与映射并行衔接：QC 完成后即可读取，其后的映射失败不撤销 QC。
同一尝试只登记一次，重试的新尝试产生新的 Analysis；不会覆盖旧 QC 或替用户采用最新结果。
本接线沿用标准分析的启动资格与原始计数声明，不新增独立 QC 调度入口；缺少映射资源、
声明不足等导致标准分析未启动时，不承诺已自动运行 QC。

QC 的 session_id、receipt_id、plan_id、declaration_revision 均为 null；assessment_id 只标识
同一后台尝试，不能把它当作已成功的映射。tool.id 为 P0-01，tool.run_id、工具/环境版本、
输入矩阵及声明、参数摘要与 receipt_sha256 固定在登记时。
qc_summary 复用现有 QC 摘要投影，包含 schema_integrity（观察数/基因数与唯一性）、
count_metrics_state、metrics、assessment_states、selected_data_view、readiness_state
及 score_state/domain_score；缺失不补零，domain_score 仍为 null，不增加总分或科学判定。
其中 evidence_ref 沿用摘要的 E0 局部别名，不能作为跨分析身份；精确身份以 Analysis.id 与 snapshot_sha256 为准。

results[].artifact 使用既有 Artifact 形状（id/name/kind/media_type/tool_id/content_class/
access_state/url）。只发布 QC PNG 图、逐观察指标 Parquet 表和已去除内部路径的 QC profile JSON。
不发布原始矩阵、细胞选择掩码、日志、manifest、HTML 或 SVG。JSON 的 display_sha256 是
脱敏展示字节的哈希，sha256 仍固定原产物；不能用展示 JSON 作为计算输入。
文件接口每次重核研究所有权、输入、原回执及产物；其他账号包括管理员不能读取他人结果。
PNG/JSON 内联、Parquet 下载，均带 private/no-store 与 nosniff。

表格预览沿用既有 Parquet 预览合同：最多 100 行、24 列，存储体积上限 8 MiB，
返回 columns/rows/total_rows/truncated 等既有字段。超限为 413 artifact_preview_too_large，
非表格为 415 artifact_preview_unsupported，不能解码为 422 artifact_preview_unavailable。
未知结果 ID 为 404 analysis_result_not_found。结果本体每文件上限 128 MiB；超出读取范围按来源不可用处理。
结果 URL 已含受控 result_id，前端直接使用该 URL，不拼服务器路径或原 artifact ID。

回执、源输入或任一发布产物被改写/删除时，历史保留原 ID、版本与哈希，availability 变为
unavailable，qc_summary 和全部 artifact 为 null；直接请求文件/预览返回 409
analysis_source_unavailable。不会展示已无法核验的旧数字，也不影响另一次有效分析。

服务启动时遍历已有后台尝试，重新核验后补登记旧 QC，包括映射失败或中断的尝试；
不重跑分析，不依赖当前 reference 配置，不改原始输入/回执/结果与样本 revision。
缺失、失败或损坏的 QC 不补登记；已有历史保持原 ID，存储写入失败阻止启动并明确报错。
历史 QC 补登记的 version 表示登记先后，可能晚于原映射记录，不能解释为实际执行先后。
所有 GET 只读。工程回归不代替三套公开预设数据与 PC 样本详情的最终功能验收。


## 12. 自动双细胞检测与细胞周期供数

新样本的 mapping_input 可追加以下可选声明，随原始样本声明冻结；省略时保持旧请求兼容：

| 字段 | 含义 |
|---|---|
| capture_id | 已确认单一捕获批次的 ID |
| capture_id_column | 原 H5AD.obs 中真实捕获批次所在的列；与 capture_id 互斥 |
| gene_symbol_column | 原 H5AD.var 的基因符号列；未声明时沿用 var_names |

新写入的 source_family_id 同样遵循前端已有的逻辑 ID 约束：
首字符为 ASCII 字母或数字，其后只允许 ASCII 字母、数字、点、下划线、冒号和连字符，
最多 160 字符；不合规请求在冻结前返回 422。旧声明和历史记录的读取保持不变，不静默改写身份。

不从文件名、样本 ID 或列名猜测捕获批次，也不自动合并多个捕获批次。没有声明或数据不足时，
沿用工具原有 not_assessed；不是零双细胞。标准自动流程向 P0-01 传入 run_scrublet=true，
计算现有 Scrublet 候选，仍保留全部原始细胞；不启用 select_qc_eligible_cells。
已有历史回执不重写、不自动重算；旧样本不可借新增字段改写已冻结声明。

双细胞仍使用第 11 节同一 QC Analysis：
- qc_metrics.parquet 在检测成功时包含 scrublet_score 与 scrublet_class，索引 observation_id 为原始 obs 名称。
- scrublet_class 为 doublet / singlet / not_assessed_empty_counts；空计数的 score 为缺失。
- 脱敏 profile 的 doublet_assessment 提供 method、method_version、random_seed、n_assessed、
  n_predicted、fraction_predicted、n_not_assessed_empty_counts，以及 per_capture 的观察数、预测数、
  threshold、expected_doublet_rate、simulated_score_histogram。
- threshold 属于具体捕获批次；不能将某一批次阈值画作全样本统一阈值。
  当前逐细胞表不附带捕获批次列，批次汇总直接读取 per_capture。

细胞周期复用 P0-06 的 exploratory_process 模式、既有固定版本的 Seurat updated-2019 资源候选，
使用全部原始观察，不自动筛细胞或改变基因集成员。工具自身处理 raw_counts 的归一化和打分。
基因缺失或歧义时按既有方法合同保留缺失，不使用原文件里同名分数或 phase 代替新计算。

回执完成后独立登记 source_kind=sample_cell_cycle 的 Analysis，tool.id=P0-06，
session_id / receipt_id / plan_id / declaration_revision 仍为 null，assessment_id 绑定后台尝试。
cell_cycle_summary 包含 cell_cycle、n_observations、interpretation_scope、domain_score、
score_state、resource_ref / resource_version / resource_sha256。
cell_cycle 内有 assessment_state、phase_counts、s_g2m_fraction、mean_s_score、mean_g2m_score、
n_observations 和 reason_codes。phase_counts 是 G1/S/G2M 三类数量，比例分母为该视图全部观察。
G1 不是 G0；周期标签不是增殖率、质量剔除标准或领域评分，domain_score 保持 null。

results 只开放 exploratory_process_profile.display-redacted.json 与
exploratory_observation_scores.parquet，使用第 11 节相同的下载/预览/归属/哈希核验接口。
Parquet 用显式 observation_id 列与同一材料的 QC 索引关联，不凭数组位置或 day 关联。
绘图字段为 cycle_S_score、cycle_G2M_score、phase；表中既有程序分数保留原工具定义。
未评估时字段保持 null/缺失。前端只绘制实际有值的图，不需要新增不可用图或状态面板。
预览最多 100 行，不能据预览重算全样本分布；绘全量分布须读完整 Parquet。

周期计算在独立子进程中执行，预算 600 秒；普通异常、非零退出或该子进程超时后继续映射，
不撤销 QC。整体 worker 仍沿用 1800 秒上限，终止时清理本次进程组。
失败回执不登记为完成分析。
有效 partial 回执可登记，是否有周期数值由原工具 cell_cycle.assessment_state 决定。
服务启动只核验并补登记已完成周期回执，不补运行；来源损坏时保留历史 ID，
cell_cycle_summary 与 artifact 置 null，直接文件请求返回 409。


## 13. 样本自身 UMAP 与 Leiden 供数

声明原始计数的样本在 QC 成功后，自动调用 P0-02 的既有
EXPRESSION-exploration-v0.1 模式，独立登记 source_kind=sample_cell_atlas。
无需配置参考，不复用原文件 obsm、用户聚类或映射参考坐标；仅描述当前样本的表达邻域，
不赋予细胞身份、谱系、跨样本可比性或领域评分。原始数据与全部观察保持不变。

复用工具默认参数并在 request/Analysis 中完整保存：总量归一化 10,000 后自然 log1p；
Seurat-flavor HVG 2,000、PCA 最多 30、邻居最多 30、UMAP min_dist=0.5、
Leiden resolution=0.5（igraph、无向、2 次迭代），random_seed=0，threads=2。
HVG、PC 与邻居数按输入维度缩小；实际值在 preparation 中。
这些参数用于探索性布局，不是 QC 筛选阈值。UMAP 全量逐细胞表不受 max_points 图形采样影响。
新运行从 P0-02 0.8.2 起附带该表；已有结果不自动重算或改写。

Analysis 的 session_id / receipt_id / plan_id / declaration_revision 为 null，
assessment_id 绑定同一次后台尝试，random_seed、parameters、工具版本和哈希沿用原合同。
cell_atlas_summary 提供 n_observations、n_genes、composition、embedding_source、
grouping_source、preparation、parameters、random_seed、dependencies、domain_score、score_state。

基础 results 公开 expression_analysis.display-redacted.json 和 expression_cells.parquet；
0.8.3 新运行另附第 14 节的 Marker 表：

| Parquet 列 | 类型与语义 |
|---|---|
| observation_id | 原始 obs 名称；与同材料 QC/周期逐细胞关联的唯一键 |
| umap_1 / umap_2 | 当前样本自身表达邻域的两个坐标 |
| leiden | 字符串聚类标识，只在该次分析内有意义 |

成功表包含全部原始细胞，顺序与原 obs 一致。缺失不能补零；工具当前对空计数细胞、
过少细胞/基因或无有效变量的输入明确拒绝，不通过静默筛细胞制造完整图。
失败时保留 QC/周期与具体原因，不登记伪造的成功图谱。输入资源上限沿用 200,000 细胞、
60,000 基因及 300,000,000 个存储值；稀疏矩阵按 nnz，稠密矩阵按总元素数计算。

文件下载、预览、账号/样本归属和 409 沿用第 11 节。图谱同时绑定该次 QC 回执、
输入视图和原始材料；任一绑定或所用 QC 来源损坏时，历史 ID 保留，
cell_atlas_summary 和 artifact 置 null，文件请求返回 409，不展示旧数字。
启动仅核验补登记已完成回执，不补运行；GET 不写入、不重算。
计算在独立子进程中执行，预算 600 秒；超时/异常不阻断已完成 QC、周期或后续映射。
整体 worker 仍有 1800 秒上限。聚类标志基因与同次表达供数见第 14 节。


## 14. 聚类 Marker、点图与按需基因表达

P0-02 0.8.3 的新探索运行将同一次 Leiden、全基因表达与 Marker 排序保存在一起。
复用 sample_cell_atlas Analysis，不另起一套 UMAP、聚类或分析历史。旧运行不补造文件，
不改写回执，不由 GET 触发重算；升级须协调现有版本结果的替换，不假设旧版自动兼容。
cell_atlas_summary 新增 marker_state、marker_inference 与 gene_expression。
marker_state 不可用或表为空时不显示假 Marker；表达可单独存在。

### Marker 表

results 的 expression_markers.parquet 通过既有鉴权下载/预览接口读取。完整列：

| 列 | 定义 |
|---|---|
| leiden | 同次 expression_cells.parquet 中的字符串群 ID |
| rank | 群内从 1 开始的原工具排名 |
| gene | 精确输入 var_names 特征 ID；不自动做符号/别名合并 |
| score | 原 Scanpy Wilcoxon 带符号统计量 |
| log2_fold_change | Scanpy 从平均 log 表达近似的 log2 倍数变化 |
| pvalue / padj | 原细胞级检验及 BH 校正值；非有限值存为 null |
| fraction_in / fraction_rest | 本群/其余全部细胞中该基因表达大于零的比例 |

沿用原方法：完整输入基因上 group-versus-rest Wilcoxon，tie_correct=true、
use_raw=false、BH 校正，按带符号统计量降序取每群最多 marker_genes（默认 50）。
不另加显著性或效应阈值，不按绝对值重新排序；top-N 不是“显著 Marker”承诺。
群少或细胞不足沿用 insufficient_groups_or_cells 与空表。
同一表达矩阵既用于聚类又用于排序，pvalue/padj 只属于本样本探索性描述，
不能当作独立验证、跨方案差异表达、生物学重复或细胞身份资格证明。

### 基因检索与表达

可读表达产物的 Analysis 附 gene_catalog_url 与 gene_expression_url，前端直接使用。

- GET /api/researches/{rid}/analyses/{aid}/genes：query 默认为空，按大小写不敏感子串筛选；
  offset 默认 0，limit 默认 50、最大 200；按输入特征顺序返回。
  JSON 包含 analysis_id、material_sha256、query、offset、total、genes（精确 ID 字符串数组）。
- GET /api/researches/{rid}/analyses/{aid}/gene-expression?gene=SOX2&gene=TH：
  1–32 个 gene 参数，每个 1–200 字符，大小写敏感的精确 var_names 匹配，不猜别名。
  重复 ID 按首次出现去重；总返回值预算按请求项数×细胞数计算，上限 2,000,000。
  超出预算为 413 gene_expression_response_too_large，前端缩小一批基因数。

表达 JSON 顶层包含 analysis_id、material_sha256、scale=natural_log1p、
normalization、observation_ids、leiden、genes。两条细胞轴与完整坐标表逐项一致；
按 observation_id 连接，勿与参考树抽样、其他分析或另一份材料按位置拼接。
genes 每项形状如下（示例数字仅说明字段）：

```json
{
  "gene": "SOX2",
  "status": "available",
  "values": [0.0, 1.2],
  "groups": [
    {"leiden": "0", "n_cells": 2, "mean_log1p": 0.6, "fraction_expressing": 0.5}
  ]
}
```

未出现在输入基因轴的 ID 返回 status=not_found、values=null、groups=null。
存在但全零的基因仍为 available，值、平均值和比例均为零。前端不得混淆二者。
原始计数以每细胞全部输入基因计数总和为分母归一化至 10,000，再取自然 log1p；
不只用 HVG 或参考交集。mean_log1p 是群内所有细胞（包括零值）的算术平均，
不是 log1p(平均计数)，也不是只在表达细胞中求平均。
fraction_expressing 是值大于 0 的细胞数除以该群全部细胞数；n_cells 为此分母。
不在 HTTP 中做归一化、缩放、排名或推断。

工具私有 expression_genes.h5 保存完整 CSC 矩阵、原始观察/特征轴、Leiden 与群汇总；
对象版本 0.1.0，绑定输入 SHA-256，回执绑定整个文件 SHA-256。该文件不作为公开下载暴露。
每次读取验证研究所有权、Analysis 快照、输入、QC、原回执、坐标/Marker 文件，以及
该表达文件的哈希、轴与必要结构。读取文件上限 1 GiB，返回预算独立于存储上限。
不可访问研究/分析返回 404；没有此类表达产物返回 404 gene_expression_unavailable；
来源、绑定或表达文件损坏返回 409 analysis_source_unavailable。表达文件损坏不必使独立
可核验的坐标表失效，前端须处理表达请求本身的错误，不能沿用此前缓存数值。
正常响应包含 no-store 与 nosniff；所有 GET 只读。重启读取相同历史与原产物。
