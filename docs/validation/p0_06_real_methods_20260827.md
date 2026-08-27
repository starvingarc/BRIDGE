# P0-06 Real-method Runtime Validation

Date: 2026-08-27

## Scope

This record covers the P0-06 `method_runtime` path. It verifies that the package
can execute externally configured expression methods on a checksummed,
analysis-ready H5AD without changing the legacy aggregation contract.

The executable selectors are:

| Selector | Runtime call | Output |
|---|---|---|
| `PROC-SCORE-SCANPY` | `scanpy.tl.score_genes` | program-score summaries |
| `PROC-SCORE-DECOUPLER` | `decoupler.mt.ulm` | weighted program-score summaries |
| `PROC-CYCLE-SCANPY` | `scanpy.tl.score_genes_cell_cycle` | cell-cycle summaries |
| `PROC-CYCLE-AGG` | BRIDGE biological-unit/state aggregation | grouped summaries and method agreement |

UCell, AUCell, pseudobulk differential expression and CNV inference remain
registered candidates. This runtime does not execute them.

## Contract checks

- The method path requires 11 checksummed JSON objects and exactly one
  normalized-expression H5AD.
- Program genes, weights, analysis scopes, cell-cycle genes, coverage rules,
  grouping assignments and method parameters come from versioned inputs.
- The H5AD identity and checksum are bound before execution and checked again
  before output publication.
- Results bind the selected methods, biological units, state scopes, input
  checksums and software versions.
- Missing coverage produces typed `not_assessed` records; it is not converted to
  zero.
- Repeated runs over identical inputs produce the same run and artifact content
  identities.

## Engineering evidence

| Check | Result |
|---|---|
| P0-06 focused and registry tests | 40 passed |
| Full repository test suite | 1,231 passed |
| Tool discovery | 12 packages |
| Clean-wheel import | package loaded outside the source tree |
| CLI smoke | `list`, `describe P0-06`, and `input-contract P0-06` passed |
| Wheel SHA-256 | `3c6d9cd5897dfd9e378e4764740e631e5ab248b43af88a389cc149fd3da20784` |
| Knowledge validation | valid; no dangling method or source references |
| Repository policy and diff hygiene | passed |

The runtime test used a fully synthetic expression matrix with synthetic
biological-unit and cell-state assignments. No internal or unpublished data are
part of this record.

## Scientific boundary

This is engineering validation of callable methods and deterministic packaging.
It is not biological validation of a gene program, threshold, state definition,
cell fitness, safety or potency. P0-06 remains `candidate`; method evidence
remains `shadow`; `domain_score` remains `null`.
