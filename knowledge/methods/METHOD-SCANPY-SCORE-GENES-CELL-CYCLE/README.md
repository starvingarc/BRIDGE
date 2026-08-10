# Scanpy score_genes_cell_cycle

| Field | Value |
|---|---|
| Method ID | `METHOD-SCANPY-SCORE-GENES-CELL-CYCLE` |
| Modules | P0-06 |
| Scientific status | benchmark |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | `unassigned` |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

proliferation and pluripotency

## Inputs

AnnData + frozen S/G2M genes with sufficient coverage

## Outputs

S_score, G2M_score, phase and coverage

## Boundaries

Transcriptomic phase is not a direct proliferation-rate or growth assay

## Environment

Python 单细胞核心环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [scanpy.tl.score_genes_cell_cycle — scanpy](https://scanpy.readthedocs.io/en/stable/api/scanpy.tl.score_genes_cell_cycle.html) (`SOURCE-3921FB2B7BCEDCE6`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
