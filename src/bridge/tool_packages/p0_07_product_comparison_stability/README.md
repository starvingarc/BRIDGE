# P0-07 Product Comparison & Stability

This module validates externally declared comparison contracts and computes only
deterministic descriptive summaries from checksummed, precomputed evidence. The
adapter entry is `adapter:adapter`; the result model is
`ProductComparisonStabilityProfile`.

Biological direction, thresholds, comparability policy and confounders remain in
the external `ComparisonStabilitySpec`. The code never reruns upstream analysis,
fills missing values, ranks products, or emits a score.

## Interface

Use `bridge-tool describe P0-07`, then pass a `ToolRequestV2` JSON document to
`bridge-tool validate --request <path>` or `bridge-tool run --request <path>`.
The Python SDK exposes the same request through `ToolRegistry`.

The request must contain checksummed, immutable JSON objects with these roles:

- one `comparison_stability_spec`;
- one `comparison_case_manifest`;
- two to twenty `product_evidence_bundle` objects.

Each evidence bundle represents one independent ProductCase/preparation and
binds its ProductDefinition, metric contract, unit, denominator, data view,
timepoint, batch/protocol/lab/cell-line metadata, provenance and optional P0-08
sufficiency summary. Paths must be absolute, `media_type` must be
`application/json`, and every object version is `0.1.0`.

The single published JSON artifact follows
`bridge://schemas/product-comparison-stability-profile/v0.1`. It contains
comparability status, group-level raw summaries, comparator-minus-baseline
deltas, neutral numeric direction, preparation/batch stability, confounding
flags, reason codes, provenance and input checksums. A minimal assessed contrast
looks like:

```json
{
  "comparison_eligibility": "strictly_comparable",
  "comparison_mode": "descriptive_only",
  "profile_state": "partial",
  "metric_contrasts": [
    {
      "contrast_state": "shadow",
      "delta_comparator_minus_baseline": 0.08,
      "direction": "increase",
      "interval_state": "descriptive_only"
    }
  ],
  "overall_score": null,
  "overall_rank": null,
  "domain_score": null,
  "score_state": "unavailable"
}
```

This fragment illustrates semantics, not a complete Schema-valid result. The
request shape is in
`examples/requests/p0_07_product_comparison_stability.json`; placeholder paths
and checksums must be replaced before validation.

## Conservative outcomes

Malformed envelopes, missing checksums, Schema/version errors and cross-object
binding failures are technical refusals and publish no result. Contract-valid
missing, unknown or unavailable metric evidence produces null summaries and
deltas, never zero. Required comparability mismatches yield `not_comparable`;
complete configured confounding yields `not_estimable`; reference/OOD groups are
descriptive only. The package is `candidate`, all evidence remains `shadow`, and
it cannot declare a winner, equivalence, safety, efficacy or release readiness.
