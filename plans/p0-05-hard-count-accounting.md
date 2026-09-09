# P0-05 Hard-count Accounting Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to implement and review this plan.

**Status:** implementation_complete_review_pending
**Tech Stack:** Existing Python, Pydantic, JSON Schema and scientific runtime; no new dependency.

## Global Constraints

- Preserve all existing versioned inputs and scientific semantics; retain candidate/shadow, domain_score=null and score_state=unavailable.
- Do not invent biological units, roles, probabilities, calibration, thresholds or release authority. Missing, unknown, unavailable and unresolved remain distinct.
- One module per branch/PR. Only the integrator edits shared input contracts, Schema index, packaged specs, generators, policy and plan index.
- Execute code/tests only in the approved private remote workspace. Keep real-resource names, locations, hashes and measurements out of Git and PR text.
- Reuse existing adapters, checksum checks and artifact publication. No general plugin, resolver, workflow or authentication framework.

**Goal:** Account existing producer reference-support counts without fabricating assignment mass.
**Architecture:** Add an opt-in aggregate-only mode with a distinct result profile; retain both legacy soft-mass modes. The package advertises a union result schema so registry dispatch remains unchanged.
**Spec:** docs/bridge_spec_v0.1/off_target_control_task_card.md; frozen profile and MeasurementResultV2 contracts.

### Task 1: Implement the count-only module path

**Files:** Module models.py, adapter.py, executor.py and narrowly shared binding checks in method_binding.py; tests/test_p0_05_hard_count_accounting.py; module README, cards/P0-05.md and the scientific task card. No method runtime, visualization or other-module implementation edits.

**Interfaces:** Add hard_count_accounting to ToolRequestV2. Required roles are product_case, product_definition_card, state_role_map, off_target_assessment_spec, cell_state_evidence_profile (v0.3/0.3.0), biological_unit_manifest and biological_unit_attestation_receipt; optional measurement_spec (v0.2). Other roles use their existing v0.1 contracts. No assets, parameters or evidence/method bundle fallback. Reuse existing product, selected-view, manifest, checksum and attestation ownership checks; these do not establish biological independence.

Add OffTargetHardCountProfileV1 (bridge://schemas/off-target-hard-count-profile/v0.1) and OffTargetControlResultV1 (bridge://schemas/off-target-control-result/v0.1), a RootModel union with existing OffTargetControlProfileV2. Existing schemas and legacy result payloads remain unchanged. Publish new schemas through the module PUBLIC_SCHEMA_MODELS map. Package version becomes 0.6.0; root owns discovery/spec wiring.

The new profile binds exact product/card/map/assessment/V3/manifest/receipt identities and hashes. Preserve the complete typed producer composition. Require canonical L1 selected-view count closure and producer reconciliation label/state consistency. Role counts account consensus_supported_only through the external StateRoleMap; all non-consensus reconciliation buckets remain separate. No source-specific double counting. Record four declared generic roles, each with strict nonnegative consensus_supported_count, count/N fraction, support_basis=consensus_supported_only and exclusion_state=cannot_exclude. The sum of role counts plus non-consensus reconciliation counts equals selected N. Single-source support is not unknown. Source conflict is unresolved. Zero consensus support does not establish absence.

Accounting has accounting_basis=producer_reference_support_counts, accounting_state=complete, mass_state=unavailable, total_soft_mass=null. Whole-view counting makes no per-unit or bootstrap estimate. Open-set assessment and rare detection remain not_assessed. Profile evidence_state=shadow; created_at derives from immutable ProductCase metadata (the producer V3 has no timestamp field). Use existing deterministic serialization, unchanged-input checks and artifact publication. No old soft-mass figures in this mode; visualizations=[].

An optional authorized MeasurementSpec must declare exactly four metrics. Produce MeasurementResultV2 artifacts: off_target_hard_count_accounting (inferred; raw_value is the complete typed accounting); off_target_soft_mass_composition, off_target_identity_unknown and off_target_rare_state_detection (unavailable; raw_value and all numeric fields null). All have source_execution_state=succeeded, exact run/provenance binding, no interval and no score. No spec means no measurement artifacts. P0-08 semantics are unchanged.

- [x] Write a failing module test using a minimal canonical V3 fixture. Check the closure directly:

```python
assert sum(r.consensus_supported_count for r in accounting.role_counts) + non_consensus_count == accounting.n_observations
assert accounting.total_soft_mass is None
assert accounting.mass_state == "unavailable"
```

- [x] Run the new test before implementation and retain RED evidence; implement only the specified count/profile/projection route.
- [x] Cover mixed support, all single-source, all conflict, zero-role counts, mismatched label/state/denominator/role, manifest/receipt/checksum drift, mixed-mode inputs and all four measurement semantics. Repeated runs must give matching content hashes. Keep unavailable measures visible to P0-08.
- [x] Run new tests plus existing P0-05 tests; preserve old Schema bytes and old runtime behavior. Document CLI/SDK role selection and a minimal logical request example without private paths/resources.
- [x] Self-review and commit only the module-owned files; report exact RED/GREEN evidence and remaining limitations.

### Task 2: Integrate, verify and review

**Files:** src/bridge/tool_packages/_input_contracts.py; src/bridge/toolkit/schemas.py; specs/p0_05.yaml; generated new schemas; plans/README.md; docs/decision-log.md and validation record. Integrator only.

- [x] Register the exact mode and union result URI; generate new Schema files without changing old schemas; validate Tool Card/spec versions.
- [x] Run focused module and shared-contract checks, 12-tool discovery, installed wheel smoke, repository policy and diff hygiene.
- [x] Independently review the complete diff and close both findings in a scoped fix review.
- [ ] Submit one Draft PR after final documentation and privacy checks. Do not claim genuine full-chain or scientific validation from deterministic fixture tests.

## Verification checkpoint

Implementation and shared integration are complete. The installed-wheel check at `f197a502` passed 186 module/shared-contract tests, 12-tool discovery, CLI describe/input-contract, knowledge and figure validation, repository policy and diff checks. The independent full-diff review requested a projection-Schema parity correction and a CLI documentation correction; both are implemented and the scoped re-review approved them with no new findings. Reproducible results and limits are in [the validation record](../docs/validation/p0_05_off_target_control.md#record-p0-05-hard-count-accounting-20260907).

GitHub CI and publication are separate pending gates. Genuine experimental-design confirmation, deployment binding and real-data Web integration remain follow-up work, not claims of this module change.
