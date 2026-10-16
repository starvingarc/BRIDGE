import { useEffect, useState } from "react";
import { api, type Principal } from "../api";
export function AccountSettings({user, onSignedOut, forced = false, embedded = false, onBusyChange}: {user: Principal; onSignedOut: () => void; forced?: boolean; embedded?: boolean; onBusyChange?: (busy: boolean) => void}) {
  const [open, setOpen] = useState(forced);
  const [oldPassword, setOld] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { onBusyChange?.(busy); }, [busy, onBusyChange]);
  return <section className="account-settings">
    {embedded ? <div className="settings-password-label"><strong>密码</strong><p>更新你的登录密码。</p></div> : <span>{user.username}</span>}
    {!forced ? <button disabled={busy} onClick={() => { setOpen(!open); setOld(""); setPassword(""); setError(""); }}>{open ? "取消修改" : "修改密码"}</button> : <h1>请先修改临时密码</h1>}
    {open ? <form onSubmit={async e => {
      e.preventDefault(); setBusy(true); setError("");
      try { await api.changePassword(oldPassword, password); onSignedOut(); }
      catch (e) { setError(e instanceof Error ? e.message : "修改失败"); }
      finally { setBusy(false); setOld(""); setPassword(""); }
    }}>
      <label>原密码<input type="password" autoComplete="current-password" required value={oldPassword} onChange={e => setOld(e.target.value)} /></label>
      <label>新密码<input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={password} onChange={e => setPassword(e.target.value)} /></label>
      <button disabled={busy}>修改并重新登录</button>{error ? <p role="alert">{error}</p> : null}
    </form> : null}
    {forced ? <button disabled={busy} onClick={async () => { try { await api.logout(); } finally { onSignedOut(); } }}>退出登录</button> : null}
  </section>;
}
