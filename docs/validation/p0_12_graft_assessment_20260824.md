# P0-12 configurable graft assessment candidate validation — 2026-08-24

## Question

Can P0-12 expose a stable callable interface for optional post-transplant
evidence while keeping biological channels, units, eligibility rules,
independent-unit requirements and interpretation intervals outside code?

This is engineering validation over synthetic objects. It does not validate a
real graft rule, reference, measurement, biological conclusion or release.

## Candidate interface

The tool accepts one GraftAssessmentSpec and one GraftEvidenceBundle through
`ToolRequestV2`. It emits one GraftAssessment JSON result and no measurement,
visualization, expression-derived object or pre-transplant update.

## Controls

- exact role, Schema, version, checksum and ProductCase/context binding;
- strict finite values and distinct missing/unknown/unavailable semantics;
- input-configured channel, unit, evidence-state, minimum-unit and interval rules;
- explicit-only preparation linkage and independent-unit identifiers;
- deterministic reuse, input immutability, output collision and V1 refusal;
- `graft_score=null`, `domain_score=null` and `product_backfill=not_performed`;
- source and installed-wheel execution in GitHub Actions only.

## Evidence status

No local project code was run. Exact GitHub Actions evidence will be recorded
after the generated projections, source suite and clean installed-wheel suite
complete on the final Draft-PR head.

## Scientific boundary

P0-12 remains `candidate`. Its first executable slice summarizes precomputed
inputs; it does not perform matrix QC, state annotation, species separation,
reference mapping, causal preparation attribution, efficacy/safety assessment,
scoring or release. Real rule objects require independent biological review.
