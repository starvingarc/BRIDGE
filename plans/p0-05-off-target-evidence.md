# P0-05 Configurable Off-target Evidence

## Goal

Make P0-05 callable through `ToolRequestV2` without embedding product roles,
off-target identities, OOD decisions, rare-state limits or biological
thresholds in code.

## Interface

The request carries one checksummed ProductCase, ProductDefinitionCard,
OffTargetRoleSpec, CellStateEvidenceProfile and QCReadinessProfile. The role
spec binds product/vocabulary context, the required full-product denominator,
selected composition channels and each observed state's reporting role.

The first executable version performs deterministic role-aware composition
only. OOD calibration and rare-state detection remain explicit
`not_assessed`; no placeholder score, limit of detection or safety threshold is
invented.

## Deliverables

- module-local models, executor and adapter;
- public and packaged role-spec/result Schemas;
- synthetic request, detailed Tool Card and validation record;
- focused source and installed-wheel tests;
- one P0-05-only stacked Draft PR based on the reviewed P0-04 branch.

## Verification and boundary

All project execution occurs in GitHub Actions. P0-05 remains `candidate`,
emits no MeasurementResult or visualization, keeps `domain_score=null`, and
cannot establish clinical harm, safety, potency, release or product ranking.

## Current closure state

- implementation, public Schemas, Tool Card, example and validation record are
  complete; bounded closure implementation is `92bd427`;
- P0-05 now consumes the shared configurable contracts directly and rejects
  non-public configured or upstream denominator text before publication;
- `/data1` source and clean-wheel validation passed 1,053 tests, with 94
  focused P0-03/P0-04/P0-05 tests, 12-tool discovery, knowledge and policy;
- Draft PR #22 remains stacked on P0-04 and awaits the required GitHub check;
- biological role, OOD and rare-state calibration review remain separate from
  this callable candidate path.
