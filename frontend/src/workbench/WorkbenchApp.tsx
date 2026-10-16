import { useEffect, useRef, useState, type ReactNode } from "react";
import { ConversationDock, type DockMessage } from "./ConversationDock";
import { Incubator } from "./Incubator";
import { DevTreeView } from "./DevTreeView";
import { NewProtocolDialog } from "./NewProtocolDialog";
import { ProtocolFlow } from "./ProtocolFlow";
import { RunBar } from "./RunBar";
import { SamplePanel } from "./SamplePanels";
import { dayKey, dayOf, samplingPoints, useManyAnalyses, useSampleAnalyses, type LoadAnalyses } from "./analyses";
import { BatchPanel } from "./BatchPanel";
import { onThisTree } from "./treeFlow";
import type { DevTree, MarkerPanel, Protocol, ProtocolOps, QueueItem, RunOps, Sample, SampleRecord } from "./types";
import type { AnalysisTab, WorkbenchLocation, WorkbenchView } from "../routes";
import "./workbench.css";
import { CellLogo } from "../components/CellLogo";

type Props = {
  userName: string; researchName: string; protocols: Protocol[]; queue: QueueItem[]; tree: DevTree;
  /** Replies for the standalone preview; the integrated app routes questions to the session Agent instead. */
  respond: (question: string, context: { protocol: Protocol | null; sample: number | null }) => Omit<DockMessage, "id" | "from">;
  previewLabel?: string;
  onReports?: () => void;
  /** Extra rail entries supplied by the host app, such as conversations and all researches. */
  railExtras?: { id: string; label: string; onClick: () => void }[];
  /** Account control for the rail's bottom row (opens settings); a plain name when absent. */
  account?: ReactNode;
  /** Routes free-text questions to the session Agent; when absent the preview answers locally. */
  onQuestion?: (text: string) => Promise<void> | void;
  /** Host supplies the existing bound Agent conversation, inside the workbench. */
  renderConversation?: (protocol: Protocol | null, question: { id: number; text: string } | null) => ReactNode;
  /** Confirms or declines a queued action on the server; absent in example mode. */
  onDecide?: (id: string, decision: "approve" | "decline") => Promise<void>;
  /** Server protocol operations; absent in example mode. */
  protocolOps?: ProtocolOps;
  /** Server run and sample operations; absent in example mode. */
  runOps?: RunOps;
  /** Reads stored marker expression for colouring the tree by gene; present only with live objects. */
  loadMarkers?: (assessmentId: string, signal: AbortSignal) => Promise<MarkerPanel>;
  /** Reads every analysis registered for a sample (QC, mapping, session results); present only with live objects. */
  loadAnalyses?: LoadAnalyses;
  /** Opens at this place and follows it when it changes, such as on browser back. */
  location?: WorkbenchLocation;
  /** Reports every move between the incubator, the comparison and a run's protocol or results. */
  onLocate?: (at: WorkbenchLocation) => void;
};

/**
 * A batch's name: its declared capture, else its data file without the extension, else its place among that day's batches.
 */
function batchLabel(point: SampleRecord, index: number, materials?: { id: string; name: string }[]) {
  const file = materials?.find(m => m.id === point.materialId)?.name.replace(/\.(h5ad|h5|loom|rds)$/i, "");
  return point.declaration?.capture_id ?? file ?? `批次 ${index + 1}`;
}

export function WorkbenchApp({ userName, researchName, protocols: initial, queue, tree, respond, previewLabel, onReports, railExtras = [], account, onQuestion, renderConversation, onDecide, protocolOps, runOps, loadMarkers, loadAnalyses, location, onLocate }: Props) {
  const [protocols, setProtocols] = useState(initial);
  useEffect(() => { setProtocols(initial); }, [initial]);
  const [queuedQuestion, setQueuedQuestion] = useState<{ id: number; text: string; focus: string } | null>(null);
  const [creating, setCreating] = useState(false);
  const [view, setView] = useState<WorkbenchView>(location?.view ?? "wall");
  const [focusId, setFocusId] = useState<string | null>(location?.focus ?? null);
  /** The sampling point whose panel is open beside the flow, and the analysis it shows; no sample means the panel is closed. */
  const [sampleId, setSampleId] = useState<string | null>(location?.sample ?? null);
  const [analysis, setAnalysis] = useState<AnalysisTab | null>(location?.analysis ?? null);
  useEffect(() => {
    if (!location) return;
    setView(location.view); setFocusId(location.focus); setSampleId(location.sample ?? null); setAnalysis(location.analysis ?? null);
  }, [location?.view, location?.focus, location?.sample, location?.analysis]);
  const report = useRef(onLocate);
  report.current = onLocate;

  const [messages, setMessages] = useState<DockMessage[]>([{ id: 0, from: "bridge", text: "这里会记下你和 BRIDGE 的每一次讨论。" }]);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [localNotice, setLocalNotice] = useState<string | null>(null);
  const nextId = useRef(1);
  const focus = protocols.find(p => p.id === focusId) ?? null;
  const points = focus && (focus.run || focus.samples.length) ? samplingPoints(focus) : [];
  // A day with several batches opens on all of them together; one batch, or a day with a single one, opens its own panel.
  const day = view === "plan" ? dayOf(sampleId) : null;
  const dayPoints = day !== null ? points.filter(p => p.day === day) : [];
  const sample = view === "plan" ? points.find(r => r.id === sampleId) ?? (dayPoints.length === 1 ? dayPoints[0] : null) : null;
  const siblings = sample ? points.filter(p => p.day === sample.day) : dayPoints;
  const labels = Object.fromEntries(points.map(p => [p.id, batchLabel(p, points.filter(q => q.day === p.day).indexOf(p), runOps?.materials)]));
  const batches = siblings.map(p => ({ id: p.id, label: labels[p.id] }));
  const allBatches = useManyAnalyses(loadAnalyses, !sample && dayPoints.length > 1 ? dayPoints : []);
  /** A day clicked on the flow's day axis, handed to the run bar's sample registration. */
  const [addAt, setAddAt] = useState<{ key: number; day: number } | null>(null);
  const tab: AnalysisTab = analysis ?? (sample?.mapping === "done" || !loadAnalyses ? "mapping" : "qc");
  const results = useSampleAnalyses(sample?.id.startsWith("example-") ? undefined : loadAnalyses, sample);
  useEffect(() => {
    report.current?.({ view, focus: focusId, ...(view === "plan" && sampleId ? { sample: sampleId, ...(analysis ? { analysis } : {}) } : {}) });
  }, [view, focusId, sampleId, analysis]);
  /** Opens a sampling point's panel; a different point starts on its own default analysis. */
  const pickSample = (record: SampleRecord | null) => {
    if (record?.id !== sampleId) setAnalysis(null);
    setSampleId(record?.id ?? null);
  };
  // A run picked on the comparison tree opens on its flow with that day's mapping.
  const treeSample = (_: string, opened: Sample) => {
    if (view !== "compare" || !opened.sampleId) return;
    setSampleId(opened.sampleId); setAnalysis("mapping");
  };
  /** Routes the tree's "why" and "next" questions to the bound conversation, or answers them locally in the preview. */
  const askAbout = (kind: "why" | "next", protocol: Protocol, index: number) => {
    if (!renderConversation) { ask(kind === "why" ? "为什么？" : "下一版怎么改？", index); return; }
    setFocusId(protocol.id);
    setQueuedQuestion({ id: nextId.current++, focus: protocol.id,
      text: `请结合这次实验 D${protocol.samples[index].day} 的已登记资料，${kind === "why" ? "解释目前的观察和证据缺口。" : "讨论下一版方案可以核查的方向，不直接修改方案。"}` });
  };
  /** The focused run's tree opened on one day: a small preview in the sample panel or the full tree; days picked inside follow the panel. */
  const runTree = (mode: "mini" | "full", point: SampleRecord, back?: () => void) => <DevTreeView key={mode} compact={mode === "mini"} tree={tree} protocols={protocols} focus={focus}
    onFocus={() => undefined} openDay={{ key: 1, day: point.day, ...(point.id.startsWith("example-") ? {} : { sampleId: point.id }) }} loadMarkers={loadMarkers} onAsk={askAbout}
    onSample={(_, picked) => { if (picked.sampleId && picked.sampleId !== sampleId) setSampleId(picked.sampleId); }}
    onOpenProtocol={() => back?.()} />;
  const say = (from: "me" | "bridge", body: Omit<DockMessage, "id" | "from">) =>
    setMessages(list => [...list, { id: nextId.current++, from, ...body }]);
  const notice = (text: string) => {
    if (renderConversation) setLocalNotice(text);
    else { say("bridge", { text }); setSheetOpen(true); }
  };
  const ask = (text: string, sample: number | null = null) => {
    say("me", { text }); say("bridge", respond(text, { protocol: focus, sample })); setSheetOpen(true);
  };
  const question = async (text: string) => {
    if (!onQuestion) { ask(text); return; }
    say("me", { text }); say("bridge", { text: "正在交给 BRIDGE…" }); setSheetOpen(true);
    try { await onQuestion(text); }
    catch (failure) { say("bridge", { text: failure instanceof Error ? failure.message : "没有发送成功，请重试。" }); }
  };
  const open = (id: string) => {
    const protocol = protocols.find(p => p.id === id);
    setFocusId(id);
    if (protocol && protocol.state === "draft" && !protocol.reagents.length) {
      setView("plan");
      notice(`${protocol.name} 还没有方案。把方案文档拖进来，我先把它画成方案图。`);
    } else setView("plan");
    setSampleId(null); setAnalysis(null);
  };
  // A focus that is not loaded yet (just created on the server) shows nothing rather than another protocol.
  const planTarget = focus ?? (focusId ? null : protocols.find(p => p.reagents.length) ?? null);
  const page = view === "plan" ? planTarget : null;
  const nav: { id: WorkbenchView; label: string }[] = [{ id: "wall", label: "培养箱" }, { id: "compare", label: "比较" }];
  return <div className="wb-app">
    <aside className="wb-rail" aria-label="研究导航">
      <div className="wb-brand"><CellLogo size={30} />
        <div><b>BRIDGE</b><small>体内 ⇄ 体外</small></div></div>
      <button className="wb-new" onClick={() => {
        if (protocolOps) { setCreating(true); return; }
        const id = `new-${nextId.current++}`;
        setProtocols(list => [{ id, name: "新的分化", version: 1, state: "draft", day: 0, totalDays: 28, today: "上传方案", reagents: [], samples: [] }, ...list]);
        open(id); setView("wall");
      }}>＋ 新的分化</button>
      <p className="wb-label">研究</p>
      <nav className="wb-nav"><button aria-current="true">{researchName}<span>{protocols.length}</span></button></nav>
      <p className="wb-label">视图</p>
      <nav className="wb-nav" aria-label="视图">
        {nav.map(item => <button key={item.id} aria-current={view === item.id || (item.id === "wall" && !!page)}
          onClick={() => { if (item.id === "compare") setFocusId(null); setView(item.id); }}>{item.label}</button>)}
        <button disabled={!onReports} title={onReports ? undefined : "即将接入"} onClick={onReports}>报告</button>
      </nav>
      {railExtras.length > 0 && <nav className="wb-nav" aria-label="更多">
        {railExtras.map(item => <button key={item.id} onClick={item.onClick}>{item.label}</button>)}
      </nav>}
      {account ?? <div className="wb-me"><span className="wb-avatar">{userName.slice(0, 2).toUpperCase()}</span><span>{userName}</span></div>}
    </aside>
    <main className="wb-main">
      {previewLabel && <p className="wb-preview-label">{previewLabel}</p>}
      {view === "wall" && <Incubator userName={userName} protocols={protocols} queue={queue} onOpen={open} onDecide={onDecide} onCreate={protocolOps ? () => setCreating(true) : undefined} />}
      {view !== "wall" && <div className="wb-stage">
        {page && <div className="wb-pagehead">
          <nav className="wb-crumb" aria-label="位置">
            <button onClick={() => setView("wall")}>培养箱</button><span aria-hidden="true">›</span>
            <span aria-current="page">{page.name}</span>
          </nav>
        </div>}
        {runOps && page?.run && <RunBar protocol={page} ops={runOps} addAt={page === focus ? addAt : null} />}
        {view === "compare" && <DevTreeView tree={tree} protocols={protocols} focus={null}
          onFocus={id => { setFocusId(id); if (id) setView("plan"); }} onSample={treeSample} loadMarkers={loadMarkers}
          onOpenProtocol={id => { setFocusId(id); setView("plan"); }}
          onAsk={askAbout} />}
        {view === "plan" && planTarget && <ProtocolFlow key={planTarget.id} protocol={planTarget} others={protocols.filter(p => p.id !== planTarget.id)}
          ops={protocolOps} runOps={runOps} onOpenVersion={id => { setFocusId(id); setView("plan"); }}
          sampling={planTarget === focus && points.length + (runOps && focus?.run ? 1 : 0) > 0 ? {
            points, selected: sample?.id ?? sampleId, onPick: point => pickSample(point.id === sampleId ? null : point), labels,
            onPickDay: picked => { setAnalysis(null); setSampleId(current => current === dayKey(picked) ? null : dayKey(picked)); },
            onAdd: runOps && focus?.run ? day => setAddAt({ key: nextId.current++, day }) : undefined,
          } : undefined}
          onDraft={draft => { setProtocols(list => [draft, ...list]); notice(`已生成「${draft.name}」，在培养箱上标为草稿。请核对剂量和天数后再开始。`); }} />}
        {view === "plan" && focus && sample && <SamplePanel key={sample.id} protocol={focus} sample={sample} tab={tab} onTab={setAnalysis} state={results}
          live={!!loadAnalyses && !sample.id.startsWith("example-")} ops={runOps} onClose={() => pickSample(null)} tree={runTree}
          onTree={s => onThisTree(s, tree)} batches={batches}
          onBatch={id => { setAnalysis(null); setSampleId(id === "all" ? dayKey(sample.day) : id); }} />}
        {view === "plan" && focus && !sample && day !== null && dayPoints.length > 1 && <BatchPanel key={dayKey(day)} protocol={focus} day={day}
          batches={batches} points={dayPoints} analyses={allBatches} onClose={() => pickSample(null)}
          onPick={id => { setAnalysis(null); setSampleId(id === "all" ? dayKey(day) : id); }} />}
        {!renderConversation && <ConversationDock messages={messages} open={sheetOpen} onOpenChange={setSheetOpen} onSend={text => void question(text)} />}
      </div>}
      {renderConversation && localNotice && <p className="wb-preview-label" role="status">{localNotice}</p>}
      {renderConversation?.(view === "wall" ? null : focus,
        view !== "wall" && queuedQuestion?.focus === focus?.id ? queuedQuestion : null)}
    </main>
    {protocolOps && <NewProtocolDialog open={creating} onClose={() => setCreating(false)}
      onCreate={async name => { const id = await protocolOps.createManual(name); setFocusId(id); setView("plan"); }}
      onUpload={async file => {
        const result = await protocolOps.importDocument(file);
        setFocusId(result.viewId); setView("plan");
        if (result.notice) notice(result.notice);
      }} />}
  </div>;
}
