# Plan Lifecycle

## Active Plans

| Workstream | Biological goal | Current finding | Next scientific action | Status |
|---|---|---|---|---|
| [P0-02 External-Source Freeze Candidate](p0-02-cell-state-scientific-freeze.md) | Determine whether reviewed fetal ventral-midbrain states can support source-aware product annotation and reject off-axis cells | Birtele is conditionally approved for source/stage-level holdout with provisional groups; all samples remain `not_estimable` as biological replicates | Review the 25 state cards one at a time, then ProductDefinitionCard and StateRoleMap | `biological_review_in_progress` |
| [Visualization System Documentation](../docs/BRIDGE_PRD.md#66-visualization-composer-与-web-交互) | Let researchers inspect product composition, target fit, review signals and evidence gaps without converting missing or shadow evidence into a product grade | The approved figure requirements were distributed across task cards; P0-01/P0-02 have partial static plots and the integrated Web result experience is not implemented | Review and merge the stable visualization specification before any shared contract or package renderer changes | `implementation_complete_review_pending` |
| [Tool Runtime Contract Cleanup](tool-runtime-contract-cleanup.md) | Make every packaged tool input discoverable without changing biological decisions | All 12 packages expose a versioned input contract; exact runtime helpers and shared product-context types are consolidated with compatibility preserved | Review the Draft PR and retain current scientific states | `implementation_complete_review_pending` |


## Visualization Delivery Sequence

The stable figure inventory and evidence semantics live in the
[BRIDGE PRD](../docs/BRIDGE_PRD.md#66-visualization-composer-与-web-交互).
This workstream changes no runtime interface or biological decision.

After review and merge, delivery proceeds as one focused PR at a time: shared
data binding and registry; Input Audit & QC; Cell-State Evidence and OOD;
Evidence Sufficiency and selected-claim trace; then each remaining scientific
package. Web integration consumes only registered components. P0-02 remains on
its existing scientific work line.

## Rules

Complex changes use one branch-scoped plan under `plans/`. The plan path is the stable identity for that task and appears only once in this index; an existing plan is resumed or handed off rather than overwritten.

Each plan records motivation, scope, non-goals, frozen interfaces, tasks, validation, decisions and unresolved risks. Stable facts belong in `docs/`; plans must not claim that proposed work is already implemented.

A Draft PR may keep an `in_progress` plan when real-data or human-review gates remain open. Before a PR becomes ready to merge, record final evidence and either complete the plan or split every remaining item into an explicit follow-up plan. Completed plans are removed from this index; their implementation and verification history remains in Git.
