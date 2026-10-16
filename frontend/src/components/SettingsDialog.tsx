import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Database, LogOut, Shield, UserRound, X } from "lucide-react";
import type { Principal } from "../api";
import { AccountSettings } from "./AccountSettings";
import { AdminSessions } from "./AdminSessions";
import { ModelSettings } from "./ModelSettings";

type Section = "account" | "models" | "admin";
/** `trigger` replaces the default name button, e.g. the workbench's avatar row; `triggerClassName` styles it. */
type Props = {principal: Principal; disabled: boolean; onLogout: () => void; onSignedOut?: () => void; trigger?: ReactNode; triggerClassName?: string};

export function SettingsDialog({principal, disabled, onLogout, onSignedOut, trigger: triggerContent, triggerClassName = "sidebar-account"}: Props) {
  const [open, setOpen] = useState(false);
  const [section, setSection] = useState<Section>("account");
  const [busy, setBusy] = useState(false);
  const [compact, setCompact] = useState(() => window.matchMedia("(max-width: 640px)").matches);
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const id = useId();
  const username = principal.username;
  const sections = [
    {id: "account" as const, label: "账号", icon: UserRound},
    {id: "models" as const, label: "模型", icon: Database},
    ...(principal.role === "admin" ? [{id: "admin" as const, label: "测试管理", icon: Shield}] : []),
  ];
  useEffect(() => { if (open) dialog.current?.showModal(); else dialog.current?.close(); }, [open]);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 640px)");
    const update = () => setCompact(media.matches);
    update(); media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  const close = () => { setOpen(false); setBusy(false); trigger.current?.focus(); };
  // Other parts of the page (such as the model picker) can open a section directly.
  useEffect(() => {
    const show = (event: Event) => {
      const wanted = (event as CustomEvent<{section?: Section}>).detail?.section;
      setSection(wanted === "models" || wanted === "account" || (wanted === "admin" && principal.role === "admin") ? wanted : "account");
      setBusy(false); setOpen(true);
    };
    window.addEventListener("bridge:open-settings", show);
    return () => window.removeEventListener("bridge:open-settings", show);
  }, [principal.role]);
  const choose = (next: Section) => { setSection(next); };
  return <>
    <button ref={trigger} className={triggerClassName} aria-haspopup="dialog" aria-expanded={open}
      title="打开设置" aria-label={triggerContent ? username : undefined} onClick={() => { setSection("account"); setBusy(false); setOpen(true); }}>
      {triggerContent ?? <span>{username}</span>}
    </button>
    <dialog ref={dialog} className="settings-dialog" aria-labelledby={`${id}-title`}
      onCancel={event => { if (busy) event.preventDefault(); else close(); }}>
      {open ? <div className="settings-shell">
        <header className="settings-header"><h2 id={`${id}-title`}>设置</h2>
          <button className="icon-button" aria-label="关闭设置" disabled={busy} onClick={close}><X size={20} aria-hidden="true" /></button></header>
        <nav className="settings-nav" aria-label="设置分类" role="tablist" aria-orientation={compact ? "horizontal" : "vertical"}>
          {sections.map(({id: key, label, icon: Icon}, index) => <button key={key} id={`${id}-${key}`} role="tab"
            aria-selected={section === key} aria-controls={`${id}-panel`} tabIndex={section === key ? 0 : -1}
            disabled={busy} onClick={() => choose(key)} onKeyDown={event => {
              if (!["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
              event.preventDefault();
              const next = event.key === "Home" ? 0 : event.key === "End" ? sections.length - 1
                : (index + (["ArrowUp", "ArrowLeft"].includes(event.key) ? -1 : 1) + sections.length) % sections.length;
              choose(sections[next].id); document.getElementById(`${id}-${sections[next].id}`)?.focus();
            }}><Icon size={17} aria-hidden="true" /><span>{label}</span></button>)}
        </nav>
        <section id={`${id}-panel`} className="settings-content" role="tabpanel" aria-labelledby={`${id}-${section}`}>
          {section === "account" ? <div className="settings-account-panel">
            <h3>账号</h3><p className="settings-description">管理你的账号和登录安全。</p>
            <div className="settings-detail-row"><span>用户 ID</span><strong>{username}</strong></div>
            <>
              <div className="settings-detail-row"><span>账号类型</span><span>{principal.role === "admin" ? "管理员" : "成员"}</span></div>
              <AccountSettings user={principal} onSignedOut={onSignedOut || onLogout} embedded onBusyChange={setBusy} />
            </>
            <div className="settings-signout"><div><strong>退出登录</strong><p>下次使用时需要重新登录。</p></div>
              <button disabled={disabled || busy} onClick={onLogout}><LogOut size={16} aria-hidden="true" />退出登录</button></div>
          </div> : section === "models" ? <ModelSettings embedded onBusyChange={setBusy} />
            : <AdminSessions embedded onBusyChange={setBusy} />}
        </section>
      </div> : null}
    </dialog>
  </>;
}
