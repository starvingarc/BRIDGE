# P0-05 Off-target Control

This directory contains whole-product role accounting and transparent
off-target method execution.

## Interface at a glance

- **Input:** six checksummed JSON objects for compatible aggregation, or nine for
  method execution with P0-02 V3 and reviewed biological-unit lineage.
- **Output:** `OffTargetControlProfile`; method mode adds an
  `OffTargetMethodBundle` with intervals, sensitivity, spike-in/design and OOD
  coordination records.
- **Boundary:** “control” means composition accounting. It is not physical
  removal, a safety conclusion, a release decision or a domain score.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-05)
- [Tool Card — authoritative runtime contract](../cards/P0-05.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/off_target_control_task_card.md)
- [Request example](../../../../examples/requests/p0_05_off_target_control.json)
- [Validation record](../../../../docs/validation/p0_05_real_method_runtime_v0.3.md)

Use `bridge-tool describe P0-05` for the installed version, schemas, environment
and registered method IDs.
