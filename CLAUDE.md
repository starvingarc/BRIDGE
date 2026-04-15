# CLAUDE.md

## Project Positioning / 项目定位

BRIDGE is maintained as a formal repository for the standardized workflows that are already stable enough to be versioned and tested.

BRIDGE 作为正式仓库，只维护已经达到“可版本化、可测试、可说明”标准的稳定流程。

Current scope for **v1**:
- Step 2: Identity Assessment
- Step 3: CLS A-F, report / visualization, query model loading, and output conventions

当前 **v1** 范围：
- Step 2：Identity Assessment
- Step 3：CLS A-F、report / visualization、query model loading、输出规范

Full conceptual pipeline:
- Step 1: reference construction and whole-brain pre-screening
- Step 2: identity assessment and candidate selection
- Step 3: CLS-based concordance scoring and reporting

完整概念流程：
- Step 1：参考构建与 whole-brain pre-screening
- Step 2：身份评估与候选细胞筛选
- Step 3：基于 CLS 的一致性评分与结果输出

Step 1 is intentionally not treated as complete production logic in this repository yet.

Step 1 在当前仓库中有意不按“已完成正式流程”处理。

## Code Organization Principles / 代码组织原则

- `src/bridge/identity` maps to formal Step 2 logic.
- `src/bridge/cls` maps to formal Step 3 logic.
- `src/bridge/io` and `src/bridge/workflows` host output handling and orchestration.
- `tests` must cover formal modules, not exploratory one-off analysis.
- notebooks must not carry core business logic.

- `src/bridge/identity` 对应正式 Step 2。
- `src/bridge/cls` 对应正式 Step 3。
- `src/bridge/io` 与 `src/bridge/workflows` 承担输出与编排层。
- `tests` 只覆盖正式模块，不承载 exploratory 分析验证。
- notebook 不允许承载核心业务逻辑。

Repository interpretation rule:
- Step 1 may be documented in `docs/`, but not advertised as implemented production code unless formalized.
- Step 2 and Step 3 are allowed to evolve as public package modules because they already have stable code structure.

仓库解释规则：
- Step 1 可以在 `docs/` 中说明，但在正式化前不得被表述为“已实现的生产级代码”。
- Step 2 与 Step 3 因为已经有较稳定的代码结构，可以作为公开包模块继续演进。

## What May Enter the Formal Codebase / 哪些内容允许进入正式主线

Allowed:
- standardized APIs
- configuration-driven parameters
- documented output contracts
- testable modules
- stable wrappers around query loading, scoring, and reporting

允许进入正式主线的内容：
- 标准化 API
- 配置化参数
- 有文档的输出协议
- 可测试模块
- 稳定的 query loading、scoring、reporting 包装层

## What Must Stay Out for Now / 当前必须留在正式主线之外的内容

Do not place the following directly into the formal package until standardized:
- `drafts`-style exploratory notebooks
- thesis-only plotting scripts
- provisional analysis fragments without stable I/O contracts
- unpublished ad hoc code that has not been documented or tested

以下内容在未标准化前不得直接进入正式包：
- `drafts` 风格 exploratory notebook
- 仅服务于论文临时绘图的脚本
- 没有稳定输入输出协议的分析片段
- 未文档化、未测试的临时代码

## Contribution Rules / 贡献规则

When adding new work:
1. First classify it as either formal workflow or exploratory extension.
2. If it belongs to the formal workflow, place it in `src/bridge` and add tests.
3. If it is exploratory, document it outside the formal package first.
4. Do not move notebook logic into core modules without defining interfaces and tests.

新增内容时：
1. 先判断它属于正式主流程还是扩展探索。
2. 如果属于正式主流程，放入 `src/bridge` 并补测试。
3. 如果属于扩展探索，先在正式包外部做文档化说明。
4. 未定义接口与测试前，不得把 notebook 逻辑直接迁入核心模块。

## Output and Naming Rules / 输出与命名规则

- Keep output contracts explicit and documented.
- Prefer stable directory and file naming over notebook-local conventions.
- Model binaries should not be committed unless they are intentionally part of a release artifact strategy.

- 输出协议必须明确且有文档。
- 优先使用稳定目录命名与文件命名，避免 notebook 局部约定。
- 模型大文件除非被明确纳入发布策略，否则不应提交进仓库。

## Migration Rules / 迁移原则

- Step 1 can be promoted into the formal repository only after method, interfaces, and outputs are stabilized.
- Experimental materials can be migrated only after standardization, documentation, and testability are established.
- Public repository structure takes precedence over preserving legacy draft layout.

- Step 1 只有在方法、接口与输出稳定之后，才能进入正式仓库。
- 扩展实验内容只有在完成标准化、文档化、可测试化后，才可迁入。
- 公开仓库结构优先于保留历史草稿布局。
