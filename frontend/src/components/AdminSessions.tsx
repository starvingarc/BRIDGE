import { useEffect, useRef, useState } from "react";
import { api, type AdminSession, type AdminUser } from "../api";
import type { Session } from "../types";

export function AdminSessions({embedded = false, onBusyChange}: {embedded?: boolean; onBusyChange?: (busy: boolean) => void} = {}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const generation = useRef(0);
  const [open, setOpen] = useState(embedded);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [owner, setOwner] = useState("");
  const [sessions, setSessions] = useState<AdminSession[]>([]);
  const [detail, setDetail] = useState<{session: Session; owner: {username: string}; protocols: {id: string; name: string}[]} | null>(null);
  const [busy, setBusy] = useState(false);
  const [mutating, setMutating] = useState(false);
  const [error, setError] = useState("");
  const [temporary, setTemporary] = useState("");
  const [confirm, setConfirm] = useState<"disable" | "reset" | null>(null);
  useEffect(() => {
    if (open) dialog.current?.showModal(); else dialog.current?.close();
  }, [open]);
  useEffect(() => () => { generation.current += 1; }, []);
  const load = async (userId = "") => {
    const current = ++generation.current;
    setBusy(true); setError(""); setDetail(null); setOwner(userId); setTemporary(""); setConfirm(null);
    try {
      const [people, histories] = await Promise.all([api.adminUsers(), api.adminSessions(userId)]);
      if (current === generation.current) { setUsers(people.users); setSessions(histories.sessions); }
    } catch (e) { if (current === generation.current) setError(e instanceof Error ? e.message : "读取失败"); }
    finally { if (current === generation.current) setBusy(false); }
  };
  useEffect(() => { if (embedded) void load(); }, [embedded]);
  useEffect(() => { onBusyChange?.(mutating); }, [mutating, onBusyChange]);
  const inspect = async (id: string) => {
    const current = ++generation.current;
    setBusy(true); setError(""); setDetail(null);
    try { const value = await api.adminSession(id); if (current === generation.current) setDetail(value); }
    catch (e) { if (current === generation.current) setError(e instanceof Error ? e.message : "读取失败"); }
    finally { if (current === generation.current) setBusy(false); }
  };
  const close = () => { generation.current += 1; setOpen(false); setDetail(null); setTemporary(""); setConfirm(null); setBusy(false); };
  const selected = users.find(value => value.id === owner);
  const session = detail?.session;
  const content = open ? <div className="admin-settings-panel">
        <header><div>{embedded ? <h3 id="admin-title">测试管理</h3> : <h2 id="admin-title">测试管理</h2>}<p>跨账号查看为只读，读取和账号管理操作均会记录审计。</p></div>{!embedded ? <button aria-label="关闭测试管理" onClick={close}>关闭</button> : null}</header>
        <label>筛选用户<select aria-label="筛选用户" value={owner} disabled={busy} onChange={e => void load(e.target.value)}><option value="">全部用户</option>
          {users.map(user => <option key={user.id} value={user.id}>{user.username}{user.disabled ? "（已停用）" : ""}</option>)}</select></label>
        {selected?.role === "user" ? <div className="admin-user-actions">
          <button disabled={busy || !!selected.disabled} onClick={() => setConfirm("disable")}>停用账号</button>
          <button disabled={busy || !!selected.disabled} onClick={() => setConfirm("reset")}>重置密码</button>
          {confirm ? <div role="group" aria-label="确认账号操作"><p>{confirm === "disable" ? "停用后此账号无法登录，已有数据保留。" : "重置将撤销所有登录。请私下将临时密码交给该用户。"}</p>
            <button onClick={() => setConfirm(null)}>取消</button><button disabled={busy} onClick={async () => {
              setBusy(true); setMutating(true); setError("");
              try {
                if (confirm === "disable") { await api.disableUser(owner); await load(owner); }
                else { const value = await api.resetPassword(owner); setTemporary(value.temporary_password); }
                setConfirm(null);
              } catch (e) { setError(e instanceof Error ? e.message : "操作失败"); }
              finally { setBusy(false); setMutating(false); }
            }}>确认操作</button></div> : null}
          {temporary ? <p role="status">临时密码：<code>{temporary}</code>（关闭窗口后不再显示）</p> : null}
        </div> : null}
        {error ? <p role="alert">{error}</p> : null}{busy ? <p role="status">正在读取…</p> : null}
        <div className="admin-columns"><nav aria-label="测试会话">{sessions.length ? sessions.map(item =>
          <button key={item.id} disabled={busy} onClick={() => void inspect(item.id)}><strong>{item.title || "未命名会话"}</strong><span>{item.owner_username} · {item.status}{item.archived ? " · 已归档" : ""}</span></button>
        ) : <p>没有会话。</p>}</nav>
        <section className="admin-detail">{session ? <>
          <h3>{session.title || "未命名会话"}</h3><p>所有者：{detail!.owner.username} · 状态：{session.status}</p>
          {session.model_configuration ? <p>任务模型：{session.model_configuration.model}</p> : null}
          <h4>对话</h4>{session.messages.map(message => <article key={message.id}><strong>{message.role === "user" ? detail!.owner.username : "BRIDGE"}</strong><p>{message.content}</p></article>)}
          <h4>上传材料</h4><ul>{session.uploads.map(file => <li key={file.id}><a href={`/api/admin/sessions/${session.id}/uploads/${file.id}`}>{file.name}</a></li>)}
          {detail!.protocols?.map(file => <li key={file.id}><a href={`/api/admin/sessions/${session.id}/protocols/${file.id}`}>{file.name}</a></li>)}</ul>
          <h4>生成结果</h4><ul>{session.artifacts.map(artifact => <li key={artifact.id}>{artifact.url && !artifact.acknowledgement_required && artifact.access_state !== "denied" ?
            <a href={artifact.url.replace("/api/sessions/", "/api/admin/sessions/")}>{artifact.name || artifact.id}</a> : <span>{artifact.name || artifact.id}（暂不可下载）</span>}</li>)}</ul>
          <a href={`/api/admin/sessions/${session.id}/transcript`}>下载对话记录</a>
        </> : <p>选择会话查看内容。</p>}</section></div>
      </div> : null;
  if (embedded) return content;
  return <>
    <button className="sidebar-model-settings" onClick={() => { setOpen(true); void load(); }}>测试管理</button>
    <dialog ref={dialog} className="admin-dialog" aria-labelledby="admin-title" onCancel={close}>{content}</dialog>
  </>;
}
