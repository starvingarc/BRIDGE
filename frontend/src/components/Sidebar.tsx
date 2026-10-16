import { ArrowLeft, Archive, ArchiveRestore, Pencil, MessageSquare, MoreHorizontal, Plus, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { SessionSummary } from "../types";
import type { Principal } from "../api";
import { ResearchBrand } from "./ResearchCover";
import { conversationName } from "../researcherLabels";
import { SettingsDialog } from "./SettingsDialog";

type Props = {
  /** Back to the research incubator, shown above "all researches" when the session belongs to a research. */
  onWorkbench?: () => void;
  researchName: string;
  onHome: () => void;
  onRename: (session: SessionSummary) => void;
  principal: Principal;
  onSignedOut?: () => void;
  sessions: SessionSummary[];
  selectedId: string | null;
  open: boolean;
  creating: boolean;
  disabled: boolean;
  onClose: () => void;
  onCreate: () => void;
  onSelect: (id: string) => void;
  onLogout: () => void;
  onManage: (id: string, operation: "archive" | "restore" | "delete") => Promise<void>;
};

export function Sidebar({
  principal, onSignedOut, sessions, selectedId, open, creating, disabled,
  onClose, onCreate, onSelect, onLogout, onManage, researchName, onHome, onRename, onWorkbench,
}: Props) {
  const [archived, setArchived] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<SessionSummary | null>(null);
  const [actionError, setActionError] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const filter = useRef<HTMLButtonElement>(null);
  const visible = sessions.filter(item => !!item.archived === archived);
  useEffect(() => {
    if (deleting) dialog.current?.showModal(); else dialog.current?.close();
  }, [deleting]);
  const changeView = (value: boolean) => { setArchived(value); setExpanded(null); };
  const confirmDelete = async () => {
    if (!deleting) return;
    setDeleteError("");
    try {
      await onManage(deleting.id, "delete");
      dialog.current?.close();
      setDeleting(null); setExpanded(null);
      filter.current?.focus();
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : "删除未完成，请重试。");
    }
  };
  return (
    <>
      {open ? <button className="sidebar-scrim" aria-label="关闭会话导航" onClick={onClose} /> : null}
      <aside className={`sidebar ${open ? "sidebar--open" : ""}`} aria-label="会话导航">
        <div className="sidebar-brand-row">
          <ResearchBrand />
          <button className="icon-button mobile-only" onClick={onClose} aria-label="关闭会话导航">
            <X aria-hidden="true" />
          </button>
        </div>
        {onWorkbench && <button className="research-back" disabled={disabled} onClick={onWorkbench}><ArrowLeft aria-hidden="true" />培养箱</button>}
        <button className="research-back" disabled={disabled} onClick={onHome}><ArrowLeft aria-hidden="true" />所有研究</button>
        <p className="research-side-label" title={researchName}>{researchName}</p>
        <button className="new-analysis" onClick={() => { changeView(false); onCreate(); }} disabled={disabled}>
          <Plus aria-hidden="true" />
          <span>{creating ? "正在创建…" : "新建会话"}</span>
        </button>
        <div className="session-filters" aria-label="会话筛选">
          <button ref={filter} aria-pressed={!archived} onClick={() => changeView(false)}>
            会话 <span>{sessions.filter(item => !item.archived).length}</span>
          </button>
          <button aria-pressed={archived} onClick={() => changeView(true)}>
            已归档 <span>{sessions.filter(item => item.archived).length}</span>
          </button>
        </div>
        <nav className="session-list" aria-label={archived ? "已归档会话" : "当前会话"}>
          {visible.length ? visible.map(session => {
            const title = conversationName(session.title);
            const busy = disabled || ["thinking", "running", "stopping"].includes(session.status || "");
            return <div key={session.id} className="session-item">
              <button
                className={`session-row ${selectedId === session.id ? "session-row--active" : ""}`}
                onClick={() => { setExpanded(null); onSelect(session.id); }}
                aria-current={selectedId === session.id ? "page" : undefined}
                disabled={disabled}
              >
                {archived ? <Archive aria-hidden="true" /> : <MessageSquare aria-hidden="true" />}
                <span title={title}>{title}</span>
              </button>
              <button className="icon-button session-options" aria-label={`会话操作：${title}`}
                aria-expanded={expanded === session.id} aria-controls={`session-actions-${session.id}`}
                disabled={disabled} onClick={() => setExpanded(expanded === session.id ? null : session.id)}>
                <MoreHorizontal aria-hidden="true" />
              </button>
              {expanded === session.id ? <div className="session-actions" id={`session-actions-${session.id}`}
                onKeyDown={event => { if (event.key === "Escape") { setExpanded(null); event.currentTarget.parentElement?.querySelector<HTMLButtonElement>(".session-options")?.focus(); } }}>
                <button disabled={busy} onClick={() => {setExpanded(null); onRename(session);}}><Pencil aria-hidden="true" />重命名</button>
                <button disabled={busy} onClick={() => {
                  setActionError("");
                  void onManage(session.id, session.archived ? "restore" : "archive")
                    .then(() => { setExpanded(null); filter.current?.focus(); }).catch(error => setActionError(error instanceof Error ? error.message : "操作未完成，请重试。"));
                }}>
                  {session.archived ? <ArchiveRestore aria-hidden="true" /> : <Archive aria-hidden="true" />}
                  {session.archived ? "恢复会话" : "归档会话"}
                </button>
                <button className="danger" disabled={busy} onClick={() => { setDeleteError(""); setDeleting(session); }}>
                  <Trash2 aria-hidden="true" />删除会话
                </button>
                {busy && !disabled ? <p>请等待当前工作结束或先停止。</p> : null}
              </div> : null}
            </div>;
          }) : <p className="empty-history">{archived ? "暂无已归档会话。" : "暂无会话。"}</p>}
        </nav>
        {actionError && <p className="research-inline-error" role="alert">{actionError}</p>}
        <SettingsDialog principal={principal} disabled={disabled} onLogout={onLogout} onSignedOut={onSignedOut} />
      </aside>
      <dialog ref={dialog} className="session-delete-dialog" aria-labelledby="session-delete-title"
        aria-describedby="session-delete-description" onCancel={event => {
          if (disabled) event.preventDefault(); else setDeleting(null);
        }}>
        <h2 id="session-delete-title">删除会话？</h2>
        <p className="session-delete-name">{deleting?.title || "Untitled analysis"}</p>
        <p id="session-delete-description">此会话的聊天记录、上传副本和生成结果将被删除，无法恢复。其他会话不受影响。</p>
        {deleteError ? <p role="alert">{deleteError}</p> : null}
        <footer>
          <button autoFocus disabled={disabled} onClick={() => setDeleting(null)}>取消</button>
          <button className="danger" disabled={disabled} onClick={() => void confirmDelete()}>{disabled ? "正在删除…" : "确认删除"}</button>
        </footer>
      </dialog>
    </>
  );
}
