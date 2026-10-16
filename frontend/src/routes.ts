import { useCallback, useEffect, useState } from "react";

/** Where the workbench is looking: the incubator, the comparison of all runs, or one run or protocol on its protocol flow. */
export type WorkbenchView = "wall" | "compare" | "plan";
/** One analysis of a sample, in the sample panel beside a run's protocol flow. */
export type AnalysisTab = "mapping" | "qc" | "records";
/** On a run's flow, `sample` and `analysis` say which sampling point's panel is open and on which analysis. */
export type WorkbenchLocation = { view: WorkbenchView; focus: string | null; sample?: string; analysis?: AnalysisTab };
const TABS: AnalysisTab[] = ["mapping", "qc", "records"];

/**
 * Addresses live in the URL hash so a reload or a shared link reopens the same place
 * without the server having to serve the app for every path.
 */
export type Route =
  | { kind: "home" }
  | { kind: "history"; session: string | null }
  | { kind: "research"; id: string; at: WorkbenchLocation }
  | { kind: "sessions"; id: string; session: string | null; report?: true };

const HOME: Route = { kind: "home" };
const SEGMENT: Record<WorkbenchView, string> = { wall: "", compare: "compare", plan: "flow" };

export function parseRoute(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(part => {
    try { return decodeURIComponent(part); } catch { return ""; }
  });
  const [head, id, sub, extra, sample, analysis] = parts;
  if (head === "history") return { kind: "history", session: id || null };
  if (head !== "r" || !id) return HOME;
  if (!sub) return { kind: "research", id, at: { view: "wall", focus: null } };
  if (sub === "sessions" || sub === "reports") return { kind: "sessions", id, session: extra || null, ...(sub === "reports" ? {report: true as const} : {}) };
  if (sub === "compare") return { kind: "research", id, at: { view: "compare", focus: null } };
  if (sub === "flow" || sub === "results" || sub === "tree") {
    // Earlier addresses: a run's tree or results open its flow; the tree of all runs is the comparison.
    if (sub !== "flow" && !extra) return { kind: "research", id, at: { view: "compare", focus: null } };
    // Cell cycle used to be a tab of its own; it is now part of QC.
    const tab = TABS.find(t => t === (analysis === "cycle" ? "qc" : analysis));
    return { kind: "research", id, at: { view: "plan", focus: extra || null, ...(extra && sample ? { sample } : {}), ...(extra && sample && tab ? { analysis: tab } : {}) } };
  }
  return { kind: "research", id, at: { view: "wall", focus: null } };
}

export function formatRoute(route: Route): string {
  const path = (...parts: (string | null)[]) => "#/" + parts.filter((part): part is string => !!part).map(encodeURIComponent).join("/");
  switch (route.kind) {
    case "home": return "#/";
    case "history": return path("history", route.session);
    case "sessions": return path("r", route.id, route.report ? "reports" : "sessions", route.session);
    case "research": return route.at.view === "wall" ? path("r", route.id)
      : route.at.view === "compare" ? path("r", route.id, SEGMENT.compare)
      : path("r", route.id, SEGMENT.plan, route.at.focus, route.at.focus ? route.at.sample ?? null : null, route.at.focus && route.at.sample ? route.at.analysis ?? null : null);
  }
}

/** The current route plus a navigator; `replace` updates the address without adding a history entry. */
export function useHashRoute(): [Route, (next: Route, options?: { replace?: boolean }) => void] {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash));
  useEffect(() => {
    const sync = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);
  const navigate = useCallback((next: Route, options: { replace?: boolean } = {}) => {
    const hash = formatRoute(next);
    if (hash !== (window.location.hash || "#/")) {
      const url = window.location.pathname + window.location.search + hash;
      if (options.replace) window.history.replaceState(null, "", url); else window.history.pushState(null, "", url);
    }
    setRoute(parseRoute(hash));
  }, []);
  return [route, navigate];
}
