import { fieldLabel, toolName } from "../researcherLabels";
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
  intakeValue(value);

export function InputChangeCard({ pending, uploads, busy, onConfirm, onDiscard, onKeep }: Props) {
  const intake = pending?.kind === "intake";
  const selection = pending?.kind === "selection";
  const nameOnly = intake && !!pending?.changes.length
    && pending.changes.every(change => change.field === "product_name")
    && !!pending.impact && pending.impact.affected.every(run => run.tool_id === "P0-10");
  const selectionLabels: Record<string, string> = { object_inputs: "分析对象", asset_ids: "数据文件", mode_id: "分析方式", measurement_spec_ref: "测量定义" };
  const targetUpload = pending
    ? uploads.find((upload) => upload.id === pending.upload_id)
    : undefined;

  return (
    <section className="input-change-card" role="region" aria-label="Input change review">
      <header>
        <strong>{intake ? "请核对产品资料" : selection ? "请核对分析输入" : "Input review required"}</strong>
        {pending ? <span>{intake || selection ? "待您确认" : `${pending.kind} change`}</span> : null}
      </header>
      {pending ? (
        <>
          {!selection ? <p>
            {intake ? "本次文件 " : "Target file "}<strong>{targetUpload?.name ?? "Unavailable upload"}</strong>{" "}
          </p> : null}
          <p>{selection ? "以下分析输入将在确认后更新；已有分析和报告的影响见下方清单。" : intake ? "以下是待确认的精确变更。确认资料不等于批准运行，不确定的项目可以保留未知。" : "This exact change is staged. Current inputs remain unchanged until confirmation."}</p>
          <dl>
            {pending.changes.map((change) => (
              <div key={change.field}>
                <dt>{intake ? intakeLabels[change.field] ?? change.field : selection ? selectionLabels[change.field] ?? fieldLabel(change.field) : fieldLabel(change.field)}</dt>
                <dd>
                  <span>{intake ? "原来：" : "Before "}{intake ? intakeValue(change.before) : <span>{exactValue(change.before)}</span>}</span>
                  <span>{intake ? "确认后：" : "After "}{intake ? intakeValue(change.after) : <span>{exactValue(change.after)}</span>}</span>
                </dd>
              </div>
            ))}
          </dl>
          {pending.impact ? (
            <section aria-label="修订影响">
              <strong>修订影响</strong>
              {nameOnly ? <p>此次只修改产品名称：确认后新报告使用新名称；已有测量、证据图和旧报告保留，不会自动重跑分析。</p>
                : <p>{pending.impact.affected.length} 项已有分析需要更新，{pending.impact.reusable.length} 项分析的输入依赖不受影响。</p>}
              {pending.impact.affected.length ? <ul>{pending.impact.affected.map((run) =>
                <li key={run.receipt_sha256}>{toolName(run.tool_id)}：{nameOnly ? "新报告需使用确认后的名称" : "需要更新"}</li>)}</ul> : null}
              {pending.impact.reusable.length ? <details><summary>输入依赖未改变的分析</summary>
                <ul>{pending.impact.reusable.map((run) => <li key={run.receipt_sha256}>{toolName(run.tool_id)}</li>)}</ul>
              </details> : null}
              <p>原始文件、历史回执和旧版报告保留。更新分析需要另行确认，不会自动开始。</p>
            </section>
          ) : null}
          <div className="input-change-actions">
            <button type="button" onClick={onConfirm} disabled={busy}>{intake ? "确认资料" : selection ? "确认修改" : "Confirm change"}</button>
            <button type="button" onClick={onDiscard} disabled={busy}>{intake || selection ? "放弃这次修改" : "Discard change"}</button>
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
