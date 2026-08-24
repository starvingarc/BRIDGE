# P0-06 configurable program-evidence candidate validation — 2026-08-24

## Question

Can P0-06 deterministically assemble stage-bound program observations and
configured shadow review signals without encoding biological programs or
decision thresholds in the implementation?

This is engineering validation. Synthetic programs, intervals and observations
do not validate a real ProgramSpec, scorer, reference, threshold or product
conclusion.

## Candidate interface

The candidate accepts ProductCase, ProductDefinitionCard,
ProgramAssessmentSpec, ProgramEvidenceBundle, DevelopmentalCompatibilityResult
and QCReadinessProfile through `ToolRequestV2`. It publishes one
ProliferationStressResponseProfile and no MeasurementResult or visualization.
`domain_score` is always null.

## Controls

- exact role, Schema, version, checksum, assay and cross-object binding;
- ProductDefinition, P0-04 developmental-window and Cell-State-profile binding;
- caller-supplied reference interval, coverage, evidence-state and direction;
- Evidence Family and independence-group de-duplication;
- missing/unavailable, low-coverage and unmatched-observation semantics;
- strict numeric, deterministic reuse, input mutation and output-path tests;
- V1 typed refusal and public Schema/Pydantic parity;
- source and installed-wheel execution.

## Evidence status

No local project code is run. GitHub Actions evidence will be recorded here
after the exact implementation head and generated projections pass. Until then,
the interface remains a Draft candidate under review.

## Scientific boundary

P0-06 remains `candidate`. All assessed review flags remain `shadow`.
Protocol attribution, residual-pluripotency LOD and transcriptomic CNV remain
`not_assessed`. The module establishes neither biological truth nor safety,
potency, release or ranking.
