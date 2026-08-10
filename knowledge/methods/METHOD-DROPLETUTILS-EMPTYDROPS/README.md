# DropletUtils emptyDrops

| Field | Value |
|---|---|
| Method ID | `METHOD-DROPLETUTILS-EMPTYDROPS` |
| Modules | P0-01 |
| Scientific status | conditional |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | droplet_cell_calling |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

input audit and QC

## Inputs

droplet_ready | capture_id; raw/filtered barcode relation

## Outputs

barcode-level cell-containing evidence 与 FDR

## Boundaries

缺未过滤 droplet matrix 或 barcode provenance

## Environment

R/Bioconductor 方法环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [Bioconductor - DropletUtils](https://bioconductor.org/packages/release/bioc/html/DropletUtils.html) (`SOURCE-0042F7B72B1CE191`)
- [EmptyDrops: distinguishing cells from empty droplets in droplet-based single-cell RNA sequencing data | Genome Biology | Springer Nature Link](https://doi.org/10.1186/s13059-019-1662-y) (`SOURCE-94902365C57141A2`)
- [https://git.bioconductor.org/packages/DropletUtils](https://git.bioconductor.org/packages/DropletUtils) (`SOURCE-E777C5DF7924F542`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
