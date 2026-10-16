import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { DataDeclaration, type Declaration } from "./DataDeclaration";
import { localDate } from "./StartRunCard";
import { stageOf } from "./stages";
import type { MaterialOption, MappingStatus, Protocol, RunInfo, RunOps, RunState, SampleInput, SampleRecord } from "./types";

const MAPPING: Record<MappingStatus, string> = {
  none: "未映射", pending: "等你确认", approved: "已确认", running: "映射中", done: "已完成", failed: "未完成",
};
const NEXT: { state: RunState; label: string }[] = [
  { state: "differentiating", label: "开始分化" }, { state: "frozen", label: "冻存" }, { state: "grafted", label: "移植" }, { state: "ended", label: "结束" },
];

/** Sampling point wording: waiting for sequencing, a failed attempt with the reason a retry cannot start now, attached data that cannot map yet, or the mapping state. */
export const label = (s: SampleRecord) => s.status === "collected" ? "待测序"
  : s.mapping === "failed" ? (s.unavailable ? `未完成，${s.unavailable}` : "未完成")
  : s.unavailable ? `数据已关联，${s.unavailable}` : MAPPING[s.mapping];
export const tone = (s: SampleRecord) => s.status === "collected" ? "collected" : s.mapping === "failed" ? "failed" : s.unavailable ? "attached" : s.mapping;

/** What the researcher can do next with a sample, given why mapping is or is not running. */
type Next = "attach" | "declare" | "retry" | "start" | "blocked" | null;
function nextStep(s: SampleRecord): Next {
  if (s.status === "collected") return "attach";
  if (s.mapping === "running" || s.mapping === "done" || s.mapping === "pending" || s.mapping === "approved") return null;
  if (s.unavailableCode === "mapping_input_required" && !s.declared) return "declare";
  if (s.unavailableCode && s.unavailableCode !== "mapping_worker_busy") return "blocked";
  return s.mapping === "failed" || s.unavailableCode ? "retry" : "start";
}

/** Run-level controls above the protocol flow: where the run is, registering a sample, and what can happen to the run next. */
export function RunBar({ protocol, ops, addAt }: {
  protocol: Protocol; ops: RunOps;
  /** Opens sample registration on this day, e.g. a day clicked on the flow's day axis. */
  addAt?: { key: number; day: number } | null;
}) {
  const run = protocol.run!;
  const [form, setForm] = useState<"sample" | "graft" | null>(null);
  const [day, setDay] = useState<{ key: number; day: number } | null>(null);
  useEffect(() => { if (addAt) { setDay(addAt); setForm("sample"); } }, [addAt?.key]); // eslint-disable-line react-hooks/exhaustive-deps
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  const stage = stageOf(protocol);
  const act = async (work: () => Promise<{ notice?: string } | void>) => {
    setBusy(true); setMessage(null);
    try { const result = await work(); if (result && result.notice) setMessage({ text: result.notice, error: false }); }
    catch (failure) { setMessage({ text: failure instanceof Error ? failure.message : "没有完成，请重试。", error: true }); }
    finally { setBusy(false); }
  };
  useSettledNotice(protocol.sampleRecords ?? [], setMessage);
  return <section className="wb-runbar" aria-label="取样与状态">
    <div className="wb-runbar-row">
      <span className="wb-runbar-title">{run.cellLine && <b>{run.cellLine}</b>}{run.startDate && <span>{run.startDate}</span>}<span>{stage.tag}</span></span>
      <span className="wb-runbar-actions">
        <button className="wb-chip" disabled={busy} onClick={() => { setDay(null); setForm(form === "sample" ? null : "sample"); }} aria-expanded={form === "sample"}>＋ 样本</button>
        {NEXT.filter(n => n.state !== run.state && !(n.state === "differentiating" && run.state !== "planned" && run.state !== "expanding")).map(n =>
          <button key={n.state} className="wb-chip" disabled={busy}
            onClick={() => n.state === "grafted" ? setForm(form === "graft" ? null : "graft") : void act(() => ops.update(run, { state: n.state }))}>{n.label}</button>)}
      </span>
    </div>
    {message && <p className={message.error ? "wb-error" : "wb-muted"} role={message.error ? "alert" : "status"}>{message.text}</p>}
    {form === "sample" && <SampleForm key={day?.key ?? "bar"} run={run} day={day?.day ?? Math.max(0, protocol.day)} ops={ops}
      onDone={notice => { setForm(null); if (notice) setMessage({ text: notice, error: false }); }} onCancel={() => setForm(null)} />}
    {form === "graft" && <GraftForm onSubmit={graft => act(async () => { await ops.update(run, { state: "grafted", graft }); setForm(null); })} onCancel={() => setForm(null)} busy={busy} />}
  </section>;
}

/**
 * A notice such as "mapping started" describes the moment it was given, so it goes when a sample finishes or fails.
 * Only those transitions count: the refresh right after a write may arrive a render later than the notice.
 */
function useSettledNotice(records: SampleRecord[], setMessage: (update: (m: { text: string; error: boolean } | null) => { text: string; error: boolean } | null) => void) {
  const states = records.map(s => `${s.id}:${s.status}`).join();
  const previous = useRef(new Map<string, string>());
  useEffect(() => {
    const now = new Map(records.map(s => [s.id, s.status] as const));
    const settled = [...now].some(([id, status]) => (status === "done" || status === "failed") && previous.current.has(id) && previous.current.get(id) !== status);
    previous.current = now;
    if (settled) setMessage(m => m && !m.error ? null : m);
  }, [states]); // eslint-disable-line react-hooks/exhaustive-deps
}

/** What can be done next with one sample: attach its data, declare it, or start or retry its mapping. */
export function SampleActions({ protocol, sample, ops }: { protocol: Protocol; sample: SampleRecord; ops: RunOps }) {
  const run = protocol.run!;
  const [form, setForm] = useState<"attach" | "declare" | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  useSettledNotice([sample], setMessage);
  const next = nextStep(sample);
  const done = (text: string) => { setForm(null); setMessage({ text, error: false }); };
  const act = async () => {
    setBusy(true); setMessage(null);
    try { const result = await ops.requestMapping(sample); if (result.notice) setMessage({ text: result.notice, error: false }); }
    catch (failure) { setMessage({ text: failure instanceof Error ? failure.message : "没有完成，请重试。", error: true }); }
    finally { setBusy(false); }
  };
  if (!next && !message) return null;
  return <div className="wb-sample-actions">
    {next === "attach" ? <button className="wb-chip" disabled={busy} aria-expanded={form === "attach"} aria-label={`关联数据 D${sample.day}`}
        onClick={() => setForm(form === "attach" ? null : "attach")}>关联数据</button>
      : next === "declare" ? <button className="wb-chip" disabled={busy} aria-expanded={form === "declare"} aria-label={`补充数据说明 D${sample.day}`}
        onClick={() => setForm(form === "declare" ? null : "declare")}>补充数据说明</button>
      : next === "blocked" ? <span className="wb-muted">映射暂不可用</span>
      : next && <button className="wb-chip" disabled={busy} aria-label={`${next === "start" ? "开始映射" : "重试映射"} D${sample.day}`}
        onClick={() => void act()}>{next === "start" ? "开始映射" : "重试映射"}</button>}
    {message && <p className={message.error ? "wb-error" : "wb-muted"} role={message.error ? "alert" : "status"}>{message.text}</p>}
    {form === "attach" && <AttachForm run={run} sample={sample} ops={ops} onDone={done} onCancel={() => setForm(null)} />}
    {form === "declare" && <DeclareForm run={run} sample={sample} ops={ops} onDone={done} onCancel={() => setForm(null)} />}
  </div>;
}

function SampleForm({ run, day, ops, onDone, onCancel }: { run: RunInfo; day: number; ops: RunOps; onDone: (notice?: string) => void; onCancel: () => void }) {
  const [value, setValue] = useState<Omit<SampleInput, "mappingInput">>({ day, assay: "scRNA-seq", collectedOn: localDate(), materialId: null });
  const [declaration, setDeclaration] = useState<Declaration>(undefined);
  const declare = useCallback((next: Declaration) => setDeclaration(next), []);
  const [materials, setMaterials] = useState(ops.materials);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const file = useRef<HTMLInputElement>(null);
  const upload = async (f?: File) => {
    if (!f) return;
    setBusy(true); setError("");
    try { const m = await ops.uploadMaterial(f); setMaterials(list => [...list.filter(x => x.id !== m.id), m]); setValue(v => ({ ...v, materialId: m.id })); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "没有上传成功"); }
    finally { setBusy(false); if (file.current) file.current.value = ""; }
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!Number.isInteger(value.day) || value.day < 0) { setError("取样天数要是非负整数"); return; }
    if (value.materialId && declaration === undefined) { setError("先把数据说明填完整，或选「不确定，先不映射」"); return; }
    setBusy(true); setError("");
    try { const result = await ops.addSample(run, { ...value, mappingInput: value.materialId ? declaration ?? null : null }); onDone(result.notice); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "没有登记成功，请重试。"); }
    finally { setBusy(false); }
  };
  return <form className="wb-flow-card wb-editor" aria-label="登记样本" onSubmit={submit}>
    <div className="wb-editor-grid">
      <label>取样天<input id="wb-s-day" type="number" min={0} step={1} value={value.day} onChange={e => setValue(v => ({ ...v, day: Number(e.target.value) }))} /></label>
      <label>日期<input id="wb-s-date" type="date" value={value.collectedOn} onChange={e => setValue(v => ({ ...v, collectedOn: e.target.value }))} /></label>
      <label>数据<select id="wb-s-material" value={value.materialId ?? ""} onChange={e => setValue(v => ({ ...v, materialId: e.target.value || null }))}>
        <option value="">测序后再关联</option>{materials.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
    </div>
    <span className="wb-seg" role="group" aria-label="测序">
      {(["scRNA-seq", "snRNA-seq"] as const).map(a => <button type="button" key={a} aria-pressed={value.assay === a} onClick={() => setValue(v => ({ ...v, assay: a }))}>{a}</button>)}
    </span>
    <label className="wb-drop wb-drop--small">
      <input id="wb-s-file" ref={file} type="file" accept=".h5ad" disabled={busy} onChange={e => void upload(e.target.files?.[0])} />
      <span>{busy ? "处理中…" : "上传 H5AD"}</span>
    </label>
    {value.materialId ? <DataDeclaration run={run} assay={value.assay} material={materials.find(m => m.id === value.materialId)} collectedOn={value.collectedOn} onChange={declare} />
      : <p className="wb-muted">取样当天先登记，测序数据回来后再关联。</p>}
    {error && <p className="wb-error" role="alert">{error}</p>}
    <div className="wb-editor-actions">
      <button type="button" className="wb-link" onClick={onCancel} disabled={busy}>取消</button>
      <button type="submit" className="wb-run" disabled={busy}>登记</button>
    </div>
  </form>;
}

/** Picks or uploads the sequencing data for a sample registered at collection. */
function AttachForm({ run, sample, ops, onDone, onCancel }: { run: RunInfo; sample: SampleRecord; ops: RunOps; onDone: (notice: string) => void; onCancel: () => void }) {
  const [materials, setMaterials] = useState<MaterialOption[]>(ops.materials);
  const [materialId, setMaterialId] = useState("");
  const [declaration, setDeclaration] = useState<Declaration>(undefined);
  const declare = useCallback((next: Declaration) => setDeclaration(next), []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const file = useRef<HTMLInputElement>(null);
  const submit = async (work: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await work(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "没有完成，请重试。"); }
    finally { setBusy(false); }
  };
  const upload = (f?: File) => f && submit(async () => {
    try { const m = await ops.uploadMaterial(f); setMaterials(list => [...list.filter(x => x.id !== m.id), m]); setMaterialId(m.id); }
    finally { if (file.current) file.current.value = ""; }
  });
  return <form className="wb-flow-card wb-editor" aria-label={`关联 D${sample.day} 的数据`}
    onSubmit={e => {
      e.preventDefault();
      if (!materialId) { setError("先选择或上传数据"); return; }
      if (declaration === undefined) { setError("先把数据说明填完整，或选「不确定，先不映射」"); return; }
      void submit(async () => onDone((await ops.attachData(sample, materialId, declaration)).notice ?? "已关联。"));
    }}>
    <div className="wb-editor-grid">
      <label>数据<select id="wb-a-material" value={materialId} onChange={e => setMaterialId(e.target.value)}>
        <option value="">选择数据</option>{materials.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
    </div>
    <label className="wb-drop wb-drop--small">
      <input id="wb-a-file" ref={file} type="file" accept=".h5ad" disabled={busy} onChange={e => void upload(e.target.files?.[0])} />
      <span>{busy ? "处理中…" : "上传 H5AD"}</span>
    </label>
    {materialId ? <DataDeclaration run={run} assay={sample.assay} material={materials.find(m => m.id === materialId)} collectedOn={sample.collectedOn} onChange={declare} />
      : <p className="wb-muted">说明数据后会自动做标准图谱映射。</p>}
    {error && <p className="wb-error" role="alert">{error}</p>}
    <div className="wb-editor-actions">
      <button type="button" className="wb-link" onClick={onCancel} disabled={busy}>取消</button>
      <button type="submit" className="wb-run" disabled={busy}>关联</button>
    </div>
  </form>;
}

/** Gives the declaration for data attached without one, then starts mapping. */
function DeclareForm({ run, sample, ops, onDone, onCancel }: { run: RunInfo; sample: SampleRecord; ops: RunOps; onDone: (notice: string) => void; onCancel: () => void }) {
  const [declaration, setDeclaration] = useState<Declaration>(undefined);
  const declare = useCallback((next: Declaration) => setDeclaration(next), []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!declaration) { setError(declaration === null ? "确定原始计数在哪里之后再映射。" : "先把数据说明填完整"); return; }
    setBusy(true); setError("");
    try { onDone((await ops.requestMapping(sample, declaration)).notice ?? "已提交。"); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "没有完成，请重试。"); }
    finally { setBusy(false); }
  };
  return <form className="wb-flow-card wb-editor" aria-label={`补充 D${sample.day} 的数据说明`} onSubmit={submit}>
    <DataDeclaration run={run} assay={sample.assay} material={ops.materials.find(m => m.id === sample.materialId)} collectedOn={sample.collectedOn} onChange={declare} />
    {error && <p className="wb-error" role="alert">{error}</p>}
    <div className="wb-editor-actions">
      <button type="button" className="wb-link" onClick={onCancel} disabled={busy}>取消</button>
      <button type="submit" className="wb-run" disabled={busy}>开始映射</button>
    </div>
  </form>;
}

function GraftForm({ onSubmit, onCancel, busy }: { onSubmit: (graft: { date: string; host: string; site: string }) => Promise<void>; onCancel: () => void; busy: boolean }) {
  const [value, setValue] = useState({ date: localDate(), host: "大鼠", site: "纹状体" });
  return <form className="wb-flow-card wb-editor" aria-label="记录移植" onSubmit={e => { e.preventDefault(); void onSubmit(value); }}>
    <div className="wb-editor-grid">
      <label>移植日期<input id="wb-g-date" type="date" value={value.date} onChange={e => setValue(v => ({ ...v, date: e.target.value }))} /></label>
      <label>宿主<input id="wb-g-host" value={value.host} onChange={e => setValue(v => ({ ...v, host: e.target.value }))} /></label>
      <label>部位<input id="wb-g-site" value={value.site} onChange={e => setValue(v => ({ ...v, site: e.target.value }))} /></label>
    </div>
    <div className="wb-editor-actions">
      <button type="button" className="wb-link" onClick={onCancel} disabled={busy}>取消</button>
      <button type="submit" className="wb-run" disabled={busy || !value.date || !value.host.trim() || !value.site.trim()}>记录移植</button>
    </div>
  </form>;
}
