# P0-07 Product Comparison & Stability

This directory contains the deterministic comparability, descriptive-delta and
selected comparison-method runtime.

## Interface at a glance

- **Legacy comparison:** a checksummed ComparisonStabilitySpec,
  ComparisonCaseManifest and two to twenty product-evidence bundles.
- **Method runtime:** the same objects plus a candidate ComparisonMethodSpec and
  typed ComparisonMethodInput series. Numeric methods run only after the shared
  comparability and source-evidence gates pass.
- **Output:** `ProductComparisonStabilityProfile` with comparability state, raw
  summaries and deltas; method mode also writes `ComparisonMethodBundle` with
  Hedges g, Jensen-Shannon distance, Spearman correlation, one-dimensional
  Wasserstein distance and ratio-scale within-group dispersion when eligible.
- **Visualization output:** typed comparison data, exact TSV fallbacks and
  deterministic SVG/PNG/PDF views for comparability, **Declared analysis-unit values
  and descriptive group differences**, and method-specific evidence. Observed ranges are descriptive, raw deltas have
  no interval, and each method remains on its own scale.
- **Boundary:** it does not fill missing values, rerun upstream analyses, select a
  winner, declare equivalence, compute inferential significance or emit a score.

## Documentation

- [Implementation, software and calls](../../../../docs/tool-packages.md#p0-07)
- [Tool Card — authoritative runtime contract](../cards/P0-07.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/product_comparison_stability_task_card.md)
- [Legacy comparison request](../../../../examples/requests/p0_07_product_comparison_stability.json)
- [Method-runtime request](../../../../examples/requests/p0_07_comparison_method_runtime.json)
- [Validation index](../../../../docs/validation/)

Use `bridge-tool describe P0-07` and `bridge-tool input-contract P0-07` for the
installed version, input modes, schemas, environment and registered method IDs.
