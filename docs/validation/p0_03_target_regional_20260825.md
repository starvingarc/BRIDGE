# P0-03 target/regional candidate validation — 2026-08-25

## Question and boundary

This record tests whether P0-03 can bind one P0-02 V3 composition to its
ProductCase, measurement, vocabulary, reference, QC and biological-unit lineage,
then publish three deterministic candidate ratios. It does not validate any
real state role, reference suitability, target/regional conclusion, efficacy,
safety, potency or release decision.

## Synthetic contract

Tests construct eleven immutable synthetic JSON objects: ProductCase,
ProductDefinitionCard, StateRoleMap, TargetRegionalAssessmentSpec,
MeasurementSpecV2, CellStateEvidenceProfileV3, QCReadinessProfileV2,
BiologicalUnitManifest, BiologicalUnitAssignmentArtifact,
AnnotationVocabulary and ReferenceManifest. Every file has a real SHA-256; no
private data, server path, laboratory identifier, gene list or product state is
used.

P0-03 consumes the single StateRoleMap contract owned with P0-05 rather than
publishing another model under the same Schema URI. That map owns product roles;
the assessment spec binds its exact checksum and owns requested channels,
target-role membership and regional state-ID numerator/denominator sets.
Changing those objects changes the result without changing Python.

## Observed behavior

A complete synthetic channel publishes one TargetRegionalEvidenceResult and
three independent checksummed MeasurementResultV2 files:

- target identity / selected DataView;
- configured regional support / target-related denominator;
- configured regional support / selected DataView.

The fixture produces `0.6`, `0.75` and `0.6`, respectively, with the original
integer numerators and denominators. Repeated inputs reuse the same run ID and
artifact bytes.

MeasurementSpec, vocabulary, reference and QC checksum drift fails eligibility.
StateRoleMap checksum, ProductDefinition, DataView, assignment hierarchy, QC
module eligibility, vocabulary labels and reference-source drift fail closed. Upstream
`unknown` or `ood` produces `not_assessed`; all three metric values, numerators
and denominators are null. A zero target-related denominator produces an
`unavailable` regional metric rather than numeric zero. A changed existing
metric artifact prevents bundle reuse.

## Engineering evidence

- Focused P0-03 and registry suite after final main sync: 29 passed.
- Exactly 12 high-level Tool Packages remain discoverable.
- Two module-owned P0-03 Schemas, the shared P0-05 StateRoleMap Schema and the
  detailed Tool Card were byte-identical across two consecutive generator
  runs.
- Knowledge validation passed with 354 methods, 396 bindings, no dangling
  method/source references and zero formally eligible methods.
- Repository policy and staged diff checks passed.

## Interpretation boundary

P0-03 remains `candidate`. Numeric results remain `shadow` and
`domain_score=null`; `complete` means only that the supplied contracts were
bound and the configured arithmetic was available. This engineering evidence
does not freeze biology or authorize a scientific or public claim.
