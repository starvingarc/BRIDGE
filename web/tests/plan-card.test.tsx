import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SourceInputForms } from "../src/components/Conversation";
import { PlanCard, PlanHistory } from "../src/components/PlanCard";
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

  it("disables confirmation when every proposed step is blocked", async () => {
    const approve = vi.fn();
    const user = userEvent.setup();
    const blockedPlan: Plan = {
      ...plan,
      steps: [{ ...plan.steps[0], status: "blocked", reason: "input_not_eligible" }],
    };

    render(
      <PlanCard
        plan={blockedPlan}
        sessionStatus="awaiting_approval"
        busy={false}
        onApprove={approve}
      />,
    );

    const button = screen.getByRole("button", { name: "Confirm analysis" });
    expect(button).toBeDisabled();
    await user.click(button);
    expect(approve).not.toHaveBeenCalled();
  });

  it("keeps a completed stage visible beside the next proposal", () => {
    const completed: Plan = {
      ...plan,
      id: "plan-qc",
      status: "completed",
      summary: "Input QC completed.",
      steps: [{ ...plan.steps[0], status: "succeeded", reason: "QC evidence retained." }],
    };

    render(
      <>
        <PlanHistory plans={[completed]} currentPlanId={plan.id} />
        <PlanCard plan={plan} sessionStatus="awaiting_approval" busy={false} onApprove={() => undefined} />
      </>,
    );

    expect(screen.getByText("Input QC completed.")).toBeInTheDocument();
    expect(screen.getByText("Review the declared input before execution.")).toBeInTheDocument();
    expect(screen.getByText("succeeded")).toBeInTheDocument();
    expect(screen.getByText("QC evidence retained.")).toBeInTheDocument();
  });

  it("distinguishes duplicate upload names and binds valid source punctuation to the selected upload", async () => {
    const save = vi.fn();
    const user = userEvent.setup();
    render(
      <SourceInputForms
        uploads={[
          { id: "aaaaaaaa11111111", name: "sample.h5ad", kind: "h5ad", size: 1 },
          { id: "bbbbbbbb22222222", name: "sample.h5ad", kind: "h5ad", size: 1 },
        ]}
        disabled={false}
        onSourceInput={save}
      />,
    );

    expect(screen.getByText("sample.h5ad · aaaaaaaa")).toBeInTheDocument();
    expect(screen.getByText("sample.h5ad · bbbbbbbb")).toBeInTheDocument();
    const inputs = screen.getAllByLabelText("Data source / experiment reference");
    await user.type(inputs[1], "Study_1.batch-2:donor.A");
    expect(inputs[1]).toBeValid();
    await user.click(screen.getAllByRole("button", { name: "Save" })[1]);
    expect(save).toHaveBeenCalledWith("bbbbbbbb22222222", "Study_1.batch-2:donor.A");

    for (const invalidValue of ["invalid source", "invalid/source"]) {
      await user.clear(inputs[1]);
      await user.type(inputs[1], invalidValue);
      expect((inputs[1] as HTMLInputElement).checkValidity()).toBe(false);
    }
  });

  it.each(["partial", "blocked", "cancelled"] as const)(
    "does not render %s as succeeded",
    (status) => {
      const statePlan: Plan = {
        ...plan,
        status: status === "partial" || status === "cancelled" ? status : "failed",
        steps: [{ ...plan.steps[0], status }],
      };
      render(
        <PlanCard plan={statePlan} sessionStatus="idle" busy={false} onApprove={() => undefined} />,
      );

      expect(screen.getByLabelText(status[0].toUpperCase() + status.slice(1))).toBeInTheDocument();
      expect(screen.queryByLabelText("Succeeded")).not.toBeInTheDocument();
    },
  );
});
