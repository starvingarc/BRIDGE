# P0-12 Optional Graft Assessment

This module runs optional graft evidence independently from the pre-transplant
product profile.

## Interface at a glance

- **No graft:** an empty structured-input list returns `not_provided`.
- **Precomputed evidence:** a checksummed GraftCase, GraftAssessmentSpec and
  GraftEvidenceBundle produce a descriptive aggregation.
- **Expression analysis:** a checksummed H5AD manifest, external analysis spec,
  aggregation-matched reference panel and marker-program collection produce
  all-row descriptive composition, sample-profile reference support and program
  means. This mode accepts exactly one declared graft/animal/timepoint; multiple
  sample IDs are technical samples, not independent biological replicates.
- **Profile semantics:** raw counts produce `sample_pseudobulk`; declared
  log-normalized values produce `sample_mean_log_expression`. The reference must
  declare the same aggregation and `log1p_cp10k` value semantics.
- **Figures:** every successful mode publishes typed specimen-scope,
  uploaded-profile composition and reference/program-evidence views with complete
  TSV fallbacks and SVG/PNG/PDF renders. Missing values remain explicit
  unavailable states; technical samples are not biological replicates.

- **Boundary:** every provided result remains `candidate/shadow`;
  `domain_score=null` and graft evidence never backfills pre-transplant
  domains.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-12)
- [Tool Card — authoritative runtime interface](../cards/P0-12.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/graft_assessment_task_card.md)
- [No-graft request](../../../../examples/requests/p0_12_graft_assessment.json)
- [Expression-analysis request](../../../../examples/requests/p0_12_expression_analysis.json)

Use `bridge-tool describe P0-12` and `bridge-tool input-contract P0-12` for
the installed version, schemas, environment, methods and exact input roles.
