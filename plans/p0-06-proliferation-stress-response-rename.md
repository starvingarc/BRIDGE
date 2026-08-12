# P0-06 Proliferation & Stress Response Naming Sync

## Status

`completed`

## Biological goal

Make clear that P0-06 examines stage-conditioned proliferation, stress-response and related transcriptomic programs on top of upstream cell-state and composition evidence. It does not repeat cell-state assignment or off-target composition, and it does not claim manufacturing-process integrity, GMP compliance, product release, safety or potency.

## Scope

- Replace the working display name `Process Integrity` with `Proliferation & Stress Response` in current user-facing documents, P0-06 specifications, Tool Cards and catalog module labels.
- Rename the candidate task-card path and candidate output object to match the working name.
- Regenerate both Tool Card projections from their maintained source.
- Record the rationale and compatibility boundary in the decision log.
- Publish the isolated change through a PR against `main`, beginning as Draft while required checks run.

## Non-goals

- Do not change Tool ID `P0-06` or Task ID `TASK-PROCESS-v0.1`.
- Do not change the program inventory, input requirements, review-flag rules, evidence semantics or module ownership.
- Do not introduce a `ScoreContract`; `domain_score` remains `null` and review flags remain `shadow`.
- Do not rewrite historical `source_ref` paths whose filenames record the original artifact provenance.
- Do not merge without separate explicit authorization after the synchronized change and required checks have been reviewed.

## Acceptance evidence

- Current labels and catalog module values use `Proliferation & Stress Response`.
- The original artifact-path token is retained only inside immutable historical `source_ref` values.
- Tool Card projections are byte-identical and point to the renamed task card.
- The packaged knowledge snapshot is deterministically regenerated after the P0-06 catalog terminology update.
- Tool discovery reports 12 packages and P0-06 version `0.1.1` with the new display name.
- Tests, knowledge validation, repository policy and whitespace checks pass.
- The required GitHub check passes on the reviewed head, and merge occurs only after separate explicit authorization.

## Validation evidence

Validated locally on 2026-08-12 from an isolated branch based on `origin/main`:

- Tool Card regeneration and knowledge-catalog regeneration were each repeated with identical outputs; packaged knowledge SHA-256: `60bb12f3e9f95bd31e1a8ac190ed3edcb2ddc62ef84a52ac8280990874400f62`.
- Wheel build completed, and the built wheel reports P0-06 name `Proliferation & Stress Response`, version `0.1.1`, with a valid packaged knowledge snapshot.
- `python -m pytest -q`: 192 passed, with three pre-existing warnings.
- Tool discovery: 12 packages; P0-06 remains `scaffold` / `candidate`.
- Knowledge validation: valid, 396 bindings, no dangling method or source references.
- Repository policy and `git diff --check`: passed.
- GitHub `repository-gates` run `31601011125` passed on reviewed head `9bd10f6`, including 192 tests, 12-tool discovery, knowledge validation, repository policy and committed-whitespace checks.
- After explicit merge authorization, PR #9 was squash-merged to `main` as `e7eab8c`; the merged tree `e936f01` is identical to the reviewed PR-head tree.
- Post-merge local verification on that exact tree repeated 192 tests, 12-tool discovery, knowledge validation, repository policy and `git diff --check` successfully. P0-06 remains `scaffold` / `candidate`, with shadow review and `domain_score=null`.
- The GitHub topic branch used the unprefixed name `p0-06-proliferation-stress-response` and was deleted automatically after merge. Draft PR #4 remains closed because GitHub closed it during the source-branch rename; PR #9 preserves and merges the same change lineage.
