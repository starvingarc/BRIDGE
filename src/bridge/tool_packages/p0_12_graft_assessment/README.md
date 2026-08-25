# P0-12 Optional Graft Assessment

This directory contains the independent, optional graft-evidence package.

## Interface at a glance

- **Input:** either no structured inputs, or exactly one checksummed GraftCase,
  GraftAssessmentSpec and precomputed GraftEvidenceBundle.
- **Output:** `GraftAssessmentResult` with `not_provided` or descriptive graft
  evidence, immutable artifacts and explicit linkage/confounding states.
- **Boundary:** graft evidence never backfills a pre-transplant score, threshold,
  method selection, training label, safety or efficacy conclusion.

## Documentation

- [Tool Card — authoritative runtime contract](../cards/P0-12.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/graft_assessment_task_card.md)
- [Request example](../../../../examples/requests/p0_12_graft_assessment.json)
- [Validation record](../../../../docs/validation/p0_12_graft_assessment_20260825.md)

Use `bridge-tool describe P0-12` for the installed version, schemas, environment
and registered method IDs.
