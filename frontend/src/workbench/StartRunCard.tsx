import { useState, type FormEvent } from "react";
import type { RunState, StartRunInput } from "./types";

type Props = {
  /** What submitting does, e.g. confirming the protocol and recording the experiment, or recording another batch. */
  title: string; submitLabel: string;
  onSubmit: (input: StartRunInput) => Promise<void>; onClose: () => void;
};

export const localDate = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

const STATES: { id: RunState; label: string }[] = [
  { id: "differentiating", label: "分化中" }, { id: "expanding", label: "还在扩增" }, { id: "ended", label: "已结束" },
];

/** The stored name of a run; the interface titles runs by protocol, cell line and date instead. */
export const runName = (input: Pick<StartRunInput, "cellLine" | "startDate">) => [input.cellLine.trim(), input.startDate].filter(Boolean).join(" ") || "实验记录";

/**
 * Records an experiment of a protocol, as in a lab notebook: the cell line, the D0 date (may be unknown, e.g. for
 * public data) and where it is now.
 */
export function RecordRunCard({ title, submitLabel, onSubmit, onClose }: Props) {
  const [value, setValue] = useState<StartRunInput>({ name: "", cellLine: "", startDate: localDate(), state: "differentiating" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true); setError("");
    try { await onSubmit({ ...value, name: runName(value), cellLine: value.cellLine.trim() }); onClose(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "没有记录成功，请重试。"); }
    finally { setBusy(false); }
  };
  return <form className="wb-flow-card wb-editor" aria-label={title} onSubmit={submit}>
    <h2 className="wb-editor-title">{title}</h2>
    <div className="wb-editor-grid">
      <label>细胞系<input id="wb-run-line" value={value.cellLine} onChange={e => setValue(v => ({ ...v, cellLine: e.target.value }))} placeholder="H9" autoFocus /></label>
      <label>D0 日期<input id="wb-run-date" type="date" value={value.startDate} onChange={e => setValue(v => ({ ...v, startDate: e.target.value }))} /></label>
    </div>
    <p className="wb-muted">日期不清楚（例如公开数据）可以清空，之后再补。</p>
    <span className="wb-seg" role="group" aria-label="现在">
      {STATES.map(s => <button type="button" key={s.id} aria-pressed={value.state === s.id} onClick={() => setValue(v => ({ ...v, state: s.id }))}>{s.label}</button>)}
    </span>
    {error && <p className="wb-error" role="alert">{error}</p>}
    <div className="wb-editor-actions">
      <button type="button" className="wb-link" onClick={onClose} disabled={busy}>取消</button>
      <button type="submit" className="wb-run" disabled={busy}>{busy ? "记录中…" : submitLabel}</button>
    </div>
  </form>;
}
