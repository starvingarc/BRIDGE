import {
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
} from "@assistant-ui/react";
import { File, Menu, MoreVertical, Paperclip, Send, Square } from "lucide-react";
import { type ChangeEvent, type FormEvent, useRef } from "react";
import type { Session, Upload } from "../types";
import { MarkdownText } from "./MarkdownText";
import { PlanCard, PlanHistory } from "./PlanCard";
import { SessionStatusMark } from "./StatusMark";

type Props = {
  session: Session;
  busy: boolean;
  uploadBusy: boolean;
  approveBusy: boolean;
  onOpenSidebar: () => void;
  onUpload: (file: File) => void;
  onSourceInput: (uploadId: string, sourceFamilyId: string) => void;
  onApprove: () => void;
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

function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="message message--assistant">
      <div className="assistant-mark" aria-hidden="true">
        <Square />
      </div>
      <div className="message-bubble message-bubble--assistant">
        <MessagePrimitive.Parts components={{ Text: MarkdownText }} />
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

  return uploads.map((upload) => {
    const uploadLabel = nameCounts.get(upload.name) === 1
      ? upload.name
      : `${upload.name} · ${upload.id.slice(0, 8)}`;
    return (
      <form className="source-form" key={upload.id} onSubmit={(event) => submit(event, upload.id)}>
        <strong className="source-upload-name">{uploadLabel}</strong>
        <label htmlFor={`source-${upload.id}`}>Data source / experiment reference</label>
        <div>
          <input
            id={`source-${upload.id}`}
            name="source_family_id"
            defaultValue={upload.source_family_id ?? ""}
            maxLength={160}
            pattern={"[A-Za-z0-9][A-Za-z0-9_.:\\-]*"}
            title="Start with a letter or number; use only letters, numbers, dot, underscore, colon, or hyphen."
            required
            disabled={disabled}
            placeholder="e.g. source-family:study-cohort"
          />
          <button type="submit" disabled={disabled}>Save</button>
        </div>
        <small>Stored with this upload locally, up to 160 letters, numbers, . _ : or -. It is not sent to the model.</small>
      </form>
    );
  });
}

export function Conversation({
  session,
  busy,
  uploadBusy,
  approveBusy,
  onOpenSidebar,
  onUpload,
  onSourceInput,
  onApprove,
}: Props) {
  const fileInput = useRef<HTMLInputElement>(null);
  const handleFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) onUpload(file);
    event.target.value = "";
  };

  return (
    <section className="conversation-pane" aria-label="Conversation">
      <header className="conversation-header">
        <button className="icon-button mobile-only" onClick={onOpenSidebar} aria-label="Open analyses">
          <Menu aria-hidden="true" />
        </button>
        <div className="conversation-title">
          <h1>{session.title || "Untitled analysis"}</h1>
          <div className="conversation-status">
            <SessionStatusMark status={session.status} />
            <span>{session.status.replace("_", " ")}</span>
          </div>
        </div>
        <a
          className="icon-button"
          href={`/api/sessions/${encodeURIComponent(session.id)}/transcript`}
          download
          aria-label="Download transcript"
          title="Download transcript"
        >
          <MoreVertical aria-hidden="true" />
        </a>
      </header>
      <ThreadPrimitive.Root className="thread-root">
        <ThreadPrimitive.Viewport className="thread-viewport">
          <div className="message-stack">
            <ThreadPrimitive.Messages>
              {({ message }) => (message.role === "user" ? <UserMessage /> : <AssistantMessage />)}
            </ThreadPrimitive.Messages>
            {session.messages.length === 0 ? (
              <div className="conversation-empty">
                <h2>Start a product assessment</h2>
                <p>Upload an H5AD file, then describe the question you want BRIDGE to assess.</p>
              </div>
            ) : null}
            {session.error ? (
              <div className="session-error" role="alert">
                {session.error}
              </div>
            ) : null}
            <PlanHistory plans={session.plan_history ?? []} currentPlanId={session.plan?.id} />
            {session.plan ? (
              <PlanCard
                plan={session.plan}
                sessionStatus={session.status}
                busy={approveBusy}
                onApprove={onApprove}
              />
            ) : null}
          </div>
          <ThreadPrimitive.ViewportFooter className="composer-footer">
            {session.uploads.length || session.capabilities?.length ? (
              <details className="analysis-context">
                <summary>Data and tool chain</summary>
                <SourceInputForms
                  uploads={session.uploads}
                  disabled={busy}
                  onSourceInput={onSourceInput}
                />
                {session.capabilities?.length ? (
                  <ul className="capability-list" aria-label="Tool-chain status">
                    {session.capabilities.map((capability) => (
                      <li key={capability.tool_id}>
                        <span><strong>{capability.tool_id}</strong> {capability.label}</span>
                        <span className={`capability-state capability-state--${capability.state}`}>
                          {capability.state.replace("_", " ")}
                        </span>
                        {capability.reason_codes.length ? (
                          <small>{capability.reason_codes.map((reason) => reason.replaceAll("_", " ")).join(" · ")}</small>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </details>
            ) : null}
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
            <ComposerPrimitive.Root className="composer">
              <ComposerPrimitive.Input
                className="composer-input"
                placeholder="Ask about this analysis…"
                rows={2}
                submitMode="enter"
                disabled={busy}
                aria-label="Message"
              />
              <div className="composer-actions">
                <input
                  ref={fileInput}
                  className="sr-only"
                  type="file"
                  accept=".h5ad,application/x-hdf5"
                  onChange={handleFile}
                  disabled={busy || uploadBusy}
                  aria-label="Choose H5AD file"
                />
                <button
                  className="composer-icon-button"
                  type="button"
                  onClick={() => fileInput.current?.click()}
                  disabled={busy || uploadBusy}
                  aria-label="Upload H5AD"
                  title="Upload H5AD"
                >
                  <Paperclip aria-hidden="true" />
                </button>
                <ComposerPrimitive.Send className="composer-send" aria-label="Send message">
                  <Send aria-hidden="true" />
                </ComposerPrimitive.Send>
              </div>
            </ComposerPrimitive.Root>
          </ThreadPrimitive.ViewportFooter>
        </ThreadPrimitive.Viewport>
      </ThreadPrimitive.Root>
    </section>
  );
}
