# Local Agent Runtime Architecture

## Purpose And Boundary

The BRIDGE local runtime turns a researcher-confirmed `ProductCase` and approved
`AnalysisPlan` into recoverable, auditable executions of registered high-level
Tool Packages. It coordinates work; it does not own scientific numbers, thresholds,
labels, evidence states or release decisions.

The architecture borrows two ideas from DeepSeek Harness: an append-only event log
as the durable source of runtime truth, and a guarded tool-execution pipeline. It
does not embed DeepSeek Harness, Cordis or a universal plugin system. BRIDGE keeps a
small Python application core and freezes the scientific contracts that determine
formal interpretation.

## System Shape

```text
User / Web / Agent
        |
        v
ProductCase -> deterministic PlanBuilder -> approved AnalysisPlan
                                              |
                                              v
                                  LocalWorkflowExecutor
                                              |
                         append RunEvent -> SQLite RunEventStore
                                              |
                                      status projection
                                              |
                                              v
                              ToolExecutionPipeline
                     eligibility -> plan/version gate -> run
                                  -> output validation
                                              |
                              ToolRun + LocalArtifactStore
                                              |
                         future Evidence/Report pipeline
```

The conversational Agent loop and the scientific workflow are separate state
machines. A conversation can clarify a case, explain a deterministic reason code or
request plan approval. Once approved, the scientific DAG is executed from the
frozen plan; model output cannot add a tool, change a version or overwrite a result.

## Durable Workflow Events

The SQLite event store appends ordered events per run:

| Event | Meaning |
|---|---|
| `run_submitted` | Stores the immutable approved plan snapshot. |
| `step_claimed` | One worker owns a ready step attempt. |
| `step_succeeded` | The attempt completed successfully. |
| `step_failed` | The attempt failed with explicit reason codes. |
| `run_resumed` | Retry-eligible failed steps return to pending. |
| `run_cancelled` | Pending or running work is cancelled. |

`RunStatus`, `StepStatus`, attempt counts and reason codes are projections, not
independently mutable rows. Appends use an expected sequence number so competing
workers cannot both commit the same transition. SQLite is the P0 durability target;
the executor remains single-worker even though event appends reject stale writers.
Persisted events carry an explicit schema version and event-specific payload
validation. Failed attempts require reason codes; retry exhaustion deterministically
marks dependent work as skipped while independent work remains claimable. Terminal
failed, succeeded, skipped or cancelled runs cannot be rewritten by cancellation.

## Case-Scoped Tool Pipeline

Each execution receives a scope derived from the approved plan. The scope pins the
case reference and case-contract digest, plan ID, immutable per-step request JSON,
Tool Package generation and version, implementation/environment/schema bindings,
MeasurementSpec, reference and prior references, and network/resource permissions.
Authorizations are keyed by step rather than Tool ID, so an asset-scoped plan may
contain multiple P0-01 steps without silently collapsing them.

The P0 pipeline is fixed:

```text
ToolRequest
  -> exact approved step/request envelope gate
  -> registered generation/version/environment/schema gate
  -> deterministic eligibility check
  -> registered Tool Package execution
  -> generation-aware ToolRun and provenance validation
  -> immutable returned outcome
```

Denial and ineligibility return explicit reason codes and do not invoke science
code. A scaffold remains `not_implemented`; missing evidence remains distinct from
a negative biological observation. Artifact hashing and evidence compilation remain
separate deterministic stages.

Planning expands P0-01 into deterministic per-asset steps. P0-08 and P0-09 are not
made reachable by assuming that unrelated scaffold tools produce their contracts;
they require explicit, checksummed structured-input bindings. Missing bindings are
recorded as a skip reason in the plan.

## Capability Seams

Only capabilities with a current or committed second implementation receive an
interface boundary:

- workflow event storage: in-memory for unit tests and SQLite for the local runtime;
- artifact storage: current local content-addressed implementation;
- Tool Package dispatch: current `ToolRegistry`.

An LLM provider, HTTP server, subprocess isolation and remote storage are future
work and are not predeclared as empty plugin interfaces.

## Local Artifact Integrity

Derived bytes are stored by SHA-256 under a configured local root. Reads and
deduplication revalidate the digest, reject non-regular objects, and fail closed on
symlinked staging, shard or object paths so neither reads nor writes can escape the
configured root. The store never rewrites a corrupt same-digest target as if
deduplication had succeeded.

## Implementation Status

| Component | Status |
|---|---|
| Immutable ProductCase and AnalysisPlan contracts | Implemented and tested |
| Deterministic PlanBuilder | Implemented and tested |
| In-memory RunEventStore | Implemented test adapter |
| Content-addressed LocalArtifactStore | Implemented and tested |
| RunEvent projection | Implemented and tested |
| SQLite RunEventStore | Implemented and recovery-tested |
| Case-scoped ToolExecutionPipeline | Implemented and tested |
| Background worker, FastAPI, Agent loop, Evidence and reporting | Not implemented |

No runtime infrastructure change promotes a scientific method, produces a domain
score, or authorizes clinical efficacy, safety, potency, GMP release or absolute
product-ranking claims.
