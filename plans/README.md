# Plan Lifecycle

## Active Plans

| Workstream | Biological goal | Current finding | Next scientific action | Status |
|---|---|---|---|---|
| [P0-02 External-Source Freeze Candidate](p0-02-cell-state-scientific-freeze.md) | Determine whether reviewed fetal ventral-midbrain states can support source-aware product annotation and reject off-axis cells | Birtele is conditionally approved for source/stage-level holdout with provisional groups; all samples remain `not_estimable` as biological replicates | Review the 25 state cards one at a time, then ProductDefinitionCard and StateRoleMap | `biological_review_in_progress` |
| [Visualization Data Contract](visualization-data-contract.md) | Let researchers inspect product composition, uncertainty and evidence provenance without turning missing evidence into zero | The reading order and figure families are approved; current figures use the minimum v0.1 artifact and are not yet Web-ready | Add a versioned data binding and discoverable figure registry before changing individual figure families | `implementation_in_progress` |
| [Tool Runtime Contract Cleanup](tool-runtime-contract-cleanup.md) | Make every packaged tool input discoverable without changing biological decisions | All 12 packages expose a versioned input contract; exact runtime helpers and shared product-context types are consolidated with compatibility preserved | Review the Draft PR and retain current scientific states | `implementation_complete_review_pending` |

## Rules

Complex changes use one branch-scoped plan under `plans/`. The plan path is the stable identity for that task and appears only once in this index; an existing plan is resumed or handed off rather than overwritten.

Each plan records motivation, scope, non-goals, frozen interfaces, tasks, validation, decisions and unresolved risks. Stable facts belong in `docs/`; plans must not claim that proposed work is already implemented.

A Draft PR may keep an `in_progress` plan when real-data or human-review gates remain open. Before a PR becomes ready to merge, record final evidence and either complete the plan or split every remaining item into an explicit follow-up plan. Completed plans are removed from this index; their implementation and verification history remains in Git.
