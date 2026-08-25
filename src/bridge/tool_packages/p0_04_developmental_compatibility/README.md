# P0-04 Developmental Compatibility

This module implements the deterministic P0-04 candidate runtime. Biology stays
in checksummed `DevelopmentWindowSpec` and `DevelopmentStateMap` inputs; the code
only validates bindings and aggregates P0-02 composition counts.

Runtime entry: `adapter:adapter`. Result model:
`DevelopmentalCompatibilityResult`. The packaged Tool Card and example request
define the full input, output, checksum, missing-state and reason-code contract.

The package never assigns a state, converts in-vitro day to fetal age, performs
inferential time-course analysis, or emits a domain score.
