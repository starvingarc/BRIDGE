import type { JsonValue } from "../types";

export const intakeLabels: Record<string, string> = {
  product_name: "产品 / 批次名称", product_family: "产品类别",
  target_cell_type: "目标细胞类型", target_stage: "预期发育阶段 / 培养天数",
  sampling_context: "本次取样", independent_cultures: "独立培养次数（可留空）",
  assay: "实验类型", matrix_location: "计数位置", count_semantics: "矩阵内容",
  source_family_id: "数据来源家族标识（可后补）",
  sample_id_column: "样本标识列", capture_id_column: "捕获批次列", gene_symbol_column: "基因名称列",
};

export const intakeValues: Record<string, string> = {
  unknown: "尚不确定", hpsc_mda: "hPSC 来源的中脑多巴胺能细胞", other: "其他细胞产品",
  pretransplant_preparation: "拟移植制剂 / 同批代表样本", process_sample: "分化过程中的样本",
  raw_counts: "未经标准化的原始计数", not_raw_counts: "已标准化或其他非原始计数",
};

export function intakeValue(value: JsonValue): string {
  if (value === null) return "未提供";
  if (typeof value === "string") return intakeValues[value] ?? value;
  return JSON.stringify(value);
}
