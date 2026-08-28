# Data Readiness Visualization

This is the first user-question figure family in the approved visualization
roadmap: “Can this analysis be trusted?” It is produced by P0-01, but future
visualization PRs follow researcher questions rather than P0 numeric order.

## Researcher question

Can the uploaded observations support the requested analyses, and which technical
limitations still need review?

The figures explain input readiness. They do not grade the cell product, declare
a product safe, remove observations, or change any biological conclusion.

## Evidence lock

The visualization may use only facts already produced by P0-01:

- declared observation count and observation unit;
- input level, assay and matrix-semantics eligibility;
- count, detected-gene, mitochondrial, ribosomal and top-gene metrics;
- caller-declared capture grouping when it is complete;
- candidate QC flags and their exact intersections;
- availability of all-observation, candidate-flag and sensitivity views;
- evidence IDs, MeasurementSpec status, missing inputs and reason codes.

A candidate-eligible flag is not a filtered dataset. The current candidate H5AD
retains every observation and adds flags; every figure and caption must say so.
Missing mitochondrial genes, incomplete capture metadata or unavailable
count-level input remain `unavailable`, never zero.

## Figure family

| Component | Role | Analytical job | Default evidence |
|---|---|---|---|
| `bridge.qc.readiness-flow@0.1.0` | main | Composition/flow from declared observations to candidate flags and downstream view availability | counts and explicit unavailable states |
| `bridge.qc.overview@0.2.0` | supporting | Per-capture distributions of five QC metrics | median, interquartile range, observations and missingness |
| `bridge.qc.counts-genes@0.2.0` | supporting | Joint counts–genes and counts–mitochondrial relationships | per-observation values with candidate-review overlay |
| `bridge.qc.flag-intersections@0.1.0` | supporting | Exclusive intersections of candidate QC flags | exact counts and full declared denominator |

The two existing `@0.1.0` static components remain registered as
`legacy_untyped` for compatibility. The new components are additive
`typed_candidate` entries and inherit P0-01's `candidate` scientific status.

A data-view sensitivity figure is deferred because P0-01 does not yet receive
downstream results computed on multiple views. Availability may be shown in the
readiness flow, but no effect or stability result may be invented.

## Reading and visual contract

- Large screen: readiness flow first; distributions, relationships and flag
  intersections follow as supporting figures with direct labels.
- Mobile portrait: the main observation and readiness flow remain first; one
  supporting figure is shown at a time, with tap/focus selection and a table
  fallback. No essential value depends on hover.
- Static export: deterministic editable SVG is primary; PNG is a derivative.
  Desktop and mobile render profiles consume the same checksummed data.
- Color roles: neutral navy/gray for context, low-saturation teal for measured
  observations, amber for candidate review, vermilion only for defined alerts,
  and cool gray with pattern/text for unavailable evidence.
- Typography and marks: Arial/Helvetica-compatible text, direct labels, restrained
  axes, no rainbow scale, no traffic-light grade and no decorative background.
- Every figure states the denominator, candidate status, main limitation and
  source/evidence link. Tables preserve exact values and record lookup keys.

## Data and artifact contract

P0-01 will add one package-owned, versioned JSON data profile plus a versioned
set of `VisualizationArtifactV2` records. The profile references the existing
checksummed Parquet table rather than copying raw expression data. Each record
contains a public lookup key, value or numerator/denominator, unit, evidence
state, scientific status, missingness, applicability and Evidence IDs.

The structured-output index will discover both new JSON objects. Existing
`ToolRun` fields and `VisualizationArtifact` v0.1 records remain byte
compatible. URLs may contain only public selection/filter/drill-down IDs; no
local path, raw payload or private sample identifier is permitted.

## Prior art and implementation boundary

- [Scanpy's official QC workflow](https://scanpy.readthedocs.io/en/latest/tutorials/basics/clustering.html)
  motivates paired distributions and counts–genes/mitochondrial relationships,
  while warning that QC patterns can reflect biology and should not imply an
  automatic hard filter.
- [scater's official manual](https://bioconductor.org/packages/release/bioc/manuals/scater/man/scater.pdf)
  motivates per-cell metadata plots and log-scaled joint QC views.
- [UpSetPlot](https://upsetplot.readthedocs.io/en/latest/api.html) motivates the
  exclusive intersection representation for overlapping flags.

BRIDGE will implement a small deterministic Matplotlib renderer over its own
typed records. These projects are references only; no new plotting dependency or
copied source enters the wheel.

## Implementation tasks

1. Add P0-01 visualization data and artifact-set models and generate their public
   Schemas.
2. Extend the structured-output index without changing the existing required
   profile or optional lineage pair.
3. Emit explicit available/unavailable records for all input levels; emit
   per-observation and flag evidence only when count input is eligible.
4. Render desktop/mobile SVG and PNG plus deterministic TSV table fallbacks.
5. Register four typed candidates while retaining the two legacy component
   versions.
6. Add semantic, Schema, missing-state, traceability, deterministic-render and
   backward-compatibility tests.
7. Validate public real-data subsets and a multi-capture fixture on the server;
   record five repeated rendering times, median/range, CPU and peak memory.
8. Build and install the wheel from the exact server SHA, then complete the one
   Draft PR for this data-readiness figure family.

## Non-goals

- No Web page or JavaScript renderer.
- No new QC method, threshold, reference, sample name or biological-state name.
- No actual row filtering and no claim that candidate flags were reviewed.
- No doublet, ambient-RNA or downstream sensitivity figure without eligible
  method output.
- No product score, pass/fail, safety, potency, release or efficacy claim.
- No change to `domain_score=null`.

## Completion gates

The PR is complete only when the data Schemas and renders agree byte-for-byte
with their bound hashes; unavailable and partial fixtures remain explicit;
desktop, mobile, vector, raster and table forms preserve the same observation;
all marks trace to records and Evidence IDs; repeated renders are deterministic;
the complete repository and wheel gates pass on the server; and real-data
figures receive a visual and scientific-boundary review.
