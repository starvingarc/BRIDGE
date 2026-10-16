/** Effort level names; kept in the providers' own English terms (an English edition will follow). */
import type { Effort } from "./api";

export const EFFORT_NAMES: Record<Effort, string> = {
  none: "None", minimal: "Minimal", low: "Low", medium: "Medium", high: "High", xhigh: "Extra high", max: "Max",
};
