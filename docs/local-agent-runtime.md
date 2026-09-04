# Local Runtime Core

BRIDGE includes a small, framework-neutral runtime core for executing approved
Tool Package requests. It is infrastructure for the future Agent, not a complete
conversational Agent or Web service.

## Contracts

| Contract | Purpose |
|---|---|
| `CaseInputBundle` | Immutable envelope for user-uploaded local assets and checksums |
| `AnalysisPlan` | Ordered batch of exact Tool Package requests |
| `PlanApprovalReceipt` | Content-bound record that an external authority approved one plan |
| `ToolExecutionScope` | Runtime allowlist derived from the approved plan |
| `StepClaim` | Attempt-specific ownership token for one workflow step |
| `StepOutcomeReceipt` | Digest and artifact references for one validated `ToolRun` |

`CaseInputBundle` is a transport envelope. It does not replace or redefine the
scientific `ProductCase` contract consumed by Tool Packages.

## Planning

`PlanBuilder` creates one P0-01 request per uploaded asset by default. Every
downstream request must already be materialized by the caller and may declare
explicit dependencies on earlier requests. The planner does not infer a fixed
12-tool chain, invent scientific objects, or turn missing inputs into values.

Each executable step pins:

- the canonical request JSON and SHA-256;
- Tool Package version, input/output schemas, environment, implementation state,
  scientific status and result schema when applicable;
- the approved output directory and its filesystem identity.

An ineligible request is represented as a skipped step with reason codes. It is
not silently rewritten into an executable request.

## Approval and execution

`approve_plan` attaches a typed receipt to the exact plan digest. The caller is
responsible for authenticating the approver and authorizing the action before
creating that receipt.

`ToolExecutionPipeline` accepts only requests present in the approved plan. It
rechecks the request digest, Tool Package bindings, normal eligibility,
checksummed inputs, output-directory identity and result schema before accepting
a run. Tool failures remain tool failures; they do not become biological
conclusions.

## Workflow persistence

`LocalWorkflowExecutor` coordinates one local worker through append-only events.
A step must be claimed before execution. Claim identifiers and attempt numbers
fence stale workers after recovery, and successful completion requires a
validated `ToolRun` receipt rather than a caller-supplied boolean.

`SQLiteRunEventStore` is an optional local event store. Its directory and
database files must be private to the current user, and incompatible event
schemas fail closed. The in-memory store is available for ephemeral use.

Workflow status describes execution only. A succeeded run does not imply
biological readiness, formal scientific release, efficacy, safety, potency or
GMP suitability; scientific readiness remains `not_assessed` and
`domain_score` remains `null`.

## Artifacts

`LocalArtifactStore` can store byte artifacts by content digest and return
immutable references. It is deliberately separate from Tool Package execution:
the runtime does not copy arbitrary result paths into the store or expose files
through a network service.

## Current boundary

| Included | Not included |
|---|---|
| Immutable upload envelope and approved execution plan | Conversation or model-provider integration |
| Explicit-request planning and normal Tool Registry gates | Dynamic scientific dependency inference |
| Claim-fenced, event-sourced local workflow | Distributed workers, queues or Web APIs |
| Private SQLite persistence and optional local CAS | Authentication, authorization UI or public download service |

Agent orchestration remains responsible for constructing valid scientific input
objects, resolving deployment-owned resources, asking users for missing
metadata, and presenting deterministic Tool Package results without changing
their evidence state.
