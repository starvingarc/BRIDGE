# P0-05 Off-target Control

This directory contains declared-denominator product-role accounting and transparent
off-target method execution.

## Interface at a glance

- **Input:** six checksummed JSON objects for compatible aggregation, or nine for
  method execution with P0-02 V3 and reviewed biological-unit lineage. Either mode
  may add one authorized checksummed `MeasurementSpecV2` structured object.
- **Output:** `OffTargetControlProfile`; method mode adds an
  `OffTargetMethodBundle` with intervals, sensitivity, spike-in/design and OOD
  coordination records. Both modes add typed visualization data, exact tables
  and static vector/raster figures for product-role accounting, rare-state
  detectability and supplied OOD channel states. P0-05 v0.5 always returns profile
  v0.2. Without a MeasurementSpec its projection state is `not_requested`, its
  spec binding is null and no normalized measurements are fabricated. With an
  authorized MeasurementSpec the projection state is `available` and the profile
  binds checksummed `MeasurementResultV2` artifacts for every role, the
  identity-unknown profile and every configured rare state. Profile v0.1 remains
  packaged only for legacy loading.
- **Boundary:** “control” means composition accounting. It is not physical
  removal, a safety conclusion, a release decision or a domain score.

Projection keeps the original domain records in profile v0.2. Missing,
unavailable and measurement-unknown values remain null where required by the
shared contract; zero observations are not interpreted as absence.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-05)
- [Tool Card — authoritative runtime contract](../cards/P0-05.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/off_target_control_task_card.md)
- [Request example](../../../../examples/requests/p0_05_off_target_control.json)
- [Validation record](../../../../docs/validation/p0_05_real_method_runtime_v0.3.md)

Use `bridge-tool describe P0-05` for the installed version, schemas, environment
and registered method IDs.
