# P0-03 Target Identity & Regional Fidelity

This directory contains the deterministic target and regional evidence package.

## Interface at a glance

- **Input:** eleven checksummed JSON objects binding the ProductCase, product and
  role definitions, assessment/measurement contracts, P0-01/P0-02 evidence,
  vocabulary and reference.
- **Output:** three configured descriptive ratios with applicability, reason and
  provenance bindings.
- **Boundary:** transcriptomic regional support is not spatial localization, and
  no state role, threshold or domain score is embedded in the executor.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-03)
- [Tool Card — authoritative runtime contract](../cards/P0-03.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/target_regional_identity_task_card.md)
- [Request example](../../../../examples/requests/p0_03_target_regional_evidence.json)
- [Validation record](../../../../docs/validation/p0_03_target_regional_20260825.md)

Use `bridge-tool describe P0-03` for the installed version, schemas, environment
and registered method IDs.
