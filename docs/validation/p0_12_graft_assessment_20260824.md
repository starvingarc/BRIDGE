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

No local project code was run. GitHub Actions run
[`32691515962`](https://github.com/starvingarc/BRIDGE/actions/runs/32691515962)
validated executable head
`e0d83a7da55c7ab1d5b89986aecb3dfdc1263781`:

- the wheel was built and `bridge` was imported from the clean installed
  site-packages directory, not the source checkout;
- the cumulative installed-wheel configurable-interface suite passed
  `195` tests, including P0-12 execution, refusal, reuse and mutation cases;
- the full source suite passed `1,154` tests with three pre-existing dependency
  warnings;
- exactly 12 tools were discoverable and all 74 registered public Schemas were
  packaged;
- knowledge validation reported no dangling method or source references and
  `formal_eligible_method_count=0`;
- repository policy and committed-whitespace checks passed.

The following documentation-only evidence commit must retain the same green
gates before this Draft PR is treated as implementation-complete.

## Scientific boundary

P0-12 remains `candidate`. Its first executable slice summarizes precomputed
inputs; it does not perform matrix QC, state annotation, species separation,
reference mapping, causal preparation attribution, efficacy/safety assessment,
scoring or release. Real rule objects require independent biological review.
