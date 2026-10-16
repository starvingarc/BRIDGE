import { useEffect, useState } from "react";
import type { Session } from "../types";
import { object } from "./graphData";
import { readBoundedText } from "./ResultsPane";

type Row = { measurement: Record<string, unknown>; definition: Record<string, unknown>; measurement_sha256: string };
type Similarity = { kind: "reference_similarity"; reference_manifest_ref: string; n_observations: number; rows: Row[] };
const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
export function parseSimilarity(value: unknown): Similarity | null {
  if (!object(value) || value.kind !== "reference_similarity" || typeof value.reference_manifest_ref !== "string"
    || (!Number.isSafeInteger(value.n_observations) || Number(value.n_observations) <= 0) || !Array.isArray(value.rows) || !value.rows.length || value.rows.length > 1000) return null;
  const seen = new Set();
  for (const row of value.rows) {
    if (!object(row) || !object(row.measurement) || !object(row.definition)) return null;
    const m = row.measurement, d = row.definition;
    if (typeof m.measurement_id !== "string" || seen.has(m.measurement_id)
      || m.unit !== "similarity_coefficient" || m.domain_score !== null
      || !(m.raw_value === null || (finite(m.raw_value) && m.raw_value >= -1 && m.raw_value <= 1))
      || !["spearman", "cosine"].includes(String(d.native_field))
      || [d.label, d.label_level, d.profile_id, d.source_id].some(x => typeof x !== "string" || !x)
      || typeof row.measurement_sha256 !== "string" || !/^[a-f0-9]{64}$/.test(row.measurement_sha256)) return null;
    seen.add(m.measurement_id);
  }
  return value as Similarity;
}
const coefficient = (kind: unknown) => kind === "spearman" ? "Spearman 相关系数" : "余弦相似度";
function SimilarityValues({ value }: { value: Similarity }) {
  const sources = [...new Set(value.rows.map(r => String(r.definition.source_id) + "|" + String(r.definition.profile_id)))];
  const groups = [...new Set(value.rows.map(r => [r.definition.source_id, r.definition.profile_id, r.definition.label_level, r.definition.native_field].join("|")))];
  const [chosen, setChosen] = useState("");
  const group = groups.includes(chosen) ? chosen : groups[0];
  const rows = value.rows.filter(r => [r.definition.source_id, r.definition.profile_id, r.definition.label_level, r.definition.native_field].join("|") === group);
  const version = value.reference_manifest_ref.split("@").at(-1);
  return <>
    <label>选择参考与系数 <select value={group ?? ""} onChange={e => setChosen(e.target.value)}>
      {groups.map(key => { const [source, profile, level, kind] = key.split("|"); return <option key={key} value={key}>
        参考 {sources.indexOf(source + "|" + profile) + 1} · {level} 标签 · {coefficient(kind)}
      </option>; })}</select></label>
    <figure className="reference-chart" aria-label="参考相似度图">
      <figcaption className="chart-meta">{value.n_observations} 个细胞 · −1 至 1</figcaption>
      <ul>{rows.map(row => <li key={String(row.measurement.measurement_id)}>
        <div className="fraction-chart-label"><span>{String(row.definition.label)}</span>
          <strong title={String(row.measurement.raw_value ?? "不可用")}>{finite(row.measurement.raw_value) ? row.measurement.raw_value.toFixed(4) : "不可用"}</strong></div>
        <span className="similarity-track" aria-hidden="true"><i />{finite(row.measurement.raw_value)
          && <b style={{left:`${(row.measurement.raw_value + 1) * 50}%`}} />}</span>
      </li>)}</ul>
      <div className="program-chart-scale" aria-hidden="true"><span>−1</span><span>0</span><span>1</span></div>
    </figure>
    <details><summary>系数与说明</summary>
    <p>所选 RNA 整体汇总与参考标签表达谱的描述性相似度 · 参考版本 {version} · {value.n_observations} 个观察细胞。</p>
    <p>同一份查询 RNA 的方法结果不是独立证据；两个系数分开解释，不合成分数或投票。未知分配与缺失系数都不是零。</p>
    <div className="figure-table-scroll"><table aria-label="参考标签相似系数"><thead><tr><th scope="col">参考标签</th><th scope="col">系数（−1 至 1）</th><th scope="col">共享基因数</th></tr></thead>
      <tbody>{rows.map(row => <tr key={String(row.measurement.measurement_id)}><th scope="row">{String(row.definition.label)}</th>
        <td title={String(row.measurement.raw_value ?? "不可用")}>{finite(row.measurement.raw_value) ? <>{row.measurement.raw_value.toFixed(4)}<span className="similarity-track" aria-hidden="true"><i /><b style={{ left: `${(row.measurement.raw_value + 1) * 50}%` }} /></span></> : "不可用（未补零）"}</td>
        <td>{finite(row.definition.shared_genes) ? row.definition.shared_genes : "未提供"}</td></tr>)}</tbody></table></div>
    </details>
  </>;
}
export default function ReferenceSimilarity({ session }: { session: Session }) {
  const specs = session.artifacts.filter(a => a.tool_id === "P0-03" && a.name.startsWith("native_measurement_spec.")
    && a.media_type === "application/json" && a.access_state !== "denied" && a.content_class !== "developer_diagnostic"
    && (!a.acknowledgement_required || a.acknowledged));
  const [chosen, setChosen] = useState("");
  const spec = specs.find(a => a.id === chosen) ?? specs.at(-1);
  const [state, setState] = useState<{ id: string; value: Similarity | null; loading: boolean }>({ id: "", value: null, loading: false });
  useEffect(() => {
    if (!spec) return;
    const controller = new AbortController();
    setState({ id: spec.id, value: null, loading: true });
    void (async () => {
      let value = null;
      try {
        const response = await fetch("/api/sessions/" + encodeURIComponent(session.id) + "/artifacts/" + encodeURIComponent(spec.id) + "/preview",
          { credentials: "same-origin", signal: controller.signal });
        if (response.ok) { const body = await readBoundedText(response, 2_000_000); if (!body.truncated) value = parseSimilarity(JSON.parse(body.text)); }
      } catch { /* Keep the missingness explanation and existing files. */ }
      if (!controller.signal.aborted) setState({ id: spec.id, value, loading: false });
    })();
    return () => controller.abort();
  }, [session.id, spec?.id]);
  if (!spec) return <p>当前会话尚未登记可核验的参考相似系数。已有参考标签预测不等于相似系数；本页未据此补画。</p>;
  return <>
    {specs.length > 1 && <label>已保存相似度结果 <select value={spec.id} onChange={e => setChosen(e.target.value)}>{specs.map((s, i) => <option value={s.id} key={s.id}>结果 {i + 1}</option>)}</select></label>}
    {state.id !== spec.id || state.loading ? <p role="status">正在核对参考系数与来源…</p> : state.value
      ? <SimilarityValues key={spec.id} value={state.value} /> : <p role="status">参考系数的来源绑定暂不可用，请查看原始附件；未补画或替代数值。</p>}
  </>;
}
