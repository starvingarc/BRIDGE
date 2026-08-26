# P0-05 Off-target Control

This directory contains the deterministic whole-product role-accounting package.

## Interface at a glance

- **Input:** six checksummed JSON objects binding ProductCase, product definition,
  StateRoleMap, OffTargetAssessmentSpec, P0-02 profile and evidence bundle.
- **Output:** `OffTargetControlProfile` with role composition, unknown reasons,
  coverage and rare-state detectability states.
- **Boundary:** “control” means composition accounting. It is not physical
  removal, a safety conclusion, a release decision or a domain score.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-05)
- [Tool Card — authoritative runtime contract](../cards/P0-05.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/off_target_control_task_card.md)
- [Request example](../../../../examples/requests/p0_05_off_target_control.json)
- [Validation record](../../../../docs/validation/p0_05_off_target_control_20260825.md)

Use `bridge-tool describe P0-05` for the installed version, schemas, environment
and registered method IDs.
