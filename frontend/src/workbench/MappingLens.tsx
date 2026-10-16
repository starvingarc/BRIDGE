import type { ReactNode } from "react";
import { ChainRings } from "./ChainRings";
import { branchBars } from "./mapping";
import { familyOf } from "./treeScene";
import type { MarkerPanel, Sample } from "./types";

const percent = (share: number) => share > 0 && share < 0.005 ? "<1" : String(Math.round(share * 100));

/**
 * Sample summary for a mapping without chain metrics: which branches its cells landed on, with every share out of
 * all cells. No headline number, so a branch share is never read as product purity.
 */
export function MappingLens({ sample, onTree, inline, children }: { sample: Sample; onTree: boolean; inline?: boolean; children?: ReactNode }) {
  const view = sample.mapping!;
  const bars = branchBars(view);
  return <aside className={`wb-lens wb-lens--mapping${inline ? " wb-lens--inline" : ""}`} aria-label="取样点摘要">
    <span className="wb-lens-day">D{sample.day} · {sample.gestation}</span>
    <span className="wb-lens-method">{view.method}{view.candidate && " · 候选结果"}</span>
    {bars.length ? <ul className="wb-bars" aria-label="细胞落在哪些枝上">
      {bars.map(b => <li key={b.key} className={`wb-bar wb-bar--${b.key === "off" ? "off" : b.key === "rest" ? "rest" : familyOf(b.code ?? "")}`}>
        <span className="wb-bar-name" title={b.code}>{b.name}</span>
        <span className="wb-bar-track" aria-hidden="true"><i style={{ width: `${Math.max(1.5, b.share * 100)}%` }} /></span>
        <span className="wb-bar-pct">{percent(b.share)}%</span>
      </li>)}
    </ul> : <p className="wb-muted">没有细胞落在树上。</p>}
    {!onTree && <p className="wb-lens-warn" role="note">发育树已更新，这次结果属于另一版树，暂不画细胞位置。</p>}
    {view.chainMissing ? <span className="wb-muted">分化链指标：尚未计算</span> : <ChainRings values={sample.chain} />}
    {onTree && <span className="wb-legend" aria-label="图例"><i className="wb-legend-ref" />参考细胞<i className="wb-legend-sample" />当前样本</span>}
    <details className="wb-method">
      <summary>方法与版本</summary>
      <dl>
        {view.reference && <><dt>参考</dt><dd>{view.reference}</dd></>}
        {view.cells !== null && <><dt>细胞数</dt><dd>{view.cells.toLocaleString("zh-CN")}</dd></>}
        {view.treeVersion && <><dt>发育树</dt><dd title={view.treeVersion}>{view.treeVersion.slice(0, 12)}</dd></>}
      </dl>
      {view.limitations.length > 0 && <ul>{view.limitations.map(text => <li key={text}>{text}</li>)}</ul>}
    </details>
    {children}
  </aside>;
}

const expressionText = (value: number) => value.toFixed(value >= 10 ? 0 : value >= 1 ? 1 : 2);

/**
 * Gene picker and colour key while the tree is coloured by marker expression. It shows expression only: no gene is
 * called positive, and no label, chain level or score changes with it.
 */
export function MarkerKey({ panel, gene, onGene, ceiling, status }: {
  panel: MarkerPanel | null; gene: string | null; onGene: (gene: string) => void; ceiling: number | null; status: string | null;
}) {
  return <section className="wb-marker" aria-label="基因表达">
    {panel && <span className="wb-marker-genes" role="group" aria-label="选择基因">
      {panel.genes.map(g => <button key={g.gene} aria-pressed={g.gene === gene} disabled={!g.available} onClick={() => onGene(g.gene)}
        title={g.available ? undefined : g.missingFrom.includes("query") ? "样本数据里没有测到这个基因" : "参考里没有这个基因"}>{g.gene}</button>)}
    </span>}
    {status === "loading" ? <span className="wb-muted" role="status">正在读取表达数据…</span>
      : status ? <p className="wb-lens-warn" role="note">{status}</p>
      : ceiling !== null && <>
        <span className="wb-marker-scale" aria-label={`颜色从 0 到 ${expressionText(ceiling)}`}><span>0</span><i aria-hidden="true" /><span>{expressionText(ceiling)}+</span></span>
        <small className="wb-muted">归一化后取对数的表达量；同一位置多个细胞取平均，浅灰为不在映射参考中的细胞。只展示表达，不判定阳性。</small>
      </>}
  </section>;
}
