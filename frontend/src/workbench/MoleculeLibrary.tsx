import { useEffect, useMemo, useState } from "react";
import { compounds, structureUrl, type Compound } from "./catalog";

/** Drag payload type for a library compound dropped on the protocol flow. */
export const COMPOUND_DRAG = "application/x-bridge-compound";

function Structure({ id }: { id: string }) {
  const [url, setUrl] = useState<string>();
  useEffect(() => { let live = true; void structureUrl(id).then(u => { if (live) setUrl(u); }); return () => { live = false; }; }, [id]);
  return url ? <img className="wb-lib-structure" src={url} alt="" width={44} height={44} /> : <span className="wb-lib-structure" />;
}

/** Concentrations the literature in the library reports for a compound, deduplicated, at most a few. */
export const reportedDoses = (c: Compound) => [...new Set(c.evidence.map(e => e.reported_concentration).filter(Boolean))].slice(0, 4);

/**
 * The reviewed small-molecule library beside the flow: search by name, alias, target or category, then drag a compound
 * onto a day of the flow, or add it to set its days in the editor.
 */
export function MoleculeLibrary({ onAdd, onCustom, onClose }: { onAdd: (compound: Compound) => void; onCustom: () => void; onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const categories = useMemo(() => [...new Set(compounds.map(c => c.category))], []);
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return compounds.filter(c => (!category || c.category === category)
      && (!q || [c.name, c.category, c.mechanism, ...c.aliases].some(text => text.toLowerCase().includes(q))));
  }, [query, category]);
  useEffect(() => {
    const key = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onClose]);
  return <aside className="wb-panel wb-lib" aria-label="小分子库">
    <header className="wb-panel-head">
      <div><span className="wb-panel-day">小分子库</span><span className="wb-panel-state">拖到方案图上的某一天加入</span></div>
      <button className="wb-link" onClick={onClose} aria-label="关闭小分子库">×</button>
    </header>
    <div className="wb-lib-search">
      <input id="wb-lib-q" type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="名称、靶点或用途，如 CHIR、SMAD、Notch" aria-label="搜索小分子" autoFocus />
      <span className="wb-lib-cats" role="group" aria-label="用途">
        <button aria-pressed={category === null} onClick={() => setCategory(null)}>全部</button>
        {categories.map(c => <button key={c} aria-pressed={category === c} onClick={() => setCategory(category === c ? null : c)}>{c}</button>)}
      </span>
    </div>
    <ul className="wb-lib-list" aria-label="小分子">
      {shown.map(c => <li key={c.id} draggable onDragStart={e => { e.dataTransfer.setData(COMPOUND_DRAG, c.id); e.dataTransfer.setData("text/plain", c.name); e.dataTransfer.effectAllowed = "copy"; }}
        aria-label={`${c.name}，${c.category}`}>
        <Structure id={c.id} />
        <div>
          <b>{c.name}</b>
          <span className="wb-lib-mech">{c.mechanism}</span>
          {reportedDoses(c).length > 0 && <span className="wb-lib-doses">{reportedDoses(c).map(d => <i key={d}>{d}</i>)}</span>}
        </div>
        <button className="wb-chip" onClick={() => onAdd(c)} aria-label={`加入 ${c.name}`}>加入</button>
      </li>)}
      {!shown.length && <li className="wb-muted">库里没有找到。</li>}
    </ul>
    <p className="wb-lib-foot">蛋白、补充剂或库里没有的小分子：<button className="wb-link" onClick={onCustom}>手动添加</button></p>
  </aside>;
}
