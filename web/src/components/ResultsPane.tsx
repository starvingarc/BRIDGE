import { Download, FileText, Image as ImageIcon, Table2 } from "lucide-react";
import { type KeyboardEvent, type PointerEvent, useEffect, useMemo, useState } from "react";
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
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>{rows[0].map((cell, index) => <th key={index}>{cell}</th>)}</tr>
        </thead>
        <tbody>
          {rows.slice(1).map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TextArtifact({ sessionId, artifact }: { sessionId: string; artifact: Artifact }) {
  const [state, setState] = useState<{
    loading: boolean;
    text: string;
    truncated: boolean;
    error: string | null;
  }>({
    loading: true,
    text: "",
    truncated: false,
    error: null,
  });

  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true, text: "", truncated: false, error: null });
    fetch(artifactUrl(sessionId, artifact.id), {
      credentials: "same-origin",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error();
        const { text, truncated } = await readBoundedText(response);
        setState({ loading: false, text, truncated, error: null });
      })
      .catch((error: unknown) => {
        if ((error as { name?: string }).name !== "AbortError") {
          setState({
            loading: false,
            text: "",
            truncated: false,
            error: "This artifact could not be previewed. Download it to inspect the original.",
          });
        }
      });
    return () => controller.abort();
  }, [artifact.id, sessionId]);

  if (state.loading) return <p className="artifact-loading">Loading preview…</p>;
  if (state.error) return <p className="artifact-error">{state.error}</p>;
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

export function ResultsPane({ session }: { session: Session | null }) {
  const [activeTab, setActiveTab] = useState<ArtifactKind>("figure");
  const artifacts = useMemo(() => artifactsForTab(session, activeTab), [activeTab, session]);

  return (
    <section className="results-pane" aria-label="Analysis results">
      <header className="results-header">
        <h1>Results</h1>
      </header>
      <div className="result-tabs" role="tablist" aria-label="Result type">
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
        {!session || !artifacts.length ? (
          <EmptyResults kind={activeTab} />
        ) : (
          <div className={`artifact-grid artifact-grid--${activeTab}`}>
            {artifacts.map((artifact) => {
              const url = artifactUrl(session.id, artifact.id);
              return (
                <article className="artifact-card" key={artifact.id}>
                  <header>
                    <div>
                      <h2>{artifact.name}</h2>
                      <p>{artifact.tool_id}</p>
                    </div>
                    <a href={url} download={artifact.name} aria-label={`Download ${artifact.name}`}>
                      <Download aria-hidden="true" />
                    </a>
                  </header>
                  {activeTab === "figure" ? (
                    <img src={url} alt={artifact.name} />
                  ) : activeTab === "download" ? (
                    <a className="download-row" href={url} download={artifact.name}>
                      <FileText aria-hidden="true" />
                      <span>Download original file</span>
                      <Download aria-hidden="true" />
                    </a>
                  ) : (
                    <TextArtifact sessionId={session.id} artifact={artifact} />
                  )}
                </article>
              );
            })}
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
