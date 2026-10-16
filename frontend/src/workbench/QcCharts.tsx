import { useEffect, useMemo, useRef, useState, type MouseEvent } from "react";
import { readPalette, ramp, rgba } from "./palette";
import { formatMetric } from "./qc";

const finite = (values: Float64Array) => Array.from(values).filter(Number.isFinite).sort((a, b) => a - b);
const quantile = (sorted: number[], q: number) => sorted.length ? sorted[Math.min(sorted.length - 1, Math.floor(q * sorted.length))] : 0;

/** Redraws a canvas chart when its width or the colour scheme changes. */
export function useCanvas(draw: (ctx: CanvasRenderingContext2D, width: number, height: number, canvas: HTMLCanvasElement) => void, deps: unknown[], height: number) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(0);
  const [scheme, setScheme] = useState(0);
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
  useEffect(() => {
    const el = ref.current, ctx = el?.getContext("2d");
    if (!el || !ctx || !width) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    el.width = width * dpr; el.height = height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    draw(ctx, width, height, el);
  }, [width, scheme, height, ...deps]); // eslint-disable-line react-hooks/exhaustive-deps
  return ref;
}

/**
 * Distribution of one per-cell metric, with its median marked; hovering a bar reads its range and cell count. The axis runs
 * to the 99.5th percentile so the bulk stays readable; cells above it are counted in a separate, labelled "≥" bar.
 */
export function Histogram({ title, values, unit }: { title: string; values: Float64Array; unit: "count" | "fraction" }) {
  const [hover, setHover] = useState<{ i: number; x: number; y: number } | null>(null);
  const shape = useMemo(() => {
    const sorted = finite(values), top = sorted.at(-1) ?? 1;
    const cut = quantile(sorted, 0.995), hi = cut > 0 && cut < top ? cut : top || 1, bins = 30, step = hi / bins;
    const counts = new Array<number>(bins).fill(0);
    let over = 0;
    for (const v of sorted) { if (v > hi) over += 1; else counts[Math.min(bins - 1, Math.max(0, Math.floor(v / step)))] += 1; }
    return { counts, over, step, hi, top, max: Math.max(1, over, ...counts), median: quantile(sorted, 0.5), n: sorted.length };
  }, [values]);
  const missing = values.length - shape.n;
  const W = 320, H = 104, left = 8, right = shape.over ? 296 : 312, base = 82;
  const x = (v: number) => left + (Math.min(v, shape.hi) / shape.hi) * (right - left);
  const label = (v: number) => formatMetric(v, unit);
  return <figure className="wb-qc-chart">
    <figcaption><b>{title}</b></figcaption>
    <div className="wb-qc-plot">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${title}分布，中位数 ${label(shape.median)}，${shape.n.toLocaleString("en-US")} 个细胞`}
        onMouseLeave={() => setHover(null)}>
        {shape.counts.map((c, i) => <rect key={i} x={x(i * shape.step) + 0.5} width={Math.max(1, (right - left) / shape.counts.length - 1)}
          y={base - (c / shape.max) * 66} height={(c / shape.max) * 66} rx={1.5} className={hover?.i === i ? "wb-qc-bar wb-qc-bar--on" : "wb-qc-bar"}
          onMouseMove={e => { const box = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect(); setHover({ i, x: e.clientX - box.left, y: e.clientY - box.top }); }} />)}
        {shape.over > 0 && <rect x={302} width={10} y={base - (shape.over / shape.max) * 66} height={Math.max(1.5, (shape.over / shape.max) * 66)} rx={1.5}
          className={hover?.i === -1 ? "wb-qc-bar wb-qc-bar--over wb-qc-bar--on" : "wb-qc-bar wb-qc-bar--over"}
          onMouseMove={e => { const box = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect(); setHover({ i: -1, x: e.clientX - box.left, y: e.clientY - box.top }); }} />}
        <line x1={x(shape.median)} x2={x(shape.median)} y1={8} y2={base} className="wb-qc-median" />
        <text x={x(shape.median) + 4} y={13} className="wb-qc-text">中位数 {label(shape.median)}</text>
        <line x1={left} x2={right} y1={base + 0.5} y2={base + 0.5} className="wb-qc-axis" />
        {[0, 0.5, 1].map(f => <text key={f} x={left + f * (right - left)} y={base + 15} className="wb-qc-text wb-qc-text--muted"
          textAnchor={f === 0 ? "start" : f === 1 ? "end" : "middle"}>{label(f * shape.hi)}</text>)}
        {shape.over > 0 && <text x={312} y={base + 15} className="wb-qc-text wb-qc-text--muted" textAnchor="end">≥</text>}
      </svg>
      {hover && <span className="wb-qc-tip" style={{ left: hover.x + 10, top: hover.y - 30 }}>
        {hover.i < 0 ? `${label(shape.hi)} 以上（最高 ${label(shape.top)}） · ${shape.over.toLocaleString("en-US")} 个细胞`
          : `${label(hover.i * shape.step)}–${label((hover.i + 1) * shape.step)} · ${shape.counts[hover.i].toLocaleString("en-US")} 个细胞`}
      </span>}
    </div>
    {missing > 0 && <p className="wb-qc-chart-note">{missing.toLocaleString("en-US")} 个细胞未测得</p>}
  </figure>;
}

type Pair = { x: Float64Array; y: Float64Array };
const log10 = (v: number) => Math.log10(Math.max(v, 1));

/** Mitochondrial fraction against total counts as a density: low-count, high-mitochondrial cells gather top left. */
export function MitoDensity({ counts, mito }: { counts: Float64Array; mito: Float64Array }) {
  const ref = useCanvas((ctx, w, h, el) => drawDensity(ctx, w, h, readPalette(el), { x: counts, y: mito }), [counts, mito], 220);
  return <figure className="wb-qc-chart">
    <figcaption><b>线粒体占比 × 总计数</b><span>左上角是低质量细胞</span></figcaption>
    <canvas ref={ref} className="wb-qc-canvas" style={{ height: 220 }} role="img" aria-label="线粒体占比与总计数的细胞密度" />
  </figure>;
}

type Frame = { x0: number; x1: number; y0: number; y1: number; logY: boolean };
const PAD = { left: 44, right: 10, top: 10, bottom: 26 };

function frameOf(pair: Pair, logY: boolean): Frame {
  const xs = finite(pair.x).filter(v => v > 0), ys = finite(pair.y);
  const x0 = log10(quantile(xs, 0)), x1 = log10(quantile(xs, 1)) || x0 + 1;
  // The full range is drawn so no cell is pushed against an edge and read as a lower value.
  const y0 = logY ? log10(Math.max(1, quantile(ys, 0))) : 0, y1 = logY ? log10(quantile(ys, 1)) : Math.max(quantile(ys, 1), 0.01);
  return { x0: x0 - 0.02, x1: x1 + 0.02, y0, y1: y1 + (logY ? 0.02 : y1 * 0.03), logY };
}

function axes(ctx: CanvasRenderingContext2D, w: number, h: number, p: ReturnType<typeof readPalette>, f: Frame) {
  ctx.strokeStyle = p.line; ctx.lineWidth = 1; ctx.beginPath();
  ctx.moveTo(PAD.left, PAD.top); ctx.lineTo(PAD.left, h - PAD.bottom); ctx.lineTo(w - PAD.right, h - PAD.bottom); ctx.stroke();
  ctx.fillStyle = p.ink3; ctx.font = "10px Sora, 'Noto Sans SC', sans-serif"; ctx.textAlign = "center";
  for (let e = Math.ceil(f.x0); e <= f.x1; e += 1) { const X = PAD.left + ((e - f.x0) / (f.x1 - f.x0)) * (w - PAD.left - PAD.right); ctx.fillText((10 ** e).toLocaleString("en-US"), X, h - 8); }
  ctx.textAlign = "right";
  const ticks = f.logY ? [500, 1000, 2000, 5000, 10000].filter(v => log10(v) >= f.y0 && log10(v) <= f.y1) : [0, f.y1 / 2, f.y1];
  for (const v of ticks) {
    const t = f.logY ? (log10(v) - f.y0) / (f.y1 - f.y0) : v / f.y1, Y = h - PAD.bottom - t * (h - PAD.top - PAD.bottom);
    ctx.fillText(f.logY ? v.toLocaleString("en-US") : formatMetric(v, "fraction"), PAD.left - 5, Y + 3);
  }
}

function drawDensity(ctx: CanvasRenderingContext2D, w: number, h: number, p: ReturnType<typeof readPalette>, pair: Pair) {
  const f = frameOf(pair, false);
  axes(ctx, w, h, p, f);
  const size = 7, cols = Math.ceil((w - PAD.left - PAD.right) / size), rows = Math.ceil((h - PAD.top - PAD.bottom) / size), grid = new Map<number, number>();
  for (let i = 0; i < pair.x.length; i += 1) {
    const xv = pair.x[i], yv = pair.y[i];
    if (!Number.isFinite(xv) || !Number.isFinite(yv) || xv <= 0) continue;
    const c = Math.min(cols - 1, Math.max(0, Math.floor(((log10(xv) - f.x0) / (f.x1 - f.x0)) * cols)));
    const r = Math.min(rows - 1, Math.max(0, Math.floor((Math.min(yv, f.y1) / f.y1) * rows)));
    grid.set(r * cols + c, (grid.get(r * cols + c) ?? 0) + 1);
  }
  const max = Math.log1p(Math.max(1, ...grid.values()));
  for (const [key, count] of grid) {
    const r = Math.floor(key / cols), c = key % cols;
    ctx.fillStyle = rgba(ramp(p, 0.15 + 0.85 * Math.log1p(count) / max), 0.95);
    ctx.fillRect(PAD.left + c * size, h - PAD.bottom - (r + 1) * size, size - 1, size - 1);
  }
}

/**
 * Scrublet doublet scores of every assessed cell, each bar split into singlets and the doublet candidates Scrublet called.
 * A threshold belongs to one capture, so a line is drawn only when the sample is a single capture.
 */
export function DoubletHistogram({ scores, classes, threshold, simulated }: {
  scores: Float64Array; classes?: (string | null)[]; threshold: number | null;
  /** The capture's simulated doublet scores, drawn as an outline scaled to the same peak height: a reference shape, not a count. */
  simulated?: { counts: number[]; edges: number[] } | null;
}) {
  const [hover, setHover] = useState<{ i: number; x: number; y: number } | null>(null);
  const shape = useMemo(() => {
    let top = 0, n = 0;
    for (const v of scores) if (Number.isFinite(v)) { n += 1; if (v > top) top = v; }
    let simTop = 0;
    simulated?.counts.forEach((c, i) => { if (c > 0) simTop = simulated.edges[i + 1]; });
    // Scores lie in [0, 1]; the axis ends at the next fifth so the start, middle and end ticks are all round.
    const hi = Math.min(1, Math.ceil(Math.max(top, threshold ?? 0, simTop, 0.05) * 1.02 * 5) / 5), bins = 40, step = hi / bins;
    const all = new Array<number>(bins).fill(0), doublets = new Array<number>(bins).fill(0);
    scores.forEach((v, i) => {
      if (!Number.isFinite(v)) return;
      const b = Math.min(bins - 1, Math.max(0, Math.floor(v / step)));
      all[b] += 1; if (classes?.[i] === "doublet") doublets[b] += 1;
    });
    return { all, doublets, step, hi, n, max: Math.max(1, ...all) };
  }, [scores, classes, threshold, simulated]);
  const W = 320, H = 104, left = 8, right = 312, base = 82;
  const x = (v: number) => left + (v / shape.hi) * (right - left), width = Math.max(1, (right - left) / shape.all.length - 1);
  const y = (c: number) => (c / shape.max) * 66;
  const score = (v: number) => v.toFixed(2);
  const simMax = simulated ? Math.max(1, ...simulated.counts) : 1;
  // A step outline, one tread per simulated bin, so the binned shape is drawn as it is rather than as a smooth curve.
  const outline = simulated ? `M${x(simulated.edges[0]).toFixed(1)},${base}` + simulated.counts.map((c, i) => {
    const top = (base - (c / simMax) * 66).toFixed(1);
    return `V${top}H${x(Math.min(simulated.edges[i + 1], shape.hi)).toFixed(1)}`;
  }).join("") + `V${base}` : "";
  const move = (i: number) => (e: MouseEvent<SVGGElement>) => {
    const box = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect(); setHover({ i, x: e.clientX - box.left, y: e.clientY - box.top });
  };
  return <figure className="wb-qc-chart">
    <figcaption className="wb-qc-keys"><span><i className="wb-qc-key wb-qc-key--doublet" />候选</span>{outline && <span><i className="wb-qc-key wb-qc-key--sim" />模拟双细胞</span>}</figcaption>
    <div className="wb-qc-plot">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`双细胞分数分布，${shape.n.toLocaleString("en-US")} 个细胞`} onMouseLeave={() => setHover(null)}>
        {shape.all.map((c, i) => <g key={i} className={hover?.i === i ? "wb-qc-stack wb-qc-stack--on" : "wb-qc-stack"} onMouseMove={move(i)}>
          <rect x={x(i * shape.step) + 0.5} width={width} y={base - y(c)} height={y(c)} rx={1.5} className="wb-qc-bar" />
          {shape.doublets[i] > 0 && <rect x={x(i * shape.step) + 0.5} width={width} y={base - y(shape.doublets[i])} height={Math.max(1, y(shape.doublets[i]))} rx={1.5} className="wb-qc-bar wb-qc-bar--doublet" />}
          <rect x={x(i * shape.step)} width={width + 1} y={8} height={base - 8} fill="transparent" />
        </g>)}
        {outline && <path d={outline} className="wb-qc-sim" />}
        {threshold !== null && <>
          <line x1={x(threshold)} x2={x(threshold)} y1={8} y2={base} className="wb-qc-median" />
          <text x={x(threshold) + (x(threshold) > 240 ? -4 : 4)} y={13} textAnchor={x(threshold) > 240 ? "end" : "start"} className="wb-qc-text">阈值 {score(threshold)}</text>
        </>}
        <line x1={left} x2={right} y1={base + 0.5} y2={base + 0.5} className="wb-qc-axis" />
        {[0, 0.5, 1].map(f => <text key={f} x={left + f * (right - left)} y={base + 15} className="wb-qc-text wb-qc-text--muted"
          textAnchor={f === 0 ? "start" : f === 1 ? "end" : "middle"}>{(f * shape.hi).toFixed(1)}</text>)}
      </svg>
      {hover && <span className="wb-qc-tip" style={{ left: hover.x + 10, top: hover.y - 30 }}>
        {score(hover.i * shape.step)}–{score((hover.i + 1) * shape.step)} · {shape.all[hover.i].toLocaleString("en-US")} 个细胞
        {shape.doublets[hover.i] > 0 ? `，其中候选 ${shape.doublets[hover.i].toLocaleString("en-US")}` : ""}
      </span>}
    </div>
  </figure>;
}

/** Batch colours, as theme properties, in the order batches are listed. */
export const BATCH_TOKENS = ["--wb-accent", "--wb-phase-g2m", "--wb-phase-s", "--wb-fp"] as const;
export const batchColour = (i: number) => `var(${BATCH_TOKENS[i % BATCH_TOKENS.length]})`;

/**
 * One per-cell metric for several batches on a shared axis, each drawn as the share of its own cells per bin so batches of
 * different size compare; the axis runs to the highest 99.5th percentile, values above it are left out of the lines.
 */
export function OverlayHistogram({ title, unit, series }: { title: string; unit: "count" | "fraction"; series: { label: string; values: Float64Array }[] }) {
  const shape = useMemo(() => {
    const sorted = series.map(s => finite(s.values));
    const hi = Math.max(...sorted.map(v => quantile(v, 0.995)), unit === "fraction" ? 0.01 : 1), bins = 30, step = hi / bins;
    const shares = sorted.map(v => {
      const counts = new Array<number>(bins).fill(0);
      for (const x of v) if (x <= hi) counts[Math.min(bins - 1, Math.max(0, Math.floor(x / step)))] += 1;
      return counts.map(c => v.length ? c / v.length : 0);
    });
    return { hi, step, shares, medians: sorted.map(v => quantile(v, 0.5)), max: Math.max(0.01, ...shares.flat()) };
  }, [series, unit]);
  const W = 320, H = 104, left = 8, right = 312, base = 82;
  const x = (v: number) => left + (v / shape.hi) * (right - left);
  const label = (v: number) => formatMetric(v, unit);
  return <figure className="wb-qc-chart">
    <figcaption><b>{title}</b></figcaption>
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${title}，按批次叠画`}>
      {shape.shares.map((shares, i) => <path key={i} className="wb-qc-overlay" style={{ stroke: batchColour(i) }}
        d={`M${x(0).toFixed(1)},${base}` + shares.map((f, b) => `V${(base - (f / shape.max) * 66).toFixed(1)}H${x((b + 1) * shape.step).toFixed(1)}`).join("") + `V${base}`} />)}
      <line x1={left} x2={right} y1={base + 0.5} y2={base + 0.5} className="wb-qc-axis" />
      {[0, 0.5, 1].map(f => <text key={f} x={left + f * (right - left)} y={base + 15} className="wb-qc-text wb-qc-text--muted"
        textAnchor={f === 0 ? "start" : f === 1 ? "end" : "middle"}>{label(f * shape.hi)}</text>)}
    </svg>
    <span className="wb-qc-keys">{series.map((s, i) => <span key={s.label}><i className="wb-qc-key" style={{ background: batchColour(i) }} />{s.label} · 中位数 {label(shape.medians[i])}</span>)}</span>
  </figure>;
}
