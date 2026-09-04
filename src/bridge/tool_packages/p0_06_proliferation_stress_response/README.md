# P0-06 Proliferation & Stress Response

This directory contains the program-scoring and evidence-aggregation package.

## Interface at a glance

- **Legacy aggregation:** seven checksummed JSON objects bind case, product,
  developmental window, ProgramSpec, P0-02 profile, ProtocolIR and precomputed
  evidence.
- **Method runtime:** eleven checksummed JSON objects and one checksummed
  normalized H5AD bind P0-02 V3 states, biological units and runtime parameters.
  Program genes, weights and phases live only in the checksummed ProgramSpec;
  the method spec selects program IDs without duplicating that content.
  Eligibility refuses a ProtocolIR independent-replicate count above the
  distinct groups in the bound BiologicalUnitManifest; equal or lower counts
  retain the existing conservative attribution rule.
- **Output:** v0.5 always emits `ProliferationStressResponseProfile` v0.2;
  without a MeasurementSpec its projection state is `not_requested` and its
  bindings are empty. An optional compatible `MeasurementSpecV2` adds one
  checksummed gate-facing measurement artifact for every program evidence record.
  The binding preserves the exact source state and its projected shared state:
  `not_applicable`, `unavailable`, and `not_assessed` become `unavailable`;
  `cannot_resolve` becomes measurement-scoped `unknown`;
  `not_detected_above_lod` becomes `negative`; and
  `transcriptomic_review_flag` becomes `alert`. Method mode additionally
  emits `ProcessMethodBundle` with Scanpy, decoupler and cell-cycle summaries
  bound to the exact ProgramSpec SHA-256. Both modes emit package-owned typed
  visualization data, exact TSV fallbacks, deterministic SVG/PNG/PDF renders
  and a visualization artifact set for stage/state-conditioned program evidence,
  method-separated program-score summaries and cell-cycle evidence.
- **Current visualization limits:** no numeric reference envelope, ordered
  ProtocolIR timeline, numeric LOD/UCB or spike-in recovery curve, or CNV
  visualization is produced; unavailable views remain `not_assessed`.
- **Projection boundary:** every source record remains intact in the profile.
  Unknown and unavailable projections carry no numeric fields and are never
  backfilled with zero; negative and alert projections preserve valid source
  values. These shared states add no biological threshold or safety meaning.
- **Boundary:** a review flag is not cell fitness, safety, tumorigenicity,
  potency or process-causality evidence, and the package emits no domain score.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-06)
- [Tool Card — authoritative runtime contract](../cards/P0-06.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/proliferation_stress_response_task_card.md)
- [Request example](../../../../examples/requests/p0_06_proliferation_stress_response.json)
- [Method-runtime request](../../../../examples/requests/p0_06_process_method_runtime.json)
- [Validation index](../../../../docs/validation/)

Use `bridge-tool describe P0-06` for the installed version, schemas,
environment and registered method IDs.
