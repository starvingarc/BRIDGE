# SingleR

| Field | Value |
|---|---|
| Method ID | `METHOD-SINGLER-502879` |
| Modules | P0-02, P0-03 |
| Scientific status | benchmark, shortlisted |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `available` |
| Evidence family | EF-CS-SIMILARITY, reference_similarity, regional_similarity |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

cell-state evidence | regional fidelity | target identity

## Inputs

labeled normalized reference + query | query + labelled reference | query expression + labelled reference

## Outputs

label + delta + pruned label | per-label scores, delta and pruned label | region label/delta/pruned

## Boundaries

Pruning is not automatically a calibrated OOD decision. | reference gap -> unassigned

## Environment

R/Bioconductor 方法环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [Bioconductor - SingleR](https://bioconductor.org/packages/SingleR/) (`SOURCE-3F1B0A4826C726D2`)
- [Reference-based analysis of lung single-cell sequencing reveals a transitional profibrotic macrophage | Nature Immunology](https://www.nature.com/articles/s41590-018-0276-y) (`SOURCE-9676FE37CA353922`)
- [GitHub - SingleR-inc/SingleR: Clone of the Bioconductor repository for the SingleR package. · GitHub](https://github.com/SingleR-inc/SingleR) (`SOURCE-ADE2BB0A8E263B7F`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
