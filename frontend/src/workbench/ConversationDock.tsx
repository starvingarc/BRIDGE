import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";

export type DockMessage = { id: number; from: "me" | "bridge"; text: string; exploratory?: boolean; tags?: string[] };

type Props = { messages: DockMessage[]; open: boolean; onOpenChange: (open: boolean) => void;
  onSend: (text: string) => Promise<boolean> | void; label?: string; disabled?: boolean; footer?: ReactNode;
  question?: { id: number; text: string } | null;
  /** A row under the input (model and effort), as in Claude Code. */
  controls?: ReactNode;
};

export function ConversationDock({ messages, open, onOpenChange, onSend, label = "对话", disabled = false, footer, question, controls }: Props) {
  const [draft, setDraft] = useState("");
  useEffect(() => { if (question) setDraft(question.text); }, [question?.id]);
  const list = useRef<HTMLDivElement>(null);
  useEffect(() => { list.current?.scrollTo({ top: list.current.scrollHeight }); }, [messages, open]);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text || disabled) return;
    if (await onSend(text) !== false) setDraft("");
  };
  const composer = <form className="wb-dock" onSubmit={submit}>
      <button type="button" className="wb-icon" aria-label={open ? "收起对话" : "展开对话"} aria-expanded={open} aria-controls="wb-sheet" onClick={() => onOpenChange(!open)}>
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M4 6h16M4 12h10M4 18h7" /></svg>
      </button>
      <input id="wb-ask" disabled={disabled} value={draft} onChange={e => setDraft(e.target.value)} placeholder="问 BRIDGE" autoComplete="off" aria-label="问 BRIDGE" />
      <button type="submit" disabled={disabled} className="wb-icon wb-send" aria-label="发送">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
      </button>
      {controls && <div className="wb-dock-tools">{controls}</div>}
    </form>;
  return <>
    {!open && composer}
    <section id="wb-sheet" className={open ? "wb-sheet wb-sheet--open" : "wb-sheet"} aria-label="对话" aria-hidden={!open}>
      <header><span>{label}</span><button className="wb-link" onClick={() => onOpenChange(false)} tabIndex={open ? 0 : -1}>收起</button></header>
      <div className="wb-messages" ref={list} aria-live="polite">
        {messages.map(m => <div key={m.id} className={m.from === "me" ? "wb-msg-me" : "wb-msg-bridge"}>
          {m.exploratory && <span className="wb-explore">探索性 · 沙箱</span>}
          <p>{m.text}</p>
          {m.tags && <span className="wb-tags">{m.tags.map(t => <span key={t}>{t}</span>)}</span>}
        </div>)}
      </div>
      {footer && <div className="wb-conversation-actions">{footer}</div>}
      {open && composer}
    </section>
  </>;
}
