# 内网多用户测试服务实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 用户自行注册并隔离会话，管理员只读查看测试内容，用户可使用默认或个人模型 API。
**Architecture:** 在现有 HTTP、会话存储和任务配置快照之间加入身份与所有权边界；保持科研执行和结果合同。反向代理提供内网 HTTPS，应用及控制连接保留回环监听。
**Tech Stack:** Python 3.12、FastAPI、SQLite、Argon2id、httpx、React、TypeScript、现有 pytest／Vitest。
**Spec:** 本文件的“已批准设计”部分。设计已获批准；实施步骤已批准，采用当前会话连续实施和最终独立审查。

## Global Constraints

- 服务器工作树内实施和验证；真实配置、会话、密钥及部署地址留在私有运行目录。
- 本地和内网统一使用账号登录；旧口令登录及模式开关已退役。所有 Web 实例使用初始化的账号存储，保留既有账号与所有权。
- Python >=3.12,<3.13；Node >=22.12.0；复用现有前端与 Web 合同，不改变科研审批和测量语义。
- 管理员跨账号读取只读且留审计；所有用户请求在后端校验权限。
- 已排队及运行任务保持捕获的模型配置；实时科学资源与分享授权仍可撤销。
- 自定义提供方失败不自动回退；密钥不进入 API 返回、浏览器存储、日志或仓库。
- 当前运行服务不随代码提交切换。交付分别记录代码、权限验证、浏览器、存储恢复和实际内网访问。

## Review Focus

1. 同一浏览器切换账号后，旧轮询或缓存不能恢复上一账号内容（任务 5）。
2. 删除部分失败留下的隐藏目录仍需所有者校验（任务 2）。
3. 模型地址在 DNS 解析后改变，或通过重定向访问受限地址（任务 3）。
4. 全局默认密钥不能被个人配置的空密钥保留逻辑继承（任务 3）。
5. 首次初始化重试不得更换管理员，备份恢复中断不能开放部分存储（任务 6）。

## 实施任务

每个任务先运行新回归确认失败原因，再实现并运行目标检查；通过后提交这一完整边界。命令均在服务器工作树中执行，python 指向现有 Python 3.12 环境。

### Task 1: 账号与可撤销登录

**Files:** 新建 src/bridge/web/accounts.py、src/bridge/web/auth_http.py、tests/test_web_accounts.py；修改 app.py、http.py、runtime.py、pyproject.toml（Web 依赖）、tests/web_support.py。
**Interfaces:** 不可变 Principal(id: str, username: str, role: Literal["user","admin"], must_change_password: bool)。AccountStore.register(username: str, password: str, notice_version: str) -> Principal；authenticate(username: str, password: str) -> Principal；issue_login(user_id: str) -> str；resolve_login(cookie: str) -> Principal | None；revoke_login(cookie: str) -> None；disable(user_id: str) -> None；reset_password(user_id: str) -> str。
**HTTP:** GET /api/auth/config 返回登录模式和测试告知；POST /api/register 与 /api/login；GET /api/me；POST /api/logout、/api/me/password。强制改密账号只能改密或退出。多用户 Cookie 身份与现有模式分离。

- [x] 编写 test_registration_is_unique_under_concurrency、test_registration_cannot_assign_admin、test_login_revoke_reset_disable，断言并发规范化用户名只有一个成功、角色字段被拒绝、重置及停用后的旧 Cookie 返回 401。断言缺少告知确认无法注册，哈希及日志中不出现原密码。
- [x] 运行 python -m pytest -q tests/test_web_accounts.py，确认失败指向缺失能力。
- [x] 实现私有 SQLite 事务、Argon2id、随机凭据哈希、登录撤销和限速；按数据库和附属文件权限检查持久化。统一用户名规范化规则与密码长度限制，前后端共用公开配置约束。
- [x] 重跑新增文件及 tests/test_web_runtime.py、tests/test_web_service.py 中现有认证边界；单操作者回归通过后提交。

### Task 2: 会话所有权与管理员只读审计

**Files:** 新建 src/bridge/web/access.py、src/bridge/web/admin_http.py、tests/test_web_ownership.py、tests/test_web_admin.py；修改 service.py、sessions.py、http.py。
**Interfaces:** SessionAccess.authorize(principal: Principal, sid: str, *, admin_read: bool = False) -> None；visible_sessions(principal: Principal) -> list[dict]；AuditStore.record(actor_id: str, target_user_id: str, sid: str, action: str, outcome: str) -> None。Service.create(*, owner_id: str | None = None)；多用户创建时 owner_id 必须来自 Principal。隐藏删除记录保留 owner_id。
**HTTP:** 所有现有会话路由先执行所有权检查；错误投影同样受控。独立 /api/admin/users 及 /api/admin/sessions 读入口，账号管理使用明确管理员写入口。管理员不能通过普通会话路由修改他人会话。管理员读取复用现有投影及下载校验，不新增越权诊断能力。

- [x] 编写参数化 test_cross_user_route_matrix_denied，枚举注册的会话端点与附件路径，断言 B 请求 A 资源既不能改变持久化状态也不返回内容或存在性；包含非法请求引起的错误投影。
- [x] 编写 test_delete_retry_preserves_owner、test_admin_reads_are_audited_and_cannot_mutate、test_unowned_records_are_hidden，覆盖隐藏目录、失败读取的审计及未迁移会话。
- [x] 运行 python -m pytest -q tests/test_web_ownership.py tests/test_web_admin.py，确认预期失败。
- [x] 实现集中访问策略、会话所有权持久化、管理员允许的只读端点及受控审计。审核全部会话路径，包括表格、图、protocol 下载与历史产物确认，不能用宽泛“所有 GET 均允许”绕过资源规则。
- [x] 运行上述测试及 tests/test_web_session_management.py、tests/test_web_artifacts.py、tests/test_web_service.py；通过后提交。

### Task 3: 个人模型与安全出口

**Files:** 新建 src/bridge/web/model_transport.py、tests/test_web_personal_models.py、tests/test_web_model_transport.py；修改 model_settings.py、provider.py、intake_autofill.py、protocol_formalization.py、runtime.py、http.py。
**Interfaces:** ModelConfiguration.view_for(user_id: str) -> dict；save_for(user_id: str, value: ModelSettingsInput) -> dict；select_for(user_id: str, source: Literal["default","personal"]) -> dict；delete_for(user_id: str) -> None；snapshot_for(user_id: str) -> Settings。model_transport.provider_client(settings: Settings, *, timeout: float) -> ContextManager[httpx.Client] 统一出口。
**HTTP:** /api/me/model-settings 的读取、保存、删除、模式选择和测试；实例默认写入仅管理员可用。个人密钥只可从同一用户、相同 endpoint 的既有个人配置保留，不能继承默认密钥。

- [x] 编写 test_personal_settings_do_not_change_default_or_other_users、test_blank_personal_key_cannot_inherit_default、test_personal_failure_never_falls_back；断言 A、B、默认配置独立且响应无密钥。
- [x] 编写 test_private_targets_redirects_and_dns_rebinding_blocked、test_operator_allowed_endpoint_is_pinned，覆盖 IPv4／IPv6、混合 DNS 答案、连接时地址变化、Host／TLS 服务名与证书校验；使用假 DNS／网络后端，不发送真实凭据。
- [x] 运行 python -m pytest -q tests/test_web_personal_models.py tests/test_web_model_transport.py，确认预期失败。
- [x] 实现个人配置存储、显式选择、有限响应探测及统一传输。采用受控 httpx/httpcore 连接层将 DNS 校验和实际连接绑定，保留 TLS 主机名验证，关闭环境代理及重定向；管理员允许列表只通过服务器配置设置。
- [x] 将所有提供方调用迁入统一传输，保留现有请求／响应限制和 provider 协议。运行新测试及 tests/test_web_model_settings.py、tests/test_web_provider.py、tests/test_web_intake_autofill.py、tests/test_web_protocol_formalization.py；通过后提交。

### Task 4: 任务配置绑定与有限资源配额

**Files:** 新建 src/bridge/web/quotas.py、tests/test_web_user_execution.py；修改 service.py、execution.py、model_settings.py、sessions.py、http.py、runtime.py。
**Interfaces:** ModelConfiguration.task_context(owner_id: str | None = None) -> ContextManager[None] 在调用时捕获快照；WebExecution.schedule 由 state.owner_id 选择上下文；UserQuotas.reserve_task(user_id: str) -> ContextManager[None]；reserve_upload(user_id: str, declared_bytes: int) -> ContextManager[None]。配额预留覆盖排队和上传并发，完成或失败释放。

- [x] 编写 test_two_users_keep_submitted_model_snapshots，使用 Event 控制顺序：A 选个人模型、B 用默认，提交后更改两种配置，断言旧任务仍分别用原配置、新任务用新配置。
- [x] 编写 test_snapshot_keeps_live_sharing_revocation、test_upload_and_task_quota_atomic_release，断言撤销分享即时生效，失败／取消后配额可回收，多账号不能超过全局上限。
- [x] 运行 python -m pytest -q tests/test_web_user_execution.py，确认预期失败。
- [x] 在现有任务捕获位置接入 owner_id；所有异步模型用途复用相同上下文。配置有限的每用户上传累计占用、任务排队与全局并发；启动时检查配额有效性，已有文件计入占用，原有单文件限制继续有效。
- [x] 运行新测试及 tests/test_web_model_settings.py、tests/test_web_large_upload.py、tests/test_web_session_management.py；通过后提交。

### Task 5: 自注册、模型选择与管理界面

**Files:** 新建 frontend/src/components/AccountSettings.tsx、AdminSessions.tsx、frontend/tests/multi-user.test.tsx；修改 LoginScreen.tsx、ModelSettings.tsx、Sidebar.tsx、App.tsx、api.ts、types.ts、styles.css。
**Interfaces:** api.me() -> PrincipalView；api.register({username,password,notice_version})；api.personalModelSettings()；api.selectModel(source)；api.adminUsers()；api.adminSessions(userId)；api.adminSession(id)。私有凭据只存在输入框临时状态，提交后清空。
**Interaction:** 登录页仅提供账号登录／注册，未知服务认证模式拒绝继续。个人模型页明确“服务默认／我的模型”。管理员有独立只读详情视图，不复用会触发会话变更的交互组件；保留现有科研显示格式。

- [x] 编写 tests 覆盖注册告知、错误提示、默认／个人切换、停用与强制改密、管理员只读详情。
- [x] 编写 delayed poll + logout + login B 回归，断言迟到的 A 响应不能显示，selected-session 本地键按账号隔离，401 清理账号内存、会话和 pending 请求。
- [x] 运行 npm --prefix frontend test -- tests/multi-user.test.tsx，确认预期失败。
- [x] 实现上述页面与 API 接线，复用现有组件样式及加载／失败处理；管理员可下载已获授权材料及结果，但不能确认历史产物、执行分析或发消息。
- [x] 运行 npm --prefix frontend test 及 npm --prefix frontend run build；用服务端浏览器和合成账号完成桌面／手机流程后提交。

### Task 6: 内网启动、空白存储、恢复及集成验收

**Files:** src/bridge/web/account_admin.py、tests/test_web_account_storage.py；修改 launcher.py、runtime.py、tests/test_web_startup.py 及 Web／隐私／开发／发行文档。
**Interfaces:** 离线初始化管理员；不复制旧会话。新存储具有身份标记，旧令牌与单操作者模式不能打开它。受存储独占锁保护的备份／恢复保留账号、配置、内容与所有权。
**Revision:** 旧测试会话已获准直接清理，取消迁移实现；新服务空白启动。

- [x] 验证初始化重试、管理员身份、未归属数据拒绝、恢复中断保护、一致快照及旧令牌拒绝。
- [x] 验证 public origin、代理头、回环控制和 --test 隔离；实现有限配额配置。
- [x] 同步稳定文档，完成受影响 Web 回归、schema、仓库及前端检查。
- [x] 完整变更集中独立审查，修复权限、凭据、并发与恢复问题，按授权范围交付。
- [x] 核对旧测试实例进程与存储归属，清理其旧会话；新服务使用独立空白目录。
- [x] 落实内网 HTTPS 地址，通过另一台客户端验证注册、会话隔离及证书校验；VPN 断开不可达，重连恢复。
- [ ] 设备使用者按私有交付说明完成浏览器证书信任；不自动修改客户端系统信任。

---
## 已批准设计

状态：功能已实现，集中审查问题已修复；实际 HTTPS、跨客户端隔离、重启及 VPN 断开／重连验收通过。设备证书信任由使用者完成。
源码基线：PR #88 合并后的主线 d5ea7a91。
本文件是该工作项唯一设计与后续实施计划入口。

## 目标与用户流程

实验室／校园网用户通过同一地址自行注册，每人拥有独立会话、附件和结果。管理员可查看测试会话。模型默认使用服务方配置的 API，用户可选择自己的 API。旧测试会话按已批准清理范围删除，新服务从空白存储开始。

- 用户名与密码注册，无须邀请码；用户名规范化并唯一约束。注册只能创建普通用户，管理员身份由服务器初始化。
- 注册时明确展示并记录确认：“这是内部测试服务，管理员可以查看会话、上传材料及生成结果，用于排查问题和改进服务。”登录页持续显示测试提示。
- 用户只能访问自己的会话，沿用归档、恢复和删除；同一账号可跨浏览器访问历史。
- 管理员在独立“测试管理”入口按用户筛选，只读查看对话、材料、结果和运行状态，并显示所有者。查看不代用户发消息、批准分析或发起模型请求。
- 管理员可停用账号、撤销登录和管理默认模型；停用不删除数据，已启动任务按原批准范围完成，新操作被拒绝。
- 初版不依赖邮箱。忘记密码由管理员重置为一次性密码，下次登录先修改；重置撤销已有登录。

保留现有科学工作流和审批边界。本期不引入组织协作、SSO、计费或公网注册。

## 默认模型与个人模型

| 场景 | 行为 |
|---|---|
| 新注册用户 | 默认使用服务方模型，无须填写 API 密钥 |
| 保存个人配置 | 保存自己的地址、模型、协议和密钥，不改变全局默认 |
| 选择个人模型 | 后续提交的任务使用个人配置，并显示实际提供方和模型 |
| 切回默认模型 | 后续任务使用服务默认；个人配置可保留或主动删除 |
| 请求失败 | 明确提示，不自动切换提供方或消耗另一方额度 |
| 任务提交后修改配置 | 排队及运行任务保持捕获的配置，新任务采用新配置 |
| 个人连接测试 | 只发送固定测试文字，不发送会话或科研材料 |

个人模型与服务默认模型分开存储。配置 API 仅返回“密钥已配置”等状态，不返回密钥原值；管理员页面也不显示个人密钥。凭据保存在服务器私有存储，沿用 owner-only 权限，不写入浏览器存储、日志、错误消息或版本库。服务器运维人员仍处于信任边界内，这不等于对操作系统管理员的密钥隔离。

任务提交时依据执行者账号解析模型并捕获不可变配置。材料提取、protocol 处理、科学草稿和解释审阅均使用该任务配置；保留现有用途限制、数据清理和工具审批。运行记录绑定提供方、模型和配置版本，不记录密钥。管理员只读查看他人内容不触发提供方调用。

普通用户自定义 API 支持经出口校验的外部 HTTPS 地址；阻止回环、链路本地、云 metadata 及未授权内网目标。管理员可通过服务器配置允许指定的内网模型端点。校验覆盖 DNS 解析与实际连接，默认关闭重定向，不能只检查表单字符串。管理员已有默认 API 在部署核对后保留。

## 身份、授权与存储

账户、角色和登录状态使用私有 SQLite 数据库，事务保护注册唯一性及撤销。密码使用 Argon2id 哈希；登录使用随机、不透明的 HttpOnly Cookie，服务器保存凭据哈希、账号、有效期和撤销状态。

业务会话沿用现有目录与状态格式，增加服务器维护的 owner_id，请求不能自行指定或修改所有者。删除失败后的重试记录也保留所有者。

HTTP 层产生可信用户身份，会话访问入口统一校验所有权。列表、消息、轮询、上传、下载、预览、图、归档、删除及错误响应均执行相同规则。普通用户跨账号访问得到一致的不可见结果，不泄露存在性、标题或状态。

管理员跨账号读取使用明确的只读入口，复用既有结果投影和产物校验。审计记录管理员、目标用户／会话、时间、操作及结果，不复制会话正文、附件或密钥。管理员角色不绕过科研产物可见性及开发诊断环境开关。

模块职责：
- HTTP：认证、Origin／CSRF 和接口权限。
- 账户模块：身份、角色、凭据与登录撤销。
- 会话存储：所有者、持久化及删除生命周期。
- 模型配置模块：默认／个人配置解析与任务快照。
- 执行模块：接收已授权会话及模型快照，保留后台任务结束保护。
- 前端：注册、账号设置、个人模型选择及管理员只读入口。

共享默认 API 费用和服务器资源由服务方承担。注册／登录有限速率，用户上传占用、排队数量与并发执行有有限配额。具体数值由部署配置按服务器容量确定，超限返回明确说明；全局资源上限不能被多账号并发绕过。

## 内网入口、空白存储与恢复

服务器反向代理提供固定内网 HTTPS 入口，应用继续监听回环地址。外部 origin 显式配置，Host／Origin 严格匹配；转发头仅信任配置的回环代理。地址、证书和允许网段保存在私有部署配置。

旧测试会话已获准删除，不迁移到多用户存储。核对当前测试实例与存储归属后清理其会话；保留其他实例和服务默认模型配置。多用户实例使用独立空白存储，离线初始化管理员；旧共享令牌不能登录。

账号、会话、模型配置按同一离线快照备份和恢复。恢复先停止写入并移出保留当前数据，只恢复到快照记录的原绝对路径，以保持不可变回执；账号绑定格式为 2.0.0，旧程序不能直接打开新存储。恢复中断不能公开部分数据。应用删除与备份、审计和共享 workflow journal 的保留边界见隐私文档。

部署前落实内网入口、允许网段、证书信任、管理员和有限配额；另一台内网客户端完成实际访问验证。

## 验收条件

1. A、B 两个普通用户可自行注册登录，用户名并发冲突正确处理，注册请求不能赋予管理员角色。
2. A 的会话、材料和结果对 B 不可见；直接替换每类接口的 ID 均不能读取或修改，覆盖错误响应、附件和删除失败重试。
3. 管理员可只读查看 A／B 内容且有访问审计；该入口不能代发消息、批准或执行任务。
4. 新用户使用默认模型；A 选个人模型只影响 A，B 仍用默认。连接测试无科研内容，失败无隐式回退，排队任务保持原配置。合成假提供方足以完成工程验证。
5. 密钥不出现在 API、浏览器存储、管理页面、日志和错误中。自定义 API 无法访问受限目标，显式获准内网端点可工作。
6. 注册提示、模型切换、归档恢复删除和管理员查看完成桌面与手机浏览器检查；账号停用、重置及撤销阻止后续请求。
7. 重启后账号、所有权和模型设置保持；新实例无旧会话；合成数据验证一致备份和中断恢复保护。
8. 未登录、跨用户、错误 Origin 和伪造代理头不能绕过权限。用户配额及全局并发边界得到验证，另一台内网客户端可注册并使用独立会话。
9. 同步更新 Web 配置、隐私、开发和发行范围文档；多用户工程验收不等于科研验证或公网发行。

## 下一阶段

剩余部署验收见任务 6；实际入口、证书与账号凭据保存在私有部署目录。
