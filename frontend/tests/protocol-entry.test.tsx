import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ResearchWorkbench } from "../src/workbench/ResearchWorkbench";
import { adaptWorkbench } from "../src/workbench/adapt";
import type { ProtocolDTO, ProtocolVersionDTO, WorkbenchDTO } from "../src/workbench/objects";
import type { Research } from "../src/types";

const principal = { id: "u1", username: "wyx", role: "user" as const, must_change_password: false };
const research = { id: "r".repeat(32), name: "mDA 祖细胞优化", materials: [] } as unknown as Research;
const hex = (c: string) => c.repeat(32);
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const v1: ProtocolVersionDTO = {
  id: hex("1"), protocol_id: hex("p"), version: 1, status: "confirmed", based_on_version_id: null, total_days: 28, confirmed_at: "2026-10-01T00:00:00Z", revision: 2,
  reagents: [{ id: hex("a"), name: "CHIR99021", short: "CHIR", pathway: "wnt", kind: "molecule", dose_text: "1.5 μM", start_day: 3, end_day: 13, catalog_id: "chir99021", unconfirmed: [] }],
};
const v2: ProtocolVersionDTO = {
  ...v1, id: hex("2"), version: 2, status: "draft", based_on_version_id: v1.id, confirmed_at: null, revision: 4,
  reagents: [{ ...v1.reagents[0], unconfirmed: ["dose_text"], source_locator: "p.3 表 1" }],
};
const protocol = (latest: ProtocolVersionDTO, versions: ProtocolVersionDTO[]): ProtocolDTO => ({
  id: hex("p"), research_id: research.id, name: "Protocol A", origin: "lab", citation: null, latest_version_id: latest.id, latest, versions, revision: 7,
});
const empty = { runs: [], samples: [], assessments: [], leads: [], actions: [] };

describe("protocol versions", () => {
  it("keeps a run on its confirmed version after a new draft is created", () => {
    const dto: WorkbenchDTO = { ...empty, protocols: [protocol(v2, [v1, v2])],
      runs: [{ id: hex("r"), research_id: research.id, name: "第 3 轮", protocol_version_id: v1.id, cell_line: "H9", start_date: "2026-09-26",
        state: "differentiating", graft: null, day: 16, stage_index: 3, today: [], revision: 1 }] };
    const { protocols } = adaptWorkbench(dto);
    expect(protocols.map(p => p.name)).toEqual(["Protocol A", "Protocol A v2"]);
    expect(protocols[0].source).toMatchObject({ versionId: v1.id, status: "confirmed" });
    expect(protocols[1].source).toMatchObject({ versionId: v2.id, status: "draft", versionRevision: 4, protocolRevision: 7 });
  });
});

describe("protocol entry", () => {
  const routes = (handlers: Record<string, (init?: RequestInit) => Response>) => {
    const calls: { key: string; body: unknown }[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input).replace(`/api/researches/${research.id}`, ""), key = `${init?.method ?? "GET"} ${url}`;
      calls.push({ key, body: typeof init?.body === "string" ? JSON.parse(init.body) : init?.body });
      const handler = handlers[key];
      return handler ? handler(init) : json({ detail: "Not Found" }, 404);
    }));
    return calls;
  };
  const openDraft = async () => {
    render(<ResearchWorkbench principal={principal} research={research} onSessions={() => undefined} onHome={() => undefined} />);
    fireEvent.click(await screen.findByRole("button", { name: /^打开Protocol A/ }));
  };

  it("edits a draft in place and confirms it only after every field is checked", async () => {
    let current = protocol(v2, [v1, v2]);
    const calls = routes({
      "GET /workbench": () => json({ ...empty, protocols: [current] }),
      [`PATCH /protocols/${hex("p")}/versions/${v2.id}`]: init => {
        const body = JSON.parse(String(init!.body));
        current = protocol({ ...v2, revision: 5, reagents: body.reagents }, [v1, v2]);
        return json(current.latest);
      },
      [`POST /protocols/${hex("p")}/versions/${v2.id}/confirm`]: () => json({ ...current.latest, status: "confirmed" }),
      "POST /runs": init => json({ id: hex("r"), research_id: research.id, name: String(JSON.parse(String(init!.body)).name), protocol_version_id: v2.id, cell_line: "H9", start_date: null,
        state: "ended", graft: null, day: null, stage_index: null, today: [], revision: 1 }),
    });
    await openDraft();
    const confirm = screen.getByRole("button", { name: "确认并记录" });
    expect(confirm).toBeDisabled();
    expect(screen.getByRole("button", { name: /CHIR99021 1.5 μM，D3–D13，待核对/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^CHIR99021/ }));
    const editor = screen.getByRole("form", { name: "编辑 CHIR99021" });
    fireEvent.change(within(editor).getByLabelText("剂量"), { target: { value: "3 μM" } });
    fireEvent.click(within(editor).getByLabelText("已对照原文核对"));
    fireEvent.click(within(editor).getByRole("button", { name: "保存" }));

    await waitFor(() => expect(calls.some(c => c.key.startsWith("PATCH"))).toBe(true));
    const patch = calls.find(c => c.key.startsWith("PATCH"))!.body as { expected_version: number; reagents: Record<string, unknown>[] };
    expect(patch.expected_version).toBe(4);
    expect(patch.reagents[0]).toMatchObject({ id: hex("a"), dose_text: "3 μM", unconfirmed: [], source_locator: "p.3 表 1", catalog_id: "chir99021" });

    await waitFor(() => expect(screen.getByRole("button", { name: "确认并记录" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "确认并记录" }));
    const record = screen.getByRole("form", { name: "确认方案并记录实验" });
    fireEvent.change(within(record).getByLabelText("细胞系"), { target: { value: "H9" } });
    fireEvent.change(within(record).getByLabelText("D0 日期"), { target: { value: "" } });
    fireEvent.click(within(record).getByRole("button", { name: "已结束" }));
    fireEvent.click(within(record).getByRole("button", { name: "确认并记录" }));
    await waitFor(() => expect(calls.some(c => c.key === "POST /runs")).toBe(true));
    expect(calls.find(c => c.key.endsWith("/confirm"))!.body).toEqual({ expected_version: 5 });
    expect(calls.findIndex(c => c.key.endsWith("/confirm"))).toBeLessThan(calls.findIndex(c => c.key === "POST /runs"));
    expect(calls.find(c => c.key === "POST /runs")!.body).toMatchObject({ protocol_version_id: v2.id, name: "H9", cell_line: "H9", start_date: null, state: "ended" });
  });

  it("refreshes and explains a version conflict instead of overwriting", async () => {
    let gets = 0;
    routes({
      "GET /workbench": () => { gets += 1; return json({ ...empty, protocols: [protocol(v2, [v1, v2])] }); },
      [`PATCH /protocols/${hex("p")}/versions/${v2.id}`]: () => json({ detail: "object_version_conflict" }, 409),
    });
    await openDraft();
    fireEvent.click(screen.getByRole("button", { name: /^CHIR99021/ }));
    fireEvent.click(within(screen.getByRole("form", { name: "编辑 CHIR99021" })).getByRole("button", { name: "保存" }));
    expect(await screen.findByText("方案刚被更新过，已刷新，请再试一次。")).toBeInTheDocument();
    expect(gets).toBeGreaterThan(1);
  });

  it("creates a manual protocol, and falls back to a blank one while document import is unavailable", async () => {
    let protocols: ProtocolDTO[] = [];
    const created = (name: string) => { const p = { ...protocol({ ...v2, reagents: [], total_days: 0, revision: 1 }, []), name }; protocols = [p]; return json(p); };
    const calls = routes({
      "GET /workbench": () => json({ ...empty, protocols }),
      "POST /uploads": () => json({ id: hex("m"), name: "方案.docx", kind: "protocol", size: 10, created_at: "" }),
      "POST /protocols": init => {
        const body = JSON.parse(String(init!.body));
        return body.material_id ? json({ detail: "protocol_import_not_implemented" }, 409) : created(body.name);
      },
    });
    render(<ResearchWorkbench principal={principal} research={research} onSessions={() => undefined} onHome={() => undefined} />);
    fireEvent.click(await screen.findByRole("button", { name: "＋ 新的分化" }));
    const file = new File(["protocol"], "方案.docx");
    fireEvent.change(screen.getByLabelText(/拖入方案文档/), { target: { files: [file] } });
    expect(await screen.findByRole("heading", { name: "方案 v2" })).toBeInTheDocument();
    const posts = calls.filter(c => c.key === "POST /protocols").map(c => c.body);
    expect(posts).toEqual([{ material_id: hex("m"), expected_version: 0 }, { name: "方案", origin: "lab", expected_version: 0 }]);
    expect(screen.getByText(/文档识别即将接入。已保存「方案.docx」/)).toBeInTheDocument();
    expect(screen.getByText("还没有试剂。点「＋ 试剂」开始录入。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "确认并记录" })).toBeDisabled();
  });
});
