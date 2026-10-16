import { useEffect, useRef, useState } from "react";
import { ApiError, api } from "../api";
import type { Session } from "../types";
import { ConversationDock } from "./ConversationDock";
import { ModelControls } from "../components/ModelPicker";

const working = new Set(["thinking", "running", "stopping"]);
type Props = {
  researchId: string; runId: string | null; label: string;
  question?: { id: number; text: string } | null;
  onOpenSession: (id: string) => void;
};

/** One mounted instance owns one server-bound scope. Its host keys account/research/run. */
export function BoundConversation({ researchId, runId, label, question, onOpenSession }: Props) {
  const [session, setSession] = useState<Session | null>(null);
  const current = useRef<Session | null>(null);
  const alive = useRef(false);
  const generation = useRef(0);
  const writing = useRef(false);
  const [pending, setPending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [readFailed, setReadFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const save = (value: Session) => { current.current = value; setSession(value); };
  const describe = (failure: unknown) => failure instanceof ApiError && failure.status === 401
    ? "登录已失效，请重新登录。" : failure instanceof Error ? failure.message : "会话暂时无法读取，请重试。";

  useEffect(() => {
    alive.current = true;
    const controller = new AbortController();
    const turn = ++generation.current;
    setLoading(true); setReadFailed(false); setError("");
    const read = current.current ? api.getSession(current.current.id, controller.signal)
      : api.getConversation(researchId, runId, controller.signal);
    read.then(value => {
      if (alive.current && generation.current === turn) save(value);
    }, failure => {
      if (!alive.current || generation.current !== turn) return;
      if (!(failure instanceof ApiError && failure.status === 404 && failure.message === "conversation_not_found")) {
        setError(describe(failure)); setReadFailed(true); setOpen(true);
      }
    }).finally(() => { if (alive.current && generation.current === turn) setLoading(false); });
    return () => { alive.current = false; generation.current += 1; controller.abort(); };
  }, [researchId, runId, retry]);

  const busy = !!session && working.has(session.status);
  useEffect(() => {
    if (!session || !busy || readFailed) return;
    let cancelled = false;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      const turn = generation.current;
      try {
        const value = await api.getSession(session.id, controller.signal);
        if (cancelled || !alive.current) return;
        if (turn === generation.current) save(value);
      } catch (failure) {
        if (!cancelled && alive.current && turn === generation.current) {
          setError(describe(failure)); setReadFailed(true); setOpen(true);
          return;
        }
      }
      // A Stop may invalidate an in-flight poll while the worker is still stopping.
      if (!cancelled && alive.current && current.current && working.has(current.current.status))
        timer = setTimeout(poll, 1250);
    };
    timer = setTimeout(poll, 1250);
    return () => { cancelled = true; controller.abort(); clearTimeout(timer); };
  }, [session?.id, busy, readFailed, retry]);

  useEffect(() => { if (question) setOpen(true); }, [question?.id]);
  const send = async (text: string) => {
    if (writing.current || loading || readFailed || (current.current && working.has(current.current.status))) return false;
    writing.current = true; setPending(true); setError(""); setOpen(true);
    const turn = ++generation.current;
    const priorMessages = new Set((current.current?.messages ?? []).map(item => item.id));
    try {
      const bound = current.current ?? await api.openConversation(researchId, runId);
      if (!alive.current || turn !== generation.current) return false;
      save(bound);
      const next = await api.sendMessage(bound.id, text);
      if (!alive.current || turn !== generation.current) return false;
      save(next);
      return true;
    } catch (failure) {
      if (!alive.current || turn !== generation.current) return false;
      // A lost response may follow an accepted message. Read before inviting a retry.
      if (current.current && (!(failure instanceof ApiError) || failure.status === 0 || failure.status >= 500 || failure.status === 409)) {
        try {
          const latest = await api.getSession(current.current.id);
          if (!alive.current || turn !== generation.current) return false;
          save(latest);
          if ((latest.messages ?? []).some(item => item.role === "user" && item.content === text && !priorMessages.has(item.id))) return true;
        } catch {
          if (!alive.current || turn !== generation.current) return false;
          setReadFailed(true);
          setError("发送状态暂时无法确认，请先重新读取会话，避免重复发送。");
          return false;
        }
      }
      setError(describe(failure));
      return false;
    } finally {
      writing.current = false;
      if (alive.current && turn === generation.current) setPending(false);
    }
  };
  const stop = async () => {
    if (!current.current || writing.current || loading) return;
    writing.current = true; setPending(true); setError("");
    const turn = ++generation.current;
    try {
      const next = await api.stopSession(current.current.id);
      if (alive.current && turn === generation.current) save(next);
    } catch (failure) {
      if (alive.current && turn === generation.current) setError(describe(failure));
    } finally {
      writing.current = false;
      if (alive.current && turn === generation.current) setPending(false);
    }
  };
  const messages = (session?.messages ?? []).filter(item => item.role === "user" || item.role === "assistant")
    .map((item, index) => ({ id: index, from: item.role === "user" ? "me" as const : "bridge" as const, text: item.content }));
  // Choosing a model before the first message binds the conversation, so the choice belongs to it.
  const ensureSession = async () => {
    const bound = current.current ?? await api.openConversation(researchId, runId);
    if (alive.current) save(bound);
    return bound.id;
  };
  return <ConversationDock messages={messages} open={open} onOpenChange={setOpen} onSend={send}
    label={label} question={question} disabled={loading || pending || busy || readFailed}
    controls={<ModelControls sessionId={session?.id ?? null} current={session?.model_selection ?? null} ensureSession={ensureSession} disabled={loading || readFailed} />}
    footer={<>
      {loading && <p role="status">正在读取对话…</p>}
      {busy && <p role="status">{session?.presentation?.summary || "BRIDGE 正在处理…"}</p>}
      {(error || session?.error) && <p role="alert">{error || session?.error}</p>}
      {readFailed && <button className="wb-link" disabled={loading || pending} onClick={() => setRetry(value => value + 1)}>重新读取会话</button>}
      {busy && <button className="wb-link" disabled={loading || pending} onClick={() => void stop()}>停止</button>}
      {session && <button className="wb-link" onClick={() => onOpenSession(session.id)}>打开完整会话</button>}
      {!busy && session?.presentation?.next_actions.some(action => action.id !== "stop" && action.id !== "provide_input") &&
        <p>{session.presentation.summary} 请在完整会话中查看结果或确认下一步。</p>}
    </>} />;
}
