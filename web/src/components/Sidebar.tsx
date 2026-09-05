import { LogOut, MessageSquare, Plus, X } from "lucide-react";
import type { SessionSummary } from "../types";

type Props = {
  sessions: SessionSummary[];
  selectedId: string | null;
  open: boolean;
  creating: boolean;
  disabled: boolean;
  onClose: () => void;
  onCreate: () => void;
  onSelect: (id: string) => void;
  onLogout: () => void;
};

export function Sidebar({
  sessions,
  selectedId,
  open,
  creating,
  disabled,
  onClose,
  onCreate,
  onSelect,
  onLogout,
}: Props) {
  return (
    <>
      {open ? <button className="sidebar-scrim" aria-label="Close analyses" onClick={onClose} /> : null}
      <aside className={`sidebar ${open ? "sidebar--open" : ""}`} aria-label="Analysis history">
        <div className="sidebar-brand-row">
          <div className="brand">BRIDGE</div>
          <button className="icon-button mobile-only" onClick={onClose} aria-label="Close analyses">
            <X aria-hidden="true" />
          </button>
        </div>
        <button className="new-analysis" onClick={onCreate} disabled={disabled}>
          <Plus aria-hidden="true" />
          <span>{creating ? "Creating…" : "New analysis"}</span>
        </button>
        <div className="sidebar-label">Sessions</div>
        <nav className="session-list">
          {sessions.length ? (
            sessions.map((session) => (
              <button
                key={session.id}
                className={`session-row ${selectedId === session.id ? "session-row--active" : ""}`}
                onClick={() => onSelect(session.id)}
                aria-current={selectedId === session.id ? "page" : undefined}
                disabled={disabled}
              >
                <MessageSquare aria-hidden="true" />
                <span>{session.title || "Untitled analysis"}</span>
              </button>
            ))
          ) : (
            <p className="empty-history">No analyses yet.</p>
          )}
        </nav>
        <button className="sidebar-logout" onClick={onLogout} disabled={disabled}>
          <LogOut aria-hidden="true" />
          <span>Sign out</span>
        </button>
      </aside>
    </>
  );
}
