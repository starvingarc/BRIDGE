# P0-07 Configurable Product Comparison

## Goal

Make P0-07 callable through `ToolRequestV2` while keeping metric identity,
units, favorable direction, comparability dimensions, assay choice, evidence
eligibility and preparation requirements in versioned checksummed inputs.

## Interface

The first executable slice accepts exactly one ComparisonSpec and one
ComparisonEvidenceBundle. It compares exactly two ProductCases at the
preparation level and publishes one ComparisonRecord.

The executor checks configured contract dimensions, filters only by
caller-supplied metric rules, calculates baseline/candidate mean and range, and
reports the raw candidate-minus-baseline delta. It does not open expression
matrices or rerun an upstream P0 module.

## Explicit non-goals

- no embedded assay, metric, product, stage, program, direction or threshold;
- no inferential test, confidence interval or effect-size model;
- no time-course, batch-correction, integration or stability model;
- no Pareto conclusion, score or rank without a future frozen ScoreContract;
- no clinical, safety, potency, GMP-release or biological-truth claim.

Missing inputs remain unavailable rather than zero. Contract-valid contextual
comparisons remain descriptive; non-comparable cases do not emit a delta.

## Deliverables

- module-local models, executor and adapter;
- three public and packaged JSON Schemas;
- a synthetic request, detailed Tool Card and validation record;
- focused source and installed-wheel tests;
- one P0-07-only stacked Draft PR based on the P0-06 branch.

## Verification and stop

All project execution occurs in GitHub Actions. The PR remains Draft after
engineering gates. ComparisonSpec contents and real ProductCase evidence need
separate scientific review and can change without implementation changes.
