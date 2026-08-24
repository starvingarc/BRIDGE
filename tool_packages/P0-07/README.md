# P0-07 Product Comparison & Stability

## Purpose

Produce a deterministic pairwise, preparation-level descriptive comparison
without embedding metric names, biological directions, assay choices or review
thresholds in executable code.

## Package contract

| Field | Value |
|---|---|
| Package version | `0.2.0` |
| Runtime state | `implemented` |
| Scientific state | `candidate` |
| EnvironmentSpec | `ENV-P0-CORE-v0.1` (`health_check_passed`) |
| Input envelope | `bridge://schemas/tool-request/v0.2` |
| Output envelope | `bridge://schemas/tool-run/v0.2` |
| Result schema | `bridge://schemas/comparison-record/v0.1` |
| Adapter | `bridge.tool_packages.p0_07_comparison.adapter:adapter` |

The CLI entry points are:

```bash
bridge-tool describe P0-07
bridge-tool validate --request request.json
bridge-tool run --request request.json
```

The Python SDK accepts the same `ToolRequestV2` through
`ToolRegistry.load_default().check_eligibility(request)` and `.run(request)`.

## Structured inputs

Every input is a canonical local JSON object with an absolute path, declared
role, Schema URI, object version, media type and SHA-256 checksum. Inline
scientific payloads, expression assets, free-form parameters and nonzero random
seeds are refused.

| Role | Schema | Required content |
|---|---|---|
| `comparison_spec` | `bridge://schemas/comparison-spec/v0.1` | Exactly one baseline and one candidate ProductCase; configurable equal-contract dimensions; mismatch policy; minimum independent preparations; metric IDs, units, eligible evidence states, required flags and direction policies. |
| `comparison_evidence_bundle` | `bridge://schemas/comparison-evidence-bundle/v0.1` | Exactly the same two ProductCases; versioned contract snapshots; P0-08 sufficiency state; preparation-level metric values, denominators, evidence states and Evidence references. |

The current input object version is `0.1.0` for both roles. Assay, target,
sampling, reference, prior, MeasurementSpec, algorithm and preprocessing are
versioned references supplied by the caller. The implementation contains no
allowed assay list, metric catalogue, biological program, favorable direction,
threshold or product identity.

## Output

One `ComparisonRecord` is written as `comparison_record.json` in an immutable,
content-addressed run directory. It contains:

- the ComparisonSpec and evidence-bundle references and role-level checksums;
- every configured contract-dimension equality check;
- baseline and candidate readiness summaries;
- per-metric eligible preparation count, mean, minimum and maximum;
- raw `candidate mean - baseline mean`, direction and input-configured interpretation;
- explicit comparability and result states, evidence references and reason codes;
- a `not_assessed` Pareto receipt, `overall_score=null` and `overall_rank=null`.

The output has no `MeasurementResult` or visualization. Missing, unknown or
unavailable metric values stay null and never become zero. A contextual
comparator may retain a descriptive raw delta, but a `not_comparable` pair does
not emit a delta.

## Eligibility, refusal and degradation

Top-level failures publish no result:

- missing, duplicate or unsupported input role;
- Schema, object-version or checksum mismatch;
- ComparisonSpec/ProductCase binding mismatch;
- expression assets, MeasurementSpec envelope parameters, free-form parameters
  or nonzero random seed;
- any non-null ScoreContract, because no score contract is frozen;
- unusable output path, input mutation or immutable-run collision;
- a V1 request, returned as typed `tool_request_v2_required`.

Contract-valid limitations degrade within the result:

- a configured contract mismatch becomes `contextual_comparator` or
  `not_comparable` according to the input policy;
- insufficient preparations or non-sufficient P0-08 evidence makes an otherwise
  available comparison `partial`;
- missing metric, unit mismatch or ineligible evidence state makes that metric
  `unavailable`;
- no available metric makes the record `not_assessed` with
  `score_state=unavailable`.

## Minimal example

See `examples/requests/p0_07_product_comparison.json`. The referenced objects
must exist at the declared absolute paths and match their checksums before
validation.

## Reproducibility and evidence boundary

The runtime is deterministic and CPU-only for this slice. Input paths and
caller-local input IDs are excluded from scientific identity; raw input
checksums, Schema URIs, object versions, tool version and environment remain
bound. Reusing the same content reuses the same run bytes.

Registered methods are the deterministic comparability gate and raw-metric
delta engine. The synthetic tests establish contract and packaging behavior,
not biological validity. P0-07 remains `candidate`; it performs no inferential
statistics, effect-size modelling, time-course modelling, integration,
stability inference, Pareto analysis, score, rank, clinical, safety, potency or
release decision.

## Detailed requirement

See `docs/bridge_spec_v0.1/product_comparison_stability_task_card.md` and
`docs/validation/p0_07_product_comparison_20260824.md`.
