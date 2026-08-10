# Scanpy ingest

| Field | Value |
|---|---|
| Method ID | `METHOD-SCANPY-INGEST` |
| Modules | P0-02 |
| Scientific status | catalog_only |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | EF-CS-LIGHT-MAPPING |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

cell-state evidence

## Inputs

compatible reference PCA/neighbors + query

## Outputs

mapped embedding and transferred labels

## Boundaries

Reference preprocessing must be identical and versioned.

## Environment

Python 单细胞核心环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [scanpy.tl.ingest — scanpy](https://scanpy.readthedocs.io/en/stable/generated/scanpy.tl.ingest.html) (`SOURCE-E3AA3008E1E475C2`)
- [GitHub - scverse/scanpy: Single-cell analysis in Python. Scales to >100M cells. · GitHub](https://github.com/scverse/scanpy) (`SOURCE-FE3CB299292A63C6`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
