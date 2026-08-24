# P0-04 configurable developmental candidate validation — 2026-08-24

## Question

Can P0-04 produce a deterministic static developmental-window profile while
keeping the window and state assignments in a versioned, checksummed object?

This is an engineering validation. Synthetic assignments do not validate a
real developmental window, fetal reference, time course or product.

## Candidate interface

The candidate accepts ProductCase, ProductDefinitionCard,
DevelopmentWindowSpec, CellStateEvidenceProfile and QCReadinessProfile through
`ToolRequestV2`. It publishes one DevelopmentalCompatibilityResult and no
MeasurementResult or visualization. `domain_score` is always null.

## Controls

- exact role, Schema, version, checksum, assay and cross-object binding;
- ProductDefinition and annotation-vocabulary binding;
- P0-02 reconciliation-state compatibility without denominator contamination;
- whole-product and target-related denominators with their source view;
- configurable state roles, missing sources and unresolved residuals;
- strict numeric, deterministic reuse, input mutation and output-path tests;
- V1 typed refusal and public Schema/Pydantic state parity;
- source and installed-wheel execution.

## Evidence status

No local project code was run. GitHub Actions run
[`32683980747`](https://github.com/starvingarc/BRIDGE/actions/runs/32683980747)
validated implementation head `7028955` through the PR merge ref on Ubuntu and
Python 3.12. The installed package resolved from `site-packages`, outside the
source checkout.

| Gate | Current result |
|---|---|
| Installed-wheel focused suite | 53 P0-03/P0-04 tests passed |
| Complete pytest | 1,012 passed; 3 existing dependency warnings |
| 12-tool discovery | passed; exactly 12 |
| Knowledge validation | passed; no dangling method/source refs; 0 formal-eligible methods |
| Repository policy | passed |
| Schema/Card projection parity and diff check | passed |

The PR remains Draft. These results demonstrate packaging and deterministic
mechanics, not approval of any biological assignment or scientific release.

## Scientific boundary

P0-04 remains `candidate`. Static output remains shadow and cannot approve the
input window, convert D to GW/PCW, infer a trajectory, or support efficacy,
safety, potency, release or ranking claims.
