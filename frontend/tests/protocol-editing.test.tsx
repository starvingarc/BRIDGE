import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ResearchWorkbench } from "../src/workbench/ResearchWorkbench";
import { COMPOUND_DRAG } from "../src/workbench/MoleculeLibrary";
import type { ProtocolDTO, ProtocolVersionDTO } from "../src/workbench/objects";
import type { Research } from "../src/types";

const principal = { id: "u1", username: "wyx", role: "user" as const, must_change_password: false };
const research = { id: "r".repeat(32), name: "研究", materials: [] } as unknown as Research;
const hex = (c: string) => c.repeat(32);
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const version = (patch: Partial<ProtocolVersionDTO>): ProtocolVersionDTO => ({
  id: hex("1"), protocol_id: hex("p"), version: 1, status: "draft", based_on_version_id: null, total_days: 20, confirmed_at: null, revision: 3,
  reagents: [{ id: hex("a"), name: "CHIR99021", short: "CHIR", pathway: "wnt", kind: "molecule", dose_text: "3 μM", start_day: 2, end_day: 6, catalog_id: "chir99021", unconfirmed: [] }],
  ...patch,
});
const protocol = (latest: ProtocolVersionDTO): ProtocolDTO => ({
  id: hex("p"), research_id: research.id, name: "Protocol A", origin: "lab", citation: null, latest_version_id: latest.id, latest, versions: [latest], revision: 7,
});
const empty = { runs: [], samples: [], assessments: [], leads: [], actions: [] };

function mount(latest: ProtocolVersionDTO, extra: Record<string, (init?: RequestInit) => Response> = {}) {
  const calls: { key: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${String(input).replace(`/api/researches/${research.id}`, "")}`;
    calls.push({ key, body: typeof init?.body === "string" ? JSON.parse(init.body) : init?.body });
    if (key === "GET /workbench") return json({ ...empty, protocols: [protocol(latest)] });
    const handler = extra[key];
    return handler ? handler(init) : json({ detail: "Not Found" }, 404);
  }));
  render(<ResearchWorkbench principal={principal} research={research} onSessions={() => undefined} onHome={() => undefined} />);
  return calls;
}
/** jsdom lays nothing out: give the day axis and the bar's lane a width so pointer positions map to days. */
function layout() {
  const box = (left: number, width: number) => () => ({ left, width, top: 0, height: 20, right: left + width, bottom: 20, x: left, y: 0, toJSON: () => ({}) });
  // 20 days plus 3 before D0 over 230 px: 10 px a day, D0 at 30 px.
  document.querySelectorAll<HTMLElement>(".wb-flow-lane, .wb-flow-track").forEach(el => { el.getBoundingClientRect = box(0, 230); });
  const bar = screen.getByRole("button", { name: /^CHIR99021/ });
  bar.getBoundingClientRect = box(50, 40);
  return bar;
}
beforeAll(() => {
  const w = window as unknown as Record<string, typeof MouseEvent>;
  for (const name of ["PointerEvent", "DragEvent"]) if (!(name in window)) w[name] = MouseEvent;
});

describe("editing the protocol flow by hand", () => {
  it("moves a draft treatment's end by dragging and saves the new window in place", async () => {
    const calls = mount(version({}), { [`PATCH /protocols/${hex("p")}/versions/${hex("1")}`]: () => json(version({})) });
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A/ }));
    const bar = layout();
    fireEvent.pointerDown(bar, { clientX: 88, button: 0, pointerId: 1 });
    fireEvent.pointerMove(bar, { clientX: 118, pointerId: 1 });
    expect(bar).toHaveTextContent("D2–D9");
    fireEvent.pointerUp(bar, { clientX: 118, pointerId: 1 });
    fireEvent.click(bar);
    await waitFor(() => expect(calls.some(c => c.key.startsWith("PATCH"))).toBe(true));
    const reagents = (calls.find(c => c.key.startsWith("PATCH"))!.body as { reagents: Record<string, unknown>[] }).reagents;
    expect(reagents[0]).toMatchObject({ name: "CHIR99021", start_day: 2, end_day: 9, dose_text: "3 μM" });
    expect(screen.queryByRole("form", { name: "编辑 CHIR99021" })).not.toBeInTheDocument();
  });

  it("turns a drag on a confirmed version into its next draft and leaves the version as it was", async () => {
    const calls = mount(version({ status: "confirmed", confirmed_at: "2026-10-01T00:00:00Z" }), {
      [`POST /protocols/${hex("p")}/versions`]: () => json(version({ id: hex("2"), version: 2, based_on_version_id: hex("1") })),
    });
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A/ }));
    expect(screen.getByText(/改动会生成下一版草稿/)).toBeInTheDocument();
    const bar = layout();
    fireEvent.pointerDown(bar, { clientX: 70, button: 0, pointerId: 1 });
    fireEvent.pointerMove(bar, { clientX: 90, pointerId: 1 });
    fireEvent.pointerUp(bar, { clientX: 90, pointerId: 1 });
    await waitFor(() => expect(calls.some(c => c.key === `POST /protocols/${hex("p")}/versions`)).toBe(true));
    expect(calls.some(c => c.key.startsWith("PATCH"))).toBe(false);
    expect(calls.find(c => c.key === `POST /protocols/${hex("p")}/versions`)!.body).toMatchObject({
      based_on_version_id: hex("1"), changes: { change_note: "CHIR99021 改为 D4–D8", reagents: [expect.objectContaining({ start_day: 4, end_day: 8 })] },
    });
  });

  it("finds a compound in the library and adds it with its pathway and reported doses", async () => {
    const calls = mount(version({ reagents: [] }), { [`PATCH /protocols/${hex("p")}/versions/${hex("1")}`]: () => json(version({})) });
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A/ }));
    fireEvent.click(screen.getByRole("button", { name: "＋ 试剂" }));
    const library = screen.getByRole("complementary", { name: "小分子库" });
    fireEvent.change(within(library).getByLabelText("搜索小分子"), { target: { value: "notch" } });
    expect(within(library).getByRole("listitem", { name: /^DAPT/ })).toBeInTheDocument();
    expect(within(library).queryByRole("listitem", { name: /^CHIR99021/ })).not.toBeInTheDocument();
    fireEvent.click(within(library).getByRole("button", { name: "加入 DAPT" }));
    const editor = screen.getByRole("form", { name: "添加试剂" });
    expect(within(editor).getByLabelText("名称")).toHaveValue("DAPT");
    expect(within(editor).getByLabelText("通路")).toHaveValue("notch");
    fireEvent.click(within(within(editor).getByRole("group", { name: "文献报告的浓度" })).getByRole("button", { name: "10 μM" }));
    fireEvent.change(within(editor).getByLabelText("开始"), { target: { value: "10" } });
    fireEvent.change(within(editor).getByLabelText("结束"), { target: { value: "16" } });
    fireEvent.click(within(editor).getByRole("button", { name: "保存" }));
    await waitFor(() => expect(calls.some(c => c.key.startsWith("PATCH"))).toBe(true));
    expect((calls.find(c => c.key.startsWith("PATCH"))!.body as { reagents: Record<string, unknown>[] }).reagents[0])
      .toMatchObject({ name: "DAPT", dose_text: "10 μM", start_day: 10, end_day: 16, catalog_id: "dapt" });
  });

  it("drops a library compound on a day of the flow", async () => {
    mount(version({ reagents: [] }));
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A/ }));
    fireEvent.click(screen.getByRole("button", { name: "＋ 试剂" }));
    document.querySelectorAll<HTMLElement>(".wb-flow-track").forEach(el => {
      el.getBoundingClientRect = () => ({ left: 0, width: 230, top: 0, height: 20, right: 230, bottom: 20, x: 0, y: 0, toJSON: () => ({}) });
    });
    const flow = screen.getByRole("region", { name: "Protocol A 方案图" });
    const dataTransfer = { types: [COMPOUND_DRAG], getData: (type: string) => type === COMPOUND_DRAG ? "chir99021" : "", dropEffect: "" };
    fireEvent.dragOver(flow, { clientX: 80, dataTransfer });
    fireEvent.drop(flow, { clientX: 80, dataTransfer });
    const editor = screen.getByRole("form", { name: "添加试剂" });
    expect(within(editor).getByLabelText("名称")).toHaveValue("CHIR99021");
    expect(within(editor).getByLabelText("开始")).toHaveValue(5);
    expect(within(editor).getByLabelText("结束")).toHaveValue(9);
  });

  it("opens a new draft against the version it came from", async () => {
    const v1 = version({ status: "confirmed", confirmed_at: "2026-10-01T00:00:00Z" });
    const v2 = version({ id: hex("2"), version: 2, based_on_version_id: v1.id, reagents: [{ ...v1.reagents[0], end_day: 9 }] });
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => String(input).endsWith("/workbench")
      ? json({ ...empty, protocols: [{ ...protocol(v2), versions: [v1, v2] }], runs: [{ id: hex("r"), research_id: research.id, name: "H9", protocol_version_id: v1.id,
        cell_line: "H9", start_date: null, state: "ended", graft: null, day: null, stage_index: null, today: [], revision: 1 }] })
      : json({ detail: "Not Found" }, 404)));
    render(<ResearchWorkbench principal={principal} research={research} onSessions={() => undefined} onHome={() => undefined} />);
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A v2/ }));
    expect(screen.getByLabelText("对比")).toHaveValue(hex("r"));
    expect(screen.getByRole("button", { name: /^CHIR99021 3 μM，D2–D9，窗口不同/ })).toBeInTheDocument();
  });
});
