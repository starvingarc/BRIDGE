# Plans

| Workstream | Biological goal | Current finding | Next scientific action | Status |
|---|---|---|---|---|
| [P0-02 External-Source Freeze Candidate](plans/p0-02-cell-state-scientific-freeze.md) | Determine whether reviewed fetal ventral-midbrain states can support source-aware product annotation and reject off-axis cells | Birtele is conditionally approved for source/stage-level holdout with provisional groups; all samples remain `not_estimable` as biological replicates | Review the 25 state cards one at a time, then ProductDefinitionCard and StateRoleMap | `biological_review_in_progress` |
| [P0-03 Configurable Target & Regional Evidence](plans/p0-03-target-regional-evidence.md) | Turn upstream cell-state composition into product-relative target and regional evidence without freezing biological assignments in code | P0-03 is a scaffold; P0-02 already emits a structured shadow composition but product roles have no executable versioned input contract | Implement a deterministic candidate that consumes checksummed ProductCase, ProductDefinitionCard, StateRoleMap and assessment-spec objects | `implementation_in_progress` |
