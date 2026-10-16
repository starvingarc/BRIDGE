import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthRoot } from "../src/AuthRoot";
import { AdminSessions } from "../src/components/AdminSessions";
import { ModelSettings } from "../src/components/ModelSettings";
import { api, resetAccountRequests } from "../src/api";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {status, headers: {"Content-Type": "application/json"}});
const user = {id: "alice-id", username: "alice", role: "user", must_change_password: false};
const config = {mode: "accounts", notice: "管理员可以查看测试会话。", notice_version: "v1", username_pattern: "[a-zA-Z0-9][a-zA-Z0-9_.-]{2,31}", password_min: 12, password_max: 128};
const model = {configured: true, base_url: "https://example.invalid/v1", model: "default-model", has_api_key: true, action_protocol: "json"};

test("registration requires notice and opens a private account workspace", async () => {
  const calls: [string, RequestInit | undefined][] = [];
  let signedIn = false;
  vi.stubGlobal("fetch", vi.fn(async (path, init) => {
    calls.push([String(path), init]);
    if (path === "/api/auth/config") return json(config);
    if (path === "/api/me") return signedIn ? json({user}) : json({}, 401);
    if (path === "/api/register") { signedIn = true; return json({user}); }
    if (path === "/api/logout") { signedIn = false; return json({authenticated: false}); }
    if (path === "/api/researches") return json({researches: []});
    if (path === "/api/sessions") return json({sessions: []});
    if (path === "/api/me/model-settings") return json({source: "default", default: model, personal: null});
    return json({});
  }));
  render(<AuthRoot />);
  await userEvent.click(await screen.findByRole("button", {name: "创建账号"}));
  await userEvent.type(screen.getByLabelText("用户名"), "alice");
  await userEvent.type(screen.getByLabelText("密码"), "example-password");
  expect(screen.getByRole("button", {name: "注册并登录"})).toBeDisabled();
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", {name: "注册并登录"}));
  expect(await screen.findByText("alice")).toBeInTheDocument();
  const body = JSON.parse(String(calls.find(([p]) => p === "/api/register")?.[1]?.body));
  expect(body).toEqual({username: "alice", password: "example-password", notice_version: "v1"});
  expect(JSON.stringify(localStorage)).not.toContain("example-password");
  await userEvent.click(screen.getByRole("button", {name: "alice"}));
  await userEvent.click(screen.getByRole("button", {name: "退出登录"}));
  expect(await screen.findByRole("button", {name: "登录"})).toBeInTheDocument();
});

test("expired request from old account cannot restore a session or expire the next account", async () => {
  let resolve!: (value: Response) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(done => { resolve = done; })));
  const listener = vi.fn();
  window.addEventListener("bridge-auth-expired", listener);
  const old = api.getSession("old-id").catch(error => error);
  resetAccountRequests();
  resolve(json({}, 401));
  expect((await old).status).toBe(0);
  expect(listener).not.toHaveBeenCalled();
  window.removeEventListener("bridge-auth-expired", listener);
});

test("temporary password blocks the workspace until changed", async () => {
  vi.stubGlobal("fetch", vi.fn(async path => path === "/api/auth/config" ? json(config) : json({user: {...user, must_change_password: true}})));
  render(<AuthRoot />);
  expect(await screen.findByRole("heading", {name: "请先修改临时密码"})).toBeInTheDocument();
  expect(screen.queryByRole("button", {name: /New analysis/})).not.toBeInTheDocument();
});

test("deletion stays in the unified account directory, without choosing a model there", async () => {
  const shared = {...model, id: "default", name: "Shared", models: ["default-model"], shared: true, editable: false};
  const personal = {...model, id: "personal", name: "Personal", models: ["my-model"], shared: false, editable: true};
  const initial = {providers: [shared, personal], selected: {provider_id: "default", model: "default-model"}};
  const fetch = vi.fn(async (path, init) => {
    if (String(path).endsWith("/select")) return json({...initial, selected: {provider_id: "personal", model: "my-model"}});
    if (init?.method === "DELETE") return json({...initial, providers: [shared]});
    return json(initial);
  });
  vi.stubGlobal("fetch", fetch);
  render(<ModelSettings />);
  expect(await screen.findByText("my-model")).toBeInTheDocument();
  expect(screen.queryByRole("button", {name: "my-model"})).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", {name: "删除 Personal (personal)"}));
  expect(screen.getByRole("alertdialog", {name: "删除 Personal (personal)？"})).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", {name: "删除 Personal (personal)"}));
  await waitFor(() => expect(screen.queryByText("Personal")).not.toBeInTheDocument());
  expect(fetch.mock.calls.every(([path]) => String(path).startsWith("/api/models"))).toBe(true);
});

test("administrator detail displays owner and audited read-only material links", async () => {
  vi.stubGlobal("fetch", vi.fn(async path => {
    if (path === "/api/admin/users") return json({users: [user]});
    if (String(path).startsWith("/api/admin/sessions?")) return json({sessions: [{id: "s1", title: "Synthetic study", owner_username: "alice", owner_id: user.id, status: "idle"}]});
    return json({owner: user, session: {id: "s1", title: "Synthetic study", status: "idle", messages: [{id: "m", role: "user", content: "Synthetic research question"}], uploads: [{id: "u1", name: "sample.h5ad"}], artifacts: []}, protocols: []});
  }));
  render(<AdminSessions />);
  await userEvent.click(screen.getByRole("button", {name: "测试管理"}));
  await userEvent.click(await screen.findByRole("button", {name: /Synthetic study/}));
  expect(await screen.findByText("Synthetic research question")).toBeInTheDocument();
  expect(screen.getByRole("link", {name: "sample.h5ad"})).toHaveAttribute("href", "/api/admin/sessions/s1/uploads/u1");
  expect(screen.queryByRole("button", {name: /批准|发送|运行分析/})).not.toBeInTheDocument();
});


test("an obsolete authentication mode cannot open the legacy token screen", async () => {
  vi.stubGlobal("fetch", vi.fn(async path => path === "/api/auth/config" ? json({mode: "token"}) : json({}, 401)));
  render(<AuthRoot />);
  expect(await screen.findByRole("alert")).toHaveTextContent("服务版本不兼容，请更新服务。");
  expect(screen.queryByLabelText("Access token")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", {name: "Sign in"})).not.toBeInTheDocument();
});
