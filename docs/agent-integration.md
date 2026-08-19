# Agent Team Integration

## Ownership

| BRIDGE science/tool team | Agent/Web team |
|---|---|
| Scientific contracts, Tool Packages, Method/Source knowledge, MeasurementSpecs, deterministic results, artifacts and validation | Conversation, orchestration, multi-Agent coordination, Web UI, task queue, authentication, permissions and model-provider integration |

The Agent calls P0-01 through P0-12 as high-level tools. It does not assemble Scanpy, R packages, foundation models or database queries itself.

## Stable Entry Points

- Python: `list_tools`, `describe_tool`, `validate_request`, `run_tool`, `search_knowledge`.
- CLI: `bridge-tool list`, `describe`, `validate`, `run`, and `knowledge search`.
- Language-neutral contracts: `schemas/`.
- Requests: `examples/requests/`.
- Tool behavior and refusal rules: `tool_packages/P0-XX/README.md`.

## Required Agent Flow

1. Call `describe` and construct a versioned `ToolRequest` from user-confirmed metadata.
2. Call `validate`; present only reason codes that require user action.
3. Call `run` only when eligible and authorized.
4. Treat `not_implemented`, `not_assessed`, `unavailable`, `unknown`, `negative` and `alert` as distinct states.
5. Render only registered artifacts and preserve denominators, units, versions and evidence references.
6. Use knowledge search for planning and explanation; never turn retrieval rank into scientific evidence weight.
7. Declare `source_family_id` so the tool can exclude same-family references, and resolve logical QC/reference IDs through deployment-owned catalogs.

## Local Application Skeleton

The Python package includes a minimal, framework-neutral application boundary:

- `bridge.domain` defines immutable `ProductCase`, `AnalysisPlan` and plan-step
  objects. Sample records must point to declared assets and preserve preparation,
  replicate, batch, timepoint, data-role and sampling-context fields explicitly.
- `bridge.planner.PlanBuilder` produces a deterministic P0 plan from a confirmed
  case and the packaged Tool Registry. A missing MeasurementSpec, ineligible input,
  scaffold package or blocked dependency is represented as a skipped step with a
  reason code rather than an invented result.
- `bridge.workflow.LocalWorkflowExecutor` provides the single-process state
  machine for approved plans. It supports dependency-aware claiming, cancellation,
  bounded retry and resume without rerunning succeeded steps. State is rebuilt
  from append-only RunEvents; `SQLiteRunEventStore` persists them across process
  restarts while `InMemoryRunEventStore` supports isolated tests. This remains a
  single-worker executor and does not claim background-daemon behavior.
- `bridge.runners.ToolExecutionPipeline` derives a case scope from an approved
  plan and rejects calls outside that plan, with mismatched Tool Package or
  MeasurementSpec versions, or failing registry eligibility before science code
  executes. Returned `ToolRun` objects are structurally round-tripped before use.
- `bridge.storage.LocalArtifactStore` writes derived bytes beneath one configured
  root, addresses them by SHA-256 and verifies content without repairing or
  rewriting a mismatch. Returned metadata uses relative paths.

The scientific planner, workflow, pipeline and Tool Packages do not invoke an LLM.
The separate `bridge-agent` entry point can make one bounded conversational model
call; it cannot create formal Evidence Records, render reports, expose HTTP routes,
start a background worker, approve a plan or promote any scientific package. Tool
execution remains owned by the registered high-level Tool Package APIs above.

P0-01, P0-02, P0-08 and P0-09 are executable candidate packages. P0-02 emits shadow Cell-State Evidence unless its `MeasurementSpec` names a signed `CellStateReleaseManifest`; draft review cards or benchmark results never become formal labels. P0-08 accepts only immutable, checksum- and Schema-bound upstream evidence objects, applies Data Readiness → Model Robustness → Prior Applicability → sufficiency, and emits no measurements or domain score. A scientifically incomplete but contract-valid P0-08 case returns `not_assessed`; malformed inputs fail eligibility. P0-09 compiles accepted atomic records and explicit missing requirements into immutable JSON/Parquet Case or Comparison Evidence Graphs. Its Agent surface exposes only seven bounded read-only queries; callers cannot submit arbitrary graph queries or writes. Rejected sibling records yield a traceable `partial` bundle without entering the graph, while top-level contract failures publish nothing. P0-03 through P0-07 and P0-10 through P0-12 deliberately return `not_implemented` without measurements. HTTP, MCP and queue adapters may wrap the same JSON contracts later without changing scientific semantics.

Reference snapshots are built and validated by the BRIDGE science team through `bridge-reference`. Agent deployments may resolve and consume a frozen snapshot, but cannot build, edit or substitute one. Candidate snapshots require an explicit science-only runtime flag and are rejected by default.

## DeepInfer Conversational Boundary

The local Agent has one concrete synchronous DeepInfer integration. It reads the
OpenAI-compatible API root from `DEEPINFER_BASE_URL`, optionally reads
`DEEPINFER_API_KEY`, and pins the request model to
`deepseek-v4-flash-0731`. Credentials and the configured URL are not returned in
the `AgentTurn`, error payload or audit record.

`bridge-agent` accepts one `AgentTurnRequest` JSON file, or `-` for stdin:

```json
{
  "classification": "public_safe",
  "user_message": "Explain why this deterministic status is unavailable.",
  "public_safe_context": [
    {
      "context_id": "status-summary",
      "classification": "public_safe",
      "content": "score_state=unavailable"
    }
  ]
}
```

```bash
bridge-agent --request agent-turn.json
```

The explicit `public_safe` classification is a caller assertion, not automatic
redaction. The entire user message and every context item leave the local process
for the configured provider; raw assets, private manifests, filesystem paths and
internal logs must not be placed in this request.

The provider request contains text messages only: no `tools`, `tool_choice`,
Tool Registry handle or plan-approval capability. The validated response is an
`AgentDecision` with an explanation, a constrained intent, text-only proposed
actions and a confirmation flag. `AgentTurn.model_call` records the provider
request ID, pinned model, finish reason, token usage, latency, canonical request
SHA-256 and canonical response SHA-256 without persisting credentials or prompt
text. Model output remains advisory and cannot be converted into a ToolRequest or
approved AnalysisPlan by this component.

This first boundary is one-shot and synchronous. It does not provide streaming,
conversation persistence, automatic retry, background execution, function calling
or model-authored reports.

## Failure Boundary

The Agent may explain a deterministic result but cannot edit numerical values, thresholds, evidence states, hashes or identifiers. Missing metadata triggers a targeted question; tool or data failure never becomes a biological product conclusion.
