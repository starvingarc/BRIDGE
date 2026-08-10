# inferCNVpy

| Field | Value |
|---|---|
| Method ID | `METHOD-INFERCNVPY` |
| Modules | P0-06 |
| Scientific status | shadow |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | `unassigned` |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

CNV shadow

## Inputs

AnnData, raw/appropriate layer, genomic gene positions and explicit reference cells

## Outputs

Relative CNV matrix, score and chromosome heatmap

## Boundaries

Official docs describe experimental status; resemblance to inferCNV is not DNA validation

## Environment

工具专用隔离环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [infercnvpy: Scanpy plugin to infer copy number variation (CNV) from single-cell transcriptomics data — infercnvpy](https://infercnvpy.readthedocs.io/en/latest/) (`SOURCE-ECEDBCAE0A7CD128`)
- [GitHub - icbi-lab/infercnvpy: Infer copy number variation (CNV) from scRNA-seq data. Plays nicely with Scanpy. · GitHub](https://github.com/icbi-lab/infercnvpy) (`SOURCE-F2EB868987A7ED4A`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
