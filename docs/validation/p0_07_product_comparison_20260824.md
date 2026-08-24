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

No local project code was run. The bounded closure implementation at
`67076af82e7c384617c248fc30303ac69d5fba0a` was transferred as a Git archive
to `/data1` and exercised there from both the exact source tree and a clean
wheel installation. The installed package resolved from the temporary
environment's `site-packages`, outside the source checkout. The wheel SHA-256
was `670ae633af676280825a2f67438b93b5bdf8b4dd0b7100e22763eb998985e7eb`.

| Gate | Current result |
|---|---|
| Source focused chain | 153 P0-03/P0-04/P0-05/P0-06/P0-07 tests passed |
| Source complete pytest | 1,112 passed; 3 existing dependency warnings |
| Installed-wheel complete pytest | 1,112 passed; 2 dependency warnings |
| 12-tool discovery | passed; exactly 12 |
| Public and packaged Schemas | 69 registered Schemas; generated copies packaged with the wheel |
| Knowledge validation | passed; no dangling method/source refs; 0 formal-eligible methods |
| Repository policy and committed diff | passed |

The closure also moves generic object references to the shared configurable
contract and rejects machine-local or credential-like units in rules,
preparation evidence and result models. Comparison calculations and
interpretation boundaries are unchanged.

The PR remains Draft. These results establish packaging and deterministic
contract behavior, not approval of a ComparisonSpec or real-case conclusion.

## Scientific boundary

P0-07 remains `candidate`. This slice is descriptive only and does not validate
comparability, independence, metric direction, inferential design, Pareto
dominance or product superiority for real data.
