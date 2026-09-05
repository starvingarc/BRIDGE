import { MessagePrimitive, ThreadPrimitive } from "@assistant-ui/react";
import { render, screen } from "@testing-library/react";
import { MarkdownText } from "../src/components/MarkdownText";
import { BridgeRuntimeProvider } from "../src/runtime/BridgeRuntimeProvider";
import type { Session } from "../src/types";

describe("Markdown rendering", () => {
  it("does not load model-authored external images", async () => {
    const session: Session = {
      id: "session-1",
      title: "Safe Markdown",
      updated_at: "2026-09-05T06:00:00Z",
      status: "idle",
      messages: [
        {
          id: "message-1",
          role: "assistant",
          content: "Visible evidence note.\n\n![tracking pixel](https://tracker.example/pixel.png)",
          created_at: "2026-09-05T06:00:00Z",
        },
      ],
      uploads: [],
      plan: null,
      artifacts: [],
      error: null,
    };

    render(
      <BridgeRuntimeProvider
        session={session}
        disabled={false}
        onSession={vi.fn()}
        onError={vi.fn()}
      >
        <ThreadPrimitive.Root>
          <ThreadPrimitive.Viewport>
            <ThreadPrimitive.Messages>
              {() => (
                <MessagePrimitive.Root>
                  <MessagePrimitive.Parts components={{ Text: MarkdownText }} />
                </MessagePrimitive.Root>
              )}
            </ThreadPrimitive.Messages>
          </ThreadPrimitive.Viewport>
        </ThreadPrimitive.Root>
      </BridgeRuntimeProvider>,
    );

    expect(await screen.findByText("Visible evidence note.")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
});
