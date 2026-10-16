import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../src/App";
import { testPrincipal, onTestSignedOut } from "./account-fixture";
import type { Session } from "../src/types";

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), {status});
const rid = "a".repeat(32), secondRid = "b".repeat(32), mid = "c".repeat(32);
const base = (id: string, title: string, research_id: string | null = rid): Session & {research_id: string | null} => ({
  id, title, research_id, updated_at: "2026-10-10T00:00:00Z", status: "idle", archived: false,
  messages: [], uploads: [], plan: null, artifacts: [], error: null,
  input_review_required: false, pending_input_change: null,
});
function setup(options: {delayFirstResearch?: Promise<Response>} = {}) {
  const research = {id: rid, name: "细胞分化研究", description: "合成研究", created_at: "2026-10-10", updated_at: "2026-10-10", session_count: 2, material_count: 1};
  const other = {...research, id: secondRid, name: "培养条件探索", session_count: 0, material_count: 0};
  const studies = [research, other];
  const materials = [{id: mid, name: "shared.h5ad", kind: "h5ad", size: 64, created_at: "2026-10-10"}];
  const sessions = [base("first", "第一段讨论"), base("second", "另一段讨论"), base("legacy", "早期记录", null)];
  sessions[0].messages = [{id: "m1", role: "user", content: "只属于第一段讨论的问题", created_at: "2026-10-10"}];
  let serial = 0;
  const selections: Array<{material_id: string; upload_id?: string}> = [];
  const protocols: Record<string, Array<{id: string; name: string}>> = {};

  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = String(input), method = init?.method ?? "GET";
    const body = typeof init?.body === "string" ? JSON.parse(init.body) : {};
    if (path === "/api/researches") {
      if (method === "POST") {
        const created = {...other, id: "d".repeat(32), name: body.name, description: body.description};
        studies.push(created); return json({...created, materials: []});
      }
      return json({researches: studies});
    }
    if (path === `/api/researches/${rid}` && options.delayFirstResearch) return options.delayFirstResearch;
    const study = studies.find(item => path === `/api/researches/${item.id}`);
    if (study) return json({...study, materials: study.id === rid ? materials : []});
    if (path === "/api/config") return json({max_upload_bytes: 1024, max_h5ad_logical_bytes: 2048, max_h5ad_dataset_elements: 1000});
    if (path === "/api/sessions") {
      if (method === "POST") {
        const session = base("created-" + ++serial, "New analysis", body.research_id);
        sessions.push(session); return json(session);
      }
      return json({sessions});
    }
    const session = sessions.find(item => path === `/api/sessions/${item.id}` || path.startsWith(`/api/sessions/${item.id}/`));
    if (session) {
      if (path.includes("/intake?")) {
        const aid = new URL(path, "http://testserver").searchParams.get("upload_id")!;
        return json({upload_id: aid, facts: {product_family: "unknown"}, state: "draft", missing_fields: [],
          next_tool: null, blockers: [], qc_state: "not_run", measurement_spec_ref: null, roadmap: [],
          observed: {n_observations: 4, n_genes: 3, matrix_locations: ["X"], obs_columns: [], var_columns: []},
          autofill: {state: "complete", revision: 1, sources: [], fields: {}, field_sources: {}, questions: [], conflicts: [],
            other_answers: {}, samples: [], protocols: protocols[aid] ?? [], protocol_stages: [], formalizations: [], sources_truncated: false, batch_binding: null}});
      }
      if (path.endsWith("/research-materials")) {
        selections.push(body);
        if (body.upload_id) {
          protocols[body.upload_id] = [{id: body.material_id, name: "method.txt"}];
          session.updated_at = "2026-10-10T01:00:00Z";
          return json(session);
        }
        session.uploads = [{id: "selected-upload", material_id: mid, name: "shared.h5ad", kind: "h5ad", size: 64} as Session["uploads"][number]];
      }
      if (path.endsWith("/messages")) {
        session.messages.push({id: "new-message", role: "user", content: body.text, created_at: "2026-10-10"});
      }
      if (path.endsWith("/title")) session.title = body.title;
      if (path.endsWith("/research")) session.research_id = body.research_id;
      return json(session);
    }
    if (path.endsWith("/workbench")) return json({protocols: [], runs: [], samples: [], assessments: [], leads: [], actions: []});
    if (path === "/api/workbench/devtree") return json({detail: "Not Found"}, 404);
    if (path === `/api/researches/${"f".repeat(32)}`) return json({detail: "research_not_found"}, 404);
    throw new Error("Unexpected request: " + path);
  });
  return {sessions, studies, materials, selections};
}

beforeEach(() => localStorage.clear());

/** Researches open in the incubator; conversations are one step further, under the rail entry. */
const openSessions = async () => userEvent.click(await screen.findByRole("button", {name: "会话"}));

it("lands in the latest research after sign-in and keeps independently selected conversation history", async () => {
  setup(); render(<App principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  expect(await screen.findByRole("heading", {name: "培养箱"})).toBeVisible();
  expect(window.location.hash).toBe(`#/r/${rid}`);
  expect(screen.queryByRole("heading", {name: "我的研究"})).not.toBeInTheDocument();
  expect(screen.queryByText("只属于第一段讨论的问题")).not.toBeInTheDocument();
  await openSessions();
  expect(await screen.findByText("只属于第一段讨论的问题")).toBeVisible();
  await userEvent.click(screen.getByRole("button", {name: "新建会话"}));
  expect(await screen.findByRole("heading", {name: "这次想研究什么？"})).toBeVisible();
  expect(screen.queryByText("只属于第一段讨论的问题")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", {name: "研究资料"}));
  expect(await screen.findByText("shared.h5ad")).toBeVisible();
  await userEvent.click(screen.getByRole("button", {name: "关闭研究资料"}));
  await userEvent.click(screen.getByRole("button", {name: "第一段讨论"}));
  expect(await screen.findByText("只属于第一段讨论的问题")).toBeVisible();  await userEvent.click(screen.getByRole("button", {name: "培养箱"}));
  expect(await screen.findByRole("heading", {name: "培养箱"})).toBeVisible();
});

it("creates a real empty research without fabricating materials or a conversation", async () => {
  const model = setup(); render(<App principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await userEvent.click(await screen.findByRole("button", {name: "所有研究"}));
  await userEvent.click(await screen.findByRole("button", {name: "新建研究"}));
  await userEvent.type(screen.getByLabelText("研究名称"), "新研究主题");
  await userEvent.click(screen.getByRole("button", {name: "创建研究"}));
  expect(await screen.findByRole("heading", {name: "从一份方案开始"})).toBeVisible();
  await openSessions();
  expect(await screen.findByRole("heading", {name: "开始第一段讨论"})).toBeVisible();
  expect(model.sessions).toHaveLength(3);
  await userEvent.click(screen.getByRole("button", {name: "研究资料"}));
  expect(await screen.findByText("还没有研究资料")).toBeVisible();
});

it("selects a shared file only for the open conversation", async () => {
  const model = setup(); render(<App principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await screen.findByRole("heading", {name: "培养箱"});
  await openSessions();
  await userEvent.click(await screen.findByRole("button", {name: "研究资料"}));
  const dialog = await screen.findByRole("dialog", {name: "研究资料"});
  await userEvent.click(within(dialog).getByRole("button", {name: "用于本会话"}));
  expect(await within(dialog).findByText("本会话已选")).toBeVisible();
  expect(model.sessions[1].uploads).toEqual([]);
  await userEvent.click(screen.getByRole("button", {name: "关闭研究资料"}));
  expect(within(screen.getByLabelText("Uploaded files")).getByText("shared.h5ad")).toBeVisible();
});

it("preserves access to historical conversations and explicit assignment", async () => {
  setup(); render(<App principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await userEvent.click(await screen.findByRole("button", {name: "所有研究"}));
  await userEvent.click(await screen.findByRole("button", {name: "打开历史会话"}));
  expect(await screen.findByRole("heading", {name: "早期记录"})).toBeVisible();
  await userEvent.click(screen.getByRole("button", {name: "移入研究"}));
  await userEvent.selectOptions(screen.getByLabelText("选择研究"), rid);
  await userEvent.click(screen.getByRole("button", {name: "确认移入"}));
  expect(await screen.findByText("细胞分化研究", {selector: ".research-workspace-name"})).toBeVisible();
});

it("rejects a late research response after another research has opened", async () => {
  let release!: (response: Response) => void;
  const late = new Promise<Response>(resolve => {release = resolve;});
  const model = setup({delayFirstResearch: late});
  render(<App principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  // Signing in opens the first research, whose answer is held back; the user then opens the other one.
  await waitFor(() => expect(window.location.hash).toBe(`#/r/${rid}`));
  await act(async () => {window.location.hash = `#/r/${secondRid}`;});
  await openSessions();
  expect(await screen.findByRole("heading", {name: "开始第一段讨论"})).toBeVisible();
  await act(async () => release(json({...model.studies[0], materials: model.materials})));
  expect(screen.getByText("培养条件探索", {selector: ".research-workspace-name"})).toBeVisible();
  expect(screen.queryByText("只属于第一段讨论的问题")).not.toBeInTheDocument();
});


it("keeps the reviewed H5AD selected when adding a shared protocol and refreshes its background", async () => {
  const model = setup();
  model.sessions[0].uploads = [
    {id: "input-a", name: "first.h5ad", kind: "h5ad", size: 64},
    {id: "input-b", name: "second.h5ad", kind: "h5ad", size: 64},
  ];
  model.materials.push({id: "e".repeat(32), name: "method.txt", kind: "protocol", size: 24, created_at: "2026-10-10"});
  render(<App principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await screen.findByRole("heading", {name: "培养箱"});
  await openSessions();
  await userEvent.click(await screen.findByRole("button", {name: "实验背景"}));
  expect(await screen.findByLabelText("本次评估文件")).toHaveValue("input-b");
  await userEvent.click(await screen.findByRole("button", {name: "从研究资料选择方案"}));
  expect(await screen.findByLabelText("实验方案对应的数据")).toHaveValue("input-b");
  const row = (await screen.findByText("method.txt")).closest("li")!;
  await userEvent.click(within(row).getByRole("button", {name: "用于本会话"}));
  await screen.findByText("已加入当前会话；请在实验背景中核对资料。");
  expect(model.selections).toEqual([{material_id: "e".repeat(32), upload_id: "input-b"}]);
  await userEvent.click(screen.getByRole("button", {name: "关闭研究资料"}));
  expect(await screen.findByText("method.txt")).toBeVisible();
});

it("recovers a failed material listing without claiming files were loaded", async () => {
  setup();
  const fetch = vi.mocked(globalThis.fetch), original = fetch.getMockImplementation()!;
  let reads = 0;
  fetch.mockImplementation((input, init) => String(input) === `/api/researches/${rid}` && ++reads === 2
    ? Promise.resolve(json({detail: "temporarily_unavailable"}, 503)) : original(input, init));
  render(<App principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await screen.findByRole("heading", {name: "培养箱"});
  await openSessions();
  await userEvent.click(await screen.findByRole("button", {name: "研究资料"}));
  const retry = await screen.findByRole("button", {name: "重试读取资料"});
  expect(screen.queryByText("shared.h5ad")).not.toBeInTheDocument();
  await userEvent.click(retry);
  expect(await screen.findByText("shared.h5ad")).toBeVisible();
});

it("checks the current material limit before transmitting a file", async () => {
  setup(); render(<App principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await screen.findByRole("heading", {name: "培养箱"});
  await openSessions();
  await userEvent.click(await screen.findByRole("button", {name: "研究资料"}));
  await screen.findByText("shared.h5ad");
  fireEvent.change(screen.getByLabelText("添加研究资料"), {target: {files: [new File([new Uint8Array(1025)], "oversized.h5ad")]}});
  expect(await screen.findByText(/文件尚未发送/)).toBeVisible();
  expect(vi.mocked(globalThis.fetch).mock.calls.some(([path]) => String(path).endsWith("/uploads"))).toBe(false);
});

it("keeps an explicit conversation view when polling reports ready results", async () => {
  const model = setup(); model.sessions[0].status = "running";
  const fetch = vi.mocked(globalThis.fetch), original = fetch.getMockImplementation()!;
  let reads = 0;
  fetch.mockImplementation((input, init) => {
    if (String(input) === "/api/sessions/first" && ++reads > 1) {
      model.sessions[0].status = "idle";
      model.sessions[0].artifacts = [{id: "table", kind: "table", name: "counts.csv", media_type: "text/csv", url: "/api/sessions/first/artifacts/table", tool_id: "P0-01"}];
      model.sessions[0].presentation = {stage: "results_ready", stage_label: "已有结果", next_actions: [], observations: []} as unknown as Session["presentation"];
    }
    return original(input, init);
  });
  render(<App principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await screen.findByRole("heading", {name: "培养箱"});
  await openSessions();
  await userEvent.click(await screen.findByRole("button", {name: "对话"}));
  await waitFor(() => expect(reads).toBeGreaterThan(1), {timeout: 2500});
  expect(screen.getByRole("button", {name: "对话"})).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", {name: "结果"})).toBeEnabled();
});

it("writes the open place into the address and reopens it after a reload", async () => {
  setup(); render(<App principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await screen.findByRole("heading", {name: "培养箱"});
  expect(await screen.findByRole("heading", {name: "培养箱"})).toBeVisible();
  expect(window.location.hash).toBe(`#/r/${rid}`);
  await openSessions();
  expect(await screen.findByText("只属于第一段讨论的问题")).toBeVisible();
  expect(window.location.hash).toBe(`#/r/${rid}/sessions/first`);
  await userEvent.click(screen.getByRole("button", {name: "另一段讨论"}));
  await waitFor(() => expect(window.location.hash).toBe(`#/r/${rid}/sessions/second`));
});

it("opens a research conversation straight from its address", async () => {
  window.history.replaceState(null, "", `/#/r/${rid}/sessions/second`);
  setup(); render(<App principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  expect(await screen.findByRole("heading", {name: "另一段讨论"})).toBeVisible();
  await userEvent.click(screen.getByRole("button", {name: "培养箱"}));
  expect(await screen.findByRole("heading", {name: "培养箱"})).toBeVisible();
  expect(window.location.hash).toBe(`#/r/${rid}`);
  await act(async () => {window.location.hash = `#/r/${rid}/sessions/second`;});
  expect(await screen.findByRole("heading", {name: "另一段讨论"})).toBeVisible();
  await act(async () => {window.location.hash = "#/";});
  expect(await screen.findByRole("heading", {name: "我的研究"})).toBeVisible();
});

it("lands in the research opened last in this browser", async () => {
  localStorage.setItem(`bridge.lastResearch.${testPrincipal.id}`, secondRid);
  try {
    setup(); render(<App principal={testPrincipal} onSignedOut={onTestSignedOut} />);
    await waitFor(() => expect(window.location.hash).toBe(`#/r/${secondRid}`));
  } finally { localStorage.removeItem(`bridge.lastResearch.${testPrincipal.id}`); }
});

it("returns to the list with the reason when an address names a missing research", async () => {
  window.history.replaceState(null, "", `/#/r/${"f".repeat(32)}`);
  setup(); render(<App principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  expect(await screen.findByRole("alert")).toBeVisible();
  expect(window.location.hash).toBe("#/");
  expect(screen.getByRole("button", {name: "打开研究：细胞分化研究"})).toBeVisible();
});


it("opens existing reports from the research rail and keeps the report entry on reload", async () => {
  setup(); render(<App principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await screen.findByRole("heading", {name: "培养箱"});
  const reportEntry = await screen.findByRole("button", {name: "报告"});
  expect(reportEntry).toBeEnabled();
  await userEvent.click(reportEntry);
  expect(await screen.findByRole("tab", {name: "研究报告"})).toHaveAttribute("aria-selected", "true");
  expect(screen.getByText("尚无当前版本报告")).toBeVisible();
  expect(window.location.hash).toBe(`#/r/${rid}/reports/first`);
  expect(screen.getByRole("button", {name: "第一段讨论"})).toBeVisible();
});

it("loads a report deep link without selecting another conversation", async () => {
  setup(); window.history.replaceState(null, "", `/#/r/${rid}/reports/second`);
  render(<App principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  expect(await screen.findByRole("tab", {name: "研究报告"})).toHaveAttribute("aria-selected", "true");
  expect(window.location.hash).toBe(`#/r/${rid}/reports/second`);
});
