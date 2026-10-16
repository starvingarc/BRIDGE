import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BoundConversation } from "../src/workbench/BoundConversation";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const session = (patch = {}) => ({ id: "bound-chat", status: "idle", messages: [], error: null, ...patch });
const base = { researchId: "research", runId: null, label: "研究总对话", onOpenSession: vi.fn() };

it("restores history, reuses one conversation and preserves failed text for retry", async () => {
  let sends = 0;
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input); calls.push(`${init?.method ?? "GET"} ${url}`);
    if (url.endsWith("/conversation") && init?.method !== "POST") return json({ detail: "conversation_not_found" }, 404);
    if (url.endsWith("/messages") && ++sends === 1) return json({ user_message: "暂时不可用" }, 503);
    if (url.endsWith("/messages")) return json(session({ messages: [{ id: "answer", role: "assistant", content: "Saved answer" }] }));
    return json(session());
  }));
  render(<BoundConversation {...base} />);
  const input = await screen.findByRole("textbox", { name: "问 BRIDGE" });
  await waitFor(() => expect(input).toBeEnabled());
  fireEvent.change(input, { target: { value: "Preserve this question" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  expect(await screen.findByRole("alert")).toBeVisible();
  expect(screen.getByRole("textbox", { name: "问 BRIDGE" })).toHaveValue("Preserve this question");
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  expect(await screen.findByText("Saved answer")).toBeVisible();
  expect(calls.filter(c => c === "POST /api/researches/research/conversation")).toHaveLength(1);
  expect(calls.filter(c => c === "POST /api/sessions/bound-chat/messages")).toHaveLength(2);
  expect(base.onOpenSession).not.toHaveBeenCalled();
});

it("ignores a late read after the bound scope is replaced", async () => {
  let finish!: (value: Response) => void;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => String(input).includes("/runs/old/")
    ? new Promise<Response>(resolve => { finish = resolve; })
    : json(session({ id: "new-chat", messages: [{ id: "new", role: "assistant", content: "New round history" }] }))));
  const { rerender } = render(<BoundConversation key="old" {...base} runId="old" />);
  await waitFor(() => expect(finish).toBeDefined());
  rerender(<BoundConversation key="new" {...base} runId="new" />);
  fireEvent.click(screen.getByRole("button", { name: "展开对话" }));
  expect(await screen.findByText("New round history")).toBeVisible();
  await act(async () => finish(json(session({ messages: [{ id: "old", role: "assistant", content: "Old round secret" }] }))));
  expect(screen.queryByText("Old round secret")).not.toBeInTheDocument();
});

it("polls actual replies, exposes stop, and leaves approvals in the existing full conversation", async () => {
  const calls: string[] = [];
  let stopped = false;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input); calls.push(url);
    if (url.endsWith("/stop")) { stopped = true; return json(session()); }
    if (url.endsWith("/messages")) return json(session({ status: "thinking" }));
    if (url.endsWith("/conversation")) return json(session());
    return json(session({ status: "thinking" }));
  }));
  const onOpenSession = vi.fn();
  render(<BoundConversation {...base} onOpenSession={onOpenSession} />);
  await waitFor(() => expect(screen.getByRole("textbox", { name: "问 BRIDGE" })).toBeEnabled());
  fireEvent.change(screen.getByRole("textbox", { name: "问 BRIDGE" }), { target: { value: "Read this round" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  await waitFor(() => expect(calls).toContain("/api/sessions/bound-chat/messages"));
  fireEvent.click(await screen.findByRole("button", { name: "停止" }));
  await waitFor(() => expect(stopped).toBe(true));
  fireEvent.click(screen.getByRole("button", { name: "打开完整会话" }));
  expect(onOpenSession).toHaveBeenCalledWith("bound-chat");
});


it("reconciles an accepted question after a lost response instead of inviting a duplicate send", async () => {
  let sent = false;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/conversation")) return json(session());
    if (url.endsWith("/messages")) { sent = true; throw new TypeError("Connection lost"); }
    return json(session({ status: "thinking", messages: [{ id: "accepted", role: "user", content: "Accepted question" }] }));
  }));
  render(<BoundConversation {...base} />);
  await waitFor(() => expect(screen.getByRole("textbox", { name: "问 BRIDGE" })).toBeEnabled());
  fireEvent.change(screen.getByRole("textbox", { name: "问 BRIDGE" }), { target: { value: "Accepted question" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  await waitFor(() => expect(sent).toBe(true));
  await waitFor(() => expect(screen.getByRole("textbox", { name: "问 BRIDGE" })).toHaveValue(""));
  expect(screen.getByRole("textbox", { name: "问 BRIDGE" })).toBeDisabled();
  expect(screen.getByText("Accepted question")).toBeVisible();
});

it("does not send to a scope unmounted while its first conversation is being created", async () => {
  let finish!: (value: Response) => void;
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input); calls.push(`${init?.method ?? "GET"} ${url}`);
    if (init?.method === "POST") return new Promise<Response>(resolve => { finish = resolve; });
    return json({ detail: "conversation_not_found" }, 404);
  }));
  const { unmount } = render(<BoundConversation {...base} />);
  await waitFor(() => expect(screen.getByRole("textbox", { name: "问 BRIDGE" })).toBeEnabled());
  fireEvent.change(screen.getByRole("textbox", { name: "问 BRIDGE" }), { target: { value: "Old scope question" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  await waitFor(() => expect(finish).toBeDefined());
  unmount();
  await act(async () => finish(json(session())));
  expect(calls.some(url => url.endsWith("/messages"))).toBe(false);
});

it.each([false, true])("continues polling after an in-flight poll is invalidated by stop (failed=%s)", async failed => {
  let finish!: (value: Response) => void, reject!: (reason: Error) => void;
  let reads = 0;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/conversation")) return json(session({ status: "thinking" }));
    if (url.endsWith("/stop")) return json(session({ status: "stopping" }));
    if (++reads === 1) return new Promise<Response>((resolve, fail) => { finish = resolve; reject = fail; });
    return json(session());
  }));
  render(<BoundConversation {...base} />);
  fireEvent.click(screen.getByRole("button", { name: "展开对话" }));
  await waitFor(() => expect(finish).toBeDefined(), { timeout: 2200 });
  fireEvent.click(screen.getByRole("button", { name: "停止" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "停止" })).toBeEnabled());
  await act(async () => { if (failed) reject(new Error("old poll failed")); else finish(json(session({ status: "thinking" }))); });
  await waitFor(() => expect(screen.getByRole("textbox", { name: "问 BRIDGE" })).toBeEnabled(), { timeout: 2200 });
});

it("serializes retry and stop so neither can strand the other loading state", async () => {
  let reads = 0, finishRead!: (value: Response) => void, finishStop!: (value: Response) => void;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/conversation")) return json(session({ status: "thinking" }));
    if (url.endsWith("/model-selection")) return json({ detail: "Not Found" }, 404);
    if (url.endsWith("/stop")) return new Promise<Response>(resolve => { finishStop = resolve; });
    if (++reads === 1) throw new TypeError("Read failed");
    return new Promise<Response>(resolve => { finishRead = resolve; });
  }));
  render(<BoundConversation {...base} />);
  const retry = await screen.findByRole("button", { name: "重新读取会话" }, { timeout: 2200 });
  fireEvent.click(screen.getByRole("button", { name: "停止" }));
  await waitFor(() => expect(finishStop).toBeDefined());
  expect(retry).toBeDisabled();
  await act(async () => finishStop(json(session({ status: "stopping" }))));
  fireEvent.click(retry);
  await waitFor(() => expect(finishRead).toBeDefined());
  expect(screen.getByRole("button", { name: "停止" })).toBeDisabled();
  await act(async () => finishRead(json(session())));
  await waitFor(() => expect(screen.getByRole("textbox", { name: "问 BRIDGE" })).toBeEnabled());
});

it("does not demand analysis data after an ordinary workbench discussion", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(session({ presentation: {
    summary: "请先提供本次研究要分析的数据。", next_actions: [{ id: "provide_input", label: "提供数据" }],
  } }))));
  render(<BoundConversation {...base} />);
  await waitFor(() => expect(screen.getByRole("textbox", { name: "问 BRIDGE" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "展开对话" }));
  expect(screen.queryByText(/请先提供本次研究要分析的数据/)).not.toBeInTheDocument();
});
