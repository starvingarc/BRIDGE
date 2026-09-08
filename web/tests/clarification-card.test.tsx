import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../src/App";

const aid = "a".repeat(32);
const initial = () => ({
  id: "question-session", title: "Choice assessment", updated_at: "2026-09-08T00:00:00Z",
  status: "idle", uploads: [{ id: aid, name: "synthetic.h5ad", kind: "h5ad", size: 100 }],
  messages: [{ id: "question-message", role: "assistant", content: "请核对这份资料", created_at: "2026-09-08T00:00:00Z" }],
  plan: null, plan_history: [], artifacts: [], error: null, input_review_required: false,
  pending_input_change: null as unknown, capabilities: [],
  clarifications: [{
    id: "b".repeat(32), digest: "c".repeat(64), upload_id: aid, message_id: "question-message",
    status: "pending", input_revision: 0, answers: [] as Array<{ field: string; selected: string[]; text: string; unknown: boolean }>,
    questions: [{ field: "assay", title: "使用哪种测序？", reason: "选择兼容的输入检查", multiple: false,
      options: [
        { id: "scRNA-seq", label: "单细胞测序", description: "整细胞" },
        { id: "snRNA-seq", label: "单核测序", description: "细胞核" },
      ] }],
  }],
});
type Fixture = ReturnType<typeof initial>;
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});
const facts = {
  product_name: null, product_family: "unknown", target_cell_type: null, target_stage: null,
  sampling_context: "unknown", independent_cultures: null, assay: "unknown",
  matrix_location: null, count_semantics: "unknown", source_family_id: null,
  sample_id_column: null, capture_id_column: null, gene_symbol_column: null,
};

function setup(value = initial()) {
  let state: Fixture = structuredClone(value);
  const writes: Array<{ path: string; body: Record<string, unknown> }> = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = String(input);
    if (init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      writes.push({ path, body });
      if (path.endsWith("/clarification/answer")) {
        state = { ...state, clarifications: [{ ...state.clarifications[0], status: "answered", answers: body.answers }] };
        if (body.answers[0].selected[0] === "scRNA-seq") {
          state = { ...state, input_review_required: true, pending_input_change: {
            id: "d".repeat(32), digest: "e".repeat(64), upload_id: aid, kind: "intake",
            changes: [{ field: "assay", before: "unknown", after: "scRNA-seq" }],
          }};
        }
      } else if (path.endsWith("/clarification/cancel")) {
        state = { ...state, clarifications: [{ ...state.clarifications[0], status: "cancelled" }] };
      } else if (path.endsWith("/clarification/revise")) {
        state = { ...state, clarifications: [
          { ...state.clarifications[0], status: "superseded" },
          { ...state.clarifications[0], id: "f".repeat(32), digest: "1".repeat(64), status: "pending", answers: [] },
        ] };
      } else throw new Error("Unexpected write: " + path);
      return response(state);
    }
    if (path === "/api/sessions") return response({ sessions: [state] });
    if (path === "/api/sessions/question-session") return response(state);
    if (path.includes("/intake?")) return response({
      upload_id: aid, facts, state: "draft", next_tool: null, missing_fields: ["assay"],
      blockers: [], qc_state: "not_run", measurement_spec_ref: null,
      observed: { n_observations: 4, n_genes: 3, matrix_locations: ["X"], obs_columns: [], var_columns: [] },
      roadmap: [],
    });
    throw new Error("Unexpected request: " + path);
  });
  return { writes };
}

beforeEach(() => localStorage.clear());

it("renders inline options without selecting or submitting a biological fact", async () => {
  const { writes } = setup();
  const user = userEvent.setup();
  render(<App />);
  const radio = await screen.findByRole("radio", { name: /单细胞测序/ });
  expect(radio).not.toBeChecked();
  const submit = screen.getByRole("button", { name: "提交答案" });
  expect(submit).toBeDisabled();
  await user.click(radio);
  expect(writes).toHaveLength(0);
  await user.click(submit);
  await waitFor(() => expect(screen.getByText("已回答")).toBeInTheDocument());
  expect(writes).toHaveLength(1);
  expect(writes[0]).toEqual({
    path: "/api/sessions/question-session/clarification/answer",
    body: { card_id: "b".repeat(32), card_digest: "c".repeat(64),
      answers: [{ field: "assay", selected: ["scRNA-seq"], text: "", unknown: false }] },
  });
  expect(screen.queryByRole("button", { name: "Confirm analysis" })).not.toBeInTheDocument();
});

it("keeps unknown exclusive and retains a private supplementary answer", async () => {
  const { writes } = setup();
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole("radio", { name: /单细胞测序/ }));
  await user.click(screen.getByRole("radio", { name: "未知／不确定" }));
  expect(screen.getByRole("radio", { name: /单细胞测序/ })).not.toBeChecked();
  await user.type(screen.getByLabelText("补充说明"), "文献没有说明");
  await user.click(screen.getByRole("button", { name: "提交答案" }));
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0].body.answers).toEqual([{ field: "assay", selected: [], text: "文献没有说明", unknown: true }]);
});

it("permits a free-text alternative without forcing a listed answer", async () => {
  const value = initial();
  value.clarifications[0].questions[0].field = "target_cell_type";
  const { writes } = setup(value);
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole("radio", { name: "其他／自行填写" }));
  await user.type(screen.getByLabelText("补充说明"), "用户补充的目标");
  await user.click(screen.getByRole("button", { name: "提交答案" }));
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0].body.answers).toEqual([{ field: "target_cell_type", selected: [], text: "用户补充的目标", unknown: false }]);
});

it("supports multiple priorities and keyboard submission with no analysis approval", async () => {
  const value = initial();
  value.clarifications[0].questions[0] = { field: "assessment_focus", title: "希望先看什么？",
    reason: "仅决定阅读重点", multiple: true, options: [
      { id: "composition", label: "细胞组成", description: "参考支持" },
      { id: "development", label: "发育阶段", description: "预期窗口" },
    ] };
  const { writes } = setup(value);
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole("checkbox", { name: /细胞组成/ }));
  await user.click(screen.getByRole("checkbox", { name: /发育阶段/ }));
  screen.getByRole("button", { name: "提交答案" }).focus();
  await user.keyboard("{Enter}");
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0].body.answers).toEqual([{ field: "assessment_focus",
    selected: ["composition", "development"], text: "", unknown: false }]);
});

it("restores a saved answer on refresh and provides an explicit revision action", async () => {
  const value = initial();
  value.clarifications[0].status = "answered";
  value.clarifications[0].answers = [{ field: "assay", selected: [], text: "尚不确定", unknown: true }];
  const { writes } = setup(value);
  const user = userEvent.setup();
  const view = render(<App />);
  expect(await screen.findByText("尚不确定")).toBeInTheDocument();
  view.unmount();
  render(<App />);
  await user.click(await screen.findByRole("button", { name: "修改回答" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "提交答案" })).toBeInTheDocument());
  expect(writes[0].path).toMatch(/clarification\/revise$/);
});

it("makes stale questions read-only and never submits their old digest", async () => {
  const value = initial();
  value.clarifications[0].status = "stale";
  const { writes } = setup(value);
  render(<App />);
  expect(await screen.findByText(/相关资料已变化/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "提交答案" })).not.toBeInTheDocument();
  expect(writes).toHaveLength(0);
});
