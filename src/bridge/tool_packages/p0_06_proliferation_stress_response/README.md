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
- **Output:** `ProliferationStressResponseProfile`; method mode additionally
  emits `ProcessMethodBundle` with Scanpy, decoupler and cell-cycle summaries
  bound to the exact ProgramSpec SHA-256.
- **Boundary:** a review flag is not cell fitness, safety, tumorigenicity, potency
  or process-causality evidence, and the package emits no domain score.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-06)
- [Tool Card — authoritative runtime contract](../cards/P0-06.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/proliferation_stress_response_task_card.md)
- [Request example](../../../../examples/requests/p0_06_proliferation_stress_response.json)
- [Validation record](../../../../docs/validation/p0_06_proliferation_stress_response_20260825.md)
- [Method-runtime request](../../../../examples/requests/p0_06_process_method_runtime.json)
- [Real-method validation](../../../../docs/validation/p0_06_real_methods_20260827.md)

Use `bridge-tool describe P0-06` for the installed version, schemas,
environment and registered method IDs.
