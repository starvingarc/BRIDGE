import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConditionalInputs } from "../src/components/ConditionalInputs";
import { api } from "../src/api";
import type { ConditionalDraft, Session } from "../src/types";

const selection = { tool_id: "P0-07", mode_id: "legacy_comparison", asset_ids: [],
  object_inputs: [], measurement_spec_ref: null };
const entry = { id: "entry", label: "已登记比较方案 1", category_label: "可作描述性比较",
  execution_available: true, reasons: [], diagnostics: { selection, reason_codes: [] } };
const initial = (): Session => ({
  id: "session", title: "研究", updated_at: "", status: "idle", messages: [], uploads: [],
  plan: null, artifacts: [], error: null, input_review_required: false, pending_input_change: null,
  conditional_inputs: { input_revision: 3, access_boundary: "仅当前会话来源", scientific_boundary: "不回填移植前结果",
    comparison: { label: "产品比较", entries: [entry], reasons: [] },
    graft: { label: "移植后证据", entries: [], reasons: ["尚未提供移植后输入"] }, selections: [] },
});

test("selection, confirmation and unapproved plan preparation are distinct UI actions", async () => {
  const user = userEvent.setup();
  const onSession = vi.fn(), onError = vi.fn();
  const state = initial();
  const props = { session: state, busy: false, onSession, onError };
  const propose = vi.spyOn(api, "proposeConditionalInputs").mockResolvedValue(state);
  const decide = vi.spyOn(api, "decideConditionalInputs").mockResolvedValue(state);
  const rendered = render(<ConditionalInputs {...props} />);
  await user.click(screen.getByText("产品比较与移植后证据"));
  expect(screen.getByText("尚未提供移植后输入")).toBeVisible();
  expect(propose).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "核对并选择此方案" }));
  await waitFor(() => expect(propose).toHaveBeenCalledWith("session", selection, 3));
  const draft: ConditionalDraft = { ...entry, id: "draft", digest: "digest", status: "pending",
    status_label: "待确认", input_revision: 3 };
  state.conditional_inputs!.selections = [draft];
  rendered.rerender(<ConditionalInputs {...props} />);
  await user.click(screen.getByRole("button", { name: "确认所选输入" }));
  await waitFor(() => expect(decide).toHaveBeenCalledWith("session", "confirm", "draft", "digest", 3));
  draft.status = "confirmed"; draft.status_label = "已确认，仍需单独批准计划";
  state.conditional_inputs!.input_revision = 4;
  rendered.rerender(<ConditionalInputs {...props} />);
  await user.click(screen.getByRole("button", { name: "生成待审批计划" }));
  await waitFor(() => expect(decide).toHaveBeenCalledWith("session", "prepare", "draft", "digest", 4));
  expect(onError).not.toHaveBeenCalled();
});

test("ineligible entries and pending source review cannot execute", async () => {
  const state = initial();
  state.conditional_inputs!.comparison.entries[0] = { ...entry, execution_available: false,
    category_label: "仅作背景资料", reasons: ["缺少已冻结的比较规范"] };
  render(<ConditionalInputs session={state} busy={false} onSession={vi.fn()} onError={vi.fn()} />);
  await userEvent.setup().click(screen.getByText("产品比较与移植后证据"));
  expect(screen.getByRole("button", { name: "核对并选择此方案" })).toBeDisabled();
  expect(screen.getByText("缺少已冻结的比较规范")).toBeVisible();
});
