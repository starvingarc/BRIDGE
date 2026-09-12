import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { ConditionalDraft, Session } from "../types";

export function ConditionalInputs({ session, busy, onSession, onError }: {
  session: Session; busy: boolean; onSession: (session: Session) => void;
  onError: (error: unknown) => void;
}) {
  const [working, setWorking] = useState(false);
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const directory = session.conditional_inputs;
  if (!directory) return null;
  const disabled = busy || working || session.input_review_required;
  const perform = async (operation: () => Promise<Session>) => {
    setWorking(true);
    try {
      const next = await operation();
      if (mounted.current) onSession(next);
    } catch (error) { if (mounted.current) onError(error); }
    finally { if (mounted.current) setWorking(false); }
  };
  const decide = (draft: ConditionalDraft, action: "confirm" | "cancel" | "prepare") =>
    perform(() => api.decideConditionalInputs(session.id, action, draft.id, draft.digest, directory.input_revision));
  return <details className="scientific-draft" aria-label="产品比较与移植后证据">
    <summary>产品比较与移植后证据</summary>
    <p>{directory.access_boundary}</p>
    {[directory.comparison, directory.graft].map((group) => <section key={group.label}>
      <h3>{group.label}</h3>
      {group.reasons.map((reason) => <p key={reason}>{reason}</p>)}
      {group.entries.map((entry) => <div className="science-choice" key={entry.id}>
        <strong>{entry.label}</strong><p>{entry.category_label}</p>
        {entry.reasons.map((reason) => <p key={reason}>{reason}</p>)}
        <button disabled={disabled || !entry.execution_available}
          onClick={() => void perform(() => api.proposeConditionalInputs(
            session.id, entry.diagnostics.selection, directory.input_revision))}>
          核对并选择此方案
        </button>
      </div>)}
    </section>)}
    {directory.selections.map((draft) => <section key={draft.id} aria-label={draft.label}>
      <h3>{draft.label}</h3><p>{draft.status_label}</p>
      {draft.reasons.map((reason) => <p key={reason}>{reason}</p>)}
      {draft.status === "pending" ? <button disabled={disabled || !draft.execution_available}
        onClick={() => void decide(draft, "confirm")}>确认所选输入</button> : null}
      {draft.status === "confirmed" ? <button disabled={disabled || !draft.execution_available}
        onClick={() => void decide(draft, "prepare")}>生成待审批计划</button> : null}
      {["pending", "confirmed"].includes(draft.status) ? <button disabled={disabled}
        onClick={() => void decide(draft, "cancel")}>取消选择</button> : null}
    </section>)}
    <p>{directory.scientific_boundary}</p>
  </details>;
}
