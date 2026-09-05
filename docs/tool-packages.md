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
| Purpose | Measure externally configured target identity and transcriptomic regional support while preserving case, reference and biological-unit provenance. [Scientific task card](bridge_spec_v0.1/target_regional_identity_task_card.md). |
| Executable implementation | Aggregation: StateRoleMap-based target/regional ratios. Optional expression mode: `TRG-PBCORR`, `REG-PBCORR`, `TRG-NNLS`, `TRG-DECOUPLER`, `REG-DECOUPLER`, `TRG-BOOTSTRAP`, `REG-CROSSREF` and `REG-MODALITY`. P0-02 benchmark adapters remain upstream; spatial catalog candidates are not invoked. |
| Software | AnnData reads the selected H5AD; NumPy/pandas/SciPy perform pseudobulk, correlation, NNLS and bootstrap; [decoupler](https://decoupler.readthedocs.io/) runs ULM program activity; the shared Pydantic/JSON Schema runtime validates and publishes results. |
| Input → output | Eleven checksummed core objects → three descriptive ratios, typed product-composition/reference-support data, exact TSV fallbacks and SVG/PNG/PDF renders. Adding one H5AD and one `TargetRegionalMethodSpec` with expression-semantics, matched-modality and residual-applicability contracts → checksummed reference support, applicability-typed continuous weights, program activity, interval state and robustness evidence. [Tool Card](../src/bridge/tool_packages/cards/P0-03.md). |
| Call | Shared CLI/SDK with `tool_id=P0-03`; use the [aggregation request](../examples/requests/p0_03_target_regional_evidence.json) or [expression request](../examples/requests/p0_03_target_regional_expression.json). |
| Current evidence / status | Synthetic end-to-end execution verifies all eight selected methods, target/regional reference separation, biological-unit binding, typed contract refusal, residual gating and one-unit bootstrap degradation. Results remain `candidate/shadow`, `domain_score=null`; engineering execution is not biological validation. [Aggregation validation](validation/p0_03_target_regional_20260825.md) · [Expression validation](validation/p0_03_expression_methods_20260826.md). |

<a id="p0-04"></a>
## P0-04 Developmental Compatibility

| Item | Details |
|---|---|
| Purpose | Evaluate externally configured developmental-window composition, source-separated reference-stage similarity and ordered sampling-point summaries. [Scientific task card](bridge_spec_v0.1/developmental_compatibility_task_card.md). |
| Executable implementation | DevelopmentStateMap/soft-composition aggregation; sample-pseudobulk Spearman/cosine with per-unit cross-profile availability; externally gated uncalibrated cumulative ordinal logistic baseline; decoupler ULM; independence-group bootstrap. Sampling-point order is categorical and continuous-time aliases return `not_assessed`. |
| Software | AnnData, NumPy, Pandas, SciPy, scikit-learn, decoupler and Matplotlib in `ENV-DEVELOPMENT-PY-v0.2`. Conditional R, trajectory, velocity and OT catalog entries are not invoked by v0.4. |
| Input → output | Eleven traceable case/P0-01/P0-02/reference objects, plus optional sampling points; expression mode adds one H5AD and `DevelopmentMethodSpec` → result, optional method bundle, typed visualization data, exact TSV fallbacks and deterministic SVG/PNG/PDF figures. [Tool Card](../src/bridge/tool_packages/cards/P0-04.md). |
| Call | `bridge-tool describe/input-contract/validate/run` with `tool_id=P0-04`; see the [request](../examples/requests/p0_04_developmental_compatibility.json) and [method spec](../examples/objects/p0_04_development_method_spec.json). |
| Current evidence / status | `candidate/shadow`, `domain_score=null`. Reference similarity is a forced ranking among supplied labels without calibrated rejection, not biological age or release evidence; ordered sampling points do not establish a trajectory. [Historical validation](validation/p0_04_developmental_compatibility_v0.3.md). |

<a id="p0-05"></a>
## P0-05 Off-target Control

| Item | Details |
|---|---|
| Purpose | Account within the declared primary denominator for product-role composition, uncertainty, rare-state detectability and supplied OOD evidence under versioned external rules. [Scientific task card](bridge_spec_v0.1/off_target_control_task_card.md). |
| Executable implementation | Role-aware soft composition plus eight selectors: Clopper-Pearson count intervals, hard/soft sensitivity, independence-group bootstrap, rare-state intervals, empirical spike-in detection hit-rate curves, single-state at-least-one binomial planning, source-family disagreement and ordered OOD coordination. |
| Software | Pydantic/JSON Schema runtime, [NumPy](https://numpy.org/) bootstrap and [SciPy](https://scipy.org/) beta quantiles; remaining aggregation, design and coordination code is internal and deterministic. Deep OOD models and rare-cluster discovery tools in the catalog are not invoked. |
| Input → output | Compatible six-object aggregation → `OffTargetControlProfile`; ten-object method mode adds P0-02 V3, immutable P0-01-declared lineage, an exact `analysis_execution` caller attestation receipt and method inputs → checksummed `OffTargetMethodBundle`. Either mode may add an independent P0-05 MeasurementSpec; projected runs verify manifest analysis, independence and cell/nucleus units before emitting `MeasurementResultV2`. Both modes publish typed data, exact TSV fallbacks and deterministic SVG/PNG/PDF figures. [Tool Card](../src/bridge/tool_packages/cards/P0-05.md). |
| Call | `bridge-tool describe P0-05`, `bridge-tool input-contract P0-05`, then shared validate/run CLI or SDK; start from the [request example](../examples/requests/p0_05_off_target_control.json). |
| Current evidence / status | Synthetic fixtures execute all eight selectors and verify deterministic seeded runs, receipt/attestation binding, lineage/refusal semantics and artifact reuse. Outputs remain `candidate/shadow`, `domain_score=null`; a caller attestation is not biological validation, independent review or safety evidence. [Receipt validation](validation/p0_05_biological_unit_attestation_receipt_20260905.md). |

<a id="p0-06"></a>
## P0-06 Proliferation & Stress Response

| Item | Details |
|---|---|
| Purpose | Score externally defined proliferation, stress and cell-cycle programs, then aggregate them by biological unit and cell state. [Scientific task card](bridge_spec_v0.1/proliferation_stress_response_task_card.md). |
| Executable implementation | [Scanpy score_genes](https://scanpy.readthedocs.io/en/stable/generated/scanpy.tl.score_genes.html), [decoupler ULM](https://decoupler.readthedocs.io/en/latest/api/generated/decoupler.mt.ulm.html), [Scanpy cell-cycle scoring](https://scanpy.readthedocs.io/en/stable/api/scanpy.tl.score_genes_cell_cycle.html), deterministic sample/state aggregation and the existing design/confounding audit. |
| Software | AnnData, Scanpy, decoupler, NumPy, pandas and SciPy, plus the shared Pydantic/JSON Schema runtime. UCell, AUCell, pseudobulk and CNV methods remain independent candidates and are not called by this adapter. |
| Input → output | Legacy: seven evidence objects and an optional P0-06 MeasurementSpec → profile v0.3 plus the historical record projection. Method runtime: six core objects (including P0-02 V3 lineage), biological-unit mapping, selector-only method spec/input, a required independent P0-06 MeasurementSpec and the exact selected DataView H5AD → method bundle v0.2, profile v0.3 and one checksummed MeasurementResultV2 per actual method summary. Normalized expression is used directly; integer raw counts receive deterministic in-package 1e4 scaling and `log1p`. Caller-provided precomputed evidence is forbidden in method mode. [Tool Card](../src/bridge/tool_packages/cards/P0-06.md). |
| Call | Shared CLI/SDK with `tool_id=P0-06`; use the [legacy request](../examples/requests/p0_06_proliferation_stress_response.json) or [method-runtime request](../examples/requests/p0_06_process_method_runtime.json). |
| Current evidence / status | Exact DataView binding, raw-count normalization lineage, real-summary projection, missing-value preservation and deterministic artifacts are exercised in the engineering suite. Outputs remain `candidate/shadow`, `domain_score=null` and do not establish cell fitness, safety or potency. [Method-measurement closeout](validation/p0_06_method_measurement_closeout_20260905.md). |

<a id="p0-07"></a>
## P0-07 Product Comparison & Stability

| Item | Details |
|---|---|
| Purpose | Compare product cases only when an explicit comparability and confounding contract permits it. [Scientific task card](bridge_spec_v0.1/product_comparison_stability_task_card.md). |
| Executable implementation | Deterministic comparability/confounding gate and raw deltas; optional method mode executes Hedges g, Jensen-Shannon distance, Spearman profile correlation, one-dimensional Wasserstein distance and within-group dispersion. Registered R/Bioconductor, Bayesian, mixed-model and integration candidates are not executed. |
| Software | [SciPy](https://docs.scipy.org/doc/scipy/) for Jensen-Shannon, Spearman and Wasserstein calls; [NumPy](https://numpy.org/doc/stable/) plus a small BRIDGE Hedges-g implementation; shared Pydantic/JSON Schema runtime. |
| Input → output | Base spec, manifest and 2–20 product-evidence bundles → `ProductComparisonStabilityProfile`; method mode adds checksummed method spec/input → `ComparisonMethodBundle`. Both modes publish typed comparability, declared-analysis-unit and method-evidence data, exact TSV fallbacks and deterministic SVG/PNG/PDF figures. [Tool Card](../src/bridge/tool_packages/cards/P0-07.md). |
| Call | Shared CLI/SDK with `tool_id=P0-07`; see the [base request](../examples/requests/p0_07_product_comparison_stability.json) and [method-runtime request](../examples/requests/p0_07_comparison_method_runtime.json). |
| Current status | Results remain `candidate/shadow`, `domain_score=null`. Observed analysis-unit ranges are not confidence intervals, raw deltas have no interval, bundle counts do not establish independent replication, and method-specific quantities are neither combined nor ranked. |

<a id="p0-08"></a>
## P0-08 Evidence Sufficiency

| Item | Details |
|---|---|
| Purpose | Decide whether existing domain evidence is ready for interpretation under a versioned gate specification. [Scientific task card](bridge_spec_v0.1/evidence_sufficiency_task_card.md). |
| Executable implementation | Deterministic gate executor, packaged rule registry and validator, canonical per-domain handoff objects, and table-backed static evidence figures. |
| Software | Shared Pydantic/JSON Schema runtime, Matplotlib, Python standard library and packaged JSON rule/reason-code resources. |
| Input → output | GateRuleSpec, one to five domain bundles, their evidence objects, and a checksummed ProductCase when case/QC context is declared → `EvidenceSufficiencyRunResultV2`, canonical v0.2 profile objects, gate trace, case summary, typed visualization data, three TSV tables and three SVG/PNG/PDF figure sets. [Tool Card](../src/bridge/tool_packages/cards/P0-08.md). |
| Call | Shared CLI/SDK with `tool_id=P0-08`; start from the [request example](../examples/requests/p0_08_evidence_sufficiency.json). |
| Current evidence / status | ProductCase, ProductDefinition, QC-selected view, assay and biological-unit lineage are checked as one case boundary; absent or unknown QC authorization fails closed. The module creates no measurement or score and remains a non-formal candidate. Axis terms apply only to the bound domain MeasurementSpec and candidate rules; record and evidence-family counts are not independent evidence. [Validation record](validation/p0_08_case_binding_v0.5.md). |

<a id="p0-09"></a>
## P0-09 Evidence Compiler & Reconciler

| Item | Details |
|---|---|
| Purpose | Compile immutable evidence, explicit missing requirements and versioned conflicts into a bounded evidence graph. [Scientific task card](bridge_spec_v0.1/evidence_compiler_task_card.md). |
| Executable implementation | Deterministic compiler/reconciler, append-only versioning, graph reconstruction and seven named read-only queries; no arbitrary writes or Cypher. |
| Software | [NetworkX](https://networkx.org/documentation/stable/) for reconstruction/invariant checks and [PyArrow/Parquet](https://arrow.apache.org/docs/python/) for graph facts, plus the shared runtime. |
| Input → output | Compilation bundle, either direct P0-08 v0.1/v0.2 profiles or canonical P0-08 v0.2 run results, and EvidenceFamily, Claim and Reconciliation registries → record sets, JSON/Parquet graph facts, three typed figures with complete TSV fallbacks, Cytoscape elements and manifests. [Tool Card](../src/bridge/tool_packages/cards/P0-09.md). |
| Call | Shared CLI/SDK with `tool_id=P0-09`; start from the [request example](../examples/requests/p0_09_evidence_compiler.json). |
| Current evidence / status | Implemented candidate. Canonical run-result ingestion supports case/comparison initial and append modes; duplicate run identity fails closed, while record-level provenance drift is isolated as partial. Missing evidence remains a requirement; record/family counts are not independent evidence; shadow input is not promoted. P0-08 v0.2 still lacks versioned family identity, so formal compilation remains conservatively unavailable. [Validation record](validation/p0_09_sufficiency_v2_ingestion_v0.4.md). |

<a id="p0-10"></a>
## P0-10 Claim Verifier

| Item | Details |
|---|---|
| Purpose | Verify that a structured report preserves cited values, units, states, scope and package-approved wording. [Scientific task card](bridge_spec_v0.1/claim_verifier_task_card.md). |
| Executable implementation | Independent Draft 2020-12 validation of four structured inputs, deterministic claim verification, exact numeric comparison, typed local-review views and release-state aggregation over the P0-09 graph. |
| Software | [regex](https://github.com/mrabarnett/mrab-regex) for bounded Unicode matching, Python [Decimal](https://docs.python.org/3/library/decimal.html), Pydantic/jsonschema, Matplotlib with a checksummed Noto Sans CJK font and the P0-09 query layer. |
| Input → output | ReportDraft, P0-09 Case graph manifest, package-authoritative ClaimPolicySpec and StatementRegistry → one `ClaimVerificationResult`, three typed review views with complete TSV fallbacks and an artifact manifest. [Tool Card](../src/bridge/tool_packages/cards/P0-10.md). |
| Call | Shared CLI/SDK with `tool_id=P0-10`; start from the [request example](../examples/requests/p0_10_claim_verifier.json). |
| Current evidence / status | Implemented candidate. `verified` is bounded to deterministic correspondence under the current cited evidence, policy and statement registry; it is not biological truth, public-export clearance or release permission. |

<a id="p0-11"></a>
## P0-11 Public-safe Export

| Item | Details |
|---|---|
| Purpose | Prepare local public-facing candidates through an allowlisted report rebuild or a format-aware artifact audit. [Scientific task card](bridge_spec_v0.1/public_safe_export_task_card.md). |
| Executable implementation | `report_export` rebuilds public JSON and records whether a supplied value matches the candidate digest. `artifact_audit` checks one hash-bound byte snapshot per JSON, Markdown, CSV or SVG candidate without uploading it. |
| Software | Pydantic/JSON Schema and `hashlib`; [markdown-it-py](https://markdown-it-py.readthedocs.io/) and [regex](https://github.com/mrabarnett/mrab-regex); Python `csv.reader(strict=True)`; [defusedxml](https://github.com/tiran/defusedxml); system `file` on a read-only snapshot; Matplotlib with DejaVu Sans for local review figures. |
| Input → output | Four report-export objects → three public-candidate JSON files plus two typed local-review figures; or audit policy plus artifact manifest → one path-free result plus two typed local-review figures. Every figure has a complete TSV fallback and SVG/PNG/PDF renders. [Tool Card](../src/bridge/tool_packages/cards/P0-11.md). |
| Call | Shared CLI/SDK with `tool_id=P0-11`; use the [report example](../examples/requests/p0_11_public_safe_export.json) or [artifact-audit example](../examples/requests/p0_11_public_artifact_audit.json). |
| Current evidence / status | Implemented candidate. A matching candidate digest does not authenticate its supplier or constitute approval. “No registered rule blocked” is limited to executed rules, not comprehensive de-identification. `ToolRunV2` and the generic internal provenance manifest are not public-safe downloads; `exported` is neither upload nor scientific release. |

<a id="p0-12"></a>
## P0-12 Optional Graft Assessment

| Item | Details |
|---|---|
| Purpose | Characterize optional post-transplant graft evidence without feeding it back into the pre-transplant product profile. [Scientific task card](bridge_spec_v0.1/graft_assessment_task_card.md). |
| Executable implementation | Three modes behind one adapter: explicit `not_provided`; deterministic aggregation of precomputed graft records; or one-declared-graft H5AD analysis with shared structural/count-matrix validation, descriptive soft composition over all uploaded rows, aggregation-matched sample-profile reference correlation and external marker-program means. Raw counts produce `sample_pseudobulk`; log-normalized values produce `sample_mean_log_expression`. Multiple sample IDs are technical samples, not independent biological replicates. State probabilities, reference profiles, programs and analysis settings are external inputs; graft QC is `not_reassessed`. |
| Software | [AnnData](https://anndata.readthedocs.io/) and [Scanpy](https://scanpy.readthedocs.io/) read and normalize H5AD; the shared P0-01 validator checks matrix structure and count semantics; [NumPy](https://numpy.org/doc/), [pandas](https://pandas.pydata.org/docs/) and [SciPy](https://docs.scipy.org/doc/scipy/) provide descriptive aggregation and Spearman correlation. No classifier, bootstrap inference, training or external graft-outcome model runs. |
| Input → output | No objects; three precomputed JSON objects; or GraftCase plus checksummed H5AD manifest, analysis spec, reference panel and marker-program collection → `GraftAssessmentResult` or `GraftExpressionAnalysisResult`, typed visualization data, three complete TSV fallbacks and matching SVG/PNG/PDF renders. [Tool Card](../src/bridge/tool_packages/cards/P0-12.md). |
| Call | Shared CLI/SDK with `tool_id=P0-12`; start from the [no-graft](../examples/requests/p0_12_graft_assessment.json) or [expression-analysis](../examples/requests/p0_12_expression_analysis.json) request. |
| Current evidence / status | Implemented candidate. Figures describe the declared specimen scope, supplied state-probability mass among uploaded graft-derived profiles, reference-profile correlation and registered-program mean expression. Technical samples remain nested within one declared graft; results are descriptive, `candidate/shadow`, `domain_score=null`, and do not establish tissue-wide composition, biological replication, maturity, function, efficacy, safety or release suitability. |

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
