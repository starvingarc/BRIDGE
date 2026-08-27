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
- `ProgramSpec` is the single source for program genes/weights and S/G2M
  phase genes. `ProcessMethodSpec` selects program IDs and runtime parameters
  without copying that biological content.
- Each selected program's canonical content digest must equal its
  `gene_set_sha256`; changing a gene, weight or phase gene while retaining the
  old digest is refused before execution.
- The H5AD identity and checksum are bound before execution and checked again
  before output publication.
- Results bind the exact ProgramSpec and method spec checksums, selected
  methods, biological units, state scopes, expression asset and software
  versions.
- Missing coverage produces typed `not_assessed` records; it is not converted to
  zero.
- Repeated runs over identical inputs produce the same run and artifact content
  identities.

## Engineering evidence

| Check | Result |
|---|---|
| P0-06 focused and registry tests | 43 passed |
| Content-integrity adversaries | gene, weight and phase-gene changes under a stale digest all refused with typed reasons |
| Generated artifacts | ProgramSpec, ProcessMethodSpec and ProcessMethodBundle schemas regenerated from their repository models |
| Repository checks | repository policy, `git diff --check` and added-lines privacy scan passed |

The runtime test used a fully synthetic expression matrix with synthetic
biological-unit and cell-state assignments. No internal or unpublished data are
part of this record.

These counts describe the focused closure run for this revision. The required
GitHub repository gate remains the authority for the complete source suite,
wheel build, 12-tool discovery and clean-install checks.

## Scientific boundary

This is engineering validation of callable methods and deterministic packaging.
It is not biological validation of a gene program, threshold, state definition,
cell fitness, safety or potency. P0-06 remains `candidate`; method evidence
remains `shadow`; `domain_score` remains `null`.
