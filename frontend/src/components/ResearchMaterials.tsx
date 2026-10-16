import { Download, FileText, Files, Plus, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { formatBytes } from "../upload";
import type { Research, ResearchMaterial, Session } from "../types";

const DOCUMENT_LIMIT = 25 * 1024 * 1024;
const kinds = {h5ad: "表达数据", protocol: "实验方案 / 文档", metadata: "样本表"};
type Props = {
  initialUploadId?: string; researchId: string; session: Session | null; disabled: boolean;
  onClose: () => void; onBusy: (busy: boolean) => void;
  onSession: (session: Session) => void; onError: (error: unknown) => void;
};

export function ResearchMaterials({researchId, session, initialUploadId, disabled, onClose, onBusy, onSession, onError}: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [research, setResearch] = useState<Research | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [protocolUpload, setProtocolUpload] = useState(initialUploadId ?? "");
  const inFlight = useRef(false);
  const alive = useRef(true);
  const requestId = useRef(0);
  const refresh = async () => {
    const request = ++requestId.current;
    setLoading(true);
    try {
      const value = await api.getResearch(researchId);
      if (alive.current && request === requestId.current) setResearch(value);
    } finally {if (alive.current && request === requestId.current) setLoading(false);}
  };
  useEffect(() => {
    alive.current = true; dialog.current?.showModal(); void refresh().catch(failure => {
      if (alive.current) {setError(failure instanceof Error ? failure.message : "资料读取失败，请重试。"); onError(failure);}
    });
    return () => {alive.current = false; requestId.current += 1;};
  }, [researchId]);
  const perform = async (operation: () => Promise<void>) => {
    if (inFlight.current || disabled) return;
    inFlight.current = true; setWorking(true); setError(""); setNotice(""); onBusy(true);
    try {await operation();}
    catch (failure) {
      if (alive.current) {setError(failure instanceof Error ? failure.message : "操作失败，请重试。"); onError(failure);}
    } finally {
      inFlight.current = false;
      if (alive.current) {setWorking(false); onBusy(false);}
    }
  };
  const upload = async (file: File) => {
    await perform(async () => {
      setNotice("正在核对上传限制…");
      const limits = await api.uploadConfig();
      const limit = file.name.toLowerCase().endsWith(".h5ad") ? limits.max_upload_bytes : Math.min(DOCUMENT_LIMIT, limits.max_upload_bytes);
      if (file.size > limit) throw new Error(`这份文件为 ${formatBytes(file.size)}，当前上限为 ${formatBytes(limit)}。文件尚未发送。`);
      setNotice(`正在上传 ${file.name} 并检查内容，请保持页面打开…`);
      const material = await api.uploadResearchMaterial(researchId, file);
      setResearch(current => current ? {...current, materials: [...current.materials, material], material_count: current.material_count + 1} : current);
      setNotice("资料已保存，本研究的其他会话也可以使用。分析前请选择需要的文件。");
    });
  };
  const selectedUpload = session?.uploads.find(item => item.id === protocolUpload)?.id ?? session?.uploads[0]?.id;
  const choose = (material: ResearchMaterial) => {
    if (!session) return;
    void perform(async () => {
      const next = await api.selectResearchMaterial(session.id, material.id, material.kind === "protocol" ? selectedUpload : undefined);
      onSession(next); setNotice("已加入当前会话；请在实验背景中核对资料。");
    });
  };
  const share = (uploadId: string) => {
    if (!session) return;
    void perform(async () => {
      await api.shareResearchMaterial(session.id, uploadId);
      const next = await api.getSession(session.id);
      onSession(next); setNotice("原始文件已保存到研究资料。"); await refresh();
    });
  };
  return <dialog ref={dialog} className="research-materials-drawer" aria-labelledby="research-materials-title"
    onCancel={event => {if (working) event.preventDefault(); else onClose();}}>
    <header><div><p>共享资料</p><h2 id="research-materials-title">研究资料</h2></div>
      <button className="icon-button" aria-label="关闭研究资料" disabled={working} onClick={onClose}><X aria-hidden="true" /></button></header>
    <p className="research-materials-intro">{research?.name}<br />同一研究内共享原始资料，各会话分别选择分析输入。</p>
    <div className="research-materials-body">
      {error && <p role="alert" className="research-inline-error">{error}</p>}
      {notice && <p role="status" className="research-material-notice">{notice}</p>}
      {loading ? <p role="status">正在读取资料…</p> : !research ? <button onClick={() => void perform(refresh)}>重试读取资料</button> : <>
        {research.materials.length === 0 && <div className="research-materials-empty"><Files aria-hidden="true" /><h3>还没有研究资料</h3><p>可以先开始讨论，或添加数据与实验方案。</p></div>}
        {research.materials.some(item => item.kind === "protocol") && !!session?.uploads.length && <label className="research-protocol-target">实验方案对应的数据
          <select value={selectedUpload} disabled={working || disabled} onChange={event => setProtocolUpload(event.target.value)}>
            {session.uploads.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}
          </select>
        </label>}
        <ul className="research-material-list">{research.materials.map(item => {
          const selected = session?.uploads.some(upload => upload.material_id === item.id);
          return <li key={item.id}><FileText aria-hidden="true" /><div><strong>{item.name}</strong><small>{kinds[item.kind]} · {formatBytes(item.size)}</small>
            <div className="research-material-actions"><a href={api.researchMaterialUrl(researchId, item.id)} download><Download aria-hidden="true" />下载</a>
              {item.kind !== "metadata" && session && <button disabled={working || disabled || selected || (item.kind === "protocol" && !selectedUpload)} onClick={() => choose(item)}>{selected ? "本会话已选" : "用于本会话"}</button>}
            </div>
            {item.kind === "metadata" && <p>可下载核对；不会自动合并到分析数据。</p>}
            {item.kind === "protocol" && session && !selectedUpload && <p>先为当前会话选择 H5AD，再关联实验方案。</p>}
          </div></li>;
        })}</ul>
        {!session && research.materials.length > 0 && <p className="research-material-note">新建会话后，可以选择资料开展分析。</p>}
        {!!session?.uploads.some(item => !item.material_id) && <section className="research-unshared"><h3>此会话已有的文件</h3><p>共享原始文件，其他会话即可选用。</p>
          {session.uploads.filter(item => !item.material_id).map(item => <div key={item.id}><span>{item.name}</span><button disabled={working || disabled} onClick={() => share(item.id)}>保存到研究</button></div>)}
        </section>}
      </>}
    </div>
    <footer><input ref={fileInput} className="sr-only" aria-label="添加研究资料" type="file" accept=".h5ad,.pdf,.docx,.txt,.md,.csv,.tsv" disabled={working || disabled}
      onChange={event => {const file = event.target.files?.[0]; event.target.value = ""; if (file) void upload(file);}} />
      <button className="research-primary" disabled={working || disabled || !research} onClick={() => fileInput.current?.click()}><Plus aria-hidden="true" />{working ? "正在处理…" : "添加资料"}</button>
      <small>H5AD · PDF · DOCX · TXT · MD · CSV · TSV<br />文档上限 25 MiB；H5AD 使用服务器当前上限。</small>
    </footer>
  </dialog>;
}
