# P0-03 configurable target/regional candidate validation — 2026-08-24

## Question

Can P0-03 deterministically turn a P0-02 composition into target-identity and
regional-fidelity evidence while keeping every biological state assignment in
a versioned, checksummed input object rather than implementation code?

This is an engineering contract test. Synthetic role assignments do not
validate a real product definition, regional interpretation, efficacy, safety,
potency, GMP release or product ranking.

## Candidate interface

The candidate accepts six `ToolRequestV2` object roles: ProductCase,
ProductDefinitionCard, StateRoleMap, TargetRegionalAssessmentSpec,
CellStateEvidenceProfile and QCReadinessProfile. It publishes one
`TargetRegionalEvidenceResult` JSON artifact and no MeasurementResult or
visualization. `domain_score` is always null.

The implementation must contain no product-specific state name. Tests change
one synthetic StateRoleMap assignment without editing code and require a new
deterministic result and run identity.

## Planned controls

- exact role, Schema, version, checksum, assay and cross-object binding;
- ProductDefinition/assessment and annotation-vocabulary/role-map binding;
- compatibility with P0-02 reconciliation-state rows without counting them as a biological axis;
- strict count, denominator and fraction semantics;
- complete, partial and not-assessed outputs;
- unmapped states and residual composition remain unresolved;
- zero target-related denominator remains unavailable rather than zero-valued;
- caller input-ID renaming does not change scientific identity;
- repeated output reuse and changed-output refusal;
- input mutation, unsafe evidence reference and output-path refusal;
- V1 typed refusal and public Schema/Pydantic parity;
- source and installed-wheel CLI/SDK invocation.

## Evidence status

No local project code was run while preparing this candidate, per user
instruction. Exact source, GitHub CI and clean-wheel counts remain pending and
must be filled from the final commit before the Draft PR can be made Ready.

| Gate | Current result |
|---|---|
| Focused P0-03 suite | pending GitHub CI |
| Complete pytest | pending GitHub CI |
| 12-tool discovery | pending GitHub CI |
| Knowledge validation | pending GitHub CI |
| Repository policy | pending GitHub CI |
| Public/packaged Schema parity | pending GitHub CI |
| Tool Card parity and regeneration | pending GitHub CI |
| Clean-wheel invocation | pending GitHub CI |

## Scientific boundary

P0-03 remains `candidate`. Draft, reviewed or frozen configuration inputs can
exercise the code, but code execution cannot approve those inputs. Upstream
P0-02 shadow evidence remains shadow; missing spatial evidence is explicitly
`not_assessed`; no score or release conclusion is created.
