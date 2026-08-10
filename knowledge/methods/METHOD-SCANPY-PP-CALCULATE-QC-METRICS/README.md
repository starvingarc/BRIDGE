# scanpy.pp.calculate_qc_metrics

| Field | Value |
|---|---|
| Method ID | `METHOD-SCANPY-PP-CALCULATE-QC-METRICS` |
| Modules | P0-01 |
| Scientific status | adopted |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | cell_qc_metrics |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

input audit and QC

## Inputs

analysis_ready | explicit count/expression view; qc_vars

## Outputs

counts、detected genes、feature fractions、top-gene fractions

## Boundaries

layer 语义不明；count 方法收到 normalized matrix

## Environment

Python 单细胞核心环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [SCANPY: large-scale single-cell gene expression data analysis | Genome Biology | Springer Nature Link](https://doi.org/10.1186/s13059-017-1382-0) (`SOURCE-26AC0E84DA0027A5`)
- [scanpy.pp.calculate_qc_metrics — scanpy](https://scanpy.readthedocs.io/en/latest/api/generated/scanpy.pp.calculate_qc_metrics.html) (`SOURCE-EB0B6F88725B6285`)
- [GitHub - scverse/scanpy: Single-cell analysis in Python. Scales to >100M cells. · GitHub](https://github.com/scverse/scanpy) (`SOURCE-FE3CB299292A63C6`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
