/** Light or dark chosen by hand from the BRIDGE menu; without a choice the system preference applies. */
export type Theme = "light" | "dark";
const KEY = "bridge.theme";

export function storedTheme(): Theme | null {
  try { const value = localStorage.getItem(KEY); return value === "light" || value === "dark" ? value : null; } catch { return null; }
}

export function applyTheme(theme: Theme | null) {
  const root = document.documentElement;
  if (theme) root.dataset.theme = theme; else delete root.dataset.theme;
  try { if (theme) localStorage.setItem(KEY, theme); else localStorage.removeItem(KEY); } catch { /* storage may be unavailable */ }
}

export function currentTheme(): Theme {
  const set = document.documentElement.dataset.theme;
  if (set === "light" || set === "dark") return set;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export const toggleTheme = () => applyTheme(currentTheme() === "dark" ? "light" : "dark");
