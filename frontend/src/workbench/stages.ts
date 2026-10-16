import type { Pathway, Protocol, Stage, StageWindow } from "./types";

export const ROMAN = ["", "I", "II", "III", "IV"] as const;
export const STAGE_NAMES = ["扩增期", "神经诱导", "底板诱导", "底板祖细胞", "神经元成熟"] as const;

/** Default stage windows (inclusive days); a structured protocol may override them. */
export const DEFAULT_WINDOWS: readonly StageWindow[] = [
  { index: 1, start: 0, end: 4 }, { index: 2, start: 5, end: 10 }, { index: 3, start: 11, end: 16 }, { index: 4, start: 17, end: Infinity },
];

/** Stage of a culture day; a day between or after custom windows stays in the last stage reached. */
export function stageIndex(day: number, windows: readonly StageWindow[] = DEFAULT_WINDOWS): 0 | 1 | 2 | 3 | 4 {
  if (day < 0) return 0;
  const list = windows.length ? windows : DEFAULT_WINDOWS;
  const hit = list.find(w => day >= w.start && day <= w.end) ?? [...list].reverse().find(w => w.start <= day) ?? list[0];
  return hit.index;
}

/**
 * Day spans [from, to) for the expansion phase and Stages I–IV. Custom windows replace the defaults
 * index by index; the last stage runs to the end of the protocol.
 */
export function stageSpans(windows: readonly StageWindow[] | undefined, pre: number): [number, number][] {
  const custom = new Map((windows ?? []).map(w => [w.index, w]));
  const spans: [number, number][] = [[-pre, 0]];
  for (const fallback of DEFAULT_WINDOWS) {
    const w = custom.get(fallback.index) ?? fallback;
    spans.push([w.start, w.end + 1]);
  }
  spans[4] = [spans[4][0], Infinity];
  return spans;
}

export function stageOf(protocol: Protocol): Stage {
  if (protocol.state === "draft") return { index: 0, tag: "未开始", name: "等待方案" };
  if (protocol.state === "frozen") return { index: 4, tag: "冻存", name: "待移植" };
  if (protocol.state === "grafted") return { index: 4, tag: "移植后", name: `第 ${protocol.graftWeeks ?? 0} 周` };
  const server = protocol.stageIndex;
  const index = protocol.state === "expanding" ? 0
    : server !== undefined && server !== null && server >= 1 && server <= 4 ? server as 1 | 2 | 3 | 4 : stageIndex(protocol.day, protocol.stages);
  return {
    index,
    tag: index ? `D${protocol.day} · Stage ${ROMAN[index]}` : `D${protocol.day}`,
    name: STAGE_NAMES[index],
  };
}

export type WallGroup = "live" | "done" | "grafted";
export function wallGroup(protocol: Protocol): WallGroup {
  if (protocol.state === "grafted") return "grafted";
  if (protocol.state === "frozen" || protocol.day >= protocol.totalDays) return "done";
  return "live";
}

export const PATHWAYS: { id: Pathway; name: string; level: number | null }[] = [
  { id: "smad", name: "SMAD 抑制", level: 1 },
  { id: "wnt", name: "WNT", level: 2 },
  { id: "fgf", name: "FGF", level: 2 },
  { id: "shh", name: "SHH", level: 3 },
  { id: "notch", name: "Notch", level: 4 },
  { id: "maturation", name: "成熟与存活", level: 4 },
  { id: "other", name: "其他", level: null },
];

export const CHAIN_NAMES = ["脱离多能", "神经谱系", "中脑定位", "底板化", "DA 命运"] as const;
export const CHAIN_SHORT = ["多能", "神经", "中脑", "底板", "DA"] as const;
export const LOW_LEVEL = 0.6;

/** Lowest chain level below the review threshold, if any. */
export function weakestLevel(chain: readonly (number | null)[]): number | null {
  let found: number | null = null;
  chain.forEach((value, index) => {
    if (value !== null && value < LOW_LEVEL && (found === null || value < (chain[found] as number))) found = index;
  });
  return found;
}

/** Product of the five levels, or null when any level is missing. */
export const targetFraction = (chain: readonly (number | null)[]) =>
  chain.some(value => value === null) ? null : chain.reduce<number>((product, value) => product * (value as number), 1);

export const isLow = (value: number | null | undefined) => value !== null && value !== undefined && value < LOW_LEVEL;
