# P0-04 Developmental Compatibility Visualization

## Biological goal

Show how a submitted cell product relates to a researcher-confirmed
developmental window and to registered in-vivo reference stages. The figures
must keep whole-product and target-related denominators separate and must not
turn expression similarity into fetal age, calibrated probability or future
cell fate.

## Scope

- Add one typed dual-denominator view of states earlier than, within and later
  than the declared window, with branch-divergent and unresolved states kept
  off the ordered axis.
- Add one source- and assay-separated reference-stage fingerprint using only
  the top stage, runner-up, correlation, margin, gene coverage and evidence
  state already produced by the package.
- Add one ordered sampling-point composition view. Sampling-point order is
  categorical unless a future contract supplies numeric time, unit and origin.
- Publish deterministic JSON, TSV, SVG, PNG and PDF artifacts from one typed
  data object and register every component.

## Non-goals

- No single developmental age, in-vitro-day to gestational-week conversion,
  continuous trajectory, terminal-fate probability, lineage flow or spatial
  projection.
- No source or assay pooling, inferred confidence interval, quality score,
  pass/fail threshold, product ranking, potency, efficacy, safety or release
  claim.
- No change to Tool IDs, ToolRequest, ToolRun, the existing result Schema or
  the `domain_score=null` boundary.
- No Web UI implementation.

## Frozen interfaces

The existing result and method-bundle Schemas remain unchanged. Stage roles,
reference labels, product scope and sampling-point labels stay in versioned,
checksummed inputs. Observation counts do not become biological replicates.
Missing or conflicting evidence remains unavailable rather than zero.

## Implementation

- Package-owned visualization-data and artifact-set Schemas.
- Exact numerator, denominator, unit, applicability, missingness and Evidence
  bindings for every plotted record.
- A compact deterministic renderer with exact table fallbacks and explicit
  empty-state figures.
- Removal of continuous trend claims from the current public method list until
  a numeric experimental-time contract exists.

