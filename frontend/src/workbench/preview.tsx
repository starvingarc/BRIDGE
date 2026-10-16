import { createRoot } from "react-dom/client";
import { demoProtocols, demoQueue, syntheticTree } from "./demo";
import { isLow } from "./stages";
import type { DevTree, Protocol } from "./types";
import { WorkbenchApp } from "./WorkbenchApp";

/** Standalone preview with example content. A private atlas tree is used only when the preview server provides one. */
function respond(question: string, { protocol, sample }: { protocol: Protocol | null; sample: number | null }) {
  const point = protocol && sample !== null ? protocol.samples[sample] : protocol?.samples.at(-1);
  const low = isLow(point?.chain[3]);
  if (question.startsWith("为什么")) return low
    ? { text: "示例回答：SHH 下游信号偏弱，腹侧化不够。", exploratory: true, tags: ["NKX6-1 ↓", "FOXA2 ↓", "GLI1 ↓", "对照 GW8 底板"] }
    : { text: "示例回答：底板标记与 GW8 底板接近，腹侧化充分。", tags: ["FOXA2", "LMX1A", "CORIN"] };
  if (question.startsWith("下一版")) return low
    ? { text: "示例回答：先核查 SHH 通路处理的强度和撤除时间。可以打开方案图，按虚线方向生成下一版草案。" }
    : { text: "示例回答：可以往后看 DA 命运，建议在最后一个时间点之后再补一次取样。" };
  return { text: "预览版未连接 Agent。正式版本会结合这批数据、证据和你的历史记录回答。" };
}

async function loadTree(): Promise<DevTree> {
  try {
    const response = await fetch("workbench-data/devtree.json", { cache: "no-store" });
    if (response.ok) return await response.json() as DevTree;
  } catch { /* fall back to the synthetic tree */ }
  return syntheticTree();
}

void loadTree().then(tree => createRoot(document.getElementById("root")!).render(
  <WorkbenchApp userName="wyx" researchName="mDA 祖细胞优化" protocols={demoProtocols} queue={demoQueue} tree={tree}
    respond={respond} previewLabel={tree.synthetic ? "预览 · 示例数据 · 合成发育树" : "预览 · 示例方案 · 图谱发育树"} />,
));
