# P0-04 Developmental Compatibility

P0-04 evaluates an externally declared developmental window without embedding
state identities, marker sets, stage conversions or score thresholds.

## Runtime

The base path aggregates the current P0-02 composition into whole-product and
target-related `earlier`, `within_window`, `later`, `branch_shift` and
`unresolved` roles. The optional expression path reads a checksummed H5AD and
executes selected reference, ordinal, program and bootstrap methods from a
versioned `DevelopmentMethodSpec`.

The ordinal method is an uncalibrated baseline and runs only when the same
checksummed method spec supplies a reviewed, passed source-group-held-out
evidence receipt bound to every selected profile and at least two sources.
Incomplete reference-profile coverage and cross-source/assay stage-role
disagreement are unavailable rather than pooled. Ordered sampling-point labels
are categorical; continuous-time and inferential time-course evidence remain
unavailable until a numeric time contract exists.

Outputs include `DevelopmentalCompatibilityResult`, typed visualization data,
three exact table fallbacks and deterministic SVG/PNG/PDF figures. Expression
mode also emits `DevelopmentMethodBundle`. All results retain
`domain_score=null`; method evidence is candidate/shadow.

## Documentation

- [Implementation, software and calls](../../../../docs/tool-packages.md#p0-04)
- [Tool Card](../cards/P0-04.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/developmental_compatibility_task_card.md)
- [Request example](../../../../examples/requests/p0_04_developmental_compatibility.json)
- [Method-spec example](../../../../examples/objects/p0_04_development_method_spec.json)
- [Validation](../../../../docs/validation/p0_04_developmental_compatibility_v0.3.md)

Use `bridge-tool describe P0-04` and `bridge-tool input-contract P0-04` for
the installed contract.
