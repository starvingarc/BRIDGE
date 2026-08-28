# Visualization System Documentation Plan

| Item | Value |
|---|---|
| Branch | `visualization-system-docs` |
| Status | `implementation_complete_review_pending` |
| Stable specification | `docs/visualization.md` |
| Runtime change | None |

## Biological goal

Let a researcher evaluating a differentiated cell product see what the data can
support, what cells are present, whether target identity and developmental
context match the reviewed product definition, which signals require review,
and which conclusions still lack evidence.

## Current finding

The scientific task cards already describe required Web views, but the
requirements are distributed across packages. P0-01 and P0-02 emit a limited set
of static plots; the remaining packages primarily emit structured results. The
current `VisualizationArtifact` is a minimum binding object and the integrated
Web experience is not implemented.

## Scope

- [x] Consolidate the user reading order and figure inventory.
- [x] Record the approved large-screen and mobile semantic design direction.
- [x] Define evidence, missingness, interaction, export and accessibility rules.
- [x] State current implementation gaps without presenting proposals as runtime.
- [x] Link the stable specification from the PRD, documentation home, product
  principles and tool contract.
- [x] Record the package-by-package implementation sequence.

## Non-goals

- No JSON Schema, Pydantic model, Python renderer or Web code changes.
- No new domain score, product grade, ranking or release claim.
- No method, reference, state, threshold or ProductDefinitionCard decision.
- No P0 package implementation in this branch.

## Decisions

- The result experience is organized by researcher questions, not P0 IDs.
- The overview uses six evidence rows and no total score, radar or traffic-light
  pass/fail view.
- Scientific tools own measurements; the future Visualization Composer owns
  view transforms; Web owns layout and selection.
- A future additive contract will bind typed visualization data without changing
  the current `VisualizationArtifact` in this documentation branch.
- One package-specific visualization is delivered per PR after the shared
  contract is reviewed and merged.

## Validation

Documentation and repository checks run against the exact branch SHA on the
server. GitHub Actions provide an additional independent repository gate.
Scientific-data and renderer validation are not applicable to this docs-only
change.

## Follow-up order

1. shared visualization data binding and registry;
2. P0-01 Input Audit & QC;
3. P0-02 Cell-State Evidence and OOD;
4. P0-08/P0-09 evidence sufficiency and selected-claim trace;
5. P0-03 through P0-06, one package per PR;
6. conditional comparison, graft and Web integration.
