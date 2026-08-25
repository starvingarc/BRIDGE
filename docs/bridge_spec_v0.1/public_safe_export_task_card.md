# BRIDGE P0-11 Public-safe Export 任务卡

| 字段 | 内容 |
|---|---|
| Task ID | `TASK-PUBLIC-SAFE` |
| Package version | `0.2.0` |
| Object version | `0.1.0` |
| Scientific status | `candidate` |
| Domain score | `null` |

## 1. 职责

P0-11 将一份已获得 P0-10 eligible receipt 的结构化报告，按冻结策略重新
构造为最小公开 JSON 候选。它回答“哪些已验证报告字段可以按当前公开策略
输出”，不回答报告中的生物学结论是否真实、产品是否安全有效或是否应发布。

第一版仅支持 JSON 和本地不可变写出。不支持 CSV、Markdown、ZIP、PDF、
HTML、图表、媒体、网络上传或通用匿名化。

## 2. 精确输入

`ToolRequestV2.object_inputs` 必须恰好包含四个 checksummed
`application/json` 对象：

| Role | Schema | 必需绑定 |
|---|---|---|
| `report_draft` | `bridge://schemas/report-draft/v0.1` | `ReportDraft.object_version=0.1.0` |
| `claim_verification_result` | `bridge://schemas/claim-verification-result/v0.1` | receipt 的 report ref/hash/audience 与 ReportDraft 完全一致，且 `public_export_eligibility=eligible` |
| `public_export_policy` | `bridge://schemas/public-export-policy-spec/v0.1` | active；冻结目标通道、claim field allowlist、公开 case alias 和 statement allowlist |
| `public_export_request` | `bridge://schemas/public-export-request/v0.1` | report ref、policy ref、target channel，以及可选 `confirmation_hash` |

每个引用必须提供绝对 regular-file path、SHA-256、Schema URI、对象版本和
媒体类型。输入表达矩阵、MeasurementSpec、自由参数、额外 role 或 inline
payload 均不属于该合同。

## 3. 白名单重建

模块从零创建 `PublicSafeReport`，不复制源报告后再删字段。固定公开骨架为：

- 新的 hash-derived `public_report_id` 和 `public_claim_id`；
- checksummed source report 和 P0-10 receipt 的 SHA-256；
- public export policy ref 和目标通道；
- policy 批准的公开 case alias；
- claim type、文本和语言；
- 仅在字段白名单中出现时输出 statement refs、evidence state 和 comparison mode。

源 claim/evidence/ProductCase/sample/preparation 标识、value bindings、
Evidence Graph refs、renderer metadata 和其他未列字段不会进入公开对象。
缺失 alias 或 statement 未获批准时整次运行失败，不做静默改写。

## 4. 确定性泄漏阻断

白名单重建后，对 report、manifest 和 result 执行固定扫描。以下任一命中
均返回 `public_payload_leak_detected` 且不发布 artifact：

- 私有数据卷、Unix/macOS user-home 或 Windows user absolute path；
- 已知私有服务器 hostname；
- password、secret、API key、access/refresh token、Bearer 或常见 token；
- 邮箱；
- 内部 `evidence:`、`product-case:`、`sample:`、
  `preparation:` 引用。

扫描器是白名单后的第二道确定性防线，不证明语义上的完全匿名或科学正确。

## 5. 输出与状态

成功运行在一个原子发布目录中产生三个 checksummed JSON artifact：

1. `public_safe_report.json`；
2. `public_export_manifest.json`；
3. `public_export_result.json`。

candidate hash 绑定 public report bytes、冻结 policy checksum 和目标通道。
无确认时结果为 `ready_for_confirmation`。调用者将该 candidate hash 写入
第二份 `PublicExportRequest.confirmation_hash` 后再次调用；精确匹配返回
`exported`，但只表示本地不可变包已确认，仍不上传。错误确认返回
`confirmation_hash_mismatch` 且无输出。

`ToolRunV2.measurements=[]`、`visualizations=[]`，
`PublicExportResult.domain_score=null`、`score_state=unavailable`。

## 6. 主要拒答

- V1 envelope、缺失/重复 role、Schema/版本/媒体类型/checksum 错误；
- receipt 与 report ref/hash/audience 不一致或不具备公开资格；
- policy inactive，请求 report/policy ref 不匹配，目标通道未获允许；
- 缺少公开 alias 或 statement 不在 allowlist；
- 泄漏扫描命中或 confirmation hash 不匹配；
- 输入运行中变化、输出路径不安全、已有 run bundle 内容不同。

## 7. Agent 调用

```bash
bridge-tool validate --request /absolute/path/to/p0_11_request.json
bridge-tool run --request /absolute/path/to/p0_11_request.json
```

SDK 使用 `ToolRegistry.load_default().check_eligibility(request)` 和
`.run(request)`。Agent 可以展示候选哈希并请求确认，不能添加白名单字段、
伪造确认、修改结果或自动上传。

## 8. 方法与边界

- `METHOD-BRIDGE-ALGORITHM-2AFBC8`：白名单投影和包编排。
- `METHOD-BRIDGE-RULE-ENGINE`：固定路径、凭据、邮箱和内部引用扫描。

两者均为 deterministic candidate。它们不产生 P0 科学域测量，不验证
P0-10 claim 的生物学真实性，也不构成临床、安全、效力、GMP release 或
公共发布许可。
