# Agent Team Integration

## Ownership

| BRIDGE science/tool team | Agent/Web team |
|---|---|
| Scientific contracts, Tool Packages, Method/Source knowledge, MeasurementSpecs, deterministic results, artifacts and validation | Conversation, orchestration, multi-Agent coordination, Web UI, task queue, authentication, permissions and model-provider integration |

The Agent calls P0-01 through P0-12 as high-level tools. It does not assemble Scanpy, R packages, foundation models or database queries itself.

## Stable Entry Points

- Python: `list_tools`, `describe_tool`, `validate_request`, `run_tool`, `search_knowledge`.
- CLI: `bridge-tool list`, `describe`, `validate`, `run`, and `knowledge search`.
- Language-neutral contracts: `src/bridge/resources/schemas/`.
- Requests: `examples/requests/`.
- Tool behavior and refusal rules: `src/bridge/tool_packages/cards/P0-XX.md`.

## Required Agent Flow

1. Call `describe` and construct a versioned `ToolRequest` from user-confirmed metadata.
2. Call `validate`; present only reason codes that require user action.
3. Call `run` only when eligible and authorized.
4. Treat `not_implemented`, `not_assessed`, `unavailable`, `unknown`, `negative` and `alert` as distinct states.
5. Render only registered artifacts and preserve denominators, units, versions and evidence references.
6. Use knowledge search for planning and explanation; never turn retrieval rank into scientific evidence weight.
7. Declare `source_family_id` so the tool can exclude same-family references, and resolve logical QC/reference IDs through deployment-owned catalogs.

P0-01, P0-02, P0-04, P0-05, P0-06, P0-08, P0-09, P0-10, P0-11 and P0-12 are executable candidate packages. P0-02 emits shadow Cell-State Evidence unless its `MeasurementSpec` names a signed `CellStateReleaseManifest`; draft review cards or benchmark results never become formal labels. P0-08 accepts only immutable, checksum- and Schema-bound upstream evidence objects, applies Data Readiness → Model Robustness → Prior Applicability → sufficiency, and emits no measurements or domain score. A scientifically incomplete but contract-valid P0-08 case returns `not_assessed`; malformed inputs fail eligibility. P0-09 compiles accepted atomic records and explicit missing requirements into immutable JSON/Parquet Case or Comparison Evidence Graphs. Its Agent surface exposes only seven bounded read-only queries; callers cannot submit arbitrary graph queries or writes. Rejected sibling records yield a traceable `partial` bundle without entering the graph, while top-level contract failures publish nothing. P0-10 checks a structured `ReportDraft` against one P0-09 graph manifest and packaged policy authority, then emits one receipt; internal correspondence does not make a report public-eligible, and public claims require cited formal Evidence. P0-11 accepts exactly four checksummed JSON inputs, rebuilds only allowlisted report fields, blocks deterministic leak canaries, and requires a candidate-hash confirmation before reporting `exported`; it writes locally and never uploads. P0-12 accepts either no graft objects or exactly one checksummed GraftCase, external GraftAssessmentSpec and precomputed GraftEvidenceBundle; it returns independent `not_provided` or descriptive candidate/shadow evidence and never backfills pretransplant domains. P0-03 and P0-07 deliberately return `not_implemented` without measurements. HTTP, MCP and queue adapters may wrap the same JSON contracts later without changing scientific semantics.

P0-05 accepts exactly six checksummed JSON objects and applies an external `StateRoleMap` and `OffTargetAssessmentSpec` to a precomputed evidence bundle. It never infers product roles from labels or embeds biological thresholds; incomplete coverage withholds fractions, zero observations do not establish absence, and missing rare-state calibration returns `cannot_exclude` or `not_assessed`.

P0-06 accepts seven checksummed structured objects and applies only external ProgramSpec stage, coverage, LOD and review rules to precomputed records. It returns descriptive shadow evidence; unresolved process metadata remains cannot_attribute, and an untriggered flag is not evidence of safety.

Reference snapshots are built and validated by the BRIDGE science team through `bridge-reference`. Agent deployments may resolve and consume a frozen snapshot, but cannot build, edit or substitute one. Candidate snapshots require an explicit science-only runtime flag and are rejected by default.

## Failure Boundary

The Agent may explain a deterministic result but cannot edit numerical values, thresholds, evidence states, hashes or identifiers. Missing metadata triggers a targeted question; tool or data failure never becomes a biological product conclusion.
