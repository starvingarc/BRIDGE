/** 3-D developmental tree projection and drawing. Pure canvas, no scientific computation. */
import { ramp, rgba, seeded, type Palette, type RGB } from "./palette";
import { bandWidth, flowOf, MIN_SHARE, onThisTree, shownIndex } from "./treeFlow";
import type { DevTree, Protocol } from "./types";

export type Vec3 = [number, number, number];
export type Camera = { yaw: number; pitch: number; x: number; y: number; z: number; scale: number };
export type Family = "trunk" | "fp" | "da" | "bp" | "glut" | "gaba" | "bmp";

export const LABELS: Record<string, string> = {
  Progenitor_root: "祖细胞", RG_mFP: "底板 RG", Nb_mFP: "底板 Nb", Neuron_DA: "DA 神经元", RG_mBIP: "mBIP RG", Nb_mBIP: "mBIP Nb",
  RG_mBMP: "mBMP RG", Nb_mBMP: "mBMP Nb", Neuron_Glut: "Glut", Neuron_GABA: "GABA",
};

export const familyOf = (name: string): Family =>
  name === "Progenitor_root" ? "trunk" : name.includes("mFP") ? "fp" : name === "Neuron_DA" ? "da" : name.includes("mBIP") ? "bp"
    : name.includes("mBMP") ? "bmp" : name.startsWith("Neuron_Glut") ? "glut" : "gaba";

const WORLD: Vec3 = [430, 330, 330];
export const ORIGIN: Vec3 = [-560, 0, 0];
export const toWorld = (v: [number, number, number]): Vec3 => [v[0] * WORLD[0], v[1] * WORLD[1], v[2] * WORLD[2]];
/** `index` is the row in the tree's `cells`, which marker expression refers to. */
export type AtlasPoint = { p: Vec3; family: Family; node: number; week: number; pt: number; phase: number; r: number; light: number; index: number };

export function buildAtlas(tree: DevTree) {
  const random = seeded(5);
  const nodes = tree.nodes.map(n => [n[0] * WORLD[0], n[1] * WORLD[1], n[2] * WORLD[2]] as Vec3);
  const points: AtlasPoint[] = tree.cells.map((c, index) => ({
    p: [c[0] * WORLD[0], c[1] * WORLD[1], c[2] * WORLD[2]], family: familyOf(tree.subtypes[c[3]] ?? ""), node: c[3], week: c[4], pt: c[5],
    phase: random() * 6.28, r: 0.9 + random() * 0.9, light: 0.55 + 0.4 * c[5], index,
  }));
  return { nodes, points };
}

export function project(cam: Camera, width: number, height: number, p: Vec3): [number, number, number, number] {
  const x0 = p[0] - cam.x, y0 = p[1] - cam.y, z0 = p[2] - cam.z;
  const cy = Math.cos(cam.yaw), sy = Math.sin(cam.yaw);
  const x = x0 * cy + z0 * sy; let z = -x0 * sy + z0 * cy;
  const cp = Math.cos(cam.pitch), sp = Math.sin(cam.pitch);
  const y = y0 * cp - z * sp; z = y0 * sp + z * cp;
  const f = 1300 / (1300 + z), k = Math.min(width / 1000, height / 640) * cam.scale * 0.72 * f;
  return [width / 2 + x * k, height / 2 + y * k, z, f];
}

/** `rows` are the mapped-cell rows drawn at this point (several cells can share one reference position). */
export type Flight = { from: Vec3; to: Vec3; family: Family; delay: number; r: number; rows?: number[] };
/** One gene's expression for colouring: reference values by tree cell index, sample values by mapped-cell row. */
export type Expression = { column: number; reference: Map<number, (number | null)[]>; sample: (number | null)[]; ceiling: number };
export type DrawState = {
  tree: DevTree; atlas: ReturnType<typeof buildAtlas>; protocols: Protocol[]; focus: Protocol | null; sampleIndex: number | null;
  flights: Flight[]; flightStart: number; growStart: number; maxWeek: number; colorBy: "lineage" | "week" | "gene"; hoverNode: number | null;
  expression?: Expression | null;
  /** Shares currently drawn per run and segment ("from>to"); eased toward the shown sample each frame. */
  flows: Map<string, Map<string, number>>;
  /** Run under the pointer in the whole-tree view. */
  hoverRun: string | null;
};

/** Mean of the measured values among rows, or null when none was measured. */
const meanOf = (rows: number[] | undefined, values: (number | null)[]) => {
  let sum = 0, n = 0;
  for (const row of rows ?? []) { const v = values[row]; if (v !== null && v !== undefined) { sum += v; n += 1; } }
  return n ? sum / n : null;
};

const weekColor = (palette: Palette, week: number): RGB => {
  const u = Math.max(0, Math.min(1, (week - 7) / 18));
  return palette.fore.map((v, i) => Math.round(v + (palette.da[i] - v) * u)) as RGB;
};

export function drawTree(ctx: CanvasRenderingContext2D, w: number, h: number, cam: Camera, s: DrawState, palette: Palette, now: number, motion: boolean) {
  // The reference cloud steps back when a run is focused, and further when one of its samples is open.
  const t = now / 1000, dim = s.sampleIndex !== null ? 0.35 : s.focus ? 0.6 : 1;
  const grow = motion ? (now - s.growStart) / 2600 : 2, wave = motion ? (t * 0.11) % 1.25 : -1;
  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = palette.dim; ctx.lineWidth = 1;
  s.tree.edges.forEach(([c, p]) => { const a = project(cam, w, h, s.atlas.nodes[c]), b = project(cam, w, h, s.atlas.nodes[p]); ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); });
  type Item = [number, AtlasPoint | Flight, number, number, number, number];
  const items: Item[] = [];
  for (const c of s.atlas.points) {
    if (c.pt > grow) continue;
    const q: Vec3 = motion ? [c.p[0] + Math.sin(t * 0.5 + c.phase) * 2, c.p[1] + Math.cos(t * 0.4 + c.phase) * 2, c.p[2]] : c.p;
    const [X, Y, Z, f] = project(cam, w, h, q); items.push([Z, c, X, Y, f, -1]);
  }
  if (s.sampleIndex !== null) {
    const elapsed = now - s.flightStart;
    for (const c of s.flights) {
      const u = motion ? Math.max(0, Math.min(1, (elapsed - c.delay) / 1200)) : 1, e = 1 - Math.pow(1 - u, 3);
      const q: Vec3 = [c.from[0] + (c.to[0] - c.from[0]) * e, c.from[1] + (c.to[1] - c.from[1]) * e - Math.sin(e * Math.PI) * 50, c.from[2] + (c.to[2] - c.from[2]) * e];
      const [X, Y, Z, f] = project(cam, w, h, q); items.push([Z - 1, c, X, Y, f, e]);
    }
  }
  // Reference cells first, then the flow bands, then the sample's own cells on top.
  items.sort((a, b) => (a[5] < 0 ? 0 : 1) - (b[5] < 0 ? 0 : 1) || b[0] - a[0]);
  const zoom = Math.max(1, cam.scale * 0.8);
  let flowsDrawn = false;
  for (const [, item, X, Y, f, e] of items) {
    if (e >= 0 && !flowsDrawn) { drawFlows(ctx, w, h, cam, s, palette, motion); flowsDrawn = true; }
    if (X < -6 || Y < -6 || X > w + 6 || Y > h + 6) continue;
    const fog = Math.max(0.3, Math.min(1, f * 1.1));
    if (e < 0) {
      const c = item as AtlasPoint, hidden = c.week > s.maxWeek, hit = Math.abs(c.pt - wave) < 0.025 ? 1.8 : 1;
      const born = Math.min(1, (grow - c.pt) * 6);
      if (s.colorBy === "gene" && s.expression) {
        // Reference cells outside the mapping reference stay a faint neutral: missing, not zero.
        // Expression stays readable behind the sample, so reference cells are dimmed less than in lineage colouring.
        const value = s.expression.reference.get(c.index)?.[s.expression.column] ?? null, soft = Math.max(dim, 0.7);
        ctx.fillStyle = value === null ? rgba(palette.exprLo, (hidden ? 0.03 : 0.16) * soft * fog * born)
          : rgba(ramp(palette, s.expression.ceiling ? value / s.expression.ceiling : 0), (hidden ? 0.06 : 0.9 * palette.cloud) * soft * fog * born);
      } else {
        const color = s.colorBy === "week" ? weekColor(palette, c.week) : palette[c.family];
        ctx.fillStyle = rgba(color, (hidden ? 0.06 : c.light * palette.cloud) * dim * fog * hit * born);
      }
      ctx.beginPath(); ctx.arc(X, Y, c.r * 1.35 * f * (hit > 1 ? 1.35 : 1) * zoom, 0, 6.29); ctx.fill();
    } else {
      // Sample cells: larger than reference cells and outlined (legend A); the fill keeps the cell's lineage colour.
      const c = item as Flight;
      const value = s.colorBy === "gene" && s.expression ? meanOf(c.rows, s.expression.sample) : undefined;
      const fill = value === undefined ? palette[c.family] : value === null ? palette.exprLo
        : ramp(palette, s.expression!.ceiling ? value / s.expression!.ceiling : 0);
      ctx.fillStyle = rgba(fill, 0.45 + 0.55 * e); ctx.beginPath(); ctx.arc(X, Y, c.r * f * (0.8 + 0.4 * e) * zoom, 0, 6.29); ctx.fill();
      ctx.strokeStyle = palette.ink; ctx.globalAlpha = 0.75 * e; ctx.lineWidth = 1; ctx.stroke(); ctx.globalAlpha = 1;
    }
  }
  if (!flowsDrawn) drawFlows(ctx, w, h, cam, s, palette, motion);
  if (s.sampleIndex === null) {
    s.tree.subtypes.forEach((name, i) => {
      if (!LABELS[name] && s.hoverNode !== i) return;
      const [X, Y] = project(cam, w, h, s.atlas.nodes[i]);
      ctx.fillStyle = s.hoverNode === i ? palette.ink : palette.ink2; ctx.font = "12px 'Noto Sans SC', system-ui, sans-serif";
      ctx.fillText(LABELS[name] ?? name.replace("Neuron_", ""), X + 8, Y - 8);
    });
  }
  const [ox, oy, , of] = project(cam, w, h, ORIGIN);
  ctx.fillStyle = palette.dim; ctx.beginPath(); ctx.arc(ox, oy, 9 * of, 0, 6.29); ctx.fill();
  ctx.fillStyle = palette.ink3; ctx.font = "12px Sora, system-ui, sans-serif"; ctx.fillText("hPSC", ox - 14, oy + 24);
}

/** Segment key of a flow, stable across samples so widths can ease from one sample to the next. */
export const segmentKey = (from: number, to: number) => `${from}>${to}`;

/**
 * Flow bands under the cells: every run shows its latest sample in the whole-tree view (faint, stronger under the
 * pointer); a focused run shows only itself, at the opened sample. Widths ease when the sample changes.
 */
function drawFlows(ctx: CanvasRenderingContext2D, w: number, h: number, cam: Camera, s: DrawState, palette: Palette, motion: boolean) {
  for (const p of s.protocols) {
    if (!p.samples.length) continue;
    const sample = p.samples[shownIndex(p, s.focus, s.sampleIndex)];
    const target = new Map((sample && onThisTree(sample, s.tree) ? flowOf(s.tree, sample.position) : []).map(seg => [segmentKey(seg.from, seg.to), seg.share]));
    const drawn = s.flows.get(p.id) ?? new Map<string, number>();
    s.flows.set(p.id, drawn);
    for (const key of new Set([...drawn.keys(), ...target.keys()])) {
      const goal = target.get(key) ?? 0, now = drawn.get(key) ?? 0, next = motion ? now + (goal - now) * 0.12 : goal;
      if (!goal && next < 0.002) drawn.delete(key); else drawn.set(key, next);
    }
    if (s.focus && s.focus !== p) continue;
    const alpha = (s.focus === p ? 0.8 : s.hoverRun === p.id ? 0.6 : 0.32) * (s.sampleIndex !== null ? 0.5 : 1);
    ctx.lineCap = "round";
    for (const [key, share] of drawn) {
      if (share < MIN_SHARE) continue;
      const [from, to] = key.split(">").map(Number);
      const a = project(cam, w, h, from < 0 ? ORIGIN : s.atlas.nodes[from]), b = project(cam, w, h, s.atlas.nodes[to]);
      ctx.strokeStyle = rgba(palette[familyOf(s.tree.subtypes[to] ?? "")], alpha);
      ctx.lineWidth = bandWidth(share, cam.scale);
      ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke();
      // A thin core line keeps the direction readable where the band crosses its own branch's cloud.
      ctx.strokeStyle = palette.ink; ctx.globalAlpha = alpha * 0.55; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); ctx.globalAlpha = 1;
    }
    ctx.lineCap = "butt";
  }
}
