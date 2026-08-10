# BBKNN

| Field | Value |
|---|---|
| Method ID | `METHOD-BBKNN` |
| Modules | P0-02, P0-07 |
| Scientific status | benchmark, shadow |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | EF-CS-INTEGRATION-GRAPH, joint_representation |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

cell-state evidence | joint analysis shadow

## Inputs

PCA + batch | PCA representation and batch labels

## Outputs

Batch-balanced KNN graph | balanced neighbor graph

## Boundaries

Does not correct expression values. | Graph balancing can create artificial proximity

## Environment

Python 单细胞核心环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [GitHub - Teichlab/bbknn: Batch balanced KNN · GitHub](https://github.com/Teichlab/bbknn) (`SOURCE-4426C1A403D323CE`)
- [BBKNN — BBKNN 1.6.0 documentation](https://bbknn.readthedocs.io/) (`SOURCE-E2C8225DFCA8DA3D`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
