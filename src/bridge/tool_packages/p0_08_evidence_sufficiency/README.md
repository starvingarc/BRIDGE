# P0-08 Evidence Sufficiency

This directory contains the deterministic evidence-gating package.

## Interface at a glance

- **Input:** one candidate GateRuleSpec, one to five checksummed domain bundles,
  and their measurement, QC, validation, prior and sensitivity records. A
  checksummed ProductCase is required when a domain declares ProductCase or QC
  context; the source and domain MeasurementSpecs remain separate contracts.
- **Output:** canonical `EvidenceSufficiencyRunResultV2`, per-domain profiles,
  gate trace, case summary, typed visualization data and three table-backed figure
  families. Each v0.2 profile is also published as a stable, canonical single-object
  JSON artifact as a P0-09-ready producer handoff; the combined wrapper is a
  noncanonical convenience view. P0-09 acceptance remains a separate package change.
- **Boundary:** it folds existing evidence only. Missing scientific axes become
  `not_assessed`; no new measurement, score or product-quality decision is made.

ProductCase, selected QC data view, assay and biological-unit lineage are checked
as one case boundary. Missing or unknown QC authorization fails closed.

The figures keep input-data, method-validation, reference/prior and current
interpretation conditions separate. Measurement-state and evidence-family counts
are descriptive references, not independent evidence.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-08)
- [Tool Card — authoritative runtime contract](../cards/P0-08.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/evidence_sufficiency_task_card.md)
- [Request example](../../../../examples/requests/p0_08_evidence_sufficiency.json)

Use `bridge-tool describe P0-08` for the installed version, schemas, environment
and registered method IDs.
