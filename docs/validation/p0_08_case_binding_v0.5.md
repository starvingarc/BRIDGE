# P0-08 case-bound evidence gate validation — v0.5

## Scope

This record validates the engineering closure that binds each QC-backed domain
assessment to one checksummed ProductCase. It does not validate a biological
reference, domain measurement, gate threshold, score or release decision.

## Contract change

P0-08 0.5.0 keeps the v0.2 result schemas and candidate gate resources. It adds
one optional ProductCase input role that becomes mandatory whenever a
DomainGateInput declares a ProductCase pointer or QC profile.

Eligibility now verifies:

- ProductCase ID, case version and provenance against every domain pointer;
- ProductDefinition identity against the ProductCase;
- QC-selected sample/preparation, biological-unit manifest checksum and assay
  against the ProductCase;
- explicit or generic `eligible`/`conditional` authorization for every tool
  named by the domain MeasurementSpec.

The ProductCase source MeasurementSpec remains independent from each domain
MeasurementSpec. Missing scientific records can still produce `not_assessed`;
missing or contradictory case bindings fail before publication.

The v0.2 run-result model also closes the exported provenance wrapper: a
non-null Case summary requires exactly one ProductCase source binding, whose
logical ref must equal the summary ref and every non-null profile ref. For this
role, `SourceObjectBinding.object_version` records `ProductCase.case_version`;
the request still carries the ProductCase Schema object version, and
`schema_ref` plus `source_sha256` continue to bind the exact accepted bytes.
A legal sparse result with no Case ref carries no ProductCase binding, and an
extra binding is rejected rather than ignored.

## Verification

| Check | Result |
|---|---|
| P0-08 module suite | 486 passed |
| Registry, CLI, SDK and shared-contract suites | 74 passed |
| Public schema generation | Result schema regenerated; historical v0.1 resources unchanged |
| Documentation parity | Spec, Tool Card, package README, request example and task card aligned |
| Repository policy | Passed |
| Diff hygiene | Passed |

The module suite includes ProductCase ID/version/provenance mismatches, absent
ProductCase, missing QC selected view, sample/preparation and biological-unit
manifest mismatch, missing/unknown QC authorization, positive explicit/generic
authorization, source/domain MeasurementSpec independence, checksum replacement,
deterministic input-order behavior, exact run-result source binding, missing,
duplicate or mismatched binding refusal, profile/summary mismatch, and no-Case sparse
compatibility.

## Scientific boundary

P0-08 remains `candidate`. It folds versioned upstream evidence and creates no
new measurement. No ScoreContract is approved, so `domain_score=null` and
`score_state=unavailable` remain mandatory. Engineering test success is not
evidence of product identity, quality, safety, efficacy, potency or release
eligibility.
