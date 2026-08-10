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
| `MeasurementResult` | Raw metric, denominator, interval, evidence and score state |
| `ArtifactManifest` | Immutable output files, media type, checksum and provenance |
| `VisualizationArtifact` | Chart component, data binding, Evidence IDs and render files |
| `KnowledgeHit` | Versioned method/source result returned by local retrieval |
| `AnnotationVocabulary` | Versioned L1/L2/L3 state hierarchy, aliases and unresolved labels |
| `ReferenceManifest` | Immutable source-aware reference snapshot and artifact checksums |
| `CellStateEvidenceProfile` | Shadow reference support, marker evidence, prediction sets and conflicts |

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

P0-02 requests carry `source_family_id` plus logical `qc_profile_ref` and `measurement_spec_ref` identifiers. Same-family reference profiles are held out at runtime. Private reference paths remain in deployment-owned catalogs. Only frozen reference snapshots are accepted in Agent runtime; reference construction is a science-team operation.
