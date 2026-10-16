---
name: product-assessment
description: Use when asking for a cell product's multidimensional assessment or domain-specific product interpretation of target identity, regional fit, developmental compatibility, whole-product composition, proliferation and stress. 产品五域研究评估；参考选择、证据冲突、比较、移植后和报告各有专门工作流。
---

# Product assessment

## Scope

Assess research evidence for a cell product. Keep identity, developmental context,
composition and process state distinct; a plausible marker profile is not a complete
product assessment. Ordinary QC/expression, target/reference definition, comparison,
graft and report-only questions have specialized entries. In approved assessment,
the server composes the relevant workflows while preserving the same action budget.

## Preparation

1. Read the current question, confirmed product intent, selected inputs and current
   evidence. Reuse a result only for its actual input/view/version and stated scope.
2. If the requested assessment lacks a consequential fact, ask that fact once or
   point to its existing private input control. Input review requires `review_inputs`.
3. When scientific definitions are missing, explain the needed source-bound
   target/role/window confirmation. Requested preparation uses the existing
   `draft_scientific_inputs` flow; its separate scope loads reference-and-target-definition.
4. QC and cell-state evidence are prerequisites, not a product score. Use registered
   P0-01/P0-02 plans when requested and eligible; do not run tools through this Skill.

## Approved assessment loop

1. Treat the server's approved scope and supplied options as the action boundary.
   Select a useful `check` or read-only `query` by its exact current option ID.
2. Follow the question across eligible domains: P0-03 covers target identity and
   regional consistency; P0-04 developmental compatibility; P0-05 whole-product and
   non-target composition; P0-06 proliferation and stress. Eligibility is per mode.
   Missing one domain does not invalidate measured evidence in another.
3. For each domain, preserve actual runnable, missing-input, unavailable or measured
   state. A high-level or unresolved cell-state label is not automatically target or
   non-target. Identity and composition consume the same reviewed role definition;
   regional and developmental axes retain their own denominator and expected window.
4. Use registered sufficiency/graph options to organize measurements and gaps.
   Follow the composed evidence-reasoning workflow for competing explanations and
   useful next checks; graph operations are not independent biological votes.
5. A requested report follows the composed research-reporting workflow and the
   server-owned current graph/explanation handoff. Scientific findings, a verified
   private report and public export remain separate states.

## Stopping and output

Address researchers with biological names: target cells, expected developmental
window, region and sample/preparation information. The private panel and source-bound
drafting flow resolve internal identifiers. Never ask a researcher to supply state,
source, upload or tool IDs; do not echo those IDs or action names in a normal reply.
When asked only what is missing, give the consequential gaps and the next private
panel action in a few sentences. Do not expand into an internal workflow inventory.

Use `question` for a consequential missing fact or `stop` when no defensible next
step exists within scope. A bounded explanation can end a phase with open questions.
Keep unavailable, unknown, negative and alert distinct. Return domain measurements,
evidence gaps and their limits; domain scores remain unavailable/shadow under the
current score contract. No clinical efficacy, safety, release or absolute ranking.

Within approved scope, product-comparison and graft-followup supply their own
conditional branches. Comparison retains declared units and comparability; graft
remains independent post-transplant evidence and cannot backfill this assessment.

Tool contracts: [identity/region](../../tool_packages/cards/P0-03.md),
[development](../../tool_packages/cards/P0-04.md), [composition](../../tool_packages/cards/P0-05.md),
[proliferation/stress](../../tool_packages/cards/P0-06.md),
[sufficiency](../../tool_packages/cards/P0-08.md), [graph](../../tool_packages/cards/P0-09.md),
[claims/report](../../tool_packages/cards/P0-10.md). Supplied eligibility and evidence remain
authoritative; Skill text neither creates missing inputs nor grants approval.

Adapted workflow and license attribution: [sources](../SOURCES.md).
