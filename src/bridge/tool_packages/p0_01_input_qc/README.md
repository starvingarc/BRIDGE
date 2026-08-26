# P0-01 Input Audit & QC

This directory contains the executable input-audit and QC package.

## Interface at a glance

- **Input:** a declared H5AD, 10x H5 or 10x MTX expression asset plus assay,
  matrix semantics, sample/capture metadata and MeasurementSpec.
- **Output:** QC readiness profiles, raw measurements, immutable data-view and
  biological-unit lineage artifacts, visualizations and a checksummed manifest.
- **Boundary:** QC readiness is not a product-quality, safety or release score.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-01)
- [Tool Card — authoritative runtime contract](../cards/P0-01.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/input_audit_qc_task_card.md)
- [Count-ready request example](../../../../examples/requests/p0_01_count_ready.json)
- [Analysis-ready request example](../../../../examples/requests/p0_01_analysis_ready.json)
- [Validation record](../../../../docs/validation/p0_01_server_integration_20260810.md)

Use `bridge-tool describe P0-01` for the installed version, environment and
registered method IDs.
