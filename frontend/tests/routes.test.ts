import { formatRoute, parseRoute, type Route } from "../src/routes";

const rid = "a".repeat(32);

describe("addresses", () => {
  it("round-trips every place the app can open", () => {
    const routes: Route[] = [
      { kind: "home" },
      { kind: "history", session: null },
      { kind: "history", session: "legacy" },
      { kind: "research", id: rid, at: { view: "wall", focus: null } },
      { kind: "research", id: rid, at: { view: "compare", focus: null } },
      { kind: "research", id: rid, at: { view: "plan", focus: "b".repeat(32), sample: "d".repeat(32) } },
      { kind: "research", id: rid, at: { view: "plan", focus: "b".repeat(32), sample: "d".repeat(32), analysis: "qc" } },
      { kind: "research", id: rid, at: { view: "plan", focus: `protocol-${"c".repeat(32)}` } },
      { kind: "sessions", id: rid, session: null },
      { kind: "sessions", id: rid, session: "first" },
      { kind: "sessions", id: rid, session: null, report: true },
      { kind: "sessions", id: rid, session: "first", report: true },
    ];
    for (const route of routes) expect(parseRoute(formatRoute(route))).toEqual(route);
  });

  it("reads short and unknown addresses as the nearest real place", () => {
    expect(parseRoute("")).toEqual({ kind: "home" });
    expect(parseRoute("#/r")).toEqual({ kind: "home" });
    expect(parseRoute("#/somewhere")).toEqual({ kind: "home" });
    expect(parseRoute(`#/r/${rid}/unknown`)).toEqual({ kind: "research", id: rid, at: { view: "wall", focus: null } });
    expect(parseRoute("#/history/%E0%A4%A")).toEqual({ kind: "history", session: null });
  });

  it("keeps the incubator address short and escapes ids", () => {
    expect(formatRoute({ kind: "research", id: rid, at: { view: "wall", focus: "ignored" } })).toBe(`#/r/${rid}`);
    expect(formatRoute({ kind: "research", id: rid, at: { view: "plan", focus: "新的/1" } })).toBe(`#/r/${rid}/flow/%E6%96%B0%E7%9A%84%2F1`);
    expect(formatRoute({ kind: "research", id: rid, at: { view: "compare", focus: "ignored" } })).toBe(`#/r/${rid}/compare`);
  });

  it("opens earlier tree addresses at the matching new place", () => {
    expect(parseRoute(`#/r/${rid}/tree`)).toEqual({ kind: "research", id: rid, at: { view: "compare", focus: null } });
    expect(parseRoute(`#/r/${rid}/tree/${"b".repeat(32)}`)).toEqual({ kind: "research", id: rid, at: { view: "plan", focus: "b".repeat(32) } });
    expect(parseRoute(`#/r/${rid}/results/${"b".repeat(32)}/${"d".repeat(32)}/qc`)).toEqual({ kind: "research", id: rid, at: { view: "plan", focus: "b".repeat(32), sample: "d".repeat(32), analysis: "qc" } });
    expect(parseRoute(`#/r/${rid}/flow/${"b".repeat(32)}/${"d".repeat(32)}/other`)).toEqual({ kind: "research", id: rid, at: { view: "plan", focus: "b".repeat(32), sample: "d".repeat(32) } });
    expect(parseRoute(`#/r/${rid}/results`)).toEqual({ kind: "research", id: rid, at: { view: "compare", focus: null } });
  });
});
