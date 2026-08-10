# Environment Card: pyscenic_stable

| 字段 | 内容 |
| --- | --- |
| Environment ID | `ENV-PYSCENIC-v0.1` |
| Environment name | `pyscenic_stable_20260601` |
| Logical alias | `pyscenic_stable` |
| 审计日期 | 2026-08-03 |
| 状态 | `existing_stable_candidate` |
| Owner | `pending_assignment` |
| Interpreter | Python 3.10.20 |
| GPU requirement | 无；多核 CPU 和充足内存 |
| Resource class | `batch_cpu` / `large_memory` |
| Registered tool IDs | `PYSCENIC`, `AUCELL` |
| Input artifact types | expression/count matrix、loom/h5ad、cisTarget DB、motif annotation |
| Output artifact types | adjacency/regulon/AUCell parquet/loom、MeasurementResult JSON |
| Update policy | 环境、cisTarget 和 motif snapshot 任一变更即生成新版本 |

## Audited Stack

| Package | Version |
| --- | --- |
| pySCENIC | 0.12.1 |
| arboreto | 0.1.6 |
| ctxcore | 0.2.0 |
| pyarrow | 12.0.1 |

## Purpose

运行 data-driven GRN、motif pruning 与 AUCell，作为 Regulatory Coherence 的独立 shadow channel。

## Required External Assets

- species/genome-build matched cisTarget ranking databases。
- versioned motif-to-TF annotation file。
- frozen TF list。
- input expression/count matrix、gene ID mapping 和 sample/state metadata。

## Output Contract

- adjacency table、module/regulon table、motif support、AUCell matrix。
- database filenames/version/hash、random seed、workers 和 input hash。
- 每个 regulon 的 parent expression/reference lineage。

## Boundaries

- coexpression 不证明调控因果。
- motif enrichment 不证明 query 中染色质开放或 TF 占位。
- 同源 reference 产生的 regulon 与 marker/mapper 不能作为独立证据重复计权。
- P0/P1 默认 `shadow_Q + E`，不进入正式域分数。

## Health Check

```bash
conda run -n pyscenic_stable_20260601 pyscenic --help
conda run -n pyscenic_stable_20260601 python -c "import pyscenic, arboreto, ctxcore; print(pyscenic.__version__)"
```

正式冻结需增加小型 GRN/ctx/AUCell fixture，并记录 cisTarget database snapshot。
