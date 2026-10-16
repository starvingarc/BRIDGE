import { useEffect, useMemo, useRef, useState } from "react";
import { PHASES, PHASE_LABEL, cycleReason, joinRows, useCellMap, useCycleCells, type CellMapCells, type CycleCells, type Phase } from "./cycle";
import { CellMap, type MapColouring } from "./CellMap";
import { Files, day } from "./QcView";
import { SourceGoneNote } from "./SourceGoneNote";
import type { AnalysisDTO } from "./objects";

const count = (n: number) => n.toLocaleString("en-US");
const share = (part: number, whole: number) => whole ? `${(part / whole * 100).toFixed(1)}%` : "—";

/** Phase colours, read from the theme so the scatter follows light and dark mode. */
function phaseColours(element: Element) {
  const style = getComputedStyle(element);
  const get = (name: string, fallback: string) => style.getPropertyValue(name).trim() || fallback;
  return { G1: get("--wb-phase-g1", "#b9c4cc"), S: get("--wb-phase-s", "#3d8fd6"), G2M: get("--wb-phase-g2m", "#d9643a"),
    line: get("--wb-line", "#e1e9e7"), ink3: get("--wb-ink-3", "#8a96a3") } satisfies Record<Phase | "line" | "ink3", string>;
}

/** About four round tick values covering [lo, hi]. */
function ticks(lo: number, hi: number) {
  const raw = (hi - lo) / 4, mag = 10 ** Math.floor(Math.log10(raw || 1)), step = [1, 2, 5, 10].map(m => m * mag).find(s => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(Math.abs(v) < step / 1e6 ? 0 : v);
  return out;
}

const PAD = { left: 40, right: 10, top: 10, bottom: 30 };

/** S score against G2/M score for every scored cell, coloured by phase; a focused phase is drawn over the others, dimmed. */
function PhaseScatter({ cells, focus }: { cells: Required<Pick<CycleCells, "s" | "g2m">> & CycleCells; focus: Phase | null }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(0);
  const [scheme, setScheme] = useState(0);
  const height = 240;
  useEffect(() => {
    const el = ref.current; if (!el) return;
    setWidth(el.clientWidth);
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width))) : null;
    observer?.observe(el);
    const media = window.matchMedia?.("(prefers-color-scheme: dark)");
    const flip = () => setScheme(n => n + 1);
    media?.addEventListener?.("change", flip);
    return () => { observer?.disconnect(); media?.removeEventListener?.("change", flip); };
  }, []);
  const frame = useMemo(() => scatterFrame(cells), [cells]);
  useEffect(() => {
    const el = ref.current, ctx = el?.getContext("2d");
    if (!el || !ctx || !width || !frame) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    el.width = width * dpr; el.height = height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    const c = phaseColours(el), w = width - PAD.left - PAD.right, h = height - PAD.top - PAD.bottom;
    const X = (v: number) => PAD.left + (Math.min(frame.x1, Math.max(frame.x0, v)) - frame.x0) / (frame.x1 - frame.x0) * w;
    const Y = (v: number) => PAD.top + h - (Math.min(frame.y1, Math.max(frame.y0, v)) - frame.y0) / (frame.y1 - frame.y0) * h;
    ctx.font = "10px Sora, 'Noto Sans SC', sans-serif"; ctx.fillStyle = c.ink3; ctx.strokeStyle = c.line; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(PAD.left, PAD.top); ctx.lineTo(PAD.left, PAD.top + h); ctx.lineTo(PAD.left + w, PAD.top + h); ctx.stroke();
    ctx.textAlign = "center";
    for (const v of ticks(frame.x0, frame.x1)) ctx.fillText(String(Number(v.toFixed(3))), X(v), PAD.top + h + 13);
    ctx.fillText("S 期评分", PAD.left + w / 2, height - 3);
    ctx.textAlign = "right";
    for (const v of ticks(frame.y0, frame.y1)) ctx.fillText(String(Number(v.toFixed(3))), PAD.left - 5, Y(v) + 3);
    // Zero on either score is where a cell's cycle genes are no higher than its background genes.
    ctx.setLineDash([3, 3]);
    if (frame.x0 < 0 && frame.x1 > 0) { ctx.beginPath(); ctx.moveTo(X(0), PAD.top); ctx.lineTo(X(0), PAD.top + h); ctx.stroke(); }
    if (frame.y0 < 0 && frame.y1 > 0) { ctx.beginPath(); ctx.moveTo(PAD.left, Y(0)); ctx.lineTo(PAD.left + w, Y(0)); ctx.stroke(); }
    ctx.setLineDash([]);
    const order: Phase[] = focus ? [...PHASES.filter(p => p !== focus), focus] : [...PHASES];
    const stride = Math.max(1, Math.ceil(cells.s.length / 30000));
    for (const phase of order) {
      ctx.fillStyle = c[phase]; ctx.globalAlpha = focus && focus !== phase ? 0.12 : 0.7;
      for (let i = 0; i < cells.s.length; i += stride) {
        if (cells.phase?.[i] !== phase) continue;
        const x = cells.s[i], y = cells.g2m[i];
        if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
        ctx.beginPath(); ctx.arc(X(x), Y(y), 1.8, 0, Math.PI * 2);
        // A cell beyond the axes sits on the edge as a hollow ring, so it is not read as that edge value.
        if (x < frame.x0 || x > frame.x1 || y < frame.y0 || y > frame.y1) { ctx.strokeStyle = c[phase]; ctx.stroke(); } else ctx.fill();
      }
    }
    ctx.globalAlpha = 1;
    ctx.save(); ctx.translate(11, PAD.top + h / 2); ctx.rotate(-Math.PI / 2); ctx.textAlign = "center"; ctx.fillStyle = c.ink3; ctx.fillText("G2/M 期评分", 0, 0); ctx.restore();
  }, [width, scheme, frame, cells, focus]);
  return <>
    <canvas ref={ref} className="wb-qc-canvas" style={{ height }} role="img"
      aria-label={`每个细胞的 S 期与 G2/M 期评分${focus ? `，突出 ${PHASE_LABEL[focus]}` : ""}`} />
    {frame && frame.outside > 0 && <p className="wb-qc-chart-note">空心点：{count(frame.outside)} 个超出范围的细胞</p>}
  </>;
}

const quantile = (sorted: number[], q: number) => sorted[Math.min(sorted.length - 1, Math.max(0, Math.floor(q * sorted.length)))];

/**
 * Axes covering the middle 99% of scored cells on each score, padded, and always including zero. A few extreme cells
 * would otherwise squeeze everyone else into a corner; they are drawn on the edge and counted instead.
 */
function scatterFrame(cells: { s: Float64Array; g2m: Float64Array }) {
  const xs: number[] = [], ys: number[] = [];
  for (let i = 0; i < cells.s.length; i += 1) if (Number.isFinite(cells.s[i]) && Number.isFinite(cells.g2m[i])) { xs.push(cells.s[i]); ys.push(cells.g2m[i]); }
  if (!xs.length) return null;
  xs.sort((a, b) => a - b); ys.sort((a, b) => a - b);
  const range = (sorted: number[]) => {
    const lo = Math.min(0, quantile(sorted, 0.005)), hi = Math.max(0, quantile(sorted, 0.995)), pad = (hi - lo || 1) * 0.05;
    return [lo - pad, hi + pad];
  };
  const [x0, x1] = range(xs), [y0, y1] = range(ys);
  let outside = 0;
  for (let i = 0; i < cells.s.length; i += 1) {
    const x = cells.s[i], y = cells.g2m[i];
    if (Number.isFinite(x) && Number.isFinite(y) && (x < x0 || x > x1 || y < y0 || y > y1)) outside += 1;
  }
  return { x0, x1, y0, y1, outside };
}

type MapColour = "phase" | "s" | "g2m";
const MAP_COLOURS: [MapColour, string][] = [["phase", "阶段"], ["s", "S 评分"], ["g2m", "G2/M 评分"]];
const score = (v: number | undefined) => v === undefined || !Number.isFinite(v) ? "—" : v.toFixed(2);

/** The sample's UMAP coloured by cycle phase or by either score, joined to the cycle table by observation id. */
function PhaseMap({ map, cells, focus }: { map: CellMapCells; cells: CycleCells; focus: Phase | null }) {
  const [colour, setColour] = useState<MapColour>("phase");
  const rows = useMemo(() => joinRows(map, cells.ids), [map, cells.ids]);
  const colouring = useMemo((): MapColouring => {
    if (colour === "phase") return { kind: "category", colours: PHASES.map(p => `--wb-phase-${p.toLowerCase()}`), focus: focus ? PHASES.indexOf(focus) : null,
      codes: Int16Array.from(rows, r => r < 0 ? -1 : PHASES.indexOf(cells.phase?.[r] as Phase)) };
    const source = colour === "s" ? cells.s : cells.g2m;
    const values = Float64Array.from(rows, r => r < 0 || !source ? NaN : source[r]);
    const sorted = Array.from(values).filter(Number.isFinite).sort((a, b) => a - b);
    return { kind: "value", values, lo: sorted[Math.floor(sorted.length * 0.01)] ?? 0, hi: sorted[Math.floor(sorted.length * 0.99)] ?? 1 };
  }, [colour, rows, cells, focus]);
  const label = (i: number) => {
    const r = rows[i], phase = r < 0 ? null : cells.phase?.[r];
    return [phase && PHASE_LABEL[phase as Phase], map.cluster?.[i] != null && `簇 ${map.cluster[i]}`,
      r >= 0 && `S ${score(cells.s?.[r])} · G2/M ${score(cells.g2m?.[r])}`].filter(Boolean).join(" · ") || "无周期评分";
  };
  return <figure className="wb-qc-chart">
    <figcaption className="wb-map-head"><b>UMAP</b>
      <span className="wb-seg" role="group" aria-label="UMAP 着色">
        {MAP_COLOURS.map(([id, text]) => <button key={id} type="button" aria-pressed={colour === id} onClick={() => setColour(id)}>{text}</button>)}
      </span>
    </figcaption>
    <CellMap x={map.x} y={map.y} colouring={colouring} label={label} name={`UMAP，按${MAP_COLOURS.find(c => c[0] === colour)![1]}着色`} />
    {colouring.kind === "value" && <span className="wb-qc-legend">{score(colouring.lo)}<i />{score(colouring.hi)}</span>}
  </figure>;
}

/** The automatic cell-cycle scoring of one sample: phase shares, the sample's UMAP by phase, and the per-cell scores. */
export function CycleView({ analysis, atlas, others }: { analysis: AnalysisDTO; atlas?: AnalysisDTO; others: number }) {
  const detail = useCycleCells(analysis);
  const map = useCellMap(atlas);
  const [focus, setFocus] = useState<Phase | null>(null);
  const summary = analysis.cell_cycle_summary!, cycle = summary.cell_cycle;
  const foot = <p className="wb-qc-foot">{analysis.tool.id} {analysis.tool.version} · {day(analysis.created_at)}{!detail?.gone && <Files analysis={analysis} />}</p>;
  if (detail?.gone) return <div className="wb-qc"><SourceGoneNote what="细胞周期" />{foot}</div>;
  const counts = cycle?.phase_counts ?? null, total = cycle?.n_observations ?? summary.n_observations ?? 0;
  const scored = counts ? PHASES.reduce((n, p) => n + (counts[p] ?? 0), 0) : 0;
  if (!cycle || cycle.assessment_state !== "available" || !counts || !scored) return <div className="wb-qc">
    <p className="wb-qc-status wb-qc-status--warn"><span>没有算出</span>{(cycle?.reason_codes ?? []).map(cycleReason).join("；")}</p>
    {foot}
  </div>;
  const cells = detail?.cells;
  const drawable = cells?.s && cells.g2m && cells.s.some(Number.isFinite) ? cells as Required<Pick<CycleCells, "s" | "g2m">> & CycleCells : null;
  const missing = (cycle.s_missing_genes?.length ?? 0) + (cycle.g2m_missing_genes?.length ?? 0);
  return <div className="wb-qc wb-cycle">
    <div className="wb-cycle-head">
      <b>{cycle.s_g2m_fraction === null ? share((counts.S ?? 0) + (counts.G2M ?? 0), total) : `${(cycle.s_g2m_fraction * 100).toFixed(1)}%`}</b>
      <span>在 S 或 G2/M 期</span>
      {others > 0 && <span className="wb-muted">共 {others + 1} 次，显示最近一次</span>}
    </div>
    <div className="wb-cycle-bar" role="img" aria-label={PHASES.map(p => `${PHASE_LABEL[p]} ${share(counts[p] ?? 0, total)}`).join("，")}>
      {PHASES.map(p => (counts[p] ?? 0) > 0 && <i key={p} className={`wb-phase--${p}`} style={{ flexGrow: counts[p] }} />)}
    </div>
    <div className="wb-cycle-legend" role="group" aria-label="周期阶段">
      {PHASES.map(p => <button key={p} type="button" aria-pressed={focus === p} onClick={() => setFocus(f => f === p ? null : p)}>
        <i className={`wb-phase--${p}`} /><b>{PHASE_LABEL[p]}</b><span>{count(counts[p] ?? 0)} · {share(counts[p] ?? 0, total)}</span>
      </button>)}
    </div>
    {map && cells && <PhaseMap map={map} cells={cells} focus={focus} />}
    <figure className="wb-qc-chart">
      <figcaption><b>S / G2/M 评分</b></figcaption>
      {drawable ? <PhaseScatter cells={drawable} focus={focus} />
        : <p className="wb-muted" role="status">{!detail ? "正在读取…" : detail.error ?? "没有评分。"}</p>}
    </figure>
    {(total > scored || missing > 0) && <p className="wb-muted">
      {[total > scored && `${count(total - scored)} 个细胞无阶段`, missing > 0 && `缺 ${missing} 个周期基因`].filter(Boolean).join("，")}</p>}
    {foot}
  </div>;
}
