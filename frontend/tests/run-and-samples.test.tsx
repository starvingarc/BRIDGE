import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ResearchWorkbench } from "../src/workbench/ResearchWorkbench";
import { adaptWorkbench, libraryId } from "../src/workbench/adapt";
import type { ProtocolDTO, ProtocolVersionDTO, RunDTO, SampleDTO, WorkbenchDTO } from "../src/workbench/objects";
import type { Research } from "../src/types";

const principal = { id: "u1", username: "wyx", role: "user" as const, must_change_password: false };
const hex = (c: string) => c.repeat(32);
const research = { id: hex("e"), name: "mDA 祖细胞优化", materials: [
  { id: hex("m"), name: "D16.h5ad", kind: "h5ad", size: 1, created_at: "", locations: ["X", "layers/counts"] },
  { id: hex("n"), name: "方案.docx", kind: "protocol", size: 1, created_at: "" },
] } as unknown as Research;
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const version: ProtocolVersionDTO = {
  id: hex("1"), protocol_id: hex("p"), version: 1, status: "confirmed", based_on_version_id: null, total_days: 28, confirmed_at: "2026-10-01T00:00:00Z", revision: 2,
  reagents: [{ id: hex("a"), name: "CHIR99021", short: "CHIR", pathway: "wnt", kind: "molecule", dose_text: "1.5 μM", start_day: 3, end_day: 13, catalog_id: "chir99021", unconfirmed: [] }],
};
const protocol: ProtocolDTO = { id: hex("p"), research_id: research.id, name: "Protocol A", origin: "lab", citation: null, latest_version_id: version.id, latest: version, versions: [version], revision: 3 };
const run: RunDTO = { id: hex("r"), research_id: research.id, name: "第 1 轮", protocol_version_id: version.id, cell_line: "H9", start_date: "2026-09-26",
  state: "differentiating", graft: null, day: 16, stage_index: 3, today: [], revision: 5 };
const sample = (patch: Partial<SampleDTO> = {}): SampleDTO => ({ id: hex("s"), run_id: run.id, day: 16, collected_on: "2026-10-12", assay: "scRNA-seq",
  material_id: hex("m"), session_id: null, assessment_id: null, revision: 1, ...patch });
const base = { protocols: [protocol], runs: [] as RunDTO[], samples: [] as SampleDTO[], assessments: [], leads: [], actions: [] };

function routes(handlers: Record<string, (body: Record<string, unknown>) => Response>) {
  const calls: { key: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${String(input).replace(`/api/researches/${research.id}`, "")}`;
    const body = typeof init?.body === "string" ? JSON.parse(init.body) : {};
    calls.push({ key, body });
    return handlers[key]?.(body) ?? json({ detail: "Not Found" }, 404);
  }));
  return calls;
}
const mount = () => render(<ResearchWorkbench principal={principal} research={research} onSessions={() => undefined} onHome={() => undefined} />);

describe("sample mapping status", () => {
  it("shows registered samples with their mapping state, including requests that are no longer pending", () => {
    const dto: WorkbenchDTO = { ...base, runs: [run], samples: [sample({ assessment_request: { action_id: hex("x"), status: "approved" } }), sample({ id: hex("t"), day: 11 })] };
    const card = adaptWorkbench(dto).protocols.find(p => p.run)!;
    expect(card.sampleRecords!.map(s => [s.day, s.mapping, s.status])).toEqual([[11, "none", "data_attached"], [16, "approved", "mapping"]]);
    expect(card.run).toMatchObject({ id: run.id, revision: 5, cellLine: "H9" });
  });
});

describe("runs and samples", () => {
  it("records an experiment of a confirmed version and opens it", async () => {
    let state: WorkbenchDTO = { ...base };
    const calls = routes({
      "GET /workbench": () => json(state),
      "POST /runs": body => { state = { ...base, runs: [{ ...run, name: String(body.name), revision: 1 }] }; return json(state.runs[0]); },
    });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A/ }));
    fireEvent.click(screen.getByRole("button", { name: "记录实验" }));
    const form = screen.getByRole("form", { name: "记录实验" });
    expect(within(form).queryByLabelText("名称")).not.toBeInTheDocument();
    fireEvent.change(within(form).getByLabelText("细胞系"), { target: { value: "H9" } });
    fireEvent.change(within(form).getByLabelText("D0 日期"), { target: { value: "2026-09-26" } });
    fireEvent.click(within(form).getByRole("button", { name: "记录" }));
    await waitFor(() => expect(screen.getByRole("region", { name: "取样与状态" })).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "再做一批" })).toBeInTheDocument();
    expect(calls.find(c => c.key === "POST /runs")!.body).toMatchObject({ protocol_version_id: version.id, name: "H9 2026-09-26", cell_line: "H9", start_date: "2026-09-26", state: "differentiating", expected_version: 0 });
  });

  it("registers a sample with existing data, declares where the raw counts are, and mapping starts", async () => {
    let state: WorkbenchDTO = { ...base, runs: [run] };
    const calls = routes({
      "GET /workbench": () => json(state),
      [`POST /runs/${run.id}/samples`]: () => { const s = sample({ status: "mapping" }); state = { ...state, samples: [s] }; return json(s); },
    });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    fireEvent.click(screen.getByRole("button", { name: "＋ 样本" }));
    const form = screen.getByRole("form", { name: "登记样本" });
    expect(within(form).getByLabelText("取样天")).toHaveValue(16);
    expect(within(form).getAllByRole("option").map(o => o.textContent)).toEqual(["测序后再关联", "D16.h5ad"]);
    fireEvent.change(within(form).getByLabelText("数据"), { target: { value: hex("m") } });
    const counts = within(form).getByRole("radiogroup", { name: "原始计数在哪里" });
    expect(within(counts).getAllByRole("radio").map(r => r.parentElement!.textContent)).toEqual(["主矩阵 X", "counts 层", "不确定，先不映射"]);
    expect(within(counts).queryByRole("radio", { checked: true })).toBeNull();
    fireEvent.click(within(form).getByRole("button", { name: "登记" }));
    expect(within(form).getByRole("alert")).toHaveTextContent("先把数据说明填完整");
    expect(calls.some(c => c.key.endsWith("/samples"))).toBe(false);
    fireEvent.click(within(counts).getByRole("radio", { name: "counts 层" }));
    expect(within(form).getByRole("button", { name: "移植前" })).toHaveAttribute("aria-pressed", "true");
    expect(within(form).getByLabelText("细胞来源")).toHaveValue("H9");
    fireEvent.click(within(form).getByRole("button", { name: "登记" }));
    expect(await screen.findByText("已登记 D16。图谱映射已开始。")).toBeInTheDocument();
    expect(calls.find(c => c.key.endsWith("/samples"))!.body).toEqual({ day: 16, assay: "scRNA-seq", collected_on: expect.any(String), material_id: hex("m"), expected_version: 5,
      mapping_input: { matrix_location: "layers/counts", matrix_semantics: "raw_counts", sample_context: "pre_graft", source_family_id: "H9" } });
    expect(calls.some(c => c.key.endsWith("/assessments"))).toBe(false);
    expect(await screen.findByRole("button", { name: "D16 scRNA-seq，映射中" })).toBeInTheDocument();
  });

  it("registers a sample on the day it is collected, before sequencing data exists", async () => {
    let state: WorkbenchDTO = { ...base, runs: [run] };
    const calls = routes({
      "GET /workbench": () => json(state),
      [`POST /runs/${run.id}/samples`]: () => { state = { ...state, samples: [sample({ material_id: null })] }; return json(sample({ material_id: null })); },
    });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    fireEvent.click(screen.getByRole("button", { name: "＋ 样本" }));
    const form = screen.getByRole("form", { name: "登记样本" });
    expect(within(form).queryByRole("radiogroup", { name: "原始计数在哪里" })).not.toBeInTheDocument();
    fireEvent.click(within(form).getByRole("button", { name: "登记" }));
    expect(await screen.findByText("已登记 D16，测序数据回来后在这里关联。")).toBeInTheDocument();
    expect(calls.find(c => c.key.endsWith("/samples"))!.body).toMatchObject({ day: 16, material_id: null });
    expect(calls.find(c => c.key.endsWith("/samples"))!.body).not.toHaveProperty("mapping_input");
    expect(await screen.findByRole("button", { name: "D16 scRNA-seq，待测序" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /映射 D16/ })).not.toBeInTheDocument();
  });

  it("attaches sequencing data with its declaration when it arrives", async () => {
    let state: WorkbenchDTO = { ...base, runs: [run], samples: [sample({ material_id: null })] };
    const calls = routes({
      "GET /workbench": () => json(state),
      [`PATCH /samples/${hex("s")}`]: body => { state = { ...state, samples: [sample({ material_id: String(body.material_id), revision: 2, status: "mapping", assessment_availability: null })] }; return json(state.samples[0]); },
    });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    fireEvent.click(screen.getByRole("button", { name: "D16 scRNA-seq，待测序" }));
    fireEvent.click(screen.getByRole("button", { name: "关联数据 D16" }));
    const form = screen.getByRole("form", { name: "关联 D16 的数据" });
    fireEvent.click(within(form).getByRole("button", { name: "关联" }));
    expect(within(form).getByRole("alert")).toHaveTextContent("先选择或上传数据");
    fireEvent.change(within(form).getByLabelText("数据"), { target: { value: hex("m") } });
    fireEvent.click(within(form).getByRole("radio", { name: "主矩阵 X" }));
    fireEvent.click(within(form).getByRole("button", { name: "关联" }));
    expect(await screen.findByText("D16 已关联数据。图谱映射已开始。")).toBeInTheDocument();
    expect(calls.find(c => c.key.startsWith("PATCH"))!.body).toEqual({ material_id: hex("m"), expected_version: 1,
      mapping_input: { matrix_location: "X", matrix_semantics: "raw_counts", sample_context: "pre_graft", source_family_id: "H9" } });
    expect(await screen.findByRole("button", { name: "D16 scRNA-seq，映射中" })).toBeInTheDocument();
  });

  it("sends the capture the researcher declares, and nothing when they do not know it", async () => {
    let state: WorkbenchDTO = { ...base, runs: [run], samples: [sample({ material_id: null })] };
    const calls = routes({
      "GET /workbench": () => json(state),
      [`PATCH /samples/${hex("s")}`]: body => { state = { ...state, samples: [sample({ material_id: String(body.material_id), revision: 2, status: "mapping" })] }; return json(state.samples[0]); },
    });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    fireEvent.click(screen.getByRole("button", { name: "D16 scRNA-seq，待测序" }));
    fireEvent.click(screen.getByRole("button", { name: "关联数据 D16" }));
    const form = screen.getByRole("form", { name: "关联 D16 的数据" });
    fireEvent.change(within(form).getByLabelText("数据"), { target: { value: hex("m") } });
    fireEvent.click(within(form).getByRole("radio", { name: "主矩阵 X" }));
    const capture = within(form).getByRole("radiogroup", { name: "捕获批次" });
    expect(within(capture).getByRole("radio", { name: "不清楚" })).toBeChecked();
    expect(within(capture).getByText("不检测双细胞")).toBeInTheDocument();
    fireEvent.click(within(capture).getByRole("radio", { name: "文件里有几次捕获，记在一列里" }));
    fireEvent.click(within(form).getByRole("button", { name: "关联" }));
    expect(within(form).getByRole("alert")).toHaveTextContent("先把数据说明填完整");
    fireEvent.change(within(capture).getByLabelText("捕获批次所在的列"), { target: { value: " library " } });
    fireEvent.click(within(form).getByRole("button", { name: "关联" }));
    expect(await screen.findByText("D16 已关联数据。图谱映射已开始。")).toBeInTheDocument();
    expect(calls.find(c => c.key.startsWith("PATCH"))!.body).toEqual({ material_id: hex("m"), expected_version: 1,
      mapping_input: { matrix_location: "X", matrix_semantics: "raw_counts", sample_context: "pre_graft", source_family_id: "H9", capture_id_column: "library" } });
  });

  it("says mapping is not available yet instead of implying it has started", async () => {
    const attached = (patch: Partial<SampleDTO> = {}) => sample({ revision: 2, status: "data_attached",
      assessment_availability: { status: "unavailable", code: "standard_mapping_not_configured" }, ...patch });
    let state: WorkbenchDTO = { ...base, runs: [run], samples: [sample({ material_id: null })] };
    routes({
      "GET /workbench": () => json(state),
      [`PATCH /samples/${hex("s")}`]: () => { state = { ...state, samples: [attached()] }; return json(attached()); },
    });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    fireEvent.click(screen.getByRole("button", { name: "D16 scRNA-seq，待测序" }));
    fireEvent.click(screen.getByRole("button", { name: "关联数据 D16" }));
    const form = screen.getByRole("form", { name: "关联 D16 的数据" });
    fireEvent.change(within(form).getByLabelText("数据"), { target: { value: hex("m") } });
    fireEvent.click(within(form).getByRole("radio", { name: "主矩阵 X" }));
    fireEvent.click(within(form).getByRole("button", { name: "关联" }));
    expect(await screen.findByText("D16 已关联数据。标准图谱映射暂不可用，暂时不能映射。")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "D16 scRNA-seq，数据已关联，标准图谱映射暂不可用" })).toBeInTheDocument();
    expect(screen.getByText("映射暂不可用")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /映射 D16/ })).not.toBeInTheDocument();
  });

  it("says plainly when the server cannot attach data yet", async () => {
    routes({ "GET /workbench": () => json({ ...base, runs: [run], samples: [sample({ material_id: null })] }) });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    fireEvent.click(screen.getByRole("button", { name: "D16 scRNA-seq，待测序" }));
    fireEvent.click(screen.getByRole("button", { name: "关联数据 D16" }));
    const form = screen.getByRole("form", { name: "关联 D16 的数据" });
    fireEvent.change(within(form).getByLabelText("数据"), { target: { value: hex("m") } });
    fireEvent.click(within(form).getByRole("radio", { name: "主矩阵 X" }));
    fireEvent.click(within(form).getByRole("button", { name: "关联" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent("服务器还不支持之后关联数据");
  });

  it("attaches data without a declaration when unsure, then starts mapping once the counts are declared", async () => {
    const waiting = sample({ revision: 2, status: "data_attached", mapping_input: null, assessment_availability: { status: "unavailable", code: "mapping_input_required" } });
    let state: WorkbenchDTO = { ...base, runs: [run], samples: [sample({ material_id: null })] };
    const calls = routes({
      "GET /workbench": () => json(state),
      [`PATCH /samples/${hex("s")}`]: () => { state = { ...state, samples: [waiting] }; return json(waiting); },
      [`POST /samples/${hex("s")}/mapping`]: () => { const s = { ...waiting, revision: 3, status: "mapping" as const, assessment_availability: null }; state = { ...state, samples: [s] }; return json(s); },
    });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    fireEvent.click(screen.getByRole("button", { name: "D16 scRNA-seq，待测序" }));
    fireEvent.click(screen.getByRole("button", { name: "关联数据 D16" }));
    let form = screen.getByRole("form", { name: "关联 D16 的数据" });
    fireEvent.change(within(form).getByLabelText("数据"), { target: { value: hex("m") } });
    fireEvent.click(within(form).getByRole("radio", { name: "不确定，先不映射" }));
    expect(within(form).queryByLabelText("细胞来源")).not.toBeInTheDocument();
    fireEvent.click(within(form).getByRole("button", { name: "关联" }));
    expect(await screen.findByText("D16 已关联数据。补充数据说明后开始映射。")).toBeInTheDocument();
    expect(calls.find(c => c.key.startsWith("PATCH"))!.body).toEqual({ material_id: hex("m"), expected_version: 1 });
    expect(await screen.findByRole("button", { name: "D16 scRNA-seq，数据已关联，还差数据说明" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "补充数据说明 D16" }));
    form = screen.getByRole("form", { name: "补充 D16 的数据说明" });
    fireEvent.click(within(form).getByRole("radio", { name: "counts 层" }));
    fireEvent.change(within(form).getByLabelText("细胞来源"), { target: { value: "H9 WA09" } });
    expect(within(form).getByLabelText("细胞来源")).toHaveAttribute("aria-invalid", "true");
    fireEvent.click(within(form).getByRole("button", { name: "开始映射" }));
    expect(within(form).getByRole("alert")).toHaveTextContent("先把数据说明填完整");
    fireEvent.change(within(form).getByLabelText("细胞来源"), { target: { value: "H9-WA09" } });
    fireEvent.click(within(form).getByRole("button", { name: "开始映射" }));
    expect(await screen.findByText("D16：图谱映射已开始。")).toBeInTheDocument();
    expect(calls.find(c => c.key.endsWith("/mapping"))!.body).toEqual({ expected_version: 2,
      mapping_input: { matrix_location: "layers/counts", matrix_semantics: "raw_counts", sample_context: "pre_graft", source_family_id: "H9-WA09" } });
  });

  it("retries a failed attempt, and explains a retry the server could not start", async () => {
    const failed = sample({ revision: 3, status: "failed", assessment_id: hex("f"), mapping_input: { matrix_location: "X", matrix_semantics: "raw_counts", sample_context: "pre_graft", source_family_id: "H9" } });
    const assessment = { id: hex("f"), sample_id: hex("s"), status: "failed", versions: { atlas: "", naming: "", metrics: "" }, chain: [], target_fraction: null,
      gestation: [], tree_position: {}, alerts: [], failure: { code: "mapping_interrupted", message: "" } };
    let state = { ...base, runs: [run], samples: [failed], assessments: [assessment] } as unknown as WorkbenchDTO;
    const calls = routes({
      "GET /workbench": () => json(state),
      [`POST /samples/${hex("s")}/mapping`]: () => { const s = { ...failed, revision: 4, assessment_availability: { status: "unavailable" as const, code: "mapping_worker_busy" } };
        state = { ...state, samples: [s] }; return json(s); },
    });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    fireEvent.click(screen.getByRole("button", { name: "D16 scRNA-seq，未完成" }));
    fireEvent.click(screen.getByRole("button", { name: "重试映射 D16" }));
    expect(await screen.findByText("D16：映射任务已满，请稍后在 D16 旁点重试。")).toBeInTheDocument();
    expect(calls.find(c => c.key.endsWith("/mapping"))!.body).toEqual({ expected_version: 3 });
    expect(await screen.findByRole("button", { name: "D16 scRNA-seq，未完成，映射任务已满，稍后重试" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重试映射 D16" })).toBeInTheDocument();
  });

  it("offers no retry while the reference for this kind of sample is missing", async () => {
    routes({ "GET /workbench": () => json({ ...base, runs: [run], samples: [sample({ status: "data_attached", assay: "snRNA-seq",
      mapping_input: { matrix_location: "X", matrix_semantics: "raw_counts", sample_context: "post_graft", source_family_id: "H9" },
      assessment_availability: { status: "unavailable", code: "mapping_reference_unavailable" } })] }) });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    fireEvent.click(screen.getByRole("button", { name: "D16 snRNA-seq，数据已关联，没有对应的参考数据" }));
    expect(screen.getByText("映射暂不可用")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /映射 D16/ })).not.toBeInTheDocument();
  });

  it("suggests post-graft for samples collected after the graft date", async () => {
    const grafted = { ...run, state: "grafted" as const, graft: { date: "2026-10-01", host: "大鼠", site: "纹状体" } };
    routes({ "GET /workbench": () => json({ ...base, runs: [grafted], samples: [sample({ material_id: null, collected_on: "2026-11-20" })] }) });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    fireEvent.click(screen.getByRole("button", { name: "D16 scRNA-seq，待测序" }));
    fireEvent.click(screen.getByRole("button", { name: "关联数据 D16" }));
    const form = screen.getByRole("form", { name: "关联 D16 的数据" });
    fireEvent.change(within(form).getByLabelText("数据"), { target: { value: hex("m") } });
    fireEvent.click(within(form).getByRole("radio", { name: "主矩阵 X" }));
    expect(within(form).getByRole("button", { name: "移植后" })).toHaveAttribute("aria-pressed", "true");
    expect(within(form).getByText(/移植后的样本要用单核（snRNA）参考/)).toBeInTheDocument();
  });

  it("keeps the notice of a write until the sample moves on", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    try {
      let state: WorkbenchDTO = { ...base, runs: [run], samples: [sample({ material_id: null })] };
      routes({
        "GET /workbench": () => json(state),
        [`PATCH /samples/${hex("s")}`]: () => { state = { ...state, samples: [sample({ revision: 2, status: "mapping" })] }; return json(state.samples[0]); },
      });
      mount();
      fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
      fireEvent.click(screen.getByRole("button", { name: "D16 scRNA-seq，待测序" }));
    fireEvent.click(screen.getByRole("button", { name: "关联数据 D16" }));
      const form = screen.getByRole("form", { name: "关联 D16 的数据" });
      fireEvent.change(within(form).getByLabelText("数据"), { target: { value: hex("m") } });
      fireEvent.click(within(form).getByRole("radio", { name: "主矩阵 X" }));
      fireEvent.click(within(form).getByRole("button", { name: "关联" }));
      expect(await screen.findByText("D16 已关联数据。图谱映射已开始。")).toBeInTheDocument();
      vi.advanceTimersByTime(4000);
      await screen.findByRole("button", { name: "D16 scRNA-seq，映射中" });
      expect(screen.getByText("D16 已关联数据。图谱映射已开始。")).toBeInTheDocument();
      state = { ...state, samples: [sample({ revision: 3, status: "done", assessment_id: null })] };
      vi.advanceTimersByTime(4000);
      await waitFor(() => expect(screen.queryByText("D16 已关联数据。图谱映射已开始。")).not.toBeInTheDocument());
    } finally { vi.useRealTimers(); }
  });

  it("refreshes while a sample is mapping and stops once it is done", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    try {
      let reads = 0;
      routes({ "GET /workbench": () => { reads += 1; return json({ ...base, runs: [run], samples: [sample({ status: reads < 2 ? "mapping" : "data_attached" })] }); } });
      mount();
      fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
      expect(screen.getByRole("button", { name: "D16 scRNA-seq，映射中" })).toBeInTheDocument();
      expect(reads).toBe(1);
      vi.advanceTimersByTime(4000);
      expect(await screen.findByRole("button", { name: "D16 scRNA-seq，未映射" })).toBeInTheDocument();
      expect(reads).toBe(2);
      vi.advanceTimersByTime(8000);
      expect(reads).toBe(2);
    } finally { vi.useRealTimers(); }
  });

  it("records freezing and grafting with the run revision", async () => {
    const calls = routes({
      "GET /workbench": () => json({ ...base, runs: [run] }),
      [`PATCH /runs/${run.id}`]: body => json({ ...run, ...body, revision: 6 }),
    });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A，/ }));
    fireEvent.click(screen.getByRole("button", { name: "冻存" }));
    await waitFor(() => expect(calls.some(c => c.key.startsWith("PATCH"))).toBe(true));
    expect(calls.find(c => c.key.startsWith("PATCH"))!.body).toEqual({ state: "frozen", expected_version: 5 });
    fireEvent.click(screen.getByRole("button", { name: "移植" }));
    const form = screen.getByRole("form", { name: "记录移植" });
    fireEvent.click(within(form).getByRole("button", { name: "记录移植" }));
    await waitFor(() => expect(calls.filter(c => c.key.startsWith("PATCH"))).toHaveLength(2));
    expect(calls.filter(c => c.key.startsWith("PATCH"))[1].body).toMatchObject({ state: "grafted", graft: { host: "大鼠", site: "纹状体" }, expected_version: 5 });
  });
});

describe("workbench address", () => {
  it("opens at the given place and reports every move", async () => {
    routes({ "GET /workbench": () => json(base) });
    const onLocate = vi.fn();
    const props = { principal, research, onSessions: () => undefined, onHome: () => undefined, onLocate };
    const view = render(<ResearchWorkbench {...props} location={{ view: "plan", focus: libraryId(hex("p")) }} />);
    expect(await screen.findByRole("button", { name: "记录实验" })).toBeInTheDocument();
    fireEvent.click(within(screen.getByRole("navigation", { name: "位置" })).getByRole("button", { name: "培养箱" }));
    expect(onLocate).toHaveBeenLastCalledWith({ view: "wall", focus: libraryId(hex("p")) });
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A/ }));
    expect(onLocate).toHaveBeenLastCalledWith({ view: "plan", focus: libraryId(hex("p")) });
    view.rerender(<ResearchWorkbench {...props} location={{ view: "wall", focus: null }} />);
    expect(await screen.findByRole("heading", { name: "培养箱" })).toBeInTheDocument();
  });
});
