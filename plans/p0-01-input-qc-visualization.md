# Input Data Quality and Analysis Eligibility Figures

This is the first figure family in the approved visualization roadmap. It is
organized around a user's need to determine whether the submitted input meets
the technical conditions of the requested analyses, but that navigation prompt
is not used as a figure title. It is produced by P0-01; future visualization PRs
follow researcher needs rather than P0 numeric order.

## Analytical scope

Can the uploaded observations support the requested analyses, and which technical
limitations still need review?

The figure-family title is **Input Data Quality and Analysis Eligibility**. The
figures report defined technical measurements and availability states; they do
not grade the cell product, establish the reliability of every downstream
analysis, declare a product safe, remove observations, or change a biological
conclusion.

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
| `bridge.qc.readiness-flow@0.1.0` | main | **Observation retention and analysis eligibility**: declared observations, validated structure/matrix semantics, candidate eligibility and downstream-view availability | counts and explicit unavailable states |
| `bridge.qc.overview@0.2.0` | supporting | **Quality-metric distributions by capture**: five measured QC variables shown separately for every complete caller-declared capture | median, interquartile range, observations and missingness |
| `bridge.qc.counts_genes@0.2.0` | supporting | **Library complexity and mitochondrial transcript fraction**: joint counts–genes and counts–mitochondrial relationships | per-observation values with candidate-review overlay |
| `bridge.qc.flag-intersections@0.1.0` | supporting | **QC-flag combinations and observation counts**: exclusive intersections of candidate QC flags | exact counts and full declared denominator |

The two existing `@0.1.0` static components remain registered as
`legacy_untyped` for compatibility. The new components are additive
`typed_candidate` entries and inherit P0-01's `candidate` scientific status.

A data-view sensitivity figure is deferred because P0-01 does not yet receive
downstream results computed on multiple views. Availability may be shown in the
readiness flow, but no effect or stability result may be invented.

## Analysis-figure contract

- Each component must work as a self-contained scientific figure with a clear
  question, one immediate observation and direct labels; P0 IDs and method names
  stay in notes or evidence details rather than leading the title.
- No figure title may ask whether the complete analysis is “trustworthy”; titles
  must name the measured variables, comparison unit and technical scope.
- Deterministic editable SVG is primary; PNG is a raster derivative, and a
  machine-readable table preserves every plotted value and lookup key.
- Color roles: neutral navy/gray for context, low-saturation teal for measured
  observations, amber for candidate review, vermilion only for defined alerts,
  and cool gray with pattern/text for unavailable evidence.
- Typography and marks: Arial/Helvetica-compatible text, direct labels, restrained
  axes, no rainbow scale, no traffic-light grade and no decorative background.
- Every figure states the denominator, candidate status, main limitation and
  source/evidence link without relying on hover or an interactive interface.
- The registry declares only `static_export` and `table` support in this PR.
  Web layout, mobile adaptation, interaction and renderer work are deferred.

## Data and artifact contract

P0-01 will add one package-owned, versioned JSON data profile plus a versioned
set of `VisualizationArtifactV2` records. The profile references the existing
checksummed Parquet table rather than copying raw expression data. Each record
contains a public lookup key, value or numerator/denominator, unit, evidence
state, scientific status, missingness, applicability and Evidence IDs.

The structured-output index will discover both new JSON objects. Existing
`ToolRun` fields and `VisualizationArtifact` v0.1 records remain byte
compatible. No public artifact may contain a local path, raw payload or private sample
identifier. Interaction lists remain empty until the later Web implementation.

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
4. Render deterministic publication SVG and PNG plus TSV table fallbacks.
5. Register four typed candidates while retaining the two legacy component
   versions.
6. Add semantic, Schema, missing-state, traceability, deterministic-render and
   backward-compatibility tests.
7. Validate public real-data subsets and a multi-capture fixture on the server;
   record five repeated rendering times, median/range, CPU and peak memory.
8. Build and install the wheel from the exact server SHA, then complete the one
   Draft PR for this data-readiness figure family.

## Implementation and validation status

The figure implementation is active on Draft PR #62. The processed
fetal-midbrain object and GSE204796 have verified deterministic rendering,
raw-unit semantics, public-identifier suppression and compressed candidate-view
storage. GSE204796 remains a supplemental engineering stress test.

Formal product-facing validation now starts from inputs that match the P0-01
contract rather than from the processed BRIDGE v1 objects:

| Dataset | Formal input | Current action |
|---|---|---|
| MacroDiff | Six cell-called raw-count captures combined without cell filtering; 78,542 cells | Run the complete multi-capture figure family and inspect capture/timepoint presentation |
| Studer-protocol D16 | Original filtered 10x-style MTX; 11,087 cells | Run the complete single-capture figure family and inspect metadata/missing-state behavior |
| SphereDiff | Upstream counts are controlled under `HRA008865`; exact local mapping unresolved | Keep the 9,547-cell v1 object as an `analysis_ready` historical control and render `count_ready` as unavailable |

The v1 MacroDiff 57,464-cell and Studer 9,046-cell objects are exact downstream
subsets of the upstream matrices. They may be used for historical comparison,
but not as the simulated user upload. Piao et al. 2021 supports the published
MSK-DA01 protocol context; it is not used to assert that the local Studer files
are the paper data.

Local working objects remain server-only and public figure artifacts must
suppress sample identifiers and paths. Independent PR review and merge
authorization remain; Web integration is still outside this plan.

## Non-goals

- No Web page, responsive/mobile layout, interaction design or JavaScript renderer.
- No new QC method, threshold, reference, sample name or biological-state name.
- No actual row filtering and no claim that candidate flags were reviewed.
- No doublet, ambient-RNA or downstream sensitivity figure without eligible
  method output.
- No product score, pass/fail, safety, potency, release or efficacy claim.
- No change to `domain_score=null`.

## Completion gates

The PR is complete only when the data Schemas and renders agree byte-for-byte
with their bound hashes; unavailable and partial fixtures remain explicit;
vector, raster and table forms preserve the same observation;
all marks trace to records and Evidence IDs; repeated renders are deterministic;
the complete repository and wheel gates pass on the server; and real-data
figures receive a visual and scientific-boundary review.
