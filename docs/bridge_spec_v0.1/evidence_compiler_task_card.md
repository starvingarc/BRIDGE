# BRIDGE P0-09 Evidence Compiler & Reconciler 任务卡

| 字段 | 内容 |
|---|---|
| Task ID | `TASK-EVIDENCE-COMPILER` |
| Tool ID / version | `P0-09` / `0.2.0` |
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
| `evidence_sufficiency_profile` | Case 1–5；Comparison 2–25 | `evidence-sufficiency-profile/v0.1` | P0-08 的产品、域、MeasurementSpec、sufficiency 和 provenance |
| `evidence_family_registry` | 1 | `evidence-family-registry/v0.1` | family 类型、channel role、独立性范围和审核状态 |
| `claim_registry` | 1 | `claim-registry/v0.1` | Claim、允许方向和 requirement template |
| `reconciliation_spec_registry` | 1 | `reconciliation-spec-registry/v0.1` | required/optional channel、独立 family 数和冲突规则 |

`assets=[]`、顶层 `measurement_spec_ref=null`、`parameters={}`。`random_seed` 仅为共享 envelope 兼容而保留，算法不使用随机数。输入期间发生任何字节变化都使整次运行失败。

Case bundle 只拥有一个 ProductCase 及其记录历史；Comparison bundle 只引用至少两个 Case graph，不复制案例值、区间或私有属性。所有 Claim 映射、ProductCase、MeasurementSpec、EvidenceFamily 和 P0-08 profile 绑定必须显式声明，不能由 Agent 推断。

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
- formal candidate 必须绑定 sufficient P0-08 profile、冻结 Claim/Reconciliation 合同、冻结 registry 和 reviewed EvidenceFamily；不满足时拒绝，不静默降级。

一个格式、绑定或发布引用错误的 sibling candidate/missing/external item 只进入 `rejected_records.json`，其余合法项可发布 `partial` graph；被拒原始值不会回显。顶层 bundle/registry/history/Schema/checksum 或 unsafe publication reference 错误则整次失败且不发布任何 artifact。publication guard 是路径、URI、环境变量、credential-like assignment/token 和 public-ref 形状的有界合同，不承诺通用 secret scanning。

## 5. EvidenceFamily 去重与确定性协调

EvidenceFamily 由版本化 registry 预注册，不由 Agent 按当前结果临时聚类。共享数据、算法、reference、prior、knowledge 或 aggregation 的多条记录保留全部 provenance，但在一个 channel 中只贡献一个 family direction。family 内支持/反对不一致时，该 family unresolved，不投票。

协调顺序：

1. 确认 Claim 与 ReconciliationSpec 已冻结且类型一致。
2. 确认绑定的 P0-08 profile 为 `sufficient`。
3. 排除非 formal、inactive、not-applicable、非法 ToolRun、unreviewed family 和不允许的 EvidenceState。
4. 先按 family 去重，再检查每个 required role 的最少独立 family 数。
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

节点/边 Parquet 使用固定列、稳定 ID、确定性排序、Zstandard 压缩和显式 content hash。NetworkX `MultiDiGraph` 只负责进程内约束、重建和查询验证，包括端点类型、悬空边、自环、重复边、revision cycle、root scope 和弱连通性。它不是持久化层。

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

查询限制 `limit<=200`、`max_depth<=6`、`max_nodes<=500`，固定 traversal 和可见字段，按 node/edge ID 排序；只有确有 reachable node/edge 被省略时才返回 `truncated=true`。manifest 只接受固定 basename，拒绝绝对/遍历路径和 symlink，并校验 checksum、Parquet row count、graph count。调用者不能提供路径、predicate、edge type、Cypher、写命令或远端 backend。Comparison 的 external EvidenceRecord 必须与 source manifest SHA/graph/version/ProductCase 一致，其 provenance 在 source Case 边界停止并返回 `source_case_graph_required`。

## 8. 不可变 artifact bundle

每次成功/partial 运行写入 `<output_dir>/<run_id>/`，共十个文件：三类规范 JSON、两个 Parquet、一个 graph manifest、Cytoscape elements、rejected list、typed run result 和 artifact manifest。Graph manifest 校验五个 authoritative facts；artifact manifest 校验前九个文件而不自哈希。

写入流程为新 staging 目录、写后校验、输入复核、原子 rename。artifact manifest 记录前九个文件的 checksum、media type 与可用 byte size；结构化输入则记录 semantic SHA，raw SHA 只保留在本次 ToolRun request。相同语义的集合顺序变体可复用 byte-identical run bundle；存在漂移时拒绝覆盖。运行结果 `measurements=[]`、`visualizations=[]`。

## 9. 方法与环境状态

| method | 作用 | 当前边界 |
|---|---|---|
| `METHOD-INTERNAL-DETERMINISTIC-ENGINE-25908A` | 原子记录、版本、requirement 和协调 | candidate；不计算生物学 |
| `METHOD-INTERNAL-READ-ONLY-API` | 七个 bounded 查询 | 无 Cypher/写权限 |
| `METHOD-COLUMNAR-STORAGE` | PyArrow/Parquet 事实表 | 固定 Schema；版本内确定性 |
| `METHOD-GRAPH-LIBRARY` | NetworkX 图约束和重建 | 不承担正式持久化 |

四个方法均保持 `formal_eligible=false`。`ENV-EVIDENCE-v0.1` 仍为 `proposed`；本地测试不能将环境或科学状态晋升为 frozen/formal。依赖和 wheel 打包由公共整合 PR 统一声明。

## 10. 验证要求与当前声明

模块测试覆盖：公开模型与 Draft 2020-12 Schema、严格 JSON、checksum、model-aware 集合归一化、确定性 run/record/graph/artifact identity、append-only evidence/requirement 修正、missing-versus-zero、boolean numeric 拒绝、四类 unsafe publication surface 与不回显、partial rejection、formal gate、family 去重、Comparison source-manifest binding、图端点与 revision cycle、JSON→Parquet→NetworkX round trip、manifest filename/symlink/checksum/row-count/size、重复运行复用、七个只读查询及其精确 cap/注入 canary。

当前 fixture 全部为合成数据，不代表真实产品、真实样本、临床结果或科学验证。P0-09 完成只表示候选编译与协调路径可执行；它不能证明任何 Claim 为真、任何域证据充分、任何 ScoreContract 已冻结、任何产品更优，或任何输出可公开/科学发布。
