# BRIDGE Visualization System

## Status and scope

| Item | Current state |
|---|---|
| Design direction | Approved on 2026-08-28 for large-screen and mobile portrait use |
| Scientific scope | Research-use cell-therapy product transcriptomic evidence |
| Current runtime | The integrated Web result experience and Visualization Composer are not implemented |
| Existing plots | P0-01 emits two QC plot families; P0-02 emits composition, reference-support, marker and conflict plot families |
| Scientific boundary | All active domains retain `domain_score=null`; candidate or shadow evidence is not a product grade, safety conclusion, potency claim or release decision |

This document is the approved user-facing visualization specification. It
consolidates the Web requirements already distributed across the scientific
task cards and defines the reading order, evidence semantics and implementation
sequence. It does not claim that the proposed Web views already exist.

## User questions and reading order

A researcher evaluating a differentiated cell product should not need to learn
the P0 package numbers. The result experience answers these questions in order:

1. Is the uploaded data usable for the requested analysis?
2. Which cells and cell states are present in the whole product?
3. How strongly do independent sources and methods support those identities?
4. Do the target lineage, regional identity and developmental state match the
   reviewed product definition?
5. Which off-target, unknown, rare, proliferation or stress signals require
   review?
6. If comparable products or batches exist, where do they differ and how stable
   are those differences?
7. Which conclusions are supported, conflicted or still missing evidence?
8. What should be measured or reviewed next?

The default product page follows the same order. Tool IDs, parameters, logs and
artifact details remain available through drill-down rather than defining the
page navigation.

## Product evidence overview

The first result view is a product evidence portrait with six rows:

- data readiness;
- cell composition and identity;
- target-lineage and regional support;
- developmental compatibility;
- off-target, unknown and rare-state evidence;
- proliferation and stress-response evidence.

Each row shows a text state, one key observation, its denominator, the number of
independent source families, the main limitation and a link to the underlying
evidence. It must not use a radar chart, total score, overall rank or
traffic-light pass/fail treatment. Missing or technically ineligible evidence is
shown as missing or unavailable, never as zero.

## Core figure inventory

| User question | Primary visual | On-demand detail | Producing evidence | Current implementation |
|---|---|---|---|---|
| Is the analysis usable? | Cell-flow and analysis-eligibility view from uploaded observations to QC-selected and downstream-eligible views | Per-sample/capture QC distributions; counts-genes and counts-mitochondrial diagnostics; QC-flag intersections; data-view sensitivity | Input Audit & QC (P0-01) | Partial: pooled distributions and counts-genes static plots exist |
| What is in the product? | Hierarchical L1/L2/L3 composition with explicit known, prediction-set, unknown/OOD and unresolved states | State-level table; optional embedding explorer; selected-view provenance | Cell-State Evidence (P0-02) | Partial: source-aware composition plots exist |
| Are the state labels supported? | Source-by-state evidence dot matrix | Method agreement, marker evidence, prediction-set coverage, calibration, OOD distributions, unknown reasons and sensitivity | Cell-State Evidence (P0-02) | Partial: reference, marker and conflict plots exist; open-set views are missing |
| Does the product contain the intended lineage and region? | Target, acceptable-adjacent, off-target and unresolved composition with intervals, paired with regional-support evidence | Reference correlation, program activity, continuous identity weights, residuals, method sensitivity and conditional spatial projection | Target Identity & Regional Fidelity (P0-03) | Not implemented as a formal visualization |
| Is the developmental state compatible with the reviewed window? | Whole-product and target-related developmental composition shown with separate denominators | Source/modality-faceted stage support, sample-level time course, program dynamics and calibration-only transition views | Developmental Compatibility (P0-04) | Not implemented as a formal visualization |
| Are off-target, unknown or rare states present? | Whole-product role composition and unknown-reason profile with intervals | Zero-observation upper bounds, rare-state LOD, spike-in recovery and multi-source OOD disagreement | Off-target Control (P0-05) | Not implemented as a formal visualization |
| Are proliferation, cell-cycle or stress signals present? | Sample-by-program evidence heatmap with reference envelope, gene coverage and evidence state | Whole-product/state-specific distributions, S/G2M evidence, method agreement, process timeline and review flags | Proliferation & Stress Response (P0-06) | Not implemented as a formal visualization |
| How do eligible products, batches or timepoints differ? | Per-metric raw-difference and effect-size forest plot | Composition deltas, program effects, preparation-level time courses, stability, confounding and sensitivity matrices | Product Comparison & Stability (P0-07) | Conditional and not implemented as a formal visualization |
| How much evidence supports each interpretation? | Domain-by-Data-Readiness/Model-Robustness/Prior-Applicability matrix | Single-domain gate trace, missing-requirement list and state-count summary | Evidence Sufficiency (P0-08) | Structured result exists; P0-08 intentionally emits no visualization |
| Why can or cannot a conclusion be stated? | Selected-claim directed evidence path from source to Evidence, Claim and Requirement | Conflicts, same-family dependencies, provenance and supporting table rows | Evidence Compiler & Reconciler (P0-09) | A bounded Cytoscape projection exists; it is not registered as a formal visualization |
| Can the report be used or shared? | Claim-verification table and public-export readiness summary | Exact blocked fields, wording findings, evidence refs and export manifest | Claim Verifier/Public-safe Export (P0-10/P0-11) | Structured receipts exist; P0-10 v0.1 does not verify figures |
| What happened after transplantation? | Separate graft composition, fetal-reference support and program-evidence views | Animal/graft/timepoint, fine subtype, method sensitivity and preparation-graft provenance | Optional Graft Assessment (P0-12) | Conditional and not implemented as a formal visualization |

Post-transplant views always remain separate from the pre-transplant product
portrait and cannot change a pre-transplant conclusion.

## Reading and interaction contract

Large-screen views use one dominant scientific figure, a compact navigation and
filter rail, and an evidence inspector. Mobile portrait views show one primary
figure at a time; filters become chips or a bottom sheet and evidence details
become a restorable bottom drawer.

Selecting a mark must expose:

- the exact value, numerator, denominator, unit and interval;
- evidence state and scientific status;
- data, reference, method, Card and environment versions;
- Evidence IDs and source-family dependencies;
- missing, conflict and applicability reasons;
- the bound table row or structured record;
- an Agent follow-up action scoped to the selected evidence.

Essential values and caveats remain visible without hover. Tap, focus and
keyboard selection provide equivalent access. URL state may contain public
selection, tab, filter and drill-down identifiers, but never private paths,
sample identifiers or raw payloads.

## Evidence and color semantics

Color supplements text, shape and pattern; it never carries status alone.

| Meaning | Visual role |
|---|---|
| Supported measured or source-consistent evidence | Muted teal with explicit state text |
| Conflict or review required | Amber with conflict symbol or outline |
| Unknown or OOD | Purple with explicit unknown/OOD label |
| Alert | Vermilion reserved for a documented review signal |
| Missing or unavailable | Cool gray; unavailable may use hatching |
| Context or unselected data | Neutral gray/navy |

`negative`, `missing`, `unknown`, `unavailable` and `alert` remain
distinct. An untriggered transcriptomic review flag is not displayed as a green
safety pass. Candidate, shadow and exploratory outputs carry a persistent text
badge in Web views and exports.

## Formal data binding

A formal figure must be generated from a typed, checksummed visualization data
artifact. The existing `VisualizationArtifact` is the current minimum runtime
object; the following requirements describe an additive future contract and
must not be inferred as implemented fields:

- component and component-version identifier;
- visualization-data Schema URI, object version and SHA-256;
- Evidence IDs and mark-to-record lookup keys;
- numerator, denominator, denominator scope, unit and interval semantics;
- evidence state, scientific status, missingness and applicability;
- ProductCase, ProductDefinitionCard, MeasurementSpec and selected DataView;
- reference, method, environment and source-family bindings;
- permitted filters, selections and drill-down state;
- static render, tabular fallback, alt text and long description;
- export profile and the exact data/configuration hash used by every renderer.

Scientific tools own measurements and scientific states. A Visualization
Composer owns view-specific transforms and renderer-neutral figure briefs. Web
code owns layout, selection and navigation but cannot recompute scientific
metrics. Static SVG/PDF/PNG and interactive Web views use the same bound data
and preserve the same claim and caveat.

No universal chart grammar is introduced before two real figure families need
the same interface. Standard tabular figures should prefer a declarative
renderer; bespoke SVG is reserved for direct labels and evidence annotations;
Canvas/WebGL is conditional on cell-level mark volume.

## Publication, accessibility and export

Formal exports follow a restrained scientific figure system:

- editable SVG/PDF for line art and text; PNG only as a raster derivative;
- consistent Arial/Helvetica-compatible typography and direct labels;
- color-blind-safe palette with no rainbow scale or red-green-only contrast;
- exact denominators, independent-unit counts and interval definitions;
- compact single- and double-column publication profiles in addition to Web;
- a machine-readable table and text alternative for every formal figure;
- deterministic fonts, ordering, dimensions and metadata for image regression.

Desktop and mobile screenshots must preserve the same scientific question,
state, caveat and source context. Dense matrices or evidence graphs may offer a
mobile landscape inspection mode, but the portrait view must still communicate
the primary conclusion without requiring rotation.

## Implementation sequence

Implementation proceeds one focused Pull Request at a time from the latest
`main`:

1. shared visualization data binding and figure registry;
2. Input Audit & QC visualizations;
3. Cell-State Evidence, prediction-set and OOD visualizations;
4. Evidence Sufficiency and selected-claim evidence-chain views;
5. Target/Regional, Developmental, Off-target and Proliferation/Stress packages,
   each in its own package-specific PR;
6. conditional Product Comparison and Graft views;
7. Web result-page integration consuming the registered components.

P0-02 continues on its existing scientific work line rather than creating a
second competing P0-02 branch. A package-specific visualization may merge as
candidate/shadow only when its evidence state is explicit. No visualization
promotes a scientific method, state or claim.

## Acceptance

A figure family is complete only when:

- its scientific question and default reading path are documented;
- the data artifact has a typed Schema, version and hash;
- missing, unknown, unavailable, conflict and alert fixtures are covered;
- every rendered mark can reach its structured record and Evidence ID;
- desktop, mobile, static export and tabular fallback preserve the same claim;
- semantic assertions and deterministic image/screenshot checks pass;
- private paths and identifiers do not enter URL state or public exports;
- an exact Git SHA is validated on the server;
- scientific and release claims remain within the producing tool's evidence.
