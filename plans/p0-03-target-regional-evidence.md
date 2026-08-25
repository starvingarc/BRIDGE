# P0-03 Configurable Target & Regional Evidence

## Goal

Package P0-03 as a callable deterministic `ToolRequestV2` module that converts
P0-02 composition records into raw target-identity and regional-fidelity
evidence without freezing mutable biological assignments in code.

## Stable interface

The request carries exactly nine checksummed objects:

- `product_case`, `product_definition_card`, `state_role_map` and
  `target_regional_assessment_spec`;
- `measurement_spec` using the public v0.2 MeasurementSpec contract;
- `cell_state_evidence_profile` and `qc_readiness_profile` using their v0.2
  lineage-aware contracts; and
- `biological_unit_manifest` plus `biological_unit_assignment`.

The adapter validates the one ProductCase/source, assay, ProductDefinition,
MeasurementSpec, data view, observation set, analysis-unit, independence-group,
manifest and assignment lineage before aggregation. The assignment artifact is
not a role input; it prevents counts from being separated from the declared
experimental units.

The result is one atomic `TargetRegionalEvidenceResult` JSON containing
role-resolved raw composition, explicit denominators, all nine input checksums,
unmapped/unknown records, provenance, a typed upstream composition state,
spatial `not_assessed`, `domain_score=null` and either `shadow` or `unavailable`
score state.

## Implementation rules

- No product state ID, marker list, target map, regional map, threshold or
  product pass/fail rule appears in implementation code.
- `StateRoleMap` supplies state assignments;
  `TargetRegionalAssessmentSpec` supplies requested views, levels, sources and
  denominator/numerator role sets.
- Structural constraints forbid contradictions and prevent upstream or explicit
  unresolved evidence from entering positive output. Other role selections stay
  externally configurable.
- Missing mappings, OOD/unknown rows and residuals are reported, never guessed,
  normalized away or replaced by zero.
- Every channel conserves its declared denominator.
- Old v0.1 QC/Cell-State profiles cannot bypass the shared scientific contract
  spine.
- Output publication is one deterministic, immutable JSON file. The shared seam
  supports atomic create, same-byte reuse and different-byte refusal only; no
  generic snapshot or directory-hash framework is introduced.
- P0-03 remains `candidate`; assessed output remains `shadow`; no release or
  score claim is created.

## Deliverables

- P0-03 models, executor and adapter;
- three generated public/packaged JSON Schemas;
- v0.2 implemented tool spec with two registered deterministic method IDs;
- nine-object example request and detailed Tool Card projection;
- updated scientific task card and current validation record;
- focused contract, adversarial, deterministic and atomic-publication tests;
- full source and clean-wheel gates performed on `/data1` only.

## Verification

Required closeout gates are P0-03 focused tests, complete pytest, exactly 12
discoverable tools, knowledge validation, repository policy, two-pass Schema
and Tool Card generation, `git diff --check`, input immutability, deterministic
reuse, source and installed-wheel CLI/SDK smoke, and a scan excluding private
paths or unpublished data.

No project code is run in the local macOS checkout. This branch is not pushed or
merged by this integration task.

## Current status

The isolated server branch has completed source and clean-wheel engineering
closeout. The exact commit identity and gate summary are reported at handoff;
independent review remains required before any PR or merge. Passing engineering
gates does not constitute biological validation, scientific freeze or release
authorization.
