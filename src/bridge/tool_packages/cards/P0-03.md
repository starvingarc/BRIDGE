# P0-03 Target Identity & Regional Fidelity

## Purpose

Convert upstream cell-state composition into product-relative target-identity
and regional-fidelity evidence without embedding a biological role table in
code.

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
`ToolRegistry.load_default().check_eligibility(request)` and
`.run(request)` with `ToolRequestV2`. The CLI equivalents are:

```bash
bridge-tool validate --request /absolute/path/to/p0_03_request.json
bridge-tool run --request /absolute/path/to/p0_03_request.json
```

The committed example is documentation-only and contains placeholder absolute
paths and checksums:
`examples/requests/p0_03_target_regional_evidence.json`.

## Biological configuration is input data

P0-03 contains no cell-state name, marker list, target assignment, regional
assignment, threshold or product pass/fail rule. The biological interpretation
is supplied by a versioned, checksummed `StateRoleMap`. A changed decision is a
new input-object version and checksum; it does not require a code change.

The assessment mechanics are separately supplied by a versioned
`TargetRegionalAssessmentSpec`. It selects which upstream composition views
and label levels to read, which lineage roles form the regional denominator and
which regional roles count as configured target-region support. Missing state
assignments are reported as unresolved and are never guessed or replaced by
zero.

Draft, reviewed and frozen configuration objects can all be processed for
engineering integration. They do not change this package's `candidate`
scientific state, and all assessed outputs remain `shadow`.

## Structured inputs

P0-03 accepts exactly seven immutable `application/json` objects. Each
`StructuredInputRef` requires a unique input ID, absolute regular-file path,
matching Schema URI and object version, and exact lowercase SHA-256 checksum.

| Role | Schema | Required content |
|---|---|---|
| `product_case` | `bridge://schemas/product-case/v0.1` | ProductCase, assay, ProductDefinition and MeasurementSpec bindings |
| `product_definition_card` | `bridge://schemas/product-definition-card/v0.1` | Versioned product context and exact StateRoleMap reference |
| `state_role_map` | `bridge://schemas/state-role-map/v0.1` | Per-state lineage and regional roles, bound to the upstream annotation vocabulary |
| `target_regional_assessment_spec` | `bridge://schemas/target-regional-assessment-spec/v0.1` | ProductDefinition-bound composition views, label levels and denominator mechanics |
| `cell_state_evidence_profile` | `bridge://schemas/cell-state-evidence-profile/v0.1` | P0-02 composition records and shadow evidence references |
| `qc_readiness_profile` | `bridge://schemas/qc-readiness-profile/v0.1` | P0-01 assay/readiness and evidence references |
| `biological_unit_manifest` | `bridge://schemas/biological-unit-manifest/v0.1` | Exact analysis-unit assignments, independence groups, scope and review state bound by the ProductCase |

Expression assets, top-level MeasurementSpec parameters, arbitrary request
parameters and additional object roles are refused. The module does not rerun
cell annotation or read an H5AD file.

## Binding and eligibility

Before execution, the adapter verifies:

1. all seven roles, Schemas, object versions and checksums;
2. ProductCase to ProductDefinitionCard binding;
3. ProductDefinitionCard to StateRoleMap binding in both directions;
4. assessment-spec to ProductDefinitionCard and StateRoleMap to annotation-vocabulary binding;
5. ProductCase, QC and Cell-State assay agreement;
6. ProductCase MeasurementSpec identity and exact P0-01 QC-selected
   `DataViewBinding` lineage against the P0-02 profile;
7. ProductCase biological-unit manifest reference, checksum, scope and unit/group memberships exactly match the supplied manifest;
8. QC readiness is not blocked, not assessed or not applicable;
9. every upstream composition row has a coherent nonnegative count,
   denominator and fraction, and its configured denominator label contains no
   machine-local path or credential-like content;
10. evidence IDs use the `evidence:` namespace, while upstream profiles use
   `cell-state-profile:` and `qc-profile:` respectively;
11. the deterministic request uses the fixed zero random-seed value and a usable output directory.

A failed envelope or cross-binding returns a typed failed `ToolRunV2` with no
result or artifacts. A complete contract with no requested composition channel
returns a successful structured `not_assessed` result, not a fabricated
measurement.

## Deterministic calculation

For every requested composition view, source and label level, the executor:

1. reads P0-02 counts and their original denominator;
2. joins each state to the supplied StateRoleMap;
3. sums lineage roles over the whole-product denominator;
4. builds the regional denominator from the lineage roles named by the
   assessment spec;
5. sums regional roles within that denominator;
6. reports configured target-region support over the whole-product denominator;
7. preserves unmapped states and unassigned composition residuals as unresolved.

The engine never infers a role from a state ID or display name. It has no
default biological mapping and no hidden fallback.

## Output

A successful or partial run publishes one immutable
`target_regional_evidence_result.json` artifact. Its
`TargetRegionalEvidenceResult` contains:

- ProductCase, ProductDefinitionCard, StateRoleMap, assessment-spec, P0-02 and
  QC references;
- SHA-256 bindings for all seven input roles without caller-local input IDs or
  paths;
- target-identity channels with role numerator, denominator view, denominator and fraction;
- regional-fidelity channels with the original denominator view, explicit target-related denominator and
  whole-product target-region fraction;
- every unmapped upstream state and stable reason code;
- a spatial profile fixed to `not_assessed` with
  `spatial_projection_not_supplied`.

Configured denominator wording remains scientifically flexible, but cannot
carry local paths, home-directory forms, file URIs or credential assignments
into the published JSON artifact.

No `MeasurementResult` or visualization is emitted in v0.2.0. Spatial
projection, uncertainty intervals and method/reference sensitivity remain
future independent evidence channels.

## Status and score semantics

- `result_state=complete`: requested composition channels were available and
  every observed state was mapped.
- `result_state=partial`: usable channels were produced, but a requested
  channel, state mapping, residual or regional denominator remained unresolved.
- `result_state=not_assessed`: no requested composition channel was available.
- Assessed results have `score_state=shadow`; not-assessed results have
  `score_state=unavailable`.
- `domain_score` is always `null`.

A zero target-related denominator is not evidence of product safety or failure.
It makes the regional fraction unavailable and produces the reason
`target_related_denominator_zero`.

## Stable reason codes

Envelope and binding failures include:

- `tool_request_v2_required`
- `tool_version_mismatch`
- `exactly_one_<role>_required`
- `unsupported_object_input_role`
- `object_input_schema_mismatch`
- `object_input_version_mismatch`
- `product_definition_binding_mismatch`
- `state_role_map_binding_mismatch`
- `state_role_map_product_definition_mismatch`
- `assessment_spec_product_definition_mismatch`
- `annotation_vocabulary_binding_mismatch`
- `product_case_assay_not_supported`
- `cell_state_profile_assay_mismatch`
- `qc_profile_assay_mismatch`
- `measurement_spec_binding_mismatch`
- `qc_not_ready_for_target_regional_evidence`
- `cell_state_composition_invalid`
- `unsafe_evidence_reference`
- `unsafe_profile_reference`
- `p0_03_random_seed_forbidden`
- `output_path_invalid`
- `existing_run_bundle_hash_mismatch`
- `structured_input_modified_during_run`

Result-level reasons include:

- `spatial_projection_not_supplied`
- `requested_composition_channel_unavailable`
- `state_role_mapping_incomplete`
- `composition_residual_unresolved`
- `target_related_denominator_zero`
- `cell_state_composition_not_assessed`

## Example behavior

With a 100-cell upstream composition and a supplied role map assigning 60 cells
to `target`, 20 to `acceptable_adjacent` and 20 to `not_target`, the
target channel reports exactly those counts and fractions. Regional values are
then calculated only from the lineage roles explicitly named in the assessment
spec. Changing a state assignment changes the checksummed input and run ID but
does not change the implementation.

## Validation boundary

The committed suite must cover public Schema/Pydantic parity, six-role
cross-binding, deterministic reuse, caller input-ID independence, missing and
unmapped states, zero denominators, strict numeric semantics, input
immutability, output-path failures, V1 refusal, wheel-installed CLI/SDK smoke
and privacy checks.

Synthetic fixtures demonstrate execution mechanics only. They do not validate
a biological role assignment, a regional conclusion, efficacy, safety,
potency, GMP release or product ranking. Before any formal scientific use, the
StateRoleMap, upstream Cell-State evidence, method/reference sensitivity and
benchmark must be independently reviewed and frozen.

## Detailed scientific requirement

Repository document:
`docs/bridge_spec_v0.1/target_regional_identity_task_card.md`.
