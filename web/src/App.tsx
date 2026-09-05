import { Menu, Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "./api";
import { Conversation } from "./components/Conversation";
import { LoginScreen } from "./components/LoginScreen";
import { ResultsPane, WorkbenchDivider } from "./components/ResultsPane";
import { Sidebar } from "./components/Sidebar";
import { BridgeRuntimeProvider } from "./runtime/BridgeRuntimeProvider";
import type { Session, SessionSummary } from "./types";

const SELECTED_SESSION_KEY = "bridge.preview.selected-session.v1";
const busyStatuses = new Set(["thinking", "running"]);
const POLL_INTERVAL_MS = 1_250;
const MAX_POLL_RETRY_MS = 8_000;

function publicError(error: unknown) {
  return error instanceof ApiError ? error.message : "The request could not be completed. Please try again.";
}

function LoadingScreen() {
  return (
    <main className="loading-screen" aria-live="polite">
      <div className="brand">BRIDGE</div>
      <div className="loading-line" />
      <p>Opening private workspace…</p>
    </main>
  );
}

function EmptyConversation({
  onOpenSidebar,
  onCreate,
  creating,
}: {
  onOpenSidebar: () => void;
  onCreate: () => void;
  creating: boolean;
}) {
  return (
    <section className="conversation-pane empty-workspace">
      <header className="conversation-header">
        <button className="icon-button mobile-only" onClick={onOpenSidebar} aria-label="Open analyses">
          <Menu aria-hidden="true" />
        </button>
        <div className="conversation-title">
          <h1>New assessment</h1>
        </div>
      </header>
      <div className="empty-workspace-content">
        <h2>No analysis selected</h2>
        <p>Create an analysis to begin a private conversation.</p>
        <button onClick={onCreate} disabled={creating}>
          <Plus aria-hidden="true" />
          {creating ? "Creating…" : "New analysis"}
        </button>
      </div>
    </section>
  );
}

export default function App() {
  const [authState, setAuthState] = useState<"checking" | "signed-out" | "signed-in">("checking");
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [action, setAction] = useState<"create" | "load" | "upload" | "approve" | "logout" | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [resultsWidth, setResultsWidth] = useState(() =>
    Math.max(420, Math.min(620, Math.round(window.innerWidth * 0.4))),
  );

  const mergeSession = useCallback((next: Session) => {
    setSession(next);
    localStorage.setItem(SELECTED_SESSION_KEY, next.id);
    setSessions((current) => {
      const summary = { id: next.id, title: next.title, updated_at: next.updated_at };
      return [summary, ...current.filter((item) => item.id !== next.id)].sort((a, b) =>
        b.updated_at.localeCompare(a.updated_at),
      );
    });
  }, []);

  const handleAuthError = useCallback((error: unknown) => {
    if (error instanceof ApiError && error.status === 401) {
      setAuthState("signed-out");
      setSession(null);
      setSessions([]);
    }
  }, []);

  const handleActionError = useCallback(
    (error: unknown) => {
      handleAuthError(error);
      setNotice(publicError(error));
    },
    [handleAuthError],
  );

  const openWorkspace = useCallback(async () => {
    const response = await api.listSessions();
    setSessions(response.sessions);
    setAuthState("signed-in");
    const saved = localStorage.getItem(SELECTED_SESSION_KEY);
    const selected = response.sessions.find((item) => item.id === saved) ?? response.sessions[0];
    if (!selected) {
      setSession(null);
      return;
    }
    try {
      mergeSession(await api.getSession(selected.id));
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) throw error;
      setSession(null);
      setNotice(publicError(error));
    }
  }, [mergeSession]);

  useEffect(() => {
    let active = true;
    openWorkspace().catch((error: unknown) => {
      if (!active) return;
      if (error instanceof ApiError && error.status === 401) {
        setAuthState("signed-out");
      } else {
        setAuthState("signed-out");
        setLoginError(publicError(error));
      }
    });
    return () => {
      active = false;
    };
  }, [openWorkspace]);

  useEffect(() => {
    const sessionId = session?.id;
    if (!sessionId || !busyStatuses.has(session.status)) return;

    let cancelled = false;
    let controller: AbortController | null = null;
    let timer: number | null = null;
    let failedAttempts = 0;

    const schedule = (delay: number) => {
      timer = window.setTimeout(poll, delay);
    };

    const poll = async () => {
      controller = new AbortController();
      try {
        const next = await api.getSession(sessionId, controller.signal);
        if (cancelled) return;
        failedAttempts = 0;
        mergeSession(next);
        if (busyStatuses.has(next.status)) schedule(POLL_INTERVAL_MS);
      } catch (error) {
        if (cancelled || (error as { name?: string }).name === "AbortError") return;
        handleActionError(error);
        if (error instanceof ApiError && error.status === 401) return;
        failedAttempts += 1;
        schedule(Math.min(MAX_POLL_RETRY_MS, POLL_INTERVAL_MS * 2 ** failedAttempts));
      }
    };

    schedule(POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      controller?.abort();
      if (timer !== null) window.clearTimeout(timer);
    };
  }, [handleActionError, mergeSession, session?.id, session?.status]);

  const login = async (token: string) => {
    setAction("load");
    setLoginError(null);
    try {
      await api.login(token);
      await openWorkspace();
    } catch (error) {
      setLoginError(publicError(error));
      handleAuthError(error);
    } finally {
      setAction(null);
    }
  };

  const logout = async () => {
    setAction("logout");
    setNotice(null);
    try {
      await api.logout();
      localStorage.removeItem(SELECTED_SESSION_KEY);
      setAuthState("signed-out");
      setSession(null);
      setSessions([]);
    } catch (error) {
      handleActionError(error);
    } finally {
      setAction(null);
    }
  };

  const createSession = async () => {
    setAction("create");
    setNotice(null);
    try {
      mergeSession(await api.createSession());
      setSidebarOpen(false);
    } catch (error) {
      handleActionError(error);
    } finally {
      setAction(null);
    }
  };

  const selectSession = async (id: string) => {
    if (session?.id === id) {
      setSidebarOpen(false);
      return;
    }
    setAction("load");
    setNotice(null);
    try {
      mergeSession(await api.getSession(id));
      setSidebarOpen(false);
    } catch (error) {
      handleActionError(error);
    } finally {
      setAction(null);
    }
  };

  const upload = async (file: File) => {
    if (!session) return;
    setAction("upload");
    setNotice(null);
    try {
      mergeSession(await api.upload(session.id, file));
    } catch (error) {
      handleActionError(error);
    } finally {
      setAction(null);
    }
  };

  const approve = async () => {
    if (!session?.plan) return;
    setAction("approve");
    setNotice(null);
    try {
      mergeSession(await api.approvePlan(session.id, session.plan.id, session.plan.digest));
    } catch (error) {
      handleActionError(error);
    } finally {
      setAction(null);
    }
  };

  if (authState === "checking") return <LoadingScreen />;
  if (authState === "signed-out") {
    return <LoginScreen busy={action === "load"} error={loginError} onLogin={login} />;
  }

  const sessionBusy = session ? busyStatuses.has(session.status) : false;
  return (
    <main className="app-shell">
      <Sidebar
        sessions={sessions}
        selectedId={session?.id ?? null}
        open={sidebarOpen}
        creating={action === "create"}
        disabled={action !== null}
        onClose={() => setSidebarOpen(false)}
        onCreate={createSession}
        onSelect={selectSession}
        onLogout={logout}
      />
      <div className="workspace">
        {session ? (
          <BridgeRuntimeProvider
            session={session}
            disabled={sessionBusy || action !== null}
            onSession={mergeSession}
            onError={handleActionError}
          >
            <Conversation
              session={session}
              busy={sessionBusy || action !== null}
              uploadBusy={action === "upload"}
              approveBusy={action !== null}
              onOpenSidebar={() => setSidebarOpen(true)}
              onUpload={upload}
              onApprove={approve}
            />
          </BridgeRuntimeProvider>
        ) : (
          <EmptyConversation
            onOpenSidebar={() => setSidebarOpen(true)}
            onCreate={createSession}
            creating={action === "create"}
          />
        )}
        <WorkbenchDivider width={resultsWidth} onWidth={setResultsWidth} />
        <div className="results-wrap" style={{ width: resultsWidth }}>
          <ResultsPane session={session} />
        </div>
      </div>
      {notice ? (
        <div className="notice" role="alert">
          <span>{notice}</span>
          <button onClick={() => setNotice(null)} aria-label="Dismiss">×</button>
        </div>
      ) : null}
    </main>
  );
}
