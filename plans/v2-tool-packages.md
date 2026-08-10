# BRIDGE v2 Tool Packages

| Field | Value |
|---|---|
| Branch | `v2-tool-packages` |
| Mode | `auto` |
| Status | `complete` |
| Owner | BRIDGE core |

## Goal

Rebuild BRIDGE around 12 high-level Tool Packages, complete the versioned method/source knowledge catalog, and deliver P0-01 Input Audit & QC as the first executable vertical slice.

## Non-goals

- Agent framework, HTTP/MCP service, job queue or Web implementation.
- Clinical, safety, potency, GMP or absolute product-quality conclusions.
- P0 domain scores before a separately validated `ScoreContract`.
- Direct execution of the remaining 11 scientific packages in this iteration.

## Frozen Decisions

- Python SDK plus JSON CLI is the collaboration boundary.
- Original inputs are immutable; every run writes a versioned artifact bundle.
- Markdown and YAML are knowledge facts; deterministic local full-text search is the first retrieval layer.
- All catalogued methods receive source-verified Method Packages; scientific status remains unchanged until benchmark.
- `h5ad` and 10x H5/MTX are the first P0-01 formats.
- Candidate scRNA/snRNA MeasurementSpec templates require explicit selection.

## Tasks

- [x] Create isolated branch and archive legacy implementation.
- [x] Add repository governance, stable documentation and public contracts.
- [x] Add 12 Tool Package manifests and non-implementation behavior.
- [x] Build normalized Method/Source Cards and retrieval index.
- [x] Implement P0-01 with immutable artifacts and registered visualizations.
- [x] Run unit, CLI, privacy, knowledge and server integration verification.

## Acceptance

- Registry discovers exactly P0-01 through P0-12.
- Only P0-01 can create a `MeasurementResult`; all other runs reject with `not_implemented`.
- Every master-registry row resolves to a canonical Method Package and source record.
- P0-01 supports declared h5ad and 10x count inputs without modifying them.
- No candidate MeasurementSpec produces a formal score or frozen-quality claim.
- All public files pass path, identifier, source, Schema and documentation checks.

## Decision Record

- The previous Step1-Step3 implementation is historical and has no compatibility requirement.
- Existing PRD score language describes a possible future contract. Until a score contract passes independent validation, current output remains `domain_score=null`.

## Verification Record

- Server test suite: 50 passed.
- Registry: exactly 12 packages; P0-01 is executable and P0-02 through P0-12 return `not_implemented` without scientific payloads.
- Knowledge snapshot: 396 source bindings, 354 canonical Method Packages and 385 verified public Source Cards, with no dangling references.
- Generated catalog, cards and schemas are deterministic across consecutive rebuilds.
- P0-01 completed immutable scRNA and snRNA server integration runs using separate candidate MeasurementSpecs.
- Repository policy, privacy, schema, wheel-install and Conda-contract checks passed.
