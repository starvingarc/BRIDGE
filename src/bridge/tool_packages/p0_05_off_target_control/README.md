# P0-05 Off-target Control

This directory contains declared-denominator product-role accounting and transparent
off-target method execution.

## Interface at a glance

- **Input:** six checksummed JSON objects for compatible aggregation, or ten for
  method execution with P0-02 V3, immutable declared biological-unit lineage and
  a separate checksummed attestation receipt. Either mode
  may add one authorized checksummed `MeasurementSpecV2`; projected runs also require the biological-unit manifest.
- **Output:** `OffTargetControlProfile`; method mode adds an
  `OffTargetMethodBundle` with intervals, sensitivity, spike-in/design and OOD
  coordination records. Both modes add typed visualization data, exact tables
  and static vector/raster figures for product-role accounting, rare-state
  detectability and supplied OOD channel states. P0-05 v0.5.2 always returns profile
  v0.2. Without a MeasurementSpec its projection state is `not_requested`, its
  spec binding is null and no normalized measurements are fabricated. With an
  authorized MeasurementSpec the projection state is `available` and the profile
  binds checksummed `MeasurementResultV2` artifacts for every role, the
  identity-unknown profile and every configured rare state. Profile v0.1 remains
  packaged only for legacy loading.
- **Boundary:** “control” means composition accounting. It is not physical
  removal, a safety conclusion, a release decision or a domain score.

Method execution accepts only a P0-01 `declared` manifest plus a confirmed `analysis_execution` attestation receipt bound to the exact assignment, selected DataView, observation set and attestation trace. It records a caller/data-owner assertion. Runtime checks structure and bindings only; it does not authenticate the attestor or prove biological truth, independent review or release authority. Deployment maps the authenticated conversation record to the attestation reference/hash. Projection uses an independent P0-05 MeasurementSpec and verifies its assay, product applicability, analysis unit, independence group and cell/nucleus observation unit against the manifest. Projection keeps the original domain records in profile v0.2. Missing,
unavailable and measurement-unknown values remain null where required by the
shared contract; zero observations are not interpreted as absence.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-05)
- [Tool Card — authoritative runtime contract](../cards/P0-05.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/off_target_control_task_card.md)
- [Request example](../../../../examples/requests/p0_05_off_target_control.json)
- [Attestation-receipt validation](../../../../docs/validation/p0_05_biological_unit_attestation_receipt_20260905.md) · [Method-runtime validation](../../../../docs/validation/p0_05_real_method_runtime_v0.3.md)

Use `bridge-tool describe P0-05` for the installed version, schemas, environment
and registered method IDs.
