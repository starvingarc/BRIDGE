# Visualization Data Contract

**Status:** implemented_awaiting_product_acceptance.
**Goal:** Present verified tool outputs as readable, source-bound figures without
changing scientific values or upgrading their status.

## Current implementation

The typed visualization contract, figure registry, CLI discovery and packaged
schemas are implemented. At the 2026-09-24 review, the registry contained 43
components: 36 typed candidates and seven legacy-untyped components. The current
registry contains 46 components: 39 typed candidates and seven legacy-untyped. The earlier
seven-component-only implementation is a historical validation snapshot, not the
current registry. Inspect the live registry through `bridge-tool figures`.

Existing Web result components display tool figures, candidate composition,
reference similarity and method-specific tables. Component registration and
successful builds do not establish complete figure-family or real-user acceptance.

## Remaining acceptance

- [ ] Check each applicable PRD question against its actual typed/checksummed data
  and rendered output, including units, denominators, uncertainty and missingness.
- [ ] Verify the result-to-evidence drill-down, readable source labels and
  table/text fallback with saved real results, reusing existing renderers.
- [ ] Account for unsupported figure families and exploratory program displays;
  a product-bound figure cannot be populated with invented biological units.
- [ ] Check the same facts and limitations in the Web view and applicable static
  report; keep missing values distinct from zero and candidate status explicit.

This work is coordinated with [single-product acceptance](step7-evidence-coordinator.md),
not a separate redesign. No total score, ranking, pass/fail promotion or new
scientific measurement is introduced.

Requirements: [PRD visualization](../docs/BRIDGE_PRD.md#66-visualization-composer-与-web-交互).
Historical contract evidence: [versioned validation](../docs/validation/visualization_data_contract_20260828.md).
Implementation: [visualization contracts and registry](../src/bridge/toolkit/visualization.py),
[Web figures](../frontend/src/components/ResearchFigures.tsx).

## Linked spatial display

[Product UMAP and spatial-reference linking design](../docs/superpowers/specs/2026-10-02-product-spatial-link-design.md) defines the implemented linked result view. Engineering and controlled internal-display checks are recorded in [display verification](../docs/validation/product-spatial-link.md); remaining biological-review and registration gates are tracked in [Product Spatial Linking](product-spatial-link.md). Existing figure-family acceptance above remains open.
