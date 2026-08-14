# Evidence Runtime Simplification

| Field | Value |
|---|---|
| Branch | `evidence-runtime-simplification` |
| Baseline | `c7a9c569eea1e48d3e4a236c62968e428ea7eb4b` |
| Status | `draft_review` |

## Motivation

P0-08 and P0-09 now provide two real callers of the same structured-input runtime mechanics. Their scientific rules differ, but strict JSON loading, checksummed regular-file reads, immutable-input checks, typed failed runs, role selection and canonical JSON do not. Keeping those mechanics twice increases review and regression cost without adding scientific capability.

## Frozen interfaces and non-goals

- Keep all 12 Tool IDs, public JSON Schema URIs and bytes, Tool Cards, CLI/SDK entry points, reason codes, artifact filenames, canonical hashes and successful bundle bytes unchanged.
- Keep P0-08/P0-09 scientific validation, binding, graph and reconciliation rules in their owning modules.
- Keep P0-01/P0-02 on the v0.1 runtime; do not introduce a plugin framework or migrate another package.
- Keep `domain_score=null`, `score_state=unavailable`, candidate/shadow status and `formal_eligible=false`.
- Do not add a new scientific module or perform a real ProductCase run.

## Work

1. [x] Add one private shared module for mechanics already used by both P0-08 and P0-09.
2. [x] Replace duplicated adapter implementations rather than layering wrappers over them.
3. [x] Delete dead production helpers and make Schema export consume each module's existing `PUBLIC_SCHEMA_MODELS` source.
4. [x] Remove completed branch plans from the active-plan index and repository.
5. [x] Keep regression tests at the public adapter/registry/query seams; add only parity tests needed to prove the refactor.

## Acceptance

- The touched production/runtime code is net smaller; any shared interface must serve both adapters.
- Focused P0-08/P0-09 tests and the complete source suite pass.
- Existing golden run IDs, result payloads and bundle bytes remain stable for representative success, failure and repeat-run fixtures.
- All 49 public and packaged Schemas retain byte parity and regenerate without drift.
- Wheel build/install, 12-tool discovery, knowledge validation, repository policy and `git diff --check` pass.

## Risks

The high-risk seams are failure fingerprints, semantic input identity, immutable publication and path/checksum handling. Changes at those seams are accepted only with before/after parity evidence; cosmetic function splitting without net deletion is out of scope.

## Validation on 2026-08-14

- Independent review reproduced one P0-08 error-taxonomy drift for a dangling
  structured-input symlink (`not_found` before the refactor versus
  `not_regular_file` after it). The shared loader now accepts the caller's
  verified-input reader, P0-08 retains its existing classification, and a
  regression assertion covers the boundary without changing P0-09 behavior.
- Post-review focused shared/runtime/P0-08/P0-09 tests: 683 passed. The complete
  local source suite remains 897 passed with the same three dependency warnings;
  GitHub wheel/merge validation must be rerun for the amended head.
- Net repository change is 82 fewer lines after the review fix, this plan and
  focused shared-seam regression coverage; the touched runtime/tooling
  implementation is 134 lines smaller.
- The pre-refactor and post-refactor representative P0-08/P0-09 success bundles and typed failures have the same normalized summary SHA-256: `10c07f3cf2b8b6f770bf07b30ca7fe5bc328ca5102936e03a596c24b178d5a47`.
- Schema export regenerated 49 public plus 49 packaged Schemas with no byte drift; Tool Card rendering also produced no diff.
- A clean Python 3.12.13 environment installed the final wheel with all `qc,test,freeze,evidence` extras; dependency check passed and the installed wheel completed all 897 tests.
- Installed-wheel discovery reports 12 tools; knowledge validation is valid with no dangling references and zero formally eligible methods. Repository policy, compilation and `git diff --check` pass.

The branch is ready only for Draft PR review. This refactor does not authorize a real ProductCase run, scientific promotion or merge.
