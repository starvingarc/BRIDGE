import { ArtifactCard } from "../src/components/ResultsPane";

describe("shared research snapshot", () => {
  it.each(["0.2.0", "0.3.0"])("renders the bound %s snapshot without reinterpreting facts", async (version) => {
    const snapshot = {
      object_version: version,
      snapshot_sha256: "a".repeat(64), input_revision: "2", graph_version: 3,
      audience: "internal_research", scientific_validation: "not_qualified",
      report_draft_json: JSON.stringify({ claim_blocks: [{ text: "受限研究结果" }] }),
      evidence_requirement_set_json: JSON.stringify({ requirements: [{ state: "open" }] }),
      ...(version === "0.3.0" ? {
        context_sections_json: JSON.stringify([["产品资料", { name: "修订产品 <img src=x onerror=alert(1)>" }]]),
      } : {}),
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(snapshot)));
    const { container } = render(<ArtifactCard sessionId="case" artifact={{
      id: "snapshot", name: "研究快照", kind: "download", media_type: "application/json",
      url: "/ignored", tool_id: "P0-10",
      research_report: { snapshot_sha256: snapshot.snapshot_sha256, input_revision: "2", graph_version: 3 },
    }} />);
    expect(await screen.findByText("受限研究结果")).toBeInTheDocument();
    expect(screen.getByText(/尚有 1 项/)).toBeInTheDocument();
    if (version === "0.3.0") {
      expect(screen.getByText("产品资料")).toBeInTheDocument();
      expect(screen.getByText(/修订产品/)).toBeInTheDocument();
      expect(container.querySelector("pre img")).toBeNull();
    } else {
      expect(screen.queryByText("产品资料")).not.toBeInTheDocument();
    }
  });
});
import { act, fireEvent, render, screen } from "@testing-library/react";
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
  input_review_required: false,
  pending_input_change: null,
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

  it("fetches a registered octet-stream Parquet preview and renders inert table cells", async () => {
    const user = userEvent.setup();
    const parquetSession: Session = {
      ...session,
      artifacts: [{
        id: "parquet id",
        name: "observations.parquet",
        kind: "table",
        media_type: "application/octet-stream",
        url: "https://untrusted.example/PAR1",
        tool_id: "p0-09",
      }],
    };
    const maliciousCell = "<img src=x onerror=alert(1)>";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        columns: ["metric", "value"],
        rows: [[maliciousCell, 7]],
        total_rows: 1,
        total_columns: 2,
        truncated: false,
      }), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    const { container } = render(<ResultsPane session={parquetSession} />);

    await user.click(screen.getByRole("tab", { name: /Tables/ }));

    expect(await screen.findByRole("columnheader", { name: "metric" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: maliciousCell })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "7" })).toBeInTheDocument();
    expect(container.querySelector("td img")).toBeNull();
    expect(screen.queryByText("PAR1")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/sessions/session%20id/artifacts/parquet%20id/preview",
      expect.objectContaining({ credentials: "same-origin" }),
    );
  });

  it("renders exact signed and unsigned integer display strings without rounding", async () => {
    const user = userEvent.setup();
    const parquetSession: Session = {
      ...session,
      artifacts: [{
        id: "integer parquet",
        name: "integers.parquet",
        kind: "table",
        media_type: "application/octet-stream",
        url: "/ignored",
        tool_id: "p0-09",
      }],
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        columns: ["signed", "unsigned"],
        rows: [
          [9007199254740991, "9007199254740992"],
          ["-9007199254740993", "18446744073709551615"],
        ],
        total_rows: 2,
        total_columns: 2,
        truncated: false,
      }), { status: 200 }),
    );
    render(<ResultsPane session={parquetSession} />);

    await user.click(screen.getByRole("tab", { name: /Tables/ }));

    expect(await screen.findByRole("cell", { name: "9007199254740991" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "9007199254740992" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "-9007199254740993" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "18446744073709551615" })).toBeInTheDocument();
  });

  it("renders finite float64 values outside the safe integer range", async () => {
    const user = userEvent.setup();
    const parquetSession: Session = {
      ...session,
      artifacts: [{
        id: "large float parquet",
        name: "large-floats.parquet",
        kind: "table",
        media_type: "application/octet-stream",
        url: "/ignored",
        tool_id: "p0-09",
      }],
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        columns: ["float64"],
        rows: [["1e+20"], ["-1e+20"], [1.25]],
        total_rows: 3,
        total_columns: 1,
        truncated: false,
      }), { status: 200 }),
    );
    render(<ResultsPane session={parquetSession} />);

    await user.click(screen.getByRole("tab", { name: /Tables/ }));

    expect(await screen.findByRole("cell", { name: "1e+20" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "-1e+20" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "1.25" })).toBeInTheDocument();
  });

  it("falls back instead of displaying a rounded unsafe JSON integer", async () => {
    const user = userEvent.setup();
    const parquetSession: Session = {
      ...session,
      artifacts: [{
        id: "unsafe integer parquet",
        name: "unsafe.parquet",
        kind: "table",
        media_type: "application/octet-stream",
        url: "/ignored",
        tool_id: "p0-09",
      }],
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        '{"columns":["value"],"rows":[[9007199254740993]],"total_rows":1,"total_columns":1,"truncated":false}',
        { status: 200 },
      ),
    );
    render(<ResultsPane session={parquetSession} />);

    await user.click(screen.getByRole("tab", { name: /Tables/ }));

    expect(await screen.findByText("This artifact could not be previewed.")).toBeInTheDocument();
    expect(screen.queryByRole("cell", { name: "9007199254740992" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download original file" })).toBeInTheDocument();
  });

  it("renders a valid empty Parquet table with its registered header", async () => {
    const user = userEvent.setup();
    const parquetSession: Session = {
      ...session,
      artifacts: [{
        id: "empty parquet",
        name: "empty.parquet",
        kind: "table",
        media_type: "application/octet-stream",
        url: "/ignored",
        tool_id: "p0-09",
      }],
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        columns: ["metric"],
        rows: [],
        total_rows: 0,
        total_columns: 1,
        truncated: false,
      }), { status: 200 }),
    );
    render(<ResultsPane session={parquetSession} />);

    await user.click(screen.getByRole("tab", { name: /Tables/ }));

    expect(await screen.findByRole("columnheader", { name: "metric" })).toBeInTheDocument();
    expect(screen.queryAllByRole("cell")).toHaveLength(0);
    expect(screen.queryByText(/Preview truncated/)).not.toBeInTheDocument();
  });

  it("states Parquet preview truncation with displayed and total shape", async () => {
    const user = userEvent.setup();
    const parquetSession: Session = {
      ...session,
      artifacts: [{
        id: "bounded parquet",
        name: "bounded.parquet",
        kind: "table",
        media_type: "application/vnd.apache.parquet",
        url: "/ignored",
        tool_id: "p0-09",
      }],
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        columns: ["metric"],
        rows: [["observed"]],
        total_rows: 101,
        total_columns: 25,
        truncated: true,
      }), { status: 200 }),
    );
    render(<ResultsPane session={parquetSession} />);

    await user.click(screen.getByRole("tab", { name: /Tables/ }));

    expect(await screen.findByText(
      "Preview truncated. Showing 1 of 101 rows and 1 of 25 columns. Download the original artifact for complete content.",
    )).toBeInTheDocument();
  });

  it("aborts and ignores an obsolete Parquet preview after the session changes", async () => {
    const user = userEvent.setup();
    const firstSession: Session = {
      ...session,
      id: "first session",
      artifacts: [{
        id: "old parquet",
        name: "old.parquet",
        kind: "table",
        media_type: "application/octet-stream",
        url: "/ignored",
        tool_id: "p0-09",
      }],
    };
    const secondSession: Session = {
      ...firstSession,
      id: "second session",
      artifacts: [{ ...firstSession.artifacts[0], id: "new parquet", name: "new.parquet" }],
    };
    let resolveOld: ((response: Response) => void) | undefined;
    let oldSignal: AbortSignal | null | undefined;
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockImplementationOnce((_input, init) => {
        oldSignal = init?.signal;
        return new Promise<Response>((resolve) => { resolveOld = resolve; });
      })
      .mockResolvedValueOnce(new Response(JSON.stringify({
        columns: ["metric"],
        rows: [["new value"]],
        total_rows: 1,
        total_columns: 1,
        truncated: false,
      }), { status: 200 }));
    const { rerender } = render(<ResultsPane session={firstSession} />);
    await user.click(screen.getByRole("tab", { name: /Tables/ }));
    expect(fetchMock).toHaveBeenCalledTimes(1);

    rerender(<ResultsPane session={secondSession} />);

    expect(await screen.findByRole("cell", { name: "new value" })).toBeInTheDocument();
    expect(oldSignal?.aborted).toBe(true);
    await act(async () => {
      resolveOld?.(new Response(JSON.stringify({
        columns: ["metric"],
        rows: [["obsolete value"]],
        total_rows: 1,
        total_columns: 1,
        truncated: false,
      }), { status: 200 }));
      await Promise.resolve();
    });
    expect(screen.queryByRole("cell", { name: "obsolete value" })).not.toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "new value" })).toBeInTheDocument();
  });

  it("shows an explicit original-download fallback when a Parquet preview fails", async () => {
    const user = userEvent.setup();
    const parquetSession: Session = {
      ...session,
      artifacts: [{
        id: "failed parquet",
        name: "failed.parquet",
        kind: "table",
        media_type: "application/octet-stream",
        url: "/ignored",
        tool_id: "p0-09",
      }],
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "artifact_preview_too_large" }), { status: 413 }),
    );
    render(<ResultsPane session={parquetSession} />);

    await user.click(screen.getByRole("tab", { name: /Tables/ }));

    expect(await screen.findByText("This artifact could not be previewed.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download original file" })).toHaveAttribute(
      "href",
      "/api/sessions/session%20id/artifacts/failed%20parquet",
    );
  });

  it("never decodes an unsupported binary table as text", async () => {
    const user = userEvent.setup();
    const binarySession: Session = {
      ...session,
      artifacts: [{
        id: "binary id",
        name: "matrix.bin",
        kind: "table",
        media_type: "application/octet-stream",
        url: "/ignored",
        tool_id: "p0-09",
      }],
    };
    const fetchMock = vi.spyOn(globalThis, "fetch");
    render(<ResultsPane session={binarySession} />);

    await user.click(screen.getByRole("tab", { name: /Tables/ }));

    expect(screen.getByText("A browser preview is not available for this artifact.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download original file" })).toHaveAttribute(
      "href",
      "/api/sessions/session%20id/artifacts/binary%20id",
    );
    expect(fetchMock).not.toHaveBeenCalled();
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
