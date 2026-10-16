import { toolName, reasonLabel, stateName } from "../researcherLabels";
import { Database, Network, PanelsTopLeft } from "lucide-react";
import type { Plan, SessionStatus } from "../types";
import { StepStatusMark } from "./StatusMark";

type Props = {
  plan: Plan;
  sessionStatus: SessionStatus;
  busy: boolean;
  approvalAvailable?: boolean;
  onApprove: () => void;
};

const StepIcon = ({ index }: { index: number }) => {
  const Icon = index % 3 === 0 ? Database : index % 3 === 1 ? Network : PanelsTopLeft;
  return <Icon aria-hidden="true" />;
};

const planActionLabel = (plan: Plan, status: SessionStatus) => {
  if (plan.status === "completed") return "分析已完成";
  if (plan.status === "failed") return "分析未完成";
  if (plan.status === "partial") return "已有部分结果";
  if (plan.status === "cancelled") return "分析已取消";
  if (status === "running") return "分析中…";
  if (plan.status === "approved") return "已确认分析";
  return "开始分析";
};

export function PlanHistory({ plans, currentPlanId }: { plans: Plan[]; currentPlanId?: string }) {
  const historicalPlans = plans.filter((plan) => plan.id !== currentPlanId);
  if (!historicalPlans.length) return null;
  return (
    <details className="stage-history">
      <summary>历史分析 <span>{historicalPlans.length}</span></summary>
      <div className="stage-history-list">
        {historicalPlans.map((plan) => (
          <details key={plan.id}>
            <summary>
              <strong>{plan.steps.map(step => toolName(step.tool_id)).join("、")}</strong>
              <span className={`plan-state plan-state--${plan.status}`}>{stateName(plan.status)}</span>
            </summary>
            <ol>
              {plan.steps.map((step) => (
                <li key={step.id}>
                  <div>
                    <span>{toolName(step.tool_id)}</span>
                    {step.reason ? <small>{reasonLabel(step.reason)}</small> : null}
                  </div>
                  <span className={`step-state step-state--${step.status}`}>
                    <StepStatusMark status={step.status} />
                    <span>{stateName(step.status)}</span>
                  </span>
                </li>
              ))}
            </ol>
          </details>
        ))}
      </div>
    </details>
  );
}

export function PlanCard({ plan, sessionStatus, busy, onApprove, approvalAvailable }: Props) {
  const approvable =
    approvalAvailable !== false && plan.status === "proposed" &&
    sessionStatus === "awaiting_approval" &&
    plan.steps.some((step) => step.status === "pending");
  return (
    <section className="plan-card" aria-labelledby={`plan-${plan.id}-title`}>
      <header>
        <div>
          <h2 id={`plan-${plan.id}-title`}>分析内容</h2>
        </div>
        <span className={`plan-state plan-state--${plan.status}`}>{stateName(plan.status)}</span>
      </header>
      <ol>
        {plan.steps.map((step, index) => (
          <li key={step.id}>
            <StepIcon index={index} />
            <div className="plan-step-copy">
              <span>{toolName(step.tool_id)}</span>
              {step.reason ? <small>{reasonLabel(step.reason)}</small> : null}
            </div>
            <span className={`step-state step-state--${step.status}`}>
              <StepStatusMark status={step.status} />
              <span>{stateName(step.status)}</span>
            </span>
          </li>
        ))}
      </ol>
      <button
        className="approve-button"
        onClick={onApprove}
        disabled={!approvable || busy}
      >
        {planActionLabel(plan, sessionStatus)}
      </button>
    </section>
  );
}
