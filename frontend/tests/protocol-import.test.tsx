import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ResearchWorkbench } from "../src/workbench/ResearchWorkbench";
import { adaptWorkbench, libraryId, sourceView } from "../src/workbench/adapt";
import type { FormalizationDTO, ProtocolDTO, ProtocolVersionDTO, WorkbenchDTO } from "../src/workbench/objects";
import type { Research } from "../src/types";

const principal = { id: "u1", username: "wyx", role: "user" as const, must_change_password: false };
const hex = (c: string) => c.repeat(32);
const research = { id: hex("e"), name: "mDA 祖细胞优化", materials: [] } as unknown as Research;
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const TEXT = "Stage 1, days 0 to 4: culture cells with CHIR99021 at 2 uM.\nFrom day 5 add SHH at 200 ng/mL.\nLDN193189 is used at 100 nM.\nTotal duration: 5 days.";
const version: ProtocolVersionDTO = {
  id: hex("1"), protocol_id: hex("p"), version: 1, status: "draft", based_on_version_id: null, total_days: 5, confirmed_at: null, revision: 2,
  unconfirmed: ["source_review", "total_days"], provenance: { material_id: hex("m"), formalization_version_id: hex("f") },
  operations: [{ day: null, kind: "passage", note: "Passage cells; reagent unspecified." }],
  reagents: [
    { id: hex("a"), name: "CHIR99021", short: "CHIR", pathway: "other", kind: "molecule", dose_text: "2 uM", start_day: 0, end_day: 4, catalog_id: "chir99021", unconfirmed: ["dose_text"] },
    { id: hex("b"), name: "SHH", short: "SHH", pathway: "shh", kind: "protein", dose_text: "200 ng/mL", start_day: 5, end_day: null, catalog_id: null, unconfirmed: ["end_day"] },
    { id: hex("c"), name: "LDN193189", short: "LDN", pathway: "smad", kind: "molecule", dose_text: "100 nM", start_day: null, end_day: null, catalog_id: null, unconfirmed: ["start_day", "end_day"] },
  ],
};
const protocol: ProtocolDTO = { id: hex("p"), research_id: research.id, name: "导入的方案", origin: "lab", citation: null, latest_version_id: version.id, latest: version, versions: [version], revision: 1 };
const base: WorkbenchDTO = { protocols: [protocol], runs: [], samples: [], assessments: [], leads: [], actions: [] };
const source = { id: "S1", kind: "protocol", label: "方案原文", location: "paragraph 1", text: TEXT };
const formalization: FormalizationDTO = {
  id: hex("f"), compiler_state: "passed", coverage_state: "needs_input", review_state: "unreviewed",
  steps: [{ id: "s1", label: "第1阶段", sources: [source] }],
  questions: [{ id: "q1", title: "第5天传代时使用的解离试剂未写明", answer_state: "unanswered", sources: [source] }],
  projection: {
    reagents: [{ name: "CHIR99021", quote: "culture cells with CHIR99021 at 2 uM" }, { name: "SHH", quote: "From day 5 add SHH at 200 ng/mL" }],
    total_days: { value: 5, quote: "Total duration: 5 days." }, stages: [{ quote: "Stage 1, days 0 to 4" }], operations: [],
  },
};

function routes(handlers: Record<string, (body: Record<string, unknown>) => Response | Promise<Response>>) {
  const calls: { key: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${String(input).replace(`/api/researches/${research.id}`, "")}`;
    const body = typeof init?.body === "string" ? JSON.parse(init.body) : {};
    calls.push({ key, body });
    return handlers[key]?.(body) ?? json({ detail: "Not Found" }, 404);
  }));
  return calls;
}
const FORMALIZATION = `GET /protocols/${hex("p")}/versions/${hex("1")}/formalization`;
const PATCH = `PATCH /protocols/${hex("p")}/versions/${hex("1")}`;
const open = (location = { view: "plan" as const, focus: libraryId(hex("p")) }) =>
  render(<ResearchWorkbench principal={principal} research={research} onSessions={() => undefined} onHome={() => undefined} location={location} />);

describe("imported protocol view model", () => {
  it("keeps unknown days, version review items and the source link", () => {
    const card = adaptWorkbench(base).protocols[0];
    expect(card.reagents.map(r => [r.short, r.start, r.end])).toEqual([["CHIR", 0, 4], ["SHH", 5, null], ["LDN", null, null]]);
    expect(card.source).toMatchObject({ review: ["source_review", "total_days"], hasSource: true });
    expect(card.operations).toEqual([{ day: null, kind: "passage", note: "Passage cells; reagent unspecified." }]);
    const view = sourceView(formalization);
    expect(view.segments).toHaveLength(1);
    expect(view.quotes.map(q => q.kind)).toEqual(["reagent", "reagent", "total", "stage"]);
    expect(view.questions).toEqual(["第5天传代时使用的解离试剂未写明"]);
  });
});

describe("source review", () => {
  it("draws open windows honestly and parks reagents without days", async () => {
    routes({ "GET /workbench": () => json(base), [FORMALIZATION]: () => json(formalization) });
    open();
    expect(await screen.findByRole("button", { name: "SHH 200 ng/mL，D5–D?，结束天未写明，待核对" })).toHaveClass("wb-cap--open-end");
    const tray = screen.getByRole("group", { name: "时间待定" });
    expect(within(tray).getByRole("button", { name: "LDN193189 100 nM，时间未写明" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^LDN193189 100 nM，D/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "确认并记录" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "确认并记录" })).toHaveAttribute("title", "还有 2 个试剂时间未定");
  });

  it("opens on the flow alone, shows the original text from a reagent, and links quotes to reagents both ways", async () => {
    const calls = routes({ "GET /workbench": () => json(base), [FORMALIZATION]: () => json(formalization) });
    open();
    fireEvent.click(await screen.findByRole("button", { name: /^CHIR99021/ }));
    expect(screen.queryByRole("complementary", { name: "方案原文" })).not.toBeInTheDocument();
    expect(calls.some(c => c.key === FORMALIZATION)).toBe(false);
    fireEvent.click(within(screen.getByRole("form", { name: "编辑 CHIR99021" })).getByRole("button", { name: "在原文中查看" }));
    const pane = await screen.findByRole("complementary", { name: "方案原文" });
    expect(await within(pane).findByText("第5天传代时使用的解离试剂未写明")).toBeInTheDocument();
    fireEvent.click(within(pane).getByRole("button", { name: "原文中的 CHIR99021：culture cells with CHIR99021 at 2 uM" }));
    expect(screen.getByRole("form", { name: "编辑 CHIR99021" })).toBeInTheDocument();
    expect(within(pane).getByRole("button", { name: /原文中的 CHIR99021/ })).toHaveAttribute("aria-current", "true");
    // A catalogue match fills the unset pathway as an editor default.
    expect(screen.getByLabelText("通路")).toHaveValue("wnt");
    fireEvent.click(within(pane).getByRole("button", { name: "收起" }));
    expect(screen.queryByRole("complementary", { name: "方案原文" })).not.toBeInTheDocument();
  });

  it("clears whole-version items one at a time, the source item only after the text has been shown", async () => {
    let gate!: (r: Response) => void;
    const calls = routes({
      "GET /workbench": () => json(base),
      [FORMALIZATION]: () => new Promise<Response>(resolve => { gate = resolve; }),
      [PATCH]: () => json({ ...version, unconfirmed: ["total_days"], revision: 3 }),
    });
    open();
    const checklist = await screen.findByRole("region", { name: "整份方案待核对" });
    expect(within(checklist).queryByRole("button", { name: "已核对：对照原文看过整份方案" })).not.toBeInTheDocument();
    fireEvent.click(within(checklist).getByRole("button", { name: "打开原文" }));
    expect(await screen.findByText("正在读取原文…")).toBeInTheDocument();
    gate(json(formalization));
    await waitFor(() => expect(within(checklist).getByRole("button", { name: "已核对：对照原文看过整份方案" })).toBeEnabled());
    fireEvent.click(within(checklist).getByRole("button", { name: "已核对：对照原文看过整份方案" }));
    await waitFor(() => expect(calls.some(c => c.key === PATCH)).toBe(true));
    expect(calls.find(c => c.key === PATCH)!.body).toEqual({ unconfirmed: ["total_days"], expected_version: 2 });
  });

  it("says when a version has no source record", async () => {
    routes({ "GET /workbench": () => json(base), [FORMALIZATION]: () => json({ detail: "protocol_formalization_not_found" }, 404) });
    open();
    fireEvent.click(within(await screen.findByRole("region", { name: "整份方案待核对" })).getByRole("button", { name: "打开原文" }));
    expect(await screen.findByText("这一版没有可读取的原文记录。")).toBeInTheDocument();
  });

  it("saves a reagent day left empty as unknown, not zero", async () => {
    const calls = routes({ "GET /workbench": () => json(base), [FORMALIZATION]: () => json(formalization), [PATCH]: () => json(version) });
    open();
    fireEvent.click(await screen.findByRole("button", { name: /^SHH 200 ng\/mL，D5–D\?/ }));
    const form = screen.getByRole("form", { name: "编辑 SHH" });
    expect(within(form).getByLabelText("结束")).toHaveValue(null);
    fireEvent.click(within(form).getByRole("button", { name: "保存" }));
    await waitFor(() => expect(calls.some(c => c.key === PATCH)).toBe(true));
    const saved = (calls.find(c => c.key === PATCH)!.body.reagents as { name: string; start_day: number | null; end_day: number | null }[]);
    expect(saved.find(r => r.name === "SHH")).toMatchObject({ start_day: 5, end_day: null });
    expect(saved.find(r => r.name === "LDN193189")).toMatchObject({ start_day: null, end_day: null });
  });
});

describe("document import", () => {
  it("shows that the document is being read, then opens the draft", async () => {
    let finish!: (r: Response) => void;
    const empty: WorkbenchDTO = { ...base, protocols: [] };
    let state = empty;
    const calls = routes({
      "GET /workbench": () => json(state),
      "POST /uploads": () => json({ id: hex("m"), name: "方案.docx", kind: "protocol", size: 10, created_at: "" }),
      "POST /protocols": () => new Promise<Response>(resolve => { finish = resolve; }),
      [FORMALIZATION]: () => json(formalization),
    });
    open({ view: "wall", focus: null } as never);
    fireEvent.click(await screen.findByRole("button", { name: "新建方案" }));
    const dialog = screen.getByRole("dialog", { name: "新的分化方案" });
    fireEvent.change(dialog.querySelector("#wb-new-file")!, { target: { files: [new File(["x"], "方案.docx")] } });
    expect(await within(dialog).findByText("正在读取「方案.docx」")).toBeInTheDocument();
    await waitFor(() => expect(calls.some(c => c.key === "POST /protocols")).toBe(true));
    expect(calls.find(c => c.key === "POST /protocols")!.body).toEqual({ material_id: hex("m"), expected_version: 0 });
    state = base;
    finish(json(protocol));
    expect(await screen.findByRole("region", { name: "导入的方案 方案图" })).toBeInTheDocument();
    expect(screen.queryByRole("complementary", { name: "方案原文" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "打开原文" })).toBeInTheDocument();
  });
});
