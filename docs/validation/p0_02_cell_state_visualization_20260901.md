# P0-02 cell-state evidence visualization validation — 2026-09-01

## Scope

This change adds a package-owned data contract, semantic validator, deterministic
renderer and lossless TSV fallback for a source-by-state evidence matrix. It
does not register a new runtime figure, change `ToolRequest`, `ToolRun`, Tool
IDs, state names or `domain_score=null`.

The main matrix keeps identity evidence and dependency structure explicit.
Primary and derived scRNA contexts are not counted as independent votes.
External sources remain `not_assessed` until their held-out analyses are run.
The hEB58 spatial object is kept outside the identity-support matrix and is
limited to working-label / figure QA and candidate label-program lookup.

## Server display checks

Three previously analysed differentiation datasets were re-read from their
analysis objects to test whether the same figure grammar works across distinct
numbers of observations, clusters and pre-existing labels.

| Display case | Retained observations | Clusters | Pre-existing analysis-object labels | Input boundary |
|---|---:|---:|---:|---|
| Studer-protocol D16 | 9,046 | 21 | 10 | Retained barcodes trace to the registered count-ready capture; this does not establish publication or product provenance |
| SphereDiff D28 | 9,547 | 5 | 5 | Historical analysis-ready object; a formal count-ready source was not available |
| MacroDiff D14/D21/D28 | 57,464 | 23 | 10 | Retained barcodes trace to six registered captures; captures are not assumed to be independent biological replicates |

Each case passed observation, cluster, label, cross-tabulation, stored-embedding,
marker-panel and spatial-reference integrity checks. The transparent candidate
lookup used 47 shared genes for Studer and 48 for SphereDiff and MacroDiff; the
spatial label-program view used 18 shared genes in all three cases. These are
display-grammar checks, not classifier validation.

Two complete export-and-render runs produced 54/54 byte-identical non-runtime
artifacts. Runtime manifests separately bind the analysis object, reference
RDS, the R aggregation script, the shared reference profile, the case-specific
shared-gene subset and the final artifacts by SHA-256. The 385,361 hEB58
segmented profiles retain 20 working labels from two sections of one embryo;
no product cell-to-location mapping is reported.

## Repository validation

| Gate | Result |
|---|---|
| Focused P0-02 visualization contract and rendering tests | `15 passed` |
| Complete repository suite | `1395 passed, 20 warnings` |
| Repository policy and diff hygiene | passed |
| Knowledge snapshot | valid; 354 methods; 396 bindings |
| Tool discovery | 12 callable Tool Packages |
| Figure registry | valid; 11 components; unchanged runtime registration |
| Generated Schema determinism | passed; SHA-256 `94df321b9d87ce6d92692fe676e7b5e0d5fdf10c117e75fc4cb0fbef6a569c43` |
| Independent scientific and contract review | no remaining Critical or Important finding |

The warnings are existing AnnData duplicate-name, Scanpy score-genes and SciPy
sparse-matrix migration warnings from unrelated fixtures.

## Interpretation boundary

The rendered similarities are not calibrated probabilities, prediction sets,
developmental-age estimates, OOD decisions, tissue localization or independent
biological validation. The display checks do not validate cell-state names,
product identity, potency, safety, efficacy or release suitability. A
reference or method can become independent support only after its own
source-aware held-out analysis and biological review.
