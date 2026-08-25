# High-level Tool Contract

## Collaboration Boundary

BRIDGE currently exposes 12 high-level Tool Packages through a Python SDK and
JSON CLI. They are the deterministic capability layer for the planned scientific
Agent, not the complete product experience. Agent and Web implementations
consume these contracts and do not call individual bioinformatics packages
directly; executing a tool by itself is not an end-to-end BRIDGE evaluation.

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
| `MeasurementResultV2` | Standalone v0.2 raw measurement with spec version, unit, source run, typed interval metadata and explicit unknown scope |
| `MeasurementSpecV2` | Additive v0.2 measurement context with controlled biological analysis and independence units; cell/nucleus remains an observation-unit declaration |
| `QCReadinessProfileV2` / `CellStateEvidenceProfileV2` | Additive content-addressed data-view and upstream-profile bindings; v0.1 profile schemas remain unchanged |
| `DataViewBinding` | Content-addressed matrix view, observation set and optional BiologicalUnitManifest binding |
| `BiologicalUnitAssignmentArtifact` / `BiologicalUnitManifest` | Checksummed observation rows plus analysis-unit and independence-group lineage; P0-01 may only declare it |
| `ProductCase` | Versioned product instance bound to one definition, measurement contract and optional exact biological-unit manifest |
| `ProductDefinitionCard` | Versioned product definition and external StateRoleMap reference; it does not freeze state assignments in code |
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

The existing v0.1 models and schemas remain the contract for current P0-01 and P0-02 behavior. A v0.2 package declares `bridge://schemas/tool-request/v0.2` and `bridge://schemas/tool-run/v0.2`. Implemented v0.2 packages additionally bind a non-empty method set, one adapter under `bridge.tool_packages.*`, and a result schema. Scaffold v0.2 packages bind neither adapter nor result schema. The registry selects the request model after reading `tool_id`; the CLI command and Python SDK entrypoints do not change. A Python caller that manually supplies the wrong request-model generation receives a structured refusal before adapter or executor resolution: `tool_request_v2_required` for a v1 request sent to a v0.2 package, or `tool_request_v1_required` for the inverse. `validate_request` returns an ineligible `EligibilityResult`; `run_tool` returns a failed envelope matching the request object that actually arrived, so the refusal remains serializable.

`ToolRunV2.measurements` intentionally remains bound to the existing `MeasurementResult`; its public v0.2 Schema bytes are unchanged. `MeasurementResultV2` is a separate structured contract for modules that explicitly declare it, and is not silently substituted into the run envelope. It requires an exact measurement-spec version, paired finite numerator/denominator and source-run fields, a positive denominator, finite ordered intervals, null values for `missing`/`unavailable`, and a controlled scope for `unknown`. Measurement-level unknowns carry no quantitative value; identity- or role-level uncertainty may retain an observed value while preserving that narrower uncertainty. `domain_score` remains null and `score_state` remains unavailable.

The shared P0 lineage spine separates observations, analysis units and independent groups. A capture or graft unit is a technical/within-subject unit and cannot be declared an independence group. Each checksummed assignment artifact is parsed row by row: its observation-set digest, typed hierarchy, analysis units, independence groups and unused declarations must agree with the manifest. One biological identity cannot be split into artificial replicate groups by changing only its object version, and a declared manufacturing-lineage unit cannot map to conflicting parents. Pooling or multiplexing requires a future explicit, checksummed contract rather than an ambiguous manifest. P0-01 may generate only `declared` lineage. A `reviewed` or `frozen` label and review reference are trace metadata, not authority; release-sensitive consumers must verify a package-owned typed receipt. `ProductDefinitionCard` therefore remains `draft` in this contract. A single-source ProductCase binds an explicit sample or preparation source, and every manifest binding must resolve to that same source together with the exact manifest checksum, independence scope and complete independence-group set. `MeasurementSpecV2` then binds its controlled analysis and independence kinds to the manifest; its inherited free-text `analysis_unit` remains descriptive compatibility metadata. These contracts record provenance and fail closed; they do not choose mutable biological roles, thresholds, markers or estimands.

The public JSON Schemas encode structural alternatives and null/pair constraints. Relations that JSON Schema cannot express safely—artifact-byte checksum verification, observation-set digest recomputation, row-to-manifest equality, source-unit membership and interval ordering/finite arithmetic—are mandatory checks in the BRIDGE standard loader and typed validators. A consumer must not treat raw Draft 2020-12 acceptance alone as scientific or release validation.

`StructuredInputRef` carries no inline payload. The supported runtime uses POSIX absolute paths, enforced in Python and public JSON Schema; Windows path syntax is not part of this contract. The checksum is exactly 64 lowercase hexadecimal characters. `application/json` is the only supported media type in v0.2 and is the default. The referenced object remains immutable and versioned outside the request envelope.

Before calling a v0.2 adapter, the registry requires every structured-input path to exist as a regular file, recomputes its SHA-256, parses strict JSON, resolves `schema_ref` only from packaged public schemas and validates the object with JSON Schema Draft 2020-12. Strict parsing rejects `NaN`, positive or negative infinity and duplicate keys at any object depth as `structured_input_invalid_json`; this shared integrity rule is compatible with, but does not replace, any narrower future P0-09 canonical-JSON contract. Ordinary failures return an ineligible result with one or more of these stable reason codes:

- `structured_input_not_found`
- `structured_input_not_regular_file`
- `structured_input_unreadable`
- `structured_input_checksum_mismatch`
- `structured_input_media_type_unsupported`
- `structured_input_invalid_json`
- `structured_input_schema_not_registered`
- `structured_input_schema_invalid`
- `structured_input_object_version_missing`
- `structured_input_object_version_mismatch`
- `structured_input_schema_validation_failed`

`object_version` binds to a top-level `object_version` or established top-level `version` property when the registered schema defines that property or the payload supplies it. A schema-defined version property is required, and every supplied top-level version property must equal the reference. Registered legacy objects whose schemas define neither property remain valid: for objects such as `QCReadinessProfile` and `MeasurementResult`, the reference's `object_version` is external schema-object version metadata. New structured objects, including future P0-08-specific objects, should define top-level `object_version` explicitly.

Within one request, `input_id` values and resolved input paths are unique. Exact duplicate references are also rejected by the public request schema; Python validation additionally rejects symlink/path aliases even when their roles or other metadata differ.

The runtime snapshots every verified input hash before adapter eligibility and execution, then recomputes all hashes after each adapter call. A changed, removed or replaced input fails with `input_asset_modified_during_run`; its adapter result or exception is discarded. Hash verification also runs when an adapter raises or returns the wrong type. If inputs remain unchanged, unrelated adapter exceptions and invalid return types remain execution errors rather than being swallowed.

Expression assets declare one of `analysis_ready`, `count_ready` or `droplet_ready`. `analysis_ready` accepts declared normalized h5ad expression; `count_ready` requires raw counts; `droplet_ready` requires a 10x raw-droplet object and currently performs contract audit only. Gene-set metrics bind either `var_names` or an explicitly declared `var` column; absent marker coverage returns `unavailable`, never zero.

## State Separation

- `implementation_state`: `scaffold`, `implemented`, `deprecated`.
- `execution_state`: `not_started`, `running`, `succeeded`, `partial`, `failed`, `skipped`, `not_implemented`.
- `scientific_status`: preserves registry values such as `candidate`, `shortlisted`, `benchmark`, `shadow`, `conditional`, `deferred`, `adopted`.
- `evidence_state`: `measured`, `inferred`, `prior_only`, `negative`, `missing`, `unknown`, `unavailable`, `alert`.

`not_implemented` is an engineering state and must not be represented as biological `unavailable`. A scaffold run returns no `MeasurementResult`.

## Artifact Rules

Original inputs are read-only. Each run creates a new bundle containing a manifest, structured results, tables, visualization payloads and optional derived data objects. Files include checksum, schema version and source references. A content change creates a new version; an old report remains reproducible.

The versioned JSON contracts in `src/bridge/resources/schemas/` are the language-neutral interface for Agent implementations. Pydantic models in `src/bridge/toolkit/contracts.py` and package-owned model modules are the Python sources used to generate those schemas.

For v0.2 implemented packages, the registry resolves only the package's declared adapter reference. The adapter implements the two-method `ToolPackageAdapter` protocol at the runtime seam. Returned runs must preserve request, tool version, implementation state and environment bindings. Successful and partial runs require both a non-null result and the exact registered result-schema reference declared by the package; every non-null result is validated with JSON Schema Draft 2020-12. Adapter/import/runtime failures from CLI `validate` or `run` are structured errors with exit code 4. The shared seam itself adds no scientific capability. P0-01 through P0-12 are executable engineering candidates; execution does not freeze a method, state, threshold, score or release claim.

P0-08 consumes only versioned upstream evidence objects. It applies Data Readiness, Model Robustness and Prior Applicability before selecting `not_assessed`, `insufficient`, `limited` or `sufficient` in the registered precedence order. It never reruns scientific analysis, emits a `MeasurementResult`, or makes a domain score available. Its module-specific input/result schemas and complete field contract are documented in the [P0-08 Tool Card](../src/bridge/tool_packages/cards/P0-08.md).

P0-09 consumes a compilation bundle, P0-08 profiles and versioned Evidence Family, Claim and reconciliation registries. It creates append-only `EvidenceRecord` and `EvidenceRequirement` facts, deterministic reconciliation records, Case or Comparison graph manifests, fixed-column Parquet node/edge tables and a Cytoscape projection. Missing evidence creates a requirement rather than a zero-valued record; shadow or exploratory evidence cannot become formal. JSON/Parquet remain authoritative, while NetworkX is limited to reconstruction, invariant checks and seven named read-only query helpers. LadybugDB is deferred shadow work and is not a release dependency. The complete interface and reason-code contract are documented in the [P0-09 Tool Card](../src/bridge/tool_packages/cards/P0-09.md).

Only `implemented` packages execute. A scaffold returns `not_implemented` with `tool_package_not_implemented`; a deprecated package is ineligible and returns a failed run with `tool_package_deprecated`. Neither state resolves or invokes an adapter.

P0-02 requests carry `source_family_id` plus logical `qc_profile_ref` and `measurement_spec_ref` identifiers. Same-family reference profiles are held out at runtime. Private reference paths remain in deployment-owned catalogs. Only frozen reference snapshots are accepted in Agent runtime; reference construction is a science-team operation.

Cell-State scientific commands are restricted to the BRIDGE science team: `bridge-benchmark cell-state prepare`, `prepare-birtele`, `audit-external-sources`, `run` and `summarize`. `prepare-birtele` and `audit-external-sources` establish checksummed external-source preparation and lineage exclusion only; their human-facing contract is [P0-02 external-source preparation](bridge_spec_v0.1/external_source_preparation.md). A pilot split cannot open locked assets; a locked split requires a signed `FreezeGateSpec`. Agent runtime cannot choose benchmark methods or thresholds.
