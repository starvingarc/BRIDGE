# BRIDGE P0-09 Evidence Compiler & Reconciler 任务卡

| 字段 | 内容 |
|---|---|
| Task ID | `TASK-EVIDENCE-COMPILER` |
| Tool ID / version | `P0-09` / `0.3.0` |
| Date | 2026-08-13 |
| Analysis unit | `metric x claim target x biological context x MeasurementSpec` |
| Runtime state | `implemented` |
| Scientific state | `candidate` |
| Result Schema | `bridge://schemas/evidence-compiler-run-result/v0.1` |

## 1. 生物学问题与边界

P0-09 读取已经完成且版本化的产品证据，回答：哪些原子记录支持或反对某项已登记 Claim，哪些记录共享同一 EvidenceFamily 因而不能当作独立重复，哪些必需证据仍然缺失，以及当前证据是否满足预注册的协调条件。

本模块不重新运行单细胞分析，不修改 MeasurementResult，不从文件名或路径推断关系，不选择“更好看”的方法，不生成 `domain_score`、总分、等级、产品 pass/fail、potency、安全性、疗效、GMP 放行或临床结论。它建立的是可执行的候选证据编译器，不是科学发布门禁。

## 2. 输入合同

共享运行入口为 `ToolRequestV2`。每个输入都是带绝对本地路径、精确 SHA-256、Schema URI、对象版本和 `application/json` media type 的 `StructuredInputRef`：

| role | 数量 | Schema | 含义 |
|---|---:|---|---|
| `compilation_bundle` | 1 | `evidence-compilation-bundle/v0.1` | Case/Comparison scope、候选项、缺失观察、对象目录和可选历史 |
| `evidence_sufficiency_profile` | Case 1–5；Comparison 2–25 | `evidence-sufficiency-profile/v0.1` 或 `v0.2` | P0-08 的产品、域、MeasurementSpec、sufficiency 和 provenance |
| `evidence_family_registry` | 1 | `evidence-family-registry/v0.1` | family 类型、channel role、独立性范围和审核状态 |
| `claim_registry` | 1 | `claim-registry/v0.1` | Claim、允许方向和 requirement template |
| `reconciliation_spec_registry` | 1 | `reconciliation-spec-registry/v0.1` | required/optional channel、独立 family 数和冲突规则 |
| `base_graph_manifest` / `base_evidence_record_set` / `base_evidence_requirement_set` | Case 有 base 时各 1，否则 0 | Case manifest / 两类 fact set | 三者与 `AppendGraphRef` 的 input ID 逐一绑定；Comparison 禁止 |
| `source_case_graph_manifest` / `source_case_evidence_record_set` | Comparison 每个 Case 各 1 | Case manifest / EvidenceRecordSet | 与每个 `BoundCaseGraphRef` input ID 严格双射；Case 禁止 |

`assets=[]`、顶层 `measurement_spec_ref=null`、`parameters={}`。`random_seed` 仅为共享 envelope 兼容而保留，算法不使用随机数。输入期间发生任何字节变化都使整次运行失败。

Case bundle 只拥有一个 ProductCase 及其记录历史；有历史时必须同时提供内容寻址的 base manifest、record set 和 requirement set，且三类事实与 bundle 历史完全一致。Comparison bundle 只引用至少两个 Case graph，不允许 base/prior/owned records，不复制案例值、区间或私有属性。每个 source manifest 会在原始目录中通过七查询层的 `open()` 完整验证五个 authoritative artifacts，再核对 raw manifest SHA、record-set SHA、确定性 graph ID、graph version 和 ProductCase。所有 Claim 映射、ProductCase、MeasurementSpec、EvidenceFamily 和 P0-08 profile 绑定必须显式声明，不能由 Agent 推断。

## 3. 原子 EvidenceRecord 与追加式修正

一个 EvidenceRecord 只表达一个：

```text
product case x sample/preparation x domain x metric x claim x context x MeasurementSpec
```

逻辑键不包含工具、路径、request ID、时间和值。稳定 Evidence ID 由该逻辑键计算；内容哈希覆盖数值、单位、分子/分母、区间、state、tier、applicability、family、ToolRun、合同/reference/prior/artifact 版本和 provenance。

版本规则固定：

1. 新逻辑键只能用 `create` 产生版本 1。
2. 同逻辑键、同内容返回 `unchanged`，不增加节点或关系。
3. 同逻辑键内容变化必须显式 `supersede` 或 `invalidate`，且 predecessor 必须是最新版本。
4. `supersede` 追加 active 的 N+1，旧版本在当前图中标记为 superseded，但旧 JSON 不修改。
5. `invalidate` 追加 invalidated 的 N+1，不产生 supports/contradicts 关系，也不进入当前协调。
6. 跨 logical key、错误 predecessor、版本间隙、冲突候选或覆盖历史均逐条拒绝。

规范化使用版本化的 `bridge-canonical-json/v0.1`：严格 UTF-8 JSON、拒绝重复 key/NaN/Infinity，按 Pydantic/JSON Schema 验证，明确集合语义的列表才排序，解释顺序、原因优先级和时间序列保留原序。它不做 Unicode normalization，也不声称 RFC 8785/JCS number rendering。

## 4. 缺失、状态和科学等级

- `missing` 通过 EvidenceRequirement 与 `missing_for` 表达，绝不生成 `value=0`。
- `negative`、`missing`、`unknown`、`unavailable`、`alert` 不互换。
- `shadow`、`exploratory`、not-applicable 和 inactive 记录保留审计可见性，但不进入 formal reconciliation。
- 上游 ToolRun 为 `failed`、`skipped` 或 `not_implemented` 时拒绝编译；`partial` 中已经验证的单条记录可以进入。
- shadow/exploratory candidate 与 P0-08 v0.1 profile 对 ProductCase、MeasurementSpec、MeasurementResult 按裸 ID 匹配；与 v0.2 profile 对三者均按完整 `object_id` + `object_version` 匹配。
- 两版 profile 都可用于 shadow/exploratory 编译。由于 `deduplicated_evidence_family_ids` 仍不含 family 版本，均不能证明完整 formal family binding；所有 formal candidate/external ref 继续以 `sufficiency_profile_version_binding_unavailable` 保守拒绝。

三个公开 record 数组都严格要求 object 元素；非 object、extra field 或其他公开 Schema 失败在注册的 public registry 路径属于顶层失败。模块内部 direct-adapter seam 可将 object-shaped parse failure 保留到逐条 sanitized rejection，但不放宽导出的公开 Schema。Schema 合法但 provenance、版本/上下文绑定、source fact 或语义非法的 sibling candidate/missing/external item 才进入 `rejected_records.json`，其余合法项可发布 `partial` graph；被拒输出仅含稳定 ID/index/digest/reason，不回显原值。完全相同的同源 external declaration 按集合语义在身份计算前幂等去重；同一 Evidence ref 只要 content/source/Claim/profile/family/relation/lifecycle 等声明不同，就保留冲突证据并逐条 `duplicate_logical_key_conflict` 拒绝。候选的 numerator、denominator 与 interval 只接受有限 JSON number；numeric string 和 bool 不发生静默强转。顶层 bundle/registry/history/Schema/checksum 或 unsafe publication reference 错误则整次失败且不发布任何 artifact。publication guard 是路径、URI、环境变量、credential-like assignment/token、禁用结论 key 和 public-ref 形状的有界合同，不承诺通用 secret scanning。P0-08 合同内固定的 `domain_score=null` 仅作为上游 provenance 保存，不被 P0-09 填值或解释。

## 5. EvidenceFamily 去重与确定性协调

EvidenceFamily 由版本化 registry 预注册，不由 Agent 按当前结果临时聚类。共享数据、算法、reference、prior、knowledge 或 aggregation 的多条记录保留全部 provenance，但在一个 channel 中只贡献一个 family direction。同一 `independence_scope`，或被 `known_dependencies` 单向/双向/传递连接的 families，归为一个对称闭包 component，只能计一次独立证据；component 内支持/反对不一致时 unresolved，不投票。confirmation 同样受此约束。

协调顺序：

1. 确认 Claim 与 ReconciliationSpec 已冻结且类型一致。
2. 确认绑定的 P0-08 profile 为 `sufficient`。
3. 排除非 formal、inactive、not-applicable、非法 ToolRun、unreviewed family 和不允许的 EvidenceState。
4. 先按 family 去重和 dependency/scope component 合并，再检查每个 required role 的最少独立 component 数。
5. 按冻结规则输出 `stable`、`consensus_supported`、`integration_sensitive` 或 `unstable`。

若合同未冻结则 eligibility 为 `not_assessed`；若 sufficiency、required role 或 formal evidence 不足则为 `insufficient_evidence`。这两种情况的 state/direction 均为 null。只有 `eligible` 才能生成协调状态。数值大小、工具数和 record 数不会改变方向。

## 6. 图事实、存储与重建

JSON 与 Parquet 是正式事实源：

- `evidence_records.json`
- `evidence_requirements.json`
- `reconciliation_records.json`
- `graph_nodes.parquet`
- `graph_edges.parquet`
- Case 或 Comparison graph manifest

节点/边 Parquet 使用固定列、稳定 ID、确定性排序、Zstandard 压缩和显式 content hash。打开时必须重算每个 node ID、每条 edge 的 properties hash/content hash/edge ID，并对可重算的 owned properties 核 content hash；external ref 只核其确定性身份与 source binding，不要求复制源端 properties。NetworkX `MultiDiGraph` 只负责进程内约束、重建和查询验证，包括端点类型、悬空边、自环、重复边、revision cycle、root scope 和弱连通性。它不是持久化层。

Cytoscape elements 是 bounded data projection，不是科学图表声明；完整导出最多 500 nodes/1,000 edges，并报告截断。科学 JSON、Parquet properties 和 rejected-record 输出都不携带本地路径、credential-like string 或原始被拒 payload。

LadybugDB 在 v0.1 中为 `shadow/deferred` adapter 候选：不安装、不参与发布门禁、不是事实源。Neo4j、任意 Cypher、远端图服务和写 API 均不在当前实现中。

## 7. 只读查询接口

部署层先按授权 graph ID/version 解析并验证 manifest，再构造 `EvidenceGraphQueries`。Agent/Web 只获得七个参数化方法：

- `get_claim_evidence`
- `trace_evidence_provenance`
- `get_conflicting_evidence`
- `get_missing_requirements`
- `get_evidence_family_members`
- `get_case_evidence_subgraph`
- `compare_evidence_paths`

查询参数执行严格类型、enum 和 bool 校验；错误统一返回 typed `query_parameter_invalid`，不抛裸异常或扩大 inactive 范围。限制 `limit<=200`、`max_depth<=6`、`max_nodes<=500`，固定 traversal 和可见字段，按 node/edge ID 排序；只有确有 reachable node/edge 被省略时才返回 `truncated=true`。`get_missing_requirements` 每个 requirement ID 只把最高版本视为当前状态。manifest 只接受固定 basename，拒绝绝对/遍历路径和 symlink，并校验 checksum、Parquet row count、graph count、连通性以及三类 JSON fact 与 owned Parquet node 的一致性；`object_counts` 省略零项且必须与实际 node-type Counter 精确相等，不能只核总数。公开 `open` 以单一 untrusted wrapper 覆盖 manifest JSON/model、artifact 读取/checksum、Parquet row/model、三类 JSON fact model 与 Case/Comparison projection；任意 nested 异常统一收敛为无 `__cause__` 的精确 `manifest_integrity_failed`，不得让 Pydantic/PyArrow 等内部错误、原始 payload、canary 或 artifact path 进入公开 traceback。调用者不能提供路径、predicate、edge type、Cypher、写命令或远端 backend。Comparison 的 external EvidenceRecord 必须在 content-addressed source record set 中唯一存在，匹配 content hash、source Claim、ProductCase、tier、applicability、ToolRun 和由完整 create/supersede/invalidate 链推导的 effective lifecycle；其 provenance 在 source Case 边界停止并返回 `source_case_graph_required`。

## 8. 不可变 artifact bundle

每次成功/partial 运行写入 `<output_dir>/<run_id>/`，共 24 个文件：原有三类规范 JSON、两个 Parquet、一个 graph manifest、Cytoscape elements、rejected list 和 typed run result，加上一份 typed visualization data、三份完整 TSV、三图各 SVG/PNG/PDF、一个 visualization artifact set，以及覆盖其余 23 个文件的 artifact manifest。Graph manifest 继续只校验五个 authoritative graph facts；解释性图形不成为新的 EvidenceRecord。三个 authoritative set ID 都由 `source_input_hash[:16]` 确定；graph ID 由 Case ProductCase 或 Comparison root 的完整版本化引用确定。查询入口与写后 roundtrip 都从已稳定读取的 bytes 解析 Parquet，并重新推导 record tier/lifecycle、Evidence/Requirement/Reconciliation 身份及 Case 全部语义边。

三图分别呈现当前可用的已协调结论、这些结论内按 dependency/scope 合并后的 EvidenceFamily 关系，以及当前 Requirement 与 compilation exclusion。没有证据且没有显式 Requirement 的 registry Claim 不生成图中行；缺行不代表零或 missing。family/record 数仅为审计计数，不代表独立证据；missing requirement 不显示为零；Claim 级 reason 不反向分配给单条 excluded evidence。静态图超过容量时保留完整 TSV，并返回完整表格回退，不做 top-N 截断。

全部产物在同一 staging 中生成、校验并原子发布；任一文件漂移都会阻止既有 bundle 复用。typed 图形数据不符合包内合同时返回 `visualization_data_invalid`；图形渲染或 figure-registry 合同失败时返回 `visualization_render_failed`；两者都不发布 artifact。运行结果仍为 `measurements=[]`、`visualizations=[]`，三份 portable visualization contract 存在 package-owned artifact set 中，不修改共享 ToolRun 合同。

## 9. 方法与环境状态

| method | 作用 | 当前边界 |
|---|---|---|
| `METHOD-INTERNAL-DETERMINISTIC-ENGINE-25908A` | 原子记录、版本、requirement 和协调 | candidate；不计算生物学 |
| `METHOD-INTERNAL-READ-ONLY-API` | 七个 bounded 查询 | 无 Cypher/写权限 |
| `METHOD-COLUMNAR-STORAGE` | PyArrow/Parquet 事实表 | 固定 Schema；版本内确定性 |
| `METHOD-GRAPH-LIBRARY` | NetworkX 图约束和重建 | 不承担正式持久化 |

四个方法均保持 `formal_eligible=false`。`ENV-EVIDENCE-v0.2` 显式声明 PyArrow、NetworkX 和 Matplotlib 等运行依赖；环境可调用不代表方法或具体案例得到科学确认。

## 10. 当前科学边界

P0-09 的 `implemented/candidate` 状态只表示合同内的证据编译、协调、查询和解释性图形路径可调用。它不能证明任何 Claim 为真、任何域证据充分、任何 ScoreContract 已冻结、任何产品更优，或任何输出已经获得科学发布资格。
