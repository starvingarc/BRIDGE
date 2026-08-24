# P0 Stack Peer-review Closeout

## Biological goal

Make the twelve registered P0 packages callable as one evidence-bounded workflow while keeping mutable state roles, developmental windows, metric rules and thresholds in versioned inputs rather than Python code.

## Review finding

Independent biology, single-cell and AI-for-science reviews rated Draft PRs #20–#27 as Major Revision. The blocking themes are: an unbound P0-01/P0-02 analysis population, independently configurable roles that can disagree across P0-03/P0-04/P0-05, cell or caller labels masquerading as biological replication in P0-06/P0-07/P0-12, loss of evidence lifecycle before P0-10, and caller-controlled publication authority in P0-10/P0-11.

## Scope

- Bind P0-01 and P0-02 through one checksummed, physically selected observation view and explicit sample/preparation lineage.
- Reuse a single ProductDefinition-bound StateRoleMap when P0-04 and P0-05 interpret target-related states.
- Bind observations to versioned metric, unit, biological unit and context definitions; aggregate repeated timepoints within biological units before between-unit summaries.
- Make missing, unknown, unavailable, negative and alert states remain distinct through P0-08–P0-10.
- Derive effective evidence lifecycle from the graph and fail closed where no trusted release authority exists.
- Disable free-text scientific rewrites in P0-11 v0.1 and permit only deterministic allowlisted projection.
- Add a synthetic no-manual-glue handoff test for the implemented workflow.

## Non-goals

- No biological state assignment, threshold, score, release decision or public disclosure decision is frozen in code.
- No new high-level Tool ID, plugin framework, signing service, clinical claim or non-null domain score.
- No local project execution and no use of `/data2`.

## Verification and stop

All project execution, schema rendering, source tests, clean-wheel tests and adversarial checks run on `/data1`. Exact final SHAs receive parallel biology, single-cell and AI4S review. Draft PRs remain Draft and merging remains a separate explicit authorization.
