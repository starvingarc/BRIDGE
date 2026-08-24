# P0 Stack Peer-review Closeout

## Biological goal

Make the twelve registered P0 packages callable as one evidence-bounded workflow while keeping mutable state roles, developmental windows, metric rules and thresholds in versioned inputs rather than Python code.

## Review finding

Independent biology, single-cell and AI-for-science reviews rated Draft PRs #20–#27 as Major Revision. The blocking themes are: an unbound P0-01/P0-02 analysis population, independently configurable roles that can disagree across P0-03/P0-04/P0-05, cell or caller labels masquerading as biological replication in P0-06/P0-07/P0-12, loss of evidence lifecycle before P0-10, and caller-controlled publication authority in P0-10/P0-11.

## Scope

- Bind P0-01 and P0-02 through one checksummed, physically selected observation view and a `declared` BiologicalUnitManifest; carrying lineage never certifies replication.
- Reuse a single ProductDefinition-bound StateRoleMap when P0-04 and P0-05 interpret target-related states.
- Bind P0-03–P0-07 to exact ProductCase-owned manifests; only externally reviewed/frozen independence groups can support P0-06/P0-07 group counts.
- Bind P0-08 and P0-09 through source-checksummed MeasurementResult v0.2 objects; callers cannot restate numeric evidence in P0-09 candidates.
- Bind observations to versioned metric, unit, biological unit and context definitions; aggregate repeated observations within independence group/animal/stratum before between-unit summaries.
- Make missing, unknown, unavailable, negative and alert states remain distinct through P0-08–P0-10.
- Derive effective evidence lifecycle from the graph and fail closed where no trusted release authority exists.
- Rename P0-11 semantics to Internal Review Projection, bind the exact producing P0-10 ToolRun and make unavailable authentication/release authority explicit.
- Separate P0-12 product/graft MeasurementSpecs, require externally reviewed graft lineage for assessment and forbid cross-stratum aggregation.
- Add a synthetic no-manual-glue handoff test for the implemented workflow.

## Non-goals

- No biological state assignment, threshold, score, release decision or public disclosure decision is frozen in code.
- No new high-level Tool ID, plugin framework, signing service, clinical claim or non-null domain score.
- No local project execution and no use of `/data2`.

## Verification and stop

All project execution, schema rendering, source tests, clean-wheel tests and adversarial checks run on `/data1`. Exact final SHAs receive parallel biology, single-cell and AI4S review. Draft PRs remain Draft and merging remains a separate explicit authorization.

The earlier `b6607aee6ea6930fe5b1baf5c4fc7020d92460d3` snapshot passed its
then-current gates but was reopened by cross-module peer review. It is not the
final closure evidence. The revised exact head must pass clean-wheel `/data1`
validation and independent biology, single-cell and AI4S re-review before the
Draft PR can be presented for merge authorization. Detailed evidence is
recorded in `docs/validation/p0_stack_peer_review_closeout_20260824.md`.
