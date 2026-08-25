# P0-11 Public-safe Export validation — 2026-08-25

## Scope

This record covers the first executable JSON-only candidate on branch
`p0-11-public-safe-export`, based on `c336a20`. It validates engineering
reproducibility and fail-closed export behavior; it does not validate scientific
truth or authorize publication.

## Frozen interface

- ToolRequestV2 with exactly four checksummed JSON inputs.
- Allowlist-rebuilt PublicSafeReport plus manifest and result JSON artifacts.
- `ready_for_confirmation` followed by an exact-hash `exported` rerun.
- No upload, media, visualization, MeasurementResult or domain score.

## Server evidence

The following checks ran against the final staged source tree under Python 3.12;
the exact branch-head SHA is reported at handoff.

| Check | Result |
|---|---|
| P0-11 focused plus registry | `25 passed in 3.82s` |
| Focused plus environment contracts | `35 passed in 4.75s` |
| Full pytest | `1062 passed, 8 warnings in 112.41s` |
| Tool discovery | Exactly 12 packages; P0-11 is implemented v0.2.0 |
| Knowledge validation | `valid=true`; 354 methods, 396 bindings, no dangling refs |
| Repository policy | Passed |
| Schema and Tool Card generators | Two-run content hashes unchanged |
| Diff check | Passed |

The focused matrix includes candidate creation, exact confirmation, wrong
confirmation, receipt/policy/alias/statement/checksum refusals, six leak canary
classes, V1 refusal, deterministic reuse, tamper refusal and output checksum
bindings.

## Boundary

A `passed` leak scan means only that the frozen deterministic canaries did not
match the rebuilt allowlisted payload. It is not a general privacy proof, a
scientific review, or public-release approval.
