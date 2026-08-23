# P0-03 Configurable Target & Regional Evidence

## Goal

Make P0-03 callable through the existing `ToolRequestV2` CLI/SDK seam. The
module converts a versioned P0-02 `CellStateEvidenceProfile` into raw target-
identity and regional-fidelity evidence. Biological state assignments remain
checksummed input data and can change by object version without editing code.

## Stable interface

The request carries exactly one object for each role:

- `product_case`
- `product_definition_card`
- `state_role_map`
- `target_regional_assessment_spec`
- `cell_state_evidence_profile`
- `qc_readiness_profile`

The first four objects define versioned context and policy. P0-02 and P0-01
profiles remain upstream evidence. The adapter validates role/schema/checksum,
cross-object identity, assay, MeasurementSpec and denominator bindings before
calling the executor.

The result is one `TargetRegionalEvidenceResult` containing:

- role-resolved target and regional composition;
- unmapped or unresolved upstream states;
- source-view and denominator provenance;
- an explicit spatial `not_assessed` state when no frozen projection is supplied;
- `domain_score=null` and a non-available score state.

## Implementation rules

- Code contains no PD-mDA state-to-role table, marker list, regional label map,
  threshold or product pass/fail rule.
- `StateRoleMap` supplies every biological state assignment.
- `TargetRegionalAssessmentSpec` selects supported deterministic composition
  views and aggregation behavior.
- Missing mappings are reported as `unresolved`; they are never guessed or
  counted as zero.
- Shadow P0-02 evidence remains shadow. This PR cannot promote a scientific
  release state or make a clinical, safety, potency or GMP claim.
- No spatial algorithm, expression re-analysis, new runtime framework,
  database, queue, LLM client or `ToolRequestV3` is introduced.
- Repository growth remains bounded to the 314-file baseline plus at most 18
  files for each newly implemented package; this module uses only its adapter,
  models, executor, schemas, test, example, plan and validation/card projections.

## Deliverables

- module-local models, executor and adapter;
- public and packaged JSON Schemas generated from the same Pydantic models;
- P0-03 v0.2 implemented spec with the two registered target/regional
  StateRoleMap method IDs;
- synthetic example inputs/request/output expectations;
- one detailed Tool Card source and its byte-identical public projection;
- focused tests for deterministic results, cross-binding, missing/unmapped
  states, input immutability, reuse, V1 refusal and score/release boundaries;
- validation record binding source and clean-wheel evidence.

## Verification

No project code is run in the local macOS checkout. Source and installed-wheel
verification run in GitHub Actions, or in `/data1` only when that environment is
separately reachable and authorized. Required gates are full pytest, 12-tool
discovery, knowledge validation, repository policy, schema/card/example parity,
wheel installation, deterministic reuse, privacy scan and `git diff --check`.

## PR boundary

Branch: `p0-03-target-regional-evidence`.

The PR remains Draft until its exact head passes the required GitHub check and
an independent closure review. Implementation and CI do not authorize merge.

## Current status

Implementation and exact installed-wheel verification are complete at
`0c876c183b2c17e15af26c68c915434c258c7fba`: 27 focused and 986 total tests
passed, 12 tools remained discoverable, the knowledge snapshot retained zero
formal-eligible methods, and repository policy passed. The remaining plan item
is an independent closure review of Draft PR #20; no scientific review or
release promotion is implied.
