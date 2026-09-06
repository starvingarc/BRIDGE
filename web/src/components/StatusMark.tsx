import { Ban, Check, CircleAlert, CircleDashed, LoaderCircle, Minus, OctagonX } from "lucide-react";
import type { PlanStep, SessionStatus } from "../types";

export function SessionStatusMark({ status }: { status: SessionStatus }) {
  const content =
    status === "thinking" || status === "running" ? (
      <LoaderCircle aria-hidden="true" className="spin" />
    ) : status === "failed" ? (
      <CircleAlert aria-hidden="true" />
    ) : (
      <span aria-hidden="true" className="status-dot" />
    );
  return (
    <span className={`session-status session-status--${status}`} title={status.replace("_", " ")}>
      {content}
      <span className="sr-only">{status.replace("_", " ")}</span>
    </span>
  );
}

export function StepStatusMark({ status }: { status: PlanStep["status"] }) {
  if (status === "running") return <LoaderCircle aria-label="Running" className="spin" />;
  if (status === "succeeded") return <Check aria-label="Succeeded" />;
  if (status === "failed") return <CircleAlert aria-label="Failed" />;
  if (status === "partial") return <CircleAlert aria-label="Partial" />;
  if (status === "blocked") return <OctagonX aria-label="Blocked" />;
  if (status === "cancelled") return <Ban aria-label="Cancelled" />;
  if (status === "skipped") return <Minus aria-label="Skipped" />;
  return <CircleDashed aria-label="Pending" />;
}
