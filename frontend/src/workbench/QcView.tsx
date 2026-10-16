import { useState, type ReactNode } from "react";
import { DoubletHistogram, Histogram, MitoDensity } from "./QcCharts";
import { METRICS, READINESS, formatMetric, median, readinessNote, reason, useQcDetail, type DoubletSummary, type QcCells } from "./qc";
import type { MappingInput } from "./types";
import type { AnalysisDTO } from "./objects";
import { SourceGoneNote } from "./SourceGoneNote";

const UNITS: Record<string, string> = { cells: "细胞", nuclei: "细胞核", barcodes: "条码" };
/** The tool's own figures, kept as originals to check the redrawn charts against. */
const FIGURES: Record<string, string> = {
  "qc_overview.png": "指标分布", "counts_genes_scatter.png": "计数与基因", "qc_metric_relationships.png": "文库复杂度",
  "qc_observation_retention.png": "细胞保留", "qc_capture_distributions.png": "按 capture 分布", "qc_flag_intersections.png": "QC 标记组合",
};
/** A column worth drawing: present, with at least one measured value. */
const hasValues = (values?: Float64Array): values is Float64Array => !!values && values.some(Number.isFinite);
export const day = (iso: string) => iso.slice(5, 16).replace("T", " ");

const count = (n: number) => n.toLocaleString("en-US");
/** A share with one decimal; a small non-zero share reads "<0.1%" rather than zero. */
const percent = (part: number, whole: number) => !whole ? "—" : part > 0 && part / whole < 0.0005 ? "<0.1%" : formatMetric(part / whole, "fraction");

/**
 * Scrublet's doublet candidates: how many, the score distribution, and per capture when there are several. Candidates
 * are marked, never removed; a capture's threshold is drawn only when the whole sample is that one capture.
 */
function Doublets({ doublet, cells }: { doublet: DoubletSummary; cells: QcCells | null | undefined }) {
  const single = doublet.captures.length === 1 ? doublet.captures[0] : null;
  return <section className="wb-qc-box" aria-label="双细胞">
    <h3>双细胞 <span className="wb-muted">候选 {count(doublet.predicted)} 个 · {percent(doublet.predicted, doublet.assessed)}</span></h3>
    {hasValues(cells?.scrublet_score) && <DoubletHistogram scores={cells!.scrublet_score!} classes={cells!.scrublet_class} threshold={single?.threshold ?? null} simulated={single?.simulated} />}
    {doublet.captures.length > 1 && <table className="wb-qc-captures">
      <thead><tr><th>捕获批次</th><th>细胞</th><th>候选</th><th>阈值</th></tr></thead>
      <tbody>{doublet.captures.map(c => <tr key={c.captureId}>
        <td>{c.captureId}</td><td>{count(c.cells)}</td><td>{count(c.predicted)} · {percent(c.predicted, c.cells)}</td><td>{c.threshold === null ? "—" : c.threshold.toFixed(2)}</td>
      </tr>)}</tbody>
    </table>}
  </section>;
}

type Capture = NonNullable<MappingInput["capture"]>;

/**
 * Doublets were not detected because no capture batch was declared: the researcher can name the capture here, which runs
 * the sample's standard analysis again with Scrublet; the earlier results stay in the records.
 */
function CaptureForm({ onCapture }: { onCapture: (capture: Capture) => Promise<string | undefined> }) {
  const [mode, setMode] = useState<"one" | "column">("one");
  const [name, setName] = useState("");
  const [state, setState] = useState<{ busy?: boolean; notice?: string; error?: string }>({});
  const value = name.trim();
  const submit = async () => {
    if (!value || value.length > 160) return;
    setState({ busy: true });
    try { setState({ notice: await onCapture(mode === "one" ? { id: value } : { column: value }) }); }
    catch (failure) { setState({ error: failure instanceof Error ? failure.message : "没有开始，请重试。" }); }
  };
  if (state.notice) return <p className="wb-muted" role="status">{state.notice}</p>;
  return <form className="wb-capture" aria-label="补充捕获批次" onSubmit={e => { e.preventDefault(); void submit(); }}>
    <span className="wb-seg" role="group" aria-label="捕获批次">
      <button type="button" aria-pressed={mode === "one"} onClick={() => setMode("one")}>整个文件一次捕获</button>
      <button type="button" aria-pressed={mode === "column"} onClick={() => setMode("column")}>几次捕获，记在一列</button>
    </span>
    <input value={name} onChange={e => setName(e.target.value)} aria-label={mode === "one" ? "捕获批次名" : "捕获批次所在的列"}
      placeholder={mode === "one" ? "批次名，如样本编号" : "obs 里的列名"} />
    <button className="wb-chip" type="submit" disabled={!value || state.busy}>{state.busy ? "正在提交…" : "检测双细胞"}</button>
    <small className="wb-muted">会重新跑这份样本的基础分析，之前的结果留在「记录」。</small>
    {state.error && <p className="wb-error" role="alert">{state.error}</p>}
  </form>;
}

/** Download of the per-cell table and, for QC, the tool's original figures, kept small in the footer. */
export function Files({ analysis }: { analysis: AnalysisDTO }) {
  const table = analysis.results.find(r => r.artifact?.kind === "table")?.artifact;
  const figures = analysis.results.flatMap(r => r.artifact?.kind === "figure" ? [r.artifact] : []);
  return <>
    {table && <> · <a className="wb-link" href={table.url} download={table.name}>下载数据</a></>}
    {figures.length > 0 && <> · <details className="wb-qc-originals"><summary>原图</summary>
      <ul>{figures.map(f => <li key={f.id}><a className="wb-link" href={f.url} target="_blank" rel="noreferrer">{FIGURES[f.name] ?? f.name}</a></li>)}</ul>
    </details></>}
  </>;
}

/** One registered automatic QC: readiness, the counts, charts redrawn from the per-cell table, doublets, and the files. */
export function QcView({ analysis, others, onCapture, children }: {
  analysis: AnalysisDTO; others: number;
  /** Declares the capture batch when doublets could not be detected for lack of one. */
  onCapture?: (capture: Capture) => Promise<string | undefined>;
  /** Further sections of the QC, such as the cell cycle, shown above the footer. */
  children?: ReactNode;
}) {
  const summary = analysis.qc_summary!;
  const detail = useQcDetail(analysis);
  const foot = <p className="wb-qc-foot">{analysis.tool.id} {analysis.tool.version} · {day(analysis.created_at)}{!detail?.gone && <Files analysis={analysis} />}</p>;
  // A file refused because its source changed withdraws the whole QC: no numbers, charts or file actions remain.
  if (detail?.gone) return <div className="wb-qc"><SourceGoneNote what="QC" />{foot}</div>;
  const readiness = READINESS[summary.readiness_state] ?? { label: summary.readiness_state, tone: "muted" as const };
  const s = summary.schema_integrity, cells = detail?.cells;
  const doublet = detail?.reasons?.doublet ?? null;
  // Why doublets were not detected, once the profile is read; only when this QC itself reports them as not assessed.
  const doubletState = summary.assessment_states.doublet_assessment;
  const doubletWhy = !doublet && detail?.reasons && doubletState && doubletState !== "candidate"
    ? detail.reasons.assessments.doublet_assessment ?? "not_assessed" : undefined;
  return <div className="wb-qc">
    <p className={`wb-qc-status wb-qc-status--${readiness.tone}`} title={readinessNote(summary, detail?.reasons ?? null)}>
      <span>可用性 {readiness.label}</span>{others > 0 && `共 ${others + 1} 次 QC，显示最近一次`}</p>
    <div className="wb-qc-tiles">
      <div><b>{count(s.n_observations)}</b><span>{UNITS[s.observation_kind] ?? s.observation_kind}</span></div>
      <div><b>{count(s.n_genes)}</b><span>基因</span></div>
      {METRICS.map(m => <div key={m.median}><b>{formatMetric(median(summary, m.median), m.unit)}</b><span>{m.label}中位数</span></div>)}
      {doublet && <div><b>{percent(doublet.predicted, doublet.assessed)}</b><span>双细胞候选</span></div>}
    </div>
    {cells && METRICS.some(m => hasValues(cells[m.column])) ? <>
      <div className="wb-qc-hists">
        {hasValues(cells.total_counts) && <Histogram title="总计数" values={cells.total_counts} unit="count" />}
        {hasValues(cells.detected_genes) && <Histogram title="检测基因" values={cells.detected_genes} unit="count" />}
        {hasValues(cells.mitochondrial_fraction) && <Histogram title="线粒体占比" values={cells.mitochondrial_fraction} unit="fraction" />}
      </div>
      {hasValues(cells.total_counts) && hasValues(cells.mitochondrial_fraction) && <MitoDensity counts={cells.total_counts} mito={cells.mitochondrial_fraction} />}
    </> : <p className="wb-muted" role="status">{!detail ? "正在读取…" : detail.cellsError ?? "没有可画的指标。"}</p>}
    {doublet && <Doublets doublet={doublet} cells={cells} />}
    {doubletWhy && <section className="wb-qc-box" aria-label="双细胞">
      <h3>双细胞 <span className="wb-muted">未检测</span></h3>
      <p className="wb-muted">{doubletWhy === "not_assessed" ? "这次 QC 没有检测双细胞。" : reason(doubletWhy)}</p>
      {doubletWhy === "capture_id_not_declared" && onCapture && <CaptureForm onCapture={onCapture} />}
    </section>}
    {children}
    {foot}
  </div>;
}
