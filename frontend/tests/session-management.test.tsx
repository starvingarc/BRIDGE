import { testPrincipal, onTestSignedOut } from "./account-fixture";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SessionWorkspace from "../src/SessionWorkspace";
import type { Session } from "../src/types";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});
const makeSession = (id: string, title: string): Session => ({
  id, title, updated_at: "2026-10-09T10:00:00Z", status: "idle", archived: false,
  messages: [], uploads: [], plan: null, artifacts: [], error: null,
  input_review_required: false, pending_input_change: null,
});

function mockServer(failDelete = false) {
  const records = new Map([
    ["one", makeSession("one", "First analysis")],
    ["two", makeSession("two", "Second analysis")],
  ]);
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = String(input);
    if (path === "/api/model-settings") return json({ configured: true, base_url: "https://provider.invalid", model: "test", has_api_key: true, action_protocol: "json" });
    if (path === "/api/config") return json({ max_upload_bytes: 100000, max_h5ad_logical_bytes: 100000, max_h5ad_dataset_elements: 100000 });
    if (path === "/api/sessions") return json({ sessions: [...records.values()] });
    const match = path.match(/^\/api\/sessions\/([^/]+)$/);
    if (match) {
      const state = records.get(match[1]);
      if (!state) return json({ user_message: "会话不存在。" }, 404);
      if (init?.method === "PATCH") {
        state.archived = JSON.parse(String(init.body)).archived;
        return json(state);
      }
      if (init?.method === "DELETE") {
        if (failDelete) return json({ user_message: "当前工作仍在进行，请等待或先停止。" }, 409);
        records.delete(state.id);
        return json({ deleted: true });
      }
      return json(state);
    }
    throw new Error(`Unexpected request: ${path}`);
  });
  return { records, fetch };
}

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

it("archives, restores, confirms deletion and clears the selected session", async () => {
  const { records, fetch } = mockServer();
  const user = userEvent.setup();
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await user.click(await screen.findByRole("button", { name: "会话操作：First analysis" }));
  await user.click(screen.getByRole("button", { name: "归档会话" }));
  await waitFor(() => expect(screen.queryByRole("button", { name: "First analysis" })).not.toBeInTheDocument());
  expect(localStorage.getItem("bridge.preview.selected-session.v1.test-user-id")).toBeNull();
  await user.click(screen.getByRole("button", { name: /已归档/ }));
  expect(screen.getByRole("button", { name: "First analysis" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "会话操作：First analysis" }));
  await user.click(screen.getByRole("button", { name: "恢复会话" }));
  await waitFor(() => expect(records.get("one")?.archived).toBe(false));
  await user.click(screen.getByRole("button", { name: /^会话\s/ }));
  await user.click(screen.getByRole("button", { name: "First analysis" }));
  await user.click(screen.getByRole("button", { name: "会话操作：First analysis" }));
  await user.click(screen.getByRole("button", { name: "删除会话" }));
  const dialog = await screen.findByRole("dialog", { name: "删除会话？" });
  expect(within(dialog).getByText("First analysis", { exact: true })).toBeInTheDocument();
  await user.click(within(dialog).getByRole("button", { name: "取消" }));
  expect(records.has("one")).toBe(true);
  expect(fetch.mock.calls.filter(([, init]) => init?.method === "DELETE")).toHaveLength(0);
  await user.click(screen.getByRole("button", { name: "删除会话" }));
  await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "确认删除" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(records.has("one")).toBe(false);
  expect(records.has("two")).toBe(true);
  expect(localStorage.getItem("bridge.preview.selected-session.v1.test-user-id")).toBeNull();
  expect(screen.queryByRole("button", { name: "First analysis" })).not.toBeInTheDocument();
});

it("keeps the session and shows the server refusal inside the delete dialog", async () => {
  const { records } = mockServer(true);
  const user = userEvent.setup();
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await user.click(await screen.findByRole("button", { name: "会话操作：First analysis" }));
  await user.click(screen.getByRole("button", { name: "删除会话" }));
  const dialog = await screen.findByRole("dialog");
  await user.click(within(dialog).getByRole("button", { name: "确认删除" }));
  expect(await within(dialog).findByRole("alert")).toHaveTextContent("当前工作仍在进行");
  expect(records.has("one")).toBe(true);
  expect(screen.getByRole("button", { name: "First analysis" })).toBeInTheDocument();
});


it("keeps an in-flight reply when archiving a different session", async () => {
  const { fetch, records } = mockServer();
  const original = fetch.getMockImplementation()!;
  let finish!: (value: Response) => void;
  const pending = new Promise<Response>(resolve => { finish = resolve; });
  fetch.mockImplementation((input, init) => String(input) === "/api/sessions/one/messages"
    ? pending : original(input, init));
  const user = userEvent.setup();
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await user.type(await screen.findByPlaceholderText("继续提问…"), "Continue the question");
  await user.click(screen.getByRole("button", { name: "Send message" }));
  await user.click(screen.getByRole("button", { name: "会话操作：Second analysis" }));
  await user.click(screen.getByRole("button", { name: "归档会话" }));
  await waitFor(() => expect(records.get("two")?.archived).toBe(true));
  await act(async () => { finish(json({ ...records.get("one"), messages: [{
    id: "reply", role: "assistant", content: "Reply after archiving", created_at: "2026-10-09T10:01:00Z", source: "provider_admitted",
  }] })); });
  expect(await screen.findByText("Reply after archiving")).toBeInTheDocument();
});

it("disables empty-workspace creation until session management completes", async () => {
  const { fetch, records } = mockServer();
  const original = fetch.getMockImplementation()!;
  let finish!: (value: Response) => void;
  const pending = new Promise<Response>(resolve => { finish = resolve; });
  fetch.mockImplementation((input, init) => String(input) === "/api/sessions/two" && init?.method === "PATCH"
    ? pending : original(input, init));
  const user = userEvent.setup();
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await user.click(await screen.findByRole("button", { name: "会话操作：First analysis" }));
  await user.click(screen.getByRole("button", { name: "归档会话" }));
  await waitFor(() => expect(screen.getAllByRole("button", { name: /新建会话|开始会话/ })).toHaveLength(2));
  await user.click(screen.getByRole("button", { name: "会话操作：Second analysis" }));
  await user.click(screen.getByRole("button", { name: "归档会话" }));
  try {
    for (const button of screen.getAllByRole("button", { name: /新建会话|开始会话/ })) expect(button).toBeDisabled();
  } finally {
    await act(async () => { finish(json({ ...records.get("two"), archived: true })); });
  }
  await waitFor(() => expect(screen.queryByRole("button", { name: "Second analysis" })).not.toBeInTheDocument());
});
