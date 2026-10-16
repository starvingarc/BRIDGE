import { fireEvent, render, screen, within } from "@testing-library/react";
import { ResearchWorkbench } from "../src/workbench/ResearchWorkbench";
import type { Research } from "../src/types";
import { adaptWorkbench } from "../src/workbench/adapt";
import { branchBars, cellTypeName, mappingView, suggestedSourceFamily } from "../src/workbench/mapping";
import { MappingLens } from "../src/workbench/MappingLens";
import type { AssessmentDTO, ProtocolVersionDTO, RunDTO, SampleDTO, WorkbenchDTO } from "../src/workbench/objects";

const hex = (c: string) => c.repeat(32);
const version: ProtocolVersionDTO = { id: hex("1"), protocol_id: hex("p"), version: 1, status: "confirmed", based_on_version_id: null, total_days: 60,
  confirmed_at: "2026-10-01T00:00:00Z", revision: 1, reagents: [] };
const run: RunDTO = { id: hex("r"), research_id: hex("e"), name: "第 1 轮", protocol_version_id: version.id, cell_line: "H9", start_date: "2026-08-20",
  state: "differentiating", graft: null, day: 46, stage_index: 4, today: [], revision: 1 };
const sample: SampleDTO = { id: hex("s"), run_id: run.id, day: 46, collected_on: "2026-10-05", assay: "scRNA-seq", material_id: hex("m"), session_id: null,
  assessment_id: hex("a"), revision: 3, status: "done" };
/** Shape of a quick mapping v0 result as the server returns it (contract §7.6). */
const quick: AssessmentDTO = {
  id: hex("a"), sample_id: sample.id, status: "done",
  versions: { atlas: "chen-vmb", naming: "l3", metrics: "not_computed", reference: "REF-CHEN-VMB-SC-v1", method: "ATLAS-ingest-quick-v0.1", tree: "f".repeat(64) },
  chain: ["脱离多能", "神经谱系", "中脑定位", "底板化", "DA 命运"].map((name, level) => ({ level, name, numerator: null, denominator: null, value: null, reason: "chain_not_computed" })),
  target_fraction: null,
  gestation: [
    { cell_type: "RG_mFP", weeks: { "8": 0.6, "9": 0.4 }, outside_reference: null, status: "uncalibrated_neighbor_distribution" },
    { cell_type: "Nb_mBIP", weeks: { "9": 1 }, outside_reference: null, status: "uncalibrated_neighbor_distribution" },
    { cell_type: "Pericyte", weeks: { "20": 1 }, outside_reference: null, status: "uncalibrated_neighbor_distribution" },
  ],
  tree_position: { RG_mFP: 0.41, Nb_mFP: 0.22, Nb_mBIP: 0.18, Neuron_DA: 0.08, Neuron_Glut_H: 0.05 },
  mapped_cells: [[0.1, 0.2, 0.3, 16]], alerts: [], failure: null,
  method_label: "快速映射 v0", scientific_status: "candidate", ood_status: "not_calibrated", n_cells: 1000, n_tree_cells: 940, tree_unavailable_cells: 60,
  limitations: ["closed_set_label_transfer_not_ood_detection", "chain_not_computed"],
};
const dto = (assessment: AssessmentDTO): WorkbenchDTO => ({
  protocols: [{ id: hex("p"), research_id: hex("e"), name: "Protocol A", origin: "lab", citation: null, latest_version_id: version.id, latest: version, versions: [version], revision: 1 }],
  runs: [run], samples: [sample], assessments: [assessment], leads: [], actions: [],
});

describe("atlas label names", () => {
  it("names the floor plate in words and keeps regional codes that are still under review", () => {
    expect(cellTypeName("RG_mFP")).toBe("底板 放射胶质");
    expect(cellTypeName("Nb_mFP")).toBe("底板 神经母细胞");
    expect(cellTypeName("Nb_mBIP")).toBe("mBIP 神经母细胞");
    expect(cellTypeName("Neuron_DA")).toBe("多巴胺能神经元");
    expect(cellTypeName("Neuron_Glut_H")).toBe("谷氨酸能神经元 H");
    expect(cellTypeName("Neuron_Glut_GABA")).toBe("谷氨酸/GABA 能神经元");
    expect(cellTypeName("Pericyte")).toBe("Pericyte");
  });

  it("suggests the cell line as source group and falls back to the run when it cannot be written that way", () => {
    const info = { id: hex("r"), revision: 1, name: "", startDate: null, state: "differentiating" as const, graft: null, protocolVersionId: "" };
    expect(suggestedSourceFamily({ ...info, cellLine: "H9 (WA09)" })).toBe("H9-WA09");
    expect(suggestedSourceFamily({ ...info, cellLine: "人胚干细胞" })).toBe(`run-${hex("r").slice(0, 8)}`);
    expect(suggestedSourceFamily({ ...info, cellLine: null })).toBe(`run-${hex("r").slice(0, 8)}`);
  });
});

describe("quick mapping result", () => {
  it("keeps every share out of all cells and never reads missing chain levels as fine", () => {
    const point = adaptWorkbench(dto(quick)).protocols.find(p => p.run)!.samples[0];
    expect(point.note).toBe("落在底板 放射胶质最多（41%）");
    expect(point.note).not.toContain("未见偏低");
    expect(point.gestation).toBe("近邻参考 ≈ GW8–9");
    expect(point.mapping).toMatchObject({ method: "快速映射 v0", candidate: true, offTree: 0.06, cells: 1000, treeVersion: "f".repeat(64), chainMissing: true });
    expect(point.mapping!.branches.map(b => b.label)).toEqual(["RG_mFP", "Nb_mFP", "Nb_mBIP", "Neuron_DA", "Neuron_Glut_H"]);
    expect(branchBars(point.mapping!).map(b => [b.name, Math.round(b.share * 100)])).toEqual([
      ["底板 放射胶质", 41], ["底板 神经母细胞", 22], ["mBIP 神经母细胞", 18], ["其他 2 根枝", 13], ["未落在树上", 6]]);
  });

  it("gives a real result no illustrated cells when the server sent none", () => {
    const point = adaptWorkbench(dto({ ...quick, mapped_cells: undefined })).protocols.find(p => p.run)!.samples[0];
    expect(point.mappedCells).toEqual([]);
  });

  it("shows branch shares without a headline number, and the method behind them", () => {
    const point = adaptWorkbench(dto(quick)).protocols.find(p => p.run)!.samples[0];
    render(<MappingLens sample={point} onTree />);
    const lens = screen.getByRole("complementary", { name: "取样点摘要" });
    expect(within(lens).getByText("快速映射 v0 · 候选结果")).toBeInTheDocument();
    const bars = within(lens).getByRole("list", { name: "细胞落在哪些枝上" });
    expect(within(bars).getAllByRole("listitem").map(li => li.textContent)).toEqual([
      "底板 放射胶质41%", "底板 神经母细胞22%", "mBIP 神经母细胞18%", "其他 2 根枝13%", "未落在树上6%"]);
    expect(within(lens).getByText("分化链指标：尚未计算")).toBeInTheDocument();
    expect(within(lens).getByLabelText("图例")).toHaveTextContent("参考细胞当前样本");
    expect(within(lens).getByText("REF-CHEN-VMB-SC-v1")).toBeInTheDocument();
    expect(within(lens).getByText("只在参考已有的细胞类型里找最像的，发现不了参考里没有的细胞。")).toBeInTheDocument();
    expect(within(lens).queryByRole("note")).not.toBeInTheDocument();
  });

  it("says when the result belongs to another version of the tree", () => {
    const point = adaptWorkbench(dto(quick)).protocols.find(p => p.run)!.samples[0];
    render(<MappingLens sample={point} onTree={false} />);
    expect(screen.getByRole("note")).toHaveTextContent("发育树已更新，这次结果属于另一版树，暂不画细胞位置。");
    expect(screen.queryByLabelText("图例")).not.toBeInTheDocument();
  });

  it("does not invent a share when no cell reached the tree", () => {
    const view = mappingView({ ...quick, tree_position: {}, tree_unavailable_cells: 1000 });
    expect(branchBars(view)).toEqual([{ key: "off", name: "未落在树上", share: 1 }]);
  });
});

describe("opening a mapped sample", () => {
  const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  const research = { id: hex("e"), name: "研究", materials: [] } as unknown as Research;
  const mount = (tree: Record<string, unknown> | null) => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith("/workbench")) return json(dto(quick));
      if (path === "/api/workbench/devtree") return tree ? json(tree) : json({ detail: "Not Found" }, 404);
      return json({ detail: "Not Found" }, 404);
    }));
    render(<ResearchWorkbench principal={{ id: "u1", username: "wyx", role: "user", must_change_password: false }} research={research} onSessions={() => undefined} onHome={() => undefined} />);
  };
  const tree = (version: string) => ({ subtypes: ["Progenitor_root", "RG_mFP"], nodes: [[0, 0, 0], [0.2, 0.1, 0]], edges: [[1, 0]],
    cells: [[0.2, 0.1, 0, 1, 8, 0.4, 1]], source: "test tree", version });

  it("opens a sampling point on the flow straight into its summary, and the full tree on that day", async () => {
    mount(tree("f".repeat(64)));
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    fireEvent.click(screen.getByRole("button", { name: "D46 scRNA-seq，已完成" }));
    const panel = screen.getByRole("complementary", { name: "D46 样本" });
    const lens = await within(panel).findByRole("complementary", { name: "取样点摘要" });
    expect(within(lens).getByText("D46 · 近邻参考 ≈ GW8–9")).toBeInTheDocument();
    expect(within(lens).queryByRole("note")).not.toBeInTheDocument();
    fireEvent.click(within(panel).getByRole("button", { name: "展开发育树" }));
    const full = await screen.findByRole("dialog", { name: "D46 发育树" });
    expect(within(full).getByRole("note")).toHaveTextContent("落在底板 放射胶质最多（41%）");
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "D46 发育树" })).not.toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "D46 样本" })).toBeInTheDocument();
  });

  it("does not draw a result's cells on a different or synthetic tree", async () => {
    mount(null);
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    fireEvent.click(screen.getByRole("button", { name: "D46 scRNA-seq，已完成" }));
    const lens = await screen.findByRole("complementary", { name: "取样点摘要" });
    expect(within(lens).getByRole("note")).toHaveTextContent("发育树已更新，这次结果属于另一版树");
  });
});
