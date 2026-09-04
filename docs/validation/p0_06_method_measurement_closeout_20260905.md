# P0-06 method-measurement closeout validation — 2026-09-05

## Scope

This record covers P0-06 tool v0.6.0 and its `method_runtime` handoff. It
verifies that gate-facing measurements are derived from package-executed
expression methods over the exact P0-02-selected DataView, not from a
caller-provided precomputed evidence bundle.

The legacy aggregation path remains compatible and continues to consume its
checksummed `ProgramEvidenceBundle`.

## Runtime contract

Method mode requires:

- six case, product, window, program, cell-state and protocol objects;
- a reviewed BiologicalUnit manifest and observation assignment;
- a selector-only `ProcessMethodSpec` and checksummed `ProcessMethodInput`;
- one independent P0-06 `MeasurementSpecV2`;
- one H5AD whose asset ID, checksum, assay, matrix location and matrix semantics
  exactly match the P0-02 V3 DataView.

A caller-provided `ProgramEvidenceBundle` is refused in method mode. The
MeasurementSpec must bind only P0-06 and exactly match the assay, observation,
analysis and independence units, selected methods, scopes, metric names and
units. It does not contain a threshold, alert rule or score.

## Observed behavior

Analysis-ready `normalized_expression` is consumed as selected. Count-ready
`raw_counts` is accepted only when finite, non-negative and integer-valued
with positive per-observation totals; P0-06 then applies deterministic
library-size 10,000 scaling and `log1p` in memory.

The emitted `ProcessMethodBundle` v0.2 records the selected matrix location,
input and analysis semantics, and package-owned normalization lineage. It binds
the expression asset, ProgramSpec, method spec/input and BiologicalUnit inputs
by checksum.

Raw-count bundles use the package recipe ID
`bridge_normalize_total_log1p_v0.1` with target sum `10000.0`; it is not a
knowledge-catalog Method reference. Both the Pydantic model and public Draft
2020-12 Schema reject missing or contradictory normalization lineage.

Each real `ProgramScoreSummary` and `CellCycleSummary` produces exactly one
checksummed `MeasurementResultV2`. Available program means and cycling
fractions use `evidence_state=inferred`; `not_assessed` summaries remain
numeric-null `unavailable`. Program-score means retain their observation denominator and algebraic score-sum
numerator; cell-cycle counts retain their numerator and denominator. The profile binding records the source summary digest, method,
program, scope and biological unit. No caller evidence state, biological
threshold, alert or numeric score is synthesized.

## Engineering verification

Exact-head server checks:

- focused P0-06 plus registry suite: 68 passed;
- schema generation was byte-identical across consecutive runs;
- repository policy and committed-whitespace checks passed;
- both committed requests and the new public Schemas parsed as valid JSON.

The required GitHub repository gate remains authoritative for the complete
suite, wheel build and clean-install checks.

## Scientific boundary

This is engineering validation of executable methods, lineage and interface
behavior. It does not validate a gene program, biological threshold, product
state, cell fitness, process causality, safety or potency. P0-06 remains
`candidate/shadow`; `score_state=unavailable` and `domain_score=null`.
