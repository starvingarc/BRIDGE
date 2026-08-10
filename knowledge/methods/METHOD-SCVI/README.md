# scVI

| Field | Value |
|---|---|
| Method ID | `METHOD-SCVI` |
| Modules | P0-02, P0-07 |
| Scientific status | shadow, shortlisted |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | EF-CS-INTEGRATION-GENERATIVE, joint_representation |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

cell-state evidence | joint analysis shadow

## Inputs

Counts, batch covariates and frozen model settings | raw counts + batch covariates | all eligible annotation targets

## Outputs

Joint latent representation | latent embedding and model diagnostics | latent sensitivity + scIB diagnostics

## Boundaries

Latent correction may suppress protocol/time effects | Latent mixing alone is not evidence of biological correctness. | No UMAP-only method selection

## Environment

Python 单细胞核心环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [Deep generative modeling for single-cell transcriptomics | Nature Methods](https://www.nature.com/articles/s41592-018-0229-2) (`SOURCE-6603496E6054E807`)
- [GitHub - scverse/scvi-tools: Deep probabilistic analysis of single-cell and spatial omics data · GitHub](https://github.com/scverse/scvi-tools) (`SOURCE-7F48A0784539FD39`)
- [Documentation — scvi-tools](https://docs.scvi-tools.org/en/stable/) (`SOURCE-DEB4E1480D9B3470`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
