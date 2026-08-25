# Agent Team Integration

> [!NOTE]
> This document describes the target Agent/tool integration boundary. The
> current `main` branch exposes the tool-side contracts and 12 deterministic P0
> packages; the end-to-end conversational Agent, Web UI and orchestration runtime
> are not yet integrated. Tool availability alone is not a complete BRIDGE
> product workflow.

## Ownership

| BRIDGE science/tool team | Agent/Web team |
|---|---|
| Scientific contracts, Tool Packages, Method/Source knowledge, MeasurementSpecs, deterministic results, artifacts and validation | Conversation, orchestration, multi-Agent coordination, Web UI, task queue, authentication, permissions and model-provider integration |

The completed product's Agent calls P0-01 through P0-12 as high-level tools. It
does not assemble Scanpy, R packages, foundation models or database queries
itself.

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

## Package Flow

```text
P0-01 → P0-02 → P0-03 / P0-04 / P0-05 / P0-06
                         ↓
                      P0-08 → P0-09 → P0-10 → P0-11

P0-07 compares multiple precomputed product-evidence bundles.
P0-12 is an optional, independent graft branch.
```

| Stage | Agent responsibility | Result boundary |
|---|---|---|
| P0-01–P0-02 | Supply declared expression, metadata and deployment-resolved reference/QC bindings | P0-02 remains shadow without a signed `CellStateReleaseManifest` |
| P0-03–P0-06 | Supply checksummed, externally versioned biological roles, windows, programs and precomputed evidence | Executors do not invent state roles, thresholds, biological age, spatial location or safety claims |
| P0-07 / P0-12 | Preserve independent preparation or graft units and explicit linkage | Comparison is descriptive; graft never backfills pre-transplant evidence |
| P0-08–P0-09 | Preserve exact upstream objects, evidence families, missing requirements and bounded graph access | No new measurement, score, arbitrary graph query or write |
| P0-10–P0-11 | Preserve the structured report, package-owned authority, receipt and candidate hash | Verification is correspondence, and export is a local JSON write rather than release or upload |

The [Tool Package guide](tool-packages.md) gives the purpose, input, output,
refusal behavior and documentation path for every module. The corresponding
[Tool Card](../src/bridge/tool_packages/cards/) remains the detailed runtime
contract. HTTP, MCP and queue adapters may wrap the same JSON contracts later
without changing scientific semantics.

Reference snapshots are built and validated by the BRIDGE science team through `bridge-reference`. Agent deployments may resolve and consume a frozen snapshot, but cannot build, edit or substitute one. Candidate snapshots require an explicit science-only runtime flag and are rejected by default.

## Failure Boundary

The Agent may explain a deterministic result but cannot edit numerical values, thresholds, evidence states, hashes or identifiers. Missing metadata triggers a targeted question; tool or data failure never becomes a biological product conclusion.
