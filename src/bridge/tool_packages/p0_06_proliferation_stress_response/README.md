# P0-06 Proliferation & Stress Response

This directory contains the program-scoring and evidence-aggregation package.

## Interface at a glance

- **Legacy aggregation:** seven checksummed JSON objects bind case, product,
  developmental window, ProgramSpec, P0-02 profile, ProtocolIR and precomputed
  evidence; an independent MeasurementSpec remains optional.
- **Method runtime:** twelve checksummed JSON objects, including a required
  P0-06 MeasurementSpec and caller/data-owner biological-unit attestation
  receipt, bind P0-02 V3 states, biological units and the exact selected DataView
  H5AD. It accepts normalized expression or integer raw
  counts; raw counts receive deterministic in-memory 10,000 scaling and `log1p`.
  Its bundle records recipe ID `bridge_normalize_total_log1p_v0.1` and target
  sum `10000.0`; the recipe ID is package metadata, not a knowledge-catalog
  Method reference.
  Program genes, weights and phases remain in the checksummed ProgramSpec; the
  method spec only selects program IDs and execution parameters. A caller-owned
  `ProgramEvidenceBundle` is refused in this mode.
- **Output:** tool v0.7.0 emits profile v0.3. Legacy projections preserve the
  legacy evidence-state mapping. Method projections are created one-to-one from
  actual program-score and cell-cycle summaries: available values are `inferred`;
  `not_assessed` values remain numeric-null `unavailable`. Both use
  `score_state=unavailable` and `domain_score=null`. Method mode also emits
  `ProcessMethodBundle` v0.2 with exact matrix semantics and normalization
  lineage. Both modes emit checksummed artifacts, typed visualization data and
  deterministic TSV/SVG/PNG/PDF output.
- **Current visualization limits:** no numeric reference envelope, ordered
  ProtocolIR timeline, numeric LOD/UCB, spike-in recovery curve or CNV
  visualization; unavailable views remain `not_assessed`.
- **Boundary:** P0-06 adds no biological threshold, state definition, score or
  alert. The attestation receipt is a caller/data-owner assertion; runtime checks
  its immutable bindings but does not authenticate the attestor or establish
  independent review. A review flag is not fitness, safety, potency or
  process-causality evidence. The source-bound mode verifies correspondence
  within a caller-supplied P0-02 bundle; it does not authenticate a fabricated
  bundle or replace deployment provenance controls.

## Source-bound observation mode

method_runtime_source_bound has the same twelve roles and expression constraints
as method_runtime, but its process_method_input must use
bridge://schemas/process-method-input/v0.2 with object_version 0.2.0. The CLI and
SDK select the mode from that exact Schema/version pair; there is no parameter
switch and v0.1/v0.2 combinations cannot be mixed.

The v0.2 input retains the v0.1 case, DataView and biological-unit lineage fields,
and replaces caller-authored observation_states with one required
source_observations descriptor. It records the fixed P0-02 source format and tool
ID, producer run/version, absolute manifest and evidence paths with strict SHA-256
values, the evidence artifact ID, and label_level L1.

A logical source_observations value is:

    {
      "source_format": "p0_02_cell_state_evidence_parquet_v0.1",
      "producer_tool_id": "P0-02",
      "producer_run_ref": "<p0-02-run>",
      "producer_tool_version": "<exact version>",
      "artifact_manifest_path": "/absolute/path/artifact_manifest.json",
      "artifact_manifest_sha256": "<64 lowercase hex>",
      "evidence_artifact_id": "artifact:<p0-02-run>:evidence",
      "evidence_path": "/absolute/path/cell_state_evidence.parquet",
      "evidence_sha256": "<64 lowercase hex>",
      "label_level": "L1"
    }

The loader checks regular non-symlink files and hashes before and after reads,
binds manifest/profile/evidence lineage, validates exact observation membership
using the existing observation digest, and reconciles L1 counts with the V3
profile. Malformed prediction JSON, unsupported producer semantics, checksum or
lineage drift, duplicate/missing IDs, unavailable Parquet support, and file
replacement fail with typed reasons. Whole-product summaries retain every
declared observation. State-specific summaries use only unique candidate states
allowed by that ProgramSpec; conflict and unavailable rows are never assigned,
and an all-conflict source produces no invented state-conditioned zero.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-06)
- [Tool Card — authoritative runtime contract](../cards/P0-06.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/proliferation_stress_response_task_card.md)
- [Request example](../../../../examples/requests/p0_06_proliferation_stress_response.json)
- [Method-runtime request](../../../../examples/requests/p0_06_process_method_runtime.json)
- [Validation index](../../../../docs/validation/)

Use `bridge-tool describe P0-06` for the installed version, schemas,
environment and registered method IDs.
