# P0-06 proliferation and stress-response candidate validation — 2026-08-25

## Biological question and scope

This validation asks whether precomputed whole-product and state-specific
program evidence can be bound to one ProductCase and represented with explicit
stage, gene-coverage, LOD and process-attribution limits. It does not test a
biological program scorer or analyze expression data.

## Synthetic inputs and controls

Tests use seven synthetic JSON objects: ProductCase, ProductDefinitionCard,
DevelopmentWindowSpec, ProgramSpec, CellStateEvidenceProfileV2, ProtocolIR and
ProgramEvidenceBundle. No real cell, sample, protocol, gene list or private
metadata is used.

DevelopmentWindowSpec is uniquely owned by P0-04 and consumed unchanged by P0-06.

The ProgramSpec owns synthetic program IDs, gene-set references and checksums,
allowed stages/states/scopes/metrics, coverage threshold, allowed and resolvable
LOD states, review mappings and attribution-count requirements. One control
replaces the complete vocabulary to verify that Python does not contain a
biology-specific list.

Controls cover whole-product and state-specific records, triggered and
untriggered review outcomes, missing process metadata, batch confounding,
insufficient replication, low coverage, unresolved LOD, unconfirmed/out-of-
window stages, partial envelopes, lineage checksum drift, cross-object drift,
cell-state MeasurementSpec drift, undeclared program/metric/state/LOD/process
values, input mutation and existing-output drift.

## Observed behavior

The valid synthetic bundle produces a deterministic descriptive shadow profile
with aligned program summaries and review flags. Low coverage becomes
`unavailable`; an unresolved LOD becomes `cannot_resolve`; stage mismatch
becomes not applicable. Missing metadata, batch confounding or insufficient
replication becomes `cannot_attribute`, and process-step associations are not
published in that state.

The externally mapped `not_detected_above_lod` outcome retains
`not_evidence_of_safety`. Every result remains `domain_score=null` and no
measurement or visualization is produced.

Malformed contracts, checksum or reference drift, and records outside the
external ProgramSpec fail before publication. Repeated identical inputs reuse
byte-identical artifacts.

## Engineering evidence

- Focused P0-06 and registry suite: 34 passed.
- Exactly 12 high-level Tool Packages remain discoverable.
- Five module-local public P0-06 Schemas are generated, packaged and byte-identical across
  two consecutive generator runs.
- Knowledge validation passed with 354 methods, 396 bindings, no dangling
  method or source references and zero formally eligible methods.
- Repository policy checks passed.
- The committed request example is documentation-only; focused tests construct
  real temporary files and calculate exact checksums.

## Boundary

This is engineering validation of a candidate handoff and aggregation contract.
It does not validate proliferation, stress, pluripotency, process causality,
tumorigenicity, safety, potency, efficacy or release. All review flags remain
shadow and require independent biological and orthogonal validation.
