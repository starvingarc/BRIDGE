# P0-05 real method runtime candidate validation — v0.3

## Question tested

Can P0-05 retain its six-object aggregation contract while adding a callable,
checksummed method mode for composition uncertainty, rare-state planning and
supplied-source OOD coordination without embedding product-specific biology?

This record validates engineering execution and refusal semantics. It does not
validate a StateRoleMap, detection limit, OOD channel, product interpretation or
safety claim.

## Validated source

| Item | Value |
|---|---|
| Branch | `p0-05-real-method-runtime` |
| Base commit | `d749e8b3a05ffe9c4461312e8eb01b3fd32eb492` |
| Validated implementation | code, schemas, examples and documentation co-committed with this record |
| Runtime | Python 3.12 |
| Tool version | `0.3.0` |
| Primary result schema | `bridge://schemas/off-target-control-profile/v0.1` |
| Method artifact schema | `bridge://schemas/off-target-method-bundle/v0.1` |
| Scientific status | `candidate / shadow` |
| Score | `score_state=unavailable`, `domain_score=null` |

## Input modes

`legacy_aggregation` uses the existing six checksummed objects and P0-02 V2.
`method_runtime` uses the same product, role, assessment and evidence objects,
requires P0-02 V3, and adds:

- a reviewed `BiologicalUnitManifest`;
- an `OffTargetMethodSpec` containing method selection and numerical rules;
- an `OffTargetMethodInput` containing unit-level composition, spike-in trials
  and OOD channel states.

The fixture used four analysis units in four declared independence groups. Unit
soft and hard counts closed exactly to the whole-product evidence bundle and to
the P0-02 V3 reconciliation partition. No expression matrix, private sample ID
or unpublished result was used.

## Executed methods

| Selector | Runtime implementation | Output boundary |
|---|---|---|
| `COMP-EXACT` | SciPy beta quantiles for Clopper-Pearson intervals | descriptive cell-count interval; not replicate uncertainty |
| `COMP-HARD-SENS` | hard-versus-soft role aggregation | sensitivity record, not a preferred annotation rule |
| `COMP-HBOOT` | seeded NumPy resampling of independence groups | uncertainty over declared groups only |
| `RARE-EXACT` | Clopper-Pearson rare-state count interval | descriptive count evidence only |
| `RARE-SPIKEIN` | empirical recovery curve and external acceptance rule | candidate detection limit, not scientific validation |
| `RARE-BINOMIAL-AT-LEAST-ONE` | single-state at-least-one-cell binomial calculation | not SCOPIT; retains independent-sampling and perfect-detection assumptions |
| `OOD-DISAGREE` | source-family state comparison | disagreement audit, not OOD inference |
| `OOD-ENSEMBLE` | ordered external-rule coordinator | supplied channel states only; family conflict returns `not_assessed` |

Catalogued deep OOD, compositional inference and rare-cluster discovery methods
remain conditional candidates and were not executed by this release.

## Results

| Gate | Result |
|---|---|
| P0-05 legacy and method suites | `24 passed` |
| P0-05 plus registry and knowledge-catalog checks | `46 passed` |
| Input contracts | `legacy_aggregation` has 6 roles; `method_runtime` has 9 roles |
| Generated artifacts | P0-05 public schemas, Tool Card and knowledge snapshot regenerated from their repository sources |
| Repository checks | knowledge validation, repository policy and `git diff --check` passed |
| Formal-eligible methods | 0 |

These counts describe the focused closure run for this revision. The required
GitHub repository gate remains the authority for the complete source suite,
wheel build, 12-tool discovery and clean-install checks.

## Observed semantics

- All eight selectors ran through the same installed adapter used by the CLI
  and SDK, producing one primary profile and one method bundle.
- Identical checksummed inputs and seed reused the same run and artifact bytes.
  Changing the seed changed the run fingerprint.
- Bootstrap sampled declared independence groups rather than cells.
- Spike-in output reports each fraction's independent-group count and uses `candidate_detection_limit_fraction`; it did not promote
  the supplied engineering acceptance rule to biological validation.
- The checksummed MethodSpec fixes each OOD channel's family, upstream-result
  checksum, method and reference. Runtime input supplies only state/reason, and
  one upstream result cannot be relabelled as two families. Within-family
  conflict remains `not_assessed`; this boundary was reviewed in code
  but was not part of the executable fixture reported above.
- Missing one of the three method objects, changing an independence-group
  binding or replacing an input file prevented execution with typed reasons.
- Legacy six-object requests remained callable and continued to emit one
  `OffTargetControlProfile` artifact.

## Measurement projection contract closure — tool v0.5.1

A later compatibility closure kept both execution modes and the v0.2 result schema,
but separated the P0-05 domain MeasurementSpec from the P0-02 source spec carried
by ProductCase. Any run requesting normalized measurement projection now also
requires one checksummed reviewed BiologicalUnitManifest. Eligibility verifies the
analysis unit, independence group, assay-specific cell/nucleus observation unit,
ProductCase manifest binding and denominator count before projection. Missing or
mismatched unit evidence fails closed.

The focused server run covered legacy aggregation and method execution, including
unit-mismatch and missing-manifest adversaries: `55 passed`. This is engineering
contract evidence only and does not validate the supplied StateRoleMap, thresholds,
OOD evidence or biological interpretation.

## Remaining scientific work

Formal evidence still requires product-specific StateRoleMap review, real
whole-product denominator review, known-mixture composition error, source-family
and OOD holdouts, rare-state spike-in/false-positive calibration,
reference/preprocessing/assay sensitivity, and signed review of every external
rule object. Cell-count intervals must not be presented as biological-replicate
inference. The single-state binomial design is optimistic when detection is imperfect and must not be represented as SCOPIT.

Until those gates are independently completed, all method outputs remain
engineering candidates: `evidence_state=shadow`, `score_state=unavailable`,
`domain_score=null`.
