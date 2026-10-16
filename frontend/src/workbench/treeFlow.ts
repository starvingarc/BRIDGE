/**
 * A run's sample drawn as a flow along the developmental tree's own branches: from hPSC to the root, then down every
 * branch, each segment as wide as the share of all cells that reached that branch or anything below it.
 */
import type { DevTree, Protocol, Sample } from "./types";

/** `from` is a tree node index, or -1 for hPSC. `share` is out of all cells of the sample. */
export type FlowSegment = { from: number; to: number; share: number };

/** Segments below this share are not drawn or hit. */
export const MIN_SHARE = 0.01;

/** Flow of one sample: cells of a label stop at its node, so a branch carries its own share plus everything downstream. */
export function flowOf(tree: DevTree, weights: Record<string, number>): FlowSegment[] {
  const children = new Map<number, number[]>(), parent = new Map<number, number>();
  for (const [child, up] of tree.edges) {
    parent.set(child, up);
    children.set(up, [...(children.get(up) ?? []), child]);
  }
  const own = tree.subtypes.map(name => Math.max(0, weights[name] ?? 0));
  const memo = new Map<number, number>();
  const reach = (node: number, seen = new Set<number>()): number => {
    if (memo.has(node)) return memo.get(node)!;
    if (seen.has(node)) return 0;
    seen.add(node);
    const total = own[node] + (children.get(node) ?? []).reduce((sum, c) => sum + reach(c, seen), 0);
    memo.set(node, total);
    return total;
  };
  const segments: FlowSegment[] = [];
  tree.subtypes.forEach((_, node) => {
    const share = reach(node);
    if (share > 0) segments.push({ from: parent.get(node) ?? -1, to: node, share });
  });
  return segments;
}

/** Mapped results belong to one exact tree; on any other tree (or the synthetic one) nothing of them is drawn. */
export const onThisTree = (sample: Sample, tree: DevTree) =>
  !sample.mapping || (!tree.synthetic && !!tree.version && sample.mapping.treeVersion === tree.version);

/** The sample a run shows on the tree: the opened one for the focused run, otherwise the latest. */
export const shownIndex = (protocol: Protocol, focus: Protocol | null, sampleIndex: number | null) =>
  focus === protocol && sampleIndex !== null ? sampleIndex : protocol.samples.length - 1;

/** Distance from point (x, y) to the segment a–b, in screen pixels. */
export function segmentDistance(x: number, y: number, ax: number, ay: number, bx: number, by: number) {
  const dx = bx - ax, dy = by - ay, length = dx * dx + dy * dy;
  const t = length ? Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / length)) : 0;
  return Math.hypot(x - (ax + t * dx), y - (ay + t * dy));
}

/** On-screen width of a segment: proportional to its share, with a floor so a thin branch stays visible. */
export const bandWidth = (share: number, scale: number) => Math.max(1.5, 22 * share) * Math.min(1.6, Math.sqrt(Math.max(0.6, scale)));
