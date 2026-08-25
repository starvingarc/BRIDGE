# P0-03 configurable target/regional candidate validation — 2026-08-25

## Question

Can P0-03 deterministically convert a lineage-bound P0-02 composition into raw
target-identity and regional-fidelity evidence while keeping every mutable
biological decision in versioned, checksummed inputs?

This is an engineering contract validation. It does not validate a real
StateRoleMap, product definition, reference, target/regional conclusion,
efficacy, safety, potency, GMP release or ranking.

## Candidate interface

The candidate accepts exactly nine `ToolRequestV2` object roles: ProductCase,
ProductDefinitionCard, StateRoleMap, TargetRegionalAssessmentSpec,
MeasurementSpecV2, CellStateEvidenceProfileV2, QCReadinessProfileV2,
BiologicalUnitManifest and BiologicalUnitAssignmentArtifact. It publishes one
atomic `TargetRegionalEvidenceResult` JSON artifact, no MeasurementResult and
no visualization. `domain_score` is always null.

The assignment artifact is validated and checksum-bound even though it does not
choose a lineage/regional role. It closes each observation to the declared
analysis unit and independence group so a valid composition cannot be reused
with a different experimental-unit interpretation.

## Controls

- exact role, Schema, role-specific object version, regular file and SHA-256;
- one ProductCase/source plus ProductDefinition and assessment binding;
- MeasurementSpec assay, applicability, analysis-unit and independence-unit
  binding;
- exact P0-01/P0-02 data view, observation set, denominator and QC lineage;
- manifest ref/checksum/scope/unit/group and assignment
  checksum/data-view/observation/hierarchy/group closure;
- configurable composition views, sources, label levels and role sets;
- explicit refusal of source configuration no-ops and unresolved-role promotion;
- upstream unknown/OOD/unresolved rows, explicit unresolved mappings and
  residual counts stay unresolved and force `partial`;
- target/regional numerator and denominator conservation;
- distinct shadow, not-assessed, unavailable, unknown and missing states;
- deterministic input identity, same-byte reuse, changed-byte refusal and input
  mutation detection;
- atomic single-JSON publication with existing-directory, extra-file,
  non-regular-path and symlink adversarial cases;
- old v0.1 profile refusal and public Schema/Pydantic parity;
- source and installed-wheel CLI/SDK invocation.

## Evidence status

The following evidence was reproduced from implementation commit
`f0b458728f311fb8ccdb3d2a59e2456ef1808c32`. Any implementation or packaged
content change invalidates this closeout. No previous PR, workflow run, wheel
checksum or test count is reused as evidence.

| Gate | Current result |
|---|---|
| P0-03/shared-runtime focused suite | 197 passed |
| Complete source pytest | 1,079 passed; 3 pre-existing dependency warnings |
| Complete installed-wheel pytest | 1,079 passed; the same 3 warnings |
| Wheel and installed import | `bridge-0.2.0.dev0-py3-none-any.whl`; SHA-256 `5ae1a0bd54e141a24df421ad879d9ce389d9adca2a84fd09a2b5d7671dcc938e`; import resolved from independent Python 3.12 `site-packages` |
| CLI/SDK validate and run | installed CLI `describe/validate/run` and SDK eligibility/run passed; identical deterministic result/run ID |
| 12-tool discovery | exactly 12, `P0-01` through `P0-12` |
| Knowledge validation | valid; no dangling method/source refs; `formal_eligible_method_count=0` |
| Repository policy | passed with the implemented-package file budget |
| Two-pass Schema/Card generation | byte-identical second pass |
| Privacy, path, LFS and diff checks | passed; only synthetic path/credential canaries remain in adversarial tests |

All validation is performed on `/data1`; no project code is executed in the
local checkout. The committed example and tests use fully synthetic identifiers
and contain no unpublished data.

## Interpretation boundary

P0-03 remains `candidate`. A `complete` result means only that requested
channels were present, mapped and arithmetically coherent. `shadow` means the
raw candidate output is retained without release promotion. It does not mean
that the external StateRoleMap, denominator selection, reference applicability
or biological conclusion has been reviewed or frozen.
