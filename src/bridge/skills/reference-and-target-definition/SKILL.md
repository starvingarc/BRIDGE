---
name: reference-and-target-definition
description: Use when selecting or explaining reference atlases, product target states, regional denominators, developmental windows or target/non-target roles, or when the server requests a source-bound scientific-input draft. 参考适用性、目标状态、预期窗口与角色候选；不用于宣布产品身份已验证。
---

# Reference and target definition

## Scope and inputs

Select defensible candidates for the confirmed product intent. Read the supplied
state/source catalog, reviewed input and existing cell-state evidence. Atlas labels,
product roles and expected developmental windows are distinct objects. A reference
match can support a candidate; it does not itself establish desired product identity.

## Decisions

1. Establish intended cell type, region, sampling context and intended developmental
   window from confirmed facts. Culture duration alone does not define maturity.
2. Inspect candidate applicability: organism, tissue/region, developmental context,
   assay, expression semantics, gene coverage, source family and version. Distinguish
   an appropriate reference, background context and an inapplicable object.
3. Use only the supplied versioned source catalog in a formal draft. Multiple atlas
   entries from the same study are dependent. Keep genuine disagreement and missing
   coverage visible; avoid choosing whichever reference makes the product look best.
4. In ordinary conversation, explain the consequential choice or use
   `draft_scientific_inputs` when the user requests preparation and the existing
   private controls permit it. This opens the separate bounded drafting scope.
5. In `scientific_input_draft` scope, return `propose_scientific_inputs` with the
   supplied upload and candidate schema. Choose only supplied state/source IDs at
   one label level. Every role/window choice needs its allowed source and rationale.
   Regional target states are a subset of the declared denominator states. Leave
   unsupported roles/windows unresolved; use empty candidate lists if none qualify.

## Handoff, stopping and output

Present candidate meaning, supporting source and limitation in researcher-facing
language. The private panel owns identifiers and explicit confirmation. Confirmation
records a reviewed definition; it does not promote candidate science to validation.
Target identity and composition must consume the same reviewed role definition.

If no suitable supplied reference or source exists, explain the exact applicability
gap and its effect on assessment. External database discovery would be a separate
candidate-curation task, not an implicit network call or an admitted reference.
Keep prior versions when a definition changes and use the existing update workflow.

Contracts: [cell-state evidence](../../tool_packages/cards/P0-02.md),
[target/region](../../tool_packages/cards/P0-03.md),
[development](../../tool_packages/cards/P0-04.md),
[composition](../../tool_packages/cards/P0-05.md).
Adapted workflow and license attribution: [sources](../SOURCES.md).
