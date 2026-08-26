# P0-03 Target Identity & Regional Fidelity

This directory contains the target and regional evidence package.

## Interface at a glance

- **Aggregation mode:** eleven checksummed JSON objects → three
  denominator-explicit ratios.
- **Expression mode:** the same objects plus one H5AD and one
  `TargetRegionalMethodSpec` → pseudobulk reference support, NNLS weights,
  decoupler program activity, bootstrap state and reference/modality robustness.
- **Configuration:** target/regional references, program cards, gene-coverage
  minima and biological roles are versioned inputs.
- **Boundary:** transcriptomic regional support is not spatial localization;
  `domain_score` remains null.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-03)
- [Tool Card — authoritative runtime contract](../cards/P0-03.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/target_regional_identity_task_card.md)
- [Aggregation request](../../../../examples/requests/p0_03_target_regional_evidence.json)
- [Expression request](../../../../examples/requests/p0_03_target_regional_expression.json)
- [Method spec example](../../../../examples/objects/p0_03_target_regional_method_spec.json)
- [Aggregation validation](../../../../docs/validation/p0_03_target_regional_20260825.md)
- [Expression-method validation](../../../../docs/validation/p0_03_expression_methods_20260826.md)

Use `bridge-tool describe P0-03` for the installed version, schemas, environment
and registered method IDs.
