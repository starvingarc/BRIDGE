# Plan Lifecycle

## Active Plans

| Workstream | Biological goal | Current finding | Next scientific action | Status |
|---|---|---|---|---|
| [Repository Simplification](repository-simplification.md) | Keep the approved evidence-driven workflow legible without changing scientific judgments | Documentation consolidation, shared figure exports, verified retirement and server engineering gates are complete; no new biological validation | Review the Draft PR while retaining the separate scientific gates below | `awaiting_review` |
| [Product Evidence Validation](product-evidence-validation.md) | Complete genuine source-reviewed product assessment and a verified report | Intake/QC/protocol engineering is accepted in its bounded scope; qualified downstream product evidence and export remain open | Finish state/role/window review, bind measured P0-03–P0-06 inputs and accept the graph/report chain | `awaiting_scientific_inputs_and_review` |
| [P0-02 External-Source Freeze Candidate](p0-02-cell-state-scientific-freeze.md) | Determine whether reviewed fetal ventral-midbrain states support source-aware annotation and off-axis rejection | Birtele is conditionally approved for source/stage holdout; all samples remain not_estimable as biological replicates | Review the 25 state cards, then ProductDefinitionCard and StateRoleMap | `biological_review_in_progress` |
| [Visualization Data Contract](visualization-data-contract.md) | Inspect composition, uncertainty and provenance without turning missing evidence into zero | Shared binding and registry are complete; figure families remain question-led | Apply the contract to each complete researcher-question figure family | `shared_contract_active` |

## Rules

Complex changes use one branch-scoped plan under plans/. The plan path is its
stable identity and appears once in this index. Stable facts belong in docs/;
plans describe only unfinished work and must not claim proposed behavior is
implemented.

A Draft PR may keep an in-progress plan. Before work is ready to merge, record
final evidence and carry every unresolved item into an explicit active plan.
Completed construction diaries leave this index and active tree after unique
facts and validation evidence are retained; their chronology remains in Git.
