# BRIDGE P0-11 Public-safe Export 任务卡

| 字段 | 内容 |
|---|---|
| Task ID | `TASK-PUBLIC-SAFE` |
| Package version | `0.3.0` |
| Object version | `0.1.0` |
| Scientific status | `candidate` |
| Domain score | `null` |

## 1. 职责

P0-11 为 Agent 的对外展示与导出提供最后一层确定性约束，包含两个互不混用
的输入模式：

1. `report_export`：将已获 P0-10 eligible receipt 的报告按冻结白名单
   重建为公开 JSON 候选，并用 candidate hash 绑定人工确认。
2. `artifact_audit`：在候选 JSON、Markdown、CSV 或 SVG 被展示前，
   核查格式、source-ref 语法、checksum、内容规则和冻结策略。

模块不上传文件，不重新判断生物学结论，也不授予发布权限。

## 2. report_export 合同

输入为四个 checksummed JSON 对象：`report_draft`、
`claim_verification_result`、`public_export_policy` 和
`public_export_request`。receipt 必须与报告 ref、内容 hash 和 audience
一致；policy 冻结字段、公开 alias、statement 与 target channel。

输出为 `PublicSafeReport`、`PublicExportManifest` 和
`PublicExportResult`。首次运行返回 `ready_for_confirmation`；只有
精确 candidate hash 的再次调用返回 `exported`，且仍然只是本地写出。

## 3. artifact_audit 合同

输入为两个 checksummed JSON 对象：

| Role | 内容 |
|---|---|
| `public_artifact_audit_policy` | 允许的格式、HTTPS host、JSON Schema、CSV 列和文件上限 |
| `public_artifact_manifest` | 1–20 个 regular file 的绝对路径、格式、媒体类型、source-ref 字符串与 SHA-256 |

支持的第一版格式与实际执行工具如下：

| 格式 | 实际执行 |
|---|---|
| JSON | 严格 JSON 与 packaged JSON Schema |
| Markdown | `markdown-it-py`、GFM 裸 URL 扫描、`regex`、小写 HTTPS 主机白名单与静态 IP/私有/特殊用途域名拒绝（不做 DNS 解析） |
| CSV | Python `csv.reader(strict=True)`、列白名单与公式注入规则 |
| SVG | `defusedxml`、元素/属性白名单、本地 fragment 与 URL 检查 |
| 全部 | 单一 hashlib 绑定的不可变 bytes、source-ref/checksum 绑定、路径/主机/凭据规则及只读副本上的 `file` |

输出一个不包含本地路径的 `PublicArtifactAuditResult`。内容违规属于完成的
审计：`execution_state=succeeded` 且 `audit_state=blocked`；合同、
checksum、文件状态或运行工具错误才使执行失败。

## 4. 主要拒答与阻断

- V1 envelope、模式混合、缺失/重复 role、Schema/版本/媒体类型错误；
- expression asset、MeasurementSpec、自由参数或 inline payload；
- receipt/policy/report 绑定失败或公开 alias、statement 未获允许；
- manifest policy 绑定失败、source-ref 语法错误、格式未获允许、JSON/CSV 规则缺失；
- 非 regular file、空文件、大小越界、checksum 变化或输出目录重叠；
- Markdown HTML/带 query、fragment、userinfo 或非默认端口的 URL、CSV 公式、SVG 主动内容或无效本地 fragment；
- 私有路径、主机、邮箱、凭据和内部标识 canary。

## 5. Agent 调用

```bash
bridge-tool describe P0-11
bridge-tool input-contract P0-11
bridge-tool validate --request /absolute/path/to/request.json
bridge-tool run --request /absolute/path/to/request.json
```

SDK 使用 `ToolRegistry.load_default().check_eligibility(request)` 和
`.run(request)`。Agent 只能依据 typed state 与 reason code 展示结果，
不能补写白名单、忽略 blocked finding、伪造确认或自动上传。

## 6. 边界

工程验证只证明已登记规则、解析器和命令在测试合同内可重复执行。source-ref
只做字符串语法检查，不验证 producer registry 或来源真实性。passed 不是完全
匿名证明；`exported` 不是网络上传、科学发布、临床判断或 GMP 放行。两个模式
均保持 `candidate`、`domain_score=null`、
`score_state=unavailable`。
