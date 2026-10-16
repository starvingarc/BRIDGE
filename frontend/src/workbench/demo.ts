/**
 * Example workbench content for the standalone preview and tests.
 * Every protocol, dose and chain value here is illustrative and is not a laboratory or published record.
 */
import type { DevTree, Protocol, QueueItem, Reagent } from "./types";

const floorPlate = (overrides: Partial<Record<string, Partial<Reagent>>> = {}): Reagent[] => {
  const base: Reagent[] = [
    { id: "sb", name: "SB431542", short: "SB", pathway: "smad", kind: "molecule", dose: "10 μM", start: 0, end: 5, catalogId: "sb431542" },
    { id: "ldn", name: "LDN193189", short: "LDN", pathway: "smad", kind: "molecule", dose: "100 nM", start: 0, end: 11, catalogId: "ldn193189" },
    { id: "chir", name: "CHIR99021", short: "CHIR", pathway: "wnt", kind: "molecule", dose: "1.5 μM", start: 3, end: 13, catalogId: "chir99021" },
    { id: "fgf8", name: "FGF8b", short: "FGF8", pathway: "fgf", kind: "protein", dose: "100 ng/mL", start: 9, end: 16 },
    { id: "shh", name: "SHH C25II", short: "SHH", pathway: "shh", kind: "protein", dose: "100 ng/mL", start: 1, end: 7 },
    { id: "pm", name: "Purmorphamine", short: "PM", pathway: "shh", kind: "molecule", dose: "2 μM", start: 1, end: 7, catalogId: "purmorphamine" },
    { id: "dapt", name: "DAPT", short: "DAPT", pathway: "notch", kind: "molecule", dose: "10 μM", start: 16, end: 28, catalogId: "dapt" },
    { id: "bdnf", name: "BDNF", short: "BDNF", pathway: "maturation", kind: "protein", dose: "20 ng/mL", start: 11, end: 28 },
    { id: "gdnf", name: "GDNF", short: "GDNF", pathway: "maturation", kind: "protein", dose: "20 ng/mL", start: 11, end: 28 },
    { id: "aa", name: "Ascorbic acid", short: "AA", pathway: "maturation", kind: "molecule", dose: "0.2 mM", start: 11, end: 28, catalogId: "l-ascorbic-acid" },
    { id: "camp", name: "dbcAMP", short: "cAMP", pathway: "maturation", kind: "molecule", dose: "0.5 mM", start: 11, end: 28, catalogId: "db-camp" },
    { id: "b27", name: "N2 / B27", short: "N2/B27", pathway: "other", kind: "supplement", dose: "1×", start: 0, end: 28 },
  ];
  return base.map(item => ({ ...item, ...overrides[item.id] })).filter(item => (item.end ?? 0) > (item.start ?? 0));
};

export const demoProtocols: Protocol[] = [
  {
    id: "a", name: "示例方案 A v3", version: 3, state: "differentiating", day: 16, totalDays: 28,
    today: "取样后换液", lead: "底板化偏低", reagents: floorPlate(),
    samples: [
      { day: 11, position: { RG_mFP: 0.6, RG_mBIP: 0.4 }, chain: [0.99, 0.9, 0.84, 0.55, 0.4], gestation: "≈ GW7", note: "底板还没成形" },
      { day: 16, position: { RG_mFP: 0.3, Nb_mFP: 0.35, Nb_mBIP: 0.35 }, chain: [0.99, 0.92, 0.81, 0.48, 0.71], gestation: "≈ GW7–8", note: "一半长到了 mBIP 那根枝上" },
    ],
  },
  {
    id: "b", name: "示例方案 B · SHH 加量", version: 1, state: "differentiating", day: 9, totalDays: 28,
    today: "加 SHH 与 PM", reagents: floorPlate({ shh: { end: 9, dose: "200 ng/mL" }, pm: { end: 9 } }),
    samples: [],
  },
  { id: "c", name: "示例 H9 新批次", version: 1, state: "expanding", day: -2, totalDays: 28, today: "观察贴壁", reagents: floorPlate(), samples: [] },
  {
    id: "d", name: "示例方案 C", version: 2, state: "frozen", day: 16, totalDays: 16, today: "D16 冻存",
    reagents: floorPlate({ dapt: { end: 0 }, bdnf: { end: 16 }, gdnf: { end: 16 }, aa: { end: 16 }, camp: { end: 16 } }),
    samples: [
      { day: 11, position: { RG_mFP: 0.85, RG_mBIP: 0.15 }, chain: [0.99, 0.93, 0.86, 0.72, 0.5], gestation: "≈ GW7", note: "大多长在底板枝上" },
      { day: 16, position: { Nb_mFP: 0.7, RG_mFP: 0.3 }, chain: [0.99, 0.94, 0.85, 0.81, 0.73], gestation: "≈ GW7–8", note: "大多长在底板枝上" },
    ],
  },
  {
    id: "e", name: "示例方案 C · 移植批", version: 2, state: "grafted", day: 16, totalDays: 16, today: "待上传移植物数据", graftWeeks: 16,
    reagents: floorPlate({ dapt: { end: 0 } }), samples: [],
  },
  {
    id: "f", name: "示例方案 D", version: 1, state: "differentiating", day: 35, totalDays: 35, today: "已完成评估",
    reagents: floorPlate({ chir: { dose: "0.8 μM" }, dapt: { end: 35 }, bdnf: { end: 35 }, gdnf: { end: 35 } }),
    samples: [
      { day: 14, position: { RG_mFP: 0.7, RG_mBIP: 0.3 }, chain: [0.99, 0.91, 0.82, 0.66, 0.55], gestation: "≈ GW7", note: "大多长在底板枝上" },
      { day: 21, position: { Nb_mFP: 0.5, RG_mFP: 0.3, Nb_mBIP: 0.2 }, chain: [0.99, 0.92, 0.8, 0.69, 0.68], gestation: "≈ GW8", note: "大多长在底板枝上" },
      { day: 35, position: { Neuron_DA: 0.5, Nb_mFP: 0.3, Nb_mBIP: 0.2 }, chain: [0.99, 0.93, 0.8, 0.7, 0.79], gestation: "≈ GW9", note: "大多长在底板枝上" },
    ],
  },
  { id: "g", name: "CHIR 梯度", version: 1, state: "draft", day: 0, totalDays: 28, today: "上传方案", reagents: [], samples: [] },
];

export const demoQueue: QueueItem[] = [
  { id: "q1", title: "SHH 靶基因梯度分析", context: "示例方案 A · D16 · 解释底板化偏低", tier: "exploratory", eta: "约 3 分钟" },
  { id: "q2", title: "与示例方案 C 逐步对比方案", context: "示例方案 A · 全部天数", tier: "formal", eta: "约 1 分钟" },
];

/** Procedural tree with the atlas hierarchy, used when no private atlas payload is configured. */
export function syntheticTree(count = 3200): DevTree {
  const subtypes = ["Progenitor_root", "RG_mFP", "RG_mBIP", "RG_mBMP", "Nb_mFP", "Nb_mBIP", "Nb_mBMP", "Neuron_DA", "Neuron_Glut", "Neuron_GABA"];
  const nodes: [number, number, number][] = [
    [-1, 0, 0], [-0.9, 0.3, 0.12], [-0.85, -0.33, 0], [-0.84, 0.31, -0.12], [-0.22, 0.47, 0.17],
    [-0.44, -0.5, 0], [-0.39, 0.47, -0.17], [0.05, 0.63, 0.23], [-0.14, -0.51, -0.43], [-0.15, -0.12, 0.66],
  ];
  const edges: [number, number][] = [[1, 0], [2, 0], [3, 0], [4, 1], [5, 2], [6, 3], [7, 4], [8, 5], [9, 5]];
  const pseudotime = [0, 0.04, 0.08, 0.08, 0.39, 0.28, 0.3, 0.52, 0.43, 0.43];
  let seed = 7;
  const random = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const gauss = () => Math.sqrt(-2 * Math.log(random() || 1e-9)) * Math.cos(2 * Math.PI * random());
  const cells: DevTree["cells"] = [];
  for (let i = 0; i < count; i += 1) {
    const [child, parent] = edges[Math.floor(random() * edges.length)];
    const t = random();
    const a = nodes[parent], b = nodes[child];
    const p = pseudotime[parent] + (pseudotime[child] - pseudotime[parent]) * t;
    const point = [0, 1, 2].map(k => a[k] + (b[k] - a[k]) * t + gauss() * 0.04) as [number, number, number];
    point[0] = p * 2 - 1;
    const week = Math.round(7 + p * 18);
    cells.push([...point, t > 0.6 ? child : parent, week, Number(p.toFixed(3)), week <= 20 ? 1 : 0]);
  }
  return { subtypes, nodes, edges, cells, source: "合成示意树（未加载图谱数据）", synthetic: true };
}
