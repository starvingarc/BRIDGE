import { useState } from "react";
import type { ExpressionAnalysis } from "../types";

function Columns({label, values, onChange}: {label: string; values: string[]; onChange: (values: string[]) => void}) {
  const [text, setText] = useState(values.join(", "));
  return <label className="analysis-input-field">{label}<input value={text} onChange={event => {
    setText(event.target.value);
    onChange(event.target.value.split(/[,，]/).map(v => v.trim()).filter(Boolean));
  }} /></label>;
}

export default function ExpressionOptions({value, disabled, onChange}: {
  value: ExpressionAnalysis; disabled: boolean; onChange: (value: ExpressionAnalysis) => void;
}) {
  const exploration = value.exploration ?? {};
  const contrast = value.contrast;
  const text = (label: string, current: string | null | undefined, change: (value: string) => void, required = false) =>
    <label className="analysis-input-field">{label}<input value={current ?? ""} required={required}
      onChange={event => change(event.target.value)} /></label>;
  return <fieldset disabled={disabled}><legend>表达探索</legend>
    <p>使用质控后选定的数据。字段名填写数据中的细胞注释列；保留原有分群，留空时生成探索性聚类。</p>
    {text("分群列", exploration.group_key, group_key => onChange({...value, exploration: {...exploration, group_key: group_key || null}}))}
    <Columns label="着色列（逗号分隔，例如 batch、sample）" values={exploration.color_keys ?? []}
      onChange={color_keys => onChange({...value, exploration: {...exploration, color_keys}})} />
    <Columns label="表达着色基因（逗号分隔）" values={exploration.genes ?? []}
      onChange={genes => onChange({...value, exploration: {...exploration, genes}})} />
    <details><summary>已有降维与标准化数据</summary>
      {text("复用的 UMAP 坐标名称（如 X_umap；留空重新计算）", exploration.embedding_key,
        embedding_key => onChange({...value, exploration: {...exploration, embedding_key: embedding_key || null}}))}
      <p>选择复用即声明坐标来自当前细胞与表达数据；坐标名称本身不能证明来源。</p>
      <label><input type="checkbox" checked={exploration.normalized_scale === "log1p"}
        onChange={event => onChange({...value, exploration: {...exploration, normalized_scale: event.target.checked ? "log1p" : null}})} />
        已标准化表达确为自然对数 log1p（原始计数无需勾选）</label>
    </details>
    <label><input type="checkbox" checked={!!contrast} onChange={event => onChange({...value, contrast: event.target.checked
      ? {group_key: exploration.group_key ?? "", group: "", sample_key: "", condition_key: "", reference: "", comparison: "", independent_samples_confirmed: false}
      : null})} /> 同时比较同一细胞类型内的两组条件</label>
    {contrast && <fieldset><legend>按样本比较条件</legend>
      <p>需要原始计数。每个样本在所选细胞类型内汇总；少于每组 3 个独立样本时仅展示描述性差异。本版支持非配对设计。</p>
      {(["group_key", "group", "sample_key", "condition_key", "reference", "comparison", "batch_key"] as const).map(key =>
        <div key={key}>{text(({group_key: "细胞类型列", group: "要比较的细胞类型", sample_key: "独立样本列",
          condition_key: "条件列", reference: "参照条件", comparison: "比较条件", batch_key: "批次列（可选）"})[key],
          contrast[key], input => onChange({...value, contrast: {...contrast, [key]: key === "batch_key" ? input || null : input}}), key !== "batch_key")}</div>)}
      <label><input type="checkbox" checked={contrast.independent_samples_confirmed ?? false}
        onChange={event => onChange({...value, contrast: {...contrast, independent_samples_confirmed: event.target.checked}})} />
        我确认样本代表独立生物学重复，而非同一个体的多次采集或技术拆分</label>
    </fieldset>}
  </fieldset>;
}
