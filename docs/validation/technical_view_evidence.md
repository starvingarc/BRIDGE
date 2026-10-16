# Technical-view evidence admission

## Scientific question and data

Can existing whole-view RNA method outputs retain their exact measurements and
source lineage through evidence gating and graph queries without claiming
biological replication? Contract fixtures are synthetic. A separate private
acceptance used existing checksummed P003 native similarity outputs, their
original inputs/reference manifest, an existing QC view and unresolved product
context. No expression matrix, QC or cell-state model was rerun.

## Observation and supported conclusion

The registered saved-source projection produced separate native Spearman and
cosine measurements. Normal P008/P009 calls accepted and compiled them; the
normal graph reader opened the result and returned an untruncated query. Every
coefficient, unit, source measurement, label/profile mapping, spec artifact hash
and shared query-RNA family was checked against the saved source. Historical
P006 native values and receipts remained readable, and historical graphs opened
without rewriting them. Private paths, sample sizes and values remain outside
the repository.

This establishes engineering preservation/admission, not scientific validation.
The new MeasurementSpec v0.3 reports a technical aggregate, unknown biological
independence and null independent replicate count. P008 receipt v0.3 changes the
source-binding envelope, not the gate/profile/summary semantics. Existing public
schema files were checked byte-for-byte against the pre-change snapshot.

## Still unanswered

Reference suitability, product-role decisions, developmental-window matching,
independent biological robustness, calibrated activation/fraction thresholds,
potency and safety are not established. A graph record does not upgrade any of
these. Same-query RNA measurements are one dependent family, not votes.

## Reproducible checks

- `tests/test_technical_view_evidence.py`: technical-unit restrictions, frozen
  source-binding compatibility, nonfinite/out-of-range refusal, source artifact
  tamper refusal, saved-only projection and missing-value preservation.
- `tests/test_p0_06_exploratory.py`: five native outputs retained with an exact
  technical view and no invented independence.
- `tests/test_p0_08_evidence_sufficiency.py`: existing gate/profile semantics and
  exact source binding under the new output receipt.
- `tests/test_p0_09_evidence_compiler.py`: old/new receipt ingestion and canonical
  graph invariants. The existing normalized-property query fix is a separately
  identified integration dependency, not a checksum bypass.

Exact run IDs, source hashes and private SDK acceptance records are held in the
private handoff. Public contract and use: [tool contract](../tool-contract.md),
[similarity Tool Card](../../src/bridge/tool_packages/cards/P0-03.md).

Subsequent source-bound program execution is recorded separately in
[candidate program validation](candidate_programs.md).

## Saved developmental and whole-product context

The integrated saved-native P004/P005 paths also have controlled registered runs
and normal P008/P009 admission records. They reuse checked P002 candidate and
auxiliary outputs, preserving selected views, subgroup denominators, original
figures and producer bindings without rerunning matrices. P004 describes
reference-state/marker context, not an approved developmental-window match;
P005 describes whole-view label accounting, not a qualified target/non-target
fraction. The shared RNA family and parent-only review limits remain explicit.
Tests are in `tests/test_saved_native_context.py`; exact private receipts remain
outside Git. Combined Web continuation is still part of the
[mainline acceptance](../../plans/step7-evidence-coordinator.md).
