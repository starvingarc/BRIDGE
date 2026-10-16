export type RGB = [number, number, number];
export type Palette = Record<"trunk" | "fp" | "da" | "bp" | "glut" | "gaba" | "bmp" | "fore" | "cell" | "exprLo" | "exprMid" | "exprHi", RGB> & {
  dish: string; line: string; ink: string; ink2: string; ink3: string; dim: string; solid: string; warn: string; violet: string; cloud: number;
};

const FALLBACK: Record<string, string> = {
  "--wb-trunk": "#9cc9c0", "--wb-fp": "#a88cf2", "--wb-da": "#7f63dc", "--wb-bp": "#f4b56f", "--wb-glut": "#ea9a58",
  "--wb-gaba": "#f2cb7e", "--wb-bmp": "#66ceb2", "--wb-fore": "#86b5ff", "--wb-cell": "#7fb9b0", "--wb-dish": "#f7fbfa",
  "--wb-line": "#e1e9e7", "--wb-ink": "#1c2632", "--wb-ink-2": "#5a6676", "--wb-ink-3": "#97a3b0", "--wb-dim": "rgba(28,38,50,.16)",
  "--wb-solid": "#ffffff", "--wb-warn": "#e0952f", "--wb-cloud": "0.9", "--wb-expr-lo": "#d9e2e6", "--wb-expr-mid": "#4fa79c", "--wb-expr-hi": "#3b2a8c",
};

const hex = (value: string): RGB => {
  const h = value.replace("#", "").trim();
  return h.length === 6 ? [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)] : [128, 128, 128];
};

export function readPalette(element: Element | null): Palette {
  const style = element ? getComputedStyle(element) : null;
  const get = (name: string) => style?.getPropertyValue(name).trim() || FALLBACK[name];
  return {
    trunk: hex(get("--wb-trunk")), fp: hex(get("--wb-fp")), da: hex(get("--wb-da")), bp: hex(get("--wb-bp")),
    glut: hex(get("--wb-glut")), gaba: hex(get("--wb-gaba")), bmp: hex(get("--wb-bmp")), fore: hex(get("--wb-fore")), cell: hex(get("--wb-cell")),
    exprLo: hex(get("--wb-expr-lo")), exprMid: hex(get("--wb-expr-mid")), exprHi: hex(get("--wb-expr-hi")),
    dish: get("--wb-dish"), line: get("--wb-line"), ink: get("--wb-ink"), ink2: get("--wb-ink-2"), ink3: get("--wb-ink-3"),
    dim: get("--wb-dim"), solid: get("--wb-solid"), warn: get("--wb-warn"), violet: get("--wb-fp"), cloud: Number(get("--wb-cloud")) || 0.9,
  };
}

/** Linear colour between two endpoints, t in [0, 1]. */
export const mix = (a: RGB, b: RGB, t: number): RGB => a.map((v, i) => Math.round(v + (b[i] - v) * Math.max(0, Math.min(1, t)))) as RGB;

/** Expression colour: low → mid → high, so middling values stay distinguishable from both ends. */
export const ramp = (p: Palette, t: number): RGB => t <= 0.5 ? mix(p.exprLo, p.exprMid, t * 2) : mix(p.exprMid, p.exprHi, (t - 0.5) * 2);

export const rgba = ([r, g, b]: RGB, alpha: number) => `rgba(${r},${g},${b},${Math.max(0, Math.min(1, alpha))})`;

export function seeded(seed: number) {
  let state = seed % 2147483647 || 1;
  return () => (state = (state * 16807) % 2147483647) / 2147483647;
}
