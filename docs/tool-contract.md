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
| `DataViewBinding` | Exact checksummed matrix artifact, semantics, cell count and deterministic cell-index checksum selected by QC |
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
| `ProductCase` | Versioned product, assay, MeasurementSpec, ProductDefinition and explicit biological-unit bindings |
| `ProductDefinitionCard` | Versioned product context and exact StateRoleMap binding; no role decisions live in code |
| `StateRoleMap` | Versioned per-state lineage and regional assignments supplied as structured input |
| `TargetRegionalAssessmentSpec` | Versioned selection of composition views, label levels and denominator mechanics |
| `TargetRegionalEvidenceResult` | Raw role-resolved target/regional evidence with unresolved states and null score |
| `DevelopmentWindowSpec` | Versioned ProductDefinition/vocabulary-bound developmental roles and static composition selection |
| `DevelopmentalCompatibilityResult` | Static dual-denominator stage evidence with unavailable dynamic/reference channels and null score |
| `OffTargetRoleSpec` | Versioned ProductDefinition/vocabulary-bound product roles and full-product denominator selection |
| `OffTargetControlResult` | Static role-resolved full-product composition with unavailable OOD/rare-state calibration and null score |
| `ProgramAssessmentSpec` | Versioned ProductDefinition/window-bound program rules, reference intervals, coverage and review directions supplied as input |
| `ProgramEvidenceBundle` | Versioned precomputed program observations with exact metric/unit/scope/state/stage, method, Evidence Family, biological unit and evidence state |
| `ProliferationStressResponseProfile` | Configured reference relations and shadow transcriptomic review flags with deferred ProtocolIR/LOD/CNV channels and null score |
| `GraftAssessmentSpec` | Versioned channel, unit, eligible-state, independent-animal and optional interval policy supplied as input |
| `GraftEvidenceBundle` | Versioned precomputed graft/timepoint observation units, animal refs, design constraints and declared preparation linkage |
| `GraftAssessment` | Equal-animal descriptive summaries with explicit absence/linkage-declaration state, null score and no ProductCase backfill |

Implemented Tool Packages retain at least one selected `method_id`. Scaffold packages keep `method_ids` empty until an executable, benchmark-bound method contract exists; candidate catalog entries do not imply implementation.

The existing v0.1 models and schemas remain the contract for current P0-01 and P0-02 behavior. A v0.2 package declares `bridge://schemas/tool-request/v0.2` and `bridge://schemas/tool-run/v0.2`. Implemented v0.2 packages additionally bind a non-empty method set, one adapter under `bridge.tool_packages.*`, and a result schema. Scaffold v0.2 packages bind neither adapter nor result schema. The registry selects the request model after reading `tool_id`; the CLI command and Python SDK entrypoints do not change. A Python caller that manually supplies the wrong request-model generation receives a structured refusal before adapter or executor resolution: `tool_request_v2_required` for a v1 request sent to a v0.2 package, or `tool_request_v1_required` for the inverse. `validate_request` returns an ineligible `EligibilityResult`; `run_tool` returns a failed envelope matching the request object that actually arrived, so the refusal remains serializable.

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

The versioned JSON contracts in `schemas/` are the language-neutral interface for Agent implementations. Pydantic models in `src/bridge/toolkit/contracts.py` are the Python source used to generate those schemas.

For v0.2 implemented packages, the registry resolves only the package's declared adapter reference. The adapter implements the two-method `ToolPackageAdapter` protocol at the runtime seam. Returned runs must preserve request, tool version, implementation state and environment bindings. Successful and partial runs require both a non-null result and the exact registered result-schema reference declared by the package; every non-null result is validated with JSON Schema Draft 2020-12. Adapter/import/runtime failures from CLI `validate` or `run` are structured errors with exit code 4. The shared seam itself adds no scientific capability; P0-03 through P0-12 are separately reviewed deterministic candidates.

P0-03 consumes exactly one ProductCase, ProductDefinitionCard, StateRoleMap,
TargetRegionalAssessmentSpec, CellStateEvidenceProfile and QCReadinessProfile.
It joins upstream composition records to caller-supplied versioned roles and
calculates explicit numerators, denominators and fractions. The implementation
contains no product-specific state names, role mapping, thresholds or pass/fail
rule. Unmapped states remain unresolved, absent requested channels return
`not_assessed`, spatial evidence remains `not_assessed` until independently
implemented, and `domain_score` is always null. The complete interface is in
the [P0-03 Tool Card](../tool_packages/P0-03/README.md).

P0-04 consumes a ProductCase, ProductDefinitionCard, StateRoleMap, DevelopmentWindowSpec,
CellStateEvidenceProfile and QCReadinessProfile. It calculates only configured
static stage composition over whole-product and target-related denominators.
The implementation contains no biological state mapping or time conversion;
reference-stage, time-course and lineage evidence remain explicitly absent.
See the [P0-04 Tool Card](../tool_packages/P0-04/README.md).

P0-05 consumes a ProductCase, ProductDefinitionCard, StateRoleMap, OffTargetRoleSpec,
CellStateEvidenceProfile and QCReadinessProfile. It reports only configured
full-product role composition, preserves the selected denominator view, and
keeps unconfigured identities role-unresolved. The implementation contains no
state-role table, OOD decision, rare-state limit or safety threshold. See the
[P0-05 Tool Card](../tool_packages/P0-05/README.md).

P0-06 consumes a ProductCase, ProductDefinitionCard, ProgramAssessmentSpec,
ProgramEvidenceBundle, P0-04 DevelopmentalCompatibilityResult and
QCReadinessProfile. It preserves precomputed values, compares them only with
caller-supplied reference intervals and counts ProductCase-declared biological
units. Each observation must match its rule's metric, unit, scope, state and
stage context exactly. The implementation contains no program, gene, stage, range, coverage
limit or biological threshold. Protocol attribution, residual-pluripotency LOD
and transcriptomic CNV remain not assessed. See the
[P0-06 Tool Card](../tool_packages/P0-06/README.md).

P0-07 consumes exactly two ProductCases, one ComparisonSpec and one
ComparisonEvidenceBundle. It checks caller-selected contract dimensions,
requires evidence units to exactly match each ProductCase without cross-arm
overlap, summarizes eligible biological-unit
values and publishes only the raw candidate-minus-baseline delta. The
implementation contains no assay allowlist, metric catalogue, biological
direction or threshold. Inferential statistics, stability modelling, Pareto,
score and rank remain unavailable. See the
[P0-07 Tool Card](../tool_packages/P0-07/README.md).

P0-08 consumes only versioned upstream evidence objects. Its profiles retain exact ProductCase, ProductDefinition, MeasurementSpec and QC refs plus v0.2 MeasurementResult refs, Schema URIs and source-byte checksums in `measurement_result_bindings`; it uses the shared `evidence-family:<id>` namespace consumed by P0-09. It applies Data Readiness, Model Robustness and Prior Applicability before selecting `not_assessed`, `insufficient`, `limited` or `sufficient` in the registered precedence order. It never reruns scientific analysis, emits a new `MeasurementResult`, or makes a domain score available. Its module-specific input/result schemas and complete field contract are documented in the [P0-08 Tool Card](../tool_packages/P0-08/README.md).

P0-09 consumes a compilation bundle, full P0-08 run results, exact quantitative v0.2 MeasurementResults and versioned Evidence Family, Claim and reconciliation registries. `EvidenceCandidate` identifies the MeasurementResult and sufficiency-result inputs but cannot restate their numeric/unit/denominator/interval/provenance fields. It creates append-only `EvidenceRecord` and `EvidenceRequirement` facts, deterministic reconciliation records, Case or Comparison graph manifests, fixed-column Parquet node/edge tables and a Cytoscape projection. Missing evidence creates a requirement rather than a zero-valued record; shadow or exploratory evidence cannot become formal. JSON/Parquet remain authoritative, while NetworkX is limited to reconstruction, invariant checks and seven named read-only query helpers. LadybugDB is deferred shadow work and is not a release dependency. The complete interface and reason-code contract are documented in the [P0-09 Tool Card](../tool_packages/P0-09/README.md).

P0-10 verifies a structured ReportDraft against a manifest-validated P0-09 Case
graph, package-owned policy and statements. Evidence lifecycle is taken from the
graph-derived latest active projection, not a predecessor row's immutable
creation state. The current package has no trusted public-release authority, so
every assessed receipt is fail-closed with
`public_release_authority_state=not_configured` and
`public_export_eligibility=ineligible`; `verified` means correspondence only.

P0-11 consumes one ReportDraft, one P0-10 ClaimVerificationResult, the exact
producing P0-10 ToolRunV2 and one ReviewProjectionSpec. It constructs a new
internal-review JSON object from selected fields and
preserves selected verified claim text exactly; source report/claim/ProductCase/Evidence IDs and
unselected prose are not projected. A bounded local-path/namespace/credential
guard supplements the explicit prohibited-literal list but is not a universal
secret scanner. Producer authentication is unavailable and public authority is
unconfigured, so the tool always reports `internal_review_only` and
`review_required`; it does not upload or authorize public distribution. See the
[P0-11 Tool Card](../tool_packages/P0-11/README.md).

P0-12 consumes exactly one ProductCase, its exact BiologicalUnitManifest, one
independent graft MeasurementSpec, one GraftAssessmentSpec and one
GraftEvidenceBundle; provided grafts also require an exact
GraftLineageManifest, while not-provided grafts forbid it. The spec supplies
channel IDs, units, disjoint graft/timepoint strata, within-animal aggregation
and denominator semantics, eligible evidence states, minimum independent-animal
counts and optional interpretation intervals. Source preparation linkage is
resolved from BiologicalUnitManifest bindings, not ProductCase independence
groups. Caller lineage labels and checksums are trace-only because the current
package has no trusted review-receipt verifier; animal-level summaries therefore
remain not assessed. It also records graft assay/specimen applicability as not
assessed until a typed real GraftCase exists. The test-only verifier seam checks
configured within-animal aggregation and cross-stratum refusal. P0-12 does not
read expression matrices, infer biology, emit a score, or write graft evidence
back into a pre-transplant ProductCase. See the
[P0-12 Tool Card](../tool_packages/P0-12/README.md).

Only `implemented` packages execute. A scaffold returns `not_implemented` with `tool_package_not_implemented`; a deprecated package is ineligible and returns a failed run with `tool_package_deprecated`. Neither state resolves or invokes an adapter.

P0-02 requests carry `source_family_id` plus logical `qc_profile_ref` and `measurement_spec_ref` identifiers. Same-family reference profiles are held out at runtime. Private reference paths remain in deployment-owned catalogs. Only frozen reference snapshots are accepted in Agent runtime; reference construction is a science-team operation.

Cell-State scientific commands are restricted to the BRIDGE science team: `bridge-benchmark cell-state prepare`, `prepare-birtele`, `audit-external-sources`, `run` and `summarize`. `prepare-birtele` and `audit-external-sources` establish checksummed external-source preparation and lineage exclusion only; their human-facing contract is [P0-02 external-source preparation](bridge_spec_v0.1/external_source_preparation.md). A pilot split cannot open locked assets; a locked split requires a signed `FreezeGateSpec`. Agent runtime cannot choose benchmark methods or thresholds.
