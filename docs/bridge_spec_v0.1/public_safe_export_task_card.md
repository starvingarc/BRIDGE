# BRIDGE P0-11 Public-safe Export 任务卡

| 字段 | 内容 |
|---|---|
| Task ID | `TASK-PUBLIC-SAFE` |
| Package version | `0.4.0` |
| Object version | `0.1.0` |
| Scientific status | `candidate` |
| Domain score | `null` |

## 1. 职责

P0-11 为本地公开候选提供两类确定性操作：

1. `report_export`：消费与报告精确绑定的 P0-10 receipt，按字段白名单重建
   JSON 候选，并记录调用方是否提供了与候选摘要完全一致的值。
2. `artifact_audit`：在候选 JSON、Markdown、CSV 或 SVG 被展示前，核查
   checksum、声明格式、文件结构、外部引用和已登记的敏感文本模式。

模块不上传文件、不重新判断生物学结论、不验证调用者身份，也不授予发布权限。

## 2. 报告候选合同

输入为四个 checksummed JSON 对象：`report_draft`、
`claim_verification_result`、`public_export_policy` 和
`public_export_request`。receipt 必须与报告 ref、内容 hash 和 audience
一致；policy 明确允许的 claim 字段、公开 alias、statement 和 target channel。

三份既有 v0.1 候选输出是 `PublicSafeReport`、
`PublicExportManifest` 和 `PublicExportResult`，其 Schema 与
`artifact_count=3` 保持不变。candidate digest 由公开报告 bytes、policy hash
和 target channel 共同派生。调用方提供相同值，只说明该值与摘要相符；不能证明
是谁提供、是否看过内容或是否批准发布。既有
`ready_for_confirmation`/`exported` 枚举仅为兼容保留，均只描述本地状态。

公开报告固定保留 public report/claim ID、public case alias、source-report 与
receipt hash、policy ref、target channel 和 created_at。hash 是可关联指纹，
不是匿名证明。白名单控制的六个 claim-content 字段为 `claim_type`、`text`、
`language`、`statement_refs`、`reported_evidence_state` 和
`comparison_mode`。

## 3. 候选文件核查合同

输入为两个 checksummed JSON 对象：

| Role | 内容 |
|---|---|
| `public_artifact_audit_policy` | 允许格式、Markdown HTTPS host、JSON Schema、CSV 列和文件上限 |
| `public_artifact_manifest` | 1–20 个 regular file 的路径、声明格式、媒体类型、source-ref 和 SHA-256 |

| 格式 | 实际执行 |
|---|---|
| JSON | 严格 JSON、解码后的 key/value 扫描与 packaged JSON Schema |
| Markdown | `markdown-it-py`、可见文字/属性解码扫描、链接发现与 HTTPS host 白名单；远程图片不允许 |
| CSV | `csv.reader(strict=True)`、header/cell 解码扫描、列白名单与公式保护 |
| SVG | `defusedxml`、文字/属性解码扫描、元素/属性白名单和本地 fragment；一律禁止外部资源 |
| 全部 | 同一不可变 byte snapshot、checksum/source-ref 绑定、已登记敏感模式和只读 `file` 检测 |

Markdown URL 白名单不适用于 SVG，在 SVG 的完整检查矩阵中必须显示为
`not_applicable`。内容被规则阻断时，工具执行可以完成并返回
`audit_state=blocked`；这不是产品通过/失败评分。

## 4. 本地审阅图

每个模式固定生成两张 typed 图，均带完整 TSV 和 SVG/PNG/PDF：

- 报告候选：当前 policy 下的 claim-content 字段投影；candidate digest 与本地
  文件状态；
- 文件核查：候选 artifact 状态；artifact × 已登记检查矩阵。

图和 typed data 只使用 `Claim 01`、`Artifact 01` 等固定显示编号，不包含
claim text、原始 artifact ID、source ref、路径、主机、运行时版本或输入 ID。
它们是本地审阅产物，不属于三份公开报告候选文件。

## 5. Agent 与 Web 调用边界

Agent 只能依据 typed state 与 reason code 展示结果，不能补写白名单、忽略
blocked finding 或自动上传。candidate digest 相符不验证提供者身份，也不等于
人工审核或发布批准。

`ToolRunV2` 是内部执行回执，其 request/artifact 记录带有部署路径。通用
`artifact_manifest.json` 标记为 `scope=internal_run_provenance`，包含环境与
输入 hash。Web 端不得把全部 `run.artifacts` 当作公开下载；只能展示明确选择的
公开候选或 P0-11 visualization artifact set。

`PublicSafeReport.claim.text` 仍是普通字符串。Web 必须按纯文本转义渲染，
不得直接作为 HTML 或 Markdown 注入。

## 6. 边界

已登记敏感模式覆盖确定的路径、主机、邮箱、凭据和内部 ID 形态，但不识别任意
姓名、电话号码或依赖语境的字段。public alias、claim text、statement ref 和
policy ref 的公开适当性仍由受控 policy 与 P0-10 receipt 负责。P0-11 不验证
policy 作者或 reviewer 身份。

“没有已登记规则阻断”只适用于实际运行的检查，不是全面去标识化、隐私证明、
科学发布、临床判断或 GMP 放行。`domain_score=null`，
`score_state=unavailable`。
