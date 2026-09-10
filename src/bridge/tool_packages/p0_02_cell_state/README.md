# P0-02 Cell-State Evidence

This directory contains the executable cell-state evidence and reference-support
package. Its output remains shadow without a signed release manifest.

## Interface at a glance

- **Input:** QC-qualified expression views, modality, annotation vocabulary,
  reference candidates and provenance; an optional typed P0-01 handoff. Raw-count
  columns that resolve to the same non-missing gene symbol are summed before
  normalization; duplicate symbols in normalized inputs remain invalid.
- **Output:** source-aware reference and marker/program evidence plus an optional
  V3 profile with explicit denominators, uncertainty and lineage bindings.
- **Boundary:** it does not release an assigned state or domain score. Pseudobulk
  correlation is reference similarity, not replicate-aware DE inference.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-02)
- [Tool Card — authoritative runtime contract](../cards/P0-02.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/cell_state_annotation_task_card.md)
- [Request example](../../../../examples/requests/p0_02_cell_state.json)
- [Pilot validation record](../../../../docs/validation/p0_02_cell_state_evidence.md#record-p0-02-scientific-freeze-pilot-20260811)
- [External-source preparation](../../../../docs/bridge_spec_v0.1/external_source_preparation.md)

Use `bridge-tool describe P0-02` for the installed version, environment and
registered method IDs.

## Descriptive L1/L2 marker evidence

Version 0.5.4 evaluates L1 and L2 cards whose allowed uses include
`shadow_evidence`; L3 remains excluded. A custom candidate card resource can be
supplied by the existing reference catalog's `marker_program_path` and is
checksummed into a new snapshot. Packaged L1 cards are unchanged; this version
does not add reviewed L2 biological definitions.

Positive and negative means describe expression over the genes actually present.
Insufficient positive-gene coverage leaves a card unavailable; absent negative
genes yield missing values, not zero expression. Means are not coexpression,
probabilities, state assignments, purity or product scores. Candidate review
status, correlation-derived labels and release gates are unchanged.

## Deterministic grouping artifacts

Exploratory grouping records preserve stable method parameters, grouping
membership, stability diagnostics and the configured thread count. Wall-clock
duration and process peak memory are excluded from the scientific JSON so
repeating the same request can reuse the checksummed bundle. Removing those
volatile diagnostics does not change normalization, clustering, ARI or state
evidence.

See the [deterministic replay validation record](../../../../docs/validation/p0_02_cell_state_evidence.md#record-p0-02-deterministic-grouping-20260905)
for the regression, installed-wheel checks and repeated-request evidence.
