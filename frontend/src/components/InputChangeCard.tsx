import type { PendingInputChange, Upload } from "../types";
import { intakeLabels, intakeValue } from "./intakeLabels";

type Props = {
  pending: PendingInputChange | null;
  uploads: Upload[];
  busy: boolean;
  onConfirm: () => void;
  onDiscard: () => void;
  onKeep: () => void;
};

const exactValue = (value: PendingInputChange["changes"][number]["before"]) =>
  JSON.stringify(value);

export function InputChangeCard({ pending, uploads, busy, onConfirm, onDiscard, onKeep }: Props) {
  const intake = pending?.kind === "intake";
  const targetUpload = pending
    ? uploads.find((upload) => upload.id === pending.upload_id)
    : undefined;

  return (
    <section className="input-change-card" role="region" aria-label="Input change review">
      <header>
        <strong>{intake ? "请核对产品资料" : "Input review required"}</strong>
        {pending ? <span>{intake ? "待您确认" : `${pending.kind} change`}</span> : null}
      </header>
      {pending ? (
        <>
          <p>
            {intake ? "本次文件 " : "Target file "}<strong>{targetUpload?.name ?? "Unavailable upload"}</strong>{" "}
            {intake ? null : <code>{pending.upload_id}</code>}
          </p>
          <p>{intake ? "以下是待确认的精确变更。确认资料不等于批准运行，不确定的项目可以保留未知。" : "This exact change is staged. Current inputs remain unchanged until confirmation."}</p>
          <dl>
            {pending.changes.map((change) => (
              <div key={change.field}>
                <dt>{intake ? intakeLabels[change.field] ?? change.field : <code>{change.field}</code>}</dt>
                <dd>
                  <span>{intake ? "原来：" : "Before "}{intake ? intakeValue(change.before) : <code>{exactValue(change.before)}</code>}</span>
                  <span>{intake ? "确认后：" : "After "}{intake ? intakeValue(change.after) : <code>{exactValue(change.after)}</code>}</span>
                </dd>
              </div>
            ))}
          </dl>
          <div className="input-change-actions">
            <button type="button" onClick={onConfirm} disabled={busy}>{intake ? "确认资料" : "Confirm change"}</button>
            <button type="button" onClick={onDiscard} disabled={busy}>{intake ? "放弃这次修改" : "Discard change"}</button>
          </div>
        </>
      ) : (
        <>
          <p>
            Review the existing input forms and stage any correction, or explicitly keep the
            current declarations. Chat remains available, but planning is paused.
          </p>
          <div className="input-change-actions">
            <button type="button" onClick={onKeep} disabled={busy}>Keep current inputs</button>
          </div>
        </>
      )}
    </section>
  );
}
