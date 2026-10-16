import { displayRecord, fieldValue } from "../researcherLabels";

// Unmapped machine terms belong in diagnostics, never in the researcher interface.
export function ResearchValue({ value, field = "", empty = "未提供" }: {
  value: unknown; field?: string; empty?: string;
}) {
  if (value === null || value === undefined) return <>{empty}</>;
  if (typeof value !== "string") return <>{typeof value === "object" ? JSON.stringify(displayRecord(value, field)) : String(value)}</>;
  const display = fieldValue(value, field);
  const key = field.replace(/\[\d+\]/g, "").split(".").pop();
  const coded = ["metric_id", "metric_name", "unit", "score_unit", "relation", "direction"].includes(key ?? "");
  return display === value && coded && /^[a-z][a-z0-9_:-]*$/.test(value)
    ? <>名称待核对</>
    : <>{display}</>;
}
