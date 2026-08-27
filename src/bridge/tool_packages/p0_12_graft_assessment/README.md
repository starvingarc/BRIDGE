# P0-12 Optional Graft Assessment

This module runs optional graft evidence independently from the pre-transplant
product profile.

## Interface at a glance

- **No graft:** an empty structured-input list returns `not_provided`.
- **Precomputed evidence:** a checksummed GraftCase, GraftAssessmentSpec and
  GraftEvidenceBundle produce a descriptive aggregation.
- **Expression analysis:** a checksummed H5AD manifest, external analysis spec,
  reference panel and marker-program collection produce sample-aware
  composition, pseudobulk reference support and program evidence.
- **Boundary:** every provided result remains `candidate/shadow`;
  `domain_score=null` and graft evidence never backfills pre-transplant
  domains.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-12)
- [Tool Card — authoritative runtime interface](../cards/P0-12.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/graft_assessment_task_card.md)
- [No-graft request](../../../../examples/requests/p0_12_graft_assessment.json)
- [Expression-analysis request](../../../../examples/requests/p0_12_expression_analysis.json)
- [Expression-analysis validation](../../../../docs/validation/p0_12_expression_analysis_20260827.md)
- [Precomputed-mode validation](../../../../docs/validation/p0_12_graft_assessment_20260825.md)

Use `bridge-tool describe P0-12` and `bridge-tool input-contract P0-12` for
the installed version, schemas, environment, methods and exact input roles.
