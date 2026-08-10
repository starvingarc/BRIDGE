# scANVI integration view

| Field | Value |
|---|---|
| Method ID | `METHOD-SCANVI-INTEGRATION-VIEW` |
| Modules | P0-02 |
| Scientific status | benchmark |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | EF-CS-INTEGRATION-GENERATIVE |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

cell-state evidence

## Inputs

counts + batch + partial labels

## Outputs

latent embedding and class posterior

## Boundaries

Labels used for integration cannot independently validate annotation.

## Environment

Python 单细胞核心环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [GitHub - scverse/scvi-tools: Deep probabilistic analysis of single-cell and spatial omics data · GitHub](https://github.com/scverse/scvi-tools) (`SOURCE-7F48A0784539FD39`)
- [scvi.model.SCANVI — scvi-tools](https://docs.scvi-tools.org/en/stable/api/reference/scvi.model.SCANVI.html) (`SOURCE-B7847218B5D1E371`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
