# P0-05 Off-target Control

## Purpose

Convert full-product Cell-State composition into product-relative target,
adjacent, known-off-target, unresolved and unknown evidence without embedding
any state identity, role, threshold or harm decision in code.

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
| Result schema | `bridge://schemas/off-target-control-result/v0.1` |
| Adapter | `bridge.tool_packages.p0_05_off_target.adapter:adapter` |

Python SDK entry points are
`ToolRegistry.load_default().check_eligibility(request)` and `.run(request)`
with `ToolRequestV2`. CLI equivalents are:

```bash
bridge-tool validate --request /absolute/path/to/p0_05_request.json
bridge-tool run --request /absolute/path/to/p0_05_request.json
```

The documentation-only example is
`examples/requests/p0_05_off_target_control.json`.

## Biological configuration is input data

`OffTargetRoleSpec` supplies the ProductDefinition and annotation vocabulary,
required denominator view, selected composition channels and per-state role.
Roles are `target`, `acceptable_adjacent`, `known_off_target`,
`role_unresolved` or `unknown`. Known off-target assignments also carry an
evidence class and interpretation direction; unknown assignments carry an
unknown reason.

The package contains no cell-state name, marker, product-role table, OOD rule,
rare-state limit, tolerated proportion or pass/fail threshold. Changing any
decision requires a new input object and checksum, not an implementation edit.

## Structured inputs

P0-05 accepts exactly six immutable JSON objects:

| Role | Schema | Required content |
|---|---|---|
| `product_case` | `bridge://schemas/product-case/v0.1` | ProductDefinition, assay, preparation and MeasurementSpec binding |
| `product_definition_card` | `bridge://schemas/product-definition-card/v0.1` | Versioned product context |
| `state_role_map` | `bridge://schemas/state-role-map/v0.1` | Exact ProductDefinition-owned state vocabulary and role authority |
| `off_target_role_spec` | `bridge://schemas/off-target-role-spec/v0.1` | Product/vocabulary-bound roles and denominator selection |
| `cell_state_evidence_profile` | `bridge://schemas/cell-state-evidence-profile/v0.1` | P0-02 composition and evidence references |
| `qc_readiness_profile` | `bridge://schemas/qc-readiness-profile/v0.1` | P0-01 assay/readiness and evidence references |

Each `StructuredInputRef` declares an absolute regular-file path, Schema URI,
object version, media type and SHA-256 checksum. Expression assets, request
parameters, top-level MeasurementSpec parameters and nonzero seeds are refused.

## Deterministic calculation

For every selected view, source and label level, P0-05:

1. accepts only the configured, publication-safe full-product `denominator_view`;
2. joins states only through `OffTargetRoleSpec`;
3. reports counts and fractions for all five roles;
4. retains per-state role/evidence metadata for drill-down;
5. maps unconfigured identities to `role_unresolved`, never to target or known
   off-target;
6. preserves residual composition and missing requested sources as partial.

P0-02 reconciliation-state rows are accepted upstream diagnostics but excluded
from role-composition denominators.

## Output

One immutable `off_target_control_result.json` contains input references and
checksums, role-resolved composition with denominator views, per-state
breakdown, unmapped states, stable reason codes and evidence references.
`domain_score` is always null. No MeasurementResult or visualization is emitted.

OOD calibration and rare-state detection are explicitly `not_assessed` in this
first callable version because no calibrated inputs are supplied. Zero observed
cells is therefore never converted into biological absence or a detection
claim.

## Status and refusal semantics

- `complete`: every requested static channel exists and every observed state is
  configured.
- `partial`: usable composition exists but a channel, mapping or residual is
  unresolved.
- `not_assessed`: no requested full-product composition channel exists.
- Assessed results remain `shadow`; not-assessed results are `unavailable`.

Eligibility checks exact role/Schema/version/checksum cardinality,
ProductDefinition, StateRoleMap, vocabulary, exact P0-01 QC-selected
`DataViewBinding`, assay, MeasurementSpec, QC readiness and publication-safe
references. Failures return a typed run with no result or artifact. Stable
reasons include `tool_request_v2_required`,
`object_input_schema_mismatch`, `product_definition_binding_mismatch`,
`off_target_role_spec_product_definition_mismatch`,
`annotation_vocabulary_binding_mismatch`,
`qc_not_ready_for_off_target_evidence`, `cell_state_composition_invalid`,
`unsafe_evidence_reference`, `output_path_invalid` and
`structured_input_modified_during_run`.

Result reasons include `ood_calibration_not_supplied`,
`rare_state_calibration_not_supplied`,
`requested_full_product_channel_unavailable`,
`product_role_mapping_incomplete`,
`composition_residual_role_unresolved` and
`off_target_composition_not_assessed`.

## Validation boundary

Tests cover Schema/Pydantic parity, real P0-02 row shapes, configured roles,
unknown/unresolved separation, denominator binding, missing sources, strict
numeric inputs, deterministic reuse, input immutability, output failures, V1
refusal and source/installed-wheel SDK execution.

Synthetic fixtures validate mechanics only. P0-05 does not validate a real
role map, OOD detector, rare-state LOD, adverse effect, safety, efficacy,
potency, release decision or product ranking.

## Detailed scientific requirement

Repository document: `docs/bridge_spec_v0.1/off_target_control_task_card.md`.
