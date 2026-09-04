# P0-04 Developmental Compatibility

P0-04 evaluates an externally declared developmental window without embedding
state identities, marker sets, stage conversions or score thresholds.

## Runtime

The base path aggregates the current P0-02 composition into whole-product and
target-related `earlier`, `within_window`, `later`, `branch_shift` and
`unresolved` roles. The optional expression path reads a checksummed H5AD and
executes selected reference, ordinal, program and bootstrap methods from a
versioned `DevelopmentMethodSpec`.

The ProductCase and P0-02 profile keep their cell-state source MeasurementSpec.
P0-04 receives a separate domain MeasurementSpec that owns developmental metric
projection, assay, tool authorization and biological-unit semantics.

The ordinal method is an uncalibrated baseline and runs only when the same
checksummed method spec supplies a reviewed, passed source-group-held-out
evidence receipt bound to every selected profile and at least two sources.
Incomplete reference-profile coverage and cross-source/assay stage-role
disagreement are unavailable rather than pooled. Ordered sampling-point labels
are categorical; continuous-time and inferential time-course evidence remain
unavailable until a numeric time contract exists.

Outputs include the preserved `DevelopmentalCompatibilityResult` v0.2 model
and a v0.3 result that binds one independent, checksummed
`MeasurementResultV2` JSON artifact for every existing whole-product and
target-related role fraction. When declared timepoints are present, their
already-computed role fractions are projected in the same way. The projection
copies raw fraction, numerator and positive denominator without adding a
threshold, developmental judgement or interval. A zero denominator, missing
profile or unavailable upstream state stays null/unavailable rather than
becoming zero.

`ToolRunV2.measurements` exposes the same projected objects for compatibility.
The v0.3 result, typed visualization data, three exact table fallbacks and
deterministic SVG/PNG/PDF figures are published atomically. Expression mode also
emits `DevelopmentMethodBundle`. All result and measurement objects retain
`domain_score=null` and `score_state=unavailable`; method evidence remains
candidate/shadow.

## Documentation

- [Implementation, software and calls](../../../../docs/tool-packages.md#p0-04)
- [Tool Card](../cards/P0-04.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/developmental_compatibility_task_card.md)
- [Request example](../../../../examples/requests/p0_04_developmental_compatibility.json)
- [Method-spec example](../../../../examples/objects/p0_04_development_method_spec.json)
- [Validation](../../../../docs/validation/p0_04_developmental_compatibility_v0.3.md)

Use `bridge-tool describe P0-04` and `bridge-tool input-contract P0-04` for
the installed contract.
