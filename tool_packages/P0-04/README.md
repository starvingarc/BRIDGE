# P0-04 Developmental Compatibility

## Purpose

Convert upstream Cell-State composition into a static developmental-window
profile without embedding a window, state assignment, fetal-age conversion or
product threshold in code.

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
| Result schema | `bridge://schemas/developmental-compatibility-result/v0.1` |
| Adapter | `bridge.tool_packages.p0_04_developmental.adapter:adapter` |

The Python SDK entry points are
`ToolRegistry.load_default().check_eligibility(request)` and `.run(request)`
with `ToolRequestV2`. CLI equivalents are:

```bash
bridge-tool validate --request /absolute/path/to/p0_04_request.json
bridge-tool run --request /absolute/path/to/p0_04_request.json
```

The documentation-only request example is
`examples/requests/p0_04_developmental_compatibility.json`.

## Biological configuration is input data

The implementation contains no cell-state name, marker program, developmental
window, allowed range, stage threshold, fetal-age conversion or product
pass/fail rule. `DevelopmentWindowSpec` supplies the versioned,
checksum-bound ProductDefinition and annotation-vocabulary context, selected
composition views, and each state's `earlier`, `within_window`, `later`,
`branch_shift` or `unresolved` role.

Draft, reviewed and frozen window objects may exercise the engineering path.
They cannot approve themselves, and every assessed P0-04 output remains
`shadow`.

## Structured inputs

P0-04 accepts exactly five immutable `application/json` objects:

| Role | Schema | Required content |
|---|---|---|
| `product_case` | `bridge://schemas/product-case/v0.1` | ProductDefinition, assay, preparation and MeasurementSpec binding |
| `product_definition_card` | `bridge://schemas/product-definition-card/v0.1` | Versioned product context |
| `development_window_spec` | `bridge://schemas/development-window-spec/v0.1` | Product/vocabulary-bound state roles and selected composition channels |
| `cell_state_evidence_profile` | `bridge://schemas/cell-state-evidence-profile/v0.1` | P0-02 composition and shadow evidence references |
| `qc_readiness_profile` | `bridge://schemas/qc-readiness-profile/v0.1` | P0-01 assay/readiness and evidence references |

Every `StructuredInputRef` has an absolute regular-file path, exact Schema URI,
object version and SHA-256 checksum. Expression assets, request parameters,
top-level MeasurementSpec parameters and nonzero random seeds are refused.

## Eligibility

The adapter verifies exact role cardinality, Schema/version/checksum bindings,
ProductCase/ProductDefinition/DevelopmentWindow identity, annotation
vocabulary, assay, MeasurementSpec, QC readiness and publication-safe evidence
and profile references. P0-02 `reconciliation_state` composition rows are
accepted as upstream diagnostics but excluded from developmental denominators.

Malformed or cross-bound inputs return a typed failed `ToolRunV2` with no
result or artifact. A complete contract with no selected composition returns
structured `not_assessed`.

## Deterministic calculation

For every selected composition view, source and label level, P0-04:

1. preserves the upstream denominator count and publication-safe `denominator_view`;
2. joins states only through the supplied DevelopmentWindowSpec;
3. reports five roles over the whole-product denominator;
4. separately reports the same roles over states marked `target_related`;
5. retains unmapped states and residual composition as unresolved;
6. marks explicitly requested but absent sources as partial.

No reference-stage model, trajectory, pseudotime or statistical inference is
silently substituted.

## Output

A successful or partial run publishes one immutable
`developmental_compatibility_result.json` containing:

- references and SHA-256 bindings for all five input roles;
- `analysis_mode=static_profile`;
- whole-product and target-related stage fractions with explicit denominator
  views;
- unmapped states and stable reason codes;
- reference-stage support as `not_assessed`;
- true-timepoint evidence as `unavailable`;
- `domain_score=null`.

No `MeasurementResult` or visualization is emitted in v0.2.0.

## Status semantics

- `complete`: all requested static channels exist and observed states are mapped.
- `partial`: usable composition exists but a source, mapping, residual or
  target-related denominator is unresolved.
- `not_assessed`: no requested composition channel exists.
- Assessed results use `score_state=shadow`; not-assessed results use
  `score_state=unavailable`.

Static compatibility does not convert an in-vitro day to GW/PCW and does not
establish dynamic progression, lineage fate or biological truth.

## Stable reason codes

Failure reasons include `tool_request_v2_required`,
`object_input_schema_mismatch`, `object_input_version_mismatch`,
`product_definition_binding_mismatch`,
`development_window_product_definition_mismatch`,
`annotation_vocabulary_binding_mismatch`,
`development_window_assay_not_supported`,
`measurement_spec_binding_mismatch`,
`qc_not_ready_for_developmental_evidence`,
`cell_state_composition_invalid`, `unsafe_evidence_reference`,
`output_path_invalid`, `existing_run_bundle_hash_mismatch` and
`structured_input_modified_during_run`.

Result reasons include `reference_stage_support_not_supplied`,
`true_timepoint_input_not_supplied`,
`requested_composition_channel_unavailable`,
`development_role_mapping_incomplete`,
`composition_residual_unresolved`,
`target_related_denominator_zero` and
`developmental_composition_not_assessed`.

## Minimal example behavior

For a 100-cell composition, the checksummed window may assign 30 cells earlier,
50 within-window and 20 later, while independently identifying which assigned
states form the target-related denominator. Changing any assignment produces a
new input checksum and run ID without a code edit.

## Validation boundary

The suite covers public Schema/Pydantic state parity, real P0-02 row shapes,
dual denominators, configurable assignments, missing sources, unmapped and
zero-denominator states, strict numeric inputs, deterministic reuse, input
immutability, output failures, V1 refusal, and source/installed-wheel CLI/SDK
execution.

Synthetic fixtures validate mechanics only. P0-04 does not validate a real
DevelopmentWindowSpec, fetal reference, time course, efficacy, safety, potency,
GMP release or product ranking.

## Detailed scientific requirement

Repository document:
`docs/bridge_spec_v0.1/developmental_compatibility_task_card.md`.
