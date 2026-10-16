import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type DragEvent as ReactDragEvent, type PointerEvent as ReactPointerEvent } from "react";
import { compound, structureUrl, suggestPathway, type Compound } from "./catalog";
import { COMPOUND_DRAG, MoleculeLibrary } from "./MoleculeLibrary";
import { categoryIcon } from "./icons";
import { ReagentEditor } from "./ReagentEditor";
import { ReviewChecklist } from "./ReviewChecklist";
import { SourcePane } from "./SourcePane";
import { dayKey, pointSummary } from "./analyses";
import { StageDish } from "./StageDish";
import { RecordRunCard } from "./StartRunCard";
import { SourceNotes } from "./SourceNotes";
import { CHAIN_NAMES, PATHWAYS, ROMAN, STAGE_NAMES, stageOf, weakestLevel, stageSpans } from "./stages";
import { resultOf } from "./analyses";
import { label as pointLabel, tone as pointTone } from "./RunBar";
import type { Protocol, ProtocolOps, Reagent, ReviewItem, RunOps, SampleRecord, SourceView } from "./types";

type Props = {
  protocol: Protocol; others: Protocol[]; onDraft: (draft: Protocol) => void;
  /** Server operations; when present, drafts are edited in place and proposals become server versions. */
  ops?: ProtocolOps; onOpenVersion?: (viewId: string) => void;
  /** Records an experiment of this version; present only with live objects. */
  runOps?: RunOps;
  /** A run's sampling points on the day axis: picking one opens its panel; a day picked on the axis registers a sample there. */
  /**
   * Sampling points on the day axis. Points of the same day are the batches of that day and share one marker; picking it
   * calls `onPickDay`, while a day with one point calls `onPick`. `labels` names each point's batch.
   */
  sampling?: { points: SampleRecord[]; selected: string | null; onPick: (point: SampleRecord) => void; onPickDay?: (day: number) => void;
    onAdd?: (day: number) => void; labels?: Record<string, string> };
};
type Selection = { kind: "stage"; index: number } | { kind: "reagent"; id: string } | { kind: "new"; reagent: Reagent } | { kind: "record"; confirm: boolean } | null;
/** A treatment bar being dragged: which edge or the whole window, where the pointer started, and the window shown now. */
type Drag = { id: string; mode: "move" | "start" | "end"; x: number; width: number; start0: number; end0: number; start: number; end: number; moved: boolean };
/** A new reagent from the library, placed on a day and given a few days to start with; the editor sets the rest. */
const fromCompound = (c: Compound, day: number | null, maxDay: number): Reagent => ({
  ...NEW_REAGENT, name: c.name, short: c.name.length <= 8 ? c.name : c.name.slice(0, 6), catalogId: c.id, pathway: suggestPathway(c) ?? "other",
  start: day, end: day === null ? null : Math.min(day + 4, maxDay),
});
const NEW_REAGENT: Reagent = { id: "unsaved-new", name: "", short: "", pathway: "other", kind: "molecule", dose: "", start: 0, end: 0 };

const PRE = 3;
/** Days drawn for a window whose other end the document does not give; the bar fades out there. */
const OPEN = 5;
const spanLabel = (spans: [number, number][], i: number, maxDay: number) => i === 0 ? "分化前" : `D${spans[i][0]}–D${i < 4 ? spans[i][1] - 1 : maxDay}`;
const same = (a: Reagent, b: Reagent) => (a.catalogId && a.catalogId === b.catalogId) || a.name === b.name;
/** Treatment window as written; an unknown day is a question mark, never D0. */
export const windowText = (r: Reagent) => `D${r.start ?? "?"}–D${r.end ?? "?"}`;
const timed = (r: Reagent) => r.start !== null && r.end !== null;

function useAsset(load: () => Promise<string | undefined>, key: string) {
  const [url, setUrl] = useState<string>();
  useEffect(() => { let live = true; setUrl(undefined); void load().then(u => { if (live) setUrl(u); }); return () => { live = false; }; }, [key]);
  return url;
}

function ReagentIcon({ reagent, size }: { reagent: Reagent; size: number }) {
  const url = useAsset(async () => (await structureUrl(reagent.catalogId)) ?? categoryIcon(reagent.kind), `${reagent.catalogId}-${reagent.kind}`);
  return url ? <img className="wb-flow-icon" src={url} alt="" width={size} height={size} /> : <span className="wb-flow-icon wb-flow-icon--empty" style={{ width: size, height: size }} />;
}

/** One-line summary of a sampling point for its hover card: where most cells landed, or why there is no result yet. */

/** The sampling points under the day axis, a hover card for each, and a "+" that follows the pointer to register a new one. */
function SamplingRow({ protocol, sampling, pct, maxDay }: { protocol: Protocol; sampling: NonNullable<Props["sampling"]>; pct: (day: number) => number; maxDay: number }) {
  const [hover, setHover] = useState<string | null>(null);
  const [ghost, setGhost] = useState<number | null>(null);
  const row = useRef<HTMLDivElement>(null);
  const near = (day: number) => sampling.points.some(p => Math.abs(pct(p.day) - pct(day)) < 4);
  const dayAt = (clientX: number) => {
    const box = row.current!.getBoundingClientRect();
    const day = Math.round(((clientX - box.left) / box.width) * (maxDay + PRE) - PRE);
    return Math.max(0, Math.min(maxDay, day));
  };
  const days = useMemo(() => {
    const byDay = new Map<number, SampleRecord[]>();
    for (const p of sampling.points) byDay.set(p.day, [...(byDay.get(p.day) ?? []), p]);
    return [...byDay.entries()].sort((a, b) => a[0] - b[0]);
  }, [sampling.points]);
  const shownGroup = days.find(([day]) => dayKey(day) === hover)?.[1];
  const shown = shownGroup?.length === 1 ? shownGroup[0] : null;
  const info = shown ? pointSummary(protocol, shown) : null;
  return <div ref={row} className="wb-flow-samples" role="group" aria-label="取样点"
    onMouseMove={e => { if (!sampling.onAdd || e.target !== e.currentTarget) return; const day = dayAt(e.clientX); setGhost(near(day) ? null : day); }}
    onMouseLeave={() => setGhost(null)}>
    {sampling.onAdd && ghost !== null && <button className="wb-mark-add" style={{ left: `${pct(ghost)}%` }} onClick={() => { sampling.onAdd!(ghost); setGhost(null); }}
      aria-label={`在 D${ghost} 登记取样`}>＋ D{ghost}</button>}
    {days.map(([day, group]) => { const p = group[0], key = dayKey(day), many = group.length > 1;
      return <button key={key} className={`wb-mark wb-mark--${pointTone(p)}`} style={{ left: `${pct(day)}%` }}
        aria-pressed={sampling.selected === key || group.some(g => g.id === sampling.selected)}
        aria-label={many ? `D${day}，${group.length} 个批次` : `D${day} ${p.assay}，${pointLabel(p)}`}
        onMouseEnter={() => { setHover(key); setGhost(null); }} onMouseLeave={() => setHover(null)} onFocus={() => setHover(key)} onBlur={() => setHover(null)}
        onClick={() => many && sampling.onPickDay ? sampling.onPickDay(day) : sampling.onPick(p)}><i />D{day}{many && <em>×{group.length}</em>}</button>; })}
    {shownGroup && shownGroup.length > 1 && <div className="wb-mark-card" role="tooltip" style={{ left: `${pct(shownGroup[0].day)}%` }}>
      <b>D{shownGroup[0].day} · {shownGroup.length} 个批次</b>
      {shownGroup.map((g, i) => { const s = pointSummary(protocol, g);
        return <span key={g.id}>{sampling.labels?.[g.id] ?? `批次 ${i + 1}`}{s.cells !== null ? ` · ${s.cells.toLocaleString("en-US")} 个细胞` : ""}</span>; })}
      <small>点击对比各批次</small>
    </div>}
    {shown && info && <div className="wb-mark-card" role="tooltip" style={{ left: `${pct(shown.day)}%` }}>
      <b>D{shown.day} · {pointLabel(shown)}</b>
      {info.cells !== null && <span>{info.cells.toLocaleString("en-US")} 个细胞</span>}
      {info.lead && <span>最多落在{info.lead}</span>}
      <small>点击查看映射、QC 与记录</small>
    </div>}
  </div>;
}

export function ProtocolFlow({ protocol, others, onDraft, ops, onOpenVersion, runOps, sampling }: Props) {
  const [selection, setSelection] = useState<Selection>(null);
  // A card opened from the source text or the tray may sit below the fold; bring it into view.
  const root = useRef<HTMLElement>(null);
  useEffect(() => { if (selection) root.current?.querySelector(".wb-flow-card")?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [selection]);
  // A new draft opens against the version it came from, so what changed is visible at once.
  const [compareId, setCompareId] = useState(() => protocol.source?.status === "draft" && protocol.version > 1
    ? others.find(o => o.source?.protocolId === protocol.source?.protocolId && o.version === protocol.version - 1 && o.reagents.length)?.id ?? "" : "");
  const compareTo = others.find(p => p.id === compareId) ?? null;
  const latest = protocol.samples.at(-1);
  const weak = latest ? weakestLevel(latest.chain) : null;
  const flagged = new Set(PATHWAYS.filter(p => p.level !== null && p.level === weak).map(p => p.id));
  const proposal = weak === 3 ? new Set(protocol.reagents.filter(r => r.pathway === "shh" && r.end !== null).map(r => r.id)) : new Set<string>();
  const stage = stageOf(protocol);
  const SPANS = useMemo(() => stageSpans(protocol.stages, PRE), [protocol.stages]);
  const current = protocol.state === "differentiating" || protocol.state === "expanding" ? stage.index : null;
  const done = (i: number) => protocol.state === "frozen" || protocol.state === "grafted" || (current !== null && i < current);
  const days = (list: Reagent[]) => list.flatMap(r => [r.start, r.end]).filter((d): d is number => d !== null);
  const maxDay = Math.max(protocol.totalDays, ...days(protocol.reagents), ...days(compareTo?.reagents ?? []), ...(sampling?.points ?? []).map(p => p.day), 20);
  const pct = (day: number) => ((Math.min(day, maxDay) + PRE) / (maxDay + PRE)) * 100;
  const geometry = (r: Reagent) => {
    if (r.start !== null && r.end !== null) return { left: pct(r.start), width: Math.max(1.5, pct(r.end) - pct(r.start)), open: "" };
    if (r.start !== null) return { left: pct(r.start), width: Math.max(9, pct(Math.min(r.start + OPEN, maxDay)) - pct(r.start)), open: " wb-cap--open-end" };
    if (r.end !== null) { const from = Math.max(r.end - OPEN, 0); return { left: pct(from), width: Math.max(9, pct(r.end) - pct(from)), open: " wb-cap--open-start" }; }
    return null;
  };
  const today = protocol.state === "differentiating" ? protocol.day : protocol.state === "expanding" ? Math.max(-PRE, protocol.day) : null;
  const rows = useMemo(() => {
    const own = PATHWAYS.flatMap(p => protocol.reagents.filter(r => r.pathway === p.id)).map(r => ({ r, ghost: compareTo?.reagents.find(o => same(o, r)), other: false }));
    const extra = (compareTo?.reagents ?? []).filter(o => !protocol.reagents.some(r => same(r, o))).map(r => ({ r, ghost: undefined, other: true }));
    return [...own, ...extra];
  }, [protocol, compareTo]);
  // One lane per factor: entries of the same compound whose days do not overlap share a lane, so a dose change
  // (SHH 500 → 100 → 20 ng/mL) reads along one row as in a protocol diagram; overlapping entries keep their own lanes.
  const lanes = useMemo(() => {
    const out: { key: string; items: typeof rows }[] = [];
    for (const row of rows) {
      const key = `${row.other ? "o" : "s"}:${row.r.catalogId ?? row.r.name.trim().toLowerCase()}`;
      const lo = row.r.start ?? row.r.end, hi = row.r.end ?? row.r.start;
      const lane = lo === null || hi === null ? undefined : out.find(l => l.key === key && l.items.every(({ r }) => {
        const a = r.start ?? r.end, b = r.end ?? r.start;
        return a !== null && b !== null && (hi < a || lo > b);
      }));
      if (lane) lane.items.push(row); else out.push({ key, items: [row] });
    }
    for (const lane of out) lane.items.sort((a, b) => (a.r.start ?? a.r.end ?? 0) - (b.r.start ?? b.r.end ?? 0));
    return out;
  }, [rows]);
  const tray = rows.filter(row => !row.other && row.r.start === null && row.r.end === null).map(row => row.r);
  const active = selection?.kind === "stage" ? SPANS[selection.index] : null;
  const picked = selection?.kind === "reagent" ? rows.find(row => (row.other ? `o-${row.r.id}` : row.r.id) === selection.id) ?? null : null;
  const info = compound(picked?.r.catalogId);
  const editable = !!ops && protocol.source?.status === "draft";
  // A confirmed version is changed through its next draft, so its own record and experiments stay as they were.
  const changeable = !!ops && !!protocol.source;
  const pending = protocol.reagents.filter(r => r.unconfirmed?.length).length;
  const noDose = protocol.reagents.filter(r => !r.dose.trim()).length;
  const untimed = protocol.reagents.filter(r => !timed(r)).length;
  const review = protocol.source?.review ?? [];
  const confirmBlock = !protocol.source?.totalDaysSet ? "先填写总天数" : !protocol.reagents.length ? "先添加试剂"
    : untimed ? `还有 ${untimed} 个试剂时间未定` : noDose ? `还有 ${noDose} 个试剂没填剂量` : pending ? `还有 ${pending} 项待核对`
    : review.length ? `整份方案还有 ${review.length} 项待核对` : "";
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const act = async (work: () => Promise<void | string>) => {
    setBusy(true); setNotice("");
    try { const next = await work(); if (typeof next === "string") onOpenVersion?.(next); }
    catch (failure) { setNotice(failure instanceof Error ? failure.message : "没有完成，请重试。"); }
    finally { setBusy(false); }
  };
  const replace = (list: Reagent[]) => ops!.saveDraft(protocol, { reagents: list });
  /** Saves a changed reagent list: in place on a draft, or as the next draft of a confirmed version, which then opens. */
  const saveReagents = async (list: Reagent[], note: string) => {
    if (editable) { await replace(list); return; }
    const id = await ops!.newVersion(protocol, { reagents: list, changeNote: note });
    setNotice(""); onOpenVersion?.(id);
  };
  const [library, setLibrary] = useState(false);
  const [drag, setDrag] = useState<Drag | null>(null);
  const dragged = useRef(false);
  const dayDelta = (dx: number, width: number) => Math.round((dx / width) * (maxDay + PRE));
  const startDrag = (event: ReactPointerEvent<HTMLButtonElement>, r: Reagent) => {
    if (!changeable || busy || r.start === null || r.end === null || event.button !== 0) return;
    const box = event.currentTarget.getBoundingClientRect(), lane = event.currentTarget.parentElement!.getBoundingClientRect();
    const edge = Math.min(10, box.width / 4), offset = event.clientX - box.left;
    const mode = offset < edge ? "start" : offset > box.width - edge ? "end" : "move";
    event.currentTarget.setPointerCapture?.(event.pointerId);
    dragged.current = false;
    setDrag({ id: r.id, mode, x: event.clientX, width: lane.width, start0: r.start, end0: r.end, start: r.start, end: r.end, moved: false });
  };
  const moveDrag = (event: ReactPointerEvent) => {
    if (!drag) return;
    const d = dayDelta(event.clientX - drag.x, drag.width), span = drag.end0 - drag.start0;
    const next = drag.mode === "move" ? { start: Math.max(0, Math.min(maxDay - span, drag.start0 + d)), end: 0 }
      : drag.mode === "start" ? { start: Math.max(0, Math.min(drag.end0, drag.start0 + d)), end: drag.end0 }
      : { start: drag.start0, end: Math.max(drag.start0, Math.min(maxDay, drag.end0 + d)) };
    if (drag.mode === "move") next.end = next.start + span;
    if (next.start !== drag.start || next.end !== drag.end) setDrag({ ...drag, ...next, moved: true });
  };
  const endDrag = () => {
    if (!drag) return;
    const r = protocol.reagents.find(x => x.id === drag.id);
    setDrag(null);
    if (!r || !drag.moved || (drag.start === drag.start0 && drag.end === drag.end0)) return;
    dragged.current = true;
    const list = protocol.reagents.map(x => x.id === r.id ? { ...x, start: drag.start, end: drag.end } : x);
    void act(() => saveReagents(list, `${r.name} 改为 D${drag.start}–D${drag.end}`));
  };
  // A compound dragged from the library shows the day it would start on; dropping it opens the editor on that day.
  // Days are read against the day axis, so a protocol without any reagent yet accepts a drop too.
  const [dropAt, setDropAt] = useState<{ day: number; x: number; top: number; bottom: number } | null>(null);
  const dropDay = (clientX: number) => {
    const axis = root.current?.querySelector(".wb-flow-track")?.getBoundingClientRect(), area = root.current?.getBoundingClientRect();
    if (!axis || !area) return null;
    const day = Math.max(0, Math.min(maxDay, Math.round(((clientX - axis.left) / axis.width) * (maxDay + PRE) - PRE)));
    return { day, x: axis.left + (pct(day) / 100) * axis.width, top: axis.top, bottom: Math.min(area.bottom, axis.top + 420) };
  };
  const dropProps = changeable ? {
    onDragOver: (e: ReactDragEvent) => {
      if (!e.dataTransfer.types.includes(COMPOUND_DRAG)) return;
      if ((e.target as Element).closest?.(".wb-lib")) { setDropAt(null); return; } e.preventDefault(); e.dataTransfer.dropEffect = "copy"; setDropAt(dropDay(e.clientX)); },
    onDragLeave: (e: ReactDragEvent) => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDropAt(null); },
    onDrop: (e: ReactDragEvent) => {
      const c = compound(e.dataTransfer.getData(COMPOUND_DRAG)), at = dropDay(e.clientX);
      setDropAt(null);
      if (!c || !at || (e.target as Element).closest?.(".wb-lib")) return;
      e.preventDefault();
      setSelection({ kind: "new", reagent: fromCompound(c, at.day, maxDay) });
    },
  } : {};
  const extended = protocol.reagents.map(r => proposal.has(r.id) && r.end !== null ? { ...r, end: r.end + 2 } : r);

  // Opening a protocol shows its flow only; the original text opens beside it on demand, from a reagent's details
  // or the review checklist, and is read the first time it is opened.
  const hasSource = !!protocol.source?.hasSource && !!ops?.formalization;
  const [showSource, setShowSource] = useState(false);
  const [source, setSource] = useState<SourceView | null | undefined>(undefined);
  const [sourceSeen, setSourceSeen] = useState(false);
  const [tab, setTab] = useState<"flow" | "source">("flow");
  const versionId = protocol.source?.versionId;
  useEffect(() => { setShowSource(false); setTab("flow"); }, [versionId]);
  useEffect(() => {
    if (!hasSource || !showSource) return;
    let live = true;
    setSource(undefined);
    ops!.formalization!(protocol).then(view => { if (live) setSource(view); }, () => { if (live) setSource(null); });
    return () => { live = false; };
  }, [hasSource, versionId, showSource]); // eslint-disable-line react-hooks/exhaustive-deps
  const openSource = () => { setShowSource(true); setTab("source"); };
  const closeSource = () => { setShowSource(false); setTab("flow"); };
  const markSeen = useCallback(() => setSourceSeen(true), []);
  // On narrow screens the text is behind a tab, so it only counts as seen once that tab has been opened.
  const [sourceOpened, setSourceOpened] = useState(false);
  useEffect(() => { if (tab === "source") setSourceOpened(true); }, [tab]);
  const narrow = typeof window !== "undefined" && !!window.matchMedia?.("(max-width: 860px)").matches;
  const seen = sourceSeen && (!narrow || sourceOpened);
  const pickByName = (name: string) => {
    const hit = protocol.reagents.find(r => r.name.toLowerCase() === name.toLowerCase());
    if (hit) { setSelection({ kind: "reagent", id: hit.id }); setTab("flow"); }
  };
  const clearReview = (item: ReviewItem) => void act(() => ops!.saveDraft(protocol, { review: review.filter(x => x !== item) }));

  const draft = () => ops ? void act(() => ops.newVersion(protocol, { reagents: extended, changeNote: "延长 SHH 通路处理窗口 2 天" })) : onDraft({
    ...protocol, id: `${protocol.id}-v${protocol.version + 1}-${Date.now().toString(36)}`, name: `${protocol.name.split(" · ")[0].replace(/ v\d+$/, "")} v${protocol.version + 1} 草案`,
    version: protocol.version + 1, state: "draft", day: 0, today: "核对后开始", lead: undefined, samples: [],
    reagents: extended,
  });

  const flow = <section ref={root} className="wb-flow" aria-label={`${protocol.name} 方案图`} {...dropProps}>
    <header className="wb-flow-head">
      <h1>{protocol.name}</h1>
      {weak !== null && <span className="wb-chip wb-chip--warn" role="status" title={`D${latest!.day} 的${CHAIN_NAMES[weak]}偏低`}>{CHAIN_NAMES[weak]}偏低</span>}
      {protocol.source && <span className={protocol.source.status === "draft" ? "wb-chip wb-chip--draft" : "wb-chip"}>第 {protocol.version} 版 · {protocol.source.status === "draft" ? "草稿" : "已确认"}</span>}
      <span className="wb-flow-tools">
        {editable && <label className="wb-chip wb-chip--select"><span>共</span>
          <input id="wb-total-days" type="number" min={1} step={1} aria-label="总天数" defaultValue={protocol.source?.totalDaysSet ? protocol.totalDays : ""} disabled={busy}
            onBlur={e => { const v = Number(e.target.value); if (Number.isInteger(v) && v > 0 && v !== protocol.totalDays) void act(() => ops!.saveDraft(protocol, { totalDays: v })); }} /><span>天</span></label>}
        {changeable && <button className="wb-chip" onClick={() => setLibrary(true)} disabled={busy} aria-expanded={library}
          title={editable ? undefined : "加入后生成下一版草稿，这一版不变"}>＋ 试剂</button>}
        {editable && (runOps
          ? <button className="wb-run" disabled={busy || !!confirmBlock} title={confirmBlock || "确认方案，同时记下这次实验"} onClick={() => setSelection({ kind: "record", confirm: true })}>确认并记录</button>
          : <button className="wb-run" disabled={busy || !!confirmBlock} title={confirmBlock || undefined} onClick={() => void act(() => ops!.confirm(protocol))}>确认方案</button>)}
        {runOps && protocol.source?.status === "confirmed" && !protocol.run && <button className="wb-run" disabled={busy} onClick={() => setSelection({ kind: "record", confirm: false })}>记录实验</button>}
        {runOps && protocol.run && <button className="wb-chip" disabled={busy} onClick={() => setSelection({ kind: "record", confirm: false })} title="按同一版方案再做一次，例如换细胞系">再做一批</button>}
        {ops && protocol.source?.status === "confirmed" && <button className="wb-chip" disabled={busy} onClick={() => void act(() => ops.newVersion(protocol))}>新建下一版</button>}
        {proposal.size > 0 && <button className="wb-chip wb-chip--action" onClick={draft} title="按虚线方向生成下一版草案，剂量与天数由你确定">生成下一版草案</button>}
        <label className="wb-chip wb-chip--select"><span>对比</span>
          <select id="wb-compare" value={compareId} onChange={e => setCompareId(e.target.value)} aria-label="对比">
            <option value="">无</option>
            {others.filter(o => o.reagents.length).map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
        </label>
      </span>
    </header>

    {notice && <p className="wb-error" role="alert">{notice}</p>}
    {editable && <ReviewChecklist protocol={protocol} sourceSeen={seen} busy={busy} onClear={clearReview} onOpenSource={hasSource ? openSource : undefined} />}
    {editable && !protocol.reagents.length && <p className="wb-flow-empty">还没有试剂。点「＋ 试剂」开始录入。</p>}
    <div className="wb-flow-journey">
      {SPANS.map(([from, to], i) => {
        const end = Math.min(to, maxDay), left = pct(from), width = pct(end) - left, now = current === i;
        return <button key={i} className={`wb-node${now ? " wb-node--now" : ""}${done(i) ? " wb-node--done" : ""}${selection?.kind === "stage" && selection.index === i ? " wb-node--on" : ""}`}
          style={{ left: `${left}%`, width: `${width}%` } as CSSProperties} onClick={() => setSelection(selection?.kind === "stage" && selection.index === i ? null : { kind: "stage", index: i })}
          aria-label={`${i ? `Stage ${ROMAN[i]} ` : ""}${STAGE_NAMES[i]}，${spanLabel(SPANS, i, maxDay)}${now ? "，当前阶段" : ""}`} aria-pressed={selection?.kind === "stage" && selection.index === i}>
          <span className="wb-node-dish"><StageDish stage={i} size={now ? 84 : 56} keyId={`${protocol.id}-${i}`} live={now} /></span>
          <span className="wb-node-roman">{i ? ROMAN[i] : "扩增"}</span>
        </button>;
      })}
    </div>
    <div className="wb-flow-track" aria-hidden="true">
      <span className="wb-flow-fill" style={{ width: `${today === null ? (done(4) ? 100 : 0) : pct(today)}%` }} />
      {SPANS.slice(1).map(([from]) => from).filter(d => d < maxDay).map(d => <span key={d} className="wb-flow-tick" style={{ left: `${pct(d)}%` }}>D{d}</span>)}
      {today !== null && <span className="wb-flow-today" style={{ left: `${pct(today)}%` }}><b>D{today}</b></span>}
    </div>

    {sampling && <SamplingRow protocol={protocol} sampling={sampling} pct={pct} maxDay={maxDay} />}

    {changeable && !editable && <p className="wb-muted wb-flow-hint">拖动试剂条可改天数，改动会生成下一版草稿，这一版和它的实验记录不变。</p>}
    {dropAt && <div className="wb-flow-drop" aria-hidden="true" style={{ left: dropAt.x, top: dropAt.top, height: dropAt.bottom - dropAt.top }}><b>D{dropAt.day}</b></div>}
    <ul className={`wb-flow-rows${dropAt ? " wb-flow-rows--drop" : ""}`}>
      {lanes.map(({ key, items }) => {
        const shown = items.filter(({ r, other }) => geometry(drag && drag.id === r.id && !other ? { ...r, start: drag.start, end: drag.end } : r));
        if (!shown.length) return null;
        const first = shown[0];
        const dimLane = shown.every(({ r }) => { const lo = r.start ?? r.end!, hi = r.end ?? r.start!; return active ? hi <= Math.max(active[0], 0) || lo >= active[1] : false; });
        return <li key={key} className={`wb-flow-row${dimLane ? " wb-flow-row--dim" : ""}${flagged.has(first.r.pathway) && !first.other ? " wb-flow-row--flag" : ""}`}>
          <ReagentIcon reagent={first.r} size={26} />
          <span className="wb-flow-lane">
            {shown.map(({ r, ghost, other }, segment) => {
              const live = drag && drag.id === r.id && !other ? { ...r, start: drag.start, end: drag.end } : r;
              const shape = geometry(live);
              if (!shape) return null;
              const id = other ? `o-${r.id}` : r.id;
              const ghostShown = ghost && timed(ghost) ? ghost : undefined;
              const diff = other ? "仅对比方案" : ghostShown && (ghostShown.start !== r.start || ghostShown.end !== r.end) ? "窗口不同" : ghost && ghost.dose !== r.dose ? "剂量不同" : "";
              const unknown = r.start === null ? "开始天未写明" : r.end === null ? "结束天未写明" : "";
              // On a shared lane every segment names its dose; the first also names the factor.
              const label = shown.length > 1 ? `${segment ? "" : `${r.short} `}${(r.dose || "?").split(/\s+/)[0]}` : r.short;
              return <Fragment key={id}>
                {ghostShown && <span className="wb-flow-ghost" style={{ left: `${pct(ghostShown.start!)}%`, width: `${pct(ghostShown.end!) - pct(ghostShown.start!)}%` }} />}
                {proposal.has(r.id) && r.end !== null && <span className="wb-flow-proposal" style={{ left: `${pct(r.end)}%`, width: `${pct(r.end + 2) - pct(r.end)}%` }} />}
                <button className={`wb-cap wb-cap--${r.pathway}${shape.width < 4 ? " wb-cap--narrow" : ""}${shape.open}${other ? " wb-cap--extra" : ""}${r.unconfirmed?.length && !other ? " wb-cap--unconfirmed" : ""}${selection?.kind === "reagent" && selection.id === id ? " wb-cap--on" : ""}${changeable && !other && timed(r) ? " wb-cap--drag" : ""}${drag?.id === r.id ? " wb-cap--dragging" : ""}`}
                  style={{ left: `${shape.left}%`, width: `${shape.width}%` }}
                  onPointerDown={other ? undefined : e => startDrag(e, r)} onPointerMove={moveDrag} onPointerUp={endDrag} onPointerCancel={() => setDrag(null)}
                  onClick={() => { if (dragged.current) { dragged.current = false; return; } setSelection({ kind: "reagent", id }); }}
                  aria-label={`${r.name} ${r.dose || "剂量未写明"}，${windowText(r)}${unknown ? `，${unknown}` : ""}${diff ? `，${diff}` : ""}${r.unconfirmed?.length && !other ? "，待核对" : ""}`}
                  title={`${r.name} · ${r.dose || "剂量未写明"} · ${windowText(r)}`}>
                  <span>{label}</span>{diff && <i className="wb-cap-diff" title={diff} />}
                  {drag?.id === r.id && <em className="wb-cap-days">D{drag.start}–D{drag.end}</em>}
                </button>
              </Fragment>;
            })}
          </span>
        </li>;
      })}
    </ul>
    {tray.length > 0 && <div className="wb-flow-tray" role="group" aria-label="时间待定">
      <span className="wb-muted">时间待定</span>
      {tray.map(r => <button key={r.id} className={`wb-cap-chip wb-cap--${r.pathway}${r.unconfirmed?.length ? " wb-cap--unconfirmed" : ""}`}
        aria-label={`${r.name} ${r.dose || "剂量未写明"}，时间未写明`} onClick={() => setSelection({ kind: "reagent", id: r.id })}>{r.short} ?</button>)}
    </div>}
    <p className="wb-flow-legend" aria-label="通路颜色">
      {PATHWAYS.filter(p => protocol.reagents.some(r => r.pathway === p.id)).map(p => <span key={p.id}><i className={`wb-cap--${p.id}`} />{p.name}</span>)}
    </p>

    {selection?.kind === "stage" && <aside className="wb-flow-card" aria-label={`${STAGE_NAMES[selection.index]}详情`}>
      <StageDish stage={selection.index} size={104} keyId={`${protocol.id}-card`} />
      <div>
        <h2>{selection.index ? `Stage ${ROMAN[selection.index]} · ` : ""}{STAGE_NAMES[selection.index]}</h2>
        <p className="wb-muted">{spanLabel(SPANS, selection.index, maxDay)}</p>
        <span className="wb-flow-starts">{protocol.reagents.filter(r => r.start !== null && r.start >= Math.max(SPANS[selection.index][0], 0) && r.start < SPANS[selection.index][1]).map(r =>
          <button key={r.id} className={`wb-cap-chip wb-cap--${r.pathway}`} onClick={() => setSelection({ kind: "reagent", id: r.id })}>{r.short}</button>)}</span>
      </div>
    </aside>}
    {selection?.kind === "record" && runOps && <RecordRunCard
      title={selection.confirm ? "确认方案并记录实验" : protocol.run ? "再做一批" : "记录实验"} submitLabel={selection.confirm ? "确认并记录" : "记录"}
      onSubmit={async input => {
        if (selection.confirm) await ops!.confirm(protocol);
        let id: string;
        try { id = await runOps.start(protocol, input); }
        catch (failure) {
          if (!selection.confirm) throw failure;
          setSelection({ kind: "record", confirm: false });
          throw new Error(`方案已确认，但实验没有记下：${failure instanceof Error ? failure.message : "请重试"}`);
        }
        onOpenVersion?.(id);
      }} onClose={() => setSelection(null)} />}
    {selection?.kind === "new" && changeable && <ReagentEditor key={`${selection.reagent.name}-${selection.reagent.start}`} reagent={selection.reagent} isNew
      onSave={r => saveReagents([...protocol.reagents, r], `添加 ${r.name}`)} onClose={() => setSelection(null)} />}
    {picked && changeable && !picked.other && <ReagentEditor key={picked.r.id} reagent={picked.r} isNew={false} onSource={hasSource ? openSource : undefined}
      onSave={r => saveReagents(protocol.reagents.map(x => x.id === picked.r.id ? r : x), `修改 ${r.name}`)}
      onRemove={() => saveReagents(protocol.reagents.filter(x => x.id !== picked.r.id), `去掉 ${picked.r.name}`)} onClose={() => setSelection(null)} />}
    {library && changeable && <MoleculeLibrary onClose={() => setLibrary(false)}
      onAdd={c => setSelection({ kind: "new", reagent: fromCompound(c, null, maxDay) })}
      onCustom={() => setSelection({ kind: "new", reagent: NEW_REAGENT })} />}
    {picked && !(changeable && !picked.other) && <aside className="wb-flow-card" aria-label={`${picked.r.name} 详情`}>
      <ReagentIcon reagent={picked.r} size={96} />
      <div>
        <h2>{picked.r.name}</h2>
        <p className="wb-flow-dose">{picked.r.dose || "剂量未写明"}<span>{windowText(picked.r)}</span></p>
        <SourceNotes reagent={picked.r} />
        {hasSource && !picked.other && <button className="wb-link" onClick={openSource}>在原文中查看</button>}
        {info && <p className="wb-muted">{info.mechanism}</p>}
        {info && <span className="wb-flow-lit" aria-label="文献报告浓度">{[...new Set(info.evidence.map(e => e.reported_concentration))].slice(0, 5).map(c => <span key={c}>{c}</span>)}</span>}
      </div>
      <button className="wb-link" onClick={() => setSelection(null)} aria-label="关闭详情">×</button>
    </aside>}
  </section>;

  // The wrapper and the flow keep their place whether or not the text is open, so opening it does not rebuild the flow.
  const split = hasSource && showSource;
  return <div className={split ? `wb-flow-split wb-flow-split--${tab}` : "wb-flow-solo"}>
    {split && <div className="wb-split-tabs" role="tablist" aria-label="原文与方案图">
      <button role="tab" aria-selected={tab === "source"} onClick={() => setTab("source")}>原文</button>
      <button role="tab" aria-selected={tab === "flow"} onClick={() => setTab("flow")}>方案图</button>
    </div>}
    {split && <SourcePane source={source} activeReagent={picked && !picked.other ? picked.r.name : null} onPickReagent={pickByName} onSeen={markSeen} onClose={closeSource} />}
    {flow}
  </div>;
}
