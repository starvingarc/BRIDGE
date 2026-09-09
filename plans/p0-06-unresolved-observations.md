# P0-06 Source-bound Observations Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to implement and review this plan.

**Status:** implementation_complete_review_pending
**Tech Stack:** Existing Python, Pydantic, JSON Schema and scientific runtime; no new dependency.

## Global Constraints

- Preserve all existing versioned inputs and scientific semantics; retain candidate/shadow, domain_score=null and score_state=unavailable.
- Do not invent biological units, roles, probabilities, calibration, thresholds or release authority. Missing, unknown, unavailable and unresolved remain distinct.
- One module per branch/PR. Only the integrator edits shared input contracts, Schema index, packaged specs, generators, policy and plan index.
- Execute code/tests only in the approved private remote workspace. Keep real-resource names, locations, hashes and measurements out of Git and PR text.
- Reuse existing adapters, checksum checks and artifact publication. No general plugin, resolver, workflow or authentication framework.

**Goal:** Accept canonical producer conflicts without forcing a single identity or losing whole-product observations.
**Architecture:** A new input version resolves existing producer Parquet rows internally against its exact artifact manifest. Existing input versions and result shapes remain unchanged.
**Spec:** docs/bridge_spec_v0.1/proliferation_stress_response_task_card.md; canonical P0-02 V3 and artifact manifest contracts.

### Task 1: Implement source-bound observation consumption

**Files:** Module method_models.py, method_binding.py, method_runtime.py and adapter.py; one focused observation_source.py if needed; tests/test_p0_06_source_bound_observations.py; module README, cards/P0-06.md and scientific task card. Do not modify the P0-02 producer or shared discovery files.

**Interfaces:** Preserve ProcessMethodInput, ObservationStateAssignment and ObservationState v0.1 byte/semantic contracts. Add standalone ProcessMethodInputV2, object_version=0.2.0, bridge://schemas/process-method-input/v0.2, process_method_input_v2.schema.json. Retain identifying/lineage metadata from v0.1, replacing caller observation_states with required source_observations: ProcessObservationSourceV1. No parallel caller-row alternative.

Descriptor fields: source_format=p0_02_cell_state_evidence_parquet_v0.1, producer_tool_id=P0-02, producer_run_ref, producer_tool_version, absolute artifact_manifest_path, artifact_manifest_sha256, evidence_artifact_id, absolute evidence_path, evidence_sha256 and label_level=L1. All hashes use the existing strict Sha256 type. This validates content correspondence, not independent authentication of a completely fabricated caller bundle.

New mode method_runtime_source_bound has the existing method_runtime expression constraints and 12 structured roles, except process_method_input uses v0.2/0.2.0. Exact version/schema selects it; mixed combinations fail. Package version 0.7.0. ProcessMethodSpec v0.1, result profile v0.3 and bundle v0.2 stay unchanged if no fields change. Register the new input in module PUBLIC_METHOD_SCHEMA_MODELS; root owns discovery/Schema/spec wiring.

Load only regular nonsymlink files, check byte hashes before/after reads and before publishing output. Bind the same-run manifest tool/run/version and exact supplied V3 and evidence artifacts, IDs/kinds/media types/hashes/paths using canonical manifest semantics. Match selected-view observation IDs and count to V3 and biological assignments, using each existing field's canonical observation-digest algorithm (including sorted-ID hashing for the biological assignment contract); join expression rows by identity, never position. Validate strict prediction_set JSON arrays of unique strings, L1 reconciliation counts and consensus counts against V3.

Parse rows internally into a separate normalized type retaining observation_id, state, state_id, prediction_set, support_state, assignment_state and open_set_state. Consensus-supported singleton with matching consensus_label is candidate; single-source singleton with null consensus_label is candidate with support distinction retained; multi-candidate source_conflict is unresolved with null state_id; empty unavailable is unavailable. Never infer unknown from conflict/empty/not_assessed. Unsupported producer semantics fail closed; old v0.1 unknown remains supported as before. Pass resolved rows explicitly to runtime without mutating input models or performing hidden model-property I/O.

Whole-product groups retain every observation in each declared unit, including unresolved/unavailable. State-specific groups contain only uniquely assigned candidates allowed by that ProgramSpec. For this new mode, a candidate outside a program allowlist remains valid in whole-product analysis. With all conflicts, no state-specific zero is invented. Existing normalization, score methods, minimum-cell behavior, measurements, figures and null score semantics remain unchanged. method_input_sha256 transitively binds descriptor and source bytes.

- [x] Write a failing source-bound test using real producer-format synthetic Parquet and manifest. Establish hand-counted groups:

```python
assert sum(whole_product_counts) == selected_observation_count
assert all(not assigned_to_state[row_id] for row_id in conflict_observation_ids)
assert resolved_conflict.state_id is None
```

- [x] Retain RED evidence, then implement exact source parser/binding and explicit resolved-row runtime handoff.
- [x] Cover all four producer support states; swapped labels/checksums/run/version/profile binding; malformed/duplicate/missing IDs or predictions; reordered expression identity joins; changed input and symlink failures. Candidate outside allowlist stays in whole-product counts. All-conflict input produces no fake conditioned result.
- [x] Run the new suite and old P0-06 tests; confirm old input schemas unchanged, exact denominator/provenance preservation and no new science defaults.
- [x] Document fields, source ownership, CLI/SDK mode selection, failure reasons and a logical request example; self-review and commit module-owned files with exact test evidence.

### Task 2: Integrate, verify and review

**Files:** src/bridge/tool_packages/_input_contracts.py; src/bridge/toolkit/schemas.py; specs/p0_06.yaml; new generated Schema; plans/README.md; docs/decision-log.md and validation record. Integrator only.

- [x] Register the new version-selected mode and input URI; generate only the new Schema and preserve old schemas; verify Card/spec versions.
- [x] Run focused module and shared-contract checks, 12-tool discovery, installed-wheel smoke, repository policy and diff hygiene.
- [x] Independently review the complete module diff and close the typed-refusal finding in a scoped fix review.
- [ ] Submit one Draft PR after final documentation and privacy checks. Source correspondence or passing fixtures alone does not prove biological lineage or a complete real-data Web run.

## Verification checkpoint

Implementation and shared integration are complete. The installed-wheel check at `8f5eb9e1` passed 186 module/shared-contract tests (49 existing Scanpy deprecation warnings), 12-tool discovery, CLI describe/input-contract, knowledge and figure validation, repository policy and diff checks. The full-diff review found one malformed-source typed-refusal defect; it is fixed and scoped re-review approved the correction with no new findings. See [the validation record](../docs/validation/p0_06_proliferation_stress_response.md#record-p0-06-source-bound-observations-20260907) for reproducible checks and limits.

GitHub CI and publication remain separate pending gates. Genuine experimental-design confirmation, actual producer binding and real-data Web integration are follow-up work, not claims of this module change.
