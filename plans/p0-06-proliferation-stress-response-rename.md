# P0-06 Proliferation & Stress Response Naming Sync

## Status

`awaiting_review`

## Biological goal

Make clear that P0-06 examines stage-conditioned proliferation, stress-response and related transcriptomic programs on top of upstream cell-state and composition evidence. It does not repeat cell-state assignment or off-target composition, and it does not claim manufacturing-process integrity, GMP compliance, product release, safety or potency.

## Scope

- Replace the working display name `Process Integrity` with `Proliferation & Stress Response` in current user-facing documents, P0-06 specifications, Tool Cards and catalog module labels.
- Rename the candidate task-card path and candidate output object to match the working name.
- Regenerate both Tool Card projections from their maintained source.
- Record the rationale and compatibility boundary in the decision log.
- Publish the isolated change as a Draft PR against `main`.

## Non-goals

- Do not change Tool ID `P0-06` or Task ID `TASK-PROCESS-v0.1`.
- Do not change the program inventory, input requirements, review-flag rules, evidence semantics or module ownership.
- Do not introduce a `ScoreContract`; `domain_score` remains `null` and review flags remain `shadow`.
- Do not rewrite historical `source_ref` paths whose filenames record the original artifact provenance.
- Do not merge the Draft PR as part of this task.

## Acceptance evidence

- Current labels and catalog module values use `Proliferation & Stress Response`.
- The original artifact-path token is retained only inside immutable historical `source_ref` values.
- Tool Card projections are byte-identical and point to the renamed task card.
- The packaged knowledge snapshot is deterministically regenerated after the P0-06 catalog terminology update.
- Tool discovery reports 12 packages and P0-06 version `0.1.1` with the new display name.
- Tests, knowledge validation, repository policy and whitespace checks pass.
- The GitHub change remains a Draft PR awaiting review.

## Validation evidence

Validated locally on 2026-08-12 from an isolated branch based on `origin/main`:

- Tool Card regeneration and knowledge-catalog regeneration were each repeated with identical outputs; packaged knowledge SHA-256: `60bb12f3e9f95bd31e1a8ac190ed3edcb2ddc62ef84a52ac8280990874400f62`.
- Wheel build completed, and the built wheel reports P0-06 name `Proliferation & Stress Response`, version `0.1.1`, with a valid packaged knowledge snapshot.
- `python -m pytest -q`: 192 passed, with three pre-existing warnings.
- Tool discovery: 12 packages; P0-06 remains `scaffold` / `candidate`.
- Knowledge validation: valid, 396 bindings, no dangling method or source references.
- Repository policy and `git diff --check`: passed.
