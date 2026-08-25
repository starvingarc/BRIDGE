# Plan Lifecycle

## Active Plans

| Workstream | Biological goal | Current finding | Next scientific action | Status |
|---|---|---|---|---|
| [P0-02 External-Source Freeze Candidate](p0-02-cell-state-scientific-freeze.md) | Determine whether reviewed fetal ventral-midbrain states can support source-aware product annotation and reject off-axis cells | Birtele is conditionally approved for source/stage-level holdout with provisional groups; all samples remain `not_estimable` as biological replicates | Review the 25 state cards one at a time, then ProductDefinitionCard and StateRoleMap | `biological_review_in_progress` |
| [Shared P0 Scientific Contract Spine](shared-p0-scientific-contract-spine.md) | Preserve exact data-view, biological-unit and measurement lineage across independently packaged P0 modules | Exact source and installed-wheel suites pass at the implementation commit without importing mutable domain decisions | Complete independent biology, single-cell/statistics and AI4S exact-head review | `implementation_complete_review_pending` |
| [Repository Readability](repository-readability.md) | Make the public entrypoints and all 12 package documentation paths readable without changing scientific claims | Reader-oriented navigation and all 12 package landing pages pass exact-source and isolated-wheel server gates | Complete GitHub exact-head CI and human review | `implementation_complete_review_pending` |

## Rules

Complex changes use one branch-scoped plan under `plans/`. The plan path is the stable identity for that task and appears only once in this index; an existing plan is resumed or handed off rather than overwritten.

Each plan records motivation, scope, non-goals, frozen interfaces, tasks, validation, decisions and unresolved risks. Stable facts belong in `docs/`; plans must not claim that proposed work is already implemented.

A Draft PR may keep an `in_progress` plan when real-data or human-review gates remain open. Before a PR becomes ready to merge, record final evidence and either complete the plan or split every remaining item into an explicit follow-up plan. Completed plans are removed from this index; their implementation and verification history remains in Git.
