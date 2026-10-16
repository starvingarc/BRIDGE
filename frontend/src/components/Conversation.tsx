import { PresentationIssue } from "./PresentationIssue";
import { stateName, researcherText, conversationName } from "../researcherLabels";
import {
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
} from "@assistant-ui/react";
import { File, Menu, Pencil, MoreVertical, PanelRightOpen, Paperclip, Send, Square } from "lucide-react";
import { type ChangeEvent, type FormEvent, type ReactNode, useRef, useState } from "react";
import { formatBytes, type UploadLimits } from "../upload";
import { api } from "../api";
import { ClarificationCard } from "./ClarificationCard";
import { ScientificInputs } from "./ScientificInputs";
import type { Message, Session, Upload } from "../types";
import { ConditionalInputs } from "./ConditionalInputs";
import { InputChangeCard } from "./InputChangeCard";
import { MarkdownText, ResearcherMarkdownText } from "./MarkdownText";
import { PlanCard, PlanHistory } from "./PlanCard";
import { SessionStatusMark } from "./StatusMark";

type Props = {
  session: Session;
  busy: boolean;
  uploadBusy: boolean;
  uploadLimits: UploadLimits | null;
  uploadLimitError: boolean;
  uploadFeedback: { message: string; error: boolean } | null;
  onRetryUploadLimits: () => void;
  approveBusy: boolean;
  stopBusy: boolean;
  onOpenSidebar: () => void;
  onReviewContext: () => void;
  onOpenMaterials?: () => void;
  onRename?: () => void;
  onUpload: (file: File) => void;
  onSourceInput: (uploadId: string, sourceFamilyId: string) => void;
  onApprove: () => void;
  onStop: () => void;
  onConfirmInputChange: () => void;
  onDiscardInputChange: () => void;
  onKeepCurrentInputs: () => void;
  onSession: (session: Session) => void;
  onError: (error: unknown) => void;
};

function UserMessage() {
  return (
    <MessagePrimitive.Root className="message message--user">
      <div className="message-bubble message-bubble--user">
        <MessagePrimitive.Parts components={{ Text: MarkdownText }} />
      </div>
    </MessagePrimitive.Root>
  );
}

function AssistantMessage({ children, original }: { children?: ReactNode; original?: Message }) {
  return (
    <MessagePrimitive.Root className="message message--assistant">
      <div className="assistant-mark" aria-hidden="true">
        <Square />
      </div>
      <div className="message-bubble message-bubble--assistant">
        {original?.provenance_warning === "legacy_unclassified" ?
          <p role="note">历史说明 · 来源与事实尚未核验，请勿作为当前结论。</p> : null}
        {original?.qualification === "proposed_explanation" ? <details className="message-interpretation">
          <summary>待检验解释{original.interpretation_ref ? ` · 第 ${original.interpretation_ref.version} 版` : ""}<span>未验证</span></summary>
          <MessagePrimitive.Parts components={{ Text: ResearcherMarkdownText }} />
        </details> : <MessagePrimitive.Parts components={{ Text: ResearcherMarkdownText }} />}
        {children}
      </div>
    </MessagePrimitive.Root>
  );
}

export function SourceInputForms({
  uploads,
  disabled,
  onSourceInput,
}: {
  uploads: Upload[];
  disabled: boolean;
  onSourceInput: (uploadId: string, sourceFamilyId: string) => void;
}) {
  const nameCounts = uploads.reduce<Map<string, number>>(
    (counts, upload) => counts.set(upload.name, (counts.get(upload.name) ?? 0) + 1),
    new Map(),
  );
  const submit = (event: FormEvent<HTMLFormElement>, uploadId: string) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const sourceFamilyId = String(form.get("source_family_id") ?? "").trim();
    if (sourceFamilyId) onSourceInput(uploadId, sourceFamilyId);
  };

  return uploads.map((upload, index) => {
    const uploadLabel = nameCounts.get(upload.name) === 1
      ? upload.name
      : `${upload.name} · 文件 ${index + 1}`;
    return (
      <form className="source-form" key={upload.id} onSubmit={(event) => submit(event, upload.id)}>
        <strong className="source-upload-name">{uploadLabel}</strong>
        <label htmlFor={`source-${upload.id}`}>数据来源或实验编号</label>
        <div>
          <input
            id={`source-${upload.id}`}
            name="source_family_id"
            key={`${upload.id}:${upload.source_family_id ?? ""}`}
            defaultValue={upload.source_family_id ?? ""}
            maxLength={160}
            pattern={"[A-Za-z0-9][A-Za-z0-9_.:\\-]*"}
            title="Start with a letter or number; use only letters, numbers, dot, underscore, colon, or hyphen."
            required
            disabled={disabled}
            placeholder="例如 study-2026-01"
          />
          <button type="submit" disabled={disabled}>核对修改</button>
        </div>
        <small>修改后需确认，已有结果会保留。</small>
      </form>
    );
  });
}

export function Conversation({
  session,
  busy,
  uploadBusy,
  uploadLimits,
  uploadLimitError,
  uploadFeedback,
  onRetryUploadLimits,
  approveBusy,
  stopBusy,
  onOpenSidebar,
  onReviewContext,
  onOpenMaterials,
  onRename,
  onUpload,
  onSourceInput,
  onApprove,
  onStop,
  onConfirmInputChange,
  onDiscardInputChange,
  onKeepCurrentInputs,
  onSession,
  onError,
}: Props) {
  const fresh = session.status === "idle" && !session.uploads.length && session.messages.length <= 1 && session.messages.every(message => message.role === "assistant" && message.content === "这次想研究什么？可以从一个问题开始，也可以先选择研究资料。");
  const fileInput = useRef<HTMLInputElement>(null);
  const [expandedHistory, setExpandedHistory] = useState<string | null>(null);
  const showHistory = expandedHistory === session.id;
  const recentMessages = new Set(session.messages.slice(-2).map(message => message.id));
  const hasInputCard = (id: string) => (session.clarifications ?? []).some(card => card.message_id === id)
    || (session.scientific_drafts ?? []).some(draft => draft.message_id === id);
  const olderCount = session.messages.filter(message => !recentMessages.has(message.id) && !hasInputCard(message.id)).length;
  const handleFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) onUpload(file);
    event.target.value = "";
  };

  return (
    <section className="conversation-pane" aria-label="Conversation">
      <header className="conversation-header">
        <button className="icon-button mobile-only" onClick={onOpenSidebar} aria-label="打开会话导航">
          <Menu aria-hidden="true" />
        </button>
        <div className="conversation-title">
          <h1>{conversationName(session.title)}</h1>
          {session.model_configuration ? <p className="task-model" title={session.model_configuration.base_url}>任务模型：{session.model_configuration.model || "未配置"}</p> : null}
          {session.presentation?.stage_label !== "已有结果" && <div className="conversation-status">
            {session.presentation ? <span>{session.presentation.stage_label}</span> : <>
              <SessionStatusMark status={session.status} />
              <span>{stateName(session.status)}</span>
            </>}
          </div>}
        </div>
        <div className="conversation-header-actions">
          {onRename && <button className="icon-button" disabled={busy} aria-label="修改会话名称" onClick={onRename}><Pencil aria-hidden="true" /></button>}
          <button className="icon-button" type="button" onClick={onReviewContext}
            aria-label="Open research overview" title="Open research overview"><PanelRightOpen aria-hidden="true" /></button>
          {(session.presentation ? session.presentation.next_actions.some(action => action.id === "stop")
            : ["thinking", "running", "awaiting_approval"].includes(session.status)) ? (
            <button
              className="stop-button"
              type="button"
              onClick={onStop}
              disabled={stopBusy}
              aria-label="Stop analysis"
            >
              <Square aria-hidden="true" />
              {stopBusy ? "Stopping…" : "Stop"}
            </button>
          ) : null}
          <a
            className="icon-button"
            href={`/api/sessions/${encodeURIComponent(session.id)}/transcript`}
            download
            aria-label="Download transcript"
            title="Download transcript"
          >
            <MoreVertical aria-hidden="true" />
          </a>
        </div>
      </header>
      <ThreadPrimitive.Root className="thread-root">
        <ThreadPrimitive.Viewport className="thread-viewport">
          <div className="message-stack" id="workspace-conversation" tabIndex={-1}>
            {olderCount > 0 && <button type="button" className="conversation-history-toggle"
              aria-expanded={showHistory} onClick={() => setExpandedHistory(showHistory ? null : session.id)}>
              {showHistory ? "收起较早对话" : `查看较早对话（${olderCount}）`}</button>}
            {!fresh && <ThreadPrimitive.Messages>
              {({ message }) => (!showHistory && !recentMessages.has(message.id) && !hasInputCard(message.id) ? null : message.role === "user" ? <UserMessage /> : (
                <AssistantMessage original={session.messages.find(item => item.id === message.id)}>
                  {(session.clarifications ?? []).filter((card) => card.message_id === message.id).map((card) => (
                    <ClarificationCard key={session.id + ":" + card.id + ":" + card.digest} card={card} busy={busy}
                      onAnswer={async (answers) => onSession(await api.answerClarification(session.id, card.id, card.digest, answers))}
                      onCancel={async () => onSession(await api.cancelClarification(session.id, card.id, card.digest))}
                      onRevise={async () => onSession(await api.reviseClarification(session.id, card.id, card.digest))} />
                  ))}
                  {(session.scientific_drafts ?? []).filter((draft) => draft.message_id === message.id).map((draft) => (
                    <ScientificInputs key={session.id + ":" + draft.id + ":" + draft.digest} draft={draft} busy={busy}
                      onPrepareReport={async (toolId) => onSession(await api.prepareReportInputs(session.id, draft.id, draft.digest, toolId))}
                      onConfirm={async () => onSession(await api.confirmScientificInputs(session.id, draft.id, draft.digest))}
                      onRevise={async (candidate) => onSession(await api.reviseScientificInputs(session.id, draft.id, draft.digest, candidate))} />
                  ))}
                </AssistantMessage>
              ))}
            </ThreadPrimitive.Messages>}
            {fresh ? <div className="conversation-empty">
              <span className="research-brand-orb" aria-hidden="true" /><h2>这次想研究什么？</h2>
              <p>从一个问题开始，也可以先选择研究资料。</p>
              <button className="start-upload" type="button" onClick={onOpenMaterials ?? (() => fileInput.current?.click())}
                disabled={busy || uploadBusy || (!onOpenMaterials && !uploadLimits)}>{onOpenMaterials ? "选择研究资料" : "上传 H5AD"}</button>
            </div> : null}
            {session.status === "stopping" ? (
              <div className="stopping-notice" role="status">
                Stop acknowledged. Current in-process work may still finish; later work is stopped.
              </div>
            ) : null}
            {session.error && session.presentation?.issue ? <PresentationIssue issue={session.presentation.issue} /> : session.error ? (
              <div className="session-error" role="alert">
                {researcherText(session.error)}
              </div>
            ) : null}
            <PlanHistory plans={session.plan_history ?? []} currentPlanId={session.plan?.id} />
            {session.plan ? (
              <div id="workspace-plan" tabIndex={-1}>
                <details open={session.plan.status !== "completed"}><summary>{session.plan.status === "completed" ? "已完成的分析" : "分析计划"}</summary><PlanCard
                plan={session.plan}
                approvalAvailable={session.presentation ? session.presentation.next_actions.some(action => action.id === "approve_plan") : undefined}
                sessionStatus={session.status}
                busy={approveBusy || session.input_review_required}
                onApprove={onApprove}
              /></details></div>
            ) : null}
          </div>
          <ThreadPrimitive.ViewportFooter className="composer-footer">
            <div id="workspace-inputs" tabIndex={-1}>
            {session.input_review_required && session.pending_input_change?.kind !== "intake" ? (
              <InputChangeCard
                pending={session.pending_input_change}
                uploads={session.uploads}
                busy={approveBusy}
                onConfirm={onConfirmInputChange}
                onDiscard={onDiscardInputChange}
                onKeep={onKeepCurrentInputs}
              />
            ) : null}
            {session.conditional_inputs && session.uploads.length > 0 ? (
              <ConditionalInputs key={session.id} session={session} busy={busy}
                onSession={onSession} onError={onError} />
            ) : null}
            {session.uploads.length > 0 && <details><summary>数据来源</summary>
              <SourceInputForms
                uploads={session.uploads}
                disabled={busy}
                onSourceInput={onSourceInput}
              />
            </details>}
            {session.uploads.length ? (
              <div className="upload-list" aria-label="Uploaded files">
                {session.uploads.map((upload) => (
                  <div className="upload-chip" key={upload.id}>
                    <File aria-hidden="true" />
                    <span>{upload.name}</span>
                    <small>{upload.kind}</small>
                  </div>
                ))}
              </div>
            ) : null}
            </div>
            <div className="upload-guidance">
              <p id="h5ad-upload-limit" className={uploadLimits ? "sr-only" : undefined}>{uploadLimits
                ? "H5AD · Up to " + formatBytes(uploadLimits.max_upload_bytes) + " per file."
                : uploadLimitError ? "Could not check the upload limit. Please retry before choosing a file."
                : "Checking upload limits…"}</p>
              {uploadLimitError ? <button type="button" disabled={busy || uploadBusy}
                onClick={onRetryUploadLimits}>Retry upload limit</button> : null}
              {uploadFeedback ? <p className={uploadFeedback.error ? "upload-feedback--error" : ""}
                role={uploadFeedback.error ? "alert" : "status"}>{uploadFeedback.message}</p> : null}
            </div>
            <ComposerPrimitive.Root className="composer">
              <ComposerPrimitive.Input
                className="composer-input"
                placeholder="继续提问…"
                rows={2}
                submitMode="enter"
                disabled={busy}
                aria-label="Message"
              />
              <div className="composer-actions">
                {!onOpenMaterials && <input
                  ref={fileInput}
                  className="sr-only"
                  type="file"
                  accept=".h5ad,application/x-hdf5"
                  onChange={handleFile}
                  disabled={busy || uploadBusy || !uploadLimits}
                  aria-label="Choose H5AD file"
                  aria-describedby="h5ad-upload-limit"
                />}
                <button
                  className="composer-icon-button"
                  type="button"
                  onClick={onOpenMaterials ?? (() => fileInput.current?.click())}
                  disabled={busy || uploadBusy || (!onOpenMaterials && !uploadLimits)}
                  aria-label={onOpenMaterials ? "打开共享资料" : "Upload H5AD"}
                  title={onOpenMaterials ? "研究资料" : "Upload H5AD"}
                  aria-describedby="h5ad-upload-limit"
                >
                  <Paperclip aria-hidden="true" />
                </button>
                <ComposerPrimitive.Send className="composer-send" aria-label="Send message">
                  <Send aria-hidden="true" />
                </ComposerPrimitive.Send>
              </div>
            </ComposerPrimitive.Root>
            {(uploadBusy || busy) && <p className="composer-hint">{uploadBusy ? "正在上传…" : "正在分析…"}</p>}
          </ThreadPrimitive.ViewportFooter>
        </ThreadPrimitive.Viewport>
      </ThreadPrimitive.Root>
    </section>
  );
}
