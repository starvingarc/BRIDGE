# BRIDGE CNV adapter

| Field | Value |
|---|---|
| Method ID | `METHOD-BRIDGE-CNV-ADAPTER` |
| Modules | P0-06 |
| Scientific status | candidate |
| Source status | `internal_no_public_source` |
| License status | `internal` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `not_applicable` |
| Evidence family | `unassigned` |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

CNV shadow

## Inputs

Versioned tool output, reference manifest and gene-coordinate build

## Outputs

CNVShadowRecord with uncertainty and provenance

## Boundaries

Must not convert tool labels into Process score or TranscriptomicReviewFlag without a future validated rule

## Environment

Python 单细胞核心环境；工具专用隔离环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- No public source registered; see `source_status`.

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
