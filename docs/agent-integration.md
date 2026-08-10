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

P0-01 is the only executable scientific package in this branch. P0-02 through P0-12 deliberately return `not_implemented` without measurements. HTTP, MCP and queue adapters may wrap the same JSON contracts later without changing scientific semantics.

## Failure Boundary

The Agent may explain a deterministic result but cannot edit numerical values, thresholds, evidence states, hashes or identifiers. Missing metadata triggers a targeted question; tool or data failure never becomes a biological product conclusion.
