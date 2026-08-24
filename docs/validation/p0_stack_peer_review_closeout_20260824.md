# P0 stack peer-review closeout validation — 2026-08-24

## Question

Can the implemented P0 packages be called as one deterministic,
evidence-bounded workflow without hard-coding mutable biological assignments,
mistaking repeated observations for biological replication, or granting public
release authority to a caller-controlled object?

This record covers engineering closure only. It does not freeze the P0-02
state vocabulary, StateRoleMap, developmental window, program rules,
thresholds, score contract, disclosure policy or any biological conclusion.

## Reviewed implementation

The implementation commit validated on `/data1` was
`b6607aee6ea6930fe5b1baf5c4fc7020d92460d3`, with Git tree
`0913cf5d22bc12fbe49617d151c6ad38f3ee24a0`. Its Git archive SHA-256 was
`500a4c84a572b338cd3962b0d93a83bffeef77a377199e7de034aa71943fb926`.
No project code was executed on the local workstation.

The evidence record was written to the private P0 stack closeout area on
`/data1`. It contains 26 checksummed files. The SHA-256 of the retained
manifest is
`c25da95438b0fa0dc00d1ce3855d4bcb27f50fad0be55d3b5b865c12ac81eda4`.

## Closure behavior

- P0-01 publishes a checksummed physical QC-selected observation view; P0-02
  consumes that exact view and preserves its QC profile, cell index, matrix and
  MeasurementSpec lineage.
- P0-03, P0-04 and P0-05 reject ProductCase, QC, P0-02 view or shared
  StateRoleMap mismatches. Biological assignments remain versioned input data.
- P0-06 binds metric, unit, scope, state, stage and biological unit before
  applying configured review rules. P0-07 binds both ProductCases, their
  declared biological units and exact P0-08 readiness summaries.
- P0-08 preserves exact versioned MeasurementResult references and distinct
  measured, inferred, prior-only, negative, missing, unknown, unavailable and
  alert counts. P0-09 consumes the shared `evidence-family:<id>` namespace and
  derives active evidence versions from graph lifecycle.
- P0-10 verifies evidence/report correspondence but keeps public export
  ineligible because no package-owned release authority is configured. P0-11
  may only rebuild unchanged, allowlisted claim text as a human-review
  candidate; it cannot rewrite verified scientific text or emit a ready or
  exported state.
- P0-12 aggregates repeated observations within animal before equal-animal
  summaries and reports preparation linkage as a declaration, not a verified
  identity.

The synthetic handoff test calls P0-08, feeds its versioned profile directly
to P0-09, uses the resulting graph in P0-10, and confirms that shadow evidence
blocks the public claim and that P0-11 publishes no artifact. No manual field
translation layer is inserted between these tools.

## Results

| Gate | Result |
|---|---|
| Exact-source focused handoff | passed |
| Exact-source complete pytest | `1198 passed`, 2 dependency/fixture warnings |
| Clean-wheel focused handoff | passed |
| Clean-wheel complete pytest | `1198 passed`, 2 dependency/fixture warnings |
| Wheel | `bridge-0.2.0.dev0-py3-none-any.whl`; SHA-256 `b79e4de71b5e44fa91acccf5c64f0ede0be602a9eadd9b8123935926999f547f` |
| Import isolation | `bridge` resolved from the fresh temporary installation directory, outside the source tree |
| Dependency check | no broken requirements |
| Tool discovery | exactly 12; all 12 `implemented` |
| Generated projections | Schema, Tool Card and P0-10 benchmark were current and byte-identical across two renders |
| Public/package parity | passed for all registered Schemas and 12 Tool Cards |
| Knowledge validation | valid; 354 methods, 396 bindings, no dangling refs, 0 formal-eligible methods |
| Repository policy | passed |
| LFS pointer scan | 0 pointers |
| Temporary server workspace | removed after validation; retained evidence and wheel were not removed |

The exact server environment did not include the optional `build` frontend.
The first archived attempt therefore stopped after its successful source suite.
The final run used `pip wheel --no-build-isolation` in a disposable workspace,
installed the resulting wheel into a new temporary directory and preserved the
earlier failed log. The server also lacked `rg`; the LFS scan was rerun with
`grep` and the corrected result was retained. Neither workaround changed the
long-lived Python environment or the committed source.

The test total is three lower than the preceding local-integration snapshot
because this branch deliberately excludes the independent PR #28 commit and
its three tests.

## Release boundary

All packages remain `candidate`; P0-02 remains
`biological_review_in_progress`, all current `domain_score` values remain
`null`, and the knowledge catalog still has zero formal-eligible methods.
Passing this validation does not make any scientific method formal, authorize
publication, resolve biological review, make the stacked Draft PRs Ready, or
authorize merging.
