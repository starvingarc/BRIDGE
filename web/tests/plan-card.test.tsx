import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PlanCard } from "../src/components/PlanCard";
import type { Plan } from "../src/types";

const plan: Plan = {
  id: "plan-1",
  digest: "sha256:exact",
  status: "proposed",
  summary: "Review the declared input before execution.",
  steps: [
    {
      id: "step-1",
      tool_id: "p0-01",
      label: "Check input data",
      status: "pending",
      reason: null,
    },
  ],
};

describe("PlanCard", () => {
  it("allows confirmation only for the proposed plan in awaiting-approval state", async () => {
    const approve = vi.fn();
    const user = userEvent.setup();
    const { rerender } = render(
      <PlanCard plan={plan} sessionStatus="awaiting_approval" busy={false} onApprove={approve} />,
    );

    await user.click(screen.getByRole("button", { name: "Confirm analysis" }));
    expect(approve).toHaveBeenCalledOnce();

    rerender(<PlanCard plan={plan} sessionStatus="running" busy={false} onApprove={approve} />);
    expect(screen.getByRole("button", { name: "Analysis running…" })).toBeDisabled();
  });
});
