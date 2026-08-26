# P0-06 Proliferation & Stress Response

This directory contains the deterministic program-evidence aggregation package.

## Interface at a glance

- **Input:** seven checksummed JSON objects binding case, product, developmental
  window, ProgramSpec, P0-02 profile, ProtocolIR and precomputed evidence.
- **Output:** `ProliferationStressResponseProfile` and transcriptomic review flags
  with coverage, LOD, confounding and process-attribution states.
- **Boundary:** a review flag is not cell fitness, safety, tumorigenicity, potency
  or process-causality evidence, and the package emits no domain score.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-06)
- [Tool Card — authoritative runtime contract](../cards/P0-06.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/proliferation_stress_response_task_card.md)
- [Request example](../../../../examples/requests/p0_06_proliferation_stress_response.json)
- [Validation record](../../../../docs/validation/p0_06_proliferation_stress_response_20260825.md)

Use `bridge-tool describe P0-06` for the installed version, schemas, environment
and registered method IDs.
