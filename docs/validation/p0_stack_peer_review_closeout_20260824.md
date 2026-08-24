# P0 stack peer-review closeout validation — 2026-08-24

## Question

Can all twelve P0 packages be called through explicit, checksummed contracts
without hard-coding mutable biology, inflating technical observations into
biological replication, allowing callers to restate quantitative evidence, or
granting release authority that the package does not possess?

This record covers engineering closure only. It does not freeze P0-02 states,
StateRoleMap, DevelopmentWindowSpec, biological-unit assignments, program or
graft rules, thresholds, ScoreContract, disclosure policy or a biological
conclusion.

## Prior snapshot is superseded

The earlier closeout snapshot at
`b6607aee6ea6930fe5b1baf5c4fc7020d92460d3` passed its then-current 1,198-test
source/wheel gates. Subsequent biology, scRNA and AI4S review found unresolved
cross-module ownership and replication issues. Those results remain historical
engineering evidence but are not the final acceptance evidence for this
revised branch.

## Revised closure behavior

- **P0-01/P0-02:** P0-01 writes a physical selected view,
  `biological_unit_assignments.parquet` and a checksummed
  `BiologicalUnitManifest`; P0-02 consumes and carries the exact artifacts.
  P0-01 may only declare lineage and neither package certifies independent
  biological repeats.
- **P0-03/P0-04/P0-05:** each requires the exact ProductCase-owned manifest in
  addition to shared configurable biological objects. Ref, checksum,
  independence scope and unit/group membership drift are refused.
- **P0-06:** observations are aggregated inside manifest independence groups.
  Only an externally reviewed/frozen manifest with a checksummed review gate can
  contribute independent groups; declared lineage yields `cannot_resolve`.
- **P0-07:** consumes two full P0-08 run results and two exact manifests.
  Repeated preparations aggregate inside reviewed groups and any group shared
  across arms is refused.
- **P0-08/P0-09:** frozen MeasurementResult v0.1 remains for ToolRun v0.1;
  quantitative handoff uses MeasurementResult v0.2 with unit,
  MeasurementSpec-version, denominator/interval and producer-run fields. P0-08
  publishes exact Schema/source-checksum bindings. P0-09 requires those same
  bytes, and `EvidenceCandidate` cannot restate the measurement.
- **P0-10/P0-11:** P0-10 correspondence remains export-ineligible. P0-11 is an
  Internal Review Projection requiring the exact P0-10 ToolRun/result/artifact
  binding. Every successful projection declares producer authentication
  unavailable, release authority not configured, internal-review-only
  distribution and human review required.
- **P0-12:** product and graft MeasurementSpecs are separate. A provided graft
  requires exact external lineage review; declared lineage is not assessed.
  Observations are grouped by disjoint graft/timepoint strata, aggregated within
  animal according to configured denominator semantics, and never aggregated
  across strata.

The stack handoff test now calls P0-08, passes its full result plus the same
checksummed MeasurementResult into P0-09, uses the resulting graph in P0-10 and
passes the exact P0-10 run/result into P0-11. No manual numeric or provenance
translation layer exists between these tools, and the chain stops at the
release-authority boundary.

## Exact-head acceptance record

The final branch SHA, source archive, clean-wheel SHA, import-isolation proof,
focused/full test counts, 12-tool discovery, generator idempotence, public/
packaged Schema and Tool Card parity, knowledge validation, repository policy,
privacy/path/LFS scans and cleanup manifest are retained under the exact SHA in
a private `/data1` exact-head evidence root. The Draft PR records the same
exact SHA and evidence-manifest checksum after the final run. No project code
is run on the local workstation.

## Release boundary

All packages remain `candidate`; P0-02 remains
`biological_review_in_progress`; `domain_score` remains null; the knowledge
catalog retains zero formal-eligible methods. Passing engineering gates does
not make a method scientifically formal, approve any lineage/threshold/rule,
authenticate an operator, authorize public distribution, make the Draft Ready,
or authorize merging.
