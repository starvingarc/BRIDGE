import { fireEvent, render, screen, within } from "@testing-library/react";
import { compound } from "../src/workbench/catalog";
import { Incubator } from "../src/workbench/Incubator";
import { demoProtocols, demoQueue, syntheticTree } from "../src/workbench/demo";
import { ProtocolFlow } from "../src/workbench/ProtocolFlow";
import { WorkbenchApp } from "../src/workbench/WorkbenchApp";
import { stageOf, targetFraction, weakestLevel } from "../src/workbench/stages";
import type { Protocol } from "../src/workbench/types";

const base = demoProtocols[0];
const variant = (patch: Partial<Protocol>): Protocol => ({ ...base, ...patch });

describe("workbench stages", () => {
  it("labels differentiation days with Roman stages and states with names", () => {
    expect(stageOf(variant({ day: 3 })).tag).toBe("D3 · Stage I");
    expect(stageOf(variant({ day: 9 })).name).toBe("底板诱导");
    expect(stageOf(variant({ day: 16 })).tag).toBe("D16 · Stage III");
    expect(stageOf(variant({ day: 24 })).name).toBe("神经元成熟");
    expect(stageOf(variant({ state: "expanding", day: -2 })).tag).toBe("D-2");
    expect(stageOf(variant({ state: "frozen" })).tag).toBe("冻存");
    expect(stageOf(variant({ state: "grafted", graftWeeks: 16 })).name).toBe("第 16 周");
    expect(stageOf(variant({ state: "draft" })).tag).toBe("未开始");
  });

  it("finds the weakest chain level and multiplies the chain", () => {
    expect(weakestLevel([0.99, 0.92, 0.81, 0.48, 0.71])).toBe(3);
    expect(weakestLevel([0.99, 0.92, 0.81, 0.8, 0.71])).toBeNull();
    expect(targetFraction([1, 0.5, 0.5, 1, 1])).toBeCloseTo(0.25);
  });
});

describe("incubator", () => {
  it("lists only runs that have something to do today", () => {
    const idle = { ...demoProtocols[0], id: "idle", name: "无事的一轮", today: "", lead: undefined };
    render(<Incubator userName="wyx" protocols={[demoProtocols[0], idle]} queue={[]} onOpen={() => undefined} />);
    const today = screen.getByRole("list", { name: "今天" });
    expect(today).toHaveTextContent("取样后换液");
    expect(today).not.toHaveTextContent("无事的一轮");
  });

  it("shows one dish per protocol and filters by state", () => {
    render(<Incubator userName="wyx" protocols={demoProtocols} queue={demoQueue} onOpen={() => undefined} />);
    expect(screen.getAllByRole("button", { name: /^打开/ })).toHaveLength(demoProtocols.length);
    expect(screen.getByRole("button", { name: /示例方案 A v3，D16 · Stage III，底板祖细胞/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "已移植" }));
    expect(screen.getAllByRole("button", { name: /^打开/ })).toHaveLength(1);
  });

  it("keeps queued analyses pending until confirmed", () => {
    render(<Incubator userName="wyx" protocols={demoProtocols} queue={demoQueue} onOpen={() => undefined} />);
    const run = screen.getAllByRole("button", { name: "运行" })[0];
    fireEvent.click(run);
    expect(run).toHaveTextContent("已提交");
    expect(run).toBeDisabled();
  });
});

describe("workbench navigation", () => {
  const app = (onLocate = vi.fn()) => render(<WorkbenchApp userName="wyx" researchName="示例研究" protocols={demoProtocols} queue={[]}
    tree={syntheticTree()} respond={() => ({ text: "" })} onLocate={onLocate} />);

  it("keeps the rail to the incubator, the comparison and reports", () => {
    app();
    const views = screen.getByRole("navigation", { name: "视图" });
    expect(within(views).getAllByRole("button").map(b => b.textContent)).toEqual(["培养箱", "比较", "报告"]);
    expect(within(views).getByRole("button", { name: "报告" })).toBeDisabled();
  });

  it("opens a run on its protocol flow with its sampling points, and a point's panel beside it", () => {
    const onLocate = vi.fn();
    app(onLocate);
    fireEvent.click(screen.getByRole("button", { name: /示例方案 A v3/ }));
    expect(screen.getByRole("navigation", { name: "位置" })).toHaveTextContent(base.name);
    expect(screen.getByRole("region", { name: `${base.name} 方案图` })).toBeInTheDocument();
    expect(onLocate).toHaveBeenLastCalledWith({ view: "plan", focus: base.id });
    const points = screen.getByRole("group", { name: "取样点" });
    const last = base.samples.at(-1)!.day;
    fireEvent.click(within(points).getByRole("button", { name: `D${last} scRNA-seq，已完成` }));
    expect(screen.getByRole("complementary", { name: `D${last} 样本` })).toBeInTheDocument();
    expect(onLocate).toHaveBeenLastCalledWith({ view: "plan", focus: base.id, sample: `example-${base.id}-${last}` });
    fireEvent.click(screen.getByRole("button", { name: "关闭样本" }));
    expect(screen.queryByRole("complementary", { name: `D${last} 样本` })).not.toBeInTheDocument();
  });

  it("shows every run on one tree under the comparison, without a run header", () => {
    const onLocate = vi.fn();
    app(onLocate);
    fireEvent.click(within(screen.getByRole("navigation", { name: "视图" })).getByRole("button", { name: "比较" }));
    expect(screen.getByRole("region", { name: "发育树" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "位置" })).not.toBeInTheDocument();
    expect(onLocate).toHaveBeenLastCalledWith({ view: "compare", focus: null });
  });
});

describe("protocol flow", () => {
  it("marks the current stage and flags the lane tied to the weak chain level", () => {
    render(<ProtocolFlow protocol={base} others={demoProtocols.slice(1)} onDraft={() => undefined} />);
    expect(screen.getByRole("status")).toHaveTextContent("底板化偏低");
    expect(screen.getByRole("button", { name: /Stage III 底板祖细胞，D11–D16，当前阶段/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^CHIR99021 1.5 μM，D3–D13/ })).toHaveTextContent("CHIR");
    const flagged = Array.from(document.querySelectorAll(".wb-flow-row--flag .wb-cap")).map(el => el.textContent);
    expect(flagged).toEqual(["SHH", "PM"]);
  });

  it("draws dose steps of one factor on one lane, and keeps overlapping entries apart", () => {
    const shh = (id: string, dose: string, start: number, end: number) =>
      ({ id, name: "SHH C25II", short: "SHH", pathway: "shh" as const, kind: "protein" as const, dose, start, end });
    const steps = { ...base, reagents: [shh("a", "500 ng/mL", 1, 8), shh("b", "100 ng/mL", 9, 12), shh("c", "20 ng/mL", 13, 36), shh("d", "50 ng/mL", 5, 10)] };
    const { container } = render(<ProtocolFlow protocol={steps} others={[]} onDraft={() => undefined} />);
    const lanes = [...container.querySelectorAll(".wb-flow-row")].map(row => [...row.querySelectorAll(".wb-cap")].map(b => b.textContent));
    expect(lanes).toEqual([["SHH 500", "100", "20"], ["SHH"]]);
    expect(screen.getByRole("button", { name: /^SHH C25II 100 ng\/mL，D9–D12/ })).toBeInTheDocument();
  });

  it("opens reagent details from the reviewed small-molecule library", () => {
    render(<ProtocolFlow protocol={base} others={[]} onDraft={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: /^CHIR99021/ }));
    const card = screen.getByRole("complementary", { name: "CHIR99021 详情" });
    expect(within(card).getByText(compound("chir99021")!.mechanism)).toBeInTheDocument();
    expect(within(card).getByLabelText("文献报告浓度")).toHaveTextContent("3 μM");
  });

  it("focuses a stage and dims reagents outside it", () => {
    render(<ProtocolFlow protocol={base} others={[]} onDraft={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: /Stage I 神经诱导/ }));
    expect(screen.getByRole("complementary", { name: "神经诱导详情" })).toBeInTheDocument();
    const dimmed = screen.getByRole("button", { name: /^DAPT/ }).closest("li");
    expect(dimmed).toHaveClass("wb-flow-row--dim");
  });

  it("marks differences against a compared protocol", () => {
    render(<ProtocolFlow protocol={base} others={[demoProtocols[1]]} onDraft={() => undefined} />);
    fireEvent.change(screen.getByLabelText("对比"), { target: { value: demoProtocols[1].id } });
    expect(screen.getByRole("button", { name: /^SHH C25II 100 ng\/mL，D1–D7，窗口不同/ })).toBeInTheDocument();
  });

  it("creates an editable next-round draft that extends the flagged pathway", () => {
    const onDraft = vi.fn();
    render(<ProtocolFlow protocol={base} others={[]} onDraft={onDraft} />);
    fireEvent.click(screen.getByRole("button", { name: "生成下一版草案" }));
    const draft = onDraft.mock.calls[0][0] as Protocol;
    expect(draft.state).toBe("draft");
    expect(draft.version).toBe(base.version + 1);
    expect(draft.reagents.find(r => r.id === "shh")!.end).toBe(9);
    expect(draft.reagents.find(r => r.id === "chir")!.end).toBe(13);
  });
});

describe("developmental tree payload", () => {
  it("synthetic tree follows the cell tuple contract", () => {
    const tree = syntheticTree(200);
    expect(tree.synthetic).toBe(true);
    expect(tree.cells.every(c => c.length === 7 && c[3] >= 0 && c[3] < tree.subtypes.length)).toBe(true);
    expect(tree.edges.every(([a, b]) => a < tree.nodes.length && b < tree.nodes.length)).toBe(true);
  });
});
