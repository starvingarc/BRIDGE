# Environment Card: spatial

| 字段 | 内容 |
| --- | --- |
| Environment ID | `ENV-SPATIAL-v0.1` |
| Environment name | `spatial` |
| 审计日期 | 2026-08-03 |
| 状态 | `existing_needs_fixture_validation` |
| Owner | `pending_assignment` |
| Interpreter | Python 3.10.14 |
| GPU requirement | 坐标/graph 可 CPU；cell2location 建议 1 GPU |
| Resource class | `batch_cpu` / `single_gpu` / `large_memory` |
| Registered tool IDs | `SPATIALDATA-IO`, `SQUIDPY`, `CELL2LOCATION`, `SPATIAL-CONCORDANCE` |
| Input artifact types | SpatialData/zarr、h5ad、image/shape/table、frozen scRNA reference |
| Output artifact types | zarr/h5ad、parquet/TSV、image、MeasurementResult JSON |
| Update policy | 新版本新建 Environment ID，保留旧 fixture 和转换记录 |

## Purpose

处理 Visium/Visium HD、SpatialData、Squidpy 和 cell2location；P0/P1 用于空间 reference、ROI 与 marker/state concordance，不直接评估移植前产品质量。

## Audited Stack

| Package | Version |
| --- | --- |
| anndata | 0.10.8 |
| scanpy | 1.10.2 |
| scvi-tools | 1.1.6 |
| torch | 2.4.0 |
| SpatialData | 0.2.2 |
| Squidpy | 1.6.0 |
| cell2location | 0.1.3 |

## Registered Tool Scope

- `SPATIALDATA-IO`、`SQUIDPY`、`CELL2LOCATION`、`SPATIAL-CONCORDANCE`。
- hEB58 两张 section 的结构、坐标、ROI 和 marker/state 可行性分析。
- 后续冠状/矢状空间数据返回后的 donor/section-aware pipeline。

## Input Contract

- assay/platform、genome build、counts layer、image/shape/table 坐标明确。
- section、donor、orientation、ROI、segmentation method 和 transformation chain 明确。
- scRNA reference 与 spatial gene universe、species 和 anatomy 匹配。

## Abstention

- 坐标系或 transformation 未确认时不做跨切片比较。
- 同一胚胎的多个 section 不作为独立 biological replicates。
- 只有 segmented profiles 不自动等于真实单细胞。
- 没有跨供体和正交验证时只输出 `Spatial Reference Concordance`。

## Health Check

```bash
conda run -n spatial python -c "import spatialdata, squidpy, cell2location; print(spatialdata.__version__, squidpy.__version__, cell2location.__version__)"
```

冻结前需使用一张脱敏小型 spatial fixture 完成 read、coordinate transform、graph、plot 和 cell2location smoke test。
