# High-level Tool Contract

## Collaboration Boundary

BRIDGE exposes 12 high-level Tool Packages through a Python SDK and JSON CLI. Agent and Web implementations consume these contracts and do not call individual bioinformatics packages directly.

Every package supports:

- `describe`: return version, purpose, status, requirements and artifacts.
- `check_eligibility`: deterministically evaluate a request without running science code.
- `run`: execute only when `implementation_state=implemented` and eligibility passes.

## Required Objects

| Object | Purpose |
|---|---|
| `ToolPackageSpec` | Stable module identity, methods, environment, input/output and validation status |
| `ToolRequest` | Versioned request, asset declarations, MeasurementSpec and output location |
| `ToolRun` | Execution state, versions, input hash, messages and artifact manifest |
| `StructuredInputRef` | Immutable v0.2 object input reference with role, schema, object version, absolute local path, media type and SHA-256 |
| `ToolPackageSpecV2` | v0.2 package identity plus packaged adapter and structured-result schema bindings |
| `ToolRequestV2` | v0.2 request retaining asset inputs while adding schema-bound structured-object references |
| `ToolRunV2` | v0.2 run envelope binding successful or partial structured results to a declared result schema |
| `MeasurementResult` | Raw metric, denominator, interval, evidence and score state |
| `ArtifactManifest` | Immutable output files, media type, checksum and provenance |
| `VisualizationArtifact` | Chart component, data binding, Evidence IDs and render files |
| `KnowledgeHit` | Versioned method/source result returned by local retrieval |
| `AnnotationVocabulary` | Versioned L1/L2/L3 state hierarchy, aliases and unresolved labels |
| `ReferenceManifest` | Immutable source-aware reference snapshot and artifact checksums |
| `CellStateEvidenceProfile` | Shadow reference support, marker evidence, prediction sets and conflicts |
| `BiologicalReviewRecord` | Per-state biological definitions, marker review, exclusions and reviewer decisions |
| `CellStateBenchmarkSpec` / `BenchmarkSplitManifest` | Source/sample-aware pilot or locked benchmark contract |
| `FreezeGateSpec` | Human-signed thresholds fixed before locked assets are opened |
| `CellStateReleaseManifest` | Approved per-state release state and runtime method selection |

Implemented Tool Packages retain at least one selected `method_id`. Scaffold packages keep `method_ids` empty until an executable, benchmark-bound method contract exists; candidate catalog entries do not imply implementation.

The existing v0.1 models and schemas remain the contract for current P0-01 and P0-02 behavior. A v0.2 package declares `bridge://schemas/tool-request/v0.2` and `bridge://schemas/tool-run/v0.2`. Implemented v0.2 packages additionally bind a non-empty method set, one adapter under `bridge.tool_packages.*`, and a result schema. Scaffold v0.2 packages bind neither adapter nor result schema. The registry selects the request model after reading `tool_id`; the CLI command and Python SDK entrypoints do not change.

`StructuredInputRef` carries no inline payload. Its path must be absolute, its checksum is exactly 64 lowercase hexadecimal characters, and its media type is explicit (default `application/json`). The referenced object remains immutable and versioned outside the request envelope.

Expression assets declare one of `analysis_ready`, `count_ready` or `droplet_ready`. `analysis_ready` accepts declared normalized h5ad expression; `count_ready` requires raw counts; `droplet_ready` requires a 10x raw-droplet object and currently performs contract audit only. Gene-set metrics bind either `var_names` or an explicitly declared `var` column; absent marker coverage returns `unavailable`, never zero.

## State Separation

- `implementation_state`: `scaffold`, `implemented`, `deprecated`.
- `execution_state`: `not_started`, `running`, `succeeded`, `partial`, `failed`, `skipped`, `not_implemented`.
- `scientific_status`: preserves registry values such as `candidate`, `shortlisted`, `benchmark`, `shadow`, `conditional`, `deferred`, `adopted`.
- `evidence_state`: `measured`, `inferred`, `prior_only`, `negative`, `missing`, `unknown`, `unavailable`, `alert`.

`not_implemented` is an engineering state and must not be represented as biological `unavailable`. A scaffold run returns no `MeasurementResult`.

## Artifact Rules

Original inputs are read-only. Each run creates a new bundle containing a manifest, structured results, tables, visualization payloads and optional derived data objects. Files include checksum, schema version and source references. A content change creates a new version; an old report remains reproducible.

The versioned JSON contracts in `schemas/` are the language-neutral interface for Agent implementations. Pydantic models in `src/bridge/toolkit/contracts.py` are the Python source used to generate those schemas.

For v0.2 implemented packages, the registry resolves only the package's declared adapter reference. The adapter implements the two-method `ToolPackageAdapter` protocol at the runtime seam. Returned successful or partial runs must preserve the request/tool/version/implementation binding and use the exact result schema declared by the package. This adds shared runtime infrastructure only; it does not implement P0-08, P0-09 or any other scaffold package.

P0-02 requests carry `source_family_id` plus logical `qc_profile_ref` and `measurement_spec_ref` identifiers. Same-family reference profiles are held out at runtime. Private reference paths remain in deployment-owned catalogs. Only frozen reference snapshots are accepted in Agent runtime; reference construction is a science-team operation.

Cell-State scientific commands are restricted to the BRIDGE science team: `bridge-benchmark cell-state prepare`, `run` and `summarize`. A pilot split cannot open locked assets; a locked split requires a signed `FreezeGateSpec`. Agent runtime cannot choose benchmark methods or thresholds.
