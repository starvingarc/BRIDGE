import { Files, Menu, Pencil, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { formatBytes, type UploadLimits } from "./upload";
import { ApiError, api, type Principal } from "./api";
import { Conversation } from "./components/Conversation";
import { ResultsPane } from "./components/ResultsPane";
import type { FocusTarget } from "./components/WorkspaceFocus";
import { Sidebar } from "./components/Sidebar";
import { ProductIntake } from "./components/ProductIntake";
import { AssessmentPanel } from "./components/AssessmentPanel";
import { BridgeRuntimeProvider } from "./runtime/BridgeRuntimeProvider";
import { ResearchMaterials } from "./components/ResearchMaterials";
import type { Research, ResearchSummary, Session, SessionSummary } from "./types";

const SELECTED_SESSION_KEY = "bridge.preview.selected-session.v1";
const busyStatuses = new Set(["thinking", "running", "stopping"]);
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
      <p>正在打开会话…</p>
    </main>
  );
}

type Props = {
  principal: Principal; onSignedOut: () => void; research: Research | null; researches: ResearchSummary[];
  onHome: () => void; onAssigned: (session: Session) => Promise<void>; initialSessionId?: string;
  /** Returns to this research's incubator; absent for historical sessions without a research. */
  onWorkbench?: () => void;
  /** Reports the open conversation so the address can follow it. */
  onSessionChange?: (sessionId: string) => void;
  initialReport?: boolean;
};

export default function SessionWorkspace({principal, onSignedOut, research, researches, onHome, onAssigned, initialSessionId, onWorkbench, onSessionChange, initialReport = false}: Props) {
  const selectedSessionKey = SELECTED_SESSION_KEY + "." + principal.id + (research ? "." + research.id : "");
  const [researchInfo, setResearchInfo] = useState(research);
  const [materialsOpen, setMaterialsOpen] = useState(false);
  const [materialsUploadId, setMaterialsUploadId] = useState<string | undefined>();
  const openMaterials = (uploadId?: string) => {setMaterialsUploadId(uploadId); setMaterialsOpen(true);};
  const [viewChoice, setViewChoice] = useState<{id: string; view: "conversation" | "results" | "context"} | null>(null);
  const [rename, setRename] = useState<{kind: "research" | "session"; id: string; title: string} | null>(null);
  const [renameError, setRenameError] = useState("");
  const renameDialog = useRef<HTMLDialogElement>(null);
  const [assigning, setAssigning] = useState(false);
  const [assignmentError, setAssignmentError] = useState("");
  const assignmentDialog = useRef<HTMLDialogElement>(null);
  const [authState, setAuthState] = useState<"checking" | "signed-out" | "signed-in">("checking");
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const reportSession = useRef(onSessionChange);
  reportSession.current = onSessionChange;
  useEffect(() => {if (session?.id) reportSession.current?.(session.id);}, [session?.id]);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [action, setAction] = useState<
    "create" | "load" | "upload" | "source" | "approve" | "stop" | "input-review" | "logout" | "manage" | "material" | null
  >(null);
  const [uploadLimits, setUploadLimits] = useState<UploadLimits | null>(null);
  const [uploadLimitError, setUploadLimitError] = useState(false);
  const [uploadFeedback, setUploadFeedback] = useState<{ message: string; error: boolean } | null>(null);
  const uploadLock = useRef(false);
  const managementLock = useRef(false);
  const configRequest = useRef(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [overviewRequest, setOverviewRequest] = useState(0);
  const navigateWorkspace = (target: FocusTarget) => {
    if (target === "overview") {
      if (session) setViewChoice({id: session.id, view: "context"});
      setOverviewRequest(value => value + 1);
      return;
    }
    if (session) setViewChoice({id: session.id, view: "conversation"});
    requestAnimationFrame(() => {
      const element = document.getElementById("workspace-" + target);
      element?.scrollIntoView({ block: "start" });
      element?.focus({ preventScroll: true });
    });
  };
  const [pollGeneration, setPollGeneration] = useState(0);
  const sessionRef = useRef<Session | null>(null);
  const sessionGeneration = useRef(0);
  sessionRef.current = session;

  const advanceSessionGeneration = useCallback(() => {
    const next = sessionGeneration.current + 1;
    sessionGeneration.current = next;
    setPollGeneration(next);
    return next;
  }, []);

  const mergeSession = useCallback((next: Session) => {
    setSession(next);
    localStorage.setItem(selectedSessionKey, next.id);
    setSessions((current) => {
      const summary = { research_id: next.research_id, id: next.id, title: next.title, updated_at: next.updated_at, archived: next.archived, status: next.status };
      return [summary, ...current.filter((item) => item.id !== next.id)].sort((a, b) =>
        b.updated_at.localeCompare(a.updated_at),
      );
    });
  }, []);

  const mergeCurrentSession = useCallback(
    (next: Session, expectedId: string, expectedGeneration: number) => {
      if (
        sessionGeneration.current !== expectedGeneration
        || sessionRef.current?.id !== expectedId
        || next.id !== expectedId
      ) return false;
      mergeSession(next);
      return true;
    },
    [mergeSession],
  );

  const renderGeneration = sessionGeneration.current;
  const acceptChildSession = useCallback(
    (next: Session) => {
      mergeCurrentSession(next, next.id, renderGeneration);
    },
    [mergeCurrentSession, renderGeneration],
  );

  const handleAuthError = useCallback((error: unknown) => {
    if (error instanceof ApiError && error.status === 401) {
      sessionGeneration.current += 1;
      configRequest.current += 1;
      setAuthState("signed-out");
      setSession(null);
      setSessions([]);
      onSignedOut();
    }
  }, [onSignedOut]);

  const handleActionError = useCallback(
    (error: unknown) => {
      handleAuthError(error);
      setNotice(publicError(error));
    },
    [handleAuthError],
  );

  const loadUploadLimits = useCallback(async (signal?: AbortSignal) => {
    const id = sessionRef.current?.id;
    const request = ++configRequest.current;
    const current = () => request === configRequest.current
      && id === sessionRef.current?.id;
    setUploadLimits(null);
    setUploadLimitError(false);
    try {
      const limits = await api.uploadConfig(signal ?? AbortSignal.timeout(15_000));
      if (!current()) return null;
      setUploadLimits(limits);
      return limits;
    } catch (error) {
      if (!current()) return null;
      handleAuthError(error);
      setUploadLimitError(true);
      return null;
    }
  }, [handleAuthError]);

  useEffect(() => {
    setUploadFeedback(null);
    setUploadLimits(null);
    setUploadLimitError(false);
    if (authState !== "signed-in" || !session?.id) return;
    const controller = new AbortController();

    // Invalidate results on a session/auth change, including fetch mocks that ignore abort.
    void loadUploadLimits(AbortSignal.any([controller.signal, AbortSignal.timeout(15_000)]));
    return () => { configRequest.current += 1; controller.abort(); };
  }, [authState, session?.id, loadUploadLimits]);

  const openWorkspace = useCallback(async () => {
    const operationGeneration = advanceSessionGeneration();
    const response = await api.listSessions();
    if (sessionGeneration.current !== operationGeneration) return;
    setSessions(response.sessions.filter(item => (item.research_id ?? null) === (research?.id ?? null)));
    setAuthState("signed-in");
    const saved = localStorage.getItem(selectedSessionKey);
    const active = response.sessions.filter(item => !item.archived && (item.research_id ?? null) === (research?.id ?? null));
    const selected = active.find(item => item.id === initialSessionId) ?? active.find((item) => item.id === saved) ?? active[0];
    if (!selected) {
      localStorage.removeItem(selectedSessionKey);
      setSession(null);
      return;
    }
    try {
      const next = await api.getSession(selected.id);
      if (sessionGeneration.current === operationGeneration) mergeSession(next);
    } catch (error) {
      if (sessionGeneration.current !== operationGeneration) return;
      if (error instanceof ApiError && error.status === 401) throw error;
      setSession(null);
      setNotice(publicError(error));
    }
  }, [advanceSessionGeneration, mergeSession]);

  useEffect(() => {
    let active = true;
    openWorkspace().catch((error: unknown) => {
      if (!active) return;
      if (error instanceof ApiError && error.status === 401) {
        handleAuthError(error);
      } else {
        setAuthState("signed-out");
        setWorkspaceError(publicError(error));
      }
    });
    return () => {
      active = false;
      sessionGeneration.current += 1;
      configRequest.current += 1;
    };
  }, [openWorkspace, handleAuthError]);

  useEffect(() => {
    const sessionId = session?.id;
    if (!sessionId || !busyStatuses.has(session.status)) return;

    let cancelled = false;
    let controller: AbortController | null = null;
    let timer: number | null = null;
    let failedAttempts = 0;
    const operationGeneration = sessionGeneration.current;

    const schedule = (delay: number) => {
      timer = window.setTimeout(poll, delay);
    };

    const poll = async () => {
      controller = new AbortController();
      try {
        const next = await api.getSession(sessionId, controller.signal);
        if (
          cancelled
          || sessionGeneration.current !== operationGeneration
          || sessionRef.current?.id !== sessionId
        ) return;
        failedAttempts = 0;
        mergeSession(next);
        if (busyStatuses.has(next.status)) schedule(POLL_INTERVAL_MS);
      } catch (error) {
        if (
          cancelled
          || sessionGeneration.current !== operationGeneration
          || (error as { name?: string }).name === "AbortError"
        ) return;
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
  }, [handleActionError, mergeSession, pollGeneration, session?.id, session?.status]);

  const logout = async () => {
    const operationGeneration = advanceSessionGeneration();
    setAction("logout");
    setNotice(null);
    try {
      await api.logout();
      if (sessionGeneration.current !== operationGeneration) return;
      localStorage.removeItem(selectedSessionKey);
      setAuthState("signed-out");
      setSession(null);
      setSessions([]);
      onSignedOut();
    } catch (error) {
      if (sessionGeneration.current === operationGeneration) handleActionError(error);
    } finally {
      if (sessionGeneration.current === operationGeneration) setAction(null);
    }
  };

  const createSession = async () => {
    const operationGeneration = advanceSessionGeneration();
    setAction("create");
    setNotice(null);
    try {
      const next = await api.createSession(research?.id);
      if (sessionGeneration.current !== operationGeneration) return;
      mergeSession(next);
      setSidebarOpen(false);
    } catch (error) {
      if (sessionGeneration.current === operationGeneration) handleActionError(error);
    } finally {
      if (sessionGeneration.current === operationGeneration) setAction(null);
    }
  };

  const selectSession = async (id: string) => {
    if (session?.id === id) {
      setSidebarOpen(false);
      return;
    }
    const operationGeneration = advanceSessionGeneration();
    setAction("load");
    setNotice(null);
    try {
      const next = await api.getSession(id);
      if (sessionGeneration.current !== operationGeneration) return;
      mergeSession(next);
      setSidebarOpen(false);
    } catch (error) {
      if (sessionGeneration.current === operationGeneration) handleActionError(error);
    } finally {
      if (sessionGeneration.current === operationGeneration) setAction(null);
    }
  };

  const manageSession = async (id: string, operation: "archive" | "restore" | "delete") => {
    if (managementLock.current || action !== null) throw new Error("请等待当前操作完成。");
    managementLock.current = true;
    let operationGeneration = sessionGeneration.current;
    setAction("manage");
    setNotice(null);
    try {
      if (operation === "delete") {
        await api.deleteSession(id);
        if (sessionGeneration.current !== operationGeneration) return;
        setSessions(current => current.filter(item => item.id !== id));
      } else {
        const summary = await api.archiveSession(id, operation === "archive");
        if (sessionGeneration.current !== operationGeneration) return;
        setSessions(current => current.map(item => item.id === id ? summary : item));
        if (operation === "restore" && sessionRef.current?.id === id) {
          setSession(current => current?.id === id ? { ...current, ...summary } : current);
        }
      }
      if (operation !== "restore" && sessionRef.current?.id === id) {
        // Fence only after the current session was successfully removed from view.
        // Unrelated management (or a refusal) must not discard in-flight replies.
        operationGeneration = advanceSessionGeneration();
        sessionRef.current = null;
        setSession(null);
        localStorage.removeItem(selectedSessionKey);
      }
    } catch (error) {
      if (sessionGeneration.current === operationGeneration) handleActionError(error);
      throw error;
    } finally {
      managementLock.current = false;
      if (sessionGeneration.current === operationGeneration) setAction(null);
    }
  };

  const upload = async (file: File) => {
    if (!session || action !== null || uploadLock.current || busyStatuses.has(session.status) || !uploadLimits) return;
    const operationSession = session.id;
    const operationGeneration = sessionGeneration.current;
    const current = () => sessionGeneration.current === operationGeneration && sessionRef.current?.id === operationSession;
    uploadLock.current = true;
    setAction("upload");
    setNotice(null);
    setUploadFeedback({ message: "Checking the current upload limit…", error: false });
    try {
      const limits = await loadUploadLimits();
      if (!current()) return;
      if (!limits) {
        setUploadFeedback(null);
        return;
      }
      if (file.size > limits.max_upload_bytes) {
        setUploadFeedback({ message: "This file is " + formatBytes(file.size) + "; the current limit is "
          + formatBytes(limits.max_upload_bytes) + ". No file data was sent. Choose a smaller file or ask the operator to review the limit.", error: true });
        return;
      }
      setUploadFeedback({ message: "Uploading " + file.name + " (" + formatBytes(file.size)
        + ") and checking the file. Please keep this page open…", error: false });
      const next = await api.upload(operationSession, file);
      if (mergeCurrentSession(next, operationSession, operationGeneration)) {
        setUploadFeedback({ message: "File received. Review the data details in the assessment overview.", error: false });
      }
    } catch (error) {
      if (!current()) return;
      handleAuthError(error);
      setUploadFeedback({ message: publicError(error), error: true });
    } finally {
      uploadLock.current = false;
      if (current()) setAction(null);
    }
  };

  const setSourceInput = async (uploadId: string, sourceFamilyId: string) => {
    if (!session) return;
    const operationSession = session.id;
    const operationGeneration = sessionGeneration.current;
    setAction("source");
    setNotice(null);
    try {
      const next = await api.setSourceInput(operationSession, uploadId, sourceFamilyId);
      if (mergeCurrentSession(next, operationSession, operationGeneration)) {
        setNotice(next.pending_input_change
          ? "Source change staged for confirmation."
          : "Source input already matches the current declaration.");
      }
    } catch (error) {
      if (sessionGeneration.current === operationGeneration) handleActionError(error);
    } finally {
      if (sessionGeneration.current === operationGeneration) setAction(null);
    }
  };

  const approve = async () => {
    if (!session?.plan || session.input_review_required) return;
    const operationSession = session.id;
    const operationGeneration = sessionGeneration.current;
    setAction("approve");
    setNotice(null);
    try {
      const next = await api.approvePlan(
        operationSession,
        session.plan.id,
        session.plan.digest,
      );
      mergeCurrentSession(next, operationSession, operationGeneration);
    } catch (error) {
      if (sessionGeneration.current === operationGeneration) handleActionError(error);
    } finally {
      if (sessionGeneration.current === operationGeneration) setAction(null);
    }
  };

  const stop = async () => {
    if (!session || session.status === "stopping") return;
    const operationSession = session.id;
    const operationGeneration = advanceSessionGeneration();
    setAction("stop");
    setNotice(null);
    try {
      const next = await api.stopSession(operationSession);
      mergeCurrentSession(next, operationSession, operationGeneration);
    } catch (error) {
      if (sessionGeneration.current === operationGeneration) handleActionError(error);
    } finally {
      if (sessionGeneration.current === operationGeneration) setAction(null);
    }
  };

  const resolveInputReview = async (resolution: "confirm" | "discard" | "keep") => {
    if (!session) return;
    const pending = session.pending_input_change;
    if (resolution !== "keep" && !pending) return;
    const operationSession = session.id;
    const operationGeneration = advanceSessionGeneration();
    setAction("input-review");
    setNotice(null);
    try {
      const next = resolution === "confirm"
        ? await api.confirmInputChange(operationSession, pending!.id, pending!.digest)
        : resolution === "discard"
          ? await api.discardInputChange(operationSession, pending!.id, pending!.digest)
          : await api.keepCurrentInputs(operationSession);
      mergeCurrentSession(next, operationSession, operationGeneration);
    } catch (error) {
      if (sessionGeneration.current === operationGeneration) handleActionError(error);
    } finally {
      if (sessionGeneration.current === operationGeneration) setAction(null);
    }
  };

  useEffect(() => {if (rename) renameDialog.current?.showModal(); else renameDialog.current?.close();}, [rename]);
  useEffect(() => {if (assigning) assignmentDialog.current?.showModal(); else assignmentDialog.current?.close();}, [assigning]);
  const saveName = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (!rename || action) return;
    const title = String(new FormData(event.currentTarget).get("title") ?? "").trim();
    if (!title) {setRenameError("请填写名称。"); return;}
    const generation = sessionGeneration.current;
    setAction("manage"); setRenameError("");
    try {
      if (rename.kind === "research" && researchInfo) {
        const next = await api.renameResearch(researchInfo.id, title, researchInfo.description);
        if (sessionGeneration.current === generation) setResearchInfo(next);
      } else {
        const next = await api.renameSession(rename.id, title);
        if (sessionGeneration.current === generation) {
          if (sessionRef.current?.id === next.id) mergeSession(next);
          else setSessions(items => items.map(item => item.id === next.id ? {...item, title: next.title} : item));
        }
      }
      if (sessionGeneration.current === generation) setRename(null);
    } catch (failure) {handleAuthError(failure); if (sessionGeneration.current === generation) setRenameError(publicError(failure));}
    finally {if (sessionGeneration.current === generation) setAction(null);}
  };
  const assign = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (!session || action) return;
    const researchId = String(new FormData(event.currentTarget).get("research") ?? "");
    if (!researchId) return;
    setAction("manage"); setAssignmentError("");
    try {
      const next = await api.assignResearch(session.id, researchId);
      await onAssigned(next);
      setAssigning(false);
    } catch (failure) {handleAuthError(failure); setAssignmentError(publicError(failure));}
    finally {setAction(null);}
  };
  const hasResults = !!session && (session.artifacts.length > 0 || !!session.assessment);
  const view = session && viewChoice?.id === session.id ? viewChoice.view
    : initialReport || (session?.presentation?.stage === "results_ready" && hasResults) ? "results" : "conversation";
  const chooseView = (next: "conversation" | "results" | "context") => {
    if (session) setViewChoice({id: session.id, view: next});
    if (next === "context") setOverviewRequest(value => value + 1);
  };

  if (authState === "checking") return <LoadingScreen />;
  if (authState === "signed-out") {
    return workspaceError ? <main className="loading-screen"><p role="alert">{workspaceError}</p>
      <button onClick={() => window.location.reload()}>重新加载</button></main> : null;
  }

  const sessionBusy = session ? busyStatuses.has(session.status) : false;
  return (
    <main className="app-shell research-shell">
      <Sidebar
        onWorkbench={onWorkbench}
        principal={principal}
        onSignedOut={onSignedOut}
        sessions={sessions}
        selectedId={session?.id ?? null}
        open={sidebarOpen}
        creating={action === "create"}
        disabled={action !== null}
        onClose={() => setSidebarOpen(false)}
        onCreate={createSession}
        onSelect={selectSession}
        onLogout={logout}
        onManage={manageSession}
        researchName={researchInfo?.name ?? "历史会话"}
        onHome={onHome}
        onRename={item => {setRenameError(""); setRename({kind: "session", id: item.id, title: item.title});}}
      />
      <div className="research-session-main">
        <header className="research-workspace-bar">
          <div className="research-workspace-heading"><button className="icon-button mobile-only" aria-label="打开会话导航" onClick={() => setSidebarOpen(true)}><Menu aria-hidden="true" /></button>
            <span className="research-workspace-name">{researchInfo?.name ?? "历史会话"}</span>
            {researchInfo && <button className="icon-button" aria-label="修改研究名称" disabled={action !== null} onClick={() => {setRenameError(""); setRename({kind: "research", id: researchInfo.id, title: researchInfo.name});}}><Pencil size={13} aria-hidden="true" /></button>}
          </div>
          <div className="research-workspace-controls">{session && <nav aria-label="工作区视图">
            <button aria-pressed={view === "conversation"} onClick={() => chooseView("conversation")}>对话</button>
            <button aria-pressed={view === "context"} onClick={() => chooseView("context")}>实验背景</button>
            <button aria-pressed={view === "results"} disabled={!hasResults} onClick={() => chooseView("results")}>结果</button>
          </nav>}
          {researchInfo ? <button className="research-materials-trigger" onClick={() => openMaterials()} aria-label="研究资料"><Files aria-hidden="true" />研究资料</button>
            : session && <button disabled={action !== null} onClick={() => {setAssignmentError(""); setAssigning(true);}}>移入研究</button>}
          </div>
        </header>
      <div className={`workspace research-workspace research-workspace--${view}`} data-view={view}>
        {session ? (
          <BridgeRuntimeProvider
            session={session}
            disabled={sessionBusy || action !== null}
            onSession={acceptChildSession}
            onError={handleActionError}
          >
            <Conversation
              session={session}
              onReviewContext={() => navigateWorkspace("overview")}
              onOpenMaterials={researchInfo ? openMaterials : undefined}
              onRename={() => {setRenameError(""); setRename({kind: "session", id: session.id, title: session.title});}}
              busy={sessionBusy || action !== null}
              uploadBusy={action === "upload"}
              uploadLimits={uploadLimits}
              uploadLimitError={uploadLimitError}
              uploadFeedback={uploadFeedback}
              onRetryUploadLimits={() => void loadUploadLimits()}
              approveBusy={action !== null}
              stopBusy={action === "stop"}
              onOpenSidebar={() => setSidebarOpen(true)}
              onUpload={upload}
              onSourceInput={setSourceInput}
              onApprove={approve}
              onStop={stop}
              onConfirmInputChange={() => void resolveInputReview("confirm")}
              onDiscardInputChange={() => void resolveInputReview("discard")}
              onKeepCurrentInputs={() => void resolveInputReview("keep")}
              onSession={acceptChildSession}
              onError={handleActionError}
            />
          </BridgeRuntimeProvider>
        ) : (
          <section className="research-empty-workspace"><span className="research-brand-orb" aria-hidden="true" />
            <h1>开始第一段讨论</h1><p>从一个问题、一个想法，或一份资料开始。</p>
            <button className="research-primary" onClick={() => void createSession()} disabled={action !== null}>{action === "create" ? "正在创建…" : "开始会话"}</button>
          </section>
        )}
        {session && view !== "conversation" && <div className="results-wrap">
          <ResultsPane key={session?.id ?? "empty"} session={session} workspaceView={view} overviewRequest={overviewRequest} initialTab={initialReport ? "report" : undefined}
            onNavigate={navigateWorkspace} overview={session ? (openGraph, openReports) => (
            <><AssessmentPanel key={session.id} session={session} busy={sessionBusy || action !== null}
              onSession={acceptChildSession} onError={handleActionError} onOpenGraph={openGraph} onOpenReports={openReports} />
            <ProductIntake session={session} onOpenMaterials={researchInfo ? openMaterials : undefined} busy={sessionBusy || action !== null}
              onSession={acceptChildSession} onError={handleActionError}
              onConfirm={() => void resolveInputReview("confirm")}
              onDiscard={() => void resolveInputReview("discard")} /></>
          ) : undefined} />
        </div>}
      </div>
      </div>
      {materialsOpen && researchInfo && <ResearchMaterials researchId={researchInfo.id} session={session} initialUploadId={materialsUploadId}
        disabled={sessionBusy || (action !== null && action !== "material")}
        onClose={() => {setMaterialsOpen(false); document.querySelector<HTMLButtonElement>(".research-materials-trigger")?.focus();}}
        onBusy={busy => setAction(busy ? "material" : null)} onSession={acceptChildSession} onError={handleAuthError} />}
      <dialog ref={renameDialog} className="research-dialog" aria-labelledby="workspace-rename-title" onCancel={event => {if (action) event.preventDefault(); else setRename(null);}}>
        <header><h2 id="workspace-rename-title">{rename?.kind === "research" ? "研究名称" : "会话名称"}</h2><button className="icon-button" aria-label="关闭名称编辑" disabled={action !== null} onClick={() => setRename(null)}><X aria-hidden="true" /></button></header>
        {rename && <form onSubmit={saveName}><label>名称<input key={rename.kind + rename.id} name="title" defaultValue={rename.title === "New analysis" ? "新会话" : rename.title} maxLength={160} required autoFocus disabled={action !== null} /></label>
          {renameError && <p role="alert">{renameError}</p>}<footer><button type="button" disabled={action !== null} onClick={() => setRename(null)}>取消</button><button className="research-primary" disabled={action !== null} type="submit">{action ? "正在保存…" : "保存名称"}</button></footer></form>}
      </dialog>
      <dialog ref={assignmentDialog} className="research-dialog" aria-labelledby="workspace-assign-title" onCancel={event => {if (action) event.preventDefault(); else setAssigning(false);}}>
        <header><h2 id="workspace-assign-title">移入研究</h2><button className="icon-button" aria-label="关闭研究选择" disabled={action !== null} onClick={() => setAssigning(false)}><X aria-hidden="true" /></button></header>
        {researches.length ? <form onSubmit={assign}><label>选择研究<select name="research" disabled={action !== null}>{researches.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><p>聊天与分析记录保留。已有原始文件可在研究资料中按需共享。</p>
          {assignmentError && <p role="alert">{assignmentError}</p>}<footer><button type="button" disabled={action !== null} onClick={() => setAssigning(false)}>取消</button><button className="research-primary" type="submit" disabled={action !== null}>{action ? "正在移入…" : "确认移入"}</button></footer></form>
          : <div><p>还没有研究，请先创建一项研究。</p><button onClick={onHome}>返回所有研究</button></div>}
      </dialog>
      {notice ? (
        <div className="notice" role="alert">
          <span>{notice}</span>
          <button onClick={() => setNotice(null)} aria-label="Dismiss">×</button>
        </div>
      ) : null}
    </main>
  );
}
