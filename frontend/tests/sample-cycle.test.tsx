import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ResearchWorkbench } from "../src/workbench/ResearchWorkbench";
import { profileReasons } from "../src/workbench/qc";
import { joinRows } from "../src/workbench/cycle";
import type { Research } from "../src/types";
import type { AnalysisDTO, ProtocolVersionDTO, RunDTO, SampleDTO, WorkbenchDTO } from "../src/workbench/objects";

/** Parquet tables by the text the fake server sends as their bytes; the reader returns only the columns a table has. */
const tables: Record<string, Record<string, unknown>[]> = {};
vi.mock("hyparquet", () => {
  const name = (file: ArrayBuffer) => new TextDecoder().decode(file);
  return {
    parquetMetadata: (file: ArrayBuffer) => ({ name: name(file), num_rows: BigInt(tables[name(file)]?.length ?? 0) }),
    parquetSchema: (metadata: { name: string }) => ({ children: Object.keys(tables[metadata.name]?.[0] ?? {}).map(column => ({ element: { name: column } })) }),
    parquetReadObjects: async ({ file, columns }: { file: ArrayBuffer; columns: string[] }) =>
      (tables[name(file)] ?? []).map(row => Object.fromEntries(columns.map(c => [c, row[c]]))),
  };
});

const hex = (c: string) => c.repeat(32);
const version: ProtocolVersionDTO = { id: hex("1"), protocol_id: hex("p"), version: 1, status: "confirmed", based_on_version_id: null, total_days: 60,
  confirmed_at: "2026-10-01T00:00:00Z", revision: 1, reagents: [] };
const run: RunDTO = { id: hex("r"), research_id: hex("e"), name: "H9 2026-08-20", protocol_version_id: version.id, cell_line: "H9", start_date: "2026-08-20",
  state: "differentiating", graft: null, day: 46, stage_index: 4, today: [], revision: 1 };
const sample: SampleDTO = { id: hex("t"), run_id: run.id, day: 46, collected_on: null, assay: "scRNA-seq", material_id: hex("n"), session_id: null,
  assessment_id: hex("b"), revision: 2, status: "failed" };
const workbench: WorkbenchDTO = {
  protocols: [{ id: hex("p"), research_id: hex("e"), name: "Protocol A", origin: "lab", citation: null, latest_version_id: version.id, latest: version, versions: [version], revision: 1 }],
  runs: [run], samples: [sample], assessments: [], leads: [], actions: [],
};
const results = (aid: string) => `/api/researches/${hex("e")}/analyses/${aid}/results`;
const artifact = (aid: string, id: string, name: string, kind: "table" | "evidence", media: string) => ({ id: hex(id), source_artifact_id: id, sha256: "0".repeat(64),
  display_sha256: null, artifact: { id: hex(id), name, kind, media_type: media, tool_id: "P0", content_class: "user_result" as const, access_state: "available" as const,
    url: `${results(aid)}/${hex(id)}` } });
const common = { research_id: hex("e"), sample_id: sample.id, run_id: run.id, created_at: "2026-10-14T06:18:02Z", session_id: null, receipt_sha256: "0".repeat(64),
  execution_state: "succeeded" as const, material_id: sample.material_id!, assessment_id: hex("b"), availability: { status: "available" as const, reason_code: null },
  input_assets: [{ asset_id: sample.material_id!, format: "h5ad", input_level: "count_ready", matrix_location: "X", matrix_semantics: "raw_counts", assay: "scRNA-seq" }] };

/** Each test uses its own QC id: what a QC's files said is remembered per analysis. */
const qc = (id = "q"): AnalysisDTO => ({ ...common, source_kind: "sample_qc", id: hex(id), version: 1,
  tool: { id: "P0-01", version: "0.1.6", run_id: "run-1", environment_spec_id: "ENV" },
  qc_summary: { state: "available", tool_id: "P0-01", execution_state: "succeeded", assay: "scRNA-seq", input_level: "count_ready", readiness_state: "limited",
    schema_integrity: { n_observations: 6, observation_kind: "cells", n_genes: 100, unique_cell_ids: true, unique_gene_ids: true },
    count_metrics_state: "measured", metrics: [], assessment_states: { doublet_assessment: "candidate" }, selected_data_view: null, score_state: "unavailable", domain_score: null },
  results: [artifact(hex(id), "j", "qc_readiness_profile_v2.display-redacted.json", "evidence", "application/json"),
    artifact(hex(id), "k", "qc_metrics.parquet", "table", "application/vnd.apache.parquet")] });

const cycle = (patch: Partial<NonNullable<NonNullable<AnalysisDTO["cell_cycle_summary"]>["cell_cycle"]>> = {}): AnalysisDTO => ({ ...common,
  source_kind: "sample_cell_cycle", id: hex("c"), version: 2, tool: { id: "P0-06", version: "0.2.0", run_id: "run-2", environment_spec_id: "ENV" },
  cell_cycle_summary: { n_observations: 6, interpretation_scope: "descriptive_only", domain_score: null, score_state: "unavailable",
    resource_ref: "RES-SEURAT-CC", resource_version: "updated-2019", resource_sha256: "0".repeat(64),
    cell_cycle: { assessment_state: "available", n_observations: 6, phase_counts: { G1: 3, S: 1, G2M: 1 }, s_g2m_fraction: 2 / 6,
      mean_s_score: 0, mean_g2m_score: 0, reason_codes: [], s_missing_genes: ["MCM2"], g2m_missing_genes: [], ...patch } },
  results: [artifact(hex("c"), "x", "exploratory_observation_scores.parquet", "table", "application/vnd.apache.parquet")] });

const doubletProfile = (captures: { capture_id: string; n_observations: number; n_predicted: number; threshold: number }[]) => ({
  doublet_assessment: { state: "candidate", method: "Scrublet", method_version: "0.2.3", n_assessed: 5, n_predicted: 1, fraction_predicted: 0.2,
    n_not_assessed_empty_counts: 1, per_capture: captures.map(c => ({ ...c, expected_doublet_rate: 0.06, simulated_score_histogram: { counts: [0, 2, 5, 1], bin_edges: [0, 0.25, 0.5, 0.75, 1] } })) } });

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const research = { id: hex("e"), name: "研究", materials: [] } as unknown as Research;
const principal = { id: "u1", username: "wyx", role: "user" as const, must_change_password: false };

/** Requests the panel sends to the server, in order. */
const posts: { url: string; body: unknown }[] = [];
function mount(analyses: AnalysisDTO[], profile: unknown = {}, extra: Record<string, () => Response> = {}, shown: SampleDTO = sample) {
  posts.length = 0;
  tables.qc = [10, 20, 30, 40, 50, 0].map((n, i) => ({ total_counts: n * 100, detected_genes: n * 50, scrublet_score: i === 5 ? null : [0.05, 0.1, 0.12, 0.2, 0.6][i],
    scrublet_class: i === 5 ? "not_assessed_empty_counts" : i === 4 ? "doublet" : "singlet" }));
  tables.cycle = ["G1", "G1", "G1", "S", "G2M", null].map((phase, i) => ({ observation_id: `c${i}`, cycle_S_score: i === 5 ? null : i / 10 - 0.2,
    cycle_G2M_score: i === 5 ? null : 0.1 - i / 20, phase }));
  const files: Record<string, () => Response> = {
    ...Object.fromEntries(analyses.filter(a => a.source_kind === "sample_qc").flatMap(a => [
      [`${results(a.id)}/${hex("j")}`, () => json(profile)], [`${results(a.id)}/${hex("k")}`, () => new Response("qc")]])),
    [`${results(hex("c"))}/${hex("x")}`]: () => new Response("cycle"),
    ...extra,
  };
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (init?.method === "POST") { posts.push({ url: path, body: JSON.parse(String(init.body)) }); return json({}); }
    if (path.endsWith("/workbench")) return json({ ...workbench, samples: [shown] });
    if (files[path]) return files[path]();
    if (path.endsWith(`/samples/${sample.id}/analyses`)) return json({ analyses });
    return json({ detail: "Not Found" }, 404);
  }));
  render(<ResearchWorkbench principal={principal} research={research} onSessions={() => undefined} onHome={() => undefined} />);
}
async function openSample() {
  fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
  fireEvent.click(screen.getByRole("button", { name: /^D46 scRNA-seq/ }));
}
const tabs = () => screen.getByRole("navigation", { name: "分析" });

describe("doublets in QC", () => {
  it("reads Scrublet candidates per capture and nothing from an assessment that did not run", () => {
    expect(profileReasons({ doublet_assessment: { state: "not_assessed", reason: "capture_id_not_declared" } }).doublet).toBeNull();
    expect(profileReasons({ doublet_assessment: { state: "candidate", n_assessed: "5" } }).doublet).toBeNull();
    expect(profileReasons(doubletProfile([{ capture_id: "L1", n_observations: 5, n_predicted: 1, threshold: 0.31 }])).doublet).toEqual({
      assessed: 5, predicted: 1, fraction: 0.2, emptyCells: 1, method: "Scrublet 0.2.3",
      captures: [{ captureId: "L1", cells: 5, predicted: 1, threshold: 0.31, expectedRate: 0.06, simulated: { counts: [0, 2, 5, 1], edges: [0, 0.25, 0.5, 0.75, 1] } }] });
    const bad = doubletProfile([{ capture_id: "L1", n_observations: 5, n_predicted: 1, threshold: 0.31 }]);
    bad.doublet_assessment.per_capture[0].simulated_score_histogram = { counts: [1, 2], bin_edges: [0, 1] };
    expect(profileReasons(bad).doublet!.captures[0].simulated).toBeNull();
  });

  it("shows the candidates and draws the threshold of a single capture", async () => {
    mount([qc()], doubletProfile([{ capture_id: "L1", n_observations: 5, n_predicted: 1, threshold: 0.31 }]));
    await openSample();
    fireEvent.click(within(tabs()).getByRole("button", { name: "QC" }));
    const box = await screen.findByRole("region", { name: "双细胞" });
    expect(within(box).getByRole("heading")).toHaveTextContent("双细胞 候选 1 个 · 20.0%");
    expect(await within(box).findByText("阈值 0.31")).toBeInTheDocument();
    expect(within(box).getByRole("img", { name: "双细胞分数分布，5 个细胞" })).toBeInTheDocument();
    expect(box.querySelectorAll(".wb-qc-bar--doublet")).toHaveLength(1);
    expect(box.querySelectorAll(".wb-qc-sim")).toHaveLength(1);
    expect(within(box).queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getByText("双细胞候选").previousSibling).toHaveTextContent("20.0%");
    expect(screen.queryByRole("region", { name: "未评估" })).not.toBeInTheDocument();
  });

  it("lists several captures with their own thresholds instead of one line for all", async () => {
    mount([qc("w")], doubletProfile([{ capture_id: "L1", n_observations: 3, n_predicted: 1, threshold: 0.31 }, { capture_id: "L2", n_observations: 2, n_predicted: 0, threshold: 0.25 }]));
    await openSample();
    fireEvent.click(within(tabs()).getByRole("button", { name: "QC" }));
    const box = await screen.findByRole("region", { name: "双细胞" });
    expect(within(box).getAllByRole("row").map(r => r.textContent)).toEqual(["捕获批次细胞候选阈值", "L131 · 33.3%0.31", "L220 · 0.0%0.25"]);
    await within(box).findByRole("img", { name: /双细胞分数分布/ });
    expect(within(box).queryByText(/^阈值 /)).not.toBeInTheDocument();
    expect(box.querySelectorAll(".wb-qc-sim")).toHaveLength(0);
  });
});

describe("the cell cycle in QC", () => {
  it("matches map cells to score rows by cell id, never by position", () => {
    const map = { ids: ["c4", "c0", null, "zz"], x: new Float64Array(4), y: new Float64Array(4) };
    expect(Array.from(joinRows(map, ["c0", "c1", "c2", "c3", "c4"]))).toEqual([4, 0, -1, -1]);
    expect(Array.from(joinRows(map, undefined))).toEqual([-1, -1, -1, -1]);
  });

  it("is a section of QC, shown only when a scoring is registered", async () => {
    mount([qc("a")]);
    await openSample();
    await within(tabs()).findByRole("button", { name: /^记录\s*1$/ });
    expect(within(tabs()).getAllByRole("button").map(b => b.textContent)).toEqual(["映射", "QC", "记录1"]);
    expect(await screen.findByText("6")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "细胞周期" })).not.toBeInTheDocument();
  });

  it("shows the phase shares, the per-cell scores and what the phases mean", async () => {
    mount([qc(), cycle()]);
    await openSample();
    const section = await screen.findByRole("region", { name: "细胞周期" });
    expect(within(section).getByText("33.3%")).toBeInTheDocument();
    const legend = screen.getByRole("group", { name: "周期阶段" });
    expect(within(legend).getAllByRole("button").map(b => b.textContent)).toEqual(["G13 · 50.0%", "S1 · 16.7%", "G2/M1 · 16.7%"]);
    expect(screen.getByText("1 个细胞无阶段，缺 1 个周期基因")).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: "每个细胞的 S 期与 G2/M 期评分" })).toBeInTheDocument();
    fireEvent.click(within(legend).getByRole("button", { name: /^S/ }));
    expect(within(legend).getByRole("button", { name: /^S/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("img", { name: "每个细胞的 S 期与 G2/M 期评分，突出 S" })).toBeInTheDocument();
    expect(screen.queryByText(/怎么读|逐细胞评分/)).not.toBeInTheDocument();
    expect(screen.queryByRole("figure", { name: /UMAP/ })).not.toBeInTheDocument();
  });

  it("shows the sample's UMAP by phase, joined to the scores by cell id, and recolours it by either score", async () => {
    tables.atlas = ["c4", "c0", "c1", "c2", "c3", "c5"].map((id, i) => ({ observation_id: id, umap_1: i, umap_2: i % 2, leiden: String(i % 2) }));
    const atlas: AnalysisDTO = { ...common, source_kind: "sample_cell_atlas", id: hex("u"), version: 3, tool: { id: "P0-02", version: "0.1.0", run_id: "run-3", environment_spec_id: "ENV" },
      // The marker table comes first; the map must still be read from the per-cell table.
      results: [artifact(hex("u"), "z", "expression_markers.parquet", "table", "application/vnd.apache.parquet"),
        artifact(hex("u"), "y", "expression_cells.parquet", "table", "application/vnd.apache.parquet")] };
    mount([qc("m"), cycle(), atlas], {}, { [`${results(hex("u"))}/${hex("y")}`]: () => new Response("atlas") });
    await openSample();
    expect(await screen.findByRole("img", { name: "UMAP，按阶段着色" })).toBeInTheDocument();
    const colour = screen.getByRole("group", { name: "UMAP 着色" });
    fireEvent.click(within(colour).getByRole("button", { name: "G2/M 评分" }));
    expect(screen.getByRole("img", { name: "UMAP，按G2/M 评分着色" })).toBeInTheDocument();
    expect(within(colour).getByRole("button", { name: "G2/M 评分" })).toHaveAttribute("aria-pressed", "true");
  });

  it("says why there are no scores rather than drawing empty charts", async () => {
    mount([qc("e"), cycle({ assessment_state: "not_assessed", phase_counts: null, s_g2m_fraction: null, reason_codes: ["cell_cycle_gene_coverage_insufficient"] })]);
    await openSample();
    const section = await screen.findByRole("region", { name: "细胞周期" });
    expect(within(section).getByText("数据里周期基因太少")).toBeInTheDocument();
    expect(within(section).queryByRole("img")).not.toBeInTheDocument();
  });

  it("opens from the records, and withdraws a scoring whose source changed", async () => {
    mount([qc(), { ...cycle(), cell_cycle_summary: null, availability: { status: "unavailable", reason_code: "analysis_source_unavailable" } }]);
    await openSample();
    fireEvent.click(await within(tabs()).findByRole("button", { name: /^记录/ }));
    const records = document.querySelector<HTMLElement>(".wb-records")!;
    expect(within(records).getByText("细胞周期")).toBeInTheDocument();
    expect(within(records).getAllByText("来源不可用")).toHaveLength(1);
    fireEvent.click(within(tabs()).getByRole("button", { name: "QC" }));
    expect(await screen.findByText("这次细胞周期的来源文件已改变或丢失。")).toBeInTheDocument();
  });
});

describe("doublets not detected", () => {
  const notAssessed = (id: string): AnalysisDTO => ({ ...qc(id), qc_summary: { ...qc(id).qc_summary!, assessment_states: { doublet_assessment: "not_assessed" } } });
  const profile = { doublet_assessment: { state: "not_assessed", reason: "capture_id_not_declared" } };
  const declared: SampleDTO = { ...sample, mapping_input: { matrix_location: "X", matrix_semantics: "raw_counts", sample_context: "pre_graft", source_family_id: "H9" } };

  it("says why, and declares the capture batch to run the standard analysis again", async () => {
    mount([notAssessed("f")], profile, {}, declared);
    await openSample();
    const box = await screen.findByRole("region", { name: "双细胞" });
    expect(await within(box).findByText("未声明 capture 标识")).toBeInTheDocument();
    const form = within(box).getByRole("form", { name: "补充捕获批次" });
    expect(within(form).getByRole("button", { name: "检测双细胞" })).toBeDisabled();
    fireEvent.change(within(form).getByLabelText("捕获批次名"), { target: { value: " GSM6194008 " } });
    fireEvent.click(within(form).getByRole("button", { name: "检测双细胞" }));
    expect(await within(box).findByText("D46 已开始重新分析，几分钟后可以看到双细胞结果。")).toBeInTheDocument();
    expect(posts).toEqual([{ url: `/api/researches/${hex("e")}/samples/${sample.id}/workflow`, body: { expected_version: 2,
      mapping_input: { matrix_location: "X", matrix_semantics: "raw_counts", sample_context: "pre_graft", source_family_id: "H9", capture_id: "GSM6194008" } } }]);
  });

  it("offers no form for a sample without a declaration", async () => {
    mount([notAssessed("g")], profile);
    await openSample();
    const box = await screen.findByRole("region", { name: "双细胞" });
    expect(await within(box).findByText("未声明 capture 标识")).toBeInTheDocument();
    expect(within(box).queryByRole("form")).not.toBeInTheDocument();
  });
});

describe("several batches on one day", () => {
  it("shares one marker, compares the batches side by side, and switches to one batch and back", async () => {
    const second: SampleDTO = { ...sample, id: hex("v"), material_id: hex("w"), mapping_input: { matrix_location: "X", matrix_semantics: "raw_counts",
      sample_context: "pre_graft", source_family_id: "H9", capture_id: "GSM2" } };
    const forSecond = (a: AnalysisDTO): AnalysisDTO => ({ ...a, sample_id: second.id });
    const qcB = forSecond({ ...qc("h"), qc_summary: { ...qc("h").qc_summary!, schema_integrity: { ...qc("h").qc_summary!.schema_integrity, n_observations: 9 } } });
    const byId: Record<string, AnalysisDTO[]> = { [sample.id]: [qc("i"), cycle()], [second.id]: [qcB] };
    tables.qc = [10, 20, 30, 40, 50, 0].map((n, i) => ({ total_counts: n * 100, detected_genes: n * 50, mitochondrial_fraction: i / 100 }));
    tables.cycle = ["G1", "G1", "G1", "S", "G2M", null].map((phase, i) => ({ observation_id: `c${i}`, cycle_S_score: 0, cycle_G2M_score: 0, phase }));
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith("/workbench")) return json({ ...workbench, samples: [sample, second] });
      for (const id of ["h", "i"]) {
        if (path === `${results(hex(id))}/${hex("j")}`) return json({});
        if (path === `${results(hex(id))}/${hex("k")}`) return new Response("qc");
      }
      const match = path.match(/\/samples\/(\w+)\/analyses$/);
      if (match) return json({ analyses: byId[match[1]] ?? [] });
      return json({ detail: "Not Found" }, 404);
    }));
    render(<ResearchWorkbench principal={principal} research={research} onSessions={() => undefined} onHome={() => undefined} />);
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    const marker = screen.getByRole("button", { name: "D46，2 个批次" });
    expect(marker).toHaveTextContent("D46×2");
    fireEvent.click(marker);
    const panel = screen.getByRole("complementary", { name: "D46 的 2 个批次" });
    const table = within(panel).getByRole("table", { name: "各批次 QC" });
    await waitFor(() => expect(within(table).getAllByRole("row").map(r => r.textContent?.split("—")[0])).toEqual(
      ["批次细胞总计数检测基因线粒体占比双细胞S/G2M", "批次 16", "GSM29"]));
    expect(await within(panel).findByRole("img", { name: "总计数，按批次叠画" })).toBeInTheDocument();
    expect(within(panel).getByRole("img", { name: /^批次 1：G1 50.0%/ })).toBeInTheDocument();
    fireEvent.click(within(within(panel).getByRole("navigation", { name: "批次" })).getByRole("button", { name: "GSM2" }));
    const one = screen.getByRole("complementary", { name: "D46 样本" });
    expect(within(within(one).getByRole("navigation", { name: "批次" })).getByRole("button", { name: "GSM2" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(within(within(one).getByRole("navigation", { name: "批次" })).getByRole("button", { name: "全部批次" }));
    expect(screen.getByRole("complementary", { name: "D46 的 2 个批次" })).toBeInTheDocument();
  });
});
