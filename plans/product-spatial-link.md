# Product UMAP and Spatial Reference Linking Implementation Plan

Engineering delivery: the development follow-up. Remaining scientific gates are listed below; completed implementation details are maintained in the linked specification and validation record.

**Goal:** 在现有产品分析结果页，以产品 UMAP 联动真实空间参考点图，并将三维胚胎缩为右上角解剖参照。

**Architecture:** 复用 QC、P0-02、不可变产物与鉴权路径；新增确定性的同版本观测连接和版本化类型对应。Web 展示适配层发布有来源绑定的联动清单与按捕获单元读取的坐标，React 容器协调两张 Canvas 图和可选的三维小视图。任何可视化读取均不运行科学方法。

**Tech Stack:** Python 3.12、现有 Pydantic/FastAPI/pandas/H5AD 读取依赖；React 19、TypeScript、Canvas、现有 Three.js；pytest、Vitest、应用内浏览器。Node.js 22.12+。不引入新的分析或绘图库。

**Spec:** [已确认规格](../docs/superpowers/specs/2026-10-02-product-spatial-link-design.md)

## Current status

Engineering implementation and controlled internal-product display checks are complete.
The linked view preserves complete product/reference denominators, reviewed display
correspondences, stable pinned selection and separate missing states. The main
application and standalone anatomy preview build independently; private assets are
excluded from Git and from the main application bundle.

[Display verification](../docs/validation/product-spatial-link.md) owns the test,
browser and internal-display evidence. Integration status is tracked in Issue #22
and its PR; deployment is separate.

## Remaining gates

- Human biological review of the versioned display correspondences and annotation applicability.
- Independently qualified product evidence; exploratory display does not establish cell identity or product qualification.
- Validated tissue-image transforms, anatomical orientation and registration before any spatial-position or three-dimensional localization claim.
- Explicit release/deployment authorization and deployment-owned reference configuration.

## Global Constraints

- 左侧约 45%：产品 UMAP；右侧约 55%：真实空间坐标图为主；右上角约 180–220 像素：半透明三维胚胎及候选切面。
- 只有明确且已审阅的对应可触发高亮；候选注释自身的科学状态保持候选。
- 所有产品比例、空间计数使用完整数据，产品与空间的分母分别标明。
- 悬停群不改变切面位置，也不在模型内生成假定的细胞云。
- 不把带坐标轴、红点和边框的历史叠加 PNG 当作纯 H&E 底图。
- 保留上传、事实确认、范围授权与 QC；调用已注册高层工具，不另拼分析命令。
- 所有源码与测试仅在现有服务器开发目录进行。受控数据、资源配置和真实回执不进入 Git；集成授权不包含数据发布或生产部署。
- 解剖预览与联动主应用按独立入口审查；提交只包含本任务代码、测试与维护文档，不包含构建产物。

## Review Focus

1. 两个有效产物来自不同 QC 子集或观测顺序：明确拒绝连接，不能依赖行数相同。（任务 1）
2. 同一聚类包含已匹配、未匹配、拒绝注释：只高亮可追溯的类型，保留未匹配组成。（任务 1、4）
3. 多张组织切片共用一个捕获坐标系：保留原图布局，不按上下位置制造层序。（任务 2、4）
4. 切换版本后旧请求迟到或映射表更新：旧响应不能覆盖新画面。（任务 3、4）
5. 数十万空间点、仅少量细胞的稀有类型、3D 加载失败：交互仍可用，计数不改变，二维视图继续工作。（任务 4、5）

## 文件与接口总览

- 新建 `src/bridge/web/spatial_link_data.py`：内部展示 DTO、观测连接、类型集合与完整计数；不定义科学 MeasurementResult。
- 新建 `src/bridge/web/spatial_reference.py`：固定配置的参考清单、版本/hash 检查、只读坐标与注释投影。
- 新建 `src/bridge/web/spatial_context.py`：组合已验证产品产物与参考，返回白名单展示数据。
- 修改 `research_context.py`：将现有 `_display_source` 提取为窄公共 `resolve_display_source`，原调用保留同样检查；不将整个协调器交给底层连接函数。
- 修改 `runtime.py`、`__main__.py`、`service.py`、`http.py`：单个可选参考配置入口、依赖装配和鉴权展示路由。
- 修改 `inputs.py`、`scientific_inputs.py`：复用实际可运行的候选注释/表达探索选择；只在既定授权范围内补齐联动所需产物。
- 新建 `frontend/src/components/spatial/{types.ts,LinkedCellExplorer.tsx,SpatialScatter.tsx,MiniAnatomy.tsx,linked-cell-explorer.css}`。
- 修改 `ExpressionUMAP.tsx`：导出可控散点视图，保留独立图模式；`ResearchFigures.tsx` 接入联动入口。
- 修改 `frontend/src/anatomy/viewer.ts` 与原预览入口：几何查看器接受显式模型 URL，私有 GLB 不进入主应用静态包；保留原预览行为。
- 各任务测试采用小型合成 fixture；真实样本的逐细胞结果只在受控环境验收。

## Task 1: 连接同版本产品坐标、注释与类型对应

**Files:** 新建 `spatial_link_data.py`、`tests/test_spatial_link_data.py`。

**Interfaces:** `ProductLinkInput` 持有完整逐观测 UMAP 表、抽样点 record_id、候选 assignments、input_sha256、data_view_ref、ordered_observation_sha256、两份 producer/receipt 绑定；`TypeCrosswalk` 持有两侧词表版本及 `product_state_id, spatial_type_id, relation, review_state, basis` 条目，其中 relation 为 `same_type|broader_type`，review_state 为 `reviewed|pending|rejected`。`build_product_link(source: ProductLinkInput, crosswalk: TypeCrosswalk) -> ProductLinkData` 输出展示点、每个类型/聚类的完整组成、可匹配类型集合、未匹配计数及来源引用。

- [x] 添加失败测试：`test_rejects_wrong_view_or_order` 验证不同 hash、DataView、顺序 checksum 以及重复/缺失 observation_id 均拒绝；`test_resolves_plot_index_through_full_table` 验证 record_id='2' 通过完整表第三行连接，而不是连接名称为 '2' 的细胞。
- [x] 添加 `test_mixed_group_preserves_unmatched`：组内两细胞 A、一个未知，A 对应空间 X；结果 matched_types=['X']、group_total=3、unmatched_count=1，A 比例为 2/3。`test_unreviewed_or_stale_crosswalk_does_not_match` 验证词表版本不一致拒绝，未审阅行不触发高亮；较宽类型关系保留标识。
- [x] 运行 `python -m pytest -q tests/test_spatial_link_data.py`，先确认缺实现导致失败，再实现上述模型和纯函数。保持 `assignment_state` 与 `qualified_assignment` 原值；同一空间类型由多条来源映射时去重，不叠加计数。
- [x] 重跑至 PASS，审查观测连接与分母测试；按允许的 Git 身份配置提交本任务差异。

## Task 2: 只读空间参考与可审阅对应表

**Files:** 新建 `spatial_reference.py`、`tests/test_spatial_reference.py`；修改 `runtime.py`、`__main__.py`、`docs/web-preview.md`、资源注册表中的相关使用说明。

**Interfaces:** `Settings.spatial_reference_manifest_path: Path | None`，环境变量 `BRIDGE_WEB_SPATIAL_REFERENCE_MANIFEST`，默认 None。`load_spatial_reference(manifest_path: Path) -> SpatialReference`；`read_spatial_section(reference: SpatialReference, section_id: str) -> SpatialSectionData`。私有清单固定数据文件/hash、二维坐标字段、类型字段、capture/section 字段、版本化 crosswalk、可选受控图像及模型资产。section_id 必须来自清单索引，不接受客户端路径。

- [x] 添加失败测试：`test_reference_coordinates_and_full_counts` 精确保留合成坐标/类型与完整计数；`test_capture_does_not_invent_slice_order` 确认无切片标识时仅列 capture；`test_zero_in_section_differs_from_missing_mapping` 区分 0 观测与未建立对应。
- [x] 添加 `test_rejects_changed_file_and_untrusted_path`，覆盖 hash 变化、越界路径、非有限坐标、缺字段和陈旧词表；不加载表达矩阵 X，不运行 Scanpy，不改输入文件。
- [x] 实现清单读取与既有字段的确定性转换；第一版使用完整空间点、按 capture 读取并建立类型索引。缓存仅按验证后的内容 hash；字段/版本变化使缓存失效。没有已验证像素变换时不启用组织底图。
- [x] 运行 `python -m pytest -q tests/test_spatial_reference.py tests/test_spatial_link_data.py` 至 PASS；补齐配置和失败语义文档。
- [x] 在受控环境只读核对实际参考词表与产品状态定义，形成有依据的候选对应表。已有审阅证明才记 reviewed；否则留 pending 并输出具体待核对条目，不能因需要演示自行提升状态。

## Task 3: 鉴权、产物来源与 Agent 结果入口

**Files:** 新建 `spatial_context.py`、`tests/test_web_spatial_context.py`；修改 `research_context.py`、`service.py`、`http.py`、`inputs.py`、`scientific_inputs.py`、`tests/test_web_expression.py`。

**Interfaces:** `build_spatial_context(product_source: ProductLinkInput, reference: SpatialReference) -> SpatialContextDisplay` 调用任务 1。内部 DTO 版本 `1.0`，kind=`linked_cell_context`，包含 context_id、product、reference、crosswalk 状态、source bindings 和明确 missing reasons。新增已鉴权 `GET /api/sessions/{sid}/artifacts/{aid}/spatial-context` 与其 `/sections/{section_id}?context_id=...` 子路径，锚定现有 expression UMAP artifact；调用现有 artifact 访问审查、canonical receipt/hash 校验，不绕过确认要求。

- [x] 添加失败测试：`test_linked_context_requires_access_and_canonical_receipts` 覆盖未登录、其他会话 artifact、未确认访问、失效回执、同名伪造文件及 assignments 来源不一致；都不得返回空间坐标。
- [x] 添加 `test_context_version_rejects_stale_section_request`：配置/对应表/产品产物变化生成新的 context_id，旧 context_id 返回 409。文件读取失败为可解释 422；未配置参考以 missing reason 返回产品可用状态，而非空计数。
- [x] 提取 `resolve_display_source` 并复用原检查；来源解析完成后才给纯函数传入已校验对象。通过现有产物/回执 ID 寻找同一 DataView 的 assignments 和完整坐标表；多份互相冲突的候选必须显式不可用，不按文件名或“最新文件”猜。
- [x] 路由采用现有认证与会话边界；只返回逻辑资源名、计数、类型和绘图坐标，不返回原始细胞条码、服务器路径、配置或密钥。配置资产只通过相同鉴权边界提供，不新增公开静态目录。
- [x] 沿既有 `assessment_candidates` 和 analysis selection 衔接表达探索与候选注释。选择同一 QC DataView；已完成且来源有效的结果复用，缺项在现有分析计划中列明。没有预算/授权时保留 pending，不在 GET 请求中暗中计算或伪造 ToolRun。
- [x] 运行 `python -m pytest -q tests/test_web_spatial_context.py tests/test_web_expression.py tests/test_web_artifacts.py` 至 PASS；保留原独立 UMAP 的 preview 合同。

## Task 4: 产品 UMAP 与空间点图联动

**Files:** 新建 `spatial/types.ts`、`LinkedCellExplorer.tsx`、`SpatialScatter.tsx`、`linked-cell-explorer.css`、`frontend/tests/linked-cell-explorer.test.tsx`；修改 `ExpressionUMAP.tsx`、`ResearchFigures.tsx`、`frontend/tests/expression.test.tsx`。

**Interfaces:** `LinkedCellExplorer({sessionId, umapArtifactId})` 读取任务 3 DTO。`ProductScatter({data, activeKey, mode, onHover, onPin})` 从原 Scatter 拆出可控视图；key 为 `{kind:'type'|'cluster', id:string}`。`SpatialScatter({section, activeTypeIds, palette})` 独立绘制原始坐标。容器持有 hoverKey、pinnedKey、sectionId 和 context_id；activeKey=pinnedKey??hoverKey，选择转成任务 1 预计算类型集合。

- [x] 添加失败交互测试：`pin_ignores_hover_and_focus_until_explicit_click_or_Escape`、`escape_clears_selection`、`mixed_cluster_retains_unmatched_count`、`version_change_discards_late_response`，断言选中类型集合、精确计数及对应空状态文案；不以 Canvas 是否被调用当成联动正确的证据。
- [x] 实现 45/55 主区与类型列表。鼠标、键盘焦点、点击/Enter 的行为一致；切片切换保留合法锁定群，产品/版本切换清空选择。AbortController 加 context_id 检查，防止迟到响应覆盖。
- [x] 空间背景和高亮使用两层 Canvas，按类型预索引；背景保留全捕获轮廓，高亮匹配位置，其余淡灰。坐标等比例映射、空间 y 方向保留图像约定；不重新计算 UMAP、不改变坐标、不生成抖动点。未验证 H&E 保持关闭。
- [x] 默认按候选细胞类型着色；原始聚类模式展示混合组成；跨图用明确 palette，较宽类型对应在图例标识。无对应、当前切片无观测、注释未知、参考不可用的文案分别保留规格定义。
- [x] 运行 `npm --prefix frontend test -- tests/expression.test.tsx tests/linked-cell-explorer.test.tsx tests/research-figures.test.tsx` 至 PASS。保留旧独立图加载/静态回退及完整分母显示。

## Task 5: 小型三维参照与结果页布局

**Files:** 新建 `spatial/MiniAnatomy.tsx`；修改 `anatomy/viewer.ts`、`anatomy/AnatomyPreview.tsx`、`spatial/LinkedCellExplorer.tsx`、`spatial/linked-cell-explorer.css`、`frontend/tests/linked-cell-explorer.test.tsx`。

**Interfaces:** `MiniAnatomy({modelUrl, stage, planeHypothesis})` 仅消费参考配置，不接收产品分群/细胞数据。查看器显式接收模型 URL；原独立预览自行提供现有 GLB URL。动态加载 Three.js 和模型；组件卸载释放 GPU/事件资源。

- [x] 添加 `anatomy_failure_keeps_linked_plots_usable`：模型失败仍可操作两张图；`group_change_does_not_move_reference_plane`：分群事件不改 planeHypothesis；不为样式写镜像测试。
- [x] 实现右上独立 180–220 像素参考卡，可旋转/折叠，始终显示“解剖参照 / 候选切面，未配准”；不覆盖空间画布。未知方向保留未知，不按标签推断切面。
- [x] 实现窄屏上下排列及来源详情折叠。复用 HDBR 来源/许可说明；原解剖预览继续工作，主应用不捆绑私有图像或模型数据。
- [x] 运行 `npm --prefix frontend run build`、`npm --prefix frontend run build:anatomy` 及任务 4 的交互测试至 PASS；检查构建目录无私有空间数据。

## Task 6: 完整链路与真实数据验收

**Files:** 新建 `tests/test_web_linked_cell_flow.py`；按验收结论更新 `docs/validation/README.md` 所链接的获准共享摘要、`frontend/README.md`；本计划复选框记录工程进度。

- [x] 添加合成端到端测试：上传→既有确认/授权→QC→真实注册工具执行→UMAP+assignments→来源连接→鉴权空间坐标。断言选中群、空间类型集合与完整计数；必须来自工具输出，不能以预填注释冒充新产品运行。候选方法依赖采用已有可控 fixture，明确标为工程验证。
- [x] 用已获准产品结果核对相同链路并记录私有运行清单；若没有可用产品结果，只报告已完成的参考侧/工程验证并列出缺项，不把空间数据自己的 UMAP 称作产品 UMAP。审阅映射表缺失时同样不宣称真实联动验收通过。
- [x] 在应用内浏览器验证桌面及窄屏：加载、hover、pin、Esc、切片切换、类型/聚类切换、参考缺失、3D 失败；保存非代码截图到交付位置。观察数十万点参考与稀有类型的真实交互，不以构建成功代替。
- [x] 如完整绘制达不到可用交互，先用离屏背景/类型索引定位瓶颈；只有必要时加固定种子的按类型抽样并测试保留稀有群，显示点数与完整计数，禁止静默丢群。
- [x] 运行本计划相关后端/前端测试、`python scripts/check_repository.py --static`、`git diff --check`；新失败修复后只重跑受影响检查。最终交付浏览器结果及工程/真实数据/科学资格三者的准确状态。

完整坐标绘制已在真实捕获单元和包含单点稀有群的合成压力数据上核对；当前无需额外抽样。内部真实样本验收限定为来源连接、完整计数与探索性展示；不形成身份、区域、阶段或产品资格结论。

## 后续维护边界

后续修改沿用现有输入授权、来源验证与版本化审阅。缺少实际数据访问、对应关系审阅或新的科学运行授权时保留明确缺项；工程集成不提高科学资格，也不自动更新生产服务。
