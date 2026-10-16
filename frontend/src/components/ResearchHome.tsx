import { CircleDot, Files, History, Search, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import type { Principal } from "../api";
import type { ResearchSummary } from "../types";
import { SettingsDialog } from "./SettingsDialog";
import { StageDish } from "../workbench/StageDish";
import { greeting } from "../workbench/greeting";
import "../workbench/workbench.css";
import { CellLogo } from "./CellLogo";

/** A stable illustrative stage per research so the list reads as a shelf of dishes. */
const researchStage = (id: string) => [1, 2, 3, 4][id.split("").reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % 4];

type Props = {
  principal: Principal; researches: ResearchSummary[]; legacyCount: number; loading: boolean; error: string | null;
  onOpen: (id: string) => void; onLegacy: () => void; onRetry: () => void;
  onCreate: (name: string, description: string) => Promise<void>;
  onLogout: () => void; onSignedOut: () => void;
};

export function ResearchHome({principal, researches, legacyCount, loading, error, onOpen, onLegacy, onRetry, onCreate, onLogout, onSignedOut}: Props) {
  const [query, setQuery] = useState("");
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const createButton = useRef<HTMLButtonElement>(null);
  useEffect(() => { if (creating) {dialog.current?.showModal(); dialog.current?.querySelector<HTMLInputElement>("input")?.focus();} else dialog.current?.close(); }, [creating]);
  const visible = researches.filter(item => `${item.name} ${item.description}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
  const close = () => {setCreating(false); createButton.current?.focus();};
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (saving) return;
    const data = new FormData(event.currentTarget), name = String(data.get("name") ?? "").trim();
    if (!name) {setFormError("请填写研究名称。"); return;}
    setSaving(true); setFormError("");
    try {await onCreate(name, String(data.get("description") ?? "").trim()); setCreating(false);}
    catch (failure) {setFormError(failure instanceof Error ? failure.message : "创建失败，请重试。");}
    finally {setSaving(false);}
  };
  const openCreate = () => {setFormError(""); setCreating(true);};
  return <main className="wb-app research-home-wb">
    <aside className="wb-rail" aria-label="研究导航">
      <div className="wb-brand"><CellLogo size={30} />
        <div><b>BRIDGE</b><small>体内 ⇄ 体外</small></div></div>
      <button ref={createButton} className="wb-new" aria-label="新建研究" onClick={openCreate} disabled={loading}>＋ 新建研究</button>
      <p className="wb-label">研究</p>
      <nav className="wb-nav" aria-label="研究列表">
        {researches.map(item => <button key={item.id} onClick={() => onOpen(item.id)} aria-label={`切换到研究：${item.name}`}><CircleDot aria-hidden="true" size={14} />{item.name}</button>)}
      </nav>
      {legacyCount > 0 && <nav className="wb-nav" aria-label="更多"><button onClick={onLegacy}><History aria-hidden="true" size={14} />历史会话<span>{legacyCount}</span></button></nav>}
    </aside>
    <section className="wb-main">
      <div className="wb-wall">
        <header className="wb-hello research-home-hello">
          <div><h1>{greeting()}，{principal.username}</h1><p>我的研究</p></div>
          <label className="research-search"><Search aria-hidden="true" />
            <input type="search" aria-label="搜索研究" placeholder="搜索研究…" value={query} onChange={event => setQuery(event.target.value)} />
          </label>
        </header>
        <h2 className="sr-only">我的研究</h2>
        {error && <div className="research-inline-error" role="alert"><span>{error}</span><button onClick={onRetry}>重试</button></div>}
        {loading && <p className="wb-muted" role="status">正在打开研究空间…</p>}
        <div className="wb-cards">
          {visible.map(item => <button key={item.id} className="wb-card" aria-label={`打开研究：${item.name}`} onClick={() => onOpen(item.id)}>
            <span className="wb-card-top"><span className="wb-stage-tag">研究</span><span className="wb-pill wb-pill--live">{item.session_count} 个会话</span></span>
            <StageDish stage={researchStage(item.id)} keyId={item.id} />
            <span className="wb-card-name">{item.name}</span>
            <span className="wb-card-stage">{item.description || "从一份方案开始"}</span>
            <span className="wb-card-today"><Files aria-hidden="true" size={12} /> {item.material_count} 份资料</span>
          </button>)}
        </div>
        {!loading && !visible.length && <div className="wb-empty">
          <h2>{query ? "没有匹配的研究" : "从你的第一项研究开始"}</h2>
          <p>{query ? "试试其他名称或清空搜索。" : "给研究起个名字，然后上传分化方案。"}</p>
          {!query && <button className="wb-run" onClick={openCreate}>新建研究</button>}
        </div>}
        {legacyCount > 0 && <p className="wb-muted research-home-legacy"><History aria-hidden="true" size={12} /> 改版前的工作仍在这里
          <button className="wb-link" onClick={onLegacy} aria-label="打开历史会话">历史会话 · {legacyCount}</button></p>}
      </div>
    </section>
    <div className="research-home-account"><SettingsDialog principal={principal} disabled={saving} onLogout={onLogout} onSignedOut={onSignedOut} /></div>
    <dialog ref={dialog} className="research-dialog" aria-labelledby="research-create-title" onCancel={event => {if (saving) event.preventDefault(); else close();}}>
      <header><h2 id="research-create-title">新建研究</h2><button className="icon-button" aria-label="关闭新建研究" disabled={saving} onClick={close}><X aria-hidden="true" /></button></header>
      <form onSubmit={submit}><label>研究名称<input name="name" maxLength={160} required autoFocus placeholder="你希望探索什么？" disabled={saving} /></label>
        <label>说明（可选）<input name="description" maxLength={500} placeholder="记录这项研究的方向" disabled={saving} /></label>
        {formError && <p role="alert">{formError}</p>}<footer><button type="button" disabled={saving} onClick={close}>取消</button>
          <button className="research-primary" type="submit" disabled={saving}>{saving ? "正在创建…" : "创建研究"}</button></footer>
      </form>
    </dialog>
  </main>;
}
