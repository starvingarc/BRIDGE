import { Download, FileText, Image as ImageIcon, Table2 } from "lucide-react";
import { type KeyboardEvent, type PointerEvent, type ReactNode, useEffect, useMemo, useState } from "react";
import type { Artifact, ArtifactKind, Session } from "../types";

const tabs: { kind: ArtifactKind; label: string }[] = [
  { kind: "figure", label: "Figures" },
  { kind: "table", label: "Tables" },
  { kind: "evidence", label: "Evidence" },
  { kind: "download", label: "Downloads" },
];

function artifactUrl(sessionId: string, artifactId: string) {
  return `/api/sessions/${encodeURIComponent(sessionId)}/artifacts/${encodeURIComponent(artifactId)}`;
}

function isParquet(artifact: Artifact) {
  return artifact.media_type === "application/vnd.apache.parquet"
    || artifact.media_type === "application/x-parquet"
    || /\.parquet$/i.test(artifact.name);
}

function isTextPreview(artifact: Artifact) {
  return artifact.media_type.startsWith("text/")
    || artifact.media_type.includes("json")
    || /\.(?:csv|tsv|json)$/i.test(artifact.name);
}

const MAX_ARTIFACT_PREVIEW_BYTES = 200_000;

export async function readBoundedText(response: Response, maxBytes = MAX_ARTIFACT_PREVIEW_BYTES) {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("stream_unavailable");
  const decoder = new TextDecoder();
  let text = "";
  let bytesRead = 0;
  let truncated = false;

  try {
    while (bytesRead < maxBytes) {
      const { done, value } = await reader.read();
      if (done) {
        text += decoder.decode();
        return { text, truncated };
      }
      const remaining = maxBytes - bytesRead;
      const chunk = value.byteLength > remaining ? value.subarray(0, remaining) : value;
      text += decoder.decode(chunk, { stream: true });
      bytesRead += chunk.byteLength;
      if (value.byteLength > remaining || bytesRead === maxBytes) {
        truncated = true;
        await reader.cancel();
        break;
      }
    }
  } finally {
    reader.releaseLock();
  }

  text += decoder.decode();
  return { text, truncated };
}

function figureGroupKey(artifact: Artifact) {
  return `${artifact.tool_id}:${artifact.name.replace(/\.(?:svg|png)$/i, "")}`;
}

function isSvg(artifact: Artifact) {
  return artifact.media_type === "image/svg+xml" || /\.svg$/i.test(artifact.name);
}

function artifactsForTab(session: Session | null, kind: ArtifactKind) {
  if (!session) return [];
  if (kind === "download") {
    return session.artifacts;
  }
  if (kind !== "figure") return session.artifacts.filter((artifact) => artifact.kind === kind);

  const figures = new Map<string, Artifact>();
  for (const artifact of session.artifacts) {
    if (artifact.kind !== "figure") continue;
    const key = figureGroupKey(artifact);
    const current = figures.get(key);
    if (!current || (!isSvg(current) && isSvg(artifact))) figures.set(key, artifact);
  }
  return Array.from(figures.values());
}

function parseDelimited(value: string, delimiter: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let index = 0; index < value.length && rows.length < 101; index += 1) {
    const char = value[index];
    if (char === "\"") {
      if (quoted && value[index + 1] === "\"") {
        cell += "\"";
        index += 1;
      } else {
        quoted = !quoted;
      }
    } else if (char === delimiter && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && value[index + 1] === "\n") index += 1;
      row.push(cell);
      rows.push(row.slice(0, 24));
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }
  if ((cell || row.length) && rows.length < 101) {
    row.push(cell);
    rows.push(row.slice(0, 24));
  }
  return rows;
}

type PreviewCell = string | number | boolean | null;

type ParquetPreview = {
  columns: string[];
  rows: PreviewCell[][];
  total_rows: number;
  total_columns: number;
  truncated: boolean;
};

function RenderedTable({ columns, rows }: { columns: string[]; rows: PreviewCell[][] }) {
  if (!columns.length) return <p className="artifact-text">Empty table (0 rows, 0 columns).</p>;
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>{columns.map((cell, index) => <th key={index}>{cell}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => <td key={cellIndex}>{cell === null ? "" : String(cell)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TablePreview({ text, mediaType }: { text: string; mediaType: string }) {
  const rows = useMemo(() => {
    if (mediaType.includes("json")) {
      try {
        const parsed = JSON.parse(text) as unknown;
        if (Array.isArray(parsed) && parsed.every((item) => item && typeof item === "object")) {
          const headers = Array.from(
            new Set(parsed.slice(0, 100).flatMap((item) => Object.keys(item as object))),
          ).slice(0, 24);
          return [
            headers,
            ...parsed
              .slice(0, 100)
              .map((item) => headers.map((header) => String((item as Record<string, unknown>)[header] ?? ""))),
          ];
        }
      } catch {
        return [];
      }
      return [];
    }
    return parseDelimited(text, mediaType.includes("csv") ? "," : "\t");
  }, [mediaType, text]);

  if (!rows.length) return <pre className="artifact-text">{text}</pre>;
  return <RenderedTable columns={rows[0]} rows={rows.slice(1)} />;
}

function DownloadFallback({ sessionId, artifact, message }: {
  sessionId: string;
  artifact: Artifact;
  message: string;
}) {
  return (
    <div className="artifact-error">
      <p>{message}</p>
      <a href={artifactUrl(sessionId, artifact.id)} download={artifact.name}>Download original file</a>
    </div>
  );
}

function TextArtifact({ sessionId, artifact }: { sessionId: string; artifact: Artifact }) {
  const [state, setState] = useState<{
    loading: boolean;
    text: string;
    truncated: boolean;
    error: boolean;
  }>({
    loading: true,
    text: "",
    truncated: false,
    error: false,
  });

  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    setState({ loading: true, text: "", truncated: false, error: false });
    fetch(artifactUrl(sessionId, artifact.id), {
      credentials: "same-origin",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error();
        const { text, truncated } = await readBoundedText(response);
        if (current) setState({ loading: false, text, truncated, error: false });
      })
      .catch((error: unknown) => {
        if (current && (error as { name?: string }).name !== "AbortError") {
          setState({ loading: false, text: "", truncated: false, error: true });
        }
      });
    return () => {
      current = false;
      controller.abort();
    };
  }, [artifact.id, sessionId]);

  if (state.loading) return <p className="artifact-loading">Loading preview…</p>;
  if (state.error) {
    return <DownloadFallback sessionId={sessionId} artifact={artifact} message="This artifact could not be previewed." />;
  }
  return (
    <>
      {state.truncated ? (
        <p className="artifact-truncated">Preview truncated. Download the original artifact for complete content.</p>
      ) : null}
      {artifact.kind === "table" ? (
        <TablePreview text={state.text} mediaType={artifact.media_type} />
      ) : (
        <pre className="artifact-text">{state.text}</pre>
      )}
    </>
  );
}

function isParquetPreview(value: unknown): value is ParquetPreview {
  if (!value || typeof value !== "object") return false;
  const preview = value as Partial<ParquetPreview>;
  return Array.isArray(preview.columns)
    && preview.columns.every((column) => typeof column === "string")
    && Array.isArray(preview.rows)
    && preview.rows.every((row) => Array.isArray(row) && row.every(
      (cell) => cell === null
        || typeof cell === "string"
        || typeof cell === "boolean"
        || (typeof cell === "number" && Number.isFinite(cell) && (
          !Number.isInteger(cell) || Number.isSafeInteger(cell)
        )),
    ))
    && Number.isSafeInteger(preview.total_rows)
    && Number.isSafeInteger(preview.total_columns)
    && typeof preview.truncated === "boolean";
}

function ParquetArtifact({ sessionId, artifact }: { sessionId: string; artifact: Artifact }) {
  const [state, setState] = useState<{
    loading: boolean;
    preview: ParquetPreview | null;
    error: boolean;
  }>({ loading: true, preview: null, error: false });

  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    setState({ loading: true, preview: null, error: false });
    fetch(`${artifactUrl(sessionId, artifact.id)}/preview`, {
      credentials: "same-origin",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error();
        const preview: unknown = await response.json();
        if (!isParquetPreview(preview)) throw new Error();
        if (current) setState({ loading: false, preview, error: false });
      })
      .catch((error: unknown) => {
        if (current && (error as { name?: string }).name !== "AbortError") {
          setState({ loading: false, preview: null, error: true });
        }
      });
    return () => {
      current = false;
      controller.abort();
    };
  }, [artifact.id, sessionId]);

  if (state.loading) return <p className="artifact-loading">Loading preview…</p>;
  if (state.error || !state.preview) {
    return <DownloadFallback sessionId={sessionId} artifact={artifact} message="This artifact could not be previewed." />;
  }
  return (
    <>
      {state.preview.truncated ? (
        <p className="artifact-truncated">
          Preview truncated. Showing {state.preview.rows.length} of {state.preview.total_rows} rows and {state.preview.columns.length} of {state.preview.total_columns} columns. Download the original artifact for complete content.
        </p>
      ) : null}
      <RenderedTable columns={state.preview.columns} rows={state.preview.rows} />
    </>
  );
}

function ResearchSnapshotView({ sessionId, artifact }: { sessionId: string; artifact: Artifact }) {
  const [content, setContent] = useState<{ texts: string[]; missing: number; error: boolean } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    setContent(null);
    fetch(artifactUrl(sessionId, artifact.id), { credentials: "same-origin", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("report_unavailable");
        const { text, truncated } = await readBoundedText(response, 8_000_000);
        if (truncated) throw new Error("report_too_large");
        const snapshot = JSON.parse(text);
        const binding = artifact.research_report;
        if (!binding || snapshot.snapshot_sha256 !== binding.snapshot_sha256
            || snapshot.input_revision !== binding.input_revision || snapshot.graph_version !== binding.graph_version
            || snapshot.audience !== "internal_research" || snapshot.scientific_validation !== "not_qualified"
            || typeof snapshot.report_draft_json !== "string") throw new Error("report_binding_invalid");
        const draft = JSON.parse(snapshot.report_draft_json);
        const requirements = JSON.parse(snapshot.evidence_requirement_set_json);
        if (!Array.isArray(draft.claim_blocks) || draft.claim_blocks.length > 5000
            || !draft.claim_blocks.every((row: { text?: unknown }) => typeof row.text === "string")
            || !Array.isArray(requirements.requirements)) throw new Error("report_shape_invalid");
        if (current) setContent({
          texts: draft.claim_blocks.map((row: { text: string }) => row.text),
          missing: requirements.requirements.filter((row: { state?: string }) => row.state === "open").length,
          error: false,
        });
      }).catch((error: unknown) => {
        if (current && (error as { name?: string }).name !== "AbortError") {
          setContent({ texts: [], missing: 0, error: true });
        }
      });
    return () => { current = false; controller.abort(); };
  }, [sessionId, artifact.id, artifact.research_report?.snapshot_sha256]);
  if (!content) return <p>正在读取已核验报告…</p>;
  if (content.error) return <p>无法确认报告快照，请下载原始附件核对；当前不展示未绑定的内容。</p>;
  return <section aria-label="同版本研究报告">
    <p>以下文字与离线报告读取同一份证据快照。尚有 {content.missing} 项开放证据要求。</p>
    {content.texts.map((text, index) => <p key={index}>{text}</p>)}
  </section>;
}

export function ArtifactCard({ sessionId, artifact, view = artifact.kind }: {
  sessionId: string; artifact: Artifact; view?: ArtifactKind;
}) {
  const url = artifactUrl(sessionId, artifact.id);
  return <article className="artifact-card">
    <header><div><h2>{artifact.name}</h2><p>{artifact.research_report
      ? `研究报告 · 输入修订 ${artifact.research_report.input_revision} · 证据图版本 ${artifact.research_report.graph_version}`
      : artifact.tool_id}</p></div>
      <a href={url} download={artifact.name} aria-label={`Download ${artifact.name}`}><Download aria-hidden="true" /></a>
    </header>
    {artifact.research_report && artifact.media_type === "application/json"
      ? <ResearchSnapshotView sessionId={sessionId} artifact={artifact} />
      : view === "figure" ? <img src={url} alt={artifact.name} />
      : view === "download" ? <a className="download-row" href={url} download={artifact.name}>
        <FileText aria-hidden="true" /><span>Download original file</span><Download aria-hidden="true" /></a>
      : isParquet(artifact) ? <ParquetArtifact sessionId={sessionId} artifact={artifact} />
      : isTextPreview(artifact) ? <TextArtifact sessionId={sessionId} artifact={artifact} />
      : <DownloadFallback sessionId={sessionId} artifact={artifact} message="A browser preview is not available for this artifact." />}
  </article>;
}

function EmptyResults({ kind }: { kind: ArtifactKind }) {
  const Icon =
    kind === "figure" ? ImageIcon : kind === "table" ? Table2 : kind === "download" ? Download : FileText;
  const label = tabs.find((tab) => tab.kind === kind)?.label.toLowerCase();
  return (
    <div className="results-empty">
      <div className="results-empty-icon">
        <Icon aria-hidden="true" />
      </div>
      <h2>{kind === "figure" ? "Results will appear here" : `No ${label} yet`}</h2>
      <p>
        {kind === "figure"
          ? "Figures are generated by the analysis tools."
          : "Results produced by approved analysis tools will appear here."}
      </p>
    </div>
  );
}

export function ResultsPane({ session, overview }: { session: Session | null; overview?: ReactNode }) {
  const [activeTab, setActiveTab] = useState<ArtifactKind | "overview">(overview ? "overview" : "figure");
  const artifacts = useMemo(() => activeTab === "overview" ? [] : artifactsForTab(session, activeTab), [activeTab, session]);

  return (
    <section className="results-pane" aria-label="Analysis results">
      <header className="results-header">
        <h1>{overview ? "产品评估" : "Results"}</h1>
      </header>
      <div className="result-tabs" role="tablist" aria-label="Result type">
        {overview ? <button type="button" role="tab" aria-selected={activeTab === "overview"}
          className={activeTab === "overview" ? "result-tab--active" : ""}
          onClick={() => setActiveTab("overview")}>评估概览</button> : null}
        {tabs.map((tab) => {
          const count = artifactsForTab(session, tab.kind).length;
          return (
            <button
              key={tab.kind}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.kind}
              className={activeTab === tab.kind ? "result-tab--active" : ""}
              onClick={() => setActiveTab(tab.kind)}
            >
              {tab.label}
              {count ? <span>{count}</span> : null}
            </button>
          );
        })}
      </div>
      <div className="results-content" role="tabpanel">
        {activeTab === "overview" ? overview : !session || !artifacts.length ? (
          <EmptyResults kind={activeTab} />
        ) : (
          <div className={`artifact-grid artifact-grid--${activeTab}`}>
            {artifacts.map((artifact) => <ArtifactCard key={artifact.id} sessionId={session.id} artifact={artifact} view={activeTab} />)}
          </div>
        )}
      </div>
    </section>
  );
}

type DividerProps = {
  width: number;
  onWidth: (width: number) => void;
};

function clampResultsWidth(width: number) {
  return Math.max(360, Math.min(Math.max(360, window.innerWidth - 560), width));
}

export function WorkbenchDivider({ width, onWidth }: DividerProps) {
  const startResize = (event: PointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    const startX = event.clientX;
    const startWidth = width;
    const move = (moveEvent: globalThis.PointerEvent) => {
      onWidth(clampResultsWidth(startWidth - (moveEvent.clientX - startX)));
    };
    const finish = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", finish);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", finish);
  };

  const resizeWithKeyboard = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    onWidth(clampResultsWidth(width + (event.key === "ArrowLeft" ? 24 : -24)));
  };

  return (
    <div
      className="workbench-divider"
      role="separator"
      aria-label="Resize results"
      aria-orientation="vertical"
      tabIndex={0}
      onPointerDown={startResize}
      onKeyDown={resizeWithKeyboard}
    >
      <span>
        <i />
        <i />
        <i />
      </span>
    </div>
  );
}
