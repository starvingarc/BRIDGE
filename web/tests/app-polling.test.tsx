import { render, screen } from "@testing-library/react";
import App from "../src/App";
import type { Session } from "../src/types";

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const makeSession = (status: Session["status"]): Session => ({
  id: "session-1",
  title: "Polling assessment",
  updated_at: "2026-09-05T06:00:00Z",
  status,
  messages: [],
  uploads: [],
  plan: null,
  artifacts: [],
  error: null,
});

beforeEach(() => {
  localStorage.clear();
});

describe("session loading and polling", () => {
  it("keeps retrying a busy session after a transient poll failure", async () => {
    let sessionReads = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const path = String(input);
      if (path === "/api/sessions") {
        return jsonResponse({
          sessions: [{ id: "session-1", title: "Polling assessment", updated_at: "2026-09-05T06:00:00Z" }],
        });
      }
      if (path === "/api/sessions/session-1") {
        sessionReads += 1;
        if (sessionReads === 1) return jsonResponse(makeSession("thinking"));
        if (sessionReads === 2) return jsonResponse({ detail: "temporary_unavailable" }, 503);
        if (sessionReads === 3) return jsonResponse(makeSession("thinking"));
        return jsonResponse(makeSession("idle"));
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<App />);

    expect(await screen.findAllByText("thinking")).toHaveLength(2);
    expect(await screen.findByRole("alert", {}, { timeout: 2_000 })).toHaveTextContent(
      "temporary_unavailable",
    );
    expect(await screen.findAllByText("idle", {}, { timeout: 6_000 })).toHaveLength(2);
    expect(sessionReads).toBe(4);
  }, 8_000);

  it("continues normal polling when a successful response remains busy", async () => {
    let sessionReads = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const path = String(input);
      if (path === "/api/sessions") {
        return jsonResponse({
          sessions: [{ id: "session-1", title: "Polling assessment", updated_at: "2026-09-05T06:00:00Z" }],
        });
      }
      sessionReads += 1;
      if (sessionReads < 3) return jsonResponse(makeSession("running"));
      return jsonResponse(makeSession("idle"));
    });

    render(<App />);

    expect(await screen.findAllByText("running")).toHaveLength(2);
    expect(await screen.findAllByText("idle", {}, { timeout: 3_500 })).toHaveLength(2);
    expect(sessionReads).toBe(3);
  }, 5_000);

  it("aborts an in-flight poll when the app unmounts", async () => {
    let sessionReads = 0;
    let pollSignal: AbortSignal | undefined;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const path = String(input);
      if (path === "/api/sessions") {
        return jsonResponse({
          sessions: [{ id: "session-1", title: "Polling assessment", updated_at: "2026-09-05T06:00:00Z" }],
        });
      }
      sessionReads += 1;
      if (sessionReads === 1) return jsonResponse(makeSession("running"));
      pollSignal = init?.signal ?? undefined;
      return new Promise<Response>((_resolve, reject) => {
        pollSignal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      });
    });

    const view = render(<App />);
    expect(await screen.findAllByText("running")).toHaveLength(2);
    await vi.waitFor(() => expect(pollSignal).toBeDefined(), { timeout: 2_000 });

    view.unmount();

    expect(pollSignal?.aborted).toBe(true);
  });

  it("stops polling and returns to login after a 401", async () => {
    let sessionReads = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const path = String(input);
      if (path === "/api/sessions") {
        return jsonResponse({
          sessions: [{ id: "session-1", title: "Polling assessment", updated_at: "2026-09-05T06:00:00Z" }],
        });
      }
      sessionReads += 1;
      if (sessionReads === 1) return jsonResponse(makeSession("thinking"));
      return jsonResponse({ detail: "authentication_required" }, 401);
    });

    render(<App />);
    expect(await screen.findAllByText("thinking")).toHaveLength(2);
    expect(
      await screen.findByRole("heading", { name: "Private research preview" }, { timeout: 2_000 }),
    ).toBeInTheDocument();
    const readsAfterLogout = sessionReads;
    await new Promise((resolve) => window.setTimeout(resolve, 1_500));
    expect(sessionReads).toBe(readsAfterLogout);
  }, 5_000);

  it("keeps the signed-in workspace visible when the selected session cannot load", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const path = String(input);
      if (path === "/api/sessions") {
        return jsonResponse({
          sessions: [{ id: "session-1", title: "Unavailable assessment", updated_at: "2026-09-05T06:00:00Z" }],
        });
      }
      return jsonResponse({ detail: "session_temporarily_unavailable" }, 503);
    });

    render(<App />);

    expect(await screen.findByRole("heading", { name: "No analysis selected" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("session_temporarily_unavailable");
    expect(screen.queryByRole("heading", { name: "Private research preview" })).not.toBeInTheDocument();
  });
});
