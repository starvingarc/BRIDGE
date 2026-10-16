/** Read-only access to the reviewed small-molecule reference library shipped in examples/protocol-visualization. */
import data from "../../../examples/protocol-visualization/molecules/data/catalog.json";
import type { Pathway } from "./types";

export type Evidence = { source_id: string; reported_concentration: string; reported_window: string; locator: string; flag: string };
export type Compound = { id: string; name: string; category: string; mechanism: string; aliases: string[]; evidence: Evidence[] };
export type Reference = { id: string; title: string; url?: string | null; model?: string };

export const compounds = (data as { compounds: Compound[] }).compounds;
const references = new Map((data as { references: Reference[] }).references.map(r => [r.id, r]));
const structures = import.meta.glob("../../../examples/protocol-visualization/molecules/assets/compact/*.svg", { query: "?url", import: "default" }) as Record<string, () => Promise<string>>;

export const catalogVersion = (data as { version: string }).version;
export const compound = (id?: string) => (id ? compounds.find(c => c.id === id) : undefined);
export const reference = (id: string) => references.get(id);

const PATHWAY_HINTS: [Pathway, RegExp][] = [
  ["wnt", /WNT|GSK-?3/i], ["shh", /SHH|hedgehog|SMO/i], ["notch", /Notch|γ-?secretase|gamma-secretase/i], ["fgf", /FGF/i],
  ["maturation", /BDNF|GDNF|cAMP|ascorb|neurotroph|成熟|存活/i], ["smad", /SMAD|BMP|TGF|ALK|Nodal|Activin/i],
];
/** Editor default for a catalogue compound's pathway, read from its mechanism; the researcher still confirms it. */
export const suggestPathway = (c?: Compound): Pathway | undefined =>
  c ? PATHWAY_HINTS.find(([, pattern]) => pattern.test(`${c.mechanism} ${c.category}`))?.[0] : undefined;

/** Exact, case-insensitive match on name or alias; no fuzzy guessing. */
export function matchCompound(name: string): Compound | undefined {
  const key = name.trim().toLowerCase();
  if (!key) return undefined;
  return compounds.find(c => c.name.toLowerCase() === key || c.aliases.some(a => a.toLowerCase() === key));
}
/** Resolves the structure drawing lazily; undefined when the library has no drawing or it cannot be served. */
export async function structureUrl(id?: string): Promise<string | undefined> {
  const load = id ? Object.entries(structures).find(([path]) => path.endsWith(`/${id}.svg`))?.[1] : undefined;
  try { return load ? await load() : undefined; } catch { return undefined; }
}
