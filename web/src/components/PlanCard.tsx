import { Database, Network, PanelsTopLeft } from "lucide-react";
import type { Plan, SessionStatus } from "../types";
import { StepStatusMark } from "./StatusMark";

type Props = {
  plan: Plan;
  sessionStatus: SessionStatus;
  busy: boolean;
  onApprove: () => void;
};

const StepIcon = ({ index }: { index: number }) => {
  const Icon = index % 3 === 0 ? Database : index % 3 === 1 ? Network : PanelsTopLeft;
  return <Icon aria-hidden="true" />;
};

const planActionLabel = (plan: Plan, status: SessionStatus) => {
  if (plan.status === "completed") return "Analysis completed";
  if (plan.status === "failed") return "Analysis failed";
  if (status === "running") return "Analysis running…";
  if (plan.status === "approved") return "Analysis approved";
  return "Confirm analysis";
};

export function PlanCard({ plan, sessionStatus, busy, onApprove }: Props) {
  const approvable = plan.status === "proposed" && sessionStatus === "awaiting_approval";
  return (
    <section className="plan-card" aria-labelledby={`plan-${plan.id}-title`}>
      <header>
        <div>
          <h2 id={`plan-${plan.id}-title`}>Analysis plan</h2>
          {plan.summary ? <p>{plan.summary}</p> : null}
        </div>
        <span className={`plan-state plan-state--${plan.status}`}>{plan.status}</span>
      </header>
      <ol>
        {plan.steps.map((step, index) => (
          <li key={step.id}>
            <StepIcon index={index} />
            <div className="plan-step-copy">
              <span>{step.label}</span>
              {step.reason ? <small>{step.reason}</small> : null}
            </div>
            <span className={`step-state step-state--${step.status}`}>
              <StepStatusMark status={step.status} />
              <span>{step.status}</span>
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
