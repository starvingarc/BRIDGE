import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ModelSettings } from "../src/components/ModelSettings";
import { api, type ModelDirectory, type ModelProvider } from "../src/api";

const shared: ModelProvider = {id: "default", name: "Shared DeepSeek", models: ["shared-model"], base_url: "https://api.deepseek.com", has_api_key: true, configured: true, editable: false, shared: true, action_protocol: "deepseek_tools"};
const personal: ModelProvider = {...shared, id: "personal", name: "My gateway", models: ["first", "second"], editable: true, shared: false};
const directory: ModelDirectory = {providers: [shared, personal], selected: {provider_id: "default", model: "shared-model"}};
async function open(value = directory) {
  vi.spyOn(api, "models").mockResolvedValue(value);
  const user = userEvent.setup();
  render(<ModelSettings />);
  await screen.findByText("My gateway");
  return user;
}
const card = (name: string) => screen.getByText(name, {selector: ".models-name"}).closest("li") as HTMLElement;


it("lists each provider with its key state and models with declared effort, without choosing a model", async () => {
  const select = vi.spyOn(api, "selectProviderModel");
  const refresh = vi.spyOn(api, "refreshCapabilities").mockResolvedValue({ok: true, checked_at: "2026-10-13T08:00:00Z", message: "",
    capabilities: {second: {status: "supported", supported_levels: ["low", "high", "max"], default_level: "high"}}});
  const user = await open();
  expect(within(card("Shared DeepSeek")).getByText("共享")).toBeInTheDocument();
  expect(within(card("Shared DeepSeek")).getByRole("img", {name: "API 密钥已配置"})).toBeInTheDocument();
  expect(within(card("Shared DeepSeek")).queryByRole("button", {name: /^编辑/})).not.toBeInTheDocument();
  expect(within(card("Shared DeepSeek")).queryByRole("button", {name: /^删除/})).not.toBeInTheDocument();
  expect(screen.queryByRole("button", {name: "second"})).not.toBeInTheDocument();
  const models = screen.getByRole("list", {name: "My gateway 的模型"});
  expect(within(models).getByText("second").nextSibling).toHaveTextContent("Effort unconfirmed");
  await user.click(within(card("My gateway")).getByRole("button", {name: "刷新能力"}));
  await waitFor(() => expect(refresh).toHaveBeenCalledOnce());
  expect(await within(models).findByText("Low · High · Max (default High)")).toBeInTheDocument();
  expect(within(card("My gateway")).getByRole("status")).toHaveTextContent("已读取能力");
  expect(select).not.toHaveBeenCalled();
});

it("says a failed capability read failed and keeps the earlier check time", async () => {
  vi.spyOn(api, "refreshCapabilities").mockResolvedValue({ok: false, checked_at: "2026-10-12T08:00:00Z", message: "服务没有返回模型列表", capabilities: {}});
  const user = await open();
  await user.click(within(card("My gateway")).getByRole("button", {name: "刷新能力"}));
  expect(await within(card("My gateway")).findByRole("status")).toHaveTextContent(/读取能力失败：服务没有返回模型列表；仍显示 .+ 的结果/);
});

it("shows a missing key and marks the unsupported effort control", async () => {
  await open({...directory, providers: [shared, {...personal, has_api_key: false, configured: false,
    capabilities: {first: {status: "unsupported", supported_levels: [], default_level: null}}}]});
  expect(within(card("My gateway")).getByRole("img", {name: "API 密钥缺失"})).toBeInTheDocument();
  expect(within(card("My gateway")).getByRole("button", {name: "刷新能力"})).toBeDisabled();
  expect(within(screen.getByRole("list", {name: "My gateway 的模型"})).getByText("first").nextSibling).toHaveTextContent("No effort control");
});

it("adds a custom model API: fetched models, a connection test, then create; no key kept in the browser", async () => {
  const catalog = vi.spyOn(api, "providerCatalog").mockResolvedValue({ok: true, models: ["remote-one", "remote-two"], message: ""});
  const save = vi.spyOn(api, "saveProvider").mockResolvedValue({...directory, providers: [...directory.providers, {...personal, id: "custom", name: "Custom Gateway"}]});
  const test = vi.spyOn(api, "testProvider").mockResolvedValue({ok: true, message: "连接成功。"});
  const user = await open();
  await user.click(screen.getByRole("button", {name: "添加模型提供商"}));
  await user.click(screen.getByRole("tab", {name: "自定义模型 API"}));
  await user.type(screen.getByLabelText("提供商 ID"), "custom");
  await user.type(screen.getByLabelText("显示名称"), "Custom Gateway");
  await user.type(screen.getByLabelText("API 地址"), "https://custom.invalid/v1");
  await user.type(screen.getByLabelText("API 密钥"), "synthetic-secret");
  await user.click(screen.getByRole("button", {name: "获取可用模型"}));
  await user.click(await screen.findByRole("checkbox", {name: "remote-two"}));
  await user.click(screen.getByRole("button", {name: "添加所选模型"}));
  expect(screen.getByLabelText("模型 ID 1")).toHaveValue("remote-two");
  await user.click(screen.getByRole("button", {name: "测试连接"}));
  expect(await screen.findByText("连接成功。")).toBeInTheDocument();
  expect(save).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", {name: "创建提供商"}));
  await waitFor(() => expect(save).toHaveBeenCalledWith({id: "custom", name: "Custom Gateway", base_url: "https://custom.invalid/v1", api_key: "synthetic-secret", models: ["remote-two"], action_protocol: "json"}));
  expect(catalog).toHaveBeenCalledOnce(); expect(test).toHaveBeenCalledOnce();
  expect(await screen.findByRole("status")).toHaveTextContent("已保存 Custom Gateway (custom)。");
  expect(screen.queryByLabelText("API 密钥")).not.toBeInTheDocument();
  expect(JSON.stringify(localStorage)).not.toContain("synthetic-secret");
  expect(JSON.stringify(sessionStorage)).not.toContain("synthetic-secret");
});

it("adds a catalogue provider with only its key and models", async () => {
  const save = vi.spyOn(api, "saveProvider").mockResolvedValue(directory);
  const user = await open();
  await user.click(screen.getByRole("button", {name: "添加模型提供商"}));
  expect(screen.getByRole("tab", {name: "第三方模型提供商"})).toHaveAttribute("aria-selected", "true");
  expect(screen.getByLabelText("提供商")).toHaveValue("deepseek");
  expect(screen.queryByLabelText("API 地址")).not.toBeInTheDocument();
  await user.type(screen.getByLabelText("API 密钥"), "synthetic-secret");
  await user.click(screen.getByRole("button", {name: "添加模型"}));
  await user.type(screen.getByLabelText("模型 ID 1"), "deepseek-chat");
  await user.click(screen.getByRole("button", {name: "创建提供商"}));
  await waitFor(() => expect(save).toHaveBeenCalledWith({id: "deepseek", name: "DeepSeek", base_url: "https://api.deepseek.com", api_key: "synthetic-secret", models: ["deepseek-chat"], action_protocol: "deepseek_tools"}));
});

it("keeps saved keys only at unchanged endpoints and opens one editor at a time", async () => {
  const user = await open({...directory, providers: [{...shared, editable: true}, personal]});
  await user.click(screen.getByRole("button", {name: "编辑 My gateway (personal)"}));
  expect(screen.getByLabelText("API 密钥")).toHaveAttribute("placeholder", "已保存；留空保留原密钥");
  await user.type(screen.getByLabelText("API 密钥"), "temporary-secret");
  await user.clear(screen.getByLabelText("API 地址"));
  await user.type(screen.getByLabelText("API 地址"), "https://different.invalid");
  expect(screen.getByLabelText("API 密钥")).toHaveValue("");
  expect(screen.getByRole("button", {name: "保存更改"})).toBeDisabled();
  await user.click(screen.getByRole("button", {name: "编辑 Shared DeepSeek (default)"}));
  expect(screen.getAllByLabelText("API 地址")).toHaveLength(1);
  expect(screen.getByLabelText("API 地址")).toHaveValue(shared.base_url);
  await user.click(screen.getByRole("button", {name: "编辑 My gateway (personal)"}));
  expect(screen.getByLabelText("API 地址")).toHaveValue(personal.base_url);
  expect(screen.getByLabelText("API 密钥")).toHaveValue("");
});

it("rejects duplicate model IDs and pasted environment assignments", async () => {
  const user = await open();
  await user.click(screen.getByRole("button", {name: "编辑 My gateway (personal)"}));
  await user.clear(screen.getByLabelText("模型 ID 2"));
  await user.type(screen.getByLabelText("模型 ID 2"), "first");
  expect(screen.getByRole("button", {name: "保存更改"})).toBeDisabled();
  await user.click(screen.getByRole("button", {name: "移除模型 2"}));
  await user.type(screen.getByLabelText("API 密钥"), "API_KEY=private");
  expect(screen.getByText(/请仅粘贴密钥本身/)).toBeInTheDocument();
  expect(screen.getByRole("button", {name: "保存更改"})).toBeDisabled();
});

it("lets an administrator save the shared provider keeping its key", async () => {
  const save = vi.spyOn(api, "saveProvider").mockResolvedValue(directory);
  const user = await open({...directory, providers: [{...shared, editable: true}, personal]});
  await user.click(screen.getByRole("button", {name: "编辑 Shared DeepSeek (default)"}));
  await user.click(screen.getByRole("button", {name: "保存更改"}));
  await waitFor(() => expect(save).toHaveBeenCalledWith(expect.objectContaining({id: "default", api_key: ""})));
});

it("asks before deleting a provider", async () => {
  const remove = vi.spyOn(api, "deleteProvider").mockResolvedValue({...directory, providers: [shared]});
  const user = await open();
  await user.click(screen.getByRole("button", {name: "删除 My gateway (personal)"}));
  const confirm = screen.getByRole("alertdialog", {name: "删除 My gateway (personal)？"});
  await user.click(within(confirm).getByRole("button", {name: "取消"}));
  expect(remove).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", {name: "删除 My gateway (personal)"}));
  await user.click(within(screen.getByRole("alertdialog")).getByRole("button", {name: "删除 My gateway (personal)"}));
  await waitFor(() => expect(remove).toHaveBeenCalledWith("personal"));
  await waitFor(() => expect(screen.queryByText("My gateway")).not.toBeInTheDocument());
});

it("recovers a directory read failure without offering stale edits", async () => {
  vi.spyOn(api, "models").mockRejectedValueOnce(new Error("Unable to read models")).mockResolvedValue(directory);
  const user = userEvent.setup(); render(<ModelSettings />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Unable to read models");
  expect(screen.queryByRole("button", {name: /^编辑/})).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", {name: "重新读取配置"}));
  expect(await screen.findByText("My gateway")).toBeInTheDocument();
});
