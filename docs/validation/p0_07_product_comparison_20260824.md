# P0-07 configurable product-comparison candidate validation — 2026-08-24

## Question

Can P0-07 publish a deterministic pairwise descriptive comparison without
encoding biological metric choices or decision thresholds in code?

This is engineering validation. Synthetic ProductCases, contracts and metric
values do not validate a real comparison, assay, direction or conclusion.

## Candidate interface

The candidate accepts a ComparisonSpec and ComparisonEvidenceBundle through
`ToolRequestV2`. It publishes one ComparisonRecord and no MeasurementResult or
visualization. `overall_score` and `overall_rank` are always null; Pareto is
always `not_assessed` in this slice.

## Controls

- exact role, Schema, version, checksum and two-ProductCase binding;
- input-configured contract dimensions, mismatch policy and metric directions;
- preparation-level mean/range and raw candidate-minus-baseline delta;
- missing/unavailable, unit and evidence-state semantics without zero imputation;
- strict numeric, deterministic reuse, input mutation and output-path tests;
- V1 typed refusal and public Schema/Pydantic parity;
- source and installed-wheel execution.

## Evidence status

No local project code was run. Exact GitHub Actions run, installed-wheel focused
count and complete-suite count will be recorded after the generated projections
and final branch head pass `repository-gates`.

## Scientific boundary

P0-07 remains `candidate`. This slice is descriptive only and does not validate
comparability, independence, metric direction, inferential design, Pareto
dominance or product superiority for real data.
