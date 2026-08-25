# P0-12 graft assessment runtime

P0-12 is an optional, deterministic handoff tool. It records whether graft
evidence was supplied and, when supplied, aggregates already computed records
under a caller-supplied versioned contract. It never runs single-cell analysis
or changes pretransplant evidence.

## Entrypoints

Use `ToolRegistry.load_default().check_eligibility(request)` and
`.run(request)` with `ToolRequestV2`, or:

```bash
bridge-tool validate --request /absolute/path/to/request.json
bridge-tool run --request /absolute/path/to/request.json
```

Package version: `0.2.0`.

## Inputs

Two shapes are valid:

1. `object_inputs=[]`: graft was not provided.
2. Exactly one checksummed local JSON object for each role below.

| Role | Public Schema | Key fields |
|---|---|---|
| `graft_case` | `bridge://schemas/graft-case/v0.1` | `graft_case_id`, assay/specimen IDs, optional animal/timepoint/replicate and preparation linkage, confounders, provenance |
| `assessment_spec` | `bridge://schemas/graft-assessment-spec/v0.1` | role rules, allowed metric IDs and states, state classes, registered methods, provenance |
| `evidence_bundle` | `bridge://schemas/graft-evidence-bundle/v0.1` | exact case/spec refs and precomputed records with source-run and provenance refs |

Every `StructuredInputRef` requires the exact role, Schema URI,
`object_version=0.1.0`, `application/json`, absolute regular-file path and
SHA-256 checksum. Expression assets, top-level MeasurementSpecs and arbitrary
parameters are rejected.

The assessment spec is the only owner of role, metric and state vocabulary.
P0-12 checks each record against it, but does not interpret or recompute its
biology.

## Output

`bridge://schemas/graft-assessment-result/v0.1` has two successful states:

| State | Meaning |
|---|---|
| `not_provided` | No object inputs; graft evidence is unavailable and pretransplant evidence is unchanged |
| `candidate` | Three inputs were bound and aggregated as `descriptive_only`, `shadow` evidence |

A provided result contains three checksum bindings, per-role record/metric/state
summaries, externally declared state-class counts, missing metadata, confounders,
missing required roles and optional explicit preparation linkage.
`domain_score=null`, `score_state=unavailable` and
`pretransplant_evidence_effect=none` are fixed.

The run publishes:

- `graft_assessment_result.json`;
- `artifact_manifest.json`.

Both are returned with SHA-256 checksums. Identical inputs reuse byte-identical
artifacts. Input replacement or an inconsistent existing bundle fails closed.

## Missing and refusal behavior

Missing animal ID, post-transplant timepoint or biological replicate produces
`graft_metadata_incomplete` and remains descriptive. Missing explicit
preparation linkage produces `provided_unlinked`; no linkage is inferred from
paths, filenames or labels. Declared confounders and missing required roles are
reported, not converted into zero.

Malformed JSON, checksum/version/Schema mismatch, partial role sets, method
drift, case/spec cross-binding drift and records outside the external spec
return a failed run with typed reason codes and no artifacts.

## Boundary

This is a candidate/shadow packaging implementation. It does not establish
biological truth, efficacy, safety, potency, maturation, clinical outcome, GMP
release or product rank. It does not validate the upstream algorithms that
created the evidence bundle.
