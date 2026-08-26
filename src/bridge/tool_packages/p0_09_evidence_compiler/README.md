# P0-09 Evidence Compiler & Reconciler

This directory contains the immutable evidence-graph compiler and bounded query
package.

## Interface at a glance

- **Input:** compilation bundle, P0-08 profiles, EvidenceFamily, Claim and
  Reconciliation registries, plus explicitly bound prior or comparison graphs.
- **Output:** evidence, requirement and reconciliation sets; JSON/Parquet graph
  facts; rebuild manifests; and seven bounded read-only queries.
- **Boundary:** it compiles existing facts, preserves history and explicit
  missingness, and never reruns biology, majority-votes tools or verifies claims.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-09)
- [Tool Card — authoritative runtime contract](../cards/P0-09.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/evidence_compiler_task_card.md)
- [Request example](../../../../examples/requests/p0_09_evidence_compiler.json)
- [Validation record](../../../../docs/validation/p0_09_evidence_compiler_20260813.md)

Use `bridge-tool describe P0-09` for the installed version, schemas, environment
and registered method IDs.
