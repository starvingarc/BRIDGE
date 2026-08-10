# scArches

| Field | Value |
|---|---|
| Method ID | `METHOD-SCARCHES` |
| Modules | P0-02, P0-03 |
| Scientific status | benchmark, conditional |
| Source status | `registered` |
| License status | `review_required` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | EF-CS-LATENT-MAPPING, latent_mapping |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

cell-state evidence | target identity

## Inputs

compatible frozen model | compatible frozen model + query counts

## Outputs

mapped latent + label evidence | mapped latent and downstream labels

## Boundaries

Model and gene-schema compatibility are mandatory. | reference update must be versioned

## Environment

Python 单细胞核心环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [Mapping single-cell data to reference atlases by transfer learning | Nature Biotechnology](https://www.nature.com/articles/s41587-021-01001-7) (`SOURCE-3DB57426FEF86E2B`)
- [GitHub - theislab/scarches: Reference mapping for single-cell genomics · GitHub](https://github.com/theislab/scarches) (`SOURCE-40DE6E1BDC79416E`)
- [scArches documentation](https://docs.scarches.org/) (`SOURCE-DAF7CC5637BEFFD4`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
