import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readBoundedText, ResultsPane, WorkbenchDivider } from "../src/components/ResultsPane";
import type { Session } from "../src/types";

const session: Session = {
  id: "session id",
  title: "Assessment",
  updated_at: "2026-09-05T05:00:00Z",
  status: "idle",
  messages: [],
  uploads: [],
  plan: null,
  error: null,
  artifacts: [
    {
      id: "figure png",
      name: "Observed figure.png",
      kind: "figure",
      media_type: "image/png",
      url: "https://untrusted.example/private-path",
      tool_id: "p0-01",
    },
    {
      id: "figure svg",
      name: "Observed figure.svg",
      kind: "figure",
      media_type: "image/svg+xml",
      url: "/ignored",
      tool_id: "p0-01",
    },
    {
      id: "table id",
      name: "Observed table",
      kind: "table",
      media_type: "text/tab-separated-values",
      url: "/ignored",
      tool_id: "p0-01",
    },
    {
      id: "download id",
      name: "Evidence bundle",
      kind: "download",
      media_type: "application/zip",
      url: "/ignored",
      tool_id: "p0-01",
    },
  ],
};

describe("ResultsPane", () => {
  it("uses registered same-origin artifact routes instead of arbitrary response URLs", () => {
    render(<ResultsPane session={session} />);
    const image = screen.getByRole("img", { name: "Observed figure.svg" });
    expect(image).toHaveAttribute(
      "src",
      "/api/sessions/session%20id/artifacts/figure%20svg",
    );
    expect(screen.getByRole("tab", { name: /^Figures/ })).toBeInTheDocument();
    expect(image).not.toHaveAttribute("src", expect.stringContaining("untrusted.example"));
  });

  it("switches tabs and renders an authenticated table preview as inert cells", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("marker\tstate\nA\tobserved", {
        status: 200,
        headers: { "Content-Type": "text/tab-separated-values" },
      }),
    );
    render(<ResultsPane session={session} />);

    await user.click(screen.getByRole("tab", { name: /Tables/ }));

    expect(await screen.findByRole("columnheader", { name: "marker" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "observed" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/sessions/session%20id/artifacts/table%20id",
      expect.objectContaining({ credentials: "same-origin" }),
    );
  });

  it("lists all artifacts in Downloads while previewing one distinct figure view", async () => {
    const user = userEvent.setup();
    const { container } = render(<ResultsPane session={session} />);
    await user.click(screen.getByRole("tab", { name: /^Downloads/ }));

    const originalLinks = Array.from(container.querySelectorAll<HTMLAnchorElement>(".download-row"));
    expect(originalLinks.map((link) => link.getAttribute("href"))).toEqual([
      "/api/sessions/session%20id/artifacts/figure%20png",
      "/api/sessions/session%20id/artifacts/figure%20svg",
      "/api/sessions/session%20id/artifacts/table%20id",
      "/api/sessions/session%20id/artifacts/download%20id",
    ]);
  });

  it("applies the same viewport-aware upper bound to keyboard resizing", () => {
    const onWidth = vi.fn();
    const originalWidth = window.innerWidth;
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1_000 });
    render(<WorkbenchDivider width={435} onWidth={onWidth} />);

    fireEvent.keyDown(screen.getByRole("separator"), { key: "ArrowLeft" });

    expect(onWidth).toHaveBeenCalledWith(440);
    Object.defineProperty(window, "innerWidth", { configurable: true, value: originalWidth });
  });

  it("stops reading and cancels an artifact stream at the preview byte limit", async () => {
    const cancel = vi.fn();
    let pulls = 0;
    const stream = new ReadableStream<Uint8Array>({
      pull(controller) {
        pulls += 1;
        controller.enqueue(new TextEncoder().encode("x".repeat(160_000)));
      },
      cancel,
    });

    const result = await readBoundedText(new Response(stream), 200_000);

    expect(result.truncated).toBe(true);
    expect(result.text).toHaveLength(200_000);
    expect(pulls).toBe(2);
    expect(cancel).toHaveBeenCalledOnce();
  });
});
