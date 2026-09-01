# P0-03 Target and Regional Visualization

## Biological goal

Show how a submitted cell product relates to its declared target roles and named
regional reference states without turning reference similarity into a cell-identity
probability or a spatial coordinate.

## Scope

- Add one typed product-composition view that preserves the whole-product
  denominator and, where applicable, the target-related denominator.
- Add one source-, assay- and evidence-scope-separated reference-support view.
- Preserve unresolved, unknown, OOD, unavailable and draft-review states.
- Publish deterministic JSON, TSV, SVG, PNG and PDF artifacts from one typed
  data object.
- Register both figure components and package their public Schemas.

## Non-goals

- No fetal-tissue coordinate projection, developmental-age estimate, product
  score, ranking, potency, efficacy, safety or release claim.
- No change to Tool IDs, ToolRequest, ToolRun, existing measurement names or
  the `domain_score=null` boundary.
- No embedded state names, product thresholds or reference assets.
- No Web UI implementation.

## Frozen interfaces

The existing P0-03 result and measurement Schemas remain unchanged. Product roles,
regional state sets and references remain external checksummed inputs. Observation
counts do not become biological replicates, and no composition interval is inferred
without independent product or preparation units.

## Implementation

- Package-owned visualization-data and artifact-set Schemas.
- One product record collection used by both role summaries and named state rows.
- Explicit applicability and reason codes when reference support is absent or
  only partially available.
- Figure-registry entries, deterministic renderer configuration and exact table
  fallbacks.
- Runtime guards that keep target and regional numerator scopes biologically
  coherent.

## Validation

The branch must pass the complete repository suite, package discovery, knowledge
validation, repository policy, deterministic Schema generation, wheel installation
and deterministic rendering before review.
