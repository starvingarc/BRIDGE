# P0-07 Product Comparison & Stability

This directory contains the deterministic comparability and descriptive-delta
package.

## Interface at a glance

- **Input:** a checksummed ComparisonStabilitySpec, ComparisonCaseManifest and two
  to twenty precomputed product-evidence bundles.
- **Output:** `ProductComparisonStabilityProfile` with comparability state, raw
  summaries and comparator-minus-baseline descriptive deltas and ranges.
- **Boundary:** it does not fill missing values, rerun upstream analyses, select a
  winner, declare equivalence or emit a score.

## Documentation

- [Tool Card — authoritative runtime contract](../cards/P0-07.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/product_comparison_stability_task_card.md)
- [Request example](../../../../examples/requests/p0_07_product_comparison_stability.json)
- [Validation record](../../../../docs/validation/p0_07_product_comparison_stability_v0.2.md)

Use `bridge-tool describe P0-07` for the installed version, schemas, environment
and registered method IDs.
