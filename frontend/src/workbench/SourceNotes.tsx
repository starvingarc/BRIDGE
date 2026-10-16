import type { Reagent } from "./types";

const FIELDS: Record<string, string> = { dose_text: "剂量", start_day: "开始天", end_day: "结束天" };
/** The source's own timing words and the values taken from a cited protocol, so unknown or relative times stay visible. */
export function SourceNotes({ reagent }: { reagent: Reagent }) {
  if (!reagent.timingText && !reagent.recipeRefs?.length) return null;
  return <p className="wb-muted wb-source-notes">
    {reagent.timingText && <span>原文时间：{reagent.timingText}</span>}
    {reagent.recipeRefs?.map(ref => <span key={ref.field}>{FIELDS[ref.field] ?? ref.field}引自所引配方：{ref.locator}</span>)}
  </p>;
}
