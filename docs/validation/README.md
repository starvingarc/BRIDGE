# Validation Records

Validation records bind a stated implementation to reproducible engineering or
scientific-review evidence. They do not by themselves promote a method, state,
threshold, score or product conclusion.

The public engineering check definition is in
[GitHub CI](https://github.com/starvingarc/BRIDGE/actions/workflows/ci.yml).
Use an exact-commit run or PR validation record to establish execution and status;
a configured workflow is not evidence that it ran.
The records below document specific versions and observations, not the status of
every later implementation. Current unfinished acceptance is in [active plans](../../plans/README.md).

## Tool Packages

| Package | Version-bound validation records |
|---|---|
| P0-01 Input Audit & QC | [Server integration, 2026-08-10](p0_01_server_integration_20260810.md) · [QC visualization, 2026-08-28](p0_01_input_qc_visualization_20260828.md) |
| P0-02 Cell-State Evidence | [Server integration, 2026-08-11](p0_02_cell_state_evidence.md#record-p0-02-server-integration-20260811) |
| P0-03 Target Identity & Regional Fidelity | [Aggregation validation, 2026-08-25](p0_03_target_regional.md#record-p0-03-target-regional-20260825) · [Expression-method validation, 2026-08-26](p0_03_target_regional.md#record-p0-03-expression-methods-20260826) |
| P0-04 Developmental Compatibility | [Candidate validation, 2026-08-25](p0_04_developmental_compatibility.md#record-p0-04-developmental-compatibility-v0-2) |
| P0-05 Off-target Control | [Count-only reference-support accounting, 2026-09-07](p0_05_off_target_control.md#record-p0-05-hard-count-accounting-20260907) · [Biological-unit attestation receipt, 2026-09-05](p0_05_off_target_control.md#record-p0-05-biological-unit-attestation-receipt-20260905) · [Candidate validation, 2026-08-25](p0_05_off_target_control.md#record-p0-05-off-target-control-20260825) |
| P0-06 Proliferation & Stress Response | [0.11.1 engineering scope, 2026-10-08](interpretation_evidence_20261008.md) · [Source-bound observations, 2026-09-07](p0_06_proliferation_stress_response.md#record-p0-06-source-bound-observations-20260907) · [Biological-unit attestation receipt, 2026-09-05](p0_06_proliferation_stress_response.md#record-p0-06-biological-unit-attestation-receipt-20260905) · [Method-measurement closeout, 2026-09-05](p0_06_proliferation_stress_response.md#record-p0-06-method-measurement-closeout-20260905) · [Legacy aggregation validation, 2026-08-25](p0_06_proliferation_stress_response.md#record-p0-06-proliferation-stress-response-20260825) |
| P0-08 Evidence Sufficiency | [Case-binding validation, v0.5](p0_08_case_binding_v0.5.md) |
| P0-10 Claim Verifier | [0.6.0 scoped engineering acceptance, 2026-10-08](interpretation_evidence_20261008.md) |

## P0-02 Scientific and Source Preparation

- [Development decisions and rejection assessment, 2026-09-11](cell_state_development_20260911.md)

- [Scientific-freeze pilot, 2026-08-11](p0_02_cell_state_evidence.md#record-p0-02-scientific-freeze-pilot-20260811)
- [External-source asset validation, 2026-08-12](p0_02_cell_state_evidence.md#record-p0-02-external-source-asset-20260812)
- [External-source preparation validation, 2026-08-13](p0_02_cell_state_evidence.md#record-p0-02-external-source-preparation-20260813)

The pilot remains unsealed and exploratory. External-source conversion and
lineage checks do not sign the biological FreezeGate.

## Shared Runtime and Repository Evidence

- [Product and spatial display verification](product-spatial-link.md)

- [Technical-view source preservation and graph admission](technical_view_evidence.md)
- [Source-bound candidate program execution](candidate_programs.md)

- [Single-product engineering closeout, 2026-10-04](step7_evidence_coordinator_20260911.md#single-product-engineering-closeout--2026-10-04)
- [Scope-bound assessment and privacy, 2026-09-11](step7_evidence_coordinator_20260911.md)
- Explicit report-intent handoff, 2026-09-16 (controlled historical record; not distributed)

- [Repository simplification, 2026-09-10](https://github.com/starvingarc/BRIDGE/blob/e338be7505b8b8ee97a81d9146f416af73017d8d/plans/repository-simplification.md#verification-and-remaining-gates): revision-bound engineering checks; [PR #98](https://github.com/starvingarc/BRIDGE/pull/98) tracks final CI and integration. No new scientific validation.
- [Private conversational Web preview, 2026-09-05](https://github.com/starvingarc/BRIDGE/blob/d3d69363c50541fb34320f703db2995edb27105e/docs/validation/web_preview_20260905.md)
- [Visualization data contract, 2026-08-28](visualization_data_contract_20260828.md)
- [Structured tool runtime contracts, 2026-08-13](tool_runtime_contracts.md#record-tool-runtime-structured-contracts-20260813)
- [Shared P0 scientific contract spine, 2026-08-25](shared_p0_scientific_contract_spine_20260825.md)
- [Runtime output-path hardening, 2026-08-24](https://github.com/starvingarc/BRIDGE/blob/d3d69363c50541fb34320f703db2995edb27105e/docs/validation/runtime_output_path_hardening_20260824.md)
- [Server reproducibility, 2026-08-12](https://github.com/starvingarc/BRIDGE/blob/d3d69363c50541fb34320f703db2995edb27105e/docs/validation/server_reproducibility_20260812.md)

Historical test counts and commit IDs are retained as evidence of those exact
runs. They are not a statement about the current `main` test count or release
state.

Completed repository-layout and workspace-cleanup logs are kept in Git history,
not as current operating instructions. Resource/environment provenance and
scientific validation records remain where current contracts cite them.

## Historical engineering records

Completed engineering records live at immutable Git revisions instead of beside
current scientific evidence. Existing links above retain their original revision.
The continuous-flow acceptance record (controlled historical record; not distributed)
and researcher-view design (controlled historical record; not distributed)
remain available for provenance. Current behavior belongs to the Web guide and
runtime documentation; historical acceptance does not qualify later versions.
