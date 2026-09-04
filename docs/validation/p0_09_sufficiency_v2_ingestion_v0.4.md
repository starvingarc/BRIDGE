# P0-09 canonical sufficiency ingestion validation

Date: 2026-09-05
Package: `P0-09 Evidence Compiler & Reconciler` v0.4.0
Prerequisite: P0-08 v0.5 case-bound result contract

## Scope

This record validates the P0-09 interface that consumes canonical
`EvidenceSufficiencyRunResultV2` objects without changing the P0-09 result
Schema. Direct v0.1/v0.2 profile inputs remain supported.

The executable matrix covers:

| Scope | Direct profile mode | Canonical run-result mode |
|---|---|---|
| Case, initial | `case_initial` | `case_initial_v2` |
| Case, append | `case_append` | `case_append_v2` |
| Comparison, initial | `comparison_initial` | `comparison_initial_v2` |
| Comparison, append | `comparison_append` | `comparison_append_v2` |

## Verified behavior

- Canonical mode accepts one P0-08 v0.2 run for a Case and two to five
  case-distinct runs for a Comparison.
- The complete P0-08 wrapper remains a checksummed semantic input. Each emitted
  EvidenceRecord cites the exact embedded profile version.
- The adapter resolves an embedded profile by request binding, ProductCase and
  domain. MeasurementSpec, MeasurementResult, Claim, source-record and family
  checks remain compiler-owned record checks.
- A Schema-valid record with drift is rejected into sanitized metadata while
  valid siblings are published as a `partial` run.
- A missing-only Case creates open EvidenceRequirements, emits no EvidenceRecord
  and never substitutes a numeric zero.
- Duplicate `result_id` plus `result_version` identities, mixed direct/run
  modes, case-set mismatch, checksum mismatch and ambiguous profile routing fail
  closed before artifact publication.
- The canonical fixture includes the ProductCase source binding emitted by the
  current P0-08 producer path.
- P0-08 family bindings remain ID-only. P0-09 therefore continues to reject
  formal evidence with `sufficiency_profile_version_binding_unavailable`.

## Executed checks

An isolated Linux source environment ran:

- `tests/test_p0_09_evidence_compiler.py`
- `tests/test_registry.py`

Result: **218 passed**.

The focused regression set additionally exercised canonical Case initial,
canonical Comparison initial, duplicate run identity, missing-only requirements,
mixed-mode refusal, record-level MeasurementResult drift, and dangling
Comparison provenance. Result: **6 passed, 212 deselected**.

Repository policy, shared contract tests, diff hygiene and publication-boundary
scans are recorded in the associated change history and continuous integration.

## Provenance design basis

The separation between run-wrapper identity and record-level derivation follows
the explicit activity/entity linkage in
[W3C PROV-O](https://www.w3.org/TR/prov-o/) and the unique run, tool version,
consumed object and generated result conventions in
[Workflow Run RO-Crate Process Run 0.5](https://www.researchobject.org/workflow-run-crate/profiles/0.5/process_run_crate/).

## Scientific boundary

This is engineering validation of deterministic ingestion, provenance,
failure isolation and artifact behavior. It does not establish biological
truth, evidence sufficiency, product superiority, potency, safety, efficacy or
release eligibility. P0-09 remains `candidate`; no domain score is created.
