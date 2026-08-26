# Tool Package Guide

The 12 high-level P0 tools are the current Agent-callable foundation, not the
complete BRIDGE product. All are implemented and callable; all remain scientific
candidates, and P0-02 and downstream domain evidence remain shadow unless their
versioned scientific authorities are approved. The future Agent will orchestrate
these packages through the same contracts rather than reproduce their scientific
logic.

**Jump to:** [P0-01–P0-02 intake and state evidence](#intake-and-state-evidence) ·
[P0-03–P0-06 product-domain evidence](#product-domain-evidence) ·
[P0-07/P0-12 comparison and graft context](#comparison-and-graft-context) ·
[P0-08–P0-11 evidence governance and export](#evidence-governance-and-export)

```text
upload → audit → state evidence → domain evidence → sufficiency → graph → verify → export
          P0-01      P0-02          P0-03–06        P0-08      P0-09   P0-10   P0-11

P0-07 compares eligible product bundles. P0-12 keeps graft evidence independent.
```

## Which document is authoritative?

Each package has four deliberately different documentation layers:

1. The package `README.md` is a short landing page for code readers.
2. The **Tool Card** is the authoritative human-readable runtime contract:
   input fields and roles, output objects, eligibility, refusal/degradation
   semantics, examples and scientific boundaries.
3. The **scientific task card** records the biological question, data and
   reference assumptions, candidate methods, validation design and literature.
4. The **validation record** states what was actually tested at a specific
   implementation version; it is not a scientific release certificate.

Public JSON Schemas remain the machine-readable interface. If an overview and a
versioned Schema disagree, stop and resolve the discrepancy rather than inferring
an answer from prose.

Shared calls are:

```bash
bridge-tool describe P0-XX
bridge-tool input-contract P0-XX
bridge-tool validate --request /absolute/path/to/request.json
bridge-tool run --request /absolute/path/to/request.json
```

The Python SDK exposes the same `list_tools`, `describe_tool`, `describe_tool_input`,
`validate_request` and `run_tool` surface. P0-01 and P0-02 use the expression-
asset `ToolRequest` v0.1 envelope; P0-03 through P0-12 use checksummed local JSON
objects in `ToolRequestV2`.

## Intake and state evidence

| Tool | Purpose | Inputs | Primary outputs | Documentation |
|---|---|---|---|---|
| **P0-01 Input Audit & QC** | Establish whether an uploaded expression object is structurally and analytically ready. | Declared H5AD, 10x H5 or 10x MTX asset; assay, matrix semantics, sample/capture metadata and MeasurementSpec. | QC readiness profiles, immutable data-view and biological-unit lineage artifacts, raw QC measurements, visualizations and manifest. | [Package](../src/bridge/tool_packages/p0_01_input_qc/README.md) · [Tool Card](../src/bridge/tool_packages/cards/P0-01.md) · [Task](bridge_spec_v0.1/input_audit_qc_task_card.md) · [Examples](../examples/requests/p0_01_count_ready.json) · [Validation](validation/p0_01_server_integration_20260810.md) |
| **P0-02 Cell-State Evidence** | Compare QC-qualified product expression with reviewed reference and marker/program channels without forcing a released label. | Expression views, modality, annotation vocabulary, reference candidates and provenance; optional typed P0-01 handoff. | Source-aware Cell-State evidence and optional V3 profile with explicit denominators, uncertainty and lineage bindings; no assigned state or score. | [Package](../src/bridge/tool_packages/p0_02_cell_state/README.md) · [Tool Card](../src/bridge/tool_packages/cards/P0-02.md) · [Task](bridge_spec_v0.1/cell_state_annotation_task_card.md) · [Example](../examples/requests/p0_02_cell_state.json) · [Validation](validation/p0_02_server_integration_20260811.md) |

P0-02's pseudobulk reference correlation is a reference-similarity summary, not
replicate-aware differential-expression inference. Its marker/program channel is
complementary rather than independent because curation sources overlap.

## Product-domain evidence

| Tool | Purpose | Inputs | Primary outputs | Documentation |
|---|---|---|---|---|
| **P0-03 Target Identity & Regional Fidelity** | Aggregate externally defined target-lineage and transcriptomic regional support. | Eleven checksummed objects binding ProductCase, product definition, role map, assessment and Measurement specs, P0-02/P0-01 evidence, vocabulary and reference. | Three configured descriptive ratios plus binding, applicability, reason and provenance records. | [Package](../src/bridge/tool_packages/p0_03_target_regional/README.md) · [Tool Card](../src/bridge/tool_packages/cards/P0-03.md) · [Task](bridge_spec_v0.1/target_regional_identity_task_card.md) · [Example](../examples/requests/p0_03_target_regional_evidence.json) · [Validation](validation/p0_03_target_regional_20260825.md) |
| **P0-04 Developmental Compatibility** | Aggregate alignment to an externally confirmed developmental window. | Checksummed ProductCase, product definition, DevelopmentWindowSpec, DevelopmentStateMap, MeasurementSpec and P0-02 profile, with optional declared timepoint series. | `DevelopmentalCompatibilityResult` with window/earlier/later/branch/unresolved composition and explicit unavailable states. | [Package](../src/bridge/tool_packages/p0_04_developmental_compatibility/README.md) · [Tool Card](../src/bridge/tool_packages/cards/P0-04.md) · [Task](bridge_spec_v0.1/developmental_compatibility_task_card.md) · [Example](../examples/requests/p0_04_developmental_compatibility.json) · [Validation](validation/p0_04_developmental_compatibility_v0.2.md) |
| **P0-05 Off-target Control** | Account for the whole product under external role and rare-state calibration rules. | Six checksummed objects: ProductCase, product definition, StateRoleMap, OffTargetAssessmentSpec, P0-02 profile and precomputed evidence bundle. | `OffTargetControlProfile` with role composition, unknown reasons, coverage and rare-state detectability states. | [Package](../src/bridge/tool_packages/p0_05_off_target_control/README.md) · [Tool Card](../src/bridge/tool_packages/cards/P0-05.md) · [Task](bridge_spec_v0.1/off_target_control_task_card.md) · [Example](../examples/requests/p0_05_off_target_control.json) · [Validation](validation/p0_05_off_target_control_20260825.md) |
| **P0-06 Proliferation & Stress Response** | Aggregate precomputed, stage-conditioned proliferation, stress-response and related review signals. | Seven checksummed objects binding case, product, developmental window, ProgramSpec, P0-02 profile, ProtocolIR and evidence bundle. | `ProliferationStressResponseProfile` and transcriptomic review flags with coverage, LOD, confounding and attribution states. | [Package](../src/bridge/tool_packages/p0_06_proliferation_stress_response/README.md) · [Tool Card](../src/bridge/tool_packages/cards/P0-06.md) · [Task](bridge_spec_v0.1/proliferation_stress_response_task_card.md) · [Example](../examples/requests/p0_06_proliferation_stress_response.json) · [Validation](validation/p0_06_proliferation_stress_response_20260825.md) |

These tools bind externally versioned biology and aggregate precomputed evidence.
They do not hard-code a cell-state map, developmental window, threshold or
product role, and they emit no spatial-localization, biological-age, safety or
release conclusion.

## Comparison and graft context

| Tool | Purpose | Inputs | Primary outputs | Documentation |
|---|---|---|---|---|
| **P0-07 Product Comparison & Stability** | Compare cases only when an explicit comparability and confounding contract permits it. | ComparisonStabilitySpec, ComparisonCaseManifest and two to twenty checksummed precomputed product-evidence bundles. | `ProductComparisonStabilityProfile` with comparability state, raw summaries and descriptive deltas/ranges. | [Package](../src/bridge/tool_packages/p0_07_product_comparison_stability/README.md) · [Tool Card](../src/bridge/tool_packages/cards/P0-07.md) · [Task](bridge_spec_v0.1/product_comparison_stability_task_card.md) · [Example](../examples/requests/p0_07_product_comparison_stability.json) · [Validation](validation/p0_07_product_comparison_stability_v0.2.md) |
| **P0-12 Optional Graft Assessment** | Keep post-transplant evidence independent from the pre-transplant product profile. | Either no object inputs, or one checksummed GraftCase, GraftAssessmentSpec and precomputed GraftEvidenceBundle. | `GraftAssessmentResult` with `not_provided` or descriptive graft evidence and no pre-transplant backfill. | [Package](../src/bridge/tool_packages/p0_12_graft_assessment/README.md) · [Tool Card](../src/bridge/tool_packages/cards/P0-12.md) · [Task](bridge_spec_v0.1/graft_assessment_task_card.md) · [Example](../examples/requests/p0_12_graft_assessment.json) · [Validation](validation/p0_12_graft_assessment_20260825.md) |

P0-07 never declares a winner or equivalence. P0-12 never turns graft evidence
into a pre-transplant score, threshold, training label or efficacy claim.

## Evidence governance and export

| Tool | Purpose | Inputs | Primary outputs | Documentation |
|---|---|---|---|---|
| **P0-08 Evidence Sufficiency** | Apply deterministic Data Readiness, Model Robustness and Prior Applicability gates to existing evidence. | Candidate GateRuleSpec and one to five domain bundles containing versioned measurement, QC, validation, prior and sensitivity records. | Canonical `EvidenceSufficiencyRunResultV2`, per-domain profiles, gate trace and case summary; no new measurement or score. | [Package](../src/bridge/tool_packages/p0_08_evidence_sufficiency/README.md) · [Tool Card](../src/bridge/tool_packages/cards/P0-08.md) · [Task](bridge_spec_v0.1/evidence_sufficiency_task_card.md) · [Example](../examples/requests/p0_08_evidence_sufficiency.json) · [Validation](validation/p0_08_evidence_sufficiency_20260813.md) |
| **P0-09 Evidence Compiler & Reconciler** | Compile immutable atomic evidence, explicit missing requirements and versioned conflicts into bounded evidence graphs. | Compilation bundle, P0-08 profiles, EvidenceFamily/Claim/Reconciliation registries and optional bound prior or comparison graphs. | Evidence/requirement/reconciliation record sets, JSON/Parquet graph facts, manifests and seven bounded read-only queries. | [Package](../src/bridge/tool_packages/p0_09_evidence_compiler/README.md) · [Tool Card](../src/bridge/tool_packages/cards/P0-09.md) · [Task](bridge_spec_v0.1/evidence_compiler_task_card.md) · [Example](../examples/requests/p0_09_evidence_compiler.json) · [Validation](validation/p0_09_evidence_compiler_20260813.md) |
| **P0-10 Claim Verifier** | Verify that a structured report preserves cited evidence values, states, scope and approved wording. | Exactly four checksummed objects: ReportDraft, P0-09 Case graph manifest, packaged-authority ClaimPolicySpec and StatementRegistry. | One `ClaimVerificationResult` correspondence receipt; no report copy, measurement, score or release permission. | [Package](../src/bridge/tool_packages/p0_10_claim_verifier/README.md) · [Tool Card](../src/bridge/tool_packages/cards/P0-10.md) · [Task](bridge_spec_v0.1/claim_verifier_task_card.md) · [Example](../examples/requests/p0_10_claim_verifier.json) · [Validation](validation/p0_10_claim_verifier_20260814.md) |
| **P0-11 Public-safe Export** | Rebuild an eligible structured report through a field allowlist and confirmation-bound local export. | Exactly four checksummed objects: ReportDraft, eligible P0-10 receipt, PublicExportPolicySpec and PublicExportRequest. | Allowlisted `PublicSafeReport`, export manifest and result as immutable local JSON; no upload. | [Package](../src/bridge/tool_packages/p0_11_public_safe_export/README.md) · [Tool Card](../src/bridge/tool_packages/cards/P0-11.md) · [Task](bridge_spec_v0.1/public_safe_export_task_card.md) · [Example](../examples/requests/p0_11_public_safe_export.json) · [Validation](validation/p0_11_public_safe_export_20260825.md) |

`verified` in P0-10 means correspondence to supplied evidence and packaged policy,
not biological truth. `exported` in P0-11 means a confirmed local JSON bundle was
written, not that it was uploaded or scientifically released.

## Methods, Schemas and evidence

- `bridge-tool describe P0-XX` is the fastest way to inspect a package version,
  schemas, environment and registered method IDs.
- The [catalog-backed method shortlist](../knowledge/active-methods.md) links
  globally curated methods to their source records. P0-10 additionally owns a
  versioned [claim-verifier benchmark](validation/p0_10_claim_verifier_benchmark_v0.1.md).
- The [public Schema directory](../src/bridge/resources/schemas/) defines the
  language-neutral object contracts.
- Literature in a task card motivates a method or validation design; it does not
  promote the package, a state definition or a result to formal scientific use.

Across every package, `missing`, `unknown`, `unavailable`, `negative` and `alert`
remain distinct. A contract failure is not a biological finding, and a valid
candidate run is not a scientific release.
