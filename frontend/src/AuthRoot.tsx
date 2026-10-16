import { useCallback, useEffect, useRef, useState } from "react";
import App from "./App";
import { api, ApiError, resetAccountRequests, type AuthConfig, type Principal } from "./api";
import { AccountSettings } from "./components/AccountSettings";
import "./workbench/workbench.css";
import { CellLogo } from "./components/CellLogo";
import { DishBackground, type DishLook } from "./components/DishBackground";
import { toggleTheme } from "./theme";


export function AuthRoot() {
  const review = new URLSearchParams(window.location.search).get("login-review") === "1";
  const [look, setLook] = useState<DishLook>(() => {
    const value = new URLSearchParams(window.location.search).get("login-look");
    return value === "morning" || value === "opal" ? value : "quiet";
  });
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [user, setUser] = useState<Principal | null>(null);
  const [ready, setReady] = useState(false);
  const [register, setRegister] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState<"about" | "notice" | null>(null);
  const card = useRef<HTMLElement>(null), brand = useRef<HTMLDivElement>(null);
  const signedOut = useCallback(() => {
    resetAccountRequests(); setUser(null); setPassword(""); setRegister(false); setAccepted(false); setBusy(false);
  }, []);
  useEffect(() => {
    let active = true;
    const boot = async () => {
      try {
        const value = await api.authConfig();
        if (!active) return;
        if (value.mode !== "accounts") { setError("服务版本不兼容，请更新服务。"); return; }
        setConfig(value);
        try {
          const result = await api.me();
          if (active) setUser(result.user);
        } catch (e) { if (!(e instanceof ApiError && e.status === 401)) throw e; }
        if (active) setReady(true);
      } catch { if (active) setError("无法连接服务，请刷新重试。"); }
    };
    void boot();
    return () => { active = false; };
  }, []);
  useEffect(() => {
    window.addEventListener("bridge-auth-expired", signedOut);
    return () => window.removeEventListener("bridge-auth-expired", signedOut);
  }, [signedOut]);
  if (!ready) return <main className="loading-screen"><div className="brand">BRIDGE</div><p role={error ? "alert" : undefined}>{error || "正在连接…"}</p></main>;
  if (user?.must_change_password) return <main className="account-shell"><AccountSettings forced user={user} onSignedOut={signedOut} /></main>;
  if (user) return <App key={user.id} principal={user} onSignedOut={signedOut} />;
  return <main className="wb-app wb-login account-login" data-login-look={look} data-login-review={review || undefined}>
    <DishBackground obstacles={[card, brand]} look={look} />
    <div className="wb-login-brand" ref={brand}>
      <CellLogo items={[
        { id: "about", label: "关于 BRIDGE", onSelect: () => setInfo("about") },
        { id: "notice", label: "使用须知", onSelect: () => setInfo("notice") },
        { id: "theme", label: "深色 / 浅色", onSelect: toggleTheme },
      ]} />
      <b>BRIDGE</b>
    </div>
    {review && <nav className="wb-login-looks" aria-label="登录页视觉候选">
      {([["quiet", "A 清透"], ["morning", "B 晨光"], ["opal", "C 珠光"]] as const).map(([value, label]) =>
        <button key={value} type="button" aria-pressed={look === value} onClick={() => {
          setLook(value);
          const url = new URL(window.location.href); url.searchParams.set("login-look", value);
          window.history.replaceState(null, "", url);
        }}>{label}</button>)}
    </nav>}
    <InfoDialog kind={info} notice={config?.notice} onClose={() => setInfo(null)} />
    <section ref={card} className="login-card wb-login-card" aria-labelledby="login-heading">
      <h1 id="login-heading" className={`login-title wb-login-title${register ? "" : " wb-login-title--hidden"}`}>{register ? "创建账号" : "登录研究空间"}</h1>
      {register ? <div className="login-notice"><p>{config?.notice}</p><p>请勿上传未经授权的材料。</p></div> : null}
      <form onSubmit={async event => {
        event.preventDefault(); if (busy || (register && !accepted)) return;
        setBusy(true); setError("");
        try {
          const result = register ? await api.register(username, password, config!.notice_version!) : await api.accountLogin(username, password);
          resetAccountRequests(); setPassword(""); setUser(result.user);
        } catch (e) { setError(e instanceof Error ? e.message : "登录未完成，请重试。"); }
        finally { setPassword(""); setBusy(false); }
      }}>
        <label>用户名<input autoComplete="username" required minLength={register ? 3 : 1} maxLength={32}
          pattern={register ? config?.username_pattern : undefined} value={username} onChange={e => setUsername(e.target.value)} disabled={busy} /></label>
        {register ? <small>3–32 位英文字母、数字、点、下划线或短横线。</small> : null}
        <label>密码<input type="password" autoComplete={register ? "new-password" : "current-password"} required
          minLength={register ? config?.password_min : 1} maxLength={config?.password_max} value={password} onChange={e => setPassword(e.target.value)} disabled={busy} /></label>
        {register ? <><small>至少 {config?.password_min} 位；忘记密码请联系管理员重置。</small><label className="notice-checkbox">
          <input type="checkbox" checked={accepted} onChange={e => setAccepted(e.target.checked)} />我已知悉管理员可查看测试内容。</label></> : null}
        <button type="submit" disabled={busy || !username || !password || (register && !accepted)}>{busy ? "正在处理…" : register ? "注册并登录" : "登录"}</button>
        {error ? <p className="form-error" role="alert">{error}</p> : null}
      </form><button className="login-switch" disabled={busy} onClick={() => { setRegister(!register); setError(""); setPassword(""); }}>
        {register ? "已有账号，返回登录" : "创建账号"}</button>
    </section>
  </main>;
}

/** About and terms of use, opened from the BRIDGE menu on the sign-in page. */
function InfoDialog({ kind, notice, onClose }: { kind: "about" | "notice" | null; notice?: string; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = dialog.current;
    if (!d) return;
    if (kind && !d.open) d.showModal();
    if (!kind && d.open) d.close();
  }, [kind]);
  return <dialog ref={dialog} className="wb-dialog wb-login-info" aria-labelledby="wb-info-title" onClose={onClose} onCancel={onClose}>
    <h2 id="wb-info-title">{kind === "notice" ? "使用须知" : "关于 BRIDGE"}</h2>
    {kind === "notice"
      ? <><p>{notice}</p><p>请勿上传未经授权的材料。</p></>
      : <p>BRIDGE 是面向细胞分化实验的研究助手：把体外分化得到的细胞，对照到人胎腹侧中脑的发育图谱上，看它们长到了哪里，再一起想下一轮怎么改。</p>}
    <button className="wb-link wb-dialog-close" onClick={onClose} aria-label="关闭">×</button>
  </dialog>;
}
