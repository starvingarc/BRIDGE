import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../src/App";
import type { IntakeResponse, Session } from "../src/types";

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
  input_review_required: false,
  pending_input_change: null,
});

const makeIntake = (uploadId: string): IntakeResponse => ({
  upload_id: uploadId,
  facts: {
    product_name: null, product_family: "unknown", target_cell_type: null,
    target_stage: null, sampling_context: "unknown", independent_cultures: null,
    assay: "unknown", matrix_location: null, count_semantics: "unknown",
    source_family_id: null, sample_id_column: null, capture_id_column: null,
    gene_symbol_column: null,
  },
  observed: {
    n_observations: 4, n_genes: 3, matrix_locations: ["X"],
    obs_columns: [], var_columns: [],
  },
  state: "draft", missing_fields: ["assay", "count_semantics"],
  next_tool: null, blockers: [], qc_state: "not_run",
  measurement_spec_ref: null, roadmap: [],
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

const analysisRegistry = {
  tools: [{
    tool_id: "P0-06",
    label: "Program response",
    input_contract: {
      tool_id: "P0-06",
      request_schema_ref: "bridge://schemas/tool-request/v0.2",
      asset_input: null,
      measurement_spec_ref_policy: "optional",
      parameters_allowed: false,
      random_seed_policy: "fixed_zero",
      object_input_modes: [],
    },
  }],
  objects: [],
  assets: [],
  selections: {
    "P0-06": {
      tool_id: "P0-06",
      mode_id: null,
      asset_ids: [],
      object_inputs: [],
      measurement_spec_ref: null,
    },
  },
  measurement_specs: [],
};

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

  it.each(["thinking", "running", "awaiting_approval"] as const)(
    "keeps an explicit stop control reachable while the session is %s",
    async (status) => {
      vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
        if (String(input) === "/api/sessions") {
          return jsonResponse({
            sessions: [{ id: "session-1", title: "Polling assessment", updated_at: "2026-09-05T06:00:00Z" }],
          });
        }
        return jsonResponse(makeSession(status));
      });

      render(<App />);

      expect(await screen.findByRole("button", { name: "Stop analysis" })).toBeEnabled();
    },
  );

  it("keeps a stop response when an older source edit resolves later", async () => {
    const oldSourceResponse = deferred<Response>();
    const current = {
      ...makeSession("awaiting_approval"),
      uploads: [{ id: "upload-1", name: "case.h5ad", kind: "h5ad", size: 12 }],
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const path = String(input);
      if (path === "/api/sessions") {
        return jsonResponse({
          sessions: [{ id: current.id, title: current.title, updated_at: current.updated_at }],
        });
      }
      if (path.includes("/intake?")) return jsonResponse(makeIntake(current.uploads[0].id));
      if (path.endsWith("/inputs") && init?.method === "POST") return oldSourceResponse.promise;
      if (path.endsWith("/stop") && init?.method === "POST") {
        return jsonResponse({ ...current, status: "stopping" });
      }
      return jsonResponse(current);
    });
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByText("4 个观测 · 3 个基因")).toBeInTheDocument();
    const source = await screen.findByLabelText("Data source / experiment reference");
    await user.type(source, "source-family:new{Enter}");
    await vi.waitFor(() => expect(fetchMock.mock.calls.some(
      ([path]) => String(path).endsWith("/inputs"),
    )).toBe(true));
    await user.click(screen.getByRole("button", { name: "Stop analysis" }));
    expect(await screen.findByText(/Current in-process work may still finish/)).toBeInTheDocument();

    await act(async () => {
      oldSourceResponse.resolve(jsonResponse({
        ...current,
        uploads: [{ ...current.uploads[0], source_family_id: "source-family:new" }],
      }));
      await Promise.resolve();
    });

    expect(screen.getAllByText("stopping")).toHaveLength(2);
  });

  it("continues polling after same-status input confirmation starts a new generation", async () => {
    const pending = {
      id: "change-stopping",
      digest: "sha256:change-stopping",
      kind: "source" as const,
      upload_id: "upload-1",
      changes: [{ field: "source_family_id", before: "study-old", after: "study-new" }],
    };
    const stopping = {
      ...makeSession("stopping"),
      input_review_required: true,
      pending_input_change: pending,
    };
    let sessionReads = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const path = String(input);
      if (path === "/api/sessions") {
        return jsonResponse({
          sessions: [{ id: stopping.id, title: stopping.title, updated_at: stopping.updated_at }],
        });
      }
      if (path.endsWith("/input-change/confirm") && init?.method === "POST") {
        return jsonResponse({
          ...stopping,
          input_review_required: false,
          pending_input_change: null,
        });
      }
      if (path === "/api/sessions/session-1") {
        sessionReads += 1;
        return jsonResponse(sessionReads === 1 ? stopping : {
          ...stopping,
          status: "idle",
          input_review_required: false,
          pending_input_change: null,
        });
      }
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Confirm change" }));

    expect(await screen.findAllByText("idle", {}, { timeout: 2_500 })).toHaveLength(2);
    expect(sessionReads).toBe(2);
  }, 4_000);

  it("continues polling a running session after stop fails", async () => {
    let sessionReads = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const path = String(input);
      if (path === "/api/sessions") {
        return jsonResponse({
          sessions: [{
            id: "session-1",
            title: "Polling assessment",
            updated_at: "2026-09-05T06:00:00Z",
          }],
        });
      }
      if (path.endsWith("/stop") && init?.method === "POST") {
        return jsonResponse({ detail: "stop_temporarily_unavailable" }, 503);
      }
      if (path === "/api/sessions/session-1") {
        sessionReads += 1;
        return jsonResponse(makeSession(sessionReads === 1 ? "running" : "idle"));
      }
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Stop analysis" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("stop_temporarily_unavailable");

    expect(await screen.findAllByText("idle", {}, { timeout: 2_500 })).toHaveLength(2);
    expect(sessionReads).toBe(2);
  }, 4_000);

  it("shows exact pending changes, blocks planning, and confirms only that change", async () => {
    const pending = {
      id: "change-1",
      digest: "sha256:change-1",
      kind: "source",
      upload_id: "bbbbbbbb22222222",
      changes: [{ field: "source_family_id", before: "study-old", after: "study-new" }],
    };
    const proposed = {
      ...makeSession("awaiting_approval"),
      uploads: [
        { id: "aaaaaaaa11111111", name: "case.h5ad", kind: "h5ad", size: 12 },
        { id: "bbbbbbbb22222222", name: "case.h5ad", kind: "h5ad", size: 12 },
      ],
      input_review_required: true,
      pending_input_change: pending,
      plan: {
        id: "plan-1",
        digest: "sha256:plan-1",
        status: "proposed",
        summary: "Pending plan",
        steps: [{
          id: "step-1",
          tool_id: "P0-06",
          label: "Program response",
          status: "pending",
          reason: null,
        }],
      },
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const path = String(input);
      if (path === "/api/sessions") {
        return jsonResponse({
          sessions: [{ id: proposed.id, title: proposed.title, updated_at: proposed.updated_at }],
        });
      }
      if (path.endsWith("/input-change/confirm") && init?.method === "POST") {
        return jsonResponse({
          ...proposed,
          status: "idle",
          input_review_required: false,
          pending_input_change: null,
          plan: null,
        });
      }
      if (path.includes("/intake?")) {
        const uploadId = new URL(path, "http://testserver").searchParams.get("upload_id");
        return jsonResponse(makeIntake(uploadId!));
      }
      if (path.endsWith("/analysis-inputs")) return jsonResponse(analysisRegistry);
      return jsonResponse(proposed);
    });
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByText("4 个观测 · 3 个基因")).toBeInTheDocument();
    const reviewCard = await screen.findByRole("region", { name: "Input change review" });
    expect(reviewCard).toHaveTextContent("source_family_id");
    expect(within(reviewCard).getByText("case.h5ad")).toBeInTheDocument();
    expect(within(reviewCard).getByText("bbbbbbbb22222222")).toBeInTheDocument();
    expect(within(reviewCard).queryByText("aaaaaaaa11111111")).not.toBeInTheDocument();
    expect(screen.getByText('"study-old"')).toBeInTheDocument();
    expect(screen.getByText('"study-new"')).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm analysis" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Discard change" })).toBeEnabled();
    expect(screen.getByLabelText("Message")).toBeEnabled();

    await user.click(screen.getByText("Analysis inputs"));
    await user.selectOptions(await screen.findByLabelText("Analysis tool"), "P0-06");
    expect(screen.getByRole("button", { name: "Prepare plan" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Confirm change" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/sessions/session-1/input-change/confirm",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          change_id: "change-1",
          change_digest: "sha256:change-1",
        }),
      }),
    ));
    expect(screen.queryByRole("region", { name: "Input change review" })).not.toBeInTheDocument();
  });

  it("offers explicit keep-current confirmation when review has no exact edit", async () => {
    const review = {
      ...makeSession("idle"),
      input_review_required: true,
      pending_input_change: null,
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const path = String(input);
      if (path === "/api/sessions") {
        return jsonResponse({
          sessions: [{ id: review.id, title: review.title, updated_at: review.updated_at }],
        });
      }
      if (path.endsWith("/input-review/keep") && init?.method === "POST") {
        return jsonResponse({ ...review, input_review_required: false });
      }
      return jsonResponse(review);
    });
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByText(/Review the existing input forms/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Keep current inputs" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/sessions/session-1/input-review/keep",
      expect.objectContaining({ method: "POST", body: "{}" }),
    ));
  });
});
