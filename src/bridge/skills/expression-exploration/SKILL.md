---
name: expression-exploration
description: Use when asking about input QC, cell filtering, expression profiles, clusters, markers or within-cell-type expression contrasts, without a product-level comparison or multidimensional product assessment. 普通质控、表达谱、细胞群、标志基因和细胞类型内差异表达。
---

# Expression exploration

## Scope

Use for a question about the uploaded expression data or existing QC/expression results.
When the question is about product identity, regional fit, developmental suitability,
whole-product composition and proliferation/stress as an assessment, use product-assessment.
A mention of a marker gene alone does not establish an assessment intent.

## Workflow

1. Read the current question and `research_context`. Separate a request to explain
   existing results from a request to prepare new analysis. An explanation uses
   `reply`; choose current `observation_aliases` when tool-owned observations exist.
2. Check input confirmation and correction state. Use `review_inputs` for a correction.
   For an unconfirmed input, draft only user-stated facts or ask the next consequential
   missing fact. An unknown biological replicate count stays unknown.
3. For requested QC, use the confirmed raw-count matrix and upload ID supplied by
   the server. Valid existing QC is reused. Otherwise `prepare_qc` proposes a plan;
   its execution still waits for exact user approval.
4. Distinguish whole expression exploration, within-cell-type contrast, marker
   interpretation and an unavailable trajectory/communication request. Choose by
   the question and explicit count/expression semantics, not by a favorite method.
   For requested cell-state analysis, inspect the supplied P0-02 capability and
   input contracts. If ready, `prepare_analysis(tool_id="P0-02")` prepares its plan.
   If prerequisites are missing, identify those gaps using the private input panel.
5. For expression profiles, clusters, marker genes or differential expression,
   use available registered results and actions. Explain an unavailable capability
   rather than inventing a new action, a shell command or a computed result.

## Interpretation and stopping

- Check that an existing result's input/view/version answers this question. A changed
  input or requested filter does not silently inherit an old result's denominator.
- A cell cluster is not an independently validated cell type. Reference-derived
  labels and subtype mappings keep their supplied candidate/reference status.
- Differential expression across conditions uses biological replication. Cells are
  not replicates; insufficient replication stays descriptive_only or not_estimable.
- A cluster-selected marker contrast is exploratory; it does not establish a
  between-condition effect or validated cell identity. Batch correction does not
  repair confounding or supply independent repeats. Interpret only the registered
  method and returned effect/uncertainty, not an upstream Skill's default threshold.
- Describe what was actually run. A QC result does not establish cell calling,
  doublet removal, ambient correction or filtering unless its states say so.
- When the user asks to stop or only understand results, finish with a concise
  explanation or one necessary question; no new plan is needed.

## Output

Return the existing Action envelope. Prefer one concise finding or missing-input
explanation plus a useful next step. Figures carry expression distributions,
composition and sample counts; method details do not replace the answer.
Use researcher-facing biological names; keep tool, upload and source identifiers
in structured actions rather than reply text. Ask for experimental facts through
the existing private panel, not internal IDs or JSON.

Tool contracts: [input QC](../../tool_packages/cards/P0-01.md) and
[cell-state evidence](../../tool_packages/cards/P0-02.md). The current safe context supplies
available actions and eligibility; a documentation link grants no execution access.

Adapted workflow and license attribution: [sources](../SOURCES.md).
