# P0-04 Developmental Compatibility

P0-04 evaluates an externally declared developmental window without embedding
state identities, marker sets, stage conversions or score thresholds.

## Runtime

The base path aggregates the current P0-02 composition into whole-product and
target-related `earlier`, `within_window`, `later`, `branch_shift` and
`unresolved` roles. The optional expression path reads a checksummed H5AD and
executes selected reference, ordinal, program, bootstrap and true-time methods
from a versioned `DevelopmentMethodSpec`.

Outputs are `DevelopmentalCompatibilityResult` and, when requested,
`DevelopmentMethodBundle`. Both retain `domain_score=null`; method evidence
is candidate/shadow.

## Documentation

- [Implementation, software and calls](../../../../docs/tool-packages.md#p0-04)
- [Tool Card](../cards/P0-04.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/developmental_compatibility_task_card.md)
- [Request example](../../../../examples/requests/p0_04_developmental_compatibility.json)
- [Method-spec example](../../../../examples/objects/p0_04_development_method_spec.json)
- [Validation](../../../../docs/validation/p0_04_developmental_compatibility_v0.3.md)

Use `bridge-tool describe P0-04` and `bridge-tool input-contract P0-04` for
the installed contract.
