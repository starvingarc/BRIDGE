# P0-02 Cell-State Evidence

This directory contains the executable cell-state evidence and reference-support
package. Its output remains shadow without a signed release manifest.

## Interface at a glance

- **Input:** QC-qualified expression views, modality, annotation vocabulary,
  reference candidates and provenance; an optional typed P0-01 handoff.
- **Output:** source-aware reference and marker/program evidence plus an optional
  V3 profile with explicit denominators, uncertainty and lineage bindings.
- **Boundary:** it does not release an assigned state or domain score. Pseudobulk
  correlation is reference similarity, not replicate-aware DE inference.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-02)
- [Tool Card — authoritative runtime contract](../cards/P0-02.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/cell_state_annotation_task_card.md)
- [Request example](../../../../examples/requests/p0_02_cell_state.json)
- [Pilot validation record](../../../../docs/validation/p0_02_scientific_freeze_pilot_20260811.md)
- [External-source preparation](../../../../docs/bridge_spec_v0.1/external_source_preparation.md)

Use `bridge-tool describe P0-02` for the installed version, environment and
registered method IDs.
