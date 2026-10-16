import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, type Principal } from "./api";
import type { Research, ResearchSummary, Session } from "./types";
import { ResearchHome } from "./components/ResearchHome";
import SessionWorkspace from "./SessionWorkspace";
import { ResearchWorkbench } from "./workbench/ResearchWorkbench";
import { useHashRoute } from "./routes";

const message = (error: unknown) => error instanceof Error ? error.message : "请求未完成，请重试。";

/** The research a user opened last, remembered in this browser only; any storage failure just forgets it. */
const lastKey = (user: string) => `bridge.lastResearch.${user}`;
const readLast = (user: string) => { try { return localStorage.getItem(lastKey(user)); } catch { return null; } };
const writeLast = (user: string, id: string) => { try { localStorage.setItem(lastKey(user), id); } catch { /* not remembered */ } };

export default function App({principal, onSignedOut}: {principal: Principal; onSignedOut: () => void}) {
  const [researches, setResearches] = useState<ResearchSummary[]>([]);
  const [legacyCount, setLegacyCount] = useState(0);
  const [route, navigate] = useHashRoute();
  const [loaded, setLoaded] = useState<Research | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Why the last address could not be opened; kept apart so reloading the list does not erase it.
  const [openError, setOpenError] = useState<string | null>(null);
  // Signing in lands in the incubator of the research used last; the research list stays one step away in the rail.
  const [landing, setLanding] = useState(route.kind === "home");
  const generation = useRef(0);
  const directoryGeneration = useRef(0);
  const mounted = useRef(true);
  const authFailure = useCallback((failure: unknown) => {
    if (failure instanceof ApiError && failure.status === 401) onSignedOut();
  }, [onSignedOut]);
  const refresh = useCallback(async () => {
    const current = ++directoryGeneration.current;
    setLoading(true); setError(null);
    try {
      const [directory, history] = await Promise.all([api.listResearches(), api.listSessions()]);
      if (!mounted.current || current !== directoryGeneration.current) return;
      setResearches(directory.researches);
      setLegacyCount(history.sessions.filter(item => !item.research_id).length);
    } catch (failure) {
      if (!mounted.current || current !== directoryGeneration.current) return;
      authFailure(failure); setError(message(failure));
    } finally {if (mounted.current && current === directoryGeneration.current) setLoading(false);}
  }, [authFailure]);
  useEffect(() => {
    mounted.current = true;
    return () => {mounted.current = false; generation.current += 1; directoryGeneration.current += 1;};
  }, []);
  // The list loads once on entry and again whenever the user comes back to it.
  const atHome = route.kind === "home";
  const listed = useRef(false);
  useEffect(() => {
    if (atHome || !listed.current) {listed.current = true; void refresh();}
  }, [atHome, refresh]);
  useEffect(() => {
    if (!landing || route.kind !== "home" || loading) return;
    setLanding(false);
    if (!researches.length) return;
    const last = readLast(principal.id);
    const id = researches.some(item => item.id === last) ? last! : researches[0].id;
    navigate({kind: "research", id, at: {view: "wall", focus: null}}, {replace: true});
  }, [landing, loading, researches, route.kind, principal.id, navigate]);
  useEffect(() => { if (route.kind === "research") writeLast(principal.id, route.id); }, [route, principal.id]);
  // The address names the research; load it when it changes. A missing one returns to the list with the reason.
  const wanted = route.kind === "research" || route.kind === "sessions" ? route.id : null;
  useEffect(() => {
    if (!wanted) {generation.current += 1; setLoaded(null); return;}
    if (loaded?.id === wanted) return;
    const current = ++generation.current;
    setOpenError(null);
    api.getResearch(wanted).then(research => {
      if (mounted.current && current === generation.current) setLoaded(research);
    }, failure => {
      if (!mounted.current || current !== generation.current) return;
      authFailure(failure); setOpenError(message(failure)); navigate({kind: "home"}, {replace: true});
    });
  }, [wanted, loaded?.id, authFailure, navigate]);
  const home = () => navigate({kind: "home"});
  const create = async (name: string, description: string) => {
    const current = ++generation.current;
    try {
      const research = await api.createResearch(name, description);
      if (mounted.current && current === generation.current) {
        setResearches(items => [research, ...items]); setLoaded(research);
        navigate({kind: "research", id: research.id, at: {view: "wall", focus: null}});
      }
    } catch (failure) {authFailure(failure); throw failure;}
  };
  const logout = async () => {
    generation.current += 1;
    try {await api.logout(); onSignedOut();}
    catch (failure) {authFailure(failure); setError(message(failure));}
  };
  const research = loaded && loaded.id === wanted ? loaded : null;
  if (route.kind === "research" && research) return <ResearchWorkbench principal={principal} research={research} onHome={home}
    onLogout={() => void logout()} onSignedOut={onSignedOut}
    location={route.at} onLocate={at => navigate({kind: "research", id: research.id, at})}
    onSessions={sessionId => navigate({kind: "sessions", id: research.id, session: sessionId ?? null})}
    onReports={() => navigate({kind: "sessions", id: research.id, session: null, report: true})} />;
  const sessions = route.kind === "sessions" && research ? research : route.kind === "history" ? null : undefined;
  if (sessions !== undefined) return <SessionWorkspace key={`${sessions?.id ?? "historical"}:${route.kind === "sessions" && route.report ? "report" : "session"}`}
    initialReport={route.kind === "sessions" && route.report}
    onWorkbench={sessions ? () => navigate({kind: "research", id: sessions.id, at: {view: "wall", focus: null}}) : undefined}
    principal={principal} onSignedOut={onSignedOut} research={sessions}
    initialSessionId={route.kind === "sessions" || route.kind === "history" ? route.session ?? undefined : undefined}
    onSessionChange={id => navigate(sessions ? {kind: "sessions", id: sessions.id, session: id, ...(route.kind === "sessions" && route.report ? {report: true as const} : {})} : {kind: "history", session: id}, {replace: true})}
    researches={researches} onHome={home}
    onAssigned={async (session: Session) => {if (session.research_id) navigate({kind: "sessions", id: session.research_id, session: session.id});}}
  />;
  if (landing && route.kind === "home") return <main className="wb-app research-home-wb"><p className="wb-muted" role="status">正在打开研究空间…</p></main>;
  return <ResearchHome principal={principal} researches={researches} legacyCount={legacyCount}
    loading={loading || wanted !== null} error={error ?? openError} onRetry={() => {setOpenError(null); void refresh();}}
    onOpen={id => navigate({kind: "research", id, at: {view: "wall", focus: null}})}
    onLegacy={() => navigate({kind: "history", session: null})}
    onCreate={create} onLogout={() => void logout()} onSignedOut={onSignedOut} />;
}
