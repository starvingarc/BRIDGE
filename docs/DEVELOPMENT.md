# 合作者开发入口

此公开源码快照提供可移植开发入口。Issue、分支和 PR 流程见 [CONTRIBUTING](../CONTRIBUTING.md)，Agent 执行规则与科学护栏见 [AGENTS](../AGENTS.md)。本页维护环境与检查入口；当前能力与未完成验收见[活动计划](../plans/README.md)。

## 在独立电脑准备环境

需要满足 [pyproject.toml](../pyproject.toml) 中 `requires-python` 的 Python、满足 [frontend/package.json](../frontend/package.json) 中 `engines.node` 的 Node.js，以及本人的 GitHub 访问权限。
Node 版本要求由该字段维护；npm 默认报告不兼容警告，不将其作为强制运行时闸门。不要共享学校账号、VPN、账号密码或模型密钥。

```bash
git clone https://github.com/starvingarc/BRIDGE.git
cd BRIDGE
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[qc,test,freeze,evidence,process,target-regional,developmental,web]"
npm --prefix frontend ci
npm --prefix frontend run build
python -m bridge.toolkit.cli list --json
python -m bridge.toolkit.cli knowledge validate
```

这是软件开发环境，不自动安装完整科学 reference 或所有外部方法环境。专门方法依赖沿用[环境说明](../environments/README.md)，不要以安装成功作为分析模块全部可用的证明。

## 启动与样例

按 [Web 配置说明](web-preview.md#start-a-private-instance) 初始化独立账号存储，配置模型服务及前端构建路径，使用统一的 `bridge-web --config /绝对路径/web.env` 入口。
`--test` 在独立 acceptance 端口和存储启动，`status`／`stop` 管理同一实例；
源码入口 `./start.sh` 和 `python -m bridge.web` 使用相同检查。配置和上传文件放在仓库外。本地与[内网多用户测试](web-preview.md#internal-multi-user-testing)统一使用账号密码登录；每个环境首次启动前初始化自己的管理员与存储，不应直接开放公网。

仓库提供[协作测试数据及合成 reference](../examples/demo/README.md)，可直接上传产品 H5AD，并通过现有资源配置切换到配套参考；另有[接口请求示例](../examples/README.md)。该数据包不依赖学校内网，尚不代表完整五域或 Web 端到端验收通过。其他方法的资源与输入仍需按合同配置，不能伪造结果。公开数据转换与完整资源就绪检查仍是[路线图阶段 2](ROADMAP.md)的工作。模型服务地址、模型名和密钥均由协作者自行配置，不复制服务器的运行配置。

前端开发与测试见 [frontend](../frontend/README.md)。内部参考和已有私有会话不是普通开发的前置条件，但缺少它们会使相应科学分析不可运行。

## 检查与内部验收

开发时按影响选择检查，不为文档改动重复完整真实分析，也不以单个测试替代需要的跨模块验收：

| 改动 | 本地必要检查 |
|---|---|
| 文档、Issue／PR 模板 | 链接、表单 YAML 和必填项、仓库规则、差异格式；无需重跑科学分析 |
| 后端、存储、执行或接口 | 受影响模块测试；跨模块时加对应集成测试；Schema 语义变化核对版本与兼容 |
| 前端 | 受影响交互测试与构建；视觉变化检查实际页面 |
| 工具、reference、测量或知识 | 对应合同／来源检查和定向测试；需要的真实数据科学验收另行记录 |
| 包装或安装接口 | 构建并核对安装后的 wheel，不只检查源码目录 |

以下 Python 命令使用项目的 **Python 3.12** 解释器，包括无科学依赖的 `--static` 检查；先用 `python --version` 确认，避免误用旧版系统解释器。

典型命令入口如下，具体测试文件按改动选择；CI 定义以 [工作流](../.github/workflows/ci.yml) 为准：

```bash
python -m pytest -q tests/test_registry.py
python scripts/check_repository.py --static
python scripts/check_repository.py
git diff --check
git diff --cached --check
npm --prefix frontend test
```

上面不是完整科学验收。模型、reference、测量或比较语义变更由内部人员检出准确提交，在受控环境运行相应真实数据验证。PR 只记录获准共享的提交、资源身份、验证范围、结果和未验证项，不上传原始回执、样本身份、模型日志或截图。

`--static` 检查目录、链接与锚点、私有路径、源码禁用项和下述文档合同，不导入科学工具；无参数时仍执行完整工具合同与适配器检查，两者不能互称。

公开仓库的 [CI 配置](../.github/workflows/ci.yml) 保留 `repository-gates`：构建与安装、完整后端测试、前端测试与构建、知识与图注册表、仓库规则、文档一致性、Schema 逐字节检查及差异格式。它不连接受控服务器，也不运行依赖私有数据的科学验收。

必要的功能测试由开发者在本地或现有受控服务器执行，按上表选择受影响模块和集成链路。共享合同、依赖或跨模块行为变化应扩大相关回归；发行前或无法界定影响范围时运行完整测试。没有新改动、新失败或具体未解决风险时，复用已通过的相关结果，不因推送或改文档重复科学计算。需要完整验证时使用现有入口：

```bash
python -m pytest -q --durations=20
npm --prefix frontend test
npm --prefix frontend run build
python scripts/check_repository.py
```

PR 记录被验证的准确提交、工作区是否干净、环境／依赖版本、实际命令、结果、未覆盖范围及原因。复用较早提交的结果时，注明来源提交及之后的改动为何不影响该验证；不要把源码测试写成已验证安装包，也不要在记录里暴露服务器路径或私有数据。

云端检查因额度、付款或平台故障无法启动时，在相同提交运行工作流里的轻量检查并记录结果，维护者据此和必要功能测试审查，无需为合并购买云端额度。静态检查成功只表示该检查范围通过；真实代码失败必须修复，未运行的云端任务仍标记未运行。这是协作约定，不表示已配置 GitHub 分支保护；合并与部署授权仍按 [CONTRIBUTING](../CONTRIBUTING.md) 分开处理。

## Schema 维护

Python 模型是接口定义的维护源。`scripts/export_schemas.py` 为新版本生成可复用已有定义的标准 `$ref`，避免在仓库重复展开；历史快照保持不变。读取接口 `load_schema`（以及 `ToolRegistry.resolve_schema`）只解析包内已登记的引用，并输出可独立校验的完整 Schema，不联网取定义。新增版本复用关系维护在同一导出脚本的 `SCHEMA_LINKS` 中，不能手改生成文件或用压缩成单行掩盖重复。

Schema 一致性检查只读，在内存中复用同一生成逻辑，逐字节比对生成物，并双向核对 `SCHEMA_REFS`、模型 ID／文件名和目录文件。失败时列出具体文件；缺文件、多文件、未注册或没有生成源均失败。`scripts/requirements-schemas.txt` 固定 Pydantic 生成版本，仅安装合同检查依赖，无需科学运行环境：

```bash
python -m pip install -r scripts/requirements-schemas.txt
PYTHONPATH=src python scripts/export_schemas.py --check
# 仅在有意更新 Python 合同后重新生成；审查版本和 diff，再运行 --check。
PYTHONPATH=src python scripts/export_schemas.py
```

`--output-dir <directory>` 可指定临时导出／检查目录。`--check` 不创建目录、不修复文件；生成命令只写模型产生的文件，不删除多余文件。历史 `developmental_compatibility_result.schema.json` 与 `target_regional_evidence_result.schema.json` 已无当前模型生成源，其原始字节在导出脚本 `HISTORICAL_SNAPSHOTS` 中显式固定 SHA-256，仍须注册、存在且校验值匹配，不属于跳过检查。其余已注册版本全部重新生成比较，不能通过新增豁免掩盖漂移。

为支持轻量生成，科学库在实际运算时导入，工具包的顶层 `adapter` 导出按需加载；注册的 `package.adapter:adapter` 运行入口保持不变。修改导入边界时，除 schema 检查外还应运行受影响的实际运算测试。

## 独立模块协作

低耦合协作规则以 [AGENTS](../AGENTS.md#实现原则) 为准。先确定模块输入、输出、错误语义和可写范围，再分配实现任务；接口变更由整合者协调，避免多人反复改写共享中心文件。

`main` 已整合 Web 装配入口、HTTP、会话存储、产物访问和任务执行的职责拆分，以及研究工作区导航；不需要选择额外候选分支。旧 Inputs/Controls 等领域对象仍依赖协调器，不能据此声称整个项目已全面解耦。工程检查与科学验收分开；部署仍需单独授权。

## Web module ownership

Service assembles collaborators and coordinates user decisions. SessionStore
owns persistence, ArtifactStore owns artifact access, and WebExecution owns
workers. QcResults owns verified QC receipts, selected-view assets and catalog
registration; callers use this module instead of coordinator-private helpers.
The remaining scientific input and assessment modules consume these results.

EvidenceSources owns assessment receipt selection, pinned graph provenance
recovery and canonical output lookup. Interpretation and report preparation use
this same selection policy: only succeeded/partial, non-invalidated receipts are
eligible; pinned outputs bind receipt file, hash and producer tool, while graph
producers also bind execution name, version and canonical content hash. Inputs
supplies verified-read adapters; the selector receives no Service and does not
cache verification across operations. Existing Inputs/ReportInputs entry points
remain compatible. Persistent schemas and scientific measurements are unchanged.

For source-selection changes, run tests/test_evidence_sources.py first. It covers
selection failures and legacy identity collisions without uploads, workers or
model requests. Then run the affected evidence/report integration tests; reuse
unchanged real-data acceptance evidence. Other module coupling remains outside
this extraction.

Shared Web test fixtures live in tests/web_support.py, outside collected test
modules. Preserve contract and failure coverage when moving tests; formatting or
fixture extraction alone is not a reason to add new tests.


### Research workspace design

These decisions extend the existing module boundaries. Scientific contracts and
report access rules remain defined in the [Web guide](web-preview.md); the
[frontend guide](../frontend/README.md#assessment-reading-flow) owns the reading
flow.

| Knowledge | Owner | Consumer interface |
|---|---|---|
| Canonical object, dependency and producer integrity | Inputs | Existing verified input operations; `verification(state)` groups a synchronous read |
| Current versus historical artifact access | ArtifactStore | Public artifact classification and authenticated artifact route |
| Current report edition and safe display | ResultsPane | Registered report artifacts and report navigation callback |
| Observation, interpretation and missingness presentation | AssessmentPanel | Server-owned assessment projection and navigation callbacks |
| Finite next action and citation vocabulary | Provider adapter | Existing structured action schema and supplied option IDs |

Producer verification considered two approaches: persistent memoization keyed by
file metadata, and reuse confined to one synchronous operation. The latter keeps
mutation detection across requests and execution phases without introducing a
cache invalidation protocol. Inputs hides the reuse mechanism; Service groups
one public projection in `verification(state)`. This scope accepts one in-memory
session state, must not await or start workers, and must not mutate artifact
files. Its exit releases all shared checks, including on failure. Each ordinary
input operation establishes its own scope automatically.

Report display considered rebuilding a report from public observations versus
rendering the registered HTML artifact. Rendering the artifact preserves the
same version and bytes as offline download and leaves scientific report logic
with its existing owner. ResultsPane groups editions using the registered input
revision, graph version and snapshot hash; an empty sandbox isolates the HTML.
No additional backend route or public scientific schema is introduced.

When report binding or access semantics change, update ArtifactStore's public
contract, ResultsPane and their access tests together. When assessment states
change, update the server projection and the frontend labels together; visual
states must never promote missing evidence or reference context into a qualified
conclusion. The existing coordinator dependency in Inputs remains design debt;
this change does not introduce a new service facade or attempt its unrelated
extraction.

## 文档一致性

使用项目的 Python 3.12 运行 `python -S scripts/check_repository.py --static`；单独定位文档问题可运行
`python -S scripts/check_documentation.py`。两者仅读取文本、Python AST 和已跟踪文件，
不执行被检查的模块、不导入项目或科学依赖。CI 还运行
`python -S -m unittest discover -s tests -p 'test_documentation_consistency.py'`，
用故意修改声明的回归确认检查确实能拒绝漂移。

检查覆盖包版本、Tool Card 与 spec 的版本和主要结果 Schema、请求／profile 钉版，
以及科学任务卡中的当前主要结果行或对应 Tool Card 引用。v0.1 spec 未单独声明结果
Schema 时卡片明确写出该缺失；模式专用、嵌套结果和历史验证记录不冒充主要结果。
输入角色合同须覆盖 Tool Card 角色表与适配器的角色映射、显式角色／Schema 条件中
接受的 Schema；固定版本由已登记 JSON Schema 的 object_version 约束核对。
新增声明形式不在静态读取范围时，应扩展读取器与回归，不能通过执行适配器求值。

索引检查要求 docs Markdown 从 docs/README.md 经本地链接可达，scripts 中每个 Python
入口在脚本索引登记，AGENTS 归属表完整或明确非穷尽。Markdown 本地链接检查目标、
标题锚点和显式 a id/name。新增的文档／锚点读取器忽略代码围栏；
仓库入口仍保留原有链接存在性检查，包括其对代码围栏中 Markdown 链接的检查。

易漂移的数值与版本优先链接维护源（代码常量、spec、Tool Card、语言版本配置或隐私
文档），不要在正文复制。确需就地展示的当前数值，在
[断言映射](../scripts/documentation_assertions.json) 增加唯一 id、document、
带命名捕获组的 pattern、预期出现次数 count，以及 groups 中对应的 source。
source 支持 Python 常量／类默认字段、TOML 字段路径、图组件声明计数；单位转换用
scale 明确指定。映射存来源而不再存一份期望数值。当前覆盖包版本、模型超时和输出预算、
对象数量／字节限额、文件默认值／上限和图组件分类数量。同步增加文档或来源被改坏、
断言被删除时必须失败的测试；历史数值只在其明确的历史上下文保留。
