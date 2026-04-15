# Formal Workflows

## BRIDGE v1

BRIDGE follows a three-step conceptual pipeline:
- Step 1: reference construction and whole-brain pre-screening
- Step 2: identity assessment and candidate selection
- Step 3: CLS-based concordance scoring, reporting, and visualization

BRIDGE 按三步式概念流程组织：
- Step 1：参考构建与 whole-brain pre-screening
- Step 2：身份评估与候选细胞筛选
- Step 3：基于 CLS 的一致性评分、报告与可视化

## What Is Formalized in v1 / v1 中已正式化的部分

Formal workflows included in v1:
- Step 2: Identity Assessment
- Step 3: CLS A-F
- report / visualization scaffolding
- query model loading
- configuration and output conventions

BRIDGE v1 正式收录的流程：
- Step 2：Identity Assessment
- Step 3：CLS A-F
- report / visualization 脚手架
- query model loading
- 配置与输出规范

## Step 1 Status / Step 1 当前状态

Step 1 is part of the intended BRIDGE architecture, but it is **not yet formalized here as a released workflow**. In thesis terms, it corresponds to:
- reference atlas construction
- integration of embryonic brain data
- whole-brain pre-screening before target-specific evaluation

Step 1 属于 BRIDGE 的目标架构，但**目前尚未在此仓库中正式化为已发布流程**。按论文逻辑，它对应：
- 参考图谱构建
- 人胚脑数据整合
- 在目标特异性评估之前进行 whole-brain pre-screening

## Step 2 and Step 3 Status / Step 2 与 Step 3 当前状态

Step 2 currently maps to the `identity` package and formal candidate-selection logic.

Step 2 当前主要对应 `identity` 包及其正式候选细胞筛选逻辑。

Step 3 currently maps to the `cls`, `io`, and workflow scaffolding that package concordance scoring and downstream outputs.

Step 3 当前主要对应 `cls`、`io` 以及用于封装一致性评分与下游输出的 workflow 脚手架。
