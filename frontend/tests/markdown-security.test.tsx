import { MessagePrimitive, ThreadPrimitive } from "@assistant-ui/react";
import { render, screen } from "@testing-library/react";
import { MarkdownText, ResearcherMarkdownText } from "../src/components/MarkdownText";
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
      input_review_required: false,
      pending_input_change: null,
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

    expect(await screen.findByText("Visible evidence note.", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
});


it("labels assistant text including code spans without modifying citation URLs or the stored message", async () => {
  const content = "P0-03：`scientific_source_review_pending`。\n\n[查看 P0-04](https://example.org/P0-04?q=unknown)";
  const session: Session = { id:"case",title:"case",updated_at:"2026-09-23T00:00:00Z",status:"idle",uploads:[],artifacts:[],plan:null,error:null,input_review_required:false,pending_input_change:null,
    messages:[{id:"m",role:"assistant",content,created_at:"2026-09-23T00:00:00Z"}] };
  const { container } = render(<BridgeRuntimeProvider session={session} disabled={false} onSession={vi.fn()} onError={vi.fn()}>
    <ThreadPrimitive.Root><ThreadPrimitive.Viewport><ThreadPrimitive.Messages>{() => <MessagePrimitive.Root>
      <MessagePrimitive.Parts components={{Text:ResearcherMarkdownText}} />
    </MessagePrimitive.Root>}</ThreadPrimitive.Messages></ThreadPrimitive.Viewport></ThreadPrimitive.Root>
  </BridgeRuntimeProvider>);
  expect(await screen.findByRole("link",{name:"查看 发育阶段"})).toHaveAttribute("href","https://example.org/P0-04?q=unknown");
  expect(container.textContent).not.toMatch(/P0-\d+|scientific_source_review_pending/);
  expect(session.messages[0].content).toBe(content);
});
