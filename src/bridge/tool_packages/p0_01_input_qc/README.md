# P0-01 Input Audit & QC

This directory contains the executable input-audit and QC package.

## Interface at a glance

- **Input:** a declared H5AD, 10x H5 or 10x MTX expression asset plus assay,
  matrix semantics, sample/capture metadata and MeasurementSpec.
- **Output:** QC readiness profiles, raw measurements, immutable data-view and
  biological-unit lineage artifacts, visualizations and a checksummed manifest.
- **Boundary:** QC readiness is not a product-quality, safety or release score.

## Explicit selected-view handoff

P0-01 0.1.5 preserves the audit-only default. To apply reviewed candidate technical
QC, set `select_qc_eligible_cells=true`, `run_scrublet=true` and an explicit
MeasurementSpec. `QC-scRNA-robust-candidate-v0.1` uses five unscaled MADs below
capture-specific log1p counts/genes and three above mitochondrial fraction.
Zero-count observations are excluded; unavailable doublet calls or degenerate
required distributions prevent a completed selection.

The unchanged parent and annotated all-observation view remain distinct from
`qc_selected_h5ad`. The selected view preserves raw counts and all features,
adds `passes_QC` and explicit exclusion flags, and carries the parent checksum,
selection specification and ordered observation checksum. Scrublet score/class,
version, threshold and simulated-score distribution are retained per capture.
Threshold JSON and per-capture PNG/SVG before/after plots support review.
P0-02 0.5.5 and the Web downstream binder consume the exact selected artifact.

Selection is explicit SDK/CLI behavior; the Web audit preparation default and
UI are unchanged. Missing raw droplets leave cell calling and ambient RNA
not assessed. Biological identity, cell-cycle and stress expression are not QC
exclusion criteria. Candidate selection is not scientific validation or release.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-01)
- [Tool Card — authoritative runtime contract](../cards/P0-01.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/input_audit_qc_task_card.md)
- [Count-ready request example](../../../../examples/requests/p0_01_count_ready.json)
- [Analysis-ready request example](../../../../examples/requests/p0_01_analysis_ready.json)
- [Validation record](../../../../docs/validation/p0_01_server_integration_20260810.md)

Use `bridge-tool describe P0-01` for the installed version, environment and
registered method IDs.
