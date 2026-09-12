import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProtocolReview } from "../src/components/ProtocolReview";
import type { ProtocolFormalization } from "../src/types";

const source = { id: "S1", kind: "protocol", label: "方案原文", location: "page 1, segment 1", text: "Wait for 2 h." };
const fixture = (): ProtocolFormalization => ({
  protocol_id: "b".repeat(32), name: "public-method.txt", revision: 2, state: "complete", error: null,
  versions: [{ id: "c".repeat(32), digest: "d".repeat(64), created_at: "", review_state: "unreviewed" }],
  latest: {
    id: "c".repeat(32), digest: "d".repeat(64), created_at: "", bpl: "protocol Probe {\n wait()\n}",
    steps: [{ id: "step-1", label: "等待", operations: "按原文给定时长等待。", line_start: 2, line_end: 2,
      source_ids: ["S1"], sources: [source], origin: "model_source" }],
    questions: [{ id: "duration", title: "这一步等待多久？", step_ids: ["step-1"], source_ids: ["S1"],
      sources: [source], options: [{ value: "source wording", label: "按原文已写明的安排" }], answer_state: "unanswered" }],
    excluded_sources: [], supplements: [], coverage_state: "needs_input", review_state: "unreviewed",
    syntax_state: "passed", compiler_state: "passed", diagnostics: [],
    unchecked: [{ code: "duration_unresolved", line: 2, message: "等待时长未明确，未检查。" }],
    compiler: { commit: "test-pin", version: "2.4.0", verified: true }, stages: [],
    source_binding: { sources_truncated: false, included_passages: 1, extracted_passages: 1 },
    generation: { number: 1, request_count: 1, model: "test", reported_model: null, prompt_version: "protocol-bpl-1", kind: "model" },
    artifacts: { bpl: "hash" },
  },
});
const downloads = (version: string, kind: string) => "/checked/" + version + "/" + kind;

it("separates compiler completion from source coverage and human review", async () => {
  const user = userEvent.setup();
  render(<ProtocolReview value={fixture()} busy={false} onAction={vi.fn()} downloadUrl={downloads} />);
  expect(screen.getByText("语法检查：通过")).toBeInTheDocument();
  expect(screen.getByText("编译器：返回成功")).toBeInTheDocument();
  expect(screen.getByText("来源与覆盖：仍有缺项")).toBeInTheDocument();
  expect(screen.getByText("人工核对：未核对")).toBeInTheDocument();
  expect(screen.queryByText("方案验证通过")).not.toBeInTheDocument();
  await user.click(screen.getByText("检查范围与未检查项"));
  expect(screen.getByText(/等待时长未明确，未检查/)).toBeInTheDocument();
  await user.click(screen.getByText("查看步骤出处"));
  expect(screen.getAllByText("Wait for 2 h.").length).toBeGreaterThan(0);
});

it("rejects empty Other and sends only the explicit protocol supplement", async () => {
  const onAction = vi.fn().mockResolvedValue(undefined);
  const user = userEvent.setup();
  render(<ProtocolReview value={fixture()} busy={false} onAction={onAction} downloadUrl={downloads} />);
  await user.click(screen.getByRole("radio", { name: "其他（自定义输入）" }));
  expect(screen.getByRole("button", { name: "保存方案补充" })).toBeDisabled();
  await user.type(screen.getByLabelText("方案补充内容"), "   ");
  expect(screen.getByRole("button", { name: "保存方案补充" })).toBeDisabled();
  await user.type(screen.getByLabelText("方案补充内容"), "等待 2 h");
  await user.click(screen.getByRole("button", { name: "保存方案补充" }));
  expect(onAction).toHaveBeenCalledExactlyOnceWith({ action: "answer", question_id: "duration",
    value: "等待 2 h", other: true, unsure: false });
});

it("lets unsure remain unresolved without a fabricated answer", async () => {
  const onAction = vi.fn().mockResolvedValue(undefined);
  const user = userEvent.setup();
  render(<ProtocolReview value={fixture()} busy={false} onAction={onAction} downloadUrl={downloads} />);
  await user.click(screen.getByRole("radio", { name: "暂不确定" }));
  await user.click(screen.getByRole("button", { name: "保存方案补充" }));
  expect(onAction).toHaveBeenCalledExactlyOnceWith({ action: "answer", question_id: "duration",
    value: "", other: false, unsure: true });
});

it("reviews only the visible digest after a deliberate acknowledgement", async () => {
  const value = fixture();
  const onAction = vi.fn().mockResolvedValue(undefined);
  const user = userEvent.setup();
  render(<ProtocolReview value={value} busy={false} onAction={onAction} downloadUrl={downloads} />);
  const save = screen.getByRole("button", { name: "保存核对版本" });
  expect(save).toBeDisabled();
  await user.click(screen.getByRole("checkbox", { name: /我已核对本版本及其未检查项/ }));
  await user.click(save);
  expect(onAction).toHaveBeenCalledExactlyOnceWith({ action: "review", digest: value.latest!.digest });
});

it("saves an edited BPL as a new unchecked version, never an execution", async () => {
  const onAction = vi.fn().mockResolvedValue(undefined);
  const user = userEvent.setup();
  render(<ProtocolReview value={fixture()} busy={false} onAction={onAction} downloadUrl={downloads} />);
  await user.click(screen.getByText("BPL 草稿与检查记录"));
  await user.click(screen.getByRole("button", { name: "编辑 BPL 草稿" }));
  const editor = screen.getByLabelText("BPL 草稿");
  await user.clear(editor);
  await user.type(editor, "protocol Changed {{ wait() }");
  const edited = (editor as HTMLTextAreaElement).value;
  await user.click(screen.getByRole("button", { name: "保存新草稿并重新检查" }));
  expect(onAction).toHaveBeenCalledExactlyOnceWith({ action: "edit", bpl: edited });
});

it("does not carry acknowledgement to another generated version", async () => {
  const user = userEvent.setup();
  const value = fixture();
  const view = render(<ProtocolReview value={value} busy={false} onAction={vi.fn()} downloadUrl={downloads} />);
  await user.click(screen.getByRole("checkbox", { name: /我已核对本版本及其未检查项/ }));
  const next = fixture();
  next.latest!.id = "e".repeat(32);
  next.latest!.digest = "f".repeat(64);
  view.rerender(<ProtocolReview value={next} busy={false} onAction={vi.fn()} downloadUrl={downloads} />);
  expect(screen.getByRole("checkbox", { name: /我已核对本版本及其未检查项/ })).not.toBeChecked();
  expect(screen.getByRole("button", { name: "保存核对版本" })).toBeDisabled();
});

it("keeps entered text when a save fails", async () => {
  const user = userEvent.setup();
  const onAction = vi.fn().mockRejectedValue(new Error("save failed"));
  render(<ProtocolReview value={fixture()} busy={false} onAction={onAction} downloadUrl={downloads} />);
  await user.click(screen.getByRole("radio", { name: "其他（自定义输入）" }));
  await user.type(screen.getByLabelText("方案补充内容"), "待核对的内容");
  await user.click(screen.getByRole("button", { name: "保存方案补充" }));
  expect(screen.getByLabelText("方案补充内容")).toHaveValue("待核对的内容");
  expect(screen.getByRole("button", { name: "保存方案补充" })).toBeEnabled();
});

it("shows retained history and does not offer review while replacement generation failed", () => {
  const value = fixture();
  value.state = "unavailable";
  value.error = "unsupported_literal";
  render(<ProtocolReview value={value} busy={false} onAction={vi.fn()} downloadUrl={downloads} />);
  expect(screen.getByText(/显示上次完整版本/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "保存核对版本" })).toBeDisabled();
  expect(screen.getByText("版本记录（1）")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "重试生成" })).toBeEnabled();
});
