import { useEffect, useRef, useState, type FormEvent } from "react";

type Props = {
  open: boolean; onClose: () => void;
  onUpload: (file: File) => Promise<void>; onCreate: (name: string) => Promise<void>;
};

/** Two ways to start a protocol: drop the document, or name it and enter it by hand. */
export function NewProtocolDialog({ open, onClose, onUpload, onCreate }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [over, setOver] = useState(false);
  const [reading, setReading] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!reading) return;
    setElapsed(0);
    const timer = setInterval(() => setElapsed(s => s + 1), 1000);
    return () => clearInterval(timer);
  }, [reading]);
  useEffect(() => {
    const d = dialog.current;
    if (!d) return;
    if (open && !d.open) { setError(""); setName(""); d.showModal(); }
    if (!open && d.open) d.close();
  }, [open]);
  const run = async (work: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await work(); onClose(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "没有完成，请重试。"); }
    finally { setBusy(false); setReading(null); }
  };
  const upload = (file?: File) => { if (file) { setReading(file.name); void run(() => onUpload(file)); } };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) { setError("给方案起个名字"); return; }
    void run(() => onCreate(name.trim()));
  };
  return <dialog ref={dialog} className="wb-dialog" aria-labelledby="wb-new-title" onCancel={e => { if (busy) e.preventDefault(); else onClose(); }}>
    <h2 id="wb-new-title">新的分化方案</h2>
    <label className={over ? "wb-drop wb-drop--over" : "wb-drop"}
      onDragOver={e => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
      onDrop={e => { e.preventDefault(); setOver(false); upload(e.dataTransfer.files[0]); }}>
      <input id="wb-new-file" type="file" accept=".pdf,.doc,.docx,.txt,.md" disabled={busy} onChange={e => upload(e.target.files?.[0])} />
      <span>{busy ? "正在处理…" : "拖入方案文档，或点这里选择"}</span>
    </label>
    {reading && <div className="wb-reading" role="status" aria-live="polite">
      <span className="wb-reading-bar" aria-hidden="true" />
      <b>正在读取「{reading}」</b>
      <span className="wb-muted">BRIDGE 在读原文并画成方案图，通常需要几十秒，请不要关闭。已用 {elapsed} 秒</span>
    </div>}
    <form className="wb-new-manual" onSubmit={submit}>
      <input id="wb-new-name" value={name} onChange={e => setName(e.target.value)} placeholder="或输入名称，手动录入" aria-label="方案名称" disabled={busy} />
      <button type="submit" className="wb-run" disabled={busy}>新建</button>
    </form>
    {error && <p className="wb-error" role="alert">{error}</p>}
    <button className="wb-link wb-dialog-close" onClick={onClose} disabled={busy} aria-label="关闭">×</button>
  </dialog>;
}
