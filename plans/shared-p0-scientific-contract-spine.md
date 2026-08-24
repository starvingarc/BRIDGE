# Shared P0 Scientific Contract Spine

## Motivation

Independent P0 modules must exchange the same selected observations, product instance, measurement contract and experimental-unit lineage without copying domain rules or trusting caller labels. The historical stacked Draft encoded these seams only after several modules had accumulated, so it cannot be merged as an independently reviewable foundation.

## Scope

- Add content-addressed `DataViewBinding` fields to QC and cell-state profiles.
- Add version/context fields to `MeasurementSpec` and a backward-compatible `MeasurementResultV2` used by `ToolRunV2`.
- Add versioned BiologicalUnit assignment/manifest, ProductCase and ProductDefinitionCard contracts.
- Add exact lineage comparison helpers, safe configured-text validation and immutable snapshot/atomic single-JSON publication primitives.
- Register and generate matching public and packaged JSON Schemas.
- Document experimental-unit and scientific-authority boundaries.

## Non-goals

- No module becomes implemented in this change.
- No cell-state role, marker, threshold, developmental window, assay decision or statistical estimand is embedded in code.
- No caller label grants biological independence, scientific review or release authority.
- No score, efficacy, safety, potency or clinical claim is introduced.

## Frozen interfaces

- Existing v0.1 request, run and measurement payloads remain valid.
- New public schema references are:
  - `bridge://schemas/biological-unit-assignment/v0.1`
  - `bridge://schemas/biological-unit-manifest/v0.1`
  - `bridge://schemas/measurement-result/v0.2`
  - `bridge://schemas/product-case/v0.1`
  - `bridge://schemas/product-definition-card/v0.1`
- P0-01 can produce only `declared` BiologicalUnit lineage.
- Technical capture and graft units cannot satisfy independence assertions.

## Validation

- Focused model, schema-parity, lineage-authority and runtime-publication tests.
- Full source-tree test suite and repository gates.
- Wheel build, isolated install, full suite and 12-tool discovery from the installed package.
- Two schema-generation passes with no diff.
- Independent biology, single-cell/statistics and AI4S exact-head review.

## Remaining boundary

The contracts make provenance auditable but do not establish the correct biological unit for a future experiment. Real-data and human review must still supply a versioned manifest and appropriate estimand. This branch remains a contract-only candidate until exact-head review and CI complete.
