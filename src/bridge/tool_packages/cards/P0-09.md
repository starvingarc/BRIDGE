# P0-09 Evidence Compiler & Reconciler

## Biological question

Given already-computed, versioned product evidence, which atomic records support or contradict a registered claim, which evidence is non-independent, and which required evidence remains missing? P0-09 compiles and reconciles existing facts; it does not rerun biology, score a product, or authorize release.

## Contract

| Field | Value |
|---|---|
| Package version | `0.2.0` |
| Runtime state | `implemented` |
| Scientific state | `candidate` |
| EnvironmentSpec | `ENV-EVIDENCE-v0.1` (`proposed`) |
| Input envelope | `bridge://schemas/tool-request/v0.2` |
| Output envelope | `bridge://schemas/tool-run/v0.2` |
| Result schema | `bridge://schemas/evidence-compiler-run-result/v0.1` |
| Adapter | `bridge.tool_packages.p0_09_evidence_compiler.adapter:adapter` |
| Canonicalization | `bridge-canonical-json/v0.1` (not RFC 8785) |

Python SDK: `ToolRegistry.load_default().check_eligibility(request)` and `.run(request)` with `ToolRequestV2`. CLI: `bridge-tool validate --request REQUEST.json` and `bridge-tool run --request REQUEST.json`. The committed example contains placeholder paths and checksums and is documentation-only.

## Inputs

Every object is an immutable local `application/json` file referenced by `StructuredInputRef`. `path` must be absolute; `sha256` must be the lowercase checksum of exact bytes; `object_version` must match the payload.

| Role | Cardinality | Schema | Required content |
|---|---:|---|---|
| `compilation_bundle` | exactly 1 | `evidence-compilation-bundle/v0.1` | Case or Comparison scope, object catalog, candidate/missing items, optional prior history |
| `evidence_sufficiency_profile` | Case 1–5; Comparison 2–25 | `evidence-sufficiency-profile/v0.1` | ProductCase, domain, MeasurementSpec, sufficiency state and provenance |
| `evidence_family_registry` | exactly 1 | `evidence-family-registry/v0.1` | Family version, channel role, independence scope, review state |
| `claim_registry` | exactly 1 | `claim-registry/v0.1` | Claim version, domain, allowed relations and requirement templates |
| `reconciliation_spec_registry` | exactly 1 | `reconciliation-spec-registry/v0.1` | Frozen channel/minimum/conflict rules; no weights or generic expressions |
| `base_graph_manifest` | exactly 1 iff Case `base_graph_ref` exists | Case graph manifest | Exact prior graph manifest; forbidden otherwise |
| `base_evidence_record_set` | exactly 1 iff Case `base_graph_ref` exists | `evidence-record-set/v0.1` | Complete prior EvidenceRecord history named by the base manifest |
| `base_evidence_requirement_set` | exactly 1 iff Case `base_graph_ref` exists | `evidence-requirement-set/v0.1` | Complete prior EvidenceRequirement history named by the base manifest |
| `source_case_graph_manifest` | exactly 1 per Comparison case ref | Case graph manifest | Content-addressed source Case graph; forbidden for Case compilation |
| `source_case_evidence_record_set` | exactly 1 per Comparison case ref | `evidence-record-set/v0.1` | Exact source facts named by its paired manifest |

The shared envelope requires `assets=[]`, `measurement_spec_ref=null`, and `parameters={}`. `random_seed` is accepted for envelope parity but unused. Input paths, request ID, output path, and wall-clock time do not enter logical object IDs.

## Outputs

Successful or partial execution writes one immutable `<output_dir>/run-<digest>/` bundle:

| File | Meaning |
|---|---|
| `evidence_records.json` | Complete supplied history plus created/appended records and per-candidate dispositions |
| `evidence_requirements.json` | Open/satisfied requirements; missing never becomes `value=0` |
| `reconciliation_records.json` | Claim gates, family-deduplicated channel resolutions and stable reason codes |
| `graph_nodes.parquet`, `graph_edges.parquet` | Authoritative, sorted graph facts with fixed Arrow schemas |
| `case_evidence_graph_manifest.json` or `comparison_evidence_graph_manifest.json` | Rebuild manifest and hashes of the five authoritative facts |
| `cytoscape_elements.json` | Bounded display projection, maximum 500 nodes/1,000 edges |
| `rejected_records.json` | IDs, indices, digests and reason codes only; never raw rejected payloads |
| `evidence_compiler_run_result.json` | Typed result returned in `ToolRunV2.result` |
| `artifact_manifest.json` | Checksums of the preceding nine files; no circular self-hash |

`measurements=[]` and `visualizations=[]`. P0-09 computes or populates no `domain_score`, total score, grade, pass/fail, potency, safety, efficacy, GMP-release or ranking field. A bound P0-08 profile's required `domain_score=null` is preserved only as upstream provenance and never becomes a P0-09 conclusion. JSON and Parquet are the facts; NetworkX validates and serves bounded in-process queries only. LadybugDB is deferred shadow work and is not required.

## Versioning and reconciliation

- Same logical key and content is `unchanged`; no duplicate node or edge is created.
- Changed content requires `supersede` or `invalidate` against the latest predecessor and appends version N+1. History is never overwritten.
- `negative`, `missing`, `unknown`, `unavailable`, and `alert` remain distinct. Missing creates an `EvidenceRequirement`, not a numeric record.
- `shadow` and `exploratory` records remain visible for audit but never enter formal reconciliation.
- Failed, skipped, or not-implemented upstream runs cannot become evidence.
- Records sharing an EvidenceFamily retain provenance but contribute one family direction. Families in the same `independence_scope`, or joined by the symmetric/transitive closure of `known_dependencies`, count as one independent component. Opposite directions within a component remain unresolved; tools and records are never majority votes.
- P0-08 v0.1 exposes bare ProductCase and MeasurementSpec IDs rather than versioned refs. P0-09 therefore validates shadow/exploratory ID, MeasurementResult and retained-family bindings but conservatively rejects every formal candidate/external ref with `sufficiency_profile_version_binding_unavailable`; v0.1 cannot emit an eligible formal reconciliation.

## Refusal and degradation

Top-level role, Schema, media type, checksum, graph scope, prior-chain, overlapping-output, legacy-score, unsafe publication reference, or input-mutation failures return `failed`, `result=null`, and no artifacts. Public `candidate_records`, `missing_observations`, and `external_case_evidence_refs` are strict object arrays: a non-object or other top-level Schema violation fails the run. A Schema-valid candidate/missing item or Comparison external mapping that fails record-level provenance/binding semantics is sanitized into `partial` metadata only; rejected payloads do not enter the graph or get echoed. The bounded publication contract rejects local/server paths, `file:` URIs, home-variable paths, credential-like assignments/tokens, and non-identifier public refs; it is not a promise of general secret detection. Contract-complete absence is a scientific `EvidenceRequirement`/`insufficient_evidence`, not a technical failure or zero.

The query projection exposes exactly seven read-only helpers: `get_claim_evidence`, `trace_evidence_provenance`, `get_conflicting_evidence`, `get_missing_requirements`, `get_evidence_family_members`, `get_case_evidence_subgraph`, and `compare_evidence_paths`. Callers cannot supply Cypher, predicates, paths, writes, or unbounded limits.

## Method, license and validation boundary

Selected catalog methods are the internal deterministic engine, bounded read-only API, PyArrow/Parquet storage, and NetworkX graph validation. They remain `formal_eligible=false`; catalog formal-eligible count remains zero. Dependency licenses and exact environment pins are governed by the packaged knowledge snapshot and `ENV-EVIDENCE-v0.1`.

Synthetic tests cover deterministic identity, append-only revision, missing-versus-zero, partial rejection, family de-duplication, graph round-trip, immutable publication and all seven query caps. This engineering evidence does not establish that a biological claim is true, that any current domain is sufficient, or that any output is scientifically releasable.

Detailed task card: `docs/bridge_spec_v0.1/evidence_compiler_task_card.md`.

## Field-level interface reference

### Shared request envelope

| Field | Type | Required | Source and rule |
|---|---|---:|---|
| `request_id` | string | yes | Caller trace only; excluded from semantic identity |
| `tool_id` | literal `P0-09` | yes | Must select this package |
| `tool_version` | literal `0.2.0` or null | no | If present, must match exactly |
| `output_dir` | absolute path | yes | Deployment-owned destination; may not contain any structured input |
| `assets` | array | yes | Must be empty; expression assets are outside P0-09 |
| `measurement_spec_ref` | null | yes | MeasurementSpec belongs inside each candidate/object catalog |
| `parameters` | object | yes | Must be empty; rules come only from versioned registries |
| `random_seed` | integer | yes | Included for envelope parity and input identity; unused by computation |
| `object_inputs` | `StructuredInputRef[]` | yes | Unique `input_id` and resolved path; exact roles/cardinalities below |

Each `StructuredInputRef` requires `input_id:string`, exact `role:string`, registered `schema_ref:string`, payload `object_version:string`, absolute `path`, lowercase 64-hex `sha256`, and `media_type="application/json"`. Exact bytes are checked before parse and immediately before publication. The reusable bundle stores only a canonical semantic checksum; raw checksums remain in the ToolRun request and never force two semantically identical set-orderings to collide at one run directory.

### EvidenceCompilationBundle

| Field | Type | Required | Meaning and constraint |
|---|---|---:|---|
| `bundle_id` | `evidence-compilation-bundle:*` | yes | Versioned caller identity |
| `bundle_version` | literal `0.1.0` | yes | Schema version |
| `graph_kind` | `case \| comparison` | yes | Selects mutually exclusive graph scope |
| `product_case_ref` | `VersionedObjectRef \| null` | case | Exactly one for Case; null for Comparison |
| `comparison_ref` | `VersionedObjectRef \| null` | comparison | Exactly one for Comparison; null for Case |
| `case_graph_refs` | `BoundCaseGraphRef[]` | comparison | 2–5 distinct source graph ID/version/manifest hash/ProductCase refs plus unique `manifest_input_id`/`record_set_input_id` bindings |
| `external_case_evidence_refs` | `ExternalCaseEvidenceRef[]` | comparison | At least one explicit source EvidenceRecord-to-Comparison Claim mapping |
| `base_graph_ref` | `AppendGraphRef \| null` | case append | Prior graph ID/version/manifest checksum plus unique base manifest/record/requirement input IDs |
| `object_catalog` | `CompilationObjectRef[]` | yes | Unique object ID/version, node type, Schema URI and declared content hash |
| `candidate_records` | raw object array | case | Individually parsed `EvidenceCandidate`; siblings can fail independently |
| `missing_observations` | raw object array | case | Individually parsed absence observations; never numeric placeholders |
| `prior_evidence_records` | `EvidenceRecord[]` | case | Complete linear, hash-valid history used for N+1 revision |
| `prior_requirements` | `EvidenceRequirement[]` | case | Complete linear requirement history |
| `created_at` | timezone-aware datetime | yes | Normalized to UTC; contributes to deterministic output time |
| `provenance_refs` | unique string array | yes | Set semantics; path/credential strings forbidden |

`VersionedObjectRef` contains `object_id` and `object_version`. `CaseGraphRef` is the pure public source identity: graph ID/version, raw manifest checksum and ProductCase ref. `BoundCaseGraphRef` adds request-local source input IDs; `AppendGraphRef` adds request-local base input IDs. Those binding IDs are never projected into a public Case/Comparison manifest. A Case bundle forbids comparison fields. A Comparison bundle forbids base/owned candidate/missing/history arrays and never copies source-case scientific properties.

### EvidenceCandidate and missing observation

| Candidate field | Type | Required | Meaning |
|---|---|---:|---|
| `candidate_id` | `evidence-candidate:*` | yes | Per-input disposition identity; unique in bundle |
| `product_case_ref`, `sample_or_preparation_ref` | versioned refs | yes | Must resolve in scope/catalog |
| `domain_id` | five-value P0 domain enum | yes | Must match Claim and P0-08 profile |
| `measurement_result_ref`, `measurement_spec_ref` | versioned refs | yes | Catalog-resolved upstream result and contract |
| `score_contract_ref` | versioned ref or null | no | Provenance only; no score is computed |
| `metric_id` | string | yes | Atomic metric identity |
| `value` | safe JSON value | yes | Preserved, not recomputed; booleans are not numeric evidence; null only for unknown/unavailable/alert |
| `unit` | string or null | no | Preserved upstream unit |
| `numerator`, `denominator` | finite number or null | no | Denominator must be positive; no implicit denominator |
| `interval` | lower/upper/confidence/method | no | Finite, ordered bounds; confidence in `(0,1)` |
| `claim_ref`, `biological_context` | versioned ref/object | yes | Explicit Claim and context; never inferred from names/paths |
| `relation` | `supports \| contradicts` | yes | Must be allowed by Claim |
| `evidence_state` | EvidenceState | yes | `missing` forbidden here; use missing observation |
| `evidence_tier` | `formal \| shadow \| exploratory` | yes | Only eligible formal evidence can reconcile |
| `applicability` | `applicable \| not_applicable \| not_assessed` | yes | Non-applicable/unassessed remains audit-only |
| `evidence_family_ref` | versioned ref | yes | Pre-registered family and channel binding |
| `sufficiency_profile_input_id` | string | yes | Exact request input ID of matching P0-08 profile |
| `tool_run_ref`, `tool_run_execution_state` | ref + enum | yes | Only succeeded/partial records compile |
| `reference_refs`, `prior_refs`, `artifact_refs` | unique ref arrays | yes | Catalog-resolved, set semantics, content-hashed |
| `provenance_refs` | unique string array | yes | Set semantics; no local path/token material |
| `revision_action` | `create \| supersede \| invalidate` | yes | Controls append-only lifecycle |
| `predecessor_ref` | Evidence ref or null | conditional | Null for create; latest same-key version for revision |
| `created_at` | timezone-aware datetime | yes | Upstream observation time, not compiler wall clock |

`MissingEvidenceObservation` requires `observation_id`, `product_case_ref`, `claim_ref`, registered `requirement_key`, one of `measurement_not_provided`, `measurement_unavailable`, `required_channel_not_provided`, `required_experiment_not_performed`, `source_contract_ref`, provenance and `observed_at`.

### Registries and P0-08 binding

| Object | Required fields | Freeze/eligibility rule |
|---|---|---|
| `EvidenceFamilyRegistry` | registry ID/version/status/time; families | Formal evidence requires frozen registry and reviewed family |
| `EvidenceFamilySpec` | ID/version/type/channel role/shared refs/independence scope/dependencies/rationale/reviewer/status | Reviewed family requires reviewer; family is the unit of independent influence |
| `ClaimRegistry` | registry ID/version/status/time; claims | Formal evidence requires frozen registry and frozen Claim |
| `ClaimSpec` | ID/version/type/domain/target/versioned biological-context ref/allowed relations/ReconciliationSpec ref/requirements/status/reviewer | Context ID and version must exactly match the candidate context; frozen Claim requires reviewer; requirement keys unique |
| `ClaimRequirementSpec` | key/channel role/modality/experiment/blocking scope/required | Missing required role materializes Requirement |
| `ReconciliationSpecRegistry` | registry ID/version/status/time; specs | Formal evidence requires frozen registry and frozen spec |
| `ReconciliationSpec` | ID/version/claim type, required/optional/primary/confirmation/integration roles, minimum family map, allowed states, fixed rules, review/validation/status | No weights, score thresholds, fallback method or expression language |
| P0-08 `EvidenceSufficiencyProfile` | profile ID/version, bare ProductCase/MeasurementSpec IDs, MeasurementResult refs, retained family IDs, sufficiency state, reasons, UTC time | Shadow/exploratory evidence must match every available ID/family binding. Missing versioned ProductCase/MeasurementSpec refs make formal authorization unavailable in v0.1 |

Reason-code lists with scientific precedence preserve their declared order. Object catalogs, refs, registry entries and other explicitly set-like lists are normalized deterministically. Reordering an interpretive/temporal list changes content identity; reordering a set-like list does not.

### EvidenceRecord output

| Field group | Fields and semantics |
|---|---|
| Identity | `evidence_id`, integer `evidence_version`, canonical `logical_key`, full `content_hash` |
| Scientific source | ProductCase, sample/preparation, domain, MeasurementResult, MeasurementSpec, optional ScoreContract |
| Observation | metric, value, unit, optional numerator/positive denominator/interval |
| Interpretation | Claim, BiologicalContext, relation, EvidenceState, tier, lifecycle, applicability |
| Provenance | EvidenceFamily, P0-08 profile, ToolRun/state, reference/prior/artifact/provenance refs |
| Revision | action, predecessor, source `created_at`, compiler version `0.2.0` |

The logical key uses only ProductCase, sample/preparation, domain, metric, Claim, BiologicalContext and MeasurementSpec. Content changes keep the same evidence ID but require a new version. No score field is present.

### EvidenceRequirement output

| Field | Meaning |
|---|---|
| `requirement_id`, `requirement_version`, `content_hash` | Stable claim/key identity plus append-only version |
| Claim/ProductCase/source contract | Exact scope and contract provenance |
| key/channel/modality/experiment/blocking scope | What evidence is required and why |
| `state` | `open`, `satisfied`, or `not_applicable` |
| reason codes and satisfying evidence refs | Explicit absence or exact active evidence; never a numeric placeholder |
| predecessor/time | Append-only requirement transition |

Every required Claim requirement without qualifying evidence remains/open-appends a Requirement. Later qualifying evidence appends a satisfied version referencing the exact EvidenceRecords.

### ReconciliationRecord output

| Field | Meaning |
|---|---|
| stable ID/version and graph ID/version | Deterministic Claim/spec scope |
| Claim/Spec/Profile refs | Frozen rule and sufficiency provenance |
| `eligibility` | `eligible`, `insufficient_evidence`, or `not_assessed` |
| `state` | null unless eligible; otherwise stable/consensus_supported/integration_sensitive/unstable |
| `direction` | supports/contradicts only for resolved eligible state; null for unstable/ineligible |
| channel resolutions | role, evidence refs, family refs, family-deduplicated direction, eligibility and reasons |
| included/excluded/open refs | Exact audit trace; shadow/exploratory remains excluded |
| reason codes/time/content hash | Deterministic gate explanation and identity |

Resolution order is integration sensitivity, independent confirmation, unresolved instability, then stable unanimous independent-component direction. Same-scope and dependency-connected families never satisfy an independent-family minimum twice. An optional/integration channel cannot satisfy a missing required channel.

### Graph manifests, artifacts and query result

Case manifest adds `product_case_ref`; Comparison manifest adds `comparison_ref` and sorted pure `CaseGraphRef` objects. Both contain graph/version, canonicalization ID, node/edge/object counts, source semantic input hash, optional pure base graph ref, fixed allowlisted basenames, exact checksums for three JSON fact sets and two Parquet tables, exact Parquet row counts, and deterministic UTC time. Query open rejects absolute/traversal names, symlinks, checksum drift, row/count/graph drift, disconnected projections, or JSON-fact-to-Parquet disagreement. Before compilation, every supplied base/source manifest is opened against its real directory and all five authoritative artifacts. Source roles and bundle input IDs form an exact bijection; graph IDs are derived from versioned ProductCase identity; source histories require create-first, continuous versions and exact predecessor chains. Comparison external nodes must uniquely match an actual source EvidenceRecord ref/content hash/Claim/ProductCase/tier/applicability/ToolRun and its derived effective lifecycle; they have `properties_json=null` and stop provenance traversal at the case boundary.

`artifact_manifest.json` records run/tool/environment/result schema, semantic checksums of structured objects, and exact checksums/media types/available byte sizes of nine preceding files. It deliberately does not hash itself. Raw input SHA remains only in the current `ToolRunV2.request`; semantically equivalent set-order variants reuse the same byte-identical bundle. `ToolRunV2.artifacts` adds absolute deployment paths for local retrieval; those paths never enter scientific JSON/Parquet facts.

Every `EvidenceGraphQueryResult` contains query name, graph ID/version, sorted node/edge objects, returned and omitted counts, `truncated`, and stable reason codes. `truncated=true` only when at least one reachable node or edge was actually omitted. It never exposes arbitrary predicates, executable query strings or mutation methods.

| Query | Required/filter parameters | Bounds and graph rule |
|---|---|---|
| `get_claim_evidence` | claim ID; optional version/tier/include inactive | `1<=limit<=200`; exactly one claim version |
| `trace_evidence_provenance` | Evidence ref | depth 1–6, nodes 1–500; external ref stops at source case |
| `get_conflicting_evidence` | claim ID; optional claim/reconciliation version | `limit<=200`; returns support and contradiction only when both exist |
| `get_missing_requirements` | exactly one of Claim or ProductCase; optional state enum | `limit<=200`; only the highest version of each requirement ID is current |
| `get_evidence_family_members` | family ID; optional include inactive | `limit<=200` |
| `get_case_evidence_subgraph` | ProductCase; optional domain/tier filters | Case graph only; depth<=6/nodes<=500 |
| `compare_evidence_paths` | Comparison plus exactly one Claim or domain | Comparison graph only; depth<=6/nodes<=500 |

### Stable technical and partial reason codes

Top-level failures include: `tool_request_v2_required`, `tool_version_mismatch`, `p0_09_expression_assets_forbidden`, `p0_09_top_level_measurement_spec_forbidden`, `p0_09_parameters_forbidden`, exact-role/cardinality failures, `unsupported_object_input_role`, `object_input_schema_mismatch`, duplicate input/profile IDs, structured input not found/not regular/media/checksum/JSON/Schema/version failures, `unsafe_structured_input_reference`, unbound profile, `graph_scope_invalid`, `prior_history_invalid`, `output_dir_overlaps_structured_input`, `legacy_evidence_contract_rejected`, input mutation, existing-bundle mismatch, graph invariant, Parquet projection and artifact checksum failure. They return failed execution, null result and no artifacts.

Record-level rejection codes are emitted in stable contract order: schema invalid, duplicate source ID, undeclared/wrong-type object, Claim not found/version/domain/relation/context mismatch, family not found/version mismatch, profile binding/case/domain/spec/MeasurementResult/family mismatch, `sufficiency_profile_version_binding_unavailable`, failed ToolRun, missing-state misuse, non-finite/invalid denominator, formal-tier gate failures, create/revision/predecessor/logical-key conflicts, duplicate logical-key conflict and invalid external mapping. Any such Schema-valid sibling rejection publishes valid facts as `partial` with `individual_records_rejected`; raw rejected content is never returned.

Reconciliation reasons include contract/spec not frozen or mismatched, sufficiency not sufficient, tier/lifecycle/applicability/ToolRun/family/state exclusions, same-family de-duplication/conflict, missing independent channel, no formal evidence, integration conflict, independent-confirmation resolution, unresolved conflict and stable family-deduplicated direction. These are scientific gate states, not runtime exceptions or product failures.

### Minimal documentation-only request

```json
{
  "request_id": "example-p0-09",
  "tool_id": "P0-09",
  "tool_version": "0.2.0",
  "output_dir": "/absolute/output",
  "assets": [],
  "measurement_spec_ref": null,
  "parameters": {},
  "random_seed": 0,
  "object_inputs": [
    {"input_id":"bundle","role":"compilation_bundle","schema_ref":"bridge://schemas/evidence-compilation-bundle/v0.1","object_version":"0.1.0","path":"/absolute/bundle.json","sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","media_type":"application/json"},
    {"input_id":"profile","role":"evidence_sufficiency_profile","schema_ref":"bridge://schemas/evidence-sufficiency-profile/v0.1","object_version":"0.1.0","path":"/absolute/profile.json","sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","media_type":"application/json"},
    {"input_id":"families","role":"evidence_family_registry","schema_ref":"bridge://schemas/evidence-family-registry/v0.1","object_version":"0.1.0","path":"/absolute/families.json","sha256":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","media_type":"application/json"},
    {"input_id":"claims","role":"claim_registry","schema_ref":"bridge://schemas/claim-registry/v0.1","object_version":"0.1.0","path":"/absolute/claims.json","sha256":"dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd","media_type":"application/json"},
    {"input_id":"rules","role":"reconciliation_spec_registry","schema_ref":"bridge://schemas/reconciliation-spec-registry/v0.1","object_version":"0.1.0","path":"/absolute/rules.json","sha256":"eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee","media_type":"application/json"}
  ]
}
```

### Minimal successful result payload

```json
{
  "result_id": "evidence-compiler-result:0123456789abcdef",
  "result_version": "0.1.0",
  "graph_kind": "case",
  "graph_id": "case-evidence-graph:0123456789abcdef01234567",
  "graph_version": 1,
  "record_set_ref": "evidence-record-set:0123456789abcdef",
  "requirement_set_ref": "evidence-requirement-set:0123456789abcdef",
  "reconciliation_refs": ["reconciliation:0123456789abcdef01234567@1"],
  "graph_manifest_schema_ref": "bridge://schemas/case-evidence-graph-manifest/v0.1",
  "graph_manifest_ref": "case_evidence_graph_manifest.json",
  "cytoscape_export_ref": "cytoscape_elements.json",
  "rejected_record_count": 0,
  "accepted_record_count": 1,
  "unchanged_record_count": 0,
  "reason_codes": []
}
```
