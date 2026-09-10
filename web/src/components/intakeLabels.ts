import type { JsonValue } from "../types";

export const intakeLabels: Record<string, string> = {
  starting_cell_type: "起始细胞", cell_line: "细胞系", culture_day: "培养天数",
  sequencing_method: "建库测序方法", protocol_name: "分化方案名称",
  protocol_documents: "本次分化方案文件", protocol_stages: "方案阶段安排（规定步骤）",
  product_name: "产品 / 批次名称", product_family: "产品类别",
  target_cell_type: "目标细胞类型", target_stage: "预期发育阶段 / 培养天数",
  sampling_context: "本次取样", independent_cultures: "独立培养次数（可留空）",
  culture_batch_column: "批次核对字段或对应关系", culture_batch_role: "字段含义", culture_batch_role_note: "字段补充说明", culture_batch_binding: "批次字段与数据绑定",
  assay: "实验类型", matrix_location: "计数位置", count_semantics: "矩阵内容",
  source_family_id: "数据来源家族标识（可后补）",
  sample_id_column: "样本标识列", capture_id_column: "捕获批次列", gene_symbol_column: "基因名称列",
};

export const intakeValues: Record<string, string> = {
  independent_culture: "每个值对应一次独立培养", not_culture: "只是样本或测序标识", unsure: "不确定",
  unknown: "尚不确定", hpsc_mda: "hPSC 来源的中脑多巴胺能细胞", other: "其他细胞产品",
  pretransplant_preparation: "拟移植制剂 / 同批代表样本", process_sample: "分化过程中的样本",
  raw_counts: "未经标准化的原始计数", not_raw_counts: "已标准化或其他非原始计数",
};

export function intakeValue(value: JsonValue): string {
  if (value === null) return "未提供";
  if (typeof value === "string") return intakeValues[value] ?? value;
  return JSON.stringify(value);
}
