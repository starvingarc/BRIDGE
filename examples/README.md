# Interface Examples

The request files document the JSON shape shared by the Python SDK and
`bridge-tool` CLI. Absolute paths, output directories and SHA-256 values are
placeholders unless stated otherwise; replace them with immutable local objects
before calling `validate` or `run`.

| Tool | Request example | What it demonstrates |
|---|---|---|
| P0-01 | [`p0_01_count_ready.json`](requests/p0_01_count_ready.json) | Count-level H5AD/10x input audit and QC |
| P0-01 | [`p0_01_analysis_ready.json`](requests/p0_01_analysis_ready.json) | Structure-only audit of normalized expression |
| P0-02 | [`p0_02_cell_state.json`](requests/p0_02_cell_state.json) | Shadow Cell-State Evidence request and deployment-resolved reference/QC bindings |
| P0-03 | [`p0_03_target_regional_evidence.json`](requests/p0_03_target_regional_evidence.json) | Eleven-object target/regional evidence request |
| P0-04 | [`p0_04_developmental_compatibility.json`](requests/p0_04_developmental_compatibility.json) | Traceable aggregation plus optional expression-method request |
| P0-05 | [`p0_05_off_target_control.json`](requests/p0_05_off_target_control.json) | Nine-object method-runtime request for whole-product composition, uncertainty, rare-state and OOD coordination |
| P0-03 | [`p0_03_target_regional_expression.json`](requests/p0_03_target_regional_expression.json) | Optional H5AD expression-method request |
| P0-03 | [`p0_03_target_regional_method_spec.json`](objects/p0_03_target_regional_method_spec.json) | External method, reference, program and coverage choices |
| P0-06 | [`p0_06_process_method_runtime.json`](requests/p0_06_process_method_runtime.json) | Exact DataView H5AD, external program/state/unit contracts, caller biological-unit attestation and required gate-facing MeasurementSpec; normalized expression or raw counts are accepted |
| P0-06 | [`p0_06_proliferation_stress_response.json`](requests/p0_06_proliferation_stress_response.json) | External program, process and precomputed-evidence request |
| P0-07 | [`p0_07_product_comparison_stability.json`](requests/p0_07_product_comparison_stability.json) | Multi-case comparability and descriptive-delta request |
| P0-07 | [`p0_07_comparison_method_runtime.json`](requests/p0_07_comparison_method_runtime.json) | Candidate descriptive-method runtime with typed numeric series |
| P0-08 | [`p0_08_evidence_sufficiency.json`](requests/p0_08_evidence_sufficiency.json) | Versioned evidence-gate request |
| P0-09 | [`p0_09_evidence_compiler.json`](requests/p0_09_evidence_compiler.json) | Compilation bundle and evidence-registry request |
| P0-10 | [`p0_10_claim_verifier.json`](requests/p0_10_claim_verifier.json) | Four-object structured claim-verification request |
| P0-11 | [`p0_11_public_safe_export.json`](requests/p0_11_public_safe_export.json) | Four-object allowlisted local-export request |
| P0-11 | [`p0_11_public_artifact_audit.json`](requests/p0_11_public_artifact_audit.json) | Two-object JSON/Markdown/CSV/SVG audit request |
| P0-12 | [`p0_12_graft_assessment.json`](requests/p0_12_graft_assessment.json), [`p0_12_expression_analysis.json`](requests/p0_12_expression_analysis.json) | Optional no-graft request and five-object, one-declared-graft H5AD analysis request |

For the P0-12 expression request, the referenced `GraftCase` must declare one
graft, animal and post-transplant timepoint, and every H5AD observation must
carry that exact graft ID. The reference panel must declare
`profile_aggregation=sample_pseudobulk` for raw counts or
`sample_mean_log_expression` for log-normalized input. Multiple sample IDs are
treated as technical samples only.

The P0-04 [method-spec example](objects/p0_04_development_method_spec.json)
shows how reference-stage roles, program cards and method selection stay
outside executable code. Ordered sampling-point labels may be supplied
separately; they are not treated as continuous experimental time.

See the [Tool Package guide](../docs/tool-packages.md) for each tool's purpose,
inputs, outputs, refusal behavior, Tool Card, scientific task card and validation
record.

## Agent Integration Profiles

The profiles declare logical resource ownership and step bindings without
embedding data, runtime paths, checksums, asset identifiers or deployment
catalogs.

| Profile | Coverage | Intended endpoint |
|---|---|---|
| [Single product](agent-integration/profiles/single-product.json) | P0-01–P0-06 and P0-08–P0-11 | Local candidate export |
| [Comparison](agent-integration/profiles/comparison.json) | P0-07 `method_runtime` | Descriptive comparison |
| [Graft](agent-integration/profiles/graft.json) | P0-12 `not_provided` and `expression_analysis` | Independent graft result |

Validate a profile against the installed 12-tool registry:

```bash
python examples/agent-integration/reference_runner.py \
  validate-profile \
  --profile examples/agent-integration/profiles/single-product.json
```

Run one binding only after the Agent has materialized the exact request:

```bash
python examples/agent-integration/reference_runner.py \
  run-step \
  --profile examples/agent-integration/profiles/single-product.json \
  --binding claim-verifier \
  --request <materialized-request.json>
```

The runner validates and dispatches existing requests; it does not resolve
resources or construct scientific objects. See
[Agent Integration](../docs/agent-integration.md) for the ownership and failure
boundaries.

## Synthetic scRNA Upload Demo

`demo-data/scrna-upload-v0.1/` mimics files a user may upload for Agent
integration testing. The expression values, cells, samples, captures, batches,
preparations and timepoint are fully synthetic. Public human gene symbols are
used only as feature identifiers.

| File | Purpose | SHA-256 |
|---|---|---|
| `demo-data/scrna-upload-v0.1/demo_scrna.h5ad` | 2,048-cell by 10,000-gene object with log-normalized `X`, integer `layers/counts` and synthetic `obs` metadata | `984f74f7a4118da1c898e593a0d93b536aee092bcda5dbf76d10fc65addd5a91` |
| `demo-data/scrna-upload-v0.1/sample_metadata.csv` | Four-row capture-level companion metadata | `81c15f855da1c83ee58d0a5711d5afe1d0e52c78362f514604864d5aa194c93a` |

- Source class: `fully_synthetic`.
- Intended tests: upload handling, metadata hand-off and Agent integration.
- Not validated here: P0 execution, biological state recovery, scoring or any
  scientific, product-quality or clinical interpretation.
