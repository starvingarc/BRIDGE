import { ArrowUpRight } from "lucide-react";
import type { Session } from "../types";

export type FocusTarget = "overview" | "plan" | "inputs" | "conversation";
export type WorkspaceFocusState = { title: string; detail: string; action?: string; target?: FocusTarget; attention?: boolean };

// Read-only navigation guidance. Authorization, execution and scientific states stay server-owned.
export function workspaceFocus(session: Session): WorkspaceFocusState {
  if (session.status === "stopping") return {
    title: "正在停止", detail: "当前工具可能仍会完成，后续任务已停止；已有结果会保留。"
  };
  if (session.input_review_required) return {
    title: "输入修改待核对", detail: "继续分析前，请核对本次待确认的修改。",
    action: "核对修改", target: session.pending_input_change?.kind === "intake" ? "overview" : "inputs", attention: true
  };
  if (session.status === "failed" || session.error) return {
    title: "本次运行需要处理", detail: "请查看对话中的错误说明；已有结果仍可查看。",
    action: "查看错误", target: "conversation", attention: true
  };
  if (session.status === "awaiting_approval") return {
    title: "分析计划待核对", detail: "请先核对工具和范围，再批准执行。",
    action: "核对计划", target: "plan", attention: true
  };
  if (session.status === "thinking" || session.status === "running" || session.assessment?.status === "running") return {
    title: session.status === "thinking" ? "正在处理问题" : "正在分析",
    detail: "分析期间仍可查看已有结果，新证据就绪后会显示在这里。"
  };
  if (session.clarifications?.some(card => card.status === "pending")
    || session.scientific_drafts?.some(draft => draft.status === "pending")) return {
    title: "还需补充信息", detail: "请核对对话中的问题与科学输入草稿。",
    action: "查看问题", target: "conversation", attention: true
  };
  if (session.presentation?.stage === "results_ready") return {
    title: "结果已就绪", detail: session.presentation.summary,
    action: "查看评估", target: "overview"
  };
  if (session.assessment && ["blocked", "interrupted", "stopped", "proposed"].includes(session.assessment.status)) return {
    title: session.assessment.status === "proposed" ? "评估范围待核对" : "评估已暂停",
    detail: "评估概览会显示当前范围、缺失输入和可继续的步骤。",
    action: "查看评估概览", target: "overview", attention: true
  };
  if (!session.uploads.length) return {
    title: "从一个问题开始", detail: "可以先讨论研究问题；开展数据分析前，再选择 H5AD 并核对实验背景。"
  };
  return {
    title: "可以继续讨论",
    detail: session.artifacts.length ? "可以查看已有结果与依据，或继续提问。"
      : "核对数据与实验背景后，再选择下一步分析。",
    action: "核对实验背景", target: "overview"
  };
}

export function WorkspaceFocus({ session, onNavigate }: { session: Session; onNavigate: (target: FocusTarget) => void }) {
  const focus = workspaceFocus(session);
  return <div className={`workspace-focus ${focus.attention ? "workspace-focus--attention" : ""}`}>
    <div className="focus-heading" role="status"><span className="focus-dot" aria-hidden="true" />{focus.title}</div>
    <p>{focus.detail}</p>
    {focus.action && focus.target ? <button onClick={() => onNavigate(focus.target!)} type="button">
      {focus.action}<ArrowUpRight aria-hidden="true" />
    </button> : null}
  </div>;
}
