# Protocol visualization reference pack

用途：支持“用户上传自己的 protocol → 模型提取有来源的信息 → 用户核对 → 交互流程图与相关信息查阅”的产品路径。完整说明与后续接入条件见 [设计说明](../../docs/protocol-visualization.md)。

这是独立、只读的设计参考包。打开 [入口](index.html)，进入 [脑类器官流程](organoid-flow.html) 或 [中脑 DA 小分子图鉴](molecules/index.html)。直接用浏览器打开 HTML 即可，也可在仓库根目录运行：

```bash
python3 -m http.server 8080 --bind 127.0.0.1 --directory examples/protocol-visualization
```

本示例不调用模型、上传服务或科学工具。脑类器官路线与中脑 DA 分子库分开呈现，不能拼成统一分化方案。

## 维护源与产物

- `organoid-flow.html`：人工维护的最终参考流程、公开文献条件和交互。
- `molecules/data/catalog.json`：唯一人工维护的小分子信息源，含来源、原文浓度、窗口、疑点、结构身份与图文件映射。32 个条目有 72 条方法记录；24 个文献条目中 20 个直接关联记录，其余为背景/交叉核对。
- `molecules/assets/`：从注明的结构来源用 RDKit 绘制；每个分子有紧凑、完整、透明三版 SVG/PNG，共 192 个文件。图示通常为母体，不用于商品盐型或水合物称量。
- `molecules/index.html`：确定性生成的离线图鉴，不手改。更新资料后运行 `python3 examples/protocol-visualization/scripts/build_gallery.py`。
- `assets/morphology/` 与 `assets/categories/`：AI 辅助形态及类别插图；各自 README 保留依据与提示词。
- `assets/reagent-details/`：既有详情示意；准确结构、类别图标与混合物必须依文字标签区分。

文献检索截至 2026-10-08，未完成 596 条命中的逐篇全文筛选。历史/扩展/转录因子辅助分层与身份、剂量疑点均保留。缺少证据不能理解为没有使用，条目数量不能作为方案优劣排序。

## 素材来源

- 化学结构：每条 catalog 的 `structure_source`、PubChem CID、原始 SMILES 与绘图 SMILES。BIO 采用 Sigma B1686 的 oxime 表示；SAG21k 采用 Tocris 5282 的 trans 表示；guggulsterone 不指定原文未明确的 E/Z。
- 形态插图：[Lancaster–Knoblich 2014](https://doi.org/10.1038/nprot.2014.158) 图 2/3 的形态参考，AI 辅助重绘，非原图复制或实验观察。
- 类别插图：AI 辅助生成与编辑，灰线白底；不是蛋白结构预测或精确多糖结构。
- 流程详情：Y-27632 母体结构来自 [PubChem CID 448042](https://pubchem.ncbi.nlm.nih.gov/compound/448042)；蛋白、多糖和复合补充剂详情改用本包自有类别插图，避免把通用图误认作特定试剂实测结构。

科学参考资料仍待审阅，不属于正式知识快照。本包不包含私人 protocol、受限全文、原始论文图或实验截图。
