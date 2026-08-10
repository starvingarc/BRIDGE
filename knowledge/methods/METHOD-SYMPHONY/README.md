# Symphony

| Field | Value |
|---|---|
| Method ID | `METHOD-SYMPHONY` |
| Modules | P0-02, P0-03 |
| Scientific status | benchmark, conditional |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | EF-CS-COMPRESSED-MAPPING, latent_mapping, regional_mapping |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

cell-state evidence | regional fidelity | target identity

## Inputs

compressed Harmony reference + query | L1/L2 internal states | reference atlas + query

## Outputs

query embedding + neighbour evidence | query embedding + neighbours | stable embedding and kNN label transfer | embedding and kNN transfer

## Boundaries

Unknown handling must be added outside native output. | Unknown handling remains external | feature/modality mismatch | modality/feature mismatch

## Environment

R/Bioconductor 方法环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [Efficient and precise single-cell reference atlas mapping with Symphony | Nature Communications](https://www.nature.com/articles/s41467-021-25957-x) (`SOURCE-12A549328F618B24`)
- [GitHub - immunogenomics/symphony: Efficient and precise single-cell reference atlas mapping with Symphony · GitHub](https://github.com/immunogenomics/symphony) (`SOURCE-C77745B61FD4AB47`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
