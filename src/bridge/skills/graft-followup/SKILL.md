---
name: graft-followup
description: Use when asking about post-transplant graft observations, graft/animal/timepoint binding, absent graft data, or links between a source preparation and independent post-transplant evidence. 移植后证据及其与来源产品的关系；不回填移植前评估。
---

# Graft follow-up

## Scope and inputs

Interpret independent post-transplant evidence. Read the declared graft, animal,
post-transplant timepoint, source preparation link and available P0-12 input mode.
Technical samples remain nested within their graft/animal context; they are not
independent graft replicates. A pre-transplant product and a graft answer different
questions even when they share a source preparation.

## Decisions

1. Distinguish explicit no-graft declaration, missing/unknown availability, precomputed
   evidence and expression analysis. Missing data is not observed absence. The
   `not_provided` mode requires the existing explicit input declaration and approval.
2. Check that the source preparation link, animal and timepoint are declared. For
   expression mode, the supplied reference/programs must match organism, assay,
   namespace, expression semantics and aggregation; the tool verifies these bindings.
3. If relevant data is outside the approved scope, explain what it could answer and
   the needed extension. Use a requested eligible P0-12 plan, or an exact supplied
   P0-12 check in approved assessment. A question about graft evidence alone grants
   no new analysis permission.
4. Interpret only executed calculations: descriptive composition from supplied state
   probabilities, matched reference support and external marker-program observations.
   These do not independently establish annotation accuracy, functional maturation,
   engraftment efficacy or safety. Respect `qc_state=not_reassessed` when supplied.
5. Keep graft findings in the independent post-transplant branch. A source-bound
   preparation-graft association is descriptive and requires linking evidence; shared
   names or apparent marker similarity do not establish that link.

## Stopping and output

Return observations at the declared graft/animal/timepoint, their source/limitations,
missing links and a useful next action. If data is absent, say what remains unknown
without producing zero-valued measurements. `pretransplant_evidence_effect=none`
remains invariant: graft evidence does not revise pre-transplant scores, thresholds,
training, calibration or identity conclusions. Keep current candidate/shadow status.

Contract: [graft assessment](../../tool_packages/cards/P0-12.md).
Adapted workflow and license attribution: [sources](../SOURCES.md).
