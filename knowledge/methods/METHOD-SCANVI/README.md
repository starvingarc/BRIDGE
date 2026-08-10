# scANVI

| Field | Value |
|---|---|
| Method ID | `METHOD-SCANVI` |
| Modules | P0-02, P0-03 |
| Scientific status | benchmark, shortlisted |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | EF-CS-LATENT-MAPPING, latent_mapping, regional_mapping |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

cell-state evidence | regional fidelity | target identity

## Inputs

counts + batch/modality | raw counts + batch + partial internal labels | L1/L2 internal states

## Outputs

latent representation and known-class posterior | latent, known-class posterior and composition | posterior + latent distance | regional posterior + distance

## Boundaries

Known-class posterior is not an open-set decision. | No preset priority; posterior is not open-set proof | overcorrection or OOD -> unavailable | query adaptation cannot alter frozen model

## Environment

Python 单细胞核心环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [GitHub - scverse/scvi-tools: Deep probabilistic analysis of single-cell and spatial omics data · GitHub](https://github.com/scverse/scvi-tools) (`SOURCE-7F48A0784539FD39`)
- [scvi.model.SCANVI — scvi-tools](https://docs.scvi-tools.org/en/stable/api/reference/scvi.model.SCANVI.html) (`SOURCE-B7847218B5D1E371`)
- [Documentation — scvi-tools](https://docs.scvi-tools.org/en/stable/) (`SOURCE-DEB4E1480D9B3470`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
