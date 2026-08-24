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

No local project code was run. The bounded closure implementation at
`d6fc5c55f7808911dacc8a55b9397c78a9262c49` was transferred as a Git archive
to `/data1` and validated from exact source and a clean wheel. The wheel
SHA-256 was
`753370f64d8eb6dcfb88b3e508f69e8590d5ebde9fcac9450bbc81a1daa547c0`:

- the wheel was built and `bridge` was imported from the clean installed
  site-packages directory, not the source checkout;
- the cumulative source configurable-interface suite passed `223` tests;
- both complete source and installed-wheel suites passed `1,182` tests, with
  three existing source-environment and two installed-environment warnings;
- exactly 12 tools were discoverable and public Schema parity remained green;
- knowledge validation reported no dangling method or source references and
  `formal_eligible_method_count=0`;
- repository policy and committed-whitespace checks passed.

The closure also moves generic object references to the shared configurable
contract and rejects machine-local or credential-like units in channel rules,
observations and result summaries. Graft calculations and scientific
boundaries are unchanged.

## Scientific boundary

P0-12 remains `candidate`. Its first executable slice summarizes precomputed
inputs; it does not perform matrix QC, state annotation, species separation,
reference mapping, causal preparation attribution, efficacy/safety assessment,
scoring or release. Real rule objects require independent biological review.

## Peer-review closeout addendum

The combined closeout separates the graft MeasurementSpec from the product
MeasurementSpec, requires exact provided-graft lineage, and makes lineage review
authority external and checksummed. Channels define disjoint graft/timepoint
strata, explicit within-animal aggregation and denominator semantics; animals
remain the estimand and cross-stratum aggregation is forbidden. Declared
lineage yields `partial/not_assessed`, and low animal count leaves interval
relation unavailable. Final exact-head evidence is recorded in the stack
closeout validation.
