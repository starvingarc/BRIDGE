import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { ResearchWorkbench } from "../src/workbench/ResearchWorkbench";
import { ANALYSES_POLL_MS } from "../src/workbench/analyses";
import { measured, profileReasons, readinessNote } from "../src/workbench/qc";
import { Histogram } from "../src/workbench/QcCharts";
import type { Research } from "../src/types";
import type { AnalysisDTO, AssessmentDTO, ProtocolVersionDTO, RunDTO, SampleDTO, WorkbenchDTO } from "../src/workbench/objects";

const hex = (c: string) => c.repeat(32);
const version: ProtocolVersionDTO = { id: hex("1"), protocol_id: hex("p"), version: 1, status: "confirmed", based_on_version_id: null, total_days: 60,
  confirmed_at: "2026-10-01T00:00:00Z", revision: 1, reagents: [] };
const run: RunDTO = { id: hex("r"), research_id: hex("e"), name: "第 1 轮", protocol_version_id: version.id, cell_line: "H9", start_date: "2026-08-20",
  state: "differentiating", graft: null, day: 46, stage_index: 4, today: [], revision: 1 };
const early: SampleDTO = { id: hex("s"), run_id: run.id, day: 16, collected_on: null, assay: "scRNA-seq", material_id: hex("m"), session_id: null,
  assessment_id: hex("a"), revision: 3, status: "done" };
const late: SampleDTO = { id: hex("t"), run_id: run.id, day: 46, collected_on: null, assay: "scRNA-seq", material_id: hex("n"), session_id: null,
  assessment_id: null, revision: 2, status: "mapping" };
const mapped: AssessmentDTO = {
  id: hex("a"), sample_id: early.id, status: "done",
  versions: { atlas: "chen-vmb", naming: "l3", metrics: "not_computed", reference: "REF-CHEN-VMB-SC-v1", method: "ATLAS-ingest-quick-v0.1", tree: "f".repeat(64) },
  chain: [], target_fraction: null, gestation: [], tree_position: { RG_mFP: 0.9 }, mapped_cells: [], alerts: [], failure: null,
  method_label: "快速映射 v0", scientific_status: "candidate", ood_status: "not_calibrated", n_cells: 1000, n_tree_cells: 900, tree_unavailable_cells: 100, limitations: [],
};
const workbench = (samples: SampleDTO[]): WorkbenchDTO => ({
  protocols: [{ id: hex("p"), research_id: hex("e"), name: "Protocol A", origin: "lab", citation: null, latest_version_id: version.id, latest: version, versions: [version], revision: 1 }],
  runs: [run], samples, assessments: [mapped], leads: [], actions: [],
});
/** A registered automatic QC as the sample analysis list returns it (docs/sample-analysis-api.md §11). */
const qc = (patch: Partial<AnalysisDTO> = {}): AnalysisDTO => ({
  source_kind: "sample_qc", assessment_id: hex("b"), id: hex("q"), research_id: hex("e"), sample_id: late.id, run_id: run.id, version: 1,
  created_at: "2026-10-14T06:18:02Z", session_id: null, receipt_sha256: "0".repeat(64), execution_state: "succeeded",
  tool: { id: "P0-01", version: "0.1.6", run_id: "run-1", environment_spec_id: "ENV-P0-CORE-v0.1" }, material_id: late.material_id!,
  input_assets: [{ asset_id: late.material_id!, format: "h5ad", input_level: "count_ready", matrix_location: "X", matrix_semantics: "raw_counts", assay: "scRNA-seq" }],
  qc_summary: {
    state: "available", tool_id: "P0-01", execution_state: "succeeded", assay: "scRNA-seq", input_level: "count_ready", readiness_state: "limited",
    schema_integrity: { n_observations: 6760, observation_kind: "cells", n_genes: 21052, unique_cell_ids: true, unique_gene_ids: true },
    count_metrics_state: "measured", metrics: [], assessment_states: {}, selected_data_view: null, score_state: "unavailable", domain_score: null,
  },
  results: [], availability: { status: "available", reason_code: null }, ...patch,
});

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const research = { id: hex("e"), name: "研究", materials: [] } as unknown as Research;
const principal = { id: "u1", username: "wyx", role: "user" as const, must_change_password: false };

/** Serves the workbench and one answer per read of each sample's analyses; the last answer repeats. */
function mount(samples: SampleDTO[], analyses: Record<string, AnalysisDTO[][]>, files: Record<string, () => Response> = {}) {
  const reads: Record<string, number> = {};
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    if (path.endsWith("/workbench")) return json(workbench(samples));
    if (files[path]) return files[path]();
    const match = path.match(/\/samples\/(\w+)\/analyses$/);
    if (match) {
      const answers = analyses[match[1]] ?? [[]], n = reads[match[1]] = (reads[match[1]] ?? 0) + 1;
      return json({ analyses: answers[Math.min(n, answers.length) - 1] });
    }
    return json({ detail: "Not Found" }, 404);
  }));
  render(<ResearchWorkbench principal={principal} research={research} onSessions={() => undefined} onHome={() => undefined} />);
  return reads;
}
const tabs = () => screen.getByRole("navigation", { name: "分析" });

describe("a sampling point's panel", () => {
  afterEach(() => { vi.useRealTimers(); });

  it("opens a day still mapping on its QC, and shows QC once it is registered", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const reads = mount([early, late], { [late.id]: [[], [qc()]] });
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    const points = screen.getByRole("group", { name: "取样点" });
    expect(within(points).getAllByRole("button").map(b => b.textContent)).toEqual(["D16", "D46"]);
    fireEvent.click(within(points).getByRole("button", { name: "D46 scRNA-seq，映射中" }));
    expect(within(points).getByRole("button", { name: "D46 scRNA-seq，映射中" })).toHaveAttribute("aria-pressed", "true");
    expect(within(tabs()).getByRole("button", { name: "QC" })).toHaveAttribute("aria-pressed", "true");
    expect(within(tabs()).getByRole("button", { name: /映射/ })).toHaveTextContent("进行中");
    expect(await screen.findByText("QC 正在运行，完成后显示在这里。")).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(ANALYSES_POLL_MS + 10); });
    expect(await screen.findByText("6,760")).toBeInTheDocument();
    expect(reads[late.id]).toBeGreaterThanOrEqual(2);
    fireEvent.click(within(tabs()).getByRole("button", { name: /映射/ }));
    expect(screen.getByText(/正在映射到胎儿腹侧中脑图谱/)).toBeInTheDocument();
  });

  it("opens a mapped day on its mapping, and counts every registered analysis", async () => {
    mount([early, late], { [early.id]: [[qc({ sample_id: early.id }), { ...qc({ sample_id: early.id, id: hex("w"), version: 2 }), source_kind: "atlas_mapping", qc_summary: undefined }]] });
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    fireEvent.click(screen.getByRole("button", { name: "D16 scRNA-seq，已完成" }));
    expect(within(tabs()).getByRole("button", { name: "映射" })).toHaveAttribute("aria-pressed", "true");
    expect(await screen.findByRole("complementary", { name: "取样点摘要" })).toBeInTheDocument();
    expect(await within(tabs()).findByRole("button", { name: /^记录\s*2$/ })).toBeInTheDocument();
  });

  it("keeps a QC whose source changed as a record without its numbers", async () => {
    mount([late], { [late.id]: [[qc({ qc_summary: null, availability: { status: "unavailable", reason_code: "analysis_source_unavailable" } })]] });
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    fireEvent.click(screen.getByRole("button", { name: "D46 scRNA-seq，映射中" }));
    expect(await screen.findByText("这次 QC 的来源文件已改变或丢失。")).toBeInTheDocument();
    expect(screen.queryByText(/个细胞/)).not.toBeInTheDocument();
  });

  it("registers a sample on the day picked on the axis", async () => {
    mount([early], {});
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    expect(screen.queryByRole("form", { name: "登记样本" })).not.toBeInTheDocument();
    const row = screen.getByRole("group", { name: "取样点" });
    row.getBoundingClientRect = () => ({ left: 0, width: 630, top: 0, height: 30, right: 630, bottom: 30, x: 0, y: 0, toJSON: () => ({}) });
    fireEvent.mouseMove(row, { clientX: 300 });
    fireEvent.click(within(row).getByRole("button", { name: /^在 D\d+ 登记取样$/ }));
    const form = screen.getByRole("form", { name: "登记样本" });
    expect(within(form).getByLabelText("取样天")).toHaveValue(27);
  });

  it("shows readiness with its reasons, the counts and what QC did not assess, and says when the per-cell table cannot be read", async () => {
    const base = `/api/researches/${hex("e")}/analyses/${hex("q")}/results`;
    const artifact = (id: string, name: string, kind: "figure" | "table" | "evidence", media: string) => ({ id: hex(id), source_artifact_id: id, sha256: "0".repeat(64),
      display_sha256: null, artifact: { id: hex(id), name, kind, media_type: media, tool_id: "P0-01", content_class: "user_result" as const, access_state: "available" as const, url: `${base}/${hex(id)}` } });
    const summary = qc().qc_summary!;
    const full = qc({
      id: hex("x"),
      qc_summary: { ...summary, metrics: [
        { metric_name: "total_counts_median", raw_value: 5888.5, denominator: 6760, evidence_state: "measured", score_state: "unavailable", domain_score: null },
        { metric_name: "mitochondrial_fraction_median", raw_value: 0.02336, denominator: 6760, evidence_state: "measured", score_state: "unavailable", domain_score: null },
      ], assessment_states: { upstream_library_qc: "not_assessed", doublet_assessment: "not_assessed" } },
      results: [artifact("j", "qc_readiness_profile_v2.display-redacted.json", "evidence", "application/json"),
        artifact("k", "qc_metrics.parquet", "table", "application/vnd.apache.parquet"), artifact("l", "qc_overview.png", "figure", "image/png")],
    });
    mount([late], { [late.id]: [[full]] }, {
      [`${base}/${hex("j")}`]: () => json({ warnings: ["capture_id_not_declared"], missing_inputs: ["measurement_spec_not_selected"],
        upstream_library_qc: { state: "not_assessed", reason: "upstream_report_not_provided" }, doublet_assessment: { state: "not_assessed", reason: "capture_id_not_declared" } }),
      [`${base}/${hex("k")}`]: () => json({ detail: "error" }, 500),
    });
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    fireEvent.click(screen.getByRole("button", { name: "D46 scRNA-seq，映射中" }));
    expect(await screen.findByText("可用性 有限")).toBeInTheDocument();
    expect(await screen.findByTitle(/未声明 capture 标识；2 项上游检查未评估/)).toBeInTheDocument();
    expect(screen.getByText("5,889")).toBeInTheDocument();
    expect(screen.getByText("2.3%")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "未评估" })).not.toBeInTheDocument();
    expect(await screen.findByText("结果文件读取失败。")).toBeInTheDocument();
    expect(screen.getByText("原图")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "下载数据" })).toHaveAttribute("href", `${base}/${hex("k")}`);
  });
});

describe("QC wording", () => {
  it("reads reasons defensively and never invents a missing one", () => {
    expect(profileReasons(null)).toEqual({ assessments: {}, warnings: [], missing: [], doublet: null });
    expect(profileReasons({ warnings: ["a", 3], doublet_assessment: { reason: 7 } })).toEqual({ assessments: {}, warnings: ["a"], missing: [], doublet: null });
    const summary = qc().qc_summary!;
    expect(readinessNote(summary, null)).toBe("结构检查通过，已计算逐细胞指标。");
    expect(readinessNote({ ...summary, schema_integrity: { ...summary.schema_integrity, unique_cell_ids: false } }, null)).toMatch("细胞或基因标识有重复");
  });

  it("keeps missing values missing and counts cells above the axis in their own bar", () => {
    expect([null, undefined, "", "x", 0, 3, BigInt(4)].map(measured)).toEqual([NaN, NaN, NaN, NaN, 0, 3, 4]);
    const values = Float64Array.from([...Array(999).fill(10), 1000]);
    const { container, unmount } = render(<Histogram title="总计数" values={values} unit="count" />);
    expect(container.querySelectorAll(".wb-qc-bar--over")).toHaveLength(1);
    unmount();
    render(<Histogram title="线粒体占比" values={Float64Array.from([0.02, NaN, 0.03])} unit="fraction" />);
    expect(screen.getByText("1 个细胞未测得")).toBeInTheDocument();
  });
});

describe("results bound to their own sample", () => {
  it("never shows another sample's mapping on a sample of the same day", async () => {
    const twin: SampleDTO = { ...late, id: hex("u"), day: 16, material_id: null, assessment_id: null, status: "collected" };
    mount([early, twin], {});
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    // Two samples of one day are its two batches: one marker, opened on both, then one batch at a time.
    fireEvent.click(screen.getByRole("button", { name: "D16，2 个批次" }));
    const both = screen.getByRole("complementary", { name: "D16 的 2 个批次" });
    fireEvent.click(within(within(both).getByRole("navigation", { name: "批次" })).getByRole("button", { name: "批次 2" }));
    const panel = screen.getByRole("complementary", { name: "D16 样本" });
    expect(within(panel).getByText(/测序数据关联后/)).toBeInTheDocument();
    expect(within(panel).queryByRole("complementary", { name: "取样点摘要" })).not.toBeInTheDocument();
    fireEvent.click(within(within(panel).getByRole("navigation", { name: "批次" })).getByRole("button", { name: "批次 1" }));
    expect(await within(screen.getByRole("complementary", { name: "D16 样本" })).findByRole("complementary", { name: "取样点摘要" })).toBeInTheDocument();
  });

  it("withdraws the mapping numbers when its registered analysis is no longer available", async () => {
    const gone = { ...qc({ sample_id: early.id, id: hex("w"), version: 2, assessment_id: mapped.id, qc_summary: undefined }),
      source_kind: "atlas_mapping" as const, availability: { status: "unavailable" as const, reason_code: "analysis_source_unavailable" } };
    mount([early], { [early.id]: [[gone]] });
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    fireEvent.click(screen.getByRole("button", { name: "D16 scRNA-seq，已完成" }));
    expect(await screen.findByText("这次映射的来源文件已改变或丢失。")).toBeInTheDocument();
    expect(screen.queryByRole("complementary", { name: "取样点摘要" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "展开发育树" })).not.toBeInTheDocument();
  });

  it("withdraws a QC's numbers, charts and files when the server says its source changed", async () => {
    const base = `/api/researches/${hex("e")}/analyses/${hex("y")}/results`;
    const file = (id: string, name: string, kind: "table" | "evidence", media: string) => ({ id: hex(id), source_artifact_id: id, sha256: "0".repeat(64), display_sha256: null,
      artifact: { id: hex(id), name, kind, media_type: media, tool_id: "P0-01", content_class: "user_result" as const, access_state: "available" as const, url: `${base}/${hex(id)}` } });
    const stale = qc({ id: hex("y"), results: [file("j", "profile.json", "evidence", "application/json"), file("k", "qc_metrics.parquet", "table", "application/vnd.apache.parquet")] });
    mount([late], { [late.id]: [[stale]] }, {
      [`${base}/${hex("j")}`]: () => json({ detail: "analysis_source_unavailable" }, 409),
      [`${base}/${hex("k")}`]: () => json({ detail: "analysis_source_unavailable" }, 409),
    });
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    fireEvent.click(screen.getByRole("button", { name: "D46 scRNA-seq，映射中" }));
    expect(await screen.findByText("这次 QC 的来源文件已改变或丢失。")).toBeInTheDocument();
    expect(screen.queryByText("6,760")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "下载数据" })).not.toBeInTheDocument();
  });
});
