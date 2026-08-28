# Visualization Data Contract

## Motivation

BRIDGE already emits static QC and cell-state figures, but the current
`VisualizationArtifact` only links a component name, one data artifact and
rendered files. A Web result page cannot yet verify the data version, recover a
record behind a mark, preserve missingness, or discover which figure components
are safe to show.

This branch adds the smallest shared interface needed before individual figure
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

## Validation

Before review, this branch must pass the complete server test suite, repository
policy, generated-Schema parity, figure-registry validation, wheel build/install
smoke, private-information scan and a clean Git/GitHub SHA check.
