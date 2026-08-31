# Visualization Data Contract

## Motivation

BRIDGE already emits static QC and cell-state figures, but the current
`VisualizationArtifact` only links a component name, one data artifact and
rendered files. A Web result page cannot yet verify the data version, recover a
record behind a mark, preserve missingness, or discover which figure components
are safe to show.

This work adds the smallest shared interface needed before individual figure
families are revised. It does not change biological measurements or their
scientific status.

## Scope

- Add a separately versioned visualization artifact that binds one typed,
  checksummed data object to one registered figure component.
- Record evidence states, scientific status, denominator and interval semantics,
  source context, allowed public interactions, static renders and accessible
  text/table fallbacks.
- Add a read-only figure registry for the existing P0-01 and P0-02 components.
  Existing components remain explicitly `legacy_untyped` until their own PR.
- Expose registry list, show and validation through the Python interface and
  `bridge-tool figures`.
- Generate and package the public JSON Schema from the Python model.

## Non-goals

- No new scientific figure, Web page, JavaScript renderer or visual redesign.
- No change to `VisualizationArtifact` v0.1, `ToolRun`, Tool IDs, measurements,
  thresholds, references, state names or `domain_score=null`.
- No migration of P0-01 or P0-02 runtime outputs in this branch.
- No private path, sample identifier, raw payload or persisted user selection.
- No generic chart grammar, ranking, total score, pass/fail state or claim
  promotion.

## Frozen interfaces

- Existing public v0.1 schemas remain byte-identical.
- Scientific tools own values, evidence states and provenance.
- The visualization layer may validate and present those facts but cannot
  recompute or upgrade them.
- Missing, unknown, unavailable, negative and alert remain distinct.
- Component status is inherited from the producing tool/run.

## Technical design

- Expected page shape: one main figure and two to six on-demand supporting
  figures; mobile portrait shows one main figure at a time.
- Data profile: immutable versioned JSON metadata that references, rather than
  embeds, the checksummed figure data.
- Renderer ownership: BRIDGE owns the data and component contracts; future Web
  code owns layout and rendering. No renderer dependency enters this package.
- Interaction state: only declared public selection, filter and drill-down IDs;
  URL encoding and persistence remain future Web responsibilities.
- Fallbacks: registered components declare desktop, mobile, static and table/text
  readiness; v0.2 artifacts require alt text, a long description and a table.
- Tests protect model invariants, missing-state semantics, registry uniqueness,
  schema packaging and CLI discovery rather than renderer internals.

## Prior art and boundaries

- [Vitessce](https://github.com/vitessce/vitessce) informed explicit view-config
  versioning and staged migration.
- [Vega-Lite](https://github.com/vega/vega-lite) informed accessible descriptions
  derived from declared data fields.
- [cellxgene](https://github.com/chanzuckerberg/cellxgene) informed typed data
  schemas that stay separate from the browser renderer.
- No dependency or source code from these projects enters BRIDGE in this branch.

## Implemented outcome

The shared contract is implemented and independently reviewed. The default
registry exposes seven existing P0-01/P0-02 figure IDs, all intentionally marked
`legacy_untyped`; no figure gained a new scientific status. Individual figure
families remain follow-up work, beginning with P0-01 in a separate PR.

## Validation

The implementation commit
`7ec8be8f4a8e2d231ed88c2be2f7b8279e7e09cf` passed:

- 65 focused contract, Schema, CLI and SDK tests;
- 1,371 complete repository tests with 20 existing unrelated warnings;
- repository policy, Tool Card parity and two deterministic Schema generations;
- 12-package discovery, figure-registry and knowledge validation;
- clean wheel build, fresh-environment installation and installed-wheel smoke;
- exact-commit GitHub Actions; and
- independent review with no remaining Critical or Important findings.

The exact wheel and server details are recorded in
[`docs/validation/visualization_data_contract_20260828.md`](../docs/validation/visualization_data_contract_20260828.md).

## Additive product-grouping requirement — 2026-08-31

The completed shared contract above is unchanged. Package-owned follow-up
artifacts must additionally distinguish four layers before rendering a
product-to-reference view:

1. the observed grouping produced after QC, normally an unsupervised cluster;
2. an optional user-provided label grouping whose original values and provenance
   remain unchanged; and
3. P0-02 cell-identity/reference evidence, aggregated from the same cell-level
   inference for either grouping; and
4. optional P0-03 anatomical-space and P0-04 developmental-stage axes, each with
   its own typed producer result, reference, method and scientific status.

The same product may be rendered by cluster or by user label. A user-label ×
cluster table exposes within-label heterogeneity through counts, row/column
fractions and declared summary statistics; this grouping overlap is not a
semantic `broader`/`narrower` crosswalk. P0-02 identity correspondence retains
the method's native value semantics: calibrated probability, prediction set,
mixture weight, similarity, distance or not assessed.

Each optional axis records its producer tool, Schema, reference, method,
`assessment_state`, `scientific_status` and reason. A missing typed producer
result renders as `not_assessed`; it is never inferred from another axis.
Renderers may not rename user labels, convert scores into probabilities, or
collapse the axes into a hard identity, fetal age, tissue coordinate or total
score.

These additive grouping and composer fields are conceptual next-version
requirements. The current P0-02 branch only defines a package-owned data Schema,
semantic validator, table fallback and deterministic renderer; it does not change
`ToolRun`, register a typed component or claim that the Web composer exists.
