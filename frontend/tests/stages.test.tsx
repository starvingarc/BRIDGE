import { render, screen } from "@testing-library/react";
import { adaptWorkbench } from "../src/workbench/adapt";
import type { ProtocolVersionDTO, RunDTO, WorkbenchDTO } from "../src/workbench/objects";
import { ProtocolFlow } from "../src/workbench/ProtocolFlow";
import { stageIndex, stageOf, stageSpans } from "../src/workbench/stages";

const hex = (c: string) => c.repeat(32);
const custom = [{ index: 1, start_day: 0, end_day: 2 }, { index: 2, start_day: 3, end_day: 9 }, { index: 3, start_day: 10, end_day: 20 }, { index: 4, start_day: 21, end_day: 35 }];
const version: ProtocolVersionDTO = {
  id: hex("1"), protocol_id: hex("p"), version: 1, status: "confirmed", based_on_version_id: null, total_days: 35, confirmed_at: "2026-10-01T00:00:00Z", revision: 2,
  stages: custom, reagents: [{ id: hex("a"), name: "CHIR99021", short: "CHIR", pathway: "wnt", kind: "molecule", dose_text: "1.5 μM", start_day: 3, end_day: 9, catalog_id: "chir99021", unconfirmed: [] }],
};
const run: RunDTO = { id: hex("r"), research_id: hex("e"), name: "第 1 轮", protocol_version_id: version.id, cell_line: "H9", start_date: "2026-09-26",
  state: "differentiating", graft: null, day: 16, stage_index: 3, today: [], revision: 5 };
const dto = (patch: Partial<RunDTO> = {}): WorkbenchDTO => ({
  protocols: [{ id: hex("p"), research_id: hex("e"), name: "Protocol A", origin: "lab", citation: null, latest_version_id: version.id, latest: version, versions: [version], revision: 3 }],
  runs: [{ ...run, ...patch }], samples: [], assessments: [], leads: [], actions: [],
});

describe("protocol-specific stages", () => {
  it("places days in custom windows, keeping gaps and overruns in the last stage reached", () => {
    const windows = [{ index: 1 as const, start: 0, end: 2 }, { index: 2 as const, start: 5, end: 9 }];
    expect([-1, 0, 2, 3, 5, 9, 40].map(day => stageIndex(day, windows))).toEqual([0, 1, 1, 1, 2, 2, 2]);
    expect([0, 4, 5, 10, 11, 16, 17].map(day => stageIndex(day))).toEqual([1, 1, 2, 2, 3, 3, 4]);
  });

  it("builds flow spans from custom windows and lets the last stage run to the end", () => {
    expect(stageSpans(undefined, 3)).toEqual([[-3, 0], [0, 5], [5, 11], [11, 17], [17, Infinity]]);
    expect(stageSpans([{ index: 2, start: 3, end: 9 }], 3)).toEqual([[-3, 0], [0, 5], [3, 10], [11, 17], [17, Infinity]]);
  });

  it("shows the server's stage for a running culture and computes from custom windows otherwise", () => {
    const card = adaptWorkbench(dto({ day: 16, stage_index: 3 })).protocols.find(p => p.run)!;
    expect(card.stages).toEqual([{ index: 1, start: 0, end: 2 }, { index: 2, start: 3, end: 9 }, { index: 3, start: 10, end: 20 }, { index: 4, start: 21, end: 35 }]);
    expect(stageOf(card).tag).toBe("D16 · Stage III");
    // Default windows would put D10 in Stage II; this protocol's windows put it in Stage III.
    const missing = adaptWorkbench(dto({ day: 10, stage_index: null })).protocols.find(p => p.run)!;
    expect(stageOf(missing).tag).toBe("D10 · Stage III");
    const server = adaptWorkbench(dto({ day: 10, stage_index: 2 })).protocols.find(p => p.run)!;
    expect(stageOf(server).tag).toBe("D10 · Stage II");
  });

  it("labels the protocol flow with this protocol's windows", () => {
    const card = adaptWorkbench(dto()).protocols.find(p => p.run)!;
    render(<ProtocolFlow protocol={card} others={[]} onOpenVersion={() => undefined} onDraft={() => undefined} />);
    expect(screen.getByRole("button", { name: /^Stage II 底板诱导，D3–D9/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Stage III 底板祖细胞，D10–D20，当前阶段/ })).toBeInTheDocument();
  });
});
