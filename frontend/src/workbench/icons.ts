/** Category pictograms from examples/protocol-visualization, loaded lazily. */
const icons = import.meta.glob("../../../examples/protocol-visualization/assets/categories/*-icon.png", { query: "?url", import: "default" }) as Record<string, () => Promise<string>>;

export async function categoryIcon(kind: "molecule" | "protein" | "supplement"): Promise<string | undefined> {
  const load = Object.entries(icons).find(([path]) => path.endsWith(`/${kind}-icon.png`))?.[1];
  try { return load ? await load() : undefined; } catch { return undefined; }
}
