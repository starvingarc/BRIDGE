# P0-06 Configurable Proliferation & Stress Response

## Goal

Make P0-06 callable through `ToolRequestV2` while keeping program definitions,
stage context, reference intervals, coverage requirements, evidence eligibility
and review directions in versioned, checksummed inputs.

## Interface

The request carries one ProductCase, ProductDefinitionCard,
ProgramAssessmentSpec, ProgramEvidenceBundle, DevelopmentalCompatibilityResult
and QCReadinessProfile. The first executable slice consumes precomputed program
observations; it does not open expression matrices or choose a scoring method.

The executor validates cross-object bindings, compares each numeric observation
with its configured reference interval, excludes insufficient coverage without
zero imputation, de-duplicates caller-supplied independence groups and produces
one aligned shadow review record per rule.

## Explicit non-goals

- no embedded program name, gene, stage, threshold or ProductDefinition;
- no raw expression scoring or method selection;
- no ProtocolIR process attribution;
- no residual-pluripotency detection limit;
- no transcriptomic-CNV claim;
- no score, clinical/safety/potency/release conclusion or cell-identity rewrite.

Deferred channels remain explicit `not_assessed`. A missing or unavailable
observation is never converted into zero or absence.

## Deliverables

- module-local models, executor and adapter;
- public and packaged assessment-spec, evidence-bundle and result Schemas;
- synthetic request, detailed Tool Card and validation record;
- focused source and installed-wheel tests;
- one P0-06-only stacked Draft PR based on the P0-05 branch.

## Verification and stop

All project execution occurs in GitHub Actions. The PR remains Draft after
engineering gates. Biological ProgramSpecs, reference envelopes, thresholds,
evidence-family independence, LOD and review directions require separate
scientific review and can change without a code modification.
