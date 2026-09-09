import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProductIntake } from "../src/components/ProductIntake";
import type { Session } from "../src/types";

const aid = "a".repeat(32);
const session = { id: "intake-stepper", title: "Case", status: "idle", updated_at: "",
  messages: [], uploads: [{ id: aid, name: "sample.h5ad", size: 10, kind: "h5ad" }],
  plan: null, artifacts: [], error: null, input_review_required: false, pending_input_change: null } as Session;
const response = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
function setup(state = "complete") {
  const writes: { path: string; body: unknown }[] = [];
  const value = {
    upload_id: aid, state: "draft", observed: { n_observations: 6247, n_genes: 33538,
      matrix_locations: ["X"], obs_columns: ["sample_id", "culture_day"], var_columns: ["gene_symbol"] },
    facts: { product_name: null, product_family: "unknown", target_cell_type: null, target_stage: null,
      starting_cell_type: null, cell_line: null, culture_day: 28, sequencing_method: null, protocol_name: null,
      sampling_context: "unknown", independent_cultures: null, assay: "unknown", matrix_location: "X",
      count_semantics: "unknown", source_family_id: null, sample_id_column: "sample_id",
      capture_id_column: null, gene_symbol_column: "gene_symbol" },
    missing_fields: [], next_tool: null, blockers: [], qc_state: "not_run", measurement_spec_ref: null, roadmap: [],
    autofill: { state, revision: 3, sources: [{ id: "M1", kind: "metadata", label: "obs.culture_day", location: "obs.culture_day", text: "28" }],
      field_sources: { culture_day: { kind: "metadata", source_ids: ["M1"], quote: "28" } },
      samples: [{ sample_id: "A", culture_days: [28], missing_days: 0, n_observations: 6247, sample_summary_complete: true }],
      protocols: [], protocol_stages: [], other_answers: {}, conflicts: [],
      questions: [{ field: "starting_cell_type", title: "实验使用什么起始细胞？", input_type: "text",
        options: [{ value: "iPSC", label: "诱导多能干细胞（iPSC）" }, { value: "__other__", label: "其他" }] },
        { field: "cell_line", title: "使用的是哪一株细胞系？", input_type: "text", options: [] }] },
  };
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = String(input);
    if (init?.method === "POST") {
      const body = init.body instanceof FormData ? init.body : JSON.parse(String(init.body));
      writes.push({ path, body });
      if (path.endsWith("/answer")) {
        const answer = body as { field: string; value: string; other: boolean };
        Object.assign(value.facts, { [answer.field]: answer.value });
        value.autofill.revision++;
        value.autofill.questions = value.autofill.questions.filter(q => q.field !== answer.field);
        return response(value);
      }
      if (path.endsWith("/parse") || path.includes("/protocols?")) {
        value.autofill.state = "parsing";
        return response({ ...session, status: "thinking" });
      }
      throw new Error(path);
    }
    if (path.includes("/intake?")) return response(value);
    throw new Error(path);
  });
  const props = { session, busy: false, onSession: vi.fn(), onError: vi.fn(), onConfirm: vi.fn(), onDiscard: vi.fn() };
  return { value, writes, props };
}

it("shows metadata first and saves one starting-cell answer without repeating the day", async () => {
  const { writes, props } = setup();
  const user = userEvent.setup();
  render(<ProductIntake {...props} />);
  expect(await screen.findByText("D28")).toBeInTheDocument();
  expect(screen.queryByText("产品类别", { selector: "legend" })).not.toBeInTheDocument();
  expect(screen.queryByRole("radio", { name: /未知|不确定/ })).not.toBeInTheDocument();
  await user.click(screen.getByRole("radio", { name: "诱导多能干细胞（iPSC）" }));
  await user.click(screen.getByRole("button", { name: "保存并继续" }));
  expect(await screen.findByText("使用的是哪一株细胞系？")).toBeInTheDocument();
  expect(writes).toHaveLength(1);
  expect(writes[0]).toMatchObject({ body: { upload_id: aid, revision: 3, field: "starting_cell_type", value: "iPSC", other: false } });
});

it("shows the data-column question with its counting boundary and sends a semantic answer", async () => {
  const { value, writes, props } = setup();
  Object.assign(value.autofill, { questions: [{ field: "culture_batch_role",
    title: "数据中的 sample_id（取值：A）是否表示独立培养批次？", input_type: "text",
    help: "只有每个值对应一次独立培养时才能据此计数。",
    options: [{ value: "independent_culture", label: "是，每个值对应一次独立培养" },
      { value: "not_culture", label: "不是，只是样本或测序标识" }, { value: "unsure", label: "不确定" }] }] });
  const user = userEvent.setup();
  render(<ProductIntake {...props} />);
  expect(await screen.findByText("只有每个值对应一次独立培养时才能据此计数。")).toBeInTheDocument();
  expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
  await user.click(screen.getByRole("radio", { name: "不确定" }));
  await user.click(screen.getByRole("button", { name: "保存并继续" }));
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0]).toMatchObject({ body: { field: "culture_batch_role", value: "unsure", other: false } });
});

it("rechecks the bound column instead of offering a detached numeric edit", async () => {
  const { value, writes, props } = setup();
  Object.assign(value.facts, { independent_cultures: 2, culture_batch_column: "sample_id", culture_batch_role: "independent_culture" });
  Object.assign(value.autofill, { batch_binding: { column: "sample_id", role: "independent_culture",
    distinct: 2, complete: true, missing: 0 }, questions: [] });
  const user = userEvent.setup();
  render(<ProductIntake {...props} />);
  await user.click(await screen.findByRole("button", { name: "重新核对批次字段" }));
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0]).toMatchObject({ body: { field: "culture_batch_column", value: "sample_id", other: false } });
  expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
});

it("explains why an incomplete batch column has no derived culture count", async () => {
  const { value, props } = setup();
  Object.assign(value.autofill, { batch_binding: { column: "sample_id", role: "independent_culture",
    distinct: 2, complete: true, missing: 1 }, questions: [] });
  render(<ProductIntake {...props} />);
  expect(await screen.findByText("这列有缺失值或读取不完整，独立培养次数仍未确定。")).toBeInTheDocument();
});

it("saves a revised free-text culture mapping as a supplement, not an invented column", async () => {
  const { value, writes, props } = setup();
  Object.assign(value.autofill, { questions: [], other_answers: { culture_batch_column: "A pools two cultures" } });
  const user = userEvent.setup();
  render(<ProductIntake {...props} />);
  await user.click(await screen.findByRole("button", { name: "修改对应关系" }));
  const input = screen.getByRole("textbox", { name: "修改批次核对字段或对应关系" });
  await user.clear(input);
  await user.type(input, "A pools three cultures");
  await user.click(screen.getByRole("button", { name: "保存并继续" }));
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0]).toMatchObject({ body: { field: "culture_batch_column", value: "A pools three cultures", other: true } });
});

it("shows and edits a custom column meaning without converting it to a predefined role", async () => {
  const { value, writes, props } = setup();
  Object.assign(value.facts, { culture_batch_column: "sample_id", culture_batch_role: "unknown" });
  Object.assign(value.autofill, { questions: [], other_answers: { culture_batch_role: "Sample pools two cultures" },
    batch_binding: { column: "sample_id", role: "unknown", distinct: 1, complete: true, missing: 0 } });
  const user = userEvent.setup();
  render(<ProductIntake {...props} />);
  expect(await screen.findByText(/Sample pools two cultures/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "修改字段说明" }));
  const input = screen.getByRole("textbox", { name: "修改字段含义" });
  expect(input).toHaveValue("Sample pools two cultures");
  await user.clear(input);
  await user.type(input, "Sample pools three cultures");
  await user.click(screen.getByRole("button", { name: "保存并继续" }));
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0]).toMatchObject({ body: {
    field: "culture_batch_role", value: "Sample pools three cultures", other: true } });
});

it("requires text for Other and sends the typed answer", async () => {
  const { writes, props } = setup();
  const user = userEvent.setup();
  render(<ProductIntake {...props} />);
  await user.click(await screen.findByRole("radio", { name: "其他" }));
  expect(screen.getByRole("button", { name: "保存并继续" })).toBeDisabled();
  await user.type(screen.getByLabelText("请填写具体内容"), "primary neural cells");
  await user.click(screen.getByRole("button", { name: "保存并继续" }));
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0]).toMatchObject({ body: { value: "primary neural cells", other: true } });
});

it("starts semantic parsing once and waits before showing missing questions", async () => {
  const { writes, props } = setup("not_started");
  render(<ProductIntake {...props} />);
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0].path).toMatch(/intake\/parse$/);
  expect(screen.queryByRole("radio", { name: /iPSC/ })).not.toBeInTheDocument();
  expect(screen.getByText(/正在解析实验元数据/)).toBeInTheDocument();
});

it("uploads protocol through its separate attachment endpoint without staging facts", async () => {
  const { writes, props } = setup();
  const user = userEvent.setup();
  render(<ProductIntake {...props} />);
  const input = await screen.findByLabelText("上传分化 protocol");
  await user.upload(input, new File(["Starting cells: iPSC"], "protocol.txt", { type: "text/plain" }));
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0].path).toContain("/intake/protocols?upload_id=");
  expect(writes[0].body).toBeInstanceOf(FormData);
  expect(props.onConfirm).not.toHaveBeenCalled();
});

it("offers an explicit retry when the initial parse request fails", async () => {
  const { props } = setup("not_started");
  const existing = vi.mocked(globalThis.fetch).getMockImplementation()!;
  vi.mocked(globalThis.fetch).mockImplementation(async (input, init) =>
    String(input).endsWith("/parse")
      ? new Response(JSON.stringify({ detail: "worker_busy" }), { status: 429, headers: { "Content-Type": "application/json" } })
      : existing(input, init));
  render(<ProductIntake {...props} />);
  expect(await screen.findByRole("button", { name: "重试解析" })).toBeEnabled();
  expect(screen.queryByText(/正在解析实验元数据/)).not.toBeInTheDocument();
});

it("keeps unsupported protocol dates empty with an explicit review note", async () => {
  const { value, props } = setup();
  Object.assign(value.autofill, { protocol_stages: [{ label: "Candidate stage", start_day: null, end_day: null,
    operations: "Review source protocol", source_ids: ["M1"], quote: "Original text", timing_state: "needs_confirmation" }] });
  render(<ProductIntake {...props} />);
  expect(await screen.findByText("起止时间未获引用原文明确支持，已留空待核对。")).toBeInTheDocument();
  expect(screen.queryByText("D22–D28")).not.toBeInTheDocument();
});
