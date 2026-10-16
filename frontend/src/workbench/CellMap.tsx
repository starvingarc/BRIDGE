import { useEffect, useMemo, useRef, useState, type MouseEvent } from "react";
import { readPalette, ramp, rgba } from "./palette";

/**
 * How points are coloured: by category (a colour per code; -1 is uncategorised, drawn grey; a focused code is drawn
 * over the dimmed rest), or by a value on the expression ramp between lo and hi (missing values grey).
 */
export type MapColouring =
  /** `colours` are CSS colours or custom property names (`--wb-…`), read from the theme when drawing. */
  | { kind: "category"; codes: Int16Array; colours: string[]; focus: number | null }
  | { kind: "value"; values: Float64Array; lo: number; hi: number };

const PAD = 10;

/**
 * A 2-D cell map such as a UMAP, drawn on canvas. Hovering a cell shows its readout; the axes carry no meaning, so
 * none are drawn. Cells without coordinates are left out.
 */
export function CellMap({ x, y, colouring, label, height = 280, name }: {
  x: Float64Array; y: Float64Array; colouring: MapColouring; label: (i: number) => string; height?: number; name: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(0);
  const [scheme, setScheme] = useState(0);
  const [hover, setHover] = useState<{ i: number; left: number; top: number } | null>(null);
  const screen = useRef<{ X: Float32Array; Y: Float32Array } | null>(null);
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
  const bounds = useMemo(() => {
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (let i = 0; i < x.length; i += 1) {
      if (!Number.isFinite(x[i]) || !Number.isFinite(y[i])) continue;
      x0 = Math.min(x0, x[i]); x1 = Math.max(x1, x[i]); y0 = Math.min(y0, y[i]); y1 = Math.max(y1, y[i]);
    }
    return Number.isFinite(x0) ? { x0, x1, y0, y1 } : null;
  }, [x, y]);
  useEffect(() => {
    const el = ref.current, ctx = el?.getContext("2d");
    if (!el || !ctx || !width || !bounds) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    el.width = width * dpr; el.height = height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    // Equal scale on both axes, centred, so distances read the same either way.
    const scale = Math.min((width - 2 * PAD) / (bounds.x1 - bounds.x0 || 1), (height - 2 * PAD) / (bounds.y1 - bounds.y0 || 1));
    const ox = (width - (bounds.x1 - bounds.x0) * scale) / 2, oy = (height - (bounds.y1 - bounds.y0) * scale) / 2;
    const X = new Float32Array(x.length).fill(NaN), Y = new Float32Array(x.length).fill(NaN);
    for (let i = 0; i < x.length; i += 1) {
      if (!Number.isFinite(x[i]) || !Number.isFinite(y[i])) continue;
      X[i] = ox + (x[i] - bounds.x0) * scale; Y[i] = height - oy - (y[i] - bounds.y0) * scale;
    }
    screen.current = { X, Y };
    const p = readPalette(el), grey = p.ink3, style = getComputedStyle(el);
    const dot = (i: number, colour: string, alpha: number) => { ctx.globalAlpha = alpha; ctx.fillStyle = colour; ctx.beginPath(); ctx.arc(X[i], Y[i], 1.7, 0, Math.PI * 2); ctx.fill(); };
    if (colouring.kind === "category") {
      const { codes, focus } = colouring;
      const colours = colouring.colours.map(c => c.startsWith("--") ? style.getPropertyValue(c).trim() || grey : c);
      // Uncategorised and unfocused cells first, so the focused category is drawn on top.
      for (let i = 0; i < x.length; i += 1) if (Number.isFinite(X[i]) && (codes[i] < 0 || (focus !== null && codes[i] !== focus)))
        dot(i, codes[i] < 0 ? grey : colours[codes[i]], focus !== null ? 0.12 : 0.5);
      for (let i = 0; i < x.length; i += 1) if (Number.isFinite(X[i]) && codes[i] >= 0 && (focus === null || codes[i] === focus)) dot(i, colours[codes[i]], 0.75);
    } else {
      const { values, lo, hi } = colouring, order = Array.from(values.keys()).sort((a, b) => (Number.isFinite(values[a]) ? values[a] : -Infinity) - (Number.isFinite(values[b]) ? values[b] : -Infinity));
      // Higher values are drawn last, so they are not hidden under low ones.
      for (const i of order) if (Number.isFinite(X[i]))
        dot(i, Number.isFinite(values[i]) ? rgba(ramp(p, (values[i] - lo) / (hi - lo || 1)), 1) : grey, Number.isFinite(values[i]) ? 0.8 : 0.3);
    }
    ctx.globalAlpha = 1;
    if (hover && Number.isFinite(X[hover.i])) { ctx.strokeStyle = p.ink; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(X[hover.i], Y[hover.i], 4, 0, Math.PI * 2); ctx.stroke(); }
  }, [width, scheme, height, bounds, x, y, colouring, hover?.i]); // eslint-disable-line react-hooks/exhaustive-deps
  const move = (event: MouseEvent<HTMLCanvasElement>) => {
    const s = screen.current; if (!s) return;
    const box = event.currentTarget.getBoundingClientRect(), mx = event.clientX - box.left, my = event.clientY - box.top;
    let best = -1, distance = 64;
    for (let i = 0; i < s.X.length; i += 1) {
      if (colouring.kind === "category" && colouring.focus !== null && colouring.codes[i] !== colouring.focus) continue;
      const d = (s.X[i] - mx) ** 2 + (s.Y[i] - my) ** 2;
      if (d < distance) { distance = d; best = i; }
    }
    setHover(best < 0 ? null : { i: best, left: s.X[best], top: s.Y[best] });
  };
  return <div className="wb-qc-plot">
    <canvas ref={ref} className="wb-qc-canvas" style={{ height }} role="img" aria-label={name} onMouseMove={move} onMouseLeave={() => setHover(null)} />
    {/* On the right half the readout opens to the left of the cell, so it stays inside the panel. */}
    {hover && <span className="wb-qc-tip" style={{ top: hover.top - 30, ...(hover.left > width / 2 ? { right: width - hover.left + 10 } : { left: hover.left + 10 }) }}>{label(hover.i)}</span>}
  </div>;
}
