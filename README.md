# BRIDGE

**Brain-Referenced In vivo-to-in vitro Developmental Guidance and Evaluation**

BRIDGE is a brain-referenced developmental guidance and evaluation framework for mapping, screening, and scoring in vitro cell products against in vivo developmental programs.

BRIDGE 是一个以真实脑发育参照为基础的 in vivo-to-in vitro 发育引导与评价框架，用于对体外细胞产物进行映射、筛选与多维评分。

Conceptually, BRIDGE is organized as a **three-step workflow**:
- **Step 1**: build the in vivo developmental reference and whole-brain pre-screening space
- **Step 2**: perform target-specific identity assessment and candidate selection
- **Step 3**: quantify developmental concordance with CLS and downstream reporting

从概念上讲，BRIDGE 是一个**三步式流程**：
- **Step 1**：构建体内发育参考系与 whole-brain pre-screening 空间
- **Step 2**：进行目标细胞身份评估与候选细胞筛选
- **Step 3**：利用 CLS 完成发育一致性量化与下游报告输出

## Status / 当前状态

**BRIDGE v1** currently formalizes the main workflows for **Step 2** and **Step 3**, while keeping **Step 1** as an explicitly planned but not yet finalized module:
- Identity Assessment
- CLS A-F
- Report / visualization
- Query model loading
- Configuration and output conventions

**BRIDGE v1** 当前正式收录 **Step 2** 和 **Step 3** 的主流程，并把 **Step 1** 明确标记为“已规划但尚未正式化”的模块：
- Identity Assessment
- CLS A-F
- report / visualization
- query model loading
- 配置与输出规范

**Step 1 is not yet complete.** In the thesis logic, Step 1 covers reference atlas construction and whole-brain pre-screening. In BRIDGE v1, those pieces are acknowledged as part of the full pipeline but are not yet released here as finalized production workflows.

**Step 1 尚未完成。** 按论文逻辑，Step 1 对应参考图谱构建与全脑 pre-screening。BRIDGE v1 已明确承认这是完整流程的一部分，但目前还没有把它作为正式生产流程发布，只保留路线图和占位说明。

## Pipeline Overview / 三步流程总览

### Step 1: Reference Construction and Pre-screening / 参考构建与预筛选

Step 1 defines the **in vivo reference coordinate system** that anchors the whole framework. It is intended to include:
- integration of human embryonic brain single-cell data into a reference atlas
- construction of region-aware and stage-aware reference spaces
- whole-brain pre-screening to identify broad lineage composition and exclude obvious off-target populations

Step 1 为整个框架提供**体内参考坐标系**。它计划包含：
- 整合人胚脑单细胞数据，构建参考图谱
- 构建具有区域与发育阶段信息的参考空间
- 在 whole-brain 层面进行预筛选，识别样本总体谱系构成并排除明显 off-target 细胞

Current repository status:
- conceptually part of BRIDGE
- not yet formalized in public v1
- represented through roadmap and scope documents only

当前仓库状态：
- 在概念上属于 BRIDGE 正式流程的一部分
- 但尚未在公开 v1 中正式化
- 当前仅通过 roadmap 和边界文档体现

### Step 2: Identity Assessment / 身份评估

Step 2 refines candidate target cells under a more specific reference. In the current codebase, this step covers:
- query model loading
- soft prediction and probability calibration
- ensemble-based uncertainty estimation
- normalized entropy calculation
- candidate selection through thresholded identity-stability rules

Step 2 在更具体的参考框架下筛选目标候选细胞。当前代码中，这一步包含：
- query model 加载
- soft prediction 与概率校准
- 基于 ensemble 的不确定性估计
- 归一化熵计算
- 基于身份稳定性的阈值规则筛选候选细胞

This is the formalized **Identity Assessment** module under BRIDGE v1.

这部分就是 BRIDGE v1 中已经正式化的 **Identity Assessment** 模块。

### Step 3: CLS and Reporting / CLS 评分与结果输出

Step 3 evaluates how well in vitro products reconstruct the in vivo developmental program after candidate selection. In the current repository, this includes:
- CLS component A-F
- shared output packaging and result serialization
- report / visualization scaffolding
- configuration and output conventions for downstream comparison

Step 3 在候选细胞确定之后，评价体外产物在多大程度上重建了体内发育程序。当前仓库中，这一步包含：
- CLS A-F 六个组件
- 统一输出包装与结果序列化
- report / visualization 脚手架
- 用于下游比较的配置与输出规范

This is the formalized **concordance scoring and reporting** layer under BRIDGE v1.

这部分构成了 BRIDGE v1 中已经正式化的**一致性评分与结果输出层**。

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

- `v1`: formalize Step 2 and Step 3 under a stable public package structure
- `future`: formalize Step 1, complete the end-to-end three-step pipeline, and migrate selected standardized extensions

- `v1`：在稳定的公开包结构下正式化 Step 2 与 Step 3
- `future`：正式化 Step 1、补全三步式端到端流程、迁移经过标准化的扩展内容

## Current Limitations / 当前限制

- Step 1 reference construction is still under planning.
- Notebooks in this repository are placeholders and entrypoint notes, not full exploratory records.
- Models are documented as interfaces and metadata, not distributed as large binary assets.
- Some current package code is still transitioning from research-grade structure to public-repo structure.

- Step 1 参考构建仍处于规划阶段。
- 本仓库中的 notebook 当前以占位和入口说明为主，不是完整研究记录。
- models 当前只记录接口和元信息，不分发大型二进制权重。
- 部分代码虽然已经进入正式包结构，但仍在从 research-grade 组织方式过渡到公开仓库组织方式。
