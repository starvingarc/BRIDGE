# Local Agent Skeleton

## Goal

Create the smallest local application backbone that turns a researcher-confirmed
product case into an immutable P0 analysis plan, executes its registered steps in
dependency order, and stores derived artifacts with content hashes.

The skeleton must preserve sample/preparation identifiers and explicit missing
metadata. It must not infer biological roles from filenames or promote scaffold,
candidate, shadow, or unavailable results into formal evidence.

## Scope

- Add immutable `ProductCase`, `AnalysisPlan`, and plan-step contracts.
- Build plans deterministically from the existing Tool Registry.
- Add an in-process workflow executor with dependency, cancellation, retry, and
  resume state transitions suitable for tests and a future SQLite adapter.
- Add a content-addressed local artifact store that never modifies source inputs.
- Cover the boundaries with synthetic contract and recovery tests.

## Non-goals

- FastAPI routes, a Web UI, an LLM coordinator, or authentication.
- SQLite/SQLAlchemy persistence, a background worker process, or subprocess tool
  isolation.
- New scientific methods, thresholds, references, scores, Evidence Records,
  claims, reports, or public-safe exports.
- A generic plugin system or distributed workflow abstraction.

## Definition of Done

- A confirmed case with declared assets and sample hierarchy produces the same
  frozen plan for the same registry snapshot.
- Only implemented and eligible Tool Packages can enter executable plan steps;
  scaffold packages remain explicitly skipped with reason codes.
- The executor cannot claim a step before its dependencies succeed, and a failed
  run can be resumed without rerunning succeeded steps.
- Stored artifact bytes are addressed and verified by SHA-256; mismatches are
  reported without rewriting the artifact.
- Every commit contains at most five files and represents one minimal functional
  unit.

## Validation

Run and record final results before delivery:

```bash
python -m pytest -q
python -m bridge.toolkit.cli list --json
python -m bridge.toolkit.cli knowledge validate
python tools/check_repository.py
git diff --check
```

## Progress

- [x] Freeze scope, non-goals, and acceptance boundaries.
- [ ] Add case and plan contracts.
- [ ] Add deterministic plan construction.
- [ ] Add local workflow execution and recovery.
- [ ] Add local artifact storage and verification.
- [ ] Record final validation evidence.
