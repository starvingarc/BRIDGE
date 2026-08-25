# P0-03 Target Identity & Regional Fidelity

## Purpose

Convert an upstream P0-02 composition into deterministic, product-relative
lineage and regional evidence. The implementation aggregates counts only; every
state-to-role decision and every requested denominator/numerator set comes from
versioned, checksummed input objects.

## Contract

| Field | Value |
|---|---|
| Package version | `0.2.0` |
| Runtime state | `implemented` |
| Scientific state | `candidate` |
| Optional | `no` |
| EnvironmentSpec | `ENV-P0-CORE-v0.1` (`health_check_passed`) |
| Input envelope | `bridge://schemas/tool-request/v0.2` |
| Output envelope | `bridge://schemas/tool-run/v0.2` |
| Result schema | `bridge://schemas/target-regional-evidence-result/v0.1` |
| Adapter | `bridge.tool_packages.p0_03_target_regional.adapter:adapter` |

The Python SDK entry points are
`ToolRegistry.load_default().check_eligibility(request)` and `.run(request)`
with `ToolRequestV2`. The CLI equivalents are:

```bash
bridge-tool validate --request /absolute/path/to/p0_03_request.json
bridge-tool run --request /absolute/path/to/p0_03_request.json
```

The documentation-only example is
`examples/requests/p0_03_target_regional_evidence.json`; replace every
placeholder absolute path and SHA-256 checksum before use.

## Request envelope

P0-03 accepts exactly nine immutable `application/json` objects. Every
`StructuredInputRef` requires a unique `input_id`, an absolute regular-file
`path`, the exact role and Schema URI below, an object version, and the lowercase
SHA-256 of the file bytes.

| Role | Schema | Object-version rule | Required meaning |
|---|---|---|---|
| `product_case` | `bridge://schemas/product-case/v0.1` | `0.1.0` | One ProductCase, one sample/preparation source, ProductDefinition, MeasurementSpec, manifest and independence bindings |
| `product_definition_card` | `bridge://schemas/product-definition-card/v0.1` | `0.1.0` | Product context, supported assay and exact StateRoleMap reference |
| `state_role_map` | `bridge://schemas/state-role-map/v0.1` | `0.1.0` | External state-to-lineage/regional assignments bound to the P0-02 vocabulary |
| `target_regional_assessment_spec` | `bridge://schemas/target-regional-assessment-spec/v0.1` | `0.1.0` | Requested views, label levels, sources and configurable aggregation role sets |
| `measurement_spec` | `bridge://schemas/measurement-spec/v0.2` | must equal payload `version` | Assay, analysis unit, independence group and raw-metric definition |
| `cell_state_evidence_profile` | `bridge://schemas/cell-state-evidence-profile/v0.2` | `0.2.0` | P0-02 composition plus exact QC, MeasurementSpec and data-view lineage |
| `qc_readiness_profile` | `bridge://schemas/qc-readiness-profile/v0.2` | `0.2.0` | P0-01 readiness and selected data-view lineage |
| `biological_unit_manifest` | `bridge://schemas/biological-unit-manifest/v0.1` | `0.1.0` | Analysis units, independence groups, observation set and assignment-artifact checksum |
| `biological_unit_assignment` | `bridge://schemas/biological-unit-assignment/v0.1` | `0.1.0` | Observation-to-analysis-unit and observation-to-independence-group rows |

`assets`, top-level `measurement_spec_ref`, arbitrary `parameters`, and nonzero
`random_seed` are refused. P0-03 does not read expression matrices, rerun cell
annotation, perform spatial projection, or accept an old v0.1 QC/Cell-State
profile as a compatibility shortcut.

The assignment artifact is not used to choose a biological role. It closes the
observed-cell-to-analysis-unit lineage: its observation set, data view,
hierarchy, group membership and checksum must agree with the manifest and both
upstream profiles. Its checksum is preserved in the result so count evidence
cannot be detached from the declared experimental unit.

## Externally configurable biology

No cell-state ID, display name, marker list, target assignment, regional
assignment, pass threshold, or product-specific role set is embedded in code.
A new biological decision requires a new `StateRoleMap` or
`TargetRegionalAssessmentSpec` version and checksum, not an executor change.

The executable constraints are semantic safety and arithmetic only:

- `target_region` cannot contradict a non-target lineage;
- `acceptable_adjacent_region` requires target-related lineage;
- `source_specific` is requested if and only if nonempty `source_ids` are
  supplied; unrequested levels and sources are not silently evaluated;
- `unresolved` lineage cannot enter the configured regional denominator and
  `unresolved` regional role cannot enter the configured whole-product
  numerator;
- upstream `unknown`, `ood`, `unresolved`, and `unresolved_labels` always remain
  unresolved and cannot be promoted by the role map;
- explicit unresolved assignments and unassigned residual counts force a
  `partial` result and are never normalized away or filled with zero.

Other lineage and regional role selections remain fully configurable. This is
why a nondefault, checksummed assessment spec can deliberately aggregate a
different role set while the implementation remains unchanged.

## Eligibility and fail-closed binding

Before execution, the adapter validates:

1. all nine roles, Schema URIs, versions, regular files and byte checksums;
2. ProductCase, ProductDefinitionCard, StateRoleMap and assessment-spec identity;
3. assay and MeasurementSpec identity/applicability across ProductCase, P0-01
   and P0-02;
4. the exact QC-selected `DataViewBinding`, observation count and denominator
   lineage consumed by P0-02;
5. the manifest ref, checksum, source scope, analysis-unit kind, independence
   kind and complete group set;
6. the assignment artifact's checksum, data view, observation IDs, row count,
   hierarchy, used analysis units and used independence groups;
7. P0-01 readiness and coherent P0-02 composition state;
8. publication-safe profile/evidence namespaces and denominator labels; and
9. a usable output directory and unchanged inputs throughout the run.

A top-level, Schema, version, checksum, binding or path failure returns a typed
failed `ToolRunV2` with no result and no artifact. A complete contract with no
requested composition channel returns a successful structured `not_assessed`
result instead of a zero.

Representative envelope/binding reason codes include
`tool_request_v2_required`, `exactly_one_<role>_required`,
`unsupported_object_input_role`, `object_input_schema_mismatch`,
`object_input_version_mismatch`, `structured_input_checksum_mismatch`,
`measurement_spec_binding_mismatch`,
`measurement_spec_profile_binding_mismatch`,
`measurement_spec_biological_unit_mismatch`,
`biological_unit_manifest_checksum_mismatch`,
`biological_unit_assignment_checksum_mismatch`,
`biological_unit_assignment_observation_set_mismatch`,
`biological_unit_assignment_group_mismatch`,
`cell_state_denominator_view_mismatch`,
`cell_state_composition_state_conflict`,
`qc_not_ready_for_target_regional_evidence`,
`unsafe_evidence_reference`, `output_dir_not_regular_directory`,
`output_run_id_invalid`, and `structured_input_modified_during_run`.

## Deterministic calculation

For each explicitly requested `(composition_view, source_id, label_level)`
channel, P0-03:

1. verifies one shared positive denominator and denominator label;
2. sends upstream unresolved/OOD/unknown rows directly to the lineage
   `unresolved` bucket;
3. joins the remaining state IDs to the checksummed StateRoleMap;
4. emits all lineage role numerators over the whole channel denominator;
5. forms the regional denominator from the lineage roles selected by the
   assessment spec;
6. emits all regional role numerators over that target-related denominator;
7. emits the configured regional-role numerator over the whole denominator; and
8. records unmapped states and residual counts without imputation.

Every target channel conserves its denominator. Every regional role numerator
sums to the target-related denominator; that denominator cannot exceed the
whole denominator, and the whole-product numerator cannot exceed its
denominator. These are contract checks, not biological thresholds.

## Output interface

A successful or partial run publishes exactly one immutable
`target_regional_evidence_result.json` through an atomic single-file publisher.
Reusing the same deterministic run and identical bytes is idempotent. A
conflicting existing directory, extra file, symlink/non-regular target, changed
payload, input mutation, or failed byte verification is refused; historical
output is not overwritten.

`TargetRegionalEvidenceResult` contains:

- ProductCase, ProductDefinition, StateRoleMap, assessment, MeasurementSpec,
  P0-02, P0-01 and BiologicalUnitManifest references;
- SHA-256 bindings for all nine inputs, including the assignment artifact;
- the distinct upstream composition state (`shadow`, `not_assessed`,
  `unavailable`, `unknown`, or `missing`);
- target-identity channels with view/source/level, denominator wording, whole
  denominator and every lineage role fraction;
- regional-fidelity channels with the whole denominator, configured
  target-related denominator, every regional role fraction and configured
  whole-product regional fraction;
- typed unmapped-state records, evidence references and stable reason codes;
- a spatial profile fixed to `not_assessed` with
  `spatial_projection_not_supplied`.

No `MeasurementResult`, visualization or score is emitted. `domain_score` is
always `null`.

## Result-state semantics

| State | Meaning | Score state |
|---|---|---|
| `complete` | every requested channel exists, all counts are mapped and conserved, and no residual/zero regional denominator remains | `shadow` |
| `partial` | usable channels exist but a requested channel, upstream/explicit unknown, unmapped state, residual or regional denominator is unresolved | `shadow` |
| `not_assessed` | no requested channel is available | `unavailable` |

Result reasons include `requested_composition_channel_unavailable`,
`state_role_mapping_incomplete`, `composition_residual_unresolved`,
`target_related_denominator_zero`, `cell_state_composition_<state>`,
`cell_state_composition_not_assessed`, and
`spatial_projection_not_supplied`. Missing, unknown, unavailable, negative and
shadow evidence remain distinct; zero is never substituted for missingness.

## Validation and interpretation boundary

Tests cover the nine-object spine, single-source ProductCase binding,
observation/analysis/independence-unit drift, v0.1-profile refusal, configurable
role sets, source/level selection, unknown/OOD non-promotion, arithmetic
conservation, deterministic identity, checksum/input immutability, atomic
publication conflicts, Schema/card parity, CLI/SDK and clean-wheel use.

Synthetic fixtures prove only engineering behavior. `candidate`, `complete` and
`shadow` do not validate a real StateRoleMap, reference applicability, target or
regional biology, efficacy, safety, potency, clinical benefit, GMP release or
product ranking. Formal use still requires independent biological review,
benchmarking and a separately frozen release/score contract.

## Detailed scientific requirement

Repository document:
`docs/bridge_spec_v0.1/target_regional_identity_task_card.md`.
