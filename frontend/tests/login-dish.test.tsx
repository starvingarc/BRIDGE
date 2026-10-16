import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthRoot } from "../src/AuthRoot";
import { CellLogo } from "../src/components/CellLogo";
import { applyTheme, currentTheme, storedTheme, toggleTheme } from "../src/theme";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const config = { mode: "accounts", notice: "管理员可以查看测试会话。", notice_version: "v1", username_pattern: "[a-zA-Z0-9][a-zA-Z0-9_.-]{2,31}", password_min: 12, password_max: 128 };

afterEach(() => { applyTheme(null); localStorage.clear(); });

describe("BRIDGE cell logo", () => {
  it("opens a menu of its items, moves through them by keyboard and closes on Escape", async () => {
    const chosen: string[] = [];
    render(<CellLogo items={[{ id: "a", label: "关于 BRIDGE", onSelect: () => chosen.push("a") }, { id: "b", label: "深色 / 浅色", onSelect: () => chosen.push("b") }]} />);
    const logo = screen.getByRole("button", { name: "BRIDGE 菜单" });
    expect(logo).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(logo);
    expect(logo).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("menuitem", { name: "关于 BRIDGE" })).toHaveFocus();
    fireEvent.keyDown(window, { key: "ArrowDown" });
    expect(screen.getByRole("menuitem", { name: "深色 / 浅色" })).toHaveFocus();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(logo).toHaveAttribute("aria-expanded", "false");
    expect(logo).toHaveFocus();
    await userEvent.click(logo);
    await userEvent.click(screen.getByRole("menuitem", { name: "深色 / 浅色" }));
    expect(chosen).toEqual(["b"]);
    expect(logo).toHaveAttribute("aria-expanded", "false");
  });

  it("is a quiet decoration without items", () => {
    const { container } = render(<CellLogo size={30} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(container.querySelector(".cell-logo")).toHaveAttribute("aria-hidden", "true");
  });
});

describe("theme", () => {
  it("remembers a hand-picked theme and otherwise follows the system", () => {
    expect(storedTheme()).toBeNull();
    expect(currentTheme()).toBe("light"); // the test environment reports no dark preference
    toggleTheme();
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(storedTheme()).toBe("dark");
    toggleTheme();
    expect(currentTheme()).toBe("light");
    applyTheme(null);
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });
});

describe("sign-in page", () => {
  it("keeps the form in a centred card and moves the terms of use into the BRIDGE menu", async () => {
    vi.stubGlobal("fetch", vi.fn(async (path: string) => path === "/api/auth/config" ? json(config) : path === "/api/me" ? json({}, 401) : json({})));
    render(<AuthRoot />);
    const card = await screen.findByRole("region", { name: "登录研究空间" });
    expect(within(card).getByLabelText("用户名")).toBeInTheDocument();
    expect(within(card).queryByText("使用须知")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "BRIDGE 菜单" }));
    expect(screen.queryByRole("menuitem", { name: /安静模式/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("menuitem", { name: "使用须知" }));
    const dialog = screen.getByRole("dialog", { name: "使用须知" });
    expect(within(dialog).getByText("管理员可以查看测试会话。")).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "关闭" }));
    expect(dialog).not.toHaveAttribute("open");
    await userEvent.click(screen.getByRole("button", { name: "BRIDGE 菜单" }));
    await userEvent.click(screen.getByRole("menuitem", { name: "深色 / 浅色" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});

it("closes when the nucleus inside the logo is clicked again, and returns focus after selection", async () => {
  const { container } = render(<CellLogo items={[{ id: "theme", label: "主题", onSelect: () => {} }]} />);
  const logo = screen.getByRole("button", { name: "BRIDGE 菜单" });
  await userEvent.click(logo);
  await userEvent.click(container.querySelector(".cell-logo-nucleus")!);
  expect(logo).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  fireEvent.keyDown(logo, { key: "ArrowDown" });
  expect(screen.getByRole("menuitem")).toHaveFocus();
  await userEvent.click(screen.getByRole("menuitem"));
  expect(logo).toHaveFocus();
});

it("lets Tab leave the menu instead of leaving a floating menu over the form", async () => {
  render(<CellLogo items={[{ id: "about", label: "关于", onSelect: () => {} }]} />);
  await userEvent.click(screen.getByRole("button", { name: "BRIDGE 菜单" }));
  await userEvent.tab();
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
});
