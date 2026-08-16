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

## Case-Scoped Tool Pipeline

Each execution receives a scope derived from the approved plan. The scope pins the
case reference, plan ID, allowed Tool Package IDs and versions, MeasurementSpec,
reference and prior references, and network/resource permissions.

The P0 pipeline is fixed:

```text
ToolRequest
  -> registered tool and approved version gate
  -> deterministic eligibility check
  -> registered Tool Package execution
  -> ToolRun structural round-trip validation
  -> immutable returned outcome
```

Denial and ineligibility return explicit reason codes and do not invoke science
code. A scaffold remains `not_implemented`; missing evidence remains distinct from
a negative biological observation. Artifact hashing and evidence compilation remain
separate deterministic stages.

## Capability Seams

Only capabilities with a current or committed second implementation receive an
interface boundary:

- workflow event storage: in-memory for unit tests and SQLite for the local runtime;
- artifact storage: current local content-addressed implementation;
- Tool Package dispatch: current `ToolRegistry`.

An LLM provider, HTTP server, subprocess isolation and remote storage are future
work and are not predeclared as empty plugin interfaces.

## Implementation Status

| Component | Status |
|---|---|
| Immutable ProductCase and AnalysisPlan contracts | Implemented and tested |
| Deterministic PlanBuilder | Implemented and tested |
| In-memory workflow state machine | Implemented baseline; being replaced by events |
| Content-addressed LocalArtifactStore | Implemented and tested |
| RunEvent projection | In implementation on `local-dev-agent` |
| SQLite RunEventStore | In implementation on `local-dev-agent` |
| Case-scoped ToolExecutionPipeline | In implementation on `local-dev-agent` |
| Background worker, FastAPI, Agent loop, Evidence and reporting | Not implemented |

No runtime infrastructure change promotes a scientific method, produces a domain
score, or authorizes clinical efficacy, safety, potency, GMP release or absolute
product-ranking claims.
