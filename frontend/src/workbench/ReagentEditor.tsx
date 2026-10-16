import { useState, type FormEvent } from "react";
import { matchCompound, suggestPathway } from "./catalog";
import { reportedDoses } from "./MoleculeLibrary";
import { SourceNotes } from "./SourceNotes";
import { PATHWAYS } from "./stages";
import type { Pathway, Reagent, ReagentKind } from "./types";

type Props = { reagent: Reagent; isNew: boolean; onSave: (reagent: Reagent) => Promise<void>; onRemove?: () => Promise<void>; onClose: () => void;
  /** Opens the original text at this reagent, when the version came from a document. */
  onSource?: () => void };
const KINDS: { id: ReagentKind; label: string }[] = [{ id: "molecule", label: "小分子" }, { id: "protein", label: "蛋白" }, { id: "supplement", label: "补充剂" }];

/** Compact in-place editor for one reagent of a draft protocol version. */
export function ReagentEditor({ reagent, isNew, onSave, onRemove, onClose, onSource }: Props) {
  // A catalogue match fills an unset pathway as a default; the researcher still checks it.
  const [value, setValue] = useState(() => reagent.pathway === "other" ? { ...reagent, pathway: suggestPathway(matchCompound(reagent.name)) ?? "other" } : reagent);
  const [checked, setChecked] = useState(!reagent.unconfirmed?.length);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const match = matchCompound(value.name);
  const set = <K extends keyof Reagent>(key: K, v: Reagent[K]) => setValue(current => ({ ...current, [key]: v }));
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!value.name.trim()) { setError("填写试剂名称"); return; }
    const bad = (d: number | null) => d !== null && (!Number.isInteger(d) || d < 0);
    if (bad(value.start) || bad(value.end)) { setError("天数要是非负整数"); return; }
    if (value.start !== null && value.end !== null && value.end < value.start) { setError("结束天不能早于开始天"); return; }
    setBusy(true); setError("");
    try {
      await onSave({
        ...value, name: value.name.trim(), short: value.short.trim() || value.name.trim().slice(0, 6),
        catalogId: match?.id, unconfirmed: checked ? undefined : reagent.unconfirmed,
      });
      onClose();
    } catch (failure) { setError(failure instanceof Error ? failure.message : "没有保存成功，请重试。"); }
    finally { setBusy(false); }
  };
  return <form className="wb-flow-card wb-editor" aria-label={isNew ? "添加试剂" : `编辑 ${reagent.name}`} onSubmit={submit}>
    <div className="wb-editor-grid">
      <label>名称<input id="wb-r-name" value={value.name} autoFocus onChange={e => {
        const name = e.target.value, hint = suggestPathway(matchCompound(name));
        setValue(current => ({ ...current, name, ...(current.pathway === "other" && hint ? { pathway: hint } : {}) }));
      }} /></label>
      <label>简称<input id="wb-r-short" value={value.short} onChange={e => set("short", e.target.value)} placeholder="CHIR" /></label>
      <label>剂量<input id="wb-r-dose" value={value.dose} onChange={e => set("dose", e.target.value)} placeholder="1.5 μM" /></label>
      <label>开始<input id="wb-r-start" type="number" min={0} step={1} value={value.start ?? ""} placeholder="未写明" onChange={e => set("start", e.target.value === "" ? null : Number(e.target.value))} /></label>
      <label>结束<input id="wb-r-end" type="number" min={0} step={1} value={value.end ?? ""} placeholder="未写明" onChange={e => set("end", e.target.value === "" ? null : Number(e.target.value))} /></label>
      <label>通路<select id="wb-r-path" value={value.pathway} onChange={e => set("pathway", e.target.value as Pathway)}>
        {PATHWAYS.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
      <label>类型<select id="wb-r-kind" value={value.kind} onChange={e => set("kind", e.target.value as ReagentKind)}>
        {KINDS.map(k => <option key={k.id} value={k.id}>{k.label}</option>)}</select></label>
    </div>
    <p className="wb-muted" aria-live="polite">{match ? `小分子库：${match.name}` : "小分子库未收录"}</p>
    {match && reportedDoses(match).length > 0 && <span className="wb-dose-hints" role="group" aria-label="文献报告的浓度">文献报告
      {reportedDoses(match).map(d => <button type="button" key={d} aria-pressed={value.dose === d} onClick={() => set("dose", d)}>{d}</button>)}</span>}
    <SourceNotes reagent={reagent} />
    {onSource && <button type="button" className="wb-link" onClick={onSource}>在原文中查看</button>}
    {(value.start === null || value.end === null) && <p className="wb-muted">原文没写明的天数可以先空着；确认方案前需要补上。</p>}
    {!!reagent.unconfirmed?.length && <label className="wb-check"><input id="wb-r-checked" type="checkbox" checked={checked} onChange={e => setChecked(e.target.checked)} />已对照原文核对</label>}
    {error && <p className="wb-error" role="alert">{error}</p>}
    <div className="wb-editor-actions">
      {onRemove && <button type="button" className="wb-link wb-danger" disabled={busy} onClick={() => { setBusy(true); void onRemove().then(onClose, f => { setBusy(false); setError(f instanceof Error ? f.message : "没有删除成功"); }); }}>删除</button>}
      <button type="button" className="wb-link" onClick={onClose} disabled={busy}>取消</button>
      <button type="submit" className="wb-run" disabled={busy}>{busy ? "保存中…" : "保存"}</button>
    </div>
  </form>;
}
