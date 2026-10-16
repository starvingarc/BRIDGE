# 协作测试数据

无需学校内网即可取得的小型合成输入和配套 reference。使用现有 Web 和工具流程，
不另建演示执行链；私有服务器继续使用自己的资源配置。

## 文件

| 文件 | 用途 |
|---|---|
| [product.h5ad](data/product.h5ad) | 上传用产品数据：384 个合成细胞、1,024 个基因 |
| [reference.h5ad](data/reference.h5ad) | 原始合成参考：384 个合成细胞，同一基因空间；含 `label`、`subtype`、`developmental_stage` 注释 |
| [已构建 reference](data/references/REF-SYNTHETIC-COLLAB-v1/reference_manifest.json) | 现有参考加载器可读取的 manifest、L1/L2 profiles、词表及 marker 定义，无需自己训练模型 |
| [product-design.csv](data/product-design.csv) | 生成时指定的类别，仅供调试对照，不是工具预测或生物学真值，不作为分析输入 |
| [checksums.json](data/checksums.json) | 数据及参考文件的 SHA-256；重新生成后以新文件的实际校验值为准 |

`X` 是稀疏、非负整数 counts；`layers['logcounts']` 是每细胞归一到 10,000 后
`log1p` 的表达矩阵。`Sample` 是样本标识列。参考中的两个样本名是生成器分组，
不是独立供体或生物学重复。全部表达值由固定种子生成，没有读取或抽取私有数据。
部分基因名为 `SYNTHETIC_GENE_*`，不用于真实基因集覆盖度评价。

## 用现有入口运行

先完成[开发环境配置](../../docs/DEVELOPMENT.md)。在仓库根目录运行：

```bash
export BRIDGE_REFERENCE_ROOT="$PWD/examples/demo/data/references"
export BRIDGE_ALLOW_CANDIDATE_REFERENCES=1
export BRIDGE_WEB_CELL_STATE_MEASUREMENT_SPEC_REF=CELLSTATE-scRNA-synthetic-v0.1
unset BRIDGE_WEB_CELL_STATE_CANDIDATE_RUNTIME_REF BRIDGE_CELLSTATE_CANDIDATE_CATALOG
./start.sh
```

个人启动配置不要覆盖上述变量；模型服务、密钥和访问口令仍按
[Web 配置说明](../../docs/web-preview.md#start-a-private-instance) 自行设置，不共享。
用独立的开发存储启动，不复用私有分析会话。网页上传 `product.h5ad`，需要确认时填写：

- 数据性质：完全合成，仅用于软件开发；模拟单细胞 RNA 测序。
- 表达矩阵：`X` 为原始 counts；样本标识列：`Sample`。
- 目标：中脑多巴胺能祖细胞／前体；不声称来自独立实验或真实供体。
- 培养时间、真实分化方案和生物学重复：没有真实实验信息，不编造。

新测量配置仅绑定独立的合成 reference 身份，仍使用现有相关性／marker 计算；
不冒用私有参考或 CellTypist 模型。没有更改任何默认或服务器配置。
其余方法仍需要各自的资源与输入；本次数据交付不代表完整五域或 Web 端到端已验证，
缺失的 gene set、模型或实验信息应保留真实缺口，不能用合成输入宣布科学资格。

## 重新生成（可选）

已提交的数据可直接用，不需要先执行脚本。需要重建时，在安装好的开发环境中运行：

```bash
python examples/demo/generate.py --output tmp/collaboration-data
```

输出目录必须为空。生成器复用现有 reference builder；同一种子重现表达内容，
不同依赖版本下 HDF5 文件字节不保证一致，不应复用旧校验值。
合成矩阵及生成脚本按仓库许可提供；复用的词表与 marker 保持原有来源及候选状态。

## 可选公开数据入口

沿用[现有数据参考注册表](../../docs/bridge_spec_v0.1/data_reference_registry.md)，
可从 [GSE204796](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE204796)
和 [GSE76381](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE76381) 查询公开资料。
这里只提供官方入口，不包含这些数据的副本，也没有承诺自动下载或即用转换。
采用前核对实际文件、物种、counts／归一化语义、注释、引用及使用条件；
可下载不等于允许再分发。本数据包不依赖这两个站点可访问。
