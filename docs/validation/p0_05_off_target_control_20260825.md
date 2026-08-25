# P0-05 Off-target Control candidate validation — 2026-08-25

## Question tested

Can P0-05 accept six immutable structured objects, apply only caller-supplied
state roles and assessment limits, and publish a deterministic whole-product
off-target profile while failing closed on incomplete coverage, zero
observations, missing calibration and broken provenance?

This is an engineering contract validation. It does not validate the biological
correctness of a StateRoleMap, an unknown vocabulary, a calibration record or
an off-target interpretation.

## Validated source

| Item | Value |
|---|---|
| Branch | `p0-05-off-target-control` |
| Base commit | `c336a20f25c8536b3a4a42dd1f85ee91bd83d6a1` |
| Validated implementation | code, schemas and documentation co-committed with this record |
| Runtime | Python 3.12 server environment |
| Tool version | `0.2.0` |
| Result schema | `bridge://schemas/off-target-control-profile/v0.1` |
| Scientific status | `candidate / shadow` |
| Score | `score_state=unavailable`, `domain_score=null` |

## Inputs and controls

Tests used only synthetic JSON objects. No private expression matrix, internal
sample identifier or unpublished biological result was opened or committed.

The happy path bound:

- one ProductCase and its ProductDefinitionCard;
- one separately checksummed StateRoleMap;
- one OffTargetAssessmentSpec that bound the exact map checksum;
- one P0-02 CellStateEvidenceProfileV2;
- one precomputed OffTargetEvidenceBundle bound to the case, card and profile.

The controls changed role assignment without changing package code, withheld
composition coverage, introduced undeclared unknown reasons, exercised detected,
calibrated-zero, missing-calibration, insufficient-calibration and
missing-observation rare states, broke cross-object bindings and checksums,
reused identical output, and tampered with a published bundle.

## Results

| Gate | Result |
|---|---|
| P0-05 focused suite | `18 passed` |
| P0-05 plus registry | `25 passed` |
| Complete source suite | `1062 passed, 8 existing warnings` |
| Tool discovery | exactly 12 packages; P0-05 is implemented |
| Public Schema count | 67; four P0-05 schemas packaged and resolvable |
| Knowledge validation | valid; 354 methods, 387 sources, 396 bindings, no dangling references |
| Tool Card and Schema generators | two successive runs were idempotent |
| P0-05 method | `METHOD-BRIDGE-ROLE-AWARE-SOFT-COMPOSITION` |
| Formal-eligible methods | 0 |

The warnings are existing AnnData duplicate-variable and SciPy sparse-matrix
migration warnings from P0-01 tests; no warning originated in P0-05.

The same immutable inputs produced the same run ID and result checksum.
Replacing the existing result bytes caused a typed failure rather than silent
overwrite. A V1 ToolRequest produced `tool_request_v2_required`.

## Observed semantics

- Changing the external role map moved the same state mass between generic
  product roles without any code change.
- Complete coverage produced role and unknown fractions against the declared
  soft-mass denominator.
- Partial coverage preserved observed mass/count but withheld fractions and
  returned `not_assessed`.
- Zero role or unknown observations returned `cannot_exclude`, not absence.
- A calibrated zero rare-state count returned `not_detected_above_lod` with
  the supplied upper bound and an explicit zero-is-not-absence reason.
- Missing or out-of-spec calibration returned `cannot_exclude`; a missing
  rare-state observation returned `not_assessed`.
- Unknown reasons and state IDs outside the external contracts failed
  eligibility.

## Boundary and remaining work

P0-05 does not rerun scRNA-seq, calculate cell-state assignments, train or select
an OOD method, fit detection limits, compare products, produce visualizations or
emit MeasurementResults. It does not establish biological truth, safety,
efficacy, potency, GMP release or product ranking.

Formal evidence remains blocked until product-specific StateRoleMap review,
real whole-product denominator review, OOD/source-family holdouts, known-mixture
composition checks, rare-state spike-in/false-positive calibration and
reference/preprocessing/assay sensitivity are independently completed and
versioned. Those scientific gates can revise the external objects without
changing this aggregation implementation.
