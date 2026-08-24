# P0-12 Configurable Graft Assessment

## Goal

Make the optional graft package callable without freezing biological states,
species choices, assay thresholds, time windows or interpretation rules in
Python. The first slice summarizes checksummed, precomputed graft observations
under one explicit versioned policy.

## Interface

The package accepts exactly one `GraftAssessmentSpec` and one
`GraftEvidenceBundle`. The spec owns channel IDs, units, eligible evidence
states, minimum independent-unit counts and optional review intervals. The
bundle owns ProductCase and graft context, independent animal/graft/timepoint
units, observations, declared design constraints and explicit preparation
linkage evidence.

It emits one `GraftAssessment` JSON object. A caller can explicitly submit
`graft_availability=not_provided`; that produces a traceable `not_provided`
result and never degrades or rewrites pre-transplant evidence.

## Explicit non-goals

- no expression-matrix, cell-state, reference-mapping or species computation;
- no encoded state names, host species, time windows, programs or thresholds;
- no inference from filenames, labels or missing linkage metadata;
- no clinical, safety, efficacy, potency, release, score or ranking claim;
- no back-propagation into P0-03 through P0-07 or a ProductCase;
- no second artifact type or general graft-analysis framework.

## Deliverables

- module-local models, executor and adapter;
- public and packaged input/result Schemas;
- synthetic request, detailed Tool Card and validation record;
- focused source and installed-wheel tests;
- one P0-12-only stacked Draft PR based on P0-11.

## Verification and stop

All project execution occurs in GitHub Actions. The clean installed-wheel
configurable-interface suite passes 195 tests and the full suite passes 1,154;
12-tool discovery, 74-Schema packaging, knowledge and repository policy are
green on the code-bearing head. Draft PR #26 remains at the independent-review
stop. Real graft rules, biological assignments and release status remain
separate scientific inputs and can change without code edits.
