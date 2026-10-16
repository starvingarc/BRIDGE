import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SettingsDialog } from "../src/components/SettingsDialog";
import { Sidebar } from "../src/components/Sidebar";
import { api, type Principal } from "../src/api";
const member: Principal = {id: "private-user-id", username: "alice", role: "user", must_change_password: false};
const directory = {providers: [{id: "default", name: "Shared", models: ["demo"], base_url: "https://example.invalid/v1", action_protocol: "json", has_api_key: true, configured: true, shared: true, editable: true}], selected: {provider_id: "default", model: "demo"}};

it("keeps only the account ID in the sidebar footer and opens grouped settings", async () => {
  const user = userEvent.setup();
  render(<Sidebar researchName="历史会话" onHome={vi.fn()} onRename={vi.fn()} principal={member} sessions={[]} selectedId={null} open={false} creating={false} disabled={false}
    onClose={vi.fn()} onCreate={vi.fn()} onSelect={vi.fn()} onLogout={vi.fn()} onSignedOut={vi.fn()} onManage={vi.fn()} />);
  const sidebar = screen.getByRole("complementary", {name: "会话导航"});
  expect(within(sidebar).getByRole("button", {name: "alice"})).toBeVisible();
  expect(within(sidebar).queryByRole("button", {name: /Sign out|修改密码|模型|测试管理/})).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", {name: "alice"}));
  expect(screen.getByRole("dialog", {name: "设置"})).toBeVisible();
  expect(screen.getByRole("tab", {name: "账号"})).toHaveAttribute("aria-selected", "true");
  expect(screen.queryByRole("tab", {name: "测试管理"})).not.toBeInTheDocument();
  expect(screen.getAllByRole("dialog")).toHaveLength(1);
});

it("embeds model settings, discards secrets on section changes and restores focus on close", async () => {
  const models = vi.spyOn(api, "models").mockResolvedValue(directory);
  const user = userEvent.setup();
  render(<SettingsDialog principal={member} disabled={false} onLogout={vi.fn()} />);
  await user.click(screen.getByRole("button", {name: "alice"}));
  expect(models).not.toHaveBeenCalled();
  await user.click(screen.getByRole("tab", {name: "模型"}));
  await user.click(await screen.findByRole("button", {name: /^编辑 /}));
  await user.type(screen.getByLabelText("API 密钥"), "unsaved-secret");
  expect(screen.getAllByRole("dialog")).toHaveLength(1);
  await user.click(screen.getByRole("tab", {name: "账号"}));
  await user.click(screen.getByRole("tab", {name: "模型"}));
  await user.click(await screen.findByRole("button", {name: /^编辑 /}));
  expect(screen.getByLabelText("API 密钥")).toHaveValue("");
  await user.click(screen.getByRole("button", {name: "关闭设置"}));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.getByRole("button", {name: "alice"})).toHaveFocus();
});

it("blocks section switching and closing while a model save is pending", async () => {
  let resolve!: (value: typeof directory) => void;
  vi.spyOn(api, "models").mockResolvedValue(directory);
  vi.spyOn(api, "saveProvider").mockImplementation(() => new Promise(done => {resolve = done;}));
  const user = userEvent.setup(); render(<SettingsDialog principal={member} disabled={false} onLogout={vi.fn()} />);
  await user.click(screen.getByRole("button", {name: "alice"}));
  await user.click(screen.getByRole("tab", {name: "模型"}));
  await user.click(await screen.findByRole("button", {name: /^编辑 /}));
  await user.click(screen.getByRole("button", {name: "保存更改"}));
  await waitFor(() => expect(screen.getByRole("button", {name: "关闭设置"})).toBeDisabled());
  expect(screen.getByRole("tab", {name: "账号"})).toBeDisabled();
  fireEvent(screen.getByRole("dialog"), new Event("cancel", {bubbles: true, cancelable: true}));
  expect(screen.getByRole("dialog")).toBeVisible();
  await act(async () => resolve(directory));
  expect(screen.getByRole("button", {name: "关闭设置"})).toBeEnabled();
});

it("exposes administrator inspection inside the same settings dialog", async () => {
  const users = vi.spyOn(api, "adminUsers").mockResolvedValue({users: []});
  vi.spyOn(api, "adminSessions").mockResolvedValue({sessions: []});
  const user = userEvent.setup(); render(<SettingsDialog principal={{...member, role: "admin"}} disabled={false} onLogout={vi.fn()} />);
  await user.click(screen.getByRole("button", {name: "alice"}));
  expect(users).not.toHaveBeenCalled();
  await user.click(screen.getByRole("tab", {name: "测试管理"}));
  expect(await screen.findByLabelText("筛选用户")).toBeVisible();
  expect(screen.getAllByRole("dialog")).toHaveLength(1);
});

it("changes password from the account panel and keeps logout disabled during other work", async () => {
  const changed = vi.spyOn(api, "changePassword").mockResolvedValue({authenticated: false});
  const signedOut = vi.fn(); const user = userEvent.setup();
  render(<SettingsDialog principal={member} disabled onLogout={vi.fn()} onSignedOut={signedOut} />);
  await user.click(screen.getByRole("button", {name: "alice"}));
  expect(screen.getByRole("button", {name: "退出登录"})).toBeDisabled();
  await user.click(screen.getByRole("button", {name: "修改密码"}));
  await user.type(screen.getByLabelText("原密码"), "old-password");
  await user.type(screen.getByLabelText("新密码"), "new-password-123");
  await user.click(screen.getByRole("button", {name: "修改并重新登录"}));
  await waitFor(() => expect(signedOut).toHaveBeenCalledOnce());
  expect(changed).toHaveBeenCalledWith("old-password", "new-password-123");
});

it("allows leaving administrator settings while a read is stalled", async () => {
  let resolve!: (value: {users: []}) => void;
  vi.spyOn(api, "adminUsers").mockImplementation(() => new Promise(done => {resolve = done;}));
  vi.spyOn(api, "adminSessions").mockResolvedValue({sessions: []});
  const user = userEvent.setup(); render(<SettingsDialog principal={{...member, role: "admin"}} disabled={false} onLogout={vi.fn()} />);
  await user.click(screen.getByRole("button", {name: "alice"}));
  await user.click(screen.getByRole("tab", {name: "测试管理"}));
  expect(await screen.findByText("正在读取…")).toBeVisible();
  await user.click(screen.getByRole("button", {name: "关闭设置"}));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  await act(async () => resolve({users: []}));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("allows closing a stalled model directory read without restoring its late response", async () => {
  let resolve!: (value: typeof directory) => void;
  vi.spyOn(api, "models").mockImplementation(() => new Promise(done => {resolve = done;}));
  const user = userEvent.setup(); render(<SettingsDialog principal={member} disabled={false} onLogout={vi.fn()} />);
  await user.click(screen.getByRole("button", {name: "alice"}));
  await user.click(screen.getByRole("tab", {name: "模型"}));
  expect(await screen.findByText("正在读取…")).toBeVisible();
  await user.click(screen.getByRole("button", {name: "关闭设置"}));
  await act(async () => resolve(directory));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
