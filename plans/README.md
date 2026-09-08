# Plan Lifecycle

## Active Plans

| Workstream | Biological goal | Current finding | Next scientific action | Status |
|---|---|---|---|---|
| [Web Full-Chain Integration](web-full-chain-integration.md) | Evaluate differentiation outputs through genuine data and traceable interpretation | PR #95 closeout consolidates Tasks 1–20; product intake is installed and genuinely exercised. P0-05/P0-06 remain explicit PR #96/#97 dependencies; prior cell-state/no-graft coverage is distinct | Choice cards, V2 interpretation, scientific review/revision, missingness compilation and a blocked internal report are installed and browser-exercised; approved descriptive P0-06 joint measurement now succeeded through an isolated installed SDK; next review its evidence and complete reviewed state/role definitions and genuine experiment facts, with Web acceptance and domain integration still separate | `downstream_measured_inputs_pending` |
| [P0-02 External-Source Freeze Candidate](p0-02-cell-state-scientific-freeze.md) | Determine whether reviewed fetal ventral-midbrain states can support source-aware product annotation and reject off-axis cells | Birtele is conditionally approved for source/stage-level holdout with provisional groups; all samples remain `not_estimable` as biological replicates | Review the 25 state cards one at a time, then ProductDefinitionCard and StateRoleMap | `biological_review_in_progress` |
| [Visualization Data Contract](visualization-data-contract.md) | Let researchers inspect product composition, uncertainty and evidence provenance without turning missing evidence into zero | The shared binding and registry are complete; visualization PRs now follow researcher questions rather than P0 numeric order | Apply the contract to each complete question-led figure family | `shared_contract_active` |
| [Tool Runtime Contract Cleanup](tool-runtime-contract-cleanup.md) | Make every packaged tool input discoverable without changing biological decisions | All 12 packages expose a versioned input contract; exact runtime helpers and shared product-context types are consolidated with compatibility preserved | Review the Draft PR and retain current scientific states | `implementation_complete_review_pending` |
| [P0-05 Hard-count Accounting](p0-05-hard-count-accounting.md) | Preserve whole-view reference-support counts when assignment mass is unavailable | Count-only route and installed-wheel checks complete; existing modes remain supported | Review the module PR and genuine design records; do not interpret counts as probabilities | `implementation_complete_review_pending` |
| [P0-06 Source-bound Observations](p0-06-unresolved-observations.md) | Preserve unresolved producer observations in whole-product expression summaries | Source-bound route and installed-wheel checks complete; existing modes remain supported | Review the module PR and bind genuine source artifacts and design records | `implementation_complete_review_pending` |

## Rules

Complex changes use one branch-scoped plan under `plans/`. The plan path is the stable identity for that task and appears only once in this index; an existing plan is resumed or handed off rather than overwritten.

Each plan records motivation, scope, non-goals, frozen interfaces, tasks, validation, decisions and unresolved risks. Stable facts belong in `docs/`; plans must not claim that proposed work is already implemented.

A Draft PR may keep an `in_progress` plan when real-data or human-review gates remain open. Before a PR becomes ready to merge, record final evidence and either complete the plan or split every remaining item into an explicit follow-up plan. Completed plans are removed from this index; their implementation and verification history remains in Git.
