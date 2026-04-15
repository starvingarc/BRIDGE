# BRIDGE

**Brain-Referenced In vivo-to-in vitro Developmental Guidance and Evaluation**

BRIDGE is a brain-referenced developmental guidance and evaluation framework for mapping, screening, and scoring in vitro cell products against in vivo developmental programs.

BRIDGE 是一个以真实脑发育参照为基础的 in vivo-to-in vitro 发育引导与评价框架，用于对体外细胞产物进行映射、筛选与多维评分。

## Status / 当前状态

**BRIDGE v1** currently formalizes only the main workflows for **Step 2** and **Step 3**:
- Identity Assessment
- CLS A-F
- Report / visualization
- Query model loading
- Configuration and output conventions

**BRIDGE v1** 当前只正式收录 **Step 2** 和 **Step 3** 的主流程：
- Identity Assessment
- CLS A-F
- report / visualization
- query model loading
- 配置与输出规范

**Step 1 is not yet complete.** Reference construction and whole-brain pre-screening are not presented here as finalized production workflows. They are tracked as roadmap items and placeholders.

**Step 1 尚未完成。** 参考图谱构建与全脑 pre-screening 目前还没有进入正式发布流程，只保留路线图和占位说明。

## What Is In Scope / 正式范围

The following are part of the formal BRIDGE v1 workflow:
- `src/bridge/identity`: Step 2 identity assessment logic
- `src/bridge/cls`: Step 3 CLS A-F component logic
- `src/bridge/io` and `src/bridge/workflows`: output handling and workflow scaffolding
- `tests/`: formal tests for v1 modules
- `configs/`: configuration placeholders and output conventions
- `docs/`: formal workflow notes, roadmap, and scope boundaries

以下内容属于 BRIDGE v1 的正式主流程：
- `src/bridge/identity`：Step 2 身份评估逻辑
- `src/bridge/cls`：Step 3 CLS A-F 组件逻辑
- `src/bridge/io` 与 `src/bridge/workflows`：输出层与流程脚手架
- `tests/`：v1 正式测试
- `configs/`：配置占位与输出规范
- `docs/`：正式流程说明、路线图与边界文档

## What Is Not In Scope / 非正式扩展内容

The following are intentionally **not** part of the initial public repository content:
- exploratory research notebooks from the current `drafts/`
- thesis writing artifacts and manuscript-generation materials
- provisional plotting scripts and one-off analyses
- large model weights and unpublished intermediate datasets

以下内容在首版公开仓库中**不会**整体纳入：
- 当前 `drafts/` 中的 exploratory notebook
- 论文写作材料与成稿生成过程文件
- 临时绘图脚本和一次性分析代码
- 大型模型权重与未整理的中间数据

These materials may be migrated later only after they are standardized, documented, and made testable.

这些内容后续只有在完成标准化、文档化和可测试化之后，才会逐步迁入。

## Repository Layout / 目录结构

```text
BRIDGE/
├─ README.md
├─ CLAUDE.md
├─ pyproject.toml
├─ src/bridge/
├─ tests/
├─ configs/
├─ models/
├─ notebooks/
├─ docs/
└─ .claude/
   └─ skills/
```

Key directory meanings:
- `src/bridge/`: formal Python package
- `tests/`: formal test suite
- `configs/`: config templates and output naming conventions
- `models/`: model metadata and loading notes, not large weights
- `notebooks/`: formal notebook entrypoints and placeholders only
- `docs/`: workflow and roadmap documents
- `.claude/skills/`: repository-local AI collaboration guidance

关键目录含义：
- `src/bridge/`：正式 Python 包
- `tests/`：正式测试集
- `configs/`：配置模板与输出命名规范
- `models/`：模型元信息与加载约定，不存放大权重
- `notebooks/`：正式 notebook 入口与占位，不迁入 `drafts`
- `docs/`：流程与路线图说明
- `.claude/skills/`：仓库内 AI 协作说明

## Quick Start / 快速开始

```bash
pip install -e .[test]
pytest -q
```

At this stage, BRIDGE v1 should be treated as a structured public skeleton for Step 2 and Step 3 rather than a fully packaged end-user release.

目前 BRIDGE v1 更适合作为 Step 2 和 Step 3 的正式公开骨架，而不是已经完成全部功能包装的最终用户发行版。

## Roadmap / 路线图

- `v1`: Step 2 + Step 3 formalization
- `future`: Step 1 formalization, broader configuration stabilization, and migration of selected extensions

- `v1`：正式化 Step 2 + Step 3
- `future`：正式化 Step 1、补全配置稳定性、迁移部分扩展内容

## Current Limitations / 当前限制

- Step 1 reference construction is still under planning.
- Notebooks in this repository are placeholders and entrypoint notes, not full exploratory records.
- Models are documented as interfaces and metadata, not distributed as large binary assets.
- Some current package code is still transitioning from research-grade structure to public-repo structure.

- Step 1 参考构建仍处于规划阶段。
- 本仓库中的 notebook 当前以占位和入口说明为主，不是完整研究记录。
- models 当前只记录接口和元信息，不分发大型二进制权重。
- 部分代码虽然已经进入正式包结构，但仍在从 research-grade 组织方式过渡到公开仓库组织方式。
