# scDblFinder

| Field | Value |
|---|---|
| Method ID | `METHOD-SCDBLFINDER` |
| Modules | P0-01 |
| Scientific status | candidate |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | transcriptome_doublet |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

input audit and QC

## Inputs

count_ready | confirmed capture_id; raw UMI counts; expected rate provenance

## Outputs

per-capture score/class、阈值和不确定性

## Boundaries

capture 未确认、counts 不合格、细胞过少

## Environment

R/Bioconductor 方法环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [GitHub - plger/scDblFinder: Methods for detecting doublets in single-cell sequencing data · GitHub](https://github.com/plger/scDblFinder) (`SOURCE-52986F3C839AE8EA`)
- [Doublet identification in single-cell sequencing... | F1000Research](https://doi.org/10.12688/f1000research.73600.2) (`SOURCE-79F7317415DE0FF6`)
- [Bioconductor - scDblFinder](https://bioconductor.org/packages/release/bioc/html/scDblFinder.html) (`SOURCE-C8FFAAB5FB995F60`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
