# AnnData

| Field | Value |
|---|---|
| Method ID | `METHOD-ANNDATA` |
| Modules | P0-01, P0-12 |
| Scientific status | adopted, shortlisted |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | object_structure |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

graft assessment | input audit and QC

## Inputs

analysis_ready | cell/gene IDs; X/layers semantics | matrix + obs/var

## Outputs

versioned analysis object | 对象结构、稀疏类型、维度、命名空间和 fingerprint

## Boundaries

 | 对象损坏、ID 不唯一、矩阵不可读

## Environment

Python 单细胞核心环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [anndata - Annotated data — anndata 0.13.2 documentation](https://anndata.readthedocs.io/) (`SOURCE-3D3C017885E9C3AF`)
- [GitHub - scverse/anndata: Annotated data. · GitHub](https://github.com/scverse/anndata) (`SOURCE-6006C385E1CCE287`)
- [anndata.AnnData — anndata 0.13.2 documentation](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html) (`SOURCE-60732A8672637605`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
