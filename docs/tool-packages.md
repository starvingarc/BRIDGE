# Tool Package Guide

BRIDGE exposes 12 high-level P0 Tool Packages as the callable capability layer
for the planned scientific Agent. All are implemented and callable engineering
candidates. Scientific readiness is tracked separately: downstream evidence
remains shadow where applicable, and no formal domain score is available.

**Jump to:** [P0-01](#p0-01) · [P0-02](#p0-02) · [P0-03](#p0-03) ·
[P0-04](#p0-04) · [P0-05](#p0-05) · [P0-06](#p0-06) ·
[P0-07](#p0-07) · [P0-08](#p0-08) · [P0-09](#p0-09) ·
[P0-10](#p0-10) · [P0-11](#p0-11) · [P0-12](#p0-12)

```text
upload → audit → state evidence → domain evidence → sufficiency → graph → verify → export
          P0-01      P0-02          P0-03–06        P0-08      P0-09   P0-10   P0-11

P0-07 compares eligible product bundles. P0-12 keeps graft evidence independent.
```

## Shared interface

The package README is the short code-reader entry point. The **Tool Card** is the
authoritative human-readable runtime interface. The scientific task card records
the biological question and validation design. The validation record says what
was actually tested. Public JSON Schemas and `input-contract` are the
machine-readable interface; prose does not override them.

```bash
bridge-tool describe P0-XX
bridge-tool input-contract P0-XX
bridge-tool validate --request <request.json>
bridge-tool run --request <request.json>
```

The Python package exposes `list_tools`, `describe_tool`, `describe_tool_input`,
`validate_request` and `run_tool`. P0-01 and P0-02 use `ToolRequest` v0.1;
P0-03 through P0-12 use checksummed local JSON objects in `ToolRequestV2`.

All modules use the shared BRIDGE contract/runtime layer built on
[Pydantic](https://docs.pydantic.dev/) and
[jsonschema](https://python-jsonschema.readthedocs.io/). The software lists below
name code that the current implementation actually calls. Registered candidates
are labelled separately and are not active runtime dependencies or selected
scientific methods.

<a id="p0-01"></a>
## P0-01 Input Audit & QC

| Item | Details |
|---|---|
| Purpose | Audit an uploaded expression object and establish whether its declared matrix and metadata are ready for downstream analysis. [Scientific task card](bridge_spec_v0.1/input_audit_qc_task_card.md). |
| Executable implementation | BRIDGE case validation, matrix audit, raw QC metrics and QC-flag generation. [Scrublet](https://github.com/swolock/scrublet) runs only when explicitly requested and eligible. |
| Software | [AnnData](https://anndata.readthedocs.io/) for H5AD, [Scanpy](https://scanpy.readthedocs.io/) for 10x H5, [SciPy](https://docs.scipy.org/doc/scipy/) for sparse/MTX input, [NumPy](https://numpy.org/doc/), [pandas](https://pandas.pydata.org/docs/) and [Matplotlib](https://matplotlib.org/stable/). CellBender, EmptyDrops, miQC, MultiQC/Cell Ranger, SampleQC, scDblFinder, scQCenrich, scuttle and SoupX are registered candidates and are not called by this adapter. |
| Input → output | H5AD, 10x H5 or 10x MTX plus assay, matrix semantics, metadata and MeasurementSpec → QC readiness profiles, raw measurements, lineage artifacts, visualizations and manifest. [Tool Card](../src/bridge/tool_packages/cards/P0-01.md). |
| Call | Shared CLI/SDK with `tool_id=P0-01`; start from the [count-ready](../examples/requests/p0_01_count_ready.json) or [analysis-ready](../examples/requests/p0_01_analysis_ready.json) request. |
| Current evidence / status | Public scRNA-seq and snRNA-seq objects exercised reading, raw metrics, immutable-input checks and artifact checksums. This establishes QC-readiness behavior, not product quality, safety or release. [Validation](validation/p0_01_server_integration_20260810.md). |

<a id="p0-02"></a>
## P0-02 Cell-State Evidence

| Item | Details |
|---|---|
| Purpose | Produce source-aware reference-similarity and marker/program evidence without forcing a released cell-state label. [Scientific task card](bridge_spec_v0.1/cell_state_annotation_task_card.md). |
| Executable implementation | The main runtime executes BRIDGE pseudobulk reference correlation and marker-program evidence. Separate benchmark adapters can execute [CellTypist](https://celltypist.readthedocs.io/), [scANVI](https://docs.scvi-tools.org/), [SingleR](https://bioconductor.org/packages/SingleR/), [scmap](https://bioconductor.org/packages/scmap/), [Symphony](https://github.com/immunogenomics/symphony) and [scConform](https://bioconductor.org/packages/scConform/); the Agent path does not select them silently. |
| Software | Python: AnnData, h5py, NumPy, pandas, SciPy, scikit-learn, PyArrow, CellTypist and scvi-tools. R/Bioconductor: SingleR, scmap, symphony, scConform, SingleCellExperiment, SummarizedExperiment, S4Vectors and jsonlite. |
| Input → output | QC-qualified expression views, modality, vocabulary, references and provenance → source-aware Cell-State evidence, uncertainty and lineage bindings; no released assignment or score. [Tool Card](../src/bridge/tool_packages/cards/P0-02.md). |
| Call | Shared CLI/SDK with `tool_id=P0-02`; start from the [request example](../examples/requests/p0_02_cell_state.json). Benchmark/freeze commands remain science-team workflows. |
| Current evidence / status | Real-data integration established a reproducible shadow baseline; the pilot exposed forced-label/OOD and fine-state limitations. Reference correlation is similarity, not replicate-aware differential expression. The method remains unfrozen, `score_state=shadow`, `domain_score=null`. [Integration](validation/p0_02_server_integration_20260811.md) · [Pilot](validation/p0_02_scientific_freeze_pilot_20260811.md). |

<a id="p0-03"></a>
## P0-03 Target Identity & Regional Fidelity

| Item | Details |
|---|---|
| Purpose | Aggregate externally defined target-lineage and transcriptomic regional support. [Scientific task card](bridge_spec_v0.1/target_regional_identity_task_card.md). |
| Executable implementation | Deterministic StateRoleMap and regional StateRoleMap aggregation; biological roles are supplied, not inferred or embedded. |
| Software | Shared Pydantic/JSON Schema runtime and Python standard library; no external biological model. |
| Input → output | Eleven checksummed case, product, role, measurement, QC, state-evidence, vocabulary and reference objects → three descriptive ratios with applicability, reasons and provenance. [Tool Card](../src/bridge/tool_packages/cards/P0-03.md). |
| Call | Shared CLI/SDK with `tool_id=P0-03`; start from the [request example](../examples/requests/p0_03_target_regional_evidence.json). |
| Current evidence / status | Synthetic cases verify deterministic ratios, missing-data behavior and checksummed artifacts. Results remain `candidate/shadow`, `domain_score=null`; this is not biological validation of regional identity. [Validation](validation/p0_03_target_regional_20260825.md). |

<a id="p0-04"></a>
## P0-04 Developmental Compatibility

| Item | Details |
|---|---|
| Purpose | Aggregate alignment to an externally supplied developmental window. [Scientific task card](bridge_spec_v0.1/developmental_compatibility_task_card.md). |
| Executable implementation | Deterministic DevelopmentStateMap validation and soft-composition aggregation; no window or state map is hard-coded. |
| Software | Shared Pydantic/JSON Schema runtime and Python standard library; no external trajectory or age model. |
| Input → output | ProductCase, product definition, DevelopmentWindowSpec, DevelopmentStateMap, MeasurementSpec and P0-02 profile, optionally with timepoints → `DevelopmentalCompatibilityResult`. [Tool Card](../src/bridge/tool_packages/cards/P0-04.md). |
| Call | Shared CLI/SDK with `tool_id=P0-04`; start from the [request example](../examples/requests/p0_04_developmental_compatibility.json). |
| Current evidence / status | Contract fixtures verify deterministic composition and unavailable/refusal states. The package remains `candidate`, `domain_score=null`; it does not freeze a developmental window or biological age. [Validation](validation/p0_04_developmental_compatibility_v0.2.md). |

<a id="p0-05"></a>
## P0-05 Off-target Control

| Item | Details |
|---|---|
| Purpose | Account for the whole product under supplied state roles and rare-state calibration rules. [Scientific task card](bridge_spec_v0.1/off_target_control_task_card.md). |
| Executable implementation | Deterministic role-aware soft composition, unknown accounting, coverage checks and rare-state detectability states. |
| Software | Shared Pydantic/JSON Schema runtime plus Python numerical and hashing utilities; no external classifier. |
| Input → output | ProductCase, product definition, StateRoleMap, assessment spec, P0-02 profile and evidence bundle → `OffTargetControlProfile`. [Tool Card](../src/bridge/tool_packages/cards/P0-05.md). |
| Call | Shared CLI/SDK with `tool_id=P0-05`; start from the [request example](../examples/requests/p0_05_off_target_control.json). |
| Current evidence / status | Synthetic positive, negative, missing and alert cases verify whole-product accounting and failure semantics. Results remain `candidate/shadow`, `domain_score=null`; they are not safety evidence. [Validation](validation/p0_05_off_target_control_20260825.md). |

<a id="p0-06"></a>
## P0-06 Proliferation & Stress Response

| Item | Details |
|---|---|
| Purpose | Aggregate precomputed, stage-conditioned proliferation, stress-response and related review signals. [Scientific task card](bridge_spec_v0.1/proliferation_stress_response_task_card.md). |
| Executable implementation | Deterministic sample/state aggregation plus design, confounding and sensitivity audit. Gene-set scoring is upstream under a supplied ProgramSpec. |
| Software | Shared Pydantic/JSON Schema runtime and Python standard library; no external gene-set engine is run. |
| Input → output | Case, product, developmental window, ProgramSpec, P0-02 profile, ProtocolIR and evidence bundle → `ProliferationStressResponseProfile`. [Tool Card](../src/bridge/tool_packages/cards/P0-06.md). |
| Call | Shared CLI/SDK with `tool_id=P0-06`; start from the [request example](../examples/requests/p0_06_proliferation_stress_response.json). |
| Current evidence / status | Synthetic cases verify deterministic profiles, alerts and unavailable paths. Results remain `candidate/shadow`, `domain_score=null`; they do not establish cell fitness, safety or potency. [Validation](validation/p0_06_proliferation_stress_response_20260825.md). |

<a id="p0-07"></a>
## P0-07 Product Comparison & Stability

| Item | Details |
|---|---|
| Purpose | Compare product cases only when an explicit comparability and confounding contract permits it. [Scientific task card](bridge_spec_v0.1/product_comparison_stability_task_card.md). |
| Executable implementation | Deterministic comparability/confounding gate and raw deltas; optional method mode executes Hedges g, Jensen-Shannon distance, Spearman profile correlation, one-dimensional Wasserstein distance and within-group dispersion. Registered R/Bioconductor, Bayesian, mixed-model and integration candidates are not executed. |
| Software | [SciPy](https://docs.scipy.org/doc/scipy/) for Jensen-Shannon, Spearman and Wasserstein calls; [NumPy](https://numpy.org/doc/stable/) plus a small BRIDGE Hedges-g implementation; shared Pydantic/JSON Schema runtime. |
| Input → output | Base spec, manifest and 2–20 product-evidence bundles → `ProductComparisonStabilityProfile`; method mode adds checksummed method spec/input → `ComparisonMethodBundle` artifact. [Tool Card](../src/bridge/tool_packages/cards/P0-07.md). |
| Call | Shared CLI/SDK with `tool_id=P0-07`; see the [base request](../examples/requests/p0_07_product_comparison_stability.json) and [method-runtime request](../examples/requests/p0_07_comparison_method_runtime.json). |
| Current evidence / status | Fixtures verify semantic/source binding, actual dispatch, deterministic estimates and explicit refusal/degradation. Results remain `candidate/shadow`, `domain_score=null`; no p-value, winner, equivalence, ranking or stability claim is produced. [Base validation](validation/p0_07_product_comparison_stability_v0.2.md); [method validation](validation/p0_07_real_methods_20260827.md). |

<a id="p0-08"></a>
## P0-08 Evidence Sufficiency

| Item | Details |
|---|---|
| Purpose | Decide whether existing domain evidence is ready for interpretation under a versioned gate specification. [Scientific task card](bridge_spec_v0.1/evidence_sufficiency_task_card.md). |
| Executable implementation | Deterministic gate executor, packaged rule registry and validator applying Data Readiness → Model Robustness → Prior Applicability → sufficiency. |
| Software | Shared Pydantic/JSON Schema runtime, Python standard library and packaged JSON rule/reason-code resources. |
| Input → output | GateRuleSpec plus one to five domain bundles → `EvidenceSufficiencyRunResultV2`, per-domain profiles, gate trace and case summary. [Tool Card](../src/bridge/tool_packages/cards/P0-08.md). |
| Call | Shared CLI/SDK with `tool_id=P0-08`; start from the [request example](../examples/requests/p0_08_evidence_sufficiency.json). |
| Current evidence / status | Fixtures verify gate precedence, checksum failure and distinct sufficiency states. The module creates no measurement or score and remains a non-formal candidate. [Validation](validation/p0_08_evidence_sufficiency_20260813.md). |

<a id="p0-09"></a>
## P0-09 Evidence Compiler & Reconciler

| Item | Details |
|---|---|
| Purpose | Compile immutable evidence, explicit missing requirements and versioned conflicts into a bounded evidence graph. [Scientific task card](bridge_spec_v0.1/evidence_compiler_task_card.md). |
| Executable implementation | Deterministic compiler/reconciler, append-only versioning, graph reconstruction and seven named read-only queries; no arbitrary writes or Cypher. |
| Software | [NetworkX](https://networkx.org/documentation/stable/) for reconstruction/invariant checks and [PyArrow/Parquet](https://arrow.apache.org/docs/python/) for graph facts, plus the shared runtime. |
| Input → output | Compilation bundle, P0-08 profiles and EvidenceFamily, Claim and Reconciliation registries → record sets, JSON/Parquet graph facts, Cytoscape elements and manifests. [Tool Card](../src/bridge/tool_packages/cards/P0-09.md). |
| Call | Shared CLI/SDK with `tool_id=P0-09`; start from the [request example](../examples/requests/p0_09_evidence_compiler.json). |
| Current evidence / status | Fixtures verify deterministic rebuilds, idempotence, partial rejection, append-only supersession and bounded queries. Missing evidence becomes a requirement; shadow input is not promoted. [Validation](validation/p0_09_evidence_compiler_20260813.md). |

<a id="p0-10"></a>
## P0-10 Claim Verifier

| Item | Details |
|---|---|
| Purpose | Verify that a structured report preserves cited values, units, states, scope and package-approved wording. [Scientific task card](bridge_spec_v0.1/claim_verifier_task_card.md). |
| Executable implementation | Deterministic claim verification, exact numeric comparison, controlled rendering, packaged rules and typed release-state aggregation over P0-09 queries. |
| Software | [regex](https://github.com/mrabarnett/mrab-regex) for bounded Unicode matching, Python [Decimal](https://docs.python.org/3/library/decimal.html), Pydantic/jsonschema and the P0-09 query layer. |
| Input → output | ReportDraft, P0-09 Case graph manifest, packaged ClaimPolicySpec and StatementRegistry → one `ClaimVerificationResult`. [Tool Card](../src/bridge/tool_packages/cards/P0-10.md). |
| Call | Shared CLI/SDK with `tool_id=P0-10`; start from the [request example](../examples/requests/p0_10_claim_verifier.json). |
| Current evidence / status | Adversarial fixtures and a package benchmark verify value/wording correspondence, authority binding and fail-closed behavior. `verified` is not biological truth or release permission. [Validation](validation/p0_10_claim_verifier_20260814.md) · [Benchmark](validation/p0_10_claim_verifier_benchmark_v0.1.md). |

<a id="p0-11"></a>
## P0-11 Public-safe Export

| Item | Details |
|---|---|
| Purpose | Rebuild an eligible structured report through a field allowlist and confirmation-bound local export. [Scientific task card](bridge_spec_v0.1/public_safe_export_task_card.md). |
| Executable implementation | Deterministic allowlist projection, packaged rules, leak-canary scan and immutable local JSON export; no network upload. |
| Software | Shared Pydantic/JSON Schema runtime plus Python regular-expression, JSON, hashing and filesystem utilities; consumes a P0-10 receipt. |
| Input → output | ReportDraft, eligible P0-10 receipt, PublicExportPolicySpec and PublicExportRequest → `PublicSafeReport`, export manifest and result. [Tool Card](../src/bridge/tool_packages/cards/P0-11.md). |
| Call | Shared CLI/SDK with `tool_id=P0-11`; start from the [request example](../examples/requests/p0_11_public_safe_export.json). |
| Current evidence / status | Fixtures verify confirmation binding, allowlisting, leak-canary checks and immutable local output. A passed scan covers frozen rules/canaries only; `exported` means neither uploaded nor scientifically released. [Validation](validation/p0_11_public_safe_export_20260825.md). |

<a id="p0-12"></a>
## P0-12 Optional Graft Assessment

| Item | Details |
|---|---|
| Purpose | Characterize optional post-transplant graft evidence without feeding it back into the pre-transplant product profile. [Scientific task card](bridge_spec_v0.1/graft_assessment_task_card.md). |
| Executable implementation | Deterministic GraftCase validation, soft-composition aggregation and explicit no-input handling. |
| Software | Shared Pydantic/JSON Schema runtime and Python standard library; no external graft-outcome model. |
| Input → output | No object inputs, or GraftCase, GraftAssessmentSpec and GraftEvidenceBundle → `GraftAssessmentResult` with `not_provided` or descriptive evidence. [Tool Card](../src/bridge/tool_packages/cards/P0-12.md). |
| Call | Shared CLI/SDK with `tool_id=P0-12`; start from the [request example](../examples/requests/p0_12_graft_assessment.json). |
| Current evidence / status | Synthetic cases verify aggregation, provenance and `not_provided`. Results remain `candidate/shadow`; they establish neither efficacy, release suitability nor a pre-transplant score. [Validation](validation/p0_12_graft_assessment_20260825.md). |

## Methods, Schemas and evidence

- `bridge-tool describe P0-XX` reports the installed version, schemas,
  environment and registered method IDs.
- `bridge-tool input-contract P0-XX` reports Agent-facing input modes and role
  cardinality.
- The [catalog-backed method shortlist](../knowledge/active-methods.md) records
  candidate methods and sources; catalog presence does not mean execution.
- The [public Schema directory](../src/bridge/resources/schemas/) defines the
  language-neutral object contracts.

Across every package, `missing`, `unknown`, `unavailable`, `negative` and `alert`
remain distinct. A valid candidate run is not a scientific release.
