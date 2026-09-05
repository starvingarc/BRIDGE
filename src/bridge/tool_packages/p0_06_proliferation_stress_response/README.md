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
- **Output:** tool v0.6.1 emits profile v0.3. Legacy projections preserve the
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
  process-causality evidence.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-06)
- [Tool Card — authoritative runtime contract](../cards/P0-06.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/proliferation_stress_response_task_card.md)
- [Request example](../../../../examples/requests/p0_06_proliferation_stress_response.json)
- [Method-runtime request](../../../../examples/requests/p0_06_process_method_runtime.json)
- [Validation index](../../../../docs/validation/)

Use `bridge-tool describe P0-06` for the installed version, schemas,
environment and registered method IDs.
