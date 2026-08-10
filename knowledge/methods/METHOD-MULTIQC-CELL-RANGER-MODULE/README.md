# MultiQC Cell Ranger module

| Field | Value |
|---|---|
| Method ID | `METHOD-MULTIQC-CELL-RANGER-MODULE` |
| Modules | P0-01 |
| Scientific status | conditional |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | upstream_library_metrics |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

input audit and QC

## Inputs

analysis_ready + upstream reports | library_id; capture_id; pipeline version

## Outputs

vendor/library metrics 的统一表与 provenance

## Boundaries

报告缺失或格式不受支持

## Environment

Python 单细胞核心环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [MultiQC: summarize analysis results for multiple tools and samples in a single report](https://doi.org/10.1093/bioinformatics/btw354) (`SOURCE-3A09B21096981D90`)
- [Cell Ranger | Seqera Docs](https://docs.seqera.io/multiqc/modules/cellranger) (`SOURCE-A4C07C837F10452E`)
- [GitHub - MultiQC/MultiQC: Aggregate results from bioinformatics analyses across many samples into a single report. · GitHub](https://github.com/MultiQC/MultiQC) (`SOURCE-D642A95D4309FF5A`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
