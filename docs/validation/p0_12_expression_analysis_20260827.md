# P0-12 expression-analysis validation — 2026-08-27

## Scope

This record verifies that the public P0-12 adapter can read a declared H5AD and
execute the selected deterministic analysis chain. It does not validate a
biological vocabulary, reference panel, marker program or release threshold.

## Fixture and controls

The executable fixture is fully synthetic: eight cells, five genes, two
technical samples and one declared graft/animal/timepoint. It provides a
raw-count layer, two externally declared
state-probability columns, a versioned reference profile and a versioned marker
program. All five JSON inputs and the H5AD carry SHA-256 bindings.

Controls cover:

- compatibility with the existing no-input and three-object modes;
- missing declared observation fields;
- H5AD checksum replacement;
- a gzip-compressed sparse H5AD whose on-disk bytes pass but whose logical
  `n_obs × n_vars` exceeds the declared matrix-element budget;
- negative and fractional raw counts;
- negative or greater-than-one individual probabilities, excessive row mass,
  and an analysis-spec tolerance above the package engineering ceiling;
- a within-tolerance floating row-mass case that preserves every input
  probability and records the tolerated residual;
- unsafe sample identifiers;
- mixed, undeclared or missing graft units and missing animal/timepoint;
- exact object, case, assay, organism, gene-namespace, value-semantics,
  profile-aggregation, reference source-family, program source-family and method
  bindings;
- separate raw-count `sample_pseudobulk` and log-normalized
  `sample_mean_log_expression` paths;
- deterministic reruns and immutable publication.

## Observed behavior

The expression request passes the same registry, CLI and single top-level
adapter seam used by the other two P0-12 modes. Scanpy first opens the H5AD in
backed mode and checks the
on-disk byte and logical matrix-element budgets. An oversized logical shape is
rejected without a full read. Eligible files are then materialized, and the
shared P0-01 expression-object validator checks matrix structure and raw-count
semantics. Raw counts are summed by technical sample, normalized and
log-transformed into `sample_pseudobulk`; already log-normalized input is
averaged by technical sample into `sample_mean_log_expression`. Reference
correlation runs only when the external panel declares the same aggregation and
value semantics. Marker-program output is the mean of the externally
declared program genes in the same transformed sample profile; it is not an
independent identity method. Cell probabilities are pooled over all uploaded
rows for descriptive composition. No biological-unit weighting, confidence
interval or graft-QC reassessment is performed.

The successful result reports two technical samples nested within one declared
graft, the declared animal/timepoint, `sample_unit=technical_sample`, exact
`profile_aggregation`, `qc_state=not_reassessed`,
`composition_denominator=all_uploaded_rows`,
`analysis_value_semantics=log1p_cp10k`, reference and marker source-family
bindings, the selected method IDs, runtime versions and checksummed JSON
artifacts. Repeated identical input produces the same run and result. Individual
probabilities are never clipped: values outside `[0,1]` fail, while only finite
row-mass roundoff up to `1e-6` is tolerated and recorded. Invalid counts,
probabilities, identifiers, mixed graft observations, changed H5AD bytes,
missing unit metadata and external-context mismatches fail without publication.

## Engineering evidence

- Focused P0-12 expression, compatibility, registry and knowledge-catalog tests
  pass through the package runtime.
- Schema export retains the P0-12 union result and five expression-analysis
  object contracts in parity with the Pydantic models, including unit and
  aggregation semantics.
- Repository policy and diff checks pass.
- Public tool discovery remains 12 packages.
- The request example contains documentation placeholders only; no expression
  data or private metadata is committed.

## Scientific boundary

The run proves that the declared calculations execute through the published
interface. External state probabilities are not independently reclassified.
Reference correlation and marker-program means are descriptive evidence, not
cell identity, maturation truth, efficacy, safety, potency or release evidence.
Every provided result remains `candidate/shadow`,
`domain_score=null`, `score_state=unavailable` and
`pretransplant_evidence_effect=none`.
