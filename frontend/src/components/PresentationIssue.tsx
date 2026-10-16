import type { SessionPresentation } from "../types";
import { researcherText } from "../researcherLabels";

export function PresentationIssue({ issue }: { issue: NonNullable<SessionPresentation["issue"]> }) {
  return <div role="status" className="presentation-issue">
    <p>{researcherText(issue.user_message)}</p>
    {issue.details?.length ? <ul aria-label="错误与修改意见">
      {issue.details.map((detail, index) => <li key={index}>{researcherText(detail)}</li>)}
    </ul> : null}
  </div>;
}
