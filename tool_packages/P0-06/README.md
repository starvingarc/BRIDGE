# P0-06 Proliferation & Stress Response

## Purpose

Assemble caller-supplied, stage-bound transcriptomic program observations into
deterministic reference relations and shadow review signals without embedding
program names, genes, reference ranges, coverage limits or biological decisions
in code.

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
| Result schema | `bridge://schemas/proliferation-stress-response-profile/v0.1` |
| Adapter | `bridge.tool_packages.p0_06_proliferation_stress.adapter:adapter` |

Python SDK entry points are
`ToolRegistry.load_default().check_eligibility(request)` and `.run(request)`
with `ToolRequestV2`. CLI equivalents are:

```bash
bridge-tool validate --request /absolute/path/to/p0_06_request.json
bridge-tool run --request /absolute/path/to/p0_06_request.json
```

The documentation-only example is
`examples/requests/p0_06_proliferation_stress_response.json`.

## Biological configuration is input data

`ProgramAssessmentSpec` supplies every program reference, stage context,
analysis scope, assay applicability, metric and unit, reference interval,
minimum gene coverage, eligible evidence states, biological-unit
requirement, review direction and orthogonal follow-up reference.

`ProgramEvidenceBundle` supplies the corresponding observed values, coverage,
method, Evidence Family, biological analysis unit and evidence state. The package
contains no program ID, gene, signature, cell-state name, stage window,
reference envelope, numerical threshold or pass/fail table. Changing a
biological interpretation requires a new object version and checksum, not a
code edit.

## Structured inputs

P0-06 accepts exactly seven immutable JSON objects:

| Role | Schema | Required content |
|---|---|---|
| `product_case` | `bridge://schemas/product-case/v0.1` | ProductDefinition, assay, preparation and MeasurementSpec binding |
| `product_definition_card` | `bridge://schemas/product-definition-card/v0.1` | Versioned product context |
| `program_assessment_spec` | `bridge://schemas/program-assessment-spec/v0.1` | Caller-supplied program rules and stage-bound reference intervals |
| `program_evidence_bundle` | `bridge://schemas/program-evidence-bundle/v0.1` | Precomputed program observations and evidence provenance |
| `developmental_compatibility_result` | `bridge://schemas/developmental-compatibility-result/v0.1` | P0-04 product, window and Cell-State context |
| `qc_readiness_profile` | `bridge://schemas/qc-readiness-profile/v0.1` | P0-01 assay/readiness and evidence references |
| `biological_unit_manifest` | `bridge://schemas/biological-unit-manifest/v0.1` | Exact ProductCase-bound analysis units, independence groups, scope and externally reviewed/frozen lineage state |

Each `StructuredInputRef` declares an absolute regular-file path, Schema URI,
object version, media type and SHA-256 checksum. Raw expression assets,
request-level MeasurementSpec parameters, arbitrary parameters and nonzero
random seeds are refused. Program scoring stays behind separately versioned
upstream methods; this package does not open H5AD or recompute expression.

## Input field semantics

Each review rule has a unique `rule_id`, versioned `program_ref`, whole-product
or state-specific scope, exact P0-04 `stage_context_ref`, assay list,
`metric_name`, publication-safe `unit`, inclusive reference bounds, coverage requirement,
eligible evidence states, minimum biological-unit count, review direction
and optional follow-up assay references.

Each observation has a unique `observation_id`, matching rule/program,
analysis-unit reference, Evidence Family, method reference, explicit metric,
unit, analysis scope, state and stage context, evidence state, raw value, gene
coverage and evidence references.
`missing`, `unknown` and `unavailable` carry null numeric fields. Numeric
strings, booleans, NaN and infinity are refused rather than coerced.

## Deterministic calculation

For every configured rule, P0-06:

1. checks ProductCase, ProductDefinition, P0-04 window, Cell-State profile,
   assay and QC bindings;
2. requires each observation's metric, unit, scope, state and stage context to
   match its rule exactly, then compares the supplied value with the supplied
   inclusive reference interval;
3. excludes observations with ineligible evidence states or insufficient
   configured gene coverage without replacing them with zero;
4. aggregates repeated analysis units inside the exact manifest-defined
   independence group, so captures, aliquots, methods or Evidence Families
   from one biological source do not become independent votes;
5. emits a shadow `transcriptomic_review_flag` only when the manifest lineage
   is externally `reviewed` or `frozen` and the configured direction is
   supported by the configured minimum number of non-conflicting groups;
6. otherwise returns `cannot_resolve` or `not_assessed` with stable reasons.

`declared` lineage remains valid provenance but contributes zero independent
groups and yields `cannot_resolve`; P0-06 cannot review its own lineage. An
unconfigured rule ID or mismatched program reference is retained as an
unmatched record and makes the run partial; it never enters a configured
program result.

## Output

One immutable `proliferation_stress_response_profile.json` contains:

- all seven versioned input references and role-specific checksums;
- per-rule raw values, gene coverage, reference relation, inclusion and reason;
- distinct included and triggering biological-unit counts;
- one aligned `TranscriptomicReviewFlag` record per rule;
- unmatched observation metadata and evidence references;
- explicit deferred process-attribution, residual-pluripotency LOD and
  transcriptomic-CNV channels.

`domain_score` is always null. No `MeasurementResult` or visualization is
emitted. The result never reassigns cell identity, recomputes composition or
converts absence of a flag into evidence of safety.

## Status and refusal semantics

- `complete`: every configured rule has assessable evidence and no unmatched
  observation.
- `partial`: at least one rule is assessable, while another rule or observation
  remains unresolved.
- `not_assessed`: no configured rule has assessable evidence.
- Assessed results remain `shadow`; not-assessed results are `unavailable`.

Eligibility failures publish nothing. Stable reasons include
`tool_request_v2_required`, `object_input_schema_mismatch`,
`product_definition_binding_mismatch`,
`program_spec_product_definition_mismatch`,
`development_window_binding_mismatch`,
`program_rule_stage_context_mismatch`,
`program_evidence_developmental_result_mismatch`,
`program_evidence_cell_state_profile_mismatch`,
`qc_not_ready_for_program_evidence`, `output_path_invalid` and
`structured_input_modified_during_run`.

Result reasons include `configured_review_condition_met`,
`independence_group_evidence_insufficient`,
`gene_coverage_below_configured_minimum`,
`program_evidence_not_eligible`, `validated_lod_not_supplied`,
`developmental_context_not_assessed`, `unmatched_program_observations`,
`protocol_ir_not_supplied`, `pluripotency_lod_not_supplied` and
`transcriptomic_cnv_not_supplied`.

## Validation boundary

Tests cover public Schema validity, strict numeric inputs, rule-only biological
changes, reference comparison, independence-group de-duplication, low coverage,
missing evidence, unavailable developmental context, unmatched observations,
cross-object bindings, deterministic reuse, immutable inputs, output failures,
V1 refusal and source/installed-wheel SDK execution.

Synthetic fixtures validate mechanics only. P0-06 does not validate a real
ProgramSpec, scorer, reference envelope, biological threshold, detection limit,
process attribution, genomic abnormality, tumorigenicity, safety, potency,
release decision or product ranking.

## Detailed scientific requirement

Repository document:
`docs/bridge_spec_v0.1/proliferation_stress_response_task_card.md`.
