# P0-06 proliferation and stress-response runtime

P0-06 packages precomputed proliferation, stress-response and related program
evidence into a deterministic candidate profile. It does not read expression
matrices or rerun scRNA-seq/snRNA-seq analysis.

## Entrypoints

Use `ToolRegistry.load_default().check_eligibility(request)` and
`.run(request)` with `ToolRequestV2`, or:

```bash
bridge-tool validate --request /absolute/path/to/request.json
bridge-tool run --request /absolute/path/to/request.json
```

Package version: `0.2.0`.

## Inputs

Exactly seven checksummed local JSON objects are required:

| Role | Schema | Purpose |
|---|---|---|
| `product_case` | `bridge://schemas/product-case/v0.1` | Product, assay, source unit and MeasurementSpec lineage |
| `product_definition_card` | `bridge://schemas/product-definition-card/v0.1` | Product definition and supported assay |
| `development_window_spec` | `bridge://schemas/development-window-spec/v0.1` | External versioned stage window |
| `program_spec` | `bridge://schemas/program-spec/v0.1` | External program, gene-set checksum, stage/state/scope, coverage/LOD and review rules |
| `cell_state_evidence_profile` | `bridge://schemas/cell-state-evidence-profile/v0.2` | Upstream state evidence and MeasurementSpec binding |
| `protocol_ir` | `bridge://schemas/protocol-ir/v0.1` | Process metadata completeness, batch confounding, replication and declared steps |
| `program_evidence_bundle` | `bridge://schemas/program-evidence-bundle/v0.1` | Precomputed whole-product/state-specific records and checksums of the other six inputs |

Every input requires the exact role, Schema URI and object version, an absolute
regular-file path, `application/json` and a lowercase SHA-256 checksum.
Expression assets, top-level MeasurementSpecs and arbitrary parameters are
refused.

The external `ProgramSpec` owns every program ID, gene-set reference and
checksum, allowed scope/state/stage/metric, gene-coverage threshold, LOD state,
review outcome and orthogonal follow-up reference. Python contains no program,
gene or threshold list.

## Deterministic evaluation

P0-06 binds all seven inputs to the same ProductCase and ProductDefinition. It
then evaluates each precomputed record in this order:

1. development-window and state applicability;
2. gene coverage against the external threshold;
3. LOD state against the external resolvable-state list;
4. review outcome through the external state-to-outcome map;
5. process attribution eligibility.

Missing process metadata, unresolved batch confounding or insufficient
replicate/comparison counts yield `cannot_attribute`. Counts required for
attribution are defined by the external ProgramSpec. No process step is
published as conditionally associated when attribution is unavailable.

Insufficient coverage produces `unavailable`; an unresolved LOD produces
`cannot_resolve`. A review rule that is not triggered produces
`not_detected_above_lod`, never a safety conclusion.

## Output

The result Schema is
`bridge://schemas/proliferation-stress-response-profile/v0.1`. It contains:

- checksum bindings for all seven inputs;
- whole-product and state-specific `ProgramEvidenceSummary` records;
- aligned `TranscriptomicReviewFlag` records;
- stage applicability, coverage, LOD and process-attribution states;
- typed reason codes and provenance-preserving evidence IDs.

The run publishes
`proliferation_stress_response_profile.json` and
`artifact_manifest.json`, both with SHA-256 checksums. Identical inputs reuse
byte-identical artifacts; input replacement or inconsistent existing output
fails closed.

The result always remains `descriptive_only`, `candidate/shadow`,
`domain_score=null` and `score_state=unavailable`.

## Boundary

A transcriptomic review flag requests orthogonal review; it is not evidence of
tumorigenicity, genomic abnormality, clinical risk or product failure. An
untriggered flag is not evidence of safety. P0-06 does not establish safety,
potency, efficacy, GMP release or product ranking and does not replace viability,
genomic or functional assays.
