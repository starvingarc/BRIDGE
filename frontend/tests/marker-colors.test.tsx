import { fireEvent, render, screen, within } from "@testing-library/react";
import { ResearchWorkbench } from "../src/workbench/ResearchWorkbench";
import { expressionCeiling, mappingView, markerMismatch, markerPanel } from "../src/workbench/mapping";
import type { AssessmentDTO, MarkerExpressionDTO, ProtocolVersionDTO, RunDTO, SampleDTO, WorkbenchDTO } from "../src/workbench/objects";
import type { Research } from "../src/types";

const hex = (c: string) => c.repeat(32);
const TREE = "t".repeat(64), FEATURES = "f".repeat(64), NORM = "shared_gene_counts_log1p_target_10000";
const version: ProtocolVersionDTO = { id: hex("1"), protocol_id: hex("p"), version: 1, status: "confirmed", based_on_version_id: null, total_days: 60,
  confirmed_at: "2026-10-01T00:00:00Z", revision: 1, reagents: [] };
const run: RunDTO = { id: hex("r"), research_id: hex("e"), name: "第 1 轮", protocol_version_id: version.id, cell_line: "H9", start_date: "2026-08-20",
  state: "differentiating", graft: null, day: 46, stage_index: 4, today: [], revision: 1 };
const sample: SampleDTO = { id: hex("s"), run_id: run.id, day: 46, collected_on: "2026-10-05", assay: "scRNA-seq", material_id: hex("m"), session_id: null,
  assessment_id: hex("a"), revision: 3, status: "done" };
const assessment: AssessmentDTO = {
  id: hex("a"), sample_id: sample.id, status: "done",
  versions: { atlas: "", naming: "", metrics: "not_computed", reference: "REF", tree: TREE, features: FEATURES },
  chain: [0, 1, 2, 3, 4].map(level => ({ level, name: "", numerator: null, denominator: null, value: null, reason: "chain_not_computed" })),
  target_fraction: null, gestation: [], tree_position: { RG_mFP: 0.9 }, alerts: [], failure: null,
  mapped_cells: [[0.2, 0.1, 0, 1], [0.2, 0.1, 0, 1], [0.3, 0.1, 0, 1]],
  method_label: "快速映射 v0", scientific_status: "candidate", n_cells: 3, tree_unavailable_cells: 0, normalization: NORM,
  marker_expression: { status: "available", genes: ["FOXA2", "TH", "CORIN"], n_sample_points: 3, n_reference_points: 1 },
};
const panel: MarkerExpressionDTO = {
  object_version: "0.1.0", genes: ["FOXA2", "TH", "CORIN"], tree_version: TREE, feature_set_sha256: FEATURES, normalization: NORM,
  gene_status: [{ gene: "FOXA2", status: "available", missing_from: [] }, { gene: "TH", status: "available", missing_from: [] },
    { gene: "CORIN", status: "not_in_shared_gene_space", missing_from: ["query"] }],
  sample: { values: [[1.2, 0, null], [0.8, 0.5, null], [2, 0, null]] },
  reference: { tree_cell_indices: [0], values: [[1.5, 0.1, null]], excluded_reason: "not_in_mapping_reference" },
};
const tree = { subtypes: ["Progenitor_root", "RG_mFP"], nodes: [[0, 0, 0], [0.2, 0.1, 0]], edges: [[1, 0]],
  cells: [[0.2, 0.1, 0, 1, 8, 0.4, 1], [0.25, 0.1, 0, 1, 9, 0.5, 1]], source: "test tree", version: TREE };
const dto: WorkbenchDTO = {
  protocols: [{ id: hex("p"), research_id: hex("e"), name: "Protocol A", origin: "lab", citation: null, latest_version_id: version.id, latest: version, versions: [version], revision: 1 }],
  runs: [run], samples: [sample], assessments: [assessment], leads: [], actions: [],
};
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function mount(markerResponse: () => Response, workbench: WorkbenchDTO = dto) {
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input); calls.push(path);
    if (path.endsWith("/workbench")) return json(workbench);
    if (path === "/api/workbench/devtree") return json(tree);
    if (path.endsWith("/marker-expression")) return markerResponse();
    return json({ detail: "Not Found" }, 404);
  }));
  render(<ResearchWorkbench principal={{ id: "u1", username: "wyx", role: "user", must_change_password: false }}
    research={{ id: hex("e"), name: "研究", materials: [] } as unknown as Research} onSessions={() => undefined} onHome={() => undefined} />);
  return calls;
}
async function openSample() {
  fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
  fireEvent.click(screen.getByRole("button", { name: "D46 scRNA-seq，已完成" }));
  fireEvent.click(await screen.findByRole("button", { name: "展开发育树" }));
  return within(await screen.findByRole("dialog", { name: "D46 发育树" })).findByRole("complementary", { name: "取样点摘要" });
}

describe("marker expression panel", () => {
  it("reads rows in server order and keeps missing values missing", () => {
    const read = markerPanel(panel);
    expect(read.sample[0]).toEqual([1.2, 0.8, 2]);
    expect(read.sample[2]).toEqual([null, null, null]);
    expect(read.reference.get(0)).toEqual([1.5, 0.1, null]);
    expect(read.reference.has(1)).toBe(false);
    expect(read.genes[2]).toEqual({ gene: "CORIN", available: false, missingFrom: ["query"] });
  });

  it("refuses to colour when tree, gene set or normalisation differ", () => {
    const view = mappingView(assessment), read = markerPanel(panel);
    expect(markerMismatch(read, view, TREE)).toBeNull();
    expect(markerMismatch(read, view, "x".repeat(64))).toMatch("不是同一版本");
    expect(markerMismatch(read, view, undefined)).toMatch("不是同一版本");
    expect(markerMismatch({ ...read, features: "g".repeat(64) }, view, TREE)).toMatch("基因集合不一致");
    expect(markerMismatch({ ...read, normalization: "other" }, view, TREE)).toMatch("归一化方式");
  });

  it("caps the colour scale near the top of measured values", () => {
    expect(expressionCeiling([null, 0, 1, 2])).toBe(2);
    expect(expressionCeiling([null])).toBe(0);
    expect(expressionCeiling([...Array(99).fill(1), 50])).toBe(50);
    expect(expressionCeiling([...Array(199).fill(1), 50])).toBe(1);
  });
});

describe("colouring the tree by gene", () => {
  it("offers genes for a result with stored expression, reading it only when asked", async () => {
    const calls = mount(() => json(panel));
    const lens = await openSample();
    expect(calls.some(c => c.endsWith("/marker-expression"))).toBe(false);
    fireEvent.click(within(screen.getByRole("group", { name: "着色" })).getByRole("button", { name: "基因" }));
    const key = await within(lens).findByRole("region", { name: "基因表达" });
    const genes = await within(key).findByRole("group", { name: "选择基因" });
    expect(within(genes).getByRole("button", { name: "FOXA2" })).toHaveAttribute("aria-pressed", "true");
    expect(within(genes).getByRole("button", { name: "CORIN" })).toBeDisabled();
    expect(within(genes).getByRole("button", { name: "CORIN" })).toHaveAttribute("title", "样本数据里没有测到这个基因");
    expect(within(key).getByLabelText("颜色从 0 到 2.0")).toBeInTheDocument();
    expect(within(key).getByText(/只展示表达，不判定阳性/)).toBeInTheDocument();
    fireEvent.click(within(genes).getByRole("button", { name: "TH" }));
    expect(within(genes).getByRole("button", { name: "TH" })).toHaveAttribute("aria-pressed", "true");
    expect(calls.filter(c => c.endsWith("/marker-expression"))).toHaveLength(1);
  });

  it("explains a result without stored expression and does not colour", async () => {
    mount(() => json({ detail: "marker_expression_unavailable" }, 404));
    const lens = await openSample();
    fireEvent.click(within(screen.getByRole("group", { name: "着色" })).getByRole("button", { name: "基因" }));
    expect(await within(lens).findByText("这次映射没有保存表达数据；较早的结果不会重新计算。")).toBeInTheDocument();
    expect(within(lens).queryByRole("group", { name: "选择基因" })).not.toBeInTheDocument();
  });

  it("does not colour with expression from another tree", async () => {
    mount(() => json({ ...panel, tree_version: "x".repeat(64) }));
    const lens = await openSample();
    fireEvent.click(within(screen.getByRole("group", { name: "着色" })).getByRole("button", { name: "基因" }));
    expect(await within(lens).findByText("表达数据和当前发育树不是同一版本，不着色。")).toBeInTheDocument();
    expect(within(lens).queryByLabelText(/颜色从/)).not.toBeInTheDocument();
  });

  it("has no gene colouring for a result without stored expression", async () => {
    mount(() => json(panel), { ...dto, assessments: [{ ...assessment, marker_expression: null }] });
    await openSample();
    expect(within(screen.getByRole("group", { name: "着色" })).queryByRole("button", { name: "基因" })).not.toBeInTheDocument();
  });
});
