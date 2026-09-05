# P0-09 Evidence Compiler & Reconciler

This directory contains the immutable evidence-graph compiler and bounded query
package.

## Interface at a glance

- **Input:** compilation bundle; either legacy P0-08 profiles or canonical P0-08
  `EvidenceSufficiencyRunResultV2` objects; EvidenceFamily, Claim and
  Reconciliation registries; plus explicitly bound prior or comparison graphs.
  Canonical-run ingestion exposes distinct case/comparison initial/append modes:
  case modes bind exactly one run and comparison modes bind two to five. Legacy
  and canonical-run roles cannot be mixed. Each embedded v0.2 profile is routed
  by the run wrapper, ProductCase and domain; MeasurementSpec, MeasurementResult,
  Claim, source-record and family drift remains a record-level compiler check.
- **Output:** evidence, requirement and reconciliation sets; JSON/Parquet graph
  facts; rebuild manifests; three typed explanatory figures with complete tables;
  and seven bounded read-only queries.
- **Boundary:** it compiles existing facts, preserves history and explicit
  missingness, and never reruns biology, majority-votes tools or verifies claims.

## Upstream catalog compatibility

Catalog entries for MeasurementSpec, MeasurementResult and ToolRun accept the
published v0.1 and v0.2 Schema references. Node types and exact object ID/version
bindings remain required; other Schema versions are rejected for the affected
record. A catalog entry contains a content hash and reference, not the complete
upstream object. The caller remains responsible for validating that object's
content against its declared Schema before materializing the compilation bundle.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-09)
- [Tool Card — authoritative runtime contract](../cards/P0-09.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/evidence_compiler_task_card.md)
- [Request example](../../../../examples/requests/p0_09_evidence_compiler.json)
- [Validation record](../../../../docs/validation/p0_09_sufficiency_v2_ingestion_v0.4.md)

Use `bridge-tool describe P0-09` for the installed version, schemas, environment
and registered method IDs.

Versioned logical references such as `data-view:run-example:all-observations@0.1.0`
are preserved in provenance. The suffix must satisfy the existing object-version
grammar; path and credential guards still apply.
