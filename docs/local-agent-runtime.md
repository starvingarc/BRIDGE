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
machines. The current DeepInfer loop can clarify a case, explain a deterministic
reason code or suggest a plan, but it has no tool/function-call binding and no plan
approval method. Once a human-approved plan exists, the scientific DAG is executed
from the frozen plan; model output cannot add a tool, change a version or overwrite
a result.

## Durable Workflow Events

The SQLite event store appends ordered events per run:

| Event | Meaning |
|---|---|
| `run_submitted` | Stores the immutable approved plan snapshot and retry policy. |
| `step_claimed` | One worker owns a ready step attempt. |
| `step_succeeded` | The attempt completed successfully. |
| `step_failed` | The attempt failed with explicit reason codes. |
| `run_resumed` | Retry-eligible failed steps return to pending. |
| `run_recovered` | Atomically recovers interrupted work after worker ownership transfer. |
| `run_cancelled` | Pending or running work is cancelled. |

`RunStatus`, `StepStatus`, attempt counts and reason codes are projections, not
independently mutable rows. Appends use an expected sequence number so competing
workers cannot both commit the same transition. SQLite is the P0 durability target;
the executor remains single-worker even though event appends reject stale writers.
Persisted events carry an explicit schema version and event-specific payload
validation. Failed attempts require reason codes; retry exhaustion deterministically
marks dependent work as skipped while independent work remains claimable. Terminal
failed, succeeded, skipped or cancelled runs cannot be rewritten by cancellation.
Explicit recovery assumes the previous single worker is dead, uses the persisted
retry limit, and resolves all interrupted steps in one sequence-guarded event.
Schema-zero histories are normalized in memory without rewriting the append-only
rows; incompatible or unknown histories fail with a coordinate-bearing compatibility
error.

## Case-Scoped Tool Pipeline

Each execution receives a scope derived from the approved plan. The scope pins the
exact case identity/version and case-contract digest, plan ID, immutable per-step request JSON,
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
  -> generation-aware ToolRun, result-Schema and provenance validation
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
Structured P0-08/P0-09 inputs must bind the same exact ProductCase identity and
version as the approved scope. Case identities are hashed before use in local output
paths, so opaque IDs cannot alter directory structure.

## Conversational Model Boundary

`DeepInferClient` is the single concrete model integration. It reads
`DEEPINFER_BASE_URL`, uses optional bearer credentials from
`DEEPINFER_API_KEY`, and pins `deepseek-v4-flash-0731`. `LocalAgentLoop` sends
only an explicitly `public_safe` `AgentTurnRequest` and validates the model's JSON
response as a text-only `AgentDecision`. The whole turn is rejected before a model
call if the explicit classification or context contract is invalid.

Successful calls return provider/model identity, usage, latency and canonical
request/response hashes. They do not expose the credential, base URL or a raw
provider response envelope. Model calls are not RunEvents: scientific workflow
history continues to contain only approved-plan and deterministic execution facts.
The caller may separately persist an AgentTurn under an appropriate conversation
retention policy.

This boundary does not perform automatic DLP. Callers must not include raw data,
private sample identifiers, filesystem paths, private manifests or internal logs in
the turn. The client is synchronous and deliberately has no retry, streaming,
function calling, background-worker or conversation-store abstraction.

## Capability Seams

Only capabilities with a current or committed second implementation receive an
interface boundary:

- workflow event storage: in-memory for unit tests and SQLite for the local runtime;
- artifact storage: current local content-addressed implementation;
- Tool Package dispatch: current `ToolRegistry`;
- conversational model: one concrete DeepInfer client and one local text loop.

An HTTP server, subprocess isolation and remote storage are future work and are not
predeclared as empty plugin interfaces.

## Local Artifact Integrity

Derived bytes are stored by SHA-256 under a configured local root. Reads and
deduplication revalidate the digest, reject non-regular objects, and fail closed on
symlinked root components, staging, shard or object paths so neither reads nor writes
can escape the configured root. Root creation walks from the filesystem anchor with
directory descriptors instead of resolving caller-controlled ancestors. Verified
reads use an immediately unlinked snapshot created inside the anchored staging
directory and never copy plaintext to the system temporary directory. The store
never rewrites a corrupt same-digest target as if deduplication had succeeded.

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
| DeepInfer one-turn conversational Agent | Implemented and contract-tested |
| Background worker, FastAPI, persistent conversation, Evidence and reporting | Not implemented |

No runtime infrastructure change promotes a scientific method, produces a domain
score, or authorizes clinical efficacy, safety, potency, GMP release or absolute
product-ranking claims.
