import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../src/App";

const facts = {
  product_name: null, product_family: "unknown", target_cell_type: null, target_stage: null,
  sampling_context: "unknown", independent_cultures: null, assay: "unknown",
  matrix_location: null, count_semantics: "unknown", source_family_id: null,
  sample_id_column: null, capture_id_column: null, gene_symbol_column: null,
};
const baseSession = {
  id: "session-intake", title: "New analysis", updated_at: "2026-09-08T00:00:00Z", status: "idle",
  messages: [], uploads: [{ id: "a".repeat(32), name: "synthetic.h5ad", kind: "h5ad", size: 100 }],
  plan: null, artifacts: [], error: null, input_review_required: false, pending_input_change: null,
};
const response = (body: unknown) => new Response(JSON.stringify(body), {
  status: 200, headers: { "Content-Type": "application/json" },
});

beforeEach(() => localStorage.clear());

it.each(["draft", "confirmed"])("keeps per-attachment protocol review accessible in %s intake without automatic generation", async state => {
  const writes: Array<{ path: string; body: Record<string, unknown> }> = [];
  const protocols = [
    { protocol_id: "1".repeat(32), name: "first-method.txt", revision: 3, state: "not_started", error: null, latest: null, versions: [] },
    { protocol_id: "2".repeat(32), name: "second-method.txt", revision: 7, state: "not_started", error: null, latest: null, versions: [] },
  ];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = String(input);
    if (init?.method === "POST") {
      writes.push({ path, body: JSON.parse(String(init.body)) });
      return response(baseSession);
    }
    if (path === "/api/sessions") return response({ sessions: [baseSession] });
    if (path === "/api/sessions/session-intake") return response(baseSession);
    if (path.includes("/intake?")) return response({
      upload_id: baseSession.uploads[0].id, facts, state, next_tool: null, missing_fields: [],
      blockers: [], qc_state: "not_run", measurement_spec_ref: null,
      observed: { n_observations: 4, n_genes: 3, matrix_locations: ["X"], obs_columns: [], var_columns: [] }, roadmap: [],
      autofill: { state: "complete", revision: 4, sources: [], fields: {}, field_sources: {}, questions: [], conflicts: [],
        other_answers: {}, samples: [], protocols: protocols.map(p => ({ id: p.protocol_id, name: p.name })),
        protocol_stages: [], sources_truncated: false, batch_binding: null, formalizations: protocols },
    });
    throw new Error("Unexpected request: " + path);
  });
  const user = userEvent.setup();
  render(<App />);
  expect(await screen.findByRole("region", { name: "方案核对：second-method.txt" })).toBeInTheDocument();
  expect(writes).toEqual([]);
  if (state === "confirmed") expect(screen.getByRole("button", { name: "修改资料" })).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("核对的方案附件"), "1".repeat(32));
  expect(screen.getByRole("region", { name: "方案核对：first-method.txt" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "生成方案表示" }));
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0]).toEqual({
    path: "/api/sessions/session-intake/intake/protocols/formalize",
    body: { upload_id: "a".repeat(32), protocol_id: "1".repeat(32), revision: 3 },
  });
  expect(screen.queryByRole("button", { name: "确认资料" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Confirm analysis" })).not.toBeInTheDocument();
});


function setupRequests() {
  const writes: Array<{ path: string; body: Record<string, unknown> }> = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = String(input);
    if (init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      writes.push({ path, body });
      if (path.endsWith("/intake")) return response({
        ...baseSession, input_review_required: true, pending_input_change: {
          id: "b".repeat(32), digest: "c".repeat(64), kind: "intake", upload_id: baseSession.uploads[0].id,
          changes: [{ field: "product_name", before: null, after: "My product" }],
        },
      });
      throw new Error("Unexpected write: " + path);
    }
    if (path === "/api/sessions") return response({ sessions: [baseSession] });
    if (path === "/api/sessions/session-intake") return response(baseSession);
    if (path.includes("/intake?")) return response({
      upload_id: baseSession.uploads[0].id, facts, state: "draft", next_tool: null,
      missing_fields: ["assay", "count_semantics"], blockers: [], qc_state: "not_run",
      measurement_spec_ref: null,
      observed: { n_observations: 4, n_genes: 3, matrix_locations: ["X"], obs_columns: [], var_columns: [] },
      roadmap: [{ question: "数据是否可分析？", state: "not_run" }],
    });
    throw new Error("Unexpected request: " + path);
  });
  return writes;
}


it("keeps an intake proposal visible even when it targets an older upload", async () => {
  const older = { ...baseSession.uploads[0], id: "d".repeat(32), name: "older.h5ad" };
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const path = String(input);
    const staged = {
      ...baseSession, uploads: [older, ...baseSession.uploads], input_review_required: true,
      pending_input_change: { id: "b".repeat(32), digest: "c".repeat(64), kind: "intake",
        upload_id: older.id, changes: [{ field: "assay", before: "unknown", after: "scRNA-seq" }] },
    };
    if (path === "/api/sessions") return response({ sessions: [staged] });
    if (path === "/api/sessions/session-intake") return response(staged);
    if (path.includes("/intake?")) {
      const aid = new URL(path, "http://testserver").searchParams.get("upload_id");
      return response({
        upload_id: aid, facts, state: "draft", next_tool: null,
        missing_fields: [], blockers: [], qc_state: "not_run", measurement_spec_ref: null,
        observed: { n_observations: 4, n_genes: 3, matrix_locations: ["X"], obs_columns: [], var_columns: [] },
        roadmap: [],
      });
    }
    throw new Error("Unexpected request: " + path);
  });
  render(<App />);
  expect(await screen.findByRole("button", { name: "确认资料" })).toBeInTheDocument();
  expect(screen.getByLabelText("本次评估文件")).toHaveValue(older.id);
});


it("requires separate fact confirmation before preparing an unapproved plan", async () => {
  const writes: string[] = [];
  let stageState = "draft";
  let savedFacts = { ...facts };
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = String(input);
    if (init?.method === "POST") {
      writes.push(path);
      if (path.endsWith("/intake")) {
        savedFacts = JSON.parse(String(init.body)).facts;
        stageState = "pending";
      } else if (path.endsWith("/input-change/confirm")) {
        stageState = "confirmed";
      } else if (path.endsWith("/intake/prepare")) {
        return response({ ...baseSession, status: "awaiting_approval",
          plan: { id: "intake-plan", digest: "e".repeat(64), status: "proposed", summary: "Input QC only",
            steps: [{ id: "step-qc", tool_id: "P0-01", label: "Input QC", status: "pending", reason: null }] } });
      } else throw new Error("Unexpected write: " + path);
      return response({ ...baseSession, input_review_required: stageState === "pending",
        pending_input_change: stageState === "pending" ? {
          id: "b".repeat(32), digest: "c".repeat(64), kind: "intake", upload_id: baseSession.uploads[0].id,
          changes: [{ field: "assay", before: "unknown", after: "scRNA-seq" }],
        } : null });
    }
    if (path === "/api/sessions") return response({ sessions: [baseSession] });
    if (path === "/api/sessions/session-intake") return response(baseSession);
    if (path.includes("/intake?")) return response({
      upload_id: baseSession.uploads[0].id, facts: savedFacts,
      state: stageState === "confirmed" ? "confirmed" : "draft", next_tool: stageState === "confirmed" ? "P0-01" : null,
      missing_fields: [], blockers: [], qc_state: "not_run", measurement_spec_ref: null,
      observed: { n_observations: 4, n_genes: 3, matrix_locations: ["X"], obs_columns: [], var_columns: [] },
      roadmap: [],
    });
    throw new Error("Unexpected request: " + path);
  });
  const user = userEvent.setup();
  render(<App />);
  await user.selectOptions(await screen.findByLabelText("实验类型"), "scRNA-seq");
  await user.selectOptions(screen.getByLabelText("计数位置"), "X");
  await user.selectOptions(screen.getByLabelText("矩阵内容"), "raw_counts");
  await user.click(screen.getByRole("button", { name: "核对产品资料" }));
  await user.click(await screen.findByRole("button", { name: "确认资料" }));
  const prepare = await screen.findByRole("button", { name: "生成下一阶段计划" });
  expect(writes).toHaveLength(2);
  expect(writes[1]).toMatch(/input-change\/confirm$/);
  await user.click(prepare);
  expect(await screen.findByRole("button", { name: "Confirm analysis" })).toBeInTheDocument();
  expect(writes).toHaveLength(3);
  expect(writes[2]).toMatch(/intake\/prepare$/);
});


it("pauses plan preparation while confirmed product facts are being edited", async () => {
  const writes: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = String(input);
    if (init?.method === "POST") writes.push(path);
    if (path === "/api/sessions") return response({ sessions: [baseSession] });
    if (path === "/api/sessions/session-intake") return response(baseSession);
    if (path.includes("/intake?")) return response({
      upload_id: baseSession.uploads[0].id, facts: { ...facts, assay: "scRNA-seq", matrix_location: "X", count_semantics: "raw_counts" },
      state: "confirmed", next_tool: "P0-01", missing_fields: [], blockers: [], qc_state: "not_run",
      measurement_spec_ref: null,
      observed: { n_observations: 4, n_genes: 3, matrix_locations: ["X"], obs_columns: [], var_columns: [] },
      roadmap: [],
    });
    throw new Error("Unexpected request: " + path);
  });
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole("button", { name: "修改资料" }));
  expect(screen.getByRole("button", { name: "生成下一阶段计划" })).toBeDisabled();
  await user.selectOptions(screen.getByLabelText("矩阵内容"), "unknown");
  await user.click(screen.getByRole("button", { name: "取消编辑" }));
  expect(screen.getByRole("button", { name: "生成下一阶段计划" })).toBeEnabled();
  expect(screen.getByText("未经标准化的原始计数")).toBeInTheDocument();
  expect(writes).toEqual([]);
});

it("shows file structure separately from unknown researcher declarations", async () => {
  const writes = setupRequests();
  render(<App />);
  const panel = await screen.findByRole("region", { name: "产品资料" });
  expect(await within(panel).findByText(/4 个观测/)).toHaveTextContent("3 个基因");
  expect(within(panel).getByLabelText("实验类型")).toHaveValue("unknown");
  expect(within(panel).getByLabelText("矩阵内容")).toHaveValue("unknown");
  expect(within(panel).getByLabelText("产品类别")).toHaveValue("unknown");
  expect(within(panel).getByLabelText("独立培养次数（可留空）")).toHaveValue(null);
  expect(screen.queryByRole("button", { name: "生成下一阶段计划" })).not.toBeInTheDocument();
  expect(writes).toEqual([]);
});

it("stages a readable draft without confirming facts or approving a run", async () => {
  const writes = setupRequests();
  const user = userEvent.setup();
  render(<App />);
  await screen.findByRole("region", { name: "产品资料" });
  await user.type(await screen.findByLabelText("产品 / 批次名称"), "My product");
  await user.selectOptions(screen.getByLabelText("实验类型"), "scRNA-seq");
  await user.selectOptions(screen.getByLabelText("计数位置"), "X");
  await user.selectOptions(screen.getByLabelText("矩阵内容"), "raw_counts");
  await user.click(screen.getByRole("button", { name: "核对产品资料" }));
  expect(await screen.findByRole("button", { name: "确认资料" })).toBeInTheDocument();
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0].path).toBe("/api/sessions/session-intake/intake");
  expect(writes[0].body).toMatchObject({
    upload_id: baseSession.uploads[0].id,
    facts: { product_name: "My product", assay: "scRNA-seq", matrix_location: "X", count_semantics: "raw_counts" },
  });
  expect(screen.getByText("产品 / 批次名称", { selector: "dt" })).toBeInTheDocument();
});
