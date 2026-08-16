# Event-Sourced Local Runtime

## Goal

Replace the process-local workflow state with an append-only SQLite event store and
add a case-scoped, deterministic tool-execution pipeline. Preserve all existing
scientific states and Tool Package behavior.

## Scope

- Define immutable, versioned workflow events and a deterministic status reducer.
- Provide in-memory and SQLite event stores with expected-sequence concurrency
  checks.
- Refactor `LocalWorkflowExecutor` to rebuild state from stored events.
- Prove that a new executor instance resumes the same SQLite-backed run.
- Gate tool execution by approved plan membership, version and registry eligibility.
- Synchronize stable repository documentation and the BRIDGE P0 design document.

## Non-goals

- Dynamic scientific plugins or runtime patching of frozen contracts.
- A multi-worker scheduler, message broker or distributed transaction protocol.
- FastAPI, Web UI, authentication, LLM provider integration or background daemon.
- Evidence compilation, report rendering, Claim Verifier or public-safe export.
- Promotion of any candidate, benchmark, shadow or scaffold scientific result.

## Definition Of Done

- Run state is reconstructed solely from ordered events.
- SQLite rejects stale sequence appends and preserves events across connections.
- Succeeded steps are not rerun after process restart or resume.
- A tool outside the approved plan, with a mismatched version, or failing
  eligibility never reaches its executor.
- The existing and new test suites plus repository policy gates pass.
- Every commit changes at most five files and represents one functional unit.

## Progress

- [x] Freeze architecture, scientific boundary and validation plan.
- [ ] Implement event contracts and projection.
- [ ] Implement in-memory and SQLite event stores.
- [ ] Refactor and recovery-test the workflow executor.
- [ ] Implement and test the tool-execution pipeline.
- [ ] Synchronize documentation and record validation evidence.
