# P0-04 Configurable Developmental Compatibility

## Goal

Make P0-04 callable through the existing `ToolRequestV2` seam while keeping
the target developmental window and every state-to-window assignment outside
implementation code.

## Interface

The request carries exactly one checksummed object for each role:

- `product_case`
- `product_definition_card`
- `development_window_spec`
- `cell_state_evidence_profile`
- `qc_readiness_profile`

`DevelopmentWindowSpec` binds the ProductDefinition and annotation vocabulary,
selects composition views and sources, and supplies the `earlier`,
`within_window`, `later`, `branch_shift` or `unresolved` assignment for each
state. A changed scientific decision therefore changes the input version and
checksum, not Python code.

The first executable version intentionally implements only the static,
dual-denominator composition path. Reference-stage support, true-timepoint
trends, inferential statistics and lineage calibration remain explicit
`not_assessed` or `unavailable` channels; no placeholder algorithm is added.

## Deliverables

- module-local models, executor and adapter;
- public and packaged DevelopmentWindowSpec/result Schemas;
- one synthetic request, detailed Tool Card and validation record;
- focused source and installed-wheel tests;
- one P0-04-only stacked Draft PR based on the reviewed P0-03 branch.

## Verification and boundary

All project execution occurs in GitHub Actions. Required gates are the
installed-wheel P0-03/P0-04 suites, complete pytest, 12-tool discovery,
knowledge validation, repository policy, projection parity and diff checks.

P0-04 remains `candidate`, emits no MeasurementResult or visualization, keeps
`domain_score=null`, and cannot approve a window, infer fetal age from an
in-vitro day, or claim efficacy, safety, potency or release readiness.
