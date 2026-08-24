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

No local project code is run. GitHub CI and installed-wheel counts remain
pending until the final Draft head is available.

| Gate | Current result |
|---|---|
| Installed-wheel focused suite | pending GitHub CI |
| Complete pytest | pending GitHub CI |
| 12-tool discovery | pending GitHub CI |
| Knowledge validation | pending GitHub CI |
| Repository policy | pending GitHub CI |
| Schema/Card projection parity | pending GitHub CI |

## Scientific boundary

P0-04 remains `candidate`. Static output remains shadow and cannot approve the
input window, convert D to GW/PCW, infer a trajectory, or support efficacy,
safety, potency, release or ranking claims.
