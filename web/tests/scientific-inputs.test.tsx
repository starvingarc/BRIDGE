import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../src/App";

const aid = "a".repeat(32);
const facts = {
  product_name: "研究样本", product_family: "hpsc_mda", target_cell_type: "中脑多巴胺能祖细胞",
  target_stage: "预期祖细胞阶段", sampling_context: "process_sample", independent_cultures: null,
  assay: "scRNA-seq", matrix_location: "X", count_semantics: "raw_counts",
  source_family_id: "public-study", sample_id_column: null, capture_id_column: null, gene_symbol_column: null,
};
const initial = () => ({
  id: "science-session", title: "Scientific review", updated_at: "2026-09-08T00:00:00Z",
  status: "idle", uploads: [{ id: aid, name: "synthetic.h5ad", kind: "h5ad", size: 100 }],
  messages: [{ id: "draft-message", role: "assistant", content: "科学输入候选已整理", created_at: "2026-09-08T00:00:00Z" }],
  plan: null, plan_history: [], artifacts: [], error: null, input_review_required: false,
  pending_input_change: null, capabilities: [], clarifications: [],
  scientific_drafts: [{
    id: "b".repeat(32), digest: "c".repeat(64), upload_id: aid, message_id: "draft-message",
    status: "pending", facts, attestation_state: "not_confirmed", object_ids: {},
    candidate: { label_level: "L1", roles: [{
      state_id: "L1:Neuron_DA", product_role: "target", source_ids: ["state-review:L1:Neuron_DA"],
      rationale: "候选角色，尚不代表已确认身份。",
    }], development: [], regional_denominator_state_ids: [], regional_target_state_ids: [] },
    sources: [{ source_id: "state-review:L1:Neuron_DA", version: "0.1.0", state_id: "L1:Neuron_DA",
      label_level: "L1", definition: "Dopaminergic neuronal transcriptional state",
      anatomy_scope: "human fetal ventral midbrain", developmental_scope: "context only",
      derivation: "Team-curated candidate", review_status: "pending",
      limitations: ["Positive and negative markers require review."], source_refs: ["BRIDGE-TEAM-ANNOTATION"] }],
    unknowns: ["independence_unknown", "scientific_source_review_pending"],
    stages: [{ tool_id: "P0-03", state: "blocked", reason_codes: ["scientific_source_review_pending"] }],
  }],
});
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});
function setup(value = initial(), confirmFails = false) {
  let state = structuredClone(value);
  const writes: Array<{ path: string; body: Record<string, unknown> }> = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = String(input);
    if (init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      writes.push({ path, body });
      if (path.endsWith("/scientific-inputs/confirm")) {
        if (confirmFails) return response({ detail: "scientific_draft_invalid_or_stale" }, 409);
        state.scientific_drafts[0].status = "confirmed";
      } else if (path.endsWith("/scientific-inputs/revise")) {
        state.scientific_drafts[0].status = "superseded";
        state.scientific_drafts.push({ ...state.scientific_drafts[0], status: "pending",
          id: "d".repeat(32), digest: "e".repeat(64), candidate: body.candidate });
      } else if (path.endsWith("/scientific-inputs/draft")) {
        state.status = "thinking";
      } else if (path.endsWith("/report-inputs/prepare")) {
        state.status = "awaiting_approval";
      } else throw new Error("Unexpected mutation: " + path);
      return response(state);
    }
    if (path === "/api/sessions") return response({ sessions: [state] });
    if (path === "/api/sessions/science-session") return response(state);
    if (path.includes("/intake?")) return response({ upload_id: aid, facts, state: "confirmed",
      next_tool: null, missing_fields: ["independent_cultures"], blockers: [], qc_state: "available",
      measurement_spec_ref: null, observed: { n_observations: 4, n_genes: 3, matrix_locations: ["X"],
        obs_columns: [], var_columns: [] }, roadmap: [] });
    throw new Error("Unexpected request: " + path);
  });
  return writes;
}
beforeEach(() => localStorage.clear());

it("shows sources, unknowns and exact candidate confirmation without executing", async () => {
  const writes = setup();
  const user = userEvent.setup();
  render(<App />);
  const card = await screen.findByRole("region", { name: "科学输入草稿" });
  expect(within(card).getByText("尚未确认生物学独立性")).toBeInTheDocument();
  await user.click(within(card).getByText("查看候选来源"));
  expect(within(card).getByText("Dopaminergic neuronal transcriptional state")).toBeInTheDocument();
  const confirm = within(card).getByRole("button", { name: "确认本版科学草稿" });
  expect(confirm).toBeDisabled();
  await user.click(within(card).getByRole("checkbox", { name: /已核对候选选择和未知项/ }));
  expect(writes).toHaveLength(0);
  await user.click(confirm);
  await waitFor(() => expect(within(card).getByText("草稿已确认")).toBeInTheDocument());
  expect(writes).toEqual([{ path: "/api/sessions/science-session/scientific-inputs/confirm",
    body: { draft_id: "b".repeat(32), draft_digest: "c".repeat(64) } }]);
  expect(screen.queryByRole("button", { name: "Confirm analysis" })).not.toBeInTheDocument();
});

it("stages a changed role as a new review version rather than confirming it", async () => {
  const writes = setup();
  const user = userEvent.setup();
  render(<App />);
  await user.selectOptions(await screen.findByLabelText("L1:Neuron_DA 的产品角色"), "role_unresolved");
  expect(writes).toHaveLength(0);
  expect(screen.getByRole("button", { name: "确认本版科学草稿" })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "保存选择为新草稿" }));
  await waitFor(() => expect(screen.getAllByRole("region", { name: "科学输入草稿" })).toHaveLength(2));
  const [previous, current] = screen.getAllByRole("region", { name: "科学输入草稿" });
  expect(within(previous).getByLabelText("L1:Neuron_DA 的产品角色")).toHaveValue("target");
  expect(within(previous).getByLabelText("L1:Neuron_DA 的产品角色")).toBeDisabled();
  expect(within(current).getByLabelText("L1:Neuron_DA 的产品角色")).toHaveValue("role_unresolved");
  expect(within(current).getByRole("button", { name: "确认本版科学草稿" })).toBeDisabled();
  expect(writes).toHaveLength(1);
  expect(writes[0].path).toMatch(/scientific-inputs\/revise$/);
  expect(writes[0].body.draft_digest).toBe("c".repeat(64));
  expect((writes[0].body.candidate as { roles: Array<{ product_role: string }> }).roles[0].product_role).toBe("role_unresolved");
});

it("provides the next scientific draft entry from confirmed ordinary product facts", async () => {
  const value = initial();
  value.scientific_drafts = [];
  const writes = setup(value);
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole("button", { name: "整理科学输入草稿" }));
  expect(writes).toEqual([{ path: "/api/sessions/science-session/scientific-inputs/draft", body: { upload_id: aid } }]);
});

it("restores confirmed review and preserves source-review blockers", async () => {
  const value = initial();
  value.scientific_drafts[0].status = "confirmed";
  const writes = setup(value);
  const first = render(<App />);
  expect(await screen.findByText("草稿已确认")).toBeInTheDocument();
  first.unmount();
  render(<App />);
  expect(await screen.findByText("草稿已确认")).toBeInTheDocument();
  expect(screen.getAllByText(/来源仍待生物学审阅/).length).toBeGreaterThan(0);
  expect(writes).toHaveLength(0);
});

it("renders stale drafts read-only and rejects a failed confirmation visibly", async () => {
  const value = initial();
  value.scientific_drafts[0].status = "stale";
  const writes = setup(value);
  render(<App />);
  expect(await screen.findByText("相关输入已变化，请重新整理草稿。")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "确认本版科学草稿" })).not.toBeInTheDocument();
  expect(writes).toHaveLength(0);
});

it("keeps failed confirmations pending without claiming success", async () => {
  setup(initial(), true);
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole("checkbox", { name: /已核对候选选择和未知项/ }));
  await user.click(screen.getByRole("button", { name: "确认本版科学草稿" }));
  expect(await screen.findByText("草稿或来源已变化，请刷新后重新核对。")).toBeInTheDocument();
  expect(screen.queryByText("草稿已确认")).not.toBeInTheDocument();
});

it("shows stage blockers and prepares missingness without approving the tool", async () => {
  const value = initial();
  value.scientific_drafts[0].status = "confirmed";
  value.scientific_drafts[0].stages.push(
    { tool_id: "P0-08", state: "ready", reason_codes: ["missingness_only"] },
    { tool_id: "P0-09", state: "blocked", reason_codes: ["report_policy_not_configured"] },
    { tool_id: "P0-10", state: "blocked", reason_codes: ["compiled_report_required"] },
    { tool_id: "P0-11", state: "blocked", reason_codes: ["verified_report_and_export_approval_required"] });
  const writes = setup(value);
  const user = userEvent.setup();
  render(<App />);
  expect(await screen.findByText("报告的证据归组与声明判定规则尚未配置")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "准备缺失证据检查" }));
  expect(writes).toEqual([{ path: "/api/sessions/science-session/report-inputs/prepare",
    body: { draft_id: "b".repeat(32), draft_digest: "c".repeat(64), tool_id: "P0-08" } }]);
});


it.each([["P0-09", "整理当前证据"], ["P0-10", "生成并核验内部报告"]])(
  "prepares %s separately and labels product comparison correctly", async (toolId, label) => {
    const value = initial();
    value.scientific_drafts[0].status = "confirmed";
    value.scientific_drafts[0].stages.push(
      { tool_id: "P0-07", state: "blocked", reason_codes: ["comparison_inputs_not_bound"] },
      { tool_id: toolId, state: "ready", reason_codes: ["internal_draft_only"] });
    const writes = setup(value);
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText(/产品比较 · 尚不可运行/)).toBeInTheDocument();
    expect(screen.queryByText(/移植证据/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: label }));
    expect(writes).toEqual([{ path: "/api/sessions/science-session/report-inputs/prepare",
      body: { draft_id: "b".repeat(32), draft_digest: "c".repeat(64), tool_id: toolId } }]);
  });

it("restores the internal report and shows the actual blocked verification without an export action", async () => {
  const value = initial();
  value.scientific_drafts[0].status = "confirmed";
  Object.assign(value.scientific_drafts[0], { internal_report: {
    audience: "internal_research", policy_state: "candidate_unreviewed", boundaries: ["本次核对不能证明安全性。"],
    sections: [{ domain_id: "developmental_compatibility", title: "发育阶段兼容性", text: "发育阶段尚未评估。", evidence_state: "not_assessed" },
      { domain_id: "target_identity", title: "目标身份",
      text: "目标身份：当前未提供正式测量，尚未评估。缺失不等于阴性。", evidence_state: "not_assessed" }],
    verification: { release_state: "release_blocked", public_export_eligibility: "ineligible",
      reason_codes: ["claim_type_policy_missing", "unapproved_renderer_requires_review"] },
    next_actions: ["完成候选来源与产品角色的生物学审阅，再准备正式域测量。"],
  } });
  const writes = setup(value);
  const first = render(<App />);
  let report = await screen.findByRole("region", { name: "内部研究报告" });
  expect(within(report).getByText("发布受阻")).toBeInTheDocument();
  expect(within(report).getByText("本次核对不能证明安全性。")).toBeInTheDocument();
  expect(within(report).getAllByRole("heading", { level: 5 })[0]).toHaveTextContent("目标身份 · 未评估");
  expect(within(report).getByText(/缺失不等于阴性/)).toBeInTheDocument();
  expect(within(report).getByText("当前声明规则尚未支持缺失性表述")).toBeInTheDocument();
  expect(within(report).queryByRole("button", { name: /导出/ })).not.toBeInTheDocument();
  first.unmount();
  render(<App />);
  report = await screen.findByRole("region", { name: "内部研究报告" });
  expect(within(report).getByText("发布受阻")).toBeInTheDocument();
  expect(writes).toHaveLength(0);
});

it("retains a completed missingness result without offering it as a product verdict", async () => {
  const value = initial();
  value.scientific_drafts[0].status = "confirmed";
  value.scientific_drafts[0].stages.push({ tool_id: "P0-08", state: "available", reason_codes: ["missingness_only"] });
  const writes = setup(value);
  render(<App />);
  expect(await screen.findByText("仅检查缺失证据，不是产品合格判定")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "准备缺失证据检查" })).not.toBeInTheDocument();
  expect(writes).toHaveLength(0);
});
