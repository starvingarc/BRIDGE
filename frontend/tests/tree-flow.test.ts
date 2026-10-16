import { bandWidth, flowOf, onThisTree, segmentDistance, shownIndex } from "../src/workbench/treeFlow";
import type { DevTree, Protocol, Sample } from "../src/workbench/types";

/** Shape of the fixed tree: root → RG → Nb → neuron classes → subtypes, edges as [child, parent]. */
const tree: DevTree = {
  subtypes: ["Progenitor_root", "RG_mFP", "Nb_mFP", "Neuron_DA", "RG_mBIP", "Nb_mBIP", "Neuron_Glut", "Neuron_Glut_H"],
  nodes: Array.from({ length: 8 }, (_, i) => [i / 10, 0, 0] as [number, number, number]),
  edges: [[1, 0], [2, 1], [3, 2], [4, 0], [5, 4], [6, 5], [7, 6]],
  cells: [], source: "test", version: "v1",
};
const byTo = (weights: Record<string, number>) => Object.fromEntries(flowOf(tree, weights).map(s => [tree.subtypes[s.to], [s.from, Number(s.share.toFixed(3))]]));

describe("flow along the tree", () => {
  it("carries each branch's own share plus everything below it, starting from hPSC", () => {
    const flow = byTo({ Neuron_DA: 0.61, Neuron_Glut_H: 0.2, Neuron_Glut: 0.11, RG_mFP: 0.01 });
    expect(flow.Progenitor_root).toEqual([-1, 0.93]);
    expect(flow.RG_mFP).toEqual([0, 0.62]);
    expect(flow.Nb_mFP).toEqual([1, 0.61]);
    expect(flow.Neuron_DA).toEqual([2, 0.61]);
    expect(flow.RG_mBIP).toEqual([0, 0.31]);
    expect(flow.Neuron_Glut).toEqual([5, 0.31]);
    expect(flow.Neuron_Glut_H).toEqual([6, 0.2]);
  });

  it("draws nothing for labels off the tree and never more than all cells", () => {
    expect(flowOf(tree, { Pericyte: 0.4 })).toEqual([]);
    const flow = flowOf(tree, { Neuron_DA: 0.5, Pericyte: 0.4 });
    expect(Math.max(...flow.map(s => s.share))).toBeCloseTo(0.5);
  });

  it("keeps a thin branch visible and widens with share", () => {
    expect(bandWidth(0.01, 1)).toBe(1.5);
    expect(bandWidth(0.6, 1)).toBeGreaterThan(bandWidth(0.3, 1));
  });

  it("measures pointer distance to a band", () => {
    expect(segmentDistance(5, 3, 0, 0, 10, 0)).toBe(3);
    expect(segmentDistance(-4, 3, 0, 0, 10, 0)).toBe(5);
  });

  it("shows the opened sample of the focused run, otherwise the latest", () => {
    const run = { samples: [{}, {}, {}] } as unknown as Protocol, other = { samples: [{}, {}] } as unknown as Protocol;
    expect(shownIndex(run, run, 0)).toBe(0);
    expect(shownIndex(run, null, null)).toBe(2);
    expect(shownIndex(other, run, 0)).toBe(1);
  });

  it("draws a mapped result only on the tree version it was placed on", () => {
    const mapped = { mapping: { treeVersion: "v1" } } as unknown as Sample;
    expect(onThisTree(mapped, tree)).toBe(true);
    expect(onThisTree(mapped, { ...tree, version: "v2" })).toBe(false);
    expect(onThisTree(mapped, { ...tree, synthetic: true })).toBe(false);
    expect(onThisTree({} as Sample, { ...tree, synthetic: true })).toBe(true);
  });
});
