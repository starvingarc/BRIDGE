# BRIDGE QC Flag Engine

| Field | Value |
|---|---|
| Method ID | `METHOD-BRIDGE-QC-FLAG-ENGINE` |
| Modules | P0-01 |
| Scientific status | adopted |
| Source status | `internal_no_public_source` |
| License status | `internal` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `not_applicable` |
| Evidence family | qc_flag_rules |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

input audit and QC

## Inputs

analysis_ready | assay_spec_id; sample/capture grouping; denominators

## Outputs

cell/sample/capture flags、eligibility 与理由

## Boundaries

MeasurementSpec 未冻结或关键分母缺失

## Environment

Python 单细胞核心环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- No public source registered; see `source_status`.

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
