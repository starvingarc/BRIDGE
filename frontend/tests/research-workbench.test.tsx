import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ResearchWorkbench } from "../src/workbench/ResearchWorkbench";
import { adaptWorkbench, gestationLabel, runTitle } from "../src/workbench/adapt";
import type { AssessmentDTO, WorkbenchDTO } from "../src/workbench/objects";
import { api } from "../src/api";
import type { Research } from "../src/types";

const principal = { id: "u1", username: "wyx", role: "user" as const, must_change_password: false };
const research = { id: "r".repeat(32), name: "mDA 祖细胞优化", materials: [] } as unknown as Research;
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const version = {
  id: "v1", protocol_id: "p1", version: 2, status: "confirmed" as const, based_on_version_id: null, total_days: 28, confirmed_at: "2026-10-01T00:00:00Z", revision: 1,
  reagents: [
    { id: "chir", name: "CHIR99021", short: "CHIR", pathway: "wnt" as const, kind: "molecule" as const, dose_text: "1.5 μM", start_day: 3, end_day: 13, catalog_id: "chir99021" },
    { id: "shh", name: "SHH C25II", short: "SHH", pathway: "shh" as const, kind: "protein" as const, dose_text: "100 ng/mL", start_day: 1, end_day: 7, catalog_id: null },
  ],
};
const assessment: AssessmentDTO = {
  id: "a1", sample_id: "s1", status: "done", versions: { atlas: "atlas-v1", naming: "naming-v1", metrics: "chain-v1" },
  chain: [0.99, 0.92, 0.81, 0.48, null].map((value, level) => ({ level, name: "", numerator: null, denominator: null, value })),
  target_fraction: null, gestation: [{ cell_type: "RG_mFP", weeks: { "7": 0.6, "8": 0.3, "12": 0.02 }, outside_reference: 0.08 }],
  tree_position: { RG_mFP: 0.5, Nb_mBIP: 0.5 }, alerts: [], failure: null,
};
const live: WorkbenchDTO = {
  protocols: [
    { id: "p1", research_id: research.id, name: "Protocol A", origin: "lab", citation: null, latest_version_id: "v1", latest: version, versions: [version], revision: 1 },
    { id: "p2", research_id: research.id, name: "Protocol B", origin: "lab", citation: null, latest_version_id: "v2", latest: { ...version, id: "v2", protocol_id: "p2", status: "draft" }, versions: [], revision: 1 },
  ],
  runs: [{ id: "run1", research_id: research.id, name: "第 3 轮", protocol_version_id: "v1", cell_line: "H9", start_date: "2026-09-26", state: "differentiating",
    graft: null, day: 16, stage_index: 3, today: [{ kind: "feed", label: "取样后换液" }], revision: 1 }],
  samples: [{ id: "s1", run_id: "run1", day: 16, collected_on: null, assay: "scRNA-seq", material_id: null, session_id: null, assessment_id: "a1", revision: 1 }],
  assessments: [assessment],
  leads: [{ id: "l1", run_id: "run1", sample_id: "s1", chain_level: 3, summary: "一半偏到了基板", status: "open", revision: 1 }],
  actions: [{ id: "act1", research_id: research.id, title: "SHH 靶基因梯度分析", context: { run_id: "run1", sample_id: "s1" }, tier: "exploratory", estimate: "约 3 分钟", kind: "analysis", status: "pending", revision: 1 }],
};

describe("contract adaptation", () => {
  it("names runs by protocol, adding cell line and start date only when a version was run more than once", () => {
    const first = live.runs[0], second = { ...first, id: "run2", cell_line: "H1", start_date: "2026-10-02" };
    expect(runTitle("Protocol A", 1, first, [first])).toBe("Protocol A");
    expect(runTitle("Protocol A", 2, first, [first])).toBe("Protocol A v2");
    expect(runTitle("Protocol A", 1, second, [first, second])).toBe("Protocol A · H1 · 10-02");
    expect(runTitle("Protocol A", 1, { ...second, cell_line: null, start_date: null }, [first, second])).toBe("Protocol A · 第 2 批");
    expect(runTitle("Boost", 2, first, [first], "Boost+")).toBe("Boost+");
    expect(runTitle("Boost", 2, first, [first], "  ")).toBe("Boost v2");
  });

  it("turns runs into cards, keeps unrun protocols in the library and preserves missing chain levels", () => {
    const { protocols, queue } = adaptWorkbench(live);
    expect(protocols.map(p => p.name)).toEqual(["Protocol A v2", "Protocol B v2"]);
    const run = protocols[0];
    expect(run).toMatchObject({ day: 16, state: "differentiating", today: "取样后换液", lead: "一半偏到了基板" });
    expect(run.samples[0].chain).toEqual([0.99, 0.92, 0.81, 0.48, null]);
    expect(run.reagents[0]).toMatchObject({ dose: "1.5 μM", start: 3, end: 13, catalogId: "chir99021" });
    expect(protocols[1]).toMatchObject({ state: "draft", today: "核对方案" });
    expect(queue).toEqual([{ id: "act1", title: "SHH 靶基因梯度分析", tier: "exploratory", eta: "约 3 分钟", context: "Protocol A v2 · D16" }]);
  });

  it("summarises gestational weeks and cells outside the reference", () => {
    expect(gestationLabel(assessment)).toBe("≈ GW7–8");
    expect(gestationLabel({ ...assessment, gestation: [{ cell_type: "RG_mFP", weeks: { "7": 0.5 }, outside_reference: 0.5 }] })).toBe("≈ GW7 · 早于参考");
  });
});

describe("research workbench", () => {
  it("falls back to labelled examples only when the workbench route is missing", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "Not Found" }, 404)));
    render(<ResearchWorkbench principal={principal} research={research} onSessions={() => undefined} onHome={() => undefined} />);
    expect(await screen.findByText(/方案与样本尚未接入，以下为示例/)).toBeInTheDocument();
  });

  it("reports other failures instead of showing examples", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "research_not_found" }, 404)));
    render(<ResearchWorkbench principal={principal} research={research} onSessions={() => undefined} onHome={() => undefined} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("research_not_found");
    expect(screen.queryByText(/以下为示例/)).toBeNull();
  });

  it("renders live runs and confirms queued actions on the server", async () => {
    const calls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input); calls.push(`${init?.method ?? "GET"} ${url}`);
      if (url.endsWith("/workbench")) return json(live);
      if (url.includes("/actions/")) return json({ ...live.actions[0], status: "approved" });
      return json({ detail: "Not Found" }, 404);
    }));
    render(<ResearchWorkbench principal={principal} research={research} onSessions={() => undefined} onHome={() => undefined} />);
    expect(await screen.findByRole("button", { name: /^打开Protocol A v2，D16 · Stage III/ })).toBeInTheDocument();
    expect(screen.queryByText(/以下为示例/)).toBeNull();
    const queue = screen.getByText("SHH 靶基因梯度分析").closest("li")!;
    fireEvent.click(within(queue).getByRole("button", { name: "运行" }));
    await waitFor(() => expect(calls).toContain(`POST /api/researches/${research.id}/actions/act1/approve`));
  });

  it("guides an empty research to upload a protocol", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) =>
      String(input).endsWith("/workbench") ? json({ protocols: [], runs: [], samples: [], assessments: [], leads: [], actions: [] }) : json({ detail: "Not Found" }, 404)));
    render(<ResearchWorkbench principal={principal} research={research} onSessions={() => undefined} onHome={() => undefined} />);
    expect(await screen.findByRole("heading", { name: "从一份方案开始" })).toBeInTheDocument();
    expect(screen.getByText("今天没有待办")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "新建方案" }));
    expect(screen.getByRole("heading", { name: "新的分化方案" })).toBeVisible();
  });

  it("keeps research and round questions in their bound conversation without leaving the workbench", async () => {
    const calls: string[] = [];
    const questions: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input); calls.push(`${init?.method ?? "GET"} ${url}`);
      if (url.endsWith("/workbench")) return json(live);
      if (url.endsWith("/conversation")) return json({ id: url.includes("/runs/") ? "round-chat" : "research-chat", status: "idle", messages: [], error: null });
      if (url.endsWith("/messages")) {
        const text = JSON.parse(String(init?.body)).text; questions.push(text);
        return json({ id: url.includes("round-chat") ? "round-chat" : "research-chat", status: "idle", messages: [{ id: "answer", role: "assistant", content: "Actual registered context answer", source: "model" }], error: null });
      }
      return json({ detail: "Not Found" }, 404);
    }));
    const onSessions = vi.fn();
    render(<ResearchWorkbench principal={principal} research={research} onSessions={onSessions} onHome={() => undefined} />);
    fireEvent.change(await screen.findByRole("textbox", { name: "问 BRIDGE" }), { target: { value: "Compare my rounds" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("Actual registered context answer")).toBeVisible();
    expect(calls).toContain("POST /api/sessions/research-chat/messages");
    fireEvent.click(screen.getByRole("button", { name: "收起" }));
    fireEvent.click(screen.getByRole("button", { name: /^打开Protocol A v2，/ }));
    await waitFor(() => expect(calls).toContain(`GET /api/researches/${research.id}/runs/run1/conversation`));
    fireEvent.change(screen.getByRole("textbox", { name: "问 BRIDGE" }), { target: { value: "Which version belongs to this round?" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    await waitFor(() => expect(calls).toContain("POST /api/sessions/round-chat/messages"));
    expect(onSessions).not.toHaveBeenCalled();
    expect(calls).not.toContain("POST /api/sessions");
    expect(questions).toEqual(["Compare my rounds", "Which version belongs to this round?"]);
  });

  it("returns to conversations and all researches from the rail", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "Not Found" }, 404)));
    const onSessions = vi.fn(), onHome = vi.fn();
    render(<ResearchWorkbench principal={principal} research={research} onSessions={onSessions} onHome={onHome} />);
    fireEvent.click(await screen.findByRole("button", { name: "会话" }));
    fireEvent.click(screen.getByRole("button", { name: "所有研究" }));
    expect(onSessions).toHaveBeenCalledWith();
    expect(onHome).toHaveBeenCalled();
  });
});
