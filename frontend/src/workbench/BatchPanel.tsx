import { useEffect } from "react";
import { OverlayHistogram, batchColour } from "./QcCharts";
import { PHASES, PHASE_LABEL } from "./cycle";
import { METRICS, formatMetric, median, useQcDetails } from "./qc";
import { ofKind, pointSummary, type SampleAnalyses } from "./analyses";
import type { AnalysisDTO } from "./objects";
import type { Protocol, SampleRecord } from "./types";

export type Batch = { id: string; label: string };

/** Switches between all batches of a day and one of them; shown only when the day has more than one batch. */
export function BatchSwitch({ batches, current, onPick }: { batches: Batch[]; current: string; onPick: (id: string) => void }) {
  return <nav className="wb-batches" aria-label="批次">
    <button aria-pressed={current === "all"} onClick={() => onPick("all")}>全部批次</button>
    {batches.map((b, i) => <button key={b.id} aria-pressed={current === b.id} onClick={() => onPick(b.id)}>
      <i style={{ background: batchColour(i) }} />{b.label}</button>)}
  </nav>;
}

const share = (part: number, whole: number) => whole ? `${(part / whole * 100).toFixed(1)}%` : "—";
const latest = (state: SampleAnalyses | undefined, kind: AnalysisDTO["source_kind"]) =>
  state?.analyses ? ofKind(state.analyses, kind).find(a => a.availability.status === "available") : undefined;

/**
 * The batches of one day side by side: QC numbers, distributions drawn per batch, cell-cycle phases and where mapping put
 * the cells. Each batch was analysed on its own; nothing here merges their data.
 */
export function BatchPanel({ protocol, day, batches, points, analyses, onPick, onClose }: {
  protocol: Protocol; day: number; batches: Batch[]; points: SampleRecord[]; analyses: Map<string, SampleAnalyses>;
  onPick: (id: string) => void; onClose: () => void;
}) {
  useEffect(() => {
    const key = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onClose]);
  const qcs = points.map(p => latest(analyses.get(p.id), "sample_qc"));
  const details = useQcDetails(qcs.filter((a): a is AnalysisDTO => !!a));
  const detailOf = (i: number) => { const a = qcs[i]; return a ? details[qcs.filter(Boolean).indexOf(a)] ?? null : null; };
  const cycles = points.map(p => latest(analyses.get(p.id), "sample_cell_cycle")?.cell_cycle_summary?.cell_cycle ?? null);
  const loading = points.some(p => p.status !== "collected" && !analyses.has(p.id));
  const series = (column: "total_counts" | "detected_genes" | "mitochondrial_fraction") => points.flatMap((_, i) => {
    const values = detailOf(i)?.cells?.[column];
    return values && values.some(Number.isFinite) ? [{ label: batches[i].label, values }] : [];
  });
  const overlays = ([["total_counts", "总计数", "count"], ["detected_genes", "检测基因", "count"], ["mitochondrial_fraction", "线粒体占比", "fraction"]] as const)
    .map(([column, title, unit]) => ({ title, unit, series: series(column) })).filter(o => o.series.length > 1);
  return <aside className="wb-panel" aria-label={`D${day} 的 ${batches.length} 个批次`}>
    <header className="wb-panel-head">
      <div><span className="wb-panel-day">D{day} · {batches.length} 个批次</span><span className="wb-muted">各批次分别分析，并排对比</span></div>
      <button className="wb-link" onClick={onClose} aria-label="关闭样本">×</button>
    </header>
    <BatchSwitch batches={batches} current="all" onPick={onPick} />
    <div className="wb-panel-body wb-qc">
      {loading && <p className="wb-muted" role="status">正在读取…</p>}
      <table className="wb-batch-table" aria-label="各批次 QC">
        <thead><tr><th>批次</th><th>细胞</th>{METRICS.slice(0, 3).map(m => <th key={m.median}>{m.label}</th>)}<th>双细胞</th><th>S/G2M</th></tr></thead>
        <tbody>{points.map((p, i) => {
          const qc = qcs[i]?.qc_summary, doublet = detailOf(i)?.reasons?.doublet, cycle = cycles[i];
          return <tr key={p.id}>
            <td><i style={{ background: batchColour(i) }} />{batches[i].label}</td>
            <td>{qc ? qc.schema_integrity.n_observations.toLocaleString("en-US") : "—"}</td>
            {METRICS.slice(0, 3).map(m => <td key={m.median}>{qc ? formatMetric(median(qc, m.median), m.unit) : "—"}</td>)}
            <td>{doublet ? share(doublet.predicted, doublet.assessed) : qc ? "未检测" : "—"}</td>
            <td>{cycle?.s_g2m_fraction != null ? `${(cycle.s_g2m_fraction * 100).toFixed(1)}%` : "—"}</td>
          </tr>;
        })}</tbody>
      </table>
      {overlays.map(o => <OverlayHistogram key={o.title} title={o.title} unit={o.unit} series={o.series} />)}
      {cycles.some(Boolean) && <section className="wb-qc-section" aria-label="各批次细胞周期">
        <h3>细胞周期</h3>
        <div className="wb-batch-cycle">{points.map((p, i) => {
          const c = cycles[i], counts = c?.phase_counts, total = c?.n_observations ?? 0;
          return [<span key={`${p.id}-l`}>{batches[i].label}</span>,
            counts && total ? <div key={`${p.id}-b`} className="wb-cycle-bar" role="img"
              aria-label={`${batches[i].label}：${PHASES.map(ph => `${PHASE_LABEL[ph]} ${share(counts[ph] ?? 0, total)}`).join("，")}`}>
              {PHASES.map(ph => (counts[ph] ?? 0) > 0 && <i key={ph} className={`wb-phase--${ph}`} style={{ flexGrow: counts[ph] }} />)}</div>
              : <span key={`${p.id}-b`} className="wb-muted">—</span>,
            <span key={`${p.id}-s`} className="wb-muted">{counts && total ? `S/G2M ${share((counts.S ?? 0) + (counts.G2M ?? 0), total)}` : ""}</span>];
        })}</div>
      </section>}
      {points.some(p => pointSummary(protocol, p).lead) && <section className="wb-qc-section" aria-label="各批次映射">
        <h3>映射</h3>
        <ul className="wb-qc-list">{points.map((p, i) => { const s = pointSummary(protocol, p);
          return <li key={p.id}><span>{batches[i].label}</span><i>{s.lead ? `最多落在${s.lead}` : "还没有映射"}</i></li>; })}</ul>
      </section>}
    </div>
  </aside>;
}
