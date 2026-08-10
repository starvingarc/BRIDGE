# Scanpy score_genes

| Field | Value |
|---|---|
| Method ID | `METHOD-SCANPY-SCORE-GENES` |
| Modules | P0-06 |
| Scientific status | benchmark |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | EF-METHOD-SCANPY |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

process programs

## Inputs

AnnData + signature + control-gene strategy

## Outputs

Target mean minus matched-control mean

## Boundaries

Affected by preprocessing, gene bins, controls and random seed; not rank-invariant

## Environment

Python 单细胞核心环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [scanpy.tl.score_genes — scanpy](https://scanpy.readthedocs.io/en/stable/generated/scanpy.tl.score_genes.html) (`SOURCE-6D4CC8F3D3BB5E0B`)
- [GitHub - scverse/scanpy: Single-cell analysis in Python. Scales to >100M cells. · GitHub](https://github.com/scverse/scanpy) (`SOURCE-FE3CB299292A63C6`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
