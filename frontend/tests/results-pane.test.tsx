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
import { readBoundedText, ResultsPane } from "../src/components/ResultsPane";
import type { Artifact, Session } from "../src/types";

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
  it("keeps an unsaved overview draft when browsing result tabs", async () => {
    const user = userEvent.setup();
    render(<ResultsPane session={{ ...session, artifacts: [] }}
      overview={<input aria-label="Research note" defaultValue="" />} />);
    await user.type(screen.getByRole("textbox", { name: "Research note" }), "Keep this draft");
    await user.click(screen.getByRole("tab", { name: /数据表/ }));
    expect(screen.queryByRole("textbox", { name: "Research note" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "评估概览" }));
    expect(screen.getByRole("textbox", { name: "Research note" })).toHaveValue("Keep this draft");
  });

  it("selects and focuses result tabs using the keyboard", async () => {
    const user = userEvent.setup();
    render(<ResultsPane session={{ ...session, artifacts: [] }} overview={<p>Research context</p>} />);
    screen.getByRole("tab", { name: "评估概览" }).focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "研究报告" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "研究报告" })).toHaveFocus();
    await user.keyboard("{Home}");
    expect(screen.getByRole("tab", { name: "评估概览" })).toHaveFocus();
    expect(screen.getByText("Research context")).toBeVisible();
  });

  it("uses registered same-origin artifact routes after opening originals", async () => {
    render(<ResultsPane session={session} />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    await userEvent.click(screen.getByText("全部原始图像附件（独立查看）"));
    const image = await screen.findByRole("img", { name: "Observed figure.svg" });
    expect(image).toHaveAttribute(
      "src",
      "/api/sessions/session%20id/artifacts/figure%20svg",
    );
    expect(screen.getByRole("tab", { name: /^图表/ })).toBeInTheDocument();
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

    await user.click(screen.getByRole("tab", { name: /数据表/ }));

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

    await user.click(screen.getByRole("tab", { name: /数据表/ }));

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

  it("shows the file's real column names, adding a known name without replacing it", async () => {
    const user = userEvent.setup();
    const qcSession: Session = {
      ...session,
      artifacts: [{ id: "qc metrics", name: "qc_metrics.parquet", kind: "table", media_type: "application/octet-stream", url: "", tool_id: "p0-01" }],
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      columns: ["n_genes_by_counts", "pct_counts_mt", "total_counts", "tool_id"],
      rows: [[812, 3.5, 2104, "p0-01"]], total_rows: 1, total_columns: 4, truncated: false,
    }), { status: 200, headers: { "Content-Type": "application/json" } }));
    render(<ResultsPane session={qcSession} />);
    await user.click(screen.getByRole("tab", { name: /数据表/ }));
    for (const name of ["n_genes_by_counts", "pct_counts_mt", "total_counts"]) {
      expect(await screen.findByRole("columnheader", { name })).toBeInTheDocument();
    }
    expect(screen.getByRole("columnheader", { name: /分析功能\s*tool_id/ })).toBeInTheDocument();
    expect(screen.queryByText("其他字段")).not.toBeInTheDocument();
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

    await user.click(screen.getByRole("tab", { name: /数据表/ }));

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

    await user.click(screen.getByRole("tab", { name: /数据表/ }));

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

    await user.click(screen.getByRole("tab", { name: /数据表/ }));

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

    await user.click(screen.getByRole("tab", { name: /数据表/ }));

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

    await user.click(screen.getByRole("tab", { name: /数据表/ }));

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
    await user.click(screen.getByRole("tab", { name: /数据表/ }));
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

    await user.click(screen.getByRole("tab", { name: /数据表/ }));

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

    await user.click(screen.getByRole("tab", { name: /数据表/ }));

    expect(screen.getByText("A browser preview is not available for this artifact.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download original file" })).toHaveAttribute(
      "href",
      "/api/sessions/session%20id/artifacts/binary%20id",
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("lists research figures and tables in Downloads without machine records while previewing one distinct figure view", async () => {
    const user = userEvent.setup();
    const { container } = render(<ResultsPane session={session} />);
    await user.click(screen.getByRole("tab", { name: /^下载/ }));

    const originalLinks = Array.from(container.querySelectorAll<HTMLAnchorElement>(".download-row"));
    expect(originalLinks.map((link) => link.getAttribute("href"))).toEqual([
      "/api/sessions/session%20id/artifacts/figure%20png",
      "/api/sessions/session%20id/artifacts/figure%20svg",
      "/api/sessions/session%20id/artifacts/table%20id",
    ]);
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


describe("historical report acknowledgement", () => {
  const historical = (name: string, media_type: string, kind: Artifact["kind"]): Artifact => ({
    id: "history id", name, media_type, kind, tool_id: "P0-10", url: "https://must-not-use.invalid",
    content_class: "research_report", access_state: "historical_unreviewed",
    acknowledged: false, acknowledgement_required: true,
    acknowledgement_url: "https://must-not-use.invalid/acknowledge",
    warning: "这是历史报告，尚未按当前输入和证据重新核对。",
    research_report: { snapshot_sha256: "a".repeat(64), input_revision: "2", graph_version: 3 },
  });
  it.each([
    ["research_report.html", "text/html", "download"],
    ["research_report.json", "application/json", "download"],
    ["research_report.csv", "text/csv", "table"],
    ["research_report.svg", "image/svg+xml", "figure"],
  ] as const)("gates %s without fetching and keeps historical status after explicit confirmation", async (name, mime, kind) => {
    const artifact = historical(name, mime, kind);
    const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({
      ...artifact, acknowledged: true, acknowledgement_required: false,
    }));
    const { container, rerender } = render(<ArtifactCard sessionId="case id" artifact={artifact} />);
    expect(fetcher).not.toHaveBeenCalled();
    expect(container.querySelector("a, img")).toBeNull();
    expect(screen.getByRole("note")).toHaveTextContent(artifact.warning!);
    await userEvent.click(screen.getByRole("button", { name: "我已了解，开放历史原件下载" }));
    const link = await screen.findByRole("link", { name: `下载历史原件：${name}` });
    expect(link).toHaveAttribute("href", "/api/sessions/case%20id/artifacts/history%20id");
    expect(link).toHaveAttribute("download", name);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher).toHaveBeenCalledWith("/api/sessions/case%20id/artifacts/history%20id/acknowledge",
      expect.objectContaining({ method: "POST", body: "{}", credentials: "same-origin" }));
    expect(screen.getByRole("note")).toHaveTextContent(artifact.warning!);
    expect(screen.queryByRole("region", { name: "同版本研究报告" })).not.toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
    // A refreshed server projection owns access; a previous local response cannot override it.
    rerender(<ArtifactCard sessionId="case id" artifact={{ ...artifact }} />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "我已了解，开放历史原件下载" })).toBeEnabled();
  });
  it("keeps access closed after a failed acknowledgement and allows a retry", async () => {
    const artifact = historical("report.json", "application/json", "download");
    const fetcher = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json({ user_message: "确认未完成，请重试。" }, { status: 409 }))
      .mockResolvedValueOnce(Response.json({ ...artifact, acknowledged: true, acknowledgement_required: false }));
    const { container } = render(<ArtifactCard sessionId="case" artifact={artifact} />);
    await userEvent.click(screen.getByRole("button", { name: "我已了解，开放历史原件下载" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("确认未完成，请重试。");
    expect(container.querySelector("a, img")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "我已了解，开放历史原件下载" }));
    expect(await screen.findByRole("link", { name: "下载历史原件：report.json" })).toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});


it("names the producing analysis without exposing its internal ID or rewriting artifact routes", () => {
  const artifact: Artifact = { id:"original-artifact", name:"P0-04-summary.csv", kind:"download",
    media_type:"text/csv", tool_id:"P0-04", url:"/ignored" };
  const { container } = render(<ArtifactCard sessionId="case" artifact={artifact} view="download" />);
  expect(container.textContent).not.toMatch(/P0-04/);
  expect(screen.getByText("发育阶段")).toBeInTheDocument();
  expect(screen.getAllByRole("link")[0]).toHaveAttribute("href", "/api/sessions/case/artifacts/original-artifact");
  expect(screen.getAllByRole("link")[0]).toHaveAttribute("download", "P0-04-summary.csv");
});


it("translates table fields and known measurement units while retaining unknown scientific terms and download identity", async () => {
  const text = "metric_id\tvalue\tnumerator\tdenominator\tunit\trelation\tcustom_measurement\n"
    + "native_s_g2m_fraction\t0.3296323452393422\t3147\t9547\tfraction\tsupports\tTP53\n";
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(text));
  const item: Artifact = {id:"readable-table",name:"exact.tsv",kind:"table",media_type:"text/tab-separated-values",tool_id:"P0-06",url:"/ignored"};
  render(<ArtifactCard sessionId="case" artifact={item} />);
  expect(await screen.findByRole("columnheader", {name:/^测量名称\s*metric_id$/})).toBeVisible();
  expect(screen.getByRole("columnheader", {name:/^分母\s*denominator$/})).toBeVisible();
  expect(screen.getByRole("columnheader", {name:"custom_measurement"})).toBeVisible();
  expect(screen.getByRole("cell", {name:"S / G2M 期细胞比例"})).toBeVisible();
  expect(screen.getByRole("cell", {name:"比例（0–1）"})).toBeVisible();
  expect(screen.getByRole("cell", {name:"支持"})).toBeVisible();
  expect(screen.getByRole("cell", {name:"0.3296323452393422"})).toBeVisible();
  expect(screen.getByRole("cell", {name:"TP53"})).toBeVisible();
  expect(screen.queryByText("custom_measurement", {selector:"code"})).not.toBeInTheDocument();
  expect(screen.queryByText("原始字段名")).not.toBeInTheDocument();
  expect(screen.getByRole("link", {name:/下载|Download/})).toHaveAttribute("download","exact.tsv");
});

describe("research report reading path", () => {
  const report = (id: string, state: "current" | "historical_unreviewed", graph = 3): Artifact => ({
    id, name: "research_report.html", kind: "download", media_type: "text/html",
    tool_id: "P0-10", url: "https://must-not-use.invalid",
    content_class: "research_report", access_state: state,
    research_report: {input_revision: "2", graph_version: graph, snapshot_sha256: String(graph).repeat(64)},
  });
  it("opens a dedicated current report reader and keeps historical bytes behind acknowledgement", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("<!doctype html><h1>受限研究结果</h1>"));
    render(<ResultsPane session={{...session, artifacts: [report("old", "historical_unreviewed", 2), report("current", "current")],
      presentation: {stage:"results_ready",stage_label:"已有结果",summary:"已有结果",issue:null,
        next_actions:[{id:"download_report",label:"下载当前报告"}],diagnostics_available:false}}} />);
    expect(screen.queryByRole("button", {name:"下载当前报告"})).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", {name:"研究报告"}));
    expect(screen.getByRole("tab", {name:"研究报告"})).toHaveAttribute("aria-selected","true");
    expect(await screen.findByTitle("研究报告 · 资料版本 2")).toHaveAttribute("sandbox","");
    expect(fetchMock).toHaveBeenCalledWith("/api/sessions/session%20id/artifacts/current", expect.objectContaining({credentials:"same-origin"}));
    expect(fetchMock.mock.calls.every(([url]) => !String(url).includes("/old"))).toBe(true);
    expect(screen.queryByRole("link", {name:/下载历史原件/})).not.toBeInTheDocument();
  });
  it("previews only the latest report when interpretation changes within one data revision", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response("<!doctype html><h1>最新研究结果</h1>"));
    const older = report("older", "current");
    const latest = {...report("latest", "current"), research_report: {
      ...older.research_report!, snapshot_sha256: "b".repeat(64)}};
    render(<ResultsPane session={{...session, artifacts:[older, latest]}} />);
    await userEvent.click(screen.getByRole("tab", {name:"研究报告"}));
    expect(await screen.findAllByTitle("研究报告 · 资料版本 2")).toHaveLength(1);
    expect(screen.getByText("最新报告")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith("/api/sessions/session%20id/artifacts/latest",
      expect.objectContaining({credentials:"same-origin"}));
    expect(fetchMock.mock.calls.every(([url]) => !String(url).includes("/older"))).toBe(true);
    await userEvent.click(screen.getByText("历史报告 · 1 个文件"));
    expect(screen.getAllByRole("link").some(link => link.getAttribute("href")?.endsWith("/older"))).toBe(true);
    expect(fetchMock.mock.calls.every(([url]) => !String(url).includes("/older"))).toBe(true);
  });
  it("does not fetch or call a report current while an input correction is pending", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    render(<ResultsPane session={{...session, input_review_required:true, artifacts:[report("pending", "current")]}} />);
    await userEvent.click(screen.getByRole("tab", {name:"研究报告"}));
    expect(screen.getByText(/输入更正待确认，报告暂不作为当前结果展示/)).toBeVisible();
    expect(screen.queryByTitle(/当前研究报告/)).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

it.each([false, true])("shows QC figures once, independently of formal assessment (%s)", async (withAssessment) => {
  const artifact = (id: string, kind: Artifact["kind"], media_type: string): Artifact =>
    ({id, kind, media_type, name:id, tool_id:"P0-01", url:"/ignored"});
  const set = {...artifact("qc-set", "download", "application/json"),
    name:"qc_visualization_artifact_set.display-redacted.json"};
  const description = "基础 QC 指标已计算。候选规则：未选择（measurement_spec_not_selected）。未生成候选标记；不可用不代表零个异常。请维护者选择匹配规则。";
  vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({
    kind:"typed_figures", figures:[{
      contract:{visualization_id:"qc-v1", component_id:"bridge.qc.readiness-flow",
        scientific_status:"candidate", insight_title:"QC", takeaway:"Saved observation",
        accessibility:{alt_text:"Saved QC audit", long_description:description}},
      renders:[artifact("qc-svg", "figure", "image/svg+xml")],
      table:artifact("qc-table", "table", "text/tab-separated-values"),
      data:artifact("qc-data", "download", "application/json"),
    }],
  }));
  const assessment = withAssessment ? {
    evidence:[{alias:"qc", tool_id:"P0-01", state:"available", artifact_ids:[set.id], summary:{}}],
    portrait:[], freshness:{state:"current"},
  } as unknown as Session["assessment"] : null;
  render(<ResultsPane session={{...session, assessment, artifacts:[set]}} />);
  await userEvent.click(screen.getByRole("tab", {name:/图表/}));
  expect(await screen.findByRole("img", {name:"Saved QC audit"}, {timeout:10000})).toHaveAttribute(
    "src", "/api/sessions/session%20id/artifacts/qc-svg");
  expect(screen.getAllByRole("img", {name:"Saved QC audit"})).toHaveLength(1);
  await userEvent.click(screen.getByText("图表说明与限制"));
  expect(screen.getByText(description)).toBeVisible();
}, 15000);
