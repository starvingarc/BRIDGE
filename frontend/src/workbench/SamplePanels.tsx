import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { ChainRings } from "./ChainRings";
import { MappingLens } from "./MappingLens";
import { SampleActions } from "./RunBar";
import { QcView } from "./QcView";
import { BatchSwitch, type Batch } from "./BatchPanel";
import { CycleView } from "./CycleView";
import { SourceGoneNote } from "./SourceGoneNote";
import { ofKind, resultOf, type SampleAnalyses } from "./analyses";
import { targetFraction } from "./stages";
import type { AnalysisDTO } from "./objects";
import type { Protocol, RunOps, Sample, SampleRecord } from "./types";
import type { AnalysisTab } from "../routes";

const STATUS: Record<SampleRecord["status"], string> = {
  collected: "待测序", data_attached: "数据已关联", mapping: "映射中", done: "已完成", failed: "映射未完成",
};

/** Why a sampling point has no mapping yet. */
function mappingWaiting(sample: SampleRecord) {
  return sample.status === "collected" ? "测序数据关联后，会自动做 QC 和映射。"
    : sample.status === "mapping" ? "正在映射到胎儿腹侧中脑图谱，通常几分钟内完成。QC 先出来，可以先看。"
    : sample.mapping === "failed" ? `映射未完成${sample.unavailable ? `，${sample.unavailable}` : ""}。`
    : `还没有映射${sample.unavailable ? `，${sample.unavailable}` : ""}。`;
}

/** Loading, failure and empty states shared by the analysis tabs; null once there is something to show. */
function pending(sample: SampleRecord, state: SampleAnalyses | null) {
  if (sample.status === "collected") return "测序数据关联后，会自动做 QC。";
  if (!state) return "正在读取…";
  if (!state.analyses) return state.error ?? "分析记录读取失败。";
  return null;
}

/**
 * QC of a sample: metrics, doublets and the cell cycle. An earlier QC or cell-cycle scoring can be picked in the records;
 * otherwise the most recently registered ones are shown.
 */
function QcTab({ sample, state, picked, pickedCycle, onCapture }: {
  sample: SampleRecord; state: SampleAnalyses | null; picked: string | null; pickedCycle: string | null;
  onCapture?: (capture: NonNullable<import("./types").MappingInput["capture"]>) => Promise<string | undefined>;
}) {
  const waiting = pending(sample, state);
  const all = state?.analyses ? ofKind(state.analyses, "sample_qc") : [];
  const shown = all.find(a => a.id === picked) ?? all[0];
  if (waiting) return <p className="wb-muted" role="status">{waiting}</p>;
  if (!shown) return <p className="wb-muted" role="status">{sample.status === "mapping" ? "QC 正在运行，完成后显示在这里。" : "这个样本还没有 QC 结果。"}</p>;
  if (shown.availability.status === "unavailable" || !shown.qc_summary) return <SourceGoneNote what="QC" />;
  const cycles = ofKind(state!.analyses!, "sample_cell_cycle");
  const cycle = cycles.find(a => a.id === pickedCycle) ?? cycles[0];
  // The sample's own UMAP, when its cell atlas is registered, shows where the phases sit.
  const atlas = ofKind(state!.analyses!, "sample_cell_atlas").find(a => a.availability.status === "available");
  return <QcView key={shown.id} analysis={shown} others={all.length - 1} onCapture={onCapture}>
    {cycle ? <section className="wb-qc-section" aria-label="细胞周期">
      <h3>细胞周期</h3>
      {cycle.availability.status === "unavailable" || !cycle.cell_cycle_summary ? <SourceGoneNote what="细胞周期" />
        : <CycleView key={cycle.id} analysis={cycle} atlas={atlas} others={cycles.length - 1} />}
    </section> : sample.status === "mapping" && <p className="wb-muted" role="status">细胞周期评分正在运行，完成后显示在这里。</p>}
  </QcView>;
}

const KINDS: Record<AnalysisDTO["source_kind"], string> = { sample_qc: "QC", sample_cell_cycle: "细胞周期", sample_cell_atlas: "细胞图谱", atlas_mapping: "图谱映射", session_execution: "会话分析" };

/** Every registered analysis of the sample, newest first; a QC can be opened, the order says nothing about which one is adopted. */
function RecordsTab({ sample, state, onOpen }: { sample: SampleRecord; state: SampleAnalyses | null; onOpen: (analysis: AnalysisDTO) => void }) {
  const waiting = pending(sample, state);
  if (waiting) return <p className="wb-muted" role="status">{waiting}</p>;
  const list = [...state!.analyses!].sort((a, b) => b.version - a.version);
  if (!list.length) return <p className="wb-muted" role="status">还没有登记的分析。</p>;
  return <>
    <ul className="wb-records">
      {list.map(a => { const readable = a.availability.status === "available";
        return <li key={a.id} className={readable ? "" : "wb-records--gone"}>
          <span className="wb-records-n">#{a.version}</span>
          <div><b>{KINDS[a.source_kind] ?? a.source_kind}</b>
            <small>{a.tool.id} {a.tool.version} · {a.created_at.slice(5, 16).replace("T", " ")}{a.mapping_versions?.reference ? ` · ${a.mapping_versions.reference}` : ""}</small></div>
          {readable && a.source_kind !== "session_execution" ? <button className="wb-link" onClick={() => onOpen(a)}>查看</button>
            : <span className="wb-muted">{readable ? "在会话中" : "来源不可用"}</span>}
        </li>; })}
    </ul>
    <p className="wb-muted">编号是登记先后，不代表采用哪一次。</p>
  </>;
}

type Props = {
  protocol: Protocol; sample: SampleRecord; tab: AnalysisTab; onTab: (tab: AnalysisTab) => void;
  state: SampleAnalyses | null; onClose: () => void;
  /** Whether analyses can be read from the server; example runs show their mapping only. */
  live: boolean;
  /** Attaches data and starts or retries mapping for this sample; absent for examples. */
  ops?: RunOps;
  /** The developmental tree opened on this day: a small preview in the panel, or the full tree. */
  tree?: (mode: "mini" | "full", sample: SampleRecord, back?: () => void) => ReactNode;
  /** Whether a result belongs to the tree shown now; cells of another tree version are not drawn. */
  onTree: (sample: Sample) => boolean;
  /** The batches of this sample's day, when there is more than one, and how to switch to another or to all of them. */
  batches?: Batch[];
  onBatch?: (id: string) => void;
};

/** The mapping tab: a small tree with this day's cells that opens full size, and where the cells landed. */
function MappingTab({ sample, mapped, tree, onTree, onFull, state, live }: {
  sample: SampleRecord; mapped: Sample | undefined; tree?: Props["tree"]; onTree: Props["onTree"]; onFull: () => void;
  state: SampleAnalyses | null; live: boolean;
}) {
  if (!mapped) return <p className="wb-muted" role="status">{mappingWaiting(sample)}</p>;
  // A stored result is shown only while its registered mapping analysis can still be verified; a changed source keeps the record only.
  // Bound by the result's own analysis id, else its mapping attempt; an older result without either uses the sample's latest mapping.
  if (live && mapped.sampleId) {
    if (!state) return <p className="wb-muted" role="status">正在读取…</p>;
    const mappings = state.analyses ? ofKind(state.analyses, "atlas_mapping") : [];
    const registered = mappings.find(a => a.id === mapped.analysisId) ?? mappings.find(a => a.assessment_id === mapped.assessmentId)
      ?? (mapped.analysisId ? undefined : mappings[0]);
    if (registered?.availability.status === "unavailable") return <SourceGoneNote what="映射" />;
  }
  const fraction = mapped.mapping ? null : targetFraction(mapped.chain);
  return <>
    {tree && <div className="wb-mini-tree">
      {tree("mini", sample)}
      <button className="wb-chip wb-mini-expand" onClick={onFull}>展开发育树</button>
    </div>}
    {mapped.mapping ? <MappingLens sample={mapped} onTree={onTree(mapped)} inline />
      : <div className="wb-example-lens">
        <span className="wb-lens-pct">{fraction === null ? "—" : <>{Math.round(fraction * 100)}<sup>%</sup></>}</span>
        <span className="wb-muted">是你要的细胞（示例）</span>
        <ChainRings values={mapped.chain} />
      </div>}
  </>;
}

/** A sampling point's analyses, slid in beside the protocol flow so the day it was taken stays in view. */
export function SamplePanel({ protocol, sample, tab, onTab, state, onClose, live, ops, tree, onTree, batches, onBatch }: Props) {
  const [full, setFull] = useState(false);
  /** A QC picked in the records; otherwise the most recently registered one is shown. */
  const [qcId, setQcId] = useState<string | null>(null);
  const [cycleId, setCycleId] = useState<string | null>(null);
  const root = useRef<HTMLElement>(null);
  // Escape closes the full tree first, then the panel.
  useEffect(() => {
    const key = (event: KeyboardEvent) => { if (event.key !== "Escape") return; if (full) setFull(false); else onClose(); };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onClose, full]);
  const mapped = resultOf(protocol, sample);
  const tabs: [AnalysisTab, string][] = live ? [["mapping", "映射"], ["qc", "QC"], ["records", "记录"]] : [["mapping", "映射"]];
  // Doublets need a declared capture batch; a sample declared without one can add it from its QC.
  const onCapture = ops && sample.declaration && !sample.declaration.capture_id && !sample.declaration.capture_id_column
    ? async (capture: Parameters<RunOps["addCapture"]>[1]) => (await ops.addCapture(sample, capture)).notice : undefined;
  // The full tree covers the whole stage, not just the panel.
  const stage = root.current?.closest(".wb-stage");
  return <aside ref={root} className="wb-panel" aria-label={`D${sample.day} 样本`}>
    <header className="wb-panel-head">
      <div>
        <span className="wb-panel-day">D{sample.day} · {sample.assay}</span>
        <span className={`wb-panel-state wb-panel-state--${sample.status}`}>{STATUS[sample.status]}</span>
      </div>
      <button className="wb-link" onClick={onClose} aria-label="关闭样本">×</button>
    </header>
    {batches && batches.length > 1 && onBatch && <BatchSwitch batches={batches} current={sample.id} onPick={onBatch} />}
    {ops && protocol.run && <SampleActions protocol={protocol} sample={sample} ops={ops} />}
    <nav className="wb-atabs" aria-label="分析">
      {tabs.map(([id, label]) => <button key={id} aria-pressed={tab === id} onClick={() => onTab(id)}>
        {label}{id === "mapping" && sample.status === "mapping" && <span className="wb-atabs-busy">进行中</span>}
        {id === "records" && state?.analyses && <span className="wb-atabs-count">{state.analyses.length}</span>}</button>)}
    </nav>
    <div className="wb-panel-body">
      {tab === "mapping" && <MappingTab sample={sample} mapped={mapped} tree={tree} onTree={onTree} onFull={() => setFull(true)} state={state} live={live} />}
      {tab === "qc" && <QcTab sample={sample} state={state} picked={qcId} pickedCycle={cycleId} onCapture={onCapture} />}
      {tab === "records" && <RecordsTab sample={sample} state={state}
        onOpen={a => { if (a.source_kind === "sample_qc") { setQcId(a.id); onTab("qc"); }
          else if (a.source_kind === "sample_cell_cycle") { setCycleId(a.id); onTab("qc"); }
          else if (a.source_kind === "sample_cell_atlas") onTab("qc"); else onTab("mapping"); }} />}
    </div>
    {full && tree && stage && createPortal(<div className="wb-tree-full" role="dialog" aria-label={`D${sample.day} 发育树`}>
      {tree("full", sample, () => setFull(false))}
      <button className="wb-chip wb-tree-full-back" onClick={() => setFull(false)}>← 返回方案图</button>
    </div>, stage)}
  </aside>;
}
