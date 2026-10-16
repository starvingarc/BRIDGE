import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { fireEvent } from "@testing-library/react";
import { ModelControls } from "../src/components/ModelPicker";
import { api, type ModelDirectory, type ModelSelectionView } from "../src/api";

const directory: ModelDirectory = {
  selected: { provider_id: "default", model: "flash" },
  providers: [
    { id: "default", name: "DeepSeek", base_url: "https://api.deepseek.com", models: ["flash", "pro"], action_protocol: "deepseek_tools",
      shared: true, editable: false, has_api_key: true, configured: true,
      capabilities: {
        flash: { status: "supported", supported_levels: ["low", "high", "max"], default_level: "high" },
        pro: { status: "supported", supported_levels: ["high", "max"], default_level: null },
      } },
    { id: "lab", name: "实验室网关", base_url: "https://lab.invalid/v1", models: ["qwen"], action_protocol: "json",
      shared: false, editable: true, has_api_key: false, configured: false },
  ],
};
const view = (patch: Partial<ModelSelectionView> = {}): ModelSelectionView => ({
  selection: { provider_id: "default", model: "flash", effort: "low" }, availability: { state: "ready", reason: null },
  capability: directory.providers[0].capabilities!.flash, task_configuration: null, ...patch,
});
const trigger = () => screen.getByRole("button", { name: /^模型：/ });
const chip = () => screen.getByRole("button", { name: /^Effort: / });
const slider = () => screen.getByRole("slider", { name: "Effort" });
const openEffort = async () => { fireEvent.click(await screen.findByRole("button", { name: /^Effort: / })); return screen.findByRole("slider", { name: "Effort" }); };
beforeEach(() => { vi.spyOn(api, "models").mockResolvedValue(directory); });

describe("model controls", () => {
  it("shows the model and an effort chip; the slider appears only when the chip is opened", async () => {
    vi.spyOn(api, "modelSelection").mockResolvedValue(view());
    render(<ModelControls sessionId="s1" current={{ provider_id: "default", model: "flash", effort: "low" }} />);
    expect(trigger()).toHaveAccessibleName("模型：flash");
    expect(await screen.findByRole("button", { name: "Effort: Low" })).toBeInTheDocument();
    expect(screen.queryByRole("slider")).not.toBeInTheDocument();
    const thumb = await openEffort();
    expect(thumb).toHaveAttribute("aria-valuetext", "Low");
    expect(thumb).toHaveAttribute("aria-valuemax", "2");
    expect(screen.getByText("Faster")).toBeInTheDocument();
    expect(screen.getByText("Smarter")).toBeInTheDocument();
    expect(screen.getByText("Default")).toBeInTheDocument();
  });

  it("lists models by service and keeps an unconfigured service unusable", async () => {
    vi.spyOn(api, "modelSelection").mockResolvedValue(view());
    const user = userEvent.setup();
    render(<ModelControls sessionId="s1" current={view().selection} />);
    await user.click(trigger());
    const list = await screen.findByRole("menu", { name: "模型" });
    expect(within(list).getByRole("menuitemradio", { name: "flash" })).toHaveAttribute("aria-checked", "true");
    expect(within(list).getByRole("menuitemradio", { name: "qwen" })).toBeDisabled();
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("switching model saves it with the declared default level and closes", async () => {
    vi.spyOn(api, "modelSelection").mockResolvedValue(view());
    const save = vi.spyOn(api, "saveModelSelection").mockImplementation(async (_sid, choice) => view({ selection: { ...choice, effort: "high" } }));
    const user = userEvent.setup();
    render(<ModelControls sessionId="s1" current={view().selection} />);
    await user.click(trigger());
    await user.click(await screen.findByRole("menuitemradio", { name: "pro" }));
    await waitFor(() => expect(save).toHaveBeenCalledWith("s1", { provider_id: "default", model: "pro", effort: null }));
    await waitFor(() => expect(screen.queryByRole("menu")).not.toBeInTheDocument());
    expect(trigger()).toHaveAccessibleName("模型：pro");
    expect(chip()).toHaveAccessibleName("Effort: High");
  });

  it("moves the effort with the keyboard and saves each step", async () => {
    vi.spyOn(api, "modelSelection").mockResolvedValue(view());
    const save = vi.spyOn(api, "saveModelSelection").mockImplementation(async (_sid, choice) => view({ selection: choice }));
    render(<ModelControls sessionId="s1" current={view().selection} />);
    fireEvent.keyDown(await openEffort(), { key: "ArrowRight" });
    await waitFor(() => expect(save).toHaveBeenCalledWith("s1", { provider_id: "default", model: "flash", effort: "high" }));
    await waitFor(() => expect(chip()).toHaveAccessibleName("Effort: High"));
    fireEvent.keyDown(slider(), { key: "End" });
    await waitFor(() => expect(save).toHaveBeenLastCalledWith("s1", { provider_id: "default", model: "flash", effort: "max" }));
  });

  it("shows the service default without a selected stop when the model declares none", async () => {
    vi.spyOn(api, "modelSelection").mockResolvedValue(view({ selection: { provider_id: "default", model: "pro", effort: null }, capability: directory.providers[0].capabilities!.pro }));
    render(<ModelControls sessionId="s1" current={{ provider_id: "default", model: "pro", effort: null }} />);
    expect(await screen.findByRole("button", { name: "Effort: Provider default" })).toBeInTheDocument();
    const thumb = await openEffort();
    expect(thumb).toHaveAttribute("aria-valuetext", "Provider default");
    expect(thumb.closest("[data-unset]")).not.toBeNull();
    expect(screen.queryByText("Default")).not.toBeInTheDocument();
  });

  it("has no slider while the levels are unconfirmed", async () => {
    const read = vi.spyOn(api, "modelSelection").mockResolvedValue(view({ capability: { status: "unknown", supported_levels: [], default_level: null }, selection: { provider_id: "default", model: "flash", effort: null } }));
    render(<ModelControls sessionId="s1" current={{ provider_id: "default", model: "flash", effort: null }} />);
    await waitFor(() => expect(read).toHaveBeenCalled());
    await new Promise(resolve => setTimeout(resolve, 0));
    expect(screen.queryByRole("button", { name: /^Effort: / })).not.toBeInTheDocument();
  });

  it("says when the chosen model is unavailable", async () => {
    vi.spyOn(api, "modelSelection").mockResolvedValue(view({ availability: { state: "unavailable", reason: "model_selection_unavailable" } }));
    render(<ModelControls sessionId="s1" current={view().selection} />);
    await waitFor(() => expect(trigger()).toHaveAccessibleName("模型：模型不可用"));
  });

  it("binds the conversation when a model is chosen before the first message", async () => {
    const ensure = vi.fn(async () => "new-session");
    vi.spyOn(api, "modelSelection").mockResolvedValue(view());
    const save = vi.spyOn(api, "saveModelSelection").mockResolvedValue(view({ selection: { provider_id: "default", model: "pro", effort: null } }));
    const user = userEvent.setup();
    render(<ModelControls sessionId={null} ensureSession={ensure} />);
    expect(screen.queryByRole("button", { name: /^Effort: / })).not.toBeInTheDocument();
    await user.click(trigger());
    await user.click(await screen.findByRole("menuitemradio", { name: "pro" }));
    await waitFor(() => expect(save).toHaveBeenCalledWith("new-session", expect.objectContaining({ model: "pro" })));
    expect(ensure).toHaveBeenCalledOnce();
  });

  it("announces a refused choice briefly", async () => {
    vi.spyOn(api, "modelSelection").mockResolvedValue(view());
    vi.spyOn(api, "saveModelSelection").mockRejectedValue(new Error("这个模型没有确认支持该 effort 档位，请刷新能力或换一个档位。"));
    render(<ModelControls sessionId="s1" current={view().selection} />);
    fireEvent.keyDown(await openEffort(), { key: "End" });
    expect(await screen.findByRole("alert")).toHaveTextContent("没有确认支持该 effort 档位");
    expect(chip()).toHaveAccessibleName("Effort: Low");
  });

  it("searches once there are five or more models", async () => {
    vi.spyOn(api, "models").mockResolvedValue({ ...directory, providers: [{ ...directory.providers[0], models: ["flash", "pro", "chat", "coder", "reasoner"] }] });
    vi.spyOn(api, "modelSelection").mockResolvedValue(view());
    const user = userEvent.setup();
    render(<ModelControls sessionId="s1" current={view().selection} />);
    await user.click(trigger());
    await user.type(await screen.findByRole("searchbox", { name: "搜索模型" }), "co");
    expect(within(screen.getByRole("menu", { name: "模型" })).getAllByRole("menuitemradio").map(i => i.textContent)).toEqual(["coder"]);
  });

  it("opens the model services in settings", async () => {
    vi.spyOn(api, "modelSelection").mockResolvedValue(view());
    const heard = vi.fn();
    window.addEventListener("bridge:open-settings", heard);
    const user = userEvent.setup();
    render(<ModelControls sessionId="s1" current={view().selection} />);
    await user.click(trigger());
    await user.click(await screen.findByRole("button", { name: "管理模型" }));
    expect((heard.mock.calls[0][0] as CustomEvent).detail).toEqual({ section: "models" });
    window.removeEventListener("bridge:open-settings", heard);
  });
});

describe("settings opened from the seat", () => {
  it("opens straight at the model services", async () => {
    const { SettingsDialog } = await import("../src/components/SettingsDialog");
    render(<SettingsDialog principal={{ id: "u1", username: "alice", role: "user", must_change_password: false }} disabled={false} onLogout={() => undefined} />);
    window.dispatchEvent(new CustomEvent("bridge:open-settings", { detail: { section: "models" } }));
    expect(await screen.findByRole("tab", { name: "模型" })).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByText("DeepSeek")).toBeInTheDocument();
  });
});
